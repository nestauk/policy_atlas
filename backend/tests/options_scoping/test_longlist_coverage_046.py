"""Coverage additions of task 046 (S11; AM20; contract items 14 and 23).

*Tried on* (the adjacent members' units), ``folded`` (the folded seeds'
names), the programme-name fold, and the setting code pass on the read side:
folded setting labels, and a setting that names a place read as the study
geography (or left out of the facet), logged. A tag sorts and never removes
a record.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import update
from sqlalchemy.engine import Connection
from structlog.testing import capture_logs

from policy_atlas.core.schema import option, option_membership
from policy_atlas.options_scoping.longlist.coverage import (
    SETTING_FOLDS,
    TRIED_ON_MAX,
    CoverageMember,
    FoldedSeed,
    distinct_words,
    empty_coverage,
    fold_programme_name,
    fold_programme_names,
    fold_setting,
    option_coverage,
)
from policy_atlas.options_scoping.longlist.longlist import read_membership
from policy_atlas.options_scoping.longlist.where_tried import names_place
from tests.options_scoping.test_longlist import (
    _current_fingerprint,
    _extraction,
    _record_under,
    _rollup_of,
    _Scripted,
    _Walk,
)


def _member(doc: str, **values: Any) -> CoverageMember:
    fields: dict[str, Any] = {
        "unit_kind": "interventions",
        "doc_key": f"doc:{doc}",
        "tss_id": None,
        "role": "evaluated",
        "basis": "abstract_only",
        "flagged": False,
        "unit": None,
        "setting": None,
        "outcome": None,
        "study_geography": None,
    }
    fields.update(values)
    return CoverageMember(**fields)


def _coverage(members: list[CoverageMember], **kwargs: Any) -> dict[str, Any]:
    return option_coverage(members, labels={}, **kwargs)


def _recomputed(walk: _Walk, option_id: uuid.UUID) -> dict[str, Any]:
    read = read_membership(
        walk.conn, task_id=walk.task_id, scope_id=walk.scope_id, option_ids=[option_id]
    )
    return read.coverage()[str(option_id)]


# --- an empty option ----------------------------------------------------------------


def test_an_option_with_no_member_has_every_new_key_empty() -> None:
    coverage = _coverage([])
    assert coverage["tried_on"] == []
    assert coverage["folded"] == []
    assert "variants" not in coverage


# --- outcome counts (R42) ------------------------------------------------------------

PLAN = ["Reduce crime", "Improve wellbeing"]


def _counts(members: list[CoverageMember], plan: list[str] = PLAN) -> dict[str, Any]:
    counts: dict[str, Any] = _coverage(members, plan_outcomes=plan)["outcome_counts"]
    return counts


def _by(counts: dict[str, Any]) -> dict[str, int]:
    return {item["outcome"]: item["documents"] for item in counts["by_outcome"]}


def _evaluated_by(counts: dict[str, Any]) -> dict[str, int]:
    return {item["outcome"]: item["evaluated"] for item in counts["by_outcome"]}


def test_a_document_evaluating_two_outcomes_counts_for_both_and_once_overall() -> None:
    counts = _counts(
        [
            _member("a", outcome_tag="Reduce crime"),
            _member("a", outcome_tag="Improve wellbeing"),
        ]
    )
    assert counts["evaluating_documents"] == 1
    assert _by(counts) == {"Reduce crime": 1, "Improve wellbeing": 1}


def test_a_described_record_with_a_plan_outcome_tag_counts_in_documents_not_evaluated() -> None:
    """R56: any role counts; the evaluated count is separate."""
    counts = _counts([_member("a", role="described", outcome_tag="Reduce crime")])
    assert counts["evaluating_documents"] == 0
    assert _by(counts) == {"Reduce crime": 1, "Improve wellbeing": 0}
    assert _evaluated_by(counts) == {"Reduce crime": 0, "Improve wellbeing": 0}


@pytest.mark.parametrize("role", ["recommended", "mentioned"])
def test_a_recommended_or_mentioned_record_counts_in_documents(role: str) -> None:
    counts = _counts([_member("a", role=role, outcome_tag="Improve wellbeing")])
    assert _by(counts) == {"Reduce crime": 0, "Improve wellbeing": 1}
    assert _evaluated_by(counts) == {"Reduce crime": 0, "Improve wellbeing": 0}


def test_a_document_with_an_evaluated_and_a_described_member_counts_in_both() -> None:
    counts = _counts(
        [
            _member("a", role="evaluated", outcome_tag="Reduce crime"),
            _member("a", role="described", outcome_tag="Reduce crime"),
        ]
    )
    assert _by(counts)["Reduce crime"] == 1
    assert _evaluated_by(counts)["Reduce crime"] == 1


def test_an_evaluating_record_tagged_other_counts_in_evaluating_documents_only() -> None:
    counts = _counts([_member("a", outcome_tag="other"), _member("b")])
    assert counts["evaluating_documents"] == 2
    assert _by(counts) == {"Reduce crime": 0, "Improve wellbeing": 0}


def test_two_documents_with_the_same_doi_count_once_in_the_outcome_counts() -> None:
    counts = _counts(
        [
            _member("a", doc_key="doi:10.1/x", outcome_tag="Reduce crime"),
            _member("b", doc_key="doi:10.1/x", outcome_tag="Reduce crime"),
        ]
    )
    assert counts["evaluating_documents"] == 1
    assert _by(counts)["Reduce crime"] == 1


def test_every_plan_outcome_is_listed_in_plan_order_with_zero_where_none() -> None:
    counts = _counts([_member("a", outcome_tag="Improve wellbeing")])
    assert counts["by_outcome"] == [
        {"outcome": "Reduce crime", "documents": 0, "evaluated": 0},
        {"outcome": "Improve wellbeing", "documents": 1, "evaluated": 1},
    ]


def test_empty_coverage_has_the_outcome_counts_key() -> None:
    assert empty_coverage()["outcome_counts"] == {
        "evaluating_documents": 0,
        "by_outcome": [],
        "other": [],
    }


# --- tried on ------------------------------------------------------------------------


def test_tried_on_lists_adjacent_units_by_document_folded() -> None:
    coverage = _coverage(
        [
            _member("a", unit="Young  adults", unit_tag="adjacent"),
            _member("a", unit="young adults", unit_tag="adjacent"),  # same doc
            _member("b", unit="YOUNG ADULTS", unit_tag="adjacent"),
            _member("c", unit="older workers", unit_tag="adjacent"),
            _member("d", unit="young people not in work", unit_tag="on_target"),
            _member("e", unit="firms", unit_tag="other"),
            _member("f", unit=None, unit_tag="adjacent"),
        ]
    )
    assert coverage["tried_on"] == [
        {"unit": "YOUNG ADULTS", "documents": 2},
        {"unit": "older workers", "documents": 1},
    ]


def test_tried_on_is_capped_at_eight_by_documents_then_text() -> None:
    members = [
        _member(f"{name}-{n}", unit=name, unit_tag="adjacent")
        for index, name in enumerate(f"group {chr(97 + i)}" for i in range(10))
        for n in range(1 + index % 3)
    ]
    tried_on = _coverage(members)["tried_on"]
    assert len(tried_on) == TRIED_ON_MAX == 8
    documents = [entry["documents"] for entry in tried_on]
    assert documents == sorted(documents, reverse=True)
    assert tried_on[0] == {"unit": "group c", "documents": 3}


# --- the example-name fold (task 046, amendment 4, R88; S33; contract review C16) ------


def _fold(*names: str) -> dict[str, str]:
    return fold_programme_names(names)


def test_three_spellings_of_one_programme_fold_to_one() -> None:
    a = "School Diet and Nutrition Programme"
    b = "the School Diet and Nutrition Programme (SDNP)"
    c = "SDNP"
    folded = _fold(a, b, c)
    assert len(set(folded.values())) == 1
    assert fold_programme_name(b) == ("school diet and nutrition programme", "sdnp")
    assert fold_programme_name(c) == ("sdnp", None)


def test_a_leading_country_word_folds_when_the_remainder_is_another_name() -> None:
    folded = _fold("Soft Drinks Industry Levy", "UK Soft Drinks Industry Levy")
    assert set(folded.values()) == {"Soft Drinks Industry Levy"}


def test_a_leading_country_word_is_kept_when_nothing_matches_the_remainder() -> None:
    folded = _fold("British Heart Foundation Grants", "Wage subsidy")
    assert folded["British Heart Foundation Grants"] == "British Heart Foundation Grants"


def test_an_acronym_name_folds_with_its_expansion() -> None:
    folded = _fold("HENRY", "Healthy Eating and Nutrition in the Really Young (HENRY)")
    assert len(set(folded.values())) == 1


def test_different_programmes_with_a_shared_prefix_stay_two() -> None:
    folded = _fold("Community Eligibility Option", "Community Eligibility Provision (CEP)")
    assert len(set(folded.values())) == 2


def test_possessives_and_punctuation_fold_but_different_keys_stay_two() -> None:
    assert len(set(_fold("Sure Start's", "Sure Start", "Sure-Start").values())) == 1
    assert len(set(_fold("Change4Life", "Change 4 Life").values())) == 2


def test_the_most_frequent_spelling_wins_over_the_shortest() -> None:
    folded = fold_programme_names(["Sure Start Centres"] * 2 + ["sure start centres!"])
    assert set(folded.values()) == {"Sure Start Centres"}
    folded = fold_programme_names(["Sure Start", "Sure Start", "sure  start (SS)", "SURE START"])
    assert set(folded.values()) == {"Sure Start"}
    folded = fold_programme_names(["Long Name Scheme", "Long Name Scheme", "the Long Name Scheme"])
    assert set(folded.values()) == {"Long Name Scheme"}
    folded = fold_programme_names(
        ["The Longer Spelling Scheme", "The Longer Spelling Scheme", "Longer Spelling Scheme"]
    )
    assert set(folded.values()) == {"The Longer Spelling Scheme"}


def test_a_count_tie_goes_to_the_shortest_then_alphabetical() -> None:
    assert set(_fold("the Levy", "Levy").values()) == {"Levy"}
    assert set(_fold("levy", "Levy").values()) == {"Levy"}


def test_folded_seeds_are_listed_under_folded() -> None:
    coverage = _coverage(
        [_member("a", programme_name="Variant 3")],
        folded_seeds=[
            FoldedSeed(name="Apprenticeship  grants", documents=0),
            FoldedSeed(name="Variant 3", documents=2),
        ],
    )
    assert coverage["folded"] == ["Apprenticeship grants", "Variant 3"]


# --- the setting code pass -----------------------------------------------------------


@pytest.mark.parametrize(
    ("setting", "label"),
    [
        ("School settings", "school"),
        ("school setting", "school"),
        ("schools", "school"),
        ("School", "school"),
        ("Primary  schools", "primary school"),
        ("primary care", "primary care"),
        ("local communities", "local community"),
        ("business", "business"),
        ("university campus", "university campus"),
        ("home", "home"),
    ],
)
def test_setting_labels_fold_by_the_one_table(setting: str, label: str) -> None:
    assert len(SETTING_FOLDS) == 3
    assert fold_setting(setting) == label


def test_spelling_variants_of_a_setting_are_one_facet_label() -> None:
    coverage = _coverage(
        [
            _member("a", setting="School settings"),
            _member("b", setting="schools"),
            _member("c", setting="school setting"),
            _member("c", setting="schools"),  # the same document again
            _member("d", setting="Workplaces"),
            _member("e", setting="Jobcentres"),
        ]
    )
    # Grouped by the folded key; shown as the most frequent original spelling.
    assert coverage["settings"] == {"schools": 3, "Jobcentres": 1, "Workplaces": 1}


def test_a_setting_label_tie_goes_to_the_shortest_then_alphabetical() -> None:
    coverage = _coverage(
        [
            _member("a", setting="school settings"),
            _member("b", setting="schools"),
            _member("c", setting="School"),
            _member("d", setting="school"),
        ]
    )
    assert coverage["settings"] == {"School": 4}


def test_a_setting_that_is_a_place_moves_to_an_empty_geography_and_is_logged() -> None:
    with capture_logs() as logs:
        coverage = _coverage([_member("a", setting="Greater Manchester")])
    assert coverage["settings"] == {}
    repairs = [log for log in logs if log["event"] == "longlist.coverage.setting_repair"]
    assert repairs == [
        {
            "event": "longlist.coverage.setting_repair",
            "log_level": "info",
            "action": "moved",
            "setting": "Greater Manchester",
            "unit_kind": "interventions",
        }
    ]


def test_a_setting_naming_a_place_moves_the_place_only() -> None:
    # Review of task 046 (2026-10-12): the geography is the place the setting
    # names, not the whole setting phrase.
    coverage = _coverage([_member("a", setting="community centres in France")])
    assert coverage["settings"] == {}
    # The moved place alone reads as the evaluated country.
    assert coverage["evaluated_countries"] == [{"country": "France", "documents": 1}]


def test_a_place_setting_is_dropped_when_the_geography_is_stated() -> None:
    with capture_logs() as logs:
        coverage = _coverage(
            [_member("a", setting="schools in Leeds", study_geography="Denmark")]
        )
    assert coverage["settings"] == {}
    # The stated geography stands; with no study_country, a geography that is a
    # country is the country (task 046, amendment 4, R87; S32).
    assert coverage["evaluated_countries"] == [{"country": "Denmark", "documents": 1}]
    assert [log["action"] for log in logs if "action" in log] == ["dropped"]


def test_a_nationality_or_a_compound_is_not_a_place() -> None:
    coverage = _coverage(
        [
            _member("a", setting="Scottish schools"),
            _member("b", setting="London-based clinics"),
        ]
    )
    assert coverage["settings"] == {"Scottish schools": 1, "London-based clinics": 1}


@pytest.mark.parametrize(
    ("text", "place"),
    [
        ("Greater Manchester", True),
        ("primary schools in England", True),
        ("UK Jobcentres", True),
        ("Scottish schools", False),
        ("London-based clinics", False),
        ("community centres", False),
        (None, False),
    ],
)
def test_names_place_reads_countries_and_subnational_places_only(
    text: str | None, place: bool
) -> None:
    assert names_place(text) is place


# --- the build and the merge ---------------------------------------------------------


def _tagged_walk(conn: Connection) -> tuple[_Walk, uuid.UUID, uuid.UUID]:
    """A walk whose records are written under the current plan's context."""
    walk = _Walk(conn)
    kept = walk.option("Youth guarantee", origin="added_by_you")
    duplicate = walk.option("Jobs guarantee")
    fingerprint = _current_fingerprint(walk)
    docs: dict[uuid.UUID, uuid.UUID] = {}
    rows = [
        ("youth guarantee", "young people aged 16 to 24", "on_target", "option", "schools"),
        ("youth guarantee", "young adults", "adjacent", "option", "school settings"),
        ("jobs guarantee", "Young adults", "adjacent", "neither", "Greater Manchester"),
        ("jobs guarantee", "long-term unemployed adults", "other", "neither", None),
    ]
    for intervention, population, population_tag, object_tag, setting in rows:
        doc = walk.doc()
        ser = _extraction(walk, doc, fingerprint=fingerprint)
        _record_under(
            walk,
            ser,
            intervention,
            programme_name=intervention,
            unit=population,
            unit_tag=population_tag,
            outcome_tag="other",
            object_tag=object_tag,
            setting=setting,
        )
        docs[doc] = ser
    _rollup_of(walk, walk.scope_id, docs)
    return walk, kept, duplicate


def _routes() -> _Scripted:
    return _Scripted(
        routes={
            "youth guarantee": ("Youth guarantee", False),
            "jobs guarantee": ("Jobs guarantee", False),
        }
    )


def test_the_build_writes_the_new_keys_and_no_tag_removes_a_record(conn: Connection) -> None:
    walk, kept, duplicate = _tagged_walk(conn)
    run_id, summary = walk.build(_routes())
    # Records tagged ``other`` and ``neither`` are still units and members.
    assert summary["units"] == 4
    assert len(walk.memberships()) == 4
    coverage = walk.result(run_id).coverage
    kept_cov, duplicate_cov = coverage[str(kept)], coverage[str(duplicate)]
    assert kept_cov["tried_on"] == [{"unit": "young adults", "documents": 1}]
    assert kept_cov["folded"] == []
    # "schools" and "school settings", once each: the tie goes to the shortest.
    assert kept_cov["settings"] == {"schools": 2}
    # The place setting left the facet.
    assert duplicate_cov["settings"] == {}


def test_coverage_after_a_merge_recomputes_tried_on_and_lists_the_folded_seed(
    conn: Connection,
) -> None:
    walk, kept, duplicate = _tagged_walk(conn)
    walk.build(_routes())
    # The merge: the duplicate's memberships move and it points at the kept one.
    conn.execute(
        update(option_membership)
        .where(option_membership.c.option_id == duplicate)
        .values(option_id=kept)
    )
    conn.execute(
        update(option).where(option.c.option_id == duplicate).values(merged_into_option_id=kept)
    )
    coverage = _recomputed(walk, kept)
    assert coverage["tried_on"] == [{"unit": "Young adults", "documents": 2}]
    # The seed's own members moved: its name is under ``folded``.
    assert coverage["folded"] == ["Jobs guarantee"]


def test_a_folded_seed_counts_its_own_member_documents(conn: Connection) -> None:
    walk, kept, duplicate = _tagged_walk(conn)
    walk.build(_routes())
    # Folded, with its members still its own.
    conn.execute(
        update(option).where(option.c.option_id == duplicate).values(merged_into_option_id=kept)
    )
    coverage = _recomputed(walk, kept)
    assert coverage["folded"] == ["Jobs guarantee"]


def test_an_option_the_user_named_is_never_a_folded_seed(conn: Connection) -> None:
    walk, kept, _duplicate = _tagged_walk(conn)
    named = walk.option("Wage subsidy", origin="added_by_you")
    walk.build(_routes())
    conn.execute(
        update(option).where(option.c.option_id == named).values(merged_into_option_id=kept)
    )
    coverage = _recomputed(walk, kept)
    assert coverage["folded"] == []


# --- the record's programme name and study country (task 046, amendment 3) ---------


def test_coverage_members_carry_the_programme_name_and_study_country(
    conn: Connection,
) -> None:
    from policy_atlas.options_scoping.longlist.longlist import _coverage_member, _own_units

    walk = _Walk(conn)
    fingerprint = _current_fingerprint(walk)
    doc = walk.doc()
    ser = _extraction(walk, doc, fingerprint=fingerprint)
    _record_under(
        walk, ser, "free school meals",
        programme_name="Magic Breakfast", study_country="United Kingdom",
    )
    _rollup_of(walk, walk.scope_id, {doc: ser})
    own = _own_units(
        conn,
        task_id=walk.task_id,
        scope_ids=[walk.scope_id],
        current_fingerprints=frozenset({fingerprint}),
    )
    (unit,) = own.units
    member = _coverage_member(unit, flagged=False)
    assert member.programme_name == "Magic Breakfast"
    assert member.study_country == "United Kingdom"
    assert _member("x").programme_name is None and _member("x").study_country is None


# --- the folded kinds (task 046, amendment 3, R54, R55; S21, S24, A4) ----------------

FOLDS: dict[str, dict[str, str]] = {
    "tried_on": {
        "16 to 24 year olds": "16 to 24 year olds",
        "young people aged 16 to 24": "16 to 24 year olds",
        "Young adults": "young adults",
        "parents": "parents",
    },
    "measures": {
        "arrests": "Reduce crime",
        "reoffending": "Reduce crime",
        "life satisfaction": "wellbeing",
        "earnings": "earnings",
    },
}


def test_without_the_maps_the_kinds_and_other_are_empty() -> None:
    coverage = _coverage(
        [_member("a", unit="parents", outcome="arrests", outcome_tag="other")],
        plan_outcomes=PLAN,
    )
    assert coverage["outcome_counts"]["other"] == []
    assert coverage["outcome_counts"]["by_outcome"][0]["documents"] == 0


def test_a_word_the_map_lacks_keeps_its_own_text() -> None:
    coverage = _coverage(
        [_member("a", outcome="attendance", role="described")],
        folds=FOLDS,
    )
    assert coverage["outcome_counts"]["other"] == [
        {"kind": "attendance", "documents": 1, "evaluated": 0}
    ]


def test_a_record_tagged_other_whose_kind_is_a_plan_outcome_counts_on_that_row_once() -> None:
    coverage = _coverage(
        [
            # One document: a tagged record and two ``other`` records of the
            # plan outcome's kind count it once on the row.
            _member("a", outcome="arrests", outcome_tag="Reduce crime"),
            _member("a", outcome="reoffending", outcome_tag="other"),
            _member("a", outcome="arrests", outcome_tag=None, role="described"),
            # Not tagged, the plan outcome's kind, evaluated.
            _member("b", outcome="reoffending"),
            # Described only: counted in documents, not evaluated.
            _member("c", outcome="arrests", outcome_tag="other", role="described"),
        ],
        plan_outcomes=PLAN,
        folds=FOLDS,
    )
    counts = coverage["outcome_counts"]
    assert _by(counts) == {"Reduce crime": 3, "Improve wellbeing": 0}
    assert _evaluated_by(counts) == {"Reduce crime": 2, "Improve wellbeing": 0}
    assert counts["other"] == []


def test_a_kind_row_counts_only_records_tagged_other_or_not_tagged() -> None:
    coverage = _coverage(
        [
            # Tagged with a plan outcome: its kind is not an ``other`` row.
            _member("a", outcome="earnings", outcome_tag="Improve wellbeing"),
            _member("b", outcome="earnings", outcome_tag="other", role="described"),
            _member("c", outcome="life satisfaction"),
            _member("c", outcome="earnings", outcome_tag="OTHER"),
        ],
        plan_outcomes=PLAN,
        folds=FOLDS,
    )
    counts = coverage["outcome_counts"]
    assert counts["other"] == [
        {"kind": "earnings", "documents": 2, "evaluated": 1},
        {"kind": "wellbeing", "documents": 1, "evaluated": 1},
    ]
    # "wellbeing" is not the plan's text "Improve wellbeing": no cross row.
    assert _by(counts) == {"Reduce crime": 0, "Improve wellbeing": 1}


def test_distinct_words_fold_case_and_space_and_keep_the_first_spelling() -> None:
    members = [
        _member("a", unit="Young adults", outcome="arrests"),
        _member("b", unit="young  adults", outcome=None),
        _member("c", unit="parents", outcome="Arrests"),
        _member("d", unit=None, outcome="  "),
    ]
    assert distinct_words(members, "tried_on") == ["parents", "Young adults"]
    assert distinct_words(members, "measures") == ["Arrests"]


