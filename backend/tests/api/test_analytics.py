"""Product analytics events for PostHog: the closed list, the gate and the emitters.

No test sends anything: the sender is a function that records each event.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from policy_atlas.api import analytics
from policy_atlas.api.analytics import (
    ANALYTICS_EVENTS,
    capture,
    capture_run_finished,
    capture_run_started,
    posthog_sender_from_env,
)
from policy_atlas.api.deps import get_analytics_sender
from policy_atlas.core.schema import task
from tests.api.resource_support import api_client, create_task
from tests.api.test_feedback import _problem
from tests.helpers import delete_task_data, now

Headers = dict[str, str]
FREE_TEXT = "Free text that must stay out of PostHog."


@contextmanager
def analytics_client(
    tmp_path: Path, *elements: str
) -> Iterator[tuple[TestClient, Headers, list[dict[str, Any]]]]:
    """Yield a client with the named elements on and a sender that records events."""
    sent: list[dict[str, Any]] = []
    with api_client(
        tmp_path,
        overrides={get_analytics_sender: lambda: sent.append},
        feedback_elements=frozenset(elements),
    ) as (client, owner, _other):
        yield client, owner, sent


def test_the_event_list_is_the_one_in_the_brief() -> None:
    """Eleven events. Do not add one without a reason."""
    assert set(ANALYTICS_EVENTS) == {
        "planner_opened",
        "taskplan_approved",
        "run_started",
        "run_completed",
        "run_failed",
        "report_opened",
        "report_exported",
        "sources_tab_opened",
        "feedback_submitted",
        "onboarding_completed",
        "onboarding_skipped",
    }


def test_capture_identifies_the_user_and_sets_person_properties() -> None:
    """The user id is the distinct id; the server's address is not the user's."""
    sent: list[dict[str, Any]] = []

    capture(
        sent.append,
        event="onboarding_completed",
        user_id="user-1",
        properties={"source": None},
        person_properties={"department": "dfe"},
    )

    assert sent[0]["event"] == "onboarding_completed"
    assert sent[0]["distinct_id"] == "user-1"
    assert sent[0]["properties"] == {
        "source": None,
        "$geoip_disable": True,
        "$set": {"department": "dfe"},
    }
    assert "timestamp" in sent[0]


def test_capture_never_raises_and_sends_nothing_it_should_not() -> None:
    """Off, no user, an event outside the list, or a broken sender: no error."""
    sent: list[dict[str, Any]] = []

    def broken(_: dict[str, Any]) -> None:
        raise ConnectionError("posthog is down")

    capture(None, event="run_started", user_id="user-1")
    capture(sent.append, event="run_started", user_id=None)
    capture(sent.append, event="page_viewed", user_id="user-1")
    capture(broken, event="run_started", user_id="user-1")

    assert sent == []


@pytest.mark.parametrize(
    ("key", "host", "feedback", "on"),
    [
        ("phc_test", "https://eu.i.posthog.com", "analytics", True),
        ("phc_test", "https://eu.i.posthog.com/", "onboarding,analytics", True),
        ("phc_test", "https://eu.i.posthog.com", "onboarding", False),
        ("", "https://eu.i.posthog.com", "analytics", False),
        ("phc_test", "", "analytics", False),
    ],
)
def test_analytics_is_on_only_with_the_key_the_host_and_the_flag(
    monkeypatch: pytest.MonkeyPatch, key: str, host: str, feedback: str, on: bool
) -> None:
    """Three settings must agree before any event leaves the server."""
    monkeypatch.setenv("POSTHOG_API_KEY", key)
    monkeypatch.setenv("POSTHOG_HOST", host)
    monkeypatch.setenv("POLICY_ATLAS_FEEDBACK", feedback)

    assert (posthog_sender_from_env() is not None) is on


def test_a_plain_http_host_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """User ids must not travel over plain HTTP."""
    monkeypatch.setenv("POSTHOG_API_KEY", "phc_test")
    monkeypatch.setenv("POSTHOG_HOST", "http://posthog.example.test")
    monkeypatch.setenv("POLICY_ATLAS_FEEDBACK", "analytics")

    with pytest.raises(RuntimeError, match="https://"):
        posthog_sender_from_env()


def test_the_sender_posts_the_event_with_the_project_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """The body PostHog's capture API expects, at ``/i/v0/e/``. No network call here."""
    posted: list[tuple[str, dict[str, Any]]] = []

    class Response:
        def raise_for_status(self) -> None:
            return None

    def fake_post(url: str, *, json: dict[str, Any], timeout: float) -> Response:
        posted.append((url, json))
        return Response()

    monkeypatch.setattr(httpx, "post", fake_post)

    analytics._post_to_posthog(
        "https://eu.i.posthog.com/i/v0/e/", "phc_test", {"event": "run_started"}
    )

    assert posted == [
        ("https://eu.i.posthog.com/i/v0/e/", {"api_key": "phc_test", "event": "run_started"})
    ]


def test_the_relay_forwards_a_page_event_for_the_caller(tmp_path: Path, engine: Engine) -> None:
    """A closed event name and a task id; the server adds the user."""
    del engine
    task_id = str(uuid.uuid4())
    with analytics_client(tmp_path, "analytics") as (client, owner, sent):
        response = client.post(
            "/api/v1/analytics/events",
            headers=owner,
            json={"event": "report_opened", "task_id": task_id},
        )
        unknown = client.post(
            "/api/v1/analytics/events", headers=owner, json={"event": "run_completed"}
        )
        with_text = client.post(
            "/api/v1/analytics/events",
            headers=owner,
            json={"event": "report_opened", "note": FREE_TEXT},
        )

        assert response.status_code == 204, response.text
        assert (unknown.status_code, with_text.status_code) == (422, 422)
        assert len(sent) == 1
        assert sent[0]["event"] == "report_opened"
        assert sent[0]["distinct_id"].startswith("owner-")
        assert sent[0]["properties"] == {"task_id": task_id, "$geoip_disable": True}


def test_the_relay_is_a_404_when_analytics_is_off(tmp_path: Path, engine: Engine) -> None:
    """With the flag off the frontend sends nothing, and the route does not exist."""
    del engine
    with analytics_client(tmp_path, "onboarding") as (client, owner, sent):
        response = client.post(
            "/api/v1/analytics/events", headers=owner, json={"event": "report_opened"}
        )

        assert response.status_code == 404
        assert sent == []


def test_feedback_submitted_has_the_kind_and_the_surface_and_no_free_text(
    tmp_path: Path, engine: Engine
) -> None:
    """The one feedback event in PostHog. The description stays in Postgres."""
    del engine
    with analytics_client(tmp_path, "problem_report", "analytics") as (client, owner, sent):
        response = client.post(
            "/api/v1/feedback",
            headers=owner,
            json=_problem(description=FREE_TEXT, query_text=FREE_TEXT),
        )

        assert response.status_code == 201, response.text
        assert [event["event"] for event in sent] == ["feedback_submitted"]
        assert sent[0]["properties"] == {
            "kind": "problem_report",
            "surface": "app_header",
            "$geoip_disable": True,
        }
        assert FREE_TEXT not in str(sent)


def test_onboarding_events_and_the_person_properties(tmp_path: Path, engine: Engine) -> None:
    """Skip once, complete once, then an edit only updates the person properties."""
    del engine
    answers = {
        "department": "other",
        "department_other": FREE_TEXT,
        "team_type": "policy",
        "primary_job": "j2",
    }
    person = {"department": "other", "team_type": "policy", "primary_job": "j2", "source": None}
    with analytics_client(tmp_path, "onboarding", "analytics") as (client, owner, sent):
        client.post("/api/v1/me/profile/skip", headers=owner)
        client.post("/api/v1/me/profile/skip", headers=owner)
        client.put("/api/v1/me/profile", headers=owner, json=answers)
        client.put("/api/v1/me/profile", headers=owner, json={**answers, "primary_job": "j5"})

        assert [event["event"] for event in sent] == [
            "onboarding_skipped",
            "onboarding_completed",
            "$set",
        ]
        assert sent[1]["properties"] == {"source": None, "$geoip_disable": True, "$set": person}
        assert sent[2]["properties"]["$set"] == {**person, "primary_job": "j5"}
        # The typed department name is free text.
        assert FREE_TEXT not in str(sent)


def test_run_started_sends_the_approval_and_the_start() -> None:
    """ "Start the search" is the approval, so the two events go together."""
    sent: list[dict[str, Any]] = []
    task_id = uuid.uuid4()

    capture_run_started(sent.append, user_id="user-1", task_id=task_id)

    assert [event["event"] for event in sent] == ["taskplan_approved", "run_started"]
    assert all(event["properties"]["task_id"] == str(task_id) for event in sent)


@pytest.mark.parametrize(
    ("status", "event"),
    [
        ("succeeded", "run_completed"),
        ("degraded", "run_completed"),
        ("failed", "run_failed"),
        ("aborted", None),
        ("interrupted", None),
    ],
)
def test_a_finished_run_is_an_event_for_the_owner_of_the_task(
    tmp_path: Path, engine: Engine, status: str, event: str | None
) -> None:
    """Completed or failed for the task's owner; an abort is neither."""
    sent: list[dict[str, Any]] = []
    with api_client(tmp_path) as (client, owner, _other):
        task_id = uuid.UUID(create_task(client, owner))

        capture_run_finished(engine, sent.append, task_id=task_id, status=status)
        capture_run_finished(engine, None, task_id=task_id, status=status)

    assert [sent_event["event"] for sent_event in sent] == ([event] if event else [])
    for sent_event in sent:
        assert sent_event["distinct_id"].startswith("owner-")
        assert sent_event["properties"]["status"] == status


def test_a_run_of_a_task_with_no_owner_sends_nothing(engine: Engine) -> None:
    """A task that the CLI made has no person to attribute the event to."""
    sent: list[dict[str, Any]] = []
    task_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            task.insert().values(
                task_id=task_id,
                created_at=now(),
                name="CLI task",
                status="active",
                updated_at=now(),
            )
        )
    try:
        capture_run_finished(engine, sent.append, task_id=task_id, status="succeeded")
    finally:
        with engine.begin() as conn:
            delete_task_data(conn, task_id)

    assert sent == []
