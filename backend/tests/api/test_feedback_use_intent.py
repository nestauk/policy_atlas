"""In-app feedback routes for element C: the ``use_intent`` kind.

The integration test posts an answer, then asserts the Postgres row and the
Langfuse score call on a fake client. The show-once rules are a frontend
concern (``frontend/src/lib/useIntent.test.ts``).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.engine import Engine

from tests.api.resource_support import create_task
from tests.api.test_feedback import URL, _row, _seed_report, feedback_client

SHOWN_AT = "2026-11-18T09:00:00+00:00"


def _answer(seeded: dict[str, str], use_intent: str, **overrides: Any) -> dict[str, Any]:
    """Build a use-intent body for the seeded report."""
    return {
        "kind": "use_intent",
        "surface": "report_key_findings",
        "task_id": seeded["task_id"],
        "artefact_id": seeded["artefact_id"],
        "use_intent": use_intent,
        "shown_at": SHOWN_AT,
        **overrides,
    }


def test_a_use_intent_answer_is_stored_and_mirrored(tmp_path: Path, engine: Engine) -> None:
    """Kind ``use_intent``: the target is the report; "with edits" scores 1."""
    with feedback_client(tmp_path, "use_intent") as (client, owner, _other, langfuse):
        seeded = _seed_report(engine, create_task(client, owner))
        body = _answer(
            seeded,
            "with_edits",
            change_reasons=["missing_evidence", "length"],
            note="Needs the 2024 trial.",
        )

        response = client.post(URL, headers=owner, json=body)

        assert response.status_code == 201, response.text
        event_id = response.json()["feedback_event_id"]
        row = _row(engine, event_id)
        assert (row["surface"], row["kind"]) == ("report_key_findings", "use_intent")
        assert (row["target_type"], row["target_id"]) == ("report", seeded["artefact_id"])
        assert str(row["capability_run_id"]) == seeded["run_id"]
        assert row["trace_id"] == "trace-synthesise"
        payload = dict(row["payload"])
        answered_at = datetime.fromisoformat(payload.pop("answered_at"))
        assert answered_at > datetime.fromisoformat(SHOWN_AT)
        assert payload == {
            "use_intent": "with_edits",
            "change_reasons": ["missing_evidence", "length"],
            "note": "Needs the 2024 trial.",
            "shown_at": SHOWN_AT,
        }
        score = langfuse.scores[0]
        assert (score["name"], score["value"], score["data_type"]) == ("use_intent", 1.0, "NUMERIC")
        assert score["score_id"] == event_id
        assert score["trace_id"] == "trace-synthesise"
        assert score["comment"] == "Needs the 2024 trial."
        assert score["metadata"]["change_reasons"] == ["missing_evidence", "length"]


@pytest.mark.parametrize(
    ("use_intent", "value", "data_type"),
    [
        ("as_is", 2.0, "NUMERIC"),
        ("with_edits", 1.0, "NUMERIC"),
        ("no", 0.0, "NUMERIC"),
        ("dismissed", "dismissed", "CATEGORICAL"),
    ],
)
def test_each_answer_has_its_score_value(
    tmp_path: Path, engine: Engine, use_intent: str, value: float | str, data_type: str
) -> None:
    """2, 1 and 0 for the answers; "Not now" is a categorical score, not a null."""
    with feedback_client(tmp_path, "use_intent") as (client, owner, _other, langfuse):
        seeded = _seed_report(engine, create_task(client, owner))

        response = client.post(URL, headers=owner, json=_answer(seeded, use_intent))

        assert response.status_code == 201, response.text
        assert (langfuse.scores[0]["value"], langfuse.scores[0]["data_type"]) == (value, data_type)
        assert response.json()["payload"]["use_intent"] == use_intent


def test_a_changed_answer_replaces_the_first(tmp_path: Path, engine: Engine) -> None:
    """One active answer per user and report: "change" retracts the earlier one."""
    with feedback_client(tmp_path, "use_intent") as (client, owner, _other, langfuse):
        seeded = _seed_report(engine, create_task(client, owner))
        first = client.post(URL, headers=owner, json=_answer(seeded, "dismissed")).json()

        second = client.post(URL, headers=owner, json=_answer(seeded, "as_is")).json()

        assert _row(engine, first["feedback_event_id"])["retracted_at"] is not None
        assert langfuse.score_api.deleted == [first["feedback_event_id"]]
        listing = client.get(
            URL, headers=owner, params={"task_id": seeded["task_id"], "kind": "use_intent"}
        )
        assert [
            (record["feedback_event_id"], record["target_id"]) for record in listing.json()["data"]
        ] == [(second["feedback_event_id"], seeded["artefact_id"])]


def test_an_answer_needs_its_flag_a_readable_task_and_a_report_of_that_task(
    tmp_path: Path, engine: Engine
) -> None:
    """Off without the flag; another user's task and another task's report are 404."""
    with feedback_client(tmp_path, "citation_flag") as (client, owner, _other, _langfuse):
        seeded = _seed_report(engine, create_task(client, owner))
        assert client.post(URL, headers=owner, json=_answer(seeded, "no")).status_code == 404

    with feedback_client(tmp_path, "use_intent") as (client, owner, other, langfuse):
        seeded = _seed_report(engine, create_task(client, owner))
        elsewhere = _seed_report(engine, create_task(client, owner))

        assert client.post(URL, headers=other, json=_answer(seeded, "no")).status_code == 404
        wrong_report = _answer(seeded, "no", artefact_id=elsewhere["artefact_id"])
        assert client.post(URL, headers=owner, json=wrong_report).status_code == 404
        assert client.post(URL, headers=owner, json=_answer(seeded, "maybe")).status_code == 422
        unknown_reason = _answer(seeded, "no", change_reasons=["too_blue"])
        assert client.post(URL, headers=owner, json=unknown_reason).status_code == 422
        assert langfuse.scores == []
