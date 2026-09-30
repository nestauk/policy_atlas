"""Where tried: two levels read from the record (task 046, amendment 3; R59, R72).

The top level from ``study_country``, the level below from
``study_geography`` as written; counts in documents, DOI-collapsed.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest

from policy_atlas.options_scoping.labels import DocumentLabels
from policy_atlas.options_scoping.longlist import where_tried
from policy_atlas.options_scoping.longlist.coverage import (
    CoverageMember,
    normalise_doi,
    option_coverage,
)
from policy_atlas.options_scoping.longlist.where_tried import (
    MULTIPLE_COUNTRIES,
    NOT_STATED,
    OTHER_PLACE,
    countries_named,
    document_where,
    record_where,
)

_SRC = Path(__file__).resolve().parents[2] / "src" / "policy_atlas"


def _member(
    doc_key: str,
    *,
    country: str | None = None,
    geography: str | None = None,
    tss_id: uuid.UUID | None = None,
) -> CoverageMember:
    return CoverageMember(
        unit_kind="interventions",
        doc_key=doc_key,
        tss_id=tss_id,
        role="evaluated",
        basis="abstract_only",
        flagged=False,
        unit=None,
        setting=None,
        outcome=None,
        study_geography=geography,
        study_country=country,
    )


# --- Per record ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("country", "geography", "top"),
    [
        ("Germany", "Hamburg", "Germany"),
        ("Germany", None, "Germany"),
        ("multiple", "12 high-income countries", MULTIPLE_COUNTRIES),
        ("Multiple", None, MULTIPLE_COUNTRIES),
        ("United Kingdom; United States", None, MULTIPLE_COUNTRIES),
        ("United Kingdom; multiple", None, MULTIPLE_COUNTRIES),
        (None, "a large city", OTHER_PLACE),
        ("", "rural districts", OTHER_PLACE),
        (None, None, NOT_STATED),
        ("  ", " ", NOT_STATED),
    ],
)
def test_a_record_s_top_level(country: str | None, geography: str | None, top: str) -> None:
    assert record_where(country, geography) == top


def test_the_same_country_twice_in_a_record_is_one_country() -> None:
    assert record_where("United Kingdom; united kingdom", None) == "United Kingdom"
    assert countries_named("United Kingdom;  united kingdom ; France") == (
        ["United Kingdom", "France"],
        False,
    )


def test_countries_named_reads_multiple_apart() -> None:
    assert countries_named("multiple") == ([], True)
    assert countries_named(None) == ([], False)


# --- Per document --------------------------------------------------------------


def test_a_document_whose_records_agree_is_that_country() -> None:
    assert document_where([("Germany", "Hamburg"), ("germany", None), (None, "Berlin")]) == (
        "Germany",
        ["Germany"],
    )


def test_a_document_whose_records_give_two_countries_is_multiple() -> None:
    assert document_where([("United Kingdom", "Leeds"), ("France", "Lyon")]) == (
        MULTIPLE_COUNTRIES,
        ["United Kingdom", "France"],
    )


def test_a_document_with_a_multiple_record_is_multiple() -> None:
    assert document_where([("Germany", None), ("multiple", None)]) == (
        MULTIPLE_COUNTRIES,
        ["Germany"],
    )


def test_a_document_with_a_place_and_no_country_is_other() -> None:
    assert document_where([(None, None), (None, "a coastal town")]) == (OTHER_PLACE, [])


def test_a_document_with_nothing_stated_is_not_stated() -> None:
    assert document_where([(None, None)]) == (NOT_STATED, [])
    assert document_where([]) == (NOT_STATED, [])


# --- Coverage: the two levels, counted in documents ---------------------------


def _where(members: list[CoverageMember]) -> list[dict[str, object]]:
    where: list[dict[str, object]] = option_coverage(members, labels={})["where_tried"]
    return where


def test_coverage_counts_documents_under_one_top_level_each() -> None:
    where = _where(
        [
            _member("doc:a", country="Germany", geography="Hamburg"),
            _member("doc:a", country="Germany", geography="Hamburg"),
            _member("doc:b", country="Germany", geography="Berlin"),
            _member("doc:c", country="multiple", geography="12 high-income countries"),
            _member("doc:d", geography="a coastal town"),
            _member("doc:e"),
        ]
    )
    assert where == [
        {
            "top": "Germany",
            "documents": 2,
            "places": [
                {"place": "Berlin", "documents": 1},
                {"place": "Hamburg", "documents": 1},
            ],
            "countries": [],
        },
        {
            "top": "multiple countries",
            "documents": 1,
            "places": [{"place": "12 high-income countries", "documents": 1}],
            "countries": [],
        },
        {"top": "not stated", "documents": 1, "places": [], "countries": []},
        {
            "top": "other",
            "documents": 1,
            "places": [{"place": "a coastal town", "documents": 1}],
            "countries": [],
        },
    ]


def test_multiple_countries_carries_its_component_countries() -> None:
    where = _where(
        [
            _member("doc:a", country="United Kingdom; United States"),
            _member("doc:b", country="France", geography="Lyon"),
            _member("doc:b", country="united kingdom", geography="Leeds"),
        ]
    )
    assert where == [
        {
            "top": "multiple countries",
            "documents": 2,
            "places": [
                {"place": "Leeds", "documents": 1},
                {"place": "Lyon", "documents": 1},
            ],
            "countries": ["France", "United Kingdom", "United States"],
        }
    ]


def test_country_case_is_folded_and_one_spelling_is_shown() -> None:
    where = _where(
        [
            _member("doc:a", country="united kingdom", geography="leeds"),
            _member("doc:b", country="United Kingdom", geography="Leeds"),
        ]
    )
    assert where == [
        {
            "top": "United Kingdom",
            "documents": 2,
            "places": [{"place": "Leeds", "documents": 2}],
            "countries": [],
        }
    ]


def test_doi_twins_count_once_under_where_tried() -> None:
    doc = "doi:10.1/abc"
    where = _where(
        [
            _member(doc, country="Canada", geography="Ontario", tss_id=uuid.uuid4()),
            _member(doc, country="Canada", geography="Ontario", tss_id=uuid.uuid4()),
        ]
    )
    assert where == [
        {
            "top": "Canada",
            "documents": 1,
            "places": [{"place": "Ontario", "documents": 1}],
            "countries": [],
        }
    ]


def test_an_option_with_no_member_has_no_where_tried() -> None:
    coverage = option_coverage([], labels={})
    assert coverage["where_tried"] == []
    assert "countries" not in coverage


# --- The old matcher is gone ---------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "where_group",
        "where_codes",
        "where_labels",
        "countries_in",
        "OECD_CODES",
        "COMPARABLE_LABEL",
        "WHERE_GROUPS",
        "WhereGroup",
        "COUNTRY_ADJECTIVES",
        "COUNTRY_GROUPS",
        "OECD_MARKERS",
    ],
)
def test_the_old_matcher_is_not_importable(name: str) -> None:
    assert not hasattr(where_tried, name)


@pytest.mark.parametrize(
    "path",
    [
        "options_scoping/longlist/where_tried.py",
        "options_scoping/longlist/coverage.py",
        "api/readmodels/repository.py",
        "api/contract/read_models.py",
    ],
)
def test_no_comparable_systems_or_oecd_label_remains(path: str) -> None:
    text = (_SRC / path).read_text(encoding="utf-8")
    assert not re.search(r"comparable systems", text, re.IGNORECASE)
    assert "OECD" not in text


def test_where_tried_reads_nothing_of_the_publisher() -> None:
    text = (_SRC / "options_scoping/longlist/where_tried.py").read_text(encoding="utf-8")
    code = text.split("# --- The place strip")[0].split('"""', 2)[2]
    for word in ("publisher", "journal", "institution", "venue", "metadata"):
        assert word not in code


# --- Counting grain (kept from task 045) ---------------------------------------


@pytest.mark.parametrize(
    ("metadata", "doi"),
    [
        ({"doi": "https://doi.org/10.1/ABC"}, "10.1/abc"),
        ({"doi": " doi:10.1/abc "}, "10.1/abc"),
        ({"doi": ""}, None),
        ({}, None),
    ],
)
def test_the_doi_is_normalised_for_counting(metadata: dict[str, str], doi: str | None) -> None:
    assert normalise_doi(metadata) == doi


@pytest.mark.parametrize("rated_first", [True, False])
def test_doi_twins_take_the_rated_twin_s_labels_in_either_id_order(rated_first: bool) -> None:
    low, high = sorted([uuid.uuid4(), uuid.uuid4()], key=str)
    rated, unrated = (low, high) if rated_first else (high, low)
    labels = {
        rated: DocumentLabels(
            evidence_type="RCTs and Quasi-Experimental Studies",
            quality_score=4,
            rubric_version="v",
            provenance="own",
        ),
        unrated: DocumentLabels(
            evidence_type=None, quality_score=None, rubric_version=None, provenance="absent"
        ),
    }
    members = [
        CoverageMember(
            unit_kind="interventions",
            doc_key="doi:10.1/abc",
            tss_id=tss,
            role=role,
            basis="abstract_only",
            flagged=False,
            unit=None,
            setting=None,
            outcome=None,
            study_geography=None,
        )
        for tss, role in ((rated, "evaluated"), (unrated, "mentioned"))
    ]
    coverage = option_coverage(members, labels=labels)
    assert coverage["documents"] == 1
    assert coverage["evidence_type"] == {"RCTs and Quasi-Experimental Studies": 1}
    assert coverage["tier"] == {"4": 1}
    assert coverage["role"]["evaluated"] == 1 and coverage["role"]["mentioned"] == 1
