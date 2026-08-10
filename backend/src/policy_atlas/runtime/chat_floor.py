"""Deterministic citation validation and display compaction for chat answers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from policy_atlas.runtime.chat_prompt import ChatAnswerWire

_MARKER_RE = re.compile(r"\[(\d+)\]")


@dataclass(frozen=True)
class FlooredAnswer:
    """A chat answer after evidence membership and appraisal checks.

    Args:
        prose: Final prose with invalid citation markers removed.
        citations: Citable display references, compacted to their final numbers.
        claims: Claim records with final citation numbers and recomputed spans.
        warning_not_evidence_checked: Whether no citation survived the floor.
        stripped: Visible audit records for rejected citations.
        evidence_not_held: The backend's explicit corpus-absence signal.
    """

    prose: str
    citations: list[dict[str, Any]]
    claims: list[dict[str, Any]]
    warning_not_evidence_checked: bool
    stripped: list[dict[str, str]]
    evidence_not_held: bool


def apply_citation_floor(
    answer: ChatAnswerWire,
    *,
    tool_chunk_ids: set[str],
    tool_finding_ids: set[str],
    frame_chunk_ids: set[str],
    appraised_chunk_ids: set[str] | None = None,
) -> FlooredAnswer:
    """Keep only citations the chat turn actually read and may cite.

    Frame citations are appraised by construction. Tool-returned findings are
    citable evidence records; chunks additionally require their returned
    appraisal flag, represented here by ``appraised_chunk_ids``.

    Args:
        answer: Structured terminal answer before deterministic validation.
        tool_chunk_ids: Chunk ids returned by this turn's search tool calls.
        tool_finding_ids: Finding ids returned by this turn's finding calls.
        frame_chunk_ids: Appraised chunk ids carried in the assembled frame.
        appraised_chunk_ids: Appraised tool-returned chunk ids.

    Returns:
        The display-compacted, audit-preserving floored answer.
    """
    appraised = appraised_chunk_ids or set()
    raw_citations = list(answer.citations)
    survivors: dict[int, dict[str, Any]] = {}
    stripped: list[dict[str, str]] = []

    for raw_index, citation in enumerate(raw_citations, start=1):
        citation_id = citation.id
        if citation_id in frame_chunk_ids:
            survivors[raw_index] = {
                "id": citation_id,
                "kind": "chunk",
                "quote": citation.quote,
            }
        elif citation_id in tool_finding_ids:
            survivors[raw_index] = {
                "id": citation_id,
                "kind": "finding",
                "quote": citation.quote,
            }
        elif citation_id in tool_chunk_ids and citation_id in appraised:
            survivors[raw_index] = {
                "id": citation_id,
                "kind": "chunk",
                "quote": citation.quote,
            }
        elif citation_id in tool_chunk_ids:
            stripped.append({"id": citation_id, "reason": "unappraised_chunk"})
        else:
            stripped.append({"id": citation_id, "reason": "not_citable_this_turn"})

    claim_raw_indexes: set[int] = set()
    claims_with_raw_indexes: list[tuple[str, list[int]]] = []
    for claim in answer.claims:
        indexes: list[int] = []
        for raw_index in claim.citation_indexes:
            if raw_index in survivors:
                indexes.append(raw_index)
                claim_raw_indexes.add(raw_index)
        claims_with_raw_indexes.append((claim.text, indexes))

    marker_raw_indexes: list[int] = []

    def rewrite_marker(match: re.Match[str]) -> str:
        raw_index = int(match.group(1))
        if raw_index not in survivors:
            return ""
        marker_raw_indexes.append(raw_index)
        return match.group(0)

    marker_checked_prose = _MARKER_RE.sub(rewrite_marker, answer.prose)
    retained_raw_indexes: list[int] = []
    for raw_index in marker_raw_indexes:
        if raw_index not in retained_raw_indexes:
            retained_raw_indexes.append(raw_index)
    for raw_index in sorted(claim_raw_indexes):
        if raw_index not in retained_raw_indexes:
            retained_raw_indexes.append(raw_index)

    compacted_numbers = {
        raw_index: compacted_index
        for compacted_index, raw_index in enumerate(retained_raw_indexes, start=1)
    }

    def compact_marker(match: re.Match[str]) -> str:
        raw_index = int(match.group(1))
        compacted = compacted_numbers.get(raw_index)
        return f"[{compacted}]" if compacted is not None else ""

    prose = _MARKER_RE.sub(compact_marker, marker_checked_prose)
    citations = [
        {
            "n": compacted_numbers[raw_index],
            **survivors[raw_index],
            "state": "unchecked",
        }
        for raw_index in retained_raw_indexes
    ]
    claims: list[dict[str, Any]] = []
    for text, raw_indexes in claims_with_raw_indexes:
        start = prose.find(text)
        span = [start, start + len(text)] if start >= 0 else None
        claims.append(
            {
                "text": text,
                "span": span,
                "citation_ns": [compacted_numbers[index] for index in raw_indexes],
            }
        )

    return FlooredAnswer(
        prose=prose,
        citations=citations,
        claims=claims,
        warning_not_evidence_checked=not citations,
        stripped=stripped,
        evidence_not_held=answer.evidence_not_held,
    )
