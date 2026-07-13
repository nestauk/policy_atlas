"""Live OpenAlex and Overton search backends with redacted HTTP transport.

Search-response caching is in-process only and TTL bounded. It trusts exactly
the same origin payload the uncached path would consume, and keys include every
non-credential request parameter so differing filters do not collide. API keys
and polite-pool mailto values are excluded from cache structures.
"""

import os
import re
import time
from collections import OrderedDict
from collections.abc import Callable, Iterable
from copy import deepcopy
from typing import Any, cast
from urllib.parse import parse_qsl, urlparse

import httpx
import structlog

from policy_atlas.acquire import BackendCaps
from policy_atlas.search_loop import (
    OA_STATUS_VALUES,
    OPENALEX_TYPES,
    OVERTON_PUBLISHER_TYPES,
    OVERTON_REGION_GROUPS,
    OVERTON_SDG_LABELS,
    openalex_wire_params,
    overton_wire_params,
)

log = structlog.get_logger()

__all__ = (
    "HTTP_TIMEOUT_S",
    "OA_SELECT",
    "OA_STATUS_VALUES",
    "OPENALEX_HOST",
    "OPENALEX_TYPES",
    "OVERTON_HOST",
    "OVERTON_MIN_INTERVAL_S",
    "OVERTON_PUBLISHER_TYPES",
    "OVERTON_REGION_GROUPS",
    "OVERTON_SDG_LABELS",
    "OpenAlexLiveBackend",
    "OvertonLiveBackend",
    "RETRY_BACKOFF_S",
    "SearchTransportError",
    "USER_AGENT",
    "live_search_backends",
    "openalex_wire_params",
    "overton_wire_params",
    "sanitize_openalex_query",
    "sanitize_title_query",
)

HTTP_TIMEOUT_S = 30.0
OVERTON_MIN_INTERVAL_S = 1.2
RETRY_BACKOFF_S = 2.0
USER_AGENT = "policy-atlas/0.1"
OPENALEX_HOST = "https://api.openalex.org"
OVERTON_HOST = "https://app.overton.io"

OA_SELECT: tuple[str, ...] = (
    "id",
    "display_name",
    "abstract_inverted_index",
    "publication_year",
    "publication_date",
    "doi",
    "language",
    "type",
    "primary_location",
    "best_oa_location",
    "open_access",
    "topics",
    "primary_topic",
    "keywords",
    "cited_by_count",
    "fwci",
    "is_retracted",
    "is_paratext",
    "ids",
    "sustainable_development_goals",
    "indexed_in",
    "authorships",
    "referenced_works",
)

_sleep = time.sleep
_monotonic = time.monotonic

_Fetch = Callable[[str, dict[str, str]], Any]
_SearchCacheKey = tuple[str, str, str, tuple[tuple[str, str], ...]]
_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})
_CACHE_CREDENTIAL_PARAMS = frozenset({"api_key", "mailto"})
_DEFAULT_SEARCH_CACHE_TTL_S = 3600.0
_SEARCH_CACHE_MAX_ENTRIES = 512
_SEARCH_CACHE: OrderedDict[_SearchCacheKey, tuple[float, Any]] = OrderedDict()
_DEFAULT_MAX_RESULTS = 50
_OPENALEX_MAX_PER_PAGE = 200
_OVERTON_PAGE_SIZE = 50
_OPENALEX_REFERENCE_BATCH_SIZE = 50
_OPENALEX_WORK_ID_RE = re.compile(r"^W\d+$")
_OPENALEX_WILDCARD_RE = re.compile(r"[*?~]")
_TITLE_PUNCT_RE = re.compile(r"[,:\(\)\-]+")
_OPENALEX_ALLOWED_WIRE_KEYS = frozenset({"filter"})
_OVERTON_ALLOWED_WIRE_KEYS = frozenset(
    {
        "published_after",
        "published_before",
        "sdgcategories",
        "source_type",
        "source_country",
        "source_region",
        "language",
    }
)
_PROTECTED_OVERTON_PARAMS = frozenset({"squery", "min_similarity", "format", "pp", "api_key"})


class SearchTransportError(RuntimeError):
    """Redacted live-search transport failure.

    Args:
        status_code: HTTP status code, or ``None`` when no status is available.
        host: Hostname involved in the failed request.
    """

    def __init__(self, status_code: int | None, host: str) -> None:
        self.status_code = status_code
        self.host = host
        super().__init__(f"search transport error host={host} status_code={status_code}")


def sanitize_openalex_query(q: str) -> str:
    """Sanitize an OpenAlex search query for filter-syntax safety.

    Args:
        q: Raw keyword or boolean query text.

    Returns:
        Query text with wildcard/fuzzy characters removed, every comma replaced
        with a space, and whitespace collapsed. Commas are the OpenAlex
        ``filter`` clause separator — a comma surviving into the embedded
        ``title_and_abstract.search:`` value would open a new, injectable
        filter clause (015 review finding, Codex + security lanes convergent).
    """
    stripped = _OPENALEX_WILDCARD_RE.sub("", q.replace(",", " "))
    return " ".join(stripped.split())


def sanitize_title_query(title: str) -> str:
    """Sanitize an OpenAlex ``title.search`` query.

    Args:
        title: Raw title text.

    Returns:
        Sanitized title text with punctuation known to 400 ``title.search``
        stripped and whitespace collapsed.
    """
    sanitized = sanitize_openalex_query(title)
    return " ".join(_TITLE_PUNCT_RE.sub(" ", sanitized).split())


class _TransportMixin:
    _client: httpx.Client | None
    _fetch: _Fetch
    http_calls: int

    def _init_transport(self, fetch: _Fetch | None) -> None:
        self.http_calls = 0
        if fetch is None:
            self._client = httpx.Client(
                timeout=httpx.Timeout(HTTP_TIMEOUT_S),
                headers={"User-Agent": USER_AGENT},
            )
            self._fetch = self._default_fetch
        else:
            self._client = None
            self._fetch = fetch

    def _default_fetch(self, url: str, params: dict[str, str]) -> Any:
        if self._client is None:
            raise SearchTransportError(status_code=None, host=_host_from_url(url))
        response = self._client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def _request_json(
        self,
        url: str,
        params: dict[str, str],
        *,
        rate_limit: Callable[[], None] | None = None,
        overton_retry_wait: bool = False,
    ) -> Any:
        host = _host_from_url(url)
        cache_ttl_s = _search_cache_ttl_s()
        cache_key = _search_cache_key(url, params) if cache_ttl_s > 0 else None
        if cache_key is not None:
            cached = _search_cache_get(cache_key, ttl_s=cache_ttl_s)
            if cached is not None:
                return cached

        attempts = 0
        while True:
            if rate_limit is not None:
                rate_limit()
            self.http_calls += 1
            try:
                data = self._fetch(url, dict(params))
            except Exception as exc:
                redacted = _redacted_error(exc, host)
                retryable = _is_retryable_error(exc, redacted)
                if attempts >= 1 or not retryable:
                    log.warning(
                        "search.http_failed",
                        host=host,
                        status_code=redacted.status_code,
                    )
                    raise redacted from None
                log.warning(
                    "search.http_retry",
                    host=host,
                    status_code=redacted.status_code,
                    attempt=attempts + 1,
                )
                _sleep(RETRY_BACKOFF_S)
                if overton_retry_wait and redacted.status_code == 429:
                    _sleep(OVERTON_MIN_INTERVAL_S)
                attempts += 1
                continue

            if cache_key is not None and _cacheable_payload(data):
                _search_cache_set(cache_key, data)
            return data


class OpenAlexLiveBackend(_TransportMixin):
    """Live OpenAlex backend over the Works API.

    Args:
        api_key: OpenAlex API key carried as a query parameter.
        email: Optional polite-pool email carried as ``mailto``.
        fetch: Optional injectable JSON fetcher for tests.
    """

    name = "openalex"
    trust_class = "academic_aggregator"
    mode = "live"
    caps = BackendCaps(has_snowball=True, has_title_lookup=True, has_doi_lookup=True)

    def __init__(self, api_key: str, *, email: str | None = None, fetch: _Fetch | None = None):
        self._api_key = api_key
        self._email = email
        self._init_transport(fetch)

    def search(
        self,
        query: str,
        *,
        wire_params: dict[str, str] | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return raw OpenAlex Work records for a sanitized keyword query.

        Args:
            query: Raw keyword or boolean query text.
            wire_params: Optional provider wire params from ``openalex_wire_params``.
            max_results: Optional result cap across pages.

        Returns:
            Raw OpenAlex Work dictionaries.
        """
        sanitized = sanitize_openalex_query(query)
        if not sanitized:
            return []
        # demo-branch observability: the live UI's search activity reads these
        log.info("search.query_issued", backend="openalex", query=sanitized)
        filter_parts = [f"title_and_abstract.search:{sanitized}"]
        filter_parts.extend(_openalex_wire_filter_parts(wire_params))
        records = self._fetch_works(filter_parts, max_results=max_results)
        log.info("search.results_page", backend="openalex", count=len(records))
        return records

    def fetch_citations(
        self, record_id: str, *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        """Return OpenAlex Work records that cite the given Work ID.

        Args:
            record_id: Bare OpenAlex Work ID or canonical OpenAlex Work URL.
            max_results: Optional result cap across pages.

        Returns:
            Raw OpenAlex Work dictionaries.
        """
        work_id = _normalize_openalex_work_id(record_id)
        return self._fetch_works([f"cites:{work_id}"], max_results=max_results)

    def fetch_references(
        self, record_ids: list[str], *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        """Batch-resolve OpenAlex reference Work IDs.

        Args:
            record_ids: Bare OpenAlex Work IDs or canonical OpenAlex Work URLs.
            max_results: Optional result cap across all batches.

        Returns:
            Raw OpenAlex Work dictionaries.
        """
        limit = _result_limit(max_results, _DEFAULT_MAX_RESULTS)
        if limit == 0 or not record_ids:
            return []

        records: list[dict[str, Any]] = []
        normalized_ids = [_normalize_openalex_work_id(record_id) for record_id in record_ids]
        for chunk in _chunks(normalized_ids, _OPENALEX_REFERENCE_BATCH_SIZE):
            remaining = limit - len(records)
            if remaining <= 0:
                break
            filter_part = f"ids.openalex:{'|'.join(chunk)}"
            records.extend(self._fetch_works([filter_part], max_results=remaining))
        return records[:limit]

    def lookup_title(self, title: str) -> list[dict[str, Any]]:
        """Return a small OpenAlex title-search page.

        Args:
            title: Raw title text.

        Returns:
            Raw OpenAlex Work dictionaries.
        """
        sanitized = sanitize_title_query(title)
        if not sanitized:
            return []
        return self._fetch_works([f"title.search:{sanitized}"], max_results=5)

    def lookup_dois(
        self, dois: list[str], *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        """Batch-resolve OpenAlex Work records by DOI.

        Args:
            dois: DOI identifiers, either bare or URL-prefixed.
            max_results: Optional cap across all DOI chunks.

        Returns:
            Raw OpenAlex Work dictionaries matching requested DOIs.
        """
        normalized = _unique_normalized_dois(dois)
        limit = _result_limit(max_results, len(normalized))
        if limit == 0 or not normalized:
            return []

        records: list[dict[str, Any]] = []
        for chunk in _chunks(normalized, _OPENALEX_REFERENCE_BATCH_SIZE):
            remaining = limit - len(records)
            if remaining <= 0:
                break
            params = {
                **self._auth_params(),
                "filter": f"doi:{'|'.join(chunk)}",
                "select": ",".join(OA_SELECT),
                "per-page": str(min(remaining, len(chunk), _OPENALEX_MAX_PER_PAGE)),
                "page": "1",
            }
            data = self._request_json(f"{OPENALEX_HOST}/works", params)
            page_results = _results_array(data, _host_from_url(OPENALEX_HOST))
            records.extend(page_results[:remaining])
        return records[:limit]

    def _fetch_works(
        self, filter_parts: list[str], *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        limit = _result_limit(max_results, _DEFAULT_MAX_RESULTS)
        if limit == 0:
            return []
        records: list[dict[str, Any]] = []
        page = 1
        while len(records) < limit:
            remaining = limit - len(records)
            per_page = min(remaining, _OPENALEX_MAX_PER_PAGE)
            params = {
                **self._auth_params(),
                "filter": ",".join(filter_parts),
                "select": ",".join(OA_SELECT),
                "per-page": str(per_page),
                "page": str(page),
            }
            # No-citation-floor guard on wire filter clauses only: the
            # *.search: values are sanitized free-text where the literal
            # phrase "cited_by_count" is data, not a filter.
            if any(
                "cited_by_count" in part
                for part in filter_parts
                if not part.startswith(("title_and_abstract.search:", "title.search:"))
            ):
                raise ValueError("OpenAlex cited_by_count filters are not allowed")

            data = self._request_json(f"{OPENALEX_HOST}/works", params)
            page_results = _results_array(data, _host_from_url(OPENALEX_HOST))
            records.extend(page_results[:remaining])
            if len(page_results) < per_page:
                break
            page += 1
        return records

    def _auth_params(self) -> dict[str, str]:
        params = {"api_key": self._api_key}
        if self._email:
            params["mailto"] = self._email
        return params


class OvertonLiveBackend(_TransportMixin):
    """Live Overton backend over the semantic documents endpoint.

    Args:
        api_key: Overton API key carried as a query parameter.
        fetch: Optional injectable JSON fetcher for tests.
    """

    name = "overton"
    trust_class = "grey_literature_aggregator"
    mode = "live"
    caps = BackendCaps(has_snowball=False, has_title_lookup=False)

    def __init__(self, api_key: str, *, fetch: _Fetch | None = None):
        self._api_key = api_key
        self._last_request_at: float | None = None
        self.last_post_filter_excluded: int | None = None
        self._init_transport(fetch)

    def search(
        self,
        query: str,
        *,
        wire_params: dict[str, str] | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return raw Overton policy-document records for a semantic query.

        Args:
            query: Natural-language semantic search text.
            wire_params: Optional provider wire params from ``overton_wire_params``.
            max_results: Optional result cap across pages.

        Returns:
            Raw Overton policy-document dictionaries.
        """
        return self._search(
            query,
            wire_params=wire_params,
            max_results=max_results,
            source_country_post_filter=None,
        )

    def search_with_post_filter(
        self,
        query: str,
        *,
        wire_params: dict[str, str] | None = None,
        source_country_post_filter: list[str],
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return Overton records filtered by source-country metadata.

        Args:
            query: Natural-language semantic search text.
            wire_params: Provider wire params from ``overton_wire_params``;
                never includes the post-filter key.
            source_country_post_filter: Overton display-country names accepted
                by the 2026-07-12 probe.
            max_results: Optional accepted-result cap across pages.

        Returns:
            Matching Overton policy-document dictionaries. Excluded records are
            counted in ``last_post_filter_excluded``.
        """
        return self._search(
            query,
            wire_params=wire_params,
            max_results=max_results,
            source_country_post_filter=set(source_country_post_filter),
        )

    def _search(
        self,
        query: str,
        *,
        wire_params: dict[str, str] | None,
        max_results: int | None,
        source_country_post_filter: set[str] | None,
    ) -> list[dict[str, Any]]:
        limit = _result_limit(max_results, _DEFAULT_MAX_RESULTS)
        self.last_post_filter_excluded = 0 if source_country_post_filter is not None else None
        if limit == 0:
            return []
        # demo-branch observability: the live UI's search activity reads these
        log.info("search.query_issued", backend="overton", query=query)

        params = {
            **_overton_wire_params(wire_params),
            "squery": query,
            "min_similarity": "0.3",
            "format": "json",
            "pp": str(_OVERTON_PAGE_SIZE),
            "api_key": self._api_key,
        }
        records: list[dict[str, Any]] = []
        next_url: str | None = None
        while len(records) < limit:
            if next_url is None:
                data = self._request_json(
                    f"{OVERTON_HOST}/documents.php",
                    params,
                    rate_limit=self._wait_rate_limit,
                    overton_retry_wait=True,
                )
            else:
                data = self._request_json(
                    next_url,
                    {},
                    rate_limit=self._wait_rate_limit,
                    overton_retry_wait=True,
                )
            response = _json_object(data, _host_from_url(OVERTON_HOST))
            page_results = _results_array(response, _host_from_url(OVERTON_HOST))
            if source_country_post_filter is None:
                remaining = limit - len(records)
                records.extend(page_results[:remaining])
            else:
                for record in page_results:
                    if len(records) >= limit:
                        break
                    if _overton_source_country(record) in source_country_post_filter:
                        records.append(record)
                    else:
                        self.last_post_filter_excluded = (
                            self.last_post_filter_excluded or 0
                        ) + 1
            if len(records) >= limit:
                break
            # An empty page that still advertises next_page_url must not be
            # followed: zero progress per iteration would loop (and egress)
            # unboundedly on a buggy or hostile endpoint (015 security lane).
            if not page_results:
                break
            next_page_url = _overton_next_page_url(response)
            if next_page_url is None:
                break
            next_url = _validate_overton_next_page_url(next_page_url)
        log.info("search.results_page", backend="overton", count=len(records))
        return records

    def fetch_citations(
        self, record_id: str, *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        """Raise because Overton v1 declares no snowball capability."""
        raise NotImplementedError("OvertonLiveBackend caps.has_snowball=False")

    def fetch_references(
        self, record_ids: list[str], *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        """Raise because Overton v1 declares no snowball capability."""
        raise NotImplementedError("OvertonLiveBackend caps.has_snowball=False")

    def lookup_title(self, title: str) -> list[dict[str, Any]]:
        """Raise because Overton v1 declares no title-lookup capability."""
        raise NotImplementedError("OvertonLiveBackend caps.has_title_lookup=False")

    def lookup_dois(
        self, dois: list[str], *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        """Raise because Overton v1 declares no DOI-lookup capability."""
        raise NotImplementedError("OvertonLiveBackend caps.has_doi_lookup=False")

    def _wait_rate_limit(self) -> None:
        now = time.monotonic()
        if self._last_request_at is not None:
            wait_s = OVERTON_MIN_INTERVAL_S - (now - self._last_request_at)
            if wait_s > 0:
                _sleep(wait_s)
                now = time.monotonic()
        self._last_request_at = now


def live_search_backends(
    *, openalex_fetch: _Fetch | None = None, overton_fetch: _Fetch | None = None
) -> list[OpenAlexLiveBackend | OvertonLiveBackend]:
    """Build live search backends from environment keys.

    Args:
        openalex_fetch: Optional injectable OpenAlex JSON fetcher.
        overton_fetch: Optional injectable Overton JSON fetcher.

    Returns:
        OpenAlex and Overton live backend instances, in acquire order.

    Raises:
        RuntimeError: If a required live provider key is missing.
    """
    openalex_key = os.environ.get("OPENALEX_API_KEY")
    if not openalex_key:
        raise RuntimeError("OPENALEX_API_KEY is required for live search")
    overton_key = os.environ.get("OVERTON_API_KEY")
    if not overton_key:
        raise RuntimeError("OVERTON_API_KEY is required for live search")
    email = os.environ.get("OPENALEX_EMAIL")
    return [
        OpenAlexLiveBackend(openalex_key, email=email, fetch=openalex_fetch),
        OvertonLiveBackend(overton_key, fetch=overton_fetch),
    ]


def _openalex_wire_filter_parts(wire_params: dict[str, str] | None) -> list[str]:
    if not wire_params:
        return []
    unknown = set(wire_params) - _OPENALEX_ALLOWED_WIRE_KEYS
    if unknown:
        raise ValueError(f"unknown OpenAlex wire param(s): {sorted(unknown)}")
    filter_value = wire_params.get("filter", "").strip()
    if not filter_value:
        return []
    if "cited_by_count" in filter_value:
        raise ValueError("OpenAlex cited_by_count filters are not allowed")
    return [filter_value]


def _overton_wire_params(wire_params: dict[str, str] | None) -> dict[str, str]:
    if not wire_params:
        return {}
    unknown = set(wire_params) - _OVERTON_ALLOWED_WIRE_KEYS
    protected = set(wire_params) & _PROTECTED_OVERTON_PARAMS
    if unknown or protected:
        blocked = sorted(unknown | protected)
        raise ValueError(f"unknown Overton wire param(s): {blocked}")
    return dict(wire_params)


def _overton_source_country(record: dict[str, Any]) -> str | None:
    source = record.get("source")
    if not isinstance(source, dict):
        return None
    country = source.get("country")
    return country if isinstance(country, str) else None


def _result_limit(max_results: int | None, default: int) -> int:
    if max_results is None:
        return default
    if max_results < 0:
        raise ValueError("max_results must be non-negative")
    return max_results


def _chunks(values: list[str], size: int) -> Iterable[list[str]]:
    for i in range(0, len(values), size):
        yield values[i : i + size]


def _normalize_doi_for_filter(doi: str) -> str | None:
    # Behavioral twin of acquire._normalize_doi (the cross-backend identity
    # key). Kept local so the transport module never imports the DB layer;
    # any prefix-handling change must land in both.
    candidate = doi.strip().lower()
    for prefix in (
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
    ):
        if candidate.startswith(prefix):
            candidate = candidate[len(prefix):]
            break
    return candidate or None


def _unique_normalized_dois(dois: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for doi in dois:
        normalized = _normalize_doi_for_filter(doi)
        if normalized is None or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _normalize_openalex_work_id(record_id: str) -> str:
    candidate = record_id.strip()
    for prefix in (
        "https://openalex.org/",
        "http://openalex.org/",
        "https://api.openalex.org/works/",
        "http://api.openalex.org/works/",
    ):
        if candidate.startswith(prefix):
            candidate = candidate[len(prefix):]
            break
    if not _OPENALEX_WORK_ID_RE.fullmatch(candidate):
        raise ValueError("record_id must be a plain OpenAlex Work ID or URL")
    return candidate


def _host_from_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed.hostname or parsed.netloc or url


def _search_cache_ttl_s() -> float:
    raw = os.environ.get("POLICY_ATLAS_SEARCH_CACHE_TTL_S")
    if raw is None:
        return _DEFAULT_SEARCH_CACHE_TTL_S
    try:
        return float(raw)
    except ValueError:
        log.warning("search.cache_ttl_invalid")
        return _DEFAULT_SEARCH_CACHE_TTL_S


def _search_cache_key(url: str, params: dict[str, str]) -> _SearchCacheKey:
    parsed = urlparse(url)
    pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key not in _CACHE_CREDENTIAL_PARAMS
    ]
    pairs.extend(
        (key, value) for key, value in params.items() if key not in _CACHE_CREDENTIAL_PARAMS
    )
    return (
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        tuple(sorted((str(key), str(value)) for key, value in pairs)),
    )


def _search_cache_get(key: _SearchCacheKey, *, ttl_s: float) -> Any | None:
    cached = _SEARCH_CACHE.get(key)
    if cached is None:
        return None
    cached_at, payload = cached
    if _monotonic() - cached_at >= ttl_s:
        del _SEARCH_CACHE[key]
        return None
    _SEARCH_CACHE.move_to_end(key)
    return deepcopy(payload)


def _search_cache_set(key: _SearchCacheKey, payload: Any) -> None:
    _SEARCH_CACHE[key] = (_monotonic(), deepcopy(payload))
    _SEARCH_CACHE.move_to_end(key)
    while len(_SEARCH_CACHE) > _SEARCH_CACHE_MAX_ENTRIES:
        _SEARCH_CACHE.popitem(last=False)


def _cacheable_payload(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    results = data.get("results")
    return isinstance(results, list) and all(isinstance(item, dict) for item in results)


def _redacted_error(exc: Exception, host: str) -> SearchTransportError:
    if isinstance(exc, SearchTransportError):
        return SearchTransportError(status_code=exc.status_code, host=host)
    status_code = _status_code(exc)
    return SearchTransportError(status_code=status_code, host=host)


def _status_code(exc: Exception) -> int | None:
    if isinstance(exc, httpx.HTTPStatusError):
        return int(exc.response.status_code)
    return None


def _is_retryable_error(exc: Exception, redacted: SearchTransportError) -> bool:
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, SearchTransportError) and redacted.status_code is None:
        return True
    return redacted.status_code in _RETRYABLE_STATUSES


def _json_object(data: Any, host: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise SearchTransportError(status_code=None, host=host)
    return cast(dict[str, Any], data)


def _results_array(data: Any, host: str) -> list[dict[str, Any]]:
    obj = _json_object(data, host)
    results = obj.get("results")
    if not isinstance(results, list):
        raise SearchTransportError(status_code=None, host=host)
    records: list[dict[str, Any]] = []
    for item in results:
        if not isinstance(item, dict):
            raise SearchTransportError(status_code=None, host=host)
        records.append(cast(dict[str, Any], item))
    return records


def _overton_next_page_url(response: dict[str, Any]) -> str | None:
    value = response.get("next_page_url")
    query = response.get("query")
    if value is None and isinstance(query, dict):
        value = query.get("next_page_url")
    if value is None or value is False or value == "":
        return None
    if not isinstance(value, str):
        raise SearchTransportError(status_code=None, host=_host_from_url(OVERTON_HOST))
    return value


def _validate_overton_next_page_url(next_page_url: str) -> str:
    parsed = urlparse(next_page_url)
    if parsed.scheme != "https" or parsed.hostname != "app.overton.io":
        raise SearchTransportError(status_code=None, host=parsed.hostname or "")
    return next_page_url
