"""The queued ingest function's handler (task 057, P10), on the test database.

No AWS call anywhere: the SQS event and the Lambda context are plain fakes, the
Secrets Manager client is a fake, and the documents come from a scripted fetcher.
These tests commit (the handler opens its own connections) and remove what they
committed.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import pytest
import structlog
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import NullPool
from structlog.testing import capture_logs

from policy_atlas.core.schema import chunk as chunk_table
from policy_atlas.core.schema import chunk_embedding, source_snapshot, task_source_snapshot
from policy_atlas.evidence_search.sourcing.ingest_full_text import FetchResult
from policy_atlas.evidence_search.sourcing.ingest_queue import new_message
from policy_atlas.ops import ingest_worker
from tests.evidence_search.sourcing.test_ingest_full_text import (
    _ScriptedFetcher,
    _seed_relevant_acquired,
)
from tests.helpers import delete_task_data, seed_scope, seed_task_and_run


class _PgError(Exception):
    """A driver error carrying a PostgreSQL error code, as psycopg's do."""

    def __init__(self, sqlstate: str) -> None:
        super().__init__(sqlstate)
        self.sqlstate = sqlstate


class _Context:
    def __init__(self, remaining_ms: int = 170_000) -> None:
        self.remaining_ms = remaining_ms

    def get_remaining_time_in_millis(self) -> int:
        return self.remaining_ms


def _event(body: str, *, attempt: int, message_id: str = "msg-1") -> dict[str, Any]:
    return {
        "Records": [
            {
                "messageId": message_id,
                "body": body,
                "attributes": {"ApproximateReceiveCount": str(attempt)},
                "eventSource": "aws:sqs",
            }
        ]
    }


@contextmanager
def _committed(engine: Engine) -> Iterator[Connection]:
    with engine.connect() as c:
        yield c
        c.commit()


def _body_text() -> bytes:
    """Unique, plainly parseable text well over the 200-character thin-text floor."""
    para = "Housing first programmes reduced rough sleeping in the evaluated cities. " * 4
    return f"{uuid.uuid4()}\n\n{para}\n\n{para}".encode()


class _Doc:
    """One committed task with one queued document whose URL serves ``result``."""

    def __init__(self, engine: Engine, result: FetchResult) -> None:
        self.url = f"https://example.org/worker-{uuid.uuid4()}.txt?token=SECRET"
        with _committed(engine) as c:
            self.task_id, self.run_id = seed_task_and_run(c)
            scope_id = seed_scope(c, self.task_id)
            self.tss_id = _seed_relevant_acquired(
                c, self.task_id, self.run_id, scope_id,
                {"backend": "overton", "provider_fields": {"pdf_url": self.url}},
            )
            c.execute(
                task_source_snapshot.update()
                .where(task_source_snapshot.c.task_source_snapshot_id == self.tss_id)
                .values(full_text_status="queued")
            )
        self.fetcher = _ScriptedFetcher({self.url: result})
        self.body = json.dumps(dict(new_message(link_row_id=self.tss_id, run_id=self.run_id)))

    def row(self, engine: Engine) -> Any:
        with engine.connect() as c:
            return c.execute(
                select(task_source_snapshot).where(
                    task_source_snapshot.c.task_source_snapshot_id == self.tss_id
                )
            ).one()


def _cleanup(engine: Engine, doc: _Doc, bodies: list[bytes]) -> None:
    hashes = [hashlib.sha256(b).hexdigest() for b in bodies]
    with _committed(engine) as c:
        c.execute(
            task_source_snapshot.update()
            .where(task_source_snapshot.c.task_id == doc.task_id)
            .values(full_text_snapshot_id=None, full_text_status="not_attempted",
                    full_text_error=None)
        )
        delete_task_data(c, doc.task_id)
        if hashes:
            snaps = select(source_snapshot.c.source_snapshot_id).where(
                source_snapshot.c.body_hash.in_(hashes)
            )
            chunks = select(chunk_table.c.chunk_id).where(
                chunk_table.c.source_snapshot_id.in_(snaps)
            )
            c.execute(chunk_embedding.delete().where(chunk_embedding.c.chunk_id.in_(chunks)))
            c.execute(chunk_table.delete().where(chunk_table.c.source_snapshot_id.in_(snaps)))
            c.execute(source_snapshot.delete().where(source_snapshot.c.body_hash.in_(hashes)))


@pytest.fixture
def use_worker(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Install a warm container (engine + fetcher) so no secret is read."""

    def install(fetcher: Any) -> None:
        monkeypatch.setattr(
            ingest_worker, "_WORKER", ingest_worker._Worker(engine=engine, fetcher=fetcher)
        )

    return install


NO_FAILURES: dict[str, list[dict[str, str]]] = {"batchItemFailures": []}


def _retry(message_id: str = "msg-1") -> dict[str, list[dict[str, str]]]:
    return {"batchItemFailures": [{"itemIdentifier": message_id}]}


def test_ingested_then_a_redelivery_is_not_queued(engine: Engine, use_worker: Any) -> None:
    """The document is fetched, parsed and linked; a second delivery of the same
    message finds the row no longer ``queued`` and does nothing. Only the message
    id and the two uuids are logged; the URL's query string never is."""
    body = _body_text()
    doc = _Doc(engine, FetchResult(status="ok", content_type="text/plain", body=body))
    try:
        use_worker(doc.fetcher)
        with capture_logs(processors=[structlog.contextvars.merge_contextvars]) as logs:
            assert ingest_worker.handler(_event(doc.body, attempt=1), _Context()) == NO_FAILURES
        row = doc.row(engine)
        assert row.full_text_status == "ingested" and row.full_text_snapshot_id is not None
        [done] = [e for e in logs if e["event"] == "ingest_worker.done"]
        assert (done["resolution"], done["written"], done["redeliver"]) == ("ingested", True, False)
        assert (done["message_id"], done["tss_id"], done["run_id"]) == (
            "msg-1", str(doc.tss_id), str(doc.run_id)
        )
        assert "SECRET" not in repr(logs)

        with capture_logs() as logs:
            assert ingest_worker.handler(_event(doc.body, attempt=2), _Context()) == NO_FAILURES
        [done] = [e for e in logs if e["event"] == "ingest_worker.done"]
        assert done["resolution"] == "not_queued"
        assert doc.row(engine).full_text_snapshot_id == row.full_text_snapshot_id
    finally:
        _cleanup(engine, doc, [body])


def test_a_document_failure_is_written_with_its_reason_on_the_first_delivery(
    engine: Engine, use_worker: Any
) -> None:
    doc = _Doc(engine, FetchResult(status="error", error="not_found"))
    try:
        use_worker(doc.fetcher)
        assert ingest_worker.handler(_event(doc.body, attempt=1), _Context()) == NO_FAILURES
        row = doc.row(engine)
        assert (row.full_text_status, row.full_text_error) == ("fetch_failed", "not_found")
    finally:
        _cleanup(engine, doc, [])


def test_a_retryable_failure_waits_for_the_second_delivery_then_is_written(
    engine: Engine, use_worker: Any
) -> None:
    """Attempt 1: a network failure leaves the row ``queued`` and reports the
    record, so SQS delivers it again. Attempt 2: the reason is written and the
    record is not reported (it will not reach the dead-letter queue)."""
    doc = _Doc(engine, FetchResult(status="error", error="timeout"))
    try:
        use_worker(doc.fetcher)
        assert ingest_worker.handler(_event(doc.body, attempt=1), _Context()) == _retry()
        assert doc.row(engine).full_text_status == "queued"
        assert ingest_worker.handler(_event(doc.body, attempt=2), _Context()) == NO_FAILURES
        row = doc.row(engine)
        assert (row.full_text_status, row.full_text_error) == ("fetch_failed", "timeout")
    finally:
        _cleanup(engine, doc, [])


def test_no_time_left_is_a_deadline_cut_and_retryable(engine: Engine, use_worker: Any) -> None:
    """The deadline is Lambda's remaining time less 10 s: with 12 s left nothing
    is started (5 s margin), and the first delivery is handed back to the queue."""
    body = _body_text()
    doc = _Doc(engine, FetchResult(status="ok", content_type="text/plain", body=body))
    try:
        use_worker(doc.fetcher)
        result = ingest_worker.handler(_event(doc.body, attempt=1), _Context(remaining_ms=12_000))
        assert result == _retry()
        assert doc.fetcher.calls == []
        assert doc.row(engine).full_text_status == "queued"
    finally:
        _cleanup(engine, doc, [body])


_A, _B = "0b6f0d0e-5c0e-4b1e-9b0a-6c1f9e0d2a11", "5f0e2c1a-8b7d-4e6f-a1c2-3d4e5f607182"


@pytest.mark.parametrize(
    "body",
    [
        "not json",
        json.dumps({"link_row_id": _A, "run_id": _B}),
        json.dumps({"link_row_id": _A, "run_id": _B, "schema": 2}),
        json.dumps({"link_row_id": "x", "run_id": _B, "schema": 1}),
        json.dumps({
            "link_row_id": _A, "run_id": _B, "schema": 1, "url": "https://example.org/a.pdf",
        }),
    ],
    ids=["not-json", "no-schema", "schema-2", "bad-uuid", "extra-key"],
)
def test_a_malformed_body_is_reported_so_it_dead_letters(body: str, use_worker: Any) -> None:
    use_worker(_ScriptedFetcher({}))
    with capture_logs() as logs:
        assert ingest_worker.handler(_event(body, attempt=1), _Context()) == _retry()
    assert [e["event"] for e in logs if e["log_level"] == "error"] == [
        "ingest_worker.malformed_message"
    ]


def test_more_than_one_record_is_an_error(use_worker: Any) -> None:
    use_worker(_ScriptedFetcher({}))
    event = _event("{}", attempt=1)
    event["Records"].append(dict(event["Records"][0], messageId="msg-2"))
    with pytest.raises(ValueError, match="exactly one SQS record, got 2"):
        ingest_worker.handler(event, _Context())
    with pytest.raises(ValueError, match="got 0"):
        ingest_worker.handler({"Records": []}, _Context())


def test_a_snapshot_deleted_under_the_link_write_is_retryable(
    engine: Engine, monkeypatch: pytest.MonkeyPatch, use_worker: Any
) -> None:
    """A foreign-key failure on the link write (the retention script deleted the
    stored snapshot between the lookup and the write) is reported for
    redelivery on attempt 1; on attempt 2 the handler tries once more at once."""
    use_worker(_ScriptedFetcher({}))
    fk = IntegrityError("UPDATE task_source_snapshot", {}, _PgError("23503"))
    calls: list[str] = []
    outcome = SimpleNamespace(
        resolution="ingested", reason=None, retryable=False, written=True, already_in_store=False
    )

    def fake_ingest(*_args: Any, on_retryable_failure: str, **_kwargs: Any) -> Any:
        calls.append(on_retryable_failure)
        if len(calls) in (1, 2):
            raise fk
        return outcome

    monkeypatch.setattr(ingest_worker, "ingest_document", fake_ingest)
    body = json.dumps(dict(new_message(link_row_id=uuid.uuid4(), run_id=uuid.uuid4())))
    assert ingest_worker.handler(_event(body, attempt=1), _Context()) == _retry()
    assert ingest_worker.handler(_event(body, attempt=2), _Context()) == NO_FAILURES
    assert calls == ["leave_queued", "write", "write"]

    other = IntegrityError("INSERT", {}, _PgError("23505"))
    monkeypatch.setattr(
        ingest_worker, "ingest_document", lambda *_a, **_k: (_ for _ in ()).throw(other)
    )
    with pytest.raises(IntegrityError):
        ingest_worker.handler(_event(body, attempt=1), _Context())


class _FakeSecrets:
    def __init__(self, secret: Mapping[str, Any]) -> None:
        self.secret = secret
        self.calls: list[str] = []

    def get_secret_value(self, *, SecretId: str) -> Mapping[str, Any]:  # noqa: N803
        self.calls.append(SecretId)
        return {"SecretString": json.dumps(self.secret)}


def test_cold_start_reads_the_database_secret_once_and_keeps_no_pool(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    arn = "arn:aws:secretsmanager:eu-west-2:000000000000:secret:db"
    secrets = _FakeSecrets(
        {"db_connection_string": engine.url.render_as_string(hide_password=False)}
    )
    monkeypatch.setattr(ingest_worker, "_WORKER", None)
    monkeypatch.delenv(ingest_worker.DB_SECRET_ARN_ENV, raising=False)
    with pytest.raises(RuntimeError, match="POLICY_ATLAS_DB_SECRET_ARN is not set"):
        ingest_worker._worker(secrets=lambda: secrets, fetcher=lambda: _ScriptedFetcher({}))

    monkeypatch.setenv(ingest_worker.DB_SECRET_ARN_ENV, arn)
    first = ingest_worker._worker(secrets=lambda: secrets, fetcher=lambda: _ScriptedFetcher({}))
    second = ingest_worker._worker(secrets=lambda: secrets, fetcher=lambda: _ScriptedFetcher({}))
    try:
        assert first is second and secrets.calls == [arn]
        assert isinstance(first.engine.pool, NullPool)
        with first.engine.connect() as c:
            assert c.exec_driver_sql("select 1").scalar_one() == 1
    finally:
        first.engine.dispose()


def test_a_secret_without_the_field_fails_loud() -> None:
    with pytest.raises(RuntimeError, match="db_connection_string"):
        ingest_worker.database_url_from_secret(_FakeSecrets({"password": "x"}), "arn")


def test_log_lines_carry_urls_without_their_query_strings() -> None:
    event = ingest_worker.redact_urls(None, "info", {
        "event": "x",
        "url": "https://example.org/a.pdf?token=SECRET",
        "attempts": ["https://example.org/b.pdf?sig=SECRET: timeout"],
        "n": 3,
    })
    assert event["url"] == "https://example.org/a.pdf"
    assert event["attempts"] == ["https://example.org/b.pdf: timeout"]
    assert "SECRET" not in repr(event)


def test_importing_the_handler_pulls_in_neither_the_cli_nor_the_runtime() -> None:
    """The image leaves out the CLI's dependency group (its Cognito type stubs);
    the handler must import without it, and without the runtime package."""
    code = (
        "import sys\n"
        "sys.modules['mypy_boto3_cognito_idp'] = None\n"
        "import policy_atlas.ops.ingest_worker\n"
        "bad = sorted(m for m in sys.modules if m.startswith(("
        "'policy_atlas.ops.cli', 'policy_atlas.ops.commands', 'policy_atlas.runtime')))\n"
        "assert not bad, bad\n"
    )
    done = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=120, check=False
    )
    assert done.returncode == 0, done.stderr[-2000:]
