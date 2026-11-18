"""Shared support for the in-app feedback tests: a fake Langfuse client and seeds.

Tracing is off in the test suite (``tests/conftest.py`` removes the Langfuse
keys), so a test that asserts a score call passes this fake client in.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy.engine import Connection

from policy_atlas.core import events
from policy_atlas.core.schema import runs
from tests.helpers import now, seed_run


class FakeScoreApi:
    """Stands in for ``client.api.legacy.score_v1``: records each delete."""

    def __init__(self, error: Exception | None = None) -> None:
        self.deleted: list[str] = []
        self.error = error

    def delete(self, score_id: str) -> None:
        """Record the delete, or raise the configured error."""
        if self.error is not None:
            raise self.error
        self.deleted.append(score_id)


class FakeLangfuse:
    """Stands in for the Langfuse client: records each ``create_score`` call."""

    def __init__(self, delete_error: Exception | None = None) -> None:
        self.scores: list[dict[str, Any]] = []
        self.score_api = FakeScoreApi(delete_error)
        self.api = type("Api", (), {"legacy": type("Legacy", (), {"score_v1": self.score_api})})

    def create_score(self, **kwargs: Any) -> None:
        """Record the keyword arguments of one score write."""
        self.scores.append(kwargs)

    def get_trace_url(self, *, trace_id: str) -> str:
        """Return a link to a trace, as the SDK does."""
        return f"https://langfuse.example.test/trace/{trace_id}"


def seed_component_run(
    conn: Connection,
    task_id: uuid.UUID,
    walk_id: uuid.UUID,
    component: str,
    *,
    trace_id: str | None,
    age_minutes: int = 0,
) -> uuid.UUID:
    """Insert a component run with its ``component.started`` event and trace id.

    Args:
        conn: Open database connection.
        task_id: The task.
        walk_id: The user-facing run (``capability_run_id``).
        component: The pipeline step, as the runner names it in the event.
        trace_id: The stored Langfuse trace id, or ``None`` for a run with none.
        age_minutes: How long ago the run started.

    Returns:
        The ``run_id`` of the new component run.
    """
    run_id = seed_run(
        conn,
        task_id,
        capability_run_id=walk_id,
        started_at=now() - timedelta(minutes=age_minutes),
    )
    conn.execute(runs.update().where(runs.c.run_id == run_id).values(trace_id=trace_id))
    events.append(
        conn,
        task_id=task_id,
        run_id=run_id,
        event_type="component.started",
        payload={"component": component},
    )
    return run_id
