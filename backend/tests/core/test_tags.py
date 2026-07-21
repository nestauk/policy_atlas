"""Tests for the shared ``source_tag`` write path in ``policy_atlas.core.tags``."""

from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import METHODOLOGICAL_STRUCTURAL, source_tag
from policy_atlas.core.tags import insert_source_tags
from tests.helpers import now, seed_project_and_run, seed_source


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
