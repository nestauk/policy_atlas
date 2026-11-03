"""The Task Agent on a theory-of-change task (task 054, step 1.3; S6, S7)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.engine import Engine

from policy_atlas.api.deps import get_task_agent_backend
from policy_atlas.api.toc_start import mint_scope
from policy_atlas.core.schema import task_agent_transcript, task_plan
from policy_atlas.runtime.capability_registry import latest_approved_plan_row
from policy_atlas.runtime.task_agent import StubTaskAgentBackend
from policy_atlas.theory_of_change import store
from policy_atlas.theory_of_change.backend import stub_draft
from tests.api.resource_support import (
    api_client,
    create_task,
    remove_committed_tasks,  # noqa: F401 — autouse
    task_agent_turn,
    task_agent_turn_ok,
)
from tests.helpers import seed_walk

QUESTION = "Fewer children living with obesity in Leeds"


def _overrides() -> dict[Callable[..., object], Callable[..., object]]:
    return {get_task_agent_backend: lambda: StubTaskAgentBackend()}


def _toc_task(client: TestClient, owner: dict[str, str]) -> str:
    client.app.state.settings = replace(  # type: ignore[attr-defined]
        client.app.state.settings,  # type: ignore[attr-defined]
        theory_of_change_enabled=True,
    )
    return create_task(
        client, owner, name="Theory", question=QUESTION, capability="theory_of_change"
    )


def _versions(engine: Engine, task_id: str) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                select(func.count())
                .select_from(task_plan)
                .where(task_plan.c.task_id == uuid.UUID(task_id))
            ).scalar_one()
        )


def _with_draft_and_walk(engine: Engine, task_id: str, *, walk: str) -> None:
    """Write the stub draft and open a running walk of the given kind."""
    tid = uuid.UUID(task_id)
    with engine.begin() as conn:
        plan_row = latest_approved_plan_row(conn, tid)
        assert plan_row is not None
        if walk == "check":
            store.write_draft(conn, task_id=tid, run_id=None, draft=stub_draft({}))
        scope_id = mint_scope(conn, task_id=tid, plan_row=plan_row, toc_walk=walk)
        seed_walk(
            conn,
            tid,
            capability="theory_of_change",
            status="running",
            scope_id=scope_id,
            plan_id=plan_row["plan_id"],
        )


def test_a_stub_turn_fills_the_plan_and_get_plan_reads_its_slot(
    engine: Engine, tmp_path: Path
) -> None:
    with api_client(tmp_path, _overrides()) as (client, owner, _other):
        task_id = _toc_task(client, owner)
        turn = task_agent_turn_ok(client, owner, task_id, QUESTION)
        assert turn["capability"] == "theory_of_change"
        assert turn["plan"] is None and turn["scoping_plan"] is None
        assert turn["toc_plan"]["ready"] is True
        assert turn["toc_plan"]["intended_change"] == QUESTION
        plan = client.get(f"/api/v1/tasks/{task_id}/plan", headers=owner)
        assert plan.status_code == 200, plan.text
        body: dict[str, Any] = plan.json()
        assert body["capability"] == "theory_of_change"
        assert body["toc"]["intended_change"] == QUESTION
        assert body["plan"] is None
        patched = client.patch(
            f"/api/v1/tasks/{task_id}/plan", headers=owner, json={"question": "Other"}
        )
        assert patched.status_code == 422
    assert _versions(engine, task_id) == 1


def test_the_plan_panel_edits_a_toc_plan_until_the_draft_exists(
    engine: Engine, tmp_path: Path
) -> None:
    with api_client(tmp_path, _overrides()) as (client, owner, _other):
        task_id = _toc_task(client, owner)
        task_agent_turn_ok(client, owner, task_id, QUESTION)
        url = f"/api/v1/tasks/{task_id}/plan"
        patched = client.patch(
            url, headers=owner, json={"toc": {"where": "Scotland", "dosage": ""}}
        )
        assert patched.status_code == 200, patched.text
        assert patched.json()["toc"]["where"] == "Scotland"
        assert patched.json()["toc"]["dosage"] is None
        with engine.connect() as conn:
            state = conn.execute(
                select(task_agent_transcript.c.task_agent_state)
                .where(task_agent_transcript.c.task_id == uuid.UUID(task_id))
                .order_by(task_agent_transcript.c.turn_index.desc())
                .limit(1)
            ).scalar_one()
        # The Task Agent's next turn starts from the edited plan.
        assert state["where"] == "Scotland"
        _with_draft_and_walk(engine, task_id, walk="check")
        fixed = client.patch(url, headers=owner, json={"toc": {"where": "Wales"}})
        assert fixed.status_code == 409
    assert _versions(engine, task_id) == 2


def test_a_turn_during_the_check_is_admitted_and_leaves_the_plan_as_approved(
    engine: Engine, tmp_path: Path
) -> None:
    with api_client(tmp_path, _overrides()) as (client, owner, _other):
        task_id = _toc_task(client, owner)
        first = task_agent_turn_ok(client, owner, task_id, QUESTION)
        _with_draft_and_walk(engine, task_id, walk="check")
        later = task_agent_turn_ok(client, owner, task_id, "Make it about adults instead")
        # The stub would rewrite the change from the first message; the plan stays.
        assert later["toc_plan"] == first["toc_plan"]
    assert _versions(engine, task_id) == 1


def test_a_turn_while_the_draft_is_written_is_refused(engine: Engine, tmp_path: Path) -> None:
    with api_client(tmp_path, _overrides()) as (client, owner, _other):
        task_id = _toc_task(client, owner)
        task_agent_turn_ok(client, owner, task_id, QUESTION)
        _with_draft_and_walk(engine, task_id, walk="draft")
        refused = task_agent_turn(client, owner, task_id, "A question")
        assert refused.status_code == 409
        assert refused.json()["error"]["code"] == "run_active"
