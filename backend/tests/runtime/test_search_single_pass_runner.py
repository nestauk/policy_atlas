"""The runner drives one search pass at every scope (task 051, ADR 0038).

The round gate of task 029 is gone: a standard or deep plan makes exactly one
acquire run and one stage-1 screen run, writes one coverage record with
``stop_condition`` ``completed`` and ``round_index`` 1, then goes on to
classify. This is the row-level evidence ``test_search_rounds.py`` used to give.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.core import events
from policy_atlas.core.schema import search_coverage_record
from policy_atlas.runtime.runner import NullIO, run_plan
from tests.runtime.test_runner import _base_plan, _cleanup, _runner_backends, _seed_task


@pytest.mark.parametrize("search_effort", ["standard", "deep"])
def test_one_acquire_run_and_one_screen_run_at_every_scope(
    engine: Engine, search_effort: str
) -> None:
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = _seed_task(engine)
        outcome = run_plan(
            engine,
            task_id=task_id,
            evidence_scope_id=scope_id,
            plan=_base_plan(search_effort=search_effort),
            plan_id=uuid.uuid4(),
            plan_version=1,
            backends=_runner_backends(),
            io=NullIO(),
        )

        assert outcome.status == "succeeded"
        components = [step.component for step in outcome.steps]
        assert components.count("acquire") == 1
        assert components.count("screen_abstract") == 1
        assert (
            components.index("acquire")
            < components.index("screen_abstract")
            < components.index("classify")
        )

        with engine.connect() as conn:
            rows = conn.execute(
                select(search_coverage_record).where(search_coverage_record.c.task_id == task_id)
            ).fetchall()
            acquire_done = [
                event["payload"]
                for event in events.read(conn, task_id, event_types=["component.completed"])
                if event["payload"].get("component") == "acquire"
            ]
        assert len(rows) == 1
        assert rows[0].stop_condition == "completed"
        assert len(acquire_done) == 1
        assert acquire_done[0]["search"]["round_index"] == 1
    finally:
        _cleanup(engine, task_id)
