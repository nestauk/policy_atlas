"""The walk's cost line (task 054, C30): every step that calls a model is priced."""

from __future__ import annotations

import uuid

from sqlalchemy import bindparam, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine

from policy_atlas.core.schema import event_log, runs
from policy_atlas.theory_of_change.backend import StubTocBackend
from policy_atlas.theory_of_change.cost import walk_cost
from tests.theory_of_change.test_check_steps import _run

STEPS = ("toc_select", "toc_search_new", "toc_figures")


def test_the_pick_and_figures_steps_have_a_known_model(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    task_id = _run(engine, cleanup, StubTocBackend())
    usage = {"prompt": 1000, "cached": 0, "completion": 100, "total": 1100}
    completed = (
        (event_log.c.task_id == task_id)
        & (event_log.c.event_type == "component.completed")
        & (event_log.c.payload["component"].astext.in_(STEPS))
    )
    with engine.begin() as conn:
        # The stub reports no tokens; give these steps some, as live calls would.
        conn.execute(
            update(event_log)
            .where(completed)
            .values(
                payload=event_log.c.payload.op("||")(
                    bindparam("usage", {"usage_totals": usage}, type_=JSONB)
                )
            )
        )
        walk = conn.execute(
            select(runs.c.capability_run_id)
            .join(event_log, event_log.c.run_id == runs.c.run_id)
            .where(completed)
            .limit(1)
        ).scalar_one()
        cost = walk_cost(conn, task_id=task_id, walk_id=walk)
    assert set(cost["steps"]) == set(STEPS)
    assert all(step["model"] != "unknown" for step in cost["steps"].values())
    assert cost["unpriced"] == [] and cost["usd"] > 0
