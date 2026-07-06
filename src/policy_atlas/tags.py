"""Single write path for ``source_tag`` assertion rows.

Both tag writers (acquire's provider materialisation, characterise's theme
persistence) route through here so the row shape, the conflict target and the
``topic_theme`` tag type stay in one place.
"""

from __future__ import annotations

import unicodedata
import uuid
from datetime import datetime

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection

from policy_atlas.schema import TOPIC_THEME, source_tag


def has_control_character(value: str) -> bool:
    """Return True when any character is in a Unicode C (control/format) category."""
    return any(unicodedata.category(char).startswith("C") for char in value)


def insert_source_tags(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    now: datetime,
    assertions: list[tuple[uuid.UUID, str, str]],
) -> None:
    """Insert tag assertion rows, idempotent on the assertion unique constraint.

    Args:
        conn: Open database connection; inserts use its active transaction.
        project_id: Owning project.
        run_id: Run recorded as the assertion's creator.
        now: Timestamp for ``created_at``.
        assertions: ``(project_source_snapshot_id, tag, asserted_by)`` triples.
    """
    rows = [
        {
            "source_tag_id": uuid.uuid4(),
            "project_id": project_id,
            "project_source_snapshot_id": pss_id,
            "tag": tag,
            "tag_type": TOPIC_THEME,
            "asserted_by": asserted_by,
            "created_by_run_id": run_id,
            "created_at": now,
        }
        for pss_id, tag, asserted_by in assertions
    ]
    if rows:
        conn.execute(
            pg_insert(source_tag)
            .values(rows)
            .on_conflict_do_nothing(constraint="uq_source_tag_assertion")
        )
