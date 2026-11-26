"""In-app feedback foundations: the envelope, toggles, the trace join and the score mirror.

Covers ``core/feedback.py``, the two mirror functions in ``core/tracing.py``,
the runner's trace id write, and the migration round trip. Tracing is off in
the test suite, so the score calls go to a fake client.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from alembic import command
from sqlalchemy import inspect, select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from policy_atlas.core import tracing
from policy_atlas.core.feedback import record_feedback, retract_feedback, trace_id_for
from policy_atlas.core.schema import app_user, feedback_event, runs
from policy_atlas.runtime.runner import _store_trace_id
from tests.conftest import _alembic_cfg
from tests.feedback_support import FakeLangfuse, seed_component_run
from tests.helpers import delete_task_data, now, seed_task_and_run, seed_walk

PREVIOUS_REVISION = "a3c9e1f7b2d4"


def _user(conn: Connection) -> str:
    """Insert one ``app_user`` row and return its id."""
    user_id = f"feedback-{uuid.uuid4()}"
    conn.execute(
        app_user.insert().values(user_id=user_id, display_name="Tester", created_at=now())
    )
    return user_id


def _flag(conn: Connection, user_id: str, **overrides: Any) -> Any:
    """Record one citation flag with defaults that a test can override."""
    values: dict[str, Any] = {
        "user_id": user_id,
        "surface": "report_references",
        "kind": "citation_flag",
        "target_type": "document",
        "target_id": "doc-1",
        "payload": {"action": "useful"},
    }
    return record_feedback(conn, **{**values, **overrides})


def test_a_record_carries_the_full_envelope(conn: Connection) -> None:
    """Each envelope column is stored, and the trace comes from the named component."""
    user_id = _user(conn)
    task_id, _ = seed_task_and_run(conn)
    walk = seed_walk(conn, task_id, capability="evidence_search")
    seed_component_run(conn, task_id, walk.walk_id, "acquire", trace_id="trace-acquire")
    seed_component_run(conn, task_id, walk.walk_id, "synthesise", trace_id="trace-synthesise")

    recorded = _flag(
        conn,
        user_id,
        capability_run_id=walk.walk_id,
        component="synthesise",
        pa_version="v1.2.3",
    )

    row = conn.execute(
        select(feedback_event).where(
            feedback_event.c.feedback_event_id == recorded.feedback_event_id
        )
    ).mappings().one()
    assert recorded.trace_id == "trace-synthesise"
    assert recorded.replaced_id is None
    assert row["user_id"] == user_id
    assert row["capability_run_id"] == walk.walk_id
    assert row["trace_id"] == "trace-synthesise"
    assert (row["surface"], row["kind"]) == ("report_references", "citation_flag")
    assert (row["target_type"], row["target_id"]) == ("document", "doc-1")
    assert row["payload"] == {"action": "useful"}
    assert row["pa_version"] == "v1.2.3"
    assert row["created_at"] is not None
    assert row["retracted_at"] is None


def test_a_second_submit_of_a_toggle_retracts_the_first(conn: Connection) -> None:
    """One active row per (user, target, kind); the old row is kept, retracted."""
    user_id = _user(conn)
    first = _flag(conn, user_id)

    second = _flag(conn, user_id, payload={"action": "not_relevant"})

    assert second.replaced_id == first.feedback_event_id
    rows = conn.execute(
        select(feedback_event.c.feedback_event_id, feedback_event.c.retracted_at).where(
            feedback_event.c.user_id == user_id
        )
    ).all()
    active = [row.feedback_event_id for row in rows if row.retracted_at is None]
    assert len(rows) == 2
    assert active == [second.feedback_event_id]


def test_a_toggle_is_per_user_and_per_target(conn: Connection) -> None:
    """Another user, or another target, does not replace the flag."""
    user_id = _user(conn)
    _flag(conn, user_id)

    assert _flag(conn, _user(conn)).replaced_id is None
    assert _flag(conn, user_id, target_id="doc-2").replaced_id is None


def test_a_kind_that_is_not_a_toggle_keeps_every_record(conn: Connection) -> None:
    """A user can report many problems for one run."""
    user_id = _user(conn)
    report = {
        "surface": "app_header",
        "kind": "problem_report",
        "target_type": "run",
        "target_id": None,
        "payload": {"problem_kind": "error"},
    }

    first = _flag(conn, user_id, **report)
    second = _flag(conn, user_id, **report)

    assert second.replaced_id is None
    assert first.feedback_event_id != second.feedback_event_id
    assert first.trace_id is None


def test_the_index_refuses_two_active_rows_for_one_toggle(conn: Connection) -> None:
    """The unique partial index is the guard when two submits race."""
    user_id = _user(conn)
    recorded = _flag(conn, user_id)
    row = conn.execute(
        select(feedback_event).where(
            feedback_event.c.feedback_event_id == recorded.feedback_event_id
        )
    ).mappings().one()

    with pytest.raises(IntegrityError, match="uq_feedback_event_active_toggle"):
        conn.execute(feedback_event.insert().values({**row, "feedback_event_id": uuid.uuid4()}))


def test_the_schema_refuses_a_value_outside_a_closed_list(conn: Connection) -> None:
    """``kind`` is a Text column with a CHECK, not a free string."""
    with pytest.raises(IntegrityError, match="ck_feedback_event_kind"):
        _flag(conn, _user(conn), kind="thumbs")


def test_retraction_keeps_the_row_and_is_only_for_the_owner(conn: Connection) -> None:
    """Retraction sets ``retracted_at``; another user cannot retract; twice is a no-op."""
    user_id = _user(conn)
    recorded = _flag(conn, user_id)
    event_id = recorded.feedback_event_id

    assert retract_feedback(conn, feedback_event_id=event_id, user_id=_user(conn)) is False
    assert retract_feedback(conn, feedback_event_id=event_id, user_id=user_id) is True
    assert retract_feedback(conn, feedback_event_id=event_id, user_id=user_id) is False
    retracted_at = conn.execute(
        select(feedback_event.c.retracted_at).where(
            feedback_event.c.feedback_event_id == event_id
        )
    ).scalar_one()
    assert retracted_at is not None


def test_the_trace_is_the_newest_run_of_the_component(conn: Connection) -> None:
    """A step that ran twice joins to its newest trace; no component means the newest run."""
    task_id, _ = seed_task_and_run(conn)
    walk = seed_walk(conn, task_id, capability="evidence_search")
    walk_id = walk.walk_id
    seed_component_run(conn, task_id, walk_id, "screen_abstract", trace_id="old", age_minutes=9)
    seed_component_run(conn, task_id, walk_id, "screen_abstract", trace_id="new", age_minutes=5)
    seed_component_run(conn, task_id, walk_id, "synthesise", trace_id="synth", age_minutes=1)

    assert trace_id_for(conn, capability_run_id=walk_id, component="screen_abstract") == "new"
    assert trace_id_for(conn, capability_run_id=walk_id) == "synth"
    assert trace_id_for(conn, capability_run_id=walk_id, component="screen_full") is None


def test_a_run_with_no_stored_trace_gives_no_trace(conn: Connection) -> None:
    """An old run, or a run with tracing off, has a NULL trace id."""
    task_id, _ = seed_task_and_run(conn)
    walk = seed_walk(conn, task_id, capability="evidence_search")
    seed_component_run(conn, task_id, walk.walk_id, "synthesise", trace_id=None)

    assert trace_id_for(conn, capability_run_id=walk.walk_id, component="synthesise") is None


def test_the_runner_stores_the_trace_id_in_its_own_transaction(engine: Engine) -> None:
    """The id is committed on the ``runs`` row; no trace means no write."""
    with engine.begin() as conn:
        task_id, run_id = seed_task_and_run(conn)
    try:
        _store_trace_id(engine, run_id=run_id, trace_id=None)
        with engine.connect() as conn:
            stored = conn.execute(select(runs.c.trace_id).where(runs.c.run_id == run_id))
            assert stored.scalar_one() is None

        _store_trace_id(engine, run_id=run_id, trace_id="trace-abc")
        with engine.connect() as conn:
            stored = conn.execute(select(runs.c.trace_id).where(runs.c.run_id == run_id))
            assert stored.scalar_one() == "trace-abc"
    finally:
        with engine.begin() as conn:
            delete_task_data(conn, task_id)


def test_the_trace_id_of_a_span() -> None:
    """A span gives its trace id; no span (tracing off) gives None."""
    span = type("Span", (), {"trace_id": "abc123"})()

    assert tracing.trace_id_of(span) == "abc123"
    assert tracing.trace_id_of(None) is None


def test_the_score_mirror_writes_one_score_by_trace_id() -> None:
    """The score id is the row id; a label is CATEGORICAL and a number is NUMERIC."""
    client = FakeLangfuse()
    event_id = uuid.uuid4()

    tracing.score_feedback(
        client,  # type: ignore[arg-type]
        feedback_event_id=event_id,
        trace_id="trace-1",
        name="citation_flag",
        value=-1.0,
        comment="not about schools",
        metadata={"surface": "sources_all"},
    )
    tracing.score_feedback(
        client,  # type: ignore[arg-type]
        feedback_event_id=event_id,
        trace_id="trace-1",
        name="claim_flag",
        value="overstated",
    )

    assert client.scores[0] == {
        "score_id": str(event_id),
        "trace_id": "trace-1",
        "name": "citation_flag",
        "value": -1.0,
        "data_type": "NUMERIC",
        "comment": "not about schools",
        "metadata": {"surface": "sources_all", "feedback_event_id": str(event_id)},
    }
    assert client.scores[1]["data_type"] == "CATEGORICAL"


def test_the_score_mirror_does_nothing_without_a_client_or_a_trace() -> None:
    """Tracing off, or a run with no stored trace: the row is kept, no score is written."""
    client = FakeLangfuse()
    event_id = uuid.uuid4()

    tracing.score_feedback(
        None, feedback_event_id=event_id, trace_id="trace-1", name="use_intent", value=2.0
    )
    tracing.score_feedback(
        client,  # type: ignore[arg-type]
        feedback_event_id=event_id,
        trace_id=None,
        name="use_intent",
        value=2.0,
    )

    assert client.scores == []


def test_a_retraction_deletes_the_score_and_a_failure_does_not_raise() -> None:
    """The delete is a direct HTTP call; an error there must not fail the request."""
    event_id = uuid.uuid4()
    client = FakeLangfuse()
    broken = FakeLangfuse(delete_error=ConnectionError("langfuse is down"))

    tracing.delete_feedback_score(client, event_id)  # type: ignore[arg-type]
    tracing.delete_feedback_score(broken, event_id)  # type: ignore[arg-type]
    tracing.delete_feedback_score(None, event_id)

    assert client.score_api.deleted == [str(event_id)]


def test_the_migration_round_trip(engine: Engine) -> None:
    """Downgrade drops the tables and the column; upgrade brings them back."""
    tables = {"feedback_event", "missing_paper_resolution", "user_profile"}
    cfg = _alembic_cfg()
    try:
        command.downgrade(cfg, PREVIOUS_REVISION)
        inspector = inspect(engine)
        assert not tables & set(inspector.get_table_names())
        assert "trace_id" not in {col["name"] for col in inspector.get_columns("runs")}
    finally:
        command.upgrade(cfg, "head")
    inspector = inspect(engine)
    assert tables <= set(inspector.get_table_names())
    assert "trace_id" in {col["name"] for col in inspector.get_columns("runs")}
