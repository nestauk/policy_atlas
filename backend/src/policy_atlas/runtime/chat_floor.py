"""Deterministic citation validation and display compaction for chat answers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from policy_atlas.runtime.chat_prompt import ChatAnswerWire

_MARKER_RE = re.compile(r"\[(\d+)\]")
# Stray provider artifact tokens (e.g. a lone "<lemma>" paragraph) observed
# leaking from the chat model class; prose is plain text by pin, so a lone
# angle-bracket token is never legitimate content.
_ARTIFACT_TOKEN_RE = re.compile(r"^\s*<[a-z_]+>\s*$", re.MULTILINE)
_SENTENCE_END_RE = re.compile(r"[.!?](?=\s|$)")


def _scrub_artifact_tokens(prose: str) -> str:
    """Drop lone angle-bracket token lines and trailing token fragments."""
    cleaned = _ARTIFACT_TOKEN_RE.sub("", prose)
    cleaned = re.sub(r"\s*<[a-z_]+>\s*$", "", cleaned)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def _sentence_around(prose: str, position: int) -> tuple[int, int]:
    """Return the [start, end) sentence bounds containing ``position``."""
    start = 0
    for match in _SENTENCE_END_RE.finditer(prose, 0, position):
        start = match.end()
    end_match = _SENTENCE_END_RE.search(prose, position)
    end = end_match.end() if end_match is not None else len(prose)
    return start, end


def derive_claims_for_uncovered_citations(
    prose: str, citation_ns: list[int], claims: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Derive sentence-grain claims for citations no existing claim references.

    Shared by the floor (persist time) and enrichment (which must also handle
    rows persisted before this derivation existed): each uncovered display
    number gets the sentence its ``[n]`` marker anchors — the sentence ENDING
    at the marker (models place markers on either side of the full stop), so
    the claim text is the asserted sentence, never the following fragment.
    """
    covered = {n for claim in claims for n in claim.get("citation_ns") or []}
    derived: list[dict[str, Any]] = []
    for n in citation_ns:
        if n in covered:
            continue
        marker = f"[{n}]"
        position = prose.find(marker)
        if position < 0:
            continue
        # Sentence start: the last terminator BEFORE the sentence the marker
        # closes — skip a terminator immediately adjacent to the marker
        # ("…data.[1]"), which belongs to the marker's own sentence.
        lookback = prose[: position - 1 if position > 0 and prose[position - 1] in ".!?" else position]
        start = 0
        for match in _SENTENCE_END_RE.finditer(lookback):
            start = match.end()
        end = position + len(marker)
        while end < len(prose) and prose[end] in ".!?":
            end += 1
        text = prose[start:end].strip()
        if not text or text == marker:
            continue
        span_start = prose.find(text)
        derived.append(
            {
                "text": text,
                "span": [span_start, span_start + len(text)] if span_start >= 0 else None,
                "citation_ns": [n],
                "derived": True,
            }
        )
        covered.add(n)
    return derived


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

    prose = _scrub_artifact_tokens(_MARKER_RE.sub(compact_marker, marker_checked_prose))
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

    # The judge is claim-grained: a surviving citation no claim references
    # would be honestly uncheckable, so derive its claim from the sentence
    # carrying its marker (spans are bound code-side — house rule). Covers
    # the observed model failure of emitting citations with empty claims[].
    claims.extend(
        derive_claims_for_uncovered_citations(
            prose, [compacted_numbers[raw_index] for raw_index in retained_raw_indexes], claims
        )
    )

    return FlooredAnswer(
        prose=prose,
        citations=citations,
        claims=claims,
        warning_not_evidence_checked=not citations,
        stripped=stripped,
        evidence_not_held=answer.evidence_not_held,
    )
