"""Round trip for task 054 iteration 3 step 2 (``80f4e6c430b0``): six layers and codes.

The revision adds and drops columns, so it runs on a per-test scratch database
(docs/knowledge/column-churn-migrations-need-scratch-db.md). Below the revision
``toc_box`` has no ``code`` column, so the seed rows are written as plain SQL.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url

from policy_atlas.core.schema import task
from tests.conftest import _alembic_cfg

PRE_REVISION = "9127f849697f"
_T0 = datetime(2026, 10, 1, tzinfo=UTC)


def test_outcomes_split_and_rows_get_codes_in_creation_order(
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
        task_id = uuid.uuid4()
        # Listed out of creation order: o1 is older than o2.
        boxes = [
            ("in", "input", 0),
            ("o2", "outcome", 2),
            ("o1", "outcome", 1),
            ("im", "impact", 3),
        ]
        box_ids = {key: uuid.uuid4() for key, _, _ in boxes}
        link_ids = [uuid.uuid4(), uuid.uuid4()]
        with scratch.begin() as conn:
            conn.execute(
                task.insert().values(
                    task_id=task_id,
                    name="Migration theory",
                    status="active",
                    capability="theory_of_change",
                    created_at=_T0,
                    updated_at=_T0,
                )
            )
            for key, layer, minute in boxes:
                conn.execute(
                    text(
                        "INSERT INTO toc_box (box_id, task_id, layer, text, result_criteria,"
                        " origin, created_at, updated_at) VALUES (:id, :t, :layer, :layer,"
                        " '{}'::jsonb, 'drafted', :at, :at)"
                    ),
                    {"id": box_ids[key], "t": task_id, "layer": layer,
                     "at": _T0 + timedelta(minutes=minute)},
                )
            for minute, (link_id, (source, target)) in enumerate(
                zip(link_ids, [("o1", "o2"), ("in", "o1")], strict=True)
            ):
                conn.execute(
                    text(
                        "INSERT INTO toc_link (link_id, task_id, source_box_id, target_box_id,"
                        " if_text, for_text, then_text, because_text, origin, created_at,"
                        " updated_at) VALUES (:id, :t, :s, :g, 'i', 'f', 't', 'b', 'drafted',"
                        " :at, :at)"
                    ),
                    {"id": link_id, "t": task_id, "s": box_ids[source], "g": box_ids[target],
                     "at": _T0 + timedelta(minutes=minute)},
                )

        command.upgrade(cfg, "head")
        with scratch.connect() as conn:
            got = {
                row.box_id: (row.layer, row.code)
                for row in conn.execute(text("SELECT box_id, layer, code FROM toc_box"))
            }
            codes = dict(conn.execute(text("SELECT link_id, code FROM toc_link")).tuples().all())
        assert got == {
            box_ids["in"]: ("input", "A1"),
            box_ids["o1"]: ("outcome_short", "S1"),
            box_ids["o2"]: ("outcome_short", "S2"),
            box_ids["im"]: ("impact", "I1"),
        }
        assert codes == {link_ids[0]: "#1", link_ids[1]: "#2"}
        with scratch.begin() as conn:
            conn.execute(
                text("UPDATE toc_box SET layer = 'outcome_long' WHERE box_id = :id"),
                {"id": box_ids["o2"]},
            )

        command.downgrade(cfg, PRE_REVISION)
        with scratch.connect() as conn:
            assert "code" not in {c["name"] for c in inspect(conn).get_columns("toc_box")}
            layers = set(conn.execute(text("SELECT layer FROM toc_box")).scalars())
        assert layers == {"input", "outcome", "impact"}
        command.upgrade(cfg, "head")
    finally:
        scratch.dispose()
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as admin:
            admin.execute(text(f'DROP DATABASE IF EXISTS "{scratch_url.database}" WITH (FORCE)'))
