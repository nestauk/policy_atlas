"""DB-backed coverage for independently committed synthesis progress events."""

from __future__ import annotations

import threading
import uuid

from sqlalchemy.engine import Engine

from policy_atlas.api.routers import sse
from policy_atlas.core import events
from policy_atlas.core.schema import artefact, runs, task
from policy_atlas.runtime.progress import ProgressEmitter
from tests.helpers import delete_task_data, now


def _seed_run(engine: Engine) -> tuple[uuid.UUID, uuid.UUID]:
    task_id = uuid.uuid4()
    run_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            task.insert().values(
                task_id=task_id,
                name="Progress test task",
                status="active",
                created_at=now(),
                updated_at=now(),
            )
        )
        conn.execute(
            runs.insert().values(
                run_id=run_id,
                task_id=task_id,
                status="running",
                started_at=now(),
            )
        )
    return task_id, run_id


def _cleanup(engine: Engine, task_id: uuid.UUID | None) -> None:
    if task_id is None:
        return
    with engine.begin() as conn:
        delete_task_data(conn, task_id)


def test_progress_emitter_uses_display_order_and_closes_empty_key_findings(
    engine: Engine,
) -> None:
    task_id: uuid.UUID | None = None
    try:
        task_id, run_id = _seed_run(engine)
        emitter = ProgressEmitter(engine, task_id=task_id, run_id=run_id)
        emitter.emit_skeleton(
            [
                {"title": "Evidence", "focus": "What the evidence says"},
                {"title": "Conclusions", "focus": "What it amounts to"},
            ]
        )
        # The page numbers sections with the key findings first, so the
        # writer's first section is the page's section 1 (task 058; the
        # streamed text is addressed with this index).
        assert emitter.display_index(0) == 1
        assert emitter.display_index(1) == 2
        emitter.section_started(0)
        emitter.section_completed(0, prose="Completed evidence prose.")
        emitter.section_started(1)
        emitter.section_completed(1, prose="Completed conclusion prose.")
        emitter.key_findings_started()
        emitter.key_findings_completed(prose="")

        with engine.connect() as conn:
            rows = sse._event_rows(conn, task_id=task_id, after=0, through=None)
            frames = sse._map_rows(conn, task_id=task_id, rows=rows, through=None)
        assert frames[0]["type"] == "artefact.skeleton"
        assert frames[0]["sections"] == [
            {
                "index": 0,
                "title": "Key findings",
                "focus": "The report's headline claims.",
                "role": "key_findings",
            },
            {"index": 1, "title": "Evidence", "focus": "What the evidence says", "role": "body"},
            {"index": 2, "title": "Conclusions", "focus": "What it amounts to", "role": "body"},
        ]
        assert [frame["index"] for frame in frames[1:]] == [1, 1, 2, 2, 0, 0]
        assert frames[-1] == {
            "type": "artefact.section_completed",
            "sequence": 7,
            "occurred_at": frames[-1]["occurred_at"],
            "index": 0,
            "title": "Key findings",
            "prose": "",
            "citations": [],
            "claims": [],
        }

        # A cursor after the skeleton is a reconnect mid-synthesis: replay
        # carries exactly the events already completed, including their prose.
        with engine.connect() as conn:
            replay_rows = sse._event_rows(conn, task_id=task_id, after=1, through=None)
            replay = sse._map_rows(
                conn, task_id=task_id, rows=replay_rows, through=None
            )
        completed = [frame for frame in replay if frame["type"] == "artefact.section_completed"]
        assert [(frame["index"], frame["prose"]) for frame in completed] == [
            (1, "Completed evidence prose."),
            (2, "Completed conclusion prose."),
            (0, ""),
        ]
    finally:
        _cleanup(engine, task_id)


def test_progress_emitter_does_not_block_on_open_synthesis_like_transaction(
    engine: Engine,
) -> None:
    task_id: uuid.UUID | None = None
    held = None
    try:
        task_id, run_id = _seed_run(engine)
        emitter = ProgressEmitter(engine, task_id=task_id, run_id=run_id)
        emitter.emit_skeleton([{"title": "Evidence", "focus": "What changed"}])

        held = engine.connect()
        transaction = held.begin()
        held.execute(
            artefact.insert().values(
                artefact_id=uuid.uuid4(),
                task_id=task_id,
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
            progress_events = events.read(conn, task_id)
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
        _cleanup(engine, task_id)


def test_progress_emitter_case_studies_slot_and_citations_survive_replay(
    engine: Engine,
) -> None:
    """Task 058, round 7: the case studies get the last slot, and every
    completed section carries its citations through the replay path."""
    task_id: uuid.UUID | None = None
    try:
        task_id, run_id = _seed_run(engine)
        emitter = ProgressEmitter(engine, task_id=task_id, run_id=run_id)
        emitter.emit_skeleton(
            [{"title": "Evidence", "focus": "What the evidence says"}],
            key_findings=True,
            case_studies=True,
        )
        assert emitter.key_findings_display_index() == 0
        assert emitter.display_index(0) == 1
        assert emitter.case_studies_display_index() == 2
        source_id = str(uuid.uuid4())
        body_citation = {
            "start": 0,
            "end": 8,
            "n": 1,
            "source_id": source_id,
            "title": "Breakfast clubs",
            # Round 8: the saved ids and the quote ride along.
            "citation_id": str(uuid.uuid4()),
            "claim_id": str(uuid.uuid4()),
            "quote": "Breakfast participation rose.",
        }
        # Recorded in the round-7 shape (no ids, no quote).
        card_citation = {"start": 20, "end": 31, "n": 2, "source_id": None,
                         "title": "Unknown source"}
        emitter.section_started(0)
        emitter.section_completed(0, prose="Evidence prose.", citations=[body_citation])
        emitter.key_findings_started()
        emitter.key_findings_completed(prose="Headline.", citations=[])
        emitter.case_studies_started()
        emitter.case_studies_completed(
            prose="**Leeds**\nBreakfast in every primary.", citations=[card_citation]
        )

        with engine.connect() as conn:
            rows = sse._event_rows(conn, task_id=task_id, after=0, through=None)
            frames = sse._map_rows(conn, task_id=task_id, rows=rows, through=None)
        assert frames[0]["sections"] == [
            {
                "index": 0,
                "title": "Key findings",
                "focus": "The report's headline claims.",
                "role": "key_findings",
            },
            {"index": 1, "title": "Evidence", "focus": "What the evidence says", "role": "body"},
            {
                "index": 2,
                "title": "Case studies",
                "focus": "Relevant examples from the cited evidence.",
                "role": "case_studies",
            },
        ]
        assert [(frame["type"], frame["index"]) for frame in frames[1:]] == [
            ("artefact.section_started", 1),
            ("artefact.section_completed", 1),
            ("artefact.section_started", 0),
            ("artefact.section_completed", 0),
            ("artefact.section_started", 2),
            ("artefact.section_completed", 2),
        ]

        # A reconnect after the skeleton replays the citations as recorded.
        with engine.connect() as conn:
            replay_rows = sse._event_rows(conn, task_id=task_id, after=1, through=None)
            replay = sse._map_rows(conn, task_id=task_id, rows=replay_rows, through=None)
        completed = {
            frame["index"]: frame
            for frame in replay
            if frame["type"] == "artefact.section_completed"
        }
        assert completed[1]["citations"] == [body_citation]
        assert completed[0]["citations"] == []
        assert completed[2]["title"] == "Case studies"
        # A citation recorded without the round-8 fields replays with them empty.
        assert completed[2]["citations"] == [
            {**card_citation, "citation_id": None, "claim_id": None, "quote": ""}
        ]
    finally:
        _cleanup(engine, task_id)


def test_progress_emitter_intro_slot_follows_the_case_studies_and_replays(
    engine: Engine,
) -> None:
    """Task 058, round 8: the introduction has its own slot after the case
    studies (no other index moves), starts, and completes with its prose and
    no citations; an empty completion closes it."""
    task_id: uuid.UUID | None = None
    try:
        task_id, run_id = _seed_run(engine)
        emitter = ProgressEmitter(engine, task_id=task_id, run_id=run_id)
        emitter.emit_skeleton(
            [{"title": "Evidence", "focus": "What the evidence says"}],
            key_findings=True,
            case_studies=True,
            intro=True,
        )
        assert emitter.display_index(0) == 1
        assert emitter.case_studies_display_index() == 2
        assert emitter.intro_display_index() == 3
        emitter.intro_started()
        emitter.intro_completed(prose="The report first weighs the evidence.")

        with engine.connect() as conn:
            rows = sse._event_rows(conn, task_id=task_id, after=0, through=None)
            frames = sse._map_rows(conn, task_id=task_id, rows=rows, through=None)
        assert frames[0]["sections"][-1] == {
            "index": 3,
            "title": "Full report",
            "focus": "",
            "role": "intro",
        }
        assert [(frame["type"], frame["index"]) for frame in frames[1:]] == [
            ("artefact.section_started", 3),
            ("artefact.section_completed", 3),
        ]
        assert frames[2]["prose"] == "The report first weighs the evidence."
        assert frames[2]["title"] == "Full report"
        assert frames[2]["citations"] == []

        # Without the slot nothing is addressable and nothing is recorded.
        bare = ProgressEmitter(engine, task_id=task_id, run_id=run_id)
        bare.emit_skeleton([{"title": "Evidence", "focus": "x"}], key_findings=False)
        assert bare.intro_display_index() is None
    finally:
        _cleanup(engine, task_id)


def test_completed_frame_recorded_before_citations_replays_with_none(
    engine: Engine,
) -> None:
    """A section_completed recorded before round 7 (no ``citations``) still replays."""
    task_id: uuid.UUID | None = None
    try:
        task_id, run_id = _seed_run(engine)
        with engine.begin() as conn:
            events.append(
                conn,
                task_id=task_id,
                run_id=run_id,
                event_type="artefact.section_completed",
                payload={"index": 0, "title": "Evidence", "prose": "Old prose."},
            )
        with engine.connect() as conn:
            rows = sse._event_rows(conn, task_id=task_id, after=0, through=None)
            frames = sse._map_rows(conn, task_id=task_id, rows=rows, through=None)
        assert frames[0]["prose"] == "Old prose."
        assert frames[0]["citations"] == []
    finally:
        _cleanup(engine, task_id)


def test_progress_emitter_failure_degrades_without_raising(engine: Engine) -> None:
    """ADR 0027 decision 5: a presentation append can never fail the walk."""
    task_id: uuid.UUID | None = None
    try:
        task_id, run_id = _seed_run(engine)
        emitter = ProgressEmitter(engine, task_id=task_id, run_id=run_id)
        emitter.emit_skeleton([{"title": "Evidence", "focus": "What the evidence says"}])

        # Skeleton drift (an index the skeleton never had) degrades quietly.
        emitter.section_started(99)
        # Once degraded, every further emission is a silent no-op.
        emitter.section_completed(0, prose="never recorded")
        emitter.key_findings_completed(prose="never recorded")

        with engine.begin() as conn:
            recorded = [entry["event_type"] for entry in events.read(conn, task_id)]
        assert recorded == ["artefact.skeleton"]

        # A DB failure on append (FK-less run id) also degrades instead of raising.
        fresh = ProgressEmitter(engine, task_id=task_id, run_id=uuid.uuid4())
        fresh.emit_skeleton([{"title": "Evidence", "focus": "What the evidence says"}])
        with engine.begin() as conn:
            assert [entry["event_type"] for entry in events.read(conn, task_id)] == [
                "artefact.skeleton"
            ]
    finally:
        _cleanup(engine, task_id)
