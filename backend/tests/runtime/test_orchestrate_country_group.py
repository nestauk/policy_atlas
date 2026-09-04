"""Pure country-group tests for the orchestrator draft-to-plan seam."""

import pytest

from policy_atlas.runtime.orchestrate import (
    _assign_country_group_authorship,
    _build_plan,
    _render_full_plan,
)
from policy_atlas.runtime.orchestration_plan import CountryGroupAuthorship
from policy_atlas.runtime.planner_prompt import CountryGroupDraft, PlanDraftWire


def _draft(
    *,
    label: str,
    countries: list[str] | None,
) -> PlanDraftWire:
    return PlanDraftWire(
        title="Scoped review",
        question="What evidence exists on scoped policy outcomes?",
        backend_scope="both",
        search_effort="rapid",
        analysis_depth="landscape",
        components=["characterise"],
        steering_mode="moderate",
        country_group=CountryGroupDraft(label=label, countries=countries),
    )


def test_country_group_authorship_flips_when_user_changes_same_label_list() -> None:
    first_by_label: dict[str, tuple[str, ...] | None] = {}
    authorship_by_label: dict[str, CountryGroupAuthorship] = {}
    initial = _draft(label="Nordic countries", countries=["NO", "SE"])
    amended = _draft(label="Nordic countries", countries=["NO", "SE", "DK"])

    initial_authorship = _assign_country_group_authorship(
        initial,
        None,
        follows_user_turn=True,
        first_countries_by_label=first_by_label,
        authorship_by_label=authorship_by_label,
    )
    amended_authorship = _assign_country_group_authorship(
        amended,
        initial.model_dump(),
        follows_user_turn=True,
        first_countries_by_label=first_by_label,
        authorship_by_label=authorship_by_label,
    )
    repeated_authorship = _assign_country_group_authorship(
        amended,
        amended.model_dump(),
        follows_user_turn=False,
        first_countries_by_label=first_by_label,
        authorship_by_label=authorship_by_label,
    )

    assert initial_authorship == "planner-proposed"
    assert amended_authorship == "user-amended"
    assert repeated_authorship == "user-amended"
    plan = _build_plan(amended, country_group_authorship=amended_authorship)
    assert plan.scope_constraints.country_group is not None
    assert plan.scope_constraints.country_group.authorship == "user-amended"


def test_country_group_render_shows_count_and_authorship_without_membership() -> None:
    plan = _build_plan(_draft(label="G7", countries=None))

    render = _render_full_plan(plan)

    assert "Country group: G7 (7 countries, pinned table)" in render
    assert "CA" not in render


def test_custom_country_group_render_uses_custom_count_and_authorship() -> None:
    plan = _build_plan(_draft(label="Nordic countries", countries=["NO", "SE", "DK"]))

    render = _render_full_plan(plan)

    assert "Country group: Nordic countries (3 countries, planner-proposed)" in render
    assert "NO" not in render


def test_publisher_source_survives_the_draft_to_plan_round_trip() -> None:
    """038 APO test mod: build_plan folds the flat publisher_source draft
    field into scope_constraints."""
    draft = PlanDraftWire(
        title="APO-only review",
        question="What evidence exists on scoped policy outcomes?",
        backend_scope="grey_lit_only",
        publisher_source="apo",
        search_effort="rapid",
        analysis_depth="landscape",
        components=["characterise"],
        steering_mode="moderate",
    )

    plan = _build_plan(draft)

    assert plan.scope_constraints.publisher_source == "apo"


@pytest.mark.parametrize("emitted", ["APO", "Australian Policy Online", "xyz"])
def test_planner_emitted_junk_publisher_source_is_dropped(emitted: str) -> None:
    """publisher_source sits in the planner's structured-output schema with no
    prompt text behind it; a non-"apo" emission must be dropped at the wire
    model — downstream Literal["apo"] layers would otherwise crash the
    turn's draft projection (038 review)."""
    assert PlanDraftWire(publisher_source=emitted).publisher_source is None
    assert PlanDraftWire(publisher_source="apo").publisher_source == "apo"


def test_apo_plan_renders_publisher_source_line() -> None:
    """038 R3 on the CLI approval surface: the render must not show an APO
    plan as unrestricted."""
    draft = PlanDraftWire(
        title="APO-only review",
        question="What evidence exists on scoped policy outcomes?",
        backend_scope="grey_lit_only",
        publisher_source="apo",
        search_effort="rapid",
        analysis_depth="landscape",
        components=["characterise"],
        steering_mode="moderate",
    )
    render = _render_full_plan(_build_plan(draft))
    assert "publisher_source: apo (Australian Policy Online)" in render
