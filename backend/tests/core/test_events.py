"""Event-log append/read-back — ordering and per-task isolation."""

import pytest
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from policy_atlas.core import events
from tests.helpers import delete_task_data, seed_task_and_run


def test_append_and_read_ordered_by_sequence(conn: Connection) -> None:
    pid, rid = seed_task_and_run(conn)

    events.append(conn, task_id=pid, run_id=rid, event_type="run.started", payload={})
    events.append(conn, task_id=pid, run_id=rid, event_type="plan.compiled", payload={"x": 1})
    events.append(conn, task_id=pid, run_id=rid, event_type="run.completed", payload={})

    log = events.read(conn, pid)
    assert [e["event_type"] for e in log] == ["run.started", "plan.compiled", "run.completed"]
    assert [e["sequence"] for e in log] == [1, 2, 3]


def test_cross_task_event_append_rejected(conn: Connection) -> None:
    """DB must reject appending run B into task A's event log (composite FK)."""
    pid1, _rid1 = seed_task_and_run(conn)
    _pid2, rid2 = seed_task_and_run(conn)  # rid2 belongs to pid2, not pid1

    with pytest.raises(IntegrityError):
        events.append(conn, task_id=pid1, run_id=rid2, event_type="poisoned", payload={})


def test_read_filters_by_event_types(conn: Connection) -> None:
    """``event_types`` restricts the read to those event_type values, in the SQL
    WHERE (sequence ordering preserved); ``None`` (default) is unchanged."""
    pid, rid = seed_task_and_run(conn)

    events.append(conn, task_id=pid, run_id=rid, event_type="run.started", payload={})
    events.append(conn, task_id=pid, run_id=rid, event_type="steering.pause", payload={})
    events.append(conn, task_id=pid, run_id=rid, event_type="plan.compiled", payload={})
    events.append(conn, task_id=pid, run_id=rid, event_type="steering.decision", payload={})

    filtered = events.read(conn, pid, event_types=["steering.pause", "steering.decision"])
    assert [e["event_type"] for e in filtered] == ["steering.pause", "steering.decision"]
    assert [e["sequence"] for e in filtered] == [2, 4]

    unfiltered = events.read(conn, pid)
    assert len(unfiltered) == 4


def test_sequence_is_per_task(conn: Connection) -> None:
    """Two tasks have independent sequence counters."""
    pid1, rid1 = seed_task_and_run(conn)
    pid2, rid2 = seed_task_and_run(conn)

    events.append(conn, task_id=pid1, run_id=rid1, event_type="a", payload={})
    events.append(conn, task_id=pid1, run_id=rid1, event_type="b", payload={})
    events.append(conn, task_id=pid2, run_id=rid2, event_type="a", payload={})

    log1 = events.read(conn, pid1)
    log2 = events.read(conn, pid2)
    assert [e["sequence"] for e in log1] == [1, 2]
    assert [e["sequence"] for e in log2] == [1]


def test_more_concurrent_writers_than_retries_all_append_in_order(engine: Engine) -> None:
    """Forty writers on one task at once all land, numbered 1 to 40 (the per-task lock).

    Without the lock each append read the same max and retried; a theory-of-change
    check's fan-out exhausted the 32 retries (deferred note, task 064a).
    """
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from sqlalchemy import create_engine

    with engine.begin() as conn:
        task_id, run_id = seed_task_and_run(conn)
    writers = events.APPEND_ATTEMPTS + 8
    # One connection per writer: the shared engine's pool is smaller, and a
    # writer waiting at the barrier for a connection would never arrive.
    burst = create_engine(engine.url, pool_size=writers, max_overflow=0)
    start = Barrier(writers, timeout=60)

    def write(index: int) -> None:
        with burst.begin() as conn:
            start.wait()
            events.append(conn, task_id=task_id, run_id=run_id, event_type="test.burst",
                          payload={"index": index})

    try:
        with ThreadPoolExecutor(max_workers=writers) as pool:
            list(pool.map(write, range(writers)))
        with engine.connect() as conn:
            sequences = [row["sequence"] for row in events.read(conn, task_id)]
        assert sequences == list(range(1, writers + 1))
    finally:
        burst.dispose()
        with engine.begin() as conn:
            delete_task_data(conn, task_id)

