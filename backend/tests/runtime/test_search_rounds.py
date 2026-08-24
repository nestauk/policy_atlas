"""Runner round-loop tests (task 029): standard/deep repeat acquire+screen.

The gate lives in the runner's walk: after screen_abstract completes and the
walk is about to enter classify, standard/deep re-open the acquire and
screen_abstract components until the depth's ``round_cap`` or a yield collapse
(``short_circuit``). Every input is recomputed from persisted state (coverage
rows, the screen run's own rows), so the loop is park/resume-safe by
construction — these tests pin the row-level evidence of that design.
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.core.schema import search_coverage_record
from policy_atlas.evidence_base.sourcing.acquire import BackendCaps
from policy_atlas.evidence_base.sourcing.search_loop import DEPTH_CONSTANTS
from policy_atlas.runtime import steering_bundles
from policy_atlas.runtime.runner import NullIO, RunnerBackends, run_plan
from tests.helpers import oa_record
from tests.runtime.test_runner import _base_plan, _cleanup, _seed_project


class ScriptableSearchBackend:
    """OpenAlex-shaped backend with two yield modes.

    ``replay=False`` (default): fresh records on every call, so dedup never
    exhausts the stream and the loop can run to its round cap.
    ``replay=True``: the same ``per_call`` records on every call — round 1
    acquires them once, round 2 dedups to zero new documents and the round
    gate's ``short_circuit`` fires. This mirrors real fixture backends.
    """

    name = "openalex"
    trust_class = "academic_aggregator"
    mode = "scripted"
    caps = BackendCaps(has_snowball=False, has_title_lookup=False)

    def __init__(self, *, per_call: int = 2, replay: bool = False) -> None:
        self.per_call = per_call
        self.replay = replay
        self.calls = 0

    def search(
        self,
        query: str,
        *,
        wire_params: dict[str, str] | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        self.calls += 1
        stem = "fixed" if self.replay else f"r{self.calls}n"
        return [
            oa_record(f"{stem}{index}", title=f"Record {stem}{index}")
            for index in range(self.per_call)
        ]

    def fetch_citations(
        self, record_id: str, *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("caps.has_snowball=False")

    def fetch_references(
        self, record_ids: list[str], *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("caps.has_snowball=False")

    def lookup_title(self, title: str) -> list[dict[str, Any]]:
        raise NotImplementedError("caps.has_title_lookup=False")

    def lookup_dois(
        self, dois: list[str], *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("caps.has_doi_lookup=False")


def _coverage_rows(engine: Engine, project_id: uuid.UUID) -> list[Any]:
    with engine.connect() as conn:
        return list(
            conn.execute(
                select(search_coverage_record)
                .where(search_coverage_record.c.project_id == project_id)
                .order_by(search_coverage_record.c.created_at)
            )
        )


def _spine_plan(**overrides: Any) -> Any:
    """Mandatory spine only: the round loop is the subject, not the deep
    analysis components (which degrade on this synthetic corpus)."""
    return _base_plan(
        components=[],
        component_rationale={},
        grouping_facets=None,
        **overrides,
    )


def _run(
    engine: Engine, project_id: uuid.UUID, scope_id: uuid.UUID, **plan_overrides: Any
) -> Any:
    plan = _spine_plan(**plan_overrides)
    backend = ScriptableSearchBackend()
    return run_plan(
        engine,
        project_id=project_id,
        evidence_scope_id=scope_id,
        plan=plan,
        plan_id=uuid.uuid4(),
        plan_version=1,
        backends=RunnerBackends(search_backends=[backend]),
        io=NullIO(),
    )


def _search_steps(outcome: Any) -> list[str]:
    return [
        step.component
        for step in outcome.steps
        if step.component in ("acquire", "screen_abstract")
    ]


def test_deep_runs_three_rounds_and_stops_budget_exhausted(engine: Engine) -> None:
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        outcome = _run(engine, project_id, scope_id, search_effort="deep")

        assert outcome.status in ("succeeded", "degraded")
        assert all(
            step.status == "succeeded"
            for step in outcome.steps
            if step.component in ("acquire", "screen_abstract")
        )
        assert _search_steps(outcome) == [
            "acquire", "screen_abstract",
            "acquire", "screen_abstract",
            "acquire", "screen_abstract",
        ]
        rows = _coverage_rows(engine, project_id)
        assert len(rows) == DEPTH_CONSTANTS["deep"]["round_cap"] == 3
        # Earlier rounds keep their own stop condition; the loop-level stop
        # lands on the final round's row. Yield stayed healthy and the corpus
        # is not thin, so the raw budget stop is reported un-overlaid.
        assert [row.stop_condition for row in rows] == [
            "completed", "completed", "budget_exhausted",
        ]
    finally:
        if project_id is not None:
            _cleanup(engine, project_id)


def test_standard_runs_two_rounds(engine: Engine) -> None:
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        outcome = _run(engine, project_id, scope_id, search_effort="standard")

        assert outcome.status in ("succeeded", "degraded")
        assert all(
            step.status == "succeeded"
            for step in outcome.steps
            if step.component in ("acquire", "screen_abstract")
        )
        assert _search_steps(outcome) == [
            "acquire", "screen_abstract",
            "acquire", "screen_abstract",
        ]
        rows = _coverage_rows(engine, project_id)
        assert len(rows) == DEPTH_CONSTANTS["standard"]["round_cap"] == 2
        assert rows[-1].stop_condition == "budget_exhausted"
    finally:
        if project_id is not None:
            _cleanup(engine, project_id)


def test_rapid_runs_one_round_and_coverage_stays_completed(engine: Engine) -> None:
    """Rapid never enters the gate: one round, and its coverage row keeps
    acquire's own honest stop condition — no loop overlay is ever written."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        outcome = _run(engine, project_id, scope_id, search_effort="rapid")

        assert outcome.status in ("succeeded", "degraded")
        assert all(
            step.status == "succeeded"
            for step in outcome.steps
            if step.component in ("acquire", "screen_abstract")
        )
        assert _search_steps(outcome) == ["acquire", "screen_abstract"]
        rows = _coverage_rows(engine, project_id)
        assert len(rows) == 1
        assert rows[0].stop_condition == "completed"
    finally:
        if project_id is not None:
            _cleanup(engine, project_id)


def test_zero_yield_round_short_circuits_before_the_round_cap(engine: Engine) -> None:
    """A deep run whose round 2 acquires nothing stops on short_circuit at
    round 2 — searching harder stopped paying, so round 3 is never bought.
    Round 1's yield (30 confident-relevant) keeps the corpus above
    THIN_CONFIDENT_RELEVANT, so the raw condition is reported un-overlaid."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _spine_plan(search_effort="deep")
        # Same 10 records every call: round 1 acquires all 10, round 2
        # dedups to zero new -> screened 0 -> short_circuit.
        backend = ScriptableSearchBackend(per_call=10, replay=True)
        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=uuid.uuid4(),
            plan_version=1,
            backends=RunnerBackends(search_backends=[backend]),
            io=NullIO(),
        )

        assert outcome.status in ("succeeded", "degraded")
        assert all(
            step.status == "succeeded"
            for step in outcome.steps
            if step.component in ("acquire", "screen_abstract")
        )
        assert _search_steps(outcome) == [
            "acquire", "screen_abstract",
            "acquire", "screen_abstract",
        ]
        rows = _coverage_rows(engine, project_id)
        assert len(rows) == 2
        assert rows[-1].stop_condition == "short_circuit"
    finally:
        if project_id is not None:
            _cleanup(engine, project_id)


def test_thin_corpus_overlays_re_searched_still_thin(engine: Engine) -> None:
    """When the loop stops with fewer than THIN_CONFIDENT_RELEVANT confident
    documents, the final row reports 're_searched_still_thin' — the honesty
    overlay re-keyed from the removed stop target to the constant that
    actually means thin."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _spine_plan(search_effort="deep")
        # Same 2 records every call: 2 confident-relevant docs total < 8.
        backend = ScriptableSearchBackend(per_call=2, replay=True)
        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=uuid.uuid4(),
            plan_version=1,
            backends=RunnerBackends(search_backends=[backend]),
            io=NullIO(),
        )

        assert outcome.status in ("succeeded", "degraded")
        rows = _coverage_rows(engine, project_id)
        assert rows[-1].stop_condition == "re_searched_still_thin"
    finally:
        if project_id is not None:
            _cleanup(engine, project_id)


def test_p1_at_round_two_reports_only_that_round(engine: Engine) -> None:
    """Task 031 invariants 1 and 2, on a real two-round walk.

    The existing P1 tests hand ``p1_bundle`` a run id directly, so nothing
    exercised the thing plan.md § Phase 1 step 4 actually asked for: after the
    *second* acquire round, the card must show that round's counts and that
    round's queries — not round 1's, and not both rounds'.
    """
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        outcome = _run(engine, project_id, scope_id, search_effort="standard")
        assert outcome.status in ("succeeded", "degraded")

        rows = _coverage_rows(engine, project_id)
        assert len(rows) == 2, "the fixture must really run two acquire rounds"
        round_one, round_two = (row.acquired_by_run_id for row in rows)
        assert round_one != round_two

        with engine.connect() as conn:
            first = steering_bundles.p1_bundle(
                conn, project_id=project_id, evidence_scope_id=scope_id,
                acquire_run_id=round_one,
            )
            second = steering_bundles.p1_bundle(
                conn, project_id=project_id, evidence_scope_id=scope_id,
                acquire_run_id=round_two,
            )

        # Each card lists its own round's calls only. Disjointness would be the
        # wrong test — the base query is legitimately re-issued each round — so
        # pin the partition instead: the two cards together are exactly the
        # scope's calls, once each. Defect 1b made each card show all of them,
        # which doubles this sum.
        with engine.connect() as conn:
            every_round, _ = steering_bundles._executed_queries(
                conn, project_id=project_id, evidence_scope_id=scope_id
            )
        assert first["queries"] and second["queries"]
        assert len(first["queries"]) + len(second["queries"]) == len(every_round)

        # Invariant 1 on the round that just finished: the per-backend counts
        # are the acquire run's own, and never the permanently-zero line.
        assert second["backends"], "round 2 acquired new records, so the line must not be empty"
        assert sum(entry["count"] for entry in second["backends"]) > 0
    finally:
        if project_id is not None:
            _cleanup(engine, project_id)
