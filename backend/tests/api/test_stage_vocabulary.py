"""Coverage guard for the public stage vocabulary (spec § SSE).

No database needed — these tests only check that the pinned `StageKey`
Literal, `STAGE_KEYS` tuple, `PlanStageKey` Literal and the presentation/
registry dicts in `stage_vocabulary` never drift apart.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import get_args

from policy_atlas.api.contract import STAGE_KEYS, StageKey
from policy_atlas.api.contract.task_agent import PlanStageKey
from policy_atlas.api.stage_vocabulary import (
    ACTIVITY,
    STAGE_BY_REGISTRY,
    STAGE_COUNTS,
    STAGE_PRESENTATION,
    STAGE_ROW,
    STEP_VERBS,
    activity,
    stage_for_payload,
)


def test_stage_keys_tuple_matches_literal() -> None:
    """`STAGE_KEYS` has exactly `StageKey`'s members, in the same order."""
    assert get_args(StageKey) == STAGE_KEYS


def test_plan_stage_key_mirrors_stage_key() -> None:
    """`PlanStageKey` (the standalone contract copy) has the same members."""
    assert set(get_args(PlanStageKey)) == set(get_args(StageKey))


def test_every_stage_key_has_a_presentation() -> None:
    """Every pinned `StageKey` has a `(label, blurb)` presentation entry."""
    assert set(STAGE_PRESENTATION) == set(get_args(StageKey))


def test_every_registry_mapping_targets_a_stage_key() -> None:
    """Every `STAGE_BY_REGISTRY` value is a valid public `StageKey`."""
    stage_keys = set(get_args(StageKey))
    for registry_component, stage in STAGE_BY_REGISTRY.items():
        assert stage in stage_keys, f"{registry_component} -> {stage} is not a StageKey"


def test_ingest_stage_words_and_registry_mapping() -> None:
    """Task 056 (N9, S5): full-text reading has its own public stage and words."""
    assert STAGE_KEYS.index("ingest") == STAGE_KEYS.index("appraise") + 1
    assert STAGE_PRESENTATION["ingest"] == (
        "Collecting the full texts",
        "Fetching each full text and making it searchable.",
    )
    # Owner round 9: the stage collects; it does not read (the full-text
    # screen, a model reading, keeps its words).
    assert STAGE_COUNTS["ingest"] == (("ingested", "collected"),)
    assert activity("ingest.progress", done=3, total=38) == "collecting 3 of 38"
    assert STEP_VERBS["screen_full"] == "Reading full texts for relevance"
    assert STAGE_BY_REGISTRY["ingest_full_text"] == "ingest"
    assert stage_for_payload({"component": "ingest_full_text"}) == "ingest"


def test_every_route_step_has_a_verb() -> None:
    """Every configured model-call step has one fixed activity verb."""
    route_file = Path(__file__).resolve().parents[2] / "src/policy_atlas/model_routes.toml"
    with route_file.open("rb") as handle:
        route_steps = set(tomllib.load(handle)["steps"])

    assert route_steps <= set(STEP_VERBS)
    # Phase 2 adds this streamed writer step to the routes file, then removes
    # this temporary allowance.
    assert set(STEP_VERBS) - route_steps <= {"synthesise_section_emit"}


def test_searching_and_screening_are_two_rows() -> None:
    """Task 058, round 8 (owner): search and screen each have their own row,
    label and blurb; classify and appraise still share one."""
    assert STAGE_ROW["acquire"] == "search"
    assert STAGE_ROW["screen"] == "screen"
    assert STAGE_PRESENTATION["acquire"] == (
        "Searching",
        "Querying the databases and collecting candidates.",
    )
    assert STAGE_PRESENTATION["screen"] == (
        "Screening",
        "Reading each abstract against the question.",
    )
    assert STAGE_ROW["classify"] == STAGE_ROW["appraise"] == "categorise"
    # A shared row still shares its label: the row is what the user sees.
    for stage, row in STAGE_ROW.items():
        sharing = {other for other, other_row in STAGE_ROW.items() if other_row == row}
        assert {STAGE_PRESENTATION[other][0] for other in sharing} == {
            STAGE_PRESENTATION[stage][0]
        }


def test_the_source_note_line_names_the_source() -> None:
    """Task 058, round 8: the note's line names its source by short name."""
    assert activity("synthesise.source_note_named", name="Smith 2023") == (
        "Writing a source note · Smith 2023"
    )


def test_the_search_and_screening_lines_round_9() -> None:
    """Task 058, round 9 (owner): no "new" or "so far" in the counts; the search
    says it writes its queries, names the query out, and names the id passes."""
    assert activity("search.writing_queries") == "Writing search queries"
    assert activity("acquire.searching", found=1234) == "searching · 1,234 found"
    assert activity("acquire.searching_again", pass_number=2, found=12) == "Search 2 · 12 found"
    assert activity("acquire.searching_query", found=34, query="school meals") == (
        "searching · 34 found · school meals"
    )
    assert activity(
        "acquire.searching_again_query", pass_number=2, found=34, query="school meals"
    ) == ("Search 2 · 34 found · school meals")
    assert activity("acquire.following", found=1234) == "following citations · 1,234 found"
    assert activity("acquire.keeping", kept=312, found=1234) == "keeping 312 of 1,234 candidates"
    assert activity("screen.abstracts", remaining=1087, relevant=104) == (
        "screening 1,087 abstracts · 104 relevant"
    )
    assert activity("search.citations_from", count=50) == "Following citations from 50 sources"
    assert activity("search.lookup_works", count=100) == "Looking up 100 cited works"
    assert activity("search.lookup_documents", count=15) == "Looking up 15 cited documents"
    assert activity("search.lookup_works_one") == "Looking up 1 cited work"
    counted = ("acquire.", "screen.", "search.")
    assert all("so far" not in line for key, line in ACTIVITY.items() if key.startswith(counted))
