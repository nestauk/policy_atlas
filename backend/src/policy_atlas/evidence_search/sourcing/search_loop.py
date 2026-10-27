"""Depth-graded search strategy, directives, and pure filter wire mapping.

This module stays HTTP-import-free. It owns the search directive grammar,
validated per-backend filter dictionaries, rapid/deep round-1 fan-out planning,
and the harness-facing ``run_search`` entrypoint that hands executed calls to
``acquire_sources`` for the existing mapping, deduplication, and persistence
machinery.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from functools import partial
from typing import Any, Literal, TypedDict, cast

from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from policy_atlas.core import tracing
from policy_atlas.core.embeddings import EmbeddingBackend
from policy_atlas.core.prompt_fields import parse_guidance_channel
from policy_atlas.core.schema import (
    DIRECTIVE_STRING_MAX,
    search_coverage_record,
)
from policy_atlas.core.usage import UsageAccumulator
from policy_atlas.evidence_search.sourcing import acquire, pool
from policy_atlas.evidence_search.sourcing.country_filters import (
    OVERTON_DISPLAY_ALLOWLIST,
    validate_iso_alpha2,
    validate_overton_display_name,
)
from policy_atlas.evidence_search.sourcing.country_filters import (
    SearchDirectiveError as _SearchDirectiveError,
)
from policy_atlas.evidence_search.sourcing.search_generation import SearchGenerationBackend
from policy_atlas.evidence_search.sourcing.search_prompts import (
    N_QUERIES,
    QueriesPayload,
    validated_queries,
)

SearchDepth = Literal["rapid", "standard", "deep", "link"]
SearchDirectiveError = _SearchDirectiveError
QueryOrigin = Literal[
    "generated",
    "variant_sr",
    "variant_rct",
    "paraphrase",
    "verbatim",
    "fallback_verbatim",
    "snowball_forward",
    "snowball_backward",
    "semantic",
    "semantic_place",
    "landmark",
    "suggestion_doi",
    "suggestion_title",
]
CallVerb = Literal[
    "search",
    "fetch_citations",
    "fetch_references",
    "lookup_dois",
    "lookup_title",
    "search_semantic",
    "fetch_by_id",
]
CallStatus = Literal["ok", "error"]

# No wall clock at any depth (task 030): a time budget over an ordered fan-out
# truncates the tail — a specific set of queries and providers, not a random
# sample — and its breach once cost the entire Overton leg while the run still
# reported 'adequate'. Volume is bounded at acquisition instead (the two caps
# in DEPTH_CONSTANTS), which brakes the thing that actually costs money, and by
# the logical-call budgets here.


class DepthConstants(TypedDict):
    """Per-depth output caps and logical-call budgets."""

    # A cap is the maximum number of records persisted from the ranked pool.
    papers_cap: int
    policy_cap: int
    # A logical call is one planned provider request, even when it pages or retries.
    call_budget: dict[str, int]


DEPTH_CONSTANTS: dict[SearchDepth, DepthConstants] = {
    "rapid": {
        "papers_cap": 100,
        "policy_cap": 50,
        "call_budget": {"openalex": 45, "overton": 30},
    },
    "standard": {
        "papers_cap": 200,
        "policy_cap": 100,
        "call_budget": {"openalex": 45, "overton": 30},
    },
    "deep": {
        "papers_cap": 400,
        "policy_cap": 200,
        "call_budget": {"openalex": 45, "overton": 30},
    },
    # The theory-of-change link search (task 054, C27): no generation call,
    # two OpenAlex semantic calls and one Overton call on the first line of
    # the intent (the link sentence), every distinct result kept. See ``_link_pools``.
    "link": {
        "papers_cap": 40,
        "policy_cap": 40,
        "call_budget": {"openalex": 2, "overton": 1},
    },
}

#: The link depth's three calls: results each keeps, and the place suffix of
#: the second OpenAlex call (C27).
LINK_SEMANTIC_RESULTS = 20
LINK_PLACE_RESULTS = 10
LINK_OVERTON_RESULTS = 10
LINK_PLACE_SUFFIX = " in the United Kingdom"


SR_CLAUSE = '("systematic review" OR "meta-analysis" OR "narrative synthesis")'
RCT_CLAUSE = (
    '("randomized controlled trial" OR "randomised controlled trial" OR '
    '"randomized control trial" OR "randomised control trial")'
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

_SHARED_FILTER_KEYS = {"published_after", "published_before", "sdgs"}
_OPENALEX_FILTER_KEYS = {
    "types",
    "languages",
    "exclude_retracted",
    "exclude_paratext",
    "oa_status",
    "author_affiliation_countries",
}
_OVERTON_FILTER_KEYS = {
    "publisher_type",
    "publisher_country",
    "publisher_source",
    "publisher_region",
    "source_country_post_filter",
    "language",
}
_BACKEND_NAMES = {"openalex", "overton"}
SEMANTIC_ACCEPTED_FILTER_KEYS: frozenset[str] = frozenset(
    {"types", "languages", "exclude_retracted"}
)
# Threads for the independent calls of one leg (the seed batch, the resolve
# batch). The backend's pacing lock, not this number, bounds the request rate.
SEARCH_CONCURRENCY = 8


@dataclass(frozen=True)
class ExecutedCall:
    """One already-executed search call handed to acquire for persistence.

    Attributes:
        backend_name: Backend identifier matching a configured backend.
        verb: Search verb.
        query: Exact query text sent to the backend.
        query_origin: Deterministic origin of the query text.
        wire_params: Executed backend wire parameters, already redacted.
        records: Raw provider records returned by the call.
        status: ``"ok"`` or ``"error"``.
        error: Redacted error string for failed calls.
        post_filter_excluded: Records excluded by a compiled post-filter, or
            ``None`` when no post-filter was active for the call.
    """

    backend_name: str
    verb: CallVerb
    query: str
    query_origin: QueryOrigin
    wire_params: dict[str, str]
    records: list[dict[str, Any]]
    status: CallStatus
    error: str | None
    post_filter_excluded: int | None = None
    pages: int | None = None


@dataclass(frozen=True)
class _PlannedCall:
    backend_name: str
    query: str
    query_origin: QueryOrigin
    group_key: str | None = None
    filter_variant_index: int = 0


# Unified filter-directive validator/raiser family.
#
# Two call paths share these helpers, distinguished by keyword args:
#   - Wire mapping (openalex_wire_params/overton_wire_params) operates on
#     already-validated directive dicts, so it coerces loosely and raises
#     plain ValueError (the defaults below).
#   - Raw-directive validation (validate_scope_filters, via the
#     _validate_*_block functions) operates on untrusted JSON, so it passes
#     error=SearchDirectiveError and strict=True (type-check, no coercion,
#     reject surrounding whitespace) plus accept_list_of_one=False for
#     single-value fields (a list is always invalid there).
#
# To add a new key validator: pick the matching shape helper below, decide
# strict/coerce semantics for the raw-JSON side, and wire it into both an
# openalex/overton wire_params branch and a _validate_*_block branch.


def _str_values(
    key: str,
    value: Any,
    *,
    error: type[Exception] = ValueError,
    strict: bool = False,
) -> list[str]:
    if not isinstance(value, list) or not value:
        raise error(f"{key} must be a non-empty list")
    if not strict:
        return [str(item) for item in value]
    out: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip() or item != item.strip():
            raise error(f"{key} must contain non-empty strings")
        out.append(item)
    return out


def _int_values(
    key: str,
    value: Any,
    min_value: int,
    max_value: int,
    *,
    error: type[Exception] = ValueError,
    strict: bool = False,
) -> list[int]:
    if not isinstance(value, list) or not value:
        raise error(f"{key} must be a non-empty list")
    ints: list[int] = []
    for item in value:
        if strict:
            if isinstance(item, bool) or not isinstance(item, int):
                raise error(f"{key} must contain integers")
            ints.append(item)
        else:
            ints.append(int(item))
    if any(item < min_value or item > max_value for item in ints):
        raise error(f"{key} contains an out-of-range value")
    return ints


def _single_str_value(
    key: str,
    value: Any,
    *,
    error: type[Exception] = ValueError,
    accept_list_of_one: bool = True,
    strict: bool = False,
) -> str:
    if isinstance(value, list):
        if not accept_list_of_one:
            raise error(f"{key} must be a non-empty string")
        if len(value) != 1:
            raise error(f"{key} must be single-valued")
        value = value[0]
    if not strict:
        return str(value)
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise error(f"{key} must be a non-empty string")
    return value


def _enum_values(
    key: str,
    value: Any,
    allowed: tuple[str, ...],
    *,
    error: type[Exception] = ValueError,
    strict: bool = False,
) -> list[str]:
    values = _str_values(key, value, error=error, strict=strict)
    allowed_set = set(allowed)
    unknown = [item for item in values if item not in allowed_set]
    if unknown:
        raise error(f"{key} contains unknown value(s): {unknown}")
    return values


def _single_enum_value(
    key: str,
    value: Any,
    allowed: tuple[str, ...],
    *,
    error: type[Exception] = ValueError,
    accept_list_of_one: bool = True,
    strict: bool = False,
) -> str:
    item = _single_str_value(
        key, value, error=error, accept_list_of_one=accept_list_of_one, strict=strict
    )
    if item not in set(allowed):
        raise error(f"{key} contains unknown value: {item}")
    return item


def _alpha_code_values(
    key: str,
    value: Any,
    *,
    length: int,
    case: Literal["lower", "upper"],
    error: type[Exception] = SearchDirectiveError,
) -> list[str]:
    values = _str_values(key, value, error=error, strict=True)
    for item in values:
        if len(item) != length or not item.isalpha():
            raise error(f"{key} must contain {length}-letter codes")
        if case == "lower" and item != item.lower():
            raise error(f"{key} must contain lowercase codes")
        if case == "upper" and item != item.upper():
            raise error(f"{key} must contain uppercase codes")
    return values


def _single_alpha_code_value(
    key: str,
    value: Any,
    *,
    length: int,
    case: Literal["lower", "upper"],
    error: type[Exception] = SearchDirectiveError,
) -> str:
    text = _single_str_value(key, value, error=error, accept_list_of_one=False, strict=True)
    if len(text) != length or not text.isalpha():
        raise error(f"{key} must be a {length}-letter code")
    if case == "lower" and text != text.lower():
        raise error(f"{key} must be lowercase")
    if case == "upper" and text != text.upper():
        raise error(f"{key} must be uppercase")
    return text


def _iso_date_value(key: str, value: Any, *, error: type[Exception] = SearchDirectiveError) -> str:
    if not isinstance(value, str):
        raise error(f"{key} must be an ISO date string")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise error(f"{key} must be a valid ISO date") from exc
    if parsed.isoformat() != value:
        raise error(f"{key} must be a YYYY-MM-DD ISO date")
    return value


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
            sdg_iris = [f"https://metadata.un.org/sdg/{n}" for n in _int_values(key, value, 1, 17)]
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
            if not isinstance(value, list) or len(value) != 1:
                raise ValueError(f"{key} must be a single-item list")
            sdg = int(value[0])
            if sdg < 1 or sdg > 17:
                raise ValueError(f"{key} contains an out-of-range value")
            params["sdgcategories"] = OVERTON_SDG_LABELS[sdg]
        elif key == "publisher_type":
            params["source_type"] = _single_enum_value(key, value, OVERTON_PUBLISHER_TYPES)
        elif key == "publisher_country":
            params["source_country"] = _single_str_value(key, value)
        elif key == "publisher_source":
            params["source"] = _single_str_value(key, value)
        elif key == "publisher_region":
            params["source_region"] = _single_enum_value(key, value, OVERTON_REGION_GROUPS)
        elif key == "language":
            params["language"] = _single_str_value(key, value)
        elif key == "source_country_post_filter":
            continue
        else:
            raise ValueError(f"unknown Overton filter key: {key}")
    return params


def parse_search_directive(
    context: dict[str, Any],
) -> tuple[SearchDepth, Any | None, list[str] | None]:
    """Parse ``context["search"]`` using the fail-closed directive grammar.

    The former D5 ``target`` key was removed with ``TARGET_CONFIDENT_RELEVANT``
    (task 030): the round cap is the budget, so there is no stop target to
    override. A directive still carrying it is refused as an unknown key —
    honest refusal beats the silent no-op it previously compiled to.

    Args:
        context: Evidence-scope context JSON object.

    Returns:
        ``(depth, raw_filters, guidance)``. Absent directive defaults to rapid
        depth, no filters and no guidance.

    Raises:
        SearchDirectiveError: If the directive has an unknown key, a malformed
            depth value, or a malformed ``guidance`` channel (B1: 1-5
            non-empty, bounded, control-character-free strings).
    """
    raw = context.get("search")
    if raw is None:
        return "rapid", None, None
    if not isinstance(raw, dict):
        raise SearchDirectiveError("search directive must be an object")
    unknown = set(raw) - {"depth", "filters", "guidance", "record_cap"}
    if unknown:
        raise SearchDirectiveError("search directive contains unknown keys")
    # Validated here (this is the fail-closed gate for the whole directive) and
    # read back by `parse_record_cap`, so the 3-tuple this function has always
    # returned is unchanged for its existing callers.
    parse_record_cap(context)
    depth: SearchDepth = "rapid"
    if "depth" in raw:
        raw_depth = raw["depth"]
        if not isinstance(raw_depth, str) or raw_depth not in DEPTH_CONSTANTS:
            raise SearchDirectiveError(
                "search directive depth must be 'rapid', 'standard', 'deep' or 'link'"
            )
        depth = raw_depth
    if "filters" in raw and raw["filters"] is None:
        raise SearchDirectiveError("search directive filters must be an object")
    guidance: list[str] | None = None
    if "guidance" in raw:
        guidance = parse_guidance_channel(
            raw["guidance"], error=SearchDirectiveError, max_chars=DIRECTIVE_STRING_MAX
        )
    return depth, raw.get("filters"), guidance


#: Ceiling on a directive-supplied per-backend record cap: the deepest rung's
#: own cap. A plan may ask for *less* volume than its depth rung buys — the
#: options-scoping baseline does (a narrow question about the status quo, task
#: 044 D7) — but never for more than the deepest rung is budgeted for.
RECORD_CAP_MAX = DEPTH_CONSTANTS["deep"]["papers_cap"]


def parse_record_cap(context: dict[str, Any]) -> int | None:
    """Parse the optional per-backend record cap from ``context["search"]``.

    Added by task 044 (plan S2): the volume brake was previously reachable only
    through the depth rung, so a plan whose question is narrow by construction
    had no way to buy a smaller acquisition than ``rapid``'s own caps. The key
    is optional and additive — an absent value keeps the depth rung's
    ``papers_cap`` / ``policy_cap`` exactly as before.

    Args:
        context: Evidence-scope context JSON object.

    Returns:
        The requested cap, or ``None`` to use the depth rung's own.

    Raises:
        SearchDirectiveError: If the value is not an integer in
            ``1..RECORD_CAP_MAX``.
    """
    raw = context.get("search")
    if not isinstance(raw, dict) or "record_cap" not in raw:
        return None
    value = raw["record_cap"]
    if isinstance(value, bool) or not isinstance(value, int):
        raise SearchDirectiveError("search directive record_cap must be an integer")
    if not 1 <= value <= RECORD_CAP_MAX:
        raise SearchDirectiveError(
            f"search directive record_cap must be between 1 and {RECORD_CAP_MAX}"
        )
    return value


def _object_block(raw: Any, *, label: str) -> dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise SearchDirectiveError(f"{label} must be an object")
    return cast(dict[str, Any], raw)


def _validate_shared_block(block: dict[str, Any]) -> dict[str, Any]:
    unknown = set(block) - _SHARED_FILTER_KEYS
    if unknown:
        raise SearchDirectiveError("shared search filters contain unknown keys")
    out: dict[str, Any] = {}
    for key, value in block.items():
        if key in {"published_after", "published_before"}:
            out[key] = _iso_date_value(key, value)
        elif key == "sdgs":
            out[key] = _int_values(key, value, 1, 17, error=SearchDirectiveError, strict=True)
    return out


def _validate_openalex_block(block: dict[str, Any]) -> dict[str, Any]:
    unknown = set(block) - _OPENALEX_FILTER_KEYS
    if unknown:
        raise SearchDirectiveError("OpenAlex search filters contain unknown keys")
    out: dict[str, Any] = {}
    for key, value in block.items():
        if key == "types":
            out[key] = _enum_values(
                key, value, OPENALEX_TYPES, error=SearchDirectiveError, strict=True
            )
        elif key == "languages":
            out[key] = _alpha_code_values(key, value, length=2, case="lower")
        elif key in {"exclude_retracted", "exclude_paratext"}:
            if not isinstance(value, bool):
                raise SearchDirectiveError(f"{key} must be a boolean")
            out[key] = value
        elif key == "oa_status":
            out[key] = _enum_values(
                key, value, OA_STATUS_VALUES, error=SearchDirectiveError, strict=True
            )
        elif key == "author_affiliation_countries":
            countries = _alpha_code_values(key, value, length=2, case="upper")
            if len(countries) > 200:
                raise SearchDirectiveError(
                    "author_affiliation_countries must contain at most 200 codes"
                )
            out[key] = validate_iso_alpha2(countries)
    return out


def _overton_post_filter_values(key: str, value: Any) -> list[str]:
    if not isinstance(value, list):
        raise SearchDirectiveError(f"{key} must be a list")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str) or item != item.strip():
            raise SearchDirectiveError(f"{key} must contain display-country strings")
        if item not in OVERTON_DISPLAY_ALLOWLIST:
            raise SearchDirectiveError(f"{key} contains an unsupported Overton country")
        out.append(item)
    return out


def _validate_overton_block(block: dict[str, Any]) -> dict[str, Any]:
    unknown = set(block) - _OVERTON_FILTER_KEYS
    if unknown:
        raise SearchDirectiveError("Overton search filters contain unknown keys")
    out: dict[str, Any] = {}
    for key, value in block.items():
        if key == "publisher_type":
            out[key] = _single_enum_value(
                key,
                value,
                OVERTON_PUBLISHER_TYPES,
                error=SearchDirectiveError,
                accept_list_of_one=False,
                strict=True,
            )
        elif key == "publisher_country":
            country = _single_str_value(
                key, value, error=SearchDirectiveError, accept_list_of_one=False, strict=True
            )
            out[key] = validate_overton_display_name(country, field_name=key)
        elif key == "publisher_source":
            source = _single_str_value(
                key, value, error=SearchDirectiveError, accept_list_of_one=False, strict=True
            )
            if source != "apo":
                raise SearchDirectiveError(f"{key} contains an unsupported Overton source")
            out[key] = source
        elif key == "publisher_region":
            out[key] = _single_enum_value(
                key,
                value,
                OVERTON_REGION_GROUPS,
                error=SearchDirectiveError,
                accept_list_of_one=False,
                strict=True,
            )
        elif key == "language":
            out[key] = _single_alpha_code_value(key, value, length=3, case="lower")
        elif key == "source_country_post_filter":
            out[key] = _overton_post_filter_values(key, value)
    return out


def validate_scope_filters(
    raw: Any,
    *,
    backend_names: list[str],
) -> dict[str, dict[str, Any]]:
    """Validate search-scope filters and return per-backend directive dictionaries.

    Args:
        raw: Raw ``context["search"]["filters"]`` value.
        backend_names: Backends included in this acquire run.

    Returns:
        Per-backend validated directive dictionaries. Empty dictionaries are
        included for backends without filters.

    Raises:
        SearchDirectiveError: If the filter shape, keys, values, or backend
            scope is invalid.
    """
    if raw is None:
        return {name: {} for name in backend_names}
    top = _object_block(raw, label="search filters")
    unknown_top = set(top) - {"shared", "openalex", "overton"}
    if unknown_top:
        raise SearchDirectiveError("search filters contain unknown top-level keys")

    backend_set = set(backend_names)
    if "openalex" in top and "openalex" not in backend_set:
        raise SearchDirectiveError("OpenAlex filters supplied outside backend scope")
    if "overton" in top and "overton" not in backend_set:
        raise SearchDirectiveError("Overton filters supplied outside backend scope")

    shared = _validate_shared_block(_object_block(top.get("shared"), label="shared filters"))
    if "overton" in backend_set and len(shared.get("sdgs", [])) > 1:
        raise SearchDirectiveError("shared sdgs must be single-valued when Overton is in scope")
    openalex_block = _validate_openalex_block(
        _object_block(top.get("openalex"), label="OpenAlex filters")
    )
    overton_block = _validate_overton_block(
        _object_block(top.get("overton"), label="Overton filters")
    )

    validated: dict[str, dict[str, Any]] = {}
    for backend_name in backend_names:
        if backend_name not in _BACKEND_NAMES:
            validated[backend_name] = {}
            continue
        merged = dict(shared)
        if backend_name == "openalex":
            merged.update(openalex_block)
        elif backend_name == "overton":
            merged.update(overton_block)
        validated[backend_name] = merged
    return validated


def to_wire_params(backend_name: str, validated: dict[str, Any]) -> dict[str, str]:
    """Map one backend's validated directive dictionary to provider wire params.

    Args:
        backend_name: Backend identifier.
        validated: Validated per-backend directive dictionary.

    Returns:
        Provider wire parameters for executed calls.

    Raises:
        SearchDirectiveError: If the backend is unsupported or the mapping
            rejects a directive key.
    """
    try:
        if backend_name == "openalex":
            return openalex_wire_params(validated)
        if backend_name == "overton":
            return overton_wire_params(validated)
    except ValueError as exc:
        raise SearchDirectiveError(str(exc)) from exc
    raise SearchDirectiveError(f"unsupported search backend for filters: {backend_name}")


def _filter_variants(backend_name: str, validated: dict[str, Any]) -> list[dict[str, Any]]:
    if backend_name != "openalex":
        return [validated]
    countries = validated.get("author_affiliation_countries")
    if not isinstance(countries, list) or len(countries) <= 100:
        return [validated]
    if len(countries) > 200:
        raise SearchDirectiveError("author_affiliation_countries must contain at most 200 codes")
    return [
        {**validated, "author_affiliation_countries": countries[start : start + 100]}
        for start in range(0, len(countries), 100)
    ]


def _scope_wire_params_payload(
    wire_params_by_backend: dict[str, list[dict[str, str]]],
) -> dict[str, Any]:
    return {
        name: variants[0] if len(variants) == 1 else {"variants": variants}
        for name, variants in wire_params_by_backend.items()
    }


def count_search_runs(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    scope_id: uuid.UUID,
) -> int:
    """Count completed search runs for a scope (one coverage row per run).

    ``run_search`` reports its ``round_index`` from this (1 on a fresh scope;
    a check-in steer that re-runs the search on the same scope counts up).
    Search is one pass at every scope (task 051); historical rows from the
    round loop still count.

    Args:
        conn: Open database connection.
        task_id: Owning task.
        scope_id: Evidence scope being searched.

    Returns:
        Number of ``search_coverage_record`` rows for the scope.
    """
    count = conn.execute(
        select(func.count())
        .select_from(search_coverage_record)
        .where(search_coverage_record.c.task_id == task_id)
        .where(search_coverage_record.c.evidence_scope_id == scope_id)
    ).scalar_one()
    return int(count)


def _compose_variant(query: str, clause: str) -> str:
    return f"({query}) AND {clause}"


def _rapid_plans(
    *,
    backend_name: str,
    intent: str,
    queries: list[str],
    overton_paraphrases: list[str],
) -> list[_PlannedCall]:
    if backend_name == "openalex":
        plans: list[_PlannedCall] = []
        for query in queries[:N_QUERIES]:
            plans.extend(
                [
                    _PlannedCall(backend_name, query, "generated", group_key=query),
                    _PlannedCall(
                        backend_name,
                        _compose_variant(query, SR_CLAUSE),
                        "variant_sr",
                        group_key=query,
                    ),
                    _PlannedCall(
                        backend_name,
                        _compose_variant(query, RCT_CLAUSE),
                        "variant_rct",
                        group_key=query,
                    ),
                ]
            )
        return plans
    if backend_name == "overton":
        return [
            _PlannedCall(backend_name, intent, "verbatim"),
            *[
                _PlannedCall(backend_name, paraphrase, "paraphrase")
                for paraphrase in overton_paraphrases
            ],
        ]
    return []


def _semantic_filter_parts(validated: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
    """Split the plan's OpenAlex filters for one semantic-search call.

    The semantic endpoint accepts only some of the filters the keyword endpoint
    takes (probe of 2026-10-09). The accepted ones go on the wire. A date range
    goes on the wire as a publication-year fence, which the endpoint accepts,
    and the exact dates are then checked locally. Every other filter is checked
    locally on the returned records (``_semantic_record_passes``), so the
    directive always holds and the semantic leg never has to be skipped.

    Args:
        validated: The validated OpenAlex filter block (one filter variant).

    Returns:
        The wire params to send, and the sorted directive keys applied locally.
    """
    accepted = {k: v for k, v in validated.items() if k in SEMANTIC_ACCEPTED_FILTER_KEYS}
    wire = openalex_wire_params(accepted)
    fence: list[str] = []
    if "published_after" in validated:
        fence.append(f"publication_year:>{int(str(validated['published_after'])[:4]) - 1}")
    if "published_before" in validated:
        fence.append(f"publication_year:<{int(str(validated['published_before'])[:4]) + 1}")
    if fence:
        parts = [wire["filter"]] if wire.get("filter") else []
        wire["filter"] = ",".join([*parts, *fence])
    local = sorted(
        key
        for key, value in validated.items()
        if key not in SEMANTIC_ACCEPTED_FILTER_KEYS and (value or key != "exclude_paratext")
    )
    return wire, local


def _semantic_record_passes(validated: dict[str, Any], record: dict[str, Any]) -> bool:
    """Check one semantic-search record against the filters applied locally.

    Args:
        validated: The validated OpenAlex filter block.
        record: A raw OpenAlex work with the ``OA_SELECT`` fields.

    Returns:
        True when the record satisfies every locally applied filter.
    """
    published = str(record.get("publication_date") or "")
    after = validated.get("published_after")
    if after and (not published or published < str(after)):
        return False
    before = validated.get("published_before")
    if before and (not published or published > str(before)):
        return False
    sdgs = validated.get("sdgs")
    if sdgs:
        wanted = {f"https://metadata.un.org/sdg/{number}" for number in sdgs}
        goals = record.get("sustainable_development_goals") or []
        found = {goal.get("id") for goal in goals if isinstance(goal, dict)}
        if not wanted & found:
            return False
    if validated.get("exclude_paratext") and record.get("is_paratext"):
        return False
    statuses = validated.get("oa_status")
    if statuses:
        open_access = record.get("open_access")
        status = open_access.get("oa_status") if isinstance(open_access, dict) else None
        if status not in set(statuses):
            return False
    countries = validated.get("author_affiliation_countries")
    return not countries or pool.country_predicate(record, set(countries))


def _semantic_scope(
    variants: list[dict[str, Any]],
) -> tuple[dict[str, str], list[str], Callable[[dict[str, Any]], bool] | None, list[str]]:
    """The wire params, local filters and local check every semantic call shares.

    The variants split only the keyword calls' country clause (at most 100
    codes per request); every local country check sees the whole list.

    Returns:
        ``(wire, local_filters, keep, countries)``.
    """
    countries = [
        code for variant in variants for code in variant.get("author_affiliation_countries") or []
    ]
    local_scope = (
        {**variants[0], "author_affiliation_countries": countries} if countries else variants[0]
    )
    wire, local_filters = _semantic_filter_parts(local_scope)
    keep = (lambda record: _semantic_record_passes(local_scope, record)) if local_filters else None
    return wire, local_filters, keep, countries


def _without_country_filter(wire_params: dict[str, str]) -> dict[str, str]:
    """Drop the affiliation-country clause from an OpenAlex wire filter.

    The resolve and forward calls carry every wire filter except this one,
    which is applied locally to the citation-found papers instead, so a
    two-variant country split does not double those calls.
    """
    parts = [
        part
        for part in wire_params.get("filter", "").split(",")
        if part and not part.startswith("authorships.countries:")
    ]
    return {"filter": ",".join(parts)} if parts else {}


def _overton_country(record: dict[str, Any]) -> str | None:
    source = record.get("source")
    return source.get("country") if isinstance(source, dict) else None


PoolEntry = tuple[dict[str, Any], str, str]
"""One record handed to acquire: ``(record, query_origin, verb)``."""

Fetch = Callable[[int], list[dict[str, Any]]]
"""A bound provider call: give it the page size, get the records."""


def _search_fetch(backend: acquire.SearchBackendBase, query: str, wire: dict[str, str]) -> Fetch:
    return lambda size: backend.search(query, wire_params=wire, max_results=size)


def _semantic_fetch(
    backend: acquire.ExtendedSearchBackend, text: str, wire: dict[str, str]
) -> Fetch:
    return lambda size: backend.search_semantic(text, wire_params=wire, max_results=size)


def _lookup_fetch(
    backend: acquire.ExtendedSearchBackend, ids: list[str], wire: dict[str, str]
) -> Fetch:
    return lambda _size: backend.lookup_ids(ids, wire_params=wire)


def _citing_fetch(
    backend: acquire.ExtendedSearchBackend, ids: list[str], wire: dict[str, str], page: int
) -> Fetch:
    return lambda size: backend.fetch_citing(ids, wire_params=wire, max_results=size, page=page)


def _by_id_fetch(backend: acquire.ExtendedSearchBackend, document_id: str) -> Fetch:
    def fetch(_size: int) -> list[dict[str, Any]]:
        record = backend.fetch_by_id(document_id)
        return [record] if record is not None else []

    return fetch


@dataclass(frozen=True)
class _CallSpec:
    """One planned logical call: what to send and how to read the answer."""

    verb: CallVerb
    query: str
    origin: QueryOrigin
    wire_params: dict[str, str]
    max_records: int
    fetch: Fetch
    keep: Callable[[dict[str, Any]], bool] | None = None


@dataclass
class _Pass:
    """What one backend's leg has called so far, and the budget it works under.

    One instance per backend leg (the two legs run side by side), so every
    field has a single writer; ``run_search`` merges the legs in backend order.

    Attributes:
        constants: The depth's caps and call budgets.
        variant_count: Filter variants per backend (the OpenAlex budget is per variant).
        executed: Every logical call, in plan order, for acquire's events and counts.
        calls: Logical calls made per backend.
        origin_of: The origin and verb of the call that returned each record
            object, keyed by ``id(record)``.
        ranked_count: How many records the ranking produced per backend.
    """

    constants: DepthConstants
    variant_count: dict[str, int]
    executed: list[ExecutedCall] = field(default_factory=list)
    calls: dict[str, int] = field(default_factory=dict)
    origin_of: dict[int, tuple[str, str]] = field(default_factory=dict)
    ranked_count: dict[str, int] = field(default_factory=dict)

    def _reserve(self, backend: acquire.SearchBackendBase) -> bool:
        """Claim one logical call against the backend's budget, in plan order."""
        budget = self.constants["call_budget"].get(backend.name, 0)
        budget *= self.variant_count.get(backend.name, 1) if backend.name == "openalex" else 1
        if self.calls.get(backend.name, 0) >= budget:
            return False
        self.calls[backend.name] = self.calls.get(backend.name, 0) + 1
        return True

    def _finish(
        self,
        backend: acquire.SearchBackendBase,
        spec: _CallSpec,
        fetched: list[dict[str, Any]] | BaseException,
    ) -> ExecutedCall:
        """Turn one fetch outcome into the executed call and record it.

        A logical call is one planned request however the transport pages or
        retries underneath (contract D12). ``spec.keep`` is a local filter
        applied to the returned records; what it drops is counted on the call
        as ``post_filter_excluded``, beside anything the backend itself
        excluded. The backend's per-request fields (``last_post_filter_excluded``,
        ``last_pages``) are read here, so a call that needs them must run
        through ``execute``, never ``execute_batch``.
        """
        if isinstance(fetched, BaseException):
            call = ExecutedCall(
                backend_name=backend.name,
                verb=spec.verb,
                query=spec.query,
                query_origin=spec.origin,
                wire_params=spec.wire_params,
                records=[],
                status="error",
                error=str(fetched),
            )
        else:
            # Copies: a backend may hand back the same record objects on every
            # call (the fixtures do), and the pool bookkeeping is by object.
            records = [dict(record) for record in fetched[: spec.max_records]]
            excluded = (
                getattr(backend, "last_post_filter_excluded", None)
                if spec.verb == "search"
                else None
            )
            if spec.keep is not None:
                kept = [record for record in records if spec.keep(record)]
                excluded = (excluded or 0) + len(records) - len(kept)
                records = kept
            call = ExecutedCall(
                backend_name=backend.name,
                verb=spec.verb,
                query=spec.query,
                query_origin=spec.origin,
                wire_params=spec.wire_params,
                records=records,
                status="ok",
                error=None,
                post_filter_excluded=excluded,
                pages=getattr(backend, "last_pages", None) if spec.verb == "search" else None,
            )
        self.executed.append(call)
        for record in call.records:
            self.origin_of.setdefault(id(record), (spec.origin, spec.verb))
        return call

    def execute(self, backend: acquire.SearchBackendBase, spec: _CallSpec) -> ExecutedCall | None:
        """Make one logical call now, or skip it when the backend's budget is spent."""
        if not self._reserve(backend):
            return None
        try:
            fetched: list[dict[str, Any]] | BaseException = spec.fetch(spec.max_records)
        except Exception as exc:
            fetched = exc
        return self._finish(backend, spec, fetched)

    def execute_batch(
        self, backend: acquire.SearchBackendBase, specs: list[_CallSpec]
    ) -> list[ExecutedCall | None]:
        """Make independent logical calls concurrently, recorded in plan order.

        The budget is reserved for each spec in plan order first (a spec past
        the budget is skipped, as a sequential run would skip it), the fetches
        run in a thread pool under the caller's tracing context, and the calls
        are recorded in plan order, so events, counts and pool order are the
        same as a sequential run. The backend's pacing lock keeps the request
        rate within its interval whatever the thread count.
        """
        admitted = [spec for spec in specs if self._reserve(backend)]
        outcomes: list[list[dict[str, Any]] | BaseException] = []
        with ThreadPoolExecutor(max_workers=SEARCH_CONCURRENCY) as executor:
            futures = [
                tracing.submit_with_context(executor, spec.fetch, spec.max_records)
                for spec in admitted
            ]
            for future in futures:
                try:
                    outcomes.append(future.result())
                except Exception as exc:
                    outcomes.append(exc)
        results: list[ExecutedCall | None] = [
            self._finish(backend, spec, outcome)
            for spec, outcome in zip(admitted, outcomes, strict=True)
        ]
        results.extend([None] * (len(specs) - len(admitted)))
        return results

    def entries(self, ranked: list[dict[str, Any]], backend_name: str) -> list[PoolEntry]:
        """The pool handed to acquire: the ranked records, then every other record.

        Every record a call returned is listed exactly once, so acquire's count
        invariant holds: the ranked ones first (persisted up to the cap), then
        duplicate copies and the records the ranking left out, which the cap
        (never larger than the ranked list, see ``run_search``) counts as
        already acquired or dropped over the cap.
        """
        self.ranked_count[backend_name] = len(ranked)
        placed = {id(record) for record in ranked}
        out: list[PoolEntry] = [(record, *self.origin_of[id(record)]) for record in ranked]
        for call in self.executed:
            if call.backend_name != backend_name:
                continue
            for record in call.records:
                if id(record) not in placed:
                    placed.add(id(record))
                    out.append((record, *self.origin_of[id(record)]))
        return out


@dataclass
class _LegSummary:
    """Counts one backend's leg reports into the ``search`` summary."""

    zero_result_queries: int = 0
    fallback_to_verbatim: bool = False
    seeds: int = 0
    backward_targets: int = 0
    forward_candidates: int = 0
    duplicate_papers: int = 0
    landmarks: int = 0


def _openalex_leg(
    search: _Pass,
    backend: acquire.SearchBackendBase,
    *,
    intent: str,
    queries: list[str],
    paraphrases: list[str],
    variants: list[dict[str, Any]],
    wires: list[dict[str, str]],
) -> tuple[list[PoolEntry], _LegSummary, list[str]]:
    """Seeds, backward snowball, forward chase, ranking: the paper pool.

    Returns the pool entries, the leg's counts, and the semantic filters applied locally.
    """
    summary = _LegSummary()
    extended = cast(acquire.ExtendedSearchBackend, backend)

    # 1. Seeds, one concurrent batch: each generated query as written and with
    #    the systematic-review and randomised-trial clauses, per filter variant
    #    (keyword), then the question, the paraphrases and the queries through
    #    the embedding search (semantic). Filters the semantic endpoint rejects
    #    are applied locally (the country filter included), so one set of
    #    semantic calls serves every variant.
    keyword_plans: list[tuple[_PlannedCall, dict[str, str]]] = [
        (plan, wire)
        for wire in wires
        for plan in _rapid_plans(
            backend_name="openalex", intent=intent, queries=queries, overton_paraphrases=[]
        )
    ]
    keyword_specs = [
        _CallSpec(
            verb="search",
            query=plan.query,
            origin=plan.query_origin,
            wire_params=wire,
            max_records=pool.KEYWORD_PER_CALL,
            fetch=_search_fetch(backend, plan.query, wire),
        )
        for plan, wire in keyword_plans
    ]
    semantic_wire, local_filters, keep, countries = _semantic_scope(variants)
    semantic_specs = [
        _CallSpec(
            verb="search_semantic",
            query=text,
            origin="semantic",
            wire_params=semantic_wire,
            max_records=pool.SEMANTIC_PER_CALL,
            fetch=_semantic_fetch(extended, text, semantic_wire),
            keep=keep,
        )
        for text in [intent, *paraphrases[:2], *queries[:N_QUERIES]]
    ]
    results = search.execute_batch(backend, [*keyword_specs, *semantic_specs])
    keyword = [
        (plan, call)
        for (plan, _wire), call in zip(keyword_plans, results[: len(keyword_specs)], strict=True)
        if call is not None
    ]
    semantic = [call for call in results[len(keyword_specs) :] if call is not None]

    # 2. The fallback decision reads the completed keyword calls (a barrier):
    #    every generated query came back empty, so search the verbatim intent,
    #    loudly (ADR 0012 decision 2), one call per filter variant.
    groups: dict[str, list[ExecutedCall]] = {}
    for plan, call in keyword:
        groups.setdefault(plan.group_key or plan.query, []).append(call)
    summary.zero_result_queries = sum(
        1 for calls in groups.values() if all(c.status == "ok" and not c.records for c in calls)
    )
    if all(c.status == "ok" and not c.records for _, c in keyword):
        summary.fallback_to_verbatim = True
        fallback_specs = [
            _CallSpec(
                verb="search",
                query=intent,
                origin="fallback_verbatim",
                wire_params=wire,
                max_records=pool.KEYWORD_PER_CALL,
                fetch=_search_fetch(backend, intent, wire),
            )
            for wire in wires
        ]
        for fallback_call in search.execute_batch(backend, fallback_specs):
            if fallback_call is not None:
                keyword.append(
                    (_PlannedCall("openalex", intent, "fallback_verbatim"), fallback_call)
                )

    # 3. The seeds are the first SEEDS distinct works, interleaved by rank.
    lists = [call.records for _, call in keyword] + [call.records for call in semantic]
    seeds = pool.interleave(lists, pool.record_short_id)[: pool.SEEDS]
    seed_ids = {work_id for record in seeds if (work_id := pool.record_short_id(record))}
    counts = pool.count_references(seeds)
    summary.seeds = len(seeds)

    # 4. Citation chasing carries every wire filter except the country clause,
    #    which is checked locally on the citation-found papers.
    citation_wire = _without_country_filter(wires[0])
    country_keep = (
        (lambda record: pool.country_predicate(record, set(countries))) if countries else None
    )

    # 5. Backward: resolve the works the seeds cite most, 50 ids per call, one
    #    concurrent batch.
    targets = pool.backward_targets(counts, seed_ids, pool.BACKWARD_EXPAND)
    summary.backward_targets = len(targets)
    resolve_specs = [
        _CallSpec(
            verb="fetch_references",
            query="|".join(batch),
            origin="snowball_backward",
            wire_params=citation_wire,
            max_records=pool.RESOLVE_BATCH,
            fetch=_lookup_fetch(extended, batch, citation_wire),
            keep=country_keep,
        )
        for batch in (
            targets[start : start + pool.RESOLVE_BATCH]
            for start in range(0, len(targets), pool.RESOLVE_BATCH)
        )
    ]
    backward: list[dict[str, Any]] = []
    for resolved in search.execute_batch(backend, resolve_specs):
        if resolved is not None:
            backward.extend(resolved.records)

    # 6. Forward: the works that cite the best-connected seeds, paged until a
    #    short page (so sequential), 100 seed ids per request.
    chased = pool.forward_seeds(
        seeds, counts, top=pool.FORWARD_TOP, max_cites=pool.FORWARD_MAX_CITES
    )
    citing: list[dict[str, Any]] = []
    for start in range(0, len(chased), pool.FORWARD_IDS_PER_CALL):
        ids = chased[start : start + pool.FORWARD_IDS_PER_CALL]
        for page in range(1, pool.FORWARD_PAGES + 1):
            page_call = search.execute(
                backend,
                _CallSpec(
                    verb="fetch_citations",
                    query="|".join(ids),
                    origin="snowball_forward",
                    wire_params=citation_wire,
                    max_records=pool.KEYWORD_PER_CALL,
                    fetch=_citing_fetch(extended, ids, citation_wire, page),
                    keep=country_keep,
                ),
            )
            if page_call is None or page_call.status != "ok":
                break
            citing.extend(page_call.records)
            if (
                len(page_call.records) + (page_call.post_filter_excluded or 0)
                < pool.KEYWORD_PER_CALL
            ):
                break
    forward = pool.score_forward(citing, seed_ids, counts, excluded_ids=set(targets))
    forward = forward[: pool.FORWARD_KEEP]
    summary.forward_candidates = len(forward)

    # 7. One pool over seeds, backward and forward candidates: duplicate copies
    #    of a paper (same title and authors) dropped, then the relevant /
    #    seminal / novel mix so every cut holds all three (ADR 0038, amended).
    seeded = [(record, search.origin_of[id(record)][0]) for record in seeds]
    cands = pool.paper_candidates(seeded, backward, forward, counts)
    unique = pool.dedupe_papers(cands)
    summary.duplicate_papers = len(cands) - len(unique)
    ranked = pool.rank_mix(unique, lists, novel_from_year=date.today().year - pool.NOVEL_YEARS)
    return search.entries([c.record for c in ranked], "openalex"), summary, local_filters


def _overton_fetch(
    backend: acquire.SearchBackendBase, validated: dict[str, Any], wire: dict[str, str]
) -> Callable[[str], Fetch]:
    """The Overton search for one text, with the source-country post filter when set.

    Raises:
        SearchDirectiveError: If the post filter is set and the backend cannot apply it.
    """
    post_filter = validated.get("source_country_post_filter")
    if isinstance(post_filter, list) and not hasattr(backend, "search_with_post_filter"):
        # Fail closed: silently searching unfiltered would admit
        # out-of-group records with no provenance trace.
        raise SearchDirectiveError(
            "source_country_post_filter requires an Overton backend "
            "with search_with_post_filter; refusing to search unfiltered"
        )

    def fetch_for(query: str) -> Fetch:
        if isinstance(post_filter, list):
            return lambda size: cast(
                list[dict[str, Any]],
                cast(Any, backend).search_with_post_filter(
                    query,
                    wire_params=wire,
                    source_country_post_filter=post_filter,
                    max_results=size,
                ),
            )
        return _search_fetch(backend, query, wire)

    return fetch_for


def _link_pools(
    passes: dict[str, _Pass],
    backends: list[acquire.SearchBackendBase],
    *,
    text: str,
    cap: int,
    variants: dict[str, list[dict[str, Any]]],
    validated: dict[str, dict[str, Any]],
    wires: dict[str, list[dict[str, str]]],
) -> tuple[dict[str, list[PoolEntry]], list[str]]:
    """The link depth's search: three calls on one sentence, ``cap`` records at most (C27).

    OpenAlex semantic search on the sentence (origin ``semantic``) and on the
    sentence with :data:`LINK_PLACE_SUFFIX` (``semantic_place``), and Overton,
    itself a search by meaning, on the sentence (``verbatim``). No query
    generation, keyword calls, citation chasing or landmarks. Duplicates are
    dropped by the usual paper and policy keys, the copy from the earlier list
    kept. Each record's origin and pool rank go on its ``source.acquired``
    event, and each list's own order survives in the pool rank, so the check
    walk's selection step can rebuild the three ranked lists.

    Returns:
        The pool entries per backend (the kept records first, so acquire's cap
        is the number kept), and the semantic filters applied locally.
    """
    found: dict[str, list[list[dict[str, Any]]]] = {}
    backend_of: dict[int, str] = {}
    local_filters: list[str] = []
    for backend in backends:
        search = passes[backend.name]
        calls: list[ExecutedCall | None] = []
        if backend.name == "openalex":
            extended = cast(acquire.ExtendedSearchBackend, backend)
            wire, local_filters, keep, _ = _semantic_scope(variants["openalex"])
            semantic_calls: list[tuple[str, int, QueryOrigin]] = [
                (text, LINK_SEMANTIC_RESULTS, "semantic"),
                (text + LINK_PLACE_SUFFIX, LINK_PLACE_RESULTS, "semantic_place"),
            ]
            calls = search.execute_batch(
                backend,
                [
                    _CallSpec(
                        verb="search_semantic",
                        query=query,
                        origin=origin,
                        wire_params=wire,
                        max_records=size,
                        fetch=_semantic_fetch(extended, query, wire),
                        keep=keep,
                    )
                    for query, size, origin in semantic_calls
                ],
            )
        elif backend.name == "overton":
            wire = wires["overton"][0]
            calls = [
                search.execute(
                    backend,
                    _CallSpec(
                        verb="search",
                        query=text,
                        origin="verbatim",
                        wire_params=wire,
                        max_records=LINK_OVERTON_RESULTS,
                        fetch=_overton_fetch(backend, validated["overton"], wire)(text),
                    ),
                )
            ]
        for call in calls:
            if call is not None:
                found.setdefault(backend.name, []).append(call.records)
                backend_of.update({id(record): backend.name for record in call.records})

    def key(record: dict[str, Any]) -> str:
        if backend_of[id(record)] == "overton":
            return "overton:" + pool.policy_key(record)
        return "openalex:" + pool.paper_key(record)

    lists = [*found.get("openalex", []), *found.get("overton", [])]
    kept = pool.interleave(lists, key)[:cap]
    pools = {
        backend.name: passes[backend.name].entries(
            [record for record in kept if backend_of[id(record)] == backend.name], backend.name
        )
        for backend in backends
    }
    return pools, local_filters


def _overton_leg(
    search: _Pass,
    backend: acquire.SearchBackendBase,
    *,
    intent: str,
    paraphrases: list[str],
    validated: dict[str, Any],
    wire: dict[str, str],
) -> tuple[list[PoolEntry], _LegSummary]:
    """Relevance results, title dedup, landmarks, ranking: the policy pool."""
    summary = _LegSummary()
    post_filter = validated.get("source_country_post_filter")
    fetch_for = _overton_fetch(backend, validated, wire)

    # 1. Three relevance-ordered searches sharing OVERTON_DOCS documents.
    per_text = -(-pool.OVERTON_DOCS // 3)
    searches: list[ExecutedCall] = []
    for plan in _rapid_plans(
        backend_name="overton", intent=intent, queries=[], overton_paraphrases=paraphrases
    ):
        call = search.execute(
            backend,
            _CallSpec(
                verb="search",
                query=plan.query,
                origin=plan.query_origin,
                wire_params=wire,
                max_records=per_text,
                fetch=fetch_for(plan.query),
            ),
        )
        if call is not None:
            searches.append(call)
    summary.zero_result_queries = sum(
        1
        for call in searches
        if call.query_origin == "paraphrase" and call.status == "ok" and not call.records
    )

    # 2. Interleave by rank, drop title duplicates (best-ranked copy kept).
    results = pool.dedupe_policy(
        pool.interleave(
            [call.records for call in searches], lambda r: r.get("policy_document_id") or None
        )
    )
    counts = pool.count_policy_cites(results)
    result_ids = {str(record.get("policy_document_id")) for record in results}

    # 3. Landmarks: the documents the results cite most and the search missed.
    country_keep = (
        (lambda record: _overton_country(record) in set(post_filter))
        if isinstance(post_filter, list)
        else None
    )
    landmarks: list[dict[str, Any]] = []
    for document_id in pool.landmark_targets(counts, result_ids, pool.OVERTON_LANDMARKS):
        call = search.execute(
            backend,
            _CallSpec(
                verb="fetch_by_id",
                query=document_id,
                origin="landmark",
                wire_params={},
                max_records=1,
                fetch=_by_id_fetch(cast(acquire.ExtendedSearchBackend, backend), document_id),
                keep=country_keep,
            ),
        )
        if call is not None:
            landmarks.extend(call.records)
    summary.landmarks = len(landmarks)

    # 4. One ranked pool over results and landmarks.
    seeded = [(record, search.origin_of[id(record)][0]) for record in results]
    ranked = pool.rank_policy(seeded, landmarks, counts)
    return search.entries([c.record for c in ranked], "overton"), summary


def run_search(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    context: acquire.AcquireContext,
    backends: list[acquire.SearchBackendBase],
    generation_backend: SearchGenerationBackend,
    embedder: EmbeddingBackend | None = None,
) -> dict[str, Any]:
    """Run the single search pass and persist the two capped pools.

    Every scope runs the same pass once (task 051, ADR 0038): one
    query-generation call, OpenAlex keyword and semantic seeds, backward and
    forward citation chasing, Overton relevance results and their landmarks,
    two specificity-ranked pools cut at the scope's two caps. Every planned
    call runs; there is no wall clock (task 030). Volume is bounded by the
    caps at acquisition and by the logical-call budgets here.

    Args:
        conn: Open database connection; writes are delegated to acquire.
        task_id: Owning task.
        run_id: The acquire run id.
        context: Scope-level acquire context.
        backends: Configured search backends, executed in list order.
        generation_backend: Query generation backend.
        embedder: Optional embedding backend passed through to acquire.

    Returns:
        Acquire counts with an added ``search`` summary dictionary.

    Raises:
        SearchDirectiveError: If the search directive or filters are malformed.
        RuntimeError: If generation fails.
    """
    depth, raw_filters, guidance = parse_search_directive(context.context)
    constants = DEPTH_CONSTANTS[depth]
    names = [backend.name for backend in backends]
    validated = validate_scope_filters(raw_filters, backend_names=names)
    variants = {name: _filter_variants(name, validated[name]) for name in names}
    wires = {name: [to_wire_params(name, item) for item in variants[name]] for name in names}
    scope_wire_params = _scope_wire_params_payload(wires) if raw_filters is not None else None
    round_index = count_search_runs(conn, task_id=task_id, scope_id=context.scope_id) + 1
    record_cap = parse_record_cap(context.context)
    started = time.monotonic()

    usage_totals = UsageAccumulator()
    queries: list[str] = []
    paraphrases: list[str] = []
    queries_dropped = 0
    generation_calls = 0
    if depth != "link":
        wire, usage = generation_backend.generate_queries(
            QueriesPayload(intent=context.intent, guidance=guidance)
        )
        usage_totals.add(usage)
        queries, paraphrases = validated_queries(wire)
        queries_dropped = len(wire.queries) - len(queries)
        generation_calls = 1

    # The two legs run side by side (plan S13): one pass state per backend, so
    # each has a single writer; the legs never touch the database connection;
    # they are merged in backend-list order below, so the events, counts and
    # pool order are the same as a sequential run.
    variant_count = {name: len(variants[name]) for name in names}
    passes = {name: _Pass(constants, variant_count) for name in names}
    leg_jobs: dict[str, Callable[[], Any]] = {}
    for backend in backends if depth != "link" else []:
        if backend.name == "openalex":
            leg_jobs[backend.name] = partial(
                _openalex_leg,
                passes[backend.name],
                backend,
                intent=context.intent,
                queries=queries,
                paraphrases=paraphrases,
                variants=variants[backend.name],
                wires=wires[backend.name],
            )
        elif backend.name == "overton":
            leg_jobs[backend.name] = partial(
                _overton_leg,
                passes[backend.name],
                backend,
                intent=context.intent,
                paraphrases=paraphrases,
                validated=validated[backend.name],
                wire=wires[backend.name][0],
            )
    pools: dict[str, list[PoolEntry]] = {}
    summaries: dict[str, _LegSummary] = {}
    local_filters: list[str] = []
    with ThreadPoolExecutor(max_workers=max(1, len(leg_jobs))) as executor:
        futures = {
            name: tracing.submit_with_context(executor, leg) for name, leg in leg_jobs.items()
        }
        for name, future in futures.items():
            outcome = future.result()
            if name == "openalex":
                pools[name], summaries[name], local_filters = outcome
            else:
                pools[name], summaries[name] = outcome
    if depth == "link":
        # The link sentence is the intent's first line (``item_text``).
        pools, local_filters = _link_pools(
            passes,
            backends,
            text=context.intent.strip().splitlines()[0],
            cap=record_cap or constants["papers_cap"],
            variants=variants,
            validated=validated,
            wires=wires,
        )
    executed = [call for name in names for call in passes[name].executed]
    calls_made = {name: passes[name].calls.get(name, 0) for name in names}
    ranked_count = {name: passes[name].ranked_count.get(name, 0) for name in names}
    if scope_wire_params is not None and local_filters:
        scope_wire_params["semantic_local_filters"] = local_filters

    counts = acquire.acquire_sources(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=context,
        backends=backends,
        embedder=embedder,
        executed_calls=executed,
        pools=pools,
        # The cap cuts the ranked list; records the ranking left out never fill it.
        # A directive `record_cap` (the options-scoping baseline, longlist and
        # option searches, task 044 D7) is one fixed target for both backends.
        caps={
            "openalex": min(record_cap or constants["papers_cap"], ranked_count.get("openalex", 0)),
            "overton": min(record_cap or constants["policy_cap"], ranked_count.get("overton", 0)),
        },
        depth=depth,
        scope_wire_params=scope_wire_params,
        search_guidance=guidance,
    )
    legs = {name: summaries.get(name, _LegSummary()) for name in names}
    counts["search"] = {
        "depth": depth,
        "round_index": round_index,
        "queries_executed": calls_made,
        "queries_zero_result": {name: legs[name].zero_result_queries for name in names},
        "queries_dropped": queries_dropped,
        "fallback_to_verbatim": {name: legs[name].fallback_to_verbatim for name in names},
        "wall_clock_s": time.monotonic() - started,
        "generation_calls": generation_calls,
        "semantic_local_filters": local_filters,
        "seeds": legs["openalex"].seeds if "openalex" in legs else 0,
        "backward_targets": legs["openalex"].backward_targets if "openalex" in legs else 0,
        "forward_candidates": legs["openalex"].forward_candidates if "openalex" in legs else 0,
        "duplicate_papers": legs["openalex"].duplicate_papers if "openalex" in legs else 0,
        "landmarks": legs["overton"].landmarks if "overton" in legs else 0,
        "pool_sizes": {name: len(pools.get(name, [])) for name in names},
    }
    counts["usage_totals"] = usage_totals.payload()
    return counts
