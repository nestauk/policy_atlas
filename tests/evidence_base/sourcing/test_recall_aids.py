"""Tests for the recall-aid helpers in ingest_full_text.py (task 016-live-fetch,
task 4): the DOI-URL fallback in ``candidate_urls`` and the standalone
``discover_document_url`` landing-page helper. Fast, no DB, no network.
"""

from typing import Any

import pytest

from policy_atlas.evidence_base.sourcing import ingest_full_text
from policy_atlas.evidence_base.sourcing.ingest_full_text import (
    candidate_urls,
    discover_document_url,
)

# --- DOI fallback in candidate_urls ---


def test_doi_fallback_appended_last_when_valid() -> None:
    meta = {
        "backend": "openalex",
        "provider_fields": {
            "primary_location": {"landing_page_url": "https://example.org/landing"},
        },
        "doi": "10.1234/abc123",
    }
    assert candidate_urls(meta) == [
        "https://example.org/landing",
        "https://doi.org/10.1234/abc123",
    ]


def test_doi_fallback_percent_encodes_special_chars() -> None:
    meta = {"backend": "overton", "provider_fields": {}, "doi": "10.1234/ab(c);x<y>"}
    assert candidate_urls(meta) == ["https://doi.org/10.1234/ab%28c%29%3Bx%3Cy%3E"]


def test_doi_fallback_preserves_slash_unescaped() -> None:
    meta = {"backend": "overton", "provider_fields": {}, "doi": "10.1234/abc/def"}
    assert candidate_urls(meta) == ["https://doi.org/10.1234/abc/def"]


def test_doi_rejected_no_10_prefix() -> None:
    meta = {"backend": "overton", "provider_fields": {}, "doi": "11.1234/abc"}
    assert candidate_urls(meta) == []


def test_doi_rejected_registrant_too_short() -> None:
    # registrant code must be 4-9 digits; "123" is too short
    meta = {"backend": "overton", "provider_fields": {}, "doi": "10.123/abc"}
    assert candidate_urls(meta) == []


def test_doi_rejected_registrant_too_long() -> None:
    # 10 digits exceeds the 4-9 digit registrant window
    meta = {"backend": "overton", "provider_fields": {}, "doi": "10.1234567890/abc"}
    assert candidate_urls(meta) == []


def test_doi_rejected_suffix_over_200_chars() -> None:
    meta = {"backend": "overton", "provider_fields": {}, "doi": "10.1234/" + "a" * 201}
    assert candidate_urls(meta) == []


def test_doi_accepted_suffix_at_200_chars() -> None:
    doi = "10.1234/" + "a" * 200
    meta = {"backend": "overton", "provider_fields": {}, "doi": doi}
    assert candidate_urls(meta) == [f"https://doi.org/10.1234/{'a' * 200}"]


def test_doi_rejected_control_character_embedded() -> None:
    meta = {"backend": "overton", "provider_fields": {}, "doi": "10.1234/ab\x01c"}
    assert candidate_urls(meta) == []


def test_doi_rejected_non_string() -> None:
    meta = {"backend": "overton", "provider_fields": {}, "doi": 12345}
    assert candidate_urls(meta) == []


def test_doi_rejected_none() -> None:
    meta: dict[str, Any] = {"backend": "overton", "provider_fields": {}, "doi": None}
    assert candidate_urls(meta) == []


def test_doi_absent_no_fallback() -> None:
    meta = {"backend": "overton", "provider_fields": {"document_url": "https://example.org/x"}}
    assert candidate_urls(meta) == ["https://example.org/x"]


def test_doi_fallback_deduped_against_existing_https_doi_url() -> None:
    meta = {
        "backend": "overton",
        "provider_fields": {"document_url": "https://doi.org/10.1234/abc123"},
        "doi": "10.1234/abc123",
    }
    assert candidate_urls(meta) == ["https://doi.org/10.1234/abc123"]


def test_doi_fallback_deduped_against_existing_dx_doi_url() -> None:
    meta = {
        "backend": "overton",
        "provider_fields": {"document_url": "http://dx.doi.org/10.1234/abc123"},
        "doi": "10.1234/abc123",
    }
    assert candidate_urls(meta) == ["http://dx.doi.org/10.1234/abc123"]


def test_doi_fallback_not_deduped_against_different_doi() -> None:
    meta = {
        "backend": "overton",
        "provider_fields": {"document_url": "https://doi.org/10.1234/other"},
        "doi": "10.1234/abc123",
    }
    assert candidate_urls(meta) == [
        "https://doi.org/10.1234/other",
        "https://doi.org/10.1234/abc123",
    ]


def test_doi_fallback_deduped_against_unescaped_reserved_chars() -> None:
    """Codex MINOR finding: a provider-supplied doi.org URL that left the DOI's
    reserved characters unescaped (e.g. ``ab(c)``) must still suppress the
    percent-encoded fallback (``ab%28c%29``) — the comparison decodes both
    sides before comparing."""
    meta = {
        "backend": "overton",
        "provider_fields": {"document_url": "https://doi.org/10.1234/ab(c)"},
        "doi": "10.1234/ab(c)",
    }
    assert candidate_urls(meta) == ["https://doi.org/10.1234/ab(c)"]


def test_doi_fallback_deduped_case_insensitively() -> None:
    """The percent-decoded comparison is also case-insensitive."""
    meta = {
        "backend": "overton",
        "provider_fields": {"document_url": "https://doi.org/10.1234/ABC123"},
        "doi": "10.1234/abc123",
    }
    assert candidate_urls(meta) == ["https://doi.org/10.1234/ABC123"]


def test_backends_without_doi_field_unaffected() -> None:
    # Reuse the metadata shapes exercised in test_ingest_full_text.py's
    # test_url_resolution_order to confirm existing candidate_urls behaviour
    # (no "doi" key at all) is preserved unchanged.
    openalex_meta = {
        "backend": "openalex",
        "provider_fields": {
            "best_oa_location": {"pdf_url": "https://example.org/best.pdf"},
            "primary_location": {
                "pdf_url": "https://example.org/best.pdf",
                "landing_page_url": "https://example.org/landing",
            },
            "open_access": {"oa_url": "https://example.org/oa.pdf"},
        },
    }
    assert candidate_urls(openalex_meta) == [
        "https://example.org/best.pdf",
        "https://example.org/oa.pdf",
        "https://example.org/landing",
    ]

    overton_meta = {
        "backend": "overton",
        "provider_fields": {
            "pdf_url": "https://example.org/doc.pdf",
            "document_url": "https://example.org/doc-landing",
        },
    }
    assert candidate_urls(overton_meta) == [
        "https://example.org/doc.pdf",
        "https://example.org/doc-landing",
    ]

    assert candidate_urls({"backend": "overton"}) == []


# --- discover_document_url ---


def test_citation_pdf_url_meta_wins_and_absolutizes_relative_content() -> None:
    html = b"""
    <html><head>
      <meta name="citation_pdf_url" content="/files/paper.pdf">
    </head><body>
      <a href="https://example.org/other.pdf">other</a>
    </body></html>
    """
    assert (
        discover_document_url(html, "https://example.org/landing/page")
        == "https://example.org/files/paper.pdf"
    )


def test_citation_pdf_url_meta_name_case_insensitive() -> None:
    html = b"""
    <html><head>
      <meta name="Citation_PDF_URL" content="https://example.org/paper.pdf">
    </head></html>
    """
    assert (
        discover_document_url(html, "https://example.org/landing")
        == "https://example.org/paper.pdf"
    )


def test_meta_absent_same_host_anchor_preferred_over_earlier_cross_host() -> None:
    html = b"""
    <html><body>
      <a href="https://other.org/cross.pdf">cross</a>
      <a href="https://example.org/same.pdf">same</a>
    </body></html>
    """
    assert (
        discover_document_url(html, "https://example.org/landing")
        == "https://example.org/same.pdf"
    )


def test_no_same_host_falls_back_to_first_cross_host() -> None:
    html = b"""
    <html><body>
      <a href="https://other-a.org/first.pdf">a</a>
      <a href="https://other-b.org/second.pdf">b</a>
    </body></html>
    """
    assert (
        discover_document_url(html, "https://example.org/landing")
        == "https://other-a.org/first.pdf"
    )


def test_pdf_extension_case_insensitive() -> None:
    html = b'<html><body><a href="https://example.org/paper.PDF">p</a></body></html>'
    assert (
        discover_document_url(html, "https://example.org/landing")
        == "https://example.org/paper.PDF"
    )


def test_query_string_ignored_when_testing_path_suffix() -> None:
    html = b'<html><body><a href="https://example.org/paper.pdf?download=1">p</a></body></html>'
    assert (
        discover_document_url(html, "https://example.org/landing")
        == "https://example.org/paper.pdf?download=1"
    )


def test_query_string_does_not_create_false_positive() -> None:
    html = b'<html><body><a href="https://example.org/view?file=paper.pdf">p</a></body></html>'
    assert discover_document_url(html, "https://example.org/landing") is None


def test_no_candidates_returns_none() -> None:
    html = b"<html><body><p>No links here.</p></body></html>"
    assert discover_document_url(html, "https://example.org/landing") is None


def test_malformed_html_returns_none() -> None:
    assert discover_document_url(b"", "https://example.org/landing") is None
    assert discover_document_url(b"\x00\x01\x02not html at all", "https://example.org") is None


def test_non_http_scheme_meta_skipped_falls_through_to_anchor() -> None:
    html = b"""
    <html><head>
      <meta name="citation_pdf_url" content="javascript:alert(1)">
    </head><body>
      <a href="https://example.org/fallback.pdf">f</a>
    </body></html>
    """
    assert (
        discover_document_url(html, "https://example.org/landing")
        == "https://example.org/fallback.pdf"
    )


def test_non_http_scheme_anchor_skipped() -> None:
    html = b"""
    <html><body>
      <a href="ftp://example.org/paper.pdf">ftp</a>
      <a href="mailto:someone@example.org">mail</a>
    </body></html>
    """
    assert discover_document_url(html, "https://example.org/landing") is None


def test_fragment_only_href_skipped() -> None:
    html = b"""
    <html><body>
      <a href="#section-2">jump</a>
    </body></html>
    """
    assert discover_document_url(html, "https://example.org/landing") is None


def test_fragment_on_pdf_href_ignored_when_testing_path() -> None:
    html = b'<html><body><a href="paper.pdf#page=3">p</a></body></html>'
    assert (
        discover_document_url(html, "https://example.org/landing/")
        == "https://example.org/landing/paper.pdf#page=3"
    )


def test_anchor_scan_bounded_by_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    """016 review stack: the anchor scan is capped at ``_ANCHOR_SCAN_CAP``. A
    same-host match within the cap is still found (and the scan stops there —
    same-host wins unconditionally, so scanning further would be dead work),
    but a page whose only match sits past the cap still returns cleanly
    (no crash, no unbounded scan) rather than finding it."""
    monkeypatch.setattr(ingest_full_text, "_ANCHOR_SCAN_CAP", 3)

    within_cap = (
        b'<html><body><a href="https://other.org/skip0">skip</a>'
        b'<a href="https://other.org/skip1">skip</a>'
        b'<a href="https://example.org/in-cap.pdf">match</a></body></html>'
    )
    assert (
        discover_document_url(within_cap, "https://example.org/landing")
        == "https://example.org/in-cap.pdf"
    )

    over_cap = (
        b'<html><body><a href="https://other.org/skip0">skip</a>'
        b'<a href="https://other.org/skip1">skip</a>'
        b'<a href="https://other.org/skip2">skip</a>'
        b'<a href="https://example.org/past-cap.pdf">match</a></body></html>'
    )
    assert discover_document_url(over_cap, "https://example.org/landing") is None
