"""The judge commits each link as it is judged (task 054, S8 / A16)."""

from __future__ import annotations

import threading
import uuid
from collections import Counter
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.api.routers.toc import toc_graph_out
from policy_atlas.core.schema import event_log, runs, toc_item_evidence
from policy_atlas.theory_of_change import store
from policy_atlas.theory_of_change.backend import StubTocBackend
from policy_atlas.theory_of_change.check import judge, shared
from tests.theory_of_change.test_check_steps import _run, _summary, _Unverifiable


def _check_walk(engine: Engine, task_id: uuid.UUID) -> uuid.UUID:
    """The check walk: the one that ran ``toc_judge``."""
    with engine.connect() as conn:
        walk = conn.execute(
            select(runs.c.capability_run_id)
            .join(event_log, event_log.c.run_id == runs.c.run_id)
            .where(runs.c.task_id == task_id)
            .where(event_log.c.event_type == "run.started")
            .where(event_log.c.payload["component"].astext == "toc_judge")
            .limit(1)
        ).scalar_one()
    return uuid.UUID(str(walk))


def _attempts(engine: Engine, task_id: uuid.UUID, component: str) -> list[uuid.UUID]:
    with engine.connect() as conn:
        return list(
            conn.execute(
                select(event_log.c.run_id)
                .where(event_log.c.task_id == task_id)
                .where(event_log.c.event_type == "run.started")
                .where(event_log.c.payload["component"].astext == component)
                .order_by(event_log.c.sequence)
            ).scalars()
        )


def _judge_changes(engine: Engine, task_id: uuid.UUID) -> list[uuid.UUID]:
    """The run of each ``toc.changed`` event the judge wrote."""
    with engine.connect() as conn:
        return list(
            conn.execute(
                select(event_log.c.run_id)
                .where(event_log.c.task_id == task_id)
                .where(event_log.c.event_type == store.TOC_CHANGED_EVENT)
                .where(event_log.c.payload["step"].astext == "toc_judge")
            ).scalars()
        )


def test_a_retried_judge_skips_the_links_it_wrote_and_leaves_no_duplicates(
    engine: Engine, cleanup: list[uuid.UUID], monkeypatch: pytest.MonkeyPatch
) -> None:
    # The first judge call of the walk raises out of the pool: the links whose
    # calls all came back are already committed, and the runner retries the step.
    original = shared._call
    lock = threading.Lock()
    raised = False

    def fail_once(name: str, call: Any) -> Any:
        nonlocal raised
        with lock:
            first, raised = not raised, True
        if first:
            raise RuntimeError("judge call lost")
        return original(name, call)

    monkeypatch.setattr(judge, "_call", fail_once)
    backend = StubTocBackend()
    task_id = _run(engine, cleanup, backend)
    attempts = _attempts(engine, task_id, "toc_judge")
    assert len(attempts) == 2  # the failed attempt and the retry
    first_jobs = backend.calls["judge"]  # every call, both attempts and the second search
    retried = _summary(engine, task_id, "toc_judge")
    again = _summary(engine, task_id, "toc_search_again")
    # The retry made no call for a link the failed attempt wrote.
    assert retried["links_already_written"] >= retried["links"] - 1 > 0
    assert retried["calls"] < first_jobs
    walk = _check_walk(engine, task_id)
    with engine.connect() as conn:
        rows = conn.execute(
            select(toc_item_evidence.c.link_id, toc_item_evidence.c.task_source_snapshot_id)
            .where(toc_item_evidence.c.task_id == task_id)
            .where(toc_item_evidence.c.capability_run_id == walk)
        ).all()
    # No duplicates, and no extra documents judged for a link already written.
    assert len(rows) == len(set(rows))
    assert len(rows) == retried["judgements"] + again.get("judgements", 0)
    # The failed attempt wrote no change event; the retry wrote one.
    assert Counter(_judge_changes(engine, task_id))[attempts[1]] == 1
    assert attempts[0] not in _judge_changes(engine, task_id)


class _HoldsOtherLinks(StubTocBackend):
    """Answers the first link's calls; every other call waits until released."""

    def __init__(self) -> None:
        super().__init__()
        self.release = threading.Event()
        self._first: str | None = None
        self._pick = threading.Lock()

    def judge(self, **kwargs: Any) -> Any:
        with self._pick:
            if self._first is None:
                self._first = kwargs["item_text"]
            mine = kwargs["item_text"] == self._first
        if not mine:
            # Bounded, so a broken build fails the test instead of hanging it.
            assert self.release.wait(timeout=60)
        return super().judge(**kwargs)


def test_a_graph_read_between_two_link_commits_shows_the_first_link_graded(
    engine: Engine, cleanup: list[uuid.UUID], monkeypatch: pytest.MonkeyPatch
) -> None:
    backend = _HoldsOtherLinks()
    seen: list[Any] = []
    write = judge._LinkWriter.write

    def write_then_read(self: Any, key: str, answered: Any) -> None:
        write(self, key, answered)
        if not seen:
            # Between the first link's commit and any other's: the others' calls wait.
            with engine.connect() as conn:
                seen.append((key, toc_graph_out(conn, self.task_id)))
            backend.release.set()

    monkeypatch.setattr(judge._LinkWriter, "write", write_then_read)
    _run(engine, cleanup, backend)
    assert seen, "no link was written"
    key, graph = seen[0]
    assert graph.check_status == "checking"
    first = next(link for link in graph.links if str(link.link_id) == key)
    others = [link for link in graph.links if str(link.link_id) != key]
    assert first.state == "checked" and first.weights.n_documents > 0
    assert others and all(
        link.state == "checking" and link.weights.n_documents == 0 for link in others
    )


def test_the_judge_writes_one_change_event_per_step(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    # Every link is left thin, so the second search (C44) judges once more.
    task_id = _run(engine, cleanup, _Unverifiable())
    judged = Counter(_judge_changes(engine, task_id))
    steps = _attempts(engine, task_id, "toc_judge") + _attempts(
        engine, task_id, "toc_search_again"
    )
    # One for the judge and one for the second search's judge, never one per link.
    assert _summary(engine, task_id, "toc_judge")["links"] > 1
    assert _summary(engine, task_id, "toc_search_again")["calls"] > 0
    assert sorted(judged, key=str) == sorted(steps, key=str)
    assert set(judged.values()) == {1}
