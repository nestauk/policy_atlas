"""Acquire-only option searches and one screen of the pool (task 046, S1, S2).

Contract acceptance, items 18 and 22: a child of a longlist walk runs
``acquire`` only; the join happens before ``screen_abstract``; a document an
option search acquired has exactly one stage-1 screen row in the task, in the
longlist scope; the add walk runs the full targeted chain; no longlist or
targeted chain holds ``ingest_full_text``. (A failed child still degrades the
walk and never fails it: ``test_option_search.py``.)
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import Engine

from policy_atlas.core.schema import (
    capability_run,
    evidence_scope,
    runs,
    source_screening_result,
    task_source_snapshot,
)
from policy_atlas.evidence_search.sourcing.acquire import BackendCaps
from policy_atlas.runtime import option_search
from policy_atlas.runtime import runner as runner_module
from policy_atlas.runtime.capability_registry import (
    EVIDENCE_SEARCH,
    OPTIONS_SCOPING,
    compose_plan,
)
from policy_atlas.runtime.runner import NullIO, RunnerBackends, run_plan
from policy_atlas.runtime.scoping_plan import (
    ACQUIRE_ONLY_CHAIN,
    ACQUIRE_ONLY_KEY,
    LONGLIST_CHAIN,
    SCOPING_SPINE,
    TARGETED_CHAIN,
    compose_scoping,
)
from policy_atlas.runtime.task_plan import compose
from tests.helpers import oa_record
from tests.runtime.test_baseline_gate import scoping_plan
from tests.runtime.test_option_search import (
    _await_children_ended,
    _children,
    _design,
    _longlist_plan,
    _seed_longlist,
    _seed_option,
    _seed_walk,
)
from tests.runtime.test_runner import _base_plan, _cleanup, _runner_backends

# --- the chains ---------------------------------------------------------------


def test_the_three_chains_are_the_plan_s() -> None:
    assert LONGLIST_CHAIN == (
        ("inherit", False),
        ("suggest", False),
        ("acquire", True),
        ("screen_abstract", True),
        ("classify", True),
        ("appraise", True),
        ("extract_interventions", True),
        ("longlist", True),
        ("option_profile", True),
        ("constrain", True),
        ("theme", False),
    )
    assert TARGETED_CHAIN == (
        "acquire",
        "screen_abstract",
        "classify",
        "appraise",
        "extract_interventions",
    )
    assert ACQUIRE_ONLY_CHAIN == ("acquire",)


def test_no_longlist_or_targeted_chain_ingests_full_text() -> None:
    plan = scoping_plan()
    for purpose, context in (
        ("longlist", None),
        ("targeted", None),
        ("targeted", {ACQUIRE_ONLY_KEY: True}),
    ):
        assert "ingest_full_text" not in compose_scoping(plan, purpose, context).components
    # The baseline chain is not changed.
    assert compose_scoping(plan).components == list(SCOPING_SPINE)
    assert "ingest_full_text" in SCOPING_SPINE


def test_an_acquire_only_record_composes_acquire_alone() -> None:
    plan = scoping_plan()
    marked = compose_plan(
        OPTIONS_SCOPING,
        plan,
        purpose="targeted",
        context={"capability": OPTIONS_SCOPING, "option_id": "x", ACQUIRE_ONLY_KEY: True},
    )
    assert marked.components == ["acquire"]
    assert all(step.spine is True for step in marked.steps)
    # The verb *add*'s search has no flag: the full targeted chain.
    add_walk = compose_plan(
        OPTIONS_SCOPING, plan, purpose="targeted", context={"option_id": "x"}
    )
    assert add_walk.components == list(TARGETED_CHAIN)
    assert compose_plan(OPTIONS_SCOPING, plan, purpose="targeted").components == list(
        TARGETED_CHAIN
    )
    # Only ``targeted`` reads the flag.
    assert compose_plan(
        OPTIONS_SCOPING, plan, purpose="longlist", context={ACQUIRE_ONLY_KEY: True}
    ) == compose_scoping(plan, "longlist")


def test_the_evidence_search_ignores_the_context() -> None:
    plan = _base_plan()
    assert compose_plan(EVIDENCE_SEARCH, plan, context={ACQUIRE_ONLY_KEY: True}) == compose(plan)


# --- the walk -----------------------------------------------------------------


class _FreshRecords:
    """An OpenAlex-shaped backend that returns new records on every call."""

    name = "openalex"
    trust_class = "academic_aggregator"
    mode = "scripted"
    caps = BackendCaps(has_snowball=False, has_title_lookup=False)

    def search(
        self,
        query: str,
        *,
        wire_params: dict[str, str] | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        stem = uuid.uuid4().hex[:12]
        return [oa_record(f"{stem}n{i}", title=f"Record {stem} {i}") for i in range(2)]

    def fetch_citations(
        self, record_id: str, *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    def fetch_references(
        self, record_ids: list[str], *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    def lookup_title(self, title: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    def lookup_dois(
        self, dois: list[str], *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        raise NotImplementedError


def test_the_children_only_acquire_and_the_longlist_scope_screens_their_documents_once(
    engine: Engine,
) -> None:
    task_id: uuid.UUID | None = None
    try:
        plan = _longlist_plan("Youth guarantee", "Wage subsidy")
        task_id, scope_id, plan_id = _seed_longlist(engine, plan)
        outcome = run_plan(
            engine,
            task_id=task_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=RunnerBackends(search_backends=[_FreshRecords()]),
            io=NullIO(),
            session_id=task_id,
        )
        parent = outcome.capability_run_id
        assert parent is not None
        assert outcome.status == "succeeded"
        children = _children(engine, task_id, parent)
        assert len(children) == 3
        assert all(child.context[ACQUIRE_ONLY_KEY] is True for child in children)
        child_ids = [child.capability_run_id for child in children]
        with engine.connect() as conn:
            child_runs = conn.execute(
                select(runs.c.run_id).where(runs.c.capability_run_id.in_(child_ids))
            ).scalars().all()
            # One run per child: its acquire.
            assert len(child_runs) == len(children)
            child_scopes = conn.execute(
                select(capability_run.c.evidence_scope_id).where(
                    capability_run.c.capability_run_id.in_(child_ids)
                )
            ).scalars().all()
            acquired = conn.execute(
                select(task_source_snapshot.c.task_source_snapshot_id)
                .where(task_source_snapshot.c.task_id == task_id)
                .where(task_source_snapshot.c.run_id.in_(child_runs))
            ).scalars().all()
            assert acquired, "the option searches acquired nothing"
            for tss_id in acquired:
                screens = conn.execute(
                    select(source_screening_result.c.evidence_scope_id)
                    .where(source_screening_result.c.task_id == task_id)
                    .where(source_screening_result.c.task_source_snapshot_id == tss_id)
                    .where(source_screening_result.c.screen_stage == 1)
                ).scalars().all()
                assert screens == [scope_id]
            # No child scope holds a screen row.
            assert conn.execute(
                select(func.count())
                .select_from(source_screening_result)
                .where(source_screening_result.c.evidence_scope_id.in_(child_scopes))
            ).scalar_one() == 0
            # The longlist scope's own record is untouched by the flag.
            parent_context = conn.execute(
                select(evidence_scope.c.context).where(
                    evidence_scope.c.evidence_scope_id == scope_id
                )
            ).scalar_one()
            assert ACQUIRE_ONLY_KEY not in parent_context
    finally:
        if task_id is not None:
            _await_children_ended(engine, task_id)
        _cleanup(engine, task_id)


def test_only_a_longlist_walk_s_option_search_is_marked_acquire_only(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AM4: the flag rides the scope's context when the walk has a parent."""
    monkeypatch.setattr(runner_module, "run_plan", lambda *args, **kwargs: None)
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id, plan_id = _seed_longlist(engine, _longlist_plan())
        parent = _seed_walk(engine, task_id, scope_id, plan_id)
        option_id = _seed_option(engine, task_id, "Own", "added_by_you")
        plan_row = {
            "plan_id": plan_id,
            "version": 1,
            "payload": _longlist_plan().model_dump(mode="json"),
        }
        contexts: dict[str, Any] = {}
        for label, parent_id in (("child", parent), ("add", None)):
            option_search.run_option_search(
                engine,
                task_id=task_id,
                plan_row=plan_row,
                design=_design("Own"),
                option_id=option_id,
                parent_capability_run_id=parent_id,
                backends=_runner_backends(),
                user_id=None,
            )
            with engine.connect() as conn:
                contexts[label] = conn.execute(
                    select(evidence_scope.c.context)
                    .where(evidence_scope.c.task_id == task_id)
                    .where(evidence_scope.c.purpose == "targeted")
                    .order_by(evidence_scope.c.created_at.desc())
                    .limit(1)
                ).scalar_one()
        assert contexts["child"][ACQUIRE_ONLY_KEY] is True
        assert ACQUIRE_ONLY_KEY not in contexts["add"]
        assert compose_scoping(_longlist_plan(), "targeted", contexts["child"]).components == [
            "acquire"
        ]
        assert compose_scoping(_longlist_plan(), "targeted", contexts["add"]).components == list(
            TARGETED_CHAIN
        )
    finally:
        _cleanup(engine, task_id)
