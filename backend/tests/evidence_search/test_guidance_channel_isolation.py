"""Cross-component isolation tests for Family B guidance channels (024
steering surface): B1 ``search.guidance``, B3 ``grouping.guidance``, B5
``characterise.guidance``.

Mirrors the 017 criteria-isolation precedent
(``test_criteria_key_handling_confined_to_screen_module`` /
``test_screen_criteria_leave_evidence_scope_intent_unchanged`` in
tests/evidence_search/assess/test_screen.py): each channel's guidance must reach
ONLY its own component's prompt payload —
(a) the target component's rendered prompt contains it,
(b) ``evidence_scope.intent``/``evidence_scope.context`` are untouched, and
(c) sibling components' prompts never contain it.
"""

from __future__ import annotations

from policy_atlas.evidence_search.assess.screen_prompt import (
    ScreenEnvelopePayload,
    build_screen_messages,
)
from policy_atlas.evidence_search.clustering_engine import ClusterUnit
from policy_atlas.evidence_search.corpus.theme_grouping import (
    DISCOVERY_SYSTEM_PROMPT,
    _discovery_messages_with_guidance,
)
from policy_atlas.evidence_search.group.group_clustering import (
    _DISCOVERY_SYSTEM_TEMPLATE,
    _PROJECTION_SUBJECT,
    _PROJECTION_UNIT_INTRO,
    build_discovery_messages,
)
from policy_atlas.evidence_search.sourcing.search_prompts import (
    QueriesPayload,
    build_queries_messages,
)

_INTENT = "Evaluate home energy retrofit grants."
_B1_GUIDANCE_TEXT = "prioritise UK policy evaluations"
_B3_GUIDANCE_TEXT = "organise by policy instrument, not sector"
_B5_GUIDANCE_TEXT = "organise around policy instruments"


def _screen_messages_text() -> str:
    messages = build_screen_messages(
        ScreenEnvelopePayload(
            tss_id="tss-1",
            title="A report",
            abstract="An abstract.",
            abstract_source=None,
            intent=_INTENT,
        )
    )
    return " ".join(str(message["content"]) for message in messages)


def _search_queries_text(guidance: list[str] | None = None) -> str:
    messages = build_queries_messages(QueriesPayload(intent=_INTENT, guidance=guidance))
    return " ".join(str(message["content"]) for message in messages)


def _group_discovery_system_text() -> str:
    # The base discovery system template, unguidanced — group's guidance
    # splice happens only in build_discovery_messages, never here.
    return _DISCOVERY_SYSTEM_TEMPLATE.format(
        subject=_PROJECTION_SUBJECT["value"],
        unit_intro=_PROJECTION_UNIT_INTRO["value"].format(facet="intervention"),
        label_max=80,
        description_max=500,
    )


def _group_discovery_messages_text(guidance: list[str] | None) -> str:
    unit = ClusterUnit(
        unit_id="v1", payload={"id": "v1", "text": "Housing First", "value": "Housing First"}
    )
    messages = build_discovery_messages(
        [unit],
        facet="intervention",
        projection="value",
        max_labels=5,
        include_context=False,
        guidance=guidance,
    )
    return " ".join(str(message["content"]) for message in messages)


# --- B1 search.guidance: reaches only the search-queries prompt ---


def test_b1_guidance_reaches_only_search_prompt() -> None:
    search_text = _search_queries_text(guidance=[_B1_GUIDANCE_TEXT])
    assert _B1_GUIDANCE_TEXT in search_text

    assert _B1_GUIDANCE_TEXT not in _screen_messages_text()
    assert _B1_GUIDANCE_TEXT not in DISCOVERY_SYSTEM_PROMPT
    assert _B1_GUIDANCE_TEXT not in _group_discovery_system_text()


# --- B3 grouping.guidance: reaches only the group discovery prompt ---


def test_b3_guidance_reaches_only_group_discovery_prompt() -> None:
    group_text = _group_discovery_messages_text(guidance=[_B3_GUIDANCE_TEXT])
    assert _B3_GUIDANCE_TEXT in group_text

    assert _B3_GUIDANCE_TEXT not in _screen_messages_text()
    assert _B3_GUIDANCE_TEXT not in _search_queries_text()
    assert _B3_GUIDANCE_TEXT not in DISCOVERY_SYSTEM_PROMPT


# --- B5 characterise.guidance: reaches only the theme discovery prompt ---


def test_b5_guidance_reaches_only_characterise_discovery_prompt() -> None:
    system, user = _discovery_messages_with_guidance(
        DISCOVERY_SYSTEM_PROMPT,
        "Intent: x\n\nTheme count bounds: produce between 1 and 5 themes.\n\nDocument records: []",
        [_B5_GUIDANCE_TEXT],
    )
    assert _B5_GUIDANCE_TEXT in system + user

    assert _B5_GUIDANCE_TEXT not in _screen_messages_text()
    assert _B5_GUIDANCE_TEXT not in _search_queries_text()
    assert _B5_GUIDANCE_TEXT not in _group_discovery_system_text()
