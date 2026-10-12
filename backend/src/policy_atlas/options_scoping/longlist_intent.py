"""The longlist's PICO-shaped intent and its screening criteria (task 045; task 046).

Both are compiled deterministically from the approved scoping plan:

- **P** — the target unit (who or what should change), as the plan holds it,
  judged wide: a wider or adjacent population passes;
- **I** — left open: any intervention;
- **O** — the plan's outcomes.

There is no C (no comparison before assessment) and **no setting** (task 046,
S7, R19; reopens 045 D21): the screen's error is neither visible nor
reversible, so it judges wide, and a setting requirement is checked by
constrain (:func:`setting_requirements`). A place in the plan's words is the
user's place, not a criterion: the rule is words in every prompt
(:func:`_place_sentence`; R74). The plan-text strip of S6 was deleted on the
owner's ruling at the review (2026-10-12). Where is never a filter in the
longlist's retrieval chain; it is shown on the way out as *where tried* and
returns at transferability (task 3).

The plan model imports this module for its chain directives, so the plan type
is imported for type checking only; the functions read plain attributes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from policy_atlas.evidence_search.extract.interventions_records import TaggingContext

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


def screen_target_unit(plan: ScopingPlan) -> str:
    """Return the target unit the screen reads.

    The plan's target unit as the plan holds it, with its trailing full
    stops removed. A place in it is the user's place, not a criterion
    (:func:`_place_sentence`; R74).

    Args:
        plan: The validated scoping plan.

    Returns:
        The text the intent and the criteria compose.
    """
    return _slot(plan.target_unit.text)


def _place_sentence(plan: ScopingPlan) -> str:
    """The place rule in words, naming the user's place from the plan's Where (R74, 18P).

    The plan's words reach the prompts with their place (the strip of S6 was deleted
    on the owner's ruling at the review, 2026-10-12); this sentence is the rule the
    prompts carry. No list of names: the plan's Where field is the only text used.

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
    target unit as the plan holds it and the outcomes; never a setting or a
    comparison; Where is named once, inside the place rule (task 046, S7; R74).

    Args:
        plan: The validated scoping plan.

    Returns:
        The intent paragraph.
    """
    target_unit = screen_target_unit(plan)
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
    adjacent population passes) and the outcomes. No setting criterion; the
    place rule in words (R74). The same criteria screen the longlist scope and the verb *add*'s
    option search, whose intent is the option's design (AM1). The screen
    composes them with its intent under its 2,000-character ceiling and
    refuses (never truncates) an over-long list;
    ``scoping_plan.compose_longlist_screen_intent`` runs that check up front.

    Args:
        plan: The validated scoping plan.

    Returns:
        The two criteria, in order.
    """
    target_unit = screen_target_unit(plan)
    return [
        f"{_place_sentence(plan)} The document evaluates, describes or proposes an "
        f"intervention, programme or policy aimed at {target_unit}, or at a wider or "
        "adjacent group, anywhere in the world.",
        f"It bears on at least one of these outcomes: {_outcomes(plan)}.",
    ]


def longlist_plan_data(plan: ScopingPlan) -> dict[str, object]:
    """The plan fields the longlist's discovery and typing prompts read, as data.

    The question, the intended change, the target unit and the outcomes as
    the plan holds them (task 046, items 1, 7, 9; the place rule is words in
    the prompts, R74). Where itself is not included.

    Args:
        plan: The validated scoping plan.

    Returns:
        ``{"question", "intended_change", "target_unit", "outcomes"}``.
    """
    return {
        "question": plan.question,
        "intended_change": plan.intended_change.text,
        "target_unit": plan.target_unit.text,
        "outcomes": [outcome.text for outcome in plan.outcomes],
    }


def plan_tagging_context(plan: ScopingPlan) -> TaggingContext:
    """Build the intervention profile's tagging context from the plan (task 046, S4).

    The target unit, the intended change and the outcomes as the plan holds
    them (the place rule is words in the prompt, R74). Deterministic: the
    same plan always gives the same context, so the same ``context_hash``.
    Where itself never enters the context.

    Args:
        plan: The validated scoping plan.

    Returns:
        The tagging context.
    """
    return TaggingContext(
        target_unit=plan.target_unit.text,
        outcomes=tuple(outcome.text for outcome in plan.outcomes),
        intended_change=plan.intended_change.text,
    )


def who_decides_considerations(plan: ScopingPlan) -> list[str]:
    """The texts of the plan's considerations on who decides, in plan order (R38).

    Args:
        plan: The validated scoping plan.

    Returns:
        The texts; empty when the plan holds none.
    """
    return [
        c.text for c in plan.constraints if c.kind == "consideration" and c.aspect == "who_decides"
    ]
