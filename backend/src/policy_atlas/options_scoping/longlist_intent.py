"""The longlist's PICO-shaped intent and its screening criteria (task 045, D20, D21).

Both are compiled deterministically from the approved scoping plan:

- **P** — the target unit (who or what should change);
- **I** — left open: any intervention;
- **O** — the plan's outcomes;
- **S** — the delivery setting, **only** when the user stated one as a
  requirement (a constraint with ``setting=True``, D21).

There is no C (no comparison before assessment) and **no place**: Where
enters nothing in the longlist's retrieval chain — not the intent, not query
generation, not the screen, not acquisition ranking (D20 as amended; ADR 0039
decision 10). Where is shown on the way out as *where tried* and returns at
transferability (task 3).

The plan model imports this module for its chain directives, so the plan type
is imported for type checking only; the functions read plain attributes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from policy_atlas.evidence_search.extract.interventions_records import TaggingContext
from policy_atlas.options_scoping.longlist.where_tried import strip_place

if TYPE_CHECKING:
    from policy_atlas.runtime.scoping_plan import ScopingPlan


def setting_requirements(plan: ScopingPlan) -> list[str]:
    """Return the texts of the plan's setting requirements, in plan order.

    A setting requirement is a ``requirement`` constraint the Task Agent
    marked ``setting=True`` (it names the delivery setting the options must
    be delivered through). This is how code knows one exists (D21).

    Args:
        plan: The validated scoping plan.

    Returns:
        The requirement texts; empty when the plan states no setting.
    """
    return [c.text for c in plan.constraints if c.kind == "requirement" and c.setting]


def _outcomes(plan: ScopingPlan) -> str:
    return "; ".join(outcome.text for outcome in plan.outcomes)


def compile_longlist_intent(plan: ScopingPlan) -> str:
    """Compile the longlist intent record's text from the plan (PICO-shaped).

    Deterministic: the same plan always gives the same intent. Contains the
    target unit and the outcomes, the setting only when a setting requirement
    exists, and never Where or a comparison.

    Args:
        plan: The validated scoping plan.

    Returns:
        The intent paragraph.
    """
    parts = [
        f"Interventions for {plan.target_unit.text}.",
        "Intervention: any intervention, programme or policy (left open).",
        f"Outcomes: {_outcomes(plan)}.",
    ]
    settings = setting_requirements(plan)
    if settings:
        parts.append(f"Setting: {'; '.join(settings)}.")
    return " ".join(parts)


def longlist_screening_criteria(plan: ScopingPlan) -> list[str]:
    """Compose the longlist screen's criteria from the plan, as data.

    The target unit, the outcomes and — only when required — the setting;
    **no place** (D20). The same criteria screen the broad search and every
    option search (the targeted chain), whose intent is the entrant's design.
    The screen composes them with its intent under its 2,000-character
    ceiling and refuses (never truncates) an over-long list;
    ``scoping_plan.compose_longlist_screen_intent`` runs that check up front.

    Args:
        plan: The validated scoping plan.

    Returns:
        The criteria, in order.
    """
    criteria = [
        "The document evaluates, describes or proposes an intervention, "
        f"programme or policy aimed at {plan.target_unit.text}.",
        f"It bears on at least one of these outcomes: {_outcomes(plan)}.",
    ]
    settings = setting_requirements(plan)
    if settings:
        criteria.append(
            f"The intervention is delivered through the required setting: {'; '.join(settings)}."
        )
    return criteria


def plan_tagging_context(plan: ScopingPlan) -> TaggingContext:
    """Build the intervention profile's tagging context from the plan (task 046, S4).

    The target unit and the intended change pass through the place strip
    (S6) against the plan's Where; the outcomes do not. Deterministic: the
    same plan always gives the same context, so the same ``context_hash``.
    Where itself never enters the context.

    Args:
        plan: The validated scoping plan.

    Returns:
        The tagging context.
    """
    where = plan.where.text
    target_unit, _ = strip_place(plan.target_unit.text, where)
    intended_change, _ = strip_place(plan.intended_change.text, where)
    return TaggingContext(
        target_unit=target_unit,
        outcomes=tuple(outcome.text for outcome in plan.outcomes),
        intended_change=intended_change,
    )
