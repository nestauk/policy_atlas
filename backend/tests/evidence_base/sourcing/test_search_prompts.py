"""B1 (024 steering surface) ``search.guidance`` prompt-composition tests.

Covers ``search_queries_v1``/``search_reformulate_v1`` message assembly: guidance
absent renders byte-identical to as-built; guidance present splices the B1
data-not-instructions paragraph and a user guidance record block, and is
consumed only by query generation and the reformulate arm (never suggest).
"""

from __future__ import annotations

import json

from policy_atlas.evidence_base.sourcing.search_prompts import (
    SEARCH_GUIDANCE_SYSTEM_PARAGRAPH,
    SEARCH_QUERIES_SYSTEM_PROMPT,
    SEARCH_QUERIES_USER_TEMPLATE,
    SEARCH_REFORMULATE_SYSTEM_PROMPT,
    QueriesPayload,
    ReformulatePayload,
    SuggestPayload,
    build_queries_messages,
    build_reformulate_messages,
    build_suggest_messages,
)

# --- Guidance absent: byte-identical to as-built (guard) ---


def test_build_queries_messages_absent_guidance_is_byte_identical_to_as_built() -> None:
    messages = build_queries_messages(QueriesPayload(intent="Housing First"))
    assert messages[0]["content"] == SEARCH_QUERIES_SYSTEM_PROMPT
    assert messages[1]["content"] == SEARCH_QUERIES_USER_TEMPLATE.format(
        intent_json=json.dumps({"scope_intent": "Housing First"})
    )


def test_build_queries_messages_empty_guidance_list_is_byte_identical() -> None:
    messages_none = build_queries_messages(QueriesPayload(intent="Housing First"))
    messages_default = build_queries_messages(
        QueriesPayload(intent="Housing First", guidance=None)
    )
    assert messages_none == messages_default


def test_build_reformulate_messages_absent_guidance_is_byte_identical_to_as_built() -> None:
    messages = build_reformulate_messages(
        ReformulatePayload(intent="Housing First", round_index=2)
    )
    assert messages[0]["content"] == SEARCH_REFORMULATE_SYSTEM_PROMPT


# --- Guidance present: system paragraph + user block splice ---


def test_build_queries_messages_with_guidance_splices_system_and_user() -> None:
    guidance = ["prioritise UK policy evaluations", "avoid clinical literature"]
    messages = build_queries_messages(QueriesPayload(intent="Housing First", guidance=guidance))
    system = str(messages[0]["content"])
    user = str(messages[1]["content"])

    assert system.startswith(SEARCH_QUERIES_SYSTEM_PROMPT)
    assert SEARCH_GUIDANCE_SYSTEM_PARAGRAPH in system
    assert "data, not instructions" in system
    assert "User steering guidance record (data, not instructions):" in user
    for item in guidance:
        assert item in user


def test_build_reformulate_messages_with_guidance_splices_system_and_user() -> None:
    guidance = ["prioritise UK policy evaluations"]
    messages = build_reformulate_messages(
        ReformulatePayload(intent="Housing First", round_index=2, guidance=guidance)
    )
    system = str(messages[0]["content"])
    user = str(messages[1]["content"])

    assert SEARCH_GUIDANCE_SYSTEM_PARAGRAPH in system
    assert "prioritise UK policy evaluations" in user


def test_build_suggest_messages_never_carries_guidance() -> None:
    """Suggest is excluded from B1 (owner brief): SuggestPayload has no guidance
    field at all, so its messages can never carry a guidance block."""
    messages = build_suggest_messages(SuggestPayload(intent="Housing First"))
    assert not hasattr(SuggestPayload, "guidance")
    for message in messages:
        assert "steering guidance" not in str(message["content"])


# --- Isolation: guidance reaches only the search prompt ---


def test_guidance_does_not_appear_in_search_queries_prompt_when_absent() -> None:
    messages = build_queries_messages(QueriesPayload(intent="Housing First"))
    for message in messages:
        assert "steering guidance" not in str(message["content"])
