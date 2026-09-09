"""The capability registry: the Evidence search entry, fail-closed, one seam.

Phase 2 of task 044 installs the registry as a chassis with the ES entry only
(X3). What these tests pin is the *seam*, not the second capability: that the
ES entry resolves to exactly what the Evidence search code used before, that an
unknown capability raises rather than defaulting, and — the one that keeps
paying — that no module in ``backend/src`` still reaches past the registry to
``TaskPlan.model_validate`` or bare ``compose``.
"""

from __future__ import annotations

import ast
import uuid
from pathlib import Path

import pytest
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import task
from policy_atlas.runtime import capability_registry as registry
from policy_atlas.runtime.steering import LATTICE_POINTS
from policy_atlas.runtime.task_plan import STEER_POINTS, TaskPlan, compose
from tests.helpers import now

#: The only files allowed to name ``TaskPlan.model_validate`` or bare
#: ``compose(``. Relative to ``backend/src/policy_atlas``.
_ALLOWED_DIRECT_CALLERS = frozenset(
    {
        # The registry itself — it is the seam.
        "runtime/capability_registry.py",
        # The definitions.
        "runtime/task_plan.py",
    }
)

_SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "policy_atlas"


def _plan_payload() -> dict[str, object]:
    """A minimal valid Evidence search plan payload."""
    return {
        "title": "NEET outreach",
        "question": "What works for NEET outreach?",
        "backend_scope": "both",
        "scope_constraints": {},
        "search_effort": "rapid",
        "analysis_depth": "landscape",
        "components": [],
        "steering_mode": "moderate",
    }


def test_the_evidence_search_entry_resolves_to_what_the_es_code_already_used() -> None:
    spec = registry.spec_for(registry.EVIDENCE_SEARCH)
    assert spec.key == "evidence_search"
    assert spec.plan_model is TaskPlan
    assert spec.compose is compose
    assert spec.task_agent_prompt_module == "policy_atlas.runtime.task_agent_prompt"
    assert spec.lattice is LATTICE_POINTS
    assert spec.steer_points == frozenset(STEER_POINTS)


def test_the_registry_holds_the_two_capabilities_this_build_knows() -> None:
    # Phase 2 built the chassis with Evidence search alone; phase 3.2 added
    # ``options_scoping`` with ``ScopingPlan``. A third capability is a third
    # entry, and until it exists a task carrying its key must fail closed
    # rather than quietly composing an Evidence search chain.
    assert set(registry.CAPABILITIES) == {"evidence_search", "options_scoping"}


def test_validate_plan_returns_the_capability_s_model() -> None:
    plan = registry.validate_plan(registry.EVIDENCE_SEARCH, _plan_payload())
    assert isinstance(plan, TaskPlan)
    assert plan.question == "What works for NEET outreach?"


def test_compose_plan_matches_the_direct_composer() -> None:
    plan = registry.expect_task_plan(
        registry.validate_plan(registry.EVIDENCE_SEARCH, _plan_payload())
    )
    assert registry.compose_plan(registry.EVIDENCE_SEARCH, plan) == compose(plan)


@pytest.mark.parametrize(
    "call",
    [
        lambda: registry.spec_for("options_appraisal"),
        lambda: registry.validate_plan("options_appraisal", _plan_payload()),
        lambda: registry.lattice_for("theory_of_change"),
        lambda: registry.steer_points_for(""),
    ],
)
def test_an_unknown_capability_fails_closed(call) -> None:  # type: ignore[no-untyped-def]
    # Fail closed, not "default to Evidence search": guessing would validate
    # the wrong model against a stored payload and compose the wrong chain.
    with pytest.raises(registry.UnknownCapability):
        call()


class _NotATaskPlan(BaseModel):
    """Stands in for the scoping plan model phase 3 adds."""


def test_expect_task_plan_refuses_a_plan_that_is_not_an_evidence_search_one() -> None:
    # The Evidence search paths this slice leaves alone read ``TaskPlan``
    # fields. When a scoping plan reaches one of them in a later phase it must
    # say so, not carry on with a silent ``cast``.
    with pytest.raises(TypeError):
        registry.expect_task_plan(_NotATaskPlan())


def test_capability_of_task_reads_the_task_row(conn: Connection) -> None:
    task_id = uuid.uuid4()
    conn.execute(
        task.insert().values(
            task_id=task_id,
            name="A task",
            status="active",
            created_at=now(),
            updated_at=now(),
        )
    )
    # The column default is the truth for every pre-044 row.
    assert registry.capability_of_task(conn, task_id) == "evidence_search"
    conn.execute(
        task.update().where(task.c.task_id == task_id).values(capability="options_scoping")
    )
    assert registry.capability_of_task(conn, task_id) == "options_scoping"
    assert (
        conn.execute(select(task.c.capability).where(task.c.task_id == task_id)).scalar_one()
        == "options_scoping"
    )


def test_capability_of_task_raises_for_a_task_that_does_not_exist(conn: Connection) -> None:
    with pytest.raises(LookupError):
        registry.capability_of_task(conn, uuid.uuid4())


# --- The seam test (C9) ----------------------------------------------------


def _direct_calls(tree: ast.AST) -> set[str]:
    """Return the banned call spellings found in one module's AST.

    ``TaskPlan.model_validate(...)`` and a bare ``compose(...)`` both mean
    "this reader decided the capability itself".
    """
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "model_validate"
            and isinstance(func.value, ast.Name)
            and func.value.id == "TaskPlan"
        ):
            found.add("TaskPlan.model_validate")
        if isinstance(func, ast.Name) and func.id == "compose":
            found.add("compose")
    return found


def test_no_module_validates_or_composes_a_plan_outside_the_registry() -> None:
    offenders: dict[str, set[str]] = {}
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        relative = path.relative_to(_SRC_ROOT).as_posix()
        if relative in _ALLOWED_DIRECT_CALLERS:
            continue
        calls = _direct_calls(ast.parse(path.read_text()))
        if calls:
            offenders[relative] = calls
    assert offenders == {}, (
        "these modules pick a plan model or a chain composer for themselves; "
        "route them through runtime/capability_registry.py instead: "
        f"{offenders}"
    )


def test_the_seam_test_would_notice_a_direct_call() -> None:
    # A guard on the guard: an AST scan that matched nothing would pass this
    # suite silently for the rest of the project's life.
    assert _direct_calls(ast.parse("TaskPlan.model_validate(payload)")) == {
        "TaskPlan.model_validate"
    }
    assert _direct_calls(ast.parse("chain = compose(plan)")) == {"compose"}
    assert _direct_calls(ast.parse("chain = compose_plan(capability, plan)")) == set()
