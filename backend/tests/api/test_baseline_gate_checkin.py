"""Answering the options-scoping baseline gate (task 044, S4, D12).

The gate offers two ends, not two amendments, and the difference between them
is the whole slice: **Confirm plan and build longlist** finishes the walk, and
**Change the plan** ends the walk *without* abandoning the plan — because the
plan-edit path reads only ``approved`` rows, so abandoning it would leave the
user with a plan they were invited to change and cannot.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import jwt
import pytest
from sqlalchemy import select, update
from sqlalchemy.engine import Engine

from policy_atlas.api.continuation import (
    AlreadyAnsweredError,
    InvalidResponseError,
    answer_check_in,
    claim_continuation,
    execute_continuation,
)
from policy_atlas.core import events
from policy_atlas.core.schema import capability_run, task, task_plan
from policy_atlas.runtime.baseline_gate import GATE_HEADING
from policy_atlas.runtime.runner import NullIO, WalkParked
from policy_atlas.runtime.scoping_plan import BASELINE_CONFIRM
from tests.api.resource_support import api_client
from tests.runtime.test_baseline_gate import (
    insert_scoping_plan_row,
    scoping_plan,
    seed_scoping_task,
)
from tests.runtime.test_runner import _cleanup, _runner_backends


class _ParkAtGateIO:
    """Continue through every boundary except the baseline gate, which parks."""

    def check_in(self, component: str, payload: dict[str, Any]) -> None:
        del component, payload

    def pause(self, point: dict[str, Any], render: str) -> Any:
        del render
        if point.get("steer_point") == BASELINE_CONFIRM:
            raise WalkParked()
        from policy_atlas.runtime.steering import Continue

        return Continue()


def _park_at_gate(engine: Engine) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """Run one scoping walk up to the gate and park it there.

    Returns:
        ``(task_id, capability_run_id, check_in_id, plan_row_id)``.
    """
    from policy_atlas.runtime.runner import run_plan

    task_id, scope_id = seed_scoping_task(engine)
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
        io=_ParkAtGateIO(),
    )
    assert outcome.status == "paused"
    assert outcome.capability_run_id is not None
    with engine.connect() as conn:
        pause = next(
            entry
            for entry in reversed(events.read(conn, task_id))
            if entry["event_type"] == "steering.pause"
        )
    assert pause["payload"]["steer_point"] == BASELINE_CONFIRM
    return task_id, outcome.capability_run_id, pause["event_id"], plan_id


def _option(option_id: str) -> dict[str, Any]:
    return {"kind": "option", "option_id": option_id}


def _decisions(engine: Engine, task_id: uuid.UUID) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        return [
            entry["payload"]
            for entry in events.read(conn, task_id)
            if entry["event_type"] == "steering.decision"
        ]


def _own(engine: Engine, task_id: uuid.UUID, headers: dict[str, str]) -> None:
    sub = jwt.decode(
        headers["Authorization"].split(" ", 1)[1], options={"verify_signature": False}
    )["sub"]
    with engine.begin() as conn:
        conn.execute(update(task).where(task.c.task_id == task_id).values(owner_user_id=sub))


# --- confirm ----------------------------------------------------------------


def test_confirm_plan_finishes_the_walk_succeeded(engine: Engine) -> None:
    """The confirm option is an ordinary ``continue``: the walk ends by running out."""
    task_id: uuid.UUID | None = None
    try:
        task_id, capability_run_id, check_in_id, _plan_id = _park_at_gate(engine)
        answer = answer_check_in(
            engine,
            task_id=task_id,
            check_in_id=check_in_id,
            response=_option("confirm_plan"),
            actor="user-1",
        )
        assert answer.continuation_requested is True
        assert claim_continuation(
            engine, task_id=task_id, capability_run_id=capability_run_id
        ) is not None
        outcome = execute_continuation(
            engine,
            task_id=task_id,
            capability_run_id=capability_run_id,
            backends=_runner_backends(),
            io=NullIO(),
        )
        assert outcome.status == "succeeded"
        with engine.connect() as conn:
            assert (
                conn.execute(
                    select(capability_run.c.status).where(
                        capability_run.c.capability_run_id == capability_run_id
                    )
                ).scalar_one()
                == "succeeded"
            )
        decision = next(
            payload
            for payload in reversed(_decisions(engine, task_id))
            if payload.get("component") == "synthesise"
        )
        assert decision["response"] == "continue"
        assert decision["plan_version"] == 1
        uuid.UUID(decision["artefact_id"])
    finally:
        _cleanup(engine, task_id)


# --- change the plan --------------------------------------------------------


def test_change_plan_ends_the_walk_and_leaves_the_plan_approved(engine: Engine) -> None:
    """D12: aborted walk, ``approved`` plan — the two facts that must coexist."""
    task_id: uuid.UUID | None = None
    try:
        task_id, capability_run_id, check_in_id, plan_id = _park_at_gate(engine)
        answer = answer_check_in(
            engine,
            task_id=task_id,
            check_in_id=check_in_id,
            response=_option("change_plan"),
            actor="user-1",
        )
        assert answer.continuation_requested is False
        with engine.connect() as conn:
            walk = conn.execute(
                select(capability_run.c.status, capability_run.c.ended_at).where(
                    capability_run.c.capability_run_id == capability_run_id
                )
            ).one()
            plan_status = conn.execute(
                select(task_plan.c.status).where(task_plan.c.plan_id == plan_id)
            ).scalar_one()
            finished = [
                entry["payload"]
                for entry in events.read(conn, task_id)
                if entry["event_type"] == "run.finished"
            ]
        assert walk.status == "aborted"
        assert walk.ended_at is not None
        assert plan_status == "approved"
        assert finished[-1] == {
            "capability_run_id": str(capability_run_id),
            "status": "aborted",
            "reason": "change_plan",
        }
        decision = _decisions(engine, task_id)[-1]
        assert decision["response"] == "abort"
        assert decision["action"] == "change_plan"
    finally:
        _cleanup(engine, task_id)


def test_the_gate_refuses_everything_but_its_own_two_options(engine: Engine) -> None:
    """X3: the generic floor is closed here — ``abort`` would abandon the plan.

    "Change the plan" ends the walk and leaves the plan ``approved`` so it can
    be edited; the universal ``abort`` marks it ``abandoned``, which would hand
    the user a plan they were invited to change and cannot. Neither the bare
    ``abort`` kind nor the ``abort`` option id may reach it.
    """
    task_id: uuid.UUID | None = None
    try:
        task_id, capability_run_id, check_in_id, plan_id = _park_at_gate(engine)
        for response in (
            {"kind": "abort"},
            _option("abort"),
            _option("continue"),
            _option("start_the_longlist"),
        ):
            with pytest.raises(InvalidResponseError):
                answer_check_in(
                    engine,
                    task_id=task_id,
                    check_in_id=check_in_id,
                    response=response,
                    actor="user-1",
                )
        with engine.connect() as conn:
            assert (
                conn.execute(
                    select(task_plan.c.status).where(task_plan.c.plan_id == plan_id)
                ).scalar_one()
                == "approved"
            )
            assert (
                conn.execute(
                    select(capability_run.c.status).where(
                        capability_run.c.capability_run_id == capability_run_id
                    )
                ).scalar_one()
                == "paused"
            )
        # Nothing was decided *at the gate* (the walk's own earlier boundaries
        # are its own).
        assert [
            payload
            for payload in _decisions(engine, task_id)
            if payload.get("component") == "synthesise"
        ] == []

        # The two real options are untouched.
        answer_check_in(
            engine,
            task_id=task_id,
            check_in_id=check_in_id,
            response=_option("change_plan"),
            actor="user-1",
        )
        assert _decisions(engine, task_id)[-1]["action"] == "change_plan"
    finally:
        _cleanup(engine, task_id)


def test_a_second_answer_to_the_gate_is_refused(engine: Engine) -> None:
    task_id: uuid.UUID | None = None
    try:
        task_id, _capability_run_id, check_in_id, _plan_id = _park_at_gate(engine)
        answer_check_in(
            engine,
            task_id=task_id,
            check_in_id=check_in_id,
            response=_option("change_plan"),
            actor="user-1",
        )
        with pytest.raises((AlreadyAnsweredError, LookupError)):
            answer_check_in(
                engine,
                task_id=task_id,
                check_in_id=check_in_id,
                response=_option("confirm_plan"),
                actor="user-1",
            )
    finally:
        _cleanup(engine, task_id)


# --- the card and the plan afterwards, over HTTP ----------------------------


def test_the_card_shows_the_two_options_the_assumption_and_the_settings(
    engine: Engine, tmp_path: Path
) -> None:
    task_id: uuid.UUID | None = None
    try:
        with api_client(tmp_path) as (client, owner, _other):
            task_id, _run_id, _check_in_id, _plan_id = _park_at_gate(engine)
            _own(engine, task_id, owner)
            response = client.get(f"/api/v1/tasks/{task_id}/check-ins", headers=owner)
            assert response.status_code == 200, response.text
            card = response.json()["data"][0]
        assert [option["id"] for option in card["options"]] == ["confirm_plan", "change_plan"]
        assert [option["label"] for option in card["options"]] == [
            "Confirm plan and build longlist",
            "Change the plan",
        ]
        assert card["render"].splitlines()[0] == GATE_HEADING
        assert "Key assumption" in card["render"]
        assert card["bundle"]["settings"]["target_unit"] == "16 to 24 year olds"
        assert card["bundle"]["settings"]["outcomes"] == ["the NEET rate"]
        assert card["bundle"]["key_assumption"] is None or isinstance(
            card["bundle"]["key_assumption"], str
        )
        assert card["stage"] == "synthesise"
    finally:
        _cleanup(engine, task_id)


def test_the_plan_is_editable_once_the_walk_has_ended_by_change_plan(
    engine: Engine, tmp_path: Path
) -> None:
    """The gate's promise: after "Change the plan" a plan edit is accepted."""
    task_id: uuid.UUID | None = None
    try:
        with api_client(tmp_path) as (client, owner, _other):
            task_id, _run_id, check_in_id, _plan_id = _park_at_gate(engine)
            _own(engine, task_id, owner)
            blocked = client.patch(
                f"/api/v1/tasks/{task_id}/plan",
                headers=owner,
                json={"scoping": {"depth": "rapid"}},
            )
            assert blocked.status_code == 409, blocked.text

            answer_check_in(
                engine,
                task_id=task_id,
                check_in_id=check_in_id,
                response=_option("change_plan"),
                actor="user-1",
            )
            edited = client.patch(
                f"/api/v1/tasks/{task_id}/plan",
                headers=owner,
                json={"scoping": {"depth": "rapid"}},
            )
        assert edited.status_code == 200, edited.text
        body = edited.json()
        assert body["capability"] == "options_scoping"
        assert body["scoping"]["depth"] == "rapid"
        assert body["version"] == 2
    finally:
        _cleanup(engine, task_id)


def test_the_gate_check_in_reports_its_own_kind_on_the_wire() -> None:
    """web-api.md § Check-ins: kind ``baseline_confirm`` — the thread keys its
    card and the open composer on it (044 live check: the pause is written with
    the generic kind, so the read model must say so)."""
    import uuid as _uuid

    from policy_atlas.api.checkin_read import _check_in

    payload = {
        "kind": "steer_point",
        "steer_point": "baseline_confirm",
        "boundary": "after_component",
        "component": "synthesise",
        "options": [
            {"id": "confirm_plan", "label": "Confirm"},
            {"id": "change_plan", "label": "Change"},
        ],
        "bundle": {"key_assumption": None, "settings": {}},
    }
    from datetime import UTC, datetime

    row = {
        "event_id": _uuid.uuid4(),
        "payload": payload,
        "occurred_at": datetime.now(UTC),
        "sequence": 1,
    }
    assert _check_in(row, decided=False).kind == "baseline_confirm"
    generic = dict(payload, steer_point=None)
    assert _check_in(dict(row, payload=generic), decided=False).kind == "steer_point"
