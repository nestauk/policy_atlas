"""The longlist read models and routes (task 045 Phase 6.1, S12; deliverable 11).

The contract's API bullet and its records bullet: the two GETs are org-scoped
reads in the ADR 0033 style and public-readable like the artefact; a link
grants no read of options; 404 before a longlist exists; the list's fields
match the stored rows; the card carries every section's data ("checked at
assessment", the in-scope check, the uncollapsed documents with inherited
labels through the resolver) and never the words "how sure"; a user
exclusion carries its reason, is reversible and survives a rebuild's
constrain; *add* proposes a design, mints *added by you* and opens a child
walk with no parent; the three buttons are ``run_active`` while a parentless
walk runs and 422 on an Evidence search task, and each writes one History
event as the user's turn.

The longlist is built by the real component and constrain on scripted
backends (``tests/options_scoping/test_longlist.py``'s fixture), committed so
the application's own connections see it.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.engine import Connection, Engine

from policy_atlas.api.deps import get_agent_backend, get_runner_backends
from policy_atlas.api.readmodels import repository
from policy_atlas.core.schema import (
    capability_run,
    evidence_scope,
    longlist_result,
    option,
    option_membership,
    option_relation,
    runs,
    source_classification_result,
    task,
    task_link,
    task_source_snapshot,
)
from policy_atlas.options_scoping.constrain.constrain import (
    IN_SCOPE_EVIDENCE_KEY,
    ConstrainContext,
    constrain_scope,
)
from policy_atlas.options_scoping.constrain.constrain_prompt import ConstrainResponse
from policy_atlas.options_scoping.longlist.longlist_backend import StubLonglistBackend
from policy_atlas.runtime.agent_backend import StubAgentBackend
from policy_atlas.runtime.option_design_prompt import OptionDesignWire
from policy_atlas.runtime.scoping_plan import CHECKED_AT_BY_KIND, ScopingConstraint, ScopingPlan
from tests.api.org_support import (
    Principal,
    make_org,
    ops_enrol,
    seeded,
    tenancy_client,
)
from tests.api.resource_support import api_client, create_task
from tests.helpers import delete_task_data, now
from tests.options_scoping.test_longlist import (
    RCT,
    _discovered,
    _linked_deep_task,
    _Scripted,
    _Walk,
)
from tests.runtime.test_baseline_gate import scoping_plan
from tests.runtime.test_runner import _runner_backends

# --- cleanup -----------------------------------------------------------------------


def _all_task_ids(engine: Engine) -> set[uuid.UUID]:
    with engine.connect() as conn:
        return {row[0] for row in conn.execute(select(task.c.task_id))}


def _await_walks_ended(engine: Engine, task_ids: list[uuid.UUID]) -> None:
    """Let any option search a test opened finish before its task is deleted."""
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        with engine.connect() as conn:
            active = conn.execute(
                select(capability_run.c.capability_run_id)
                .where(capability_run.c.task_id.in_(task_ids))
                .where(capability_run.c.status.in_(("running", "paused")))
            ).first()
        if active is None:
            return
        time.sleep(0.1)


@pytest.fixture(autouse=True)
def _remove_committed_tasks(engine: Engine) -> Iterator[None]:
    """Hard-delete every task these tests commit (a left scoping walk blocks downgrades)."""
    before = _all_task_ids(engine)
    yield
    created = list(_all_task_ids(engine) - before)
    _await_walks_ended(engine, created)
    with engine.begin() as conn:
        conn.execute(
            capability_run.update()
            .where(capability_run.c.task_id.in_(created))
            .where(capability_run.c.status.in_(("running", "paused")))
            .values(status="aborted", ended_at=now())
        )
        conn.execute(task_link.delete().where(task_link.c.source_task_id.in_(created)))
        conn.execute(task_link.delete().where(task_link.c.target_task_id.in_(created)))
        # A linked finding's membership names its source task.
        conn.execute(option_membership.delete().where(option_membership.c.task_id.in_(created)))
        # A target's row for a snapshot its source also holds (inherit copied
        # it) goes first, so each task's delete removes only its own snapshots.
        other = task_source_snapshot.alias("other")
        conn.execute(
            task_source_snapshot.delete()
            .where(task_source_snapshot.c.task_id.in_(created))
            .where(
                select(other.c.task_source_snapshot_id)
                .where(other.c.source_snapshot_id == task_source_snapshot.c.source_snapshot_id)
                .where(other.c.task_id != task_source_snapshot.c.task_id)
                .where(other.c.origin == "acquired")
                .where(other.c.ingested_at < task_source_snapshot.c.ingested_at)
                .exists()
            )
        )
        for task_id in created:
            delete_task_data(conn, task_id)


# --- the fixture -------------------------------------------------------------------

REQUIREMENT = "Delivered through Jobcentres"
PREFERENCE = "Low cost to run"
RESTRICTION = "Published since 2020"


def _plan() -> ScopingPlan:
    """A plan with a requirement, a preference and a year restriction."""
    base = scoping_plan()
    extra = [
        ScopingConstraint(
            text=REQUIREMENT,
            kind="requirement",
            origin="your_call",
            checked_at=CHECKED_AT_BY_KIND["requirement"],
        ),
        ScopingConstraint(
            text=PREFERENCE,
            kind="preference",
            origin="your_call",
            checked_at=CHECKED_AT_BY_KIND["preference"],
        ),
        ScopingConstraint(
            text=RESTRICTION,
            kind="evidence_restriction",
            origin="your_call",
            checked_at=CHECKED_AT_BY_KIND["evidence_restriction"],
            published_after="2020-01-01",
        ),
    ]
    return base.model_copy(update={"constraints": [*base.constraints, *extra]})


@dataclass
class _Built:
    task_id: uuid.UUID
    walk_id: uuid.UUID
    scope_id: uuid.UUID
    run_id: uuid.UUID
    source_task_id: uuid.UUID
    options: dict[str, uuid.UUID]


class _Breaks(StubLonglistBackend):
    """The stub's constrain, with the first requirement broken for some options."""

    def __init__(self, breaking: set[uuid.UUID]) -> None:
        super().__init__()
        self.breaking = {str(option_id) for option_id in breaking}

    def constrain(
        self,
        *,
        plan: dict[str, object],
        requirements: list[dict[str, str]],
        preferences: list[dict[str, str]],
        options: list[dict[str, object]],
    ) -> tuple[ConstrainResponse, Any]:
        response, usage = super().constrain(
            plan=plan, requirements=requirements, preferences=preferences, options=options
        )
        for wire in response.options:
            if wire.option_id in self.breaking:
                wire.judgements[0] = wire.judgements[0].model_copy(
                    update={"verdict": "breaks", "reason": "It is not run through Jobcentres."}
                )
        return response, usage


def _constrain(engine: Engine, built: _Built, backend: StubLonglistBackend) -> None:
    """Run the walk's constrain step again (a rebuild's last step)."""
    with engine.begin() as conn:
        run_id = uuid.uuid4()
        conn.execute(
            runs.insert().values(
                run_id=run_id,
                task_id=built.task_id,
                status="running",
                started_at=now(),
                capability_run_id=built.walk_id,
            )
        )
        constrain_scope(
            conn,
            task_id=built.task_id,
            run_id=run_id,
            context=ConstrainContext(scope_id=built.scope_id, intent="", context={}),
            backend=backend,
        )


def _inherit_label(conn: Connection, *, target: _Walk, source_task_id: uuid.UUID) -> uuid.UUID:
    """The target holds the linked task's document (inherit copied it); the source classified it.

    Returns:
        The target's own ``task_source_snapshot`` row for the document.
    """
    source_tss = conn.execute(
        select(task_source_snapshot).where(task_source_snapshot.c.task_id == source_task_id)
    ).one()
    source_walk = conn.execute(
        select(capability_run).where(capability_run.c.task_id == source_task_id)
    ).one()
    source_run = conn.execute(
        select(runs.c.run_id).where(runs.c.task_id == source_task_id)
    ).scalar_one()
    conn.execute(
        source_classification_result.insert().values(
            source_classification_result_id=uuid.uuid4(),
            evidence_scope_id=source_walk.evidence_scope_id,
            task_source_snapshot_id=source_tss.task_source_snapshot_id,
            task_id=source_task_id,
            classified_by_run_id=source_run,
            primary_evidence_type=RCT,
            classified_at=now(),
        )
    )
    own = uuid.uuid4()
    conn.execute(
        task_source_snapshot.insert().values(
            task_source_snapshot_id=own,
            task_id=target.task_id,
            source_snapshot_id=source_tss.source_snapshot_id,
            origin="acquired",
            run_id=None,
            ingested_at=now(),
        )
    )
    return own


def _build(
    engine: Engine, *, owner: str, org_id: uuid.UUID | None = None, linked: bool = True
) -> _Built:
    """A built, constrained longlist on a finished longlist walk, owned by ``owner``.

    ``linked=False`` leaves out the linked Evidence search task (an option
    search's walk would otherwise screen the snapshot the two tasks share,
    which the teardown cannot then remove).
    """
    with engine.begin() as conn:
        walk = _Walk(conn, _plan())
        guarantee = walk.option("Youth guarantee", origin="added_by_you")
        uk = walk.doc(
            {"title": "UK guarantee evaluation", "doi": "10.1/uk", "publication_year": 2022}
        )
        preprint = walk.doc(
            {
                "title": "UK guarantee preprint",
                "doi": "https://doi.org/10.1/UK",
                "publication_year": 2022,
            }
        )
        old = walk.doc({"title": "An old Danish study", "publication_year": 2010})
        # Both DOI twins are rated: coverage reads the first twin's labels.
        walk.classify(uk, RCT, 4)
        walk.classify(preprint, RCT, 4)
        walk.record(
            uk,
            "youth guarantee",
            study_geography="England",
            setting="Jobcentres",
            population="16 to 24 year olds",
            outcome="employment",
        )
        walk.record(preprint, "youth guarantee flagged", study_geography="United Kingdom")
        walk.record(old, "mentoring", role="described", study_geography="Denmark")
        walk.record(
            uk, "guarantee package", is_bundle=True, components=["Youth guarantee", "mentoring"]
        )
        walk.rollup(walk.scope_id, [uk, preprint, old])
        source_task_id = walk.task_id
        if linked:
            source_task_id = _linked_deep_task(conn, walk, "youth guarantee")
            _inherit_label(conn, target=walk, source_task_id=source_task_id)
        backend = _Scripted(
            discovered=[
                _discovered("Mentoring"),
                _discovered(
                    "Guarantee package",
                    is_bundle=True,
                    components=["Mentoring", "Youth guarantee"],
                ),
            ],
            routes={
                "youth guarantee": ("Youth guarantee", False),
                "youth guarantee flagged": ("Youth guarantee", True),
                "mentoring": ("Mentoring", False),
                "guarantee package": ("Guarantee package", False),
            },
            typings={
                "Mentoring": {
                    "primary_lever_type": None,
                    "secondary_lever_types": [],
                    "none_fits_reason": "Mentoring is delivered by volunteers.",
                }
            },
        )
        run_id, _ = walk.build(backend)
        conn.execute(
            capability_run.update()
            .where(capability_run.c.capability_run_id == walk.walk_id)
            .values(status="succeeded", ended_at=now())
        )
        conn.execute(
            update(task)
            .where(task.c.task_id == walk.task_id)
            .values(owner_user_id=owner, org_id=org_id, visibility="org" if org_id else "private")
        )
        options = {
            row.name: row.option_id
            for row in conn.execute(select(option).where(option.c.task_id == walk.task_id))
        }
        assert options["Youth guarantee"] == guarantee
    built = _Built(
        task_id=walk.task_id,
        walk_id=walk.walk_id,
        scope_id=walk.scope_id,
        run_id=run_id,
        source_task_id=source_task_id,
        options=options,
    )
    _constrain(engine, built, StubLonglistBackend())
    return built


def _clients(
    tmp_path: Path,
    engine: Engine,
    overrides: dict[Callable[..., object], Callable[..., object]] | None = None,
) -> Any:
    return tenancy_client(tmp_path, count=3, overrides=overrides)


def _org_build(
    engine: Engine, owner: Principal, colleague: Principal, *, linked: bool = True
) -> _Built:
    with seeded(engine) as conn:
        org_id = make_org(conn)
        ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
        ops_enrol(conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague")
    return _build(engine, owner=owner.user_id, org_id=org_id, linked=linked)


def _longlist(client: TestClient, task_id: uuid.UUID, headers: dict[str, str] | None) -> Any:
    return client.get(f"/api/v1/tasks/{task_id}/longlist", headers=headers)


def _card(client: TestClient, built: _Built, name: str, headers: dict[str, str] | None) -> Any:
    return client.get(
        f"/api/v1/tasks/{built.task_id}/options/{built.options[name]}", headers=headers
    )


# --- reads: tenancy, public, links ---------------------------------------------------


def test_the_reads_are_org_scoped_and_public_like_the_artefact(
    engine: Engine, tmp_path: Path
) -> None:
    with _clients(tmp_path, engine) as (client, (owner, colleague, stranger)):
        built = _org_build(engine, owner, colleague)
        for caller in (owner, colleague):
            assert _longlist(client, built.task_id, caller.headers).status_code == 200
            assert _card(client, built, "Mentoring", caller.headers).status_code == 200
        absent = client.get(
            f"/api/v1/tasks/{uuid.uuid4()}/longlist", headers=stranger.headers
        )
        hidden = _longlist(client, built.task_id, stranger.headers)
        assert hidden.status_code == absent.status_code == 404
        assert hidden.content == absent.content
        assert _card(client, built, "Mentoring", stranger.headers).status_code == 404
        assert _longlist(client, built.task_id, None).status_code == 404

        shared = client.patch(
            f"/api/v1/tasks/{built.task_id}", headers=owner.headers, json={"is_public": True}
        )
        assert shared.status_code == 200, shared.text
        for headers in (None, stranger.headers):
            assert _longlist(client, built.task_id, headers).status_code == 200
            assert _card(client, built, "Mentoring", headers).status_code == 200
        # Public read is a read: the buttons stay the owner's.
        refused = client.post(
            f"/api/v1/tasks/{built.task_id}/options/{built.options['Mentoring']}/exclude",
            headers=stranger.headers,
            json={"reason": "Not mine to decide."},
        )
        assert refused.status_code == 404
        colleague_refused = client.post(
            f"/api/v1/tasks/{built.task_id}/options/{built.options['Mentoring']}/exclude",
            headers=colleague.headers,
            json={"reason": "Not mine to decide."},
        )
        assert colleague_refused.status_code == 403


def test_a_link_grants_no_read_of_the_targets_options(engine: Engine, tmp_path: Path) -> None:
    """A user who can read the linked source task only is refused the target's longlist."""
    with _clients(tmp_path, engine) as (client, (owner, colleague, source_owner)):
        built = _org_build(engine, owner, colleague)
        with engine.begin() as conn:
            conn.execute(
                update(task)
                .where(task.c.task_id == built.source_task_id)
                .values(owner_user_id=source_owner.user_id)
            )
        source = client.get(
            f"/api/v1/tasks/{built.source_task_id}", headers=source_owner.headers
        )
        assert source.status_code == 200
        assert _longlist(client, built.task_id, source_owner.headers).status_code == 404
        assert _card(client, built, "Youth guarantee", source_owner.headers).status_code == 404


def test_no_longlist_is_a_404_and_an_unknown_option_too(engine: Engine, tmp_path: Path) -> None:
    with api_client(tmp_path) as (client, owner, _other):
        task_id = create_task(client, owner)
        assert client.get(f"/api/v1/tasks/{task_id}/longlist", headers=owner).status_code == 404
        unknown = client.get(f"/api/v1/tasks/{task_id}/options/{uuid.uuid4()}", headers=owner)
        assert unknown.status_code == 404


# --- the list ----------------------------------------------------------------------


def test_the_list_matches_the_stored_rows(engine: Engine, tmp_path: Path) -> None:
    with _clients(tmp_path, engine) as (client, (owner, colleague, _)):
        built = _org_build(engine, owner, colleague)
        body = _longlist(client, built.task_id, owner.headers).json()
        with engine.connect() as conn:
            result = conn.execute(
                select(longlist_result).where(longlist_result.c.task_id == built.task_id)
            ).one()
            rows = {
                row.option_id: row
                for row in conn.execute(select(option).where(option.c.task_id == built.task_id))
            }
            relations = list(
                conn.execute(
                    select(option_relation).where(option_relation.c.task_id == built.task_id)
                )
            )
        assert body["run_id"] == str(built.run_id)
        assert body["capability_run_id"] == str(built.walk_id)
        assert body["plan_version"] == body["built_from_plan_version"] == 2
        assert body["current_plan_version"] == 2
        assert body["depth_label"] == "scoping pass"
        assert body["where_label"] == "United Kingdom"
        assert body["lever_types"][0] == "regulate" and len(body["lever_types"]) == 10
        assert [band["key"] for band in body["ambition_bands"]] == [
            "do_minimum",
            "incremental",
            "structural",
        ]
        counts = body["counts"]
        assert counts["options"] == len(rows) == 3
        assert counts["themes"] == len(result.themes)
        assert counts["included"] == sum(1 for r in rows.values() if r.state == "included")
        assert counts["excluded"] == sum(1 for r in rows.values() if r.state == "excluded")
        assert counts["no_in_scope"] == 1  # Mentoring: its only document is from 2010
        assert counts["unclustered"] == result.counts["unclustered"]
        assert counts["not_an_option"] == result.counts["not_an_option"]
        assert counts["none_fits"] == 1

        themed = [oid for theme in body["themes"] for oid in theme["option_ids"]]
        assert sorted(themed + body["unthemed_option_ids"]) == sorted(str(o) for o in rows)
        assert [o["option_id"] for o in body["options"]] == themed + body["unthemed_option_ids"]

        by_name = {o["name"]: o for o in body["options"]}
        guarantee = by_name["Youth guarantee"]
        coverage = result.coverage[str(built.options["Youth guarantee"])]
        assert guarantee["origin"] == "added_by_you"
        assert guarantee["state"] == "included" and guarantee["exclusion"] is None
        assert guarantee["document_count"] == coverage["documents"] == 2
        assert guarantee["evaluated_count"] == coverage["role"]["evaluated"]
        assert guarantee["where_tried"] == {
            "where": coverage["where_tried"]["where"],
            "comparable": coverage["where_tried"]["comparable"],
            "other": coverage["where_tried"]["other"],
            "unknown": coverage["where_tried"]["unknown"],
        }
        assert guarantee["settings"] == ["Jobcentres"]
        assert guarantee["primary_lever_type"] == "subsidise"
        assert guarantee["ambition"] == "incremental"
        assert guarantee["is_entrant_with_no_documents"] is False

        mentoring = by_name["Mentoring"]
        assert mentoring["no_in_scope_evidence"] is True
        assert mentoring["restriction_text"] == RESTRICTION
        assert mentoring["primary_lever_type"] is None
        assert mentoring["lever_none_fits_reason"] == "Mentoring is delivered by volunteers."
        assert mentoring["where_tried"]["comparable"] == 1  # Denmark

        package = by_name["Guarantee package"]
        expected = {
            (str(r.from_option_id), str(r.to_option_id)) for r in relations if r.kind == "part_of"
        }
        seen = {
            (o["option_id"], rel["other_option_id"])
            for o in body["options"]
            for rel in o["relations"]
            if rel["kind"] == "part_of"
        }
        assert seen == expected
        assert {rel["other_name"] for rel in package["relations"]} == {
            "Mentoring",
            "Youth guarantee",
        }
        assert {rel["kind"] for rel in package["relations"]} == {"has_part"}


# --- the card ----------------------------------------------------------------------


def test_the_card_carries_every_section_and_never_how_sure(
    engine: Engine, tmp_path: Path
) -> None:
    with _clients(tmp_path, engine) as (client, (owner, colleague, _)):
        built = _org_build(engine, owner, colleague)
        response = _card(client, built, "Youth guarantee", owner.headers)
        assert response.status_code == 200
        card = response.json()
        assert card["design"]["name"] == "Youth guarantee"
        assert card["design_features"] == ["Youth guarantee feature"]
        assert card["transferability"] == "checked at assessment"
        assert card["depth_label"] == "scoping pass"
        assert card["run_id"] == str(built.run_id) and card["plan_version"] == 2
        # Judgements: the requirement, then the three screens; the guess on the
        # preference; no guess for the transferability preference.
        assert [j["constraint_id"] for j in card["judgements"]] == [
            "req-1",
            "relevant",
            "distinct",
            "in_scope",
        ]
        assert card["judgements"][0]["constraint_text"] == REQUIREMENT
        assert [g["constraint_id"] for g in card["guesses"]] == ["pref-1"]
        assert card["guesses"][0]["constraint_text"] == PREFERENCE
        # Every document passes the restriction: the check ran, nothing is marked.
        assert card["in_scope"]["restriction"] == RESTRICTION
        assert card["in_scope"]["in_scope_documents"] == card["in_scope"]["documents"] > 0
        assert card["no_in_scope_evidence"] is False and card["restriction_text"] is None
        evidence = card["evidence"]
        assert evidence["documents"] == 2
        # The DOI twins count once; the linked document's tier did not come across.
        assert evidence["by_tier"] == {"Strong": 1, "not rated": 1}
        assert evidence["by_evidence_type"] == {RCT: 2}
        assert evidence["inherited_labels"] == 1
        assert evidence["flagged_not_stated"] == 0  # the DOI twin states the feature
        assert evidence["by_role"]["evaluated"] >= 1
        assert evidence["populations"] == ["16 to 24 year olds"]
        # The documents: one per membership row, never DOI-collapsed.
        documents = card["documents"]
        with engine.connect() as conn:
            members = conn.execute(
                select(option_membership).where(
                    option_membership.c.option_id == built.options["Youth guarantee"]
                )
            ).all()
        assert len(documents) == len(members) == 4
        titles = sorted(d["title"] for d in documents)
        assert titles == [
            "A deep read",
            "A deep read",
            "UK guarantee evaluation",
            "UK guarantee preprint",
        ]
        inherited = [d for d in documents if d["title"] == "A deep read"]
        assert {d["source_task_id"] for d in inherited} == {str(built.source_task_id)}
        assert {d["role"] for d in inherited} == {"evaluated", "described"}
        # The label came through the link, read by the resolver.
        assert {d["evidence_type"] for d in inherited} == {RCT}
        assert all(d["task_source_snapshot_id"] is not None for d in inherited)
        evaluation = next(d for d in documents if d["title"] == "UK guarantee evaluation")
        assert evaluation["tier"] == "Strong" and evaluation["where_tried_group"] == "where"
        assert evaluation["source_task_id"] is None
        preprint = next(d for d in documents if d["title"] == "UK guarantee preprint")
        assert preprint["design_feature_not_stated"] is True

        mentoring = _card(client, built, "Mentoring", owner.headers).json()
        assert mentoring["in_scope"] == {
            "restriction": RESTRICTION,
            "in_scope_documents": 0,
            "documents": 1,
        }
        assert {
            j["constraint_id"]: j["verdict"] for j in mentoring["judgements"]
        }["distinct"] == "passes"
        for body in (
            _longlist(client, built.task_id, owner.headers).text,
            *(_card(client, built, name, owner.headers).text for name in built.options),
        ):
            assert "how sure" not in body.lower()


def test_the_transferability_row_follows_the_plan(conn: Connection) -> None:
    """No default preference on the plan: the card carries no transferability row."""
    plan = _plan()
    stripped = plan.model_copy(
        update={
            "constraints": [c for c in plan.constraints if c.default is None],
            "removed_defaults": ["transferability"],
        }
    )
    walk = _Walk(conn, stripped)
    option_id = walk.option("Youth guarantee", origin="added_by_you")
    walk.build(_Scripted())
    card = repository.option_out(conn, walk.task_id, option_id)
    assert card is not None
    assert card.transferability is None
    assert card.document_count == 0 and card.is_entrant_with_no_documents is True


def test_the_in_scope_key_is_constrains(conn: Connection) -> None:
    assert repository.LONGLIST_IN_SCOPE_KEY == IN_SCOPE_EVIDENCE_KEY


def test_an_option_added_since_the_build_reads_with_an_empty_profile(conn: Connection) -> None:
    walk = _Walk(conn)
    walk.option("Youth guarantee", origin="added_by_you")
    walk.build(_Scripted())
    late = walk.option("Wage subsidy", origin="added_by_you")
    listed = repository.longlist_out(conn, walk.task_id)
    assert listed is not None
    assert listed.unthemed_option_ids[-1] == late
    card = repository.option_out(conn, walk.task_id, late)
    assert card is not None
    assert card.document_count == 0 and card.documents == []
    assert card.evidence.where_tried.model_dump() == {
        "where": 0,
        "comparable": 0,
        "other": 0,
        "unknown": 0,
    }


# --- the buttons -------------------------------------------------------------------


def _decisions(client: TestClient, built: _Built, headers: dict[str, str]) -> list[dict[str, Any]]:
    response = client.get(
        f"/api/v1/tasks/{built.task_id}/decisions?page_size=200", headers=headers
    )
    assert response.status_code == 200, response.text
    return [d for d in response.json()["data"] if d["kind"].startswith("option.")]


def test_exclude_records_the_reason_and_include_reverses_it(
    engine: Engine, tmp_path: Path
) -> None:
    with _clients(tmp_path, engine) as (client, (owner, colleague, _)):
        built = _org_build(engine, owner, colleague)
        oid = built.options["Youth guarantee"]
        excluded = client.post(
            f"/api/v1/tasks/{built.task_id}/options/{oid}/exclude",
            headers=owner.headers,
            json={"reason": "  Too costly   for us. "},
        )
        assert excluded.status_code == 200, excluded.text
        card = excluded.json()
        assert card["state"] == "excluded"
        assert card["exclusion"] == {
            "constraint": "your decision",
            "reason": "Too costly for us.",
            "by": "user",
        }
        listed = _longlist(client, built.task_id, owner.headers).json()
        assert listed["counts"]["excluded"] == 1

        history = _decisions(client, built, owner.headers)
        assert len(history) == 1
        assert history[0]["kind"] == "option.excluded"
        assert history[0]["decided_by"] == "user"
        assert "Youth guarantee" in history[0]["summary"]
        assert "Too costly for us." in history[0]["summary"]

        included = client.post(
            f"/api/v1/tasks/{built.task_id}/options/{oid}/include", headers=owner.headers
        )
        assert included.status_code == 200, included.text
        assert included.json()["state"] == "included"
        assert included.json()["exclusion"] is None
        history = _decisions(client, built, owner.headers)
        assert [h["kind"] for h in history] == ["option.included", "option.excluded"]
        assert history[0]["decided_by"] == "user"

        blank = client.post(
            f"/api/v1/tasks/{built.task_id}/options/{oid}/exclude",
            headers=owner.headers,
            json={"reason": "   "},
        )
        # A reason is optional (owner, 2026-09-24): a blank one is recorded empty.
        assert blank.status_code == 200
        assert blank.json()["exclusion"]["reason"] == ""
        unknown = client.post(
            f"/api/v1/tasks/{built.task_id}/options/{uuid.uuid4()}/exclude",
            headers=owner.headers,
            json={"reason": "Why not."},
        )
        assert unknown.status_code == 404
        assert len(_decisions(client, built, owner.headers)) == 3


def test_user_state_survives_a_rebuilds_constrain(engine: Engine, tmp_path: Path) -> None:
    """5.3's rule: a user exclusion stands, and a user inclusion is never re-excluded."""
    with _clients(tmp_path, engine) as (client, (owner, colleague, _)):
        built = _org_build(engine, owner, colleague)
        guarantee = built.options["Youth guarantee"]
        mentoring = built.options["Mentoring"]
        client.post(
            f"/api/v1/tasks/{built.task_id}/options/{guarantee}/exclude",
            headers=owner.headers,
            json={"reason": "We ran one already."},
        )
        client.post(
            f"/api/v1/tasks/{built.task_id}/options/{mentoring}/include", headers=owner.headers
        )
        # Everything passes: the user's exclusion stands.
        _constrain(engine, built, StubLonglistBackend())
        # Everything breaks the requirement: the user's inclusion stands.
        _constrain(engine, built, _Breaks({guarantee, mentoring}))
        by_name = {
            o["name"]: o for o in _longlist(client, built.task_id, owner.headers).json()["options"]
        }
        assert by_name["Youth guarantee"]["state"] == "excluded"
        assert by_name["Youth guarantee"]["exclusion"]["reason"] == "We ran one already."
        assert by_name["Youth guarantee"]["exclusion"]["by"] == "user"
        assert by_name["Mentoring"]["state"] == "included"
        assert by_name["Mentoring"]["exclusion"] is None


def test_constrains_exclusion_reads_by_constrain(engine: Engine, tmp_path: Path) -> None:
    with _clients(tmp_path, engine) as (client, (owner, colleague, _)):
        built = _org_build(engine, owner, colleague)
        _constrain(engine, built, _Breaks({built.options["Guarantee package"]}))
        card = _card(client, built, "Guarantee package", owner.headers).json()
        assert card["state"] == "excluded"
        assert card["exclusion"] == {
            "constraint": REQUIREMENT,
            "reason": "It is not run through Jobcentres.",
            "by": "constrain",
        }
        assert card["judgements"][0]["verdict"] == "breaks"


def _design_backend() -> StubAgentBackend:
    return StubAgentBackend(
        option_design_responses=OptionDesignWire.model_validate(
            {
                "name": "Wage subsidy",
                "description": "Employers are paid part of a young recruit's wage.",
                "design_features": ["a wage subsidy for six months", "for 16 to 24 year olds"],
                "outcomes_served": ["the NEET rate"],
                "assumed": ["a wage subsidy for six months"],
            }
        )
    )


def test_add_proposes_a_design_mints_it_and_opens_a_parentless_walk(
    engine: Engine, tmp_path: Path
) -> None:
    agent = _design_backend()
    overrides = {get_agent_backend: lambda: agent, get_runner_backends: _runner_backends}
    with _clients(tmp_path, engine, overrides) as (client, (owner, colleague, _)):
        built = _org_build(engine, owner, colleague, linked=False)
        response = client.post(
            f"/api/v1/tasks/{built.task_id}/options",
            headers=owner.headers,
            json={"text": "pay employers  to hire young people"},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert agent.option_design_words == ["pay employers to hire young people"]
        added = body["option"]
        assert added["origin"] == "added_by_you"
        assert added["name"] == "Wage subsidy"
        assert added["design"]["assumed"] == ["a wage subsidy for six months"]
        assert added["is_entrant_with_no_documents"] is True
        opened = uuid.UUID(body["opened_run"]["capability_run_id"])
        with engine.connect() as conn:
            row = conn.execute(
                select(option).where(option.c.option_id == uuid.UUID(added["option_id"]))
            ).one()
            walk = conn.execute(
                select(capability_run, evidence_scope.c.purpose, evidence_scope.c.context)
                .select_from(
                    capability_run.join(
                        evidence_scope,
                        evidence_scope.c.evidence_scope_id == capability_run.c.evidence_scope_id,
                    )
                )
                .where(capability_run.c.capability_run_id == opened)
            ).one()
        assert row.created_by_run_id is None
        assert walk.parent_capability_run_id is None
        assert walk.purpose == "targeted"
        assert walk.context["option_id"] == added["option_id"]
        history = _decisions(client, built, owner.headers)
        assert len(history) == 1 and history[0]["kind"] == "option.added"
        assert history[0]["decided_by"] == "user" and "Wage subsidy" in history[0]["summary"]
        listed = _longlist(client, built.task_id, owner.headers).json()
        assert added["option_id"] in listed["unthemed_option_ids"]

        # The add's own option search is a parentless walk: it fences the next add.
        with engine.connect() as conn:
            status = conn.execute(
                select(capability_run.c.status).where(capability_run.c.capability_run_id == opened)
            ).scalar_one()
        if status in ("running", "paused"):
            again = client.post(
                f"/api/v1/tasks/{built.task_id}/options",
                headers=owner.headers,
                json={"text": "another"},
            )
            assert again.status_code == 409
        _await_walks_ended(engine, [built.task_id])


def test_the_buttons_are_run_active_while_a_parentless_walk_runs(
    engine: Engine, tmp_path: Path
) -> None:
    agent = _design_backend()
    overrides = {get_agent_backend: lambda: agent, get_runner_backends: _runner_backends}
    with _clients(tmp_path, engine, overrides) as (client, (owner, colleague, _)):
        built = _org_build(engine, owner, colleague)
        oid = built.options["Mentoring"]
        with engine.begin() as conn:
            conn.execute(
                capability_run.update()
                .where(capability_run.c.capability_run_id == built.walk_id)
                .values(status="running", ended_at=None)
            )
        responses = [
            client.post(
                f"/api/v1/tasks/{built.task_id}/options",
                headers=owner.headers,
                json={"text": "a wage subsidy"},
            ),
            client.post(
                f"/api/v1/tasks/{built.task_id}/options/{oid}/exclude",
                headers=owner.headers,
                json={"reason": "No."},
            ),
            client.post(
                f"/api/v1/tasks/{built.task_id}/options/{oid}/include", headers=owner.headers
            ),
        ]
        for response in responses:
            assert response.status_code == 409, response.text
            assert response.json()["error"]["code"] == "run_active"
        assert agent.option_design_calls == 0  # refused before the model call
        assert _decisions(client, built, owner.headers) == []

        # A child walk never fences.
        with engine.begin() as conn:
            conn.execute(
                capability_run.update()
                .where(capability_run.c.capability_run_id == built.walk_id)
                .values(status="succeeded", ended_at=now())
            )
            child_scope = uuid.uuid4()
            conn.execute(
                evidence_scope.insert().values(
                    evidence_scope_id=child_scope,
                    task_id=built.task_id,
                    intent="child",
                    context={},
                    created_at=now(),
                    purpose="targeted",
                )
            )
            conn.execute(
                capability_run.insert().values(
                    capability_run_id=uuid.uuid4(),
                    task_id=built.task_id,
                    evidence_scope_id=child_scope,
                    capability="options_scoping",
                    plan_id=uuid.uuid4(),
                    plan_version=2,
                    status="running",
                    started_at=now(),
                    parent_capability_run_id=built.walk_id,
                )
            )
        allowed = client.post(
            f"/api/v1/tasks/{built.task_id}/options/{oid}/exclude",
            headers=owner.headers,
            json={"reason": "Not now."},
        )
        assert allowed.status_code == 200, allowed.text


def test_the_buttons_are_422_on_an_evidence_search_task(engine: Engine, tmp_path: Path) -> None:
    agent = _design_backend()
    overrides = {get_agent_backend: lambda: agent, get_runner_backends: _runner_backends}
    with api_client(tmp_path, overrides) as (client, owner, _other):
        task_id = create_task(client, owner)
        oid = uuid.uuid4()
        for response in (
            client.post(f"/api/v1/tasks/{task_id}/options", headers=owner, json={"text": "x"}),
            client.post(
                f"/api/v1/tasks/{task_id}/options/{oid}/exclude",
                headers=owner,
                json={"reason": "x"},
            ),
            client.post(f"/api/v1/tasks/{task_id}/options/{oid}/include", headers=owner),
        ):
            assert response.status_code == 422, response.text
        assert agent.option_design_calls == 0


def test_an_added_option_reads_its_own_search_until_the_next_build(conn: Connection) -> None:
    """Live-check finding: an option added since the build reads its option search's records.

    While the add's walk runs, ``search_pending`` is set and the counts are
    zero; once it has ended, its scope's profile records (comparators left
    out) are the option's documents, DOI-collapsed for the counts.
    """
    walk = _Walk(conn)
    walk.option("Youth guarantee", origin="added_by_you")
    walk.build(_Scripted())
    added = walk.option("Wage subsidy", origin="added_by_you")
    scope_id = uuid.uuid4()
    conn.execute(
        evidence_scope.insert().values(
            evidence_scope_id=scope_id,
            task_id=walk.task_id,
            intent="Wage subsidy.",
            context={"capability": "options_scoping", "option_id": str(added)},
            created_at=now(),
            purpose="targeted",
            plan_id=walk.plan_id,
        )
    )
    search_walk = uuid.uuid4()
    conn.execute(
        capability_run.insert().values(
            capability_run_id=search_walk,
            task_id=walk.task_id,
            evidence_scope_id=scope_id,
            capability="options_scoping",
            plan_id=walk.plan_id,
            plan_version=2,
            status="running",
            started_at=now(),
            parent_capability_run_id=None,
        )
    )

    card = repository.option_out(conn, walk.task_id, added)
    assert card is not None
    assert card.search_pending is True
    assert card.document_count == 0 and card.documents == []
    listed = repository.longlist_out(conn, walk.task_id)
    assert listed is not None
    summary = next(o for o in listed.options if o.option_id == added)
    assert summary.search_pending is True and summary.document_count == 0

    # The search screened in and profiled three documents; two share a DOI.
    first = walk.doc({"title": "Wage subsidy trial", "doi": "10.9/ws"})
    twin = walk.doc({"title": "Wage subsidy trial (preprint)", "doi": "https://doi.org/10.9/WS"})
    other = walk.doc({"title": "A Danish wage subsidy"})
    walk.classify(first, RCT, 4)
    walk.classify(twin, RCT, 4)
    walk.record(first, "wage subsidy", study_geography="England", setting="Employers")
    walk.record(twin, "wage subsidy", study_geography="United Kingdom")
    walk.record(other, "wage subsidy", role="described", study_geography="Denmark")
    walk.record(other, "unemployment benefit", role="comparator")
    walk.rollup(scope_id, [first, twin, other])
    conn.execute(
        capability_run.update()
        .where(capability_run.c.capability_run_id == search_walk)
        .values(status="succeeded", ended_at=now())
    )

    card = repository.option_out(conn, walk.task_id, added)
    assert card is not None
    assert card.search_pending is False
    assert card.is_entrant_with_no_documents is False
    assert card.document_count == 2  # the DOI twins count once
    assert card.evaluated_count == 1
    assert card.where_tried.model_dump() == {
        "where": 1,
        "comparable": 1,
        "other": 0,
        "unknown": 0,
    }
    assert card.evidence.by_tier == {"Strong": 1, "not rated": 1}
    assert card.settings == ["Employers"]
    # One per record, never collapsed; the comparator is not a document.
    assert sorted(d.title for d in card.documents) == [
        "A Danish wage subsidy",
        "Wage subsidy trial",
        "Wage subsidy trial (preprint)",
    ]
    trial = next(d for d in card.documents if d.title == "Wage subsidy trial")
    assert trial.tier == "Strong" and trial.where_tried_group == "where"
    listed = repository.longlist_out(conn, walk.task_id)
    assert listed is not None
    summary = next(o for o in listed.options if o.option_id == added)
    assert summary.document_count == 2 and summary.search_pending is False
    # A build-assigned option is untouched by the rule.
    seeded = next(o for o in listed.options if o.name == "Youth guarantee")
    assert seeded.search_pending is False


# --- step-7 fixes (A4, A5, S2, F3) ----------------------------------------------------


def test_add_answers_with_the_option_when_its_search_is_still_queued(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A4: the option has committed, so a slow option-search pool is no 500. The
    reservation fences the task until the queued search settles."""
    from concurrent.futures import Future

    from policy_atlas.api import longlist_actions
    from policy_atlas.api.routers import runs as runs_router
    from policy_atlas.runtime import option_search

    queued: Future[None] = Future()
    child_id = uuid.uuid4()

    def run_option_search(*args: Any, **kwargs: Any) -> uuid.UUID:
        with option_search._handles_lock:
            option_search._futures[child_id] = queued
        return child_id

    def never_opens(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("executor did not create a capability run")

    monkeypatch.setattr(longlist_actions, "run_option_search", run_option_search)
    monkeypatch.setattr(longlist_actions, "_await_new_run", never_opens)
    agent = _design_backend()
    overrides = {get_agent_backend: lambda: agent, get_runner_backends: _runner_backends}
    try:
        with _clients(tmp_path, engine, overrides) as (client, (owner, colleague, _)):
            built = _org_build(engine, owner, colleague, linked=False)
            response = client.post(
                f"/api/v1/tasks/{built.task_id}/options",
                headers=owner.headers,
                json={"text": "pay employers to hire young people"},
            )
            assert response.status_code == 201, response.text
            assert response.json()["opened_run"] is None
            assert response.json()["option"]["name"] == "Wage subsidy"
            assert built.task_id in runs_router._dispatching_tasks
            again = client.post(
                f"/api/v1/tasks/{built.task_id}/options",
                headers=owner.headers,
                json={"text": "another"},
            )
            assert again.status_code == 409, again.text
            queued.set_result(None)
            assert built.task_id not in runs_router._dispatching_tasks
            assert built.task_id not in runs_router._search_reservations
    finally:
        with option_search._handles_lock:
            option_search._futures.pop(child_id, None)


def test_a_document_two_added_searches_share_counts_for_both(conn: Connection) -> None:
    """A5: one extraction record listed by two searches' roll-ups is each option's."""
    walk = _Walk(conn)
    walk.option("Youth guarantee", origin="added_by_you")
    walk.build(_Scripted())
    shared = walk.doc({"title": "A wage subsidy and mentoring trial"})
    walk.classify(shared, RCT, 4)
    walk.record(shared, "wage subsidy", study_geography="England")
    added: list[uuid.UUID] = []
    for name in ("Wage subsidy", "Mentoring"):
        option_id = walk.option(name, origin="added_by_you")
        added.append(option_id)
        scope_id = uuid.uuid4()
        conn.execute(
            evidence_scope.insert().values(
                evidence_scope_id=scope_id,
                task_id=walk.task_id,
                intent=f"{name}.",
                context={"capability": "options_scoping", "option_id": str(option_id)},
                created_at=now(),
                purpose="targeted",
                plan_id=walk.plan_id,
            )
        )
        conn.execute(
            capability_run.insert().values(
                capability_run_id=uuid.uuid4(),
                task_id=walk.task_id,
                evidence_scope_id=scope_id,
                capability="options_scoping",
                plan_id=walk.plan_id,
                plan_version=2,
                status="succeeded",
                started_at=now(),
                ended_at=now(),
                parent_capability_run_id=None,
            )
        )
        walk.rollup(scope_id, [shared])
    listed = repository.longlist_out(conn, walk.task_id)
    assert listed is not None
    counts = {o.option_id: o.document_count for o in listed.options}
    assert [counts[oid] for oid in added] == [1, 1]


def test_a_linked_finding_needs_a_link_to_this_task(conn: Connection) -> None:
    """S2: a membership row naming another task's finding is read only while that
    task is linked to this one."""
    walk = _Walk(conn, _plan())
    guarantee = walk.option("Youth guarantee", origin="added_by_you")
    _linked_deep_task(conn, walk, "youth guarantee")
    walk.build(_Scripted(routes={"youth guarantee": ("Youth guarantee", False)}))
    card = repository.option_out(conn, walk.task_id, guarantee)
    assert card is not None
    assert "A deep read" in {d.title for d in card.documents}
    conn.execute(task_link.delete().where(task_link.c.target_task_id == walk.task_id))
    card = repository.option_out(conn, walk.task_id, guarantee)
    assert card is not None
    assert "A deep read" not in {d.title for d in card.documents}


def test_an_option_from_the_evidence_search_names_its_report_section(
    conn: Connection,
) -> None:
    """F3: the section suggest recorded for the option reaches the list and the card."""
    from policy_atlas.core import events

    walk = _Walk(conn)
    walk.option("Youth guarantee", origin="added_by_you")
    suggest_run = walk.run()
    drawn = walk.option(
        "Employer incentives", origin="from_evidence_search", created_by_run_id=suggest_run
    )
    events.append(
        conn,
        task_id=walk.task_id,
        run_id=suggest_run,
        event_type="component.completed",
        payload={
            "component": "suggest",
            "report_sections": {str(drawn): "What works for employers"},
        },
    )
    walk.build(_Scripted())
    listed = repository.longlist_out(conn, walk.task_id)
    assert listed is not None
    sections = {o.option_id: o.from_section for o in listed.options}
    assert sections[drawn] == "What works for employers"
    assert {v for k, v in sections.items() if k != drawn} == {None}
    card = repository.option_out(conn, walk.task_id, drawn)
    assert card is not None
    assert card.from_section == "What works for employers"
