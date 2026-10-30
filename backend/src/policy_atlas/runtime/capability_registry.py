"""One place that says what each capability's plan is, and what it composes to.

Before task 044 there was exactly one capability, so every reader of a plan
payload could name ``TaskPlan`` and ``compose`` directly. Options scoping makes
that a bug waiting to happen (C9): a payload's shape is decided by
``task.capability``, and a reader that guesses wrong either validates a scoping
plan against the Evidence search model or — worse — composes an Evidence search
chain for a scoping task. The same argument applies to the steering lattice
(A2): a flat, global point table would fire a scoping pause on an Evidence
search walk in frequent mode.

So: one :class:`CapabilitySpec` per capability, and three lookups
(:func:`validate_plan`, :func:`compose_plan`, :func:`lattice_for`) that every
reader goes through. Unknown capability is
a typed error, never a default — a row whose ``capability`` this build does not
know is a row this build must not run.

Phase 2 of task 044 built this as the chassis with the Evidence search entry
alone; phase 3.2 added the options-scoping entry, and — as designed — it cost
one more dict entry and nothing else.

A test (``tests/runtime/test_capability_registry.py``) asserts by AST scan that
``TaskPlan.model_validate`` and bare ``compose(`` appear nowhere else in
``backend/src``.
"""

from __future__ import annotations

import importlib
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, cast

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine, RowMapping

from policy_atlas.core.schema import capability_run, evidence_scope, task, task_plan
from policy_atlas.runtime.scoping_plan import (
    BASELINE_CONFIRM,
    ScopingPlan,
    compose_scoping,
)
from policy_atlas.runtime.steering import LATTICE_POINTS, PausePoint
from policy_atlas.runtime.task_plan import ComposedChain, TaskPlan, compose
from policy_atlas.runtime.toc_plan import TocPlan, compose_toc

#: The Evidence search capability key. Named rather than spelled out at each
#: call site so the constant-capability readers (the ones whose *input type* is
#: already Evidence search — a ``PlanDraftWire``, a ``TaskPlan``) are greppable.
EVIDENCE_SEARCH = "evidence_search"

#: The options-scoping capability key.
OPTIONS_SCOPING = "options_scoping"

#: The theory-of-change capability key (task 054).
THEORY_OF_CHANGE = "theory_of_change"

#: Any capability's plan model. The runner and the continuation reducer are
#: capability-agnostic *chassis* — they carry a plan without knowing which kind
#: it is — while almost everything they hand it to is Evidence search code
#: typed on ``TaskPlan``. Those hand-offs go through :func:`expect_task_plan`,
#: so a scoping plan reaching an Evidence search path is a loud ``TypeError``
#: and not a silent wrong answer.
AnyPlan = TaskPlan | ScopingPlan | TocPlan


class UnknownCapability(LookupError):
    """A capability this build has no spec for.

    Raised rather than defaulted: guessing Evidence search for an unrecognised
    value would validate the wrong model against a stored payload and compose
    the wrong chain. Fail closed.
    """


@dataclass(frozen=True)
class TaskAgentProfile:
    """What the Task Agent (the planning assistant) does for one capability.

    The turn route and the live backend read everything capability-specific
    from here, so they have one code path. Drafts, inputs and turns are typed
    loosely: each profile's functions know their own shapes.

    Args:
        capability: The capability key.
        wire: The structured-output turn model the model fills.
        build_messages: ``(turns, previous_draft, inputs)`` → chat messages,
            from the capability's hash-pinned prompt module.
        model: Model id.
        max_output_tokens: Completion token cap.
        prompt_version: Recorded on every trace.
        trace_name: Static Langfuse observation name.
        usage_event: structlog event name for usage logging.
        label: Call label for parse errors.
        load_inputs: ``(conn, task_id)`` → the extra inputs a turn needs
            (linked context, baseline state, previous plan); ``None`` when
            there are none.
        build_plan: ``(draft, inputs, turn_index)`` → the executable plan, or
            raises ``ValidationError`` / ``ValueError``.
        draft_from_plan: Approved plan → its API draft.
        draft_from_wire: ``(draft, ready, inputs)`` → the API draft of a
            not-yet-approved wire draft.
        seed_draft: Executed plan → the wire draft dict a successor
            conversation starts from.
        stub_turn: Zero-egress turn for tests and keyless runs, from the
            conversation turns alone.
        part_ids: The part (card) ids this Task Agent may propose.
        no_primary_parts: Part ids whose options carry no primary.
        degrade_suggestions: Whether malformed suggested answers are dropped.
        after_turn: Optional hook after every turn (task 054).
        after_approve: Optional ``(engine, task_id, plan, agent)`` →
            ``(plan, reply note)``, run outside any transaction once a turn
            approves a plan.
    """

    capability: str
    wire: type[BaseModel]
    build_messages: Callable[[list[dict[str, str]], dict[str, object] | None, Any], list[Any]]
    model: str
    max_output_tokens: int
    prompt_version: str
    trace_name: str
    usage_event: str
    label: str
    load_inputs: Callable[[Connection, uuid.UUID], Any]
    build_plan: Callable[[Any, Any, int], AnyPlan]
    draft_from_plan: Callable[[Any], BaseModel]
    draft_from_wire: Callable[[Any, bool, Any], BaseModel]
    seed_draft: Callable[[Any], dict[str, object]]
    stub_turn: Callable[[list[dict[str, str]]], Any]
    part_ids: frozenset[str]
    no_primary_parts: frozenset[str] = frozenset()
    degrade_suggestions: bool = False
    after_approve: (
        Callable[[Engine, uuid.UUID, Any, Any], tuple[AnyPlan, str | None]] | None
    ) = None
    #: ``(engine, task_id, turn, user_id)`` → a note added to the reply, after any
    #: turn: the theory of change stores proposed edits and clarifications here
    #: (task 054, C46, C49).
    after_turn: Callable[[Engine, uuid.UUID, Any, str], str | None] | None = None


@dataclass(frozen=True)
class CapabilitySpec:
    """Everything a reader needs to know about one kind of work.

    Args:
        plan_model: The pydantic model that validates this capability's plan
            payload.
        compose: Builds the deterministic component chain from a validated
            plan of ``plan_model``, the intent record's ``purpose`` and its
            ``context`` (task 045: options scoping composes a different chain
            per purpose; task 046: a targeted record's context can mark it
            acquire-only; the Evidence search ignores both).
        lattice: Point name → the component boundary it sits on.
        load_task_agent: Returns the capability's :class:`TaskAgentProfile`.
            A loader, not the profile: the profile modules import this
            registry (and the Evidence search one imports ``runtime.agent``,
            which imports it too), and a plan reader should not pull in every
            prompt.
    """

    plan_model: type[AnyPlan]
    compose: Callable[[Any, str | None, Mapping[str, Any] | None], ComposedChain]
    lattice: dict[str, PausePoint]
    load_task_agent: Callable[[], TaskAgentProfile]

    @property
    def task_agent(self) -> TaskAgentProfile:
        """The capability's Task Agent profile."""
        return self.load_task_agent()


def _evidence_search_task_agent() -> TaskAgentProfile:
    from policy_atlas.runtime.task_agent import EVIDENCE_SEARCH_TASK_AGENT

    return EVIDENCE_SEARCH_TASK_AGENT


def _options_scoping_task_agent() -> TaskAgentProfile:
    from policy_atlas.runtime.task_agent_scoping import OPTIONS_SCOPING_TASK_AGENT

    return OPTIONS_SCOPING_TASK_AGENT


def _toc_task_agent() -> TaskAgentProfile:
    # By name: the profile module lands in task 054 step 1.3, and nothing may
    # import it before a turn asks for it.
    module = importlib.import_module("policy_atlas.runtime.task_agent_toc")
    return cast(TaskAgentProfile, module.TOC_TASK_AGENT)


#: The registry: Evidence search, options scoping (task 044), theory of change (task 054).
CAPABILITIES: dict[str, CapabilitySpec] = {
    EVIDENCE_SEARCH: CapabilitySpec(
        plan_model=TaskPlan,
        compose=compose,
        lattice=LATTICE_POINTS,
        load_task_agent=_evidence_search_task_agent,
    ),
    OPTIONS_SCOPING: CapabilitySpec(
        plan_model=ScopingPlan,
        compose=compose_scoping,
        # The gate is registered here as *data* — the point exists on the
        # scoping chain and nowhere else (A2), so an Evidence search walk can
        # never resolve it. Its options, card, unattended recording and
        # end-walk disposition are phase 5.2.
        lattice={BASELINE_CONFIRM: PausePoint("after_component", "synthesise")},
        load_task_agent=_options_scoping_task_agent,
    ),
    THEORY_OF_CHANGE: CapabilitySpec(
        plan_model=TocPlan,
        compose=compose_toc,
        # Empty: a theory-of-change walk never pauses (C12).
        lattice={},
        load_task_agent=_toc_task_agent,
    ),
}


def spec_for(capability: str) -> CapabilitySpec:
    """Return one capability's spec.

    Args:
        capability: A stored capability value.

    Returns:
        The spec.

    Raises:
        UnknownCapability: If no spec is registered for the value.
    """
    try:
        return CAPABILITIES[capability]
    except KeyError:
        raise UnknownCapability(
            f"no capability spec for {capability!r} "
            f"(known: {sorted(CAPABILITIES)})"
        ) from None


def validate_plan(capability: str, payload: Mapping[str, Any] | Any) -> AnyPlan:
    """Validate a stored plan payload against its capability's model.

    Args:
        capability: The owning task's capability.
        payload: The raw stored payload.

    Returns:
        The validated plan, typed as the capability's ``plan_model``.

    Raises:
        UnknownCapability: If the capability is not registered.
        ValidationError: If the payload does not satisfy the model.
    """
    return spec_for(capability).plan_model.model_validate(payload)


def compose_plan(
    capability: str,
    plan: AnyPlan,
    *,
    purpose: str | None = None,
    context: Mapping[str, Any] | None = None,
) -> ComposedChain:
    """Compose a validated plan into its capability's component chain.

    Args:
        capability: The owning task's capability.
        plan: A plan already validated by :func:`validate_plan`.
        purpose: The walk's intent-record ``purpose`` (ADR 0039 decision 2),
            read by the caller from ``evidence_scope.purpose`` — on the fresh
            path and on both resume paths, so a parked walk recomposes the
            chain it started on. ``None`` for every Evidence search walk and
            every pre-045 scoping walk.
        context: The walk's intent-record ``context``, read beside the
            purpose (ADR 0040 decision 1: the chain is recoverable from the
            purpose and the context). ``None`` where the caller has none.

    Returns:
        The composed chain.

    Raises:
        UnknownCapability: If the capability is not registered.
    """
    return spec_for(capability).compose(plan, purpose, context)


def lattice_for(capability: str) -> dict[str, PausePoint]:
    """Return the steering lattice belonging to one capability (A2).

    Args:
        capability: The owning task's capability.

    Returns:
        Point name → component boundary, for that capability's chain only.

    Raises:
        UnknownCapability: If the capability is not registered.
    """
    return spec_for(capability).lattice


def capability_of_task(conn: Connection, task_id: uuid.UUID) -> str:
    """Read one task's capability.

    One indexed primary-key lookup. Readers that already hold the task row
    should take ``row["capability"]`` instead; this is for the readers whose
    query starts at the plan.

    Args:
        conn: Open database connection.
        task_id: The task.

    Returns:
        The stored capability value.

    Raises:
        LookupError: If the task does not exist.
    """
    value = conn.execute(
        select(task.c.capability).where(task.c.task_id == task_id)
    ).scalar_one_or_none()
    if value is None:
        raise LookupError(f"task {task_id} does not exist")
    return str(value)


def intent_record(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    walk_id: uuid.UUID | None = None,
    scope_id: uuid.UUID | None = None,
) -> tuple[str | None, dict[str, Any]]:
    """Read the ``purpose`` and ``context`` of one intent record.

    The purpose selects the chain :func:`compose_plan` composes (task 045) and
    the context composes beside it. Pass ``walk_id`` to read the record a walk
    runs under (through its ``evidence_scope_id``; both rows are task-scoped),
    or ``scope_id`` to read a record directly.

    Args:
        conn: Open database connection.
        task_id: The task owning the record.
        walk_id: The walk whose record is wanted.
        scope_id: The record itself.

    Returns:
        The purpose (``None`` for a record that carries none, as every
        Evidence search record) and the context mapping (empty when the stored
        value is not a mapping).

    Raises:
        LookupError: If the walk or record does not exist for the task.
    """
    columns = select(evidence_scope.c.purpose, evidence_scope.c.context)
    if walk_id is not None:
        query = (
            columns.select_from(
                capability_run.join(
                    evidence_scope,
                    (evidence_scope.c.evidence_scope_id == capability_run.c.evidence_scope_id)
                    & (evidence_scope.c.task_id == capability_run.c.task_id),
                )
            )
            .where(capability_run.c.task_id == task_id)
            .where(capability_run.c.capability_run_id == walk_id)
        )
        missing = f"capability run {walk_id} does not exist"
    else:
        query = (
            columns.where(evidence_scope.c.task_id == task_id)
            .where(evidence_scope.c.evidence_scope_id == scope_id)
        )
        missing = f"intent record {scope_id} does not exist"
    row = conn.execute(query).one_or_none()
    if row is None:
        raise LookupError(missing)
    purpose = None if row.purpose is None else str(row.purpose)
    context = dict(row.context) if isinstance(row.context, Mapping) else {}
    return purpose, context


def purpose_of_scope(
    conn: Connection, *, task_id: uuid.UUID, evidence_scope_id: uuid.UUID
) -> str | None:
    """Read one intent record's ``purpose`` (see :func:`intent_record`)."""
    return intent_record(conn, task_id=task_id, scope_id=evidence_scope_id)[0]


def context_of_scope(
    conn: Connection, *, task_id: uuid.UUID, evidence_scope_id: uuid.UUID
) -> dict[str, Any]:
    """Read one intent record's ``context`` (see :func:`intent_record`)."""
    return intent_record(conn, task_id=task_id, scope_id=evidence_scope_id)[1]


def latest_approved_plan_row(conn: Connection, task_id: uuid.UUID) -> RowMapping | None:
    """Return the task's current approved ``task_plan`` row, or ``None`` before the first.

    Args:
        conn: Open database connection.
        task_id: The task.

    Returns:
        The highest-version approved row.
    """
    return conn.execute(
        select(task_plan)
        .where(task_plan.c.task_id == task_id)
        .where(task_plan.c.status == "approved")
        .order_by(task_plan.c.version.desc())
        .limit(1)
    ).mappings().one_or_none()


def expect_task_plan(plan: BaseModel) -> TaskPlan:
    """Narrow a registry-validated plan to the Evidence search model.

    The Evidence search code paths this slice leaves alone — the steering
    router, the plan-draft projection, the runner's step loop — are typed on
    ``TaskPlan`` and read its fields. Routing their validation through the
    registry keeps the single seam; this puts the type back afterwards, loudly,
    rather than with a ``cast`` that would go quiet the day a scoping plan
    reaches one of them.

    Args:
        plan: A plan returned by :func:`validate_plan`.

    Returns:
        The same object, typed.

    Raises:
        TypeError: If the plan is not an Evidence search plan.
    """
    if not isinstance(plan, TaskPlan):
        raise TypeError(
            f"this path handles Evidence search plans only, got {type(plan).__name__}"
        )
    return plan


def expect_scoping_plan(plan: BaseModel) -> ScopingPlan:
    """Narrow a registry-validated plan to the options-scoping model.

    The mirror of :func:`expect_task_plan` for the scoping paths.

    Args:
        plan: A plan returned by :func:`validate_plan`.

    Returns:
        The same object, typed.

    Raises:
        TypeError: If the plan is not an options-scoping plan.
    """
    if not isinstance(plan, ScopingPlan):
        raise TypeError(f"this path handles scoping plans only, got {type(plan).__name__}")
    return plan


def expect_toc_plan(plan: BaseModel) -> TocPlan:
    """Narrow a registry-validated plan to the theory-of-change model.

    The mirror of :func:`expect_task_plan` for the theory-of-change paths.

    Args:
        plan: A plan returned by :func:`validate_plan`.

    Returns:
        The same object, typed.

    Raises:
        TypeError: If the plan is not a theory-of-change plan.
    """
    if not isinstance(plan, TocPlan):
        raise TypeError(
            f"this path handles theory-of-change plans only, got {type(plan).__name__}"
        )
    return plan
