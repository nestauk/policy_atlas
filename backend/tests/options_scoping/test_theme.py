"""The ``theme`` component (task 046, S13a, R28; ADR 0040 decision 5).

Contract acceptance, items 5 and 8: ``theme`` runs after ``constrain`` and
receives the included options only; themes contain no excluded or merged
option; ``longlist`` writes no theme; a failed ``theme`` step ends the walk
``degraded`` with the verdicts stored; the run stream carries the ``theme``
stage; the registry, the harness graph and the plan mapping know ``theme``.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import Connection, Engine

from policy_atlas.api.contract.sse import STAGE_KEYS
from policy_atlas.api.routers import sse
from policy_atlas.api.stage_vocabulary import STAGE_BY_REGISTRY, STAGE_PRESENTATION
from policy_atlas.core import events
from policy_atlas.core.schema import longlist_result, option
from policy_atlas.options_scoping.longlist.longlist_backend import StubLonglistBackend
from policy_atlas.options_scoping.theme.theme import (
    ThemeContext,
    ThemeFailure,
    theme_ceiling,
    theme_scope,
)
from policy_atlas.runtime.harness import build_graph
from policy_atlas.runtime.run_spec import COMPONENT_REGISTRY, Plan, compile
from policy_atlas.runtime.runner import NullIO, run_plan
from policy_atlas.runtime.scoping_plan import LONGLIST_CHAIN
from policy_atlas.runtime.task_plan import OPTIONS_SCOPING_STEPS, registry_component_for
from tests.options_scoping.test_longlist import _Scripted, _Walk
from tests.runtime.test_baseline_gate import (
    insert_scoping_plan_row,
    scoping_plan,
    seed_scoping_task,
)
from tests.runtime.test_compose_by_purpose import _set_purpose
from tests.runtime.test_runner import _cleanup, _runner_backends


@pytest.mark.parametrize(("options", "ceiling"), [(2, 3), (20, 7), (60, 12)])
def test_the_theme_ceiling_is_clamp_ceil_n_over_3_3_12(options: int, ceiling: int) -> None:
    assert theme_ceiling(options) == ceiling


# --- the component on the transactional connection ------------------------------------


class _RaisingThemes(_Scripted):
    def discover_themes(self, **kwargs: Any) -> Any:
        raise RuntimeError("provider down")


def _theme(walk: _Walk, backend: Any) -> tuple[uuid.UUID, dict[str, Any]]:
    run_id = walk.run()
    summary = theme_scope(
        walk.conn,
        task_id=walk.task_id,
        run_id=run_id,
        context=ThemeContext(scope_id=walk.scope_id, intent="longlist intent", context={}),
        backend=backend,
    )
    return run_id, summary


def _latest(walk: _Walk) -> Any:
    return walk.conn.execute(
        select(longlist_result)
        .where(longlist_result.c.task_id == walk.task_id)
        .order_by(longlist_result.c.created_at.desc())
    ).first()


def _list_with_verdicts(walk: _Walk) -> dict[str, uuid.UUID]:
    """Four options — two included, one excluded, one merged — and a longlist."""
    kept = walk.option("Youth guarantee")
    other = walk.option("Wage subsidy")
    excluded = walk.option("Work trial")
    merged = walk.option("Youth guarantee scheme")
    walk.build(_Scripted())
    walk.conn.execute(
        option.update().where(option.c.option_id == excluded).values(state="excluded")
    )
    walk.conn.execute(
        option.update().where(option.c.option_id == merged).values(merged_into_option_id=kept)
    )
    return {"kept": kept, "other": other, "excluded": excluded, "merged": merged}


def test_longlist_writes_no_theme_and_makes_no_theme_call(conn: Connection) -> None:
    walk = _Walk(conn)
    walk.option("Youth guarantee")
    backend = _Scripted()
    run_id, summary = walk.build(backend)
    result = walk.result(run_id)
    assert result.themes == []
    assert "themes" not in result.counts and "no_theme" not in result.counts
    assert "themes" not in summary
    assert backend.calls["themes"] == []
    assert "theme" not in result.provenance
    assert "theme_clustering" not in result.provenance


def test_theme_groups_the_included_unmerged_options_only(conn: Connection) -> None:
    walk = _Walk(conn)
    ids = _list_with_verdicts(walk)
    backend = _Scripted()
    run_id, summary = _theme(walk, backend)

    offered = {str(r["unit_id"]) for r in backend.calls["themes"][0]["records"]}
    assert offered == {str(ids["kept"]), str(ids["other"])}
    assert summary == {"options": 2, "themes": 1, "no_theme": 1}
    result = _latest(walk)
    themed = {oid for theme in result.themes for oid in theme["option_ids"]}
    assert themed.isdisjoint({str(ids["excluded"]), str(ids["merged"])})
    assert themed <= offered
    assert result.counts["themes"] == 1 and result.counts["no_theme"] == 1
    provenance = result.provenance["theme"]
    assert provenance["run_id"] == str(run_id)
    assert provenance["theme_ceiling"] == {
        "formula": "clamp(ceil(n/3), 3, 12)",
        "options": 2,
        "ceiling": theme_ceiling(2),
    }
    assert provenance["clustering"]["ran"] is True
    # The longlist's own counts and verdicts are kept.
    assert result.counts["options"] == 4


def test_a_theme_failure_writes_nothing(conn: Connection) -> None:
    walk = _Walk(conn)
    _list_with_verdicts(walk)
    before = _latest(walk)
    with pytest.raises(ThemeFailure):
        _theme(walk, _RaisingThemes())
    after = _latest(walk)
    assert after.themes == before.themes == []
    assert after.counts == before.counts
    assert "theme" not in after.provenance


def test_theme_needs_a_longlist(conn: Connection) -> None:
    walk = _Walk(conn)
    with pytest.raises(ThemeFailure, match="no longlist"):
        _theme(walk, _Scripted())


# --- the registries -------------------------------------------------------------------


def test_the_registry_the_graph_the_plan_mapping_and_the_stream_know_theme() -> None:
    assert COMPONENT_REGISTRY["theme"] == {"requires": ["evidence_scope_id"]}
    compile(Plan(component="theme", evidence_scope_id=uuid.uuid4()))
    assert "theme" in OPTIONS_SCOPING_STEPS
    assert registry_component_for("theme") == "theme"
    graph = build_graph()
    assert "theme" in graph.get_graph().nodes
    assert STAGE_BY_REGISTRY["theme"] == "theme"
    assert "theme" in STAGE_KEYS
    assert STAGE_PRESENTATION["theme"] == (
        "Grouping into themes",
        "Included options grouped into themes.",
    )
    assert STAGE_PRESENTATION["longlist"] == (
        "Clustering into options",
        "Records grouped into options.",
    )
    assert [c for c, _ in LONGLIST_CHAIN][-4:] == [
        "longlist",
        "option_profile",
        "constrain",
        "theme",
    ]
    assert dict(LONGLIST_CHAIN)["theme"] is False


# --- the walk -------------------------------------------------------------------------


def _longlist_walk(engine: Engine) -> tuple[uuid.UUID, Any]:
    task_id, scope_id = seed_scoping_task(engine)
    _set_purpose(engine, scope_id, "longlist")
    plan = scoping_plan(steering_mode="moderate")
    plan_id = insert_scoping_plan_row(engine, task_id=task_id, scope_id=scope_id, plan=plan)
    outcome = run_plan(
        engine,
        task_id=task_id,
        evidence_scope_id=scope_id,
        plan=plan,
        plan_id=plan_id,
        plan_version=1,
        plan_row_id=plan_id,
        backends=_runner_backends(),
        io=NullIO(),
    )
    return task_id, outcome


def test_theme_runs_after_constrain_and_the_stream_carries_its_stage(engine: Engine) -> None:
    task_id: uuid.UUID | None = None
    try:
        task_id, outcome = _longlist_walk(engine)
        assert outcome.status == "succeeded"
        components = [step.component for step in outcome.steps]
        assert components[-2:] == ["constrain", "theme"]
        theme_step = outcome.steps[-1]
        assert theme_step.status == "succeeded"
        with engine.connect() as conn:
            result = conn.execute(
                select(longlist_result).where(longlist_result.c.task_id == task_id)
            ).one()
            log = events.read(conn, task_id)
            rows = [entry for entry in log if entry["run_id"] == theme_step.run_id]
            frames = sse._map_rows(conn, task_id=task_id, rows=rows, through=None)
        # The stub groups every included option under its one theme.
        assert result.counts["themes"] == len(result.themes) == 1
        assert len(result.judgements) == 1  # constrain's verdicts, on the same row
        stages = [(frame["type"], frame.get("stage")) for frame in frames]
        assert ("stage.started", "theme") in stages
        assert ("stage.completed", "theme") in stages
    finally:
        _cleanup(engine, task_id)


def test_a_failed_theme_step_degrades_the_walk_and_keeps_the_verdicts(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _down(self: Any, **kwargs: Any) -> Any:
        raise RuntimeError("provider down")

    monkeypatch.setattr(StubLonglistBackend, "discover_themes", _down)
    task_id: uuid.UUID | None = None
    try:
        task_id, outcome = _longlist_walk(engine)
        assert outcome.status == "degraded"
        statuses = {step.component: step.status for step in outcome.steps}
        assert statuses["constrain"] == "succeeded"
        assert statuses["theme"] == "failed"
        with engine.connect() as conn:
            result = conn.execute(
                select(longlist_result).where(longlist_result.c.task_id == task_id)
            ).one()
            walks = conn.execute(
                select(func.count()).select_from(longlist_result).where(
                    longlist_result.c.task_id == task_id
                )
            ).scalar_one()
        assert walks == 1
        assert len(result.judgements) == 1
        assert result.themes == []
    finally:
        _cleanup(engine, task_id)
