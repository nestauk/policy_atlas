"""Pure unit tests for qv_v1 verification, iof_rules_v3 rules, and dedup.

No DB fixtures — every case exercises the pure functions directly.
"""

from __future__ import annotations

import pytest

from policy_atlas.evidence_base.extract.iof_records import (
    IOFAnchorWire,
    IOFRecord,
    IOFRecordWire,
    IOFStatisticsWire,
    IOFStratumWire,
)
from policy_atlas.evidence_base.extract.quote_verify import (
    FIELD_RULES_VERSION,
    NULL_LIKE_STRINGS,
    QUOTE_VERIFIER_VERSION,
    QuoteMatcher,
    build_basis,
    canonical_strata,
    claim_key,
    dedup_records,
    locate_unique_span,
    validate_record,
)


def _wire(
    *,
    intervention: str | None = "home visiting",
    outcome: str | None = "hospital admissions",
    population: str | None = None,
    setting: str | None = None,
    comparator: str | None = "usual care",
    effect_direction: str = "decrease",
    estimate_level: str | None = "pooled",
    study_design: str | None = None,
    study_geography: str | None = None,
    stratum_qualifiers: list[IOFStratumWire] | None = None,
    statistics: IOFStatisticsWire | None = None,
    causality_by_design: str | None = "attributable",
    effect_basis: str | None = None,
    is_primary: bool | None = True,
    is_prevalence_only: bool | None = False,
    anchors: list[IOFAnchorWire] | None = None,
) -> IOFRecordWire:
    """Build a wire record with sane defaults; override per test."""
    if statistics is None:
        statistics = IOFStatisticsWire(
            effect_size=None,
            effect_size_type=None,
            ci_lower=None,
            ci_upper=None,
            standard_error=None,
            p_value=None,
            n=None,
            k=None,
            i_squared=None,
            tau2=None,
        )
    if anchors is None:
        anchors = [IOFAnchorWire(segment_id="s1", quote="home visiting reduced admissions")]
    return IOFRecordWire(
        intervention=intervention,
        outcome=outcome,
        population=population,
        setting=setting,
        comparator=comparator,
        effect_direction=effect_direction,  # type: ignore[arg-type]
        estimate_level=estimate_level,  # type: ignore[arg-type]
        study_design=study_design,
        study_geography=study_geography,
        stratum_qualifiers=stratum_qualifiers or [],
        statistics=statistics,
        causality_by_design=causality_by_design,  # type: ignore[arg-type]
        effect_basis=effect_basis,  # type: ignore[arg-type]
        is_primary=is_primary,
        is_prevalence_only=is_prevalence_only,
        anchors=anchors,
    )


# --- version constants ----------------------------------------------------


def test_version_constants() -> None:
    assert QUOTE_VERIFIER_VERSION == "qv_v1"
    assert FIELD_RULES_VERSION == "iof_rules_v3"
    assert "" in NULL_LIKE_STRINGS


# --- qv_v1 quote verification ---------------------------------------------


def test_exact_verbatim_hit() -> None:
    basis = build_basis([("c1", "The intervention reduced admissions by half.")])
    matcher = QuoteMatcher(basis)
    quote = "reduced admissions"
    match = matcher.find(quote)
    assert match.status == "exact"
    assert len(match.spans) == 1
    span = match.spans[0]
    assert span.chunk_id == "c1"
    # Chunk-local raw slice is byte-identical to the quote.
    assert basis.raw_text[span.start : span.end] == quote


def test_normalised_hit_smart_quotes_dash_nbsp_soft_hyphen() -> None:
    # Curly quotes, em dash, NBSP and a soft hyphen in the raw text.
    raw = "She said “the pro­gramme—a trial” worked."
    basis = build_basis([("c1", raw)])
    matcher = QuoteMatcher(basis)
    quote = '"the programme-a trial" worked'
    match = matcher.find(quote)
    assert match.status == "normalised"
    assert len(match.spans) == 1
    span = match.spans[0]
    # The recorded raw slice normalises back to the matched quote.
    from policy_atlas.evidence_base.extract.quote_verify import _normalise

    raw_slice = basis.raw_text[span.start : span.end]
    assert _normalise(raw_slice) == _normalise(quote)


def test_boundary_spanning_quote_two_segments() -> None:
    basis = build_basis([("c1", "ends with word"), ("c2", "next begins here")])
    matcher = QuoteMatcher(basis)
    match = matcher.find("word next")
    assert match.status in ("exact", "normalised")
    assert len(match.spans) == 2
    first, second = match.spans
    assert first.chunk_id == "c1"
    assert second.chunk_id == "c2"
    # Chunk-local intervals recover the pieces on each side of the separator.
    assert "ends with word"[first.start : first.end] == "word"
    assert "next begins here"[second.start : second.end] == "next"


def test_repeated_identical_quote_uses_ordered_cursor() -> None:
    basis = build_basis([("c1", "alpha beta alpha beta alpha")])
    matcher = QuoteMatcher(basis)
    first = matcher.find("alpha")
    second = matcher.find("alpha")
    third = matcher.find("alpha")
    fourth = matcher.find("alpha")  # beyond last occurrence -> repeats last
    intervals = [
        (m.spans[0].start, m.spans[0].end) for m in (first, second, third, fourth)
    ]
    assert intervals[0] != intervals[1]
    assert intervals[1] != intervals[2]
    assert intervals[2] == intervals[3]  # cursor clamps to the last occurrence


def test_fabricated_quote_fails_empty_spans() -> None:
    basis = build_basis([("c1", "nothing to see here")])
    matcher = QuoteMatcher(basis)
    match = matcher.find("entirely invented sentence")
    assert match.status == "failed"
    assert match.spans == ()


def test_empty_quote_fails() -> None:
    basis = build_basis([("c1", "some text")])
    matcher = QuoteMatcher(basis)
    match = matcher.find("")
    assert match.status == "failed"
    assert match.spans == ()


def test_half_open_interval_semantics() -> None:
    basis = build_basis([("c1", "abcdef")])
    matcher = QuoteMatcher(basis)
    match = matcher.find("cd")
    span = match.spans[0]
    assert (span.start, span.end) == (2, 4)  # [2, 4) is exactly "cd"
    assert basis.raw_text[span.start : span.end] == "cd"


def test_abstract_basis_chunk_id_none() -> None:
    basis = build_basis([(None, "abstract only text here")])
    matcher = QuoteMatcher(basis)
    match = matcher.find("only text")
    assert match.status == "exact"
    assert match.spans[0].chunk_id is None


# --- locate_unique_span: canonical read-time locator (task 029 delta-review) ----


def test_locate_unique_span_exact_hit() -> None:
    basis = build_basis([("c1", "The intervention reduced admissions by half.")])
    span = locate_unique_span(basis, "reduced admissions")
    assert span is not None
    start, end = span
    assert basis.raw_text[start:end] == "reduced admissions"


def test_locate_unique_span_normalised_hit() -> None:
    raw = "She said “Clear   Evidence” worked."
    basis = build_basis([("c1", raw)])
    span = locate_unique_span(basis, '"clear evidence" worked')
    assert span is not None
    start, end = span
    assert basis.raw_text[start:end] == '“Clear   Evidence” worked'


def test_locate_unique_span_absent_quote_is_none() -> None:
    basis = build_basis([("c1", "nothing to see here")])
    assert locate_unique_span(basis, "entirely invented sentence") is None


def test_locate_unique_span_empty_quote_is_none() -> None:
    basis = build_basis([("c1", "some text")])
    assert locate_unique_span(basis, "") is None


def test_locate_unique_span_overlap_aware_occurrence_counting_is_ambiguous() -> None:
    """A step-1 scan finds OVERLAPPING occurrences a non-overlapping ``str.count``
    (or a stepped scan) would miss: "red blue red" occurs at both offset 0 and
    offset 9 of "red blue red blue red" (they overlap on the middle "red")."""
    basis = build_basis([("c1", "RED blue red blue RED")])
    assert basis.normalised.count("red blue red") == 1  # str.count under-counts
    assert locate_unique_span(basis, "red blue red") is None  # truly ambiguous


def test_locate_unique_span_word_boundary_rejects_embedded_match() -> None:
    """The sole substring occurrence of "cat" in "concatenate" is rejected: it
    is embedded in a longer word, not a standalone match."""
    basis = build_basis([("c1", "Words that concatenate strings are common.")])
    assert basis.normalised.count("cat") == 1  # unambiguous by count alone
    assert locate_unique_span(basis, "cat") is None


def test_locate_unique_span_word_boundary_accepts_standalone_match() -> None:
    basis = build_basis([("c1", "The cat sat on the mat.")])
    span = locate_unique_span(basis, "cat")
    assert span is not None
    start, end = span
    assert basis.raw_text[start:end] == "cat"


def test_locate_unique_span_ligature_partial_expansion_rejected() -> None:
    """"ff" must NOT match inside "oﬃce": the ﬃ ligature casefolds to the three
    normalised chars "ffi", so any match landing on part of that expansion is
    rejected — here via the word-boundary guard, since a partial-expansion
    match is necessarily embedded in the surrounding word."""
    basis = build_basis([("c1", "The oﬃce building.")])
    assert locate_unique_span(basis, "ff") is None


def test_locate_unique_span_full_ligature_expansion_matches() -> None:
    """The WHOLE ligature expansion, standing alone (not embedded in a longer
    word), is a legitimate, unambiguous match."""
    basis = build_basis([("c1", "ﬃ")])
    span = locate_unique_span(basis, "ffi")
    assert span is not None
    start, end = span
    assert basis.raw_text[start:end] == "ﬃ"


def test_locate_unique_span_composed_decomposed_nfc_pair_is_honest_absence() -> None:
    """qv_v1 does not perform Unicode NFC composition/decomposition — only
    casefold, punctuation/whitespace folding and soft-hyphen deletion
    (``_build_norm``). A composed accented char (NFC, single codepoint) and
    its decomposed form (base char + combining mark, two codepoints) are
    therefore different normalised strings and do not match each other, even
    though they render identically and a Unicode-NFC-aware matcher would
    consider them equal. This is a documented gap in the envelope, pinned
    here as an honest absence — not a bug (task 029 delta-review, Fix 1)."""
    composed = "café"  # "é" is U+00E9, one codepoint
    decomposed = "café"  # "e" + U+0301 COMBINING ACUTE ACCENT, two codepoints
    assert composed != decomposed  # confirms these are genuinely different strings
    basis = build_basis([("c1", f"The word is {composed} in the source.")])
    assert locate_unique_span(basis, decomposed) is None


# --- iof_rules_v1: null-like coercion + enum exemption ---------------------


def test_null_like_coercion_free_text() -> None:
    for token in ("null", "N/A", ""):
        wire = _wire(population=token)
        result = validate_record(wire)
        assert result.record is not None
        assert result.record.population is None
        assert result.field_coverage["population"] == "not_extracted"
        assert "population" in result.coerced_null_fields


def test_enum_exemption_no_effect_survives() -> None:
    wire = _wire(effect_direction="no_effect")
    result = validate_record(wire)
    assert result.record is not None
    assert result.record.effect_direction == "no_effect"
    assert "effect_direction" not in result.field_coverage
    assert "effect_direction" not in result.coerced_null_fields


# --- iof_rules_v1: bounds rules -------------------------------------------


def _stats(**kwargs: object) -> IOFStatisticsWire:
    base: dict[str, object] = {
        "effect_size": None,
        "effect_size_type": None,
        "ci_lower": None,
        "ci_upper": None,
        "standard_error": None,
        "p_value": None,
        "n": None,
        "k": None,
        "i_squared": None,
        "tau2": None,
    }
    base.update(kwargs)
    return IOFStatisticsWire.model_validate(base)


def test_bounds_p_value_out_of_range() -> None:
    result = validate_record(_wire(statistics=_stats(p_value=1.5)))
    assert result.record is not None
    assert result.record.statistics.p_value is None
    assert result.field_coverage["p_value"] == "unclear"
    assert "p_value" in result.unclear_fields


def test_bounds_inverted_ci_flags_both() -> None:
    result = validate_record(
        _wire(statistics=_stats(ci_lower=0.9, ci_upper=0.5))
    )
    assert result.record is not None
    assert result.record.statistics.ci_lower is None
    assert result.record.statistics.ci_upper is None
    assert result.field_coverage["ci_lower"] == "unclear"
    assert result.field_coverage["ci_upper"] == "unclear"


def test_bounds_n_zero_and_k_zero() -> None:
    result = validate_record(
        _wire(estimate_level="pooled", statistics=_stats(n=0, k=0))
    )
    assert result.record is not None
    assert result.record.statistics.n is None
    assert result.record.statistics.k is None
    assert result.field_coverage["n"] == "unclear"
    assert result.field_coverage["k"] == "unclear"


def test_bounds_i_squared_over_100_and_negative_tau2() -> None:
    result = validate_record(
        _wire(estimate_level="pooled", statistics=_stats(i_squared=250.0, tau2=-1.0))
    )
    assert result.record is not None
    assert result.record.statistics.i_squared is None
    assert result.record.statistics.tau2 is None
    assert result.field_coverage["i_squared"] == "unclear"
    assert result.field_coverage["tau2"] == "unclear"


def test_bounds_effect_size_nan() -> None:
    result = validate_record(_wire(statistics=_stats(effect_size="NaN")))
    assert result.record is not None
    assert result.record.statistics.effect_size is None
    assert result.field_coverage["effect_size"] == "unclear"


# --- iof_rules_v1: numeric parsing ----------------------------------------


def test_numeric_string_parsing() -> None:
    result = validate_record(_wire(statistics=_stats(p_value="0.03")))
    assert result.record is not None
    assert result.record.statistics.p_value == 0.03


def test_numeric_string_unparseable() -> None:
    result = validate_record(_wire(statistics=_stats(effect_size="twelve")))
    assert result.record is not None
    assert result.record.statistics.effect_size is None
    assert result.field_coverage["effect_size"] == "unclear"


def test_integer_field_accepts_integral_float_string() -> None:
    result = validate_record(
        _wire(estimate_level="pooled", statistics=_stats(n="12.0"))
    )
    assert result.record is not None
    assert result.record.statistics.n == 12


def test_integer_field_rejects_non_integral() -> None:
    result = validate_record(
        _wire(estimate_level="pooled", statistics=_stats(n="12.5"))
    )
    assert result.record is not None
    assert result.record.statistics.n is None
    assert result.field_coverage["n"] == "unclear"


# --- iof_rules_v1: estimate-level coherence -------------------------------


def test_study_with_k_present_is_unclear() -> None:
    result = validate_record(
        _wire(estimate_level="study", statistics=_stats(k=12))
    )
    assert result.record is not None
    assert result.record.statistics.k is None
    assert result.field_coverage["k"] == "unclear"


def test_study_with_k_absent_is_not_applicable() -> None:
    result = validate_record(_wire(estimate_level="study"))
    assert result.record is not None
    assert result.field_coverage["k"] == "not_applicable"
    assert result.field_coverage["i_squared"] == "not_applicable"
    assert result.field_coverage["tau2"] == "not_applicable"


def test_claim_with_effect_size_present_is_unclear() -> None:
    result = validate_record(
        _wire(estimate_level="claim", statistics=_stats(effect_size=0.8))
    )
    assert result.record is not None
    assert result.record.statistics.effect_size is None
    assert result.field_coverage["effect_size"] == "unclear"


def test_claim_with_absent_numerics_is_not_applicable() -> None:
    result = validate_record(_wire(estimate_level="claim"))
    assert result.record is not None
    assert result.field_coverage["n"] == "not_applicable"
    assert result.field_coverage["effect_size"] == "not_applicable"


def test_pooled_with_absent_k_is_not_extracted() -> None:
    result = validate_record(_wire(estimate_level="pooled"))
    assert result.record is not None
    assert result.field_coverage["k"] == "not_extracted"


# --- iof_rules_v1: grain invalidation -------------------------------------


def test_grain_invalid_null_intervention() -> None:
    result = validate_record(_wire(intervention="null"))
    assert result.grain_invalid is True
    assert result.record is None
    # Coverage is still populated for counting.
    assert result.field_coverage["intervention"] == "not_extracted"


def test_grain_invalid_zero_anchors() -> None:
    result = validate_record(_wire(anchors=[]))
    assert result.grain_invalid is True
    assert result.record is None
    # Field coverage still computed despite the ungroundable emission.
    assert "k" in result.field_coverage or "population" in result.field_coverage


# --- stratum canonicalisation ---------------------------------------------


def test_canonical_strata_order_whitespace_dupes() -> None:
    strata = [
        IOFStratumWire(type="subgroup", value="  girls  "),
        IOFStratumWire(type="timepoint", value="12   months"),
        IOFStratumWire(type="subgroup", value="girls"),  # dup after normalise
    ]
    result = canonical_strata(strata)
    # Sorted by (type, casefold(value)); "subgroup" precedes "timepoint".
    assert [(s.type, s.value) for s in result] == [
        ("subgroup", "girls"),
        ("timepoint", "12 months"),
    ]


# --- claim-keyed dedup ----------------------------------------------------


def _record(**kwargs: object) -> IOFRecord:
    wire = _wire(**kwargs)  # type: ignore[arg-type]
    result = validate_record(wire)
    assert result.record is not None
    return result.record


def test_dedup_merges_anchors_same_claim() -> None:
    r1 = _record(
        anchors=[IOFAnchorWire(segment_id="s1", quote="quote one")],
        statistics=_stats(effect_size=0.8),
    )
    r2 = _record(
        anchors=[IOFAnchorWire(segment_id="s2", quote="quote two")],
        statistics=_stats(effect_size=0.8),
    )
    deduped, collapsed = dedup_records([r1, r2])
    assert collapsed == 1
    assert len(deduped) == 1
    quotes = {a.quote for a in deduped[0].anchors}
    assert quotes == {"quote one", "quote two"}


def test_dedup_distinct_effect_size_splits() -> None:
    r1 = _record(statistics=_stats(effect_size=0.8))
    r2 = _record(statistics=_stats(effect_size=0.5))
    deduped, collapsed = dedup_records([r1, r2])
    assert collapsed == 0
    assert len(deduped) == 2


def test_dedup_skips_identical_anchor() -> None:
    r1 = _record(
        anchors=[IOFAnchorWire(segment_id="s1", quote="same quote")],
        statistics=_stats(effect_size=0.8),
    )
    r2 = _record(
        anchors=[IOFAnchorWire(segment_id="s1", quote="same quote")],
        statistics=_stats(effect_size=0.8),
    )
    deduped, collapsed = dedup_records([r1, r2])
    assert collapsed == 1
    assert len(deduped[0].anchors) == 1  # identical (segment_id, quote) skipped


def test_claim_key_stable_across_casefold_and_whitespace() -> None:
    r1 = _record(intervention="Home  Visiting", statistics=_stats(effect_size=0.8))
    r2 = _record(intervention="home visiting", statistics=_stats(effect_size=0.8))
    assert claim_key(r1) == claim_key(r2)


# --- iof_rules_v3: setting / study_geography / effect_basis coverage -------


@pytest.mark.parametrize(
    ("value", "expected_stored", "expect_coverage_key", "expect_coerced"),
    [
        ("primary care", "primary care", False, False),
        ("N/A", None, True, True),
        (None, None, True, False),
    ],
)
def test_setting_coverage_v3(
    value: str | None,
    expected_stored: str | None,
    expect_coverage_key: bool,
    expect_coerced: bool,
) -> None:
    result = validate_record(_wire(setting=value))
    assert result.record is not None
    assert result.record.setting == expected_stored
    if expect_coverage_key:
        assert result.field_coverage["setting"] == "not_extracted"
    else:
        assert "setting" not in result.field_coverage
    assert ("setting" in result.coerced_null_fields) is expect_coerced
    assert "setting" not in result.unclear_fields


@pytest.mark.parametrize(
    ("value", "expected_stored", "expect_coverage_key", "expect_coerced"),
    [
        ("United Kingdom", "United Kingdom", False, False),
        ("N/A", None, True, True),
        (None, None, True, False),
    ],
)
def test_study_geography_coverage_v2(
    value: str | None,
    expected_stored: str | None,
    expect_coverage_key: bool,
    expect_coerced: bool,
) -> None:
    """A real value passes through uncovered; a null-like string is coerced
    to None (coverage + coerced_null_fields); a wire null completes straight
    to "not_extracted" without ever touching coerced_null_fields. There is no
    path to "unclear" for this free-text field in v2 — only coercion applies."""
    result = validate_record(_wire(study_geography=value))
    assert result.record is not None
    assert result.record.study_geography == expected_stored
    if expect_coverage_key:
        assert result.field_coverage["study_geography"] == "not_extracted"
    else:
        assert "study_geography" not in result.field_coverage
    assert ("study_geography" in result.coerced_null_fields) is expect_coerced
    assert "study_geography" not in result.unclear_fields


@pytest.mark.parametrize(
    ("value", "expect_coverage_key"),
    [
        ("observed", False),
        ("modelled", False),
        (None, True),
    ],
)
def test_effect_basis_coverage_v2(value: str | None, expect_coverage_key: bool) -> None:
    """A real value passes through uncovered; a wire null completes to
    "not_extracted". "unclear" is unreachable for effect_basis in v2: it is a
    strict Literal at the wire model boundary, so an invalid string fails
    pydantic validation before ever reaching validate_record — there is no
    unparseable value left for these rules to flag."""
    result = validate_record(_wire(effect_basis=value))
    assert result.record is not None
    assert result.record.effect_basis == value
    if expect_coverage_key:
        assert result.field_coverage["effect_basis"] == "not_extracted"
    else:
        assert "effect_basis" not in result.field_coverage
    assert "effect_basis" not in result.coerced_null_fields
    assert "effect_basis" not in result.unclear_fields


def test_v1_null_vs_v2_null_coverage_distinguisher() -> None:
    """A v2-validated record with both new fields null carries both coverage
    keys; a v1-era coverage dict (predating these fields) has neither key —
    the two null states are distinguishable by key-absence in the stored
    coverage dict, never by a stored None/placeholder value."""
    result = validate_record(_wire(study_geography=None, effect_basis=None))
    assert result.record is not None
    assert result.field_coverage["study_geography"] == "not_extracted"
    assert result.field_coverage["effect_basis"] == "not_extracted"

    v1_shaped_coverage: dict[str, str] = {"population": "not_extracted"}
    assert "study_geography" not in v1_shaped_coverage
    assert "effect_basis" not in v1_shaped_coverage


# --- iof_rules_v3: dedup twins (effect_basis in the claim key, geography/setting out) ---


def test_dedup_distinct_effect_basis_splits() -> None:
    """effect_basis rides the claim key: observed vs modelled is a different
    claim, never collapsed."""
    r1 = _record(effect_basis="observed", statistics=_stats(effect_size=0.8))
    r2 = _record(effect_basis="modelled", statistics=_stats(effect_size=0.8))
    deduped, collapsed = dedup_records([r1, r2])
    assert collapsed == 0
    assert len(deduped) == 2


def test_dedup_same_claim_different_study_geography_collapses_first_wins() -> None:
    """study_geography stays out of the claim key: two otherwise-identical
    records with different study_geography collapse, and the survivor keeps
    the first record's study_geography (first-wins)."""
    r1 = _record(study_geography="United Kingdom", statistics=_stats(effect_size=0.8))
    r2 = _record(study_geography="France", statistics=_stats(effect_size=0.8))
    deduped, collapsed = dedup_records([r1, r2])
    assert collapsed == 1
    assert len(deduped) == 1
    assert deduped[0].study_geography == "United Kingdom"


def test_dedup_same_claim_different_setting_collapses_first_wins() -> None:
    """Top-level setting stays out of the claim key: it is descriptive metadata."""
    r1 = _record(setting="primary care", statistics=_stats(effect_size=0.8))
    r2 = _record(setting="secondary schools", statistics=_stats(effect_size=0.8))
    assert claim_key(r1) == claim_key(r2)

    deduped, collapsed = dedup_records([r1, r2])
    assert collapsed == 1
    assert len(deduped) == 1
    assert deduped[0].setting == "primary care"


def test_top_level_setting_coexists_with_setting_stratum() -> None:
    result = validate_record(
        _wire(
            setting="primary care",
            stratum_qualifiers=[
                IOFStratumWire(type="setting", value="rural clinics")
            ],
        )
    )

    assert result.record is not None
    assert result.record.setting == "primary care"
    assert [(s.type, s.value) for s in result.record.stratum_qualifiers] == [
        ("setting", "rural clinics")
    ]
