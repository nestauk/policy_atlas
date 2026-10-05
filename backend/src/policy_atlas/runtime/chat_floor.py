"""Deterministic citation validation and display compaction for chat answers."""

from __future__ import annotations

import json
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


def _strip_trailing_structured_blob(prose: str) -> str:
    """Drop a trailing citations/claims JSON dump from the answer prose.

    The schema-free prose stream can leak the structured payload as text
    (observed live, 2026-08-11). Only a TERMINAL JSON object that parses and
    carries the structured-answer keys is stripped — never JSON the answer
    legitimately quotes mid-prose.
    """
    brace = prose.rfind("\n{")
    starts_with_brace = prose.startswith("{")
    candidate_start = brace + 1 if brace >= 0 else (0 if starts_with_brace else -1)
    if candidate_start < 0:
        return prose
    candidate = prose[candidate_start:].strip()
    if not candidate.endswith("}"):
        return prose
    try:
        decoded = json.loads(candidate)
    except ValueError:
        return prose
    if isinstance(decoded, dict) and ("citations" in decoded or "claims" in decoded):
        return prose[:candidate_start].rstrip()
    return prose


def _marker_anchor_sentence(prose: str, position: int, marker_len: int) -> tuple[int, int]:
    """Return the sentence ``[start, end)`` a marker at ``position`` anchors.

    The sentence ENDING at the marker — models place markers on either side of
    the full stop, so a terminator immediately adjacent to the marker belongs
    to the marker's own sentence, not the one before it.
    """
    adjacent_stop = position > 0 and prose[position - 1] in ".!?"
    lookback = prose[: position - 1 if adjacent_stop else position]
    start = 0
    for match in _SENTENCE_END_RE.finditer(lookback):
        start = match.end()
    end = position + marker_len
    while end < len(prose) and prose[end] in ".!?":
        end += 1
    return start, end


def derive_claims_for_uncovered_citations(
    prose: str, citation_ns: list[int], claims: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Derive sentence-grain claims for marker occurrences no claim covers.

    Coverage is judged per ``[n]`` marker OCCURRENCE, not per citation number:
    a number cited twice can have one occurrence judged by an existing claim
    while the other is left honestly unjudged — collapsing both to the same
    verdict would show an unjudged assertion wearing a judged one's verdict.
    An occurrence is covered when some claim referencing its number has a span
    overlapping the occurrence's anchoring sentence; a claim with no usable
    span instead covers only the FIRST uncovered occurrence of its number
    (preserves the single-occurrence behaviour). Every occurrence still
    uncovered after that gets its own sentence-grain claim.

    Shared by the floor (persist time) and enrichment (which must also handle
    rows persisted before this derivation existed).
    """
    wanted = set(citation_ns)
    occurrences: dict[int, list[tuple[int, int, int]]] = {}
    for match in _MARKER_RE.finditer(prose):
        n = int(match.group(1))
        if n not in wanted:
            continue
        start, end = _marker_anchor_sentence(prose, match.start(), len(match.group(0)))
        occurrences.setdefault(n, []).append((match.start(), start, end))

    covered: set[tuple[int, int]] = set()  # (citation_n, marker_position)

    # Pass 1: a span-bearing claim covers every occurrence of its number whose
    # anchoring sentence overlaps the claim's span.
    for claim in claims:
        span = claim.get("span")
        if not (isinstance(span, list) and len(span) == 2):
            continue
        claim_start, claim_end = span
        for n in claim.get("citation_ns") or []:
            for position, sentence_start, sentence_end in occurrences.get(n, []):
                if sentence_start < claim_end and sentence_end > claim_start:
                    covered.add((n, position))

    # Pass 2: a claim with no usable span covers only the first occurrence of
    # its number that pass 1 left uncovered.
    for claim in claims:
        span = claim.get("span")
        if isinstance(span, list) and len(span) == 2:
            continue
        for n in claim.get("citation_ns") or []:
            for position, _sentence_start, _sentence_end in occurrences.get(n, []):
                if (n, position) not in covered:
                    covered.add((n, position))
                    break

    derived: list[dict[str, Any]] = []
    for n in citation_ns:
        for position, start, end in occurrences.get(n, []):
            if (n, position) in covered:
                continue
            marker = f"[{n}]"
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
            covered.add((n, position))
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

    prose = _scrub_artifact_tokens(
        _strip_trailing_structured_blob(_MARKER_RE.sub(compact_marker, marker_checked_prose))
    )
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
