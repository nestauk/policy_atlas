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

import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.engine import Connection, RowMapping

from policy_atlas.core.schema import capability_run, evidence_scope, task, task_plan
from policy_atlas.runtime.scoping_plan import (
    BASELINE_CONFIRM,
    ScopingPlan,
    compose_scoping,
)
from policy_atlas.runtime.steering import LATTICE_POINTS, PausePoint
from policy_atlas.runtime.task_plan import ComposedChain, TaskPlan, compose

#: The Evidence search capability key. Named rather than spelled out at each
#: call site so the constant-capability readers (the ones whose *input type* is
#: already Evidence search — a ``PlanDraftWire``, a ``TaskPlan``) are greppable.
EVIDENCE_SEARCH = "evidence_search"

#: The options-scoping capability key.
OPTIONS_SCOPING = "options_scoping"

#: Either capability's plan model. The runner and the continuation reducer are
#: capability-agnostic *chassis* — they carry a plan without knowing which kind
#: it is — while almost everything they hand it to is Evidence search code
#: typed on ``TaskPlan``. Those hand-offs go through :func:`expect_task_plan`,
#: so a scoping plan reaching an Evidence search path is a loud ``TypeError``
#: and not a silent wrong answer.
AnyPlan = TaskPlan | ScopingPlan


class UnknownCapability(LookupError):
    """A capability this build has no spec for.

    Raised rather than defaulted: guessing Evidence search for an unrecognised
    value would validate the wrong model against a stored payload and compose
    the wrong chain. Fail closed.
    """


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
        task_agent_prompt_module: Dotted path of the module holding this
            capability's Task Agent prompt. A string, not the module: the
            prompt modules are hash-pinned and importing them all eagerly
            would drag every prompt into every process that reads a plan.
        lattice: Point name → the component boundary it sits on.
    """

    plan_model: type[AnyPlan]
    compose: Callable[[Any, str | None, Mapping[str, Any] | None], ComposedChain]
    task_agent_prompt_module: str
    lattice: dict[str, PausePoint]


#: The registry. Both capabilities as of phase 3.2 (X3).
CAPABILITIES: dict[str, CapabilitySpec] = {
    EVIDENCE_SEARCH: CapabilitySpec(
        plan_model=TaskPlan,
        compose=compose,
        task_agent_prompt_module="policy_atlas.runtime.task_agent_prompt",
        lattice=LATTICE_POINTS,
    ),
    OPTIONS_SCOPING: CapabilitySpec(
        plan_model=ScopingPlan,
        compose=compose_scoping,
        task_agent_prompt_module="policy_atlas.runtime.task_agent_scoping_prompt",
        # The gate is registered here as *data* — the point exists on the
        # scoping chain and nowhere else (A2), so an Evidence search walk can
        # never resolve it. Its options, card, unattended recording and
        # end-walk disposition are phase 5.2.
        lattice={BASELINE_CONFIRM: PausePoint("after_component", "synthesise")},
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
