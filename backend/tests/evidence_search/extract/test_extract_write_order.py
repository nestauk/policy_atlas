"""``_write_docs`` takes the memo keys' locks in one stable order (task 045, L7).

Two option-search child walks profiling overlapping documents write their memo
rows concurrently. Each takes one advisory lock per memo key, in sorted key
order, before its first write, so the two can never wait on each other's
unique-index entries in opposite orders. The writes themselves keep
selected-set order (the Evidence search's pinned write order).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from sqlalchemy.engine import Connection

from policy_atlas.evidence_search.extract import extract as extract_module


class _Conn:
    def __init__(self, log: list[tuple[str, Any]]) -> None:
        self.log = log

    def execute(self, statement: Any) -> None:
        params = statement.compile().params
        assert "pg_advisory_xact_lock" in str(statement)
        self.log.append(("lock", next(iter(params.values()))))

    @contextmanager
    def begin_nested(self) -> Iterator[None]:
        yield


def _doc(snapshot: uuid.UUID, *, reused: bool = False) -> Any:
    doc = extract_module._Doc(
        tss_id=uuid.uuid4(),
        text_basis="abstract_only",
        envelope_snapshot_id=snapshot,
        full_text_snapshot_id=None,
        metadata={},
        primary_evidence_type=None,
        chunks=[],
    )
    doc.record_snapshot_id = snapshot
    doc.reused = reused
    return doc


def test_memo_keys_are_locked_in_sorted_order_before_the_first_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log: list[tuple[str, Any]] = []

    def record(conn: Any, **kwargs: Any) -> None:
        log.append(("write", kwargs["doc"].record_snapshot_id))

    monkeypatch.setattr(extract_module, "_write_doc", record)
    task_id = uuid.uuid4()
    docs = [_doc(uuid.uuid4(), reused=(i == 2)) for i in range(5)]
    extract_module._write_docs(
        cast(Connection, _Conn(log)),
        task_id=task_id,
        run_id=uuid.uuid4(),
        fingerprint="fp",
        docs=docs,
        created_at=datetime.now(UTC),
        profile=cast(Any, None),
    )
    written = [doc for i, doc in enumerate(docs) if i != 2]
    keys = sorted(
        extract_module._memo_lock_key(task_id, doc.record_snapshot_id, "fp") for doc in written
    )
    assert log == [
        *(("lock", key) for key in keys),
        *(("write", doc.record_snapshot_id) for doc in written),
    ]
