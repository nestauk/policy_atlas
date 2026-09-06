"""Transport matrix for the live search backends — sanitizers, limiter, timeout,
retry/redaction, shape validation, ``next_page_url`` guard, the OA_SELECT superset,
no-citation-floor, the ``squery``/``min_similarity`` wire contract, verb mechanics
and ``live_search_backends`` key checks.

Every test injects a fetch callable — zero real sockets, no sleeps (``_sleep`` is
monkeypatched to a recorder), no RNG.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from policy_atlas.evidence_search.sourcing import search_live
from policy_atlas.evidence_search.sourcing.acquire import (
    _OPENALEX_RETAIN_KEYS,
    _map_openalex_work,
    _map_overton_document,
)
from policy_atlas.evidence_search.sourcing.search_live import (
    HTTP_TIMEOUT_S,
    OA_SELECT,
    OVERTON_MIN_INTERVAL_S,
    RETRY_BACKOFF_S,
    OpenAlexLiveBackend,
    OvertonLiveBackend,
    SearchTransportError,
    live_search_backends,
    sanitize_openalex_query,
    sanitize_title_query,
)


def _sleep_recorder(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    calls: list[float] = []
    monkeypatch.setattr(search_live, "_sleep", calls.append)
    return calls


def _oa_stub_record(rid: str = "https://example.org/W1") -> dict[str, Any]:
    return {"id": rid, "display_name": "Stub title"}


def _overton_stub_record(rid: str, country: str | None) -> dict[str, Any]:
    record: dict[str, Any] = {"policy_document_id": rid, "title": f"Title {rid}"}
    if country is not None:
        record["source"] = {"country": country}
    return record


def _status_error(status_code: int, host: str = "api.openalex.org") -> httpx.HTTPStatusError:
    url = f"https://{host}/works?api_key=SECRET123"
    request = httpx.Request("GET", url)
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(f"status {status_code}", request=request, response=response)


def _timeout_error(host: str = "api.openalex.org") -> httpx.TimeoutException:
    url = f"https://{host}/works?api_key=SECRET123"
    request = httpx.Request("GET", url)
    return httpx.TimeoutException("timed out", request=request)


@pytest.fixture(autouse=True)
def _clear_search_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    search_live._SEARCH_CACHE.clear()
    monkeypatch.delenv("POLICY_ATLAS_SEARCH_CACHE_TTL_S", raising=False)


# --- sanitize_openalex_query / sanitize_title_query ---


def test_sanitize_openalex_query_strips_wildcards() -> None:
    assert sanitize_openalex_query("clim*ate ch?ange re~gulation") == "climate change regulation"


# Replaces the rev-1 commas-only-inside-quotes pin: commas are the OpenAlex
# filter-clause separator, so NONE may survive into the embedded search value
# (015 review: comma-borne filter injection, Codex + security lanes convergent).
def test_sanitize_openalex_query_replaces_all_commas() -> None:
    assert (
        sanitize_openalex_query('"systematic review, meta" analysis, policy')
        == '"systematic review meta" analysis policy'
    )


def test_openalex_comma_query_cannot_inject_filter_clause() -> None:
    captured: list[dict[str, str]] = []

    def fetch(url: str, params: dict[str, str]) -> Any:
        captured.append(dict(params))
        return {"results": []}

    backend = OpenAlexLiveBackend("KEY", fetch=fetch)
    backend.search("housing policy,is_retracted:true", max_results=5)

    assert len(captured) == 1
    assert (
        captured[0]["filter"]
        == "title_and_abstract.search:housing policy is_retracted:true"
    )


def test_openalex_query_naming_cited_by_count_is_data_not_floor() -> None:
    captured: list[dict[str, str]] = []

    def fetch(url: str, params: dict[str, str]) -> Any:
        captured.append(dict(params))
        return {"results": []}

    backend = OpenAlexLiveBackend("KEY", fetch=fetch)
    backend.search("trends in cited_by_count metrics", max_results=5)

    assert len(captured) == 1
    assert captured[0]["filter"].startswith("title_and_abstract.search:")


def test_sanitize_openalex_query_collapses_whitespace() -> None:
    assert sanitize_openalex_query("  climate   policy  ") == "climate policy"


def test_sanitize_title_query_strips_additional_punctuation() -> None:
    assert (
        sanitize_title_query("Climate, Policy: (A Review) - 2020")
        == "Climate Policy A Review 2020"
    )


# --- Search-response cache ---


def test_search_cache_hit_skips_transport_and_overton_limiter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps = _sleep_recorder(monkeypatch)
    calls: list[tuple[str, dict[str, str]]] = []

    def fetch(url: str, params: dict[str, str]) -> Any:
        calls.append((url, dict(params)))
        return {"results": [_overton_stub_record("p1", "UK")]}

    backend = OvertonLiveBackend("KEY", fetch=fetch)

    first = backend.search("housing policy", max_results=1)
    second = backend.search("housing policy", max_results=1)

    assert first == second
    assert len(calls) == 1
    assert backend.http_calls == 1
    assert sleeps == []


def test_search_cache_ttl_expiry_refetches(monkeypatch: pytest.MonkeyPatch) -> None:
    now = {"value": 0.0}
    monkeypatch.setattr(search_live, "_monotonic", lambda: now["value"])
    calls = {"n": 0}

    def fetch(url: str, params: dict[str, str]) -> Any:
        del url, params
        calls["n"] += 1
        return {"results": [_oa_stub_record(f"https://example.org/W{calls['n']}")]}

    backend = OpenAlexLiveBackend("KEY", fetch=fetch)

    assert backend.search("policy", max_results=1)[0]["id"] == "https://example.org/W1"
    now["value"] = 3599.0
    assert backend.search("policy", max_results=1)[0]["id"] == "https://example.org/W1"
    now["value"] = 3601.0
    assert backend.search("policy", max_results=1)[0]["id"] == "https://example.org/W2"
    assert calls["n"] == 2


def test_search_cache_different_params_miss() -> None:
    calls: list[dict[str, str]] = []

    def fetch(url: str, params: dict[str, str]) -> Any:
        del url
        calls.append(dict(params))
        return {"results": []}

    backend = OpenAlexLiveBackend("KEY", fetch=fetch)
    backend.search("policy", wire_params={"filter": "publication_year:2020"}, max_results=1)
    backend.search("policy", wire_params={"filter": "publication_year:2021"}, max_results=1)

    assert len(calls) == 2


def test_search_cache_error_response_not_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    _sleep_recorder(monkeypatch)
    calls = {"n": 0}

    def fetch(url: str, params: dict[str, str]) -> Any:
        del url, params
        calls["n"] += 1
        if calls["n"] <= 2:
            raise _status_error(429)
        return {"results": []}

    backend = OpenAlexLiveBackend("KEY", fetch=fetch)
    with pytest.raises(SearchTransportError):
        backend.search("policy", max_results=1)

    assert backend.search("policy", max_results=1) == []
    assert calls["n"] == 3


def test_search_cache_malformed_payload_not_cached() -> None:
    responses: list[Any] = [{"results": "oops"}, {"results": []}]

    def fetch(url: str, params: dict[str, str]) -> Any:
        del url, params
        return responses.pop(0)

    backend = OpenAlexLiveBackend("KEY", fetch=fetch)
    with pytest.raises(SearchTransportError):
        backend.search("policy", max_results=1)

    assert backend.search("policy", max_results=1) == []
    assert responses == []


def test_search_cache_disable_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLICY_ATLAS_SEARCH_CACHE_TTL_S", "0")
    calls = {"n": 0}

    def fetch(url: str, params: dict[str, str]) -> Any:
        del url, params
        calls["n"] += 1
        return {"results": []}

    backend = OpenAlexLiveBackend("KEY", fetch=fetch)
    backend.search("policy", max_results=1)
    backend.search("policy", max_results=1)

    assert calls["n"] == 2


def test_search_cache_covers_validated_next_page_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps = _sleep_recorder(monkeypatch)
    calls: list[tuple[str, dict[str, str]]] = []
    next_url = "https://app.overton.io/documents.php?page=2&api_key=SECRET"

    def fetch(url: str, params: dict[str, str]) -> Any:
        calls.append((url, dict(params)))
        if url == next_url:
            return {"results": [_overton_stub_record("p2", "UK")]}
        return {
            "results": [_overton_stub_record("p1", "UK")],
            "next_page_url": next_url,
        }

    backend = OvertonLiveBackend("KEY", fetch=fetch)

    first = backend.search("housing policy", max_results=2)
    second = backend.search("housing policy", max_results=2)

    assert [record["policy_document_id"] for record in first] == ["p1", "p2"]
    assert first == second
    assert len(calls) == 2
    assert len(sleeps) == 1


def test_search_cache_key_excludes_credentials_and_sorts_params() -> None:
    key = search_live._search_cache_key(
        "https://app.overton.io/documents.php?api_key=SECRET&page=2&b=2",
        {"mailto": "person@example.org", "a": "1"},
    )

    assert key == (
        "https",
        "app.overton.io",
        "/documents.php",
        (("a", "1"), ("b", "2"), ("page", "2")),
    )


# --- Overton limiter ---


def test_overton_limiter_sleeps_between_consecutive_search_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps = _sleep_recorder(monkeypatch)
    backend = OvertonLiveBackend("KEY", fetch=lambda url, params: {"results": []})

    backend.search("housing policy", max_results=1)
    assert sleeps == []  # first-ever request never waits

    backend.search("housing policy updated", max_results=1)
    assert len(sleeps) == 1
    assert 0 < sleeps[0] <= OVERTON_MIN_INTERVAL_S


def test_overton_limiter_gates_next_page_url_follow(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps = _sleep_recorder(monkeypatch)
    calls: list[tuple[str, dict[str, str]]] = []

    def fetch(url: str, params: dict[str, str]) -> Any:
        calls.append((url, dict(params)))
        if len(calls) == 1:
            return {
                "results": [{"policy_document_id": "p1", "title": "T1"}],
                "next_page_url": "https://app.overton.io/documents.php?page=2",
            }
        return {"results": [{"policy_document_id": "p2", "title": "T2"}]}

    backend = OvertonLiveBackend("KEY", fetch=fetch)
    records = backend.search("housing policy", max_results=2)

    assert len(records) == 2
    assert len(calls) == 2
    assert len(sleeps) == 1
    assert 0 < sleeps[0] <= OVERTON_MIN_INTERVAL_S


def test_overton_source_country_post_filter_paginates_until_quota(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _sleep_recorder(monkeypatch)
    calls: list[tuple[str, dict[str, str]]] = []

    def fetch(url: str, params: dict[str, str]) -> Any:
        calls.append((url, dict(params)))
        if len(calls) == 1:
            return {
                "results": [
                    _overton_stub_record("p1", "UK"),
                    _overton_stub_record("p2", "IGO"),
                    _overton_stub_record("p3", None),
                ],
                "next_page_url": "https://app.overton.io/documents.php?page=2",
            }
        return {
            "results": [
                _overton_stub_record("p4", "France"),
                _overton_stub_record("p5", "USA"),
                _overton_stub_record("p6", "UK"),
            ]
        }

    backend = OvertonLiveBackend("KEY", fetch=fetch)
    records = backend.search_with_post_filter(
        "housing policy",
        wire_params={"published_after": "2020-01-01"},
        source_country_post_filter=["UK", "France"],
        max_results=3,
    )

    assert [record["policy_document_id"] for record in records] == ["p1", "p4", "p6"]
    assert backend.last_post_filter_excluded == 3
    assert len(calls) == 2
    assert calls[0][1]["published_after"] == "2020-01-01"
    assert "source_country" not in calls[0][1]
    assert "source_country_post_filter" not in calls[0][1]


# --- Timeout ---


@pytest.mark.parametrize("backend_cls", [OpenAlexLiveBackend, OvertonLiveBackend])
def test_default_client_carries_pinned_timeout(
    backend_cls: type[OpenAlexLiveBackend] | type[OvertonLiveBackend],
) -> None:
    backend = backend_cls("KEY")
    assert backend._client is not None
    assert backend._client.timeout == httpx.Timeout(HTTP_TIMEOUT_S)
    backend._client.close()


# --- Retry: retryable statuses + timeout ---


@pytest.mark.parametrize(
    "make_exc",
    [
        lambda: _status_error(429),
        lambda: _status_error(500),
        lambda: _status_error(502),
        lambda: _status_error(503),
        lambda: _status_error(504),
        lambda: _timeout_error(),
    ],
)
def test_retry_once_then_succeed(
    monkeypatch: pytest.MonkeyPatch, make_exc: Callable[[], Exception]
) -> None:
    sleeps = _sleep_recorder(monkeypatch)
    calls = {"n": 0}

    def fetch(url: str, params: dict[str, str]) -> Any:
        calls["n"] += 1
        if calls["n"] == 1:
            raise make_exc()
        return {"results": [_oa_stub_record()]}

    backend = OpenAlexLiveBackend("KEY", fetch=fetch)
    records = backend.search("policy", max_results=1)

    assert len(records) == 1
    assert calls["n"] == 2
    assert sleeps == [RETRY_BACKOFF_S]


@pytest.mark.parametrize(
    "make_exc",
    [
        lambda: _status_error(429),
        lambda: _status_error(500),
        lambda: _status_error(502),
        lambda: _status_error(503),
        lambda: _status_error(504),
        lambda: _timeout_error(),
    ],
)
def test_retry_fails_twice_raises_search_transport_error(
    monkeypatch: pytest.MonkeyPatch, make_exc: Callable[[], Exception]
) -> None:
    _sleep_recorder(monkeypatch)
    calls = {"n": 0}

    def fetch(url: str, params: dict[str, str]) -> Any:
        calls["n"] += 1
        raise make_exc()

    backend = OpenAlexLiveBackend("KEY", fetch=fetch)
    with pytest.raises(SearchTransportError) as excinfo:
        backend.search("policy", max_results=1)
    assert calls["n"] == 2

    message = str(excinfo.value)
    assert "api.openalex.org" in message
    assert "SECRET123" not in message
    assert "api_key" not in message


def test_400_status_error_no_retry_immediate_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps = _sleep_recorder(monkeypatch)
    calls = {"n": 0}

    def fetch(url: str, params: dict[str, str]) -> Any:
        calls["n"] += 1
        raise _status_error(400)

    backend = OpenAlexLiveBackend("KEY", fetch=fetch)
    with pytest.raises(SearchTransportError) as excinfo:
        backend.search("policy", max_results=1)

    assert calls["n"] == 1  # no retry for a non-retryable status
    assert sleeps == []
    message = str(excinfo.value)
    assert "api.openalex.org" in message
    assert "400" in message
    assert "SECRET123" not in message


# --- Shape validation ---


@pytest.mark.parametrize(
    "bad_payload",
    [
        ["not", "a", "dict"],
        {},
        {"results": "oops"},
        {"results": [{"id": "W1"}, "bad_item"]},
    ],
)
def test_shape_validation_rejects_malformed_openalex_response(
    monkeypatch: pytest.MonkeyPatch, bad_payload: Any
) -> None:
    _sleep_recorder(monkeypatch)
    backend = OpenAlexLiveBackend("KEY", fetch=lambda url, params: bad_payload)
    with pytest.raises(SearchTransportError):
        backend.search("policy", max_results=1)


def test_overton_next_page_url_false_tolerated_single_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _sleep_recorder(monkeypatch)

    def fetch(url: str, params: dict[str, str]) -> Any:
        return {
            "results": [{"policy_document_id": "p1", "title": "T1"}],
            "next_page_url": False,
        }

    backend = OvertonLiveBackend("KEY", fetch=fetch)
    records = backend.search("housing", max_results=50)
    assert len(records) == 1


def test_overton_empty_page_with_next_page_url_does_not_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A zero-record page advertising next_page_url must not be followed:
    # zero progress per iteration means unbounded egress against a buggy or
    # hostile endpoint (015 security lane).
    _sleep_recorder(monkeypatch)
    calls: list[str] = []

    def fetch(url: str, params: dict[str, str]) -> Any:
        calls.append(url)
        return {
            "results": [],
            "next_page_url": "https://app.overton.io/documents.php?page=2",
        }

    backend = OvertonLiveBackend("KEY", fetch=fetch)
    records = backend.search("housing policy", max_results=10)

    assert records == []
    assert len(calls) == 1


# --- next_page_url guard ---


def test_next_page_url_http_scheme_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _sleep_recorder(monkeypatch)
    calls: list[str] = []

    def fetch(url: str, params: dict[str, str]) -> Any:
        calls.append(url)
        return {
            "results": [{"policy_document_id": "p1", "title": "T1"}],
            "next_page_url": "http://app.overton.io/documents.php?page=2",
        }

    backend = OvertonLiveBackend("KEY", fetch=fetch)
    with pytest.raises(SearchTransportError):
        backend.search("housing", max_results=5)


def test_next_page_url_wrong_host_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _sleep_recorder(monkeypatch)

    def fetch(url: str, params: dict[str, str]) -> Any:
        return {
            "results": [{"policy_document_id": "p1", "title": "T1"}],
            "next_page_url": "https://evil.example.com/documents.php?page=2",
        }

    backend = OvertonLiveBackend("KEY", fetch=fetch)
    with pytest.raises(SearchTransportError):
        backend.search("housing", max_results=5)


def test_next_page_url_valid_followed_verbatim(monkeypatch: pytest.MonkeyPatch) -> None:
    _sleep_recorder(monkeypatch)
    calls: list[tuple[str, dict[str, str]]] = []
    next_url = "https://app.overton.io/documents.php?page=2&extra=1"

    def fetch(url: str, params: dict[str, str]) -> Any:
        calls.append((url, dict(params)))
        if len(calls) == 1:
            return {
                "results": [{"policy_document_id": "p1", "title": "T1"}],
                "next_page_url": next_url,
            }
        return {"results": []}

    backend = OvertonLiveBackend("KEY", fetch=fetch)
    backend.search("housing", max_results=5)

    assert calls[1][0] == next_url
    assert calls[1][1] == {}


def test_next_page_url_query_survives_real_httpx_url_building(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The next-page follow must reach the wire with its query string intact.

    Regression guard for a live-only 302: every other test in this module
    injects a ``fetch`` double that keys off ``url`` and ignores ``params``,
    so none of them exercise httpx's URL building — where handing ``params`` to
    ``.get()`` REPLACES (blanks) a URL's existing query instead of merging into
    it. That stripped the api_key, squery and page off the validated
    ``next_page_url``, and Overton redirected the resulting bare,
    unauthenticated request. This test drives the real transport so the merge
    behaviour is covered.

    The non-empty case is asserted too: guarding only the empty-dict case (the
    original ``params or None`` fix) left the same hazard live for any future
    caller that passes a param alongside a query-bearing URL.
    """
    _sleep_recorder(monkeypatch)
    next_url = "https://app.overton.io/documents.php?page=2&api_key=KEY&squery=housing"
    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        if len(seen) == 1:
            return httpx.Response(
                200,
                json={
                    "results": [_overton_stub_record("p1", "UK")],
                    "next_page_url": next_url,
                },
            )
        return httpx.Response(200, json={"results": [_overton_stub_record("p2", "UK")]})

    backend = OvertonLiveBackend("KEY")
    assert backend._client is not None
    backend._client.close()
    # Real httpx client + client-side transport: URL building is genuine, no sockets.
    backend._client = httpx.Client(transport=httpx.MockTransport(handler))

    try:
        records = backend.search("housing", max_results=100)

        assert [record["policy_document_id"] for record in records] == ["p1", "p2"]
        assert len(seen) == 2
        followed = seen[1]
        assert followed.params.get("page") == "2"
        assert followed.params.get("api_key") == "KEY"
        assert followed.params.get("squery") == "housing"

        # A non-empty params dict must MERGE through the real fetch path, not
        # blank the URL's own query: the credential has to survive alongside the
        # added param. Guarding only the empty case left this broken.
        backend._default_fetch(next_url, {"pp": "50"})
        assert len(seen) == 3
        with_param = seen[2]
        assert with_param.params.get("api_key") == "KEY"
        assert with_param.params.get("squery") == "housing"
        assert with_param.params.get("pp") == "50"
    finally:
        backend._client.close()


# --- OA_SELECT superset ---


def test_oa_select_is_superset_of_everything_the_mapper_reads() -> None:
    envelope_sources = {
        "id",
        "display_name",
        "abstract_inverted_index",
        "publication_year",
        "publication_date",
        "doi",
        "language",
        "type",
    }
    required = envelope_sources | set(_OPENALEX_RETAIN_KEYS) | {"authorships", "referenced_works"}
    assert required <= set(OA_SELECT)


# --- No citation floor ---


def test_no_citation_floor_across_all_verbs(monkeypatch: pytest.MonkeyPatch) -> None:
    _sleep_recorder(monkeypatch)
    calls: list[tuple[str, dict[str, str]]] = []

    def fetch(url: str, params: dict[str, str]) -> Any:
        calls.append((url, dict(params)))
        return {"results": [_oa_stub_record()]}

    backend = OpenAlexLiveBackend("KEY", fetch=fetch)
    backend.search("policy", max_results=1)
    backend.fetch_citations("W1", max_results=1)
    backend.fetch_references(["W1", "W2"], max_results=1)
    backend.lookup_title("policy title")
    backend.lookup_dois(["10.99999/aa"], max_results=1)

    assert calls
    for _url, params in calls:
        assert "cited_by_count" not in params.get("filter", "")


def test_openalex_wire_params_cited_by_count_filter_rejected() -> None:
    backend = OpenAlexLiveBackend("KEY", fetch=lambda url, params: {"results": []})
    with pytest.raises(ValueError, match="cited_by_count"):
        backend.search("policy", wire_params={"filter": "cited_by_count:>5"})


# --- squery + min_similarity wire contract, transport side ---


def test_overton_search_carries_squery_and_min_similarity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _sleep_recorder(monkeypatch)
    calls: list[dict[str, str]] = []

    def fetch(url: str, params: dict[str, str]) -> Any:
        calls.append(dict(params))
        return {"results": []}

    backend = OvertonLiveBackend("KEY", fetch=fetch)
    backend.search("housing policy", max_results=5)

    assert calls
    for params in calls:
        assert params["squery"] == "housing policy"
        assert params["min_similarity"] == "0.3"


def test_openalex_fetches_never_carry_squery_or_min_similarity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _sleep_recorder(monkeypatch)
    calls: list[dict[str, str]] = []

    def fetch(url: str, params: dict[str, str]) -> Any:
        calls.append(dict(params))
        return {"results": [_oa_stub_record()]}

    backend = OpenAlexLiveBackend("KEY", fetch=fetch)
    backend.search("policy", max_results=1)
    backend.fetch_citations("W1", max_results=1)
    backend.lookup_title("policy")

    assert calls
    for params in calls:
        assert "squery" not in params
        assert "min_similarity" not in params


# --- Mapper-consumable ---


def test_openalex_live_records_feed_mapper_without_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _sleep_recorder(monkeypatch)
    fixture = json.loads(
        (
        Path(__file__).resolve().parents[2] / "data" / "provider_records" / "openalex_works.json"
    ).read_text()
    )
    records = fixture["records"]
    backend = OpenAlexLiveBackend("KEY", fetch=lambda url, params: {"results": records})
    fetched = backend.search("policy", max_results=len(records))
    assert fetched
    for record in fetched:
        _map_openalex_work(record)  # must not raise


def test_overton_live_records_feed_mapper_without_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _sleep_recorder(monkeypatch)
    fixture = json.loads(
        (
        Path(__file__).resolve().parents[2] / "data" / "provider_records" / "overton_documents.json"
    ).read_text()
    )
    records = fixture["records"]
    backend = OvertonLiveBackend("KEY", fetch=lambda url, params: {"results": records})
    fetched = backend.search("housing policy", max_results=len(records))
    assert fetched
    for record in fetched:
        _map_overton_document(record)  # must not raise


# --- Verb mechanics ---


def test_fetch_references_chunks_over_50_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    _sleep_recorder(monkeypatch)
    calls: list[dict[str, str]] = []

    def fetch(url: str, params: dict[str, str]) -> Any:
        calls.append(dict(params))
        return {"results": []}

    backend = OpenAlexLiveBackend("KEY", fetch=fetch)
    ids = [f"W{i}" for i in range(70)]
    backend.fetch_references(ids, max_results=1000)

    assert len(calls) == 2
    first_ids = calls[0]["filter"].removeprefix("ids.openalex:").split("|")
    second_ids = calls[1]["filter"].removeprefix("ids.openalex:").split("|")
    assert len(first_ids) == 50
    assert len(second_ids) == 20


def test_lookup_dois_chunks_over_50(monkeypatch: pytest.MonkeyPatch) -> None:
    _sleep_recorder(monkeypatch)
    calls: list[dict[str, str]] = []

    def fetch(url: str, params: dict[str, str]) -> Any:
        calls.append(dict(params))
        return {"results": []}

    backend = OpenAlexLiveBackend("KEY", fetch=fetch)
    dois = [f"10.99999/d{i}" for i in range(70)]
    backend.lookup_dois(dois, max_results=1000)

    assert len(calls) == 2
    first_dois = calls[0]["filter"].removeprefix("doi:").split("|")
    second_dois = calls[1]["filter"].removeprefix("doi:").split("|")
    assert len(first_dois) == 50
    assert len(second_dois) == 20


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("W123", "W123"),
        ("https://openalex.org/W123", "W123"),
        ("http://openalex.org/W123", "W123"),
        ("https://api.openalex.org/works/W123", "W123"),
    ],
)
def test_normalize_openalex_work_id_accepts(raw: str, expected: str) -> None:
    assert search_live._normalize_openalex_work_id(raw) == expected


@pytest.mark.parametrize("raw", ["garbage", "W", "123", "https://example.com/W1", ""])
def test_normalize_openalex_work_id_rejects_garbage(raw: str) -> None:
    with pytest.raises(ValueError):
        search_live._normalize_openalex_work_id(raw)


def test_overton_verbs_raise_not_implemented() -> None:
    backend = OvertonLiveBackend("KEY", fetch=lambda url, params: {"results": []})
    with pytest.raises(NotImplementedError):
        backend.fetch_citations("x")
    with pytest.raises(NotImplementedError):
        backend.fetch_references(["x"])
    with pytest.raises(NotImplementedError):
        backend.lookup_title("x")
    with pytest.raises(NotImplementedError):
        backend.lookup_dois(["x"])


# --- live_search_backends key checks ---


def test_live_search_backends_missing_openalex_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    monkeypatch.delenv("OVERTON_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENALEX_API_KEY"):
        live_search_backends()


def test_live_search_backends_missing_overton_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENALEX_API_KEY", "key1")
    monkeypatch.delenv("OVERTON_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OVERTON_API_KEY"):
        live_search_backends()
