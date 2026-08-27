"""The public stage vocabulary: internal component names → presentation keys.

Shared by the SSE frame builder and the check-in read model (review finding
MAJOR-1, 2026-07-21: the check-in card served the raw runner component name in
its ``stage`` field, leaking internal vocabulary the locked-vocabulary pin and
the field's own contract forbid). Internal names must never leave the API —
``StageKey`` is the pinned contract vocabulary, labels/blurbs are
server-supplied presentation.
"""

from __future__ import annotations

from typing import Any

from policy_atlas.api.contract import StageKey
from policy_atlas.runtime.orchestration_plan import registry_component_for

STAGE_PRESENTATION: dict[StageKey, tuple[str, str]] = {
    "acquire": ("Searching sources", "Queries out to academic and policy databases."),
    "screen": ("Screening for relevance", "Every title and abstract, against your question."),
    "classify": ("Sorting by evidence type", "Each source is labelled by its evidence type."),
    "appraise": ("Appraising quality", "How much weight each source can bear."),
    "characterise": ("Mapping the landscape", "What the evidence covers, and where it is thin."),
    "select": ("Shortlisting", "The strongest, most varied set for close reading."),
    "extract": ("Extracting findings", "Each claim is pulled out with its exact quote."),
    "group": ("Grouping findings", "Findings that answer the same question, together."),
    "synthesise": ("Writing the evidence base", "Cited, checked, ready to challenge."),
}

STAGE_BY_REGISTRY: dict[str, StageKey] = {
    "acquire": "acquire",
    "screen": "screen",
    "screen_full": "screen",
    "classify": "classify",
    "appraise": "appraise",
    "characterise": "characterise",
    "select": "select",
    "extract": "extract",
    "group": "group",
    "synthesise": "synthesise",
}


def stage_for_payload(payload: dict[str, Any]) -> StageKey | None:
    """Map a composed or registry component name onto a public stage key."""
    component = payload.get("component")
    if not isinstance(component, str):
        return None
    registry_component = payload.get("registry_component")
    if not isinstance(registry_component, str):
        registry_component = registry_component_for(component)
    if registry_component == "screen_full":
        # screen_full maps to "screen" only for the approved-plan steps list
        # (approved item 15's collapse). Live stage frames keep the pre-027
        # behaviour — emitting a second "Screening for relevance" here put a
        # duplicate, misdescribed row on deep-depth timelines (review, 2026-07-29).
        return None
    return STAGE_BY_REGISTRY.get(registry_component)


def presentation(stage: StageKey) -> tuple[str, str]:
    """Return the server-owned label and blurb for a public stage."""
    return STAGE_PRESENTATION[stage]
