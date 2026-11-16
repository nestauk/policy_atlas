"""Parse profile v2: the markup rule at segmentation (task 057, contract N7 and D8).

v2 is v1 with ``core.markup.strip_markup`` applied to every chunk's text and every
heading. These are the quick, in-memory checks on each route. The checks on the
committed fixture corpus (no markup left, v1's structure kept, byte-identical runs)
parse large PDFs, so they live with the other corpus tests in
``test_ingest_full_text.py`` (the slow lane that ``make test-fast`` skips).
"""

from __future__ import annotations

from typing import Any

import pytest

from policy_atlas.core.markup import strip_markup
from policy_atlas.evidence_search.sourcing.ingest_full_text import (
    _segment_markdown_pages,
    parse_and_segment,
    parse_profile_for,
)


def _markup_bearing(chunks: list[dict[str, Any]]) -> int:
    return sum(1 for c in chunks if strip_markup(c["content"]) != c["content"])


def test_parse_profile_for_names_each_route() -> None:
    assert parse_profile_for("application/pdf") == ("pymupdf4llm_v2", "pymupdf4llm_struct_v2")
    assert parse_profile_for("text/html; charset=UTF-8") == (
        "trafilatura_v2", "trafilatura_para_v2",
    )
    assert parse_profile_for("application/xml") == ("jats_expat_v2", "jats_struct_v2")
    assert parse_profile_for("TEXT/XML") == ("jats_expat_v2", "jats_struct_v2")
    assert parse_profile_for("text/plain") == ("plain_v2", "plain_para_v2")
    assert parse_profile_for("") == ("plain_v2", "plain_para_v2")  # untyped = plain route


def test_parse_profile_for_agrees_with_parse_and_segment_on_plain_text() -> None:
    result = parse_and_segment(b"Plain words. " * 40, "text/plain; charset=utf-8", 0)
    assert parse_profile_for("text/plain; charset=utf-8") == (
        result["parse_profile"], result["segmentation_policy"],
    )


def test_parse_profile_for_refuses_types_that_are_never_parsed() -> None:
    with pytest.raises(ValueError, match="unsupported_type"):
        parse_profile_for("image/jpeg")
    assert parse_and_segment(b"\xff\xd8", "image/jpeg", 0)["reason"] == "unsupported_type"


def test_html_markup_in_the_source_is_stripped() -> None:
    para = (
        "The **pilot** cut costs by _a third_ in [the first year](https://example.org/y1)"
        " and kept its staff &lt;br&gt; through the winter."
    )
    body = (
        "<html><body><article><h1>Results</h1>"
        f"<p>{para}</p><p>Second paragraph with enough words to read as body text.</p>"
        "</article></body></html>"
    ).encode()
    result = parse_and_segment(body, "text/html", 0)
    assert result["status"] == "ok", result
    contents = [c["content"] for c in result["chunks"]]
    # (trafilatura repeats the body of a page this small; the repeat is not the point)
    assert (
        "The pilot cut costs by a third in the first year and kept its staff\n"
        "through the winter."
    ) in contents
    assert _markup_bearing(result["chunks"]) == 0
    assert [c["locator"] for c in result["chunks"]] == [
        {"paragraph": i} for i in range(1, len(contents) + 1)
    ]


def test_plain_text_markup_is_stripped_per_paragraph() -> None:
    body = b"A **bold** start.\n\n![figure](f.png)\n\nThe `end`."
    result = parse_and_segment(body, "text/plain", 0)
    assert [c["content"] for c in result["chunks"]] == ["A bold start.", "The end."]
    assert [c["locator"] for c in result["chunks"]] == [{"paragraph": 1}, {"paragraph": 2}]


def test_markdown_tables_keep_one_row_per_line_and_headings_lose_markup() -> None:
    page = (
        "## **Key findings**\n\n"
        "Costs fell by **30%** in ![chart](c.png) year one.\n\n"
        "| Arm | Result |\n|---|---|\n| **A** | fell<br>sharply |\n"
    )
    chunks = _segment_markdown_pages([(3, page)])
    # The table is cut as soon as it ends; its section's text follows (as in v1).
    assert chunks == [
        {
            "content": "| Arm | Result |\n|---|---|\n| A | fell sharply |",
            "locator": {"pages": [3], "heading_path": ["Key findings"]},
        },
        {
            "content": "Costs fell by 30% in  year one.",
            "locator": {"pages": [3], "heading_path": ["Key findings"]},
        },
    ]
