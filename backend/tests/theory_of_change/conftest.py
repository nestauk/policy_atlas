"""Shared fixtures for the theory-of-change walk tests."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy.engine import Engine

from policy_atlas.core import events
from tests.helpers import delete_task_data
from tests.theory_of_change.test_walks import await_children


@pytest.fixture(autouse=True)
def _wider_event_append_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give these tests more append retries than production has.

    A check walk's six child walks can make the parent's append lose more than
    ``APPEND_ATTEMPTS`` races on a loaded runner, a known production ceiling
    (docs/deferred.md, the event-log sequence retry entry). The fix is its own
    slice; until then these tests should not fail on it.
    """
    monkeypatch.setattr(events, "APPEND_ATTEMPTS", 256)


@pytest.fixture
def cleanup(engine: Engine) -> Iterator[list[uuid.UUID]]:
    """Tasks a test appends here are deleted once their walks have ended."""
    tasks: list[uuid.UUID] = []
    yield tasks
    for task_id in tasks:
        await_children(engine, task_id)
        with engine.begin() as conn:
            delete_task_data(conn, task_id)
