"""Deterministic quote verification and field validation (task 011, decision 4).

Pure functions only — no I/O, no DB. Three responsibilities:

* ``qv_v1`` quote verification — normalise a candidate quote and the document's
  frozen basis text the same way, match on a normalised copy that carries an
  index map back to *raw* offsets, and record chunk-local raw intervals with a
  graded status (``exact`` | ``normalised`` | ``failed``). The offset substrate
  is never normalised (the LangExtract NFC lesson): recorded intervals are
  always raw, half-open ``[start, end)``.
* ``iof_rules_v1`` field validation — null-like coercion, numeric parsing,
  bounds/consistency checks, estimate-level coherence and field coverage, then
  the grain gate that builds the stored :class:`IOFRecord`.
* Stratum canonicalisation and claim-keyed within-document dedup.

Closed enums are exempt from coercion by construction (``no_effect`` is a value,
not an absence); a violating field is flagged, never a reason to reject the
finding.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from policy_atlas.extraction_records import (
    IOFAnchor,
    IOFRecord,
    IOFRecordWire,
    IOFStatistics,
    IOFStratum,
    IOFStratumWire,
)

QUOTE_VERIFIER_VERSION = "qv_v1"
FIELD_RULES_VERSION = "iof_rules_v1"

# Strings that mean "the source does not report this", matched case-insensitively
# on the stripped value. Closed enums are exempt by construction.
NULL_LIKE_STRINGS = frozenset({"null", "none", "n/a", "na", "unknown", ""})

# Punctuation/space folds applied to both sides of a quote match. Each maps one
# raw character to one folded character (soft hyphens are deleted separately).
_SOFT_HYPHEN = "­"
_FOLD_MAP = {
    "“": '"',  # left double quotation mark
    "”": '"',  # right double quotation mark
    "‘": "'",  # left single quotation mark
    "’": "'",  # right single quotation mark
    "–": "-",  # en dash
    "—": "-",  # em dash
    " ": " ",  # no-break space
}

# The statistics numeric fields, in canonical order (the "all 9").
_FLOAT_FIELDS = (
    "effect_size",
    "ci_lower",
    "ci_upper",
    "standard_error",
    "p_value",
    "i_squared",
    "tau2",
)
_INT_FIELDS = ("n", "k")
_NUMERIC_STAT_FIELDS = (
    "effect_size",
    "ci_lower",
    "ci_upper",
    "standard_error",
    "p_value",
    "n",
    "k",
    "i_squared",
    "tau2",
)
# Statistics that belong to a pooled estimate only.
_POOLED_ONLY_FIELDS = ("k", "i_squared", "tau2")

# Nullable fields whose absence is completed to "not_extracted" in step 5.
_OTHER_NULLABLE_FIELDS = (
    "population",
    "comparator",
    "estimate_level",
    "study_design",
    "causality_by_design",
    "is_primary",
    "is_prevalence_only",
    "effect_size_type",
)


# --- qv_v1 quote verification ---------------------------------------------


def _build_norm(raw_text: str) -> tuple[str, list[int], list[int]]:
    """Normalise ``raw_text`` and record each normalised char's raw span.

    The normalised copy is built character by character so that one normalised
    char can map back to a run of raw chars (whitespace collapse) or to a raw
    span containing deleted chars (soft hyphens). ``casefold`` may expand a
    single raw char into several normalised chars; each carries the same raw
    span. The raw offset substrate is never mutated.

    Args:
        raw_text: The frozen basis (or quote) text.

    Returns:
        A ``(normalised, raw_start, raw_end)`` triple. ``raw_start[i]`` /
        ``raw_end[i]`` are the raw offsets the i-th normalised char consumed;
        the raw interval of a normalised match ``[i, j)`` is
        ``[raw_start[i], raw_end[j - 1])``.
    """
    norm: list[str] = []
    raw_start: list[int] = []
    raw_end: list[int] = []
    prev_space = False
    for idx, ch in enumerate(raw_text):
        if ch == _SOFT_HYPHEN:
            continue
        folded = _FOLD_MAP.get(ch, ch)
        if folded.isspace():
            if prev_space:
                # Extend the current normalised space over the whitespace run so
                # a match ending on the space covers the whole raw run.
                raw_end[-1] = idx + 1
                continue
            norm.append(" ")
            raw_start.append(idx)
            raw_end.append(idx + 1)
            prev_space = True
            continue
        prev_space = False
        for folded_char in folded.casefold():
            norm.append(folded_char)
            raw_start.append(idx)
            raw_end.append(idx + 1)
    return "".join(norm), raw_start, raw_end


def _normalise(text: str) -> str:
    """Return the qv_v1 normalised form of ``text`` (no offset map)."""
    return _build_norm(text)[0]


@dataclass(frozen=True)
class AnchorSpan:
    """A chunk-local raw half-open interval an anchor quote grounds to.

    Attributes:
        chunk_id: The touched chunk's id, or ``None`` for an envelope-abstract
            basis segment.
        start: Chunk-local raw start offset (inclusive).
        end: Chunk-local raw end offset (exclusive).
    """

    chunk_id: str | None
    start: int
    end: int


@dataclass(frozen=True)
class QuoteMatch:
    """The graded result of verifying one quote against a basis.

    Attributes:
        status: ``"exact"`` (the raw slice equals the quote verbatim),
            ``"normalised"`` (matched only after normalisation), or
            ``"failed"`` (no occurrence, or an empty normalised quote).
        spans: One :class:`AnchorSpan` per chunk the match touches (a
            boundary-spanning quote yields two or more); empty when failed.
    """

    status: Literal["exact", "normalised", "failed"]
    spans: tuple[AnchorSpan, ...]


@dataclass(frozen=True)
class BasisText:
    """A document's basis text plus its normalised copy and offset tables.

    Built once per document and reused across every quote. ``raw_text`` is the
    offset substrate; ``segments`` is the boundary table mapping doc offsets to
    ``(chunk_id, doc_start, doc_end)`` spans (the synthetic ``"\\n"`` separators
    between segments belong to no chunk).

    Attributes:
        raw_text: The concatenated raw basis text.
        normalised: The qv_v1 normalised copy of ``raw_text``.
        raw_start: Per normalised-char raw start offsets.
        raw_end: Per normalised-char raw end offsets (just past consumed raw).
        segments: Ordered ``(chunk_id, doc_start, doc_end)`` spans.
    """

    raw_text: str
    normalised: str
    raw_start: list[int]
    raw_end: list[int]
    segments: list[tuple[str | None, int, int]]

    def split_interval(self, start: int, end: int) -> tuple[AnchorSpan, ...]:
        """Split a raw doc interval into chunk-local spans.

        Args:
            start: Raw doc-level start offset (inclusive).
            end: Raw doc-level end offset (exclusive).

        Returns:
            One :class:`AnchorSpan` per chunk the interval overlaps, in doc
            order; synthetic separator positions produce no span.
        """
        spans: list[AnchorSpan] = []
        for chunk_id, seg_start, seg_end in self.segments:
            lo = max(start, seg_start)
            hi = min(end, seg_end)
            if lo < hi:
                spans.append(AnchorSpan(chunk_id, lo - seg_start, hi - seg_start))
        return tuple(spans)


def build_basis(segments: Sequence[tuple[str | None, str]]) -> BasisText:
    """Assemble a :class:`BasisText` from ordered ``(chunk_id, content)`` pairs.

    Segment raw contents are concatenated with a single ``"\\n"`` separator
    between them; a ``chunk_id`` of ``None`` marks the envelope-abstract basis
    (a single segment). The separators are synthetic and belong to no chunk, so
    they never appear in a recorded span.

    Args:
        segments: Ordered ``(chunk_id, raw_content)`` pairs.

    Returns:
        The precomputed basis: raw text, normalised copy, offset map and the
        chunk-boundary table.
    """
    parts: list[str] = []
    seg_spans: list[tuple[str | None, int, int]] = []
    pos = 0
    for index, (chunk_id, content) in enumerate(segments):
        if index > 0:
            parts.append("\n")
            pos += 1
        seg_start = pos
        parts.append(content)
        pos += len(content)
        seg_spans.append((chunk_id, seg_start, pos))
    raw_text = "".join(parts)
    normalised, raw_start, raw_end = _build_norm(raw_text)
    return BasisText(
        raw_text=raw_text,
        normalised=normalised,
        raw_start=raw_start,
        raw_end=raw_end,
        segments=seg_spans,
    )


class QuoteMatcher:
    """Verifies quotes against one :class:`BasisText` with an ordered cursor.

    The n-th call to :meth:`find` with the same normalised quote returns the
    n-th occurrence; calls beyond the last occurrence repeat the last one rather
    than failing. Cursor and occurrence state live on the instance.

    Args:
        basis: The document basis to match against.
    """

    def __init__(self, basis: BasisText) -> None:
        self._basis = basis
        self._occ_cache: dict[str, list[int]] = {}
        self._cursor: dict[str, int] = {}

    def _occurrences(self, normalised_quote: str) -> list[int]:
        cached = self._occ_cache.get(normalised_quote)
        if cached is not None:
            return cached
        positions: list[int] = []
        haystack = self._basis.normalised
        step = len(normalised_quote)
        i = 0
        while True:
            j = haystack.find(normalised_quote, i)
            if j == -1:
                break
            positions.append(j)
            i = j + step  # non-overlapping, left to right
        self._occ_cache[normalised_quote] = positions
        return positions

    def find(self, quote: str) -> QuoteMatch:
        """Verify one quote and record its chunk-local spans.

        Args:
            quote: The candidate anchor quote, raw as emitted.

        Returns:
            A :class:`QuoteMatch`. An empty normalised quote or a quote with no
            occurrence returns status ``"failed"`` with empty spans.
        """
        normalised_quote = _normalise(quote)
        if not normalised_quote:
            return QuoteMatch(status="failed", spans=())
        positions = self._occurrences(normalised_quote)
        if not positions:
            return QuoteMatch(status="failed", spans=())

        call_index = self._cursor.get(normalised_quote, 0)
        self._cursor[normalised_quote] = call_index + 1
        chosen = positions[min(call_index, len(positions) - 1)]

        raw_s = self._basis.raw_start[chosen]
        raw_e = self._basis.raw_end[chosen + len(normalised_quote) - 1]
        spans = self._basis.split_interval(raw_s, raw_e)
        if self._basis.raw_text[raw_s:raw_e] == quote:
            return QuoteMatch(status="exact", spans=spans)
        return QuoteMatch(status="normalised", spans=spans)


# --- iof_rules_v1 field validation ----------------------------------------


@dataclass
class ValidatedRecord:
    """The outcome of validating one wire record.

    Attributes:
        record: The stored :class:`IOFRecord`, or ``None`` when the grain is
            invalid (the coverage and flag lists are still populated so the
            caller can count the malformed emission).
        field_coverage: Per-field coverage markers (``not_extracted`` |
            ``unclear`` | ``not_applicable``); present valid fields are absent.
        unclear_fields: Fields flagged ``unclear`` (unparseable, out of bounds,
            or incoherent for the estimate level).
        coerced_null_fields: Fields whose null-like value was coerced to None.
        grain_invalid: True if intervention/outcome are missing or the wire
            carried zero anchors.
    """

    record: IOFRecord | None
    field_coverage: dict[str, str]
    unclear_fields: list[str]
    coerced_null_fields: list[str]
    grain_invalid: bool


def _coerce_text(
    field_name: str,
    value: str | None,
    coverage: dict[str, str],
    coerced: list[str],
) -> str | None:
    """Coerce a null-like free-text value to real None with a coverage marker."""
    if value is None:
        return None
    if value.strip().casefold() in NULL_LIKE_STRINGS:
        coverage[field_name] = "not_extracted"
        coerced.append(field_name)
        return None
    return value


def _parse_numeric(
    field_name: str,
    raw_value: float | int | str | None,
    coverage: dict[str, str],
    unclear: list[str],
    coerced: list[str],
) -> float | int | None:
    """Parse one statistics numeric, flagging null-like and unparseable values."""
    if raw_value is None:
        return None
    if isinstance(raw_value, str):
        stripped = raw_value.strip()
        if stripped.casefold() in NULL_LIKE_STRINGS:
            coverage[field_name] = "not_extracted"
            coerced.append(field_name)
            return None
        try:
            numeric = float(stripped)
        except ValueError:
            coverage[field_name] = "unclear"
            unclear.append(field_name)
            return None
    elif isinstance(raw_value, bool):
        # bool is a subclass of int; it is a valid value for no numeric field
        # the spec pins as invalid for n/k, and meaningless elsewhere.
        if field_name in _INT_FIELDS:
            coverage[field_name] = "unclear"
            unclear.append(field_name)
            return None
        numeric = float(raw_value)
    else:
        numeric = float(raw_value)

    if field_name in _INT_FIELDS:
        if numeric.is_integer():
            return int(numeric)
        coverage[field_name] = "unclear"
        unclear.append(field_name)
        return None
    return numeric


def _void_unclear(
    field_name: str,
    stats: dict[str, float | int | None],
    coverage: dict[str, str],
    unclear: list[str],
) -> None:
    """Void one field's value, flagging it ``unclear``."""
    stats[field_name] = None
    coverage[field_name] = "unclear"
    unclear.append(field_name)


def _apply_bounds(
    stats: dict[str, float | int | None],
    coverage: dict[str, str],
    unclear: list[str],
) -> None:
    """Void out-of-bounds numerics, flagging each ``unclear``."""

    def fail(field_name: str) -> None:
        _void_unclear(field_name, stats, coverage, unclear)

    p_value = stats["p_value"]
    if p_value is not None and not 0.0 <= p_value <= 1.0:
        fail("p_value")
    ci_lower, ci_upper = stats["ci_lower"], stats["ci_upper"]
    if ci_lower is not None and ci_upper is not None and ci_lower > ci_upper:
        fail("ci_lower")
        fail("ci_upper")
    n = stats["n"]
    if n is not None and n < 1:
        fail("n")
    k = stats["k"]
    if k is not None and k < 1:
        fail("k")
    i_squared = stats["i_squared"]
    if i_squared is not None and not 0.0 <= i_squared <= 100.0:
        fail("i_squared")
    tau2 = stats["tau2"]
    if tau2 is not None and tau2 < 0:
        fail("tau2")
    effect_size = stats["effect_size"]
    if effect_size is not None and not math.isfinite(effect_size):
        fail("effect_size")


# Fields incoherent with an estimate level: pooled-only stats on a study
# estimate; every numeric stat on a claim (a claim carries no estimate).
_INCOHERENT_FIELDS_BY_LEVEL: dict[str, tuple[str, ...]] = {
    "study": _POOLED_ONLY_FIELDS,
    "claim": _NUMERIC_STAT_FIELDS,
}


def _apply_estimate_coherence(
    estimate_level: str | None,
    stats: dict[str, float | int | None],
    coverage: dict[str, str],
    unclear: list[str],
) -> None:
    """Apply estimate-level coherence, voiding incoherent stats and marking N/A."""
    incoherent = _INCOHERENT_FIELDS_BY_LEVEL.get(estimate_level or "")
    if incoherent is None:
        # pooled / None: absent numerics fall through to "not_extracted" in step 5.
        return
    for field_name in incoherent:
        if stats[field_name] is not None:
            _void_unclear(field_name, stats, coverage, unclear)
        else:
            coverage[field_name] = "not_applicable"


def validate_record(wire: IOFRecordWire) -> ValidatedRecord:
    """Validate one wire record under ``iof_rules_v1``.

    Runs null-like coercion, numeric parsing, bounds/consistency checks,
    estimate-level coherence and coverage completion, then the grain gate that
    builds the stored :class:`IOFRecord`. A violating field is flagged and
    voided; the finding itself is only rejected when its grain is invalid.

    Args:
        wire: The tolerant wire record as parsed from the model response.

    Returns:
        A :class:`ValidatedRecord` carrying the stored record (or ``None`` when
        grain-invalid) plus coverage and flag lists for run counting.
    """
    coverage: dict[str, str] = {}
    unclear: list[str] = []
    coerced: list[str] = []

    # Step 1 — null-like coercion of nullable free-text fields.
    intervention = _coerce_text("intervention", wire.intervention, coverage, coerced)
    outcome = _coerce_text("outcome", wire.outcome, coverage, coerced)
    population = _coerce_text("population", wire.population, coverage, coerced)
    comparator = _coerce_text("comparator", wire.comparator, coverage, coerced)
    study_design = _coerce_text("study_design", wire.study_design, coverage, coerced)
    effect_size_type = _coerce_text(
        "effect_size_type", wire.statistics.effect_size_type, coverage, coerced
    )

    # Step 2 — numeric parsing.
    stats: dict[str, float | int | None] = {}
    for field_name in _NUMERIC_STAT_FIELDS:
        stats[field_name] = _parse_numeric(
            field_name,
            getattr(wire.statistics, field_name),
            coverage,
            unclear,
            coerced,
        )

    # Step 3 — bounds/consistency.
    _apply_bounds(stats, coverage, unclear)

    # Step 4 — estimate-level coherence + not_applicable markers.
    _apply_estimate_coherence(wire.estimate_level, stats, coverage, unclear)

    # Step 5 — coverage completion for remaining absent nullable fields.
    other_values: dict[str, object | None] = {
        "population": population,
        "comparator": comparator,
        "estimate_level": wire.estimate_level,
        "study_design": study_design,
        "causality_by_design": wire.causality_by_design,
        "is_primary": wire.is_primary,
        "is_prevalence_only": wire.is_prevalence_only,
        "effect_size_type": effect_size_type,
    }
    for field_name in _OTHER_NULLABLE_FIELDS:
        if other_values[field_name] is None and field_name not in coverage:
            coverage[field_name] = "not_extracted"
    for field_name in _NUMERIC_STAT_FIELDS:
        if stats[field_name] is None and field_name not in coverage:
            coverage[field_name] = "not_extracted"

    # Step 6 — grain validation.
    grain_invalid = False
    if intervention is None or not intervention.strip():
        grain_invalid = True
    if outcome is None or not outcome.strip():
        grain_invalid = True
    if len(wire.anchors) == 0:
        grain_invalid = True

    if grain_invalid:
        return ValidatedRecord(
            record=None,
            field_coverage=coverage,
            unclear_fields=unclear,
            coerced_null_fields=coerced,
            grain_invalid=True,
        )

    assert intervention is not None and outcome is not None  # narrowed by step 6
    statistics = IOFStatistics.model_validate(
        {
            "effect_size": stats["effect_size"],
            "effect_size_type": effect_size_type,
            "ci_lower": stats["ci_lower"],
            "ci_upper": stats["ci_upper"],
            "standard_error": stats["standard_error"],
            "p_value": stats["p_value"],
            "n": stats["n"],
            "k": stats["k"],
            "i_squared": stats["i_squared"],
            "tau2": stats["tau2"],
        }
    )
    record = IOFRecord(
        intervention=intervention.strip(),
        outcome=outcome.strip(),
        population=population,
        comparator=comparator,
        effect_direction=wire.effect_direction,
        estimate_level=wire.estimate_level,
        study_design=study_design,
        stratum_qualifiers=canonical_strata(wire.stratum_qualifiers),
        statistics=statistics,
        causality_by_design=wire.causality_by_design,
        is_primary=wire.is_primary,
        is_prevalence_only=wire.is_prevalence_only,
        anchors=[
            IOFAnchor(segment_id=anchor.segment_id, quote=anchor.quote)
            for anchor in wire.anchors
        ],
    )
    return ValidatedRecord(
        record=record,
        field_coverage=coverage,
        unclear_fields=unclear,
        coerced_null_fields=coerced,
        grain_invalid=False,
    )


# --- Stratum canonicalisation ---------------------------------------------


def canonical_strata(strata: list[IOFStratumWire]) -> list[IOFStratum]:
    """Canonicalise stratum qualifiers for storage and dedup.

    Each value is whitespace-normalised (runs collapsed, ends stripped); exact
    duplicate ``(type, value)`` pairs are dropped; the result is sorted by
    ``(type, value.casefold())``. This canonical array is both stored and used
    as the dedup comparison form.

    Args:
        strata: Wire stratum qualifiers as emitted.

    Returns:
        The sorted, de-duplicated list of :class:`IOFStratum`.
    """
    seen: set[tuple[str, str]] = set()
    result: list[IOFStratum] = []
    for stratum in strata:
        value = " ".join(stratum.value.split())
        key = (stratum.type, value)
        if key in seen:
            continue
        seen.add(key)
        result.append(IOFStratum(type=stratum.type, value=value))
    result.sort(key=lambda item: (item.type, item.value.casefold()))
    return result


# --- Claim-keyed dedup -----------------------------------------------------


def _canonical_text(text: str) -> str:
    """Whitespace-normalise and casefold a text component for keying."""
    return " ".join(text.split()).casefold()


def claim_key(record: IOFRecord) -> tuple[object, ...]:
    """Compute the claim-dimension dedup key for a stored record.

    Args:
        record: A stored :class:`IOFRecord`.

    Returns:
        A hashable tuple over the claim dimensions (intervention, outcome,
        effect direction, effect size + type, comparator, estimate level and the
        canonical stratum pairs), with text components casefolded and
        whitespace-normalised.
    """
    return (
        _canonical_text(record.intervention),
        _canonical_text(record.outcome),
        record.effect_direction,
        record.statistics.effect_size,
        _canonical_text(record.statistics.effect_size_type or ""),
        _canonical_text(record.comparator or ""),
        record.estimate_level or "",
        tuple(
            (stratum.type, stratum.value.casefold())
            for stratum in record.stratum_qualifiers
        ),
    )


def dedup_records(records: list[IOFRecord]) -> tuple[list[IOFRecord], int]:
    """Collapse claim-identical records, merging their anchors.

    The first occurrence of a claim key wins its position and field values;
    later records with the same key merge their anchors onto the survivor in
    emission order, skipping anchors already present with an identical
    ``(segment_id, quote)``.

    Args:
        records: Stored records in emission order.

    Returns:
        A ``(deduped, collapsed_count)`` tuple: the survivors in first-occurrence
        order and the number of records absorbed.
    """
    survivors: dict[tuple[object, ...], IOFRecord] = {}
    order: list[tuple[object, ...]] = []
    collapsed = 0
    for record in records:
        key = claim_key(record)
        survivor = survivors.get(key)
        if survivor is None:
            survivors[key] = record.model_copy(deep=True)
            order.append(key)
            continue
        collapsed += 1
        present = {(anchor.segment_id, anchor.quote) for anchor in survivor.anchors}
        for anchor in record.anchors:
            pair = (anchor.segment_id, anchor.quote)
            if pair not in present:
                survivor.anchors.append(anchor.model_copy(deep=True))
                present.add(pair)
    return [survivors[key] for key in order], collapsed
