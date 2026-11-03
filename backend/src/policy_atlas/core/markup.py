"""The markup rule: strip markdown and HTML markup from text, keeping the words.

Parsed full texts (the PDF parser's markdown output, and HTML) carry markup such as
``**bold**``, ``_emphasis_``, ``[link text](url)``, ``<br>`` line breaks and HTML tags.
This module holds the one rule that removes it, so that every reader applies the same
rule (task 057, contract N7 and N14):

* the parser strips markup from newly parsed text (parse profile v2), using
  :func:`strip_markup`;
* the quote verifier (``evidence_search.extract.quote_verify``, version ``qv_v2``)
  ignores markup on both the quote and the chunk text, using :func:`markup_deletions`,
  which says *which raw characters* the rule removes so the verifier can keep its map
  from the cleaned text back to the original character positions.

What the rule does, in order (one line at a time; lines are split on ``"\\n"``):

1. image syntax ``![alt](src)`` is removed entirely;
2. link syntax ``[text](url)`` is reduced to ``text`` (twice, for a link inside a link);
3. ``<br>`` becomes a line break (or a space in a table row);
4. other known HTML tags (``<b>``, ``</span>`` ...; a fixed list of names) are removed,
   while tag-shaped maths such as ``x<y and y>z`` is kept;
5. inline code ```code``` is reduced to ``code``;
6. paired emphasis markers (``*``/``**``/``***``/``_``/``__``/``___``) are removed,
   when the opening marker does not follow a letter or digit (so identifiers keep
   their underscores), keeping the words between them (up to three rounds, for nested emphasis);
7. leftover runs of ``**`` or ``__`` (a marker whose partner was lost) are removed;
8. backslash escapes such as ``\\*`` become the plain character ``*``.

This module must not import anything from ``evidence_search`` (``core`` sits below it).
"""

from __future__ import annotations

import re

# The HTML tag names the rule removes; anything else shaped like a tag (``x<y and y>z``)
# is kept. This set is the single source of truth for the tag pattern below.
_HTML_TAGS = frozenset(
    [
        "a",
        "abbr",
        "article",
        "aside",
        "b",
        "big",
        "blockquote",
        "body",
        "br",
        "caption",
        "center",
        "cite",
        "code",
        "col",
        "colgroup",
        "dd",
        "del",
        "dfn",
        "div",
        "dl",
        "dt",
        "em",
        "figcaption",
        "figure",
        "font",
        "footer",
        "form",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "head",
        "header",
        "hr",
        "html",
        "i",
        "img",
        "input",
        "ins",
        "kbd",
        "label",
        "li",
        "link",
        "main",
        "mark",
        "meta",
        "nav",
        "ol",
        "option",
        "p",
        "pre",
        "q",
        "s",
        "samp",
        "script",
        "section",
        "select",
        "small",
        "span",
        "strike",
        "strong",
        "style",
        "sub",
        "sup",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "title",
        "tr",
        "tt",
        "u",
        "ul",
        "var",
    ]
)

_IMG_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK_RE = re.compile(r"\[([^\]]*)\]\((?:[^()\s]|\([^()]*\))*\)")
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_TAG_RE = re.compile(
    r"</?(?:" + "|".join(sorted(_HTML_TAGS, key=lambda n: (-len(n), n))) + r")(?:\s[^<>]*)?/?>",
    re.IGNORECASE,
)
_EMPH_RE = re.compile(r"(?<![A-Za-z0-9])(\*{1,3}|_{1,3})(?=\S)(.+?)(?<=\S)\1(?![A-Za-z0-9])")
# Stray ``**`` after a digit is a significance star in a statistics table (``0.50**``),
# not a lost emphasis marker, so it stays (owner ruling 2026-11-03: the rule must not
# delete content).
_STRAY_EMPH_RE = re.compile(r"(?<![0-9*])\*\*+|(?<![A-Za-z0-9])__+|__+(?![A-Za-z0-9])")
_CODE_RE = re.compile(r"`([^`]*)`")
_ESC_RE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|>~])")

# Every pattern above needs at least one of these characters; a line without any of
# them carries no markup and is skipped (a cheap fast path for plain text).
_MARKUP_CHARS = frozenset("![]<>`*_\\")

# What a ``<br>`` span is replaced with when the verifier folds it: one space.
BR_REPLACEMENT = " "


def _has_markup_chars(line: str) -> bool:
    return not _MARKUP_CHARS.isdisjoint(line)


def _strip_line(line: str, *, table: bool) -> str:
    """Apply the markup rule to one line (the E6 reference behaviour)."""
    t = _IMG_RE.sub("", line)
    for _ in range(2):  # nested link text
        t = _LINK_RE.sub(r"\1", t)
    t = _BR_RE.sub(" " if table else "\n", t)
    t = _TAG_RE.sub("", t)
    t = _CODE_RE.sub(r"\1", t)
    for _ in range(3):  # nested / adjacent emphasis
        new = _EMPH_RE.sub(r"\2", t)
        if new == t:
            break
        t = new
    t = _STRAY_EMPH_RE.sub("", t)
    t = _ESC_RE.sub(r"\1", t)
    return t


def strip_markup(text: str, *, table: bool = False) -> str:
    """Remove markdown and HTML markup from text, keeping the words.

    The rule is applied to each line on its own (lines split on ``"\\n"``), so a
    one-line input behaves exactly as the task 057 experiment E6 rule did.

    Args:
        text: Text that may carry markup (for example a line of the PDF parser's
            markdown output).
        table: True for a table row: ``<br>`` becomes a space so the row stays on one
            line. False (the default): ``<br>`` becomes a line break ``"\\n"``.

    Returns:
        The text without markup. With ``table=False`` it may contain extra ``"\\n"``
        characters where a ``<br>`` was.
    """
    return "\n".join(
        _strip_line(line, table=table) if _has_markup_chars(line) else line
        for line in text.split("\n")
    )


# --- offset-tracking version of the same rule --------------------------------------
#
# The text is held as a list of characters, each tagged with where it came from: its
# position in the raw input (>= 0), or, for the line break a ``<br>`` turned into, a
# negative tag ``-(k + 1)`` naming the k-th ``<br>`` span. Each pass rebuilds the list,
# keeping the characters the regex keeps, so after all passes the surviving tags say
# exactly which raw characters remain.


def _sub_tracked(
    pattern: re.Pattern[str],
    chars: list[str],
    origins: list[int],
    *,
    keep_group: int | None,
) -> tuple[list[str], list[int], bool]:
    """Mirror ``pattern.sub`` on a tagged character list.

    Each match is replaced by the text of ``keep_group`` (or by nothing when
    ``keep_group`` is None), keeping that text's original tags.

    Returns:
        The new characters, their tags, and whether anything matched.
    """
    text = "".join(chars)
    out_chars: list[str] = []
    out_origins: list[int] = []
    pos = 0
    matched = False
    for match in pattern.finditer(text):
        matched = True
        start, end = match.span()
        out_chars.extend(chars[pos:start])
        out_origins.extend(origins[pos:start])
        if keep_group is not None:
            g_start, g_end = match.span(keep_group)
            out_chars.extend(chars[g_start:g_end])
            out_origins.extend(origins[g_start:g_end])
        pos = end
    out_chars.extend(chars[pos:])
    out_origins.extend(origins[pos:])
    return out_chars, out_origins, matched


def _line_deletions(line: str, offset: int) -> list[tuple[int, int, str]]:
    """Return the deletion spans for one line, in input offsets (``offset`` added)."""
    chars = list(line)
    origins = list(range(len(line)))

    chars, origins, _ = _sub_tracked(_IMG_RE, chars, origins, keep_group=None)
    for _ in range(2):
        chars, origins, _ = _sub_tracked(_LINK_RE, chars, origins, keep_group=1)

    # <br>: replace each span with one tagged line-break character (table=False rule).
    text = "".join(chars)
    br_spans: list[tuple[int, int]] = []  # raw (start, end) of each <br>
    new_chars: list[str] = []
    new_origins: list[int] = []
    pos = 0
    for match in _BR_RE.finditer(text):
        start, end = match.span()
        new_chars.extend(chars[pos:start])
        new_origins.extend(origins[pos:start])
        # A <br> is plain characters at this point (no earlier pass inserts any), so
        # its raw span runs from its first to its last character's raw position.
        br_spans.append((origins[start], origins[end - 1] + 1))
        new_chars.append("\n")
        new_origins.append(-len(br_spans))
        pos = end
    new_chars.extend(chars[pos:])
    new_origins.extend(origins[pos:])
    chars, origins = new_chars, new_origins

    chars, origins, _ = _sub_tracked(_TAG_RE, chars, origins, keep_group=None)
    chars, origins, _ = _sub_tracked(_CODE_RE, chars, origins, keep_group=1)
    for _ in range(3):
        chars, origins, matched = _sub_tracked(_EMPH_RE, chars, origins, keep_group=2)
        if not matched:
            break
    chars, origins, _ = _sub_tracked(_STRAY_EMPH_RE, chars, origins, keep_group=None)
    chars, origins, _ = _sub_tracked(_ESC_RE, chars, origins, keep_group=1)

    kept = [False] * len(line)
    surviving_br: list[tuple[int, int]] = []
    for tag in origins:
        if tag >= 0:
            kept[tag] = True
        else:
            surviving_br.append(br_spans[-tag - 1])
    for start, end in surviving_br:
        for i in range(start, end):
            kept[i] = True  # covered by its own " " span below, not a plain deletion

    spans: list[tuple[int, int, str]] = [
        (offset + start, offset + end, BR_REPLACEMENT) for start, end in surviving_br
    ]
    i = 0
    while i < len(line):
        if kept[i]:
            i += 1
            continue
        j = i
        while j < len(line) and not kept[j]:
            j += 1
        spans.append((offset + i, offset + j, ""))
        i = j
    spans.sort()
    return spans


def markup_deletions(text: str) -> list[tuple[int, int, str]]:
    """Return the raw spans the markup rule changes, for offset-preserving readers.

    This is the same rule as :func:`strip_markup` (``table=False``), reported as edits
    on the original text instead of as a new string, so a reader that must map
    cleaned text back to original character positions (the quote verifier) can do so.

    Each entry is ``(start, end, replacement)``: the half-open raw range
    ``text[start:end]`` is removed and ``replacement`` put in its place.
    ``replacement`` is ``""`` for removed markup, or one space ``" "`` for a ``<br>``
    line break. (:func:`strip_markup` with ``table=False`` writes ``"\\n"`` for a
    ``<br>``; the verifier collapses every run of whitespace to one space, so a space
    and a line break fold to the same thing there.) Spans are sorted and do not
    overlap.

    Args:
        text: Text that may carry markup; may hold several lines.

    Returns:
        The edit spans, in order. Applying them (with ``"\\n"`` for each ``" "``
        span) gives exactly ``strip_markup(text)``.
    """
    spans: list[tuple[int, int, str]] = []
    offset = 0
    for line in text.split("\n"):
        if _has_markup_chars(line):
            spans.extend(_line_deletions(line, offset))
        offset += len(line) + 1
    return spans
