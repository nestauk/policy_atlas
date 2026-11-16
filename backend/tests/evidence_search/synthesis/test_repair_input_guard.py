"""The repair input guard (task 056 N5).

A repair dependency chunk over the oversized threshold is cut to a window
around the cited quote through the same rule the ``search_chunks`` tool return
uses (``oversized_chunk_window``), carrying the same ``window_start`` /
``window_end`` marker; chunks at or under the threshold go whole.
"""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from policy_atlas.core.embeddings import UNIT_CHAR_BUDGET
from policy_atlas.evidence_search.synthesis.section_prompt import (
    SECTION_REPAIR_TEMPLATE,
    build_section_prefix,
    build_section_repair_messages,
)
from policy_atlas.evidence_search.synthesis.synthesis_tools import (
    OVERSIZED_CHUNK_WINDOW_MARGIN_CHARS,
    oversized_chunk_window,
    window_repair_dependency_chunks,
)

_QUOTE = "Rent controls reduced evictions by twelve percent over three years."
_SMALL = "A short chunk that stays whole. " * 10
# ≥ 12,000 characters, the quote in the middle.
_FILLER_A = "".join(f"Background sentence {i} about housing supply. " for i in range(150))
_FILLER_B = "".join(f"Later sentence {i} about tenancy law. " for i in range(170))
_LARGE = _FILLER_A + _QUOTE + " " + _FILLER_B
_WINDOW_BOUND = len(_QUOTE) + 2 * OVERSIZED_CHUNK_WINDOW_MARGIN_CHARS


def _record(quote_small: str, quote_large: str) -> dict[str, Any]:
    return {
        "claim_id": "s0c0",
        "claim": {
            "claim_type": "chunk",
            "text": "Rent controls cut evictions.",
            "citations": [
                {"chunk_record_id": "chunk-small", "quote": quote_small},
                {"chunk_record_id": "chunk-large", "quote": quote_large},
            ],
        },
        "failure_reason": "overstates",
        "replacement_span": None,
        "paragraph_context": None,
        "dependencies": {
            "chunks": {
                "chunk-small": {"chunk_record_id": "chunk-small", "content": _SMALL},
                "chunk-large": {"chunk_record_id": "chunk-large", "content": _LARGE},
            }
        },
    }


def _repair_payload(failing: list[dict[str, Any]]) -> dict[str, Any]:
    content = build_section_repair_messages({"intent": "x"}, failing=failing)[-1]["content"]
    prefix, _, _ = SECTION_REPAIR_TEMPLATE.partition("{repair_json}")
    payload: dict[str, Any] = json.loads(content[len(prefix) :].split("\n\nRewrite ONLY", 1)[0])
    return payload


def test_synthetic_payload_sizes() -> None:
    assert len(_SMALL) <= UNIT_CHAR_BUDGET
    assert len(_LARGE) >= 12_000
    assert abs(_LARGE.index(_QUOTE) - len(_LARGE) / 2) < len(_LARGE) / 4


def test_large_chunk_windowed_around_quote_small_chunk_whole() -> None:
    failing = [_record("stays whole", _QUOTE)]
    before = copy.deepcopy(failing)
    payload = _repair_payload(failing)
    chunks = payload["failing_claims"][0]["dependencies"]["chunks"]

    small = chunks["chunk-small"]
    assert small["content"] == _SMALL
    assert "window_start" not in small and "window_end" not in small

    large = chunks["chunk-large"]
    assert _QUOTE in large["content"]
    assert len(large["content"]) <= _WINDOW_BOUND
    quote_at = _LARGE.index(_QUOTE)
    assert large["window_start"] == quote_at - OVERSIZED_CHUNK_WINDOW_MARGIN_CHARS
    assert large["window_end"] == quote_at + len(_QUOTE) + OVERSIZED_CHUNK_WINDOW_MARGIN_CHARS
    assert large["content"] == _LARGE[large["window_start"] : large["window_end"]]
    # Same rule, same bounds as the tool-return helper.
    assert (large["window_start"], large["window_end"]) == oversized_chunk_window(
        len(_LARGE), quote_at, quote_at + len(_QUOTE)
    )
    # The caller's records are untouched.
    assert failing == before


def test_quote_not_found_windows_around_longest_matching_stretch() -> None:
    # The model's quote drifted: the opening words are not in the chunk, but
    # its longest stretch ("s reduced evictions by twelve percent over three
    # years.", the "s " shared by "caps " and "controls ") is.
    drifted = "Strict caps " + _QUOTE[len("Rent controls ") :]
    chunks = window_repair_dependency_chunks([_record("stays whole", drifted)])[0][
        "dependencies"
    ]["chunks"]
    large = chunks["chunk-large"]
    stretch = "s " + _QUOTE[len("Rent controls ") :]
    stretch_at = _LARGE.index(stretch)
    assert stretch in large["content"]
    assert large["window_start"] == stretch_at - OVERSIZED_CHUNK_WINDOW_MARGIN_CHARS
    assert large["window_end"] == stretch_at + len(stretch) + OVERSIZED_CHUNK_WINDOW_MARGIN_CHARS


def test_quote_matched_under_verification_normalisation() -> None:
    # Case and whitespace differences match the way verification matches.
    loose = "RENT controls   reduced evictions\nby twelve percent over three years."
    large = window_repair_dependency_chunks([_record("x", loose)])[0]["dependencies"][
        "chunks"
    ]["chunk-large"]
    assert large["window_start"] == _LARGE.index(_QUOTE) - OVERSIZED_CHUNK_WINDOW_MARGIN_CHARS


def test_finding_claim_anchor_chunk_windowed_on_grounding_quote() -> None:
    record = {
        "claim_id": "s0c1",
        "claim": {"claim_type": "finding", "text": "Evictions fell.", "cited_finding_ids": ["f1"]},
        "dependencies": {
            "findings": {"f1": {"finding_id": "f1", "grounding": [{"quote": _QUOTE}]}},
            "chunks": {"chunk-large": {"chunk_record_id": "chunk-large", "content": _LARGE}},
        },
    }
    large = window_repair_dependency_chunks([record])[0]["dependencies"]["chunks"]["chunk-large"]
    assert _QUOTE in large["content"]
    assert len(large["content"]) <= _WINDOW_BOUND


def test_already_windowed_and_unanchored_chunks_sent_unchanged() -> None:
    tool_window = {
        "chunk_record_id": "chunk-large",
        "content": _LARGE[:2500],
        "window_start": 0,
        "window_end": 2500,
    }
    record = _record("x", _QUOTE)
    record["dependencies"]["chunks"]["chunk-large"] = tool_window
    out = window_repair_dependency_chunks([record])[0]["dependencies"]["chunks"]
    assert out["chunk-large"] == tool_window

    unanchored = {
        "claim_id": "s0c2",
        "claim": {"claim_type": "chunk", "text": "t", "citations": []},
        "dependencies": {"chunks": {"c": {"chunk_record_id": "c", "content": _LARGE}}},
    }
    assert window_repair_dependency_chunks([unanchored])[0] == unanchored


def test_records_without_chunk_dependencies_pass_through() -> None:
    records: list[dict[str, Any]] = [{"claim_id": "c1", "dependencies": {}}, {"claim_id": "c2"}]
    assert window_repair_dependency_chunks(records) == records


def test_window_helper_rejects_anchor_outside_oversized_chunk() -> None:
    assert oversized_chunk_window(UNIT_CHAR_BUDGET, 0, 10) is None
    with pytest.raises(ValueError, match="offsets are required"):
        oversized_chunk_window(UNIT_CHAR_BUDGET + 1, 5, UNIT_CHAR_BUDGET + 2)


def test_repair_prefix_unchanged_by_guard() -> None:
    seed = {"intent": "x"}
    messages = build_section_repair_messages(seed, failing=[_record("x", _QUOTE)])
    assert messages[:-1] == build_section_prefix(seed)


def test_synthetic_payload_chars_before_and_after() -> None:
    failing = [_record("stays whole", _QUOTE)]
    before = len(
        SECTION_REPAIR_TEMPLATE.format(
            repair_json=json.dumps(
                {"failing_claims": failing}, ensure_ascii=False, sort_keys=True
            )
        )
    )
    after = len(build_section_repair_messages({"intent": "x"}, failing=failing)[-1]["content"])
    print(f"repair message chars before={before} after={after}")
    # Deterministic figures for verification.md (task 056 Phase 4).
    assert (before, after) == (EXPECTED_BEFORE, EXPECTED_AFTER)


EXPECTED_BEFORE = 15_551
EXPECTED_AFTER = 3_052
