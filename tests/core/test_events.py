"""Event-log append/read-back — ordering and per-project isolation."""

import pytest
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from policy_atlas.core import events
from tests.helpers import seed_project_and_run


def test_append_and_read_ordered_by_sequence(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)

    events.append(conn, project_id=pid, run_id=rid, event_type="run.started", payload={})
    events.append(conn, project_id=pid, run_id=rid, event_type="plan.compiled", payload={"x": 1})
    events.append(conn, project_id=pid, run_id=rid, event_type="run.completed", payload={})

    log = events.read(conn, pid)
    assert [e["event_type"] for e in log] == ["run.started", "plan.compiled", "run.completed"]
    assert [e["sequence"] for e in log] == [1, 2, 3]


def test_cross_project_event_append_rejected(conn: Connection) -> None:
    """DB must reject appending run B into project A's event log (composite FK)."""
    pid1, _rid1 = seed_project_and_run(conn)
    _pid2, rid2 = seed_project_and_run(conn)  # rid2 belongs to pid2, not pid1

    with pytest.raises(IntegrityError):
        events.append(conn, project_id=pid1, run_id=rid2, event_type="poisoned", payload={})


def test_sequence_is_per_project(conn: Connection) -> None:
    """Two projects have independent sequence counters."""
    pid1, rid1 = seed_project_and_run(conn)
    pid2, rid2 = seed_project_and_run(conn)

    events.append(conn, project_id=pid1, run_id=rid1, event_type="a", payload={})
    events.append(conn, project_id=pid1, run_id=rid1, event_type="b", payload={})
    events.append(conn, project_id=pid2, run_id=rid2, event_type="a", payload={})

    log1 = events.read(conn, pid1)
    log2 = events.read(conn, pid2)
    assert [e["sequence"] for e in log1] == [1, 2]
    assert [e["sequence"] for e in log2] == [1]
