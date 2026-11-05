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
  failure worth retrying (the network, the deadline) or an unexpected error
  leaves the row ``queued`` and reports the record in ``batchItemFailures`` so
  SQS delivers it again. On the second, the handler writes the reason on the
  row and reports success, so the row never sits ``queued`` waiting for the
  stage's deadline; an unexpected error there writes ``fetch_failed`` /
  ``worker_error`` and raises an error that names only the error's type (no
  SQL, parameters or URLs reach the logs).

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
import random
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
from sqlalchemy.pool import NullPool

from policy_atlas.core.logging import configure_logging
from policy_atlas.evidence_search.sourcing.fetch_live import LiveDocumentFetcher
from policy_atlas.evidence_search.sourcing.ingest_document import (
    DocumentOutcome,
    _write_failed,
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
#: A message handed back for a retry comes again after this many seconds (a random
#: value in the range), not after the queue's own 210 s wait. The first try is over
#: by then, so the message cannot arrive while it still runs; a host that was
#: throttling us has had time to recover, and the stage does not wait minutes.
RETRY_DELAY_RANGE_S = (30, 60)
#: The retry-delay call must end inside the ``DEADLINE_RESERVE_S`` kept back before
#: Lambda stops the function: one attempt, at most 2 s to connect and 3 s to answer.
SQS_CLIENT_CONFIG = Config(
    connect_timeout=2, read_timeout=3, retries={"mode": "standard", "max_attempts": 1}
)
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


def sqs_client() -> Any:
    """Build the SQS client (region from ``AWS_REGION``, set by Lambda).

    Returns:
        The boto3 ``sqs`` client.
    """
    return boto3.client(
        "sqs",
        region_name=os.environ.get("AWS_REGION") or "eu-west-2",
        config=SQS_CLIENT_CONFIG,
    )


def _delay_redelivery(record: Mapping[str, Any]) -> None:
    """Ask SQS to deliver this message again after ``RETRY_DELAY_RANGE_S`` seconds.

    Without this, SQS waits the queue's full visibility timeout (210 s) before it
    delivers a retried message. The function's role already holds
    ``sqs:ChangeMessageVisibility`` (the queue event source grants it). If the call
    fails for any reason the message is still retried, only later, so the error is
    logged and not raised.

    Args:
        record: The SQS record being handed back (its queue ARN and receipt handle).
    """
    try:
        region, account, name = str(record["eventSourceARN"]).split(":")[3:6]
        sqs_client().change_message_visibility(
            QueueUrl=f"https://sqs.{region}.amazonaws.com/{account}/{name}",
            ReceiptHandle=record["receiptHandle"],
            VisibilityTimeout=round(random.uniform(*RETRY_DELAY_RANGE_S)),  # noqa: S311
        )
    except Exception as exc:
        log.warning("ingest_worker.retry_delay_failed", error_type=type(exc).__name__)


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
    if isinstance(value, dict):  # task 057 review (security 3): nested values too
        return {key: _redact_urls_in(item) for key, item in value.items()}
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


def _ingest(
    worker: _Worker, *, tss_id: uuid.UUID, run_id: uuid.UUID, deadline: float, attempt: int
) -> DocumentOutcome:
    """Run ``ingest_document`` for one message (it recovers a pruned store hit itself)."""
    # task 057 review (Codex 7 / code-review 2): the prune-race recovery moved
    # into ``ingest_document``, so both ingest modes share it.
    return ingest_document(
        worker.engine.begin,
        tss_id=tss_id,
        run_id=run_id,
        fetcher=worker.fetcher,
        deadline=deadline,
        on_retryable_failure="leave_queued" if attempt == 1 else "write",
    )


def handler(event: Mapping[str, Any], context: LambdaContext) -> BatchResponse:
    """Handle one SQS message: ingest its document (see the module docstring).

    Args:
        event: The SQS event, with exactly one record.
        context: Lambda's context (the remaining time).

    Returns:
        ``{"batchItemFailures": [...]}``: the record when SQS should deliver it
        again (a malformed body, or a retryable failure or unexpected error on
        the first delivery), else an empty list.

    Raises:
        ValueError: The event does not carry exactly one record.
        RuntimeError: An unexpected error on the last delivery (after the row
            is marked ``worker_error``); it names only the error's type.
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
            try:
                outcome = _ingest(
                    worker, tss_id=tss_id, run_id=run_id, deadline=deadline, attempt=attempt
                )
            except Exception as exc:
                # task 057 review (Codex 8 / security 3): never let an unexpected
                # error's text (SQL, parameters, URLs) reach the logs, and on the
                # last delivery (the queue's maxReceiveCount is 2) write a
                # reason-coded status before giving up (contract N2).
                if attempt < 2:
                    log.error("ingest_worker.error", error_type=type(exc).__name__)
                    return retry_record
                try:
                    _write_failed(
                        worker.engine.begin, tss_id=tss_id, run_id=run_id,
                        resolution="fetch_failed", reason="worker_error",
                    )
                except Exception as write_exc:  # best effort: the stage's deadline still closes it
                    log.error(
                        "ingest_worker.failed_write_failed",
                        error_type=type(write_exc).__name__,
                    )
                # The type only, no traceback: an escaped database error's text
                # carries SQL and parameters (chunk text, the full URL); the row's
                # reason and the dead-letter message are the diagnostics.
                log.error("ingest_worker.failed", error_type=type(exc).__name__)
                raise RuntimeError(f"ingest worker failed: {type(exc).__name__}") from None
            retry = attempt == 1 and outcome.retryable and not outcome.written
            log.info(
                "ingest_worker.done",
                resolution=outcome.resolution,
                reason=outcome.reason,
                retryable=outcome.retryable,
                written=outcome.written,
                already_in_store=outcome.already_in_store,
                redeliver=retry,
            )
    if retry:
        _delay_redelivery(record)
        return retry_record
    return {"batchItemFailures": []}
