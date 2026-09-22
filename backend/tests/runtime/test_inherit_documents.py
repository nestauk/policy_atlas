"""The document part of inherit (task 045 Phase 4.2, S6; ADR 0039 decision 9).

The contract's pool bullet, inherit half: inherited rows are created once per
linked document with their original origin and the shared snapshot id, by the
inherit step (``run_id`` set), idempotently; an unreadable link degrades the
walk and is named. Seeded on the transactional ``conn`` fixture (rolled back);
the one walk-level test commits and cleans up.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import OperationalError

from policy_atlas.core.schema import (
    capability_run,
    source_snapshot,
    task,
    task_link,
    task_plan,
    task_source_snapshot,
)
from policy_atlas.runtime import harness, inherit
from policy_atlas.runtime.inherit import InheritSummary, inherit_documents
from policy_atlas.runtime.runner import NullIO, run_plan
from tests.helpers import now, seed_run, seed_scope, seed_screening_result, seed_source
from tests.runtime.test_baseline_gate import (
    insert_scoping_plan_row,
    scoping_plan,
    seed_scoping_task,
)
from tests.runtime.test_compose_by_purpose import _set_purpose
from tests.runtime.test_runner import _cleanup, _runner_backends


def _make_task(conn: Connection, *, capability: str = "evidence_search") -> uuid.UUID:
    task_id = uuid.uuid4()
    conn.execute(
        task.insert().values(
            task_id=task_id,
            created_at=now(),
            name=f"Task {task_id.hex[:6]}",
            status="active",
            updated_at=now(),
            capability=capability,
        )
    )
    return task_id


class _Source:
    """One linked Evidence search task with a finished walk over one scope."""

    def __init__(self, conn: Connection) -> None:
        self.task_id = _make_task(conn)
        self.run_id = seed_run(conn, self.task_id)
        self.scope_id = seed_scope(conn, self.task_id)
        plan_id = uuid.uuid4()
        conn.execute(
            task_plan.insert().values(
                plan_id=plan_id,
                task_id=self.task_id,
                version=1,
                status="approved",
                payload={},
                created_at=now(),
                created_by="test",
            )
        )
        self.walk_id = uuid.uuid4()
        conn.execute(
            capability_run.insert().values(
                capability_run_id=self.walk_id,
                task_id=self.task_id,
                evidence_scope_id=self.scope_id,
                capability="evidence_search",
                plan_id=plan_id,
                plan_version=1,
                status="succeeded",
                started_at=now(),
            )
        )

    def document(
        self, conn: Connection, *, status: str = "relevant", origin: str = "acquired"
    ) -> tuple[uuid.UUID, uuid.UUID]:
        """A document of this task screened under the pinned walk's scope."""
        snapshot_id, tss_id = seed_source(conn, self.task_id, meta={"title": "A study"})
        conn.execute(
            task_source_snapshot.update()
            .where(task_source_snapshot.c.task_source_snapshot_id == tss_id)
            .values(origin=origin)
        )
        seed_screening_result(conn, self.task_id, self.run_id, self.scope_id, tss_id, status)
        return snapshot_id, tss_id

    def link_to(self, conn: Connection, target_id: uuid.UUID) -> uuid.UUID:
        link_id = uuid.uuid4()
        conn.execute(
            task_link.insert().values(
                link_id=link_id,
                source_task_id=self.task_id,
                target_task_id=target_id,
                source_capability_run_id=self.walk_id,
                created_by="test",
                created_at=now(),
            )
        )
        return link_id


def _target(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
    target_id = _make_task(conn, capability="options_scoping")
    return target_id, seed_run(conn, target_id)


def _rows(conn: Connection, task_id: uuid.UUID) -> list[Any]:
    return list(
        conn.execute(
            select(task_source_snapshot).where(task_source_snapshot.c.task_id == task_id)
        ).mappings()
    )


def test_one_row_per_linked_document_with_its_origin_and_shared_snapshot(
    conn: Connection,
) -> None:
    source = _Source(conn)
    acquired_snapshot, _ = source.document(conn, origin="acquired")
    uploaded_snapshot, _ = source.document(conn, origin="uploaded")
    target_id, run_id = _target(conn)
    source.link_to(conn, target_id)

    summary = inherit_documents(conn, task_id=target_id, run_id=run_id)

    rows = {row["source_snapshot_id"]: row for row in _rows(conn, target_id)}
    assert set(rows) == {acquired_snapshot, uploaded_snapshot}
    # Origin unchanged (A3); created by the inherit step (its run).
    assert rows[acquired_snapshot]["origin"] == "acquired"
    assert rows[uploaded_snapshot]["origin"] == "uploaded"
    assert {row["run_id"] for row in rows.values()} == {run_id}
    assert summary.as_summary() == {
        "links": 1,
        "documents": 2,
        "already_present": 0,
        "failed_links": 0,
        "failed_link_ids": [],
        "failed_reasons": [],
        "degrades_walk": False,
    }


def test_only_the_pinned_walk_s_screened_in_documents_are_inherited(
    conn: Connection,
) -> None:
    source = _Source(conn)
    kept, _ = source.document(conn, status="relevant")
    source.document(conn, status="not_relevant")
    seed_source(conn, source.task_id)  # acquired, never screened in that scope
    target_id, run_id = _target(conn)
    source.link_to(conn, target_id)

    inherit_documents(conn, task_id=target_id, run_id=run_id)

    assert [row["source_snapshot_id"] for row in _rows(conn, target_id)] == [kept]


def test_the_full_text_attachment_is_copied_so_ingest_does_not_refetch(
    conn: Connection,
) -> None:
    source = _Source(conn)
    snapshot_id, source_tss = source.document(conn)
    full_text_id = uuid.uuid4()
    conn.execute(
        source_snapshot.insert().values(
            source_snapshot_id=full_text_id,
            content_hash=str(uuid.uuid4()),
            text_basis="full_text",
            source_locator="full.pdf",
            metadata={},
            created_at=now(),
        )
    )
    conn.execute(
        task_source_snapshot.update()
        .where(task_source_snapshot.c.task_source_snapshot_id == source_tss)
        .values(full_text_snapshot_id=full_text_id, full_text_status="ingested")
    )
    target_id, run_id = _target(conn)
    source.link_to(conn, target_id)

    inherit_documents(conn, task_id=target_id, run_id=run_id)

    [row] = _rows(conn, target_id)
    assert row["source_snapshot_id"] == snapshot_id
    assert row["full_text_snapshot_id"] == full_text_id
    assert row["full_text_status"] == "ingested"


def test_inherit_is_idempotent_and_never_duplicates_a_document_the_task_holds(
    conn: Connection,
) -> None:
    source = _Source(conn)
    shared, _ = source.document(conn)
    only_linked, _ = source.document(conn)
    target_id, run_id = _target(conn)
    # The baseline already acquired one of the two documents.
    baseline_tss = uuid.uuid4()
    conn.execute(
        task_source_snapshot.insert().values(
            task_source_snapshot_id=baseline_tss,
            task_id=target_id,
            source_snapshot_id=shared,
            origin="acquired",
            run_id=None,
            ingested_at=now(),
        )
    )
    source.link_to(conn, target_id)

    first = inherit_documents(conn, task_id=target_id, run_id=run_id)
    second = inherit_documents(conn, task_id=target_id, run_id=seed_run(conn, target_id))

    rows = {row["source_snapshot_id"]: row for row in _rows(conn, target_id)}
    assert set(rows) == {shared, only_linked}
    assert rows[shared]["task_source_snapshot_id"] == baseline_tss
    assert rows[shared]["run_id"] is None
    assert rows[only_linked]["run_id"] == run_id
    assert (first.documents, first.already_present) == (1, 1)
    assert (second.documents, second.already_present) == (0, 2)


def test_no_links_inherits_nothing(conn: Connection) -> None:
    target_id, run_id = _target(conn)
    summary = inherit_documents(conn, task_id=target_id, run_id=run_id)
    assert summary == InheritSummary()
    assert _rows(conn, target_id) == []


def test_an_unreadable_link_is_named_and_the_others_are_kept(
    conn: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A link that fails mid-read rolls back to its savepoint; the rest stand."""
    readable = _Source(conn)
    kept, _ = readable.document(conn)
    broken = _Source(conn)
    broken.document(conn)
    target_id, run_id = _target(conn)
    readable.link_to(conn, target_id)
    broken_link = broken.link_to(conn, target_id)

    real = inherit._inherit_one_link

    def _flaky(conn: Connection, **kwargs: Any) -> tuple[int, int]:
        created = real(conn, **kwargs)
        if kwargs["source_task_id"] == broken.task_id:
            # After its rows were written: the savepoint must take them back.
            raise OperationalError("SELECT 1", {}, Exception("connection reset"))
        return created

    monkeypatch.setattr(inherit, "_inherit_one_link", _flaky)

    summary = inherit_documents(conn, task_id=target_id, run_id=run_id)

    assert [row["source_snapshot_id"] for row in _rows(conn, target_id)] == [kept]
    out = summary.as_summary()
    assert out["links"] == 2
    assert out["documents"] == 1
    assert out["failed_links"] == 1
    assert out["failed_link_ids"] == [str(broken_link)]
    assert out["failed_reasons"] == ["OperationalError"]
    assert out["degrades_walk"] is True


def test_a_failed_link_degrades_the_longlist_walk_which_carries_on(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """inherit completes with the link named; the runner ends the walk degraded.

    ``longlist`` is still a stub (Phase 5), so the walk is cut there; what is
    under test is that inherit *completed* (its summary reaches the thread)
    and the walk is flagged degraded rather than failed at inherit.
    """
    failed_link = uuid.uuid4()

    def _one_failed_link(conn: Connection, *, task_id: uuid.UUID, run_id: uuid.UUID) -> Any:
        del conn, task_id, run_id
        return InheritSummary(
            links=1, failed_link_ids=[failed_link], failed_reasons=["pinned walk missing"]
        )

    monkeypatch.setattr(harness, "inherit_documents", _one_failed_link)
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = seed_scoping_task(engine)
        _set_purpose(engine, scope_id, "longlist")
        plan = scoping_plan(steering_mode="moderate")
        plan_id = insert_scoping_plan_row(engine, task_id=task_id, scope_id=scope_id, plan=plan)
        outcome = run_plan(
            engine,
            task_id=task_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=NullIO(),
        )
        inherit_step = outcome.steps[0]
        assert (inherit_step.component, inherit_step.status) == ("inherit", "succeeded")
        assert {
            "component": "inherit",
            "status": "degraded",
            "run_id": str(inherit_step.run_id),
        } in outcome.flagged_events
    finally:
        _cleanup(engine, task_id)


def test_a_completed_walk_with_a_degrading_step_ends_degraded(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The final status reads the flag: with every step succeeding, still degraded."""
    from policy_atlas.runtime import runner
    from policy_atlas.runtime.task_plan import ComponentStep, ComposedChain

    failed_link = uuid.uuid4()

    def _one_failed_link(conn: Connection, *, task_id: uuid.UUID, run_id: uuid.UUID) -> Any:
        del conn, task_id, run_id
        return InheritSummary(
            links=1, failed_link_ids=[failed_link], failed_reasons=["pinned walk missing"]
        )

    def _inherit_only(capability: str, plan: Any, *, purpose: str | None = None) -> Any:
        del capability, plan, purpose
        return ComposedChain(
            steps=[ComponentStep(component="inherit", directive_delta={}, spine=False)]
        )

    monkeypatch.setattr(harness, "inherit_documents", _one_failed_link)
    monkeypatch.setattr(runner, "compose_plan", _inherit_only)
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = seed_scoping_task(engine)
        _set_purpose(engine, scope_id, "longlist")
        plan = scoping_plan(steering_mode="moderate")
        plan_id = insert_scoping_plan_row(engine, task_id=task_id, scope_id=scope_id, plan=plan)
        outcome = run_plan(
            engine,
            task_id=task_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=NullIO(),
        )
        assert [(step.component, step.status) for step in outcome.steps] == [
            ("inherit", "succeeded")
        ]
        assert outcome.status == "degraded"
    finally:
        _cleanup(engine, task_id)
