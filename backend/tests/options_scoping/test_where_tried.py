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
        # No place under "multiple countries" (task 046, amendment 4, R87; S32).
        {"top": "multiple countries", "documents": 1, "places": [], "countries": []},
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
            # No place under "multiple countries" (task 046, amendment 4, R87; S32).
            "places": [],
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


# --- The country resolver (task 046, amendment 4; R87, S29a) -------------------


@pytest.mark.parametrize(
    ("text", "code", "name"),
    [
        ("Tajikistan", "TJ", "Tajikistan"),
        ("Paraguay", "PY", "Paraguay"),
        ("Jordan", "JO", "Jordan"),
        ("Lebanon", "LB", "Lebanon"),
        ("New South Wales", "AU", "Australia"),
        ("bolivia", "BO", "Bolivia"),
        ("bolivia (plurinational state of)", "BO", "Bolivia"),
        ("iran", "IR", "Iran"),
        ("korea (the republic of)", "KR", "South Korea"),
        ("North  Korea", "KP", "North Korea"),
        ("The Netherlands", "NL", "Netherlands"),
        ("Viet Nam", "VN", "Vietnam"),
        ("Côte d’Ivoire", "CI", "Côte d'Ivoire"),
        ("USA", "US", "United States"),
    ],
)
def test_the_resolver_knows_every_country(text: str, code: str, name: str) -> None:
    assert where_tried.resolve_country(text) == (code, name)


@pytest.mark.parametrize(
    "text",
    [
        "UK",
        "U.K.",
        "England",
        "Scotland",
        "Wales",
        "Northern Ireland",
        "Britain",
        "Great Britain",
        "the United Kingdom",
        "united kingdom of great britain and northern ireland",
    ],
)
def test_the_united_kingdom_s_names_resolve_to_it(text: str) -> None:
    assert where_tried.resolve_country(text) == ("GB", "United Kingdom")


@pytest.mark.parametrize("text", ["Hamburg", "Narnia", "us", "", "  ", None])
def test_an_unknown_place_resolves_to_nothing(text: str | None) -> None:
    assert where_tried.resolve_country(text) is None


def test_every_iso_country_has_one_short_name_and_a_table_entry() -> None:
    from policy_atlas.evidence_search.sourcing.country_filters import ISO_3166_ALPHA2

    names = where_tried.COUNTRY_DISPLAY_NAMES
    assert set(names) == set(ISO_3166_ALPHA2)
    assert [name for name in names.values() if "(" in name] == ["Cocos (Keeling) Islands"]
    assert not [name for name in names.values() if "*" in name or "[" in name]
    assert set(where_tried.COUNTRY_NAMES.values()) == set(ISO_3166_ALPHA2)


def test_the_old_aliases_are_kept() -> None:
    for alias, code in (
        ("britain", "GB"),
        ("great britain", "GB"),
        ("holland", "NL"),
        ("türkiye", "TR"),
        ("dprk", "KP"),
        ("czechia", "CZ"),
        ("hong kong", "HK"),
    ):
        assert where_tried.COUNTRY_NAMES[alias] == code


@pytest.mark.parametrize(
    ("text", "key"),
    [("South West", "southwest"), ("south-west", "southwest"), ("the  Southwest", "southwest")],
)
def test_the_place_key_folds_hyphens_spaces_and_the(text: str, key: str) -> None:
    assert where_tried.place_key(text) == key


# --- The evidence signal and the place checks (R76, R87; S29, S32) ------------


def _signal_member(
    doc_key: str,
    *,
    role: str = "evaluated",
    country: str | None = None,
    geography: str | None = None,
    outcome_tag: str | None = None,
) -> CoverageMember:
    return CoverageMember(
        unit_kind="interventions",
        doc_key=doc_key,
        tss_id=None,
        role=role,
        basis="abstract_only",
        flagged=False,
        unit=None,
        setting=None,
        outcome=None,
        study_geography=geography,
        study_country=country,
        outcome_tag=outcome_tag,
    )


def _countries(members: list[CoverageMember], where: str | None = None) -> list[object]:
    coverage = option_coverage(members, labels={}, where_country=where)
    countries: list[object] = coverage["evaluated_countries"]
    return countries


def test_a_describing_document_s_country_is_not_an_evaluated_country() -> None:
    members = [
        _signal_member("doc:a", country="France"),
        _signal_member("doc:b", role="described", country="Germany"),
        _signal_member("doc:c", role="recommended", country="Spain"),
    ]
    coverage = option_coverage(members, labels={})
    assert coverage["evaluated_countries"] == [{"country": "France", "documents": 1}]
    # The describing count the reader is served is documents − evaluated (C10).
    assert coverage["documents"] - coverage["role"]["evaluated"] == 2


def test_an_evaluated_country_comes_from_the_evaluating_members_only() -> None:
    # Review of task 046 (2026-10-12): a describing record of the same
    # document names no evaluated place, and does not make it "multiple".
    members = [
        _signal_member("doc:a"),  # evaluated, no country
        _signal_member("doc:a", role="described", country="France"),
        _signal_member("doc:b", country="United Kingdom"),
        _signal_member("doc:b", role="described", country="France"),
    ]
    assert _countries(members) == [{"country": "United Kingdom", "documents": 1}]


def test_a_document_of_two_countries_or_other_counts_for_no_country() -> None:
    members = [
        _signal_member("doc:a", country="France; Germany"),
        _signal_member("doc:b", country="multiple"),
        _signal_member("doc:c", country="Spain"),
        _signal_member("doc:c", country="Italy"),  # two countries between its records
        _signal_member("doc:d", geography="a coastal town"),  # "other"
        _signal_member("doc:e"),  # "not stated"
    ]
    assert _countries(members) == []


def test_england_in_the_where_puts_the_united_kingdom_first() -> None:
    members = [
        _signal_member("doc:a", country="England"),
        _signal_member("doc:b", country="United Kingdom"),
        _signal_member("doc:c", country="France"),
        _signal_member("doc:d", country="France"),
        _signal_member("doc:e", country="France"),
    ]
    assert _countries(members) == [
        {"country": "France", "documents": 3},
        {"country": "United Kingdom", "documents": 2},
    ]
    resolved = where_tried.resolve_country("England")
    assert resolved is not None
    assert _countries(members, resolved[1]) == [
        {"country": "United Kingdom", "documents": 2},
        {"country": "France", "documents": 3},
    ]
    # The raw text resolves the same way.
    assert _countries(members, "England")[0] == {"country": "United Kingdom", "documents": 2}


def test_a_where_the_resolver_cannot_map_keeps_count_order() -> None:
    members = [
        _signal_member("doc:a", country="Denmark"),
        _signal_member("doc:b", country="France"),
        _signal_member("doc:c", country="France"),
    ]
    expected = [{"country": "France", "documents": 2}, {"country": "Denmark", "documents": 1}]
    assert _countries(members, "the Shire") == expected
    assert _countries(members, None) == expected


def test_a_one_outcome_plan_with_one_evaluating_document_measures_one() -> None:
    coverage = option_coverage(
        [
            _signal_member("doc:a", outcome_tag="The  NEET rate"),
            _signal_member("doc:b", role="described", outcome_tag="earnings"),
        ],
        labels={},
        plan_outcomes=["the NEET rate"],
    )
    assert coverage["outcomes_evaluated"] == 1
    assert len(coverage["outcome_counts"]["by_outcome"]) == 1
    described_only = option_coverage(
        [_signal_member("doc:a", role="described", outcome_tag="the NEET rate")],
        labels={},
        plan_outcomes=["the NEET rate", "earnings"],
    )
    assert described_only["outcomes_evaluated"] == 0


def test_an_unknown_country_is_kept_as_written_and_counted() -> None:
    coverage = option_coverage(
        [
            _signal_member("doc:a", country="Narnia"),
            _signal_member("doc:b", role="described", country="Narnia"),
            _signal_member("doc:c", country="France"),
        ],
        labels={},
    )
    assert coverage["evaluated_countries"] == [
        {"country": "France", "documents": 1},
        {"country": "Narnia", "documents": 1},
    ]
    # Every document under the unknown top level, whatever its role (R87).
    assert coverage["places_unknown_country"] == [{"country": "Narnia", "documents": 2}]


def test_the_empty_coverage_carries_the_signal_keys() -> None:
    coverage = option_coverage([], labels={})
    assert coverage["evaluated_countries"] == []
    assert coverage["outcomes_evaluated"] == 0
    assert coverage["places_unknown_country"] == []


def _places(members: list[CoverageMember]) -> dict[str, list[object]]:
    return {entry["top"]: entry["places"] for entry in _where(members)}  # type: ignore[misc]


def test_south_west_spellings_are_one_place() -> None:
    places = _places(
        [
            _signal_member("doc:a", country="United Kingdom", geography="south-west"),
            _signal_member("doc:b", country="United Kingdom", geography="Southwest"),
            _signal_member("doc:c", country="United Kingdom", geography="the South West"),
        ]
    )
    assert places["United Kingdom"] == [{"place": "Southwest", "documents": 3}]


def test_an_organisation_as_a_geography_stays_as_written() -> None:
    places = _places(
        [_signal_member("doc:a", country="Spain", geography="Spanish Ministry of Health")]
    )
    assert places == {"Spain": [{"place": "Spanish Ministry of Health", "documents": 1}]}


def test_a_geography_that_is_the_record_s_country_has_no_place_below() -> None:
    places = _places(
        [
            _signal_member("doc:a", country="United Kingdom", geography="Scotland"),
            _signal_member("doc:b", country="United Kingdom", geography="UK"),
            _signal_member("doc:c", country="United Kingdom", geography="London"),
        ]
    )
    # "London" is a place within the country, kept below it.
    assert places == {"United Kingdom": [{"place": "London", "documents": 1}]}


def test_a_geography_of_another_country_stays_the_place_below() -> None:
    places = _places(
        [_signal_member("doc:a", country="United Kingdom", geography="Georgia")]
    )
    assert places == {"United Kingdom": [{"place": "Georgia", "documents": 1}]}


def test_a_country_geography_with_no_country_is_the_top_level() -> None:
    coverage = option_coverage([_signal_member("doc:a", geography="Wales")], labels={})
    assert coverage["where_tried"] == [
        {"top": "Wales", "documents": 1, "places": [], "countries": []}
    ]
    assert coverage["evaluated_countries"] == [{"country": "United Kingdom", "documents": 1}]


def test_a_geography_under_multiple_countries_is_no_place_and_no_country() -> None:
    coverage = option_coverage(
        [_signal_member("doc:a", country="multiple", geography="France")], labels={}
    )
    assert coverage["where_tried"][0]["places"] == []
    assert coverage["evaluated_countries"] == []
