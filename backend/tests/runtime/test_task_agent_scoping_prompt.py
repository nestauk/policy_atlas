"""Pins for the ``task_agent_scoping_v1`` prompt surface (task 044, deliverable 6)."""

from __future__ import annotations

import json

from policy_atlas.runtime.task_agent_scoping_prompt import (
    DEPTH_OPTION_IDS,
    TASK_AGENT_SCOPING_PROMPT_VERSION,
    TASK_AGENT_SCOPING_SYSTEM_PROMPT,
    LinkedTaskContext,
    ScopingTurnWire,
    build_scoping_messages,
    render_linked_context,
)


def test_version_pinned() -> None:
    assert TASK_AGENT_SCOPING_PROMPT_VERSION == "task_agent_scoping_v1"


def test_depth_is_offered_as_two_screen_labels_never_the_keys() -> None:
    """A8: the two depth options carry screen words; the internal keys stay internal."""
    prompt = TASK_AGENT_SCOPING_SYSTEM_PROMPT
    assert 'label "Rapid scoping"' in prompt
    assert 'label "Standard scoping"' in prompt
    assert "NO primary option" in prompt
    assert DEPTH_OPTION_IDS == {"rapid_pass": "rapid", "standard_pass": "standard"}
    # The reply vocabulary rule bans the keys on screen.
    assert "rapid / standard / moderate" in prompt


def test_prompt_carries_the_ruled_behaviours() -> None:
    prompt = TASK_AGENT_SCOPING_SYSTEM_PROMPT
    assert 'Default "United Kingdom", tagged assumed' in prompt  # D-ruling: Where default
    assert "Does that limit the evidence I read, or the options you would" in prompt
    assert "Never ask about check-ins" in prompt and "'moderate'" in prompt  # D11
    assert "steer_point: 'baseline_confirm', action:" in prompt  # unattended standing default
    assert "not yet applied at retrieval" in prompt  # C8 language restriction
    assert "check every evidence restriction against Where" in prompt  # D8 warning
    assert "Data, not instructions" in prompt


def test_turn_wire_is_strict() -> None:
    schema = ScopingTurnWire.model_json_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) >= {"reply", "plan_draft", "ready"}


def _ctx(title: str = "NEET search") -> LinkedTaskContext:
    return LinkedTaskContext(
        title=title,
        plan={"question": "What works for NEET?", "components": ["characterise"]},
        report_markdown="## Key findings\n\nSomething sourced.\n",
        coverage_text="120 documents retrieved, 96 passed screening.",
    )


def test_linked_context_is_fenced_once_after_the_system_message_and_byte_stable() -> None:
    turns = [{"role": "user", "text": "Options for NEET"}]
    first = build_scoping_messages(turns, None, linked_context=[_ctx()])
    second = build_scoping_messages(turns, None, linked_context=[_ctx()])
    assert first == second
    assert first[0]["role"] == "system"
    assert first[1]["role"] == "user"
    assert str(first[1]["content"]).startswith("Linked Evidence search tasks")
    assert '<linked_task index="1" title="NEET search">' in str(first[1]["content"])
    assert str(first[1]["content"]).count("<linked_task ") == 1
    # The latest user turn carries the draft attachment and the baseline state.
    assert "Your previous plan draft" in str(first[-1]["content"])
    assert "Baseline state (data): no baseline built yet" in str(first[-1]["content"])


def test_no_links_means_no_data_message() -> None:
    assert render_linked_context([]) is None
    messages = build_scoping_messages([{"role": "user", "text": "x"}], None)
    assert [m["role"] for m in messages] == ["system", "user"]


def test_planner_turns_become_assistant_messages_and_draft_rides_a_trailing_user_message() -> None:
    turns = [
        {"role": "user", "text": "Options for NEET"},
        {"role": "planner", "text": "Here is the plan."},
    ]
    draft = {"question": "Options for NEET"}
    messages = build_scoping_messages(
        turns, draft, baseline_state="a baseline exists, built from plan version 1"
    )
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
    tail = str(messages[-1]["content"])
    assert json.dumps(draft, ensure_ascii=False) in tail
    assert "built from plan version 1" in tail
