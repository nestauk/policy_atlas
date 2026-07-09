"""Live OpenAlex and Overton search backends with redacted HTTP transport."""

import os
import re
import time
from collections.abc import Callable, Iterable
from typing import Any, cast
from urllib.parse import urlparse

import httpx
import structlog

from policy_atlas.acquire import BackendCaps

log = structlog.get_logger()

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

OPENALEX_TYPES: tuple[str, ...] = (
    "article",
    "book-chapter",
    "dataset",
    "other",
    "dissertation",
    "preprint",
    "book",
    "review",
    "paratext",
    "libguides",
    "letter",
    "report",
    "peer-review",
    "reference-entry",
    "editorial",
    "conference-paper",
    "standard",
    "erratum",
    "software",
    "conference-abstract",
    "supplementary-materials",
    "retraction",
    "book-review",
    "database",
    "book-section",
    "data-paper",
    "report-component",
    "grant",
)
OA_STATUS_VALUES: tuple[str, ...] = ("diamond", "gold", "green", "hybrid", "bronze", "closed")
OVERTON_PUBLISHER_TYPES: tuple[str, ...] = ("government", "think tank", "igo", "other")
OVERTON_REGION_GROUPS: tuple[str, ...] = (
    "OECD members",
    "G7",
    "G20",
    "Europe",
    "North America",
    "APAC",
    "Oceania",
    "EU27",
    "EEA",
    "Very high human development",
)
OVERTON_SDG_LABELS: dict[int, str] = {
    1: "SDG 1: No Poverty",
    2: "SDG 2: Zero Hunger",
    3: "SDG 3: Good Health and Well-being",
    4: "SDG 4: Quality Education",
    5: "SDG 5: Gender Equality",
    6: "SDG 6: Clean Water and Sanitation",
    7: "SDG 7: Affordable and Clean Energy",
    8: "SDG 8: Decent Work and Economic Growth",
    9: "SDG 9: Industry, Innovation and Infrastructure",
    10: "SDG 10: Reduced Inequalities",
    11: "SDG 11: Sustainable Cities and Communities",
    12: "SDG 12: Responsible Consumption and Production",
    13: "SDG 13: Climate Action",
    14: "SDG 14: Life Below Water",
    15: "SDG 15: Life on Land",
    16: "SDG 16: Peace, Justice and Strong Institutions",
    17: "SDG 17: Partnerships for the Goals",
}

_sleep = time.sleep

_Fetch = Callable[[str, dict[str, str]], Any]
_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})
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
        Query text with wildcard/fuzzy characters removed, commas removed from
        quoted phrases, and whitespace collapsed.
    """
    in_quotes = False
    chars: list[str] = []
    for ch in q:
        if ch == '"':
            in_quotes = not in_quotes
            chars.append(ch)
        elif ch == "," and in_quotes:
            continue
        else:
            chars.append(ch)
    stripped = _OPENALEX_WILDCARD_RE.sub("", "".join(chars))
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


def openalex_wire_params(filters: dict[str, Any] | None) -> dict[str, str]:
    """Map validated search filter directives to OpenAlex wire params.

    Args:
        filters: Validated directive dictionary for OpenAlex.

    Returns:
        OpenAlex query parameters, currently a ``filter`` value.

    Raises:
        ValueError: If an unknown or unsupported directive key is present.
    """
    if not filters:
        return {}

    filter_parts: list[str] = []
    for key, value in filters.items():
        if key == "published_after":
            filter_parts.append(f"from_publication_date:{value}")
        elif key == "published_before":
            filter_parts.append(f"to_publication_date:{value}")
        elif key == "sdgs":
            sdg_iris = [
                f"https://metadata.un.org/sdg/{n}" for n in _int_values(key, value, 1, 17)
            ]
            filter_parts.append(f"sustainable_development_goals.id:{'|'.join(sdg_iris)}")
        elif key == "types":
            filter_parts.append(f"type:{'|'.join(_enum_values(key, value, OPENALEX_TYPES))}")
        elif key == "languages":
            filter_parts.append(f"language:{'|'.join(_str_values(key, value))}")
        elif key == "exclude_retracted":
            if bool(value):
                filter_parts.append("is_retracted:false")
        elif key == "exclude_paratext":
            if bool(value):
                filter_parts.append("is_paratext:false")
        elif key == "oa_status":
            statuses = _enum_values(key, value, OA_STATUS_VALUES)
            filter_parts.append(f"oa_status:{'|'.join(statuses)}")
        elif key == "author_affiliation_countries":
            countries = _str_values(key, value)
            filter_parts.append(f"authorships.countries:{'|'.join(countries)}")
        else:
            raise ValueError(f"unknown OpenAlex filter key: {key}")

    if not filter_parts:
        return {}
    return {"filter": ",".join(filter_parts)}


def overton_wire_params(filters: dict[str, Any] | None) -> dict[str, str]:
    """Map validated search filter directives to Overton wire params.

    Args:
        filters: Validated directive dictionary for Overton.

    Returns:
        Overton query parameters for document search.

    Raises:
        ValueError: If an unknown or unsupported directive key is present.
    """
    if not filters:
        return {}

    params: dict[str, str] = {}
    for key, value in filters.items():
        if key == "published_after":
            params["published_after"] = str(value)
        elif key == "published_before":
            params["published_before"] = str(value)
        elif key == "sdgs":
            sdg = _single_int_value(key, value, 1, 17)
            params["sdgcategories"] = OVERTON_SDG_LABELS[sdg]
        elif key == "publisher_type":
            params["source_type"] = _single_enum_value(key, value, OVERTON_PUBLISHER_TYPES)
        elif key == "publisher_country":
            params["source_country"] = _single_str_value(key, value)
        elif key == "publisher_region":
            params["source_region"] = _single_enum_value(key, value, OVERTON_REGION_GROUPS)
        elif key == "language":
            params["language"] = _single_str_value(key, value)
        else:
            raise ValueError(f"unknown Overton filter key: {key}")
    return params


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
        attempts = 0
        while True:
            if rate_limit is not None:
                rate_limit()
            self.http_calls += 1
            try:
                return self._fetch(url, dict(params))
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
    caps = BackendCaps(has_snowball=True, has_title_lookup=True)

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
        filter_parts = [f"title_and_abstract.search:{sanitized}"]
        filter_parts.extend(_openalex_wire_filter_parts(wire_params))
        return self._fetch_works(filter_parts, max_results=max_results)

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
            if "cited_by_count" in params["filter"]:
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
        limit = _result_limit(max_results, _DEFAULT_MAX_RESULTS)
        if limit == 0:
            return []

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
            remaining = limit - len(records)
            records.extend(page_results[:remaining])
            if len(records) >= limit:
                break
            next_page_url = _overton_next_page_url(response)
            if next_page_url is None:
                break
            next_url = _validate_overton_next_page_url(next_page_url)
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


def _str_values(key: str, value: Any) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{key} must be a non-empty list")
    return [str(item) for item in value]


def _int_values(key: str, value: Any, min_value: int, max_value: int) -> list[int]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{key} must be a non-empty list")
    ints = [int(item) for item in value]
    if any(item < min_value or item > max_value for item in ints):
        raise ValueError(f"{key} contains an out-of-range value")
    return ints


def _single_str_value(key: str, value: Any) -> str:
    if isinstance(value, list):
        if len(value) != 1:
            raise ValueError(f"{key} must be single-valued")
        value = value[0]
    return str(value)


def _single_int_value(key: str, value: Any, min_value: int, max_value: int) -> int:
    if not isinstance(value, list) or len(value) != 1:
        raise ValueError(f"{key} must be a single-item list")
    item = int(value[0])
    if item < min_value or item > max_value:
        raise ValueError(f"{key} contains an out-of-range value")
    return item


def _enum_values(key: str, value: Any, allowed: tuple[str, ...]) -> list[str]:
    values = _str_values(key, value)
    allowed_set = set(allowed)
    unknown = [item for item in values if item not in allowed_set]
    if unknown:
        raise ValueError(f"{key} contains unknown value(s): {unknown}")
    return values


def _single_enum_value(key: str, value: Any, allowed: tuple[str, ...]) -> str:
    item = _single_str_value(key, value)
    if item not in set(allowed):
        raise ValueError(f"{key} contains unknown value: {item}")
    return item


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


def _result_limit(max_results: int | None, default: int) -> int:
    if max_results is None:
        return default
    if max_results < 0:
        raise ValueError("max_results must be non-negative")
    return max_results


def _chunks(values: list[str], size: int) -> Iterable[list[str]]:
    for i in range(0, len(values), size):
        yield values[i : i + size]


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
