"""The ingest queue: messages, the queue-client seam, and the in-process client (task 057).

The full-text stage sends one message per document to a queue client (plan P9).
A message names the link row (``task_source_snapshot`` row) and the run, nothing
else: no URL and no user id ever enters the queue (owner item 2, contract N1).

Two clients implement :class:`QueueClient`:

- :class:`LocalQueueClient` (``POLICY_ATLAS_INGEST_MODE=in_process``, the default):
  ``send`` runs the per-document function on a pool of threads, each with its own
  database connection, and returns when every document is done. With
  ``workers=0`` it runs each document on the caller's thread instead (the inline
  mode the tests use with their rolled-back connection).
- :class:`SqsQueueClient` (``queued``) puts the messages on an SQS queue (Amazon
  Simple Queue Service, a managed to-do list of messages); AWS starts the ingest
  function (``policy_atlas.ops.ingest_worker``) once per message. ``send`` returns
  as soon as the queue has accepted the messages; the stage then waits for the
  documents' statuses to change, up to :data:`QUEUED_STAGE_DEADLINE_S`.
"""

from __future__ import annotations

import contextvars
import functools
import json
import os
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Protocol, TypedDict, cast

import boto3
import structlog
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy.engine import Connection

from policy_atlas.evidence_search.sourcing.ingest_document import (
    DocumentOutcome,
    ingest_document,
)
from policy_atlas.evidence_search.sourcing.ingest_full_text import (
    DEFAULT_MAX_WORKERS,
    PARSE_TIMEOUT_SECONDS,
    THIN_TEXT_MIN_CHARS,
    ConnectFactory,
    DocumentFetcher,
    parse_and_segment,
)

log = structlog.get_logger()

#: The message layout's version. Version 1 carries two ids and nothing else, ever.
MESSAGE_SCHEMA = 1

#: How long the stage waits for queued documents, from the first send (D4).
#: A document still being read then is marked ``not_ready`` and tried again on
#: the next run.
QUEUED_STAGE_DEADLINE_S = 600.0
#: SQS takes at most 10 messages per ``SendMessageBatch`` call.
SQS_BATCH_SIZE = 10
#: The SQS client's waits and retries: give up on a connection or a response
#: after 10 s, and let botocore try each call up to 3 times.
SQS_CLIENT_CONFIG = Config(
    connect_timeout=10, read_timeout=10, retries={"mode": "standard", "max_attempts": 3}
)


class IngestMessage(TypedDict):
    """One document to ingest: its link row and the run that asked for it.

    Attributes:
        link_row_id: The ``task_source_snapshot`` row id, as text.
        run_id: The run id, as text.
        schema: The message layout version (``MESSAGE_SCHEMA``).
    """

    link_row_id: str
    run_id: str
    schema: int


def new_message(*, link_row_id: uuid.UUID, run_id: uuid.UUID) -> IngestMessage:
    """Build the message for one document.

    Args:
        link_row_id: The link row to ingest.
        run_id: The run.

    Returns:
        The message.
    """
    return {"link_row_id": str(link_row_id), "run_id": str(run_id), "schema": MESSAGE_SCHEMA}


@dataclass(frozen=True)
class SendResult:
    """What a ``send`` did with each message.

    Attributes:
        sent: Link row ids whose message was accepted.
        failed: Link row id -> reason, for messages the queue refused.
        outcomes: The per-document outcomes, when the client ran the documents
            itself (the local client); None when it only queued them.
    """

    sent: list[str]
    failed: dict[str, str] = field(default_factory=dict)
    outcomes: list[DocumentOutcome] | None = None


class QueueClient(Protocol):
    """Where the full-text stage sends its messages."""

    def send(self, messages: Sequence[IngestMessage]) -> SendResult:
        """Hand the messages over.

        Args:
            messages: One message per document, in eligible-set order.

        Returns:
            Which messages were sent and which failed.
        """
        ...


#: The per-document handler a local client runs: given a connection factory and a
#: message, ingest the document.
IngestHandler = Callable[[ConnectFactory, IngestMessage], DocumentOutcome]


def make_ingest_handler(
    fetcher: DocumentFetcher,
    *,
    parse_fn: Callable[[bytes, str, int], dict[str, Any]] = parse_and_segment,
    parse_timeout: float = PARSE_TIMEOUT_SECONDS,
    thin_min: int = THIN_TEXT_MIN_CHARS,
) -> IngestHandler:
    """Build the in-process handler: one message -> one ``ingest_document`` call.

    Args:
        fetcher: The ``DocumentFetcher`` seam.
        parse_fn: Parse callable (a test seam).
        parse_timeout: Hard per-document parse timeout in seconds.
        thin_min: Thin-text guard threshold in characters.

    Returns:
        The handler. In process there is no deadline (D4).
    """

    def handle(connect: ConnectFactory, message: IngestMessage) -> DocumentOutcome:
        if message.get("schema") != MESSAGE_SCHEMA:
            raise ValueError(f"unknown ingest message schema {message.get('schema')!r}")
        return ingest_document(
            connect,
            tss_id=uuid.UUID(message["link_row_id"]),
            run_id=uuid.UUID(message["run_id"]),
            fetcher=fetcher,
            parse_fn=parse_fn,
            deadline=None,
            parse_timeout=parse_timeout,
            thin_min=thin_min,
        )

    return handle


class LocalQueueClient:
    """The in-process queue: ``send`` ingests the documents itself.

    With ``workers > 0`` the documents run on a pool of that many threads; each
    thread opens its own connections through ``connect`` (a SQLAlchemy connection
    is not thread-safe, finding 17) and commits per document, so both ingest modes
    have the same commit behaviour. ``send`` returns when every document is done;
    if any handler raised, the first error is raised after the rest have finished.

    With ``workers == 0`` (inline mode) each document runs on the caller's thread,
    one after another; used with ``inline_connect`` on a test's rolled-back
    connection.

    Args:
        handler: The per-document handler (``make_ingest_handler``).
        connect: Opens one short transaction that commits on exit.
        workers: Threads; 0 for inline.
    """

    def __init__(self, handler: IngestHandler, connect: ConnectFactory, workers: int) -> None:
        if workers < 0:
            raise ValueError("workers must be >= 0")
        self._handler = handler
        self._connect = connect
        self._workers = workers

    @property
    def inline(self) -> bool:
        """True when documents run on the caller's thread (``workers == 0``)."""
        return self._workers == 0

    @property
    def workers(self) -> int:
        """The number of threads (0 when inline)."""
        return self._workers

    def send(self, messages: Sequence[IngestMessage]) -> SendResult:
        """Ingest every message's document, then return.

        Args:
            messages: One message per document.

        Returns:
            Every message as sent, with the outcomes in message order.

        Raises:
            Exception: The first error a handler raised (after all have finished).
        """
        if self.inline:
            outcomes = [self._handler(self._connect, message) for message in messages]
        else:
            with ThreadPoolExecutor(
                max_workers=self._workers, thread_name_prefix="policy-atlas-ingest"
            ) as pool:
                # task 057 review (code-review 3): each document runs in a fresh
                # copy of the caller's contextvars (structlog run binding, Langfuse).
                futures: list[Future[DocumentOutcome]] = [
                    pool.submit(
                        contextvars.copy_context().run, self._handler, self._connect, message
                    )
                    for message in messages
                ]
            errors = [f.exception() for f in futures if f.exception() is not None]
            if errors:
                raise cast(BaseException, errors[0])
            outcomes = [f.result() for f in futures]
        return SendResult(
            sent=[message["link_row_id"] for message in messages], outcomes=outcomes
        )


class SqsClient(Protocol):
    """The one SQS call the queue client makes (boto3's ``sqs`` client).

    A protocol rather than the generated stub type: the project's boto3 type
    stubs cover only the services it already typed (``ops/environment.py`` does
    the same for STS), and a test passes a small fake instead.
    """

    def send_message_batch(
        self, *, QueueUrl: str, Entries: list[dict[str, str]]  # noqa: N803 - boto3's names
    ) -> Mapping[str, Any]:
        """Send up to 10 messages; returns ``Successful`` and ``Failed`` entries."""
        ...


@functools.cache  # task 057 review (code-review 6): one client per process (thread-safe)
def sqs_client() -> SqsClient:
    """Build the SQS client once with :data:`SQS_CLIENT_CONFIG` (region from ``AWS_REGION``).

    Returns:
        The boto3 ``sqs`` client, shared by every caller in the process.
    """
    client: SqsClient = boto3.client(
        "sqs",
        region_name=os.environ.get("AWS_REGION") or "eu-west-2",
        config=SQS_CLIENT_CONFIG,
    )
    return client


class SqsQueueClient:
    """The cloud queue: ``send`` puts one message per document on an SQS queue.

    Messages go out in batches of 10 (``SendMessageBatch``). The body is the
    message's JSON (two ids and the schema version, nothing else). A message the
    queue refuses comes back in :attr:`SendResult.failed` with the queue's reason,
    and the stage marks its row ``fetch_failed`` / ``send_failed``; a batch whose
    whole call the queue refuses (a ``ClientError``, after botocore's retries) is
    reported the same way, so one bad call never fails the run. A batch whose
    call ended without an answer (a ``BotoCoreError``, such as a read timeout)
    may have been accepted, so it is reported neither sent nor failed: the
    stage's deadline closes those rows ``not_ready`` if no message arrives.

    Args:
        queue_url: The queue's URL (``POLICY_ATLAS_INGEST_QUEUE_URL``).
        client: The SQS client; None builds one (:func:`sqs_client`).

    Attributes:
        stage_deadline_s: How long the stage waits for these documents
            (:data:`QUEUED_STAGE_DEADLINE_S`).
    """

    stage_deadline_s: float = QUEUED_STAGE_DEADLINE_S

    def __init__(self, queue_url: str, client: SqsClient | None = None) -> None:
        if not queue_url:
            raise ValueError("SqsQueueClient needs a queue URL")
        self.queue_url = queue_url
        self._client = client if client is not None else sqs_client()

    def send(self, messages: Sequence[IngestMessage]) -> SendResult:
        """Put the messages on the queue, 10 per call.

        Args:
            messages: One message per document.

        Returns:
            The link row ids the queue accepted, and the refused ones with the
            queue's reason (a batch with an unknown fate is in neither).
            ``outcomes`` is None: the function reports through the link rows,
            not here.
        """
        sent: list[str] = []
        failed: dict[str, str] = {}
        unknown = 0
        for start in range(0, len(messages), SQS_BATCH_SIZE):
            group = messages[start:start + SQS_BATCH_SIZE]
            # Entry ids only need to be unique within one call; positions are.
            by_entry = {str(i): message["link_row_id"] for i, message in enumerate(group)}
            entries = [
                {
                    "Id": str(i),
                    "MessageBody": json.dumps(dict(message), separators=(",", ":")),
                }
                for i, message in enumerate(group)
            ]
            try:
                response = self._client.send_message_batch(
                    QueueUrl=self.queue_url, Entries=entries
                )
            except ClientError as exc:
                reason = str(exc.response.get("Error", {}).get("Code") or "ClientError")
                failed.update(dict.fromkeys(by_entry.values(), reason))
                continue
            except BotoCoreError as exc:
                # task 057 review (Codex 2): no answer (e.g. a read timeout after
                # SQS accepted the batch); closing the rows now would lose the
                # document when its accepted message later no-ops.
                unknown += len(group)
                log.warning(
                    "ingest.queue_send_unknown", count=len(group), error_type=type(exc).__name__
                )
                continue
            for entry in response.get("Successful", []):
                sent.append(by_entry[entry["Id"]])
            for entry in response.get("Failed", []):
                failed[by_entry[entry["Id"]]] = str(entry.get("Code") or "failed")
        if failed:
            log.warning("ingest.queue_send_refused", count=len(failed), reasons=sorted(
                set(failed.values())
            ))
        log.info("ingest.queue_sent", sent=len(sent), failed=len(failed), unknown=unknown)
        return SendResult(sent=sent, failed=failed)


@contextmanager
def _savepoint(conn: Connection) -> Iterator[Connection]:
    with conn.begin_nested():
        yield conn


def inline_connect(conn: Connection) -> ConnectFactory:
    """A connection factory that hands back ``conn`` inside a savepoint.

    Pairs with the inline local client: "a short transaction that commits" is a
    savepoint released on the caller's connection, so a test's rolled-back
    connection still rolls everything back.

    Args:
        conn: The caller's open connection.

    Returns:
        The factory.
    """
    return lambda: _savepoint(conn)


def build_queue_client(
    mode: str,
    *,
    connect: ConnectFactory,
    fetcher: DocumentFetcher,
    workers: int = DEFAULT_MAX_WORKERS,
    queue_url: str | None = None,
    sqs: SqsClient | None = None,
) -> QueueClient:
    """Build the queue client for an ingest mode.

    Args:
        mode: ``in_process`` or ``queued``.
        connect: Opens one short transaction that commits on exit (``engine.begin``).
        fetcher: The ``DocumentFetcher`` seam the in-process handler fetches with.
        workers: Threads for the in-process client.
        queue_url: The SQS queue URL; required for ``queued``.
        sqs: The SQS client for ``queued`` (a test seam); None builds one.

    Returns:
        The client.

    Raises:
        RuntimeError: ``queued`` without a queue URL.
        ValueError: An unknown mode.
    """
    if mode == "in_process":
        return LocalQueueClient(make_ingest_handler(fetcher), connect, workers)
    if mode == "queued":
        if not queue_url:
            raise RuntimeError(
                "POLICY_ATLAS_INGEST_MODE=queued needs POLICY_ATLAS_INGEST_QUEUE_URL"
            )
        return SqsQueueClient(queue_url, client=sqs)
    raise ValueError(f"unknown ingest mode {mode!r}")
