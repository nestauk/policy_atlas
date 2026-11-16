"""The report says when the reader changed the theory after it was written (task 054, S9 / A17)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.engine import Engine

from policy_atlas.api.routers.toc import toc_graph_out
from policy_atlas.core import events
from policy_atlas.core.schema import runs, toc_item_evidence
from policy_atlas.theory_of_change import edits
from policy_atlas.theory_of_change.backend import StubTocBackend
from policy_atlas.theory_of_change.review import report_stale
from tests.helpers import seed_toc_task
from tests.theory_of_change.test_check_steps import _run
from tests.theory_of_change.test_edits import _last_event

ME = "user-ada"


def _component(conn: Any, task_id: uuid.UUID, walk: uuid.UUID, component: str) -> uuid.UUID:
    """One component run of the walk: its ``run.started`` and ``component.completed``."""
    run_id = uuid.uuid4()
    conn.execute(
        runs.insert().values(
            run_id=run_id,
            task_id=task_id,
            status="succeeded",
            started_at=datetime.now(UTC),
            capability_run_id=walk,
        )
    )
    events.append(
        conn,
        task_id=task_id,
        run_id=run_id,
        event_type="run.started",
        payload={"component": component},
    )
    events.append(
        conn,
        task_id=task_id,
        run_id=run_id,
        event_type="component.completed",
        payload={"component": component, "report": {"title": "A report"}},
    )
    return run_id


@pytest.fixture
def ids(engine: Engine, cleanup: list[uuid.UUID]) -> dict[str, uuid.UUID]:
    """A theory whose check walk (summarise, then the report) has just written a report."""
    with engine.begin() as conn:
        seeded = seed_toc_task(conn)
        _component(conn, seeded["task_id"], seeded["walk"], "toc_summarise")
        _component(conn, seeded["task_id"], seeded["walk"], "toc_report")
    cleanup.append(seeded["task_id"])
    return seeded


def _stale(engine: Engine, ids: dict[str, uuid.UUID]) -> bool:
    with engine.connect() as conn:
        return report_stale(conn, ids["task_id"])


def test_a_report_is_not_stale_right_after_it_is_written(engine: Engine, ids: Any) -> None:
    assert _stale(engine, ids) is False


def test_a_content_edit_makes_the_report_stale(engine: Engine, ids: Any) -> None:
    with engine.begin() as conn:
        edits.edit_box(
            conn,
            task_id=ids["task_id"],
            actor=ME,
            box_id=ids["source"],
            expected_revision=1,
            fields={"text": "Restrict adverts before 9pm"},
        )
    assert _stale(engine, ids) is True


def test_an_undo_makes_the_report_stale(engine: Engine, ids: Any) -> None:
    # The edit is older than the report; only its Undo comes after.
    task_id = ids["task_id"]
    with engine.begin() as conn:
        edits.set_critical(
            conn, task_id=task_id, actor=ME, link_id=ids["link"], expected_revision=1
        )
    edit = _last_event(engine, task_id)
    with engine.begin() as conn:
        # A newer report written after the edit: not stale yet.
        walk2 = _new_walk(conn, task_id)
        _component(conn, task_id, walk2, "toc_report")
    assert _stale(engine, ids) is False
    with engine.begin() as conn:
        edits.undo(conn, task_id=task_id, actor=ME, event_id=edit)
    assert _stale(engine, ids) is True


@pytest.mark.parametrize("action", ["remove", "restore", "accept", "reject"])
def test_an_evidence_decision_makes_the_report_stale(
    engine: Engine, ids: Any, action: str
) -> None:
    task_id = ids["task_id"]
    revision = 1
    if action in ("accept", "reject"):
        # Found by Find more evidence, waiting for the reader (C44).
        with engine.begin() as conn:
            conn.execute(
                toc_item_evidence.update()
                .where(toc_item_evidence.c.evidence_id == ids["evidence"])
                .values(status="pending")
            )
    if action == "restore":
        with engine.begin() as conn:
            edits.edit_evidence(
                conn,
                task_id=task_id,
                actor=ME,
                evidence_id=ids["evidence"],
                expected_revision=1,
                action="remove",
            )
            # A report after the removal: only the restore is newer.
            _component(conn, task_id, _new_walk(conn, task_id), "toc_report")
        revision = 2
        assert _stale(engine, ids) is False
    with engine.begin() as conn:
        edits.edit_evidence(
            conn,
            task_id=task_id,
            actor=ME,
            evidence_id=ids["evidence"],
            expected_revision=revision,
            action=action,
        )
    assert _stale(engine, ids) is True


def test_moving_a_box_leaves_the_report_current(engine: Engine, ids: Any) -> None:
    task_id = ids["task_id"]
    with engine.begin() as conn:
        edits.move_box(
            conn,
            task_id=task_id,
            actor=ME,
            box_id=ids["source"],
            expected_revision=1,
            position={"x": 10, "y": 20},
        )
        edits.reset_layout(conn, task_id=task_id, actor=ME)
    assert _stale(engine, ids) is False
    # Undoing a move moves the box back: still only the layout.
    with engine.begin() as conn:
        edits.undo(conn, task_id=task_id, actor=ME, event_id=_last_event(engine, task_id))
    assert _stale(engine, ids) is False


def test_the_graph_read_carries_stale_on_the_report(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    task_id = _run(engine, cleanup, StubTocBackend())
    with engine.connect() as conn:
        report = toc_graph_out(conn, task_id).report
    assert report is not None and report.stale is False
    with engine.connect() as conn:
        box = toc_graph_out(conn, task_id).boxes[0]
    with engine.begin() as conn:
        edits.edit_box(
            conn,
            task_id=task_id,
            actor=ME,
            box_id=box.box_id,
            expected_revision=box.revision,
            fields={"text": "A new wording"},
        )
    with engine.connect() as conn:
        report = toc_graph_out(conn, task_id).report
    assert report is not None and report.stale is True


def _new_walk(conn: Any, task_id: uuid.UUID) -> uuid.UUID:
    from tests.helpers import seed_walk

    return seed_walk(
        conn,
        task_id,
        capability="theory_of_change",
        purpose="toc",
        context={"toc_walk": "check"},
        plan_payload={},
        plan_version=2,
    ).walk_id
