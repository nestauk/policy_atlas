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
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal, TypedDict, cast

from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from policy_atlas import acquire
from policy_atlas.embeddings import EmbeddingBackend
from policy_atlas.schema import search_coverage_record
from policy_atlas.search_generation import SearchGenerationBackend
from policy_atlas.search_prompts import N_QUERIES, QueriesPayload, validated_queries

SearchDepth = Literal["rapid", "deep"]
QueryOrigin = Literal[
    "generated",
    "variant_sr",
    "variant_rct",
    "paraphrase",
    "verbatim",
    "fallback_verbatim",
]
CallStatus = Literal["ok", "error"]

RAPID_WALL_CLOCK_S = 30
DEEP_WALL_CLOCK_S = 150
ROUND_CAP = 3


class DepthConstants(TypedDict):
    """Per-depth budget constants used by the search strategy."""

    result_cap_per_backend: int
    wall_clock_s: int
    round_cap: int
    http_budget: dict[str, int]
    generation_call_cap: int


DEPTH_CONSTANTS: dict[SearchDepth, DepthConstants] = {
    "rapid": {
        "result_cap_per_backend": 50,
        "wall_clock_s": RAPID_WALL_CLOCK_S,
        "round_cap": 1,
        "http_budget": {"openalex": 20, "overton": 5},
        "generation_call_cap": 1,
    },
    "deep": {
        "result_cap_per_backend": 150,
        "wall_clock_s": DEEP_WALL_CLOCK_S,
        "round_cap": ROUND_CAP,
        "http_budget": {"openalex": 50, "overton": 15},
        "generation_call_cap": 8,
    },
}

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
    "publisher_region",
    "language",
}
_BACKEND_NAMES = {"openalex", "overton"}


class SearchDirectiveError(ValueError):
    """Raised when a search directive or filter block fails closed."""


@dataclass(frozen=True)
class ExecutedCall:
    """One already-executed search call handed to acquire for persistence.

    Attributes:
        backend_name: Backend identifier matching a configured backend.
        verb: Search verb; Phase 5 uses only ``"search"``.
        query: Exact query text sent to the backend.
        query_origin: Deterministic origin of the query text.
        wire_params: Executed backend wire parameters, already redacted.
        records: Raw provider records returned by the call.
        status: ``"ok"`` or ``"error"``.
        error: Redacted error string for failed calls.
    """

    backend_name: str
    verb: Literal["search"]
    query: str
    query_origin: QueryOrigin
    wire_params: dict[str, str]
    records: list[dict[str, Any]]
    status: CallStatus
    error: str | None


@dataclass(frozen=True)
class _PlannedCall:
    backend_name: str
    query: str
    query_origin: QueryOrigin
    group_key: str | None = None


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


def parse_search_directive(context: dict[str, Any]) -> tuple[SearchDepth, Any | None]:
    """Parse ``context["search"]`` using the fail-closed directive grammar.

    Args:
        context: Evidence-scope context JSON object.

    Returns:
        ``(depth, raw_filters)``. Absent directive defaults to rapid depth and
        no filters.

    Raises:
        SearchDirectiveError: If the directive has an unknown key or malformed
            depth value.
    """
    raw = context.get("search")
    if raw is None:
        return "rapid", None
    if not isinstance(raw, dict):
        raise SearchDirectiveError("search directive must be an object")
    unknown = set(raw) - {"depth", "filters"}
    if unknown:
        raise SearchDirectiveError("search directive contains unknown keys")
    depth: SearchDepth = "rapid"
    if "depth" in raw:
        raw_depth = raw["depth"]
        if not isinstance(raw_depth, str) or raw_depth not in DEPTH_CONSTANTS:
            raise SearchDirectiveError("search directive depth must be 'rapid' or 'deep'")
        depth = raw_depth
    if "filters" in raw and raw["filters"] is None:
        raise SearchDirectiveError("search directive filters must be an object")
    return depth, raw.get("filters")


def _object_block(raw: Any, *, label: str) -> dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise SearchDirectiveError(f"{label} must be an object")
    return cast(dict[str, Any], raw)


def _validate_iso_date(key: str, value: Any) -> str:
    if not isinstance(value, str):
        raise SearchDirectiveError(f"{key} must be an ISO date string")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise SearchDirectiveError(f"{key} must be a valid ISO date") from exc
    if parsed.isoformat() != value:
        raise SearchDirectiveError(f"{key} must be a YYYY-MM-DD ISO date")
    return value


def _validate_sdgs(value: Any) -> list[int]:
    if not isinstance(value, list) or not value:
        raise SearchDirectiveError("sdgs must be a non-empty list")
    out: list[int] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int):
            raise SearchDirectiveError("sdgs must contain integers")
        if item < 1 or item > 17:
            raise SearchDirectiveError("sdgs must contain values from 1 to 17")
        out.append(item)
    return out


def _validate_str_list(key: str, value: Any) -> list[str]:
    if not isinstance(value, list) or not value:
        raise SearchDirectiveError(f"{key} must be a non-empty list")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip() or item != item.strip():
            raise SearchDirectiveError(f"{key} must contain non-empty strings")
        out.append(item)
    return out


def _validate_enum_list(key: str, value: Any, allowed: tuple[str, ...]) -> list[str]:
    values = _validate_str_list(key, value)
    unknown = [item for item in values if item not in set(allowed)]
    if unknown:
        raise SearchDirectiveError(f"{key} contains unknown value(s): {unknown}")
    return values


def _validate_single_str(key: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise SearchDirectiveError(f"{key} must be a non-empty string")
    return value


def _validate_single_enum(key: str, value: Any, allowed: tuple[str, ...]) -> str:
    text = _validate_single_str(key, value)
    if text not in set(allowed):
        raise SearchDirectiveError(f"{key} contains unknown value: {text}")
    return text


def _validate_alpha_code_list(
    key: str,
    value: Any,
    *,
    length: int,
    case: Literal["lower", "upper"],
) -> list[str]:
    values = _validate_str_list(key, value)
    for item in values:
        if len(item) != length or not item.isalpha():
            raise SearchDirectiveError(f"{key} must contain {length}-letter codes")
        if case == "lower" and item != item.lower():
            raise SearchDirectiveError(f"{key} must contain lowercase codes")
        if case == "upper" and item != item.upper():
            raise SearchDirectiveError(f"{key} must contain uppercase codes")
    return values


def _validate_single_alpha_code(
    key: str,
    value: Any,
    *,
    length: int,
    case: Literal["lower", "upper"],
) -> str:
    text = _validate_single_str(key, value)
    if len(text) != length or not text.isalpha():
        raise SearchDirectiveError(f"{key} must be a {length}-letter code")
    if case == "lower" and text != text.lower():
        raise SearchDirectiveError(f"{key} must be lowercase")
    if case == "upper" and text != text.upper():
        raise SearchDirectiveError(f"{key} must be uppercase")
    return text


def _validate_shared_block(block: dict[str, Any]) -> dict[str, Any]:
    unknown = set(block) - _SHARED_FILTER_KEYS
    if unknown:
        raise SearchDirectiveError("shared search filters contain unknown keys")
    out: dict[str, Any] = {}
    for key, value in block.items():
        if key in {"published_after", "published_before"}:
            out[key] = _validate_iso_date(key, value)
        elif key == "sdgs":
            out[key] = _validate_sdgs(value)
    return out


def _validate_openalex_block(block: dict[str, Any]) -> dict[str, Any]:
    unknown = set(block) - _OPENALEX_FILTER_KEYS
    if unknown:
        raise SearchDirectiveError("OpenAlex search filters contain unknown keys")
    out: dict[str, Any] = {}
    for key, value in block.items():
        if key == "types":
            out[key] = _validate_enum_list(key, value, OPENALEX_TYPES)
        elif key == "languages":
            out[key] = _validate_alpha_code_list(key, value, length=2, case="lower")
        elif key in {"exclude_retracted", "exclude_paratext"}:
            if not isinstance(value, bool):
                raise SearchDirectiveError(f"{key} must be a boolean")
            out[key] = value
        elif key == "oa_status":
            out[key] = _validate_enum_list(key, value, OA_STATUS_VALUES)
        elif key == "author_affiliation_countries":
            out[key] = _validate_alpha_code_list(key, value, length=2, case="upper")
    return out


def _validate_overton_block(block: dict[str, Any]) -> dict[str, Any]:
    unknown = set(block) - _OVERTON_FILTER_KEYS
    if unknown:
        raise SearchDirectiveError("Overton search filters contain unknown keys")
    out: dict[str, Any] = {}
    for key, value in block.items():
        if key == "publisher_type":
            out[key] = _validate_single_enum(key, value, OVERTON_PUBLISHER_TYPES)
        elif key == "publisher_country":
            out[key] = _validate_single_str(key, value)
        elif key == "publisher_region":
            out[key] = _validate_single_enum(key, value, OVERTON_REGION_GROUPS)
        elif key == "language":
            out[key] = _validate_single_alpha_code(key, value, length=3, case="lower")
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


def _count_existing_rounds(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
) -> int:
    count = conn.execute(
        select(func.count())
        .select_from(search_coverage_record)
        .where(search_coverage_record.c.project_id == project_id)
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


def run_search(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    context: acquire.AcquireContext,
    backends: list[acquire.SearchBackend],
    generation_backend: SearchGenerationBackend,
    embedder: EmbeddingBackend | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Execute the Phase-5 search strategy and persist acquired records.

    Args:
        conn: Open database connection; writes are delegated to acquire.
        project_id: Owning project.
        run_id: The acquire run id.
        context: Scope-level acquire context.
        backends: Configured search backends, executed in list order.
        generation_backend: Query generation backend.
        embedder: Optional embedding backend passed through to acquire.
        clock: Monotonic clock dependency for wall-clock budget checks.

    Returns:
        Acquire counts with an added ``search`` summary dictionary.

    Raises:
        SearchDirectiveError: If the search directive or filters are malformed.
        NotImplementedError: For deep rounds after round 1; Phase 6 owns them.
        RuntimeError: If generation fails.
    """
    depth, raw_filters = parse_search_directive(context.context)
    constants = DEPTH_CONSTANTS[depth]
    backend_names = [backend.name for backend in backends]
    validated_filters = validate_scope_filters(raw_filters, backend_names=backend_names)
    wire_params_by_backend = {
        name: to_wire_params(name, validated_filters[name]) for name in backend_names
    }
    scope_wire_params = wire_params_by_backend if raw_filters is not None else None

    round_index = _count_existing_rounds(
        conn,
        project_id=project_id,
        scope_id=context.scope_id,
    ) + 1
    if depth == "deep" and round_index >= 2:
        raise NotImplementedError("deep rounds land in phase 6")

    start = clock()
    executed_calls: list[ExecutedCall] = []
    raw_results_by_backend = dict.fromkeys(backend_names, 0)
    http_calls_by_backend = dict.fromkeys(backend_names, 0)
    queries_zero_result = dict.fromkeys(backend_names, 0)
    fallback_to_verbatim = dict.fromkeys(backend_names, False)
    wall_clock_breached = False
    stop_all = False
    generation_calls = 0

    def execute_plan(backend: acquire.SearchBackend, plan: _PlannedCall) -> ExecutedCall | None:
        nonlocal stop_all, wall_clock_breached
        if stop_all:
            return None
        backend_budget = constants["http_budget"].get(backend.name, 0)
        if http_calls_by_backend[backend.name] >= backend_budget:
            return None
        remaining = constants["result_cap_per_backend"] - raw_results_by_backend[backend.name]
        if remaining <= 0:
            return None
        if clock() - start > constants["wall_clock_s"]:
            wall_clock_breached = True
            stop_all = True
            return None

        http_calls_by_backend[backend.name] += 1
        wire_params = wire_params_by_backend[backend.name]
        try:
            records = backend.search(
                plan.query,
                wire_params=wire_params,
                max_results=remaining,
            )
            records = records[:remaining]
            raw_results_by_backend[backend.name] += len(records)
            call = ExecutedCall(
                backend_name=backend.name,
                verb="search",
                query=plan.query,
                query_origin=plan.query_origin,
                wire_params=wire_params,
                records=records,
                status="ok",
                error=None,
            )
        except Exception as exc:
            call = ExecutedCall(
                backend_name=backend.name,
                verb="search",
                query=plan.query,
                query_origin=plan.query_origin,
                wire_params=wire_params,
                records=[],
                status="error",
                error=str(exc),
            )
        executed_calls.append(call)
        return call

    if all(backend.mode == "fixture" for backend in backends):
        for backend in backends:
            execute_plan(backend, _PlannedCall(backend.name, context.intent, "verbatim"))
            if stop_all:
                break
    else:
        wire = generation_backend.generate_queries(QueriesPayload(intent=context.intent))
        generation_calls = 1
        queries, overton_paraphrases = validated_queries(wire)

        for backend in backends:
            plans = _rapid_plans(
                backend_name=backend.name,
                intent=context.intent,
                queries=queries,
                overton_paraphrases=overton_paraphrases,
            )
            backend_calls: list[ExecutedCall] = []
            generated_groups: dict[str, list[ExecutedCall]] = {}
            for plan in plans:
                call = execute_plan(backend, plan)
                if call is not None:
                    backend_calls.append(call)
                    if plan.group_key is not None:
                        generated_groups.setdefault(plan.group_key, []).append(call)
                if stop_all:
                    break
            if stop_all:
                break

            zero_groups = 0
            for calls in generated_groups.values():
                if calls and all(call.status == "ok" and len(call.records) == 0 for call in calls):
                    zero_groups += 1
            # Overton's generated paraphrases have no variant group; each
            # zero-result paraphrase is one counted-and-dropped generated query.
            zero_groups += sum(
                1
                for call in backend_calls
                if call.query_origin == "paraphrase"
                and call.status == "ok"
                and len(call.records) == 0
            )
            queries_zero_result[backend.name] = zero_groups

            generated_calls = [
                call
                for call in backend_calls
                if call.query_origin in {"generated", "variant_sr", "variant_rct"}
            ]
            has_verbatim = any(call.query_origin == "verbatim" for call in backend_calls)
            all_generated_zero = bool(generated_calls) and all(
                call.status == "ok" and len(call.records) == 0 for call in generated_calls
            )
            if backend.name == "openalex" and not generated_calls:
                all_generated_zero = True
            if all_generated_zero and not has_verbatim:
                fallback = _PlannedCall(backend.name, context.intent, "fallback_verbatim")
                if execute_plan(backend, fallback) is not None:
                    fallback_to_verbatim[backend.name] = True
            if stop_all:
                break

    elapsed = clock() - start
    counts = acquire.acquire_sources(
        conn,
        project_id=project_id,
        run_id=run_id,
        context=context,
        backends=backends,
        embedder=embedder,
        executed_calls=executed_calls,
        depth=depth,
        scope_wire_params=scope_wire_params,
    )
    counts["search"] = {
        "depth": depth,
        "round_index": round_index,
        "queries_executed": {
            name: sum(1 for call in executed_calls if call.backend_name == name)
            for name in backend_names
        },
        "queries_zero_result": queries_zero_result,
        "fallback_to_verbatim": fallback_to_verbatim,
        "wall_clock_s": elapsed,
        "wall_clock_breached": wall_clock_breached,
        "generation_calls": generation_calls,
    }
    return counts
