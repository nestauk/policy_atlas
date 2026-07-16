"""Deterministic steering primitives for orchestration-plan runs.

This module owns the task-017 structural steering core: pause-boundary
compilation, deterministic human-readable renders, bounded adjustment
validation/persistence and Unattended-mode default resolution. It deliberately
contains no prompt surface.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, cast

from pydantic import ValidationError
from sqlalchemy import select as sa_select
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import orchestration_plan, selection_result
from policy_atlas.evidence_base.assess import appraise as appraise_module
from policy_atlas.evidence_base.assess import screen as screen_module
from policy_atlas.evidence_base.corpus import characterise as characterise_module
from policy_atlas.evidence_base.corpus import select as select_module
from policy_atlas.evidence_base.extract import extract as extract_module
from policy_atlas.evidence_base.group.facet_values import (
    FacetDirectiveError,
    parse_grouping_directive,
)
from policy_atlas.evidence_base.sourcing.search_loop import (
    SearchDirectiveError,
    parse_search_directive,
    validate_scope_filters,
)
from policy_atlas.runtime.orchestration_plan import (
    ANALYSIS_DEPTH_TABLE,
    EXTRACT_PROFILE_IDS,
    NAMED_PAIRINGS,
    TIME_BANDS,
    AnalysisDepth,
    ComposedChain,
    OrchestrationPlan,
    SearchEffort,
    SteeringMode,
    _enabled_components,
    compose,
)

PauseBoundary = Literal["after_component", "before_component"]
UnattendedAction = Literal["proceed_flag", "stop"]

PAUSE_SETS: dict[SteeringMode, tuple[str, ...]] = {
    "frequent": ("after_every_component",),
    "moderate": ("deepening_selection", "before_synthesise"),
    "minimal": ("deepening_selection",),
    "unattended": (),
}
DEEPENING_SELECTION_STEER_POINT = "deepening_selection"


@dataclass(frozen=True, order=True)
class PausePoint:
    """One deterministic component-boundary pause point.

    Args:
        boundary: Whether the pause occurs before or after a component.
        component: Composed component step name at the boundary.
    """

    boundary: PauseBoundary
    component: str


@dataclass(frozen=True)
class Continue:
    """Steering response that continues the run unchanged."""


@dataclass(frozen=True)
class Adjust:
    """Steering response that requests a bounded plan amendment.

    Args:
        directive_deltas: Component directive deltas keyed by not-yet-run
            composed component step name.
        new_mode: Optional replacement steering mode.
        nudge: Optional lighter/as-proposed/deeper run-depth nudge.
    """

    directive_deltas: dict[str, dict[str, Any]] = field(default_factory=dict)
    new_mode: str | None = None
    nudge: str | None = None


@dataclass(frozen=True)
class Abort:
    """Steering response that cleanly stops the remaining run walk."""


SteeringResponse = Continue | Adjust | Abort


class SteeringAdjustmentError(ValueError):
    """Raised when a steering adjustment cannot be represented safely.

    Args:
        message: Human-readable validation failure.
    """


def pause_points(mode: SteeringMode, chain: ComposedChain) -> set[PausePoint]:
    """Compile a steering mode into concrete pause boundaries for a chain.

    Args:
        mode: Steering mode from the approved orchestration plan.
        chain: Deterministically composed component chain.

    Returns:
        Concrete pause points present in ``chain``.
    """
    components = set(chain.components)
    rules = PAUSE_SETS[mode]
    points: set[PausePoint] = set()
    if "after_every_component" in rules:
        points.update(PausePoint("after_component", step.component) for step in chain.steps)
    if "deepening_selection" in rules and "select" in components:
        points.add(PausePoint("after_component", "select"))
    if "before_synthesise" in rules and "synthesise" in components:
        points.add(PausePoint("before_component", "synthesise"))
    return points


def render_check_in(step_outcome_payload: dict[str, Any]) -> str:
    """Render one runner check-in payload deterministically.

    Args:
        step_outcome_payload: Payload emitted through ``OrchestratorIO.check_in``.

    Returns:
        Human-readable, stable check-in text.
    """
    component = str(step_outcome_payload.get("component", "unknown"))
    status = str(step_outcome_payload.get("status", "unknown"))
    parts = [f"{component}: {status}"]
    wall_clock = step_outcome_payload.get("wall_clock_s")
    if isinstance(wall_clock, int | float) and not isinstance(wall_clock, bool):
        parts.append(f"wall_clock={wall_clock:.3f}s")
    headline_counts = step_outcome_payload.get("headline_counts")
    if isinstance(headline_counts, dict) and headline_counts:
        rendered_counts = ", ".join(
            f"{key}={_stable_value(headline_counts[key])}" for key in sorted(headline_counts)
        )
        parts.append(f"counts: {rendered_counts}")
    if step_outcome_payload.get("retried") is True:
        parts.append("retried=true")
    if step_outcome_payload.get("skipped") is True:
        parts.append("skipped=true")
    reason = step_outcome_payload.get("reason")
    if reason is not None:
        parts.append(f"reason={_stable_value(reason)}")
    return " | ".join(parts)


def render_collation(flagged_events: list[dict[str, Any]]) -> str:
    """Render end-of-run flagged-event collation deterministically.

    Args:
        flagged_events: Retry, failure, skip and auto-resolution flags collected
            by the runner.

    Returns:
        Human-readable grouped collation text.
    """
    groups: dict[str, list[dict[str, Any]]] = {
        "failures": [],
        "retries": [],
        "skips": [],
        "auto-resolutions": [],
    }
    for event in flagged_events:
        kind = _collation_kind(event)
        if kind in groups:
            groups[kind].append(event)

    lines = ["Flagged event collation"]
    for kind in ("failures", "retries", "skips", "auto-resolutions"):
        events = groups[kind]
        if not events:
            lines.append(f"{kind}: none")
            continue
        lines.append(f"{kind}:")
        for event in events:
            lines.append(f"- {_render_event(event)}")
    return "\n".join(lines)


def resolve_unattended(plan: OrchestrationPlan, point: str) -> str:
    """Resolve an Unattended-mode steer point from visible plan defaults.

    Args:
        plan: Approved orchestration plan.
        point: Steer-point name to resolve.

    Returns:
        ``"proceed_flag"`` or ``"stop"``. Missing defaults proceed with a
        visible unconfigured-default flag owned by the caller.
    """
    for rule in plan.steer_point_defaults:
        if rule.steer_point == point:
            return rule.action
    return "proceed_flag"


# Deepening-selection emphasis multipliers (plan-pinned, contract decision 6
# rev 2.5): weight_emphasis values MULTIPLY the default signal weights — select
# multiplies the defaults by these values and sums unnormalised (select.py:439,
# 568), there is no renormalisation — so 2.0 doubles the quality weight and 2.5
# lifts the screen-confidence weight to the closest as-built relevance proxy.
STRONGEST_QUALITY_MULTIPLIER = 2.0
RELEVANCE_CONFIDENCE_MULTIPLIER = 2.5

REFUSAL_MESSAGE_TEMPLATE = (
    "Steering intent {intent!r} is not yet expressible in the selection grammar. "
    "It has been recorded as a seam rather than silently approximated."
)


def steer_point_triggers(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    selection_run_id: uuid.UUID,
    plan: OrchestrationPlan,
) -> list[dict[str, Any]]:
    """Compute fired deepening-selection triggers from a persisted selection.

    Reads the persisted ``selection_result`` flags for ``selection_run_id`` and
    maps them to the pre-declared deepening-selection triggers. Select already
    computes ``large_stratum_excluded`` at ``LARGE_STRATUM_SHARE`` and the
    user-nomination conflicts against the plan-compiled nominations, so the flags
    are read here, never recomputed.

    Args:
        conn: Open read connection.
        project_id: Owning project.
        selection_run_id: Run id whose ``selection_result`` carries the rationale.
        plan: Approved orchestration plan (nomination source, read-only).

    Returns:
        Fired trigger dicts, each ``{"trigger": str, "detail": Any}``. Empty when
        no selection row exists for the run or when no trigger flag fired. The
        policy-unmeetable spec trigger is not applicable in v1 (no policy object).
    """
    # Nominations (priority_strata / must_include_ids) reach select as directive
    # keys compiled from the plan, so select already evaluated the user-nominated
    # conflicts into flags; the plan is accepted for symmetry but not re-read.
    del plan
    row = conn.execute(
        sa_select(selection_result.c.flags)
        .where(selection_result.c.project_id == project_id)
        .where(selection_result.c.run_id == selection_run_id)
    ).first()
    if row is None:
        return []
    raw_flags = row.flags
    flags = raw_flags if isinstance(raw_flags, dict) else {}
    triggers: list[dict[str, Any]] = []
    if "large_stratum_excluded" in flags:
        triggers.append(
            {"trigger": "excluded_large_stratum", "detail": flags["large_stratum_excluded"]}
        )
    nominated: dict[str, Any] = {}
    if "priority_stratum_excluded" in flags:
        nominated["priority_stratum_excluded"] = flags["priority_stratum_excluded"]
    if "must_include_conflict" in flags:
        nominated["must_include_conflict"] = flags["must_include_conflict"]
    if nominated:
        triggers.append({"trigger": "excluded_user_nominated", "detail": nominated})
    if "thin_base" in flags:
        triggers.append({"trigger": "thin_base", "detail": flags["thin_base"]})
    return triggers


def build_steer_point_options(
    *,
    plan: OrchestrationPlan,
    point: str,
) -> list[dict[str, Any]]:
    """Return the deepening-selection options in the user-intent vocabulary.

    Each option is data — id, the user intent it speaks, a label, an honest
    description and a ``delta`` template in the as-built selection grammar — for
    an IO layer (the CLI) to render later. The option set is **closed**: a
    free-text steering intent that maps to none of these must be answered with
    ``refuse_inexpressible`` and recorded as a seam, never approximated to the
    nearest option (contract "honest absence" discipline).

    Args:
        plan: Current orchestration plan (source of the current select budget).
        point: Steer-point name being rendered (unused; one steer point in v1).

    Returns:
        The five deepening-selection options with grammar-exact delta templates.
    """
    del point
    current_budget = ANALYSIS_DEPTH_TABLE[plan.analysis_depth]["selection_budget"]
    budget_default = (
        current_budget
        if current_budget is not None
        else select_module.DEFAULT_SELECTION_BUDGET
    )
    return [
        {
            "id": "deepen_clusters",
            "intent": "Deepen the named clusters",
            "label": "Deepen the clusters or documents I name",
            "description": (
                "Prioritise the themes you name and force-include the documents "
                "you name. Provide cluster and document ids to fill the template."
            ),
            "delta": {"selection": {"priority_strata": [], "must_include_ids": []}},
            "requires_user_input": True,
        },
        {
            "id": "strongest_evidence",
            "intent": "Just the strongest evidence",
            "label": "Favour the strongest-quality evidence",
            "description": (
                "Doubles the appraisal-quality weight in selection ranking "
                "(weight_emphasis quality x2.0 — a multiplier on the default weight)."
            ),
            "delta": {
                "selection": {"weight_emphasis": {"quality": STRONGEST_QUALITY_MULTIPLIER}}
            },
            "requires_user_input": False,
        },
        {
            "id": "most_relevant",
            "intent": "Most relevant to my question",
            "label": "Favour relevance to my question",
            "description": (
                "Lifts screen confidence as the closest as-built relevance proxy "
                "(weight_emphasis screen_confidence x2.5) — an honest proxy, not a "
                "true question-relevance signal."
            ),
            "delta": {
                "selection": {
                    "weight_emphasis": {"screen_confidence": RELEVANCE_CONFIDENCE_MULTIPLIER}
                }
            },
            "requires_user_input": False,
        },
        {
            "id": "adjust_budget",
            "intent": "Adjust the budget",
            "label": "Change how many documents are selected",
            "description": "Change the selection budget; provide the new document budget.",
            "delta": {"selection": {"budget": budget_default}},
            "requires_user_input": True,
        },
        {
            "id": "as_proposed",
            "intent": "As proposed",
            "label": "Continue with the current selection",
            "description": "Proceed with the current selection unchanged.",
            "delta": {},
            "requires_user_input": False,
        },
    ]


def refuse_inexpressible(intent_text: str) -> str:
    """Return the standard honest refusal for an inexpressible steering intent.

    The deepening-selection option set (``build_steer_point_options``) is closed.
    An IO layer that receives a free-text steering intent matching no option must
    answer with this message and record the seam — never silently approximate to
    the nearest expressible option.

    Args:
        intent_text: The user's free-text steering intent.

    Returns:
        The standard not-yet-expressible refusal message.
    """
    return REFUSAL_MESSAGE_TEMPLATE.format(intent=intent_text)


def apply_adjustment(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    plan_row: Any,
    plan: OrchestrationPlan,
    adjustment: Adjust,
    completed_components: set[str],
) -> tuple[OrchestrationPlan, uuid.UUID, int]:
    """Validate and persist a bounded steering adjustment as a new plan row.

    Args:
        conn: Open transaction used for the short plan-version write.
        project_id: Project owning the plan lineage.
        plan_row: Current persisted orchestration-plan row.
        plan: Current validated orchestration plan payload.
        adjustment: Requested steering adjustment.
        completed_components: Components whose boundary has already passed.

    Returns:
        The amended plan, new plan id and new plan version.

    Raises:
        SteeringAdjustmentError: If the adjustment names completed/unknown
            components, falls outside directive grammar, cannot map to plan
            fields, or would change an already-run component configuration.
    """
    current_chain = compose(plan)
    current_components = set(current_chain.components)
    _validate_delta_component_bounds(
        adjustment.directive_deltas,
        current_components=current_components,
        completed_components=completed_components,
    )

    payload = plan.model_dump(mode="json")
    try:
        _apply_mode(payload, adjustment.new_mode)
        _apply_nudge(payload, adjustment.nudge)
        for component, delta in adjustment.directive_deltas.items():
            _validate_directive_delta(component, delta, backend_scope=plan.backend_scope)
            _apply_component_delta_to_payload(payload, component=component, delta=delta)
        payload["expected_artefact_shape"] = ""
        payload["time_band"] = ""
        amended = OrchestrationPlan.model_validate(payload)
    except (ValidationError, ValueError, TypeError) as exc:
        raise SteeringAdjustmentError(str(exc)) from exc

    amended_chain = compose(amended)
    _validate_completed_component_stability(
        current_chain=current_chain,
        amended_chain=amended_chain,
        completed_components=completed_components,
    )
    _validate_delta_round_trip(adjustment.directive_deltas, amended_chain=amended_chain)

    new_plan_id, new_version = _persist_new_plan_version(
        conn,
        project_id=project_id,
        plan_row=plan_row,
        payload=amended.model_dump(mode="json"),
    )
    return amended, new_plan_id, new_version


def _persist_new_plan_version(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    plan_row: Any,
    payload: dict[str, Any],
) -> tuple[uuid.UUID, int]:
    """Supersede the current plan row and insert a user-attributed successor.

    Args:
        conn: Open transaction for the version-row write.
        project_id: Project owning the plan lineage.
        plan_row: Current persisted orchestration-plan row.
        payload: JSON payload for the new approved version row.

    Returns:
        The new plan id and new plan version.

    Raises:
        SteeringAdjustmentError: If the plan row lacks a UUID id or integer
            version.
    """
    prior_plan_id = _plan_row_value(plan_row, "plan_id")
    prior_version = _plan_row_value(plan_row, "version")
    evidence_scope_id = _plan_row_value(plan_row, "evidence_scope_id")
    if not isinstance(prior_plan_id, uuid.UUID):
        raise SteeringAdjustmentError("current plan row has no UUID plan_id")
    if not isinstance(prior_version, int):
        raise SteeringAdjustmentError("current plan row has no integer version")

    new_plan_id = uuid.uuid4()
    new_version = prior_version + 1
    now = datetime.now(UTC)
    conn.execute(
        orchestration_plan.update()
        .where(orchestration_plan.c.plan_id == prior_plan_id)
        .where(orchestration_plan.c.project_id == project_id)
        .values(status="superseded")
    )
    conn.execute(
        orchestration_plan.insert().values(
            plan_id=new_plan_id,
            project_id=project_id,
            evidence_scope_id=evidence_scope_id,
            version=new_version,
            status="approved",
            payload=payload,
            created_at=now,
            created_by="user",
            approved_at=now,
        )
    )
    return new_plan_id, new_version


def apply_reselect(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    plan_row: Any,
    plan: OrchestrationPlan,
    select_directive: dict[str, Any],
) -> tuple[uuid.UUID, int]:
    """Persist a user-attributed plan version row for a deepening-selection re-run.

    The deepening-selection steer point fires *after* ``select`` runs, so the
    generic completed-component adjustment path (``apply_adjustment``) cannot
    amend it — it treats ``select`` as already-run. This records the user's
    steering event as a new plan version row (the contract's "human substance
    enters honestly in provenance" rule). The fine select directive
    (``weight_emphasis`` / ``priority_strata`` / ``must_include_ids`` / a
    non-``analysis_depth`` ``budget``) is a **commit-layer** directive the task-2
    ``OrchestrationPlan`` model deliberately does not carry (decision 4 compiles
    only the selection *budget* via ``analysis_depth``); the runner applies it to
    the scope context and it is recorded faithfully in the re-run's
    ``selection_result`` provenance — never smuggled into the plan payload, which
    therefore carries forward unchanged.

    Args:
        conn: Open transaction for the version-row write.
        project_id: Project owning the plan lineage.
        plan_row: Current persisted orchestration-plan row.
        plan: Current validated orchestration plan (carried forward unchanged).
        select_directive: The merged select directive, validated fail-closed.

    Returns:
        The new plan id and new plan version.

    Raises:
        SteeringAdjustmentError: If the merged select directive is malformed or
            the plan row lacks a UUID id / integer version.
    """
    try:
        select_module._parse_directive(select_directive.get("selection"))
    except select_module.DirectiveError as exc:
        raise SteeringAdjustmentError(str(exc)) from exc

    return _persist_new_plan_version(
        conn,
        project_id=project_id,
        plan_row=plan_row,
        payload=plan.model_dump(mode="json"),
    )


def _stable_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _collation_kind(event: dict[str, Any]) -> str:
    status = event.get("status")
    if status == "failed":
        return "failures"
    if status in {"retrying", "retried"}:
        return "retries"
    if status == "skipped":
        return "skips"
    if status == "auto_resolved":
        return "auto-resolutions"
    return "other"


def _render_event(event: dict[str, Any]) -> str:
    return ", ".join(f"{key}={_stable_value(event[key])}" for key in sorted(event))


def _validate_delta_component_bounds(
    directive_deltas: dict[str, dict[str, Any]],
    *,
    current_components: set[str],
    completed_components: set[str],
) -> None:
    for component in directive_deltas:
        if component in completed_components:
            raise SteeringAdjustmentError(
                f"adjustment names already-run component {component!r}"
            )
        if component not in current_components:
            raise SteeringAdjustmentError(f"adjustment names unknown component {component!r}")


def _apply_mode(payload: dict[str, Any], new_mode: str | None) -> None:
    if new_mode is not None:
        payload["steering_mode"] = new_mode


def _apply_nudge(payload: dict[str, Any], nudge: str | None) -> None:
    if nudge is None or nudge in {"as_proposed", "as-proposed"}:
        return
    if nudge not in NAMED_PAIRINGS:
        raise SteeringAdjustmentError(
            "nudge must be 'lighter', 'as_proposed', 'as-proposed', 'standard', or 'deeper'"
        )
    search_effort, analysis_depth = NAMED_PAIRINGS[nudge]
    payload["search_effort"] = search_effort
    payload["analysis_depth"] = analysis_depth
    _clip_components_to_depth(payload, analysis_depth=analysis_depth)
    payload["time_band"] = TIME_BANDS[(search_effort, analysis_depth)]


def _clip_components_to_depth(payload: dict[str, Any], *, analysis_depth: AnalysisDepth) -> None:
    enabled = _enabled_components(analysis_depth)
    payload["components"] = [
        component for component in payload.get("components", []) if component in enabled
    ]
    if "group" not in payload["components"]:
        payload["grouping_facets"] = None


def _validate_directive_delta(
    component: str,
    delta: dict[str, Any],
    *,
    backend_scope: str,
) -> None:
    if not delta:
        return
    if component == "acquire":
        _require_keys(component, delta, {"search"})
        try:
            _, raw_filters, _, _ = parse_search_directive({"search": delta["search"]})
            validate_scope_filters(raw_filters, backend_names=_backend_names(backend_scope))
        except SearchDirectiveError as exc:
            raise SteeringAdjustmentError(str(exc)) from exc
        return
    if component in {"screen_abstract", "screen_full"}:
        _require_keys(component, delta, {"screening"})
        screen_module._parse_screen_directive({"screening": delta["screening"]})
        return
    if component == "select":
        _require_keys(component, delta, {"selection"})
        try:
            select_module._parse_directive(delta["selection"])
        except select_module.DirectiveError as exc:
            raise SteeringAdjustmentError(str(exc)) from exc
        return
    if component == "extract":
        _require_keys(component, delta, {"extraction"})
        try:
            extract_module._parse_extraction_directive(delta["extraction"])
        except extract_module.ExtractError as exc:
            raise SteeringAdjustmentError(str(exc)) from exc
        return
    if component == "group":
        _require_keys(component, delta, {"grouping"})
        try:
            parse_grouping_directive({"grouping": delta["grouping"]})
        except FacetDirectiveError as exc:
            raise SteeringAdjustmentError(str(exc)) from exc
        return
    if component == "appraise":
        _require_keys(component, delta, {"appraisal"})
        try:
            appraise_module._parse_appraisal_directive(delta["appraisal"])
        except appraise_module.AppraiseDirectiveError as exc:
            raise SteeringAdjustmentError(str(exc)) from exc
        return
    if component == "characterise":
        _require_keys(component, delta, {"characterise"})
        try:
            characterise_module._parse_characterise_directive(delta["characterise"])
        except characterise_module.CharacteriseDirectiveError as exc:
            raise SteeringAdjustmentError(str(exc)) from exc
        return
    raise SteeringAdjustmentError(f"component {component!r} has no steering directive grammar")


def _backend_names(backend_scope: str) -> list[str]:
    if backend_scope == "academic_only":
        return ["openalex"]
    if backend_scope == "grey_lit_only":
        return ["overton"]
    return ["openalex", "overton"]


def _require_keys(component: str, delta: dict[str, Any], keys: set[str]) -> None:
    if set(delta) != keys:
        raise SteeringAdjustmentError(
            f"{component!r} directive delta must contain exactly {sorted(keys)!r}"
        )


def _apply_component_delta_to_payload(
    payload: dict[str, Any],
    *,
    component: str,
    delta: dict[str, Any],
) -> None:
    if not delta:
        return
    if component == "acquire":
        _apply_acquire_delta(payload, delta["search"])
    elif component in {"screen_abstract", "screen_full"}:
        _apply_screen_delta(payload, component=component, screening=delta["screening"])
    elif component == "select":
        _apply_select_delta(payload, delta["selection"])
    elif component == "extract":
        _apply_extract_delta(payload, delta["extraction"])
    elif component == "group":
        # D8's granularity and B3's guidance are commit-layer directives with
        # no OrchestrationPlan field (the appraisal-rubric precedent): only
        # facets round-trip through the plan payload; granularity and guidance
        # are discarded here and exempted below.
        facets, _facet_source, _granularity, _guidance = parse_grouping_directive(
            {"grouping": delta["grouping"]}
        )
        payload["grouping_facets"] = facets
    elif component == "appraise":
        # D1's appraisal rubric override is a commit-layer directive with no
        # OrchestrationPlan field (apply_reselect's fine select directive is
        # the same precedent, documented on its docstring): there is nothing
        # to write into the plan payload, so the amended payload carries
        # appraisal forward unchanged, same as an untouched component.
        pass
    elif component == "characterise":
        # B5/D9's characterise directive (themes bound + guidance) is a
        # commit-layer directive with no OrchestrationPlan field (same
        # precedent as appraise): nothing to write into the plan payload;
        # characterise carries forward unchanged.
        pass


def _apply_acquire_delta(payload: dict[str, Any], search: Any) -> None:
    if not isinstance(search, dict):
        raise SteeringAdjustmentError("acquire search directive must be an object")
    depth = search.get("depth")
    if depth is not None:
        payload["search_effort"] = cast(SearchEffort, depth)
    if "filters" in search:
        payload["scope_constraints"] = _scope_constraints_from_filters(search["filters"])


def _scope_constraints_from_filters(filters: Any) -> dict[str, str]:
    if not isinstance(filters, dict):
        raise SteeringAdjustmentError("search filters must be an object")
    allowed_top = {"shared", "overton"}
    if set(filters) - allowed_top:
        raise SteeringAdjustmentError("search filters do not map to plan scope_constraints")
    constraints: dict[str, str] = {}
    shared = filters.get("shared", {})
    if not isinstance(shared, dict):
        raise SteeringAdjustmentError("shared search filters must be an object")
    for key in ("published_after", "published_before"):
        if key in shared:
            value = shared[key]
            if not isinstance(value, str):
                raise SteeringAdjustmentError(f"{key} must be a string")
            constraints[key] = value
    if set(shared) - {"published_after", "published_before"}:
        raise SteeringAdjustmentError("shared filters do not map to plan scope_constraints")
    overton = filters.get("overton", {})
    if not isinstance(overton, dict):
        raise SteeringAdjustmentError("overton search filters must be an object")
    if "publisher_country" in overton:
        value = overton["publisher_country"]
        if not isinstance(value, str):
            raise SteeringAdjustmentError("publisher_country must be a string")
        constraints["publisher_country"] = value
    if set(overton) - {"publisher_country"}:
        raise SteeringAdjustmentError("overton filters do not map to plan scope_constraints")
    return constraints


def _apply_screen_delta(
    payload: dict[str, Any],
    *,
    component: str,
    screening: Any,
) -> None:
    if not isinstance(screening, dict):
        raise SteeringAdjustmentError("screening directive must be an object")
    stage = screening.get("stage")
    expected_stage = 2 if component == "screen_full" else 1
    if stage is not None and stage != expected_stage:
        raise SteeringAdjustmentError(
            f"{component!r} cannot map screening stage {stage!r} to the plan"
        )
    if "criteria" in screening:
        criteria = screening["criteria"]
        if not isinstance(criteria, list):
            raise SteeringAdjustmentError("screening criteria must be a list")
        payload["screening_criteria"] = list(criteria)


def _apply_select_delta(payload: dict[str, Any], selection: Any) -> None:
    if not isinstance(selection, dict):
        raise SteeringAdjustmentError("selection directive must be an object")
    mappable_keys = {"budget"}
    if set(selection) - mappable_keys:
        raise SteeringAdjustmentError("selection directive is not yet mappable to plan fields")
    if "budget" not in selection:
        return
    budget = selection["budget"]
    for depth, settings in ANALYSIS_DEPTH_TABLE.items():
        if settings["selection_budget"] == budget:
            payload["analysis_depth"] = depth
            payload["time_band"] = TIME_BANDS[(payload["search_effort"], depth)]
            _clip_components_to_depth(payload, analysis_depth=depth)
            return
    raise SteeringAdjustmentError("selection budget does not map to a plan analysis_depth")


def _apply_extract_delta(payload: dict[str, Any], extraction: Any) -> None:
    # D3's refresh is a commit-layer directive with no OrchestrationPlan field
    # (the appraisal-rubric precedent): only profiles round-trip through the
    # plan payload; refresh is discarded here and exempted in the round-trip
    # check below.
    try:
        profiles, _refresh = extract_module._parse_extraction_directive(extraction)
    except extract_module.ExtractError as exc:
        raise SteeringAdjustmentError(str(exc)) from exc
    by_profile_id = {profile_id: profile for profile, profile_id in EXTRACT_PROFILE_IDS.items()}
    payload["extract_profiles"] = [by_profile_id[profile_id] for profile_id in profiles]


def _validate_completed_component_stability(
    *,
    current_chain: ComposedChain,
    amended_chain: ComposedChain,
    completed_components: set[str],
) -> None:
    current_by_component = {step.component: step.directive_delta for step in current_chain.steps}
    amended_by_component = {step.component: step.directive_delta for step in amended_chain.steps}
    for component in sorted(completed_components):
        if component not in amended_by_component:
            raise SteeringAdjustmentError(
                f"adjustment would remove already-run component {component!r}"
            )
        if current_by_component.get(component) != amended_by_component[component]:
            raise SteeringAdjustmentError(
                f"adjustment would change already-run component {component!r}"
            )


def _validate_delta_round_trip(
    directive_deltas: dict[str, dict[str, Any]],
    *,
    amended_chain: ComposedChain,
) -> None:
    amended_by_component = {step.component: step.directive_delta for step in amended_chain.steps}
    for component, requested_delta in directive_deltas.items():
        # D1/B5/D9: appraise's appraisal-rubric delta and characterise's
        # themes/guidance delta are commit-layer directives with no
        # OrchestrationPlan field by design (same exemption as
        # apply_reselect's fine select directive, which never re-enters this
        # generic round-trip path at all) — there is no plan field for either
        # to round-trip through, so both are exempted rather than failed closed.
        if component in {"appraise", "characterise"}:
            continue
        # compose() always injects sibling keys the caller need not supply
        # (e.g. acquire's "depth", screen_full's "stage"), so the recompiled
        # delta is checked to *contain* the request, not to equal it — a
        # requested value the plan fields cannot express still fails closed.
        if component == "extract" and requested_delta:
            try:
                requested_profiles, _requested_refresh = (
                    extract_module._parse_extraction_directive(
                        requested_delta.get("extraction")
                    )
                )
            except extract_module.ExtractError as exc:
                raise SteeringAdjustmentError(str(exc)) from exc
            actual = amended_by_component.get(component)
            actual_extraction = actual.get("extraction") if isinstance(actual, dict) else None
            actual_profiles = (
                actual_extraction.get("profiles")
                if isinstance(actual_extraction, dict)
                else None
            )
            if tuple(actual_profiles or ()) == requested_profiles:
                continue
            raise SteeringAdjustmentError(
                f"adjustment for {component!r} cannot round-trip through plan fields"
            )
        if requested_delta and not _delta_contains(
            amended_by_component.get(component), requested_delta
        ):
            raise SteeringAdjustmentError(
                f"adjustment for {component!r} cannot round-trip through plan fields"
            )


def _delta_contains(actual: Any, requested: Any) -> bool:
    if isinstance(requested, dict):
        if not isinstance(actual, dict):
            return False
        return all(_delta_contains(actual.get(key), value) for key, value in requested.items())
    return bool(actual == requested)


def _plan_row_value(plan_row: Any, key: str) -> Any:
    mapping = getattr(plan_row, "_mapping", None)
    if mapping is not None and key in mapping:
        return mapping[key]
    return getattr(plan_row, key)
