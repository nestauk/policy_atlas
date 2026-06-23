"""Harness — run-record lifecycle and event-log completeness."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas import events
from policy_atlas.harness import run_harness
from policy_atlas.inference import StubEchoProvider
from policy_atlas.plan import Plan, compile
from policy_atlas.schema import project, runs
from tests.helpers import now, seed_project_and_run


class _FabricatedProvider:
    def complete(self, prompt: str) -> str:  # noqa: ARG002
        return "fabricated text not in source"


def test_run_lifecycle_succeeded(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    config = compile(Plan(component="echo", source_ref="syn-001"))

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
    config = compile(Plan(component="echo", source_ref="syn-001"))

    events.append(conn, project_id=pid, run_id=rid, event_type="run.started", payload={})
    events.append(conn, project_id=pid, run_id=rid, event_type="plan.compiled", payload={})

    run_harness(conn, config=config, project_id=pid, run_id=rid, provider=_FabricatedProvider())

    row = conn.execute(select(runs).where(runs.c.run_id == rid)).one()
    assert row.status == "failed"
    assert row.ended_at is not None

    log = events.read(conn, pid)
    assert log[-1]["event_type"] == "run.failed"


def test_run_project_mismatch_raises_before_write(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    other_pid = uuid.uuid4()
    conn.execute(project.insert().values(project_id=other_pid, created_at=now()))
    config = compile(Plan(component="echo", source_ref="syn-001"))

    with pytest.raises(ValueError, match="belongs to project"):
        run_harness(
            conn, config=config, project_id=other_pid, run_id=rid, provider=StubEchoProvider()
        )


def test_failed_grounding_emits_component_failed_with_block_id(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    config = compile(Plan(component="echo", source_ref="syn-001"))

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
    config = compile(Plan(component="echo", source_ref="syn-001"))

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
