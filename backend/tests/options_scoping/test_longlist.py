"""The ``longlist`` component (task 045 Phase 5.2, S8; contract deliverable 6).

The contract's longlist bullet: every record lands in one option, unclustered
or not an option (code-enforced); a document with three records can belong to
three options; a bundle mints a package with *part of* rows; each option has
one primary lever type from the list or *none fits* with a reason, the
taxonomy version and an ambition tag with its justification; the runner-up is
in ``longlist_result`` and not on the option row; coverage buckets Unknown and
Non-evidence separately, shows the role funnel, where tried grouped against
Where, settings, and counts flagged members; two documents sharing a DOI count
once and stay two membership rows; seeds are assigned against and survive with
zero members; linked findings cluster beside profile records (D5); the
rebuild keeps ids and user state and deletes nothing; comparator records never
become members. Seeded on the transactional ``conn`` fixture, with a scripted
backend standing in for the model.
"""

from __future__ import annotations

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
    TYPING_INVALID_REASON,
    LonglistContext,
    LonglistFailure,
    discovery_ceiling,
    longlist_scope,
    theme_ceiling,
)
from policy_atlas.options_scoping.longlist.longlist_backend import (
    STUB_DISCOVERED_LABEL,
    StubLonglistBackend,
)
from policy_atlas.options_scoping.longlist.longlist_cluster_prompt import (
    NOT_AN_OPTION_LABEL,
    DiscoveredOptionWire,
    OptionAssignmentsResponse,
    OptionAssignmentWire,
    OptionDiscoveryResponse,
)
from policy_atlas.options_scoping.longlist.longlist_theme_prompt import (
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
        "outcomes_served": ["the NEET rate"],
        "is_bundle": False,
        "components": [],
    }
    values.update(overrides)
    return DiscoveredOptionWire.model_validate(values)


def _typing(unit_id: str, **overrides: Any) -> LeverTypingWire:
    values: dict[str, Any] = {
        "unit_id": unit_id,
        "primary_lever_type": "subsidise",
        "secondary_lever_types": ["inform"],
        "runner_up_lever_type": None,
        "runner_up_reason": None,
        "none_fits_reason": None,
        "lever_reason": "The defining feature is a payment.",
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
    routes: dict[str, tuple[str, bool]] = field(default_factory=dict)
    typings: dict[str, dict[str, Any]] = field(default_factory=dict)
    discover_error: Exception | None = None
    calls: dict[str, list[dict[str, Any]]] = field(
        default_factory=lambda: {"discover": [], "assign": [], "themes": [], "type": []}
    )
    mode: str = "stub"

    def discover(
        self,
        *,
        question: str,
        seeds: list[dict[str, object]],
        records: list[dict[str, object]],
        max_new: int,
    ) -> UsageResult[OptionDiscoveryResponse]:
        self.calls["discover"].append(
            {"question": question, "seeds": seeds, "records": records, "max_new": max_new}
        )
        if self.discover_error is not None:
            raise self.discover_error
        return OptionDiscoveryResponse(options=self.discovered), None

    def assign(
        self, *, options: list[dict[str, object]], records: list[dict[str, object]]
    ) -> UsageResult[OptionAssignmentsResponse]:
        self.calls["assign"].append({"options": options, "records": records})
        out = []
        for record in records:
            label, flag = self.routes.get(str(record.get("intervention")), ("ungroupable", False))
            out.append(
                OptionAssignmentWire(
                    unit_id=str(record["unit_id"]),
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
        self, *, options: list[dict[str, object]]
    ) -> UsageResult[LeverTypingResponse]:
        self.calls["type"].append({"options": options})
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

    def rollup(self, scope_id: uuid.UUID, tss_ids: list[uuid.UUID]) -> None:
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
                counts={},
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


@pytest.mark.parametrize(("units", "ceiling"), [(10, 8), (100, 25), (400, 40)])
def test_the_discovery_ceiling_is_clamp_ceil_n_over_4_8_40(units: int, ceiling: int) -> None:
    assert discovery_ceiling(units) == ceiling


@pytest.mark.parametrize(("options", "ceiling"), [(2, 3), (20, 7), (60, 12)])
def test_the_theme_ceiling_is_clamp_ceil_n_over_3_3_12(options: int, ceiling: int) -> None:
    assert theme_ceiling(options) == ceiling


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
        "themes": 1,
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
    assert discover["max_new"] == discovery_ceiling(5) - 1


def test_a_discovered_bundle_mints_a_package_with_part_of_rows(conn: Connection) -> None:
    walk = _Walk(conn)
    seed_id = walk.option("Careers advice")
    doc = walk.doc()
    walk.record(doc, "careers advice")
    walk.record(doc, "mentoring")
    walk.record(doc, "guarantee package", is_bundle=True, components=["mentoring", "advice"])
    walk.rollup(walk.scope_id, [doc])
    backend = _Scripted(
        discovered=[
            _discovered("Mentoring"),
            _discovered(
                "Guarantee package", is_bundle=True, components=["mentoring", "Careers advice"]
            ),
        ],
        routes={
            "careers advice": ("Careers advice", False),
            "mentoring": ("Mentoring", False),
            "guarantee package": ("Guarantee package", False),
        },
    )
    walk.build(backend)
    options = walk.options()
    package = options["Guarantee package"].option_id
    relations = {
        (row.from_option_id, row.to_option_id, row.kind, row.created_by)
        for row in conn.execute(
            select(option_relation).where(option_relation.c.task_id == walk.task_id)
        )
    }
    assert relations == {
        (options["Mentoring"].option_id, package, "part_of", "longlist"),
        (seed_id, package, "part_of", "longlist"),
    }


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


def test_the_option_searches_records_join_the_longlist_scope_s(conn: Connection) -> None:
    walk = _Walk(conn)
    seed = walk.option("Youth guarantee", origin="added_by_you")
    broad = walk.doc()
    targeted = walk.doc()
    walk.record(broad, "youth guarantee")
    walk.record(targeted, "youth guarantee")
    walk.rollup(walk.scope_id, [broad])
    child = walk.child_scope(seed)
    walk.rollup(child, [broad, targeted])  # the same document in both: one unit
    run_id, summary = walk.build(
        _Scripted(routes={"youth guarantee": ("Youth guarantee", False)})
    )
    assert summary["units"] == 2
    assert walk.result(run_id).provenance["scopes"]["targeted"] == [str(child)]


def test_a_rebuild_reads_every_option_s_latest_finished_search_whatever_its_parent(
    conn: Connection,
) -> None:
    """A1/B1: an earlier build's option search and the verb *add*'s parentless
    one are read by the next build (a rebuild searches only new entrants); a
    failed search is not, and per option only the latest finished one is."""
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
    assert summary["units"] == 2
    assert walk.result(run_id).provenance["scopes"]["targeted"] == [
        str(add_search),
        str(kept),
    ]


def test_seeds_survive_with_zero_members_and_no_discovery_past_the_ceiling(
    conn: Connection,
) -> None:
    walk = _Walk(conn)
    seeds = [walk.option(f"Seed option {i}") for i in range(9)]
    doc = walk.doc()
    walk.record(doc, "Seed option 0")
    walk.rollup(walk.scope_id, [doc])
    backend = _Scripted(routes={"Seed option 0": ("Seed option 0", False)})
    run_id, summary = walk.build(backend)
    # Nine seeds over one unit: the ceiling (8) is below the seeds, so every
    # seed is offered, no new option is asked for, and no call is made.
    assert backend.calls["discover"] == []
    assert summary["options"] == 9
    result = walk.result(run_id)
    assert result.provenance["ceiling"]["max_labels"] == 9
    assert result.provenance["ceiling"]["max_new"] == 0
    empty = result.coverage[str(seeds[5])]
    assert empty["members"] == 0 and empty["documents"] == 0
    assert result.counts["seeds_without_members"] == 8
    assert set(walk.options()) == {f"Seed option {i}" for i in range(9)}


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
            "Free bus passes": {
                "runner_up_lever_type": "provide a service",
                "runner_up_reason": "The pass is delivered by the operator.",
            },
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
    for name in ("Garbled", "Wrong band"):
        assert options[name].primary_lever_type is None
        assert options[name].lever_none_fits_reason == TYPING_INVALID_REASON
        assert options[name].taxonomy_version == TAXONOMY_VERSION
    # The two invalid typings count once, under typing_invalid (F14).
    assert summary["none_fits"] == 1
    result = walk.result(run_id)
    assert result.counts["none_fits"] == 1
    assert result.counts["typing_invalid"] == 2
    # The runner-up is in the record only.
    assert result.provenance["runner_up"] == {
        str(bus.option_id): {
            "lever_type": "provide a service",
            "reason": "The pass is delivered by the operator.",
        }
    }
    assert "runner_up" not in dict(bus._mapping)
    assert "provide a service" not in bus.secondary_lever_types


def test_a_failed_typing_call_is_typing_invalid_never_a_crash(conn: Connection) -> None:
    walk = _Walk(conn)
    walk.option("Youth guarantee")

    class _Broken(_Scripted):
        def type_options(self, *, options: list[dict[str, object]]) -> Any:
            raise RuntimeError("provider down")

    run_id, summary = walk.build(_Broken())
    assert summary["none_fits"] == 0
    assert walk.result(run_id).counts["typing_invalid"] == 1
    assert walk.options()["Youth guarantee"].lever_none_fits_reason == TYPING_INVALID_REASON


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
    walk.record(nowhere, "youth guarantee", role="mentioned", study_geography="a large city")
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
    assert walk.result(run_id).themes[0]["option_ids"] == [
        str(seed_id),
        str(options[STUB_DISCOVERED_LABEL].option_id),
    ]


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
        "themes": 1,
        "unclustered": 0,
        "not_an_option": 0,
        "none_fits": 0,
        "units": 0,
    }
    assert walk.result(run_id).coverage[str(seed_id)]["members"] == 0
