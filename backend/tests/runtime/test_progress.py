"""DB-backed coverage for independently committed synthesis progress events."""

from __future__ import annotations

import threading
import uuid

from sqlalchemy.engine import Engine

from policy_atlas.api.routers import sse
from policy_atlas.core import events
from policy_atlas.core.schema import artefact, project, runs
from policy_atlas.runtime.progress import ProgressEmitter
from tests.helpers import delete_project_data, now


def _seed_run(engine: Engine) -> tuple[uuid.UUID, uuid.UUID]:
    project_id = uuid.uuid4()
    run_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            project.insert().values(
                project_id=project_id,
                name="Progress test project",
                status="active",
                created_at=now(),
                updated_at=now(),
            )
        )
        conn.execute(
            runs.insert().values(
                run_id=run_id,
                project_id=project_id,
                status="running",
                started_at=now(),
            )
        )
    return project_id, run_id


def _cleanup(engine: Engine, project_id: uuid.UUID | None) -> None:
    if project_id is None:
        return
    with engine.begin() as conn:
        delete_project_data(conn, project_id)


def test_progress_emitter_uses_display_order_and_closes_empty_key_findings(
    engine: Engine,
) -> None:
    project_id: uuid.UUID | None = None
    try:
        project_id, run_id = _seed_run(engine)
        emitter = ProgressEmitter(engine, project_id=project_id, run_id=run_id)
        emitter.emit_skeleton(
            [
                {"title": "Evidence", "focus": "What the evidence says"},
                {"title": "Conclusions", "focus": "What it amounts to"},
            ]
        )
        emitter.section_started(0)
        emitter.section_completed(0, prose="Completed evidence prose.")
        emitter.section_started(1)
        emitter.section_completed(1, prose="Completed conclusion prose.")
        emitter.key_findings_started()
        emitter.key_findings_completed(prose="")

        with engine.connect() as conn:
            rows = sse._event_rows(conn, project_id=project_id, after=0, through=None)
            frames = sse._map_rows(conn, project_id=project_id, rows=rows, through=None)
        assert frames[0]["type"] == "artefact.skeleton"
        assert frames[0]["sections"] == [
            {"index": 0, "title": "Key findings", "focus": "The report's headline claims."},
            {"index": 1, "title": "Evidence", "focus": "What the evidence says"},
            {"index": 2, "title": "Conclusions", "focus": "What it amounts to"},
        ]
        assert [frame["index"] for frame in frames[1:]] == [1, 1, 2, 2, 0, 0]
        assert frames[-1] == {
            "type": "artefact.section_completed",
            "sequence": 7,
            "occurred_at": frames[-1]["occurred_at"],
            "index": 0,
            "title": "Key findings",
            "prose": "",
        }

        # A cursor after the skeleton is a reconnect mid-synthesis: replay
        # carries exactly the events already completed, including their prose.
        with engine.connect() as conn:
            replay_rows = sse._event_rows(conn, project_id=project_id, after=1, through=None)
            replay = sse._map_rows(
                conn, project_id=project_id, rows=replay_rows, through=None
            )
        completed = [frame for frame in replay if frame["type"] == "artefact.section_completed"]
        assert [(frame["index"], frame["prose"]) for frame in completed] == [
            (1, "Completed evidence prose."),
            (2, "Completed conclusion prose."),
            (0, ""),
        ]
    finally:
        _cleanup(engine, project_id)


def test_progress_emitter_does_not_block_on_open_synthesis_like_transaction(
    engine: Engine,
) -> None:
    project_id: uuid.UUID | None = None
    held = None
    try:
        project_id, run_id = _seed_run(engine)
        emitter = ProgressEmitter(engine, project_id=project_id, run_id=run_id)
        emitter.emit_skeleton([{"title": "Evidence", "focus": "What changed"}])

        held = engine.connect()
        transaction = held.begin()
        held.execute(
            artefact.insert().values(
                artefact_id=uuid.uuid4(),
                project_id=project_id,
                title="Uncommitted artefact",
                created_at=now(),
            )
        )
        finished = threading.Event()
        failures: list[BaseException] = []

        def emit_while_component_transaction_is_open() -> None:
            try:
                emitter.section_started(0)
                emitter.section_completed(0, prose="Visible before component commit.")
            except BaseException as exc:  # pragma: no cover - asserted below
                failures.append(exc)
            finally:
                finished.set()

        worker = threading.Thread(target=emit_while_component_transaction_is_open)
        worker.start()
        assert finished.wait(timeout=2), "progress append blocked behind component transaction"
        worker.join()
        assert failures == []
        with engine.connect() as conn:
            progress_events = events.read(conn, project_id)
        assert [event["event_type"] for event in progress_events] == [
            "artefact.skeleton",
            "artefact.section_started",
            "artefact.section_completed",
        ]
        transaction.rollback()
        held.close()
        held = None
    finally:
        if held is not None:
            held.rollback()
            held.close()
        _cleanup(engine, project_id)
