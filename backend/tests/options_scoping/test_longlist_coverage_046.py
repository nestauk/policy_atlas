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
        "population": None,
        "setting": None,
        "outcome": None,
        "study_geography": None,
    }
    fields.update(values)
    return CoverageMember(**fields)


def _coverage(members: list[CoverageMember], **kwargs: Any) -> dict[str, Any]:
    return option_coverage(members, labels={}, home=frozenset({"GB"}), **kwargs)


# --- counts by population tag ------------------------------------------------------


def test_population_tags_are_counted_by_document_with_not_tagged() -> None:
    coverage = _coverage(
        [
            _member("a", population_tag="on_target"),
            _member("a", population_tag="on_target"),  # one document
            _member("b", population_tag="adjacent"),
            _member("c", population_tag="other"),
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


# --- tried on ------------------------------------------------------------------------


def test_tried_on_lists_adjacent_populations_by_document_folded() -> None:
    coverage = _coverage(
        [
            _member("a", population="Young  adults", population_tag="adjacent"),
            _member("a", population="young adults", population_tag="adjacent"),  # same doc
            _member("b", population="YOUNG ADULTS", population_tag="adjacent"),
            _member("c", population="older workers", population_tag="adjacent"),
            _member("d", population="young people not in work", population_tag="on_target"),
            _member("e", population="firms", population_tag="other"),
            _member("f", population=None, population_tag="adjacent"),
        ]
    )
    assert coverage["tried_on"] == [
        {"population": "YOUNG ADULTS", "documents": 2},
        {"population": "older workers", "documents": 1},
    ]


def test_tried_on_is_capped_at_eight_by_documents_then_text() -> None:
    members = [
        _member(f"{name}-{n}", population=name, population_tag="adjacent")
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
    assert coverage["where_tried"]["where"] == 1
    assert coverage["countries"] == {"GB": 1}
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
    assert coverage["countries"] == {"DK": 1}  # the stated geography stands
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
            population=population,
            population_tag=population_tag,
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
    assert duplicate_cov["where_tried"]["where"] == 1
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
        where="United Kingdom",
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
        where="United Kingdom",
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
        where="United Kingdom",
        option_ids=[kept],
    )[str(kept)]
    assert all(not v["folded_seed"] for v in coverage["variants"])
