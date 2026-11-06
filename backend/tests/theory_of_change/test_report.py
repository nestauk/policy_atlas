"""Detailed information as a narrative report (task 054, C38): rows, checks, numbering, step."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.engine import Engine

from policy_atlas.api.routers.toc import toc_graph_out
from policy_atlas.core.model_routes import route
from policy_atlas.theory_of_change.backend import StubTocBackend
from policy_atlas.theory_of_change.report import (
    ROW_FALLBACK,
    LinkFacts,
    TextChecker,
    assumption_rows,
    citation,
    method_note,
    publisher,
    renumber,
    weakest_links,
)
from policy_atlas.theory_of_change.report_prompt import (
    ConnectionReasonWire,
    PathwayLineWire,
    ReportResponse,
    WhatToTestWire,
)
from tests.theory_of_change.test_check_steps import _run, _summary


def _link(code: str, verdict: str, **values: Any) -> LinkFacts:
    base: dict[str, Any] = {
        "key": code,
        "code": code,
        "source_code": "S1",
        "target_code": "L1",
        "sentence": f"Step {code}.",
        "verdict": verdict,
        "evidence_sentence": None,
        "critical": False,
        "conditions": [],
        "on_failure": False,
        "on_success": True,
        "on_pathways": 1,
    }
    return LinkFacts(**{**base, **values})


LINKS = [
    _link("#1", "supported", conditions=["c1a", "c1b", "c1c"], on_pathways=4),
    _link("#2", "not_sure_mixed", critical=True, conditions=["c2a", "c2b"], on_pathways=3),
    _link("#3", "against", conditions=["c3a"]),
    _link(
        "#4",
        "not_sure_insufficient",
        target_code="F1",
        on_failure=True,
        on_success=False,
        on_pathways=0,
    ),
    # On no kept pathway: left out of the table.
    _link("#5", "supported", on_success=False, on_pathways=0),
]


def test_one_row_per_connection_supported_risks_first_then_most_central_then_weak_risks() -> None:
    supported_risk = _link(
        "#6",
        "leaning_supports",
        target_code="F2",
        on_failure=True,
        on_success=False,
        on_pathways=0,
    )
    rows = assumption_rows([*LINKS, supported_risk], {"#2": [3, 4]}, pathways=4)
    assert [(r["key"], r["code"], r["importance"], r["flag"]) for r in rows] == [
        # A risk the evidence supports: the likeliest way to fail.
        ("r1", "#6", "Risk", False),
        # Then the success connections, most central first.
        ("r2", "#1", "100% of pathways", False),
        # On 3 of 4 pathways and Mixed: central and weak.
        ("r3", "#2", "75% of pathways", True),
        ("r4", "#3", "25% of pathways", False),
        # A risk with too little support: last.
        ("r5", "#4", "Risk", False),
    ]
    second = rows[2]
    assert second["statement"] == "Step #2." and second["conditions"] == ["c2a", "c2b"]
    assert second["verdict"] == "Mixed" and second["sources"] == [3, 4]
    assert rows[4]["kind"] == "risk" and rows[4]["share"] is None


def test_the_publisher_is_the_journal_or_the_organisation_unless_it_is_the_author() -> None:
    assert publisher({"venue": "The Lancet"}, ["Grant Wyper"]) == "The Lancet"
    assert publisher({"publisher_org": "The Lancet"}, ["Grant Wyper"]) == "The Lancet"
    phs = "Public Health Scotland"
    assert publisher({"publisher_org": phs}, [phs]) is None
    assert publisher({}, []) is None


def test_the_weakest_links_are_the_critical_one_then_the_lowest_on_success_pathways() -> None:
    assert weakest_links(LINKS) == ["#2", "#3", "#1"]


def test_unknown_codes_and_unsupported_citations_are_removed_and_counted() -> None:
    check = TextChecker(codes={"#1", "#2", "S1", "L1"}, sources={1: {"#1"}, 2: {"#2"}})
    # L7 and #7 are unknown; [2] bears on #2, which the text does not name; [5] is unlisted.
    text = check("Exposure fell (S1 → L7) on #7 and #1 [1][2][5].")
    assert text == "Exposure fell (S1) on and #1 [1]."
    assert (check.removals.codes, check.removals.citations) == (2, 2)
    # Text that only looks like a code is left alone.
    assert check("Route X9 (A road).") == "Route X9 (A road)."
    # A pathway's own links count, even when the paragraph names only boxes.
    assert check("Snacking fell (S1) [2].", ["#2"]) == "Snacking fell (S1) [2]."
    assert check("Unknown (#9).") == "Unknown."


def test_sources_are_renumbered_by_first_citation_and_uncited_ones_dropped() -> None:
    report: dict[str, Any] = {
        "summary": {"if_then_because": "If x [3].", "context": ""},
        "pathways": [{"title": "Route", "paragraph": "It works [5][3]."}],
        "how_it_could_fail": "#2 [1].",
        "assumptions": [{"why": "Thin [1].", "sources": [4, 1]}],
        "tests": [{"question": "Q [5]?", "indicator": "I", "test_and_learn": "T"}],
    }
    sources = [{"n": n, "citation": f"S{n}"} for n in range(1, 7)]
    renumber(report, sources)
    assert report["summary"]["if_then_because"] == "If x [1]."
    assert report["pathways"][0]["paragraph"] == "It works [2][1]."
    assert report["how_it_could_fail"] == "#2 [3]."
    assert report["assumptions"][0] == {"why": "Thin [3].", "sources": [4, 3]}
    assert report["tests"][0]["question"] == "Q [2]?"
    # Sources 2 and 6 were never cited: dropped.
    assert [(s["n"], s["citation"]) for s in report["sources"]] == [
        (1, "S3"),
        (2, "S5"),
        (3, "S1"),
        (4, "S4"),
    ]


def test_the_method_note_names_the_date_and_the_judge_model() -> None:
    note = method_note(datetime(2026, 10, 28, tzinfo=UTC), "gpt-6.1-terra")
    assert note == (
        "Generated by Policy Atlas with AI on 28 October 2026 from OpenAlex and Overton "
        "searches for each step; evidence judged by gpt-6.1-terra; not yet reviewed by a "
        "person. 'Too little evidence' means none was found in this search, not that none "
        "exists."
    )


def test_a_citation_names_the_first_author_et_al() -> None:
    assert citation(
        authors=["Emma Boyland", "Jason Halford"],
        year=2016,
        title="Advertising as a cue to consume",
        venue="American Journal of Clinical Nutrition",
        kind="systematic review",
    ) == (
        "Boyland et al. (2016) Advertising as a cue to consume. "
        "American Journal of Clinical Nutrition. Systematic review."
    )
    assert citation(authors=[], year=None, title="A page", venue=None, kind=None) == "A page."
    # An organisation keeps its whole name.
    assert citation(
        authors=["Public Health Scotland"],
        year=2022,
        title="MUP and prices",
        venue=None,
        kind=None,
        organisation=True,
    ) == ("Public Health Scotland (2022) MUP and prices.")


def test_the_step_stores_the_report_and_the_read_serves_it(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    backend = StubTocBackend()
    task_id = _run(engine, cleanup, backend)
    with engine.connect() as conn:
        report = toc_graph_out(conn, task_id).report
    assert report is not None
    sent = backend.inputs["report"][0]
    assert sent["plan"]["goal"] and sent["theory"]["weakest_critical_connections"]
    assert all(row["code"].startswith("#") for row in sent["rows"])
    assert report.summary.directly_influenced == "outputs"
    assert report.title == "A drafted theory of change"
    assert report.summary_text == "What the theory says, and where its evidence is weakest."
    # Each source carries its quote; a connection's also its judgement, so a marker
    # opens it in context (the whole programme's are judged but not stored per row).
    assert all(s.quote for s in report.sources)
    assert any(s.evidence_id is not None for s in report.sources)
    success = [p for p in sent["theory"]["pathways"] if p["kind"] == "success"]
    assert len(report.pathways) == len(success)
    assert all(p.pathway_id is not None and p.strength for p in report.pathways)
    assert report.how_it_could_fail
    # The stub cites each pathway's first link's first source: renumbered from 1, all listed.
    assert [s.n for s in report.sources] == list(range(1, len(report.sources) + 1))
    # The verdict's reason, with the whole programme's evaluations, comes first, so it holds [1].
    assert report.verdict_reason and "[1]" in report.verdict_reason
    assert report.summary.question
    # One bullet per supporting activity the draft named, with its citations renumbered.
    assert report.supporting_activities and report.supporting_activities[0].startswith("Set-up")
    assert "[2]" in report.pathways[0].paragraph
    assert route().model_for("toc_judge") in report.method
    assert all(row.why for row in report.assumptions)
    # A row lists at most three sources when its reason cites none.
    assert all(len(row.sources) <= 3 for row in report.assumptions)


def test_the_step_counts_what_its_checks_removed(engine: Engine, cleanup: list[uuid.UUID]) -> None:
    bad = ReportResponse(
        title="A title",
        summary="A summary.",
        if_then_because="If it happens (L9), then it works [99].",
        context="Context.",
        question="Does it work?",
        verdict_reason="Because.",
        supporting_activities=[],
        found_routes=[],
        pathways=[PathwayLineWire(pathway="p99", title="Nowhere", sentence="No.")],
        how_it_could_fail="None.",
        connection_reasons=[ConnectionReasonWire(connection="#99", why="Unknown row.")],
        tests=[
            WhatToTestWire(connection="#99", sentence="Find out."),
        ],
    )
    task_id = _run(engine, cleanup, StubTocBackend({"report": [bad]}))
    summary = _summary(engine, task_id, "toc_report")
    assert summary["removed_codes"] == 1 and summary["removed_citations"] == 1
    assert summary["removed_rows"] == 2  # the unknown pathway and the unknown test link
    report = summary["report"]
    assert report["summary"]["if_then_because"] == "If it happens, then it works."
    assert report["pathways"] == [] and report["tests"] == []
    assert {row["why"] for row in report["assumptions"]} == {ROW_FALLBACK}


def test_a_report_with_a_first_format_verdict_still_reads() -> None:
    from policy_atlas.api.routers.toc import report_out

    summary = dict.fromkeys(
        ("goal", "if_then_because", "population", "time_horizon", "directly_influenced", "context"),
        "",
    )
    report = {"summary": summary, "pathways": [], "assumptions": [], "tests": [], "sources": []}
    old = {"label": "Supported", "verdict": "supported", "headline": "h", "reason": "r"}
    assert report_out({**report, "method": "m", "verdict": old}).verdict is None


def test_one_paper_found_twice_gets_one_number_and_split_capitals_are_mended() -> None:
    from policy_atlas.theory_of_change.report import mend_title, same_work

    doi = {"doi": "https://doi.org/10.1/X", "title": "A"}
    assert same_work(doi) == same_work({"doi": "10.1/x", "title": "B"})
    assert same_work({"title": "Alcohol in Scotland.", "publication_year": 1983}) == same_work(
        {"title": "alcohol in scotland", "publication_year": 1983}
    )
    assert mend_title("Drinking in G reat B ritain") == "Drinking in Great Britain"
    # One split letter alone is left: it may be real ("Vitamin D levels").
    assert mend_title("T cells and alcohol") == "T cells and alcohol"


def test_the_report_notices_when_steps_hold_but_the_programme_does_not() -> None:
    from policy_atlas.theory_of_change.report import steps_hold_but_programme_does_not

    assert steps_hold_but_programme_does_not(["supported", "leaning_supports"], "not_sure_mixed")
    assert not steps_hold_but_programme_does_not(["supported"], "supported")
    assert not steps_hold_but_programme_does_not(["supported", "not_sure_mixed"], "not_sure_mixed")
    assert not steps_hold_but_programme_does_not([], "not_sure_mixed")
