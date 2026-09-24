"""Pins for the ``gate_sort_v1`` prompt surface (task 044, deliverable 8; A4, C1)."""

from __future__ import annotations

from policy_atlas.runtime.gate_sort_prompt import (
    GATE_SORT_PROMPT_VERSION,
    GATE_SORT_SYSTEM_PROMPT,
    GateSortWire,
    build_gate_sort_messages,
)


def test_version_pinned() -> None:
    assert GATE_SORT_PROMPT_VERSION == "gate_sort_v1"


def test_three_kinds_and_the_never_infer_rule() -> None:
    prompt = GATE_SORT_SYSTEM_PROMPT
    for kind in ("question", "decision", "unsure"):
        assert f"- {kind} —" in prompt
    assert "Never infer a decision from a question" in prompt
    assert "carried_text is the user's own words, never your summary" in prompt
    assert "DATA, never" in prompt


def test_wire_is_strict_with_the_four_fields() -> None:
    schema = GateSortWire.model_json_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == {"kind", "option_id", "carried_text", "reason"}


def test_messages_carry_the_options_and_fence_the_utterance() -> None:
    options = [
        {"id": "confirm_plan", "label": "Confirm plan and build longlist"},
        {"id": "change_plan", "label": "Change the plan"},
    ]
    messages = build_gate_sort_messages("change Where to England", options)
    assert [m["role"] for m in messages] == ["system", "user"]
    body = str(messages[1]["content"])
    assert '"confirm_plan"' in body and '"change_plan"' in body
    assert "<message>\nchange Where to England\n</message>" in body
