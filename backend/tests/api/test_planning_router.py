"""HTTP coverage for durable planner-turn persistence and retry rules."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.api.contract import RunOut
from policy_atlas.api.deps import get_planner_backend
from policy_atlas.api.routers import planning
from policy_atlas.api.routers import runs as runs_router
from policy_atlas.api.stage_vocabulary import stage_for_payload
from policy_atlas.core.schema import (
    capability_run,
    conversation,
    evidence_scope,
    orchestration_plan,
    planning_transcript,
)
from policy_atlas.runtime.conversation_lifecycle import (
    close_planning_conversation,
    ensure_active_planning_conversation,
    seed_draft_from_executed_plan,
)
from policy_atlas.runtime.orchestration_plan import TIME_BANDS, OrchestrationPlan
from policy_atlas.runtime.planner import StubPlannerBackend
from policy_atlas.runtime.planner_prompt import (
    PartChipWire,
    PartOptionWire,
    PartProposalWire,
    PlanDraftWire,
    PlannerTurnWire,
)
from tests.api.resource_support import api_client, create_project


class CountingPlanner(StubPlannerBackend):
    """Stub planner that records the durable rehydration call composition."""

    def __init__(self) -> None:
        self.calls: list[tuple[list[dict[str, str]], dict[str, object] | None]] = []
        self.session_ids: list[uuid.UUID | None] = []

    def plan_turn(
        self,
        turns: list[dict[str, str]],
        previous_draft: dict[str, object] | None,
        *,
        session_id: uuid.UUID | None = None,
    ) -> PlannerTurnWire:
        """Record and delegate the deterministic planner turn."""
        self.calls.append((turns, previous_draft))
        self.session_ids.append(session_id)
        return super().plan_turn(turns, previous_draft)


class FailOncePlanner(CountingPlanner):
    """Planner double that leaves a durable failed transcript row once."""

    def plan_turn(
        self,
        turns: list[dict[str, str]],
        previous_draft: dict[str, object] | None,
        *,
        session_id: uuid.UUID | None = None,
    ) -> PlannerTurnWire:
        """Fail once, then use the ordinary deterministic reply."""
        if not self.calls:
            self.calls.append((turns, previous_draft))
            raise RuntimeError("planned test failure")
        return super().plan_turn(turns, previous_draft, session_id=session_id)


class PartPlanner(CountingPlanner):
    """Planner double that attaches a controlled part proposal to each turn."""

    def __init__(self, part: PartProposalWire) -> None:
        super().__init__()
        self.part = part

    def plan_turn(
        self,
        turns: list[dict[str, str]],
        previous_draft: dict[str, object] | None,
        *,
        session_id: uuid.UUID | None = None,
    ) -> PlannerTurnWire:
        """Return the ordinary stub turn with the configured structured part."""
        turn = super().plan_turn(turns, previous_draft, session_id=session_id)
        return turn.model_copy(update={"part": self.part})


def _reset_turn_locks() -> None:
    """Reset process-local guards to model an API restart in route tests."""
    with planning._turn_locks_guard:
        planning._turn_locks.clear()


def _pending_values(
    project_id: str,
    *,
    client_turn_id: uuid.UUID,
    turn_index: int,
    message: str,
    created_at: datetime,
    status: str = "pending",
    conversation_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Build a direct transcript fixture row for retry-boundary tests."""
    return {
        "id": uuid.uuid4(),
        "project_id": uuid.UUID(project_id),
        "conversation_id": conversation_id,
        "client_turn_id": client_turn_id,
        "turn_index": turn_index,
        "user_message": message,
        "reply": None,
        "planner_state": None,
        "response": None,
        "suggestions": [],
        "status": status,
        "created_at": created_at,
        "completed_at": datetime.now(UTC) if status == "failed" else None,
    }


def test_draft_projection_derives_time_band_and_deduplicates_public_stages() -> None:
    """Drafts gain an honest time band; approved steps use presentation vocabulary."""
    draft = planning._draft_from_wire(
        PlanDraftWire(search_effort="rapid", analysis_depth="standard"), ready=False
    )
    assert draft.time_band == TIME_BANDS[("rapid", "standard")]
    plan = OrchestrationPlan(
        title="Evidence review",
        question="What does the evidence show?",
        backend_scope="both",
        search_effort="deep",
        analysis_depth="deep",
        components=["screen_full", "characterise", "select", "extract", "group"],
        component_rationale={
            "screen_full": "Confirm relevance from the full text",
            "characterise": "Map the evidence base",
            "select": "Choose sources for close reading",
            "extract": "Extract findings",
            "group": "Group related findings",
        },
        grouping_facets=["intervention"],
        steering_mode="moderate",
    )
    projected = planning._draft_from_plan(plan)
    assert [step.stage for step in projected.steps].count("acquire") == 1
    assert [step.stage for step in projected.steps].count("screen") == 1
    assert projected.steps[0].label == "Searching sources"
    assert projected.steps[1].blurb == "Every title and abstract, against your question."
    # The screen_full collapse is a plan-steps presentation rule only: live
    # stage frames keep the pre-027 behaviour (no second "screen" stage row).
    assert (
        stage_for_payload({"component": "screen_full", "registry_component": "screen_full"}) is None
    )


def test_planning_turn_is_durable_idempotent_and_ready_turn_persists_plan(
    engine: Engine, tmp_path: Path
) -> None:
    """Persist both response representations and replay a completed id verbatim."""
    _reset_turn_locks()
    stub = CountingPlanner()
    with api_client(tmp_path, {get_planner_backend: lambda: stub}) as (client, owner, _):
        project_id = create_project(client, owner)
        turn_id = str(uuid.uuid4())
        first = client.post(
            f"/api/v1/projects/{project_id}/planning-turns",
            headers=owner,
            json={"message": "How can cities reduce heat risk?", "client_turn_id": turn_id},
        )
        _reset_turn_locks()
        duplicate = client.post(
            f"/api/v1/projects/{project_id}/planning-turns",
            headers=owner,
            json={"message": "How can cities reduce heat risk?", "client_turn_id": turn_id},
        )
        assert first.status_code == duplicate.status_code == 200
        assert first.json() == duplicate.json()
        assert len(stub.calls) == 1

        transcript = client.get(f"/api/v1/projects/{project_id}/planning-turns", headers=owner)
        assert transcript.status_code == 200
        assert transcript.json()["pagination"] == {"page": 1, "page_size": 50, "total_items": 1}
        assert transcript.json()["data"][0]["turn_index"] == 0
        assert transcript.json()["data"][0]["status"] == "completed"
        conversation_id = first.json()["conversation_id"]
        assert transcript.json()["data"][0]["conversation_id"] == conversation_id

        ready = client.post(
            f"/api/v1/projects/{project_id}/planning-turns",
            headers=owner,
            json={
                "message": "A comparison of intervention options",
                "client_turn_id": str(uuid.uuid4()),
            },
        )
        assert ready.status_code == 200
        assert ready.json()["plan"]["ready"] is True
        assert ready.json()["conversation_id"] == conversation_id
        assert stub.session_ids == [uuid.UUID(conversation_id), uuid.UUID(conversation_id)]
        persisted = client.get(f"/api/v1/projects/{project_id}/plan", headers=owner)
        assert persisted.status_code == 200
        assert persisted.json()["status"] == "approved"
    with engine.connect() as conn:
        rows = (
            conn.execute(
                select(planning_transcript)
                .where(planning_transcript.c.project_id == uuid.UUID(project_id))
                .order_by(planning_transcript.c.turn_index)
            )
            .mappings()
            .all()
        )
        assert [row["turn_index"] for row in rows] == [0, 1]
        assert rows[0]["planner_state"] != rows[0]["response"]["plan"]
        assert rows[1]["status"] == "completed"
        assert rows[1]["completed_at"] is not None
        assert (
            conn.execute(
                select(orchestration_plan.c.plan_id, orchestration_plan.c.conversation_id).where(
                    orchestration_plan.c.project_id == uuid.UUID(project_id)
                )
            ).one()
            .conversation_id
            == uuid.UUID(conversation_id)
        )
        planning_conversation = conn.execute(
            select(conversation.c.title, conversation.c.status).where(
                conversation.c.id == uuid.UUID(conversation_id)
            )
        ).one()
        assert planning_conversation.title == ready.json()["plan"]["title"]
        assert planning_conversation.status == "active"


def test_planning_part_round_trips_and_replays_idempotently(engine: Engine, tmp_path: Path) -> None:
    """Persist a valid card verbatim in both transcript and replay response shapes."""
    _reset_turn_locks()
    part = PartProposalWire(
        id="scope",
        step_label="Plan · 2 of 3 · scope",
        title="Focus on the UK since 2016",
        body="This keeps the search decision-relevant.",
        chips=[
            PartChipWire(label="Since 2016", kind="date_range", value='{"after": "2016"}'),
            PartChipWire(
                label="United Kingdom",
                kind="country_list",
                value='{"countries": ["GB"]}',
            ),
        ],
        options=[
            PartOptionWire(id="confirm", label="Use this scope", primary=True),
            PartOptionWire(id="refine", label="Refine it", primary=False),
        ],
    )
    stub = PartPlanner(part)
    with api_client(tmp_path, {get_planner_backend: lambda: stub}) as (client, owner, _):
        project_id = create_project(client, owner)
        turn_id = str(uuid.uuid4())
        first = client.post(
            f"/api/v1/projects/{project_id}/planning-turns",
            headers=owner,
            json={"message": "How can cities reduce heat risk?", "client_turn_id": turn_id},
        )
        replay = client.post(
            f"/api/v1/projects/{project_id}/planning-turns",
            headers=owner,
            json={"message": "How can cities reduce heat risk?", "client_turn_id": turn_id},
        )
        transcript = client.get(f"/api/v1/projects/{project_id}/planning-turns", headers=owner)
    assert first.status_code == replay.status_code == transcript.status_code == 200
    assert replay.json()["part"] == first.json()["part"]
    assert transcript.json()["data"][0]["part"] == first.json()["part"]
    with engine.connect() as conn:
        stored = conn.execute(
            select(planning_transcript.c.part, planning_transcript.c.response).where(
                planning_transcript.c.project_id == uuid.UUID(project_id)
            )
        ).mappings().one()
    assert stored["part"] == first.json()["part"]
    assert stored["response"]["part"] == first.json()["part"]


def test_planning_part_with_snake_case_option_id_is_kept(tmp_path: Path) -> None:
    """A card whose option id is valid snake_case survives validation intact."""
    _reset_turn_locks()
    part = PartProposalWire(
        id="question",
        step_label="Plan · 1 of 3",
        title="Question",
        options=[
            PartOptionWire(id="quick_look", label="Quick look", primary=True),
            PartOptionWire(id="deep_dive", label="Deep dive", primary=False),
        ],
    )
    with api_client(tmp_path, {get_planner_backend: lambda: PartPlanner(part)}) as (
        client,
        owner,
        _,
    ):
        project_id = create_project(client, owner)
        response = client.post(
            f"/api/v1/projects/{project_id}/planning-turns",
            headers=owner,
            json={
                "message": "How can cities reduce heat risk?",
                "client_turn_id": str(uuid.uuid4()),
            },
        )
    assert response.status_code == 200
    assert response.json()["part"] is not None
    assert [option["id"] for option in response.json()["part"]["options"]] == [
        "quick_look",
        "deep_dive",
    ]


@pytest.mark.parametrize(
    ("part", "reason"),
    [
        (
            PartProposalWire(
                id="question",
                step_label="Plan · 1 of 3",
                title="Question",
                options=[
                    PartOptionWire(id=f"option_{index}", label="Option", primary=index == 0)
                    for index in range(5)
                ],
            ),
            "invalid_option_count",
        ),
        (
            PartProposalWire(
                id="question",
                step_label="Plan · 1 of 3",
                title="Question",
                options=[
                    PartOptionWire(id="one", label="One", primary=False),
                    PartOptionWire(id="two", label="Two", primary=False),
                ],
            ),
            "invalid_primary_count",
        ),
        (
            PartProposalWire(
                id="scope",
                step_label="Plan · 2 of 3",
                title="Scope",
                chips=[PartChipWire(label="Since 2016", kind="date_range", value="not json")],
                options=[
                    PartOptionWire(id="one", label="One", primary=True),
                    PartOptionWire(id="two", label="Two", primary=False),
                ],
            ),
            "invalid_chip_json",
        ),
        (
            PartProposalWire(
                id="question",
                step_label="Plan · 1 of 3",
                title="Question",
                options=[
                    PartOptionWire(id="quick-look", label="Quick look", primary=True),
                    PartOptionWire(id="deep_dive", label="Deep dive", primary=False),
                ],
            ),
            "invalid_option_id",
        ),
    ],
)
def test_malformed_planning_part_degrades_to_prose_and_logs_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, part: PartProposalWire, reason: str
) -> None:
    """Drop invalid cards without failing their otherwise valid planner turn."""
    _reset_turn_locks()
    warnings: list[tuple[tuple[object, ...], dict[str, object]]] = []
    monkeypatch.setattr(
        planning.log,
        "warning",
        lambda *args, **kwargs: warnings.append((args, kwargs)),
    )
    with api_client(tmp_path, {get_planner_backend: lambda: PartPlanner(part)}) as (
        client,
        owner,
        _,
    ):
        project_id = create_project(client, owner)
        response = client.post(
            f"/api/v1/projects/{project_id}/planning-turns",
            headers=owner,
            json={
                "message": "How can cities reduce heat risk?",
                "client_turn_id": str(uuid.uuid4()),
            },
        )
    assert response.status_code == 200
    assert response.json()["part"] is None
    assert warnings == [(("planning_part_dropped",), {"reason": reason})]


def test_newer_turn_demotes_approved_plan_and_reapproval_clears_start_fence(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fence dispatch when a completed planning turn supersedes approval."""
    _reset_turn_locks()
    stub = CountingPlanner()
    with api_client(tmp_path, {get_planner_backend: lambda: stub}) as (client, owner, _):
        project_id = create_project(client, owner)
        first = client.post(
            f"/api/v1/projects/{project_id}/planning-turns",
            headers=owner,
            json={
                "message": "How can cities reduce heat risk?",
                "client_turn_id": str(uuid.uuid4()),
            },
        )
        approved = client.post(
            f"/api/v1/projects/{project_id}/planning-turns",
            headers=owner,
            json={"message": "Compare intervention options", "client_turn_id": str(uuid.uuid4())},
        )
        assert first.status_code == approved.status_code == 200
        with engine.begin() as conn:
            conn.execute(
                planning_transcript.insert().values(
                    id=uuid.uuid4(),
                    project_id=uuid.UUID(project_id),
                    client_turn_id=uuid.uuid4(),
                    turn_index=2,
                    user_message="One more planning detail",
                    reply="A legacy completed reply.",
                    planner_state=first.json()["plan"],
                    response=first.json(),
                    suggestions=[],
                    status="completed",
                    created_at=datetime.now(UTC),
                    completed_at=datetime.now(UTC),
                )
            )
            approved_payload = conn.execute(
                select(orchestration_plan.c.payload)
                .where(orchestration_plan.c.project_id == uuid.UUID(project_id))
                .where(orchestration_plan.c.status == "approved")
            ).scalar_one()
        assert approved_payload["source_turn_index"] == 1

        plan_after_newer_turn = client.get(f"/api/v1/projects/{project_id}/plan", headers=owner)
        transcript = client.get(f"/api/v1/projects/{project_id}/planning-turns", headers=owner)
        stale_start = client.post(f"/api/v1/projects/{project_id}/runs", headers=owner, json={})
        assert plan_after_newer_turn.status_code == transcript.status_code == 200
        assert plan_after_newer_turn.json() == {
            "plan": first.json()["plan"],
            "version": 0,
            "status": "draft",
        }
        assert transcript.json()["data"][-1]["part"] is None
        assert stale_start.status_code == 409
        assert stale_start.json()["error"] == {
            "code": "plan_stale",
            "message": "the plan predates your latest planning message — review it, then start",
        }

        reapproved = client.post(
            f"/api/v1/projects/{project_id}/planning-turns",
            headers=owner,
            json={"message": "Ready to proceed", "client_turn_id": str(uuid.uuid4())},
        )
        assert reapproved.status_code == 200
        reapproved_plan = client.get(f"/api/v1/projects/{project_id}/plan", headers=owner)
        assert reapproved_plan.json()["status"] == "approved"
        with engine.connect() as conn:
            refreshed_payload = conn.execute(
                select(orchestration_plan.c.payload)
                .where(orchestration_plan.c.project_id == uuid.UUID(project_id))
                .where(orchestration_plan.c.status == "approved")
            ).scalar_one()
        assert refreshed_payload["source_turn_index"] == 3

        monkeypatch.setattr(runs_router, "_dispatch_run", lambda *args, **kwargs: None)
        monkeypatch.setattr(
            runs_router,
            "_await_new_run",
            lambda _engine, *, project_id, **_kwargs: RunOut(
                capability_run_id=uuid.uuid4(),
                project_id=project_id,
                plan_id=uuid.uuid4(),
                plan_version=2,
                status="running",
                started_at=datetime.now(UTC),
            ),
        )
        restarted = client.post(f"/api/v1/projects/{project_id}/runs", headers=owner, json={})
        assert restarted.status_code == 201


def test_legacy_approved_plan_without_a_source_turn_index_stays_startable(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stale-plan fence is additive: pre-028 approved payloads retain their behaviour."""
    _reset_turn_locks()
    stub = CountingPlanner()
    with api_client(tmp_path, {get_planner_backend: lambda: stub}) as (client, owner, _):
        project_id = create_project(client, owner)
        first = client.post(
            f"/api/v1/projects/{project_id}/planning-turns",
            headers=owner,
            json={
                "message": "How can cities reduce heat risk?",
                "client_turn_id": str(uuid.uuid4()),
            },
        )
        approved = client.post(
            f"/api/v1/projects/{project_id}/planning-turns",
            headers=owner,
            json={"message": "Compare intervention options", "client_turn_id": str(uuid.uuid4())},
        )
        assert first.status_code == approved.status_code == 200
        with engine.begin() as conn:
            payload = conn.execute(
                select(orchestration_plan.c.payload)
                .where(orchestration_plan.c.project_id == uuid.UUID(project_id))
                .where(orchestration_plan.c.status == "approved")
            ).scalar_one()
            payload.pop("source_turn_index")
            conn.execute(
                orchestration_plan.update()
                .where(orchestration_plan.c.project_id == uuid.UUID(project_id))
                .where(orchestration_plan.c.status == "approved")
                .values(payload=payload)
            )
            conn.execute(
                planning_transcript.insert().values(
                    id=uuid.uuid4(),
                    project_id=uuid.UUID(project_id),
                    client_turn_id=uuid.uuid4(),
                    turn_index=2,
                    user_message="A newer completed legacy turn",
                    reply="A legacy reply.",
                    planner_state=first.json()["plan"],
                    response=first.json(),
                    suggestions=[],
                    status="completed",
                    created_at=datetime.now(UTC),
                    completed_at=datetime.now(UTC),
                )
            )
        plan = client.get(f"/api/v1/projects/{project_id}/plan", headers=owner).json()
        assert plan["status"] == "approved"
        monkeypatch.setattr(runs_router, "_dispatch_run", lambda *args, **kwargs: None)
        monkeypatch.setattr(
            runs_router,
            "_await_new_run",
            lambda _engine, *, project_id, **_kwargs: RunOut(
                capability_run_id=uuid.uuid4(),
                project_id=project_id,
                plan_id=uuid.uuid4(),
                plan_version=1,
                status="running",
                started_at=datetime.now(UTC),
            ),
        )
        started = client.post(f"/api/v1/projects/{project_id}/runs", headers=owner, json={})
        assert started.status_code == 201


def test_planning_rehydrates_after_restart_and_get_plan_reads_stored_draft(
    engine: Engine, tmp_path: Path
) -> None:
    """Use only completed durable rows for planner parity and draft reads."""
    _reset_turn_locks()
    stub = CountingPlanner()
    with api_client(tmp_path, {get_planner_backend: lambda: stub}) as (client, owner, _):
        project_id = create_project(client, owner)
        first = client.post(
            f"/api/v1/projects/{project_id}/planning-turns",
            headers=owner,
            json={
                "message": "How can cities reduce heat risk?",
                "client_turn_id": str(uuid.uuid4()),
            },
        )
        assert first.status_code == 200
        _reset_turn_locks()
        draft_after_restart = client.get(f"/api/v1/projects/{project_id}/plan", headers=owner)
        assert draft_after_restart.status_code == 200
        assert draft_after_restart.json() == {
            "plan": first.json()["plan"],
            "version": 0,
            "status": "draft",
        }

        second_message = "A comparison of intervention options"
        second = client.post(
            f"/api/v1/projects/{project_id}/planning-turns",
            headers=owner,
            json={"message": second_message, "client_turn_id": str(uuid.uuid4())},
        )
        assert second.status_code == 200
    with engine.connect() as conn:
        first_row = (
            conn.execute(
                select(planning_transcript)
                .where(planning_transcript.c.project_id == uuid.UUID(project_id))
                .where(planning_transcript.c.turn_index == 0)
            )
            .mappings()
            .one()
        )
    assert stub.calls[1][0] == [
        {"role": "user", "text": "How can cities reduce heat risk?"},
        {"role": "planner", "text": first.json()["reply"]},
        {"role": "user", "text": second_message},
    ]
    assert stub.calls[1][1] == first_row["planner_state"]
    assert stub.calls[1][1] != first_row["response"]["plan"]


def test_failed_turn_retries_in_place_and_stale_rules_are_honest(
    engine: Engine, tmp_path: Path
) -> None:
    """Keep the phase-one row on planner failure and enforce retry boundaries."""
    _reset_turn_locks()
    stub = FailOncePlanner()
    with api_client(tmp_path, {get_planner_backend: lambda: stub}) as (client, owner, _):
        project_id = create_project(client, owner)
        turn_id = str(uuid.uuid4())
        failed = client.post(
            f"/api/v1/projects/{project_id}/planning-turns",
            headers=owner,
            json={"message": "Recoverable planner failure", "client_turn_id": turn_id},
        )
        assert failed.status_code == 500
        listed = client.get(f"/api/v1/projects/{project_id}/planning-turns", headers=owner)
        assert listed.json()["data"] == [
            {
                "turn_index": 0,
                "conversation_id": listed.json()["data"][0]["conversation_id"],
                "client_turn_id": turn_id,
                "user_message": "Recoverable planner failure",
                "reply": None,
                "suggestions": [],
                "part": None,
                "status": "failed",
                "created_at": listed.json()["data"][0]["created_at"],
                "completed_at": listed.json()["data"][0]["completed_at"],
            }
        ]
        retried = client.post(
            f"/api/v1/projects/{project_id}/planning-turns",
            headers=owner,
            json={"message": "Recoverable planner failure", "client_turn_id": turn_id},
        )
        assert retried.status_code == 200
        mismatch = client.post(
            f"/api/v1/projects/{project_id}/planning-turns",
            headers=owner,
            json={"message": "Different message", "client_turn_id": turn_id},
        )
        assert mismatch.status_code == 409
        assert mismatch.json()["error"]["code"] == "stale_turn"

        old_id, latest_id = uuid.uuid4(), uuid.uuid4()
        with engine.begin() as conn:
            conn.execute(
                planning_transcript.insert(),
                [
                    _pending_values(
                        project_id,
                        client_turn_id=old_id,
                        turn_index=1,
                        message="old failed",
                        created_at=datetime.now(UTC),
                        status="failed",
                    ),
                    _pending_values(
                        project_id,
                        client_turn_id=latest_id,
                        turn_index=2,
                        message="latest failed",
                        created_at=datetime.now(UTC),
                        status="failed",
                    ),
                ],
            )
        stale = client.post(
            f"/api/v1/projects/{project_id}/planning-turns",
            headers=owner,
            json={"message": "old failed", "client_turn_id": str(old_id)},
        )
        assert stale.status_code == 409
        assert stale.json()["error"]["code"] == "stale_turn"


def test_pending_staleness_fresh_pending_and_transcript_ownership(
    engine: Engine, tmp_path: Path
) -> None:
    """Fail old pending rows on read, block fresh ones, and preserve owner 404s."""
    _reset_turn_locks()
    stub = CountingPlanner()
    with api_client(tmp_path, {get_planner_backend: lambda: stub}) as (client, owner, other):
        project_id = create_project(client, owner)
        old_id = uuid.uuid4()
        with engine.begin() as conn:
            conversation_id = ensure_active_planning_conversation(
                conn, project_id=uuid.UUID(project_id), now=datetime.now(UTC)
            )
            conn.execute(
                planning_transcript.insert().values(
                    **_pending_values(
                        project_id,
                        client_turn_id=old_id,
                        turn_index=0,
                        message="expired pending",
                        created_at=datetime.now(UTC) - timedelta(minutes=11),
                        conversation_id=conversation_id,
                    )
                )
            )
        old_read = client.get(f"/api/v1/projects/{project_id}/planning-turns", headers=owner)
        assert old_read.status_code == 200
        assert old_read.json()["data"][0]["status"] == "failed"
        assert old_read.json()["data"][0]["conversation_id"] == str(conversation_id)
        assert old_read.json()["data"][0]["completed_at"] is not None
        other_read = client.get(f"/api/v1/projects/{project_id}/planning-turns", headers=other)
        assert other_read.status_code == 404

        fresh_id = uuid.uuid4()
        with engine.begin() as conn:
            conn.execute(
                planning_transcript.insert().values(
                    **_pending_values(
                        project_id,
                        client_turn_id=fresh_id,
                        turn_index=1,
                        message="fresh pending",
                        created_at=datetime.now(UTC),
                        conversation_id=conversation_id,
                    )
                )
            )
        blocked = client.post(
            f"/api/v1/projects/{project_id}/planning-turns",
            headers=owner,
            json={"message": "a distinct new turn", "client_turn_id": str(uuid.uuid4())},
        )
        assert blocked.status_code == 409
        assert blocked.json()["error"]["code"] == "planning_turn_in_progress"

        # A fresh (in-window) pending row lists honestly as pending — the
        # crash-between-phases incomplete-turn render depends on it.
        fresh_read = client.get(f"/api/v1/projects/{project_id}/planning-turns", headers=owner)
        assert fresh_read.status_code == 200
        fresh_row = fresh_read.json()["data"][1]
        assert fresh_row["status"] == "pending"
        assert fresh_row["reply"] is None
        assert fresh_row["completed_at"] is None


def test_planning_turn_409s_while_walk_active_or_parked(engine: Engine, tmp_path: Path) -> None:
    """409 `run_active` fences replanning while a walk is running or parked."""
    _reset_turn_locks()
    stub = CountingPlanner()
    with api_client(tmp_path, {get_planner_backend: lambda: stub}) as (client, owner, _other):
        project_id = create_project(client, owner)
        run_id = uuid.uuid4()
        scope_id = uuid.uuid4()
        with engine.begin() as conn:
            conn.execute(
                evidence_scope.insert().values(
                    evidence_scope_id=scope_id,
                    project_id=uuid.UUID(project_id),
                    intent="planning-router fence sweep",
                    context={},
                    created_at=datetime.now(UTC),
                )
            )
            conn.execute(
                capability_run.insert().values(
                    capability_run_id=run_id,
                    project_id=uuid.UUID(project_id),
                    evidence_scope_id=scope_id,
                    capability="evidence_base",
                    plan_id=uuid.uuid4(),
                    plan_version=1,
                    status="paused",
                    session_id=None,
                    started_at=datetime.now(UTC),
                    ended_at=None,
                )
            )
        try:
            paused = client.post(
                f"/api/v1/projects/{project_id}/planning-turns",
                headers=owner,
                json={"message": "Steer this walk", "client_turn_id": str(uuid.uuid4())},
            )
            assert paused.status_code == 409
            assert paused.json()["error"]["code"] == "run_active"

            with engine.begin() as conn:
                conn.execute(
                    capability_run.update()
                    .where(capability_run.c.capability_run_id == run_id)
                    .values(status="running")
                )
            running = client.post(
                f"/api/v1/projects/{project_id}/planning-turns",
                headers=owner,
                json={"message": "Steer this walk again", "client_turn_id": str(uuid.uuid4())},
            )
            assert running.status_code == 409
            assert running.json()["error"]["code"] == "run_active"

            with engine.begin() as conn:
                conn.execute(
                    capability_run.update()
                    .where(capability_run.c.capability_run_id == run_id)
                    .values(status="succeeded", ended_at=datetime.now(UTC))
                )
            succeeded = client.post(
                f"/api/v1/projects/{project_id}/planning-turns",
                headers=owner,
                json={"message": "Replan now", "client_turn_id": str(uuid.uuid4())},
            )
            assert succeeded.status_code == 200
        finally:
            with engine.begin() as conn:
                conn.execute(
                    capability_run.update()
                    .where(capability_run.c.capability_run_id == run_id)
                    .values(status="aborted", ended_at=datetime.now(UTC))
                )


def test_run_starting_mid_planner_call_fails_turn_and_persists_no_plan(
    engine: Engine, tmp_path: Path
) -> None:
    """Phase two re-checks the run fence: a plan never lands under a live walk."""
    _reset_turn_locks()

    class RunStartsMidPlanner(CountingPlanner):
        """Planner double that models a run starting during the LLM call."""

        project_id: str | None = None

        def plan_turn(
            self,
            turns: list[dict[str, str]],
            previous_draft: dict[str, object] | None,
            *,
            session_id: uuid.UUID | None = None,
        ) -> PlannerTurnWire:
            wire = super().plan_turn(turns, previous_draft, session_id=session_id)
            if wire.ready and self.project_id is not None:
                scope_id = uuid.uuid4()
                with engine.begin() as conn:
                    conn.execute(
                        evidence_scope.insert().values(
                            evidence_scope_id=scope_id,
                            project_id=uuid.UUID(self.project_id),
                            intent="mid-call run start",
                            context={},
                            created_at=datetime.now(UTC),
                        )
                    )
                    conn.execute(
                        capability_run.insert().values(
                            capability_run_id=uuid.uuid4(),
                            project_id=uuid.UUID(self.project_id),
                            evidence_scope_id=scope_id,
                            capability="evidence_base",
                            plan_id=uuid.uuid4(),
                            plan_version=1,
                            status="running",
                            session_id=None,
                            started_at=datetime.now(UTC),
                            ended_at=None,
                        )
                    )
            return wire

    stub = RunStartsMidPlanner()
    with api_client(tmp_path, {get_planner_backend: lambda: stub}) as (client, owner, _):
        project_id = create_project(client, owner)
        stub.project_id = project_id
        first = client.post(
            f"/api/v1/projects/{project_id}/planning-turns",
            headers=owner,
            json={
                "message": "How can cities reduce heat risk?",
                "client_turn_id": str(uuid.uuid4()),
            },
        )
        assert first.status_code == 200

        conflicted = client.post(
            f"/api/v1/projects/{project_id}/planning-turns",
            headers=owner,
            json={"message": "Proceed with the full review.", "client_turn_id": str(uuid.uuid4())},
        )
        assert conflicted.status_code == 409
        assert conflicted.json()["error"]["code"] == "run_active"

        with engine.begin() as conn:
            plans = conn.execute(
                select(orchestration_plan.c.plan_id).where(
                    orchestration_plan.c.project_id == uuid.UUID(project_id)
                )
            ).all()
            assert plans == []
            last_status = conn.execute(
                select(planning_transcript.c.status)
                .where(planning_transcript.c.project_id == uuid.UUID(project_id))
                .order_by(planning_transcript.c.turn_index.desc())
                .limit(1)
            ).scalar_one()
        assert last_status == "failed"


def test_closed_planning_conversation_creates_seeded_successor(
    engine: Engine, tmp_path: Path
) -> None:
    """A successor starts from the approved plan, never the closed transcript."""
    _reset_turn_locks()
    stub = CountingPlanner()
    with api_client(tmp_path, {get_planner_backend: lambda: stub}) as (client, owner, _):
        project_id = create_project(client, owner)
        first = client.post(
            f"/api/v1/projects/{project_id}/planning-turns",
            headers=owner,
            json={
                "message": "How can cities reduce heat risk?",
                "client_turn_id": str(uuid.uuid4()),
            },
        )
        approved = client.post(
            f"/api/v1/projects/{project_id}/planning-turns",
            headers=owner,
            json={"message": "Compare intervention options", "client_turn_id": str(uuid.uuid4())},
        )
        assert first.status_code == approved.status_code == 200
        predecessor_id = uuid.UUID(approved.json()["conversation_id"])
        with engine.begin() as conn:
            plan_payload = conn.execute(
                select(orchestration_plan.c.payload)
                .where(orchestration_plan.c.project_id == uuid.UUID(project_id))
                .where(orchestration_plan.c.status == "approved")
            ).scalar_one()
            close_planning_conversation(
                conn, project_id=uuid.UUID(project_id), closed_at=datetime.now(UTC)
            )

        successor = client.post(
            f"/api/v1/projects/{project_id}/planning-turns",
            headers=owner,
            json={
                "message": "Run it again with a narrower scope",
                "client_turn_id": str(uuid.uuid4()),
            },
        )
        assert successor.status_code == 200
        successor_id = uuid.UUID(successor.json()["conversation_id"])
        assert successor_id != predecessor_id
        assert stub.calls[-1][0] == [
            {"role": "user", "text": "Run it again with a narrower scope"}
        ]
        assert stub.calls[-1][1] == seed_draft_from_executed_plan(
            OrchestrationPlan.model_validate(plan_payload)
        ).model_dump(mode="json")
        assert stub.session_ids[-1] == successor_id

        follow_up = client.post(
            f"/api/v1/projects/{project_id}/planning-turns",
            headers=owner,
            json={
                "message": "Keep the same evidence question",
                "client_turn_id": str(uuid.uuid4()),
            },
        )
        assert follow_up.status_code == 200
        assert stub.calls[-1][0] == [
            {"role": "user", "text": "Run it again with a narrower scope"},
            {"role": "planner", "text": successor.json()["reply"]},
            {"role": "user", "text": "Keep the same evidence question"},
        ]
        assert stub.session_ids[-1] == successor_id
