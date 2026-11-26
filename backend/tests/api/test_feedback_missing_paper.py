"""In-app feedback routes for element B: ``missing_paper`` and ``screening_override``.

One integration test per kind posts a record, then asserts the Postgres rows
and the Langfuse score call on a fake client. The resolver's own branches are
in ``test_missing_paper.py``.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.api.deps import get_langfuse_client, get_paper_lookup
from policy_atlas.api.routers import feedback as feedback_router
from policy_atlas.core.schema import missing_paper_resolution
from tests.api.resource_support import api_client, create_task
from tests.api.test_feedback import URL, _row
from tests.api.test_missing_paper import WORK, FakeLookup
from tests.feedback_support import FakeLangfuse, seed_component_run
from tests.helpers import seed_screening_result, seed_source, seed_walk

SCREENED_OUT_DOI = "10.1000/screened-out"
#: As the acquire step writes it: an OpenAlex document always has a record id.
SCREENED_OUT_DOCUMENT = {
    "backend": "openalex",
    "backend_record_id": "https://openalex.org/W900",
    "doi": SCREENED_OUT_DOI,
}
QUESTION = "What works for school attendance?"
Headers = dict[str, str]


@contextmanager
def missing_paper_client(
    tmp_path: Path, lookup: Any
) -> Iterator[tuple[TestClient, Headers, Headers, FakeLangfuse]]:
    """Yield a client with element B on, a fake Langfuse and a fake OpenAlex lookup."""
    langfuse = FakeLangfuse()
    with api_client(
        tmp_path,
        overrides={get_langfuse_client: lambda: langfuse, get_paper_lookup: lambda: lookup},
        feedback_elements=frozenset({"missing_paper"}),
    ) as (client, owner, other):
        yield client, owner, other, langfuse


def _seed_run(engine: Engine, task_id: str) -> dict[str, str]:
    """Give a task one run whose title-and-abstract screen removed one document."""
    task_uuid = uuid.UUID(task_id)
    with engine.begin() as conn:
        walk = seed_walk(conn, task_uuid, capability="evidence_search")
        screen_run = seed_component_run(
            conn, task_uuid, walk.walk_id, "screen_abstract", trace_id="trace-screen", age_minutes=9
        )
        seed_component_run(conn, task_uuid, walk.walk_id, "synthesise", trace_id="trace-synthesise")
        _, source_id = seed_source(
            conn, task_uuid, {"title": "A screened-out paper", **SCREENED_OUT_DOCUMENT}
        )
        seed_screening_result(
            conn, task_uuid, screen_run, walk.scope_id, source_id, "not_relevant", screen_stage=1
        )
        _, kept_id = seed_source(conn, task_uuid, {"title": "A kept paper"})
        seed_screening_result(conn, task_uuid, screen_run, walk.scope_id, kept_id, "relevant")
    return {
        "task_id": task_id,
        "run_id": str(walk.walk_id),
        "source_id": str(source_id),
        "kept_id": str(kept_id),
    }


def _report(seeded: dict[str, str], raw_input: str, **overrides: Any) -> dict[str, Any]:
    """Build a missing-paper body."""
    return {
        "kind": "missing_paper",
        "surface": "sources_tab",
        "task_id": seeded["task_id"],
        "raw_input": raw_input,
        **overrides,
    }


def _resolution(engine: Engine, feedback_event_id: str) -> Any:
    """Read the resolution row of one missing-paper record."""
    with engine.connect() as conn:
        return conn.execute(
            select(missing_paper_resolution).where(
                missing_paper_resolution.c.feedback_event_id == uuid.UUID(feedback_event_id)
            )
        ).mappings().one()


def test_a_missing_paper_is_stored_resolved_and_mirrored(tmp_path: Path, engine: Engine) -> None:
    """Kind ``missing_paper``: the event, its resolution row and the score with the stage."""
    with missing_paper_client(tmp_path, FakeLookup([])) as (client, owner, _other, langfuse):
        seeded = _seed_run(engine, create_task(client, owner, question=QUESTION))
        body = _report(seeded, f"https://doi.org/{SCREENED_OUT_DOI}", why="The main UK trial.")

        response = client.post(URL, headers=owner, json=body)

        assert response.status_code == 201, response.text
        event_id = response.json()["feedback_event_id"]
        row = _row(engine, event_id)
        assert (row["surface"], row["kind"]) == ("sources_tab", "missing_paper")
        assert (row["target_type"], row["target_id"]) == ("run", seeded["run_id"])
        assert row["trace_id"] == "trace-synthesise"
        assert row["payload"] == {
            "raw_input": f"https://doi.org/{SCREENED_OUT_DOI}",
            "why": "The main UK trial.",
            "query_text": QUESTION,
        }
        resolution = _resolution(engine, event_id)
        assert resolution["failure_stage"] == "screened_out_s1"
        assert resolution["resolved_id"] == seeded["source_id"]
        assert resolution["resolver_confidence"] == 1.0
        assert resolution["resolved_at"] is not None
        assert response.json()["resolution"]["failure_stage"] == "screened_out_s1"
        assert response.json()["resolution"]["resolved_id"] == seeded["source_id"]
        score = langfuse.scores[0]
        assert (score["name"], score["value"], score["score_id"]) == (
            "missing_paper",
            "screened_out_s1",
            event_id,
        )
        assert score["trace_id"] == "trace-synthesise"
        assert score["comment"] == "The main UK trial."
        assert score["metadata"]["failure_stage"] == "screened_out_s1"


def test_a_paper_outside_the_task_and_an_unmatched_input(tmp_path: Path, engine: Engine) -> None:
    """Not retrieved keeps the paper's own id; an unmatched input is for a person to review."""
    with missing_paper_client(tmp_path, FakeLookup([WORK])) as (client, owner, _other, _langfuse):
        seeded = _seed_run(engine, create_task(client, owner))

        outside = client.post(URL, headers=owner, json=_report(seeded, "10.1000/breakfast.1"))
        unmatched = client.post(URL, headers=owner, json=_report(seeded, "that breakfast report"))

        assert outside.json()["resolution"] == {
            "failure_stage": "not_retrieved",
            "resolved_id": "https://openalex.org/W100",
            "resolver_confidence": 1.0,
            "resolved_at": outside.json()["resolution"]["resolved_at"],
        }
        assert unmatched.json()["resolution"]["failure_stage"] == "unresolved"
        assert unmatched.json()["resolution"]["resolved_id"] is None


def test_the_same_paper_is_one_record_in_a_run_and_separate_across_runs(
    tmp_path: Path, engine: Engine
) -> None:
    """Dedupe only within a run: a second report of the same input returns the first."""
    with missing_paper_client(tmp_path, FakeLookup([])) as (client, owner, _other, langfuse):
        first_run = _seed_run(engine, create_task(client, owner))
        other_run = _seed_run(engine, create_task(client, owner))

        first = client.post(URL, headers=owner, json=_report(first_run, SCREENED_OUT_DOI))
        again = client.post(URL, headers=owner, json=_report(first_run, f" {SCREENED_OUT_DOI} "))
        elsewhere = client.post(URL, headers=owner, json=_report(other_run, SCREENED_OUT_DOI))

        assert again.json()["feedback_event_id"] == first.json()["feedback_event_id"]
        assert elsewhere.json()["feedback_event_id"] != first.json()["feedback_event_id"]
        assert len(langfuse.scores) == 2


def test_a_slow_resolution_answers_pending_and_finishes_later(
    tmp_path: Path, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Past the time budget the response is pending; a later read has the stage."""
    release = threading.Event()

    class SlowLookup(FakeLookup):
        def lookup_dois(self, dois: list[str]) -> list[dict[str, Any]]:
            release.wait(timeout=10)
            return super().lookup_dois(dois)

    monkeypatch.setattr(feedback_router, "RESOLVE_BUDGET_S", 0.05)
    with missing_paper_client(tmp_path, SlowLookup([])) as (client, owner, other, langfuse):
        seeded = _seed_run(engine, create_task(client, owner))

        response = client.post(URL, headers=owner, json=_report(seeded, SCREENED_OUT_DOI))

        assert response.status_code == 201, response.text
        event_id = response.json()["feedback_event_id"]
        assert response.json()["resolution"]["failure_stage"] is None
        assert langfuse.scores == []
        assert client.get(f"{URL}/{event_id}", headers=other).status_code == 404

        release.set()
        deadline = time.monotonic() + 5
        stage = None
        while stage is None and time.monotonic() < deadline:
            stage = client.get(f"{URL}/{event_id}", headers=owner).json()["resolution"][
                "failure_stage"
            ]
            time.sleep(0.02)
        assert stage == "screened_out_s1"
        assert langfuse.scores[0]["value"] == "screened_out_s1"


def test_a_screening_override_is_stored_and_mirrored(tmp_path: Path, engine: Engine) -> None:
    """Kind ``screening_override``: the stage comes from the server; the trace is the screen's."""
    with missing_paper_client(tmp_path, None) as (client, owner, _other, langfuse):
        seeded = _seed_run(engine, create_task(client, owner))
        body = {
            "kind": "screening_override",
            "surface": "screened_out_row",
            "task_id": seeded["task_id"],
            "source_id": seeded["source_id"],
        }

        response = client.post(URL, headers=owner, json=body)

        assert response.status_code == 201, response.text
        event_id = response.json()["feedback_event_id"]
        row = _row(engine, event_id)
        assert (row["surface"], row["kind"]) == ("screened_out_row", "screening_override")
        assert (row["target_type"], row["target_id"]) == ("document", seeded["source_id"])
        assert str(row["capability_run_id"]) == seeded["run_id"]
        assert row["trace_id"] == "trace-screen"
        assert row["payload"] == {"stage": "s1", "document": SCREENED_OUT_DOCUMENT}
        score = langfuse.scores[0]
        assert (score["name"], score["value"], score["trace_id"]) == (
            "screening_override",
            1.0,
            "trace-screen",
        )
        assert score["metadata"]["stage"] == "s1"

        # A toggle with no free text: the list shows it, and an undo retracts it.
        listing = client.get(
            URL, headers=owner, params={"task_id": seeded["task_id"], "kind": "screening_override"}
        )
        assert [record["target_id"] for record in listing.json()["data"]] == [seeded["source_id"]]
        assert client.delete(f"{URL}/{event_id}", headers=owner).status_code == 204
        assert _row(engine, event_id)["retracted_at"] is not None


def test_an_override_is_only_for_a_screened_out_document(tmp_path: Path, engine: Engine) -> None:
    """A document that screening kept, or that is not in the task, cannot be overridden."""
    with missing_paper_client(tmp_path, None) as (client, owner, _other, langfuse):
        seeded = _seed_run(engine, create_task(client, owner))
        body = {
            "kind": "screening_override",
            "surface": "screened_out_row",
            "task_id": seeded["task_id"],
        }

        kept = client.post(URL, headers=owner, json={**body, "source_id": seeded["kept_id"]})
        unknown = client.post(URL, headers=owner, json={**body, "source_id": str(uuid.uuid4())})

        assert kept.status_code == 422, kept.text
        assert unknown.status_code == 404
        assert langfuse.scores == []


def test_element_b_is_off_without_its_flag(tmp_path: Path, engine: Engine) -> None:
    """Both kinds of element B are behind the ``missing_paper`` flag."""
    langfuse = FakeLangfuse()
    with api_client(
        tmp_path,
        overrides={get_langfuse_client: lambda: langfuse},
        feedback_elements=frozenset({"citation_flag"}),
    ) as (client, owner, _other):
        seeded = _seed_run(engine, create_task(client, owner))
        override = {
            "kind": "screening_override",
            "surface": "screened_out_row",
            "task_id": seeded["task_id"],
            "source_id": seeded["source_id"],
        }

        assert client.post(URL, headers=owner, json=_report(seeded, "x")).status_code == 404
        assert client.post(URL, headers=owner, json=override).status_code == 404
