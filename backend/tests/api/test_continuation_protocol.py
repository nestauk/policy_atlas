"""Contract coverage for the parked-walk continuation protocol."""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.api.continuation import (
    AlreadyAnsweredError,
    InvalidResponseError,
    answer_check_in,
    claim_continuation,
    compile_free_text,
    confirm_free_text,
    execute_continuation,
    startup_sweep,
)
from policy_atlas.core import events
from policy_atlas.core.schema import capability_run
from policy_atlas.runtime.orchestrator_backend import StubOrchestratorBackend
from policy_atlas.runtime.orchestrator_prompt import RouterCompileWire, RouterFragmentWire
from policy_atlas.runtime.runner import NullIO, WalkParked, run_plan
from tests.runtime.test_runner import _base_plan, _cleanup, _runner_backends, _seed_project
from tests.runtime.test_steering import _insert_plan_row


class _ParkOnceIO:
    """Park the first after-component pause and continue any later pause."""

    def __init__(self) -> None:
        self.parked = False

    def check_in(self, component: str, payload: dict[str, Any]) -> None:
        """Accept deterministic check-ins while driving the scripted pause."""
        del component, payload

    def pause(self, point: dict[str, Any], render: str) -> Any:
        """Park the first after-component presentation after it is durable."""
        del render
        if not self.parked and point["boundary"] == "after_component":
            self.parked = True
            raise WalkParked()
        from policy_atlas.runtime.steering import Continue

        return Continue()


class _ParkAtIO:
    """Park one exact boundary while allowing the scripted walk to reach it."""

    def check_in(self, component: str, payload: dict[str, Any]) -> None:
        """Accept intermediate check-ins before the target boundary."""
        del component, payload

    def pause(self, point: dict[str, Any], render: str) -> Any:
        """Park exactly before synthesis, whose durable affordance forbids re-entry."""
        del render
        if point["boundary"] == "before_component" and point["component"] == "synthesise":
            raise WalkParked()
        from policy_atlas.runtime.steering import Continue

        return Continue()


def _park_walk(engine: Engine) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """Seed and park one scripted walk, returning project/scope/run/check-in ids."""
    project_id, scope_id = _seed_project(engine)
    plan = _base_plan(steering_mode="frequent", search_effort="standard")
    plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
    outcome = run_plan(
        engine,
        project_id=project_id,
        evidence_scope_id=scope_id,
        plan=plan,
        plan_id=plan_id,
        plan_version=1,
        plan_row_id=plan_id,
        backends=_runner_backends(),
        io=_ParkOnceIO(),
    )
    assert outcome.status == "paused"
    assert outcome.capability_run_id is not None
    with engine.connect() as conn:
        pause = next(
            entry
            for entry in reversed(events.read(conn, project_id))
            if entry["event_type"] == "steering.pause"
        )
    return project_id, scope_id, outcome.capability_run_id, pause["event_id"]


def _continue_response() -> dict[str, Any]:
    """Return the canonical response offered by every scripted park."""
    return {"kind": "option", "option_id": "continue"}


def test_steering_round_trip_through_real_continuation_seam(engine: Engine) -> None:
    """A durable answer/claim/resume completes the original capability walk."""
    project_id: uuid.UUID | None = None
    try:
        project_id, _scope_id, capability_run_id, check_in_id = _park_walk(engine)
        answer = answer_check_in(
            engine,
            project_id=project_id,
            check_in_id=check_in_id,
            response=_continue_response(),
            actor="user-1",
        )
        assert answer.continuation_requested is True
        claim = claim_continuation(
            engine, project_id=project_id, capability_run_id=capability_run_id
        )
        assert claim is not None
        outcome = execute_continuation(
            engine,
            project_id=project_id,
            capability_run_id=capability_run_id,
            backends=_runner_backends(),
            io=NullIO(),
        )
        assert outcome.status == "succeeded"
        with engine.connect() as conn:
            log = events.read(conn, project_id)
            status = conn.execute(
                select(capability_run.c.status).where(
                    capability_run.c.capability_run_id == capability_run_id
                )
            ).scalar_one()
        decision = next(entry for entry in log if entry["event_id"] == answer.decision_event_id)
        assert decision["event_type"] == "steering.decision"
        assert decision["run_id"] == next(
            entry["run_id"] for entry in log if entry["event_id"] == check_in_id
        )
        assert [entry["event_type"] for entry in log].count("continuation.requested") == 1
        assert [entry["event_type"] for entry in log].count("continuation.claimed") == 1
        assert status == "succeeded"
    finally:
        _cleanup(engine, project_id)


def test_double_answer_barrier_allows_exactly_one_decision(engine: Engine) -> None:
    """Project-row locking turns two simultaneous answers into one answer and one 409."""
    project_id: uuid.UUID | None = None
    try:
        project_id, _scope_id, _capability_run_id, check_in_id = _park_walk(engine)
        barrier = threading.Barrier(2)

        def answer() -> str:
            """Synchronise two POST-equivalent answer attempts."""
            barrier.wait()
            try:
                answer_check_in(
                    engine,
                    project_id=project_id,
                    check_in_id=check_in_id,
                    response=_continue_response(),
                    actor="user-1",
                )
            except AlreadyAnsweredError:
                return "already_answered"
            return "accepted"

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(answer), pool.submit(answer)]
            outcomes = sorted(future.result() for future in futures)
        assert outcomes == ["accepted", "already_answered"]
        with engine.connect() as conn:
            log = events.read(conn, project_id)
        assert [entry["event_type"] for entry in log].count("steering.decision") == 1
        assert [entry["event_type"] for entry in log].count("continuation.requested") == 1
    finally:
        _cleanup(engine, project_id)


def test_crash_before_claim_drains_then_resumes(engine: Engine) -> None:
    """An answer committed before a crash remains redispatchable on startup."""
    project_id: uuid.UUID | None = None
    try:
        project_id, _scope_id, capability_run_id, check_in_id = _park_walk(engine)
        answer_check_in(
            engine,
            project_id=project_id,
            check_in_id=check_in_id,
            response=_continue_response(),
            actor="user-1",
        )
        report = startup_sweep(engine)
        assert [claim.capability_run_id for claim in report.redispatch] == [capability_run_id]
        assert claim_continuation(
            engine, project_id=project_id, capability_run_id=capability_run_id
        ) is not None
        outcome = execute_continuation(
            engine,
            project_id=project_id,
            capability_run_id=capability_run_id,
            backends=_runner_backends(),
            io=NullIO(),
        )
        assert outcome.status == "succeeded"
    finally:
        _cleanup(engine, project_id)


def test_crash_after_claim_is_reexecuted_not_interrupted(engine: Engine) -> None:
    """A claimed-but-unexecuted walk is recovered on the next boot, never discarded.

    Deliberate behaviour change (review finding adv-M1, adjudicated 2026-07-21):
    the sweep previously interrupted this walk — discarding a just-answered park
    even though the claim is durable and no component ever ran. The sweep now
    classifies it for direct re-execution; the contract's "a crash between
    answer and execution loses nothing" covers the claim→execute window too.
    """
    project_id: uuid.UUID | None = None
    try:
        project_id, _scope_id, capability_run_id, check_in_id = _park_walk(engine)
        answer_check_in(
            engine,
            project_id=project_id,
            check_in_id=check_in_id,
            response=_continue_response(),
            actor="user-1",
        )
        assert claim_continuation(
            engine, project_id=project_id, capability_run_id=capability_run_id
        ) is not None
        report = startup_sweep(engine)
        assert report.interrupted_capability_run_ids == ()
        assert report.redispatch == ()
        assert [claim.capability_run_id for claim in report.reexecute] == [capability_run_id]
        with engine.connect() as conn:
            log = events.read(conn, project_id)
            status = conn.execute(
                select(capability_run.c.status).where(
                    capability_run.c.capability_run_id == capability_run_id
                )
            ).scalar_one()
        # Still claimed/running, no interruption event — the walk executes next.
        assert status == "running"
        assert [entry["event_type"] for entry in log].count("run.interrupted") == 0
        outcome = execute_continuation(
            engine,
            project_id=project_id,
            capability_run_id=capability_run_id,
            backends=_runner_backends(),
            io=NullIO(),
        )
        assert outcome.status == "succeeded"
    finally:
        _cleanup(engine, project_id)


def test_crash_mid_execution_after_claim_is_interrupted(engine: Engine) -> None:
    """Post-claim component progress means mid-execution death → honest interruption."""
    project_id: uuid.UUID | None = None
    try:
        project_id, _scope_id, capability_run_id, check_in_id = _park_walk(engine)
        answer_check_in(
            engine,
            project_id=project_id,
            check_in_id=check_in_id,
            response=_continue_response(),
            actor="user-1",
        )
        assert claim_continuation(
            engine, project_id=project_id, capability_run_id=capability_run_id
        ) is not None
        # Simulate the executor having started a component before dying: any
        # run-attached non-continuation event after the claim counts as progress
        # (reuse the walk's real attachment — event_log.run_id is a real FK).
        with engine.begin() as conn:
            attachment = next(
                row["run_id"]
                for row in reversed(events.read(conn, project_id))
                if row["run_id"] is not None
            )
            events.append(
                conn,
                project_id=project_id,
                run_id=attachment,
                event_type="run.started",
                payload={"component": "acquire"},
            )
        report = startup_sweep(engine)
        assert report.interrupted_capability_run_ids == (capability_run_id,)
        assert report.reexecute == ()
        with engine.connect() as conn:
            status = conn.execute(
                select(capability_run.c.status).where(
                    capability_run.c.capability_run_id == capability_run_id
                )
            ).scalar_one()
        assert status == "interrupted"
    finally:
        _cleanup(engine, project_id)


def test_orphan_sweep_double_boot_is_idempotent(engine: Engine) -> None:
    """The second startup sweep appends no additional interruption event."""
    project_id: uuid.UUID | None = None
    try:
        project_id, _scope_id, capability_run_id, check_in_id = _park_walk(engine)
        answer_check_in(
            engine,
            project_id=project_id,
            check_in_id=check_in_id,
            response=_continue_response(),
            actor="user-1",
        )
        assert claim_continuation(
            engine, project_id=project_id, capability_run_id=capability_run_id
        ) is not None
        # Mark real progress so both boots see a mid-execution death.
        with engine.begin() as conn:
            attachment = next(
                row["run_id"]
                for row in reversed(events.read(conn, project_id))
                if row["run_id"] is not None
            )
            events.append(
                conn,
                project_id=project_id,
                run_id=attachment,
                event_type="run.started",
                payload={"component": "acquire"},
            )
        first = startup_sweep(engine)
        with engine.connect() as conn:
            first_count = len(events.read(conn, project_id))
        second = startup_sweep(engine)
        with engine.connect() as conn:
            second_count = len(events.read(conn, project_id))
        assert first.interrupted_capability_run_ids == (capability_run_id,)
        assert second.interrupted_capability_run_ids == ()
        assert second.reexecute == ()
        assert first_count == second_count
    finally:
        _cleanup(engine, project_id)


def test_parked_answers_reject_replays_and_invalid_options(engine: Engine) -> None:
    """A parked pause accepts its first answer and fail-closes invalid/replayed input."""
    project_id: uuid.UUID | None = None
    try:
        project_id, _scope_id, _capability_run_id, check_in_id = _park_walk(engine)
        with pytest.raises(InvalidResponseError):
            answer_check_in(
                engine,
                project_id=project_id,
                check_in_id=check_in_id,
                response={"kind": "option", "option_id": "not-offered"},
                actor="user-1",
            )
        answer_check_in(
            engine,
            project_id=project_id,
            check_in_id=check_in_id,
            response=_continue_response(),
            actor="user-1",
        )
        with pytest.raises(AlreadyAnsweredError):
            answer_check_in(
                engine,
                project_id=project_id,
                check_in_id=check_in_id,
                response=_continue_response(),
                actor="user-1",
            )
    finally:
        _cleanup(engine, project_id)


def test_disallowed_segment_reentry_fails_closed_at_confirmation(engine: Engine) -> None:
    """An additive free-text fragment is refused where the pause did not offer re-entry."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(steering_mode="frequent", search_effort="standard")
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=_ParkAtIO(),
        )
        assert outcome.status == "paused"
        with engine.connect() as conn:
            pause = next(
                entry
                for entry in reversed(events.read(conn, project_id))
                if entry["event_type"] == "steering.pause"
            )
        assert pause["payload"]["segment_reentry_allowed"] is False
        orchestrator = StubOrchestratorBackend(
            route_responses=RouterCompileWire(
                fragments=[
                    RouterFragmentWire(
                        fragment_text="search again",
                        compiles=True,
                        component="acquire",
                        delta={"search": {"depth": "deep"}},
                        rerun_mode="additive",
                    )
                ],
                summary="Add another search pass.",
            )
        )
        compiled = compile_free_text(
            engine,
            orchestrator,
            project_id=project_id,
            check_in_id=pause["event_id"],
            text="search again",
        )
        with pytest.raises(InvalidResponseError):
            confirm_free_text(
                engine,
                project_id=project_id,
                check_in_id=pause["event_id"],
                confirm_token=compiled.confirm_token,
                apply=True,
                actor="user-1",
            )
    finally:
        _cleanup(engine, project_id)


def test_sweep_survives_running_walk_with_no_attachment(engine: Engine) -> None:
    """Death between run.opened and the first component must not brick boot.

    The sweep previously raised LookupError inside the lifespan — every
    subsequent API start failed until manual DB surgery (review finding
    backend-M3, 2026-07-21). It now interrupts with a null attachment.
    """
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        orphan_id = uuid.uuid4()
        with engine.begin() as conn:
            from datetime import UTC, datetime

            conn.execute(
                capability_run.insert().values(
                    capability_run_id=orphan_id,
                    project_id=project_id,
                    evidence_scope_id=scope_id,
                    capability="evidence_base",
                    plan_id=uuid.uuid4(),
                    plan_version=1,
                    status="running",
                    started_at=datetime.now(UTC),
                )
            )
            events.append(
                conn,
                project_id=project_id,
                run_id=None,
                event_type="run.opened",
                payload={"capability_run_id": str(orphan_id)},
            )
        report = startup_sweep(engine)
        assert orphan_id in report.interrupted_capability_run_ids
        with engine.connect() as conn:
            status = conn.execute(
                select(capability_run.c.status).where(
                    capability_run.c.capability_run_id == orphan_id
                )
            ).scalar_one()
            log_rows = events.read(conn, project_id)
        assert status == "interrupted"
        interruptions = [row for row in log_rows if row["event_type"] == "run.interrupted"]
        assert len(interruptions) == 1
        assert interruptions[0]["run_id"] is None
    finally:
        _cleanup(engine, project_id)


def test_abort_emits_terminal_event_and_abandons_plan(engine: Engine) -> None:
    """API abort mirrors the runner path: run.finished(aborted) + plan abandoned."""
    from policy_atlas.core.schema import orchestration_plan

    project_id: uuid.UUID | None = None
    try:
        project_id, _scope_id, capability_run_id, check_in_id = _park_walk(engine)
        answer_check_in(
            engine,
            project_id=project_id,
            check_in_id=check_in_id,
            response={"kind": "option", "option_id": "abort"},
            actor="user-1",
        )
        with engine.connect() as conn:
            status = conn.execute(
                select(capability_run.c.status).where(
                    capability_run.c.capability_run_id == capability_run_id
                )
            ).scalar_one()
            log_rows = events.read(conn, project_id)
            plan_statuses = [
                row[0]
                for row in conn.execute(
                    select(orchestration_plan.c.status).where(
                        orchestration_plan.c.project_id == project_id
                    )
                )
            ]
        assert status == "aborted"
        finished = [
            row
            for row in log_rows
            if row["event_type"] == "run.finished"
            and row["payload"].get("capability_run_id") == str(capability_run_id)
        ]
        assert len(finished) == 1
        assert finished[0]["payload"]["status"] == "aborted"
        # SSE replay derives run.status frames from run.* events, so the store
        # sees the terminal transition (review findings adv-M5/codex-5).
        assert "abandoned" in plan_statuses
    finally:
        _cleanup(engine, project_id)


def test_event_sequence_allocation_survives_concurrent_writers(engine: Engine) -> None:
    """Two unserialized writers appending concurrently never lose an event.

    The max+1 allocator collides under concurrency; the SAVEPOINT retry turns
    the collision into a re-read instead of a failed transaction (review
    findings backend-M2/codex-6, 2026-07-21).
    """
    project_id: uuid.UUID | None = None
    try:
        project_id, _scope_id = _seed_project(engine)
        barrier = threading.Barrier(2)
        errors: list[Exception] = []

        def _writer(tag: str) -> None:
            try:
                for index in range(20):
                    with engine.begin() as conn:
                        barrier.wait(timeout=10)
                        events.append(
                            conn,
                            project_id=project_id,
                            run_id=None,
                            event_type="project.renamed",
                            payload={"tag": tag, "index": index},
                        )
            except Exception as exc:  # pragma: no cover - failure reporting
                errors.append(exc)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(_writer, tag) for tag in ("a", "b")]
            for future in futures:
                future.result(timeout=60)
        assert errors == []
        with engine.connect() as conn:
            rows = events.read(conn, project_id)
        sequences = [row["sequence"] for row in rows]
        assert len(rows) == 40
        assert sequences == sorted(sequences)
        assert len(set(sequences)) == 40
    finally:
        _cleanup(engine, project_id)
