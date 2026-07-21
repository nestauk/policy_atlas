"""Tests for the shared Family B guidance-splice helpers (024 steering
surface): ``guidance_user_block`` and ``splice_guidance`` hoist the
injection-guard trio that was previously duplicated near-byte-identically
across search_prompts.py, theme_grouping.py and group_clustering.py.
"""

from __future__ import annotations

import json

from policy_atlas.core.prompt_fields import (
    GUIDANCE_USER_HEADING,
    guidance_user_block,
    splice_guidance,
)
from policy_atlas.core.schema import DIRECTIVE_STRING_MAX


def test_guidance_user_block_serializes_sanitized_entries() -> None:
    block = guidance_user_block(["prioritise UK policy evaluations", "avoid clinical work"])
    assert block.startswith(f"{GUIDANCE_USER_HEADING}\n")
    payload = json.loads(block[len(GUIDANCE_USER_HEADING) + 1 :])
    assert payload == ["prioritise UK policy evaluations", "avoid clinical work"]


def test_guidance_user_block_truncates_overlong_entry_at_assembly() -> None:
    overlong = "x" * (DIRECTIVE_STRING_MAX + 50)
    block = guidance_user_block([overlong])
    payload = json.loads(block[len(GUIDANCE_USER_HEADING) + 1 :])
    assert payload == [overlong[:DIRECTIVE_STRING_MAX]]


def test_splice_guidance_absent_is_byte_identical() -> None:
    system, user = splice_guidance(
        "SYSTEM", "USER", None, guard_paragraph="GUARD PARAGRAPH"
    )
    assert (system, user) == ("SYSTEM", "USER")


def test_splice_guidance_empty_list_is_byte_identical() -> None:
    system, user = splice_guidance(
        "SYSTEM", "USER", [], guard_paragraph="GUARD PARAGRAPH"
    )
    assert (system, user) == ("SYSTEM", "USER")


def test_splice_guidance_present_appends_guard_and_user_block() -> None:
    system, user = splice_guidance(
        "SYSTEM", "USER", ["do the thing"], guard_paragraph="GUARD PARAGRAPH"
    )
    assert system == "SYSTEM\nGUARD PARAGRAPH"
    assert user == f"USER\n{guidance_user_block(['do the thing'])}"


def test_splice_guidance_uses_the_caller_supplied_guard_paragraph() -> None:
    """Different components pass different guard paragraphs; the shared
    helper must not hardcode any one of them."""
    system_a, _ = splice_guidance("S", "U", ["g"], guard_paragraph="PARAGRAPH A")
    system_b, _ = splice_guidance("S", "U", ["g"], guard_paragraph="PARAGRAPH B")
    assert "PARAGRAPH A" in system_a
    assert "PARAGRAPH B" in system_b
    assert "PARAGRAPH A" not in system_b
