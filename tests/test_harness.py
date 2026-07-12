"""Harness — run-record lifecycle and event-log completeness."""

import uuid
from typing import Any

import pytest
import structlog
from sqlalchemy import func, select
from sqlalchemy.engine import Connection, Engine

from policy_atlas import events
from policy_atlas.fixtures import get_source
from policy_atlas.grounding_judge import StubGroundingJudgeBackend
from policy_atlas.harness import run_harness
from policy_atlas.inference import StubEchoProvider
from policy_atlas.ingest import ingest_upload
from policy_atlas.plan import Plan, compile
from policy_atlas.schema import annotation, artefact, block, project, runs
from policy_atlas.synthesis_backend import StubSynthesisBackend
from tests.helpers import (
    delete_project_data,
    now,
    seed_characterisation,
    seed_project_and_run,
    seed_run,
    seed_scope,
)

_CHUNKS = list(get_source("syn-001").chunks)


class _FabricatedProvider:
    def complete(self, prompt: str) -> str:  # noqa: ARG002
        return "fabricated text not in source"


def _seed_snapshot(conn: Connection, project_id: uuid.UUID) -> uuid.UUID:
    return ingest_upload(
        conn,
        project_id=project_id,
        chunks=_CHUNKS,
        source_locator="syn-001",
        metadata={"synthetic": True},
        text_basis="full_text",
    )


def test_run_lifecycle_succeeded(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    snapshot_id = _seed_snapshot(conn, pid)
    config = compile(Plan(component="echo", source_snapshot_id=snapshot_id))

    # Emit run.started + plan.compiled (skeleton does this; simulate here)
    events.append(conn, project_id=pid, run_id=rid, event_type="run.started", payload={})
    events.append(conn, project_id=pid, run_id=rid, event_type="plan.compiled", payload={})

    run_harness(conn, config=config, project_id=pid, run_id=rid, provider=StubEchoProvider())

    # Run record reached succeeded
    row = conn.execute(select(runs).where(runs.c.run_id == rid)).one()
    assert row.status == "succeeded"
    assert row.ended_at is not None


def test_run_lifecycle_failed_on_grounding_error(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    snapshot_id = _seed_snapshot(conn, pid)
    config = compile(Plan(component="echo", source_snapshot_id=snapshot_id))

    events.append(conn, project_id=pid, run_id=rid, event_type="run.started", payload={})
    events.append(conn, project_id=pid, run_id=rid, event_type="plan.compiled", payload={})

    run_harness(conn, config=config, project_id=pid, run_id=rid, provider=_FabricatedProvider())

    row = conn.execute(select(runs).where(runs.c.run_id == rid)).one()
    assert row.status == "failed"
    assert row.ended_at is not None

    log = events.read(conn, pid)
    assert log[-1]["event_type"] == "run.failed"


def test_run_harness_binds_project_run_component_contextvars(conn: Connection) -> None:
    """run_harness binds project_id/run_id/component once via
    structlog.contextvars.bound_contextvars around the component body, so
    log calls made deep inside a component execution (here, the provider
    invoked by the echo component's grounding leg) inherit them without any
    kwarg being hand-threaded down to that call site.
    """
    pid, rid = seed_project_and_run(conn)
    snapshot_id = _seed_snapshot(conn, pid)
    config = compile(Plan(component="echo", source_snapshot_id=snapshot_id))

    events.append(conn, project_id=pid, run_id=rid, event_type="run.started", payload={})
    events.append(conn, project_id=pid, run_id=rid, event_type="plan.compiled", payload={})

    seen_contextvars: dict[str, Any] = {}

    class _ContextSpyingProvider:
        def complete(self, prompt: str) -> str:  # noqa: ARG002
            seen_contextvars.update(structlog.contextvars.get_contextvars())
            return "fabricated text not in source"

    # Outside the harness call, no ambient project_id/run_id/component context.
    assert structlog.contextvars.get_contextvars() == {}

    run_harness(
        conn, config=config, project_id=pid, run_id=rid, provider=_ContextSpyingProvider()
    )

    assert seen_contextvars == {
        "project_id": str(pid),
        "run_id": str(rid),
        "component": "echo",
    }
    # bound_contextvars unwinds after the call — no leakage across executions.
    assert structlog.contextvars.get_contextvars() == {}


def test_configure_logging_json_chain_renders_exc_info(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """configure_logging's JSON processor chain must render exc_info (dict_tracebacks
    before JSONRenderer), so log.error(..., exc_info=True) inside an except block
    surfaces the traceback instead of silently dropping it.
    """
    import json

    from policy_atlas.logging import configure_logging

    monkeypatch.setenv("LOG_FORMAT", "json")
    try:
        configure_logging()
        log = structlog.get_logger()
        try:
            raise ValueError("boom")
        except ValueError:
            log.error("something.failed", exc_info=True)

        out = capsys.readouterr().out.strip().splitlines()
        assert len(out) == 1
        record = json.loads(out[0])
        assert record["event"] == "something.failed"
        assert record["exception"][0]["exc_type"] == "ValueError"
        assert record["exception"][0]["exc_value"] == "boom"
    finally:
        structlog.reset_defaults()


def test_run_project_mismatch_raises_before_write(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    snapshot_id = _seed_snapshot(conn, pid)
    other_pid = uuid.uuid4()
    conn.execute(project.insert().values(project_id=other_pid, created_at=now()))
    config = compile(Plan(component="echo", source_snapshot_id=snapshot_id))

    with pytest.raises(ValueError, match="belongs to project"):
        run_harness(
            conn, config=config, project_id=other_pid, run_id=rid, provider=StubEchoProvider()
        )


def test_failed_grounding_emits_component_failed_with_block_id(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    snapshot_id = _seed_snapshot(conn, pid)
    config = compile(Plan(component="echo", source_snapshot_id=snapshot_id))

    events.append(conn, project_id=pid, run_id=rid, event_type="run.started", payload={})
    events.append(conn, project_id=pid, run_id=rid, event_type="plan.compiled", payload={})

    run_harness(conn, config=config, project_id=pid, run_id=rid, provider=_FabricatedProvider())

    event_log = events.read(conn, pid)
    types = [e["event_type"] for e in event_log]
    assert "component.failed" in types
    cf = next(e for e in event_log if e["event_type"] == "component.failed")
    assert "block_id" in cf["payload"], (
        "persisted block_id must appear in component.failed audit event"
    )


def test_event_log_six_types_in_order(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    snapshot_id = _seed_snapshot(conn, pid)
    config = compile(Plan(component="echo", source_snapshot_id=snapshot_id))

    events.append(conn, project_id=pid, run_id=rid, event_type="run.started", payload={})
    events.append(conn, project_id=pid, run_id=rid, event_type="plan.compiled", payload={})
    run_harness(conn, config=config, project_id=pid, run_id=rid, provider=StubEchoProvider())

    log = events.read(conn, pid)
    types = [e["event_type"] for e in log]
    assert types == [
        "run.started",
        "plan.compiled",
        "component.started",
        "component.completed",
        "block.written",
        "run.completed",
    ]
    # Sequences are contiguous and ordered
    seqs = [e["sequence"] for e in log]
    assert seqs == list(range(1, len(seqs) + 1))


def test_synthesise_completes_with_characterisation_substrate(conn: Connection) -> None:
    """A characterisation-only reference is a groundable substrate — synthesise
    should complete, mirroring the select-over-characterisation seeding
    precedent (tests.helpers.seed_characterisation).
    """
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    characterisation_run_id = seed_run(conn, pid)
    seed_characterisation(
        conn,
        pid,
        scope_id,
        characterisation_run_id,
        themes={"theme-a": []},
    )
    config = compile(
        Plan(
            component="synthesise",
            evidence_scope_id=scope_id,
            characterisation_run_id=characterisation_run_id,
        )
    )

    events.append(conn, project_id=pid, run_id=rid, event_type="run.started", payload={})
    events.append(conn, project_id=pid, run_id=rid, event_type="plan.compiled", payload={})

    run_harness(
        conn,
        config=config,
        project_id=pid,
        run_id=rid,
        provider=StubEchoProvider(),
        synthesis_backend=StubSynthesisBackend(),
        grounding_judge_backend=StubGroundingJudgeBackend(),
    )

    row = conn.execute(select(runs).where(runs.c.run_id == rid)).one()
    assert row.status == "succeeded"

    log = events.read(conn, pid)
    completed = next(
        e for e in log
        if e["event_type"] == "component.completed"
        and e["payload"].get("component") == "synthesise"
    )
    assert completed["payload"]["artefact_id"] is not None


def test_synthesise_harness_same_run_reexecution_is_loud(conn: Connection) -> None:
    """Running the synthesise component twice for the SAME run_id through the
    real harness node (``run_harness`` -> ``_run_synthesise``) must not raise
    out of the harness: the second attempt fails loudly but gracefully — a
    ``component.failed`` event lands, the run ends 'failed', and no second
    artefact is written.
    """
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    characterisation_run_id = seed_run(conn, pid)
    seed_characterisation(
        conn,
        pid,
        scope_id,
        characterisation_run_id,
        themes={"theme-a": []},
    )
    config = compile(
        Plan(
            component="synthesise",
            evidence_scope_id=scope_id,
            characterisation_run_id=characterisation_run_id,
        )
    )

    events.append(conn, project_id=pid, run_id=rid, event_type="run.started", payload={})
    events.append(conn, project_id=pid, run_id=rid, event_type="plan.compiled", payload={})

    run_harness(
        conn,
        config=config,
        project_id=pid,
        run_id=rid,
        provider=StubEchoProvider(),
        synthesis_backend=StubSynthesisBackend(),
        grounding_judge_backend=StubGroundingJudgeBackend(),
    )

    row = conn.execute(select(runs).where(runs.c.run_id == rid)).one()
    assert row.status == "succeeded"
    artefacts_before = conn.execute(
        select(func.count()).select_from(artefact).where(artefact.c.project_id == pid)
    ).scalar_one()

    # Second attempt, same run_id, same harness path — must not raise.
    run_harness(
        conn,
        config=config,
        project_id=pid,
        run_id=rid,
        provider=StubEchoProvider(),
        synthesis_backend=StubSynthesisBackend(),
        grounding_judge_backend=StubGroundingJudgeBackend(),
    )

    row_after = conn.execute(select(runs).where(runs.c.run_id == rid)).one()
    assert row_after.status == "failed"

    log = events.read(conn, pid)
    failed_events = [
        e
        for e in log
        if e["event_type"] == "component.failed"
        and e["payload"].get("component") == "synthesise"
    ]
    assert len(failed_events) == 1
    assert "same_run_reexecution" in failed_events[0]["payload"]["error"]

    artefacts_after = conn.execute(
        select(func.count()).select_from(artefact).where(artefact.c.project_id == pid)
    ).scalar_one()
    assert artefacts_after == artefacts_before


def test_fail_annotation_survives_commit(engine: Engine) -> None:
    """Flag-don't-drop must hold across a real COMMIT, not only inside a rolled-back txn.

    Every other failure-path test reads back on the same connection the conftest fixture
    rolls back, so none of them prove the fail annotation *persists*. A future refactor that
    re-raised GroundingError past skeleton's `engine.begin()` would roll the annotation back,
    and the whole suite would still pass. This test commits, reopens a fresh connection, and
    asserts the failure evidence is durably there.
    """
    pid = uuid.uuid4()
    rid = uuid.uuid4()
    try:
        with engine.begin() as conn:
            conn.execute(project.insert().values(project_id=pid, created_at=now()))
            conn.execute(runs.insert().values(
                run_id=rid, project_id=pid, status="running", started_at=now()
            ))
            snapshot_id = _seed_snapshot(conn, pid)
            config = compile(Plan(component="echo", source_snapshot_id=snapshot_id))
            events.append(conn, project_id=pid, run_id=rid, event_type="run.started", payload={})
            events.append(conn, project_id=pid, run_id=rid, event_type="plan.compiled", payload={})
            run_harness(
                conn, config=config, project_id=pid, run_id=rid, provider=_FabricatedProvider()
            )
        # transaction has committed on block exit (harness swallows GroundingError → no rollback)

        with engine.connect() as conn:
            run_row = conn.execute(select(runs).where(runs.c.run_id == rid)).one()
            assert run_row.status == "failed"

            ann = conn.execute(
                select(annotation).where(
                    annotation.c.block_id.in_(
                        select(block.c.block_id).where(
                            block.c.artefact_id.in_(
                                select(artefact.c.artefact_id).where(
                                    artefact.c.project_id == pid
                                )
                            )
                        )
                    )
                )
            ).one()
            assert ann.payload["verification_result"] == "fail"

            assert events.read(conn, pid)[-1]["event_type"] == "run.failed"
    finally:
        with engine.begin() as conn:
            delete_project_data(conn, pid)
