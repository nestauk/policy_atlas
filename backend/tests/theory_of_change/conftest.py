"""Shared fixtures for the theory-of-change walk tests."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy.engine import Engine

from tests.helpers import delete_task_data
from tests.theory_of_change.test_walks import await_children


@pytest.fixture
def cleanup(engine: Engine) -> Iterator[list[uuid.UUID]]:
    """Tasks a test appends here are deleted once their walks have ended."""
    tasks: list[uuid.UUID] = []
    yield tasks
    for task_id in tasks:
        await_children(engine, task_id)
        with engine.begin() as conn:
            delete_task_data(conn, task_id)
