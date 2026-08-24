"""Round-trip smoke tests for the `/api/v1` Pydantic contract package.

No database needed — these tests only exercise `pydantic` validation/
serialisation over the contract models in
`policy_atlas.api.contract`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from policy_atlas.api.contract import (
    PAGE_SIZE_MAX,
    AbortResponse,
    CheckInResponse,
    FreeTextConfirmResponse,
    FreeTextResponse,
    OptionResponse,
    Page,
    PageMeta,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    RunCreate,
    SseFrame,
)
from policy_atlas.api.contract.sse import (
    ArtefactSectionCompletedFrame,
    ArtefactSectionStartedFrame,
    ArtefactSkeletonFrame,
    CheckinPendingFrame,
    CheckinResolvedFrame,
    PlanUpdatedFrame,
    ProjectUpdatedFrame,
    RunStatusFrame,
    StageCompletedFrame,
    StageFailedFrame,
    StageStartedFrame,
    TickFrame,
)


def _now() -> datetime:
    return datetime.now(UTC)


# --- check-in response tagged union -----------------------------------------


def test_option_response_discriminates() -> None:
    """A dict tagged `kind: "option"` deserialises to `OptionResponse`."""
    adapter: TypeAdapter[CheckInResponse] = TypeAdapter(CheckInResponse)
    model = adapter.validate_python(
        {"kind": "option", "option_id": "opt-1", "params": {"budget": 10}}
    )
    assert isinstance(model, OptionResponse)
    assert model.option_id == "opt-1"


def test_free_text_response_discriminates() -> None:
    """A dict tagged `kind: "free_text"` deserialises to `FreeTextResponse`."""
    adapter: TypeAdapter[CheckInResponse] = TypeAdapter(CheckInResponse)
    model = adapter.validate_python({"kind": "free_text", "text": "widen to grey lit"})
    assert isinstance(model, FreeTextResponse)
    assert model.text == "widen to grey lit"


def test_free_text_confirm_response_discriminates() -> None:
    """A dict tagged `kind: "free_text_confirm"` deserialises correctly."""
    adapter: TypeAdapter[CheckInResponse] = TypeAdapter(CheckInResponse)
    model = adapter.validate_python(
        {"kind": "free_text_confirm", "confirm_token": "tok-1", "apply": True}
    )
    assert isinstance(model, FreeTextConfirmResponse)
    assert model.apply is True


def test_abort_response_discriminates() -> None:
    """A dict tagged `kind: "abort"` deserialises to `AbortResponse`."""
    adapter: TypeAdapter[CheckInResponse] = TypeAdapter(CheckInResponse)
    model = adapter.validate_python({"kind": "abort"})
    assert isinstance(model, AbortResponse)


def test_check_in_response_unknown_kind_rejected() -> None:
    """An unknown discriminator value fails validation."""
    adapter: TypeAdapter[CheckInResponse] = TypeAdapter(CheckInResponse)
    with pytest.raises(ValidationError):
        adapter.validate_python({"kind": "not_a_real_kind"})


def test_option_response_extra_field_rejected() -> None:
    """Inbound models forbid unknown fields."""
    with pytest.raises(ValidationError):
        OptionResponse.model_validate(
            {"kind": "option", "option_id": "opt-1", "surprise": "nope"}
        )


# --- inbound extra="forbid" ---------------------------------------------------


def test_project_create_extra_field_raises() -> None:
    """An extra field on `ProjectCreate` (inbound) raises."""
    with pytest.raises(ValidationError):
        ProjectCreate.model_validate({"name": "A project", "not_a_field": 1})


def test_project_create_strips_and_bounds_name() -> None:
    """`name` is stripped of outer whitespace, then bounded 1-200 chars."""
    model = ProjectCreate.model_validate({"name": "  My Project  "})
    assert model.name == "My Project"
    with pytest.raises(ValidationError):
        ProjectCreate.model_validate({"name": "   "})
    with pytest.raises(ValidationError):
        ProjectCreate.model_validate({"name": "x" * 201})


def test_project_update_is_all_optional_and_forbids_extra() -> None:
    """`ProjectUpdate` accepts an empty patch body but rejects unknown fields."""
    model = ProjectUpdate.model_validate({})
    assert model.name is None
    assert model.question is None
    with pytest.raises(ValidationError):
        ProjectUpdate.model_validate({"unexpected": "field"})


def test_run_create_forbids_any_body() -> None:
    """`RunCreate` accepts `{}` but rejects any field at all."""
    RunCreate.model_validate({})
    with pytest.raises(ValidationError):
        RunCreate.model_validate({"note": "please run"})


# --- pagination ---------------------------------------------------------------


def test_page_of_project_out_serialises() -> None:
    """`Page[ProjectOut]` round-trips a list of projects with pagination meta."""

    class ProjectPage(BaseModel):
        page: Page[ProjectOut]

    project = ProjectOut(
        project_id=uuid.uuid4(),
        name="A project",
        question=None,
        status="active",
        created_at=_now(),
        updated_at=_now(),
        archived_at=None,
        latest_run=None,
        # Task 033 made all three required: `visibility` is a column, and
        # `is_owner`/`owner_display` are caller-relative, so no default could
        # be honest about which caller the page was built for.
        visibility="org",
        is_owner=True,
        owner_display="Test User",
    )
    wrapper = ProjectPage(
        page=Page[ProjectOut](
            data=[project],
            pagination=PageMeta(page=1, page_size=50, total_items=1),
        )
    )
    dumped = wrapper.model_dump(mode="json")
    assert dumped["page"]["data"][0]["name"] == "A project"
    assert dumped["page"]["pagination"]["total_items"] == 1

    # Round-trip back through validation.
    restored = ProjectPage.model_validate(dumped)
    assert restored.page.data[0].project_id == project.project_id


def test_page_size_max_enforced_on_page_meta() -> None:
    """`PageMeta.page_size` is capped at `PAGE_SIZE_MAX`."""
    PageMeta(page=1, page_size=PAGE_SIZE_MAX, total_items=0)
    with pytest.raises(ValidationError):
        PageMeta(page=1, page_size=PAGE_SIZE_MAX + 1, total_items=0)


# --- SSE frame union ------------------------------------------------------


def _adapter() -> TypeAdapter[SseFrame]:
    return TypeAdapter(SseFrame)


def test_run_status_frame_discriminates() -> None:
    """`type: "run.status"` deserialises to `RunStatusFrame`."""
    model = _adapter().validate_python(
        {
            "type": "run.status",
            "sequence": 1,
            "occurred_at": _now().isoformat(),
            "capability_run_id": str(uuid.uuid4()),
            "status": "running",
        }
    )
    assert isinstance(model, RunStatusFrame)


def test_stage_started_frame_discriminates() -> None:
    """`type: "stage.started"` deserialises to `StageStartedFrame`."""
    model = _adapter().validate_python(
        {
            "type": "stage.started",
            "sequence": 2,
            "occurred_at": _now().isoformat(),
            "stage": "acquire",
            "label": "Searching sources",
            "blurb": "…",
        }
    )
    assert isinstance(model, StageStartedFrame)


def test_stage_completed_frame_discriminates() -> None:
    """`type: "stage.completed"` deserialises to `StageCompletedFrame`."""
    model = _adapter().validate_python(
        {
            "type": "stage.completed",
            "sequence": 3,
            "occurred_at": _now().isoformat(),
            "stage": "acquire",
            "label": "Searching sources",
            "summary": {"found": 58},
            "seconds": 12.4,
        }
    )
    assert isinstance(model, StageCompletedFrame)
    assert model.summary == {"found": 58}


def test_stage_failed_frame_discriminates() -> None:
    """`type: "stage.failed"` deserialises to `StageFailedFrame`."""
    model = _adapter().validate_python(
        {
            "type": "stage.failed",
            "sequence": 4,
            "occurred_at": _now().isoformat(),
            "stage": "characterise",
            "label": "Characterising the landscape",
            "reason": "backend timeout",
            "skipped": True,
        }
    )
    assert isinstance(model, StageFailedFrame)


def test_artefact_frames_discriminate_with_whole_section_prose() -> None:
    """The three live-artefact frame shapes retain their display identity."""
    skeleton = _adapter().validate_python(
        {
            "type": "artefact.skeleton",
            "sequence": 5,
            "occurred_at": _now().isoformat(),
            "sections": [
                {"index": 0, "title": "Key findings", "focus": "Headlines"},
                {"index": 1, "title": "Evidence", "focus": "What changed"},
            ],
        }
    )
    started = _adapter().validate_python(
        {
            "type": "artefact.section_started",
            "sequence": 6,
            "occurred_at": _now().isoformat(),
            "index": 1,
        }
    )
    completed = _adapter().validate_python(
        {
            "type": "artefact.section_completed",
            "sequence": 7,
            "occurred_at": _now().isoformat(),
            "index": 1,
            "title": "Evidence",
            "prose": "Whole completed section prose.",
        }
    )
    assert isinstance(skeleton, ArtefactSkeletonFrame)
    assert isinstance(started, ArtefactSectionStartedFrame)
    assert isinstance(completed, ArtefactSectionCompletedFrame)
    assert completed.prose == "Whole completed section prose."


def test_checkin_pending_frame_discriminates() -> None:
    """`type: "checkin.pending"` deserialises to `CheckinPendingFrame`."""
    model = _adapter().validate_python(
        {
            "type": "checkin.pending",
            "sequence": 5,
            "occurred_at": _now().isoformat(),
            "check_in": {
                "check_in_id": str(uuid.uuid4()),
                "kind": "steer_point",
                "boundary": "after_component",
                "component": "acquire",
                "stage": "acquire",
                "render": "58 sources found. Proceed?",
                "options": [
                    {
                        "id": "proceed",
                        "label": "Proceed",
                        "description": "Continue with the current scope.",
                        "requires_user_input": False,
                        "suggested": True,
                    }
                ],
                "triggers": [],
                "segment_reentry_allowed": True,
                "rerun_component": None,
                "status": "pending",
                "created_at": _now().isoformat(),
                "sequence": 5,
            },
        }
    )
    assert isinstance(model, CheckinPendingFrame)
    assert model.check_in.options[0].id == "proceed"


def test_checkin_resolved_frame_discriminates() -> None:
    """`type: "checkin.resolved"` deserialises to `CheckinResolvedFrame`."""
    model = _adapter().validate_python(
        {
            "type": "checkin.resolved",
            "sequence": 6,
            "occurred_at": _now().isoformat(),
            "check_in_id": str(uuid.uuid4()),
            "response": {"kind": "option", "option_id": "proceed"},
            "decided_by": "user",
        }
    )
    assert isinstance(model, CheckinResolvedFrame)


def test_plan_updated_frame_discriminates() -> None:
    """`type: "plan.updated"` deserialises to `PlanUpdatedFrame`."""
    model = _adapter().validate_python(
        {
            "type": "plan.updated",
            "sequence": 7,
            "occurred_at": _now().isoformat(),
            "plan": {"title": "Draft title", "ready": False},
            "version": 2,
        }
    )
    assert isinstance(model, PlanUpdatedFrame)
    assert model.plan.title == "Draft title"


def test_project_updated_frame_discriminates() -> None:
    """`type: "project.updated"` deserialises to `ProjectUpdatedFrame`."""
    model = _adapter().validate_python(
        {
            "type": "project.updated",
            "sequence": 8,
            "occurred_at": _now().isoformat(),
            "name": "Renamed project",
        }
    )
    assert isinstance(model, ProjectUpdatedFrame)


def test_tick_frame_discriminates_and_has_no_sequence() -> None:
    """`type: "tick"` deserialises to `TickFrame`, with no `sequence` field."""
    model = _adapter().validate_python(
        {
            "type": "tick",
            "occurred_at": _now().isoformat(),
            "note": "still working…",
        }
    )
    assert isinstance(model, TickFrame)
    assert not hasattr(model, "sequence")


def test_sse_frame_unknown_type_rejected() -> None:
    """An unknown `type` discriminator fails validation."""
    with pytest.raises(ValidationError):
        _adapter().validate_python({"type": "not_a_real_frame", "occurred_at": _now().isoformat()})
