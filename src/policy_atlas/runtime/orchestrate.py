"""The orchestrator CLI — the one new public interface of slice 017.

Runnable as ``python -m policy_atlas.runtime.orchestrate``. It owns the whole
user-facing product path: a planning conversation (intent -> refined,
depth-graded orchestration plan), plan review and approval, and driving the EB
capability-runner with steering check-ins. Sub-agents never address the user;
the orchestrator relays deterministic runner check-ins and steering pauses
through a small, injectable console seam.

Live switch mirrors ``skeleton.py``: a configured ``OPENAI_API_KEY`` selects the
live planner + live backend set (with Langfuse tracing); its absence selects the
deterministic stubs and an egress-free fixture corpus, so the demo/dev path
never leaves the machine.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol, cast

import structlog
from pydantic import ValidationError
from sqlalchemy import select as sa_select
from sqlalchemy.engine import Engine

from policy_atlas.core import tracing
from policy_atlas.core.db import get_engine
from policy_atlas.core.embeddings import EmbeddingBackend, OpenAIEmbeddingBackend
from policy_atlas.core.fixtures import get_source
from policy_atlas.core.logging import configure_logging
from policy_atlas.core.schema import artefact, evidence_scope, orchestration_plan, project
from policy_atlas.evidence_base.assess.classification_backend import OpenAIClassificationBackend
from policy_atlas.evidence_base.assess.screening_backend import OpenAIScreeningBackend
from policy_atlas.evidence_base.corpus.ranking import OpenAIRankingBackend
from policy_atlas.evidence_base.corpus.theme_grouping import (
    OpenAIThemeGroupingBackend,
    ThemeGroupingBackend,
)
from policy_atlas.evidence_base.extract.extraction_backend import (
    OpenAIExtractionBackend,
    OpenAIICFExtractionBackend,
)
from policy_atlas.evidence_base.extract.finding_vetter import (
    OpenAIFindingVetterBackend,
    OpenAIICFFindingVetterBackend,
)
from policy_atlas.evidence_base.group.group_clustering import OpenAIGroupClusteringBackendFactory
from policy_atlas.evidence_base.sourcing import search_generation, search_live
from policy_atlas.evidence_base.sourcing.acquire import SearchBackend
from policy_atlas.evidence_base.sourcing.country_filters import TIER1_GROUPS, expand_tier1
from policy_atlas.evidence_base.sourcing.fetch_live import LiveDocumentFetcher
from policy_atlas.evidence_base.sourcing.ingest_upload import ingest_upload
from policy_atlas.evidence_base.synthesis.grounding_judge import OpenAIGroundingJudgeBackend
from policy_atlas.evidence_base.synthesis.synthesis_backend import OpenAISynthesisBackend
from policy_atlas.runtime.orchestration_plan import CountryGroupAuthorship, OrchestrationPlan
from policy_atlas.runtime.orchestrator_backend import (
    OpenAIOrchestratorBackend,
    OrchestratorBackend,
    StubOrchestratorBackend,
)
from policy_atlas.runtime.planner import OpenAIPlannerBackend, PlannerBackend, StubPlannerBackend
from policy_atlas.runtime.planner_prompt import PLANNER_HISTORY_TURNS_MAX, PlanDraftWire
from policy_atlas.runtime.runner import RunnerBackends, RunPlanOutcome, run_plan
from policy_atlas.runtime.steering import (
    Abort,
    Adjust,
    Continue,
    FreeText,
    SteeringResponse,
    refuse_inexpressible,
    render_check_in,
)

log = structlog.get_logger()

# Cap the planning conversation so a planner that never returns ``ready`` (or a
# plan that never validates) fails honestly instead of looping forever.
MAX_PLANNER_TURNS = 10

# The prompt's history window must hold every turn a conversation can have
# accumulated when the planner is called (1 intent + 2 per completed
# iteration): if it rotated, the original intent would silently drop and the
# intent-sized first-turn cap would land on a mid-conversation turn.
assert (MAX_PLANNER_TURNS - 1) * 2 + 1 <= PLANNER_HISTORY_TURNS_MAX

# Exit codes. No token/cost surface — time only (contract decision 11).
EXIT_SUCCESS = 0
EXIT_RUN_FAILED = 2
EXIT_ABORTED = 3
EXIT_ABANDONED = 4
EXIT_NO_PLAN = 2  # planner never converged on an approved, valid plan

_EXIT_BY_STATUS: dict[str, int] = {
    "succeeded": EXIT_SUCCESS,
    "degraded": EXIT_SUCCESS,
    "failed": EXIT_RUN_FAILED,
    "aborted": EXIT_ABORTED,
}

_STEERING_MODES = frozenset({"frequent", "moderate", "minimal", "unattended"})

# The delegation-posture labels (contract § Modes as delegation postures; annex
# § the target-shape mode table). The mode is a delegation posture — "when
# should I come back to you?" — and moves who decides, never what is decided or
# recorded. Plan values are unchanged; these are presentation only.
_MODE_ORDER: tuple[str, ...] = ("frequent", "moderate", "minimal", "unattended")
_MODE_LABELS: dict[str, str] = {
    "frequent": "Often — walk me through it",
    "moderate": "At the key decisions",
    "minimal": "Only if something needs my judgment",
    "unattended": "Never — here are my standing instructions",
}
_DEFAULT_MODE = "moderate"

# Canonical-option ids that the always-present console frame already covers
# (Continue / Change steering mode / Abort). They are dropped from the numbered
# canonical block so the generic non-lattice floor (finding M6) and any
# point-local continue/abort are not rendered twice. Filtering is display-only —
# the durable pause payload carries the full option list unchanged.
_FRAME_OPTION_IDS: frozenset[str] = frozenset({"continue", "change_mode", "abort"})


def _mode_label(mode: str) -> str:
    """Return the delegation-posture label for a plan mode value."""
    label = _MODE_LABELS.get(mode, mode)
    return f"{label} (default)" if mode == _DEFAULT_MODE else label


def _mode_legend_lines(indent: str = "    ") -> list[str]:
    """Render the four delegation-posture labels as a legend (all four shown)."""
    lines = [f"{indent}Steering modes (when should I come back to you?):"]
    for mode in _MODE_ORDER:
        lines.append(f"{indent}  {mode} — {_mode_label(mode)}")
    return lines


def _route_option_delta(delta: dict[str, Any]) -> dict[str, Any]:
    """Route a canonical-option delta into a component-keyed ``directive_deltas``.

    Mirrors :func:`steering.validate_option_delta`: a bare ``{"selection": ...}``
    is the select fine-directive (wrapped under the ``select`` component), a bare
    ``{"synthesis": ...}`` the synthesise directive (wrapped under ``synthesise``);
    every other option delta already names its component at the top level (P1
    ``acquire``, P2 ``screen_abstract``/``characterise``, P3 ``extract``, P4
    ``group``) and is used as-is. The old blanket ``{"select": delta}`` wrap is
    retired — only the bare-selection shape keeps it.
    """
    keys = set(delta)
    if keys == {"selection"}:
        return {"select": delta}
    if keys == {"synthesis"}:
        return {"synthesise": delta}
    return delta


def _bundle_headline(key: str, value: Any) -> str:
    """A compact one-line headline for one decision-bundle key.

    Bundle keys with headline numbers only — never full document lists
    (contract deliverable § pause rendering upgrades). Scalars print their
    value; collections print a count (or their scalar sub-fields, when the
    dict carries headline numbers).
    """
    if isinstance(value, bool):
        return f"{key}: {value}"
    if isinstance(value, int | float):
        return f"{key}: {value}"
    if isinstance(value, str):
        text = value if len(value) <= 80 else value[:77] + "..."
        return f"{key}: {text}"
    if isinstance(value, list):
        return f"{key}: {len(value)} items"
    if isinstance(value, dict):
        numbers = {
            sub_key: sub_value
            for sub_key, sub_value in value.items()
            if isinstance(sub_value, int | float) and not isinstance(sub_value, bool)
        }
        if numbers:
            rendered = ", ".join(f"{sub}={numbers[sub]}" for sub in sorted(numbers))
            return f"{key}: {rendered}"
        return f"{key}: {len(value)} entries"
    return f"{key}: —"

# The egress-free demo/dev corpus, mirroring skeleton.py's ingest_upload seed:
# two synthetic full-text reviews the stub classify/appraise path scores so the
# chain has an appraised, screened-in corpus to run over.
_STUB_CORPUS: tuple[tuple[str, str], ...] = (
    ("syn-001", "Synthetic policy review"),
    ("syn-002", "Synthetic review of housing affordability policies"),
)


def _now() -> datetime:
    return datetime.now(UTC)


class ConsoleIO(Protocol):
    """Console seam for the planning conversation and steering menus.

    The ``python -m`` entrypoint injects a stdin/stdout implementation;
    scripted tests inject a deterministic double.
    """

    def prompt(self, message: str) -> str:
        """Print ``message`` and return one line of user input."""
        ...

    def print(self, message: str) -> None:
        """Print one line of orchestrator output."""
        ...


def _strip_control(text: str) -> str:
    return "".join(
        ch
        for ch in text
        if ch in ("\n", "\t") or (ch >= " " and ch != "\x7f" and not ("\x80" <= ch <= "\x9f"))
    )


class StdConsole:
    """Real stdin/stdout console used by ``python -m policy_atlas.runtime.orchestrate``."""

    def prompt(self, message: str) -> str:
        """Print ``message`` and read one line from stdin.

        Args:
            message: The prompt to display.

        Returns:
            The user's line, without the trailing newline.
        """
        return input(message)

    def print(self, message: str) -> None:
        """Write one line to stdout, stripped of terminal control characters.

        Planner output is untrusted model text; escape sequences could rewrite
        or hide the very plan lines the user is approving, so everything but
        newlines and tabs in the C0/C1/DEL ranges is dropped at this seam.

        Args:
            message: The text to print.
        """
        print(_strip_control(message))


@dataclass
class OrchestrateResult:
    """Structured result of one orchestrator session (testability seam).

    Args:
        exit_code: Process exit code the ``python -m`` entrypoint returns.
        plan: The approved orchestration plan, or ``None`` if none was approved.
        plan_id: The persisted orchestration-plan row id, or ``None``.
        project_id: The created project id, or ``None`` if nothing was created.
        evidence_scope_id: The created evidence-scope id, or ``None``.
        outcome: The runner outcome, or ``None`` if no run was launched.
        turns: The full planning-conversation turn log.
        runner_io: The steering IO used for the run (``CliIO``/``UnattendedIO``),
            or ``None`` if no run was launched.
        artefact_present: Whether a synthesis artefact row exists for the project.
        conversation_id: Langfuse session id minted for this orchestrator conversation.
    """

    exit_code: int
    plan: OrchestrationPlan | None = None
    plan_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    evidence_scope_id: uuid.UUID | None = None
    outcome: RunPlanOutcome | None = None
    turns: list[dict[str, str]] = field(default_factory=list)
    runner_io: CliIO | UnattendedIO | None = None
    artefact_present: bool = False
    conversation_id: uuid.UUID | None = None


class CliIO:
    """Attended steering IO: relays check-ins and blocks for pause decisions.

    Args:
        console: The console seam the pauses render through.
    """

    def __init__(self, console: ConsoleIO) -> None:
        self._console = console
        self.pause_calls = 0

    def check_in(self, component: str, payload: dict[str, Any]) -> None:
        """Relay one deterministic runner check-in to the console.

        Args:
            component: Orchestration step name.
            payload: Deterministic outcome payload.
        """
        del component
        self._console.print(render_check_in(payload))

    def confirm(self, render: str) -> bool:
        """Render a router fan-out and take the confirm gate (contract decision 3).

        Nothing a free-text steer compiles into applies until the user confirms
        the rendered fan-out — the fan-out already declares each fragment's re-run
        mode in plain language. Default is no: a bare Enter, ``n``, or anything
        that is not an explicit yes declines, so nothing applies.

        Args:
            render: The deterministic fan-out confirmation render.

        Returns:
            ``True`` only on an explicit yes.
        """
        self._console.print(render)
        answer = self._console.prompt("Apply this steering? [y/N]: ").strip().lower()
        return answer in ("y", "yes")

    def pause(self, point: dict[str, Any], render: str) -> SteeringResponse:
        """Render a steering boundary as a numbered menu and map the answer.

        Continue (1) · the point's canonical options · watch-authored options
        (when present) · change mode · abort are numbered; anything that is not a
        number or a menu keyword is free prose returned as :class:`FreeText` for
        the router to compile. An out-of-range or empty entry re-prompts locally.

        Args:
            point: Pause-point payload — ``steer_point`` name, ``options`` (the
                canonical floor), ``triggers``, ``bundle`` and ``authored_options``
                (watch-authored, attributed) all optional.
            render: Deterministic pause render (the check-in text; the runner
                appends any refusal/rejection note on a re-presentation).

        Returns:
            The mapped steering response.
        """
        self.pause_calls += 1
        options = [
            option
            for option in cast(list[dict[str, Any]], point.get("options") or [])
            if option.get("id") not in _FRAME_OPTION_IDS
        ]
        authored = cast(list[dict[str, Any]], point.get("authored_options") or [])
        while True:
            lines = self._render_pause_header(point, render)
            lines.append("Steering options:")
            lines.append("  1) Continue")
            option_by_num: dict[int, dict[str, Any]] = {}
            authored_by_num: dict[int, dict[str, Any]] = {}
            num = 2
            for option in options:
                lines.append(f"  {num}) {option['label']} — {option['description']}")
                option_by_num[num] = option
                num += 1
            if authored:
                lines.append("Suggested for this run (suggested by the orchestrator):")
                for option in authored:
                    why = str(option.get("why", "")).strip()
                    label = str(option.get("label", "")).strip()
                    lines.append(f"  {num}) {label} — {why}" if why else f"  {num}) {label}")
                    authored_by_num[num] = option
                    num += 1
            mode_num = num
            lines.append(f"  {num}) Change steering mode")
            num += 1
            abort_num = num
            lines.append(f"  {num}) Abort")
            lines.append("  (or type your own steering instruction)")
            self._console.print("\n".join(lines))

            raw = self._console.prompt("Choose an option, or type an instruction: ").strip()
            key = raw.lower()
            if key in ("1", "continue"):
                return Continue()
            if key in (str(abort_num), "abort"):
                return Abort()
            if key in (str(mode_num), "mode"):
                return self._prompt_mode()
            if raw.isdigit():
                num_choice = int(raw)
                if num_choice in option_by_num:
                    response = self._option_to_response(option_by_num[num_choice])
                    if response is not None:
                        return response
                    continue
                if num_choice in authored_by_num:
                    return self._authored_to_response(authored_by_num[num_choice])
                self._console.print(
                    f"{raw} is not one of the numbered options; choose again or "
                    "type an instruction."
                )
                continue
            if not raw:
                continue
            # Free prose → the router (contract decision 3). The runner compiles
            # it, re-validates author-blind, confirms, and applies — or degrades
            # to this menu with an honest note appended to the render.
            return FreeText(raw)

    def _render_pause_header(self, point: dict[str, Any], render: str) -> list[str]:
        """Render the check-in plus the steer-point name, fired triggers and bundle."""
        lines = [render]
        steer_point = point.get("steer_point")
        if steer_point:
            lines.append(f"Steer point: {steer_point}")
        triggers = cast(list[dict[str, Any]], point.get("triggers") or [])
        if triggers:
            names = ", ".join(str(trigger.get("trigger", trigger)) for trigger in triggers)
            lines.append(f"Triggers fired: {names}")
        bundle = cast(dict[str, Any], point.get("bundle") or {})
        if bundle:
            lines.append("Evidence snapshot:")
            for bundle_key in sorted(bundle):
                lines.append(f"  {_bundle_headline(bundle_key, bundle[bundle_key])}")
        return lines

    def _prompt_mode(self) -> SteeringResponse:
        self._console.print("\n".join(_mode_legend_lines(indent="")))
        raw = self._console.prompt(
            "New steering mode [frequent/moderate/minimal/unattended]: "
        ).strip().lower()
        return Adjust(new_mode=raw)

    def _authored_to_response(self, option: dict[str, Any]) -> SteeringResponse:
        """Map a picked watch-authored option to a bounded adjustment.

        Authored options carry a component + its own-grammar delta (the router
        fragment shape), so ``directive_deltas`` is ``{component: delta}`` — the
        same path a compiled router fragment or canonical option takes. The
        orchestrator authored the option; the user picked it — the decision
        event records decided_by=user, authored_by=orchestrator (discipline iv).
        """
        component = option.get("component")
        delta = cast(dict[str, Any], option.get("delta") or {})
        if not isinstance(component, str) or not component or not delta:
            return Continue()
        return Adjust(directive_deltas={component: delta}, authored_by="orchestrator")

    def _option_to_response(self, option: dict[str, Any]) -> SteeringResponse | None:
        delta = cast(dict[str, Any], option.get("delta") or {})
        if not delta:
            # Empty delta = proceed (continue / as_proposed / accept_thin).
            return Continue()
        if option.get("requires_user_input"):
            filled = self._fill_option_delta(option)
            if filled is None:
                return None
            delta = filled
        return Adjust(directive_deltas=_route_option_delta(delta))

    def _fill_option_delta(self, option: dict[str, Any]) -> dict[str, Any] | None:
        if option["id"] == "adjust_budget":
            raw = self._console.prompt("New selection budget: ").strip()
            if not raw.isdigit():
                self._console.print(refuse_inexpressible(raw))
                return None
            return {"selection": {"budget": int(raw)}}
        if option["id"] == "deepen_clusters":
            strata = _split_ids(self._console.prompt("Cluster ids (comma-separated): "))
            docs = _split_ids(self._console.prompt("Document ids to force-include: "))
            return {"selection": {"priority_strata": strata, "must_include_ids": docs}}
        # Richer requires-user-input options (criteria lists, section objects,
        # guidance sentences) are best given as prose: the router compiles them
        # faithfully. Direct the user there rather than approximate a template.
        self._console.print(
            f"'{option['label']}' needs details best given in your own words — "
            "type your instruction instead of picking this option."
        )
        return None


class UnattendedIO:
    """Unattended steering IO: relays check-ins; a pause is a honesty violation.

    Unattended plans have no pause points, so the runner never calls ``pause``.
    If it ever does, that is a runner regression — this implementation raises.

    Args:
        console: The console seam check-ins render through.
    """

    def __init__(self, console: ConsoleIO) -> None:
        self._console = console
        self.pause_calls = 0

    def check_in(self, component: str, payload: dict[str, Any]) -> None:
        """Relay one deterministic runner check-in to the console.

        Args:
            component: Orchestration step name.
            payload: Deterministic outcome payload.
        """
        del component
        self._console.print(render_check_in(payload))

    def pause(self, point: dict[str, Any], render: str) -> SteeringResponse:
        """Raise: an unattended run must never reach a steering pause.

        Args:
            point: Pause-point payload.
            render: Deterministic pause render.

        Returns:
            Never returns.

        Raises:
            AssertionError: Always — unattended mode compiles no pause points.
        """
        del point, render
        self.pause_calls += 1
        raise AssertionError("UnattendedIO.pause called: unattended runs must not pause")


def _split_ids(raw: str) -> list[str]:
    return [token.strip() for token in raw.split(",") if token.strip()]


def _country_group_identity(raw_group: object) -> tuple[str, tuple[str, ...] | None] | None:
    if raw_group is None:
        return None
    if isinstance(raw_group, dict):
        label = raw_group.get("label")
        countries = raw_group.get("countries")
    else:
        label = getattr(raw_group, "label", None)
        countries = getattr(raw_group, "countries", None)
    if not isinstance(label, str):
        return None
    if countries is None:
        return label, None
    if not isinstance(countries, list):
        return None
    return label, tuple(str(country).upper() for country in countries)


def _assign_country_group_authorship(
    draft: PlanDraftWire,
    previous_draft: dict[str, object] | None,
    *,
    follows_user_turn: bool,
    first_countries_by_label: dict[str, tuple[str, ...] | None],
    authorship_by_label: dict[str, CountryGroupAuthorship],
) -> CountryGroupAuthorship | None:
    current = _country_group_identity(draft.country_group)
    if current is None:
        return None
    label, countries = current
    if label in TIER1_GROUPS:
        authorship_by_label[label] = "pinned-table"
        return "pinned-table"

    first = first_countries_by_label.setdefault(label, countries)
    authorship = authorship_by_label.get(label, "planner-proposed")
    previous = (
        _country_group_identity(previous_draft.get("country_group"))
        if previous_draft is not None
        else None
    )
    if first != countries:
        authorship = "user-amended"
    if (
        follows_user_turn
        and previous is not None
        and previous[0] == label
        and previous[1] != countries
    ):
        authorship = "user-amended"
    authorship_by_label[label] = authorship
    return authorship


def _default_country_group_authorship(raw_group: object) -> CountryGroupAuthorship:
    identity = _country_group_identity(raw_group)
    if identity is not None and identity[0] in TIER1_GROUPS:
        return "pinned-table"
    return "planner-proposed"


def _build_plan(
    draft: PlanDraftWire,
    *,
    country_group_authorship: CountryGroupAuthorship | None = None,
) -> OrchestrationPlan:
    """Build the executable plan from a ready draft, fail-closed.

    Drops null draft fields, folds the flat scope-constraint fields into the
    nested ``scope_constraints`` object, and lets the model validate and fill
    the derived fields (expected artefact shape, time band).

    Args:
        draft: The planner's ready plan draft.

    Returns:
        The validated orchestration plan.

    Raises:
        ValidationError: If the draft is not a valid orchestration plan.
    """
    data = draft.model_dump(exclude_none=True)
    constraints: dict[str, object] = {}
    for key in (
        "published_after",
        "published_before",
        "publisher_country",
        "author_affiliation_countries",
    ):
        if key in data:
            constraints[key] = data.pop(key)
    if "country_group" in data:
        raw_group = data.pop("country_group")
        if isinstance(raw_group, dict):
            constraints["country_group"] = {
                **raw_group,
                "authorship": country_group_authorship
                or _default_country_group_authorship(raw_group),
            }
    if constraints:
        data["scope_constraints"] = constraints
    # The wire carries a pinned option's delta JSON-encoded (strict schemas
    # cannot carry open objects); decode fail-closed — a malformed string is
    # passed through as-is so SteerPointDefault's dict validation rejects it.
    for rule in data.get("steer_point_defaults") or []:
        if isinstance(rule, dict) and "delta_json" in rule:
            raw = rule.pop("delta_json")
            if raw is not None:
                try:
                    rule["delta"] = json.loads(raw)
                except (TypeError, ValueError):
                    rule["delta"] = raw
    return OrchestrationPlan.model_validate(data)


def _render_draft(draft: PlanDraftWire) -> str:
    parts = ["Current plan draft:"]
    for label, value in (
        ("title", draft.title),
        ("question", draft.question),
        ("search_effort", draft.search_effort),
        ("analysis_depth", draft.analysis_depth),
        ("components", draft.components),
        ("grouping_facets", draft.grouping_facets),
        ("extract_profiles", draft.extract_profiles),
        ("steering_mode", draft.steering_mode),
    ):
        if value:
            if label == "steering_mode" and isinstance(value, str):
                parts.append(f"  {label}: {value} — {_mode_label(value)}")
            else:
                parts.append(f"  {label}: {value}")
    return "\n".join(parts)


def _render_scope_constraints(plan: OrchestrationPlan) -> list[str]:
    constraints = plan.scope_constraints
    if not constraints.to_filters():
        return []
    lines = ["  scope_constraints:"]
    if constraints.published_after is not None:
        lines.append(f"    published_after: {constraints.published_after}")
    if constraints.published_before is not None:
        lines.append(f"    published_before: {constraints.published_before}")
    if constraints.publisher_country is not None:
        lines.append(f"    publisher_country: {constraints.publisher_country}")
    if constraints.author_affiliation_countries is not None:
        lines.append(
            "    author_affiliation_countries: "
            f"{constraints.author_affiliation_countries}"
        )
    if constraints.country_group is not None:
        group = constraints.country_group
        if group.label in TIER1_GROUPS:
            count = len(expand_tier1(group.label))
        else:
            count = len(group.countries or [])
        authorship = (
            "pinned table" if group.authorship == "pinned-table" else group.authorship
        )
        lines.append(
            f"    Country group: {group.label} ({count} countries, {authorship})"
        )
    return lines


def _render_full_plan(plan: OrchestrationPlan) -> str:
    lines = [
        "Proposed orchestration plan:",
        f"  title: {plan.title}",
        f"  question: {plan.question}",
        f"  backend_scope: {plan.backend_scope}",
        f"  search_effort: {plan.search_effort}",
        f"  analysis_depth: {plan.analysis_depth}",
        f"  components: {plan.components}",
        f"  grouping_facets: {plan.grouping_facets}",
        f"  extract_profiles: {plan.extract_profiles}",
        f"  steering_mode: {plan.steering_mode} — {_mode_label(plan.steering_mode)}",
        f"  expected_artefact_shape: {plan.expected_artefact_shape}",
        f"  time_band: {plan.time_band}",
    ]
    if plan.scoping_notes:
        lines.append(f"  scoping_notes: {plan.scoping_notes}")
    if plan.screening_criteria:
        lines.append(f"  screening_criteria: {plan.screening_criteria}")
    lines.extend(_render_scope_constraints(plan))
    if plan.component_rationale:
        lines.append("  component_rationale:")
        for component, rationale in plan.component_rationale.items():
            lines.append(f"    - {component}: {rationale}")
    if plan.steer_point_defaults:
        lines.append(
            f"  steer_point_defaults: {[d.model_dump() for d in plan.steer_point_defaults]}"
        )
    if plan.assumptions:
        lines.append(f"  assumptions: {plan.assumptions}")
    # The delegation-posture legend (all four labels) so the mode's meaning is
    # visible at the approval surface, not just its plan value.
    lines.extend(_mode_legend_lines())
    return "\n".join(lines)


def _ask(console: ConsoleIO, question: str, suggestions: list[str] | None) -> str:
    """Render a planner question with numbered suggestions and read the answer.

    A numeric answer within range picks that suggestion; any other text is
    accepted verbatim (free text is always allowed).

    Args:
        console: The console seam.
        question: The planner's clarifying question.
        suggestions: Ordered suggested answers, or ``None``.

    Returns:
        The resolved answer text.
    """
    lines = [question]
    if suggestions:
        for index, suggestion in enumerate(suggestions, start=1):
            lines.append(f"  {index}) {suggestion}")
        lines.append("  (or type your own answer)")
    console.print("\n".join(lines))
    raw = console.prompt("> ")
    stripped = raw.strip()
    if suggestions and stripped.isdigit():
        index = int(stripped)
        if 1 <= index <= len(suggestions):
            return suggestions[index - 1]
    return raw


def _live_planner_and_backends(
    langfuse_client: Any,
) -> tuple[PlannerBackend, RunnerBackends]:
    """Build the live planner + full live backend set, mirroring skeleton.py.

    Args:
        langfuse_client: The resolved Langfuse client (tracing lives inside the
            backends, as in ``skeleton.py``).

    Returns:
        The live planner backend and the live runner backend bundle.
    """
    embedding: EmbeddingBackend = OpenAIEmbeddingBackend()
    theme_grouping: ThemeGroupingBackend = OpenAIThemeGroupingBackend()
    if langfuse_client is not None:
        embedding = tracing.TracedEmbeddingBackend(embedding, langfuse_client)
        theme_grouping = tracing.TracedThemeGroupingBackend(theme_grouping, langfuse_client)
    fetcher = LiveDocumentFetcher()
    assert fetcher.mode == "live"
    backends = RunnerBackends(
        embedding=embedding,
        theme_grouping=theme_grouping,
        screening=OpenAIScreeningBackend(langfuse_client=langfuse_client),
        classification=OpenAIClassificationBackend(langfuse_client=langfuse_client),
        ranking=OpenAIRankingBackend(langfuse_client=langfuse_client),
        extraction=OpenAIExtractionBackend(langfuse_client=langfuse_client),
        finding_vetter=OpenAIFindingVetterBackend(langfuse_client=langfuse_client),
        icf_extraction=OpenAIICFExtractionBackend(langfuse_client=langfuse_client),
        icf_finding_vetter=OpenAIICFFindingVetterBackend(
            langfuse_client=langfuse_client
        ),
        group_clustering=OpenAIGroupClusteringBackendFactory(
            langfuse_client=langfuse_client
        ),
        synthesis=OpenAISynthesisBackend(langfuse_client=langfuse_client),
        grounding_judge=OpenAIGroundingJudgeBackend(langfuse_client=langfuse_client),
        search_backends=cast(list[SearchBackend], search_live.live_search_backends()),
        search_generation=search_generation.OpenAISearchGenerationBackend(
            langfuse_client=langfuse_client
        ),
        document_fetcher=fetcher,
        langfuse_client=langfuse_client,
    )
    planner = OpenAIPlannerBackend(langfuse_client=langfuse_client)
    return planner, backends


def _seed_stub_corpus(engine: Engine, project_id: uuid.UUID) -> None:
    """Seed the egress-free demo/dev corpus for a stub run.

    Mirrors skeleton.py's ingest_upload seed: synthetic full-text reviews the
    stub classify/appraise path scores, so the chain has an appraised,
    screened-in corpus to run over without any network egress.

    Args:
        engine: SQLAlchemy engine.
        project_id: The project the corpus is ingested into.
    """
    with engine.begin() as conn:
        for locator, title in _STUB_CORPUS:
            source = get_source(locator)
            ingest_upload(
                conn,
                project_id=project_id,
                chunks=list(source.chunks),
                source_locator=locator,
                metadata={
                    "synthetic": True,
                    "title": title,
                    "abstract": f"A synthetic systematic review ({locator}).",
                    "_stub_systematic_review": True,
                },
                text_basis="full_text",
            )


def _write_plan_row(
    engine: Engine,
    *,
    plan: OrchestrationPlan,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Create project + evidence scope and insert the approved plan row.

    Approval is the user's act: the row is written ``status='approved'``,
    ``created_by='user'``, ``version=1`` in one short transaction.

    Args:
        engine: SQLAlchemy engine.
        plan: The approved orchestration plan.

    Returns:
        ``(project_id, evidence_scope_id, plan_id)``.
    """
    project_id = uuid.uuid4()
    scope_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    now = _now()
    with engine.begin() as conn:
        conn.execute(project.insert().values(project_id=project_id, created_at=now))
        conn.execute(
            evidence_scope.insert().values(
                evidence_scope_id=scope_id,
                project_id=project_id,
                intent=plan.question,
                context={},
                created_at=now,
            )
        )
        conn.execute(
            orchestration_plan.insert().values(
                plan_id=plan_id,
                project_id=project_id,
                evidence_scope_id=scope_id,
                version=1,
                status="approved",
                payload=plan.model_dump(mode="json"),
                created_at=now,
                created_by="user",
                approved_at=now,
            )
        )
    return project_id, scope_id, plan_id


def _artefact_present(engine: Engine, project_id: uuid.UUID) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            sa_select(artefact.c.artefact_id)
            .where(artefact.c.project_id == project_id)
            .limit(1)
        ).first()
    return row is not None


def _plan_conversation(
    console: ConsoleIO,
    planner: PlannerBackend,
    turns: list[dict[str, str]],
    *,
    session_id: uuid.UUID,
) -> OrchestrationPlan | Literal["abandoned", "no_plan"]:
    """Drive the planning conversation to an approved plan, or abandonment.

    Returns:
        The approved plan, ``"abandoned"`` if the user abandoned, or
        ``"no_plan"`` if the planner never converged within the turn cap.
    """
    previous_draft: dict[str, object] | None = None
    first_country_groups: dict[str, tuple[str, ...] | None] = {}
    country_group_authorship: dict[str, CountryGroupAuthorship] = {}
    for _ in range(MAX_PLANNER_TURNS):
        follows_user_turn = bool(turns and turns[-1]["role"] == "user")
        turn = planner.plan_turn(turns, previous_draft, session_id=session_id)
        assigned_country_group_authorship = _assign_country_group_authorship(
            turn.plan_draft,
            previous_draft,
            follows_user_turn=follows_user_turn,
            first_countries_by_label=first_country_groups,
            authorship_by_label=country_group_authorship,
        )
        console.print(turn.reply)
        console.print(_render_draft(turn.plan_draft))
        previous_draft = turn.plan_draft.model_dump()
        turns.append({"role": "planner", "text": turn.reply})

        if not turn.ready:
            answer = _ask(console, turn.question or "Anything to add?", turn.suggested_answers)
            turns.append({"role": "user", "text": answer})
            continue

        try:
            plan = _build_plan(
                turn.plan_draft,
                country_group_authorship=assigned_country_group_authorship,
            )
        except ValidationError as exc:
            console.print(f"The proposed plan failed validation and was not run:\n{exc}")
            response = console.prompt(
                "Describe a revision, or type 'abandon' to stop: "
            ).strip()
            if response.lower() == "abandon":
                return "abandoned"
            turns.append(
                {"role": "user", "text": f"The plan failed validation ({exc}). {response}"}
            )
            continue

        console.print(_render_full_plan(plan))
        decision = console.prompt("Approve, edit, or abandon? [approve/edit/abandon]: ")
        normalised = decision.strip().lower()
        if normalised == "approve":
            return plan
        if normalised == "abandon":
            return "abandoned"
        change = console.prompt("What would you like to change? ")
        turns.append({"role": "user", "text": change})

    console.print("Planner did not reach an approved plan within the turn cap.")
    return "no_plan"


def main(
    console: ConsoleIO | None = None,
    engine: Engine | None = None,
    planner: PlannerBackend | None = None,
    backends: RunnerBackends | None = None,
    orchestrator: OrchestratorBackend | None = None,
) -> OrchestrateResult:
    """Run one orchestrator session: plan -> approve -> run -> report.

    Args:
        console: Console seam; defaults to real stdin/stdout.
        engine: SQLAlchemy engine; defaults to the configured engine.
        planner: Planner backend; defaults to the live/stub choice by key.
        backends: Runner backend bundle; defaults to the live/stub choice by key.
        orchestrator: Orchestrator backend (router + watch moments); defaults to
            the live/stub choice by key, mirroring the planner. Threaded into
            ``run_plan`` so free-text steering compiles at pauses and the watch
            observes boundaries; the deterministic stub keeps CI zero-egress.

    Returns:
        The structured session result, including the process exit code.
    """
    configure_logging()
    conversation_id = uuid.uuid4()
    console = console if console is not None else StdConsole()
    engine = engine if engine is not None else get_engine()

    live = bool(os.environ.get("OPENAI_API_KEY"))
    langfuse_client = tracing.get_langfuse() if live else None
    default_orchestrator: OrchestratorBackend
    if live:
        default_planner, default_backends = _live_planner_and_backends(langfuse_client)
        default_orchestrator = OpenAIOrchestratorBackend(langfuse_client=langfuse_client)
    else:
        default_planner = StubPlannerBackend()
        default_backends = RunnerBackends()
        default_orchestrator = StubOrchestratorBackend()
    planner = planner if planner is not None else default_planner
    backends = backends if backends is not None else default_backends
    orchestrator = orchestrator if orchestrator is not None else default_orchestrator
    log.info(
        "orchestrate.start",
        mode="live" if live else "stub",
        session_id=str(conversation_id),
    )

    intent = console.prompt("Describe the evidence review you want: ")
    turns: list[dict[str, str]] = [{"role": "user", "text": intent}]

    plan = _plan_conversation(console, planner, turns, session_id=conversation_id)
    if isinstance(plan, str):
        console.print("No plan approved; nothing was run.")
        exit_code = EXIT_NO_PLAN if plan == "no_plan" else EXIT_ABANDONED
        return OrchestrateResult(
            exit_code=exit_code,
            turns=turns,
            conversation_id=conversation_id,
        )

    project_id, scope_id, plan_id = _write_plan_row(engine, plan=plan)
    if not live:
        _seed_stub_corpus(engine, project_id)

    runner_io: CliIO | UnattendedIO = (
        UnattendedIO(console) if plan.steering_mode == "unattended" else CliIO(console)
    )
    outcome = run_plan(
        engine,
        project_id=project_id,
        evidence_scope_id=scope_id,
        plan=plan,
        plan_id=plan_id,
        plan_version=1,
        plan_row_id=plan_id,
        backends=backends,
        io=runner_io,
        session_id=conversation_id,
        orchestrator=orchestrator,
    )

    console.print(outcome.collation_render)
    console.print(f"Run status: {outcome.status}")
    artefact_present = _artefact_present(engine, project_id)
    console.print(f"Artefact minted: {artefact_present}")

    return OrchestrateResult(
        exit_code=_EXIT_BY_STATUS[outcome.status],
        plan=plan,
        plan_id=plan_id,
        project_id=project_id,
        evidence_scope_id=scope_id,
        outcome=outcome,
        turns=turns,
        runner_io=runner_io,
        artefact_present=artefact_present,
        conversation_id=conversation_id,
    )


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main().exit_code)
