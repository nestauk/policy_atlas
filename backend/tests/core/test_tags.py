"""Tests for the shared ``source_tag`` write path in ``policy_atlas.core.tags``."""

import uuid
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import METHODOLOGICAL_STRUCTURAL, source_tag
from policy_atlas.core.tags import TAG_INSERT_BATCH, insert_source_tags
from tests.helpers import now, seed_project_and_run, seed_source

# PostgreSQL's hard limit on bind parameters in one statement.
_MAX_BIND_PARAMS = 65_535


def test_insert_source_tags_batches_more_rows_than_one_statement_can_bind() -> None:
    """A big acquire round must not be sent as one oversized statement.

    PostgreSQL accepts at most 65,535 bind parameters per statement and a tag
    row spends 9 of them, so a single insert breaks above ~7,281 rows — which a
    search round at a high record cap reaches. No database needed: this counts
    the statements the write path emits and checks each one's parameter load.
    """

    class _RecordingConn:
        def __init__(self) -> None:
            self.statements: list[Any] = []

        def execute(self, statement: Any) -> None:
            self.statements.append(statement)

    recorder = _RecordingConn()
    pss_id = uuid.uuid4()
    n_rows = TAG_INSERT_BATCH * 2 + 1

    insert_source_tags(
        cast(Connection, recorder),
        project_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        now=now(),
        assertions=[(pss_id, f"tag-{i}", "test") for i in range(n_rows)],
    )

    assert len(recorder.statements) == 3
    for statement in recorder.statements:
        assert len(statement.compile().params) <= _MAX_BIND_PARAMS


def test_insert_source_tags_no_rows_executes_nothing() -> None:
    class _RecordingConn:
        def __init__(self) -> None:
            self.statements: list[Any] = []

        def execute(self, statement: Any) -> None:
            self.statements.append(statement)

    recorder = _RecordingConn()
    insert_source_tags(
        cast(Connection, recorder),
        project_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        now=now(),
        assertions=[],
    )
    assert recorder.statements == []


def test_insert_source_tags_default_topic_theme(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    _, pss_id = seed_source(conn, pid)

    insert_source_tags(
        conn, project_id=pid, run_id=rid, now=now(),
        assertions=[(pss_id, "housing", "test")],
    )

    row = conn.execute(
        select(source_tag.c.tag_type).where(source_tag.c.project_source_snapshot_id == pss_id)
    ).one()
    assert row.tag_type == "topic_theme"


def test_insert_source_tags_methodological_structural(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    _, pss_id = seed_source(conn, pid)

    insert_source_tags(
        conn, project_id=pid, run_id=rid, now=now(),
        assertions=[(pss_id, "rct", "test")],
        tag_type=METHODOLOGICAL_STRUCTURAL,
    )

    row = conn.execute(
        select(source_tag.c.tag_type).where(source_tag.c.project_source_snapshot_id == pss_id)
    ).one()
    assert row.tag_type == "methodological_structural"


def test_insert_source_tags_theme_less_reassertion_keeps_existing_theme_id(
    conn: Connection,
) -> None:
    """A theme-less re-assertion of the same tag must not clobber theme_id to NULL."""
    pid, rid = seed_project_and_run(conn)
    _, pss_id = seed_source(conn, pid)
    theme_id = uuid.uuid4()

    insert_source_tags(
        conn, project_id=pid, run_id=rid, now=now(),
        assertions=[(pss_id, "housing", "test")],
        theme_id=theme_id,
    )
    insert_source_tags(
        conn, project_id=pid, run_id=rid, now=now(),
        assertions=[(pss_id, "housing", "test")],
    )

    row = conn.execute(
        select(source_tag.c.theme_id).where(source_tag.c.project_source_snapshot_id == pss_id)
    ).one()
    assert row.theme_id == theme_id


def test_insert_source_tags_theme_reassertion_with_new_theme_id_updates(
    conn: Connection,
) -> None:
    """A theme-carrying re-assertion of the same tag overwrites the durable theme_id."""
    pid, rid = seed_project_and_run(conn)
    _, pss_id = seed_source(conn, pid)
    theme_id = uuid.uuid4()
    new_theme_id = uuid.uuid4()

    insert_source_tags(
        conn, project_id=pid, run_id=rid, now=now(),
        assertions=[(pss_id, "housing", "test")],
        theme_id=theme_id,
    )
    insert_source_tags(
        conn, project_id=pid, run_id=rid, now=now(),
        assertions=[(pss_id, "housing", "test")],
        theme_id=new_theme_id,
    )

    row = conn.execute(
        select(source_tag.c.theme_id).where(source_tag.c.project_source_snapshot_id == pss_id)
    ).one()
    assert row.theme_id == new_theme_id


def test_insert_source_tags_theme_less_duplicate_assertion_in_one_batch_does_not_raise(
    conn: Connection,
) -> None:
    """A theme-less batch with the same assertion twice is idempotent, not an error."""
    pid, rid = seed_project_and_run(conn)
    _, pss_id = seed_source(conn, pid)

    insert_source_tags(
        conn, project_id=pid, run_id=rid, now=now(),
        assertions=[(pss_id, "housing", "test"), (pss_id, "housing", "test")],
    )

    rows = conn.execute(
        select(source_tag.c.tag).where(source_tag.c.project_source_snapshot_id == pss_id)
    ).all()
    assert len(rows) == 1
