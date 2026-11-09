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


def test_the_shortlist_row_counts_the_shortlist_after_the_step() -> None:
    """Round 11: the done row reads the shortlist, not the places kept before it."""
    assert STAGE_COUNTS["shortlist"] == (("shortlisted", "shortlisted"),)


def test_every_stage_key_has_a_row_and_a_counts_entry() -> None:
    """The two presentation tables cover exactly the public stage keys."""
    assert set(STAGE_ROW) == set(STAGE_KEYS)
    assert set(STAGE_COUNTS) == set(STAGE_KEYS)


def test_every_route_step_has_a_verb() -> None:
    """Every configured model-call step has one fixed activity verb."""
    route_file = Path(__file__).resolve().parents[2] / "src/policy_atlas/model_routes.toml"
    with route_file.open("rb") as handle:
        route_steps = set(tomllib.load(handle)["steps"])

    assert route_steps <= set(STEP_VERBS)
    assert set(STEP_VERBS) <= route_steps


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


#: Task 054, the 058 alignment (S1, § 9): the theory of change's fifteen keys.
TOC_KEYS: tuple[StageKey, ...] = (
    "toc_draft",
    "toc_read",
    "toc_item_searches",
    "toc_select",
    "toc_discover",
    "toc_merge",
    "toc_search_new",
    "toc_new_link_searches",
    "toc_judge",
    "toc_search_again",
    "toc_retry_searches",
    "toc_figures",
    "toc_choose",
    "toc_summarise",
    "toc_report",
)


def test_the_theory_of_change_keys_join_the_vocabulary() -> None:
    """A1: 15 ToC keys, 34 in all, in every mirror and table."""
    assert STAGE_KEYS[-len(TOC_KEYS) :] == TOC_KEYS
    assert len(STAGE_KEYS) == 34
    assert set(TOC_KEYS) <= set(get_args(PlanStageKey))
    for key in TOC_KEYS:
        assert key in STAGE_PRESENTATION and key in STAGE_ROW and key in STAGE_COUNTS


def test_the_theory_of_change_labels_are_the_owners() -> None:
    """A1: the labels of § 8, the fan-outs with their step's label and row."""
    labels = {key: STAGE_PRESENTATION[key][0] for key in TOC_KEYS}
    assert labels == {
        "toc_draft": "Drafting the theory",
        "toc_read": "Reading your diagram",
        "toc_item_searches": "Searching for each connection",
        "toc_select": "Screening",
        "toc_discover": "Looking for other routes",
        "toc_merge": "Merging similar steps",
        "toc_search_new": "Searching for the new connections",
        "toc_new_link_searches": "Searching for the new connections",
        "toc_judge": "Judging the evidence",
        "toc_search_again": "Searching again for thin connections",
        "toc_retry_searches": "Searching again for thin connections",
        "toc_figures": "Finding the size of change",
        "toc_choose": "Choosing pathways",
        "toc_summarise": "Writing titles and summaries",
        "toc_report": "Writing the report",
    }
    assert STAGE_ROW["toc_new_link_searches"] == STAGE_ROW["toc_search_new"]
    assert STAGE_ROW["toc_retry_searches"] == STAGE_ROW["toc_search_again"]
    # This pass has no claim check and no per-section call.
    assert STAGE_PRESENTATION["toc_report"][1] == "The report, as it is written."
    assert all(STAGE_PRESENTATION[key][1] for key in TOC_KEYS)


def test_the_theory_of_change_done_counts() -> None:
    """S2: the § 9 table's done counts, each from an integer summary key."""
    nouns = {key: [noun for _, noun in STAGE_COUNTS[key]] for key in TOC_KEYS}
    assert nouns == {
        "toc_draft": ["boxes", "connections", "pathways"],
        "toc_read": ["boxes", "connections", "pathways"],
        "toc_item_searches": ["searches", "found"],
        "toc_select": ["read", "relevant"],
        "toc_discover": ["routes found"],
        "toc_merge": ["merged"],
        "toc_search_new": ["connections"],
        "toc_new_link_searches": ["searches", "found"],
        "toc_judge": ["judged", "test them"],
        "toc_search_again": ["connections", "judged"],
        "toc_retry_searches": ["searches", "found"],
        "toc_figures": ["figures"],
        "toc_choose": ["kept", "set aside"],
        "toc_summarise": [],
        "toc_report": [],
    }


def test_every_theory_of_change_component_maps_to_its_stage() -> None:
    """A1: the registry names map onto their keys; the upload's read is stamped."""
    for key in TOC_KEYS:
        if key != "toc_read":
            assert STAGE_BY_REGISTRY[key] == key
            assert stage_for_payload({"component": key}) == key
    assert "toc_read" not in STAGE_BY_REGISTRY


def test_a_stamped_stage_is_read_first() -> None:
    """A21: a payload's stamped ``stage`` wins over its component's own key."""
    assert stage_for_payload({"component": "toc_draft"}) == "toc_draft"
    assert stage_for_payload({"component": "toc_draft", "stage": "toc_read"}) == "toc_read"
    # Only a public key counts as a stamp; anything else falls back to the component.
    assert stage_for_payload({"component": "toc_draft", "stage": 2}) == "toc_draft"
    assert stage_for_payload({"component": "toc_draft", "stage": "nope"}) == "toc_draft"


def test_the_theory_of_change_activity_lines() -> None:
    """A4: the fan-outs, screening and the judge, with no "so far"."""
    assert activity("toc_searches.progress", done=9, total=17, found=1214) == (
        "9 of 17 searches done · 1,214 found"
    )
    assert activity("toc_select.progress", done=120, total=187, relevant=41) == (
        "120 of 187 read · 41 relevant"
    )
    assert activity("toc_judge.progress", done=30, total=64) == "30 of 64 documents"
    assert all("so far" not in line for key, line in ACTIVITY.items() if key.startswith("toc_"))
