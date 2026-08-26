"""Single write path for ``source_tag`` assertion rows.

Both tag writers (acquire's provider materialisation, characterise's theme
persistence) route through here so the row shape and the conflict target stay
in one place. The tag type is a parameter defaulting to ``topic_theme``.
"""

from __future__ import annotations

import unicodedata
import uuid
from datetime import datetime
from itertools import batched

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import TOPIC_THEME, source_tag

# Rows per INSERT statement. The point of inserting in bulk is to stop paying a
# database round trip per row; 1,000 rows a statement already makes round trips
# negligible (a 7,000-tag acquire round costs 7 of them). Batching is also what
# keeps this write path safe at any size: PostgreSQL accepts at most 65,535
# bind parameters in one statement, and a row here spends 9 of them, so a
# single unbatched statement breaks somewhere above 7,281 rows — a ceiling a
# big search round can reach (and did, at record_cap_per_backend=1000).
TAG_INSERT_BATCH = 1_000


def has_control_character(value: str) -> bool:
    """Return True when any character is in a Unicode C (control/format) category.

    Args:
        value: Text to scan.
    """
    return any(unicodedata.category(char).startswith("C") for char in value)


def insert_source_tags(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    now: datetime,
    assertions: list[tuple[uuid.UUID, str, str]],
    tag_type: str = TOPIC_THEME,
    theme_id: uuid.UUID | None = None,
) -> None:
    """Insert tag assertion rows, idempotent on the assertion unique constraint.

    Args:
        conn: Open database connection; inserts use its active transaction.
        project_id: Owning project.
        run_id: Run recorded as the assertion's creator.
        now: Timestamp for ``created_at``.
        assertions: ``(project_source_snapshot_id, tag, asserted_by)`` triples.
        tag_type: The tag-assignment type; defaults to ``topic_theme`` so
            existing callers are untouched.
        theme_id: Optional durable identity for a characterisation theme.
    """
    rows = [
        {
            "source_tag_id": uuid.uuid4(),
            "project_id": project_id,
            "project_source_snapshot_id": pss_id,
            "tag": tag,
            "tag_type": tag_type,
            "asserted_by": asserted_by,
            "created_by_run_id": run_id,
            "created_at": now,
            "theme_id": theme_id,
        }
        for pss_id, tag, asserted_by in assertions
    ]
    # Batched (see TAG_INSERT_BATCH): the conflict clause is per row, not per
    # statement, so splitting one big insert into several changes nothing about
    # the result — duplicates across batches resolve the same way as inside one.
    for batch in batched(rows, TAG_INSERT_BATCH):
        insert = pg_insert(source_tag).values(list(batch))
        # Only the theme-carrying caller (characterise) may overwrite on
        # conflict; theme-less callers keep the historical do-nothing so a
        # re-assertion never clobbers an existing theme_id to NULL (review 028
        # m2). do_nothing also tolerates duplicate keys inside one batch.
        if theme_id is None:
            statement = insert.on_conflict_do_nothing(constraint="uq_source_tag_assertion")
        else:
            statement = insert.on_conflict_do_update(
                constraint="uq_source_tag_assertion",
                set_={"theme_id": theme_id},
            )
        conn.execute(statement)
