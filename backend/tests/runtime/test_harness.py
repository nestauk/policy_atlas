"""Harness — run-record lifecycle and event-log completeness."""

import uuid
from typing import Any

import pytest
import structlog
from sqlalchemy import func, select
from sqlalchemy.engine import Connection, Engine

from policy_atlas.core import events
from policy_atlas.core.inference import StubEchoProvider
from policy_atlas.core.schema import artefact, project, runs
from policy_atlas.evidence_base.corpus.theme_grouping import StubThemeGroupingBackend
from policy_atlas.evidence_base.synthesis.grounding_judge import StubGroundingJudgeBackend
from policy_atlas.evidence_base.synthesis.synthesis_backend import StubSynthesisBackend
from policy_atlas.runtime import harness
from policy_atlas.runtime.harness import run_harness
from policy_atlas.runtime.run_spec import Plan, compile
from tests.evidence_base.corpus.test_characterise import _RaisingDiscoverBackend, _seed_doc
from tests.helpers import (
    delete_project_data,
    now,
    seed_characterisation,
    seed_project_and_run,
    seed_run,
    seed_scope,
)

# NOTE: these tests exercise generic harness dispatch/lifecycle machinery.
# echo (the walking-skeleton component) was retired in task 023 C3 — its
# grounding-chain-specific behaviour (block.written, quote-verification
# annotations) has no surviving equivalent component, so these repoint onto
# acquire (plain lifecycle) and characterise (a real failure path with a
# structured partial-progress payload, mirroring the old block_id check).


def test_run_lifecycle_succeeded(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    config = compile(Plan(component="acquire", evidence_scope_id=scope_id))

    # Emit run.started + plan.compiled (skeleton does this; simulate here)
    events.append(conn, project_id=pid, run_id=rid, event_type="run.started", payload={})
    events.append(conn, project_id=pid, run_id=rid, event_type="plan.compiled", payload={})

    run_harness(conn, config=config, project_id=pid, run_id=rid, provider=StubEchoProvider())

    # Run record reached succeeded
    row = conn.execute(select(runs).where(runs.c.run_id == rid)).one()
    assert row.status == "succeeded"
    assert row.ended_at is not None


def test_run_lifecycle_failed_on_component_error(conn: Connection) -> None:
    pid, rid_screen = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _seed_doc(conn, pid, rid_screen, scope_id, title="Report", abstract="Body. [stub-theme: X]")

    rid = uuid.uuid4()
    conn.execute(runs.insert().values(
        run_id=rid, project_id=pid, status="running", started_at=now()
    ))
    config = compile(Plan(component="characterise", evidence_scope_id=scope_id))

    events.append(conn, project_id=pid, run_id=rid, event_type="run.started", payload={})
    events.append(conn, project_id=pid, run_id=rid, event_type="plan.compiled", payload={})

    run_harness(
        conn, config=config, project_id=pid, run_id=rid, provider=StubEchoProvider(),
        theme_grouping_backend=_RaisingDiscoverBackend(),
    )

    row = conn.execute(select(runs).where(runs.c.run_id == rid)).one()
    assert row.status == "failed"
    assert row.ended_at is not None

    log = events.read(conn, pid)
    assert log[-1]["event_type"] == "run.failed"


def test_run_harness_binds_project_run_component_contextvars(conn: Connection) -> None:
    """run_harness binds project_id/run_id/component once via
    structlog.contextvars.bound_contextvars around the component body, so
    log calls made deep inside a component execution (here, the theme
    grouping backend invoked by characterise) inherit them without any
    kwarg being hand-threaded down to that call site.
    """
    pid, rid_screen = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _seed_doc(conn, pid, rid_screen, scope_id, title="Report", abstract="Body. [stub-theme: X]")

    rid = uuid.uuid4()
    conn.execute(runs.insert().values(
        run_id=rid, project_id=pid, status="running", started_at=now()
    ))
    config = compile(Plan(component="characterise", evidence_scope_id=scope_id))

    events.append(conn, project_id=pid, run_id=rid, event_type="run.started", payload={})
    events.append(conn, project_id=pid, run_id=rid, event_type="plan.compiled", payload={})

    seen_contextvars: dict[str, Any] = {}

    class _ContextSpyingThemeGroupingBackend:
        mode = "stub"

        def discover(
            self,
            docs: list[Any],
            *,
            intent: str,
            min_themes: int,
            max_themes: int,
            guidance: list[str] | None = None,
        ) -> Any:
            seen_contextvars.update(structlog.contextvars.get_contextvars())
            return StubThemeGroupingBackend().discover(
                docs,
                intent=intent,
                min_themes=min_themes,
                max_themes=max_themes,
                guidance=guidance,
            )

        def assign(self, batch: list[Any], *, themes: list[Any]) -> Any:
            return StubThemeGroupingBackend().assign(batch, themes=themes)

    # Outside the harness call, no ambient project_id/run_id/component context.
    assert structlog.contextvars.get_contextvars() == {}

    run_harness(
        conn, config=config, project_id=pid, run_id=rid, provider=StubEchoProvider(),
        theme_grouping_backend=_ContextSpyingThemeGroupingBackend(),
    )

    assert seen_contextvars == {
        "project_id": str(pid),
        "run_id": str(rid),
        "component": "characterise",
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

    from policy_atlas.core.logging import configure_logging

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
    other_pid = uuid.uuid4()
    conn.execute(project.insert().values(project_id=other_pid, created_at=now()))
    config = compile(Plan(component="acquire", evidence_scope_id=uuid.uuid4()))

    with pytest.raises(ValueError, match="belongs to project"):
        run_harness(
            conn, config=config, project_id=other_pid, run_id=rid, provider=StubEchoProvider()
        )


def test_failed_characterise_emits_component_failed_with_coverage(conn: Connection) -> None:
    """component.failed must carry more than a boilerplate error string: a
    genuine mid-pipeline failure persists partial-progress detail (here,
    characterise's ``coverage`` — the equivalent of the old echo/grounding
    chain's ``block_id`` on a failed grounding attempt)."""
    pid, rid_screen = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _seed_doc(conn, pid, rid_screen, scope_id, title="Report", abstract="Body. [stub-theme: X]")

    rid = uuid.uuid4()
    conn.execute(runs.insert().values(
        run_id=rid, project_id=pid, status="running", started_at=now()
    ))
    config = compile(Plan(component="characterise", evidence_scope_id=scope_id))

    events.append(conn, project_id=pid, run_id=rid, event_type="run.started", payload={})
    events.append(conn, project_id=pid, run_id=rid, event_type="plan.compiled", payload={})

    run_harness(
        conn, config=config, project_id=pid, run_id=rid, provider=StubEchoProvider(),
        theme_grouping_backend=_RaisingDiscoverBackend(),
    )

    event_log = events.read(conn, pid)
    types = [e["event_type"] for e in event_log]
    assert "component.failed" in types
    cf = next(e for e in event_log if e["event_type"] == "component.failed")
    assert "coverage" in cf["payload"], (
        "persisted coverage must appear in component.failed audit event"
    )


def test_component_failed_persists_structured_exception_reason(
    conn: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review fix D (harness.py ~171): a sources_fn raising a structured
    exception with a ``.reason`` attribute (e.g. ``ScreenSupersessionError``'s
    ``stage2_supersession_collision``) must have that reason persisted onto
    the ``component.failed`` event — flattening to ``str(exc)`` alone would
    make a halt-and-re-gate undiagnosable from the record (the 013 rule: a
    persisted rejection must persist its reason)."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    config = compile(Plan(component="screen", evidence_scope_id=scope_id))

    events.append(conn, project_id=pid, run_id=rid, event_type="run.started", payload={})
    events.append(conn, project_id=pid, run_id=rid, event_type="plan.compiled", payload={})

    class _ReasonedError(RuntimeError):
        reason = "stage2_supersession_collision"

    def failing_screen_sources(
        conn: Connection,
        *,
        project_id: uuid.UUID,
        run_id: uuid.UUID,
        context: Any,
        screening_backend: Any = None,
    ) -> dict[str, Any]:
        del conn, project_id, run_id, context, screening_backend
        raise _ReasonedError("forced supersession collision")

    monkeypatch.setattr(harness, "screen_sources", failing_screen_sources)

    run_harness(conn, config=config, project_id=pid, run_id=rid, provider=StubEchoProvider())

    event_log = events.read(conn, pid)
    cf = next(e for e in event_log if e["event_type"] == "component.failed")
    assert cf["payload"]["error"] == "forced supersession collision"
    assert cf["payload"]["reason"] == "stage2_supersession_collision"


def test_event_log_five_types_in_order(conn: Connection) -> None:
    pid, rid_screen = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _seed_doc(conn, pid, rid_screen, scope_id, title="Report", abstract="Body. [stub-theme: X]")

    rid = uuid.uuid4()
    conn.execute(runs.insert().values(
        run_id=rid, project_id=pid, status="running", started_at=now()
    ))
    config = compile(Plan(component="characterise", evidence_scope_id=scope_id))

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


def test_failure_evidence_survives_commit(engine: Engine) -> None:
    """Failure evidence must hold across a real COMMIT, not only inside a rolled-back txn.

    Every other failure-path test reads back on the same connection the conftest fixture
    rolls back, so none of them prove the failure evidence *persists*. A future refactor
    that let a component exception escape past skeleton's `engine.begin()` would roll
    the failed run status and event log back, and the whole suite would still pass. This
    test commits, reopens a fresh connection, and asserts the failure evidence is durably
    there.

    (Task 023 C3: the echo/grounding chain's own commit-durability guarantee — the
    quote-verification ``annotation`` row on a failed grounding attempt — has no
    surviving equivalent now echo is retired; this repoints onto characterise's
    structured failure path, whose durable evidence is the failed run status plus
    the ``component.failed``/``run.failed`` event pair.)
    """
    pid = uuid.uuid4()
    rid_screen = uuid.uuid4()
    rid = uuid.uuid4()
    try:
        with engine.begin() as conn:
            conn.execute(project.insert().values(project_id=pid, created_at=now()))
            conn.execute(runs.insert().values(
                run_id=rid_screen, project_id=pid, status="running", started_at=now()
            ))
            scope_id = seed_scope(conn, pid)
            _seed_doc(
                conn, pid, rid_screen, scope_id, title="Report", abstract="Body. [stub-theme: X]"
            )
            conn.execute(runs.insert().values(
                run_id=rid, project_id=pid, status="running", started_at=now()
            ))
            config = compile(Plan(component="characterise", evidence_scope_id=scope_id))
            events.append(conn, project_id=pid, run_id=rid, event_type="run.started", payload={})
            events.append(conn, project_id=pid, run_id=rid, event_type="plan.compiled", payload={})
            run_harness(
                conn, config=config, project_id=pid, run_id=rid, provider=StubEchoProvider(),
                theme_grouping_backend=_RaisingDiscoverBackend(),
            )
        # transaction committed on block exit (harness swallows CharacteriseFailure, no rollback)

        with engine.connect() as conn:
            run_row = conn.execute(select(runs).where(runs.c.run_id == rid)).one()
            assert run_row.status == "failed"

            log = events.read(conn, pid)
            assert log[-1]["event_type"] == "run.failed"
            failed = next(e for e in log if e["event_type"] == "component.failed")
            assert "coverage" in failed["payload"]
    finally:
        with engine.begin() as conn:
            delete_project_data(conn, pid)
