"""The maturity rung and its coverage inputs (task 055, item 7; contract A3)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from policy_atlas.api.readmodels.repository import _year
from policy_atlas.core.schema import EVIDENCE_TYPES
from policy_atlas.options_scoping.labels import DocumentLabels
from policy_atlas.options_scoping.longlist.coverage import (
    CoverageMember,
    document_year,
    empty_coverage,
    option_coverage,
)
from policy_atlas.options_scoping.longlist.maturity import (
    MATURITY_RECENT_YEARS,
    REVIEW_EVIDENCE_TYPE,
    maturity_of,
)

RCT = "RCTs and Quasi-Experimental Studies"
OBS = "Observational Research Studies"


def test_the_review_type_is_in_the_classify_vocabulary() -> None:
    assert REVIEW_EVIDENCE_TYPE in EVIDENCE_TYPES


@pytest.mark.parametrize(
    "metadata",
    [
        {"publication_year": 2019, "year": 2001},
        {"year": 2020},
        {"publication_year": "2019", "year": True},
        {},
    ],
)
def test_the_year_rule_agrees_with_the_read_path(metadata: dict[str, Any]) -> None:
    assert document_year(metadata) == _year(metadata)


def test_a_missing_metadata_has_no_year() -> None:
    assert document_year(None) is None


def _member(doc: str, tss: uuid.UUID | None = None, **values: Any) -> CoverageMember:
    fields: dict[str, Any] = {
        "unit_kind": "interventions",
        "doc_key": f"doc:{doc}",
        "tss_id": tss,
        "role": "evaluated",
        "basis": "full_text",
        "flagged": False,
        "unit": None,
        "setting": None,
        "outcome": None,
        "study_geography": None,
    }
    fields.update(values)
    return CoverageMember(**fields)


def _label(evidence_type: str) -> DocumentLabels:
    return DocumentLabels(
        evidence_type=evidence_type, quality_score=None, rubric_version=None, provenance="own"
    )


def test_coverage_counts_types_and_years_over_evaluating_documents_only() -> None:
    a, b, c, d = (uuid.uuid4() for _ in range(4))
    members = [
        _member("a", a, year=2018),
        _member("b", b, year=2022),
        _member("c", c, role="described", year=2025),
        _member("d", d, role="recommended"),
    ]
    labels = {a: _label(RCT), b: _label(OBS), c: _label(OBS), d: _label(OBS)}
    coverage = option_coverage(members, labels=labels)
    assert coverage["evaluating_evidence_type"] == {OBS: 1, RCT: 1}
    assert coverage["evidence_type"] == {OBS: 3, RCT: 1}
    assert coverage["latest_evaluation_year"] == 2022


def test_doi_twins_count_once_and_take_the_newest_year() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    members = [
        _member("x", a, doc_key="doi:10.1/x", year=2015),
        _member("x2", b, doc_key="doi:10.1/x", year=2021),
        _member("y", None, doc_key="doc:y", year=None),
    ]
    coverage = option_coverage(members, labels={a: _label(RCT), b: _label(RCT)})
    assert sum(coverage["evaluating_evidence_type"].values()) == 2
    assert coverage["latest_evaluation_year"] == 2021


def test_no_evaluation_leaves_the_year_empty() -> None:
    coverage = option_coverage([_member("a", role="described", year=2024)], labels={})
    assert coverage["evaluating_evidence_type"] == {}
    assert coverage["latest_evaluation_year"] is None
    assert empty_coverage()["latest_evaluation_year"] is None


def _entry(**keys: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "role": {"evaluated": 0, "described": 0, "recommended": 0},
        "evaluating_evidence_type": {},
        "evaluated_countries": [],
        "latest_evaluation_year": None,
    }
    entry.update(keys)
    return entry


def test_the_four_rungs() -> None:
    def rung(**keys: Any) -> str:
        found = maturity_of(_entry(**keys), where_country=None, today_year=2026)
        assert found is not None
        return found.rung

    assert rung() == "proposal_only"
    assert rung(role={"evaluated": 0, "described": 1, "recommended": 0}) == "described"
    assert rung(role={"evaluated": 0, "described": 0, "recommended": 2}) == "described"
    assert rung(role={"evaluated": 1}, evaluating_evidence_type={OBS: 1}) == "evaluated"
    assert (
        rung(role={"evaluated": 2}, evaluating_evidence_type={OBS: 1, REVIEW_EVIDENCE_TYPE: 1})
        == "reviewed"
    )


def test_an_option_with_no_document_is_proposal_only() -> None:
    found = maturity_of(empty_coverage(), where_country="France", today_year=2026)
    assert found is not None
    assert (found.rung, found.design_mix, found.none_in_your_setting, found.stale) == (
        "proposal_only",
        "",
        False,
        False,
    )


def test_the_design_mix_reads_most_frequent_first() -> None:
    found = maturity_of(
        _entry(role={"evaluated": 3}, evaluating_evidence_type={RCT: 1, OBS: 2}),
        where_country=None,
        today_year=2026,
    )
    assert found is not None
    assert found.design_mix == f"2 {OBS}, 1 {RCT}"


def test_none_in_your_setting() -> None:
    kwargs = {
        "role": {"evaluated": 2},
        "evaluating_evidence_type": {OBS: 2},
        "evaluated_countries": [{"country": "Spain", "documents": 2}],
    }

    def flag(where: str | None) -> bool:
        found = maturity_of(_entry(**kwargs), where_country=where, today_year=2026)
        assert found is not None
        return found.none_in_your_setting

    assert flag("France") is True
    assert flag("spain") is False
    assert flag(None) is False
    undescribed = maturity_of(
        _entry(role={"described": 1}), where_country="France", today_year=2026
    )
    assert undescribed is not None
    assert undescribed.none_in_your_setting is False


def test_stale_when_the_newest_evaluation_is_older_than_five_years() -> None:
    def stale(year: int | None) -> bool:
        found = maturity_of(
            _entry(role={"evaluated": 1}, latest_evaluation_year=year),
            where_country=None,
            today_year=2026,
        )
        assert found is not None
        return found.stale

    assert MATURITY_RECENT_YEARS == 5
    assert stale(2021) is False
    assert stale(2020) is True
    assert stale(None) is False


def test_an_older_coverage_entry_has_no_rung() -> None:
    old = {"documents": 3, "role": {"evaluated": 1, "described": 0, "recommended": 0}}
    assert maturity_of(old, where_country=None, today_year=2026) is None
