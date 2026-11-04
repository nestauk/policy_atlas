"""qv_v2: the quote matcher ignores markdown/HTML markup on both sides (task 057 N14)."""

from __future__ import annotations

from policy_atlas.evidence_search.extract.quote_verify import (
    QUOTE_VERIFIER_VERSION,
    QuoteMatcher,
    _normalise,
    build_basis,
    locate_unique_span,
)


def test_version_is_qv_v2() -> None:
    assert QUOTE_VERIFIER_VERSION == "qv_v2"


def test_markup_quote_matches_plain_chunk() -> None:
    raw = "Results: bold words appeared in the summary."
    basis = build_basis([("c1", raw)])
    match = QuoteMatcher(basis).find("**bold** words")
    assert match.status == "normalised"
    (span,) = match.spans
    assert raw[span.start : span.end] == "bold words"


def test_plain_quote_matches_markup_chunk() -> None:
    raw = "Results: **bold** words appeared in the _summary_."
    basis = build_basis([("c1", raw)])
    match = QuoteMatcher(basis).find("bold words appeared in the summary")
    assert match.status == "normalised"
    (span,) = match.spans
    # The span runs through the deleted closing "**" and the inner "_" markers.
    assert raw[span.start : span.end] == "bold** words appeared in the _summary"


def test_link_quote_matches_link_text_chunk() -> None:
    raw = "Read the evaluation report before deciding."
    basis = build_basis([("c1", raw)])
    match = QuoteMatcher(basis).find("the [evaluation report](https://example.org/r.pdf) before")
    assert match.status == "normalised"
    (span,) = match.spans
    assert raw[span.start : span.end] == "the evaluation report before"


def test_link_text_quote_matches_link_chunk() -> None:
    raw = "Read the [evaluation report](https://example.org/r_(v2).pdf) before deciding."
    basis = build_basis([("c1", raw)])
    quote = "the evaluation report before"
    match = QuoteMatcher(basis).find(quote)
    assert match.status == "normalised"
    (span,) = match.spans
    link = "[evaluation report](https://example.org/r_(v2).pdf)"
    assert raw[span.start : span.end] == f"the {link} before"
    # The read-time locator agrees, even though the span cuts the link syntax.
    assert locate_unique_span(basis, quote) == (span.start, span.end)


def test_anchor_span_covers_deleted_markup_like_soft_hyphen() -> None:
    # Compare test_normalised_hit_smart_quotes_dash_nbsp_soft_hyphen: deleted
    # characters inside a match stay inside the recorded raw interval.
    soft = "so the pro­gramme worked"
    marked = "so the **programme** worked"
    for raw, inner in ((soft, "pro­gramme"), (marked, "**programme**")):
        basis = build_basis([("c1", raw)])
        match = QuoteMatcher(basis).find("the programme worked")
        (span,) = match.spans
        raw_slice = raw[span.start : span.end]
        assert raw_slice == f"the {inner} worked"
        assert _normalise(raw_slice) == _normalise("the programme worked")
    # Two chunks: the deleted markup stays in the right chunk-local interval.
    basis = build_basis([("c1", "intro"), ("c2", "a <b>tagged</b> phrase here")])
    match = QuoteMatcher(basis).find("tagged phrase")
    (span,) = match.spans
    assert span.chunk_id == "c2"
    assert "a <b>tagged</b> phrase here"[span.start : span.end] == "tagged</b> phrase"


def test_br_in_chunk_matches_space_in_quote() -> None:
    raw = "first line<br>second line"
    basis = build_basis([("c1", raw)])
    quote = "line second"
    match = QuoteMatcher(basis).find(quote)
    assert match.status == "normalised"
    (span,) = match.spans
    assert raw[span.start : span.end] == "line<br>second"
    assert locate_unique_span(basis, quote) == (span.start, span.end)


def test_br_in_quote_matches_space_in_chunk() -> None:
    basis = build_basis([("c1", "first line second line")])
    assert QuoteMatcher(basis).find("line<br/>second").status == "normalised"


def test_verbatim_markup_quote_grades_normalised() -> None:
    raw = "the **bold** claim"
    basis = build_basis([("c1", raw)])
    match = QuoteMatcher(basis).find("**bold** claim")
    # Normalised match starts at "b" (opening markers are deleted), so the raw
    # slice is "bold** claim" — not byte-equal to the quote.
    assert match.status == "normalised"
    (span,) = match.spans
    assert raw[span.start : span.end] == "bold** claim"


def test_locate_unique_span_markup_both_sides() -> None:
    basis = build_basis([(None, "Policy **X** cut costs by _10%_ in year one.")])
    assert locate_unique_span(basis, "policy x cut costs by 10%") is not None
    assert locate_unique_span(basis, "Policy X cut [costs](u) by 10%") is not None


def test_locate_unique_span_still_rejects_partial_ligature() -> None:
    basis = build_basis([(None, "an eﬃcient **plan**")])
    assert locate_unique_span(basis, "efficient plan") is not None
    assert locate_unique_span(basis, "fficient plan") is None
