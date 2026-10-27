"""The shared Task Agent route, driven as an options-scoping task.

Task 044 phase 3.2. What is worth owning at the HTTP level here is the part
that cannot be seen from either plan model alone:

- **One route, two capabilities.** The durable machinery — the transcript, the
  idempotency key, the run fences, the transaction that joins an approved plan
  to the turn that approved it — is shared. Only the Task Agent called, the
  model that validates its output and the projection returned differ (C9).
- **The intent record.** A scoping plan's scope row carries
  ``purpose='baseline'`` and points at the plan version that minted it, and a
  new version gets a *new* scope row (C3) — otherwise "which plan version was
  this baseline built from" has two answers.
- **Confirming is a plan version.** The walk has ended by then, so the
  confirmation cannot be a steering event (S4, X5).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine

from policy_atlas.api.deps import get_executor, get_task_agent_backend
from policy_atlas.core.schema import (
    artefact,
    capability_run,
    evidence_scope,
    task_plan,
)
from policy_atlas.runtime.scoping_plan import (
    BASELINE_TIME_BAND,
    ScopingPlan,
    longlist_inputs,
    wire_draft_from_plan,
)
from policy_atlas.runtime.task_agent_scoping import (
    StubScopingTaskAgentBackend,
    _seed_draft,
)
from tests.api.resource_support import (
    api_client,
    create_scoping_task,
    create_task,
    remove_committed_tasks,  # noqa: F401 — autouse
    task_agent_turn_ok,
    to_ready,
)
from tests.api.test_longlist_start import RecordingExecutor


def _scope_rows(engine: Engine, task_id: str) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        return [
            dict(row)
            for row in conn.execute(
                select(evidence_scope)
                .where(evidence_scope.c.task_id == uuid.UUID(task_id))
                .order_by(evidence_scope.c.created_at.asc())
            ).mappings()
        ]


def _plan_rows(engine: Engine, task_id: str) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        return [
            dict(row)
            for row in conn.execute(
                select(task_plan)
                .where(task_plan.c.task_id == uuid.UUID(task_id))
                .order_by(task_plan.c.version.asc())
            ).mappings()
        ]


def _overrides() -> dict[Callable[..., object], Callable[..., object]]:
    # A confirm opens the longlist walk (task 045, S3); these tests are about
    # the plan versions, so the walk executor opens the walk's row and runs
    # nothing.
    executor = RecordingExecutor(status="succeeded")
    return {
        get_task_agent_backend: lambda: StubScopingTaskAgentBackend(),
        get_executor: lambda: executor,
    }


# --- the conversation -------------------------------------------------------


def test_the_stub_conversation_reaches_a_ready_plan_in_four_turns(
    engine: Engine, tmp_path: Path
) -> None:
    with api_client(tmp_path, _overrides()) as (client, owner, _other):
        task_id = create_scoping_task(client, owner)
        final = to_ready(client, owner, task_id)

    assert final["capability"] == "options_scoping"
    assert final["plan"] is None
    plan = final["scoping_plan"]
    assert plan["ready"] is True
    assert plan["depth"] == "standard"
    assert plan["risk_appetite"] == "mostly_tried"
    assert plan["target_unit"] == {"text": "16 to 24 year olds", "origin": "your_call"}
    assert plan["where"] == {"text": "United Kingdom", "origin": "assumed"}
    assert plan["steering_mode"] == "moderate"
    assert plan["time_band"] == BASELINE_TIME_BAND
    assert [step["label"] for step in plan["steps"]] == [
        "Baseline",
        "Longlist",
        "Shortlist and assessment",
    ]


def test_the_depth_card_carries_no_recommendation(engine: Engine, tmp_path: Path) -> None:
    """OS ruling 25: neither depth is the recommended one, so no primary."""
    with api_client(tmp_path, _overrides()) as (client, owner, _other):
        task_id = create_scoping_task(client, owner)
        task_agent_turn_ok(client, owner, task_id, "Young people are not getting into work.")
        second = task_agent_turn_ok(client, owner, task_id, "16 to 24 year olds")
    options = second["part"]["options"]
    assert [option["id"] for option in options] == ["rapid_pass", "standard_pass"]
    assert not any(option["primary"] for option in options)


def test_the_appetite_card_offers_three_options_with_the_middle_primary(
    engine: Engine, tmp_path: Path
) -> None:
    with api_client(tmp_path, _overrides()) as (client, owner, _other):
        task_id = create_scoping_task(client, owner)
        task_agent_turn_ok(client, owner, task_id, "Young people are not getting into work.")
        task_agent_turn_ok(client, owner, task_id, "16 to 24 year olds")
        third = task_agent_turn_ok(
            client, owner, task_id, "[confirm part=depth option=rapid_pass]"
        )
    assert third["scoping_plan"]["ready"] is False
    part = third["part"]
    assert part["id"] == "appetite"
    assert [(o["id"], o["primary"]) for o in part["options"]] == [
        ("appetite_tried", False),
        ("appetite_mostly", True),
        ("appetite_open", False),
    ]


def test_an_appetite_chosen_by_marker_or_in_words_sets_the_plan(
    engine: Engine, tmp_path: Path
) -> None:
    for answer, expected in (
        ("[confirm part=appetite option=appetite_open]", "open_to_untested"),
        ("only options that have been tried elsewhere", "tried_only"),
    ):
        with api_client(tmp_path, _overrides()) as (client, owner, _other):
            task_id = create_scoping_task(client, owner)
            task_agent_turn_ok(client, owner, task_id, "Young people are not getting into work.")
            task_agent_turn_ok(client, owner, task_id, "16 to 24 year olds")
            task_agent_turn_ok(client, owner, task_id, "[confirm part=depth option=rapid_pass]")
            ready = task_agent_turn_ok(client, owner, task_id, answer)
        assert ready["scoping_plan"]["ready"] is True
        assert ready["scoping_plan"]["risk_appetite"] == expected


def test_no_appetite_choice_reads_mostly_tried(engine: Engine, tmp_path: Path) -> None:
    with api_client(tmp_path, _overrides()) as (client, owner, _other):
        task_id = create_scoping_task(client, owner)
        task_agent_turn_ok(client, owner, task_id, "Young people are not getting into work.")
        task_agent_turn_ok(client, owner, task_id, "16 to 24 year olds")
        task_agent_turn_ok(client, owner, task_id, "[confirm part=depth option=rapid_pass]")
        ready = task_agent_turn_ok(client, owner, task_id, "carry on")
    assert ready["scoping_plan"]["ready"] is True
    assert ready["scoping_plan"]["risk_appetite"] == "mostly_tried"
    assert _plan_rows(engine, task_id)[0]["payload"]["risk_appetite"] == "mostly_tried"


def test_a_chosen_appetite_survives_approval_seeding_and_a_later_patch(
    engine: Engine, tmp_path: Path
) -> None:
    with api_client(tmp_path, _overrides()) as (client, owner, _other):
        task_id = create_scoping_task(client, owner)
        task_agent_turn_ok(client, owner, task_id, "Young people are not getting into work.")
        task_agent_turn_ok(client, owner, task_id, "16 to 24 year olds")
        task_agent_turn_ok(client, owner, task_id, "[confirm part=depth option=rapid_pass]")
        task_agent_turn_ok(client, owner, task_id, "[confirm part=appetite option=appetite_open]")
        patched = client.patch(
            f"/api/v1/tasks/{task_id}/plan",
            headers=owner,
            json={"scoping": {"where": {"text": "England", "origin": "your_call"}}},
        )
        assert patched.status_code == 200, patched.text

    plans = _plan_rows(engine, task_id)
    assert [p["payload"]["risk_appetite"] for p in plans] == ["open_to_untested"] * 2
    seeded = wire_draft_from_plan(ScopingPlan.model_validate(plans[0]["payload"]))
    assert "risk_appetite" not in seeded  # the seed helper adds it, in the profile
    assert _seed_draft(ScopingPlan.model_validate(plans[0]["payload"]))[
        "risk_appetite"
    ] == "open_to_untested"


def test_an_evidence_search_task_still_gets_the_evidence_search_shape(
    engine: Engine, tmp_path: Path
) -> None:
    with api_client(tmp_path, _overrides()) as (client, owner, _other):
        task_id = create_task(client, owner)
        turn = task_agent_turn_ok(client, owner, task_id, "What works for youth employment?")
    assert turn["capability"] == "evidence_search"
    assert turn["scoping_plan"] is None
    assert turn["plan"] is not None
    assert turn["plan"]["backend_scope"] == "both"


# --- the intent record ------------------------------------------------------


def test_the_first_plan_writes_a_baseline_scope_pointing_at_it(
    engine: Engine, tmp_path: Path
) -> None:
    with api_client(tmp_path, _overrides()) as (client, owner, _other):
        task_id = create_scoping_task(client, owner)
        to_ready(client, owner, task_id)

    scopes = _scope_rows(engine, task_id)
    plans = _plan_rows(engine, task_id)
    assert len(scopes) == len(plans) == 1
    assert scopes[0]["purpose"] == "baseline"
    assert scopes[0]["plan_id"] == plans[0]["plan_id"]
    assert plans[0]["evidence_scope_id"] == scopes[0]["evidence_scope_id"]
    assert scopes[0]["context"]["capability"] == "options_scoping"
    assert scopes[0]["context"]["target_unit"] == "16 to 24 year olds"
    assert scopes[0]["context"]["where"] == "United Kingdom"
    # The intent text is compiled from the plan, never written by a model.
    assert "16 to 24 year olds" in scopes[0]["intent"]
    assert "United Kingdom" in scopes[0]["intent"]


def test_an_amended_plan_gets_its_own_scope_row(engine: Engine, tmp_path: Path) -> None:
    """C3: one scope per plan version, so the baseline's provenance is unique."""
    with api_client(tmp_path, _overrides()) as (client, owner, _other):
        task_id = create_scoping_task(client, owner)
        to_ready(client, owner, task_id)
        patched = client.patch(
            f"/api/v1/tasks/{task_id}/plan",
            headers=owner,
            json={"scoping": {"where": {"text": "England", "origin": "your_call"}}},
        )
        assert patched.status_code == 200, patched.text

    body = patched.json()
    assert body["version"] == 2
    assert body["capability"] == "options_scoping"
    assert body["plan"] is None
    assert body["scoping"]["where"] == {"text": "England", "origin": "your_call"}

    scopes = _scope_rows(engine, task_id)
    plans = _plan_rows(engine, task_id)
    assert len(scopes) == len(plans) == 2
    assert {scope["purpose"] for scope in scopes} == {"baseline"}
    assert [scope["plan_id"] for scope in scopes] == [
        plan["plan_id"] for plan in plans
    ]
    assert scopes[1]["context"]["where"] == "England"
    assert "England" in scopes[1]["intent"]
    assert plans[0]["status"] == "superseded"
    assert plans[1]["status"] == "approved"


def test_a_rebuild_after_a_change_reads_the_new_version(
    engine: Engine, tmp_path: Path
) -> None:
    """A second approval through the Task Agent mints version 3 and its scope."""
    with api_client(tmp_path, _overrides()) as (client, owner, _other):
        task_id = create_scoping_task(client, owner)
        to_ready(client, owner, task_id)
        client.patch(
            f"/api/v1/tasks/{task_id}/plan",
            headers=owner,
            json={"scoping": {"where": {"text": "England", "origin": "your_call"}}},
        )
        task_agent_turn_ok(client, owner, task_id, "standard, and run it unattended")

    scopes = _scope_rows(engine, task_id)
    plans = _plan_rows(engine, task_id)
    assert len(scopes) == len(plans) == 3
    assert scopes[2]["plan_id"] == plans[2]["plan_id"]
    assert plans[2]["payload"]["steering_mode"] == "unattended"
    assert plans[2]["payload"]["steer_point_defaults"] == [
        {"steer_point": "baseline_confirm", "action": "proceed_flag"}
    ]


def test_an_appetite_only_patch_mints_a_version_and_leaves_the_longlist_inputs(
    engine: Engine, tmp_path: Path
) -> None:
    """Task 055 item 1: the appetite is a plan field the patch can change alone."""
    with api_client(tmp_path, _overrides()) as (client, owner, _other):
        task_id = create_scoping_task(client, owner)
        to_ready(client, owner, task_id)
        before = client.get(f"/api/v1/tasks/{task_id}/plan", headers=owner).json()
        patched = client.patch(
            f"/api/v1/tasks/{task_id}/plan",
            headers=owner,
            json={"scoping": {"risk_appetite": "open_to_untested"}},
        )
        assert patched.status_code == 200, patched.text

    assert before["scoping"]["risk_appetite"] == "mostly_tried"
    body = patched.json()
    assert body["version"] == 2
    assert body["scoping"]["risk_appetite"] == "open_to_untested"
    plans = _plan_rows(engine, task_id)
    assert [p["payload"]["risk_appetite"] for p in plans] == ["mostly_tried", "open_to_untested"]
    older, newer = (ScopingPlan.model_validate(p["payload"]) for p in plans)
    assert longlist_inputs(older) == longlist_inputs(newer)


def test_an_unknown_appetite_in_a_patch_is_refused(engine: Engine, tmp_path: Path) -> None:
    with api_client(tmp_path, _overrides()) as (client, owner, _other):
        task_id = create_scoping_task(client, owner)
        to_ready(client, owner, task_id)
        refused = client.patch(
            f"/api/v1/tasks/{task_id}/plan",
            headers=owner,
            json={"scoping": {"risk_appetite": "reckless"}},
        )
    assert refused.status_code == 422, refused.text
    assert len(_plan_rows(engine, task_id)) == 1


# --- GET /plan --------------------------------------------------------------


def test_get_plan_returns_the_scoping_shape(engine: Engine, tmp_path: Path) -> None:
    with api_client(tmp_path, _overrides()) as (client, owner, _other):
        task_id = create_scoping_task(client, owner)
        to_ready(client, owner, task_id)
        read = client.get(f"/api/v1/tasks/{task_id}/plan", headers=owner)

    assert read.status_code == 200, read.text
    body = read.json()
    assert body["capability"] == "options_scoping"
    assert body["version"] == 1
    assert body["status"] == "approved"
    assert body["plan"] is None
    assert body["scoping"]["depth"] == "standard"


def test_an_evidence_search_field_on_a_scoping_plan_is_refused(
    engine: Engine, tmp_path: Path
) -> None:
    with api_client(tmp_path, _overrides()) as (client, owner, _other):
        task_id = create_scoping_task(client, owner)
        to_ready(client, owner, task_id)
        refused = client.patch(
            f"/api/v1/tasks/{task_id}/plan",
            headers=owner,
            json={"analysis_depth": "deep"},
        )
    assert refused.status_code == 422, refused.text


def test_a_scoping_patch_on_an_evidence_search_plan_is_refused(
    engine: Engine, tmp_path: Path
) -> None:
    with api_client(tmp_path, _overrides()) as (client, owner, _other):
        task_id = create_task(client, owner)
        task_agent_turn_ok(client, owner, task_id, "What works for youth employment?")
        task_agent_turn_ok(client, owner, task_id, "A one-off briefing")
        refused = client.patch(
            f"/api/v1/tasks/{task_id}/plan",
            headers=owner,
            json={"scoping": {"depth": "rapid"}},
        )
    assert refused.status_code == 422, refused.text


# --- confirm-baseline -------------------------------------------------------


def _seed_artefact(engine: Engine, task_id: str) -> uuid.UUID:
    artefact_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            artefact.insert().values(
                artefact_id=artefact_id,
                task_id=uuid.UUID(task_id),
                capability_run_id=None,
                title="Baseline",
                created_at=datetime.now(UTC),
            )
        )
    return artefact_id


def _seed_paused_walk(conn: Connection, task_id: str) -> None:
    row = conn.execute(
        select(task_plan)
        .where(task_plan.c.task_id == uuid.UUID(task_id))
        .where(task_plan.c.status == "approved")
    ).mappings().one()
    conn.execute(
        capability_run.insert().values(
            capability_run_id=uuid.uuid4(),
            task_id=uuid.UUID(task_id),
            evidence_scope_id=row["evidence_scope_id"],
            capability="options_scoping",
            plan_id=row["plan_id"],
            plan_version=row["version"],
            status="paused",
            started_at=datetime.now(UTC),
        )
    )


def test_confirming_writes_the_record_as_a_new_plan_version(
    engine: Engine, tmp_path: Path
) -> None:
    with api_client(tmp_path, _overrides()) as (client, owner, _other):
        task_id = create_scoping_task(client, owner)
        to_ready(client, owner, task_id)
        artefact_id = _seed_artefact(engine, task_id)
        confirmed = client.post(
            f"/api/v1/tasks/{task_id}/plan/confirm-baseline",
            headers=owner,
            json={"artefact_id": str(artefact_id), "plan_version": 1},
        )

    assert confirmed.status_code == 200, confirmed.text
    body = confirmed.json()
    assert body["version"] == 2
    assert body["scoping"]["baseline_confirmed"] == {
        "artefact_id": str(artefact_id),
        "plan_version": 2,
    }


def test_confirming_the_same_pair_twice_mints_one_version(
    engine: Engine, tmp_path: Path
) -> None:
    with api_client(tmp_path, _overrides()) as (client, owner, _other):
        task_id = create_scoping_task(client, owner)
        to_ready(client, owner, task_id)
        artefact_id = _seed_artefact(engine, task_id)
        body = {"artefact_id": str(artefact_id), "plan_version": 1}
        first = client.post(
            f"/api/v1/tasks/{task_id}/plan/confirm-baseline", headers=owner, json=body
        )
        second = client.post(
            f"/api/v1/tasks/{task_id}/plan/confirm-baseline", headers=owner, json=body
        )

    assert first.json()["version"] == second.json()["version"] == 2
    assert len(_plan_rows(engine, task_id)) == 2


def test_confirming_is_refused_while_a_walk_is_paused(
    engine: Engine, tmp_path: Path
) -> None:
    with api_client(tmp_path, _overrides()) as (client, owner, _other):
        task_id = create_scoping_task(client, owner)
        to_ready(client, owner, task_id)
        artefact_id = _seed_artefact(engine, task_id)
        with engine.begin() as conn:
            _seed_paused_walk(conn, task_id)
        refused = client.post(
            f"/api/v1/tasks/{task_id}/plan/confirm-baseline",
            headers=owner,
            json={"artefact_id": str(artefact_id), "plan_version": 1},
        )
    assert refused.status_code == 409, refused.text
    assert refused.json()["error"]["code"] == "run_active"


def test_confirming_an_artefact_of_another_task_is_not_found(
    engine: Engine, tmp_path: Path
) -> None:
    with api_client(tmp_path, _overrides()) as (client, owner, _other):
        task_id = create_scoping_task(client, owner)
        to_ready(client, owner, task_id)
        refused = client.post(
            f"/api/v1/tasks/{task_id}/plan/confirm-baseline",
            headers=owner,
            json={"artefact_id": str(uuid.uuid4()), "plan_version": 1},
        )
    assert refused.status_code == 404, refused.text


def test_confirm_baseline_does_not_apply_to_an_evidence_search_task(
    engine: Engine, tmp_path: Path
) -> None:
    with api_client(tmp_path, _overrides()) as (client, owner, _other):
        task_id = create_task(client, owner)
        refused = client.post(
            f"/api/v1/tasks/{task_id}/plan/confirm-baseline",
            headers=owner,
            json={"artefact_id": str(uuid.uuid4()), "plan_version": 1},
        )
    assert refused.status_code == 422, refused.text
