"""Coverage additions of task 046 (S11; AM20; contract items 14 and 23).

The counts by population tag, *tried on* (the adjacent members'
populations), the *variants* (folded seeds first), and the setting code
pass on the read side: folded setting labels, and a setting that names a
place read as the study geography (or left out of the facet), counted and
logged. A tag sorts and never removes a record.
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
    VARIANTS_MAX,
    CoverageMember,
    FoldedSeed,
    empty_coverage,
    fold_setting,
    option_coverage,
)
from policy_atlas.options_scoping.longlist.longlist import membership_coverage
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


# --- counts by population tag ------------------------------------------------------


def test_population_tags_are_counted_by_document_with_not_tagged() -> None:
    coverage = _coverage(
        [
            _member("a", unit_tag="on_target"),
            _member("a", unit_tag="on_target"),  # one document
            _member("b", unit_tag="adjacent"),
            _member("c", unit_tag="other"),
            _member("d"),  # another context, or a linked finding
        ]
    )
    assert coverage["population_tags"] == {
        "on_target": 1,
        "adjacent": 1,
        "other": 1,
        "not_tagged": 1,
    }


def test_an_option_with_no_member_has_every_new_key_empty() -> None:
    coverage = _coverage([])
    assert coverage["population_tags"] == dict.fromkeys(
        ("on_target", "adjacent", "other", "not_tagged"), 0
    )
    assert coverage["tried_on"] == []
    assert coverage["variants"] == []
    assert coverage["setting_repairs"] == 0


# --- outcome counts (R42) ------------------------------------------------------------

PLAN = ["Reduce crime", "Improve wellbeing"]


def _counts(members: list[CoverageMember], plan: list[str] = PLAN) -> dict[str, Any]:
    counts: dict[str, Any] = _coverage(members, plan_outcomes=plan)["outcome_counts"]
    return counts


def _by(counts: dict[str, Any]) -> dict[str, int]:
    return {item["outcome"]: item["documents"] for item in counts["by_outcome"]}


def test_a_document_evaluating_two_outcomes_counts_for_both_and_once_overall() -> None:
    counts = _counts(
        [
            _member("a", outcome_tag="Reduce crime"),
            _member("a", outcome_tag="Improve wellbeing"),
        ]
    )
    assert counts["evaluating_documents"] == 1
    assert _by(counts) == {"Reduce crime": 1, "Improve wellbeing": 1}


def test_a_described_record_with_a_plan_outcome_tag_counts_for_nothing() -> None:
    counts = _counts([_member("a", role="described", outcome_tag="Reduce crime")])
    assert counts["evaluating_documents"] == 0
    assert _by(counts) == {"Reduce crime": 0, "Improve wellbeing": 0}


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
        {"outcome": "Reduce crime", "documents": 0},
        {"outcome": "Improve wellbeing", "documents": 1},
    ]


def test_empty_coverage_has_the_outcome_counts_key() -> None:
    assert empty_coverage()["outcome_counts"] == {"evaluating_documents": 0, "by_outcome": []}


# --- tried on ------------------------------------------------------------------------


def test_tried_on_lists_adjacent_populations_by_document_folded() -> None:
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
        {"population": "YOUNG ADULTS", "documents": 2},
        {"population": "older workers", "documents": 1},
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
    assert tried_on[0] == {"population": "group c", "documents": 3}


# --- variants ------------------------------------------------------------------------


def test_variants_are_distinct_folded_names_by_document() -> None:
    coverage = _coverage(
        [
            _member("a", intervention="Youth Guarantee"),
            _member("b", intervention="youth  guarantee"),
            _member("b", intervention="youth guarantee"),  # the same document
            _member("c", intervention="wage subsidy"),
        ]
    )
    assert coverage["variants"] == [
        {"name": "Youth Guarantee", "documents": 2, "folded_seed": False},
        {"name": "wage subsidy", "documents": 1, "folded_seed": False},
    ]


def test_folded_seeds_come_first_and_the_list_is_capped_at_eight() -> None:
    members = [
        _member(f"{i}-{n}", intervention=f"variant {i}") for i in range(10) for n in range(i + 1)
    ]
    coverage = _coverage(
        members,
        folded_seeds=[
            FoldedSeed(name="Apprenticeship grants", documents=0),
            # A member name too: one entry, with the larger count (4 documents).
            FoldedSeed(name="Variant 3", documents=2),
        ],
    )
    variants = coverage["variants"]
    assert len(variants) == VARIANTS_MAX == 8
    assert variants[:2] == [
        {"name": "Variant 3", "documents": 4, "folded_seed": True},
        {"name": "Apprenticeship grants", "documents": 0, "folded_seed": True},
    ]
    assert [v["name"] for v in variants[2:]] == [f"variant {i}" for i in (9, 8, 7, 6, 5, 4)]
    assert all(not v["folded_seed"] for v in variants[2:])


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
    assert coverage["setting_repairs"] == 0


def test_a_setting_that_is_a_place_moves_to_an_empty_geography_and_is_logged() -> None:
    with capture_logs() as logs:
        coverage = _coverage([_member("a", setting="Greater Manchester")])
    assert coverage["settings"] == {}
    # No study_country: the moved place is "other", its text below (R59).
    assert coverage["where_tried"] == [
        {
            "top": "other",
            "documents": 1,
            "places": [{"place": "Greater Manchester", "documents": 1}],
            "countries": [],
        }
    ]
    assert coverage["setting_repairs"] == 1
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


def test_a_place_setting_is_dropped_when_the_geography_is_stated() -> None:
    with capture_logs() as logs:
        coverage = _coverage(
            [_member("a", setting="schools in Leeds", study_geography="Denmark")]
        )
    assert coverage["settings"] == {}
    # The stated geography stands (no study_country: "other", Denmark below).
    assert coverage["where_tried"][0]["places"] == [{"place": "Denmark", "documents": 1}]
    assert coverage["setting_repairs"] == 1
    assert [log["action"] for log in logs if "action" in log] == ["dropped"]


def test_a_nationality_or_a_compound_is_not_a_place() -> None:
    coverage = _coverage(
        [
            _member("a", setting="Scottish schools"),
            _member("b", setting="London-based clinics"),
        ]
    )
    assert coverage["settings"] == {"Scottish schools": 1, "London-based clinics": 1}
    assert coverage["setting_repairs"] == 0


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
    assert kept_cov["population_tags"] == {
        "on_target": 1,
        "adjacent": 1,
        "other": 0,
        "not_tagged": 0,
    }
    assert kept_cov["tried_on"] == [{"population": "young adults", "documents": 1}]
    assert kept_cov["variants"] == [
        {"name": "youth guarantee", "documents": 2, "folded_seed": False}
    ]
    # "schools" and "school settings", once each: the tie goes to the shortest.
    assert kept_cov["settings"] == {"schools": 2}
    assert duplicate_cov["setting_repairs"] == 1
    assert {e["top"]: e["documents"] for e in duplicate_cov["where_tried"]} == {
        "other": 1,
        "not stated": 1,
    }
    assert duplicate_cov["population_tags"]["other"] == 1


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
    coverage = membership_coverage(
        conn,
        task_id=walk.task_id,
        scope_id=walk.scope_id,
        option_ids=[kept],
    )[str(kept)]
    assert coverage["tried_on"] == [{"population": "Young adults", "documents": 2}]
    # The seed's own members moved, so its entry counts the moved members
    # that carry its name.
    assert coverage["variants"] == [
        {"name": "Jobs guarantee", "documents": 2, "folded_seed": True},
        {"name": "youth guarantee", "documents": 2, "folded_seed": False},
    ]
    assert coverage["setting_repairs"] == 1


def test_a_folded_seed_counts_its_own_member_documents(conn: Connection) -> None:
    walk, kept, duplicate = _tagged_walk(conn)
    walk.build(_routes())
    # Folded, with its members still its own.
    conn.execute(
        update(option).where(option.c.option_id == duplicate).values(merged_into_option_id=kept)
    )
    coverage = membership_coverage(
        conn,
        task_id=walk.task_id,
        scope_id=walk.scope_id,
        option_ids=[kept],
    )[str(kept)]
    assert coverage["variants"][0] == {
        "name": "Jobs guarantee",
        "documents": 2,
        "folded_seed": True,
    }


def test_an_option_the_user_named_is_never_a_folded_seed(conn: Connection) -> None:
    walk, kept, _duplicate = _tagged_walk(conn)
    named = walk.option("Wage subsidy", origin="added_by_you")
    walk.build(_routes())
    conn.execute(
        update(option).where(option.c.option_id == named).values(merged_into_option_id=kept)
    )
    coverage = membership_coverage(
        conn,
        task_id=walk.task_id,
        scope_id=walk.scope_id,
        option_ids=[kept],
    )[str(kept)]
    assert all(not v["folded_seed"] for v in coverage["variants"])


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
