"""Grounding — content_hash stability, quote-presence pass/fail, hard-fail behaviour."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.grounding import (
    GroundingError,
    content_hash,
    produce_grounded_block,
    quote_present,
)
from policy_atlas.inference import StubEchoProvider
from policy_atlas.schema import annotation, artefact, block, project
from tests.helpers import now


def _seed_artefact(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
    pid = uuid.uuid4()
    aid = uuid.uuid4()
    conn.execute(project.insert().values(project_id=pid, created_at=now()))
    conn.execute(artefact.insert().values(
        artefact_id=aid, project_id=pid, title="t", created_at=now()
    ))
    return pid, aid


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
    _, aid = _seed_artefact(conn)
    ids = produce_grounded_block(
        conn, artefact_id=aid, source_ref="syn-001", provider=StubEchoProvider()
    )
    assert "block_id" in ids
    assert "unit_id" in ids
    assert "annotation_id" in ids

    # Verify annotation payload
    row = conn.execute(
        annotation.select().where(annotation.c.annotation_id == ids["annotation_id"])
    ).one()
    assert row.payload["verification_result"] == "pass"
    assert row.payload["source_ref"] == "syn-001"


def test_produce_grounded_block_fabricated_quote_hard_fail(conn: Connection) -> None:
    """A provider returning a fabricated quote must raise GroundingError.

    The annotation is still written with verification_result='fail' — flag, don't drop.
    """
    _, aid = _seed_artefact(conn)

    class FabricatedProvider:
        def complete(self, prompt: str) -> str:  # noqa: ARG002
            return "This quote does not appear in any source chunk at all."

    with pytest.raises(GroundingError):
        produce_grounded_block(
            conn, artefact_id=aid, source_ref="syn-001", provider=FabricatedProvider()
        )

    # Annotation was written with fail result — never promoted to clean tier
    # Scope to this test's artefact to avoid picking up rows from other runs.
    row = conn.execute(
        annotation.select().where(
            annotation.c.block_id.in_(
                select(block.c.block_id).where(block.c.artefact_id == aid)
            )
        )
    ).one()
    assert row.payload["verification_result"] == "fail"
    assert row.annotation_type == "citation"
