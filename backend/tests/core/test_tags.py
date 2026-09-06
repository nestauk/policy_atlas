"""Tests for the shared ``source_tag`` write path in ``policy_atlas.core.tags``."""

import uuid

from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import METHODOLOGICAL_STRUCTURAL, source_tag
from policy_atlas.core.tags import insert_source_tags
from tests.helpers import now, seed_source, seed_task_and_run


def test_insert_source_tags_default_topic_theme(conn: Connection) -> None:
    pid, rid = seed_task_and_run(conn)
    _, tss_id = seed_source(conn, pid)

    insert_source_tags(
        conn, task_id=pid, run_id=rid, now=now(),
        assertions=[(tss_id, "housing", "test")],
    )

    row = conn.execute(
        select(source_tag.c.tag_type).where(source_tag.c.task_source_snapshot_id == tss_id)
    ).one()
    assert row.tag_type == "topic_theme"


def test_insert_source_tags_methodological_structural(conn: Connection) -> None:
    pid, rid = seed_task_and_run(conn)
    _, tss_id = seed_source(conn, pid)

    insert_source_tags(
        conn, task_id=pid, run_id=rid, now=now(),
        assertions=[(tss_id, "rct", "test")],
        tag_type=METHODOLOGICAL_STRUCTURAL,
    )

    row = conn.execute(
        select(source_tag.c.tag_type).where(source_tag.c.task_source_snapshot_id == tss_id)
    ).one()
    assert row.tag_type == "methodological_structural"


def test_insert_source_tags_theme_less_reassertion_keeps_existing_theme_id(
    conn: Connection,
) -> None:
    """A theme-less re-assertion of the same tag must not clobber theme_id to NULL."""
    pid, rid = seed_task_and_run(conn)
    _, tss_id = seed_source(conn, pid)
    theme_id = uuid.uuid4()

    insert_source_tags(
        conn, task_id=pid, run_id=rid, now=now(),
        assertions=[(tss_id, "housing", "test")],
        theme_id=theme_id,
    )
    insert_source_tags(
        conn, task_id=pid, run_id=rid, now=now(),
        assertions=[(tss_id, "housing", "test")],
    )

    row = conn.execute(
        select(source_tag.c.theme_id).where(source_tag.c.task_source_snapshot_id == tss_id)
    ).one()
    assert row.theme_id == theme_id


def test_insert_source_tags_theme_reassertion_with_new_theme_id_updates(
    conn: Connection,
) -> None:
    """A theme-carrying re-assertion of the same tag overwrites the durable theme_id."""
    pid, rid = seed_task_and_run(conn)
    _, tss_id = seed_source(conn, pid)
    theme_id = uuid.uuid4()
    new_theme_id = uuid.uuid4()

    insert_source_tags(
        conn, task_id=pid, run_id=rid, now=now(),
        assertions=[(tss_id, "housing", "test")],
        theme_id=theme_id,
    )
    insert_source_tags(
        conn, task_id=pid, run_id=rid, now=now(),
        assertions=[(tss_id, "housing", "test")],
        theme_id=new_theme_id,
    )

    row = conn.execute(
        select(source_tag.c.theme_id).where(source_tag.c.task_source_snapshot_id == tss_id)
    ).one()
    assert row.theme_id == new_theme_id


def test_insert_source_tags_theme_less_duplicate_assertion_in_one_batch_does_not_raise(
    conn: Connection,
) -> None:
    """A theme-less batch with the same assertion twice is idempotent, not an error."""
    pid, rid = seed_task_and_run(conn)
    _, tss_id = seed_source(conn, pid)

    insert_source_tags(
        conn, task_id=pid, run_id=rid, now=now(),
        assertions=[(tss_id, "housing", "test"), (tss_id, "housing", "test")],
    )

    rows = conn.execute(
        select(source_tag.c.tag).where(source_tag.c.task_source_snapshot_id == tss_id)
    ).all()
    assert len(rows) == 1
