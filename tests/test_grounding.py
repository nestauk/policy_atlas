"""Grounding — content_hash stability, quote-presence pass/fail, hard-fail behaviour."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.fixtures import get_source
from policy_atlas.grounding import (
    GroundingError,
    content_hash,
    produce_grounded_block,
    quote_present,
)
from policy_atlas.inference import StubEchoProvider
from policy_atlas.ingest_upload import ingest_upload
from policy_atlas.schema import annotation, artefact, block, project
from policy_atlas.schema import chunk as chunk_table
from policy_atlas.schema import citation as citation_table
from tests.helpers import now

_CHUNKS = list(get_source("syn-001").chunks)


def _seed_artefact(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
    pid = uuid.uuid4()
    aid = uuid.uuid4()
    conn.execute(project.insert().values(project_id=pid, created_at=now()))
    conn.execute(artefact.insert().values(
        artefact_id=aid, project_id=pid, title="t", created_at=now()
    ))
    return pid, aid


def _seed_snapshot(conn: Connection, project_id: uuid.UUID) -> uuid.UUID:
    """Seed the two-sentence synthetic source into the DB and return snapshot_id."""
    return ingest_upload(
        conn,
        project_id=project_id,
        chunks=_CHUNKS,
        source_locator="syn-001",
        metadata={"synthetic": True},
        text_basis="full_text",
    )


def test_content_hash_stable() -> None:
    assert content_hash("hello world") == content_hash("hello world")


def test_content_hash_whitespace_insensitive() -> None:
    assert content_hash("hello  world") == content_hash("hello world")


def test_quote_present_exact() -> None:
    assert quote_present("foo bar", ("foo bar baz",))


def test_quote_present_boundary_spanning() -> None:
    """A quote spanning two chunks is found after concatenation."""
    assert quote_present("bar baz", ("foo bar ", "baz qux"))


def test_quote_absent() -> None:
    assert not quote_present("not here", ("foo bar",))


def test_produce_grounded_block_pass(conn: Connection) -> None:
    pid, aid = _seed_artefact(conn)
    snapshot_id = _seed_snapshot(conn, pid)
    ids = produce_grounded_block(
        conn,
        artefact_id=aid,
        source_snapshot_id=snapshot_id,
        provider=StubEchoProvider(),
    )
    assert "block_id" in ids
    assert "unit_id" in ids
    assert "annotation_id" in ids
    assert "citation_id" in ids

    # Annotation payload shape
    row = conn.execute(
        annotation.select().where(annotation.c.annotation_id == ids["annotation_id"])
    ).one()
    assert row.payload["verification_result"] == "pass"
    assert "source_ref" not in row.payload

    # Citation row has non-null chunk_id FK
    cit = conn.execute(
        select(citation_table).where(citation_table.c.citation_id == ids["citation_id"])
    ).one()
    assert cit.chunk_id is not None
    assert cit.verification_result == "pass"


def test_produce_grounded_block_fabricated_quote_hard_fail(conn: Connection) -> None:
    """A provider returning a fabricated quote must raise GroundingError.

    Annotation and citation are still written with verification_result='fail' — flag, don't drop.
    """
    pid, aid = _seed_artefact(conn)
    snapshot_id = _seed_snapshot(conn, pid)

    class FabricatedProvider:
        def complete(self, prompt: str) -> str:  # noqa: ARG002
            return "This quote does not appear in any source chunk at all."

    with pytest.raises(GroundingError):
        produce_grounded_block(
            conn,
            artefact_id=aid,
            source_snapshot_id=snapshot_id,
            provider=FabricatedProvider(),
        )

    # Annotation written with fail result
    row = conn.execute(
        annotation.select().where(
            annotation.c.block_id.in_(
                select(block.c.block_id).where(block.c.artefact_id == aid)
            )
        )
    ).one()
    assert row.payload["verification_result"] == "fail"
    assert row.annotation_type == "citation"

    # Citation row also written with fail + chunk_id still set (flag-don't-drop)
    cit = conn.execute(
        select(citation_table).where(citation_table.c.annotation_id == row.annotation_id)
    ).one()
    assert cit.verification_result == "fail"
    assert cit.chunk_id is not None


def test_citation_annotation_fk_integrity(conn: Connection) -> None:
    """Every annotation_type='citation' row must have a matching citation row."""
    pid, aid = _seed_artefact(conn)
    snapshot_id = _seed_snapshot(conn, pid)
    produce_grounded_block(
        conn,
        artefact_id=aid,
        source_snapshot_id=snapshot_id,
        provider=StubEchoProvider(),
    )

    # All citation annotations for this artefact have a citation row
    ann_ids = [
        row.annotation_id
        for row in conn.execute(
            select(annotation.c.annotation_id).where(
                annotation.c.block_id.in_(
                    select(block.c.block_id).where(block.c.artefact_id == aid)
                ),
                annotation.c.annotation_type == "citation",
            )
        ).fetchall()
    ]
    assert ann_ids, "expected at least one citation annotation"

    for ann_id in ann_ids:
        cit = conn.execute(
            select(citation_table).where(citation_table.c.annotation_id == ann_id)
        ).one_or_none()
        assert cit is not None, f"annotation {ann_id} has no matching citation row"
        assert cit.chunk_id is not None


def test_produce_grounded_block_missing_snapshot_raises(conn: Connection) -> None:
    """A non-existent source_snapshot_id raises ValueError before any rows are written."""
    _, aid = _seed_artefact(conn)

    with pytest.raises(ValueError, match="No chunks found"):
        produce_grounded_block(
            conn,
            artefact_id=aid,
            source_snapshot_id=uuid.uuid4(),
            provider=StubEchoProvider(),
        )

    assert conn.execute(
        select(block.c.block_id).where(block.c.artefact_id == aid)
    ).one_or_none() is None


def test_boundary_spanning_quote_cites_first_chunk(conn: Connection) -> None:
    """A quote spanning two chunks falls back to chunk sequence=1 for citation.chunk_id."""
    pid, aid = _seed_artefact(conn)
    snapshot_id = _seed_snapshot(conn, pid)

    first_chunk_id = conn.execute(
        select(chunk_table.c.chunk_id)
        .where(chunk_table.c.source_snapshot_id == snapshot_id)
        .order_by(chunk_table.c.sequence)
        .limit(1)
    ).scalar_one()

    class SpanningProvider:
        def complete(self, prompt: str) -> str:  # noqa: ARG002
            # Straddles chunk 1 end ("...test source. ") and chunk 2 start ("Evidence suggests...")
            # Present in the concatenation, absent from either chunk alone.
            return "test source. Evidence"

    ids = produce_grounded_block(
        conn,
        artefact_id=aid,
        source_snapshot_id=snapshot_id,
        provider=SpanningProvider(),
    )

    cit = conn.execute(
        select(citation_table).where(citation_table.c.citation_id == ids["citation_id"])
    ).one()
    assert cit.chunk_id == first_chunk_id
    assert cit.verification_result == "pass"
