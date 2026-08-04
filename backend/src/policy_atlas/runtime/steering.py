"""Deterministic steering primitives for orchestration-plan runs.

This module owns the task-017 structural steering core: pause-boundary
compilation, deterministic human-readable renders, bounded adjustment
validation/persistence and Unattended-mode default resolution. It deliberately
contains no prompt surface.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, cast

from pydantic import ValidationError
from sqlalchemy import select as sa_select
from sqlalchemy.engine import Connection

from policy_atlas.core.prompt_fields import scrub_nul
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
from policy_atlas.evidence_base.synthesis.synthesis_tools import (
    SynthesisDirectiveError,
    parse_synthesis_directive,
)
from policy_atlas.runtime.orchestration_plan import (
    ANALYSIS_DEPTH_TABLE,
    EXTRACT_PROFILE_IDS,
    NAMED_PAIRINGS,
    AnalysisDepth,
    ComposedChain,
    OrchestrationPlan,
    SearchEffort,
    SteeringMode,
    _enabled_components,
    compose,
    time_band_for,
)
from policy_atlas.runtime.orchestrator_prompt import RouterCompileWire

PauseBoundary = Literal["after_component", "before_component"]
UnattendedAction = Literal["proceed_flag", "stop"]

# Commit-layer components (task 024, 15c): their directive validates through
# ``_validate_directive_delta`` but has NO OrchestrationPlan field to round-trip
# through (appraise's rubric, characterise's themes/guidance, synthesise's
# sections/boosts). A pending adjustment for one of these is recorded on the plan
# version but reaches the component's run through the runner's PENDING OVERLAY,
# not the plan payload. This is the single source of truth the round-trip
# exemption and the overlay both read.
COMMIT_LAYER_COMPONENTS: frozenset[str] = frozenset({"appraise", "characterise", "synthesise"})

# Mixed-grammar components (task 024, 15d): part of the directive maps to a plan
# field (extract ``profiles`` -> ``extract_profiles``; group ``facets`` ->
# ``grouping_facets``; select ``budget`` -> ``analysis_depth``) and part is
# commit-layer with NO plan field (extract ``refresh`` (D3) +
# ``relevance_emphasis`` (the B2' entry point); group ``granularity`` +
# ``guidance``; select's D6 ``strata_scope`` / D7 ``exclude_ids`` and the rest of
# its rich grammar). A pending adjustment SPLITS: the plan-mappable part takes the
# plan path, the commit-layer remainder folds into the overlay so it reaches the
# component's executed directive at its run (FIX 3b — closes the P2 pending-select
# compile/apply gap).
_MIXED_COMMIT_LAYER_KEYS: dict[str, tuple[str, frozenset[str]]] = {
    "extract": ("extraction", frozenset({"refresh", "relevance_emphasis"})),
    "group": ("grouping", frozenset({"granularity", "guidance"})),
    "select": (
        "selection",
        frozenset(
            {
                "must_include_ids",
                "boosts",
                "weight_emphasis",
                "priority_strata",
                "strata_scope",
                "exclude_ids",
            }
        ),
    ),
}


def deep_merge_delta(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge ``overlay`` over ``base`` — overlay wins per leaf key.

    Nested objects merge recursively; a non-dict overlay value (list, scalar)
    replaces the base value wholesale. Used to fold a pending overlay into a
    component's composed directive at execution time (task 024, 15c).

    Args:
        base: The component's composed directive delta.
        overlay: The pending overlay directive to merge over it.

    Returns:
        A new merged dict (inputs are not mutated).
    """
    merged = dict(base)
    for key, value in overlay.items():
        existing = merged.get(key)
        if isinstance(value, dict) and isinstance(existing, dict):
            merged[key] = deep_merge_delta(existing, value)
        else:
            merged[key] = value
    return merged


def commit_layer_overlay(component: str, delta: dict[str, Any]) -> dict[str, Any] | None:
    """Return the commit-layer part of a pending delta to fold into the overlay.

    A pure commit-layer component (:data:`COMMIT_LAYER_COMPONENTS`) overlays its
    whole delta. A mixed-grammar component (extract / group) overlays ONLY its
    commit-layer keys — the plan-mappable part (extract profiles, group facets)
    takes the plan path (task 024, 15d). Returns ``None`` when there is nothing to
    overlay.

    Args:
        component: The pending component the delta targets.
        delta: The component's directive delta (its own grammar).

    Returns:
        The commit-layer sub-delta to overlay, or ``None``.
    """
    if not delta:
        return None
    if component in COMMIT_LAYER_COMPONENTS:
        return delta
    spec = _MIXED_COMMIT_LAYER_KEYS.get(component)
    if spec is None:
        return None
    context_key, keys = spec
    inner = delta.get(context_key)
    if not isinstance(inner, dict):
        return None
    part = {key: value for key, value in inner.items() if key in keys}
    return {context_key: part} if part else None


# --- The steer-point lattice (task 024 decision 5) -------------------------
#
# Four named steer points at fixed component boundaries:
#   acquire ─P1─> ... ─P2─> select ─P3─> ... ─P4─> synthesise
# P1 after acquire (exception point) · P2 before select (the coverage /
# "evidence base" point) · P3 after select (deepening selection, the existing
# point) · P4 before synthesise (the synthesis-shape point).
SEARCH_REVIEW = "search_review"
# Compatibility alias for callers compiled before the owner-ruled rename.
SEARCH_EXCEPTION = SEARCH_REVIEW
EVIDENCE_BASE_COVERAGE = "evidence_base_coverage"
DEEPENING_SELECTION = "deepening_selection"
FINDING_GROUPS = "finding_groups"
SYNTHESIS_SHAPE = "synthesis_shape"

# Retained for callers/tests that name the existing P3 point directly.
DEEPENING_SELECTION_STEER_POINT = DEEPENING_SELECTION

# Per-point per-mode policy — the annex mode table:
#   "always" pauses whenever the point is present in the chain; "fired" pauses
#   only when that point's floor triggers fire (read at the boundary through
#   Task 10 readers, never recomputed); "off" never pauses. Frequent adds a
#   generic-floor pause at every OTHER (non-lattice) component boundary.
LatticePolicy = Literal["always", "fired", "off"]
_LATTICE_MODE_POLICY: dict[SteeringMode, dict[str, LatticePolicy]] = {
    "frequent": {
        SEARCH_REVIEW: "always",
        EVIDENCE_BASE_COVERAGE: "always",
        DEEPENING_SELECTION: "always",
        FINDING_GROUPS: "always",
        SYNTHESIS_SHAPE: "always",
    },
    "moderate": {
        SEARCH_REVIEW: "always",
        EVIDENCE_BASE_COVERAGE: "fired",
        DEEPENING_SELECTION: "fired",
        FINDING_GROUPS: "fired",
        SYNTHESIS_SHAPE: "always",
    },
    "minimal": {
        SEARCH_REVIEW: "fired",
        EVIDENCE_BASE_COVERAGE: "fired",
        DEEPENING_SELECTION: "fired",
        FINDING_GROUPS: "fired",
        SYNTHESIS_SHAPE: "fired",
    },
    "unattended": {
        SEARCH_REVIEW: "off",
        EVIDENCE_BASE_COVERAGE: "off",
        DEEPENING_SELECTION: "off",
        FINDING_GROUPS: "off",
        SYNTHESIS_SHAPE: "off",
    },
}


@dataclass(frozen=True, order=True)
class PausePoint:
    """One deterministic component-boundary pause point.

    Args:
        boundary: Whether the pause occurs before or after a component.
        component: Composed component step name at the boundary.
    """

    boundary: PauseBoundary
    component: str


# Canonical boundary for each lattice point. P2/P4 are before-boundaries; P1/P3
# are after-boundaries. Defined after PausePoint (it constructs them).
LATTICE_POINTS: dict[str, PausePoint] = {
    SEARCH_REVIEW: PausePoint("after_component", "acquire"),
    EVIDENCE_BASE_COVERAGE: PausePoint("before_component", "select"),
    DEEPENING_SELECTION: PausePoint("after_component", "select"),
    FINDING_GROUPS: PausePoint("after_component", "group"),
    SYNTHESIS_SHAPE: PausePoint("before_component", "synthesise"),
}
_LATTICE_BY_POINT: dict[PausePoint, str] = {point: name for name, point in LATTICE_POINTS.items()}


def lattice_name_for(point: PausePoint) -> str | None:
    """Return the lattice point name for a boundary, or ``None`` if not one.

    Args:
        point: A concrete component boundary.

    Returns:
        The steer-point name (``search_exception``/``evidence_base_coverage``/
        ``deepening_selection``/``synthesis_shape``) or ``None`` when the
        boundary is not a lattice point.
    """
    return _LATTICE_BY_POINT.get(point)


def lattice_policy(mode: SteeringMode, name: str) -> LatticePolicy:
    """Return the pause policy for a lattice point under a mode.

    Args:
        mode: Steering mode from the approved plan.
        name: Lattice point name.

    Returns:
        ``"always"``, ``"fired"`` or ``"off"``.
    """
    return _LATTICE_MODE_POLICY[mode].get(name, "off")


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
    # Authorship of the delta's CONTENT (steering discipline iv): "orchestrator"
    # when the user picked a watch-authored option — the user decided, the
    # orchestrator authored. None ≡ user-authored.
    authored_by: str | None = None


@dataclass(frozen=True)
class Abort:
    """Steering response that cleanly stops the remaining run walk."""


# The only shipped additive-re-entry segment this slice (contract decision 7a):
# the walk jumps back to acquire and re-walks forward. Any other start component
# fails closed ("segment not shipped").
SHIPPED_SEGMENT_START = "acquire"


@dataclass(frozen=True)
class ReEnterSegment:
    """Additive segment re-entry (contract decision 7a) — a bounded re-walk.

    At an ``after_component`` boundary the walk jumps BACK to ``segment_start``
    with an amended directive, re-walks forward through every already-completed
    component up to the boundary (in chain order), then re-enters the SAME
    boundary once to show updated state. Incremental by construction: the
    re-walked components run with their normal directives plus the amendment,
    and each component's own memo/skip logic (acquire dedups; screen/classify/
    appraise skip already-processed docs) means NOTHING already processed is
    reprocessed. One re-entry cycle per boundary (the one-adjustment rule
    generalised).

    Args:
        segment_start: Component the segment restarts from. Only
            :data:`SHIPPED_SEGMENT_START` (``"acquire"``) is a shipped segment
            this slice; anything else fails closed.
        directive_deltas: The amendment — per-component directive deltas keyed
            by component (typically ``{"acquire": {"search": {"guidance":
            [...]}}}``), each validated fail-closed through the component's own
            parser.
    """

    segment_start: str = SHIPPED_SEGMENT_START
    directive_deltas: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class FreeText:
    """Free-text steering prose typed at a pause (task 024, decision 3 — the router).

    Returned by a pause-capable IO layer (the CLI, Task 17) when the user typed
    prose rather than picking a canonical option. The runner compiles it through
    the orchestrator ``route`` backend into a deterministically-validated fan-out
    of bounded directive deltas, renders that fan-out for confirmation, and
    applies only what the user confirms. ``NullIO`` never returns it.

    Args:
        text: The user's verbatim free-text steering prose.
    """

    text: str


SteeringResponse = Continue | Adjust | Abort | ReEnterSegment | FreeText


class SteeringAdjustmentError(ValueError):
    """Raised when a steering adjustment cannot be represented safely.

    Args:
        message: Human-readable validation failure.
    """


class SteeringDeltaInvalid(SteeringAdjustmentError):
    """A proposed steering delta is invalid for this pause surface."""


@dataclass(frozen=True)
class SteeringValidationCtx:
    """The full state that makes a steering delta valid at one pause."""

    backend_scope: str
    current_components: set[str]
    completed_components: set[str]
    rerun_surface: RerunSurface


@dataclass(frozen=True)
class ValidatedDelta:
    """A delta accepted by the shared author-blind validator."""

    component: str
    delta: dict[str, Any]


def validate_steering_delta(
    delta: Mapping[str, Any], component: str, ctx: SteeringValidationCtx
) -> ValidatedDelta:
    """Validate one author-blind delta for its current steering surface.

    Args:
        delta: Component-local directive delta.
        component: Component the delta targets.
        ctx: Current run scope and pause affordances.

    Returns:
        The validated, copied delta.

    Raises:
        SteeringDeltaInvalid: If the delta is malformed or unavailable here.
    """
    if component not in ctx.current_components:
        raise SteeringDeltaInvalid(f"component {component!r} is not in the plan")
    if (
        component in ctx.completed_components
        and component != ctx.rerun_surface.replacement_component
    ):
        raise SteeringDeltaInvalid(
            f"component {component!r} has already run and cannot be adjusted"
        )
    if not isinstance(delta, Mapping):
        raise SteeringDeltaInvalid("delta must be an object")
    copied = dict(delta)
    try:
        _validate_directive_delta(component, copied, backend_scope=ctx.backend_scope)
    except SteeringAdjustmentError as exc:
        raise SteeringDeltaInvalid(str(exc)) from exc
    return ValidatedDelta(component=component, delta=copied)


def pause_points(mode: SteeringMode, chain: ComposedChain) -> set[PausePoint]:
    """Compile a steering mode into the *always-pause* boundaries for a chain.

    This is the static pause set — the boundaries that pause unconditionally in
    ``mode``. ``"fired"`` lattice points are deliberately NOT here: the runner
    evaluates their floor triggers at the boundary (Task 10 readers) and pauses
    only when a trigger fired, so a static set cannot express them.

    Frequent pauses after every component (the pre-024 behaviour), enriching the
    after-boundary lattice points (P1 after acquire, P3 after select), PLUS the
    before-boundary lattice points P2 (before select) and P4 (before synthesise)
    as additional enriched pauses — "walk me through everything" keeps the
    per-component check-in and adds the coverage / synthesis-shape decision points.

    Moderate/Minimal contribute only their ``always`` lattice points (Moderate:
    P2/P3/P4; Minimal: none — all four are fired-only). Unattended is empty.

    Args:
        mode: Steering mode from the approved orchestration plan.
        chain: Deterministically composed component chain.

    Returns:
        The always-pause points present in ``chain``.
    """
    component_set = set(chain.components)
    points: set[PausePoint] = set()

    if mode == "frequent":
        points.update(PausePoint("after_component", component) for component in component_set)

    for name, point in LATTICE_POINTS.items():
        if lattice_policy(mode, name) != "always":
            continue
        if point.component in component_set:
            points.add(point)
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
        # Loudest-flag ordering (Unattended (c), ADR 0021 decision 4): auto-
        # resolutions with rule="unconfigured_default" (no pinned rule decided —
        # the loudest flag class) are reviewed FIRST; a stable sort keeps the
        # relative order otherwise unchanged.
        ordered = events
        if kind == "auto-resolutions":
            ordered = sorted(
                events,
                key=lambda event: 0 if event.get("rule") == "unconfigured_default" else 1,
            )
        for event in ordered:
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

# Placeholder tokens for requires_user_input option templates: the template must
# itself compile through its grammar (guidance/criteria/strata channels reject
# empty), so a bounded non-empty placeholder stands in until the router/CLI fills
# it. Never applied unconfirmed.
_GUIDANCE_PLACEHOLDER = "Describe what to prioritise"
_CRITERIA_PLACEHOLDER = "Describe the new inclusion criterion"
_STRATUM_PLACEHOLDER = "theme or stratum name"

# The unfilled-template sentinels: a standing rule whose delta still carries one
# of these has NOT supplied the user input its option needs (fail closed).
_OPTION_PLACEHOLDERS: frozenset[str] = frozenset(
    {_GUIDANCE_PLACEHOLDER, _CRITERIA_PLACEHOLDER, _STRATUM_PLACEHOLDER}
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
    plan: OrchestrationPlan | None,
    point: str,
) -> list[dict[str, Any]]:
    """Return the canonical floor options for a lattice point, in intent vocabulary.

    Each option is data — id, the user intent it speaks, a label, an honest
    description, a ``delta`` template that compiles through an EXISTING grammar
    (no new keys), and ``requires_user_input``. The per-point set is the closed
    **deterministic floor** the watch/router build on and ``steer_point_defaults``
    rules anchor (steerability-refinement "Orchestrator-authored options"). A
    free-text intent matching none of them is answered with
    ``refuse_inexpressible`` and recorded as a seam, never approximated.

    Args:
        plan: Current orchestration plan (source of the current select budget), or
            ``None`` when only the option vocabulary is needed (plan-validation
            time): P3's budget-adjust template then falls back to
            ``DEFAULT_SELECTION_BUDGET`` — the ids and grammar are plan-independent.
        point: Lattice point name — one of ``search_exception``,
            ``evidence_base_coverage``, ``deepening_selection``,
            ``synthesis_shape``.

    Returns:
        The point's canonical options with grammar-exact delta templates.

    Raises:
        ValueError: If ``point`` is not a known lattice point.
    """
    if point == SEARCH_REVIEW:
        return _p1_options()
    if point == EVIDENCE_BASE_COVERAGE:
        return _p2_options()
    if point == DEEPENING_SELECTION:
        return _p3_options(plan)
    if point == FINDING_GROUPS:
        return _groups_options()
    if point == SYNTHESIS_SHAPE:
        return _p4_options()
    raise ValueError(f"unknown steer point: {point!r}")


def generic_floor_options() -> list[dict[str, Any]]:
    """Return the generic non-lattice floor (finding M6).

    At a Frequent-mode boundary that is not a lattice point the canonical menu is
    continue · change mode · abort — always present, the degrade target for a
    watch/authoring failure there. Free text arrives with the Phase-5 router; it
    is not an option id.

    Returns:
        The three generic-floor options.
    """
    return [
        {
            "id": "continue",
            "intent": "Continue",
            "label": "Continue the run",
            "description": "Proceed to the next component unchanged.",
            "delta": {},
            "requires_user_input": False,
        },
        {
            "id": "change_mode",
            "intent": "Change how often I am asked",
            "label": "Change the steering mode",
            "description": (
                "Change how often the run pauses for you; provide the new mode "
                "(frequent / moderate / minimal / unattended)."
            ),
            "delta": {},
            "requires_user_input": True,
        },
        {
            "id": "abort",
            "intent": "Stop the run",
            "label": "Stop the run here",
            "description": "Abort the remaining walk; prior component work is preserved.",
            "delta": {},
            "requires_user_input": False,
        },
    ]


def _p1_options() -> list[dict[str, Any]]:
    """P1 search-review floor (after acquire)."""
    return [
        {
            "id": "continue",
            "intent": "Looks right — assess these",
            "label": "Looks right — assess these",
            "description": "Screening starts on what came back.",
            "delta": {},
            "requires_user_input": False,
        },
        {
            "id": "deepen_search",
            "intent": "Search harder",
            "label": "Search deeper",
            "description": (
                "Widens and deepens the search across the same databases; new results are added."
            ),
            "delta": {"acquire": {"search": {"depth": "deep"}}},
            "requires_user_input": False,
        },
        {
            "id": "rescope_filters",
            "intent": "Change the search scope",
            "label": "Change the search scope",
            "description": "Set new date or geography limits; the search re-runs.",
            "delta": {
                "acquire": {"search": {"filters": {"shared": {"published_after": "2015-01-01"}}}}
            },
            "requires_user_input": True,
        },
        {
            "id": "guide_queries",
            "intent": "Guide the queries",
            "label": "Guide the queries",
            "description": "Describe what to look for; new results are added to what came back.",
            "delta": {"acquire": {"search": {"guidance": [_GUIDANCE_PLACEHOLDER]}}},
            "requires_user_input": True,
        },
        {
            "id": "abort",
            "intent": "Stop the run",
            "label": "Stop the run",
            "description": "Abort the remaining walk; prior component work is preserved.",
            "delta": {},
            "requires_user_input": False,
        },
    ]


def _p2_options() -> list[dict[str, Any]]:
    """P2 evidence_base_coverage floor (before select).

    ``search_more`` is ADDITIVE (segment re-entry back to acquire); the criteria
    re-screen and re-characterise are REPLACEMENT re-runs (contract decision 7):
    the criteria re-screen supersedes screen rows at document grain via the
    generation mechanism (Task 9), even though the walk mechanics are an
    acquire→assess re-walk. NOTE: a stage-2 toggle is deliberately OMITTED — the
    plan grammar cannot express enabling ``screen_full`` mid-run as a directive
    delta (it is a chain-composition change, not a component directive), so the
    honest floor omits it rather than approximate it.
    """
    return [
        {
            "id": "continue",
            "intent": "The evidence base looks right",
            "label": "Looks right — go on to choose the reading list",
            "description": "Nothing changes; the run continues.",
            "delta": {},
            "requires_user_input": False,
        },
        {
            "id": "search_more",
            "intent": "Search more on a subtopic",
            "label": "Search for more on a subtopic",
            "description": (
                "You say what to look for; new documents are added — nothing already "
                "assessed is redone."
            ),
            "delta": {"acquire": {"search": {"guidance": [_GUIDANCE_PLACEHOLDER]}}},
            "requires_user_input": True,
        },
        {
            "id": "adjust_criteria_rescreen",
            "intent": "Change the screening criteria and re-screen",
            "label": "Change the inclusion criteria and re-assess",
            "description": (
                "You set new criteria; every document is re-assessed against them, "
                "replacing today's decisions."
            ),
            "delta": {
                "screen_abstract": {
                    "screening": {"criteria": [_CRITERIA_PLACEHOLDER], "rescreen": True}
                }
            },
            "requires_user_input": True,
        },
        {
            "id": "recharacterise",
            "intent": "Re-map the themes",
            "label": "Re-map the themes",
            "description": (
                "Regenerate the theme map — plain regenerate, or guided by your "
                "instructions. The current map is replaced."
            ),
            "delta": {
                "characterise": {
                    "characterise": {"themes": "standard", "guidance": [_GUIDANCE_PLACEHOLDER]}
                }
            },
            "requires_user_input": True,
        },
        {
            "id": "scope_strata",
            "intent": "Keep only named themes",
            "label": "Keep only the themes I name",
            "description": "Name the themes; only their documents go forward to reading.",
            "delta": {"select": {"selection": {"strata_scope": {"only": [_STRATUM_PLACEHOLDER]}}}},
            "requires_user_input": True,
        },
        {
            "id": "exclude_docs",
            "intent": "Leave out named documents",
            "label": "Leave out documents I name",
            "description": "Name documents to exclude from everything that follows.",
            "delta": {"select": {"selection": {"exclude_ids": []}}},
            "requires_user_input": True,
        },
    ]


def _p3_options(plan: OrchestrationPlan | None) -> list[dict[str, Any]]:
    """P3 reading-list floor (after select)."""
    current_budget = (
        ANALYSIS_DEPTH_TABLE[plan.analysis_depth]["selection_budget"] if plan is not None else None
    )
    budget_default = (
        current_budget if current_budget is not None else select_module.DEFAULT_SELECTION_BUDGET
    )
    return [
        {
            "id": "deepen_clusters",
            "intent": "Make sure these are read",
            "label": "Make sure these are read",
            "description": (
                "Name themes or documents that must be on the list; it is re-picked around them."
            ),
            "delta": {"selection": {"priority_strata": [], "must_include_ids": []}},
            "requires_user_input": True,
        },
        {
            "id": "strongest_evidence",
            "intent": "Just the strongest evidence",
            "label": "Prefer the strongest evidence",
            "description": (
                "Re-picks the list, weighting study quality more heavily. Replaces this list."
            ),
            "delta": {"selection": {"weight_emphasis": {"quality": STRONGEST_QUALITY_MULTIPLIER}}},
            "requires_user_input": False,
        },
        {
            "id": "most_relevant",
            "intent": "Most relevant to my question",
            "label": "Prefer the most relevant",
            "description": (
                "Re-picks the list using how directly each document meets your question. "
                "Replaces this list."
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
            "label": "Read more (or fewer) documents",
            "description": "Set the number; the list is re-picked.",
            "delta": {"selection": {"budget": budget_default}},
            "requires_user_input": True,
        },
        {
            "id": "as_proposed",
            "intent": "As proposed",
            "label": f"Read these {budget_default}",
            "description": "The run continues into full-text reading.",
            "delta": {},
            "requires_user_input": False,
        },
    ]


def _groups_options() -> list[dict[str, Any]]:
    """Groups floor, available only on deep chains after grouping."""
    return [
        {
            "id": "as_proposed",
            "intent": "Keep these groups",
            "label": "Keep these groups",
            "description": "On to the report plan.",
            "delta": {},
            "requires_user_input": False,
        },
        {
            "id": "regroup_granularity",
            "intent": "Broader or narrower groups",
            "label": "Broader or narrower groups",
            "description": (
                "Regroups the findings into fewer, broader clusters — or more, narrower "
                "ones. Re-runs grouping; the report plan is then redrawn."
            ),
            "delta": {"group": {"grouping": {"granularity": "coarser"}}},
            "requires_user_input": False,
        },
        {
            "id": "regroup_guided",
            "intent": "Regroup around my guidance",
            "label": "Regroup around my guidance",
            "description": (
                "Describe the grouping you want; the findings are regrouped. Re-runs grouping."
            ),
            "delta": {"group": {"grouping": {"guidance": [_GUIDANCE_PLACEHOLDER]}}},
            "requires_user_input": True,
        },
    ]


def _p4_options() -> list[dict[str, Any]]:
    """P4 synthesis_shape floor (before synthesise).

    ``edit_sections``/``emphasis_boosts`` target the synthesis directive grammar
    (``context["synthesis"]``); ``regroup_*`` are REPLACEMENT re-runs of group.
    Tag boosts are dropped (D4) — the boost floor speaks type/tier only.
    """
    return [
        {
            "id": "as_proposed",
            "intent": "As proposed",
            "label": "Write the report with these sections",
            "description": "The displayed plan is used to write the report.",
            "delta": {},
            "requires_user_input": False,
        },
        {
            "id": "emphasis_boosts",
            "intent": "Emphasise stronger evidence",
            "label": "Lean on the strongest evidence",
            "description": "The writing draws more heavily on the highest-quality studies.",
            "delta": {"synthesis": {"retrieval_boosts": {"appraisal_tier": {"5": 2.0}}}},
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


# --- The router fan-out (task 024, decision 3) -----------------------------
#
# A user's free-text utterance at a pause is compiled by the orchestrator
# ``route`` backend into a fan-out of per-intent fragments. Every fragment the
# model claims compiles is RE-VALIDATED here, author-blind, through the SAME
# fail-closed grammars a canonical option choice takes (steering discipline 3):
# nothing the model asserts is trusted — a fragment that fails validation is
# demoted to refused (``validation_failed``). Nothing applies unconfirmed; the
# render below is the confirmation the user sees.

FragmentKind = Literal["plan_adjustment", "replacement_rerun", "segment_reentry"]


@dataclass(frozen=True)
class RerunSurface:
    """The re-run surface available at one pause (what the router may target).

    Args:
        replacement_component: The component the point offers as a REPLACEMENT
            re-run from the pause (``"select"`` at the deepening-selection point,
            ``None`` elsewhere this slice), or ``None`` when no replacement re-run
            is wired at this boundary.
        segment_reentry_available: Whether an ADDITIVE segment re-entry (re-search
            back to acquire, or a criteria re-screen re-walk) can execute at this
            boundary — an after_component boundary with acquire already completed.
    """

    replacement_component: str | None
    segment_reentry_available: bool


@dataclass(frozen=True)
class CompiledFragment:
    """One router fragment that passed author-blind validation, ready to apply.

    Args:
        fragment_text: The part of the utterance this fragment answers (verbatim
            from the router, for the confirmation render and the record).
        kind: Which apply path the fragment takes.
        component: The composed component the delta targets.
        delta: The validated directive delta in the component's own grammar (the
            same shape a canonical option's ``delta`` carries).
        rerun_mode: ``"additive"`` / ``"replacement"`` for a re-run fragment, else
            ``None``.
    """

    fragment_text: str
    kind: FragmentKind
    component: str
    delta: dict[str, Any]
    rerun_mode: str | None


@dataclass(frozen=True)
class RefusedFragment:
    """One router fragment refused — by the model, by validation, or by the surface.

    Args:
        fragment_text: The part of the utterance this fragment answers (verbatim).
        reason: One plain sentence naming why it was not applied — never a
            suggestion to approximate it (the demand meter).
    """

    fragment_text: str
    reason: str


@dataclass(frozen=True)
class FanOut:
    """A deterministically-validated fan-out: what will apply, what was refused.

    Args:
        compiled: Fragments that will apply on confirmation, in application order.
        refused: Fragments refused, each carrying its verbatim text and reason.
        summary: The router's one/two-sentence plain summary for the render.
    """

    compiled: list[CompiledFragment] = field(default_factory=list)
    refused: list[RefusedFragment] = field(default_factory=list)
    summary: str = ""

    @property
    def plan_adjustments(self) -> list[CompiledFragment]:
        """The pending-component adjustment fragments (merged into one Adjust)."""
        return [frag for frag in self.compiled if frag.kind == "plan_adjustment"]

    @property
    def rerun(self) -> CompiledFragment | None:
        """The single re-run fragment to apply this pause, or ``None`` (one-cycle rule)."""
        return next((frag for frag in self.compiled if frag.kind != "plan_adjustment"), None)

    def as_interpreted_action(self) -> dict[str, Any]:
        """The JSON-safe fan-out record stamped on the confirmed decision event."""
        return {
            "compiled": [
                {
                    "fragment_text": frag.fragment_text,
                    "kind": frag.kind,
                    "component": frag.component,
                    "delta": frag.delta,
                    "rerun_mode": frag.rerun_mode,
                }
                for frag in self.compiled
            ],
            "refused": [
                {"fragment_text": frag.fragment_text, "reason": frag.reason}
                for frag in self.refused
            ],
            "summary": self.summary,
        }


class _FragmentRefused(Exception):
    """Internal: a compiling fragment failed re-validation or the surface check.

    Args:
        reason: The honest refusal reason recorded on the refused fragment.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def compile_fanout(
    compile_result: RouterCompileWire,
    *,
    backend_scope: str,
    current_components: set[str],
    completed_components: set[str],
    rerun_surface: RerunSurface,
) -> FanOut:
    """Re-validate a router compile, author-blind, into an apply-ready fan-out.

    Each fragment the model marked ``compiles=false`` is refused as-is. Each
    ``compiles=true`` fragment is re-validated through the same fail-closed
    grammar its target takes (:func:`_validate_directive_delta` for a pending
    component or an additive re-search / criteria re-screen; the replacement
    grammar for a select/characterise/group re-run) AND checked against the
    boundary's re-run surface and component bounds. A fragment that fails any
    check is demoted to a refused fragment with a ``validation_failed`` reason —
    the model's claim is never trusted (steering discipline 3). At most one
    re-run fragment survives: a second re-run is refused (the one-cycle rule,
    applying the one the utterance leads with).

    Args:
        compile_result: The router's raw fan-out.
        backend_scope: The plan's backend scope (acquire filter validation).
        current_components: The composed chain's component names.
        completed_components: Components whose boundary has already passed.
        rerun_surface: The re-run surface available at this boundary.

    Returns:
        The validated :class:`FanOut`.
    """
    compiled: list[CompiledFragment] = []
    refused: list[RefusedFragment] = []
    rerun_taken = False
    for fragment in compile_result.fragments:
        text = fragment.fragment_text
        if not fragment.compiles:
            refused.append(RefusedFragment(text, fragment.refusal_reason or "not yet expressible"))
            continue
        try:
            candidate = _classify_and_validate(
                fragment,
                backend_scope=backend_scope,
                current_components=current_components,
                completed_components=completed_components,
                rerun_surface=rerun_surface,
            )
        except _FragmentRefused as exc:
            refused.append(RefusedFragment(text, exc.reason))
            continue
        if candidate.kind != "plan_adjustment":
            if rerun_taken:
                refused.append(
                    RefusedFragment(
                        text,
                        "only one re-run can apply at a pause; an earlier re-run in your "
                        "request leads and was applied instead",
                    )
                )
                continue
            rerun_taken = True
        compiled.append(candidate)
    return FanOut(compiled=compiled, refused=refused, summary=compile_result.summary)


def _normalise_fragment_delta(component: Any, delta: dict[str, Any]) -> dict[str, Any]:
    """Normalise common live-model delta envelopes before fail-closed validation.

    Live routers sometimes wrap the directive in the component's own name
    (``{"acquire": {"search": ...}}``) or use the prompt's dotted family names
    (``{"search.guidance": [...]}``). Both are unambiguous; unwrapping/expanding
    them here is author-blind-safe because the SAME fail-closed validation runs
    on the result — this widens what parses, never what validates (024 live-check
    finding: a well-formed additive re-search was demoted on its envelope alone).
    """
    normalised = delta
    # Per-component directive-family key; unwrapping {component: inner} is only
    # unambiguous when the component name is NOT itself the family key
    # (characterise's family IS "characterise" — never unwrap it).
    family_keys = {
        "acquire": "search",
        "screen_abstract": "screening",
        "screen_full": "screening",
        "select": "selection",
        "extract": "extraction",
        "group": "grouping",
        "characterise": "characterise",
        "appraise": "appraisal",
        "synthesise": "synthesis",
    }
    if (
        isinstance(component, str)
        and set(normalised) == {component}
        and isinstance(normalised[component], dict)
        and family_keys.get(component) != component
    ):
        normalised = normalised[component]
    if any("." in key for key in normalised):
        expanded: dict[str, Any] = {}
        for key, value in normalised.items():
            if "." in key:
                family, _, leaf = key.partition(".")
                if not isinstance(expanded.get(family), dict):
                    expanded[family] = {}
                expanded[family][leaf] = value
            elif isinstance(value, dict) and isinstance(expanded.get(key), dict):
                expanded[key] = {**expanded[key], **value}
            else:
                expanded[key] = value
        normalised = expanded
    return normalised


def _classify_and_validate(
    fragment: Any,
    *,
    backend_scope: str,
    current_components: set[str],
    completed_components: set[str],
    rerun_surface: RerunSurface,
) -> CompiledFragment:
    """Classify one compiling fragment and re-validate it fail-closed, or refuse it."""
    component = fragment.component
    delta = _normalise_fragment_delta(fragment.component, fragment.delta or {})
    if not isinstance(component, str) or not component:
        raise _FragmentRefused("validation_failed: compiling fragment named no component")
    mode = fragment.rerun_mode

    if mode == "additive":
        if not rerun_surface.segment_reentry_available:
            raise _FragmentRefused(
                "validation_failed: an additive re-search is not available at this pause"
            )
        try:
            validate_steering_delta(
                delta,
                component,
                SteeringValidationCtx(
                    backend_scope=backend_scope,
                    current_components=current_components,
                    completed_components=set(),
                    rerun_surface=rerun_surface,
                ),
            )
        except SteeringDeltaInvalid as exc:
            raise _FragmentRefused(f"validation_failed: {exc}") from exc
        return CompiledFragment(
            fragment.fragment_text, "segment_reentry", component, delta, "additive"
        )

    if mode == "replacement":
        if component in REPLACEMENT_RERUN_CONTEXT_KEYS:
            if component != rerun_surface.replacement_component:
                raise _FragmentRefused(
                    f"validation_failed: a replacement re-run of {component!r} is not "
                    "available at this pause"
                )
            try:
                _validate_replacement_directive(component, delta)
            except SteeringAdjustmentError as exc:
                raise _FragmentRefused(f"validation_failed: {exc}") from exc
            return CompiledFragment(
                fragment.fragment_text, "replacement_rerun", component, delta, "replacement"
            )
        if component in {"screen_abstract", "screen_full"}:
            # A criteria re-screen replaces screening at the document grain but its
            # walk mechanics are an additive acquire->assess re-walk (contract
            # decision 7 / P2 note), so it rides the segment-re-entry apply path.
            if not rerun_surface.segment_reentry_available:
                raise _FragmentRefused(
                    "validation_failed: a criteria re-screen is not available at this pause"
                )
            _revalidate_directive(component, delta, backend_scope=backend_scope)
            return CompiledFragment(
                fragment.fragment_text, "segment_reentry", component, delta, "replacement"
            )
        raise _FragmentRefused(
            f"validation_failed: {component!r} has no replacement re-run at this pause"
        )

    # No re-run mode: a bounded adjustment of a not-yet-run component.
    if component in completed_components:
        raise _FragmentRefused(
            f"validation_failed: {component!r} has already run and cannot be adjusted"
        )
    if component not in current_components:
        raise _FragmentRefused(f"validation_failed: {component!r} is not in the plan")
    try:
        validate_steering_delta(
            delta,
            component,
            SteeringValidationCtx(
                backend_scope=backend_scope,
                current_components=current_components,
                completed_components=completed_components,
                rerun_surface=rerun_surface,
            ),
        )
    except SteeringDeltaInvalid as exc:
        raise _FragmentRefused(f"validation_failed: {exc}") from exc
    return CompiledFragment(fragment.fragment_text, "plan_adjustment", component, delta, None)


def _revalidate_directive(component: str, delta: dict[str, Any], *, backend_scope: str) -> None:
    """Re-validate a directive delta fail-closed, mapping failure to a refusal."""
    try:
        _validate_directive_delta(component, delta, backend_scope=backend_scope)
    except SteeringAdjustmentError as exc:
        raise _FragmentRefused(f"validation_failed: {exc}") from exc


def _fragment_mode_sentence(fragment: CompiledFragment) -> str:
    """The plain-language mode sentence declared for one fragment in the render."""
    if fragment.kind == "segment_reentry" and fragment.rerun_mode == "additive":
        return "this will ADD TO your evidence base"
    if fragment.kind == "segment_reentry" and fragment.rerun_mode == "replacement":
        return "this will RE-SCREEN every document at new criteria, replacing the current screening"
    if fragment.kind == "replacement_rerun":
        noun = {
            "select": "selection",
            "characterise": "characterisation",
            "group": "grouping",
        }.get(fragment.component, fragment.component)
        return f"this will REDO {noun}, replacing the current one"
    return f"this will adjust {fragment.component} before it runs"


# Bounds for the confirm-gate delta/refusal renders: a large model-authored
# delta or reason cannot flood the surface — it truncates with an explicit
# marker (FIX A/B).
_DELTA_RENDER_MAX = 500
_REFUSED_TEXT_MAX = 200
_REFUSED_REASON_MAX = 300


def _bound_display(value: str, limit: int) -> str:
    """NUL-scrub then length-bound one model-authored string for a user surface.

    The scrub is the existing output path (:func:`scrub_nul`); over the bound the
    string is truncated with an explicit ``…(truncated)`` marker so a large model
    string cannot flood the confirmation surface.
    """
    scrubbed = scrub_nul(value)
    if len(scrubbed) > limit:
        return scrubbed[:limit] + "…(truncated)"
    return scrubbed


def _bounded_delta_render(delta: dict[str, Any]) -> str:
    """Compact, sorted, bounded JSON render of a fragment delta for the confirm gate.

    Deterministic (``sort_keys``) so the same delta always renders the same text,
    NUL-scrubbed through the existing output path, and bounded to
    :data:`_DELTA_RENDER_MAX` characters. Lets the user SEE the compiled delta
    ("drop methodology sections" became ``{"synthesis":{"sections":[...]}}``)
    before confirming — the summary sentence alone can hide a diverging compile
    (FIX A).
    """
    dumped = json.dumps(delta, sort_keys=True, separators=(",", ":"), default=str)
    return _bound_display(dumped, _DELTA_RENDER_MAX)


def render_refused_fragment(refused: RefusedFragment) -> str:
    """One bounded confirm-surface line for a refused fragment: verbatim text + reason.

    Shared by :func:`render_fanout_confirmation` and the runner's all-refused note
    (FIX B) so both surface the same ``- 'text': reason`` line — the plain-language
    reason no longer lives only in the event log. Text and reason are NUL-scrubbed
    and length-bounded.
    """
    text = _bound_display(refused.fragment_text, _REFUSED_TEXT_MAX)
    reason = _bound_display(refused.reason, _REFUSED_REASON_MAX)
    return f"- {text!r}: {reason}"


def render_authored_replacement_confirmation(fragment: CompiledFragment) -> str:
    """Confirm-gate render for a picked watch-authored re-run/re-entry option (FIX C).

    A watch-AUTHORED option the user picked takes the same replacement-re-run or
    segment-re-entry apply path a confirmed router fan-out does, so it gets the
    same plain-language mode declaration ("this will REDO selection, replacing the
    current one" / additive equivalent) plus the bounded delta render before it
    applies. The user's y/N on THIS render is the safety gate — nothing applies
    unconfirmed (contract decision 3).
    """
    return "\n".join(
        [
            "Confirm this run-specific change:",
            f"- {fragment.component}: {_fragment_mode_sentence(fragment)}.",
            f"    {_bounded_delta_render(fragment.delta)}",
        ]
    )


def render_fanout_confirmation(fanout: FanOut) -> str:
    """Render a validated fan-out for the confirmation gate, deterministically.

    Each compiling fragment is shown with its target component, its re-run mode
    declared in plain language ("this will ADD TO your evidence base" / "this will
    REDO selection, replacing the current one"), and — indented beneath — the
    actual compiled delta as a bounded, deterministic JSON render (FIX A), so the
    user can SEE what the prose compiled to before confirming. Each refused
    fragment is named with its reason. Nothing here applies — the user's
    confirmation of this render is the safety gate (contract decision 3).

    Args:
        fanout: The validated fan-out from :func:`compile_fanout`.

    Returns:
        Stable, human-readable confirmation text.
    """
    lines = ["Steering interpretation — confirm to apply:"]
    if fanout.summary:
        lines.append(fanout.summary)
    if fanout.compiled:
        lines.append("Will apply:")
        for fragment in fanout.compiled:
            lines.append(
                f"- {fragment.fragment_text!r} → {fragment.component}: "
                f"{_fragment_mode_sentence(fragment)}."
            )
            lines.append(f"    {_bounded_delta_render(fragment.delta)}")
    if fanout.refused:
        lines.append("Refused (not expressible / not available):")
        for refused in fanout.refused:
            lines.append(render_refused_fragment(refused))
    return "\n".join(lines)


def validate_option_delta(delta: dict[str, Any], *, backend_scope: str = "both") -> None:
    """Compile one canonical-option delta through its component grammar (fail-closed).

    Mirrors the shapes :func:`build_steer_point_options` emits: an empty delta is
    a no-op (continue / abort / accept_thin / as_proposed); a bare
    ``{"selection": ...}`` is the legacy P3 select fine-directive; a bare
    ``{"synthesis": ...}`` is the synthesis directive grammar; every other delta
    names exactly one component and compiles through
    :func:`_validate_directive_delta`. This is the single delta-compile seam the
    ``SteerPointDefault`` validator and the router share.

    Args:
        delta: The compiled directive delta to compile-check.
        backend_scope: Backend scope for acquire filter validation. Defaults to
            ``"both"`` (the permissive compile check at plan-validation time,
            where the run's scope is not the sub-model's to see); the real apply
            path re-validates against the run's scope.

    Raises:
        SteeringAdjustmentError: If the delta does not compile.
        ValueError: If the delta is not a single-component (or bare select /
            synthesis) shape.
    """
    if not delta:
        return
    keys = set(delta)
    if keys == {"selection"}:
        try:
            select_module._parse_directive(delta["selection"])
        except select_module.DirectiveError as exc:
            raise SteeringAdjustmentError(str(exc)) from exc
        return
    if keys == {"synthesis"}:
        try:
            parse_synthesis_directive({"synthesis": delta["synthesis"]}, grouping_group_ids=None)
        except SynthesisDirectiveError as exc:
            raise SteeringAdjustmentError(str(exc)) from exc
        return
    if len(keys) != 1:
        raise ValueError(f"option delta must name exactly one component, got {sorted(keys)!r}")
    (component,) = keys
    _validate_directive_delta(component, delta[component], backend_scope=backend_scope)


def _delta_has_content(value: Any) -> bool:
    """Return whether a delta carries any supplied user input (fail-closed helper).

    A ``requires_user_input`` option's rule must supply real input, not the
    unfilled template. Content = any non-empty string that is NOT an option
    placeholder sentinel, or any number, anywhere in the delta. Bare booleans
    (e.g. ``rescreen: True``) and empty collections/placeholders are NOT content:
    the template ``{"screening": {"criteria": ["Describe…"], "rescreen": True}}``
    and ``{"selection": {"priority_strata": [], "must_include_ids": []}}`` both
    read as unfilled.
    """
    if isinstance(value, dict):
        return any(_delta_has_content(item) for item in value.values())
    if isinstance(value, list):
        return any(_delta_has_content(item) for item in value)
    if isinstance(value, bool):
        return False
    if isinstance(value, str):
        return bool(value) and value not in _OPTION_PLACEHOLDERS
    if isinstance(value, int | float):
        return True
    return value is not None


def validate_steer_point_default(
    *,
    steer_point: str,
    action: str,
    option_id: str | None,
    delta: dict[str, Any] | None,
) -> None:
    """Fail-closed validation of a standing-instruction rule's option binding.

    Called from ``SteerPointDefault``'s model validator when ``option_id`` or
    ``delta`` is present (the bare two-field rule skips it). The steer-point name
    itself is validated by the model's field validator; this asserts:

    * the binding is only present on a ``proceed_flag`` action (a ``stop`` is a
      hard stop — it carries no option);
    * the ``option_id`` is a canonical option at the point (author-blind
      vocabulary check against :func:`build_steer_point_options`);
    * the ``delta`` compiles through the point's component grammar; and
    * a ``requires_user_input`` option's rule supplies real input in its delta
      (an unfilled template is rejected).

    Args:
        steer_point: The (already name-validated) lattice point name.
        action: The rule's action — only ``proceed_flag`` may carry a binding.
        option_id: The canonical option id, or ``None``.
        delta: The compiled directive delta, or ``None``.

    Raises:
        ValueError: On any of the fail-closed conditions above.
        SteeringAdjustmentError: If the delta does not compile (a ``ValueError``
            subclass — pydantic surfaces it as a validation error either way).
    """
    if action != "proceed_flag":
        raise ValueError(
            f"steer_point_default for {steer_point!r} with action {action!r} cannot carry "
            "an option_id/delta — only 'proceed_flag' rules bind an option"
        )
    options = build_steer_point_options(plan=None, point=steer_point)
    by_id = {option["id"]: option for option in options}
    if option_id is not None and option_id not in by_id:
        raise ValueError(
            f"option_id {option_id!r} is not a canonical option at steer point "
            f"{steer_point!r}; expected one of {sorted(by_id)!r}"
        )
    if delta is not None:
        validate_option_delta(delta)
    if (
        option_id is not None
        and by_id[option_id].get("requires_user_input")
        and not _delta_has_content(delta)
    ):
        raise ValueError(
            f"option {option_id!r} at steer point {steer_point!r} requires user input, "
            "but the standing rule's delta supplies none"
        )


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


# Replacement re-run components (contract decision 7): reselect · re-characterise
# · re-group (same facet). Each maps its component name to the single fine-directive
# context key its parser validates. The mode is "replacement" — old result rows
# persist immutably; the walk's reference moves to the new run id.
REPLACEMENT_RERUN_CONTEXT_KEYS: dict[str, str] = {
    "select": "selection",
    "characterise": "characterise",
    "group": "grouping",
}


def _validate_replacement_directive(component: str, directive: dict[str, Any]) -> None:
    """Validate a replacement re-run's fine directive through the component's parser.

    Each replacement re-run carries a commit-layer directive under the component's
    own context key; it is validated fail-closed by that component's parser and
    never smuggled into the plan payload (the ``apply_reselect`` precedent).

    Raises:
        SteeringAdjustmentError: On any malformed shape, wrapping the component
            parser's own fail-closed error.
    """
    if component == "select":
        try:
            select_module._parse_directive(directive.get("selection"))
        except select_module.DirectiveError as exc:
            raise SteeringAdjustmentError(str(exc)) from exc
        return
    if component == "characterise":
        try:
            characterise_module._parse_characterise_directive(directive.get("characterise"))
        except characterise_module.CharacteriseDirectiveError as exc:
            raise SteeringAdjustmentError(str(exc)) from exc
        return
    if component == "group":
        try:
            parse_grouping_directive({"grouping": directive.get("grouping")})
        except FacetDirectiveError as exc:
            raise SteeringAdjustmentError(str(exc)) from exc
        return
    raise SteeringAdjustmentError(f"component {component!r} has no replacement re-run grammar")


def apply_replacement_rerun(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    plan_row: Any,
    plan: OrchestrationPlan,
    component: str,
    directive: dict[str, Any],
) -> tuple[uuid.UUID, int]:
    """Persist a user-attributed plan version row for a replacement re-run.

    Generalises the deepening-selection reselect pattern to the three
    reference-moving replacement re-runs (contract decision 7): reselect,
    re-characterise and re-group. Each fires at a steer point *after* its
    component has run, so the generic completed-component adjustment path
    (``apply_adjustment``) cannot amend it — it treats the component as
    already-run. This records the user's steering event as a new plan version
    row (the "human substance enters honestly in provenance" rule).

    The fine directive (select ``weight_emphasis``/``budget``, characterise
    ``themes``/``guidance``, group ``granularity``/``guidance``/``facets``) is a
    **commit-layer** directive the task-2 ``OrchestrationPlan`` model deliberately
    does not carry: the runner applies it to the scope context and it is recorded
    faithfully in the re-run's own result provenance — never smuggled into the
    plan payload, which therefore carries forward unchanged.

    Args:
        conn: Open transaction for the version-row write.
        project_id: Project owning the plan lineage.
        plan_row: Current persisted orchestration-plan row.
        plan: Current validated orchestration plan (carried forward unchanged).
        component: The re-run component — ``select``/``characterise``/``group``.
        directive: The merged fine directive, validated fail-closed.

    Returns:
        The new plan id and new plan version.

    Raises:
        SteeringAdjustmentError: If the merged directive is malformed, the
            component has no replacement grammar, or the plan row lacks a UUID id
            / integer version.
    """
    _validate_replacement_directive(component, directive)
    return _persist_new_plan_version(
        conn,
        project_id=project_id,
        plan_row=plan_row,
        payload=plan.model_dump(mode="json"),
    )


def apply_segment_reentry(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    plan_row: Any,
    plan: OrchestrationPlan,
    segment_start: str,
    directive_deltas: dict[str, dict[str, Any]],
) -> tuple[uuid.UUID, int]:
    """Persist a user-attributed plan version row for an additive segment re-entry.

    Additive segment re-entry (contract decision 7a) is a user decision, so it
    records a new plan version row the same way a replacement re-run does — but
    it is *additive*, not reference-moving: the plan payload carries forward
    unchanged and the amendment is a commit-layer directive the runner applies to
    the scope context as it re-walks each segment component (the
    ``apply_replacement_rerun`` / ``apply_reselect`` fine-directive precedent).

    Fail-closed: ``segment_start`` must be the one shipped segment
    (:data:`SHIPPED_SEGMENT_START`); every amendment delta is validated through
    its component's own parser (:func:`_validate_directive_delta`).

    Args:
        conn: Open transaction for the version-row write.
        project_id: Project owning the plan lineage.
        plan_row: Current persisted orchestration-plan row.
        plan: Current validated orchestration plan (carried forward unchanged).
        segment_start: The segment start component; must be ``"acquire"``.
        directive_deltas: The amendment, keyed by component.

    Returns:
        The new plan id and new plan version.

    Raises:
        SteeringAdjustmentError: If the segment is not shipped, an amendment
            delta is malformed, or the plan row lacks a UUID id / integer
            version.
    """
    if segment_start != SHIPPED_SEGMENT_START:
        raise SteeringAdjustmentError(
            f"segment {segment_start!r} not shipped; only {SHIPPED_SEGMENT_START!r} "
            "is a shipped re-entry segment"
        )
    for component, delta in directive_deltas.items():
        _validate_directive_delta(component, delta, backend_scope=plan.backend_scope)
    return _persist_new_plan_version(
        conn,
        project_id=project_id,
        plan_row=plan_row,
        payload=plan.model_dump(mode="json"),
    )


def apply_reselect(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    plan_row: Any,
    plan: OrchestrationPlan,
    select_directive: dict[str, Any],
) -> tuple[uuid.UUID, int]:
    """Thin alias for ``apply_replacement_rerun`` at the ``select`` component.

    Retained so existing reselect callers and tests read unchanged; new code uses
    :func:`apply_replacement_rerun` with an explicit component.
    """
    return apply_replacement_rerun(
        conn,
        project_id=project_id,
        plan_row=plan_row,
        plan=plan,
        component="select",
        directive=select_directive,
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
            raise SteeringAdjustmentError(f"adjustment names already-run component {component!r}")
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
    payload["time_band"] = time_band_for(
        search_effort, analysis_depth, payload.get("section_budget")
    )


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
        try:
            screen_module._parse_screen_directive({"screening": delta["screening"]})
        except screen_module.ScreenDirectiveError as exc:
            # Map to the refusal path like every sibling branch — a malformed
            # router-compiled delta must refuse honestly, never crash the
            # compile (live-check finding, 2026-07-21: this was the one
            # unwrapped branch of seven).
            raise SteeringAdjustmentError(str(exc)) from exc
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
    if component == "synthesise":
        # P4 synthesis-shape edits (sections / retrieval boosts) are a
        # commit-layer directive with no OrchestrationPlan field (the appraise /
        # characterise precedent): validated through the synthesis grammar, and
        # exempt from the plan round-trip below.
        _require_keys(component, delta, {"synthesis"})
        try:
            parse_synthesis_directive({"synthesis": delta["synthesis"]}, grouping_group_ids=None)
        except SynthesisDirectiveError as exc:
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
        # Mixed grammar (task 024, 15d): ONLY facets map to the plan payload.
        # D8 granularity and B3 guidance are commit-layer (folded into the
        # pending overlay). Write grouping_facets ONLY when the delta actually
        # names facets — a granularity-/guidance-only delta must NOT clobber the
        # plan's facet set back to the default.
        grouping = delta["grouping"]
        if isinstance(grouping, dict) and ("facets" in grouping or "facet" in grouping):
            facets, _facet_source, _granularity, _guidance = parse_grouping_directive(
                {"grouping": grouping}
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
    elif component == "synthesise":
        # P4's synthesis directive (sections / retrieval boosts) is a
        # commit-layer directive with no OrchestrationPlan field (same
        # precedent as characterise): nothing to write into the plan payload.
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
    # Mixed grammar (task 024, 15d / FIX 3b): ONLY ``budget`` maps to the plan
    # payload (via ``analysis_depth``). The rest of select's grammar (D6
    # strata_scope, D7 exclude_ids, weight_emphasis, boosts, must_include_ids,
    # priority_strata) is commit-layer — validated fail-closed at
    # ``_validate_directive_delta`` time and folded into the pending overlay so it
    # reaches select's executed directive at its run, never silently dropped. Only
    # a key outside select's whole grammar is the loud raise (the guarded path).
    if not isinstance(selection, dict):
        raise SteeringAdjustmentError("selection directive must be an object")
    _context_key, commit_keys = _MIXED_COMMIT_LAYER_KEYS["select"]
    if set(selection) - ({"budget"} | commit_keys):
        raise SteeringAdjustmentError("selection directive is not yet mappable to plan fields")
    if "budget" not in selection:
        return
    budget = selection["budget"]
    for depth, settings in ANALYSIS_DEPTH_TABLE.items():
        if settings["selection_budget"] == budget:
            payload["analysis_depth"] = depth
            payload["time_band"] = time_band_for(
                payload["search_effort"], depth, payload.get("section_budget")
            )
            _clip_components_to_depth(payload, analysis_depth=depth)
            return
    raise SteeringAdjustmentError("selection budget does not map to a plan analysis_depth")


def _apply_extract_delta(payload: dict[str, Any], extraction: Any) -> None:
    # Mixed grammar (task 024, 15d): ONLY ``profiles`` maps to the plan payload.
    # ``refresh`` (D3) and ``relevance_emphasis`` (the B2' entry point) are
    # commit-layer — validated here but folded into the pending overlay so they
    # reach the run, never silently dropped. Parse validates the whole directive
    # (incl. relevance_emphasis) fail-closed; profiles are written only when the
    # delta actually names them (a refresh-/emphasis-only delta must NOT clobber
    # the plan's profile set).
    try:
        profiles, _refresh = extract_module._parse_extraction_directive(extraction)
    except extract_module.ExtractError as exc:
        raise SteeringAdjustmentError(str(exc)) from exc
    if not (isinstance(extraction, dict) and "profiles" in extraction):
        return
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
        if component in COMMIT_LAYER_COMPONENTS:
            continue
        # compose() always injects sibling keys the caller need not supply
        # (e.g. acquire's "depth", screen_full's "stage"), so the recompiled
        # delta is checked to *contain* the request, not to equal it — a
        # requested value the plan fields cannot express still fails closed.
        # Mixed grammar (task 024, 15d): only the plan-mappable part round-trips.
        # extract -> profiles; group -> facets. The commit-layer remainder
        # (extract refresh / relevance_emphasis; group granularity / guidance) is
        # validated at _validate_directive_delta time and consumed verbatim by the
        # component's own parser at run time via the pending overlay — it has no
        # plan field to round-trip through, so it is exempt here (never dropped).
        if component == "extract" and requested_delta:
            extraction = requested_delta.get("extraction")
            if not (isinstance(extraction, dict) and "profiles" in extraction):
                continue  # refresh / relevance_emphasis are commit-layer (overlay)
            try:
                requested_profiles, _requested_refresh = extract_module._parse_extraction_directive(
                    extraction
                )
            except extract_module.ExtractError as exc:
                raise SteeringAdjustmentError(str(exc)) from exc
            actual = amended_by_component.get(component)
            actual_extraction = actual.get("extraction") if isinstance(actual, dict) else None
            actual_profiles = (
                actual_extraction.get("profiles") if isinstance(actual_extraction, dict) else None
            )
            if tuple(actual_profiles or ()) == requested_profiles:
                continue
            raise SteeringAdjustmentError(
                f"adjustment for {component!r} cannot round-trip through plan fields"
            )
        if component == "select" and requested_delta:
            # Mixed grammar (FIX 3b): only ``budget`` round-trips (through
            # analysis_depth); the commit-layer keys (D6 strata_scope, D7
            # exclude_ids, weight_emphasis, ...) have no plan field and reach
            # select's executed directive via the pending overlay, so they are
            # exempt here (never dropped) — exactly the extract/group pattern.
            selection = requested_delta.get("selection")
            budget_part = (
                {"budget": selection["budget"]}
                if isinstance(selection, dict) and "budget" in selection
                else {}
            )
            if budget_part and not _delta_contains(
                amended_by_component.get(component), {"selection": budget_part}
            ):
                raise SteeringAdjustmentError(
                    f"adjustment for {component!r} cannot round-trip through plan fields"
                )
            continue
        if component == "group" and requested_delta:
            grouping = requested_delta.get("grouping")
            facet_part = (
                {key: value for key, value in grouping.items() if key in {"facet", "facets"}}
                if isinstance(grouping, dict)
                else {}
            )
            if facet_part and not _delta_contains(
                amended_by_component.get(component), {"grouping": facet_part}
            ):
                raise SteeringAdjustmentError(
                    f"adjustment for {component!r} cannot round-trip through plan fields"
                )
            continue
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
