"""In-app feedback routes: ``/api/v1/feedback``, one integration test per kind.

Each kind's test posts a record, then asserts the Postgres row (the system of
record) and the Langfuse score call on a fake client.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.api.deps import get_langfuse_client
from policy_atlas.core.feedback import route_problem_report
from policy_atlas.core.schema import artefact, feedback_event
from tests.api.resource_support import api_client, create_task
from tests.feedback_support import FakeLangfuse, seed_component_run
from tests.helpers import now, seed_source, seed_walk

URL = "/api/v1/feedback"
DOCUMENT = {
    "backend": "openalex",
    "backend_record_id": "https://openalex.org/W123",
    "doi": "10.1000/example.1",
}
Headers = dict[str, str]


@contextmanager
def feedback_client(
    tmp_path: Path, *elements: str
) -> Iterator[tuple[TestClient, Headers, Headers, FakeLangfuse]]:
    """Yield a client with the named feedback elements on and a fake Langfuse."""
    langfuse = FakeLangfuse()
    with api_client(
        tmp_path,
        overrides={get_langfuse_client: lambda: langfuse},
        feedback_elements=frozenset(elements),
    ) as (client, owner, other):
        yield client, owner, other, langfuse


def _seed_report(engine: Engine, task_id: str) -> dict[str, str]:
    """Give a task one run with traces, one document and one report."""
    task_uuid = uuid.UUID(task_id)
    artefact_id = uuid.uuid4()
    with engine.begin() as conn:
        walk = seed_walk(conn, task_uuid, capability="evidence_search")
        seed_component_run(conn, task_uuid, walk.walk_id, "acquire", trace_id="trace-acquire")
        seed_component_run(
            conn, task_uuid, walk.walk_id, "synthesise", trace_id="trace-synthesise", age_minutes=5
        )
        _, source_id = seed_source(conn, task_uuid, {**DOCUMENT, "title": "A cited paper"})
        conn.execute(
            artefact.insert().values(
                artefact_id=artefact_id,
                task_id=task_uuid,
                capability_run_id=walk.walk_id,
                title="Report",
                created_at=now(),
            )
        )
    return {
        "task_id": task_id,
        "run_id": str(walk.walk_id),
        "artefact_id": str(artefact_id),
        "source_id": str(source_id),
    }


def _row(engine: Engine, feedback_event_id: str) -> Any:
    """Read one ``feedback_event`` row."""
    with engine.connect() as conn:
        return conn.execute(
            select(feedback_event).where(
                feedback_event.c.feedback_event_id == uuid.UUID(feedback_event_id)
            )
        ).mappings().one()


def _flag(seeded: dict[str, str], **overrides: Any) -> dict[str, Any]:
    """Build a citation flag body for the seeded report."""
    return {
        "kind": "citation_flag",
        "surface": "report_references",
        "task_id": seeded["task_id"],
        "artefact_id": seeded["artefact_id"],
        "source_id": seeded["source_id"],
        "action": "useful",
        **overrides,
    }


def _problem(**overrides: Any) -> dict[str, Any]:
    """Build a problem report body."""
    return {
        "kind": "problem_report",
        "surface": "app_header",
        "problem_kind": "error",
        "description": "The search stopped with an error.",
        "page": "/tasks/abc/result",
        "client": {"browser": "TestBrowser/1.0", "time": "2026-11-18T09:00:00Z"},
        **overrides,
    }


def test_with_every_flag_off_the_feedback_routes_are_404(tmp_path: Path, engine: Engine) -> None:
    """The API surface with the flags off is the same as before the feature."""
    with feedback_client(tmp_path) as (client, owner, _other, langfuse):
        seeded = _seed_report(engine, create_task(client, owner))

        assert client.post(URL, headers=owner, json=_flag(seeded)).status_code == 404
        assert client.post(URL, headers=owner, json=_problem()).status_code == 404
        listing = client.get(
            URL, headers=owner, params={"task_id": seeded["task_id"], "kind": "citation_flag"}
        )
        assert listing.status_code == 404
        assert client.delete(f"{URL}/{uuid.uuid4()}", headers=owner).status_code == 404
        assert langfuse.scores == []


def test_each_element_has_its_own_flag(tmp_path: Path, engine: Engine) -> None:
    """With only "Report a problem" on, a citation flag is still a 404."""
    with feedback_client(tmp_path, "problem_report") as (client, owner, _other, _langfuse):
        seeded = _seed_report(engine, create_task(client, owner))

        assert client.post(URL, headers=owner, json=_flag(seeded)).status_code == 404
        assert client.post(URL, headers=owner, json=_problem()).status_code == 201


def test_a_citation_flag_is_stored_and_mirrored(tmp_path: Path, engine: Engine) -> None:
    """Kind ``citation_flag``: the row has the full envelope; the score is 1 on the trace."""
    with feedback_client(tmp_path, "citation_flag") as (client, owner, _other, langfuse):
        seeded = _seed_report(engine, create_task(client, owner))

        response = client.post(URL, headers=owner, json=_flag(seeded))

        assert response.status_code == 201, response.text
        event_id = response.json()["feedback_event_id"]
        row = _row(engine, event_id)
        assert row["user_id"].startswith("owner-")
        assert str(row["capability_run_id"]) == seeded["run_id"]
        assert row["trace_id"] == "trace-synthesise"
        assert (row["surface"], row["kind"]) == ("report_references", "citation_flag")
        assert (row["target_type"], row["target_id"]) == ("document", seeded["source_id"])
        assert row["payload"] == {"action": "useful", "document": DOCUMENT}
        assert row["retracted_at"] is None
        assert langfuse.scores == [
            {
                "score_id": event_id,
                "trace_id": "trace-synthesise",
                "name": "citation_flag",
                "value": 1.0,
                "data_type": "NUMERIC",
                "comment": None,
                "metadata": {
                    "surface": "report_references",
                    "action": "useful",
                    "source_id": seeded["source_id"],
                    **DOCUMENT,
                    "feedback_event_id": event_id,
                },
            }
        ]


def test_a_second_flag_replaces_the_first_and_persists(tmp_path: Path, engine: Engine) -> None:
    """A toggle: the first row is retracted, its score deleted, and the list has one flag."""
    with feedback_client(tmp_path, "citation_flag") as (client, owner, _other, langfuse):
        seeded = _seed_report(engine, create_task(client, owner))
        first = client.post(URL, headers=owner, json=_flag(seeded)).json()

        refined = _flag(seeded, action="not_relevant", reason="off_topic", note="About adults.")
        second = client.post(URL, headers=owner, json=refined).json()

        assert _row(engine, first["feedback_event_id"])["retracted_at"] is not None
        assert langfuse.score_api.deleted == [first["feedback_event_id"]]
        assert langfuse.scores[-1]["value"] == -1.0
        assert langfuse.scores[-1]["comment"] == "About adults."
        assert langfuse.scores[-1]["metadata"]["reason"] == "off_topic"
        listing = client.get(
            URL, headers=owner, params={"task_id": seeded["task_id"], "kind": "citation_flag"}
        )
        assert listing.status_code == 200, listing.text
        assert [record["feedback_event_id"] for record in listing.json()["data"]] == [
            second["feedback_event_id"]
        ]
        assert listing.json()["data"][0]["payload"]["note"] == "About adults."


def test_a_retraction_keeps_the_row_and_deletes_the_score(tmp_path: Path, engine: Engine) -> None:
    """Undo sets ``retracted_at``; only the owner of the record can retract it."""
    with feedback_client(tmp_path, "citation_flag") as (client, owner, other, langfuse):
        seeded = _seed_report(engine, create_task(client, owner))
        event_id = client.post(URL, headers=owner, json=_flag(seeded)).json()["feedback_event_id"]

        assert client.delete(f"{URL}/{event_id}", headers=other).status_code == 404
        assert client.delete(f"{URL}/{event_id}", headers=owner).status_code == 204
        assert client.delete(f"{URL}/{event_id}", headers=owner).status_code == 404

        assert _row(engine, event_id)["retracted_at"] is not None
        assert langfuse.score_api.deleted == [event_id]
        listing = client.get(
            URL, headers=owner, params={"task_id": seeded["task_id"], "kind": "citation_flag"}
        )
        assert listing.json()["data"] == []


def test_a_flag_on_the_sources_tab_joins_the_latest_run(tmp_path: Path, engine: Engine) -> None:
    """With no report named, the task's newest run is the run of the flag."""
    with feedback_client(tmp_path, "citation_flag") as (client, owner, _other, _langfuse):
        seeded = _seed_report(engine, create_task(client, owner))
        body = _flag(seeded, surface="sources_all", artefact_id=None)

        response = client.post(URL, headers=owner, json=body)

        assert response.status_code == 201, response.text
        assert response.json()["capability_run_id"] == seeded["run_id"]


def test_a_flag_needs_a_readable_task_and_a_document_of_that_task(
    tmp_path: Path, engine: Engine
) -> None:
    """Another user's task, an unknown document and another task's report are all 404."""
    with feedback_client(tmp_path, "citation_flag") as (client, owner, other, langfuse):
        seeded = _seed_report(engine, create_task(client, owner))
        elsewhere = _seed_report(engine, create_task(client, owner))

        assert client.post(URL, headers=other, json=_flag(seeded)).status_code == 404
        unknown = _flag(seeded, source_id=str(uuid.uuid4()))
        assert client.post(URL, headers=owner, json=unknown).status_code == 404
        wrong_report = _flag(seeded, artefact_id=elsewhere["artefact_id"])
        assert client.post(URL, headers=owner, json=wrong_report).status_code == 404
        assert client.post(URL, headers=owner, json=_flag(seeded, action="meh")).status_code == 422
        assert langfuse.scores == []


def test_a_problem_report_is_stored_and_mirrored(tmp_path: Path, engine: Engine) -> None:
    """Kind ``problem_report``: target is the run; the trace is the newest component run's."""
    with feedback_client(tmp_path, "problem_report") as (client, owner, _other, langfuse):
        seeded = _seed_report(engine, create_task(client, owner))
        body = _problem(
            task_id=seeded["task_id"],
            step_reached="Screening",
            step_status="failed",
            query_text="What works for school attendance?",
        )

        response = client.post(URL, headers=owner, json=body)

        assert response.status_code == 201, response.text
        event_id = response.json()["feedback_event_id"]
        row = _row(engine, event_id)
        assert (row["surface"], row["kind"]) == ("app_header", "problem_report")
        assert (row["target_type"], row["target_id"]) == ("run", seeded["run_id"])
        assert row["trace_id"] == "trace-acquire"
        assert row["payload"] == {
            "problem_kind": "error",
            "description": "The search stopped with an error.",
            "page": "/tasks/abc/result",
            "step_reached": "Screening",
            "step_status": "failed",
            "query_text": "What works for school attendance?",
            "client": {"browser": "TestBrowser/1.0", "time": "2026-11-18T09:00:00Z"},
        }
        score = langfuse.scores[0]
        assert (score["name"], score["value"], score["data_type"]) == (
            "problem_report",
            "error",
            "CATEGORICAL",
        )
        assert score["score_id"] == event_id
        assert score["comment"] == "The search stopped with an error."
        # The research question is free text: it is in Postgres, not in the metadata.
        assert "query_text" not in score["metadata"]


def test_a_problem_report_before_any_run_has_no_run_and_no_score(
    tmp_path: Path, engine: Engine
) -> None:
    """Raised on a page with no task: stored with a null run; a user can send many."""
    with feedback_client(tmp_path, "problem_report") as (client, owner, _other, langfuse):
        first = client.post(URL, headers=owner, json=_problem(page="/new"))
        second = client.post(URL, headers=owner, json=_problem(page="/new", problem_kind="other"))

        assert (first.status_code, second.status_code) == (201, 201)
        row = _row(engine, first.json()["feedback_event_id"])
        assert row["capability_run_id"] is None
        assert (row["target_type"], row["target_id"]) == ("run", None)
        assert _row(engine, second.json()["feedback_event_id"])["retracted_at"] is None
        assert langfuse.scores == []


def test_problem_reports_route_by_kind() -> None:
    """Errors and stalls go to engineering with a trace link; the rest to the eval backlog."""
    langfuse = FakeLangfuse()
    event_id = uuid.uuid4()

    def route(problem_kind: str, trace_id: str | None = "t1") -> tuple[str, str | None]:
        return route_problem_report(
            langfuse,  # type: ignore[arg-type]
            feedback_event_id=event_id,
            problem_kind=problem_kind,
            trace_id=trace_id,
        )

    link = "https://langfuse.example.test/trace/t1"
    assert route("error") == ("engineering_alert", link)
    assert route("stalled") == ("engineering_alert", link)
    assert route("stalled", trace_id=None) == ("engineering_alert", None)
    assert route("unusable") == ("eval_backlog", None)
    assert route("other") == ("eval_backlog", None)
