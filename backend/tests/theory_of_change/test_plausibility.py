"""Can the theory work at all? The sense check and the overall verdict (task 054, red team)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.engine import Engine

from policy_atlas.api.routers.toc import toc_graph_out
from policy_atlas.theory_of_change.backend import StubTocBackend
from policy_atlas.theory_of_change.plausibility_prompt import SenseCheckResponse
from policy_atlas.theory_of_change.sense_check import for_verdict, latest, run_sense_check
from tests.helpers import seed_toc_task
from tests.theory_of_change.test_check_steps import _run

PLAN = {
    "intervention": "Paint every GP surgery door blue",
    "intended_change": "Fewer adults with type 2 diabetes",
    "where": "England",
}
DOUBTFUL = SenseCheckResponse(
    active_ingredient="The colour of a door.",
    best_route="A visual cue might prompt a visit.",
    mechanism="implausible",
    mechanism_reason="Door colour changes no driver of diabetes [W1].",
    evidence="too_little",
    evidence_reason="Nothing evaluates it.",
    warning="There is no credible route from door colour to diabetes.",
    note=None,
)
AGAINST = SenseCheckResponse(
    active_ingredient="Prison visits.",
    best_route="Deterrence.",
    mechanism="plausible",
    mechanism_reason="Deterrence is a known route.",
    evidence="against",
    evidence_reason="Trials found more offending [W2].",
    warning=None,
    note="Trials of this programme found it increased offending.",
)


def _search(text: str) -> list[dict[str, Any]]:
    return [
        {"id": "https://openalex.org/W1", "title": "Diabetes prevention", "publication_year": 2020},
        {"id": "https://openalex.org/W2", "title": "Hospital wayfinding"},
    ]


def _task(engine: Engine, cleanup: list[uuid.UUID]) -> uuid.UUID:
    with engine.begin() as conn:
        task_id = seed_toc_task(conn)["task_id"]
    cleanup.append(task_id)
    return task_id


def test_a_flagged_plan_warns_once_with_its_sources(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    task_id = _task(engine, cleanup)
    backend = StubTocBackend({"sense_check": [DOUBTFUL]})
    warning = run_sense_check(engine, task_id=task_id, plan=PLAN, backend=backend, search=_search)
    assert warning is not None
    assert warning.startswith("Before I draft it: There is no credible route")
    # Only the cited document is listed, with its year.
    assert "Diabetes prevention (2020)" in warning and "wayfinding" not in warning
    # Both searches' documents went to the judge, once each.
    assert [d["id"] for d in backend.inputs["sense_check"][0]["documents"]] == ["W1", "W2"]
    with engine.connect() as conn:
        stored = latest(conn, task_id)
    assert stored is not None and stored["mechanism"] == "implausible"
    assert for_verdict(stored) == {
        "mechanism": "implausible",
        "mechanism_reason": "Door colour changes no driver of diabetes [W1].",
        "evidence": "too_little",
        "evidence_reason": "Nothing evaluates it.",
        "documents": {"W1": "Diabetes prevention"},
    }
    # The same plan is not checked again.
    again = run_sense_check(engine, task_id=task_id, plan=PLAN, backend=backend, search=_search)
    assert again is None and backend.calls["sense_check"] == 1


def test_a_plausible_plan_with_evidence_against_gets_a_note_not_a_warning(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    task_id = _task(engine, cleanup)
    backend = StubTocBackend({"sense_check": [AGAINST]})
    note = run_sense_check(engine, task_id=task_id, plan=PLAN, backend=backend, search=_search)
    assert note is not None
    assert note.startswith("Before you start: Trials of this programme found")
    assert "Hospital wayfinding" in note


def test_a_plausible_plan_or_a_failed_check_says_nothing(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    task_id = _task(engine, cleanup)
    assert (
        run_sense_check(
            engine, task_id=task_id, plan=PLAN, backend=StubTocBackend(), search=_search
        )
        is None
    )

    def broken(text: str) -> list[dict[str, Any]]:
        raise RuntimeError("OpenAlex is down")

    other = {**PLAN, "intervention": "Something else"}
    backend = StubTocBackend()
    assert (
        run_sense_check(engine, task_id=task_id, plan=other, backend=backend, search=broken) is None
    )
    assert backend.calls["sense_check"] == 0


def test_the_report_leads_with_the_overall_verdict(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    backend = StubTocBackend()
    task_id = _run(engine, cleanup, backend)
    with engine.connect() as conn:
        report = toc_graph_out(conn, task_id).report
    assert report is not None and report.verdict is not None
    assert report.verdict.label == "Too little evidence"
    assert report.verdict.mechanism == "plausible"
    sent = backend.inputs["theory_verdict"][0]
    assert sent["theory"]["connections"] and sent["sense_check"] is None
    # The whole programme was searched and judged in the check, and the verdict read it.
    assert isinstance(sent["theory"]["whole_programme"], dict)
    assert report.verdict_reason
    programme_sources = {s.n for s in report.sources if f"[{s.n}]" in report.verdict_reason}
    assert programme_sources
    # The report's writer sees the verdict its prose must agree with.
    assert backend.inputs["report"][0]["theory"]["overall_verdict"]["label"] == report.verdict.label


def test_a_failed_verdict_leaves_the_report_without_one(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    backend = StubTocBackend({"theory_verdict": [RuntimeError("down")] * 5})
    task_id = _run(engine, cleanup, backend)
    with engine.connect() as conn:
        report = toc_graph_out(conn, task_id).report
    assert report is not None and report.verdict is None


def test_a_warning_replaces_the_invitation_to_start() -> None:
    from policy_atlas.runtime.task_agent_toc import toc_merge_note

    reply = "The plan is ready. It covers England. Start it when you are ready."
    assert toc_merge_note(reply, "Before I draft it: no route.") == (
        "The plan is ready. It covers England.\n\nBefore I draft it: no route."
    )
