"""The ``longlist`` component (task 045 Phase 5.2, S8; contract deliverable 6).

The contract's longlist bullet: every record lands in one option, unclustered
or not an option (code-enforced); a document with three records can belong to
three options; a bundle is one option and no *part of* row is written (task
046, item 4); each option has
one primary lever type from the list or *none fits* with a reason, the
taxonomy version and an ambition tag with its justification; the runner-up is
in ``longlist_result`` and not on the option row; coverage buckets Unknown and
Non-evidence separately, shows the role funnel, where tried grouped against
Where, settings, and counts flagged members; two documents sharing a DOI count
once and stay two membership rows; seeds are assigned against and survive with
zero members; linked findings cluster beside profile records (D5); the
rebuild keeps ids and user state and deletes nothing; comparator records never
become members. Task 046 (items 1, 2, 4, 6, 7, 15, 26): the target size and the
hard ceiling, the corpus digest, folds and their guards, the residual pass,
short ids, outcomes at mint time, typing in parallel with the keep-previous
rule, and the thinning rules. Seeded on the transactional ``conn`` fixture,
with a scripted backend standing in for the model.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import (
    capability_run,
    evidence_scope,
    extraction_result,
    implementation_context_finding,
    intervention_outcome_finding,
    intervention_profile_record,
    longlist_result,
    option,
    option_membership,
    option_relation,
    runs,
    source_appraisal_result,
    source_classification_result,
    source_extraction_record,
    source_snapshot,
    task,
    task_link,
    task_plan,
    task_source_snapshot,
)
from policy_atlas.core.usage import UsageResult
from policy_atlas.evidence_search.extract.icf_records import PROFILE_ID as ICF_PROFILE_ID
from policy_atlas.evidence_search.extract.interventions_records import (
    PROFILE_ID as INTERVENTIONS_PROFILE_ID,
)
from policy_atlas.evidence_search.extract.iof_records import PROFILE_ID as IOF_PROFILE_ID
from policy_atlas.options_scoping.design import OptionDesign
from policy_atlas.options_scoping.longlist.lever_types import (
    AMBITION_BANDS,
    LEVER_TYPE_KEYS,
    TAXONOMY_VERSION,
)
from policy_atlas.options_scoping.longlist.lever_typing_prompt import (
    LeverTypingResponse,
    LeverTypingWire,
)
from policy_atlas.options_scoping.longlist.longlist import (
    LONGLIST_HARD_CEILING,
    LONGLIST_TARGET_SIZE,
    RECORDS_PER_DOCUMENT_MAX,
    TYPING_INVALID_REASON,
    LonglistContext,
    LonglistFailure,
    corpus_digest,
    current_profile_fingerprints,
    discovery_bounds,
    longlist_scope,
)
from policy_atlas.options_scoping.longlist.longlist_backend import (
    STUB_DISCOVERED_LABEL,
    StubLonglistBackend,
)
from policy_atlas.options_scoping.longlist.longlist_cluster_prompt import (
    NOT_AN_OPTION_LABEL,
    DiscoveredOptionWire,
    FoldWire,
    OptionAssignmentsResponse,
    OptionAssignmentWire,
    OptionDiscoveryResponse,
)
from policy_atlas.options_scoping.theme.longlist_theme_prompt import (
    ThemeAssignmentsResponse,
    ThemeAssignmentWire,
    ThemeDiscoveryResponse,
    ThemeWire,
)
from policy_atlas.runtime.scoping_plan import ScopingPlan
from tests.helpers import now
from tests.runtime.test_baseline_gate import scoping_plan

UNKNOWN = "Unknown / Insufficient information"
NON_EVIDENCE = "Other (Non-evidence documents)"
RCT = "RCTs and Quasi-Experimental Studies"


# --- the scripted backend -----------------------------------------------------------


def _discovered(label: str, **overrides: Any) -> DiscoveredOptionWire:
    values: dict[str, Any] = {
        "label": label,
        "description": f"{label}, as the units state it.",
        "design_features": [f"{label} feature"],
    }
    values.update(overrides)
    return DiscoveredOptionWire.model_validate(values)


def _typing(unit_id: str, **overrides: Any) -> LeverTypingWire:
    values: dict[str, Any] = {
        "unit_id": unit_id,
        "primary_lever_type": "subsidise",
        "secondary_lever_types": ["inform"],
        "runner_up_lever_type": None,
        "none_fits_reason": None,
        "ambition": "incremental",
        "ambition_reason": "A new scheme inside the present structure.",
    }
    values.update(overrides)
    return LeverTypingWire.model_validate(values)


@dataclass
class _Scripted:
    """A deterministic backend: assignment by the record's ``intervention`` text.

    ``routes`` maps an intervention text to ``(label, design_feature_not_stated)``;
    an unrouted record is ``ungroupable``. ``typings`` maps an option label to
    wire overrides.
    """

    discovered: list[DiscoveredOptionWire] = field(default_factory=list)
    folds: list[FoldWire] = field(default_factory=list)
    # The residual pass's discovery, when it differs from the first pass's.
    residual_discovered: list[DiscoveredOptionWire] | None = None
    routes: dict[str, tuple[str, bool]] = field(default_factory=dict)
    typings: dict[str, dict[str, Any]] = field(default_factory=dict)
    discover_error: Exception | None = None
    # How the answered unit id is written back (a model mangling short ids).
    mangle: Any = None
    calls: dict[str, list[dict[str, Any]]] = field(
        default_factory=lambda: {"discover": [], "assign": [], "themes": [], "type": []}
    )
    mode: str = "stub"

    def discover(
        self,
        *,
        plan: dict[str, object],
        baseline_sections: list[tuple[str, str]],
        seeds: list[dict[str, object]],
        digest: list[dict[str, object]],
        target_size: int,
        max_new: int,
        residual: bool = False,
    ) -> UsageResult[OptionDiscoveryResponse]:
        self.calls["discover"].append(
            {
                "plan": plan,
                "baseline_sections": baseline_sections,
                "seeds": seeds,
                "digest": digest,
                "target_size": target_size,
                "max_new": max_new,
                "residual": residual,
            }
        )
        if self.discover_error is not None:
            raise self.discover_error
        if residual and self.residual_discovered is not None:
            return OptionDiscoveryResponse(options=self.residual_discovered, folds=[]), None
        return OptionDiscoveryResponse(options=self.discovered, folds=self.folds), None

    def assign(
        self, *, options: list[dict[str, object]], records: list[dict[str, object]]
    ) -> UsageResult[OptionAssignmentsResponse]:
        self.calls["assign"].append({"options": options, "records": records})
        out = []
        for record in records:
            label, flag = self.routes.get(str(record.get("intervention")), ("ungroupable", False))
            unit_id = str(record["unit_id"])
            out.append(
                OptionAssignmentWire(
                    unit_id=self.mangle(unit_id) if self.mangle else unit_id,
                    option_label=label,
                    reason=f"{record.get('intervention')} decides it.",
                    design_feature_not_stated=flag,
                )
            )
        return OptionAssignmentsResponse(assignments=out), None

    def discover_themes(
        self, *, question: str, records: list[dict[str, object]], max_labels: int
    ) -> UsageResult[ThemeDiscoveryResponse]:
        self.calls["themes"].append({"records": records, "max_labels": max_labels})
        return (
            ThemeDiscoveryResponse(
                themes=[ThemeWire(label="Getting young people into work", description="Jobs.")]
            ),
            None,
        )

    def assign_themes(
        self, *, themes: list[dict[str, str]], records: list[dict[str, object]]
    ) -> UsageResult[ThemeAssignmentsResponse]:
        # The first option has no theme; every other one joins the only theme.
        return (
            ThemeAssignmentsResponse(
                assignments=[
                    ThemeAssignmentWire(
                        unit_id=str(r["unit_id"]),
                        theme_label="ungroupable" if i == 0 else themes[0]["label"],
                    )
                    for i, r in enumerate(records)
                ]
            ),
            None,
        )

    def type_options(
        self,
        *,
        options: list[dict[str, object]],
        plan: dict[str, object],
        baseline_sections: list[tuple[str, str]],
    ) -> UsageResult[LeverTypingResponse]:
        self.calls["type"].append(
            {"options": options, "plan": plan, "baseline_sections": baseline_sections}
        )
        return (
            LeverTypingResponse(
                typings=[
                    _typing(str(o["unit_id"]), **self.typings.get(str(o["label"]), {}))
                    for o in options
                ]
            ),
            None,
        )


# --- the fixture -------------------------------------------------------------------


def _task_row(conn: Connection, *, capability: str) -> uuid.UUID:
    task_id = uuid.uuid4()
    conn.execute(
        task.insert().values(
            task_id=task_id,
            created_at=now(),
            name="Task",
            status="active",
            updated_at=now(),
            capability=capability,
        )
    )
    return task_id


class _Walk:
    """A scoping task with a longlist walk, its intent record and runs."""

    def __init__(self, conn: Connection, plan: ScopingPlan | None = None) -> None:
        self.conn = conn
        self.task_id = _task_row(conn, capability="options_scoping")
        self.plan_id = uuid.uuid4()
        conn.execute(
            task_plan.insert().values(
                plan_id=self.plan_id,
                task_id=self.task_id,
                version=2,
                status="approved",
                payload=(plan or scoping_plan()).model_dump(mode="json"),
                created_at=now(),
                created_by="task_agent",
            )
        )
        self.scope_id = self._scope("longlist")
        self.walk_id = self._walk(self.scope_id)
        self.extract_run = self.run()
        self._ser: dict[uuid.UUID, uuid.UUID] = {}

    def _scope(self, purpose: str, context: dict[str, Any] | None = None) -> uuid.UUID:
        scope_id = uuid.uuid4()
        self.conn.execute(
            evidence_scope.insert().values(
                evidence_scope_id=scope_id,
                task_id=self.task_id,
                intent=f"{purpose} intent",
                context=context or {},
                created_at=now(),
                purpose=purpose,
                plan_id=self.plan_id,
            )
        )
        return scope_id

    def _walk(
        self,
        scope_id: uuid.UUID,
        parent: uuid.UUID | None = None,
        status: str = "running",
        started_at: datetime | None = None,
    ) -> uuid.UUID:
        walk_id = uuid.uuid4()
        self.conn.execute(
            capability_run.insert().values(
                capability_run_id=walk_id,
                task_id=self.task_id,
                evidence_scope_id=scope_id,
                capability="options_scoping",
                plan_id=self.plan_id,
                plan_version=2,
                status=status,
                started_at=started_at or now(),
                parent_capability_run_id=parent,
            )
        )
        return walk_id

    def child_scope(
        self,
        option_id: uuid.UUID,
        *,
        parent: uuid.UUID | None = None,
        parentless: bool = False,
        status: str = "succeeded",
        started_at: datetime | None = None,
    ) -> uuid.UUID:
        """A targeted scope naming an option, and its walk (an option search).

        By default the walk is a finished child of this walk (the join has
        run by the time ``longlist`` does); ``parent`` names another walk,
        ``parentless`` is the verb *add*'s search.
        """
        scope_id = self._scope("targeted", {"option_id": str(option_id)})
        self._walk(
            scope_id,
            parent=None if parentless else (parent or self.walk_id),
            status=status,
            started_at=started_at,
        )
        return scope_id

    def run(self, walk_id: uuid.UUID | None = None) -> uuid.UUID:
        run_id = uuid.uuid4()
        self.conn.execute(
            runs.insert().values(
                run_id=run_id,
                task_id=self.task_id,
                status="running",
                started_at=now(),
                capability_run_id=walk_id or self.walk_id,
            )
        )
        return run_id

    def doc(self, meta: dict[str, Any] | None = None) -> uuid.UUID:
        """One document of this task; returns its ``task_source_snapshot`` id."""
        snapshot_id = uuid.uuid4()
        self.conn.execute(
            source_snapshot.insert().values(
                source_snapshot_id=snapshot_id,
                content_hash=str(uuid.uuid4()),
                text_basis="abstract_only",
                source_locator=f"https://example.org/{snapshot_id}",
                metadata={"title": "A document", **(meta or {})},
                created_at=now(),
            )
        )
        tss_id = uuid.uuid4()
        self.conn.execute(
            task_source_snapshot.insert().values(
                task_source_snapshot_id=tss_id,
                task_id=self.task_id,
                source_snapshot_id=snapshot_id,
                origin="acquired",
                run_id=None,
                ingested_at=now(),
            )
        )
        return tss_id

    def record(self, tss_id: uuid.UUID, intervention: str, **values: Any) -> uuid.UUID:
        """One intervention profile record of the document (one memo row per document)."""
        if tss_id not in self._ser:
            snapshot_id = self.conn.execute(
                select(task_source_snapshot.c.source_snapshot_id).where(
                    task_source_snapshot.c.task_source_snapshot_id == tss_id
                )
            ).scalar_one()
            ser_id = uuid.uuid4()
            self.conn.execute(
                source_extraction_record.insert().values(
                    extraction_record_id=ser_id,
                    task_id=self.task_id,
                    source_snapshot_id=snapshot_id,
                    task_source_snapshot_id=tss_id,
                    extraction_fingerprint=f"fp-{ser_id}",
                    status="extracted",
                    basis="abstract_only",
                    run_id=self.extract_run,
                    created_at=now(),
                )
            )
            self._ser[tss_id] = ser_id
        record_id = uuid.uuid4()
        row: dict[str, Any] = {
            "record_id": record_id,
            "task_id": self.task_id,
            "extraction_record_id": self._ser[tss_id],
            "intervention": intervention,
            "role": "evaluated",
            "design_features": [],
            "is_bundle": False,
            "components": [],
            "field_coverage": {},
            "grounding": [{"quote": f"We studied {intervention}."}],
            "created_at": now(),
        }
        row.update(values)
        self.conn.execute(intervention_profile_record.insert().values(**row))
        return record_id

    def rollup(
        self,
        scope_id: uuid.UUID,
        tss_ids: list[uuid.UUID],
        counts: dict[str, Any] | None = None,
    ) -> None:
        """The scope's intervention-profile roll-up over the given documents."""
        self.conn.execute(
            extraction_result.insert().values(
                extraction_result_id=uuid.uuid4(),
                task_id=self.task_id,
                evidence_scope_id=scope_id,
                run_id=self.run(),
                selection_run_id=None,
                extraction_provenance={},
                docs=[
                    {
                        "tss_id": str(tss_id),
                        "basis": "abstract_only",
                        "profiles": {
                            INTERVENTIONS_PROFILE_ID: {
                                "extraction_record_id": str(self._ser[tss_id])
                            }
                        },
                    }
                    for tss_id in tss_ids
                ],
                counts=counts or {},
                flags=[],
                created_at=now(),
            )
        )

    def option(self, name: str, origin: str = "suggested", **values: Any) -> uuid.UUID:
        option_id = uuid.uuid4()
        design = OptionDesign(
            name=name,
            description=f"{name}, as suggested.",
            design_features=[f"{name} feature"],
            outcomes_served=["the NEET rate"],
        )
        row: dict[str, Any] = {
            "option_id": option_id,
            "task_id": self.task_id,
            "name": name,
            "description": design.description,
            "design": design.model_dump(mode="json"),
            "outcomes": ["the NEET rate"],
            "origin": origin,
            "state": "included",
            "secondary_lever_types": [],
            "created_at": now(),
            "updated_at": now(),
        }
        row.update(values)
        self.conn.execute(option.insert().values(**row))
        return option_id

    def classify(self, tss_id: uuid.UUID, evidence_type: str, score: int | None = None) -> None:
        run_id = self.run()
        self.conn.execute(
            source_classification_result.insert().values(
                source_classification_result_id=uuid.uuid4(),
                evidence_scope_id=self.scope_id,
                task_source_snapshot_id=tss_id,
                task_id=self.task_id,
                classified_by_run_id=run_id,
                primary_evidence_type=evidence_type,
                classified_at=now(),
            )
        )
        if score is not None:
            from policy_atlas.evidence_search.assess.appraise import DEFAULT_RUBRIC_VERSION

            self.conn.execute(
                source_appraisal_result.insert().values(
                    source_appraisal_result_id=uuid.uuid4(),
                    evidence_scope_id=self.scope_id,
                    task_source_snapshot_id=tss_id,
                    task_id=self.task_id,
                    appraised_by_run_id=run_id,
                    quality_score=score,
                    rubric_version=DEFAULT_RUBRIC_VERSION,
                    appraised_at=now(),
                )
            )

    def build(self, backend: Any) -> tuple[uuid.UUID, dict[str, Any]]:
        run_id = self.run()
        summary = longlist_scope(
            self.conn,
            task_id=self.task_id,
            run_id=run_id,
            context=LonglistContext(scope_id=self.scope_id, intent="longlist intent", context={}),
            backend=backend,
        )
        return run_id, summary

    def result(self, run_id: uuid.UUID) -> Any:
        return self.conn.execute(
            select(longlist_result).where(longlist_result.c.run_id == run_id)
        ).one()

    def options(self) -> dict[str, Any]:
        return {
            row.name: row
            for row in self.conn.execute(select(option).where(option.c.task_id == self.task_id))
        }

    def memberships(self) -> list[Any]:
        return list(
            self.conn.execute(
                select(option_membership).where(option_membership.c.task_id == self.task_id)
            )
        )


# --- the ceilings ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("seeds", "bounds"), [(0, (25, 25)), (3, (22, 25)), (25, (0, 25)), (31, (0, 31))]
)
def test_the_bounds_are_the_hard_ceiling_counting_seeds(
    seeds: int, bounds: tuple[int, int]
) -> None:
    """Task 046, R1: ``max_new = max(25 - seeds, 0)``; every seed is assigned against."""
    assert (LONGLIST_TARGET_SIZE, LONGLIST_HARD_CEILING) == (20, 25)
    assert discovery_bounds(seeds) == bounds


# --- assignment ---------------------------------------------------------------------


def test_every_record_lands_in_one_option_unclustered_or_not_an_option(
    conn: Connection,
) -> None:
    walk = _Walk(conn)
    seed_id = walk.option("Youth guarantee", origin="added_by_you")
    three = walk.doc()
    other = walk.doc()
    walk.record(three, "youth guarantee")
    walk.record(three, "wage subsidy")
    walk.record(three, "work trial")
    walk.record(other, "a theory of change")
    walk.record(other, "something unplaced")
    walk.rollup(walk.scope_id, [three, other])
    backend = _Scripted(
        discovered=[_discovered("Wage subsidy"), _discovered("Work trial")],
        routes={
            "youth guarantee": ("Youth guarantee", True),
            "wage subsidy": ("Wage subsidy", False),
            "work trial": ("work TRIAL", False),  # case is normalised to the label
            "a theory of change": (NOT_AN_OPTION_LABEL, False),
        },
    )

    run_id, summary = walk.build(backend)

    assert summary == {
        "options": 3,
        "unclustered": 1,
        "not_an_option": 1,
        "none_fits": 0,
        "units": 5,
    }
    members = walk.memberships()
    assert len(members) + summary["unclustered"] + summary["not_an_option"] == summary["units"]
    # One document, three records, three options.
    by_option = {m.option_id for m in members if m.task_source_snapshot_id == three}
    assert len(by_option) == 3
    options = walk.options()
    assert options["Youth guarantee"].option_id == seed_id
    assert {options["Wage subsidy"].origin, options["Work trial"].origin} == {"clustered"}
    # Membership rows carry the reason and the flag; one option per record.
    flagged = [m for m in members if m.design_feature_not_stated]
    assert [m.option_id for m in flagged] == [seed_id]
    assert all(m.assignment_reason for m in members)
    assert all(m.unit_kind == "interventions" and m.unit_task_id == walk.task_id for m in members)
    assert len({m.unit_id for m in members}) == len(members)
    result = walk.result(run_id)
    assert result.counts["unclustered"] == 1 and result.counts["not_an_option"] == 1
    assert result.judgements == {} and result.guesses == {}
    assert result.plan_version == 2
    # The seeded run keeps the seed's id and offered it to discovery.
    assert result.provenance["seed_ids"] == [str(seed_id)]
    discover = backend.calls["discover"][0]
    assert [seed["label"] for seed in discover["seeds"]] == ["Youth guarantee"]
    assert discover["max_new"] == LONGLIST_HARD_CEILING - 1
    assert discover["target_size"] == LONGLIST_TARGET_SIZE


def test_a_bundle_is_one_option_and_no_part_of_row_is_written(conn: Connection) -> None:
    """Task 046, item 4: discovery mints no package; ``part_of`` stays for users."""
    walk = _Walk(conn)
    walk.option("Careers advice")
    doc = walk.doc()
    walk.record(doc, "careers advice")
    walk.record(doc, "mentoring")
    walk.record(doc, "guarantee package", is_bundle=True, components=["mentoring", "advice"])
    walk.rollup(walk.scope_id, [doc])
    backend = _Scripted(
        discovered=[_discovered("Mentoring"), _discovered("Guarantee package")],
        routes={
            "careers advice": ("Careers advice", False),
            "mentoring": ("Mentoring", False),
            "guarantee package": ("Guarantee package", False),
        },
    )
    run_id, summary = walk.build(backend)
    assert summary["options"] == 3
    assert "Guarantee package" in walk.options()
    assert conn.execute(
        select(func.count())
        .select_from(option_relation)
        .where(option_relation.c.task_id == walk.task_id)
        .where(option_relation.c.created_by == "longlist")
    ).scalar_one() == 0
    result = walk.result(run_id)
    assert "packages" not in result.counts and "bundles" not in result.provenance
    # The unit payloads carry no bundle fields any more.
    records = backend.calls["assign"][0]["records"]
    assert all("is_bundle" not in r and "components" not in r for r in records)


def test_comparator_records_never_become_members(conn: Connection) -> None:
    walk = _Walk(conn)
    walk.option("Youth guarantee")
    doc = walk.doc()
    walk.record(doc, "youth guarantee")
    comparator = walk.record(doc, "youth guarantee", role="comparator")
    walk.rollup(walk.scope_id, [doc])
    run_id, summary = walk.build(
        _Scripted(routes={"youth guarantee": ("Youth guarantee", False)})
    )
    assert summary["units"] == 1
    assert comparator not in {m.unit_id for m in walk.memberships()}
    assert walk.result(run_id).counts["comparator_records"] == 1


def test_an_add_walk_s_records_join_the_longlist_scope_s(conn: Connection) -> None:
    """Task 046, S3: the verb *add*'s parentless search supplies units."""
    walk = _Walk(conn)
    seed = walk.option("Youth guarantee", origin="added_by_you")
    broad = walk.doc()
    targeted = walk.doc()
    walk.record(broad, "youth guarantee")
    walk.record(targeted, "youth guarantee")
    walk.rollup(walk.scope_id, [broad])
    child = walk.child_scope(seed, parentless=True)
    walk.rollup(child, [broad, targeted])  # the same document in both: one unit
    run_id, summary = walk.build(
        _Scripted(routes={"youth guarantee": ("Youth guarantee", False)})
    )
    assert summary["units"] == 2
    assert walk.result(run_id).provenance["scopes"]["targeted"] == [str(child)]


def test_a_rebuild_reads_only_the_latest_finished_add_walk_search_of_each_option(
    conn: Connection,
) -> None:
    """Task 046, S3 (AM5): the verb *add*'s parentless search is read by the
    next build; a longlist walk's option search (a child with a parent, here
    an earlier build's) supplies no units, and a failed search none either."""
    walk = _Walk(conn)
    earlier = walk.option("Youth guarantee", origin="added_by_you")
    added = walk.option("Wage subsidy", origin="added_by_you")
    earlier_doc, stale_doc, added_doc, failed_doc = (walk.doc() for _ in range(4))
    for doc in (earlier_doc, stale_doc):
        walk.record(doc, "youth guarantee")
    walk.record(added_doc, "wage subsidy")
    walk.record(failed_doc, "wage subsidy")
    old_build = walk._walk(walk._scope("longlist"), status="succeeded")
    t0 = now() - timedelta(hours=2)
    stale = walk.child_scope(earlier, parent=old_build, started_at=t0)
    walk.rollup(stale, [stale_doc])
    kept = walk.child_scope(earlier, parent=old_build, started_at=t0 + timedelta(minutes=5))
    walk.rollup(kept, [earlier_doc])
    add_search = walk.child_scope(added, parentless=True, status="degraded", started_at=t0)
    walk.rollup(add_search, [added_doc])
    failed = walk.child_scope(added, status="failed")
    walk.rollup(failed, [failed_doc])
    run_id, summary = walk.build(
        _Scripted(
            routes={
                "youth guarantee": ("Youth guarantee", False),
                "wage subsidy": ("Wage subsidy", False),
            }
        )
    )
    assert summary["units"] == 1
    assert walk.result(run_id).provenance["scopes"]["targeted"] == [str(add_search)]
    assert {str(stale), str(kept), str(failed)}.isdisjoint(
        walk.result(run_id).provenance["scopes"]["targeted"]
    )


def test_seeds_over_the_ceiling_survive_and_discovery_adds_none(conn: Connection) -> None:
    """Task 046, AM9: seeds alone over 25 — discovery adds no option (it may
    still fold) and the excess is recorded; every seed survives, members or
    not."""
    walk = _Walk(conn)
    seeds = [walk.option(f"Seed option {i}", origin="added_by_you") for i in range(26)]
    doc = walk.doc()
    walk.record(doc, "Seed option 0")
    walk.rollup(walk.scope_id, [doc])
    backend = _Scripted(
        discovered=[_discovered("Something new")],
        routes={"Seed option 0": ("Seed option 0", False)},
    )
    run_id, summary = walk.build(backend)
    # Nothing can be added and no seed can be folded (all the user's): no call.
    assert backend.calls["discover"] == []
    assert summary["options"] == 26
    result = walk.result(run_id)
    ceiling = result.provenance["ceiling"]
    assert (ceiling["max_labels"], ceiling["max_new"], ceiling["excess"]) == (26, 0, 1)
    empty = result.coverage[str(seeds[5])]
    assert empty["members"] == 0 and empty["documents"] == 0
    assert result.counts["seeds_without_members"] == 25
    assert set(walk.options()) == {f"Seed option {i}" for i in range(26)}


def test_seeds_over_the_ceiling_that_can_fold_still_get_one_call_and_no_new_option(
    conn: Connection,
) -> None:
    walk = _Walk(conn)
    for i in range(26):
        walk.option(f"Seed option {i}")
    doc = walk.doc()
    walk.record(doc, "Seed option 0")
    walk.rollup(walk.scope_id, [doc])
    backend = _Scripted(
        discovered=[_discovered("Something new")],
        routes={"Seed option 0": ("Seed option 0", False)},
    )
    run_id, summary = walk.build(backend)
    assert [call["max_new"] for call in backend.calls["discover"]] == [0]
    assert summary["options"] == 26
    ceiling = walk.result(run_id).provenance["ceiling"]
    assert (ceiling["over_ceiling_dropped"], ceiling["excess"]) == (1, 1)
    assert "Something new" not in walk.options()


# --- typing -----------------------------------------------------------------------


def test_typing_one_primary_or_none_fits_the_version_and_the_ambition(
    conn: Connection,
) -> None:
    walk = _Walk(conn)
    walk.option("Free bus passes")
    walk.option("A new body")
    walk.option("Garbled")
    walk.option("Wrong band")
    backend = _Scripted(
        typings={
            "Free bus passes": {"runner_up_lever_type": "provide a service"},
            "A new body": {"primary_lever_type": None, "none_fits_reason": "It sets a mood."},
            "Garbled": {"primary_lever_type": "make it so"},
            "Wrong band": {"primary_lever_type": None, "none_fits_reason": None},
        }
    )
    run_id, summary = walk.build(backend)
    options = walk.options()
    bus = options["Free bus passes"]
    assert bus.primary_lever_type in LEVER_TYPE_KEYS
    assert bus.secondary_lever_types == ["inform"]
    assert bus.taxonomy_version == TAXONOMY_VERSION
    assert bus.ambition in AMBITION_BANDS and bus.ambition_reason
    assert options["A new body"].primary_lever_type is None
    assert options["A new body"].lever_none_fits_reason == "It sets a mood."
    # An invalid typing leaves the columns as they were (task 046, S12): here
    # never typed, so still empty.
    for name in ("Garbled", "Wrong band"):
        assert options[name].primary_lever_type is None
        assert options[name].lever_none_fits_reason is None
        assert options[name].taxonomy_version is None
        assert options[name].ambition is None
    # The two invalid typings count once, under typing_invalid (F14).
    assert summary["none_fits"] == 1
    result = walk.result(run_id)
    assert result.counts["none_fits"] == 1
    assert result.counts["typing_invalid"] == 2
    # The runner-up is in the record only; the wire has no reasons for it.
    assert result.provenance["runner_up"] == {
        str(bus.option_id): {"lever_type": "provide a service"}
    }
    # The typing prompt receives the plan and the baseline (item 9).
    typed = backend.calls["type"][0]
    assert typed["plan"]["target_unit"] == "16 to 24 year olds"
    assert typed["baseline_sections"] == []
    assert "runner_up" not in dict(bus._mapping)
    assert "provide a service" not in bus.secondary_lever_types


def test_a_failed_typing_call_is_counted_never_a_crash(conn: Connection) -> None:
    walk = _Walk(conn)
    walk.option("Youth guarantee")

    class _Broken(_Scripted):
        def type_options(self, **kwargs: Any) -> Any:
            raise RuntimeError("provider down")

    run_id, summary = walk.build(_Broken())
    assert summary["none_fits"] == 0
    result = walk.result(run_id)
    assert result.counts["typing_invalid"] == 1
    assert result.provenance["typing"]["failed_batches"] == 1
    # The option's columns are left as they were (task 046, S12).
    row = walk.options()["Youth guarantee"]
    assert (row.lever_none_fits_reason, row.taxonomy_version) == (None, None)
    assert row.lever_none_fits_reason != TYPING_INVALID_REASON


# --- coverage ---------------------------------------------------------------------


def test_coverage_buckets_labels_roles_where_tried_settings_and_flags(conn: Connection) -> None:
    walk = _Walk(conn)
    seed_id = walk.option("Youth guarantee", origin="added_by_you")
    uk = walk.doc({"doi": "https://doi.org/10.1/ABC"})
    uk_again = walk.doc({"doi": "10.1/abc"})  # the same DOI, normalised
    danish = walk.doc({"doi": "10.2/dk"})
    oecd = walk.doc()
    nowhere = walk.doc()
    walk.classify(uk, RCT, 4)
    walk.classify(uk_again, RCT, 4)
    walk.classify(danish, UNKNOWN)
    walk.classify(oecd, NON_EVIDENCE)
    walk.record(uk, "youth guarantee", study_geography="England", setting="Jobcentres")
    walk.record(uk_again, "youth guarantee", study_geography="United Kingdom")
    walk.record(
        danish, "youth guarantee flagged", role="recommended", study_geography="Denmark"
    )
    walk.record(oecd, "youth guarantee", role="described", study_geography="12 OECD countries")
    # A feature keeps the mention through thinning (task 046, S10).
    walk.record(
        nowhere,
        "youth guarantee",
        role="mentioned",
        study_geography="a large city",
        design_features=["a job offer"],
    )
    walk.rollup(walk.scope_id, [uk, uk_again, danish, oecd, nowhere])
    run_id, _summary = walk.build(
        _Scripted(
            routes={
                "youth guarantee": ("Youth guarantee", False),
                "youth guarantee flagged": ("Youth guarantee", True),
            }
        )
    )
    coverage = walk.result(run_id).coverage[str(seed_id)]
    # Two documents sharing a normalised DOI count once, and stay two rows.
    assert coverage["members"] == 5
    assert len([m for m in walk.memberships() if m.option_id == seed_id]) == 5
    assert coverage["documents"] == 4
    assert coverage["evidence_type"] == {RCT: 1, UNKNOWN: 1, NON_EVIDENCE: 1, "not rated": 1}
    assert coverage["tier"] == {"not rated": 3, "4": 1}
    assert coverage["role"] == {"evaluated": 1, "described": 1, "recommended": 1, "mentioned": 1}
    assert coverage["where_tried"] == {"where": 1, "comparable": 2, "other": 0, "unknown": 1}
    assert coverage["countries"] == {"DK": 1, "GB": 1}
    assert coverage["settings"] == {"Jobcentres": 1}
    assert coverage["flagged_members"] == 1 and coverage["flagged_documents"] == 1
    assert coverage["abstract_only"] == 4
    result = walk.result(run_id)
    assert result.counts["documents"] == 4
    assert result.provenance["where_tried_labels"]["where"] == "United Kingdom"


def test_a_document_without_a_doi_counts_as_itself(conn: Connection) -> None:
    walk = _Walk(conn)
    seed_id = walk.option("Youth guarantee")
    first, second = walk.doc(), walk.doc()
    walk.record(first, "youth guarantee")
    walk.record(second, "youth guarantee")
    walk.rollup(walk.scope_id, [first, second])
    run_id, _ = walk.build(_Scripted(routes={"youth guarantee": ("Youth guarantee", False)}))
    assert walk.result(run_id).coverage[str(seed_id)]["documents"] == 2


# --- linked findings (D5) -------------------------------------------------------------


def _linked_deep_task(conn: Connection, target: _Walk, intervention: str) -> uuid.UUID:
    """An Evidence search task whose pinned walk ran ``extract`` (one IOF, one ICF)."""
    source_id = _task_row(conn, capability="evidence_search")
    scope_id = uuid.uuid4()
    conn.execute(
        evidence_scope.insert().values(
            evidence_scope_id=scope_id,
            task_id=source_id,
            intent="es",
            context={},
            created_at=now(),
        )
    )
    plan_id = uuid.uuid4()
    conn.execute(
        task_plan.insert().values(
            plan_id=plan_id,
            task_id=source_id,
            version=1,
            status="approved",
            payload={},
            created_at=now(),
            created_by="user",
        )
    )
    walk_id = uuid.uuid4()
    conn.execute(
        capability_run.insert().values(
            capability_run_id=walk_id,
            task_id=source_id,
            evidence_scope_id=scope_id,
            capability="evidence_search",
            plan_id=plan_id,
            plan_version=1,
            status="succeeded",
            started_at=now(),
        )
    )
    run_id = uuid.uuid4()
    conn.execute(
        runs.insert().values(
            run_id=run_id,
            task_id=source_id,
            status="succeeded",
            started_at=now(),
            capability_run_id=walk_id,
        )
    )
    snapshot_id = uuid.uuid4()
    conn.execute(
        source_snapshot.insert().values(
            source_snapshot_id=snapshot_id,
            content_hash=str(uuid.uuid4()),
            text_basis="full_text",
            source_locator="https://example.org/deep",
            metadata={"title": "A deep read"},
            created_at=now(),
        )
    )
    source_tss = uuid.uuid4()
    conn.execute(
        task_source_snapshot.insert().values(
            task_source_snapshot_id=source_tss,
            task_id=source_id,
            source_snapshot_id=snapshot_id,
            origin="acquired",
            run_id=None,
            ingested_at=now(),
        )
    )
    ser_ids = {}
    for profile in (IOF_PROFILE_ID, ICF_PROFILE_ID):
        ser_ids[profile] = uuid.uuid4()
        conn.execute(
            source_extraction_record.insert().values(
                extraction_record_id=ser_ids[profile],
                task_id=source_id,
                source_snapshot_id=snapshot_id,
                task_source_snapshot_id=source_tss,
                extraction_fingerprint=f"fp-{profile}",
                status="extracted",
                basis="full_text",
                run_id=run_id,
                created_at=now(),
            )
        )
    conn.execute(
        intervention_outcome_finding.insert().values(
            finding_id=uuid.uuid4(),
            task_id=source_id,
            extraction_record_id=ser_ids[IOF_PROFILE_ID],
            intervention=intervention,
            outcome="employment",
            effect_direction="increase",
            study_geography="Scotland",
            stratum_qualifiers=[],
            statistics={},
            field_coverage={},
            grounding=[{"quote": "Employment rose."}],
            created_at=now(),
        )
    )
    conn.execute(
        implementation_context_finding.insert().values(
            finding_id=uuid.uuid4(),
            task_id=source_id,
            extraction_record_id=ser_ids[ICF_PROFILE_ID],
            context_type=_icf_context_type(),
            claim="Delivery relied on local employers.",
            intervention=intervention,
            field_coverage={},
            grounding=[],
            created_at=now(),
        )
    )
    conn.execute(
        extraction_result.insert().values(
            extraction_result_id=uuid.uuid4(),
            task_id=source_id,
            evidence_scope_id=scope_id,
            run_id=run_id,
            selection_run_id=None,
            extraction_provenance={},
            docs=[
                {
                    "tss_id": str(source_tss),
                    "basis": "full_text",
                    "profiles": {
                        IOF_PROFILE_ID: {"extraction_record_id": str(ser_ids[IOF_PROFILE_ID])},
                        ICF_PROFILE_ID: {"extraction_record_id": str(ser_ids[ICF_PROFILE_ID])},
                    },
                }
            ],
            counts={},
            flags=[],
            created_at=now(),
        )
    )
    conn.execute(
        task_link.insert().values(
            link_id=uuid.uuid4(),
            source_task_id=source_id,
            target_task_id=target.task_id,
            source_capability_run_id=walk_id,
            created_by="test",
            created_at=now(),
        )
    )
    return source_id


def _icf_context_type() -> str:
    from policy_atlas.core.schema import CONTEXT_TYPES

    return CONTEXT_TYPES[0]


def test_linked_findings_cluster_beside_profile_records(conn: Connection) -> None:
    walk = _Walk(conn)
    seed_id = walk.option("Wage subsidy")
    doc = walk.doc()
    walk.record(doc, "wage subsidy")
    walk.rollup(walk.scope_id, [doc])
    source_id = _linked_deep_task(conn, walk, "wage subsidy")
    run_id, summary = walk.build(_Scripted(routes={"wage subsidy": ("Wage subsidy", False)}))
    assert summary["units"] == 3
    members = walk.memberships()
    assert sorted(m.unit_kind for m in members) == ["icf", "interventions", "iof"]
    findings = [m for m in members if m.unit_kind != "interventions"]
    assert all(m.unit_task_id == source_id and m.task_source_snapshot_id is None for m in findings)
    assert all(m.option_id == seed_id for m in members)
    coverage = walk.result(run_id).coverage[str(seed_id)]
    assert coverage["findings"] == {"iof": 1, "icf": 1}
    assert coverage["role"]["evaluated"] == 2  # the profile record and the IOF document
    assert coverage["where_tried"]["where"] == 1  # Scotland
    provenance = walk.result(run_id).provenance["links"]
    assert provenance == [
        {
            "source_task_id": str(source_id),
            "source_run_id": provenance[0]["source_run_id"],
            "ran_extract": True,
            "findings": 2,
        }
    ]


# --- rebuild (D14) ------------------------------------------------------------------


def test_the_rebuild_keeps_ids_and_user_state_and_deletes_nothing(conn: Connection) -> None:
    walk = _Walk(conn)
    walk.option("Youth guarantee", origin="added_by_you")
    doc = walk.doc()
    walk.record(doc, "youth guarantee")
    walk.record(doc, "wage subsidy")
    walk.rollup(walk.scope_id, [doc])
    first = _Scripted(
        discovered=[_discovered("Wage subsidy")],
        routes={
            "youth guarantee": ("Youth guarantee", False),
            "wage subsidy": ("Wage subsidy", False),
        },
    )
    walk.build(first)
    before = walk.options()
    exclusion = {"constraint": "Delivered through schools", "reason": "It is not.", "by": "you"}
    conn.execute(
        option.update()
        .where(option.c.option_id == before["Wage subsidy"].option_id)
        .values(state="excluded", exclusion=exclusion)
    )

    # The plan changed; the rebuild's discovery proposes nothing new and the
    # wage subsidy record now goes nowhere.
    second = _Scripted(routes={"youth guarantee": ("Youth guarantee", False)})
    run_id, summary = walk.build(second)
    after = walk.options()
    assert {name: row.option_id for name, row in after.items()} == {
        name: row.option_id for name, row in before.items()
    }
    assert after["Wage subsidy"].state == "excluded"
    assert after["Wage subsidy"].exclusion == exclusion
    # Every existing option was a seed, the clustered one included.
    seeds = [seed["label"] for seed in second.calls["discover"][0]["seeds"]]
    assert seeds == ["Youth guarantee", "Wage subsidy"]
    # Memberships are this run's only.
    members = walk.memberships()
    assert len(members) == 1
    assert {m.assigned_by_run_id for m in members} == {run_id}
    assert summary["unclustered"] == 1
    result = walk.result(run_id)
    assert result.coverage[str(after["Wage subsidy"].option_id)]["members"] == 0
    assert result.counts["excluded"] == 1 and result.counts["included"] == 1
    assert conn.execute(
        select(func.count()).select_from(longlist_result).where(
            longlist_result.c.task_id == walk.task_id
        )
    ).scalar_one() == 2


# --- failure writes nothing ------------------------------------------------------------


def test_a_clustering_failure_writes_nothing(conn: Connection) -> None:
    walk = _Walk(conn)
    walk.option("Youth guarantee")
    doc = walk.doc()
    walk.record(doc, "wage subsidy")
    walk.rollup(walk.scope_id, [doc])
    with pytest.raises(LonglistFailure):
        walk.build(_Scripted(discover_error=RuntimeError("provider down")))
    assert walk.memberships() == []
    assert set(walk.options()) == {"Youth guarantee"}
    assert walk.options()["Youth guarantee"].taxonomy_version is None
    assert conn.execute(
        select(func.count()).select_from(longlist_result).where(
            longlist_result.c.task_id == walk.task_id
        )
    ).scalar_one() == 0


# --- the stub backend ------------------------------------------------------------------


def test_the_stub_backend_matches_seeds_by_name_and_discovers_one(conn: Connection) -> None:
    walk = _Walk(conn)
    seed_id = walk.option("Youth guarantee")
    doc = walk.doc()
    walk.record(doc, "Youth guarantee")
    walk.record(doc, "something else")
    walk.rollup(walk.scope_id, [doc])
    run_id, summary = walk.build(StubLonglistBackend())
    assert summary["options"] == 2 and summary["units"] == 2
    options = walk.options()
    assert options[STUB_DISCOVERED_LABEL].origin == "clustered"
    assert options["Youth guarantee"].option_id == seed_id
    assert all(row.primary_lever_type == "provide a service" for row in options.values())
    assert all(row.ambition == "incremental" for row in options.values())
    # Themes are the ``theme`` component's (task 046, R28): none written here.
    assert walk.result(run_id).themes == []


def test_the_harness_runs_longlist_on_the_stub_backends(conn: Connection) -> None:
    """The ``longlist`` node is real."""
    from policy_atlas.core.inference import StubEchoProvider
    from policy_atlas.runtime.harness import run_harness
    from policy_atlas.runtime.run_spec import Plan, compile

    walk = _Walk(conn)
    seed_id = walk.option("Youth guarantee")
    run_id = walk.run()
    outcome = run_harness(
        conn,
        config=compile(Plan(component="longlist", evidence_scope_id=walk.scope_id)),
        task_id=walk.task_id,
        run_id=run_id,
        provider=StubEchoProvider(),
    )
    assert outcome["error"] is None
    assert outcome["summary"] == {
        "options": 1,
        "unclustered": 0,
        "not_an_option": 0,
        "none_fits": 0,
        "units": 0,
    }
    assert walk.result(run_id).coverage[str(seed_id)]["members"] == 0


# --- task 046: units from the longlist scope and the add walks (S3, AM5) ---------


def _extraction(
    walk: _Walk, tss_id: uuid.UUID, *, fingerprint: str, created_at: datetime | None = None
) -> uuid.UUID:
    """A second extraction record of a document, under its own fingerprint."""
    snapshot_id = walk.conn.execute(
        select(task_source_snapshot.c.source_snapshot_id).where(
            task_source_snapshot.c.task_source_snapshot_id == tss_id
        )
    ).scalar_one()
    ser_id = uuid.uuid4()
    walk.conn.execute(
        source_extraction_record.insert().values(
            extraction_record_id=ser_id,
            task_id=walk.task_id,
            source_snapshot_id=snapshot_id,
            task_source_snapshot_id=tss_id,
            extraction_fingerprint=fingerprint,
            status="extracted",
            basis="abstract_only",
            run_id=walk.extract_run,
            created_at=created_at or now(),
        )
    )
    return ser_id


def _record_under(walk: _Walk, ser_id: uuid.UUID, intervention: str, **values: Any) -> uuid.UUID:
    record_id = uuid.uuid4()
    row: dict[str, Any] = {
        "record_id": record_id,
        "task_id": walk.task_id,
        "extraction_record_id": ser_id,
        "intervention": intervention,
        "role": "evaluated",
        "design_features": [],
        "is_bundle": False,
        "components": [],
        "field_coverage": {},
        "grounding": [{"quote": f"We studied {intervention}."}],
        "created_at": now(),
    }
    row.update(values)
    walk.conn.execute(intervention_profile_record.insert().values(**row))
    return record_id


def _rollup_of(walk: _Walk, scope_id: uuid.UUID, docs: dict[uuid.UUID, uuid.UUID]) -> None:
    """A roll-up naming, per document, the given extraction record."""
    walk.conn.execute(
        extraction_result.insert().values(
            extraction_result_id=uuid.uuid4(),
            task_id=walk.task_id,
            evidence_scope_id=scope_id,
            run_id=walk.run(),
            selection_run_id=None,
            extraction_provenance={},
            docs=[
                {
                    "tss_id": str(tss_id),
                    "basis": "abstract_only",
                    "profiles": {INTERVENTIONS_PROFILE_ID: {"extraction_record_id": str(ser)}},
                }
                for tss_id, ser in docs.items()
            ],
            counts={},
            flags=[],
            created_at=now(),
        )
    )


def _current_fingerprint(walk: _Walk) -> str:
    return sorted(
        current_profile_fingerprints(walk.conn, task_id=walk.task_id, scope_id=walk.scope_id)
    )[0]


def test_a_rebuild_of_a_task_built_before_this_slice_counts_no_document_twice(
    conn: Connection,
) -> None:
    """AM5: an old full-chain child scope with records supplies no unit."""
    walk = _Walk(conn)
    seed = walk.option("Youth guarantee", origin="added_by_you")
    doc = walk.doc()
    # The pre-046 build: its child screened and profiled the document under the
    # context-free fingerprint.
    old_build = walk._walk(walk._scope("longlist"), status="succeeded")
    old_child = walk.child_scope(seed, parent=old_build, started_at=now() - timedelta(hours=1))
    old_ser = _extraction(walk, doc, fingerprint="pre-046", created_at=now() - timedelta(hours=1))
    _record_under(walk, old_ser, "youth guarantee")
    _rollup_of(walk, old_child, {doc: old_ser})
    # This build's longlist scope profiled it again, under the plan's context.
    new_ser = _extraction(walk, doc, fingerprint=_current_fingerprint(walk))
    _record_under(walk, new_ser, "youth guarantee")
    _rollup_of(walk, walk.scope_id, {doc: new_ser})
    backend = _Scripted(routes={"youth guarantee": ("Youth guarantee", False)})
    run_id, summary = walk.build(backend)
    assert summary["units"] == 1
    result = walk.result(run_id)
    assert result.counts["documents"] == 1
    assert result.provenance["scopes"]["targeted"] == []
    assert len(walk.memberships()) == 1


def test_a_document_profiled_in_two_scopes_counts_once_under_the_current_context(
    conn: Connection,
) -> None:
    """An add walk and the longlist scope profiled one document under two
    contexts: only the current context's extraction is read."""
    walk = _Walk(conn)
    seed = walk.option("Youth guarantee", origin="added_by_you")
    doc = walk.doc()
    add_search = walk.child_scope(seed, parentless=True)
    stale = _extraction(walk, doc, fingerprint="older plan", created_at=now())
    _record_under(walk, stale, "youth guarantee")
    _record_under(walk, stale, "wage subsidy")
    _rollup_of(walk, add_search, {doc: stale})
    current = _extraction(
        walk, doc, fingerprint=_current_fingerprint(walk), created_at=now() - timedelta(hours=1)
    )
    kept = _record_under(walk, current, "youth guarantee", population_tag="on_target")
    _rollup_of(walk, walk.scope_id, {doc: current})
    backend = _Scripted(routes={"youth guarantee": ("Youth guarantee", False)})
    run_id, summary = walk.build(backend)
    assert summary["units"] == 1
    assert [m.unit_id for m in walk.memberships()] == [kept]
    assert walk.result(run_id).provenance["scopes"]["superseded_records"] == 2


def test_a_record_tagged_under_another_context_reads_as_not_tagged(conn: Connection) -> None:
    """S3 (a): tags pass through only under the current plan's fingerprint."""
    walk = _Walk(conn)
    walk.option("Youth guarantee", origin="added_by_you")
    current_doc, stale_doc = walk.doc(), walk.doc()
    tags = {"population_tag": "adjacent", "outcome_tag": "the NEET rate", "object_tag": "option"}
    current = _extraction(walk, current_doc, fingerprint=_current_fingerprint(walk))
    _record_under(walk, current, "youth guarantee", **tags)
    stale = _extraction(walk, stale_doc, fingerprint="older plan")
    _record_under(walk, stale, "wage subsidy", **tags)
    _rollup_of(walk, walk.scope_id, {current_doc: current, stale_doc: stale})
    backend = _Scripted(discovered=[_discovered("Wage subsidy")])
    walk.build(backend)
    records = {r["intervention"]: r for r in backend.calls["assign"][0]["records"]}
    assert {k: records["youth guarantee"][k] for k in tags} == tags
    assert {k: records["wage subsidy"][k] for k in tags} == dict.fromkeys(tags)


# --- task 046: reader grain (items 1, 2, 4, 6, 7, 15, 26) -------------------------


def _tagged(walk: _Walk, tss_id: uuid.UUID, intervention: str, **values: Any) -> uuid.UUID:
    """A record of the document under the current plan's tagging context."""
    ser_id = walk._ser.get(tss_id)
    if ser_id is None:
        ser_id = _extraction(walk, tss_id, fingerprint=_current_fingerprint(walk))
        walk._ser[tss_id] = ser_id
    return _record_under(walk, ser_id, intervention, **values)


def test_the_digest_folds_names_and_counts_records_by_role() -> None:
    digest, names = corpus_digest(
        [
            ("Youth guarantee", "evaluated"),
            ("youth  GUARANTEE", "described"),
            ("Youth guarantee", "evaluated"),
            ("Wage subsidy", "mentioned"),
            (None, "evaluated"),
            ("Apprenticeships", None),
        ]
    )
    assert names == 3
    assert digest == [
        {"name": "Youth guarantee", "records": 3, "roles": {"evaluated": 2, "described": 1}},
        {"name": "Apprenticeships", "records": 1, "roles": {}},
        {"name": "Wage subsidy", "records": 1, "roles": {"mentioned": 1}},
    ]
    capped, total = corpus_digest([(f"name {i}", "evaluated") for i in range(450)])
    assert (len(capped), total) == (400, 450)


def test_no_discovery_call_receives_unit_payloads(conn: Connection) -> None:
    walk = _Walk(conn)
    walk.option("Youth guarantee", origin="added_by_you")
    first, second = walk.doc(), walk.doc()
    walk.record(first, "youth guarantee")
    walk.record(first, "wage subsidy", role="described")
    walk.record(second, "Youth Guarantee", role="recommended")
    walk.rollup(walk.scope_id, [first, second])
    backend = _Scripted(discovered=[_discovered("Wage subsidy")])
    run_id, _ = walk.build(backend)
    call = backend.calls["discover"][0]
    assert "records" not in call
    sent = repr(call)
    assert "We studied" not in sent  # no quote, no unit record
    assert all(str(m.unit_id) not in sent for m in walk.memberships())
    assert call["digest"] == [
        {"name": "Youth Guarantee", "records": 2, "roles": {"evaluated": 1, "recommended": 1}},
        {"name": "wage subsidy", "records": 1, "roles": {"described": 1}},
    ]
    assert call["seeds"][0]["origin"] == "added by you"
    assert call["plan"] == {
        "question": "What could reduce the number of young people not in work?",
        "intended_change": "Reduce the number of young people not in work",
        "target_unit": "16 to 24 year olds",
        "outcomes": ["the NEET rate"],
    }
    assert walk.result(run_id).provenance["digest"] == {"units": 3, "names": 2, "shown": 2}


def test_the_option_count_never_exceeds_the_hard_ceiling(conn: Connection) -> None:
    walk = _Walk(conn)
    for name in ("Seed one", "Seed two", "Seed three"):
        walk.option(name, origin="added_by_you")
    doc = walk.doc()
    walk.record(doc, "anything")
    walk.rollup(walk.scope_id, [doc])
    backend = _Scripted(
        discovered=[_discovered(f"Discovered {i}") for i in range(30)],
        routes={"anything": ("Discovered 0", False)},
    )
    run_id, summary = walk.build(backend)
    assert backend.calls["discover"][0]["max_new"] == 22
    assert summary["options"] == LONGLIST_HARD_CEILING
    ceiling = walk.result(run_id).provenance["ceiling"]
    assert (ceiling["over_ceiling_dropped"], ceiling["excess"]) == (8, 0)
    assert len(walk.options()) == LONGLIST_HARD_CEILING


def test_a_suggested_seed_folds_into_a_wider_option_and_shows_as_its_variant(
    conn: Connection,
) -> None:
    walk = _Walk(conn)
    seed = walk.option("Named breakfast programme", origin="suggested")
    doc = walk.doc()
    walk.record(doc, "school breakfast clubs")
    walk.rollup(walk.scope_id, [doc])
    backend = _Scripted(
        discovered=[_discovered("School food provision")],
        folds=[
            FoldWire(seed_label="Named breakfast programme", into_label="School food provision")
        ],
        routes={"school breakfast clubs": ("School food provision", False)},
    )
    run_id, summary = walk.build(backend)
    options = walk.options()
    wider = options["School food provision"]
    folded = options["Named breakfast programme"]
    # The existing merge: the seed row stays, merged into the new option.
    assert folded.option_id == seed and folded.merged_into_option_id == wider.option_id
    assert folded.name == "Named breakfast programme"
    assert summary["options"] == 1
    # No unit can be assigned to a folded seed.
    offered = [o["label"] for o in backend.calls["assign"][0]["options"]]
    assert offered == ["School food provision"]
    result = walk.result(run_id)
    variants = result.coverage[str(wider.option_id)]["variants"]
    assert variants[0] == {
        "name": "Named breakfast programme",
        "documents": 0,
        "folded_seed": True,
    }
    assert str(seed) not in result.coverage
    assert result.counts["folded"] == 1
    assert result.provenance["folds"]["accepted"] == [
        {
            "seed_id": str(seed),
            "seed_label": "Named breakfast programme",
            "into_id": str(wider.option_id),
            "into_label": "School food provision",
        }
    ]


def test_a_user_s_option_and_a_user_held_seed_are_never_folded(conn: Connection) -> None:
    walk = _Walk(conn)
    own = walk.option("My own option", origin="added_by_you")
    held = walk.option(
        "Held suggestion",
        exclusion={"constraint": None, "reason": "Keep it.", "by": "user"},
    )
    target = walk.option("Wider option")
    doc = walk.doc()
    walk.record(doc, "something")
    walk.rollup(walk.scope_id, [doc])
    backend = _Scripted(
        folds=[
            FoldWire(seed_label="My own option", into_label="Wider option"),
            FoldWire(seed_label="Held suggestion", into_label="Wider option"),
        ],
        routes={"something": ("Wider option", False)},
    )
    run_id, summary = walk.build(backend)
    options = walk.options()
    assert options["My own option"].option_id == own
    assert options["My own option"].merged_into_option_id is None
    assert options["Held suggestion"].option_id == held
    assert options["Held suggestion"].merged_into_option_id is None
    assert options["Wider option"].option_id == target
    assert summary["options"] == 3
    folds = walk.result(run_id).provenance["folds"]
    assert folds["accepted"] == []
    assert folds["rejected_by_reason"] == {"added_by_you": 1, "user_held": 1}


def test_a_fold_into_an_unknown_label_or_a_folded_seed_is_rejected_and_counted(
    conn: Connection,
) -> None:
    walk = _Walk(conn)
    walk.option("Seed A")
    walk.option("Seed B")
    walk.option("Seed C")
    doc = walk.doc()
    walk.record(doc, "something")
    walk.rollup(walk.scope_id, [doc])
    backend = _Scripted(
        discovered=[_discovered("Wider")],
        folds=[
            FoldWire(seed_label="Seed A", into_label="Nowhere"),
            FoldWire(seed_label="Seed B", into_label="Wider"),
            FoldWire(seed_label="Seed C", into_label="Seed B"),
            FoldWire(seed_label="Seed B", into_label="Seed A"),
            FoldWire(seed_label="Seed A", into_label="Seed A"),
            FoldWire(seed_label="Not a seed", into_label="Wider"),
        ],
        routes={"something": ("Wider", False)},
    )
    run_id, summary = walk.build(backend)
    options = walk.options()
    assert options["Seed B"].merged_into_option_id == options["Wider"].option_id
    assert options["Seed A"].merged_into_option_id is None
    assert options["Seed C"].merged_into_option_id is None
    assert summary["options"] == 3
    folds = walk.result(run_id).provenance["folds"]
    assert folds["rejected_by_reason"] == {
        "unknown_target": 1,
        "into_folded_seed": 1,
        "already_folded": 1,
        "into_itself": 1,
        "unknown_seed": 1,
    }
    assert len(folds["rejected"]) == 5


def test_the_residual_pass_runs_once_over_the_unclustered_units(conn: Connection) -> None:
    walk = _Walk(conn)
    walk.option("Youth guarantee", origin="added_by_you")
    doc = walk.doc()
    walk.record(doc, "youth guarantee")
    walk.record(doc, "wage subsidy")
    walk.record(doc, "a theory of change")
    walk.record(doc, "something else")
    walk.rollup(walk.scope_id, [doc])
    backend = _Scripted(
        residual_discovered=[_discovered("Wage subsidy")],
        routes={
            "youth guarantee": ("Youth guarantee", False),
            # Unknown in the first pass (the engine's repair leaves it
            # residual), placed once the residual pass discovers it.
            "wage subsidy": ("Wage subsidy", False),
            "a theory of change": (NOT_AN_OPTION_LABEL, False),
        },
    )
    run_id, summary = walk.build(backend)
    calls = backend.calls["discover"]
    assert [call["residual"] for call in calls] == [False, True]
    residual = calls[1]
    assert [seed["origin"] for seed in residual["seeds"]] == ["on the list"]
    assert residual["max_new"] == LONGLIST_HARD_CEILING - 1
    # Its digest covers the unclustered units only (not the not-an-option one).
    assert {entry["name"] for entry in residual["digest"]} == {"wage subsidy", "something else"}
    # Its assignment offers every option.
    assert {o["label"] for o in backend.calls["assign"][-1]["options"]} == {
        "Youth guarantee",
        "Wage subsidy",
    }
    assert summary == {
        "options": 2,
        "unclustered": 1,
        "not_an_option": 1,
        "none_fits": 0,
        "units": 4,
    }
    wage = walk.options()["Wage subsidy"]
    assert wage.origin == "clustered"
    assert [m.option_id for m in walk.memberships()].count(wage.option_id) == 1
    record = walk.result(run_id).provenance["residual_pass"]
    assert record["ran"] is True
    assert (record["units"], record["new_options"], record["units_placed"]) == (2, 1, 1)
    assert record["units_left"] == 1


def test_the_residual_pass_is_skipped_with_no_room_or_nothing_unclustered(
    conn: Connection,
) -> None:
    walk = _Walk(conn)
    for i in range(25):
        walk.option(f"Seed option {i}", origin="added_by_you")
    doc = walk.doc()
    walk.record(doc, "something else")
    walk.rollup(walk.scope_id, [doc])
    backend = _Scripted(residual_discovered=[_discovered("Never")])
    run_id, summary = walk.build(backend)
    assert backend.calls["discover"] == []  # no room, nothing foldable
    assert summary["unclustered"] == 1
    record = walk.result(run_id).provenance["residual_pass"]
    assert (record["ran"], record["skipped"]) == (False, "no room under the ceiling")

    other = _Walk(conn)
    other.option("Youth guarantee", origin="added_by_you")
    placed = other.doc()
    other.record(placed, "youth guarantee")
    other.rollup(other.scope_id, [placed])
    backend = _Scripted(routes={"youth guarantee": ("Youth guarantee", False)})
    run_id, _ = other.build(backend)
    assert [call["residual"] for call in backend.calls["discover"]] == [False]
    record = other.result(run_id).provenance["residual_pass"]
    assert (record["ran"], record["skipped"]) == (False, "no unclustered unit")


def test_prompts_carry_short_ids_and_a_mangled_one_is_repaired_without_a_call(
    conn: Connection,
) -> None:
    walk = _Walk(conn)
    seed = walk.option("Youth guarantee", origin="added_by_you")
    doc = walk.doc()
    for i in range(3):
        walk.record(doc, f"youth guarantee {i}")
    walk.rollup(walk.scope_id, [doc])
    mangled = {"u1": "U1", "u2": " u2 ", "u3": "3"}
    backend = _Scripted(
        routes={f"youth guarantee {i}": ("Youth guarantee", False) for i in range(3)},
        mangle=lambda unit_id: mangled[unit_id],
    )
    run_id, summary = walk.build(backend)
    records = backend.calls["assign"][0]["records"]
    assert [r["unit_id"] for r in records] == ["u1", "u2", "u3"]
    assert all(str(m.unit_id) not in repr(backend.calls["assign"]) for m in walk.memberships())
    # One assignment call: the three ids were repaired in code.
    assert len(backend.calls["assign"]) == 1
    assert summary["unclustered"] == 0
    assert [m.option_id for m in walk.memberships()] == [seed] * 3
    assert walk.result(run_id).provenance["clustering"]["short_id_repairs"] == 3


def test_a_discovered_option_s_outcomes_are_the_plan_outcomes_its_members_name(
    conn: Connection,
) -> None:
    plan = scoping_plan(
        outcomes=[
            {"text": "the NEET rate", "origin": "assumed"},
            {"text": "employment", "origin": "assumed"},
        ]
    )
    walk = _Walk(conn, plan)
    seed = walk.option("Youth guarantee", origin="added_by_you")
    first, second = walk.doc(), walk.doc()
    _tagged(walk, first, "wage subsidy", outcome_tag="employment")
    _tagged(walk, first, "wage subsidy scheme", outcome_tag="other")
    _tagged(walk, second, "mentoring", outcome_tag="other")
    walk.rollup(walk.scope_id, [first, second])
    backend = _Scripted(
        discovered=[_discovered("Wage subsidy"), _discovered("Mentoring")],
        routes={
            "wage subsidy": ("Wage subsidy", False),
            "wage subsidy scheme": ("Wage subsidy", False),
            "mentoring": ("Mentoring", False),
        },
    )
    walk.build(backend)
    options = walk.options()
    plan_outcomes = {"the NEET rate", "employment"}
    wage = options["Wage subsidy"]
    assert wage.outcomes == ["employment"]
    assert wage.design["outcomes_served"] == ["employment"]
    assert set(wage.outcomes) <= plan_outcomes
    assert options["Mentoring"].outcomes == []
    # A seed keeps its design's outcomes.
    assert options["Youth guarantee"].option_id == seed
    assert options["Youth guarantee"].outcomes == ["the NEET rate"]


def test_typing_batches_run_in_parallel(conn: Connection) -> None:
    walk = _Walk(conn)
    for i in range(41):  # three batches of at most 20
        walk.option(f"Seed option {i}", origin="added_by_you")
    barrier = threading.Barrier(3, timeout=10)

    class _Together(_Scripted):
        def type_options(self, **kwargs: Any) -> Any:
            barrier.wait()  # only passes when the three batches are in flight at once
            return super().type_options(**kwargs)

    backend = _Together()
    run_id, _ = walk.build(backend)
    typing = walk.result(run_id).provenance["typing"]
    assert (typing["calls"], typing["failed_batches"], typing["invalid"]) == (3, 0, 0)
    assert all(row.primary_lever_type == "subsidise" for row in walk.options().values())


def test_an_invalid_typing_keeps_the_previous_values_version_and_runner_up(
    conn: Connection,
) -> None:
    walk = _Walk(conn)
    walk.option("Free bus passes")
    walk.build(_Scripted(typings={"Free bus passes": {"runner_up_lever_type": "inform"}}))
    before = walk.options()["Free bus passes"]
    # Typed under the earlier list: the version must survive a failed typing.
    conn.execute(
        option.update()
        .where(option.c.option_id == before.option_id)
        .values(taxonomy_version="lever_types_v1")
    )
    run_id, _ = walk.build(
        _Scripted(typings={"Free bus passes": {"primary_lever_type": "make it so"}})
    )
    after = walk.options()["Free bus passes"]
    assert (after.primary_lever_type, after.ambition, after.ambition_reason) == (
        before.primary_lever_type,
        before.ambition,
        before.ambition_reason,
    )
    assert after.secondary_lever_types == before.secondary_lever_types
    assert after.taxonomy_version == "lever_types_v1"
    result = walk.result(run_id)
    assert result.counts["typing_invalid"] == 1
    assert result.provenance["typing"]["kept_ids"] == [str(before.option_id)]
    assert result.provenance["runner_up"] == {
        str(before.option_id): {"lever_type": "inform", "carried_forward": True}
    }


def test_each_thinning_rule_with_its_count_and_never_on_a_tag(conn: Connection) -> None:
    walk = _Walk(conn)
    walk.option("Youth guarantee", origin="added_by_you")
    bare, collapse, crowded = walk.doc(), walk.doc(), walk.doc()
    # Rule 1: a bare mention goes; a mention with a feature or an outcome stays.
    walk.record(bare, "passing mention", role="mentioned")
    walk.record(bare, "featured mention", role="mentioned", design_features=["free"])
    walk.record(bare, "outcome mention", role="mentioned", outcome="employment")
    # Rule 2: the same folded name in one document collapses to the highest role.
    walk.record(collapse, "Youth guarantee", role="described")
    kept_evaluated = walk.record(collapse, "youth  GUARANTEE", role="evaluated")
    # Rule 3: at most eight a document, by role; the two mentions go.
    for i in range(7):
        walk.record(crowded, f"programme {i}", role="evaluated")
    walk.record(crowded, "recommended one", role="recommended")
    for i in range(2):
        walk.record(crowded, f"mentioned {i}", role="mentioned", outcome="x")
    # A tag never drops a record.
    tagged_doc = walk.doc()
    _tagged(
        walk,
        tagged_doc,
        "other-tagged",
        population_tag="other",
        outcome_tag="other",
        object_tag="neither",
    )
    walk.rollup(walk.scope_id, [bare, collapse, crowded, tagged_doc])
    backend = _Scripted(routes={"youth GUARANTEE": ("Youth guarantee", False)})
    run_id, summary = walk.build(backend)
    result = walk.result(run_id)
    assert result.provenance["thinning"] == {
        "mentioned_without_features_or_outcome": 1,
        "same_name_in_document": 1,
        "over_document_cap": 2,
        "document_cap": RECORDS_PER_DOCUMENT_MAX,
    }
    assert summary["units"] == 2 + 1 + 8 + 1
    sent = {r["intervention"] for call in backend.calls["assign"] for r in call["records"]}
    assert "other-tagged" in sent
    assert "passing mention" not in sent
    assert not {"mentioned 0", "mentioned 1"} & sent
    assert kept_evaluated in {m.unit_id for m in walk.memberships()}


def test_the_title_only_count_is_copied_from_the_extract_summary(conn: Connection) -> None:
    walk = _Walk(conn)
    walk.option("Youth guarantee", origin="added_by_you")
    doc = walk.doc()
    walk.record(doc, "youth guarantee")
    walk.rollup(walk.scope_id, [doc], counts={"title_only": 3})
    run_id, _ = walk.build(_Scripted(routes={"youth guarantee": ("Youth guarantee", False)}))
    assert walk.result(run_id).counts["title_only"] == 3
