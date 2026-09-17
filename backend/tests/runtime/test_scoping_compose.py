"""What an options-scoping plan compiles to.

Contract § Acceptance checks "compile" (task 044). Two properties carry the
weight: the chain is fixed (nothing the user says adds or removes a component),
and every directive this composer emits **parses under the component's own
fail-closed grammar** — a plan that validates here and is refused at the
component boundary is an approved plan that cannot run.
"""

from __future__ import annotations

from typing import Any

import pytest

from policy_atlas.evidence_search.sourcing.search_loop import (
    SearchDirectiveError,
    parse_record_cap,
    parse_search_directive,
)
from policy_atlas.evidence_search.synthesis.baseline_prompt import (
    BASELINE_PROPOSED_SECTIONS_MAX,
    BASELINE_SECTION_TURN_CAP,
    BASELINE_SECTIONS,
    SOURCES_SECTION_TITLE,
    required_titles,
)
from policy_atlas.evidence_search.synthesis.synthesis_tools import (
    SECTION_CAP,
    SynthesisDirectiveError,
    parse_synthesis_directive,
)
from policy_atlas.runtime.capability_registry import OPTIONS_SCOPING, compose_plan
from policy_atlas.runtime.scoping_plan import (
    BASELINE_ACQUISITION_TARGETS,
    SCOPING_SPINE,
    ScopingPlan,
    build_scoping_plan,
    compose_scoping,
)
from policy_atlas.runtime.task_agent_prompt import CountryGroupDraft
from policy_atlas.runtime.task_agent_scoping_prompt import (
    ScopingConstraintWire,
    ScopingPlanDraftWire,
    TaggedText,
)


def _plan(**overrides: object) -> ScopingPlan:
    values: dict[str, object] = {
        "title": "Youth employment options",
        "question": "What could reduce the number of young people not in work?",
        "intended_change": TaggedText(
            text="Reduce the number of young people not in work",
            origin="from_your_question",
        ),
        "target_unit": TaggedText(text="16 to 24 year olds", origin="your_call"),
        "outcomes": [TaggedText(text="the NEET rate", origin="assumed")],
        "depth": "standard",
    }
    values.update(overrides)
    return build_scoping_plan(ScopingPlanDraftWire.model_validate(values))


def _delta(plan: ScopingPlan, component: str) -> dict[str, Any]:
    return next(
        step.directive_delta
        for step in compose_scoping(plan).steps
        if step.component == component
    )


# --- the chain --------------------------------------------------------------


def test_the_chain_is_exactly_the_six_components() -> None:
    assert compose_scoping(_plan()).components == list(SCOPING_SPINE)


def test_depth_changes_the_directives_never_the_chain() -> None:
    """D7 (revised 2026-09-17): depth shapes the target and the section list."""
    rapid = compose_scoping(_plan(depth="rapid"))
    standard = compose_scoping(_plan(depth="standard"))
    assert rapid.components == standard.components
    assert rapid != standard


# --- synthesise -------------------------------------------------------------


def test_standard_supplies_seven_sections_plus_sources_and_allows_two_proposals() -> None:
    synthesis = _delta(_plan(depth="standard"), "synthesise")["synthesis"]
    assert [s["title"] for s in synthesis["sections"]] == list(required_titles())
    assert len(synthesis["sections"]) == 8
    assert synthesis["section_budget"] == BASELINE_PROPOSED_SECTIONS_MAX


def test_rapid_supplies_the_same_seven_sections_and_no_proposal_budget() -> None:
    """Owner ruling 2026-09-17: seven sections at both depths; rapid proposes none."""
    synthesis = _delta(_plan(depth="rapid"), "synthesise")["synthesis"]
    standard = _delta(_plan(depth="standard"), "synthesise")["synthesis"]
    assert synthesis["sections"] == standard["sections"]
    assert len(synthesis["sections"]) == 8
    assert "section_budget" not in synthesis


def test_the_registry_composes_the_scoping_chain_not_the_evidence_search_one() -> None:
    plan = _plan()
    assert compose_plan(OPTIONS_SCOPING, plan) == compose_scoping(plan)


# --- acquire ----------------------------------------------------------------


def test_acquire_carries_the_depths_acquisition_target() -> None:
    assert BASELINE_ACQUISITION_TARGETS == {"standard": 20, "rapid": 10}
    for depth, target in BASELINE_ACQUISITION_TARGETS.items():
        search = _delta(_plan(depth=depth), "acquire")["search"]
        assert search["record_cap"] == target


def test_the_acquire_directive_parses_under_the_search_grammar() -> None:
    context = _delta(_plan(), "acquire")
    depth, filters, guidance = parse_search_directive(context)
    assert depth == "rapid"
    assert guidance is None
    assert parse_record_cap(context) == BASELINE_ACQUISITION_TARGETS["standard"]
    assert filters is None


def test_a_record_cap_above_the_deepest_rung_is_refused() -> None:
    with pytest.raises(SearchDirectiveError, match="record_cap"):
        parse_search_directive({"search": {"depth": "rapid", "record_cap": 10_000}})


def test_an_absent_record_cap_leaves_the_depth_rung_alone() -> None:
    """Additive: today's Evidence search directives are unchanged."""
    assert parse_record_cap({"search": {"depth": "standard"}}) is None
    assert parse_search_directive({}) == ("rapid", None, None)


def test_an_evidence_restriction_lands_on_acquire_as_scope_constraints() -> None:
    plan = _plan(
        constraints=[
            ScopingConstraintWire(
                text="OECD evidence only",
                kind="evidence_restriction",
                origin="your_call",
                checked_at="retrieval",
                country_group=CountryGroupDraft(label="OECD members", countries=None),
            ),
            ScopingConstraintWire(
                text="since 2015",
                kind="evidence_restriction",
                origin="from_your_question",
                checked_at="retrieval",
                published_after="2015-01-01",
            ),
        ]
    )
    filters = _delta(plan, "acquire")["search"]["filters"]
    assert filters["shared"]["published_after"] == "2015-01-01"
    assert filters["overton"]["publisher_region"] == "OECD members"
    assert filters["openalex"]["author_affiliation_countries"]


def test_a_language_restriction_is_on_the_plan_and_not_in_the_search(  # C8
) -> None:
    plan = _plan(
        constraints=[
            ScopingConstraintWire(
                text="English-language only",
                kind="evidence_restriction",
                origin="from_your_question",
                checked_at="retrieval",
                languages=["English"],
            )
        ]
    )
    assert plan.constraints[0].languages == ["English"]
    assert "filters" not in _delta(plan, "acquire")["search"]


def test_a_requirement_never_reaches_the_search() -> None:
    """Requirements bite at the longlist, which this release does not run."""
    plan = _plan(
        constraints=[
            ScopingConstraintWire(
                text="only options a local authority can run",
                kind="requirement",
                origin="from_your_question",
                checked_at="longlist",
            )
        ]
    )
    assert "filters" not in _delta(plan, "acquire")["search"]


# --- screen -----------------------------------------------------------------


def test_screening_names_the_target_unit_and_where() -> None:
    criteria = _delta(_plan(), "screen_abstract")["screening"]["criteria"]
    assert len(criteria) == 1
    assert "16 to 24 year olds" in criteria[0]
    assert "United Kingdom" in criteria[0]


def test_a_source_origin_restriction_is_also_a_screening_criterion() -> None:
    plan = _plan(
        constraints=[
            ScopingConstraintWire(
                text="OECD evidence only",
                kind="evidence_restriction",
                origin="your_call",
                checked_at="retrieval",
                country_group=CountryGroupDraft(label="OECD members", countries=None),
            )
        ]
    )
    assert _delta(plan, "screen_abstract")["screening"]["criteria"][1] == "OECD evidence only"


def test_a_year_restriction_is_not_repeated_as_a_screening_criterion() -> None:
    """The search grammar already excluded them; re-judging would double-count."""
    plan = _plan(
        constraints=[
            ScopingConstraintWire(
                text="since 2015",
                kind="evidence_restriction",
                origin="from_your_question",
                checked_at="retrieval",
                published_after="2015-01-01",
            )
        ]
    )
    assert len(_delta(plan, "screen_abstract")["screening"]["criteria"]) == 1


# --- synthesise -------------------------------------------------------------


def test_synthesise_carries_the_baseline_template_and_its_sections() -> None:
    synthesis = _delta(_plan(), "synthesise")["synthesis"]
    assert synthesis["template"] == "baseline"
    assert synthesis["section_budget"] == BASELINE_PROPOSED_SECTIONS_MAX
    titles = [section["title"] for section in synthesis["sections"]]
    assert titles == [section.title for section in BASELINE_SECTIONS] + [
        SOURCES_SECTION_TITLE
    ]
    assert all(section["nav_label"] for section in synthesis["sections"])
    # The per-section turn cap travels with the section (task 044 phase 4.2);
    # the code-rendered Sources section runs no loop, so it carries none.
    written = synthesis["sections"][:-1]
    assert [section["turn_cap"] for section in written] == [
        BASELINE_SECTION_TURN_CAP
    ] * len(BASELINE_SECTIONS)
    assert "turn_cap" not in synthesis["sections"][-1]


def test_the_supplied_sections_fit_the_section_cap() -> None:
    """Seven written sections plus the code-rendered Sources section."""
    sections = _delta(_plan(), "synthesise")["synthesis"]["sections"]
    assert len(sections) == len(BASELINE_SECTIONS) + 1 == SECTION_CAP


def test_the_synthesise_directive_parses_under_the_synthesis_grammar() -> None:
    directive = parse_synthesis_directive(
        _delta(_plan(), "synthesise"), grouping_group_ids=None
    )
    assert directive.template == "baseline"
    assert directive.section_budget == BASELINE_PROPOSED_SECTIONS_MAX
    assert directive.sections is not None
    assert len(directive.sections) == SECTION_CAP
    # The nav labels survive the parse: before task 044 the key set rejected
    # them, so a supplied section could never carry one.
    assert directive.sections[0]["nav_label"] == BASELINE_SECTIONS[0].nav_label
    assert directive.sections[0]["turn_cap"] == BASELINE_SECTION_TURN_CAP


def test_an_unknown_template_is_refused() -> None:
    with pytest.raises(SynthesisDirectiveError, match="template"):
        parse_synthesis_directive({"synthesis": {"template": "briefing"}}, grouping_group_ids=None)


def test_outside_template_mode_the_section_budget_still_caps_the_list() -> None:
    """The Evidence search meaning of ``section_budget`` is untouched."""
    with pytest.raises(SynthesisDirectiveError, match="1..2 items"):
        parse_synthesis_directive(
            {
                "synthesis": {
                    "section_budget": 2,
                    "sections": [
                        {"title": f"S{i}", "focus": "f"} for i in range(3)
                    ],
                }
            },
            grouping_group_ids=None,
        )


def test_synthesise_threads_the_deepest_successful_reference() -> None:
    step = next(
        step for step in compose_scoping(_plan()).steps if step.component == "synthesise"
    )
    assert step.reference_rule == "deepest_successful_reference"
