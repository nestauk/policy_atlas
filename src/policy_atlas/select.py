"""Select component: coverage-aware stratified document selection."""

from __future__ import annotations

import math
import uuid
from collections.abc import Sequence
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

import structlog
from sqlalchemy import select as sa_select
from sqlalchemy.engine import Connection

from policy_atlas import tracing
from policy_atlas.characterise import ScreenedSource, screened_sources
from policy_atlas.grouping import UNCLUSTERED, GroupingDoc
from policy_atlas.ranking import (
    MAX_CONCURRENT_RERANK_BATCHES,
    PROMPT_VERSION,
    RERANK_BATCH_SIZE,
    RERANK_MODEL,
    RERANK_RETRY_CAP,
    RankedDoc,
    RankingBackend,
    validate_ranked,
)
from policy_atlas.schema import (
    DIRECTIVE_STRING_MAX,
    SELECTION_STRATEGIES,
    characterisation_result,
    selection_result,
    source_tag,
)
from policy_atlas.tags import has_control_character
from policy_atlas.usage import UsageAccumulator

log = structlog.get_logger()

DEFAULT_SELECTION_BUDGET = 25
DEFAULT_WEIGHTS: dict[str, float] = {
    # Arbitrary until selection-quality evals exist; directive emphasis can steer
    # these cheap pre-extract signals without changing the deterministic structure.
    "recency": 0.25,
    "quality": 0.25,
    "text_basis": 0.20,
    "screen_confidence": 0.15,
    "origin": 0.15,
}
BOOST_CLAMP = (0.1, 10.0)
# Directive input caps (review finding, security lane): the directive is untrusted
# scope-context JSONB — bound every string and collection so a malformed or hostile
# directive fails closed at parse time, never late at the DB or in O(n²) matching.
# DIRECTIVE_STRING_MAX lives in schema.py (shared with the grouping directive).
DIRECTIVE_BUDGET_MAX = 10_000
DIRECTIVE_LIST_MAX = 200
# Publisher ahead-of-print dates legitimately run one year ahead; anything further
# is bad metadata and reads as a missing signal (flag-not-block), never a boost.
RECENCY_FUTURE_GRACE_YEARS = 1
LARGE_STRATUM_SHARE = 0.20
SUFFICIENT_CONFIDENCE = 0.6
# Stub constant: screen confidence is 0.9 until the LLM screen tool lands.
THIN_BASE_FLOOR = 10
THIN_FULL_TEXT_SHARE = 0.5
NON_EVIDENCE_TYPE = "Other (Non-evidence documents)"

_DIRECTIVE_KEYS = {"budget", "must_include_ids", "boosts", "weight_emphasis", "priority_strata"}
_BOOST_KEYS = {"match", "weight"}
_REASON_ORDER = ("must_include", "breadth_floor", "ranked")


class SelectError(Exception):
    """Structural failure in select."""


class DirectiveError(SelectError):
    """Malformed selection directive; select fails closed."""


@dataclass(frozen=True)
class SelectContext:
    """Scope-level input to select.

    Attributes:
        scope_id: Evidence scope being selected.
        intent: Evidence intent grounding optional rerank judgment.
        context: Scope context JSONB, including an optional selection directive.
        characterisation_run_id: Explicit characterisation run to select over.
    """

    scope_id: uuid.UUID
    intent: str
    context: dict[str, Any]
    characterisation_run_id: uuid.UUID


@dataclass(frozen=True)
class SourceTag:
    """Source tag available to directive matching.

    Attributes:
        tag_type: Tag namespace.
        tag: Tag value.
        asserted_by: Assertion provenance.
    """

    tag_type: str
    tag: str
    asserted_by: str


@dataclass(frozen=True)
class SelectionCandidate:
    """Pure select input for one candidate source.

    Attributes:
        source: Screened source and cheap signal fields.
        tags: Scope/project source tags for boost and priority matching.
    """

    source: ScreenedSource
    tags: tuple[SourceTag, ...]


@dataclass(frozen=True)
class SelectionStratum:
    """Pure select input for one characterisation stratum.

    Attributes:
        name: Theme or ``unclustered`` stratum name.
        candidate_ids: Eligible candidate ids belonging to this stratum.
    """

    name: str
    candidate_ids: tuple[uuid.UUID, ...]


@dataclass(frozen=True)
class _Boost:
    index: int
    match: dict[str, Any]
    weight: float


@dataclass(frozen=True)
class SelectionDirective:
    """Validated selection directive.

    Attributes:
        budget: Budgeted non-must-include slots.
        must_include_ids: Candidate ids to force include when in scope.
        boosts: Soft boost rules that multiply matched document composites.
        weight_emphasis: Multipliers for default signal weights.
        priority_strata: Soft priority patterns used only for trigger flags.
    """

    budget: int = DEFAULT_SELECTION_BUDGET
    must_include_ids: tuple[uuid.UUID, ...] = ()
    boosts: tuple[_Boost, ...] = ()
    weight_emphasis: dict[str, float] | None = None
    priority_strata: tuple[str, ...] = ()

    def normalized(self) -> dict[str, Any]:
        """Return the executed directive as deterministic JSON-compatible data.

        Returns:
            Normalized directive payload.
        """
        emphasis = self.weight_emphasis or {}
        return {
            "budget": self.budget,
            "must_include_ids": [str(pss_id) for pss_id in self.must_include_ids],
            "boosts": [
                {"match": boost.match, "weight": boost.weight}
                for boost in self.boosts
            ],
            "weight_emphasis": {
                signal: emphasis[signal]
                for signal in DEFAULT_WEIGHTS
                if signal in emphasis
            },
            "priority_strata": list(self.priority_strata),
        }


@dataclass(frozen=True)
class SelectionOutcome:
    """Pure select result ready for IO wrapping.

    Attributes:
        strategy: Strategy version used.
        budget: Executed budget.
        strata: Summary stratum payload.
        selected: Selected document rationale records.
        excluded_by_stratum: Aggregate exclusion counts by stratum.
        notable_exclusions: Notable exclusion rationale records.
        flags: Fired trigger flags.
        provenance: Strategy provenance excluding IO wrapper fields.
        usage_totals: Component-level token totals.
        selected_by_reason: Selected counts by reason.
        not_in_characterisation: Eligible docs absent from the referenced run.
    """

    strategy: str
    budget: int
    strata: list[dict[str, Any]]
    selected: list[dict[str, Any]]
    excluded_by_stratum: dict[str, dict[str, int]]
    notable_exclusions: list[dict[str, str]]
    flags: dict[str, Any]
    provenance: dict[str, Any]
    usage_totals: dict[str, int]
    selected_by_reason: dict[str, int]
    not_in_characterisation: int


@dataclass(frozen=True)
class _SignalDoc:
    candidate: SelectionCandidate
    signals: dict[str, float]
    missing_signals: list[str]
    composite: float
    boost_multiplier: float


@dataclass(frozen=True)
class _Allocation:
    floor_slots: dict[str, int]
    ranked_slots: dict[str, int]
    allocated_slots: dict[str, int]


@dataclass(frozen=True)
class _RankInfo:
    score: int | None
    reason: str | None
    rank_fallback: bool


@dataclass(frozen=True)
class _RerankStats:
    baseline: int
    maximum: int
    used: int
    retry_count: int
    fallback_count: int
    title_only_count: int


@dataclass
class _RerankCallBudget:
    maximum: int
    used: int = 0

    def reserve(self) -> bool:
        if self.used >= self.maximum:
            return False
        self.used += 1
        return True


def _fail(message: str) -> None:
    raise DirectiveError(message)


def _float_in_clamp(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        _fail(f"selection directive {field} must be a number")
    normalized = float(value)
    if not BOOST_CLAMP[0] <= normalized <= BOOST_CLAMP[1]:
        _fail(f"selection directive {field} outside allowed range")
    return normalized


def _int_value(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(f"selection directive {field} must be an integer")
    return cast("int", value)


def _string_value(value: Any, *, field: str) -> str:
    if not isinstance(value, str):
        _fail(f"selection directive {field} must be a string")
    text = cast("str", value)
    if len(text) > DIRECTIVE_STRING_MAX or has_control_character(text):
        _fail(f"selection directive {field} must be a bounded string without control characters")
    return text


def _parse_match(match: Any) -> dict[str, Any]:
    if not isinstance(match, dict):
        _fail("selection directive boost match must be an object")
    keys = set(match)
    is_column = "column" in keys
    is_tag = "tag_type" in keys or "tag" in keys
    is_year = "year" in keys
    if sum((is_column, is_tag, is_year)) != 1:
        _fail("selection directive boost match must use exactly one match form")

    if is_column:
        if keys not in ({"column", "equals"}, {"column", "in"}):
            _fail("selection directive column match has invalid keys")
        # Unknown columns are legal and match nothing (contract decision 4:
        # "unknown columns/tags referenced by a directive are flagged in the
        # rationale, never fatal") — they surface via unmatched_boosts.
        column = _string_value(match["column"], field="boost column")
        if "equals" in match:
            return {
                "column": column,
                "equals": _string_value(match["equals"], field="boost equals"),
            }
        in_values = match["in"]
        if not isinstance(in_values, list) or not in_values or len(in_values) > DIRECTIVE_LIST_MAX:
            _fail("selection directive boost in must be a non-empty bounded list")
        return {
            "column": column,
            "in": [
                _string_value(item, field="boost in value")
                for item in in_values
            ],
        }

    if is_tag:
        if keys not in ({"tag_type", "tag"}, {"tag_type", "tag", "asserted_by"}):
            _fail("selection directive tag match has invalid keys")
        normalized: dict[str, Any] = {
            "tag_type": _string_value(match["tag_type"], field="boost tag_type"),
            "tag": _string_value(match["tag"], field="boost tag"),
        }
        if "asserted_by" in match:
            normalized["asserted_by"] = _string_value(
                match["asserted_by"], field="boost asserted_by"
            )
        return normalized

    if keys != {"year"} or not isinstance(match["year"], dict):
        _fail("selection directive year match has invalid shape")
    year_match = match["year"]
    year_keys = set(year_match)
    if not year_keys or year_keys - {"gte", "lte"}:
        _fail("selection directive year match has invalid bounds")
    normalized_year: dict[str, int] = {}
    if "gte" in year_match:
        normalized_year["gte"] = _int_value(year_match["gte"], field="year gte")
    if "lte" in year_match:
        normalized_year["lte"] = _int_value(year_match["lte"], field="year lte")
    return {"year": normalized_year}


def _parse_directive(raw: Any) -> tuple[SelectionDirective, str]:
    if raw is None:
        return SelectionDirective(), "default"
    if not isinstance(raw, dict):
        _fail("selection directive must be an object")
    if not raw:
        return SelectionDirective(), "default"
    unknown = set(raw) - _DIRECTIVE_KEYS
    if unknown:
        _fail("selection directive contains unknown keys")

    budget = DEFAULT_SELECTION_BUDGET
    if "budget" in raw:
        budget = _int_value(raw["budget"], field="budget")
        if budget <= 0:
            _fail("selection directive budget must be positive")
        if budget > DIRECTIVE_BUDGET_MAX:
            _fail("selection directive budget exceeds the maximum")

    must_include_ids: tuple[uuid.UUID, ...] = ()
    if "must_include_ids" in raw:
        must_raw = raw["must_include_ids"]
        if not isinstance(must_raw, list) or len(must_raw) > DIRECTIVE_LIST_MAX:
            _fail("selection directive must_include_ids must be a bounded list")
        parsed_ids: list[uuid.UUID] = []
        for item in must_raw:
            item_string = _string_value(item, field="must_include id")
            try:
                parsed_ids.append(uuid.UUID(item_string))
            except ValueError as exc:
                raise DirectiveError(
                    "selection directive contains invalid must_include id"
                ) from exc
        must_include_ids = tuple(parsed_ids)

    boosts: tuple[_Boost, ...] = ()
    if "boosts" in raw:
        boosts_raw = raw["boosts"]
        if not isinstance(boosts_raw, list) or len(boosts_raw) > DIRECTIVE_LIST_MAX:
            _fail("selection directive boosts must be a bounded list")
        parsed_boosts: list[_Boost] = []
        for index, item in enumerate(boosts_raw):
            if not isinstance(item, dict) or set(item) != _BOOST_KEYS:
                _fail("selection directive boost must have match and weight")
            parsed_boosts.append(
                _Boost(
                    index=index,
                    match=_parse_match(item["match"]),
                    weight=_float_in_clamp(item["weight"], field="boost weight"),
                )
            )
        boosts = tuple(parsed_boosts)

    weight_emphasis: dict[str, float] | None = None
    if "weight_emphasis" in raw:
        emphasis_raw = raw["weight_emphasis"]
        if not isinstance(emphasis_raw, dict):
            _fail("selection directive weight_emphasis must be an object")
        unknown_emphasis = set(emphasis_raw) - set(DEFAULT_WEIGHTS)
        if unknown_emphasis:
            _fail("selection directive weight_emphasis contains unknown signal")
        weight_emphasis = {
            signal: _float_in_clamp(value, field="weight emphasis")
            for signal, value in emphasis_raw.items()
        }

    priority_strata: tuple[str, ...] = ()
    if "priority_strata" in raw:
        priority_raw = raw["priority_strata"]
        if not isinstance(priority_raw, list) or len(priority_raw) > DIRECTIVE_LIST_MAX:
            _fail("selection directive priority_strata must be a bounded list")
        parsed_priority: list[str] = []
        for item in priority_raw:
            pattern = _string_value(item, field="priority stratum")
            if not pattern:
                _fail("selection directive priority pattern must be non-empty")
            parsed_priority.append(pattern)
        priority_strata = tuple(parsed_priority)

    return (
        SelectionDirective(
            budget=budget,
            must_include_ids=must_include_ids,
            boosts=boosts,
            weight_emphasis=weight_emphasis,
            priority_strata=priority_strata,
        ),
        "scope_context",
    )


def _effective_weights(directive: SelectionDirective) -> dict[str, float]:
    emphasis = directive.weight_emphasis or {}
    return {
        signal: weight * emphasis.get(signal, 1.0)
        for signal, weight in DEFAULT_WEIGHTS.items()
    }


def _year_value(source: ScreenedSource) -> int | None:
    value = source.metadata.get("year")
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _signal_values(
    source: ScreenedSource, *, reference_year: int
) -> tuple[dict[str, float], list[str]]:
    signals: dict[str, float] = {}
    missing: list[str] = []

    year = _year_value(source)
    if year is None or year > reference_year + RECENCY_FUTURE_GRACE_YEARS:
        # Absent or implausibly-future year metadata reads neutral and is
        # flagged — never a recency reward for bad data (flag-not-block).
        signals["recency"] = 0.5
        missing.append("recency")
    else:
        age_years = max(0, reference_year - year)
        signals["recency"] = max(0.0, 1 - age_years / 15)

    if source.quality_score is None:
        signals["quality"] = 0.5
        missing.append("quality")
    else:
        signals["quality"] = (source.quality_score - 1) / 4

    if source.text_basis == "full_text":
        signals["text_basis"] = 1.0
    elif source.text_basis == "abstract_only":
        signals["text_basis"] = 0.25
    else:
        signals["text_basis"] = 0.5
        missing.append("text_basis")

    if source.screen_confidence is None:
        signals["screen_confidence"] = 0.5
        missing.append("screen_confidence")
    else:
        signals["screen_confidence"] = source.screen_confidence

    if source.origin == "uploaded":
        signals["origin"] = 1.0
    elif source.origin == "acquired":
        signals["origin"] = 0.5
    else:
        signals["origin"] = 0.5
        missing.append("origin")

    return (
        {signal: signals[signal] for signal in DEFAULT_WEIGHTS},
        [signal for signal in DEFAULT_WEIGHTS if signal in missing],
    )


def _column_value(source: ScreenedSource, column: str) -> str | None:
    if column == "origin":
        return source.origin
    if column == "primary_evidence_type":
        return source.primary_evidence_type
    if column == "text_basis":
        return source.text_basis
    # Unknown column: matches nothing; the boost lands in unmatched_boosts.
    return None


def _boost_matches(candidate: SelectionCandidate, match: dict[str, Any]) -> bool:
    source = candidate.source
    if "column" in match:
        value = _column_value(source, cast("str", match["column"]))
        if "equals" in match:
            return value == cast("str", match["equals"])
        return value in cast("list[str]", match["in"])
    if "tag_type" in match:
        asserted_by = match.get("asserted_by")
        return any(
            tag.tag_type == match["tag_type"]
            and tag.tag == match["tag"]
            and (asserted_by is None or tag.asserted_by == asserted_by)
            for tag in candidate.tags
        )
    year = _year_value(source)
    if year is None:
        return False
    year_match = cast("dict[str, int]", match["year"])
    if "gte" in year_match and year < year_match["gte"]:
        return False
    return not ("lte" in year_match and year > year_match["lte"])


def _boost_multiplier(
    candidate: SelectionCandidate,
    directive: SelectionDirective,
    match_counts: dict[int, int],
) -> float:
    multiplier = 1.0
    for boost in directive.boosts:
        if _boost_matches(candidate, boost.match):
            match_counts[boost.index] += 1
            multiplier *= boost.weight
    return min(BOOST_CLAMP[1], max(BOOST_CLAMP[0], multiplier))


def _signal_docs(
    candidates: Sequence[SelectionCandidate],
    directive: SelectionDirective,
    *,
    reference_year: int,
) -> tuple[dict[uuid.UUID, _SignalDoc], dict[str, int], list[int], dict[str, float]]:
    effective_weights = _effective_weights(directive)
    match_counts = {boost.index: 0 for boost in directive.boosts}
    signal_availability = {signal: 0 for signal in DEFAULT_WEIGHTS}
    docs: dict[uuid.UUID, _SignalDoc] = {}

    for candidate in candidates:
        signals, missing = _signal_values(candidate.source, reference_year=reference_year)
        for signal in missing:
            signal_availability[signal] += 1
        boost_multiplier = _boost_multiplier(candidate, directive, match_counts)
        composite = (
            sum(effective_weights[signal] * signals[signal] for signal in DEFAULT_WEIGHTS)
            * boost_multiplier
        )
        docs[candidate.source.pss_id] = _SignalDoc(
            candidate=candidate,
            signals=signals,
            missing_signals=missing,
            composite=composite,
            boost_multiplier=boost_multiplier,
        )

    unmatched_boosts = [
        boost.index
        for boost in directive.boosts
        if match_counts[boost.index] == 0
    ]
    return docs, signal_availability, unmatched_boosts, effective_weights


def _share(count: int, base: int) -> float:
    return 0.0 if base == 0 else count / base


def _ordered_strata(strata: Sequence[SelectionStratum]) -> list[SelectionStratum]:
    return sorted(strata, key=lambda stratum: (-len(stratum.candidate_ids), stratum.name))


def _stratum_doc_map(strata: Sequence[SelectionStratum]) -> dict[uuid.UUID, str]:
    seen: dict[uuid.UUID, str] = {}
    for stratum in strata:
        for pss_id in stratum.candidate_ids:
            if pss_id in seen:
                raise SelectError("characterisation assigns a source to multiple strata")
            seen[pss_id] = stratum.name
    return seen


def _largest_remainder_slots(
    capacities: dict[str, int],
    *,
    slots: int,
    stratum_order: list[str],
) -> dict[str, int]:
    allocations = {name: 0 for name in capacities}
    remaining = min(slots, sum(capacities.values()))
    if remaining <= 0:
        return allocations
    total_capacity = sum(capacity for capacity in capacities.values() if capacity > 0)
    if total_capacity == 0:
        return allocations

    quotas = {
        name: remaining * capacities[name] / total_capacity
        for name in stratum_order
        if capacities[name] > 0
    }
    for name, quota in quotas.items():
        allocations[name] = min(capacities[name], math.floor(quota))
    leftover = remaining - sum(allocations.values())

    fractional_order = sorted(
        quotas,
        key=lambda name: (-(quotas[name] - math.floor(quotas[name])), stratum_order.index(name)),
    )
    while leftover > 0:
        progressed = False
        for name in fractional_order:
            if leftover == 0:
                break
            if allocations[name] < capacities[name]:
                allocations[name] += 1
                leftover -= 1
                progressed = True
        if not progressed:
            break
    return allocations


def _allocate(
    *,
    strata: Sequence[SelectionStratum],
    directive: SelectionDirective,
    selected_must_by_stratum: dict[str, set[uuid.UUID]],
) -> _Allocation:
    remaining_budget = directive.budget
    floor_slots = {stratum.name: 0 for stratum in strata}
    ranked_slots = {stratum.name: 0 for stratum in strata}

    for stratum in strata:
        if remaining_budget == 0:
            break
        if not stratum.candidate_ids or selected_must_by_stratum[stratum.name]:
            continue
        floor_slots[stratum.name] = 1
        remaining_budget -= 1

    capacities: dict[str, int] = {}
    for stratum in strata:
        must_count = len(selected_must_by_stratum[stratum.name])
        capacities[stratum.name] = max(
            0,
            len(stratum.candidate_ids) - must_count - floor_slots[stratum.name],
        )
    stratum_order = [stratum.name for stratum in strata]
    ranked_slots = _largest_remainder_slots(
        capacities,
        slots=remaining_budget,
        stratum_order=stratum_order,
    )
    allocated_slots = {
        name: floor_slots[name] + ranked_slots[name]
        for name in floor_slots
    }
    return _Allocation(
        floor_slots=floor_slots,
        ranked_slots=ranked_slots,
        allocated_slots=allocated_slots,
    )


def _doc_for_rerank(signal_doc: _SignalDoc) -> GroupingDoc:
    source = signal_doc.candidate.source
    title_value = source.metadata.get("title")
    title = title_value if isinstance(title_value, str) and title_value else source.source_locator
    abstract_value = source.metadata.get("abstract")
    abstract = abstract_value if isinstance(abstract_value, str) else None
    return {"id": str(source.pss_id), "title": title, "abstract": abstract}


def _batches(values: list[uuid.UUID]) -> list[list[uuid.UUID]]:
    return [
        values[start:start + RERANK_BATCH_SIZE]
        for start in range(0, len(values), RERANK_BATCH_SIZE)
    ]


def _fallback_batch(
    batch: Sequence[uuid.UUID],
    rank_infos: dict[uuid.UUID, _RankInfo],
) -> int:
    for pss_id in batch:
        rank_infos[pss_id] = _RankInfo(score=None, reason=None, rank_fallback=True)
    return len(batch)


def _apply_ranked_output(
    *,
    batch: Sequence[uuid.UUID],
    output: list[RankedDoc],
    rank_infos: dict[uuid.UUID, _RankInfo],
) -> int:
    valid = validate_ranked({str(pss_id) for pss_id in batch}, output)
    fallback_count = 0
    for pss_id in batch:
        ranked = valid.get(str(pss_id))
        if ranked is None:
            rank_infos[pss_id] = _RankInfo(score=None, reason=None, rank_fallback=True)
            fallback_count += 1
        else:
            rank_infos[pss_id] = _RankInfo(
                score=ranked["score"],
                reason=ranked["reason"],
                rank_fallback=False,
            )
    return fallback_count


def _rerank_infos(
    *,
    contested_ids: list[uuid.UUID],
    signal_docs: dict[uuid.UUID, _SignalDoc],
    ranking_backend: RankingBackend,
    intent: str,
) -> tuple[dict[uuid.UUID, _RankInfo], _RerankStats, dict[str, int]]:
    baseline = math.ceil(len(contested_ids) / RERANK_BATCH_SIZE)
    maximum = baseline * (1 + RERANK_RETRY_CAP)
    # Contract decision 10: judging degrades to title-only where the envelope
    # did — counted here so the degradation is flagged, never silent.
    title_only_count = sum(
        1
        for pss_id in contested_ids
        if _doc_for_rerank(signal_docs[pss_id])["abstract"] is None
    )
    log.info(
        "select.rerank_call_budget",
        baseline=baseline,
        maximum=maximum,
        title_only=title_only_count,
    )
    budget = _RerankCallBudget(maximum=maximum)
    rank_infos: dict[uuid.UUID, _RankInfo] = {}
    fallback_count = 0
    retry_count = 0
    batches = _batches(contested_ids)
    submitted: list[tuple[list[uuid.UUID], Future[Any]]] = []
    usage_totals = UsageAccumulator()

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_RERANK_BATCHES) as executor:
        for batch in batches:
            if not budget.reserve():
                fallback_count += _fallback_batch(batch, rank_infos)
                continue
            docs = [_doc_for_rerank(signal_docs[pss_id]) for pss_id in batch]
            submitted.append((
                batch,
                tracing.submit_with_context(
                    executor, ranking_backend.rank, docs, intent=intent
                ),
            ))
        wait([future for _, future in submitted])

    for batch, future in submitted:
        try:
            output, usage = future.result()
            usage_totals.add(usage)
        except Exception as exc:
            log.warning(
                "select.rerank_batch_failed",
                batch_size=len(batch),
                error_type=type(exc).__name__,
            )
            if budget.reserve():
                retry_count += 1
                try:
                    output, usage = ranking_backend.rank(
                        [_doc_for_rerank(signal_docs[pss_id]) for pss_id in batch],
                        intent=intent,
                    )
                    usage_totals.add(usage)
                except Exception as retry_exc:
                    log.warning(
                        "select.rerank_batch_retry_failed",
                        batch_size=len(batch),
                        error_type=type(retry_exc).__name__,
                    )
                    fallback_count += _fallback_batch(batch, rank_infos)
                else:
                    fallback_count += _apply_ranked_output(
                        batch=batch,
                        output=output,
                        rank_infos=rank_infos,
                    )
            else:
                fallback_count += _fallback_batch(batch, rank_infos)
        else:
            fallback_count += _apply_ranked_output(
                batch=batch,
                output=output,
                rank_infos=rank_infos,
            )

    return (
        rank_infos,
        _RerankStats(
            baseline=baseline,
            maximum=maximum,
            used=budget.used,
            retry_count=retry_count,
            fallback_count=fallback_count,
            title_only_count=title_only_count,
        ),
        usage_totals.payload(),
    )


def _deterministic_order(
    ids: Sequence[uuid.UUID],
    signal_docs: dict[uuid.UUID, _SignalDoc],
) -> list[uuid.UUID]:
    return sorted(ids, key=lambda pss_id: (-signal_docs[pss_id].composite, str(pss_id)))


def _llm_order(
    ids: Sequence[uuid.UUID],
    signal_docs: dict[uuid.UUID, _SignalDoc],
    rank_infos: dict[uuid.UUID, _RankInfo],
) -> list[uuid.UUID]:
    scored = [
        pss_id
        for pss_id in ids
        if pss_id in rank_infos and rank_infos[pss_id].score is not None
    ]
    fallback = [
        pss_id
        for pss_id in ids
        if pss_id not in rank_infos or rank_infos[pss_id].score is None
    ]
    return sorted(
        scored,
        key=lambda pss_id: (
            -cast("int", rank_infos[pss_id].score),
            -signal_docs[pss_id].composite,
            str(pss_id),
        ),
    ) + _deterministic_order(fallback, signal_docs)


def _priority_matches_stratum(
    pattern: str,
    stratum: SelectionStratum,
    signal_docs: dict[uuid.UUID, _SignalDoc],
) -> bool:
    folded = pattern.casefold()
    if folded in stratum.name.casefold():
        return True
    return any(
        folded == tag.tag.casefold()
        for pss_id in stratum.candidate_ids
        for tag in signal_docs[pss_id].candidate.tags
    )


def _priority_matches(
    directive: SelectionDirective,
    strata: Sequence[SelectionStratum],
    signal_docs: dict[uuid.UUID, _SignalDoc],
) -> tuple[set[str], list[str]]:
    matched_strata: set[str] = set()
    unmatched_patterns: list[str] = []
    for pattern in directive.priority_strata:
        pattern_matches: set[str] = {
            stratum.name
            for stratum in strata
            if _priority_matches_stratum(pattern, stratum, signal_docs)
        }
        if pattern_matches:
            matched_strata.update(pattern_matches)
        else:
            unmatched_patterns.append(pattern)
    return matched_strata, unmatched_patterns


def _selected_record(
    *,
    pss_id: uuid.UUID,
    stratum_name: str,
    reason: str,
    signal_doc: _SignalDoc,
    strategy: str,
    rank_infos: dict[uuid.UUID, _RankInfo],
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "pss_id": str(pss_id),
        "stratum": stratum_name,
        "reason": reason,
        "text_basis": signal_doc.candidate.source.text_basis,
        "screen_stage": signal_doc.candidate.source.screen_stage,
        "signals": signal_doc.signals,
        "missing_signals": signal_doc.missing_signals,
        "composite": signal_doc.composite,
        "boost_multiplier": signal_doc.boost_multiplier,
    }
    if strategy == "llm_rerank_v1" and pss_id in rank_infos:
        rank_info = rank_infos[pss_id]
        if rank_info.score is not None:
            record["llm_score"] = rank_info.score
            record["llm_reason"] = rank_info.reason
        record["rank_fallback"] = rank_info.rank_fallback
    return record


def _stratum_share(
    ids: Sequence[uuid.UUID],
    selected_ids: Sequence[uuid.UUID],
    signal_docs: dict[uuid.UUID, _SignalDoc],
) -> tuple[float, float]:
    candidate_full_text = sum(
        1 for pss_id in ids if signal_docs[pss_id].candidate.source.text_basis == "full_text"
    )
    selected_full_text = sum(
        1
        for pss_id in selected_ids
        if signal_docs[pss_id].candidate.source.text_basis == "full_text"
    )
    return _share(candidate_full_text, len(ids)), _share(selected_full_text, len(selected_ids))


def _reason_counts(selected: Sequence[dict[str, Any]]) -> dict[str, int]:
    counts = {reason: 0 for reason in _REASON_ORDER}
    for record in selected:
        reason = cast("str", record["reason"])
        counts[reason] += 1
    return {reason: counts[reason] for reason in _REASON_ORDER if counts[reason] > 0}


def _flags(
    *,
    strata: Sequence[SelectionStratum],
    selected_by_stratum: dict[str, list[uuid.UUID]],
    eligible_total: int,
    signal_docs: dict[uuid.UUID, _SignalDoc],
    priority_matched_strata: set[str],
    must_include_out_of_scope: list[str],
) -> dict[str, Any]:
    flags: dict[str, Any] = {}
    large_strata = [
        stratum.name
        for stratum in strata
        if len(selected_by_stratum[stratum.name]) == 0
        and len(stratum.candidate_ids) >= LARGE_STRATUM_SHARE * eligible_total
    ]
    if large_strata:
        flags["large_stratum_excluded"] = large_strata

    priority_excluded = [
        stratum.name
        for stratum in strata
        if stratum.name in priority_matched_strata
        and len(selected_by_stratum[stratum.name]) == 0
    ]
    if priority_excluded:
        flags["priority_stratum_excluded"] = priority_excluded

    if must_include_out_of_scope:
        flags["must_include_conflict"] = must_include_out_of_scope

    sufficiently_confident = sum(
        1
        for signal_doc in signal_docs.values()
        if signal_doc.candidate.source.screen_confidence is not None
        and signal_doc.candidate.source.screen_confidence >= SUFFICIENT_CONFIDENCE
    )
    if sufficiently_confident < THIN_BASE_FLOOR:
        flags["thin_base"] = {
            "sufficiently_confident": sufficiently_confident,
            "floor": THIN_BASE_FLOOR,
        }

    selected_ids = [
        pss_id
        for selected_ids_for_stratum in selected_by_stratum.values()
        for pss_id in selected_ids_for_stratum
    ]
    full_text_share = _share(
        sum(
            1
            for pss_id in selected_ids
            if signal_docs[pss_id].candidate.source.text_basis == "full_text"
        ),
        len(selected_ids),
    )
    if full_text_share < THIN_FULL_TEXT_SHARE:
        flags["thin_full_text"] = {
            "share": full_text_share,
            "floor": THIN_FULL_TEXT_SHARE,
        }
    return flags


def _assert_outcome_invariants(
    *,
    eligible_total: int,
    selected: Sequence[dict[str, Any]],
    strata: Sequence[SelectionStratum],
    selected_by_stratum: dict[str, list[uuid.UUID]],
    not_in_characterisation: int,
) -> None:
    selected_ids = [record["pss_id"] for record in selected]
    if len(selected_ids) != len(set(selected_ids)):
        raise SelectError("selection invariant violated: duplicate selected source")
    not_selected = (
        sum(
            len(stratum.candidate_ids) - len(selected_by_stratum[stratum.name])
            for stratum in strata
        )
        + not_in_characterisation
    )
    if eligible_total != len(selected) + not_selected:
        raise SelectError("selection invariant violated: eligible count mismatch")
    reason_total = sum(_reason_counts(selected).values())
    if reason_total != len(selected):
        raise SelectError("selection invariant violated: selected reason count mismatch")
    bucketed_selected = sum(len(ids) for ids in selected_by_stratum.values())
    if bucketed_selected != len(selected):
        raise SelectError("selection invariant violated: selected stratum bucket mismatch")


def select_documents(
    candidates: Sequence[SelectionCandidate],
    *,
    strata: Sequence[SelectionStratum],
    strategy: str,
    directive: SelectionDirective,
    intent: str,
    ranking_backend: RankingBackend | None,
) -> SelectionOutcome:
    """Select candidate documents for Tier-1 extraction.

    Args:
        candidates: Eligible screened sources enriched with source tags.
        strata: Characterisation strata over the eligible candidates.
        strategy: Selection strategy version.
        directive: Validated selection directive.
        intent: Evidence intent used by optional reranking.
        ranking_backend: Optional ranking backend for ``llm_rerank_v1``.

    Returns:
        Selection outcome with deterministic rationale payloads.

    Raises:
        ValueError: If the strategy is unknown or rerank is requested without a backend.
        SelectError: If a selection invariant is violated.
    """
    if strategy not in SELECTION_STRATEGIES:
        raise ValueError(f"unknown selection strategy {strategy}")
    if strategy == "llm_rerank_v1" and ranking_backend is None:
        raise ValueError("llm_rerank_v1 requires a ranking backend")

    ordered_strata = _ordered_strata(strata)
    candidate_by_id = {candidate.source.pss_id: candidate for candidate in candidates}
    # Pinned once per run and recorded in provenance: recency is clock-relative
    # by definition, so the payload names the year it was computed against.
    reference_year = datetime.now(UTC).year
    signal_docs, signal_availability, unmatched_boosts, effective_weights = _signal_docs(
        candidates,
        directive,
        reference_year=reference_year,
    )
    stratum_by_doc = _stratum_doc_map(ordered_strata)
    selectable_ids = set(stratum_by_doc)
    not_in_characterisation = len(set(candidate_by_id) - selectable_ids)

    # Out of scope = not selectable: not eligible, or eligible but absent from the
    # referenced characterisation (a must-include is never silently unselected).
    must_include_out_of_scope = [
        str(pss_id)
        for pss_id in directive.must_include_ids
        if pss_id not in selectable_ids
    ]
    notable_exclusions = [
        {"pss_id": pss_id, "flag": "must_include_not_in_scope"}
        for pss_id in must_include_out_of_scope
    ]
    selected_must_by_stratum = {stratum.name: set[uuid.UUID]() for stratum in ordered_strata}
    for pss_id in directive.must_include_ids:
        if pss_id in selectable_ids:
            selected_must_by_stratum[stratum_by_doc[pss_id]].add(pss_id)

    allocation = _allocate(
        strata=ordered_strata,
        directive=directive,
        selected_must_by_stratum=selected_must_by_stratum,
    )
    rankable_by_stratum = {
        stratum.name: [
            pss_id
            for pss_id in stratum.candidate_ids
            if pss_id not in selected_must_by_stratum[stratum.name]
        ]
        for stratum in ordered_strata
    }
    # Contested = some rankable docs selected, some not (contract decision 10:
    # allocation < stratum size) — a floor-only slot is still a real choice the
    # ranker must order; wholly-selected and zero-slot strata get no calls.
    contested_strata = {
        stratum.name
        for stratum in ordered_strata
        if 0 < allocation.allocated_slots[stratum.name] < len(rankable_by_stratum[stratum.name])
    }
    rank_infos: dict[uuid.UUID, _RankInfo] = {}
    rerank_stats: _RerankStats | None = None
    usage_totals = UsageAccumulator().payload()
    if strategy == "llm_rerank_v1":
        contested_ids = [
            pss_id
            for stratum in ordered_strata
            if stratum.name in contested_strata
            for pss_id in sorted(rankable_by_stratum[stratum.name], key=str)
        ]
        rank_infos, rerank_stats, usage_totals = _rerank_infos(
            contested_ids=contested_ids,
            signal_docs=signal_docs,
            ranking_backend=cast("RankingBackend", ranking_backend),
            intent=intent,
        )

    selected: list[dict[str, Any]] = []
    selected_by_stratum: dict[str, list[uuid.UUID]] = {
        stratum.name: [] for stratum in ordered_strata
    }
    excluded_by_stratum: dict[str, dict[str, int]] = {}

    for stratum in ordered_strata:
        must_ids = sorted(selected_must_by_stratum[stratum.name], key=str)
        selected_by_stratum[stratum.name].extend(must_ids)
        for pss_id in must_ids:
            selected.append(
                _selected_record(
                    pss_id=pss_id,
                    stratum_name=stratum.name,
                    reason="must_include",
                    signal_doc=signal_docs[pss_id],
                    strategy=strategy,
                    rank_infos=rank_infos,
                )
            )

        rankable_ids = rankable_by_stratum[stratum.name]
        if strategy == "llm_rerank_v1" and stratum.name in contested_strata:
            ordered_rankable = _llm_order(rankable_ids, signal_docs, rank_infos)
        else:
            ordered_rankable = _deterministic_order(rankable_ids, signal_docs)
        allocated = allocation.allocated_slots[stratum.name]
        selected_rankable = ordered_rankable[:allocated]
        for offset, pss_id in enumerate(selected_rankable):
            reason = "breadth_floor" if offset < allocation.floor_slots[stratum.name] else "ranked"
            selected_by_stratum[stratum.name].append(pss_id)
            selected.append(
                _selected_record(
                    pss_id=pss_id,
                    stratum_name=stratum.name,
                    reason=reason,
                    signal_doc=signal_docs[pss_id],
                    strategy=strategy,
                    rank_infos=rank_infos,
                )
            )

        unselected_count = len(stratum.candidate_ids) - len(selected_by_stratum[stratum.name])
        if unselected_count:
            reason_class = (
                "ranked_below_cut"
                if allocation.ranked_slots[stratum.name] > 0
                else "budget_exhausted"
            )
            excluded_by_stratum[stratum.name] = {reason_class: unselected_count}

    priority_matched_strata, unmatched_priority_patterns = _priority_matches(
        directive,
        ordered_strata,
        signal_docs,
    )
    flags = _flags(
        strata=ordered_strata,
        selected_by_stratum=selected_by_stratum,
        eligible_total=len(candidates),
        signal_docs=signal_docs,
        priority_matched_strata=priority_matched_strata,
        must_include_out_of_scope=must_include_out_of_scope,
    )

    strata_summary: list[dict[str, Any]] = []
    for stratum in ordered_strata:
        selected_ids = selected_by_stratum[stratum.name]
        candidate_share, selected_share = _stratum_share(
            stratum.candidate_ids,
            selected_ids,
            signal_docs,
        )
        strata_summary.append({
            "name": stratum.name,
            "candidate_count": len(stratum.candidate_ids),
            "allocated_count": allocation.allocated_slots[stratum.name],
            "selected_count": len(selected_ids),
            "selected_ids": [str(pss_id) for pss_id in selected_ids],
            "full_text_share_candidates": candidate_share,
            "full_text_share_selected": selected_share,
        })

    _assert_outcome_invariants(
        eligible_total=len(candidates),
        selected=selected,
        strata=ordered_strata,
        selected_by_stratum=selected_by_stratum,
        not_in_characterisation=not_in_characterisation,
    )

    backend_mode = ranking_backend.mode if ranking_backend is not None else "none"
    provenance: dict[str, Any] = {
        "effective_weights": effective_weights,
        "signal_availability": signal_availability,
        "recency_reference_year": reference_year,
        "unmatched_boosts": unmatched_boosts,
        "unmatched_priority_patterns": unmatched_priority_patterns,
        "backend_mode": backend_mode,
    }
    if strategy == "llm_rerank_v1":
        stats = rerank_stats or _RerankStats(0, 0, 0, 0, 0, 0)
        provenance.update({
            "prompt_version": PROMPT_VERSION,
            "model": RERANK_MODEL,
            "batch_size": RERANK_BATCH_SIZE,
            "call_budget": {
                "baseline": stats.baseline,
                "maximum": stats.maximum,
                "used": stats.used,
            },
            "retry_count": stats.retry_count,
            "fallback_count": stats.fallback_count,
            "title_only_count": stats.title_only_count,
        })

    return SelectionOutcome(
        strategy=strategy,
        budget=directive.budget,
        strata=strata_summary,
        selected=selected,
        excluded_by_stratum=excluded_by_stratum,
        notable_exclusions=notable_exclusions,
        flags=flags,
        provenance=provenance,
        usage_totals=usage_totals,
        selected_by_reason=_reason_counts(selected),
        not_in_characterisation=not_in_characterisation,
    )


def _tags_by_source(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    pss_ids: Sequence[uuid.UUID],
) -> dict[uuid.UUID, tuple[SourceTag, ...]]:
    if not pss_ids:
        return {}
    rows = conn.execute(
        sa_select(
            source_tag.c.project_source_snapshot_id,
            source_tag.c.tag_type,
            source_tag.c.tag,
            source_tag.c.asserted_by,
        )
        .where(source_tag.c.project_id == project_id)
        .where(source_tag.c.project_source_snapshot_id.in_(pss_ids))
        .order_by(
            source_tag.c.project_source_snapshot_id,
            source_tag.c.tag_type,
            source_tag.c.asserted_by,
            source_tag.c.tag,
        )
    ).fetchall()
    tags: dict[uuid.UUID, list[SourceTag]] = {}
    for row in rows:
        pss_id = cast("uuid.UUID", row.project_source_snapshot_id)
        tags.setdefault(pss_id, []).append(
            SourceTag(
                tag_type=cast("str", row.tag_type),
                tag=cast("str", row.tag),
                asserted_by=cast("str", row.asserted_by),
            )
        )
    return {pss_id: tuple(values) for pss_id, values in tags.items()}


def _candidate_inputs(
    sources: Sequence[ScreenedSource],
    tags_by_pss: dict[uuid.UUID, tuple[SourceTag, ...]],
) -> list[SelectionCandidate]:
    return [
        SelectionCandidate(source=source, tags=tags_by_pss.get(source.pss_id, ()))
        for source in sources
    ]


def _parse_uuid_list(values: Any, *, field: str) -> tuple[uuid.UUID, ...]:
    if not isinstance(values, list):
        raise SelectError(f"characterisation field {field} must be a list")
    parsed: list[uuid.UUID] = []
    for value in values:
        if not isinstance(value, str):
            raise SelectError(f"characterisation field {field} contains a non-string id")
        try:
            parsed.append(uuid.UUID(value))
        except ValueError as exc:
            raise SelectError(f"characterisation field {field} contains an invalid id") from exc
    return tuple(parsed)


def _load_strata(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    characterisation_run_id: uuid.UUID,
    eligible_ids: set[uuid.UUID],
) -> list[SelectionStratum]:
    row = conn.execute(
        sa_select(characterisation_result.c.themes)
        .where(characterisation_result.c.project_id == project_id)
        .where(characterisation_result.c.evidence_scope_id == scope_id)
        .where(characterisation_result.c.run_id == characterisation_run_id)
    ).first()
    if row is None:
        raise SelectError(
            "no characterisation row for scope "
            f"{scope_id} and characterisation_run_id {characterisation_run_id} "
            "— run characterise first"
        )
    payload = row.themes
    if not isinstance(payload, dict):
        raise SelectError("characterisation themes payload must be an object")

    raw_themes = payload.get("themes")
    if not isinstance(raw_themes, list):
        raise SelectError("characterisation themes payload missing themes list")
    raw_strata: list[tuple[str, tuple[uuid.UUID, ...]]] = []
    seen_names: set[str] = set()
    for index, theme in enumerate(raw_themes):
        if not isinstance(theme, dict):
            raise SelectError("characterisation theme entry must be an object")
        name = theme.get("name")
        if not isinstance(name, str):
            raise SelectError("characterisation theme entry missing name")
        if name in seen_names:
            raise SelectError("characterisation theme names must be unique")
        seen_names.add(name)
        raw_strata.append((
            name,
            _parse_uuid_list(theme.get("member_ids"), field=f"themes[{index}].member_ids"),
        ))

    unclustered_ids = _parse_uuid_list(payload.get("unclustered_ids"), field="unclustered_ids")
    raw_strata.append((UNCLUSTERED, unclustered_ids))
    return [
        SelectionStratum(
            name=name,
            candidate_ids=tuple(pss_id for pss_id in ids if pss_id in eligible_ids),
        )
        for name, ids in raw_strata
    ]


def _selection_provenance(
    *,
    strategy: str,
    characterisation_run_id: uuid.UUID,
    directive: SelectionDirective,
    directive_source: str,
    outcome: SelectionOutcome,
) -> dict[str, Any]:
    return {
        "strategy_version": strategy,
        "characterisation_run_id": str(characterisation_run_id),
        "directive": directive.normalized(),
        "directive_source": directive_source,
        **outcome.provenance,
    }


def _assert_base_invariants(
    *,
    screened_in: int,
    non_evidence: int,
    eligible: int,
    selected: Sequence[dict[str, Any]],
    not_selected: int,
) -> None:
    if screened_in != non_evidence + eligible:
        raise SelectError("selection invariant violated: screened base mismatch")
    if eligible != len(selected) + not_selected:
        raise SelectError("selection invariant violated: selected base mismatch")
    if sum(_reason_counts(selected).values()) != len(selected):
        raise SelectError("selection invariant violated: selected reasons mismatch")


def _summary(
    *,
    outcome: SelectionOutcome,
    excluded: dict[str, Any],
    base: dict[str, int],
    characterisation_run_id: uuid.UUID,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    return {
        "strata": outcome.strata,
        "selected": {
            "count": len(outcome.selected),
            "by_reason": outcome.selected_by_reason,
        },
        "excluded": {
            "by_stratum_reason_counts": outcome.excluded_by_stratum,
            "notable": outcome.notable_exclusions,
        },
        "base": base,
        "characterisation_run_id": str(characterisation_run_id),
        "flags": outcome.flags,
        "provenance": provenance,
        "usage_totals": outcome.usage_totals,
    }


def _empty_summary(
    *,
    screened_in: int,
    non_evidence: int,
    characterisation_run_id: uuid.UUID,
    strategy: str,
    directive: SelectionDirective,
    directive_source: str,
    ranking_backend: RankingBackend | None,
) -> dict[str, Any]:
    provenance: dict[str, Any] = {
        "strategy_version": strategy,
        "characterisation_run_id": str(characterisation_run_id),
        "directive": directive.normalized(),
        "directive_source": directive_source,
        "effective_weights": _effective_weights(directive),
        "signal_availability": {signal: 0 for signal in DEFAULT_WEIGHTS},
        "unmatched_boosts": [boost.index for boost in directive.boosts],
        "unmatched_priority_patterns": list(directive.priority_strata),
        "backend_mode": ranking_backend.mode if ranking_backend is not None else "none",
    }
    if strategy == "llm_rerank_v1":
        # Same provenance shape as a ranked run — an empty scope spends zero
        # calls but readers (e.g. the skeleton's rerank-fired check) still see
        # the call-budget keys (review finding: KeyError on the live path).
        provenance.update({
            "prompt_version": PROMPT_VERSION,
            "model": RERANK_MODEL,
            "batch_size": RERANK_BATCH_SIZE,
            "call_budget": {"baseline": 0, "maximum": 0, "used": 0},
            "retry_count": 0,
            "fallback_count": 0,
            "title_only_count": 0,
        })
    return {
        "strata": [],
        "selected": {"count": 0, "by_reason": {}},
        "excluded": {"by_stratum_reason_counts": {}, "notable": []},
        "base": {
            "screened_in": screened_in,
            "non_evidence": non_evidence,
            "eligible": 0,
        },
        "characterisation_run_id": str(characterisation_run_id),
        "flags": {"empty_scope": {"eligible": 0}},
        "provenance": provenance,
        "usage_totals": UsageAccumulator().payload(),
    }


def select_scope(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    context: SelectContext,
    ranking_backend: RankingBackend | None,
) -> dict[str, Any]:
    """Select Tier-1 extraction documents and persist the run-local result.

    Args:
        conn: Open database connection; all writes use its active transaction.
        project_id: Owning project.
        run_id: Run writing the selection result.
        context: Scope-level select input.
        ranking_backend: Optional reranking backend; ``None`` selects deterministically.

    Returns:
        Selection summary payload for ``component.completed``.

    Raises:
        SelectError: If required characterisation or structural invariants fail.
        DirectiveError: If the scope selection directive is malformed.
    """
    strategy = "llm_rerank_v1" if ranking_backend is not None else "coverage_stratified_v1"
    directive, directive_source = _parse_directive(context.context.get("selection"))
    candidates = screened_sources(conn, project_id=project_id, scope_id=context.scope_id)
    eligible_sources = [
        source
        for source in candidates
        if source.primary_evidence_type != NON_EVIDENCE_TYPE
    ]
    screened_in = len(candidates)
    non_evidence = screened_in - len(eligible_sources)
    if not eligible_sources:
        return _empty_summary(
            screened_in=screened_in,
            non_evidence=non_evidence,
            characterisation_run_id=context.characterisation_run_id,
            strategy=strategy,
            directive=directive,
            directive_source=directive_source,
            ranking_backend=ranking_backend,
        )

    tags_by_pss = _tags_by_source(
        conn,
        project_id=project_id,
        pss_ids=[source.pss_id for source in eligible_sources],
    )
    pure_candidates = _candidate_inputs(eligible_sources, tags_by_pss)
    eligible_ids = {source.pss_id for source in eligible_sources}
    strata = _load_strata(
        conn,
        project_id=project_id,
        scope_id=context.scope_id,
        characterisation_run_id=context.characterisation_run_id,
        eligible_ids=eligible_ids,
    )
    outcome = select_documents(
        pure_candidates,
        strata=strata,
        strategy=strategy,
        directive=directive,
        intent=context.intent,
        ranking_backend=ranking_backend,
    )
    base = {
        "screened_in": screened_in,
        "non_evidence": non_evidence,
        "eligible": len(eligible_sources),
    }
    excluded = {
        "by_stratum": outcome.excluded_by_stratum,
        "notable": outcome.notable_exclusions,
        "base": {
            **base,
            "not_in_characterisation": outcome.not_in_characterisation,
        },
    }
    not_selected = (
        sum(sum(reason_counts.values()) for reason_counts in outcome.excluded_by_stratum.values())
        + outcome.not_in_characterisation
    )
    _assert_base_invariants(
        screened_in=screened_in,
        non_evidence=non_evidence,
        eligible=len(eligible_sources),
        selected=outcome.selected,
        not_selected=not_selected,
    )
    provenance = _selection_provenance(
        strategy=strategy,
        characterisation_run_id=context.characterisation_run_id,
        directive=directive,
        directive_source=directive_source,
        outcome=outcome,
    )

    conn.execute(
        selection_result.insert().values(
            selection_result_id=uuid.uuid4(),
            project_id=project_id,
            evidence_scope_id=context.scope_id,
            run_id=run_id,
            strategy=outcome.strategy,
            budget=outcome.budget,
            selection_provenance=provenance,
            selected=outcome.selected,
            excluded=excluded,
            flags=outcome.flags,
            created_at=datetime.now(UTC),
        )
    )
    return _summary(
        outcome=outcome,
        excluded=excluded,
        base=base,
        characterisation_run_id=context.characterisation_run_id,
        provenance=provenance,
    )
