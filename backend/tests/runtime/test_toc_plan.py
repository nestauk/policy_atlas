"""The theory-of-change plan and its chains (task 054, S2, S3)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine

from policy_atlas.core.schema import evidence_scope
from policy_atlas.evidence_search.sourcing.search_loop import (
    SearchDirectiveError,
    parse_link_scale,
    parse_search_directive,
)
from policy_atlas.runtime import option_search, runner
from policy_atlas.runtime.agent import persist_approved_plan
from policy_atlas.runtime.toc_plan import (
    DEFAULT_PUBLISHED_AFTER,
    TOC_FIND_MORE_SCALE,
    TOC_ITEM_RECORD_CAP,
    TocPlan,
    compose_toc,
)
from policy_atlas.theory_of_change.check.item_search_prompt import ITEM_SEARCH_GUIDANCE
from tests.helpers import delete_task_data, seed_task_and_run, seed_walk


def _plan(**overrides: Any) -> TocPlan:
    values: dict[str, Any] = {
        "title": "Healthy weight",
        "question": "How would a junk-food advertising ban reduce childhood obesity?",
        "entry_point": "intervention_first",
        "intended_change": "Fewer children living with obesity",
        "target_population": "children aged 4 to 11",
        "intervention": "a junk-food advertising ban",
        "where": "London",
    }
    values.update(overrides)
    return TocPlan.model_validate(values)


def test_the_draft_walk_drafts() -> None:
    draft = {"toc_walk": "draft"}
    assert compose_toc(_plan(), "toc", draft).components == ["toc_draft"]


def test_the_check_walk_classifies_only_after_the_judge() -> None:
    chain = compose_toc(_plan(), "toc", {"toc_walk": "check"})
    assert [(s.component, s.spine) for s in chain.steps] == [
        ("toc_select", True),
        ("toc_discover", False),
        ("toc_merge", True),
        ("toc_search_new", False),
        ("toc_judge", True),
        ("toc_search_again", False),
        ("toc_figures", False),
        ("classify", True),
        ("appraise", True),
        ("toc_choose", True),
        ("toc_summarise", False),
        ("toc_report", False),
    ]
    # A check named on links (C40) leaves the report to Update the report (C45).
    named = compose_toc(_plan(), "toc", {"toc_walk": "check", "links": ["l1"]})
    assert named.components == [
        "toc_select",
        "toc_judge",
        "toc_search_again",
        "toc_figures",
        "classify",
        "appraise",
        "toc_summarise",
    ]
    report = compose_toc(_plan(), "toc", {"toc_walk": "check", "mode": "report"})
    assert report.components == ["toc_summarise", "toc_report"]


def test_the_check_walk_has_no_screen_directive() -> None:
    step = compose_toc(_plan(), "toc", {"toc_walk": "check"}).steps[0]
    assert step.directive_delta == {}


def test_an_item_search_only_acquires_under_the_plan_s_restriction() -> None:
    plan = _plan(evidence_restriction={"published_after": "2015-01-01"})
    chain = compose_toc(plan, "targeted", {"acquire_only": True})
    assert chain.components == ["acquire"]
    directive = chain.steps[0].directive_delta
    assert directive["search"]["record_cap"] == TOC_ITEM_RECORD_CAP == 60
    assert directive["search"]["guidance"] == list(ITEM_SEARCH_GUIDANCE)
    # The search loop's own parser admits it.
    depth, filters, guidance = parse_search_directive(directive)
    assert (depth, filters) == ("link", {"shared": {"published_after": "2015-01-01"}})
    assert guidance == list(ITEM_SEARCH_GUIDANCE)


def test_find_more_evidence_doubles_the_item_search() -> None:
    """C44: the child context's ``link_scale`` doubles the cap and travels in the directive."""
    directive = compose_toc(
        _plan(), "targeted", {"acquire_only": True, "link_scale": TOC_FIND_MORE_SCALE}
    ).steps[0].directive_delta
    assert directive["search"]["record_cap"] == 2 * TOC_ITEM_RECORD_CAP == 120
    assert directive["search"]["link_scale"] == 2
    parse_search_directive(directive)  # the search loop's parser admits it
    assert parse_link_scale(directive) == 2
    plain = compose_toc(_plan(), "targeted", {"acquire_only": True}).steps[0].directive_delta
    assert "link_scale" not in plain["search"] and parse_link_scale(plain) == 1
    with pytest.raises(SearchDirectiveError):
        parse_link_scale({"search": {"depth": "link", "link_scale": 9}})


def test_a_reformulated_item_search_carries_the_earlier_queries() -> None:
    """C44: ``reformulate`` in the child context swaps the guidance and flags the directive."""
    from policy_atlas.theory_of_change.check.item_search_prompt import (
        REFORMULATE_GUIDANCE,
        reformulate_guidance,
    )

    earlier = ["advertising AND snacking", "Fewer ads lead to less snacking"]
    directive = compose_toc(
        _plan(), "targeted", {"acquire_only": True, "reformulate": earlier}
    ).steps[0].directive_delta
    assert directive["search"]["reformulate"] is True
    assert directive["search"]["guidance"] == reformulate_guidance(earlier)
    assert directive["search"]["guidance"][:3] == list(REFORMULATE_GUIDANCE)
    shown = directive["search"]["guidance"][3]
    assert shown.startswith("Earlier queries: advertising AND snacking; ")
    assert all(len(line) <= 200 for line in directive["search"]["guidance"])
    parse_search_directive(directive)  # the search loop's parser admits it
    plain = compose_toc(_plan(), "targeted", {"acquire_only": True}).steps[0].directive_delta
    assert "reformulate" not in plain["search"]
    assert plain["search"]["guidance"] == list(ITEM_SEARCH_GUIDANCE)


def test_check_again_and_find_more_skip_the_second_search() -> None:
    """The user is steering those checks (owner, 2026-11-06); a full check and new items run it."""
    link = {"toc_walk": "check", "links": ["l1"]}
    assert "toc_search_again" in compose_toc(_plan(), "toc", {"toc_walk": "check"}).components
    new_items = compose_toc(_plan(), "toc", {**link, "mode": "new_items"}).components
    assert "toc_search_again" in new_items
    for mode in ("check_again", "find_more"):
        steered = compose_toc(_plan(), "toc", {**link, "mode": mode}).components
        assert "toc_search_again" not in steered


def test_an_item_search_defaults_to_evidence_from_2000() -> None:
    """A plan with no restriction (a plan stored before the years existed) searches from 2000."""
    directive = compose_toc(_plan(), "targeted", {"acquire_only": True}).steps[0].directive_delta
    _depth, filters, _guidance = parse_search_directive(directive)
    assert filters == {"shared": {"published_after": DEFAULT_PUBLISHED_AFTER}}
    assert DEFAULT_PUBLISHED_AFTER == "2000-01-01"


@pytest.mark.parametrize(
    ("purpose", "context"),
    [
        ("toc", {"toc_walk": "recheck"}),
        ("toc", {}),
        ("targeted", {}),
        ("baseline", None),
    ],
)
def test_a_walk_this_build_does_not_compose_fails_closed(
    purpose: str, context: dict[str, Any] | None
) -> None:
    with pytest.raises(ValueError):
        compose_toc(_plan(), purpose, context)


def test_ready_needs_the_entry_point_s_own_slot() -> None:
    assert _plan().ready
    assert not _plan(intervention=None).ready
    assert _plan(entry_point="outcome_first", intervention=None).ready
    assert not _plan(entry_point="existing_theory").ready
    assert _plan(entry_point="existing_theory", existing_theory_text="Our theory...").ready


def test_the_plan_never_pauses_and_refuses_a_standing_default() -> None:
    with pytest.raises(ValidationError):
        _plan(steering_mode="moderate")
    with pytest.raises(ValidationError):
        _plan(steer_point_defaults=[{"steer_point": "baseline_confirm", "action": "proceed_flag"}])
    with pytest.raises(ValidationError):
        _plan(evidence_restriction={"published_after": "last year"})


@pytest.mark.parametrize(("purpose", "abandons"), [("toc", True), ("baseline", False)])
def test_the_end_of_a_toc_walk_abandons_its_item_searches(
    engine: Engine, monkeypatch: pytest.MonkeyPatch, purpose: str, abandons: bool
) -> None:
    """S6: ``_finish_run`` ends a toc walk's children as it ends a longlist walk's."""
    calls: list[uuid.UUID] = []

    def abandon(_engine: Engine, *, task_id: uuid.UUID, parent_id: uuid.UUID) -> list[uuid.UUID]:
        calls.append(parent_id)
        return []

    monkeypatch.setattr(option_search, "abandon_children", abandon)
    with engine.begin() as conn:
        task_id, _run = seed_task_and_run(conn)
        walk = seed_walk(
            conn, task_id, purpose=purpose, status="running", context={"toc_walk": "check"}
        ).walk_id
    try:
        runner._finish_run(
            engine, [], [], status="failed", capability_run_id=walk, task_id=task_id
        )
        assert calls == ([walk] if abandons else [])
    finally:
        with engine.begin() as conn:
            delete_task_data(conn, task_id)


def test_an_approved_plan_opens_the_draft_walk_s_intent_record(conn: Connection) -> None:
    """S6: ``persist_approved_plan`` writes ``purpose='toc'`` and ``toc_walk='draft'``."""
    task_id, _run = seed_task_and_run(conn)
    scope_id, plan_id = persist_approved_plan(conn, task_id=task_id, plan=_plan())
    row = conn.execute(
        select(evidence_scope).where(evidence_scope.c.evidence_scope_id == scope_id)
    ).mappings().one()
    assert (row["purpose"], row["plan_id"]) == ("toc", plan_id)
    assert row["context"] == {"capability": "theory_of_change", "toc_walk": "draft"}
