"""One place that says what each capability's plan is, and what it composes to.

Before task 044 there was exactly one capability, so every reader of a plan
payload could name ``TaskPlan`` and ``compose`` directly. Options scoping makes
that a bug waiting to happen (C9): a payload's shape is decided by
``task.capability``, and a reader that guesses wrong either validates a scoping
plan against the Evidence search model or — worse — composes an Evidence search
chain for a scoping task. The same argument applies to the steering lattice
(A2): a flat, global point table would fire a scoping pause on an Evidence
search walk in frequent mode.

So: one :class:`CapabilitySpec` per capability, and four lookups
(:func:`validate_plan`, :func:`compose_plan`, :func:`lattice_for`,
:func:`steer_points_for`) that every reader goes through. Unknown capability is
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
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import capability_run, evidence_scope, task
from policy_atlas.runtime.scoping_plan import (
    BASELINE_CONFIRM,
    SCOPING_STEER_POINTS,
    ScopingPlan,
    compose_scoping,
)
from policy_atlas.runtime.steering import LATTICE_POINTS, PausePoint
from policy_atlas.runtime.task_plan import STEER_POINTS, ComposedChain, TaskPlan, compose

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
        key: The stored ``task.capability`` / ``capability_run.capability``
            value.
        plan_model: The pydantic model that validates this capability's plan
            payload.
        compose: Builds the deterministic component chain from a validated
            plan of ``plan_model`` and the intent record's ``purpose`` (task
            045: options scoping composes a different chain per purpose; the
            Evidence search ignores it).
        task_agent_prompt_module: Dotted path of the module holding this
            capability's Task Agent prompt. A string, not the module: the
            prompt modules are hash-pinned and importing them all eagerly
            would drag every prompt into every process that reads a plan.
        steer_points: The lattice point names a plan of this capability may
            pre-declare standing defaults for.
        lattice: Point name → the component boundary it sits on.
    """

    key: str
    plan_model: type[AnyPlan]
    compose: Callable[[Any, str | None], ComposedChain]
    task_agent_prompt_module: str
    steer_points: frozenset[str]
    lattice: dict[str, PausePoint]


#: The registry. Both capabilities as of phase 3.2 (X3).
CAPABILITIES: dict[str, CapabilitySpec] = {
    EVIDENCE_SEARCH: CapabilitySpec(
        key=EVIDENCE_SEARCH,
        plan_model=TaskPlan,
        compose=compose,
        task_agent_prompt_module="policy_atlas.runtime.task_agent_prompt",
        steer_points=frozenset(STEER_POINTS),
        lattice=LATTICE_POINTS,
    ),
    OPTIONS_SCOPING: CapabilitySpec(
        key=OPTIONS_SCOPING,
        plan_model=ScopingPlan,
        compose=compose_scoping,
        task_agent_prompt_module="policy_atlas.runtime.task_agent_scoping_prompt",
        steer_points=SCOPING_STEER_POINTS,
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
    capability: str, plan: AnyPlan, *, purpose: str | None = None
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

    Returns:
        The composed chain.

    Raises:
        UnknownCapability: If the capability is not registered.
    """
    return spec_for(capability).compose(plan, purpose)


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


def steer_points_for(capability: str) -> frozenset[str]:
    """Return the steer-point names a plan of one capability may name (A18d).

    Args:
        capability: The owning task's capability.

    Returns:
        The valid standing-default point names.

    Raises:
        UnknownCapability: If the capability is not registered.
    """
    return spec_for(capability).steer_points


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


def purpose_of_walk(
    conn: Connection, *, task_id: uuid.UUID, capability_run_id: uuid.UUID
) -> str | None:
    """Read the ``purpose`` of the intent record one walk runs under.

    The purpose selects the chain :func:`compose_plan` composes (task 045).
    It lives on the intent record, not the walk, so it is read through the
    walk's ``evidence_scope_id``; both rows are task-scoped.

    Args:
        conn: Open database connection.
        task_id: The task owning the walk.
        capability_run_id: The walk.

    Returns:
        The purpose, or ``None`` for an intent record that carries none (every
        Evidence search record).

    Raises:
        LookupError: If the walk does not exist for the task.
    """
    row = conn.execute(
        select(evidence_scope.c.purpose)
        .select_from(
            capability_run.join(
                evidence_scope,
                (evidence_scope.c.evidence_scope_id == capability_run.c.evidence_scope_id)
                & (evidence_scope.c.task_id == capability_run.c.task_id),
            )
        )
        .where(capability_run.c.task_id == task_id)
        .where(capability_run.c.capability_run_id == capability_run_id)
    ).one_or_none()
    if row is None:
        raise LookupError(f"capability run {capability_run_id} does not exist")
    return None if row.purpose is None else str(row.purpose)


def purpose_of_scope(
    conn: Connection, *, task_id: uuid.UUID, evidence_scope_id: uuid.UUID
) -> str | None:
    """Read one intent record's ``purpose``.

    Args:
        conn: Open database connection.
        task_id: The task owning the record.
        evidence_scope_id: The intent record.

    Returns:
        The purpose, or ``None`` when the record carries none.

    Raises:
        LookupError: If the record does not exist for the task.
    """
    row = conn.execute(
        select(evidence_scope.c.purpose)
        .where(evidence_scope.c.task_id == task_id)
        .where(evidence_scope.c.evidence_scope_id == evidence_scope_id)
    ).one_or_none()
    if row is None:
        raise LookupError(f"intent record {evidence_scope_id} does not exist")
    return None if row.purpose is None else str(row.purpose)


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
