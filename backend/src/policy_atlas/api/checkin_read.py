"""Shared durable steering-pause projection for HTTP and SSE readers."""

from __future__ import annotations

from typing import Any

from policy_atlas.api.contract import CheckInOption, CheckInOut, CheckInTrigger
from policy_atlas.api.stage_vocabulary import stage_for_payload
from policy_atlas.runtime.task_plan import canonical_steer_point


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
            why=option.get("why") if isinstance(option.get("why"), str) else None,
            endorsement=(
                option.get("endorsement") if isinstance(option.get("endorsement"), str) else None
            ),
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
        bundle=_task_bundle(payload),
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


def _task_bundle(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Project only the owner-approved display fields from a durable bundle."""
    bundle = payload.get("bundle")
    # Pause records are never rewritten, so a pre-038 record still carries
    # the old P2 steer-point id (task 038, contract A3).
    point = canonical_steer_point(payload.get("steer_point"))
    if not isinstance(bundle, dict) or not isinstance(point, str):
        return None
    if point == "search_review":
        return {
            "backends": bundle.get("backends") if isinstance(bundle.get("backends"), list) else [],
            "queries": bundle.get("queries") if isinstance(bundle.get("queries"), list) else [],
            "sample_titles": bundle.get("sample_titles")
            if isinstance(bundle.get("sample_titles"), list)
            else [],
        }
    if point == "evidence_search_coverage":
        themes = bundle.get("themes")
        return {"themes": themes if isinstance(themes, list) else []}
    if point == "deepening_selection":
        rows = bundle.get("selection_preview")
        preview_rows = rows if isinstance(rows, list) else []
        shortlist = [
            {"title": row.get("title"), "stratum": row.get("stratum")}
            for row in preview_rows
            if isinstance(row, dict)
        ]
        return {"shortlist": shortlist}
    if point == "finding_groups":
        return {"groups": bundle.get("groups") if isinstance(bundle.get("groups"), list) else []}
    if point == "synthesis_shape":
        proposal = bundle.get("proposal")
        rows = proposal.get("proposed_sections") if isinstance(proposal, dict) else []
        proposed_rows = rows if isinstance(rows, list) else []
        return {
            "proposed_sections": [
                {"title": row.get("title"), "focus": row.get("focus")}
                for row in proposed_rows
                if isinstance(row, dict)
            ]
        }
    return None
