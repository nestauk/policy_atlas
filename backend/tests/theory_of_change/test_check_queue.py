"""Checks asked for while a walk runs wait in a queue (task 054, round 5)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.api.toc_start import (
    clear_queue,
    queue_check,
    queued_link_ids,
    take_queued_check,
)
from policy_atlas.core.schema import evidence_scope
from tests.helpers import seed_toc_task


def test_queued_checks_of_one_mode_run_as_one_walk(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    from policy_atlas.runtime.agent import persist_approved_plan
    from tests.theory_of_change.test_walks import toc_plan

    with engine.begin() as conn:
        seeded: dict[str, Any] = seed_toc_task(conn)
        task_id = seeded["task_id"]
        cleanup.append(task_id)
        persist_approved_plan(conn, task_id=task_id, plan=toc_plan())
        for links, mode in ((["a"], "find_more"), (["b"], "new_items"), (["c", "a"], "find_more")):
            queue_check(conn, task_id=task_id, link_ids=links, mode=mode, studies=None, user_id="u")
        assert queued_link_ids(conn, task_id) == ["a", "b", "c"]

        taken = take_queued_check(conn, task_id)
        assert taken is not None
        context = conn.execute(
            select(evidence_scope.c.context).where(evidence_scope.c.evidence_scope_id == taken[0])
        ).scalar_one()
        assert context["links"] == ["a", "c"] and context["mode"] == "find_more"
        assert queued_link_ids(conn, task_id) == ["b"]

        clear_queue(conn, task_id)
        assert queued_link_ids(conn, task_id) == []
        assert take_queued_check(conn, task_id) is None
