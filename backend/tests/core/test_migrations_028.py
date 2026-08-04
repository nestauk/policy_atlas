"""Roundtrip coverage for task 028 Phase-A additive columns."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url

from policy_atlas.core.schema import artefact, block, planning_transcript, source_tag
from tests.conftest import _alembic_cfg
from tests.helpers import seed_project_and_run, seed_source

PRE_028_REVISION = "e9a7c3d1f6b4"


def test_028_migration_roundtrip_preserves_legacy_rows(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Upgrade nullable columns, then downgrade without touching legacy rows."""
    shared = engine
    base_url = make_url(os.environ["DATABASE_URL"])
    scratch_name = f"{base_url.database}_migr_{uuid.uuid4().hex[:8]}"
    with shared.connect().execution_options(isolation_level="AUTOCOMMIT") as admin:
        admin.execute(text(f'CREATE DATABASE "{scratch_name}"'))
    scratch_url = base_url.set(database=scratch_name)
    monkeypatch.setenv("DATABASE_URL", scratch_url.render_as_string(hide_password=False))
    scratch = create_engine(scratch_url)
    cfg = _alembic_cfg()
    artefact_id, block_id, tag_id, transcript_id = (uuid.uuid4() for _ in range(4))

    try:
        command.upgrade(cfg, PRE_028_REVISION)
        with scratch.begin() as conn:
            project_id, run_id = seed_project_and_run(conn)
            _, pss_id = seed_source(conn, project_id)
            now = datetime(2026, 8, 4, tzinfo=UTC)
            conn.execute(
                artefact.insert().values(
                    artefact_id=artefact_id,
                    project_id=project_id,
                    title="Legacy artefact",
                    created_at=now,
                )
            )
            conn.execute(
                block.insert().values(
                    block_id=block_id,
                    artefact_id=artefact_id,
                    version=1,
                    content="Legacy block",
                    content_hash="legacy-hash",
                    created_at=now,
                )
            )
            conn.execute(
                source_tag.insert().values(
                    source_tag_id=tag_id,
                    project_id=project_id,
                    project_source_snapshot_id=pss_id,
                    tag="Legacy theme",
                    tag_type="topic_theme",
                    asserted_by="characterise",
                    created_by_run_id=run_id,
                    created_at=now,
                )
            )
            conn.execute(
                planning_transcript.insert().values(
                    id=transcript_id,
                    project_id=project_id,
                    client_turn_id=uuid.uuid4(),
                    turn_index=0,
                    user_message="Legacy planning turn",
                    reply=None,
                    planner_state=None,
                    response=None,
                    suggestions=[],
                    status="pending",
                    created_at=now,
                    completed_at=None,
                )
            )

        command.upgrade(cfg, "head")
        with scratch.connect() as conn:
            inspector = inspect(conn)
            assert {"summary", "summary_status"} <= {
                column["name"] for column in inspector.get_columns("block")
            }
            assert {"summary", "summary_status"} <= {
                column["name"] for column in inspector.get_columns("artefact")
            }
            assert "theme_id" in {column["name"] for column in inspector.get_columns("source_tag")}
            assert "part" in {
                column["name"] for column in inspector.get_columns("planning_transcript")
            }
            assert conn.execute(
                select(block.c.summary, block.c.summary_status).where(block.c.block_id == block_id)
            ).one() == (None, None)
            assert conn.execute(
                select(artefact.c.summary, artefact.c.summary_status).where(
                    artefact.c.artefact_id == artefact_id
                )
            ).one() == (None, None)
            assert (
                conn.execute(
                    select(source_tag.c.theme_id).where(source_tag.c.source_tag_id == tag_id)
                ).scalar_one()
                is None
            )
            assert (
                conn.execute(
                    select(planning_transcript.c.part).where(
                        planning_transcript.c.id == transcript_id
                    )
                ).scalar_one()
                is None
            )

        command.downgrade(cfg, PRE_028_REVISION)
        with scratch.connect() as conn:
            inspector = inspect(conn)
            assert "part" not in {
                column["name"] for column in inspector.get_columns("planning_transcript")
            }
            assert {"summary", "summary_status"}.isdisjoint(
                column["name"] for column in inspector.get_columns("block")
            )
            assert {"summary", "summary_status"}.isdisjoint(
                column["name"] for column in inspector.get_columns("artefact")
            )
            assert "theme_id" not in {
                column["name"] for column in inspector.get_columns("source_tag")
            }
            assert conn.execute(
                select(block.c.content).where(block.c.block_id == block_id)
            ).scalar_one() == ("Legacy block")
            assert conn.execute(
                select(artefact.c.title).where(artefact.c.artefact_id == artefact_id)
            ).scalar_one() == ("Legacy artefact")
            assert conn.execute(
                select(source_tag.c.tag).where(source_tag.c.source_tag_id == tag_id)
            ).scalar_one() == ("Legacy theme")
    finally:
        scratch.dispose()
        with shared.connect().execution_options(isolation_level="AUTOCOMMIT") as admin:
            admin.execute(text(f'DROP DATABASE IF EXISTS "{scratch_name}" WITH (FORCE)'))
