"""The longlist's PICO-shaped intent and its screening criteria (task 045; task 046).

Both are compiled deterministically from the approved scoping plan:

- **P** — the target unit (who or what should change), with its place removed
  by :func:`~policy_atlas.options_scoping.longlist.where_tried.strip_place`
  (task 046, S6), and judged wide: a wider or adjacent population passes;
- **I** — left open: any intervention;
- **O** — the plan's outcomes.

There is no C (no comparison before assessment), **no setting** and **no
place** (task 046, S7, R19; reopens 045 D21): the screen's error is neither
visible nor reversible, so it judges wide, and a setting requirement is
checked by constrain (:func:`setting_requirements`). Where enters nothing in
the longlist's retrieval chain; it is shown on the way out as *where tried*
and returns at transferability (task 3).

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

    A setting requirement is a ``boundary`` constraint the Task Agent
    marked ``setting=True`` (it names the delivery setting the options must
    be delivered through). This is how code knows one exists (D21).

    Args:
        plan: The validated scoping plan.

    Returns:
        The requirement texts; empty when the plan states no setting.
    """
    return [c.text for c in plan.constraints if c.kind == "boundary" and c.setting]


def _slot(text: str) -> str:
    """One slot's text with its trailing full stops removed, so no ".." appears."""
    return text.strip().rstrip(".").rstrip()


def _outcomes(plan: ScopingPlan) -> str:
    return "; ".join(_slot(outcome.text) for outcome in plan.outcomes)


def screen_target_unit(plan: ScopingPlan) -> tuple[str, list[str]]:
    """Return the target unit the screen reads, and the place spans removed.

    The plan's target unit after :func:`strip_place` against the plan's Where
    (task 046, S6), with its trailing full stops removed.

    Args:
        plan: The validated scoping plan.

    Returns:
        ``(target_unit, removed)``: the text the intent and the criteria
        compose, and the removed spans in removal order (empty when the
        target unit names no place). The longlist start surface records
        ``removed`` in the longlist scope's context as ``place_removed``.
    """
    cleaned, removed = strip_place(plan.target_unit.text, plan.where.text)
    return _slot(cleaned), removed


def _place_sentence(plan: ScopingPlan) -> str:
    """The place rule in words, naming the user's place from the plan's Where (R74, 18P).

    The strip stays (M4 did not hold on the replays without it: the round record of 18P);
    this sentence is the rule the prompts carry beside it. No list of names: the plan's
    Where field is the only text used.

    Args:
        plan: The validated scoping plan.

    Returns:
        One sentence: the user's place is not a criterion; a study anywhere passes.
    """
    where = _slot(plan.where.text) if plan.where.text.strip() else ""
    named = f"The user works in {where}: that place," if where else "A place named above,"
    return (
        f"{named} and any place named in the group above, is the user's place, not a "
        "criterion. A study in another country, region or city passes; judge the document "
        "as if no place were named."
    )


def compile_longlist_intent(plan: ScopingPlan) -> str:
    """Compile the longlist intent record's text from the plan (PICO-shaped).

    Deterministic: the same plan always gives the same intent. Contains the
    place-stripped target unit and the outcomes; never a setting, Where, a
    place or a comparison (task 046, S7).

    Args:
        plan: The validated scoping plan.

    Returns:
        The intent paragraph.
    """
    target_unit, _ = screen_target_unit(plan)
    return " ".join(
        [
            f"Interventions for {target_unit}.",
            "Intervention: any intervention, programme or policy (left open).",
            f"Outcomes: {_outcomes(plan)}.",
            _place_sentence(plan),
        ]
    )


def longlist_screening_criteria(plan: ScopingPlan) -> list[str]:
    """Compose the longlist screen's criteria from the plan, as data.

    Exactly two criteria (task 046, S7): the wide target unit (a wider or
    adjacent population passes) and the outcomes. No setting criterion and no
    place. The same criteria screen the longlist scope and the verb *add*'s
    option search, whose intent is the option's design (AM1). The screen
    composes them with its intent under its 2,000-character ceiling and
    refuses (never truncates) an over-long list;
    ``scoping_plan.compose_longlist_screen_intent`` runs that check up front.

    Args:
        plan: The validated scoping plan.

    Returns:
        The two criteria, in order.
    """
    target_unit, _ = screen_target_unit(plan)
    return [
        f"{_place_sentence(plan)} The document evaluates, describes or proposes an "
        f"intervention, programme or policy aimed at {target_unit}, or at a wider or "
        "adjacent group, anywhere in the world.",
        f"It bears on at least one of these outcomes: {_outcomes(plan)}.",
    ]


def longlist_plan_data(plan: ScopingPlan) -> dict[str, object]:
    """The plan fields the longlist's discovery and typing prompts read, as data.

    The question, the intended change and the target unit pass through the
    place strip (S6) against the plan's Where; the outcomes do not (task 046,
    items 1, 7, 9). Where itself is not included.

    Args:
        plan: The validated scoping plan.

    Returns:
        ``{"question", "intended_change", "target_unit", "outcomes"}``.
    """
    where = plan.where.text
    question, _ = strip_place(plan.question, where)
    intended_change, _ = strip_place(plan.intended_change.text, where)
    target_unit, _ = strip_place(plan.target_unit.text, where)
    return {
        "question": question,
        "intended_change": intended_change,
        "target_unit": target_unit,
        "outcomes": [outcome.text for outcome in plan.outcomes],
    }


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
