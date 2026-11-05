"""Turn a JATS XML article into the markdown-like text the full-text segmenter reads.

JATS (Journal Article Tag Suite) is the XML format publishers deposit articles in;
Europe PMC serves it for open-access papers. Unlike a PDF it says outright which
text is a section heading, a paragraph or a table, so no layout guessing is needed.

The output has the same shape the PDF branch of ``ingest_full_text`` builds before
it cuts the text into chunks: a list of ``(page_number, markdown_text)`` pairs that
``_segment_markdown_pages`` consumes. XML has no pages, so the whole article is one
pseudo-page numbered 1. In the markdown:

- ``#`` is the article title, ``##`` the abstract and each top-level section,
  ``###`` and deeper the nested sections (capped at ``######``);
- paragraphs are separated by blank lines;
- tables are simple pipe tables (``| a | b |``), with their label and caption as
  a paragraph just above;
- figure captions are paragraphs ("Figure 1. ...");
- the reference list is left out. It is a list of citations, not findings: in a
  chunk it adds search noise and embedding cost without adding evidence, and the
  cited works are already kept from OpenAlex (``referenced_works``). Appendices,
  acknowledgements and other back-matter sections are kept.

Safety. The XML comes from the internet, so it is parsed with the standard
library's expat parser set up to fetch nothing: parameter entities and the external
DTD are never read (``XML_PARAM_ENTITY_PARSING_NEVER``) and any external entity
reference (``<!ENTITY x SYSTEM "file:///...">``) is refused, which fails the
document. Entity "bombs" (one entity expanding to billions of characters) are
stopped by expat's own amplification limit (expat 2.4.1 and newer; the parse
fails with an error, quickly). Named entities that JATS files use without defining
them (``&nbsp;``, ``&ndash;`` ...) would be fatal to a non-validating parser, so
they are swapped for numeric character references before parsing, from a small
table, with the Unicode replacement character for any name not in it.

Never raises: a document that cannot be read comes back as
``{"status": "error", "reason": ..., "detail": ...}`` like every other per-document
outcome in ``parse_and_segment``.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any
from xml.parsers import expat

# The parser leans on expat's entity-amplification limit (added in 2.4.1) against
# entity bombs; fail at import, where the service starts, not inside a parse worker.
if expat.version_info < (2, 4, 1):
    raise RuntimeError(f"parse_jats needs expat >= 2.4.1, found {expat.version_info}")

# v2 (task 057, N7): the segmenter applies the markup rule to the text this parser
# renders; the parser itself is unchanged since v1.
JATS_PARSE_PROFILE = "jats_expat_v2"
JATS_SEGMENTATION_POLICY = "jats_struct_v2"

_MAX_HEADING_LEVEL = 6
_XML_PREDEFINED_ENTITIES = frozenset({"amp", "lt", "gt", "quot", "apos"})
# Common named entities from the HTML/ISO sets that appear undeclared in JATS.
_ENTITY_FALLBACKS: dict[str, int] = {
    "nbsp": 0x00A0, "ensp": 0x2002, "emsp": 0x2003, "thinsp": 0x2009, "hairsp": 0x200A,
    "ndash": 0x2013, "mdash": 0x2014, "minus": 0x2212, "hyphen": 0x2010,
    "lsquo": 0x2018, "rsquo": 0x2019, "ldquo": 0x201C, "rdquo": 0x201D,
    "laquo": 0x00AB, "raquo": 0x00BB, "hellip": 0x2026, "bull": 0x2022,
    "middot": 0x00B7, "deg": 0x00B0, "times": 0x00D7, "divide": 0x00F7,
    "plusmn": 0x00B1, "le": 0x2264, "ge": 0x2265, "ne": 0x2260, "asymp": 0x2248,
    "micro": 0x00B5, "copy": 0x00A9, "reg": 0x00AE, "trade": 0x2122,
    "sect": 0x00A7, "para": 0x00B6, "dagger": 0x2020, "Dagger": 0x2021,
    "prime": 0x2032, "Prime": 0x2033, "permil": 0x2030, "euro": 0x20AC,
    "pound": 0x00A3, "alpha": 0x03B1, "beta": 0x03B2, "gamma": 0x03B3,
    "delta": 0x03B4, "epsilon": 0x03B5, "kappa": 0x03BA, "lambda": 0x03BB,
    "mu": 0x03BC, "pi": 0x03C0, "rho": 0x03C1, "sigma": 0x03C3, "tau": 0x03C4,
    "chi": 0x03C7, "omega": 0x03C9, "Delta": 0x0394, "Sigma": 0x03A3,
    "eacute": 0x00E9, "egrave": 0x00E8, "aacute": 0x00E1, "oacute": 0x00F3,
    "uuml": 0x00FC, "ouml": 0x00F6, "auml": 0x00E4, "ccedil": 0x00E7,
}
_REPLACEMENT_CHAR = 0xFFFD
_ENTITY_REF_RE = re.compile(rb"&([A-Za-z_][A-Za-z0-9._-]*);")
_ENTITY_DECL_RE = re.compile(rb"<!ENTITY\s+([A-Za-z_][A-Za-z0-9._:-]*)")
_WHITESPACE_RE = re.compile(r"\s+")

# Elements rendered as their own blocks when met inside a paragraph or section.
_TABLE_TAGS = frozenset({"table-wrap"})
_FIGURE_TAGS = frozenset({"fig"})
_LIST_TAGS = frozenset({"list", "def-list"})
_BLOCK_TAGS = _TABLE_TAGS | _FIGURE_TAGS | _LIST_TAGS | frozenset(
    {"disp-quote", "boxed-text", "table-wrap-group", "fig-group"}
)
# Never rendered as text.
_SKIP_TAGS = frozenset({"ref-list", "fn-group", "graphic", "inline-graphic", "media",
                        "object-id", "permissions", "supplementary-material"})
_FORMULA_TAGS = frozenset({"inline-formula", "disp-formula"})
# One of these as a direct child of an unknown element means it is a container to walk into.
_CONTAINER_HINT_TAGS = _BLOCK_TAGS | frozenset({"p", "sec"})
# Inline elements that stand for a line break or a block: keep words apart.
_SPACED_INLINE_TAGS = frozenset({"break", "p", "list-item", "title", "label"})
_TEX_DOCUMENT_RE = re.compile(r"\\begin\{document\}(.*?)\\end\{document\}", re.DOTALL)


class _ExternalEntityRefused(Exception):
    pass


def parse_jats(body: bytes) -> dict[str, Any]:
    """Parse one JATS XML article into pseudo-page markdown ready for segmentation.

    Args:
        body: Raw XML bytes, as returned by ``fetch_europe_pmc_xml``.

    Returns:
        On success ``{"status": "ok", "pages": [(1, markdown)], "title": str | None,
        "parse_profile": JATS_PARSE_PROFILE, "segmentation_policy":
        JATS_SEGMENTATION_POLICY}``, where ``pages`` is the input
        ``_segment_markdown_pages`` takes. On failure ``{"status": "error",
        "reason": "corrupt" | "empty", "detail": str}``: ``corrupt`` when the XML
        cannot be read safely (malformed, an entity bomb, an external entity),
        ``empty`` when the article has no body text (only an abstract), in which
        case the caller should try another route. Never raises.
    """
    try:
        root = _parse_xml(_replace_undefined_entities(body))
    except _ExternalEntityRefused:
        return _error("corrupt", "external entity reference refused")
    except expat.ExpatError as exc:
        return _error("corrupt", f"xml: {exc}")
    except Exception as exc:  # defensive: a parser crash is a corrupt document
        return _error("corrupt", f"{type(exc).__name__}: {exc}")
    try:
        title, markdown, body_blocks = _render_article(root)
    except RecursionError:
        return _error("corrupt", "nesting too deep")
    except Exception as exc:  # defensive: never raise for one document
        return _error("corrupt", f"{type(exc).__name__}: {exc}")
    if body_blocks == 0:
        return _error("empty", "no body text in the XML")
    return {
        "status": "ok",
        "pages": [(1, markdown)],
        "title": title,
        "parse_profile": JATS_PARSE_PROFILE,
        "segmentation_policy": JATS_SEGMENTATION_POLICY,
    }


def _error(reason: str, detail: str) -> dict[str, Any]:
    return {"status": "error", "reason": reason, "detail": detail[:500]}


# --- Safe parsing ---


def _replace_undefined_entities(body: bytes) -> bytes:
    """Swap named entities the document never declares for numeric references.

    Entities the document declares itself (in its own ``<!DOCTYPE [...]>``) and the
    five XML built-ins are left for expat, so its amplification limit still applies
    to them.
    """
    declared = {m.group(1) for m in _ENTITY_DECL_RE.finditer(body)}

    def replace(match: re.Match[bytes]) -> bytes:
        name = match.group(1)
        text = name.decode("ascii", errors="replace")
        if text in _XML_PREDEFINED_ENTITIES or name in declared:
            return match.group(0)
        code = _ENTITY_FALLBACKS.get(text, _REPLACEMENT_CHAR)
        return b"&#x%X;" % code

    return _ENTITY_REF_RE.sub(replace, body)


def _parse_xml(body: bytes) -> ET.Element:
    builder = ET.TreeBuilder()
    parser = expat.ParserCreate()  # no namespace processing: "mml:math" stays a plain name
    # Never read the external DTD or parameter entities (no file or network access).
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    parser.ExternalEntityRefHandler = _refuse_external_entity
    # An entity expat skips (declared only in the unread external DTD) becomes the
    # replacement character in the text; skipped parameter entities add nothing.
    parser.SkippedEntityHandler = lambda _name, is_param: (
        None if is_param else builder.data(chr(_REPLACEMENT_CHAR))
    )
    parser.StartElementHandler = builder.start
    parser.EndElementHandler = builder.end
    parser.CharacterDataHandler = builder.data
    parser.buffer_text = True
    parser.Parse(body, True)
    return builder.close()


def _refuse_external_entity(
    context: str | None, base: str | None, system_id: str | None, public_id: str | None
) -> int:
    raise _ExternalEntityRefused(system_id or public_id or "")


# --- Rendering ---


def _local(tag: Any) -> str:
    return tag if isinstance(tag, str) else ""


def _clean(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def _safe_line(text: str) -> str:
    """Stop body text from being read as a heading or a table row by the segmenter."""
    if text.startswith(("#", "|")):
        return "\\" + text
    return text


def _inline_text(elem: ET.Element) -> str:
    """All text inside ``elem`` on one line, formulas reduced to their TeX form if given."""
    return _clean("".join(_iter_inline(elem)))


def _iter_inline(elem: ET.Element) -> list[str]:
    tag = _local(elem.tag)
    if tag in _SKIP_TAGS:
        return []
    if tag in _FORMULA_TAGS:
        return [" ", _formula_text(elem), " "]
    if tag in _SPACED_INLINE_TAGS:
        return [" ", *_iter_inline_children(elem), " "]
    return _iter_inline_children(elem)


def _iter_inline_children(elem: ET.Element) -> list[str]:
    out: list[str] = [elem.text or ""]
    for child in elem:
        out.extend(_iter_inline(child))
        out.append(child.tail or "")
    return out


def _formula_text(elem: ET.Element) -> str:
    """A formula as TeX when the file gives it (minus the LaTeX preamble), else MathML text."""
    tex = elem.find(".//tex-math")
    if tex is not None:
        text = "".join(tex.itertext())
        match = _TEX_DOCUMENT_RE.search(text)
        if match is not None:
            text = match.group(1)
        return _clean(text.replace("$$", " "))
    return _clean(" ".join(elem.itertext()))


class _Renderer:
    def __init__(self) -> None:
        self.blocks: list[str] = []
        self.body_blocks = 0
        self.in_body = False

    def heading(self, level: int, text: str) -> None:
        text = _clean(text)
        if text:
            self.blocks.append(f"{'#' * min(level, _MAX_HEADING_LEVEL)} {text}")

    def paragraph(self, text: str) -> None:
        text = _clean(text)
        if text:
            self.blocks.append(_safe_line(text))
            if self.in_body:
                self.body_blocks += 1

    def section(self, sec: ET.Element, level: int) -> None:
        title = sec.find("title")
        label = sec.find("label")
        heading = " ".join(
            t for t in (
                _inline_text(label) if label is not None else "",
                _inline_text(title) if title is not None else "",
            ) if t
        )
        start = len(self.blocks)
        self.children(sec, level + 1, skip={"title", "label"})
        # A heading over nothing (e.g. a "References" section whose list is left out)
        # is dropped rather than left as an empty section.
        if heading and len(self.blocks) > start:
            self.blocks.insert(start, f"{'#' * min(level, _MAX_HEADING_LEVEL)} {heading}")

    def children(
        self, parent: ET.Element, level: int, skip: frozenset[str] | set[str] = frozenset()
    ) -> None:
        for child in parent:
            tag = _local(child.tag)
            if tag in skip or tag in _SKIP_TAGS:
                continue
            self.block(child, level)

    def block(self, elem: ET.Element, level: int) -> None:
        tag = _local(elem.tag)
        if tag in {"sec", "app", "ack", "glossary", "notes", "bio"}:
            self.section(elem, level)
        elif tag in {"app-group", "body", "back", "floats-group", "abstract", "trans-abstract"}:
            self.children(elem, level)
        elif tag == "p":
            self.mixed_paragraph(elem, level)
        elif tag in _TABLE_TAGS:
            self.table_wrap(elem)
        elif tag in _FIGURE_TAGS:
            self.caption_block(elem, default_label="Figure")
        elif tag in _LIST_TAGS:
            self.list_block(elem)
        elif tag in {"table-wrap-group", "fig-group", "boxed-text", "disp-quote"}:
            self.children(elem, level, skip={"label", "caption"})
        elif tag in {"disp-formula", "label", "caption", "title", "def-item", "list-item"}:
            self.paragraph(_inline_text(elem))
        else:
            # Unknown element: walk into it if it holds blocks, else keep its text,
            # so nothing silently disappears.
            if any(_local(child.tag) in _CONTAINER_HINT_TAGS for child in elem):
                self.children(elem, level)
            else:
                self.paragraph(_inline_text(elem))

    def mixed_paragraph(self, p: ET.Element, level: int) -> None:
        """A ``<p>`` may hold tables, figures or lists mid-text: split around them."""
        parts: list[str] = [p.text or ""]

        def flush() -> None:
            self.paragraph("".join(parts))
            parts.clear()

        for child in p:
            if _local(child.tag) in _BLOCK_TAGS:
                flush()
                self.block(child, level)
            else:
                parts.extend(_iter_inline(child))
            parts.append(child.tail or "")
        flush()

    def caption_block(self, elem: ET.Element, *, default_label: str) -> None:
        label = elem.find("label")
        caption = elem.find("caption")
        label_text = _inline_text(label) if label is not None else ""
        caption_parts: list[str] = []
        if caption is not None:
            for child in caption:
                text = _inline_text(child)
                if text:
                    caption_parts.append(text)
        caption_text = " ".join(caption_parts)
        if not label_text and caption_text:
            label_text = default_label
        if label_text and caption_text:
            self.paragraph(f"{label_text.rstrip('.:')}. {caption_text}")
        elif label_text or caption_text:
            self.paragraph(label_text or caption_text)

    def table_wrap(self, wrap: ET.Element) -> None:
        self.caption_block(wrap, default_label="Table")
        for table in wrap.iter("table"):
            lines = _pipe_table(table)
            if lines:
                self.blocks.append("\n".join(lines))
                if self.in_body:
                    self.body_blocks += 1
        for foot in wrap.iter("table-wrap-foot"):
            self.paragraph(_inline_text(foot))

    def list_block(self, lst: ET.Element) -> None:
        items: list[str] = []
        for item in lst:
            tag = _local(item.tag)
            if tag in {"list-item", "def-item"}:
                text = _inline_text(item)
                if text:
                    items.append(f"- {text}")
            elif tag == "title":
                self.paragraph(_inline_text(item))
        if items:
            self.blocks.append("\n".join(items))
            if self.in_body:
                self.body_blocks += 1


def _pipe_table(table: ET.Element) -> list[str]:
    """Render a JATS/XHTML table as a simple pipe table (colspan padded, rowspan ignored)."""
    rows: list[list[str]] = []
    header_rows = 0
    for section_tag in ("thead", "tbody", "tfoot"):
        for section in table.findall(section_tag):
            for tr in section.findall("tr"):
                rows.append(_row_cells(tr))
                if section_tag == "thead":
                    header_rows += 1
    for tr in table.findall("tr"):  # rows written straight under <table>
        rows.append(_row_cells(tr))
    rows = [r for r in rows if any(cell for cell in r)]
    if not rows:
        return []
    width = max(len(r) for r in rows)
    lines: list[str] = []
    split_after = max(header_rows, 1)
    for i, row in enumerate(rows):
        padded = row + [""] * (width - len(row))
        lines.append("| " + " | ".join(padded) + " |")
        if i == split_after - 1:
            lines.append("| " + " | ".join(["---"] * width) + " |")
    return lines


def _row_cells(tr: ET.Element) -> list[str]:
    cells: list[str] = []
    for cell in tr:
        if _local(cell.tag) not in {"td", "th"}:
            continue
        text = _inline_text(cell).replace("|", "\\|")
        cells.append(text)
        try:
            span = int(cell.get("colspan", "1"))
        except ValueError:
            span = 1
        cells.extend([""] * max(0, min(span, 50) - 1))
    return cells


def _render_article(root: ET.Element) -> tuple[str | None, str, int]:
    renderer = _Renderer()
    article = root
    if _local(root.tag) != "article":
        found = root.find(".//article")
        article = found if found is not None else root
    meta = article.find("front/article-meta")
    title: str | None = None
    if meta is not None:
        title_elem = meta.find("title-group/article-title")
        if title_elem is not None:
            title = _inline_text(title_elem) or None
    if title:
        renderer.heading(1, title)
    if meta is not None:
        for abstract in meta.findall("abstract"):
            abstract_title = abstract.find("title")
            heading = _inline_text(abstract_title) if abstract_title is not None else ""
            renderer.heading(2, heading or "Abstract")
            renderer.children(abstract, 3, skip={"title"})
    renderer.in_body = True
    body = article.find("body")
    if body is not None:
        renderer.children(body, 2)
    renderer.in_body = False
    back = article.find("back")
    if back is not None:
        renderer.children(back, 2)
    floats = article.find("floats-group")
    if floats is not None and len(floats):
        renderer.heading(2, "Figures and tables")
        renderer.in_body = True
        renderer.children(floats, 3)
        renderer.in_body = False
    return title, "\n\n".join(renderer.blocks) + "\n", renderer.body_blocks
