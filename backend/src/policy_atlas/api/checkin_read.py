"""Shared durable steering-pause projection for HTTP and SSE readers."""

from __future__ import annotations

from typing import Any

from policy_atlas.api.contract import CheckInOption, CheckInOut, CheckInTrigger
from policy_atlas.api.stage_vocabulary import stage_for_payload


def _render(payload: dict[str, Any]) -> str:
    """Return the pause's persisted deterministic render (content of record)."""
    persisted = payload.get("render")
    if isinstance(persisted, str) and persisted:
        return persisted
    component = payload.get("component") or "walk"
    kind = payload.get("kind") or "check_in"
    lines = [f"{component}: {kind}"]
    for option in payload.get("options", []):
        if isinstance(option, dict) and isinstance(option.get("id"), str):
            lines.append(str(option.get("label") or option["id"]))
    return "\n".join(lines)


def _check_in(row: dict[str, Any], *, decided: bool) -> CheckInOut:
    """Project one durable steering.pause event into the public read model."""
    payload = row["payload"]
    if not isinstance(payload, dict):
        raise LookupError("check-in has malformed payload")
    options = [
        CheckInOption(
            id=str(option["id"]),
            label=str(option.get("label") or option["id"]),
            description=str(option.get("description") or ""),
            requires_user_input=option.get("requires_user_input") is True,
            suggested=option.get("suggested") is True,
        )
        for option in payload.get("options", [])
        if isinstance(option, dict) and isinstance(option.get("id"), str)
    ]
    triggers = [
        CheckInTrigger(trigger=str(trigger["trigger"]), detail=trigger.get("detail"))
        for trigger in payload.get("triggers", [])
        if isinstance(trigger, dict) and isinstance(trigger.get("trigger"), str)
    ]
    boundary = payload.get("boundary")
    if boundary not in {"after_component", "before_component"}:
        raise LookupError("check-in has malformed boundary")
    return CheckInOut(
        check_in_id=row["event_id"],
        kind=str(payload.get("kind") or "check_in"),
        boundary=boundary,
        component=payload.get("component") if isinstance(payload.get("component"), str) else None,
        # The public presentation key, never the raw component name — the raw
        # name leaked internal vocabulary onto the check-in card (review
        # finding MAJOR-1, 2026-07-21; the field's contract always said
        # "presentation stage key").
        stage=stage_for_payload(payload),
        render=_render(payload),
        options=options,
        triggers=triggers,
        segment_reentry_allowed=payload.get("segment_reentry_allowed") is True,
        rerun_component=(
            payload.get("rerun_component")
            if isinstance(payload.get("rerun_component"), str)
            else None
        ),
        status="decided" if decided else "pending",
        created_at=row["occurred_at"],
        sequence=row["sequence"],
    )
