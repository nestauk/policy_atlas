"""Round trip for the announcements revision: tokens for existing people, clean downgrade."""

from __future__ import annotations

import uuid

from alembic import command
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from tests.conftest import _alembic_cfg

PRE_REVISION = "a3c9e1f7b2d4"
REVISION = "6727acd9234c"
_TABLES = {"announcement", "announcement_recipient"}
_COLUMNS = {"updates_unsubscribed_at", "unsubscribe_token"}


def _app_user_columns(engine: Engine) -> set[str]:
    with engine.connect() as conn:
        return {column["name"] for column in inspect(conn).get_columns("app_user")}


def _tables(engine: Engine) -> set[str]:
    with engine.connect() as conn:
        return set(inspect(conn).get_table_names())


def test_upgrade_gives_each_existing_person_a_distinct_token(engine: Engine) -> None:
    cfg = _alembic_cfg()
    ids = [f"announce-migration-{uuid.uuid4()}" for _ in range(5)]
    try:
        command.downgrade(cfg, PRE_REVISION)
        assert not _COLUMNS & _app_user_columns(engine)
        assert not _TABLES & _tables(engine)
        with engine.begin() as conn:
            for user_id in ids:
                conn.execute(
                    text(
                        "INSERT INTO app_user (user_id, display_name, created_at) "
                        "VALUES (:user_id, 'Existing person', now())"
                    ),
                    {"user_id": user_id},
                )

        command.upgrade(cfg, REVISION)
        with engine.connect() as conn:
            tokens = conn.execute(
                text("SELECT unsubscribe_token FROM app_user WHERE user_id = ANY(:ids)"),
                {"ids": ids},
            ).scalars().all()
        assert len(tokens) == len(ids)
        assert None not in tokens
        assert len(set(tokens)) == len(ids)
        assert _tables(engine) >= _TABLES

        command.downgrade(cfg, PRE_REVISION)
        assert not _COLUMNS & _app_user_columns(engine)
        assert not _TABLES & _tables(engine)
    finally:
        command.upgrade(cfg, "head")
