"""Pure country-group tests for the orchestrator draft-to-plan seam."""

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
