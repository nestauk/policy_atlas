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
- The cloud client (``queued``) puts the messages on an SQS queue that a function
  reads; it is built in task 057 Phase 4b (``SqsQueueClient``, here).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Protocol, TypedDict, cast

import structlog
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
                futures: list[Future[DocumentOutcome]] = [
                    pool.submit(self._handler, self._connect, message) for message in messages
                ]
            errors = [f.exception() for f in futures if f.exception() is not None]
            if errors:
                raise cast(BaseException, errors[0])
            outcomes = [f.result() for f in futures]
        return SendResult(
            sent=[message["link_row_id"] for message in messages], outcomes=outcomes
        )


# The cloud client, ``SqsQueueClient`` (boto3, batches of 10), arrives in Phase 4b.


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
) -> QueueClient:
    """Build the queue client for an ingest mode.

    Args:
        mode: ``in_process`` or ``queued``.
        connect: Opens one short transaction that commits on exit (``engine.begin``).
        fetcher: The ``DocumentFetcher`` seam the in-process handler fetches with.
        workers: Threads for the in-process client.

    Returns:
        The client.

    Raises:
        RuntimeError: ``queued`` before its client exists (task 057 Phase 4b).
        ValueError: An unknown mode.
    """
    if mode == "in_process":
        return LocalQueueClient(make_ingest_handler(fetcher), connect, workers)
    if mode == "queued":
        raise RuntimeError(
            "POLICY_ATLAS_INGEST_MODE=queued needs the cloud queue client, which is not "
            "built yet (task 057 Phase 4b); use in_process"
        )
    raise ValueError(f"unknown ingest mode {mode!r}")
