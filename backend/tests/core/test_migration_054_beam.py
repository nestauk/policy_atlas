"""Round trip for task 054 iteration 3 step 3 (``7fbb8bf487f2``): one verdict per link.

Old two-question judgements are mapped once, in the migration (C36): worked
elsewhere supports → weak, challenges → refutes, not_about stays; relevance 3
when holds here supported, else 1. The revision adds and drops columns, so it
runs on a per-test scratch database
(docs/knowledge/column-churn-migrations-need-scratch-db.md); seed rows below
the revision are plain SQL.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest
from alembic import command
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url

from tests.conftest import _alembic_cfg
from tests.helpers import seed_toc_task

PRE_REVISION = "80f4e6c430b0"
_AT = datetime(2026, 10, 1, tzinfo=UTC)


def test_old_judgements_map_to_support_and_relevance_and_back(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    base_url = make_url(os.environ["DATABASE_URL"])
    scratch_url = base_url.set(database=f"{base_url.database}_migr_{uuid.uuid4().hex[:8]}")
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as admin:
        admin.execute(text(f'CREATE DATABASE "{scratch_url.database}"'))
    monkeypatch.setenv("DATABASE_URL", scratch_url.render_as_string(hide_password=False))
    scratch = create_engine(scratch_url)
    try:
        cfg = _alembic_cfg()
        command.upgrade(cfg, PRE_REVISION)
        # (elsewhere, here) → expected (support, relevance, quote)
        cases = {
            ("supports", "supports"): ("weak", 3, "e"),
            ("supports", "not_about"): ("weak", 1, "e"),
            ("challenges", "challenges"): ("refutes", 1, "e"),
            ("not_about", "supports"): ("not_about", 3, None),
        }
        rows = {pair: uuid.uuid4() for pair in cases}
        with scratch.begin() as conn:
            ids = seed_toc_task(conn, judgement=False)
            conn.execute(
                text(
                    "UPDATE toc_link SET elsewhere_sentence = 'Found in Chile.',"
                    " here_sentence = 'Holds in the UK.'"
                )
            )
            for n, ((elsewhere, here), evidence_id) in enumerate(rows.items()):
                conn.execute(
                    text(
                        "INSERT INTO toc_item_evidence (evidence_id, task_id, link_id,"
                        " task_source_snapshot_id, capability_run_id, stance_elsewhere,"
                        " quote_elsewhere, stance_here, quote_here, item_hash, created_at,"
                        " updated_at) VALUES (:id, :task, :link, :tss, :walk, :e, :qe, :h,"
                        " :qh, :hash, :at, :at)"
                    ),
                    {
                        "task": ids["task_id"],
                        "link": ids["link"],
                        "tss": ids["tss"],
                        "walk": ids["walk"],
                        "id": evidence_id,
                        "e": elsewhere,
                        "qe": None if elsewhere == "not_about" else "e",
                        "h": here,
                        "qh": None if here == "not_about" else "h",
                        "hash": f"h{n}",
                        "at": _AT,
                    },
                )

        command.upgrade(cfg, "head")
        with scratch.connect() as conn:
            got = {
                row.evidence_id: (row.support, row.relevance, row.quote)
                for row in conn.execute(
                    text("SELECT evidence_id, support, relevance, quote FROM toc_item_evidence")
                )
            }
            sentence = conn.execute(text("SELECT evidence_sentence FROM toc_link")).scalar_one()
        assert got == {rows[pair]: expected for pair, expected in cases.items()}
        assert sentence == "Found in Chile. Holds in the UK."

        # A row written after the upgrade has no stances; the downgrade maps it back.
        new_row = uuid.uuid4()
        with scratch.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO toc_item_evidence (evidence_id, task_id, link_id,"
                    " task_source_snapshot_id, capability_run_id, support, quote, relevance,"
                    " item_hash, created_at, updated_at) VALUES (:id, :task, :link, :tss,"
                    " :walk, 'strong', 'q', 3, 'new', :at, :at)"
                ),
                {
                    "task": ids["task_id"],
                    "link": ids["link"],
                    "tss": ids["tss"],
                    "walk": ids["walk"],
                    "id": new_row,
                    "at": _AT,
                },
            )
        command.downgrade(cfg, PRE_REVISION)
        with scratch.connect() as conn:
            back = conn.execute(
                text(
                    "SELECT stance_elsewhere, quote_elsewhere, stance_here, quote_here"
                    " FROM toc_item_evidence WHERE evidence_id = :id"
                ),
                {"id": new_row},
            ).one()
        assert tuple(back) == ("supports", "q", "supports", "q")
        command.upgrade(cfg, "head")
    finally:
        scratch.dispose()
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as admin:
            admin.execute(text(f'DROP DATABASE IF EXISTS "{scratch_url.database}" WITH (FORCE)'))
