"""In-app feedback foundations (task 062, ADR 0045): the event envelope, the
toggle rule, retraction, the Langfuse score mirror, the trace id the runner
stores on each component run, and the migration round trip.

Tests on the ``conn`` fixture roll back. The runner and migration tests commit:
they remove what they wrote and leave the chain at head.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any, cast

import pytest
from alembic import command
from sqlalchemy import inspect, select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from policy_atlas.core import tracing
from policy_atlas.core.feedback import record_feedback_event, retract_feedback, submit_feedback
from policy_atlas.core.schema import app_user, feedback_event, runs
from policy_atlas.runtime import runner as runner_module
from tests.conftest import _alembic_cfg
from tests.helpers import now, seed_task_and_run, seed_walk
from tests.runtime.test_runner import _cleanup, _seed_task, _single_component_attempt

PRE_REVISION = "f5a1c8e93b27"
TRACE_ID = "0af7651916cd43dd8448eb211c80319c"
FEEDBACK_TABLES = {"feedback_event", "missing_paper_resolution", "user_profile"}


class _FakeLangfuse:
    """Records the score calls the mirror makes."""

    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.deleted: list[str] = []
        self.api = SimpleNamespace(
            legacy=SimpleNamespace(score_v1=SimpleNamespace(delete=self.deleted.append))
        )

    def create_score(self, **kwargs: Any) -> None:
        self.created.append(kwargs)

    def flush(self) -> None:
        pass


class _OneConnEngine:
    """Hands ``submit_feedback`` the test's rolled-back connection as its transaction."""

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    @contextmanager
    def begin(self) -> Iterator[Connection]:
        yield self._conn


def _seed(conn: Connection) -> dict[str, Any]:
    """Insert a user and a run with one traced component run; return the event fields."""
    task_id, _ = seed_task_and_run(conn)
    walk = seed_walk(conn, task_id, with_run=True)
    conn.execute(runs.update().where(runs.c.run_id == walk.run_id).values(trace_id=TRACE_ID))
    user_id = f"user-{uuid.uuid4()}"
    conn.execute(
        app_user.insert().values(user_id=user_id, display_name="Test user", created_at=now())
    )
    return {
        "user_id": user_id,
        "capability_run_id": walk.walk_id,
        "component_run_id": walk.run_id,
        "surface": "report_references",
        "kind": "citation_flag",
        "target_type": "document",
        "target_id": str(uuid.uuid4()),
        "payload": {"action": "useful"},
        "pa_version": "abc1234",
    }


def _active(conn: Connection, user_id: str) -> list[Any]:
    return list(
        conn.execute(
            select(feedback_event)
            .where(feedback_event.c.user_id == user_id)
            .where(feedback_event.c.retracted_at.is_(None))
        )
    )


def test_an_event_stores_the_envelope_and_the_component_runs_trace(conn: Connection) -> None:
    event = _seed(conn)

    event_id, trace_id, replaced = record_feedback_event(conn, **event)

    row = conn.execute(
        select(feedback_event).where(feedback_event.c.feedback_event_id == event_id)
    ).one()
    assert (trace_id, replaced) == (TRACE_ID, [])
    assert row.trace_id == TRACE_ID
    assert row.payload == {"action": "useful"}
    assert row.pa_version == "abc1234"
    assert row.retracted_at is None


def test_an_event_with_no_component_run_has_no_trace(conn: Connection) -> None:
    event = _seed(conn) | {"component_run_id": None}

    _, trace_id, _ = record_feedback_event(conn, **event)

    assert trace_id is None


def test_a_changed_toggle_retracts_the_first_row_and_keeps_it(conn: Connection) -> None:
    event = _seed(conn)
    first, _, _ = record_feedback_event(conn, **event)

    second, _, replaced = record_feedback_event(
        conn, **(event | {"payload": {"action": "not_relevant"}})
    )

    assert replaced == [first]
    assert [row.feedback_event_id for row in _active(conn, event["user_id"])] == [second]
    assert (
        conn.execute(
            select(feedback_event.c.retracted_at).where(
                feedback_event.c.feedback_event_id == first
            )
        ).scalar_one()
        is not None
    )


def test_the_same_document_in_another_run_is_a_separate_flag(conn: Connection) -> None:
    event = _seed(conn)
    record_feedback_event(conn, **event)
    task_id, _ = seed_task_and_run(conn)
    other_run = seed_walk(conn, task_id).walk_id

    _, _, replaced = record_feedback_event(
        conn, **(event | {"capability_run_id": other_run, "component_run_id": None})
    )

    assert replaced == []
    assert len(_active(conn, event["user_id"])) == 2


def test_a_kind_that_is_not_a_toggle_keeps_every_row(conn: Connection) -> None:
    event = _seed(conn) | {
        "kind": "missing_paper",
        "surface": "report_foot",
        "target_type": "run",
    }

    record_feedback_event(conn, **event)
    _, _, replaced = record_feedback_event(conn, **event)

    assert replaced == []
    assert len(_active(conn, event["user_id"])) == 2


def test_an_unknown_kind_is_rejected(conn: Connection) -> None:
    event = _seed(conn) | {"kind": "thumbs"}

    with pytest.raises(IntegrityError), conn.begin_nested():
        record_feedback_event(conn, **event)


def test_submit_mirrors_the_row_as_a_score_and_replaces_the_old_score(
    conn: Connection,
) -> None:
    event = _seed(conn)
    engine = cast(Engine, _OneConnEngine(conn))
    client = _FakeLangfuse()

    first = submit_feedback(engine, cast(Any, client), score_value=1.0, **event)
    second = submit_feedback(
        engine,
        cast(Any, client),
        score_value=-1.0,
        comment="About schools, not hospitals",
        score_metadata={"reason": "off_topic"},
        **(event | {"payload": {"action": "not_relevant"}}),
    )

    assert client.created[0] == {
        "trace_id": TRACE_ID,
        "score_id": str(first),
        "name": "citation_flag",
        "value": 1.0,
        "data_type": "NUMERIC",
        "comment": None,
        "metadata": {"feedback_event_id": str(first)},
    }
    assert client.created[1]["score_id"] == str(second)
    assert client.created[1]["comment"] == "About schools, not hospitals"
    assert client.created[1]["metadata"] == {
        "feedback_event_id": str(second),
        "reason": "off_topic",
    }
    assert client.deleted == [str(first)]


def test_submit_saves_the_row_and_writes_no_score_when_the_run_has_no_trace(
    conn: Connection,
) -> None:
    event = _seed(conn) | {"component_run_id": None}
    client = _FakeLangfuse()

    submit_feedback(
        cast(Engine, _OneConnEngine(conn)), cast(Any, client), score_value=1.0, **event
    )

    assert client.created == []
    assert len(_active(conn, event["user_id"])) == 1


def test_retract_sets_retracted_at_and_deletes_the_score_for_the_owner_only(
    conn: Connection,
) -> None:
    event = _seed(conn)
    engine = cast(Engine, _OneConnEngine(conn))
    client = _FakeLangfuse()
    event_id, _, _ = record_feedback_event(conn, **event)

    assert not retract_feedback(
        engine, cast(Any, client), user_id="someone-else", feedback_event_id=event_id
    )
    assert len(_active(conn, event["user_id"])) == 1

    assert retract_feedback(
        engine, cast(Any, client), user_id=event["user_id"], feedback_event_id=event_id
    )
    assert _active(conn, event["user_id"]) == []
    assert client.deleted == [str(event_id)]
    # A second retraction is a no-op.
    assert not retract_feedback(
        engine, cast(Any, client), user_id=event["user_id"], feedback_event_id=event_id
    )


def test_a_category_is_a_categorical_score_and_a_failed_mirror_never_raises() -> None:
    client = _FakeLangfuse()
    tracing.feedback_score(
        cast(Any, client), trace_id=TRACE_ID, score_id="s", name="use_intent", value="dismissed"
    )
    assert client.created[0]["data_type"] == "CATEGORICAL"

    def fail(**kwargs: Any) -> None:
        raise RuntimeError("Langfuse is down")

    client.create_score = fail  # type: ignore[method-assign]
    tracing.feedback_score(
        cast(Any, client), trace_id=TRACE_ID, score_id="s", name="use_intent", value=2.0
    )
    client.api.legacy.score_v1.delete = fail
    tracing.delete_feedback_score(cast(Any, client), score_id="s")
    # Tracing off: nothing to call.
    tracing.feedback_score(None, trace_id=TRACE_ID, score_id="s", name="use_intent", value=2.0)
    tracing.delete_feedback_score(None, score_id="s")


def test_the_runner_stores_the_trace_id_even_when_the_component_rolls_back(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    task_id: uuid.UUID | None = None

    @contextmanager
    def traced_span(*args: Any, **kwargs: Any) -> Iterator[Any]:
        yield SimpleNamespace(trace_id=TRACE_ID)

    def rollback_harness(conn: Connection, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("forced component rollback")

    monkeypatch.setattr(tracing, "component_span", traced_span)
    monkeypatch.setattr(runner_module, "run_harness", rollback_harness)
    try:
        task_id, scope_id = _seed_task(engine)
        outcome = _single_component_attempt(
            engine, task_id=task_id, scope_id=scope_id, component="acquire"
        )
        assert outcome.status == "failed"
        with engine.connect() as conn:
            stored = conn.execute(
                select(runs.c.trace_id).where(runs.c.task_id == task_id)
            ).scalar_one()
        assert stored == TRACE_ID
    finally:
        _cleanup(engine, task_id)


def test_the_revision_round_trips(engine: Engine) -> None:
    cfg = _alembic_cfg()

    def shape() -> tuple[set[str], bool]:
        with engine.connect() as conn:
            inspector = inspect(conn)
            tables = FEEDBACK_TABLES & set(inspector.get_table_names())
            has_trace = "trace_id" in {c["name"] for c in inspector.get_columns("runs")}
        return tables, has_trace

    try:
        command.upgrade(cfg, "head")
        assert shape() == (FEEDBACK_TABLES, True)
        command.downgrade(cfg, PRE_REVISION)
        assert shape() == (set(), False)
    finally:
        command.upgrade(cfg, "head")
    assert shape() == (FEEDBACK_TABLES, True)
