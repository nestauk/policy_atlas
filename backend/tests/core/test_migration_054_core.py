"""Round trip and constraints for task 054 revision 1 (``9127f849697f``).

Contract § Schema and § Acceptance checks 1: upgrade, downgrade, upgrade; the
downgrade refuses while a theory-of-change task exists; and the keys and
checks that make the graph safe across tasks.

The ``engine`` fixture is session-scoped and the test database is shared, so
every test that moves the chain leaves it back at head, and every committed
task is removed (044 verification, Phase 2: a task left behind makes a
downgrade refuse for every later round-trip test).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

import pytest
from alembic import command
from sqlalchemy import delete, inspect, select, text, update
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from policy_atlas.core.schema import toc_box, toc_item_evidence, toc_link
from tests.conftest import _alembic_cfg
from tests.helpers import delete_task_data, now, seed_task_and_run, seed_toc_task

PRE_REVISION = "f1b6d3a8c2e5"

_NEW_TABLES = {
    "toc_box",
    "toc_link",
    "toc_band_item",
    "toc_pathway",
    "toc_pathway_link",
    "toc_item_evidence",
}

_WIDENED = {
    "ck_task_capability": "'theory_of_change'",
    "ck_capr_capability": "'theory_of_change'",
    "ck_scope_purpose": "'toc'",
    "ck_conversation_kind": "'stress_test'",
}


def _definition(conn: Connection, name: str) -> str:
    return str(
        conn.execute(
            text("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = :n"),
            {"n": name},
        ).scalar_one()
    )


def test_the_revision_round_trips(engine: Engine) -> None:
    cfg = _alembic_cfg()
    try:
        command.downgrade(cfg, PRE_REVISION)
        with engine.connect() as conn:
            assert not (_NEW_TABLES & set(inspect(conn).get_table_names()))
            for name, value in _WIDENED.items():
                assert value not in _definition(conn, name)
        command.upgrade(cfg, "head")
        with engine.connect() as conn:
            assert set(inspect(conn).get_table_names()) >= _NEW_TABLES
            for name, value in _WIDENED.items():
                assert value in _definition(conn, name)
    finally:
        command.upgrade(cfg, "head")


def test_the_downgrade_refuses_while_a_theory_of_change_task_exists(engine: Engine) -> None:
    cfg = _alembic_cfg()
    with engine.begin() as conn:
        task_id = seed_toc_task(conn)["task_id"]
    try:
        with pytest.raises(RuntimeError, match="ops_remove_toc_tasks"):
            command.downgrade(cfg, PRE_REVISION)
        # Refused before any DDL.
        with engine.connect() as conn:
            assert set(inspect(conn).get_table_names()) >= _NEW_TABLES
    finally:
        command.upgrade(cfg, "head")
        with engine.begin() as conn:
            delete_task_data(conn, task_id)


# --- constraints, on the rolled-back connection --------------------------------


def _refused(conn: Connection, name: str, write: Callable[[], object]) -> None:
    with pytest.raises(IntegrityError, match=name), conn.begin_nested():
        write()


def test_a_box_layer_outside_the_four_layers_and_failure_is_refused(conn: Connection) -> None:
    ids = seed_toc_task(conn)
    _refused(
        conn,
        "ck_toc_box_layer",
        lambda: conn.execute(
            update(toc_box).where(toc_box.c.box_id == ids["source"]).values(layer="activity")
        ),
    )


def test_kept_by_takes_only_user_check_or_choose(conn: Connection) -> None:
    ids = seed_toc_task(conn)
    _refused(
        conn,
        "ck_toc_link_kept_by",
        lambda: conn.execute(
            update(toc_link).where(toc_link.c.link_id == ids["link"]).values(kept_by="robot")
        ),
    )


def test_a_task_has_at_most_one_critical_connection(conn: Connection) -> None:
    ids = seed_toc_task(conn)
    conn.execute(
        update(toc_link).where(toc_link.c.link_id == ids["link"]).values(critical=True)
    )
    second = conn.execute(
        select(toc_link).where(toc_link.c.link_id == ids["link"])
    ).mappings().one()
    _refused(
        conn,
        "uq_toc_link_one_critical",
        lambda: conn.execute(
            toc_link.insert().values(
                {
                    **second,
                    "link_id": uuid.uuid4(),
                    "source_box_id": ids["target"],
                    "target_box_id": ids["case_box"],
                }
            )
        ),
    )


def _judgement(ids: dict[str, uuid.UUID], **values: object) -> dict[str, object]:
    return {
        "evidence_id": uuid.uuid4(),
        "task_id": ids["task_id"],
        "link_id": ids["link"],
        "task_source_snapshot_id": ids["tss"],
        "capability_run_id": ids["walk"],
        "stance_elsewhere": "not_about",
        "stance_here": "not_about",
        "support": "not_about",
        "relevance": 0,
        "item_hash": "h2",
        "created_at": now(),
        "updated_at": now(),
        **values,
    }


def test_a_stance_outside_the_three_is_refused(conn: Connection) -> None:
    ids = seed_toc_task(conn)
    _refused(
        conn,
        "ck_toc_evidence_stances",
        lambda: conn.execute(
            toc_item_evidence.insert().values(_judgement(ids, stance_here="maybe", quote_here="q"))
        ),
    )


def test_a_stance_that_speaks_needs_its_quote(conn: Connection) -> None:
    ids = seed_toc_task(conn)
    _refused(
        conn,
        "ck_toc_evidence_quotes",
        lambda: conn.execute(
            toc_item_evidence.insert().values(_judgement(ids, stance_here="challenges"))
        ),
    )


def test_a_link_cannot_name_another_task_s_box(conn: Connection) -> None:
    ids = seed_toc_task(conn)
    other_task, _run = seed_task_and_run(conn)
    _refused(
        conn,
        "fk_toc_link_source",
        lambda: conn.execute(
            toc_link.insert().values(
                link_id=uuid.uuid4(),
                task_id=other_task,
                source_box_id=ids["source"],
                target_box_id=ids["target"],
                if_text="if",
                for_text="for",
                then_text="then",
                because_text="because",
                origin="user",
                created_at=now(),
                updated_at=now(),
            )
        ),
    )


def test_deleting_a_case_study_box_keeps_the_judgement(conn: Connection) -> None:
    """``SET NULL (case_box_id)`` nulls the box only, never ``task_id``."""
    ids = seed_toc_task(conn)
    conn.execute(delete(toc_box).where(toc_box.c.box_id == ids["case_box"]))
    row = conn.execute(
        select(toc_item_evidence.c.case_box_id, toc_item_evidence.c.task_id).where(
            toc_item_evidence.c.evidence_id == ids["evidence"]
        )
    ).one()
    assert (row.case_box_id, row.task_id) == (None, ids["task_id"])
