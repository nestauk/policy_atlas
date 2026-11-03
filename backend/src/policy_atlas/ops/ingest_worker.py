"""The queued ingest function's handler: one queue message, one document (task 057, P10).

In plain words: in ``queued`` mode the API puts one message per document on an
SQS queue (Amazon Simple Queue Service, a managed to-do list), and AWS Lambda
starts this handler once per message. The handler fetches the document, reads
(parses) it and writes its passages to the database, through the same
:func:`~policy_atlas.evidence_search.sourcing.ingest_document.ingest_document`
the in-process mode runs. It makes no AI model call and holds no model key
(contract D6): embedding stays in the API's run.

The function's image command is
``python -m awslambdaric policy_atlas.ops.ingest_worker.handler`` (the AWS
Lambda Runtime Interface Client, ``awslambdaric``, runs the handler inside the
backend container image).

How one message is handled:

- The event carries exactly one record (the queue's batch size is 1; more is an
  error). The body is ``{"link_row_id", "run_id", "schema": 1}`` and nothing
  else; a body that is not that is logged and reported as failed, so after its
  second delivery the queue moves it to the dead-letter queue.
- The handler's deadline is the time Lambda has left, less 10 s, so the result
  is written before Lambda stops the process.
- ``ApproximateReceiveCount`` says which delivery this is. On the first, a
  failure worth retrying (the network, the deadline, a snapshot deleted under
  the write) leaves the row ``queued`` and reports the record in
  ``batchItemFailures`` so SQS delivers it again. On the second, the handler
  writes the reason on the row and reports success, so the row never sits
  ``queued`` waiting for the stage's deadline.

Start-up ("cold start", once per Lambda container): the database address is read
from Secrets Manager (``POLICY_ATLAS_DB_SECRET_ARN``, field
``db_connection_string``, the same secret the API task reads) through the
function's own permission, never from an environment variable; the database
engine keeps no pool (``NullPool``), so each message opens and closes its own
connections. Logs are structlog JSON (``LOG_FORMAT=json``) with any URL cut to
scheme, host and path; the message id and the two uuids are the only
identifiers logged.

This module must not import the operator CLI or the runtime: the backend image
leaves out the CLI's dependency group, and the runtime's imports would slow
every cold start.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from collections.abc import Callable, Mapping, MutableMapping
from dataclasses import dataclass
from typing import Any, Protocol

import boto3
import structlog
from botocore.config import Config
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import NullPool

from policy_atlas.core.logging import configure_logging
from policy_atlas.evidence_search.sourcing.fetch_live import LiveDocumentFetcher
from policy_atlas.evidence_search.sourcing.ingest_document import (
    DocumentOutcome,
    ingest_document,
)
from policy_atlas.evidence_search.sourcing.ingest_full_text import (
    DocumentFetcher,
    _redact_url,
)
from policy_atlas.evidence_search.sourcing.ingest_queue import MESSAGE_SCHEMA

log = structlog.get_logger()

#: Seconds kept back from Lambda's remaining time, so the result is written
#: before Lambda stops the process.
DEADLINE_RESERVE_S = 10.0
#: The environment variable naming the database secret (its ARN, Amazon
#: Resource Name), and the secret's field holding the database address.
DB_SECRET_ARN_ENV = "POLICY_ATLAS_DB_SECRET_ARN"
DB_SECRET_FIELD = "db_connection_string"
#: Secrets Manager client waits and retries at cold start.
SECRETS_CLIENT_CONFIG = Config(
    connect_timeout=5, read_timeout=10, retries={"mode": "standard", "max_attempts": 3}
)
#: PostgreSQL's code for a foreign-key violation.
_FOREIGN_KEY_VIOLATION = "23503"
_MESSAGE_KEYS = frozenset({"link_row_id", "run_id", "schema"})
_URL_RE = re.compile(r"https?://[^\s\"'<>]+")
_TRAILING_PUNCTUATION = ":,.;)]"

#: What the handler returns to Lambda: the records SQS should deliver again.
BatchResponse = dict[str, list[dict[str, str]]]


class SecretsClient(Protocol):
    """The one Secrets Manager call the handler makes (boto3's client)."""

    def get_secret_value(self, *, SecretId: str) -> Mapping[str, Any]:  # noqa: N803 - boto3's name
        """Return the secret, its value under ``SecretString``."""
        ...


class LambdaContext(Protocol):
    """The part of Lambda's context object the handler reads."""

    def get_remaining_time_in_millis(self) -> int:
        """Milliseconds before Lambda stops this invocation."""
        ...


class MalformedMessage(ValueError):  # noqa: N818 - names what the message is
    """The message body is not a schema-1 ingest message."""


@dataclass(frozen=True)
class _Worker:
    """What a Lambda container builds once: the database engine and the fetcher."""

    engine: Engine
    fetcher: DocumentFetcher


_WORKER: _Worker | None = None


def secrets_client() -> SecretsClient:
    """Build the Secrets Manager client (region from ``AWS_REGION``, set by Lambda).

    Returns:
        The boto3 ``secretsmanager`` client.
    """
    client: SecretsClient = boto3.client(
        "secretsmanager",
        region_name=os.environ.get("AWS_REGION") or "eu-west-2",
        config=SECRETS_CLIENT_CONFIG,
    )
    return client


def database_url_from_secret(client: SecretsClient, secret_arn: str) -> str:
    """Read the database address from the database secret.

    Args:
        client: The Secrets Manager client.
        secret_arn: The secret's ARN.

    Returns:
        The SQLAlchemy database URL.

    Raises:
        RuntimeError: The secret has no ``db_connection_string`` text field.
    """
    response = client.get_secret_value(SecretId=secret_arn)
    try:
        value = json.loads(response["SecretString"])[DB_SECRET_FIELD]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"the database secret has no {DB_SECRET_FIELD!r} field") from exc
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"the database secret's {DB_SECRET_FIELD!r} field is empty")
    return value


def _redact_match(match: re.Match[str]) -> str:
    url = match.group(0)
    kept = url.rstrip(_TRAILING_PUNCTUATION)  # "…/a.pdf?x=1: timeout" keeps its ":"
    return (_redact_url(kept) or "") + url[len(kept):]


def _redact_urls_in(value: Any) -> Any:
    if isinstance(value, str) and "://" in value:
        return _URL_RE.sub(_redact_match, value)
    if isinstance(value, list):
        return [_redact_urls_in(item) for item in value]
    return value


def redact_urls(
    _logger: Any, _method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """structlog processor: cut every URL in a log line to scheme, host and path.

    The ingest code already logs URLs this way; this catches any that do not
    (a query string can carry a token).
    """
    for key, value in list(event_dict.items()):
        event_dict[key] = _redact_urls_in(value)
    return event_dict


def _configure_worker_logging() -> None:
    """The product's logging setup, plus :func:`redact_urls` before the renderer."""
    configure_logging()
    processors = list(structlog.get_config()["processors"])
    processors.insert(len(processors) - 1, redact_urls)
    structlog.configure(processors=processors)


def _worker(
    *,
    secrets: Callable[[], SecretsClient] = secrets_client,
    fetcher: Callable[[], DocumentFetcher] = LiveDocumentFetcher,
) -> _Worker:
    """Build the container's engine and fetcher once (the cold start), then reuse them.

    Raises:
        RuntimeError: ``POLICY_ATLAS_DB_SECRET_ARN`` is unset.
    """
    global _WORKER
    if _WORKER is None:
        _configure_worker_logging()
        secret_arn = os.environ.get(DB_SECRET_ARN_ENV)
        if not secret_arn:
            raise RuntimeError(f"{DB_SECRET_ARN_ENV} is not set")
        url = database_url_from_secret(secrets(), secret_arn)
        # No pool: one invocation at a time per container, connections closed
        # on return (contract N5).
        _WORKER = _Worker(engine=create_engine(url, poolclass=NullPool), fetcher=fetcher())
        log.info("ingest_worker.cold_start")
    return _WORKER


def parse_message(body: str) -> tuple[uuid.UUID, uuid.UUID]:
    """Read a schema-1 message body.

    Args:
        body: The SQS message body.

    Returns:
        The link row id and the run id.

    Raises:
        MalformedMessage: Not JSON, other keys than the three, another schema
            version, or ids that are not uuids.
    """
    try:
        data = json.loads(body)
    except (TypeError, json.JSONDecodeError) as exc:
        raise MalformedMessage("not JSON") from exc
    if not isinstance(data, dict) or set(data) != _MESSAGE_KEYS:
        raise MalformedMessage("not the schema-1 keys")
    if data["schema"] != MESSAGE_SCHEMA or isinstance(data["schema"], bool):
        raise MalformedMessage(f"unknown schema {data['schema']!r}")
    try:
        return uuid.UUID(str(data["link_row_id"])), uuid.UUID(str(data["run_id"]))
    except ValueError as exc:
        raise MalformedMessage("an id is not a uuid") from exc


def _is_foreign_key_violation(exc: IntegrityError) -> bool:
    return getattr(exc.orig, "sqlstate", None) == _FOREIGN_KEY_VIOLATION


def _ingest(
    worker: _Worker, *, tss_id: uuid.UUID, run_id: uuid.UUID, deadline: float, attempt: int
) -> DocumentOutcome | None:
    """Run ``ingest_document``; None when the link write hit a deleted snapshot.

    A store hit links an existing snapshot by id; if the retention script
    deleted that snapshot between the lookup and the write, the write fails on
    the foreign key. That is worth a retry (the next try parses afresh), so it
    is reported like any other retryable failure.
    """
    try:
        return ingest_document(
            worker.engine.begin,
            tss_id=tss_id,
            run_id=run_id,
            fetcher=worker.fetcher,
            deadline=deadline,
            on_retryable_failure="leave_queued" if attempt == 1 else "write",
        )
    except IntegrityError as exc:
        if not _is_foreign_key_violation(exc):
            raise
        log.warning("ingest_worker.snapshot_pruned_under_write", attempt=attempt)
        return None


def handler(event: Mapping[str, Any], context: LambdaContext) -> BatchResponse:
    """Handle one SQS message: ingest its document (see the module docstring).

    Args:
        event: The SQS event, with exactly one record.
        context: Lambda's context (the remaining time).

    Returns:
        ``{"batchItemFailures": [...]}``: the record when SQS should deliver it
        again (a malformed body, or a retryable failure on the first delivery),
        else an empty list.

    Raises:
        ValueError: The event does not carry exactly one record.
    """
    records = event.get("Records")
    if not isinstance(records, list) or len(records) != 1:
        count = len(records) if isinstance(records, list) else None
        raise ValueError(f"the ingest function takes exactly one SQS record, got {count}")
    record = records[0]
    message_id = str(record["messageId"])
    attempt = int(record["attributes"]["ApproximateReceiveCount"])
    deadline = (
        time.monotonic() + context.get_remaining_time_in_millis() / 1000 - DEADLINE_RESERVE_S
    )
    retry_record: BatchResponse = {"batchItemFailures": [{"itemIdentifier": message_id}]}

    with structlog.contextvars.bound_contextvars(message_id=message_id, attempt=attempt):
        worker = _worker()
        try:
            tss_id, run_id = parse_message(record.get("body"))
        except MalformedMessage as exc:
            log.error("ingest_worker.malformed_message", error=str(exc))
            return retry_record

        with structlog.contextvars.bound_contextvars(tss_id=str(tss_id), run_id=str(run_id)):
            outcome = _ingest(
                worker, tss_id=tss_id, run_id=run_id, deadline=deadline, attempt=attempt
            )
            if outcome is None and attempt > 1:
                # The second delivery: try once more now (the deleted snapshot is
                # no longer found by key, so this parses afresh) rather than
                # leave the row for the stage's deadline.
                outcome = _ingest(
                    worker, tss_id=tss_id, run_id=run_id, deadline=deadline, attempt=attempt
                )
            if outcome is None:
                retry = True
            else:
                retry = attempt == 1 and outcome.retryable and not outcome.written
            log.info(
                "ingest_worker.done",
                resolution=None if outcome is None else outcome.resolution,
                reason=None if outcome is None else outcome.reason,
                retryable=True if outcome is None else outcome.retryable,
                written=False if outcome is None else outcome.written,
                already_in_store=None if outcome is None else outcome.already_in_store,
                redeliver=retry,
            )
    return retry_record if retry else {"batchItemFailures": []}
