"""The shared markup rule: ``strip_markup`` and its offset-tracking twin agree."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from policy_atlas.core import markup
from policy_atlas.core.markup import markup_deletions, strip_markup

LINES = [
    "plain text with no markup at all",
    "**bold** words",
    "some _emphasis_ and __strong__ and ***both***",
    "see [the report](https://example.org/a_(b)) for details",
    "a [[nested](inner)](outer) link",
    "![a figure](fig1.png) Figure 1: results",
    "first<br>second<BR/>third<br />fourth",
    "<b>tagged</b> and <span class='x'>spanned</span>",
    "inline `code_here` stays",
    "a stray ** marker and a lost__ one",
    r"escaped \*star\* and \[bracket\] and a\_b",
    "snake_case_name and 2*3*4 keep their characters",
    "0.47* 0.50** 0.54*** 0.15 significance stars stay",
    "x<y and y>z stays whole",
    "Situation_report_-_the_file.pdf stays whole",
    "<em>kept</em> and <unknown>kept</unknown>",
    "| cell one<br>more | **cell two** |",
    "**[linked bold](http://x.org)** then _[em link](u)_",
    "<a <br> b> tag swallowing a break",
    "multi\nline **text**\nwith [links](x) on<br>several lines",
    "",
]


def _apply(text: str, spans: list[tuple[int, int, str]], br_as: str) -> str:
    out: list[str] = []
    pos = 0
    for start, end, replacement in spans:
        out.append(text[pos:start])
        out.append(br_as if replacement else "")
        pos = end
    out.append(text[pos:])
    return "".join(out)


@pytest.mark.parametrize("line", LINES)
def test_deletions_reproduce_strip_markup(line: str) -> None:
    spans = markup_deletions(line)
    # strip_markup(table=False) writes "\n" for a <br>; the spans report " ".
    assert _apply(line, spans, "\n") == strip_markup(line)
    assert all(replacement in ("", " ") for _, _, replacement in spans)


@pytest.mark.parametrize("line", LINES)
def test_spans_sorted_and_disjoint(line: str) -> None:
    spans = markup_deletions(line)
    for (_, prev_end, _), (start, _, _) in zip(spans, spans[1:], strict=False):
        assert prev_end <= start
    assert all(0 <= s < e <= len(line) for s, e, _ in spans)


def test_strip_markup_examples() -> None:
    assert strip_markup("**bold** words") == "bold words"
    # Significance stars in a statistics table are content, not markup (a line from the
    # frontiers_school_readiness_2022 fixture).
    assert strip_markup("0.47* 0.50** 0.54*** 0.15") == "0.47* 0.50** 0.54*** 0.15"
    assert strip_markup("see [the report](https://x.org) now") == "see the report now"
    assert strip_markup("x<y and y>z") == "x<y and y>z"
    assert strip_markup("see Situation_report_-_the_file") == "see Situation_report_-_the_file"
    assert strip_markup("<em>a</em> and <unknown>b</unknown>") == "a and <unknown>b</unknown>"
    assert strip_markup("<B>loud</B>") == "loud"
    assert strip_markup("_em_ and *it*") == "em and it"
    assert strip_markup("a<br>b") == "a\nb"
    assert strip_markup("a<br>b", table=True) == "a b"
    assert strip_markup("![fig](f.png) caption") == " caption"
    assert strip_markup(r"3 \* 4 and a\_b") == "3 * 4 and a_b"
    # task 057 review (Codex 12): an escaped marker neither opens nor closes
    # emphasis, so the stars survive and rule 8 unescapes them.
    assert strip_markup(r"\*literal\*") == "*literal*"
    assert strip_markup(r"\*a\* and *b*") == "*a* and b"


def test_one_letter_tag_names_need_a_tag_shape() -> None:
    """task 057 review (contract verifier 5): tag-shaped maths with a one-letter
    name stays whole; real one-letter tags still strip."""
    for kept in ("x<y and y>z", "a<b and c>d", "p<q"):
        assert strip_markup(kept) == kept
    assert strip_markup("<b>bold</b> x") == "bold x"
    assert strip_markup('<a href="u">link</a>') == "link"
    assert strip_markup("<i>it</i>") == "it"


def test_br_span_is_a_space() -> None:
    assert markup_deletions("a<br>b") == [(1, 5, " ")]


def test_plain_text_has_no_deletions() -> None:
    assert markup_deletions("nothing to see here, 3 - 2 = 1.") == []


def test_core_markup_does_not_import_evidence_search() -> None:
    tree = ast.parse(Path(markup.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert "evidence_search" not in (node.module or "")
        elif isinstance(node, ast.Import):
            assert all("evidence_search" not in alias.name for alias in node.names)
