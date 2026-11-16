"""Tests for the JATS XML parser and the Europe PMC full-text fetch (task 056 N10, S7).

Zero egress: the hostile-XML tests prove no file or network access happens, and the
fetch tests use a fake httpx transport. The three real articles under
``tests/data/jats/`` are open-access CC BY files saved once (see their README).
"""

from __future__ import annotations

import hashlib
import pyexpat
import socket
import time
from pathlib import Path
from typing import Any

import httpx
import pytest

from policy_atlas.evidence_search.sourcing import fetch_live
from policy_atlas.evidence_search.sourcing.fetch_live import (
    USER_AGENT,
    LiveDocumentFetcher,
    fetch_europe_pmc_xml,
    normalise_pmcid,
)
from policy_atlas.evidence_search.sourcing.ingest_full_text import (
    _segment_markdown_pages,
    parse_and_segment,
)
from policy_atlas.evidence_search.sourcing.parse_jats import (
    JATS_PARSE_PROFILE,
    JATS_SEGMENTATION_POLICY,
    parse_jats,
)

JATS_DIR = Path(__file__).parents[2] / "data" / "jats"

_BODY = b"<body><sec><title>Introduction</title><p>Body text here, long enough.</p></sec></body>"


def _article(body: bytes, doctype: bytes = b"") -> bytes:
    return b'<?xml version="1.0"?>' + doctype + b"<article>" + body + b"</article>"


def _markdown(result: dict[str, Any]) -> str:
    assert result["status"] == "ok", result
    [(page, markdown)] = result["pages"]
    assert page == 1
    assert isinstance(markdown, str)
    return markdown


# --- Expat version and entity hardening ---


def test_expat_has_amplification_limits() -> None:
    """Expat 2.4.1 added the entity-bomb limit the parser relies on; fail loudly if older."""
    assert pyexpat.version_info >= (2, 4, 1)


def test_billion_laughs_fails_fast_without_blowing_up() -> None:
    entities = b'<!ENTITY l0 "lol">' + b"".join(
        b'<!ENTITY l%d "%s">' % (i, (b"&l%d;" % (i - 1)) * 10) for i in range(1, 10)
    )
    payload = _article(b"<body><p>&l9;</p></body>", b"<!DOCTYPE article [" + entities + b"]>")
    started = time.monotonic()
    result = parse_jats(payload)
    elapsed = time.monotonic() - started
    # "Fast" means seconds, not the minutes a real bomb takes; loose for a loaded suite.
    assert elapsed < 10.0
    assert result["status"] == "error"
    assert result["reason"] == "corrupt"
    assert "amplification" in result["detail"]


def test_quadratic_blowup_fails_fast() -> None:
    doctype = b'<!DOCTYPE article [<!ENTITY a "' + b"x" * 100_000 + b'">]>'
    payload = _article(b"<body><p>" + b"&a;" * 100_000 + b"</p></body>", doctype)
    started = time.monotonic()
    result = parse_jats(payload)
    assert time.monotonic() - started < 2.0
    assert result["status"] == "error"
    assert result["reason"] == "corrupt"


class _ConnectRecorder:
    """Stands in for the socket module's connect paths and records any attempt."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def record(self, name: str) -> Any:
        def _fn(*args: Any, **kwargs: Any) -> Any:
            self.calls.append((name, args))
            raise OSError("network disabled in this test")

        return _fn


@pytest.fixture
def connect_recorder(monkeypatch: pytest.MonkeyPatch) -> _ConnectRecorder:
    recorder = _ConnectRecorder()
    monkeypatch.setattr(socket, "getaddrinfo", recorder.record("getaddrinfo"))
    monkeypatch.setattr(socket, "create_connection", recorder.record("create_connection"))
    monkeypatch.setattr(socket.socket, "connect", recorder.record("connect"))
    return recorder


def test_external_file_entity_is_not_resolved(
    tmp_path: Path, connect_recorder: _ConnectRecorder
) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP-SECRET-MARKER-5f1c")
    for target in (secret.as_uri(), "file:///etc/passwd"):
        doctype = b'<!DOCTYPE article [<!ENTITY x SYSTEM "' + target.encode() + b'">]>'
        result = parse_jats(_article(_BODY.replace(b"Body", b"&x; Body"), doctype))
        assert result["status"] == "error"
        assert result["reason"] == "corrupt"
        assert "TOP-SECRET-MARKER" not in repr(result)
        assert "root:" not in repr(result)
    assert connect_recorder.calls == []


def test_external_http_entity_makes_no_network_call(connect_recorder: _ConnectRecorder) -> None:
    for system_id in (b"http://example.com/x.ent", b"https://127.0.0.1:9/x.ent"):
        doctype = b'<!DOCTYPE article [<!ENTITY x SYSTEM "' + system_id + b'">]>'
        result = parse_jats(_article(_BODY.replace(b"Body", b"&x; Body"), doctype))
        assert result["status"] == "error"
        assert result["reason"] == "corrupt"
    assert connect_recorder.calls == []


def test_external_entity_and_dtd_never_reach_a_live_listener() -> None:
    """A real loopback server (allowed by pytest-socket) sees no connection at all."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(4)
    server.settimeout(0.3)
    port = server.getsockname()[1]
    url = f"http://127.0.0.1:{port}".encode()
    payloads = [
        _article(_BODY.replace(b"Body", b"&x; Body"),
                 b'<!DOCTYPE article [<!ENTITY x SYSTEM "' + url + b'/x.ent">]>'),
        _article(_BODY, b'<!DOCTYPE article [<!ENTITY % p SYSTEM "' + url + b'/p.dtd"> %p;]>'),
        _article(_BODY, b'<!DOCTYPE article PUBLIC "-//NLM//DTD JATS" "' + url + b'/jats.dtd">'),
    ]
    try:
        for payload in payloads:
            parse_jats(payload)
        with pytest.raises(TimeoutError):
            server.accept()
    finally:
        server.close()


def test_external_dtd_is_ignored_and_undefined_entities_are_replaced() -> None:
    doctype = b'<!DOCTYPE article PUBLIC "-//NLM//DTD JATS" "http://example.com/jats.dtd">'
    body = _BODY.replace(b"Body", b"A&ndash;B &mdash; C&nbsp;D &unknownthing; Body")
    markdown = _markdown(parse_jats(_article(body, doctype)))
    assert "A–B — C D � Body text here" in markdown


def test_undefined_entities_without_doctype_are_not_fatal() -> None:
    body = _BODY.replace(b"Body", b"x &hellip; &zzz; &amp; &lt;tag&gt; Body")
    markdown = _markdown(parse_jats(_article(body)))
    assert "x … � & <tag> Body text here" in markdown


def test_declared_internal_entity_is_expanded_by_expat() -> None:
    doctype = b'<!DOCTYPE article [<!ENTITY org "Nesta">]>'
    markdown = _markdown(parse_jats(_article(_BODY.replace(b"Body", b"&org; Body"), doctype)))
    assert "Nesta Body text here" in markdown


# --- Per-document failures never raise ---


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        (b"", "corrupt"),
        (b"not xml at all", "corrupt"),
        (b"<article><body><p>unclosed</body></article>", "corrupt"),
        (b"<article><body>" + b"<sec>" * 50_000 + b"<p>x</p>" + b"</sec>" * 50_000
         + b"</body></article>", "corrupt"),
        (b"<article><front><article-meta><abstract><p>Only an abstract.</p></abstract>"
         b"</article-meta></front></article>", "empty"),
    ],
    ids=["empty-bytes", "not-xml", "malformed", "too-deep", "abstract-only"],
)
def test_bad_documents_come_back_as_errors(payload: bytes, reason: str) -> None:
    result = parse_jats(payload)
    assert result["status"] == "error"
    assert result["reason"] == reason
    assert isinstance(result["detail"], str) and result["detail"]


# --- Rendering shape ---


def test_rendering_shape_on_a_small_article() -> None:
    xml = b"""<article><front><article-meta>
      <title-group><article-title>A <italic>small</italic> study</article-title></title-group>
      <abstract><sec><title>Background</title><p>Why.</p></sec></abstract>
    </article-meta></front>
    <body>
      <sec><label>1</label><title>Methods</title>
        <p>We did # things | here.</p>
        <sec><title>Design</title>
          <p>Before the table.<table-wrap><label>Table 1</label><caption><p>Results.</p></caption>
            <table><thead><tr><th>Arm</th><th colspan="2">Outcome</th></tr></thead>
            <tbody><tr><td>A</td><td>1|2</td><td>3<break/>4</td></tr></tbody></table>
          </table-wrap>After the table.</p>
          <fig><label>Figure 2</label><caption><title>Flow.</title><p>Detail.</p></caption>
            <graphic/></fig>
          <list><list-item><p>one</p></list-item><list-item><p>two</p></list-item></list>
        </sec>
      </sec>
    </body>
    <back><ack><title>Acknowledgements</title><p>Thanks.</p></ack>
      <ref-list><title>References</title>
        <ref><mixed-citation>Cited 2020.</mixed-citation></ref></ref-list>
    </back></article>"""
    result = parse_jats(xml)
    assert result["title"] == "A small study"
    assert result["parse_profile"] == JATS_PARSE_PROFILE
    assert result["segmentation_policy"] == JATS_SEGMENTATION_POLICY
    assert _markdown(result) == (
        "# A small study\n\n"
        "## Abstract\n\n"
        "### Background\n\n"
        "Why.\n\n"
        "## 1 Methods\n\n"
        "We did # things | here.\n\n"
        "### Design\n\n"
        "Before the table.\n\n"
        "Table 1. Results.\n\n"
        "| Arm | Outcome |  |\n"
        "| --- | --- | --- |\n"
        "| A | 1\\|2 | 3 4 |\n\n"
        "After the table.\n\n"
        "Figure 2. Flow. Detail.\n\n"
        "- one\n- two\n\n"
        "## Acknowledgements\n\n"
        "Thanks.\n"
    )


def test_text_that_looks_like_markdown_structure_is_escaped() -> None:
    xml = _article(b"<body><p># not a heading</p><p>| not a table</p></body>")
    markdown = _markdown(parse_jats(xml))
    assert markdown == "\\# not a heading\n\n\\| not a table\n"
    chunks = _segment_markdown_pages([(1, markdown)])
    # The escape keeps the lines body text; parse profile v2's markup rule then turns
    # the escaped characters back into plain ones in the chunk (task 057, N7).
    assert [c["content"] for c in chunks] == ["# not a heading\n\n| not a table"]
    assert [c["locator"]["heading_path"] for c in chunks] == [[]]


def test_markup_in_jats_text_is_stripped_at_segmentation() -> None:
    """Markup written into the article's text (not XML tags) leaves the chunk text and
    the heading path under parse profile v2 (task 057, N7)."""
    xml = _article(
        b"<body><sec><title>**Main** results</title>"
        b"<p>The effect was **large** (see [the appendix](https://example.org/a))"
        b" and _robust_ &lt;br&gt;across sites.</p>"
        b"<table-wrap><table><tr><td>`A`</td><td>1&lt;br&gt;2</td></tr></table></table-wrap>"
        b"</sec></body>"
    )
    result = parse_and_segment(xml, "application/xml", 0)
    assert result["status"] == "ok", result
    assert result["parse_profile"] == JATS_PARSE_PROFILE == "jats_expat_v2"
    assert result["segmentation_policy"] == JATS_SEGMENTATION_POLICY == "jats_struct_v2"
    assert [(c["content"], c["locator"]["heading_path"]) for c in result["chunks"]] == [
        # A table is cut as soon as it ends; its section's text follows (as in v1).
        ("| A | 1 2 |\n| --- | --- |", ["Main results"]),
        ("The effect was large (see the appendix) and robust\nacross sites.", ["Main results"]),
    ]


# --- Real articles ---

# sha256 of the markdown parse_jats produces for each saved article. A deliberate
# parser change updates these after the new output has been read by eye.
GOLDEN_DIGESTS = {
    "PMC11210863.xml": "3d076bc628440430ebf01aa620527795a4d4b85c90bf840713e93d366c763024",
    "PMC5264339.xml": "80da24c58365841ee7bb3fd4f9448432d40e4d3a85af790b4fefc79640b4c2e1",
    "PMC11218303.xml": "ef560d1b4ee9c70ef83587f765854499d8f10fc8379882993f3e75f0c5d11850",
}


@pytest.mark.parametrize("name", sorted(GOLDEN_DIGESTS))
def test_real_article_yields_headings_paragraphs_and_tables(name: str) -> None:
    result = parse_jats((JATS_DIR / name).read_bytes())
    markdown = _markdown(result)
    assert result["title"]
    assert markdown.startswith(f"# {result['title']}\n")
    headings = [line for line in markdown.splitlines() if line.startswith("#")]
    assert len(headings) >= 3
    assert "## Abstract" in headings
    assert not any(line.strip() == "## References" for line in headings)

    chunks = _segment_markdown_pages(result["pages"])
    tables = [c for c in chunks if c["content"].startswith("| ")]
    prose = [c for c in chunks if not c["content"].startswith("| ")]
    assert len(tables) >= 1  # each of the three saved articles has tables
    assert all("| --- |" in t["content"] for t in tables)
    assert len(prose) >= 5
    assert any(len(c["locator"]["heading_path"]) >= 2 for c in chunks)
    assert hashlib.sha256(markdown.encode()).hexdigest() == GOLDEN_DIGESTS[name]


# --- Europe PMC fetch ---


class _RecordingTransport(httpx.BaseTransport):
    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        self.requests: list[httpx.Request] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.response


def test_fetch_sends_only_the_id_in_the_path() -> None:
    body = b'<?xml version="1.0"?><article/>'
    transport = _RecordingTransport(httpx.Response(200, content=body))
    assert fetch_europe_pmc_xml("PMC5264339", timeout=5.0, transport=transport) == body
    [request] = transport.requests
    assert request.method == "GET"
    assert str(request.url) == (
        "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC5264339/fullTextXML"
    )
    assert request.url.query == b""
    assert request.content == b""
    assert "cookie" not in request.headers
    assert request.headers["user-agent"] == USER_AGENT


@pytest.mark.parametrize(
    "pmcid",
    [
        "", "5264339", "pmc5264339", "PMC", "PMC12a", "PMC1/../../x", "PMC1?q=1", "PMC1 ",
        None, 5264339,
    ],
)
def test_fetch_refuses_an_invalid_id_without_a_request(pmcid: Any) -> None:
    transport = _RecordingTransport(httpx.Response(200, content=b"<article/>"))
    assert fetch_europe_pmc_xml(pmcid, timeout=5.0, transport=transport) is None
    assert transport.requests == []


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(404, content=b"<error/>"),
        httpx.Response(302, headers={"location": "https://example.com/"}),
        httpx.Response(500, content=b"oops"),
        httpx.Response(200, content=b"<!DOCTYPE html><html><body>Not found</body></html>"),
        httpx.Response(200, content=b'{"error": "no full text"}'),
        httpx.Response(200, content=b""),
    ],
    ids=["404", "redirect", "500", "html", "json", "empty"],
)
def test_fetch_returns_none_for_missing_or_non_xml(response: httpx.Response) -> None:
    transport = _RecordingTransport(response)
    assert fetch_europe_pmc_xml("PMC1", timeout=5.0, transport=transport) is None
    assert len(transport.requests) == 1


def test_fetch_returns_none_when_the_transport_fails() -> None:
    class _Failing(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("down", request=request)

    assert fetch_europe_pmc_xml("PMC1", timeout=5.0, transport=_Failing()) is None


def test_fetch_refuses_a_body_over_the_xml_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    """The XML route has its own, lower cap than PDFs (review of task 056)."""
    monkeypatch.setattr(fetch_live, "EUROPE_PMC_MAX_BYTES", 8)
    transport = _RecordingTransport(httpx.Response(200, content=b"<article>long</article>"))
    assert fetch_europe_pmc_xml("PMC1", timeout=5.0, transport=transport) is None


def test_live_fetcher_puts_the_xml_body_on_the_byte_budget() -> None:
    """An XML body counts against the shared in-flight budget until the ingest
    loop releases it, like every PDF or HTML body (review of task 056)."""
    body = b'<?xml version="1.0"?><article/>'
    fetcher = LiveDocumentFetcher(
        resolver=lambda host, port: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))
        ],
        sleep=lambda _s: None,
        transport=_RecordingTransport(httpx.Response(200, content=body)),
    )
    assert fetcher.fetch_europe_pmc_xml("PMC5264339") == body
    assert fetcher._inflight_bytes == len(body)
    fetcher.release_body(len(body))
    assert fetcher._inflight_bytes == 0


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://www.ncbi.nlm.nih.gov/pmc/articles/5264339", "PMC5264339"),
        ("https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5264339/", "PMC5264339"),
        ("PMC5264339", "PMC5264339"),
        ("pmc5264339", "PMC5264339"),
        ("5264339", "PMC5264339"),
        ("https://doi.org/10.1186/s13643-016-0394-2", None),
        ("", None),
        (None, None),
    ],
)
def test_normalise_pmcid(value: Any, expected: str | None) -> None:
    assert normalise_pmcid(value) == expected
