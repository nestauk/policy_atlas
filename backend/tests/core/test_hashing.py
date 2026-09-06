"""content_hash stability and normalisation."""

import uuid

from sqlalchemy import select, update
from sqlalchemy.engine import Connection

from policy_atlas.core.hashing import content_hash
from policy_atlas.core.schema import artefact, block
from tests.helpers import now, seed_task_and_run


def test_content_hash_stable() -> None:
    assert content_hash("hello world") == content_hash("hello world")


def test_content_hash_whitespace_insensitive() -> None:
    assert content_hash("hello  world") == content_hash("hello world")


def test_block_content_hash_is_unchanged_by_summary(conn: Connection) -> None:
    """Block summaries are metadata and never enter the content hash."""
    task_id, _ = seed_task_and_run(conn)
    artefact_id, block_id = uuid.uuid4(), uuid.uuid4()
    prose = "The content that was synthesised."
    hashed = content_hash(prose)
    conn.execute(
        artefact.insert().values(
            artefact_id=artefact_id,
            task_id=task_id,
            title="Hash fixture",
            created_at=now(),
        )
    )
    conn.execute(
        block.insert().values(
            block_id=block_id,
            artefact_id=artefact_id,
            version=1,
            content=prose,
            content_hash=hashed,
            created_at=now(),
        )
    )
    conn.execute(
        update(block)
        .where(block.c.block_id == block_id)
        .values(summary="A verified short summary.", summary_status="verified")
    )
    assert (
        conn.execute(select(block.c.content_hash).where(block.c.block_id == block_id)).scalar_one()
        == hashed
    )
