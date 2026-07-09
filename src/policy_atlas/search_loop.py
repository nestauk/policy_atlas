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

from policy_atlas import acquire, screen
from policy_atlas.embeddings import EmbeddingBackend
from policy_atlas.schema import (
    event_log,
    project_source_snapshot,
    search_coverage_record,
    source_snapshot,
)
from policy_atlas.search_generation import SearchGenerationBackend
from policy_atlas.search_prompts import (
    N_QUERIES,
    ExemplarRecord,
    QueriesPayload,
    ReformulatePayload,
    SuggestPayload,
    validated_queries,
    validated_suggestions,
)

SearchDepth = Literal["rapid", "deep"]
QueryOrigin = Literal[
    "generated",
    "variant_sr",
    "variant_rct",
    "paraphrase",
    "verbatim",
    "fallback_verbatim",
    "snowball_forward",
    "snowball_backward",
    "suggestion_doi",
    "suggestion_title",
]
CallVerb = Literal[
    "search",
    "fetch_citations",
    "fetch_references",
    "lookup_dois",
    "lookup_title",
]
CallStatus = Literal["ok", "error"]
ArmName = Literal["reformulate", "snowball", "suggest", "diversity"]

RAPID_WALL_CLOCK_S = 30
DEEP_WALL_CLOCK_S = 150
ROUND_CAP = 3
POS_EXEMPLARS = 8
NEG_EXEMPLARS = 4
SNOWBALL_SEEDS = 5
SNOWBALL_RESULTS = 40
TARGET_CONFIDENT_RELEVANT = 20
CONFIDENT_FLOOR = 0.7
SHORT_CIRCUIT_RATE = 1.0 / 50.0
THIN_CONFIDENT_RELEVANT = 8
DIVERSITY_FRACTION = 0.15
REFORMULATE_CALL_CAP = 4
SNOWBALL_CALL_CAP = 6
SUGGEST_CALL_CAP = 6
DIVERSITY_CALL_MIN = 1


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
        verb: Search verb.
        query: Exact query text sent to the backend.
        query_origin: Deterministic origin of the query text.
        wire_params: Executed backend wire parameters, already redacted.
        records: Raw provider records returned by the call.
        status: ``"ok"`` or ``"error"``.
        error: Redacted error string for failed calls.
    """

    backend_name: str
    verb: CallVerb
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


@dataclass(frozen=True)
class _ScreenedRecord:
    pss_id: uuid.UUID
    metadata: dict[str, Any]
    confidence: float


@dataclass(frozen=True)
class StopDecision:
    """Deep-loop stop decision.

    Attributes:
        stop: Whether the loop should stop after this evaluation.
        stop_condition: Raw stop condition before any deep-thin overlay.
        overlay_applied: Whether an overlay has already been applied.
    """

    stop: bool
    stop_condition: str | None
    overlay_applied: bool


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


def confident_relevant_count(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
) -> int:
    """Count effective relevant rows at or above the confidence floor.

    Args:
        conn: Open database connection.
        project_id: Owning project.
        scope_id: Evidence scope being searched.

    Returns:
        Count of effective screened rows with ``status='relevant'`` and
        ``screen_decision_confidence >= CONFIDENT_FLOOR``.
    """
    effective = screen.effective_screen_rows()
    count = conn.execute(
        select(func.count())
        .select_from(effective)
        .where(effective.c.project_id == project_id)
        .where(effective.c.evidence_scope_id == scope_id)
        .where(effective.c.status == "relevant")
        .where(effective.c.screen_decision_confidence >= CONFIDENT_FLOOR)
    ).scalar_one()
    return int(count)


def should_escalate(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
) -> bool:
    """Return whether a rapid run is thin enough to need deep continuation.

    Args:
        conn: Open database connection.
        project_id: Owning project.
        scope_id: Evidence scope being searched.

    Returns:
        ``True`` when confident relevant evidence is below
        ``THIN_CONFIDENT_RELEVANT``.
    """
    return (
        confident_relevant_count(conn, project_id=project_id, scope_id=scope_id)
        < THIN_CONFIDENT_RELEVANT
    )


def evaluate_deep_stop(
    *,
    round_index: int,
    confident_relevant: int,
    new_confident_relevant: int,
    docs_screened_this_round: int,
    wall_clock_breached: bool,
    round_cap: int = ROUND_CAP,
) -> StopDecision:
    """Evaluate deep-loop stopping without touching the database.

    Args:
        round_index: Search round just completed.
        confident_relevant: Current confident-relevant total.
        new_confident_relevant: New confident-relevant rows from this round.
        docs_screened_this_round: Stage-1 docs screened this round.
        wall_clock_breached: Whether the deep wall-clock budget was exceeded.
        round_cap: Maximum round index before the budget backstop fires.

    Returns:
        Stop decision with the raw stop condition, if any.
    """
    if confident_relevant >= TARGET_CONFIDENT_RELEVANT:
        return StopDecision(True, "target_reached", False)
    if round_index >= 2 and (
        docs_screened_this_round == 0
        or new_confident_relevant / docs_screened_this_round < SHORT_CIRCUIT_RATE
    ):
        return StopDecision(True, "short_circuit", False)
    if wall_clock_breached or round_index >= round_cap:
        return StopDecision(True, "budget_exhausted", False)
    return StopDecision(False, None, False)


def finalise_deep_stop(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    stop_condition: str,
    below_target: bool,
) -> str:
    """Write the final deep stop condition onto the latest coverage row.

    Args:
        conn: Open database connection.
        project_id: Owning project.
        scope_id: Evidence scope being searched.
        stop_condition: Raw stop condition from ``evaluate_deep_stop``.
        below_target: Whether final confident-relevant count is below target.

    Returns:
        Stop condition written to ``search_coverage_record`` after applying the
        deep-thin overlay.

    Raises:
        RuntimeError: If no search coverage row exists for the scope.
    """
    final_value = (
        "re_searched_still_thin"
        if stop_condition != "target_reached" and below_target
        else stop_condition
    )
    row = conn.execute(
        select(search_coverage_record.c.search_coverage_record_id)
        .where(search_coverage_record.c.project_id == project_id)
        .where(search_coverage_record.c.evidence_scope_id == scope_id)
        .order_by(
            search_coverage_record.c.created_at.desc(),
            search_coverage_record.c.acquired_by_run_id.desc(),
        )
        .limit(1)
    ).one_or_none()
    if row is None:
        raise RuntimeError("deep stop finalisation requires a coverage row")
    conn.execute(
        search_coverage_record.update()
        .where(
            search_coverage_record.c.search_coverage_record_id
            == row.search_coverage_record_id
        )
        .values(stop_condition=final_value)
    )
    return final_value


def _metadata(raw: Any) -> dict[str, Any]:
    return dict(raw) if isinstance(raw, dict) else {}


def _text_or_none(raw: Any) -> str | None:
    return raw if isinstance(raw, str) and raw else None


def _normalized_doi(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    candidate = raw.strip().lower()
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


def _normalized_title(raw: Any) -> str:
    return " ".join(str(raw or "").casefold().split())


def _record_key(record: dict[str, Any]) -> str:
    record_id = record.get("id")
    if isinstance(record_id, str) and record_id:
        return f"id:{record_id}"
    doi = _normalized_doi(record.get("doi"))
    if doi is not None:
        return f"doi:{doi}"
    return f"title:{_normalized_title(record.get('display_name'))}"


def _dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        key = _record_key(record)
        if key in seen:
            continue
        seen.add(key)
        out.append(record)
    return out


def _prior_deep_usage(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    backend_names: list[str],
) -> tuple[dict[str, int], dict[str, int]]:
    http_calls = dict.fromkeys(backend_names, 0)
    result_counts = dict.fromkeys(backend_names, 0)
    rows = conn.execute(
        select(event_log.c.payload)
        .where(event_log.c.project_id == project_id)
        .where(event_log.c.event_type == "search.executed")
        .where(event_log.c.payload.op("->>")("evidence_scope_id") == str(scope_id))
        .where(event_log.c.payload.op("->>")("depth") == "deep")
    ).fetchall()
    for row in rows:
        payload = _metadata(row.payload)
        backend = payload.get("backend")
        if not isinstance(backend, str) or backend not in http_calls:
            continue
        http_calls[backend] += 1
        try:
            result_counts[backend] += int(payload.get("result_count") or 0)
        except (TypeError, ValueError):
            continue
    return http_calls, result_counts


def _screened_records(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    status: Literal["relevant", "not_relevant"],
    limit: int,
    confidence_floor: float | None,
) -> list[_ScreenedRecord]:
    effective = screen.effective_screen_rows()
    query = (
        select(
            project_source_snapshot.c.project_source_snapshot_id,
            source_snapshot.c.metadata,
            effective.c.screen_decision_confidence,
        )
        .select_from(
            effective.join(
                project_source_snapshot,
                (
                    effective.c.project_source_snapshot_id
                    == project_source_snapshot.c.project_source_snapshot_id
                )
                & (effective.c.project_id == project_source_snapshot.c.project_id),
            ).join(
                source_snapshot,
                project_source_snapshot.c.source_snapshot_id
                == source_snapshot.c.source_snapshot_id,
            )
        )
        .where(effective.c.project_id == project_id)
        .where(effective.c.evidence_scope_id == scope_id)
        .where(effective.c.status == status)
        .where(effective.c.screen_decision_confidence.is_not(None))
        .order_by(
            effective.c.screen_decision_confidence.desc(),
            project_source_snapshot.c.project_source_snapshot_id,
        )
        .limit(limit)
    )
    if confidence_floor is not None:
        query = query.where(effective.c.screen_decision_confidence >= confidence_floor)
    return [
        _ScreenedRecord(
            pss_id=cast(uuid.UUID, row.project_source_snapshot_id),
            metadata=_metadata(row.metadata),
            confidence=float(row.screen_decision_confidence),
        )
        for row in conn.execute(query)
    ]


def _exemplar(record: _ScreenedRecord) -> ExemplarRecord:
    return ExemplarRecord(
        pss_id=str(record.pss_id),
        title=_text_or_none(record.metadata.get("title")) or "",
        abstract=_text_or_none(record.metadata.get("abstract")),
        screen_confidence=record.confidence,
    )


def _read_exemplars(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
) -> tuple[
    list[_ScreenedRecord],
    list[_ScreenedRecord],
    list[ExemplarRecord],
    list[ExemplarRecord],
]:
    positives = _screened_records(
        conn,
        project_id=project_id,
        scope_id=scope_id,
        status="relevant",
        limit=POS_EXEMPLARS,
        confidence_floor=CONFIDENT_FLOOR,
    )
    negatives = _screened_records(
        conn,
        project_id=project_id,
        scope_id=scope_id,
        status="not_relevant",
        limit=NEG_EXEMPLARS,
        confidence_floor=None,
    )
    return positives, negatives, [_exemplar(record) for record in positives], [
        _exemplar(record) for record in negatives
    ]


def _suggest_grounded_screened_out(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    pss_ids: list[str],
) -> int:
    if not pss_ids:
        return 0
    effective = screen.effective_screen_rows()
    parsed = [uuid.UUID(pss_id) for pss_id in pss_ids]
    count = conn.execute(
        select(func.count())
        .select_from(effective)
        .where(effective.c.project_id == project_id)
        .where(effective.c.evidence_scope_id == scope_id)
        .where(effective.c.project_source_snapshot_id.in_(parsed))
        .where(effective.c.status == "not_relevant")
    ).scalar_one()
    return int(count)


def _docs_screened_from_payload(payload: dict[str, Any]) -> int:
    # Stage-1 ``screened`` is the honest deep-loop denominator: it is the
    # number of newly loaded docs before consensus insertion.
    value = payload.get("screened")
    if isinstance(value, int):
        return value
    raise RuntimeError("deep loop screen_round payload must include stage-1 'screened'")


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
    """Execute the depth-graded search strategy and persist acquired records.

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
    prior_http_calls, prior_result_counts = _prior_deep_usage(
        conn,
        project_id=project_id,
        scope_id=context.scope_id,
        backend_names=backend_names,
    ) if depth == "deep" else (
        dict.fromkeys(backend_names, 0),
        dict.fromkeys(backend_names, 0),
    )

    start = clock()
    executed_calls: list[ExecutedCall] = []
    raw_results_by_backend = dict(prior_result_counts)
    http_calls_by_backend = dict(prior_http_calls)
    queries_zero_result = dict.fromkeys(backend_names, 0)
    fallback_to_verbatim = dict.fromkeys(backend_names, False)
    arm_calls: dict[ArmName, int] = {
        "reformulate": 0,
        "snowball": 0,
        "suggest": 0,
        "diversity": 0,
    }
    positive_exemplars: list[ExemplarRecord] = []
    negative_exemplars: list[ExemplarRecord] = []
    suggestions_proposed = 0
    suggestions_grounded = 0
    suggestions_dropped = 0
    suggest_failures = 0
    wall_clock_breached = False
    stop_all = False
    generation_calls = 0

    def execute_call(
        backend: acquire.SearchBackend,
        *,
        verb: CallVerb,
        query: str,
        query_origin: QueryOrigin,
        wire_params: dict[str, str],
        fetch: Callable[[int], list[dict[str, Any]]],
        max_records: int | None = None,
        arm: ArmName | None = None,
    ) -> ExecutedCall | None:
        nonlocal stop_all, wall_clock_breached
        if stop_all:
            return None
        backend_budget = constants["http_budget"].get(backend.name, 0)
        if http_calls_by_backend[backend.name] >= backend_budget:
            return None
        remaining = constants["result_cap_per_backend"] - raw_results_by_backend[backend.name]
        if max_records is not None:
            remaining = min(remaining, max_records)
        if remaining <= 0:
            return None
        if clock() - start > constants["wall_clock_s"]:
            wall_clock_breached = True
            stop_all = True
            return None

        http_calls_by_backend[backend.name] += 1
        try:
            records = fetch(remaining)
            records = records[:remaining]
            raw_results_by_backend[backend.name] += len(records)
            call = ExecutedCall(
                backend_name=backend.name,
                verb=verb,
                query=query,
                query_origin=query_origin,
                wire_params=wire_params,
                records=records,
                status="ok",
                error=None,
            )
        except Exception as exc:
            call = ExecutedCall(
                backend_name=backend.name,
                verb=verb,
                query=query,
                query_origin=query_origin,
                wire_params=wire_params,
                records=[],
                status="error",
                error=str(exc),
            )
        executed_calls.append(call)
        if arm is not None:
            arm_calls[arm] += 1
        return call

    def execute_plan(
        backend: acquire.SearchBackend,
        plan: _PlannedCall,
        *,
        arm: ArmName | None = None,
        max_records: int | None = None,
    ) -> ExecutedCall | None:
        wire_params = wire_params_by_backend[backend.name]
        return execute_call(
            backend,
            verb="search",
            query=plan.query,
            query_origin=plan.query_origin,
            wire_params=wire_params,
            max_records=max_records,
            arm=arm,
            fetch=lambda remaining: backend.search(
                plan.query,
                wire_params=wire_params,
                max_results=remaining,
            ),
        )

    if all(backend.mode == "fixture" for backend in backends):
        for backend in backends:
            execute_plan(backend, _PlannedCall(backend.name, context.intent, "verbatim"))
            if stop_all:
                break
    elif depth == "deep" and round_index >= 2:
        positive_records, _negative_records, positive_exemplars, negative_exemplars = (
            _read_exemplars(
                conn,
                project_id=project_id,
                scope_id=context.scope_id,
            )
        )

        wire = generation_backend.reformulate(
            ReformulatePayload(
                intent=context.intent,
                round_index=round_index,
                positive=positive_exemplars,
                negative=negative_exemplars,
            )
        )
        generation_calls += 1
        queries, overton_paraphrases = validated_queries(wire)

        for backend in backends:
            # Same cap-distribution rule as the rapid fan-out: this round's
            # search-arm calls share the episode's remaining result cap.
            episode_remaining = max(
                1,
                constants["result_cap_per_backend"] - raw_results_by_backend[backend.name],
            )
            if backend.name == "openalex":
                planned = min(len(queries), REFORMULATE_CALL_CAP) + DIVERSITY_CALL_MIN
                quota = max(1, episode_remaining // max(1, planned))
                for query in queries[:REFORMULATE_CALL_CAP]:
                    execute_plan(
                        backend,
                        _PlannedCall(backend.name, query, "generated"),
                        arm="reformulate",
                        max_records=quota,
                    )
                    if stop_all:
                        break
            elif backend.name == "overton":
                planned = min(len(overton_paraphrases), 2)
                quota = max(1, episode_remaining // max(1, planned))
                for paraphrase in overton_paraphrases[:2]:
                    execute_plan(
                        backend,
                        _PlannedCall(backend.name, paraphrase, "paraphrase"),
                        arm="reformulate",
                        max_records=quota,
                    )
                    if stop_all:
                        break
            if stop_all:
                break

        openalex_backend = next(
            (
                backend for backend in backends
                if backend.name == "openalex" and backend.caps.has_snowball
            ),
            None,
        )
        if openalex_backend is not None and not stop_all:
            seeds = [
                record for record in positive_records
                if record.metadata.get("backend") == "openalex"
                and isinstance(record.metadata.get("backend_record_id"), str)
            ][:SNOWBALL_SEEDS]
            snowball_records = 0
            per_seed = SNOWBALL_RESULTS // SNOWBALL_SEEDS
            for seed in seeds:
                if arm_calls["snowball"] >= SNOWBALL_CALL_CAP:
                    break
                if snowball_records >= SNOWBALL_RESULTS:
                    break
                seed_id = cast(str, seed.metadata["backend_record_id"])

                def fetch_forward_citations(
                    remaining: int,
                    *,
                    record_id: str = seed_id,
                ) -> list[dict[str, Any]]:
                    return openalex_backend.fetch_citations(
                        record_id,
                        max_results=remaining,
                    )

                call = execute_call(
                    openalex_backend,
                    verb="fetch_citations",
                    query=seed_id,
                    query_origin="snowball_forward",
                    wire_params={},
                    max_records=min(per_seed, SNOWBALL_RESULTS - snowball_records),
                    arm="snowball",
                    fetch=fetch_forward_citations,
                )
                if call is not None and call.status == "ok":
                    snowball_records += len(call.records)
                if stop_all:
                    break

            referenced: list[str] = []
            seen_refs: set[str] = set()
            for seed in seeds:
                provider_fields = seed.metadata.get("provider_fields")
                if not isinstance(provider_fields, dict):
                    continue
                raw_refs = provider_fields.get("referenced_works")
                if not isinstance(raw_refs, list):
                    continue
                for raw_ref in raw_refs:
                    ref = raw_ref if isinstance(raw_ref, str) else None
                    if ref is None or ref in seen_refs:
                        continue
                    seen_refs.add(ref)
                    referenced.append(ref)
                    if len(referenced) == 50:
                        break
                if len(referenced) == 50:
                    break

            remaining_snowball = SNOWBALL_RESULTS - snowball_records
            if (
                referenced
                and remaining_snowball > 0
                and arm_calls["snowball"] < SNOWBALL_CALL_CAP
                and not stop_all
            ):
                execute_call(
                    openalex_backend,
                    verb="fetch_references",
                    query="|".join(referenced),
                    query_origin="snowball_backward",
                    wire_params={},
                    max_records=remaining_snowball,
                    arm="snowball",
                    fetch=lambda remaining: openalex_backend.fetch_references(
                        referenced,
                        max_results=remaining,
                    ),
                )

        suggest_backend = next(
            (
                backend for backend in backends
                if backend.name == "openalex"
                and (backend.caps.has_doi_lookup or backend.caps.has_title_lookup)
            ),
            None,
        )
        if suggest_backend is not None and not stop_all:
            try:
                generation_calls += 1
                suggestions = validated_suggestions(
                    generation_backend.suggest(
                        SuggestPayload(intent=context.intent, positive=positive_exemplars)
                    )
                )
            except Exception:
                suggest_failures += 1
                suggestions = []

            suggestions_proposed = len(suggestions)
            grounded_indices: set[int] = set()
            doi_to_indices: dict[str, list[int]] = {}
            doi_values: list[str] = []
            for index, suggestion in enumerate(suggestions):
                doi = _normalized_doi(suggestion.get("doi"))
                if doi is None:
                    continue
                doi_to_indices.setdefault(doi, []).append(index)
                if doi not in doi_values:
                    doi_values.append(doi)

            if (
                doi_values
                and suggest_backend.caps.has_doi_lookup
                and arm_calls["suggest"] < SUGGEST_CALL_CAP
            ):

                def fetch_doi_groundings(remaining: int) -> list[dict[str, Any]]:
                    candidates = suggest_backend.lookup_dois(
                        doi_values,
                        max_results=min(remaining, len(doi_values)),
                    )
                    grounded: list[dict[str, Any]] = []
                    for candidate in candidates:
                        candidate_doi = _normalized_doi(candidate.get("doi"))
                        if candidate_doi not in doi_to_indices:
                            continue
                        grounded.extend([candidate])
                        grounded_indices.update(doi_to_indices[candidate_doi])
                    return _dedupe_records(grounded)

                execute_call(
                    suggest_backend,
                    verb="lookup_dois",
                    query="|".join(doi_values),
                    query_origin="suggestion_doi",
                    wire_params={},
                    arm="suggest",
                    fetch=fetch_doi_groundings,
                )

            if suggest_backend.caps.has_title_lookup:
                for index, suggestion in enumerate(suggestions):
                    if index in grounded_indices:
                        continue
                    if arm_calls["suggest"] >= SUGGEST_CALL_CAP or stop_all:
                        break
                    title = cast(str, suggestion["title"])
                    suggestion_doi = _normalized_doi(suggestion.get("doi"))
                    title_key = _normalized_title(title)

                    def fetch_title_grounding(
                        remaining: int,
                        *,
                        title_text: str = title,
                        normalized_title: str = title_key,
                        doi: str | None = suggestion_doi,
                        suggestion_index: int = index,
                    ) -> list[dict[str, Any]]:
                        candidates = suggest_backend.lookup_title(title_text)
                        grounded: list[dict[str, Any]] = []
                        for candidate in candidates:
                            title_matches = (
                                _normalized_title(candidate.get("display_name"))
                                == normalized_title
                            )
                            doi_matches = (
                                doi is not None
                                and _normalized_doi(candidate.get("doi")) == doi
                            )
                            if title_matches or doi_matches:
                                grounded.append(candidate)
                        if grounded:
                            grounded_indices.add(suggestion_index)
                        return _dedupe_records(grounded)[:remaining]

                    execute_call(
                        suggest_backend,
                        verb="lookup_title",
                        query=title,
                        query_origin="suggestion_title",
                        wire_params={},
                        arm="suggest",
                        fetch=fetch_title_grounding,
                    )

            suggestions_grounded = len(grounded_indices)
            suggestions_dropped = suggestions_proposed - suggestions_grounded

        diversity_backend = next(
            (backend for backend in backends if backend.name == "openalex"),
            None,
        )
        if diversity_backend is not None and not stop_all:
            if round_index == 2:
                diversity_query = context.intent
                diversity_origin: QueryOrigin = "verbatim"
            else:
                diversity_query = _compose_variant(context.intent, SR_CLAUSE)
                diversity_origin = "variant_sr"
            if arm_calls["diversity"] < DIVERSITY_CALL_MIN:
                execute_plan(
                    diversity_backend,
                    _PlannedCall(
                        diversity_backend.name,
                        diversity_query,
                        diversity_origin,
                    ),
                    arm="diversity",
                )
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
            # Distribute the run cap across the planned fan-out so no single
            # query can consume it — the first live check showed call #1
            # returning the full cap and silently collapsing the fan-out to
            # one load-bearing query (the exact decision-14 failure mode).
            quota = max(1, constants["result_cap_per_backend"] // max(1, len(plans)))
            backend_calls: list[ExecutedCall] = []
            generated_groups: dict[str, list[ExecutedCall]] = {}
            for plan in plans:
                call = execute_plan(backend, plan, max_records=quota)
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
        "arm_calls": arm_calls,
        "suggestions_proposed": suggestions_proposed,
        "suggestions_grounded": suggestions_grounded,
        "suggestions_dropped": suggestions_dropped,
        "suggest_failures": suggest_failures,
        "exemplars": {
            "positive": len(positive_exemplars),
            "negative": len(negative_exemplars),
        },
        "prior_http_calls": prior_http_calls,
    }
    return counts


def run_deep_rounds(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    acquire_round: Callable[[], dict[str, Any]],
    screen_round: Callable[[], dict[str, Any]],
    start_round: int = 2,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Run skeleton-sequenced deep acquire/screen rounds to a stop.

    Args:
        conn: Open database connection.
        project_id: Owning project.
        scope_id: Evidence scope being searched.
        acquire_round: Callable that executes one acquire component and returns
            its ``component.completed`` payload.
        screen_round: Callable that executes one stage-1 screen component and
            returns its ``component.completed`` payload.
        start_round: First deep continuation round. Defaults to round 2 because
            round 1 is the already-screened rapid leg.
        clock: Monotonic clock dependency for deterministic tests.

    Returns:
        Deep-loop summary containing per-round costs, final stop condition,
        final confident-relevant count, wall-clock seconds and suggest-arm
        quality counters.

    Raises:
        RuntimeError: If a screen payload does not include the stage-1
            ``screened`` count or finalization lacks a coverage row.
    """
    started = clock()
    round_index = start_round
    rounds: list[dict[str, Any]] = []
    suggest_pss_ids: list[str] = []
    prior_confident = confident_relevant_count(
        conn,
        project_id=project_id,
        scope_id=scope_id,
    )
    final_stop_condition: str | None = None
    overlay_applied = False

    while True:
        elapsed = clock() - started
        if elapsed > DEEP_WALL_CLOCK_S:
            final_stop_condition = finalise_deep_stop(
                conn,
                project_id=project_id,
                scope_id=scope_id,
                stop_condition="budget_exhausted",
                below_target=prior_confident < TARGET_CONFIDENT_RELEVANT,
            )
            overlay_applied = final_stop_condition != "budget_exhausted"
            break

        acquire_payload = acquire_round()
        by_verb = acquire_payload.get("acquired_pss_by_verb")
        if isinstance(by_verb, dict):
            for verb in ("lookup_dois", "lookup_title"):
                values = by_verb.get(verb)
                if isinstance(values, list):
                    suggest_pss_ids.extend(str(value) for value in values)

        screen_payload = screen_round()
        docs_screened = _docs_screened_from_payload(screen_payload)
        confident = confident_relevant_count(
            conn,
            project_id=project_id,
            scope_id=scope_id,
        )
        new_confident = max(0, confident - prior_confident)
        cost = None if new_confident == 0 else docs_screened / new_confident
        rounds.append(
            {
                "round": round_index,
                "docs_screened": docs_screened,
                "new_confident_relevant": new_confident,
                "cost_per_marginal_confident_relevant": cost,
            }
        )

        wall_clock_breached = clock() - started > DEEP_WALL_CLOCK_S
        decision = evaluate_deep_stop(
            round_index=round_index,
            confident_relevant=confident,
            new_confident_relevant=new_confident,
            docs_screened_this_round=docs_screened,
            wall_clock_breached=wall_clock_breached,
        )
        if decision.stop:
            if decision.stop_condition is None:
                raise RuntimeError("deep stop decision missing stop_condition")
            final_stop_condition = finalise_deep_stop(
                conn,
                project_id=project_id,
                scope_id=scope_id,
                stop_condition=decision.stop_condition,
                below_target=confident < TARGET_CONFIDENT_RELEVANT,
            )
            overlay_applied = final_stop_condition != decision.stop_condition
            prior_confident = confident
            break

        prior_confident = confident
        round_index += 1

    if final_stop_condition is None:
        raise RuntimeError("deep loop ended without a stop condition")

    suggest_grounded_screened_out = _suggest_grounded_screened_out(
        conn,
        project_id=project_id,
        scope_id=scope_id,
        pss_ids=suggest_pss_ids,
    )
    wall_clock_s = clock() - started
    return {
        "rounds": rounds,
        "stop_condition": final_stop_condition,
        "confident_relevant": prior_confident,
        "wall_clock_s": wall_clock_s,
        "overlay_applied": overlay_applied,
        "suggest": {
            "acquired_pss": suggest_pss_ids,
            "acquired": len(suggest_pss_ids),
            "grounded_screened_out": suggest_grounded_screened_out,
        },
        "suggest_grounded_screened_out": suggest_grounded_screened_out,
    }
