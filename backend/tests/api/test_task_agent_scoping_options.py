"""The scoping plan's new slots over HTTP (task 045, D19, D22; deliverable 2).

- **Options you already have in mind.** The Task Agent records the user's words;
  the approving turn (and a direct plan edit) proposes a design back for each
  option through ``option_design_v1`` — once per new or reworded option, never
  again for words that did not change.
- **The default transferability preference.** On every plan, assumed, checked at
  assessment; follows Where until edited; a direct edit that omits it removes
  it, and no later version mints it again.
- **The baseline-state line** names the longlist states.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.api.deps import get_agent_backend, get_scoping_task_agent_backend
from policy_atlas.api.routers.task_agent import _baseline_state
from policy_atlas.core.schema import (
    capability_run,
    evidence_scope,
    longlist_result,
    runs,
    task,
    task_link,
    task_plan,
)
from policy_atlas.runtime.agent_backend import StubAgentBackend
from policy_atlas.runtime.task_agent_scoping import NO_BASELINE_STATE, StubScopingTaskAgentBackend
from policy_atlas.runtime.task_agent_scoping_prompt import (
    LinkedTaskContext,
    ScopingTurnWire,
    YourOptionWire,
)
from tests.api.resource_support import api_client
from tests.helpers import delete_task_data


@pytest.fixture(autouse=True)
def _remove_committed_tasks(engine: Engine):  # type: ignore[no-untyped-def]
    """Hard-delete every task these tests commit (a left scoping task blocks downgrades)."""
    before = _all_task_ids(engine)
    yield
    created = list(_all_task_ids(engine) - before)
    with engine.begin() as conn:
        conn.execute(task_link.delete().where(task_link.c.source_task_id.in_(created)))
        conn.execute(task_link.delete().where(task_link.c.target_task_id.in_(created)))
        for task_id in created:
            delete_task_data(conn, task_id)


def _all_task_ids(engine: Engine) -> set[uuid.UUID]:
    with engine.connect() as conn:
        return {row[0] for row in conn.execute(select(task.c.task_id))}


class _OptionsScopingAgent(StubScopingTaskAgentBackend):
    """The stub scoping Task Agent, with the user's options on every draft."""

    def __init__(self) -> None:
        self.options: list[str] | None = None

    def scope_turn(
        self,
        turns: list[dict[str, str]],
        previous_draft: dict[str, object] | None,
        *,
        linked_context: list[LinkedTaskContext] | None = None,
        baseline_state: str = NO_BASELINE_STATE,
        session_id: uuid.UUID | None = None,
        conversation_id: uuid.UUID | None = None,
    ) -> ScopingTurnWire:
        turn = super().scope_turn(
            turns,
            previous_draft,
            linked_context=linked_context,
            baseline_state=baseline_state,
            session_id=session_id,
            conversation_id=conversation_id,
        )
        if self.options is not None:
            turn.plan_draft.your_options = [YourOptionWire(text=t) for t in self.options]
        return turn


def _overrides(
    scoping: _OptionsScopingAgent, agent: StubAgentBackend
) -> dict[Callable[..., object], Callable[..., object]]:
    return {
        get_scoping_task_agent_backend: lambda: scoping,
        get_agent_backend: lambda: agent,
    }


def _scoping_task(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={
            "name": "Youth employment options",
            "question": "What could reduce the number of young people not in work?",
            "capability": "options_scoping",
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["task_id"])


def _turn(
    client: TestClient, headers: dict[str, str], task_id: str, message: str
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/tasks/{task_id}/task-agent-turns",
        headers=headers,
        json={"message": message, "client_turn_id": str(uuid.uuid4())},
    )
    assert response.status_code == 200, response.text
    return dict(response.json())


def _to_ready(client: TestClient, headers: dict[str, str], task_id: str) -> dict[str, Any]:
    _turn(client, headers, task_id, "Young people are not getting into work.")
    _turn(client, headers, task_id, "16 to 24 year olds")
    ready = _turn(client, headers, task_id, "[confirm part=depth option=standard_pass]")
    assert ready["scoping_plan"]["ready"] is True
    return ready


def _plan(client: TestClient, headers: dict[str, str], task_id: str) -> dict[str, Any]:
    response = client.get(f"/api/v1/tasks/{task_id}/plan", headers=headers)
    assert response.status_code == 200, response.text
    return dict(response.json()["scoping"])


def _patch(
    client: TestClient, headers: dict[str, str], task_id: str, scoping: dict[str, Any]
) -> dict[str, Any]:
    response = client.patch(
        f"/api/v1/tasks/{task_id}/plan", headers=headers, json={"scoping": scoping}
    )
    assert response.status_code == 200, response.text
    return dict(response.json()["scoping"])


def _defaults(scoping: dict[str, Any]) -> list[dict[str, Any]]:
    return [c for c in scoping["constraints"] if c.get("default") == "transferability"]


def _latest_source_turn(engine: Engine, task_id: str) -> int:
    with engine.connect() as conn:
        payload = conn.execute(
            select(task_plan.c.payload)
            .where(task_plan.c.task_id == uuid.UUID(task_id))
            .order_by(task_plan.c.version.desc())
            .limit(1)
        ).scalar_one()
    return int(payload["source_turn_index"])


# --- Options you already have in mind -----------------------------------------


def test_the_approving_turn_proposes_a_design_for_each_option(
    engine: Engine, tmp_path: Path
) -> None:
    scoping, agent = _OptionsScopingAgent(), StubAgentBackend()
    scoping.options = ["  a youth guarantee  ", "wage subsidies"]
    with api_client(tmp_path, _overrides(scoping, agent)) as (client, owner, _other):
        task_id = _scoping_task(client, owner)
        ready = _to_ready(client, owner, task_id)
        options = ready["scoping_plan"]["your_options"]
        assert [o["text"] for o in options] == ["  a youth guarantee  ", "wage subsidies"]
        assert all(o["design"] is not None for o in options)
        assert options[1]["design"]["name"] == "wage subsidies"
        turn = _latest_source_turn(engine, task_id)
        assert {o["turn_index"] for o in options} == {turn}
        assert agent.option_design_words == ["  a youth guarantee  ", "wage subsidies"]
        assert _plan(client, owner, task_id)["your_options"] == options


def test_a_reworded_option_is_proposed_again_and_the_others_keep_their_design(
    engine: Engine, tmp_path: Path
) -> None:
    scoping, agent = _OptionsScopingAgent(), StubAgentBackend()
    scoping.options = ["a youth guarantee", "wage subsidies"]
    with api_client(tmp_path, _overrides(scoping, agent)) as (client, owner, _other):
        task_id = _scoping_task(client, owner)
        first = _to_ready(client, owner, task_id)["scoping_plan"]["your_options"]
        scoping.options = ["a youth guarantee", "wage subsidies for employers"]
        again = _turn(client, owner, task_id, "make it wage subsidies for employers")
        options = again["scoping_plan"]["your_options"]
        assert options[0] == first[0]
        assert options[1]["design"]["name"] == "wage subsidies for employers"
        assert agent.option_design_calls == 3


def test_no_options_is_a_plan_and_calls_nothing(engine: Engine, tmp_path: Path) -> None:
    scoping, agent = _OptionsScopingAgent(), StubAgentBackend()
    with api_client(tmp_path, _overrides(scoping, agent)) as (client, owner, _other):
        task_id = _scoping_task(client, owner)
        ready = _to_ready(client, owner, task_id)
        assert ready["scoping_plan"]["your_options"] == []
        assert agent.option_design_calls == 0


def test_an_unready_draft_shows_the_options_without_a_design(
    engine: Engine, tmp_path: Path
) -> None:
    scoping, agent = _OptionsScopingAgent(), StubAgentBackend()
    scoping.options = ["a youth guarantee"]
    with api_client(tmp_path, _overrides(scoping, agent)) as (client, owner, _other):
        task_id = _scoping_task(client, owner)
        draft = _turn(client, owner, task_id, "Young people are not getting into work.")
        assert draft["scoping_plan"]["ready"] is False
        assert draft["scoping_plan"]["your_options"] == [
            {"text": "a youth guarantee", "design": None, "turn_index": None}
        ]
        assert agent.option_design_calls == 0


def test_a_patch_rewording_an_option_drops_and_re_proposes_its_design(
    engine: Engine, tmp_path: Path
) -> None:
    scoping, agent = _OptionsScopingAgent(), StubAgentBackend()
    scoping.options = ["a youth guarantee", "wage subsidies"]
    with api_client(tmp_path, _overrides(scoping, agent)) as (client, owner, _other):
        task_id = _scoping_task(client, owner)
        first = _to_ready(client, owner, task_id)["scoping_plan"]["your_options"]
        patched = _patch(
            client,
            owner,
            task_id,
            {"your_options": [{"text": "a youth guarantee"}, {"text": "apprenticeship levy"}]},
        )
        assert patched["your_options"][0] == first[0]
        assert patched["your_options"][1]["design"]["name"] == "apprenticeship levy"
        assert agent.option_design_words[-1] == "apprenticeship levy"
        assert agent.option_design_calls == 3


def test_a_patch_may_not_edit_another_users_options(engine: Engine, tmp_path: Path) -> None:
    scoping, agent = _OptionsScopingAgent(), StubAgentBackend()
    with api_client(tmp_path, _overrides(scoping, agent)) as (client, owner, other):
        task_id = _scoping_task(client, owner)
        _to_ready(client, owner, task_id)
        response = client.patch(
            f"/api/v1/tasks/{task_id}/plan",
            headers=other,
            json={"scoping": {"your_options": [{"text": "anything"}]}},
        )
        assert response.status_code in (403, 404)
        assert agent.option_design_calls == 0


# --- the default transferability preference -----------------------------------


def test_every_scoping_plan_carries_the_default_preference(
    engine: Engine, tmp_path: Path
) -> None:
    scoping, agent = _OptionsScopingAgent(), StubAgentBackend()
    with api_client(tmp_path, _overrides(scoping, agent)) as (client, owner, _other):
        task_id = _scoping_task(client, owner)
        draft = _turn(client, owner, task_id, "Young people are not getting into work.")
        assert _defaults(draft["scoping_plan"])[0]["text"] == "Transferable to United Kingdom"
        _to_ready(client, owner, task_id)
        [default] = _defaults(_plan(client, owner, task_id))
        assert default["kind"] == "preference"
        assert default["origin"] == "assumed"
        assert default["checked_at"] == "assessment"
        assert default["setting"] is False


def test_the_default_follows_where_until_the_user_edits_it(
    engine: Engine, tmp_path: Path
) -> None:
    scoping, agent = _OptionsScopingAgent(), StubAgentBackend()
    with api_client(tmp_path, _overrides(scoping, agent)) as (client, owner, _other):
        task_id = _scoping_task(client, owner)
        _to_ready(client, owner, task_id)
        moved = _patch(client, owner, task_id, {"where": {"text": "Wales", "origin": "your_call"}})
        assert [d["text"] for d in _defaults(moved)] == ["Transferable to Wales"]

        edited = [
            {**c, "text": "Transferable to a small nation"} if c.get("default") else c
            for c in moved["constraints"]
        ]
        _patch(client, owner, task_id, {"constraints": edited})
        after = _patch(
            client, owner, task_id, {"where": {"text": "Scotland", "origin": "your_call"}}
        )
        assert [d["text"] for d in _defaults(after)] == ["Transferable to a small nation"]


def test_a_removed_default_is_never_minted_again(engine: Engine, tmp_path: Path) -> None:
    scoping, agent = _OptionsScopingAgent(), StubAgentBackend()
    with api_client(tmp_path, _overrides(scoping, agent)) as (client, owner, _other):
        task_id = _scoping_task(client, owner)
        ready = _to_ready(client, owner, task_id)
        kept = [c for c in ready["scoping_plan"]["constraints"] if not c.get("default")]
        removed = _patch(client, owner, task_id, {"constraints": kept})
        assert _defaults(removed) == []
        # A later Task Agent turn builds a new version from its draft.
        _turn(client, owner, task_id, "one more thing")
        assert _defaults(_plan(client, owner, task_id)) == []
        with engine.connect() as conn:
            payload = conn.execute(
                select(task_plan.c.payload)
                .where(task_plan.c.task_id == uuid.UUID(task_id))
                .order_by(task_plan.c.version.desc())
                .limit(1)
            ).scalar_one()
        assert payload["removed_defaults"] == ["transferability"]


# --- the baseline-state line ----------------------------------------------------

_T0 = datetime(2026, 9, 22, 9, 0, tzinfo=UTC)


def _walk(
    engine: Engine, task_id: uuid.UUID, *, purpose: str, status: str
) -> tuple[uuid.UUID, uuid.UUID]:
    scope_id, walk_id = uuid.uuid4(), uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            evidence_scope.insert().values(
                evidence_scope_id=scope_id,
                task_id=task_id,
                intent="intent",
                context={},
                created_at=_T0,
                purpose=purpose,
            )
        )
        conn.execute(
            capability_run.insert().values(
                capability_run_id=walk_id,
                task_id=task_id,
                evidence_scope_id=scope_id,
                capability="options_scoping",
                plan_id=uuid.uuid4(),
                plan_version=2,
                status=status,
                started_at=_T0 + timedelta(minutes=5),
                ended_at=None if status in ("running", "paused") else _T0,
            )
        )
    return scope_id, walk_id


def test_the_baseline_state_names_the_longlist_states(engine: Engine, tmp_path: Path) -> None:
    scoping, agent = _OptionsScopingAgent(), StubAgentBackend()
    with api_client(tmp_path, _overrides(scoping, agent)) as (client, owner, _other):
        task_id = uuid.UUID(_scoping_task(client, owner))
        with engine.connect() as conn:
            assert _baseline_state(conn, task_id) == NO_BASELINE_STATE

        scope_id, walk_id = _walk(engine, task_id, purpose="longlist", status="running")
        with engine.connect() as conn:
            assert _baseline_state(conn, task_id) == "a longlist is being built"

        run_id = uuid.uuid4()
        with engine.begin() as conn:
            conn.execute(
                capability_run.update()
                .where(capability_run.c.capability_run_id == walk_id)
                .values(status="succeeded", ended_at=_T0)
            )
            conn.execute(
                runs.insert().values(
                    run_id=run_id,
                    task_id=task_id,
                    status="succeeded",
                    started_at=_T0,
                    capability_run_id=walk_id,
                )
            )
            conn.execute(
                longlist_result.insert().values(
                    longlist_result_id=uuid.uuid4(),
                    task_id=task_id,
                    evidence_scope_id=scope_id,
                    run_id=run_id,
                    plan_version=2,
                    themes=[],
                    coverage={},
                    judgements={},
                    guesses=[],
                    counts={},
                    provenance={},
                    created_at=_T0,
                )
            )
        with engine.connect() as conn:
            assert _baseline_state(conn, task_id) == "a longlist exists, built from plan version 2"
