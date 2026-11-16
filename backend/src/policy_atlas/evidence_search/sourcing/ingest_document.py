"""Ingest one document: fetch, look it up in the document store, parse, write (task 057).

This is the one function both ingest modes run for each document (plan P8): the
in-process thread pool calls it on the API's machine, and the cloud function
(Phase 4b) calls it once per queue message. It is given the id of a link row (a
``task_source_snapshot`` row) in status ``queued`` and:

1. reads the link row and its envelope snapshot's metadata (one short read; a row
   that is no longer ``queued`` is left alone, so a second delivery of the same
   message does nothing);
2. walks today's candidate cascade: Europe PMC XML first when the fetcher offers
   it, then the provider URLs, a PDF link found on a landing page, the next URL
   when a parse fails, the open-access cross-check and the reason priority;
3. hashes each fetched body and looks the store key (body hash, parse profile,
   segmentation policy) up BEFORE parsing; a hit links the existing snapshot
   without parsing again (N9);
4. otherwise parses in its own process with the 120 s kill;
5. writes the result in one short transaction whose link-row update is guarded on
   ``full_text_status = 'queued'`` and on the message's run, so a result that
   arrives after the stage closed the row, or after a later run queued it again,
   changes nothing on the row (the parsed snapshot still joins the store).

``ingested_by_run_id`` is the run that last queued the row; it is stamped at
queue time and required by the guarded writes (task 057 review, Codex 1 /
security 8). A store hit whose snapshot the retention script deleted between the
lookup and the write is parsed afresh and written again (Codex 7 / code-review 2).

No connection is held while fetching or parsing. The shared snapshot row carries
no task, user, run or URL key beyond the public document address in
``source_locator``; the run and the address the bytes came from go on the link row.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from policy_atlas.core.hashing import content_hash
from policy_atlas.core.schema import chunk as chunk_table
from policy_atlas.core.schema import source_snapshot, task_source_snapshot
from policy_atlas.evidence_search.sourcing.ingest_full_text import (
    DEADLINE_MARGIN_S,
    FAILURE_REASONS,
    FETCH_DEADLINE,
    NOT_READ_YET_REASONS,
    PARSE_TIMEOUT_SECONDS,
    THIN_TEXT_MIN_CHARS,
    ConnectFactory,
    DocumentFetcher,
    _apply_oa_cross_check,
    _DocState,
    _fetch_next_body,
    _redact_url,
    _release_fetch_body,
    _route_of,
    candidate_urls,
    europe_pmc_candidate,
    parse_and_segment,
    parse_profile_for,
    run_parse_worker,
)

log = structlog.get_logger()

Resolution = Literal["ingested", "fetch_failed", "parse_failed", "late", "not_queued"]

# Fetch reasons that say the network, not the document, failed: worth a second try.
_TRANSPORT_FETCH_REASONS = frozenset({"timeout", "fetch_error"})
#: PostgreSQL's code for a foreign-key violation.
_FOREIGN_KEY_VIOLATION = "23503"


@dataclass(frozen=True)
class DocumentOutcome:
    """What one call of :func:`ingest_document` did.

    Attributes:
        tss_id: The link row.
        resolution: ``ingested`` | ``fetch_failed`` | ``parse_failed``, or
            ``late`` (the work finished but the row was no longer ``queued``, so
            nothing on the row changed) or ``not_queued`` (the row was not
            ``queued`` when the call began; nothing was done).
        reason: The failure reason (closed vocabulary), else None. The
            not-read-yet reasons (``not_ready``, ``send_failed``,
            ``worker_error``) are the stage's or the handler's, never this
            function's.
        already_in_store: True when an existing snapshot was linked by store key
            and nothing was parsed.
        retryable: True for a transport-level fetch failure (``timeout``,
            ``fetch_error``) or a cut at the deadline.
        route: ``europe_pmc_xml`` | ``pdf`` | ``html`` | ``plain`` when ingested.
        bytes_fetched: Bytes received over every attempt.
        attempts: Redacted URL attempts, for the log only.
        written: True when this call changed the link row.
    """

    tss_id: uuid.UUID
    resolution: Resolution
    reason: str | None
    already_in_store: bool
    retryable: bool
    route: str | None
    bytes_fetched: int
    attempts: list[str] = field(default_factory=list)
    written: bool = False


@dataclass
class _Parsed:
    """An ok parse waiting to be written (or a store hit, with no chunks)."""

    snapshot_id: uuid.UUID | None  # set on a store hit
    body_hash: str
    parse_profile: str
    segmentation_policy: str
    chunks: list[dict[str, Any]]


def _read_queued_row(
    connect: ConnectFactory, tss_id: uuid.UUID, run_id: uuid.UUID
) -> dict[str, Any] | None:
    """Return the envelope metadata of a link row ``run_id`` queued, else None."""
    with connect() as conn:
        row = conn.execute(
            select(
                task_source_snapshot.c.full_text_status,
                task_source_snapshot.c.ingested_by_run_id,
                source_snapshot.c.metadata,
            )
            .select_from(
                task_source_snapshot.join(
                    source_snapshot,
                    task_source_snapshot.c.source_snapshot_id
                    == source_snapshot.c.source_snapshot_id,
                )
            )
            .where(task_source_snapshot.c.task_source_snapshot_id == tss_id)
        ).one_or_none()
    # task 057 review (Codex 1 / security 8): a stale delivery from a run that no
    # longer owns the row does no fetch at all.
    if row is None or row.full_text_status != "queued" or row.ingested_by_run_id != run_id:
        return None
    return dict(row.metadata)


def find_in_store(
    connect: ConnectFactory, *, body_hash: str, parse_profile: str, segmentation_policy: str
) -> uuid.UUID | None:
    """Look the store key up: the snapshot already parsed from these bytes, if any.

    Args:
        connect: Opens one short transaction.
        body_hash: SHA-256 of the fetched bytes (hex).
        parse_profile: The profile the bytes would be parsed under.
        segmentation_policy: The policy the text would be cut under.

    Returns:
        The existing full-text snapshot's id, or None.
    """
    with connect() as conn:
        found: uuid.UUID | None = conn.execute(
            select(source_snapshot.c.source_snapshot_id)
            .where(source_snapshot.c.body_hash == body_hash)
            .where(source_snapshot.c.parse_profile == parse_profile)
            .where(source_snapshot.c.segmentation_policy == segmentation_policy)
        ).scalar_one_or_none()
    return found


def _write_ingested(
    connect: ConnectFactory,
    *,
    tss_id: uuid.UUID,
    run_id: uuid.UUID,
    parsed: _Parsed,
    fetched_from: str,
    content_type: str,
    route: str,
) -> bool:
    """Store the snapshot (unless it is there already) and link it, in one transaction.

    Returns:
        True when the link row was updated; False when it was no longer ``queued``
        (the snapshot is stored either way).
    """
    now = datetime.now(UTC)
    with connect() as conn:
        snapshot_id = parsed.snapshot_id
        if snapshot_id is None:
            inserted = conn.execute(
                pg_insert(source_snapshot)
                .values(
                    source_snapshot_id=uuid.uuid4(),
                    content_hash=content_hash("".join(c["content"] for c in parsed.chunks)),
                    text_basis="full_text",
                    # The public document address (owner item 4); no task, user or run key.
                    source_locator=fetched_from,
                    metadata={
                        "parse_profile": parsed.parse_profile,
                        "segmentation_policy": parsed.segmentation_policy,
                        "content_type": content_type,
                        "source_kind": route,
                    },
                    created_at=now,
                    body_hash=parsed.body_hash,
                    parse_profile=parsed.parse_profile,
                    segmentation_policy=parsed.segmentation_policy,
                )
                .on_conflict_do_nothing(
                    index_elements=["body_hash", "parse_profile", "segmentation_policy"],
                    index_where=source_snapshot.c.body_hash.is_not(None),
                )
                .returning(source_snapshot.c.source_snapshot_id)
            ).scalar_one_or_none()
            if inserted is None:
                # Another call stored the same bytes first; its chunks are there.
                snapshot_id = conn.execute(
                    select(source_snapshot.c.source_snapshot_id)
                    .where(source_snapshot.c.body_hash == parsed.body_hash)
                    .where(source_snapshot.c.parse_profile == parsed.parse_profile)
                    .where(source_snapshot.c.segmentation_policy == parsed.segmentation_policy)
                ).scalar_one()
            else:
                snapshot_id = inserted
                conn.execute(
                    chunk_table.insert(),
                    [
                        {
                            "chunk_id": uuid.uuid4(),
                            "source_snapshot_id": snapshot_id,
                            "sequence": seq,
                            "content": chunk["content"],
                            "content_hash": content_hash(chunk["content"]),
                            "locator": chunk["locator"],
                            "segmentation_policy": parsed.segmentation_policy,
                            "created_at": now,
                        }
                        for seq, chunk in enumerate(parsed.chunks, start=1)
                    ],
                )
        updated = conn.execute(
            task_source_snapshot.update()
            .where(task_source_snapshot.c.task_source_snapshot_id == tss_id)
            .where(task_source_snapshot.c.full_text_status == "queued")
            # task 057 review (Codex 1 / security 8): only the run that queued it.
            .where(task_source_snapshot.c.ingested_by_run_id == run_id)
            .values(
                full_text_snapshot_id=snapshot_id,
                full_text_status="ingested",
                full_text_error=None,
                ingested_by_run_id=run_id,
                fetched_from=fetched_from,
            )
        ).rowcount
    return bool(updated)


def _write_failed(
    connect: ConnectFactory,
    *,
    tss_id: uuid.UUID,
    run_id: uuid.UUID,
    resolution: str,
    reason: str,
) -> bool:
    """Record a reason-coded failure on the link row, guarded on ``queued`` and the run."""
    with connect() as conn:
        updated = conn.execute(
            task_source_snapshot.update()
            .where(task_source_snapshot.c.task_source_snapshot_id == tss_id)
            .where(task_source_snapshot.c.full_text_status == "queued")
            # task 057 review (Codex 1 / security 8): only the run that queued it.
            .where(task_source_snapshot.c.ingested_by_run_id == run_id)
            .values(
                full_text_snapshot_id=None,
                full_text_status=resolution,
                full_text_error=reason,
            )
        ).rowcount
    return bool(updated)


def _seconds_left(deadline: float | None) -> float | None:
    """Seconds usable before the deadline, keeping the margin; None without a deadline."""
    if deadline is None:
        return None
    return deadline - time.monotonic() - DEADLINE_MARGIN_S


def ingest_document(
    connect: ConnectFactory,
    *,
    tss_id: uuid.UUID,
    run_id: uuid.UUID,
    fetcher: DocumentFetcher,
    parse_fn: Callable[[bytes, str, int], dict[str, Any]] = parse_and_segment,
    deadline: float | None,
    parse_timeout: float = PARSE_TIMEOUT_SECONDS,
    thin_min: int = THIN_TEXT_MIN_CHARS,
    on_retryable_failure: Literal["write", "leave_queued"] = "write",
) -> DocumentOutcome:
    """Fetch, parse and store one queued document, and resolve its link row.

    Args:
        connect: Opens one short transaction that commits on exit. Called only
            for the first read, the store lookups and the final write; nothing is
            held while fetching or parsing.
        tss_id: The link row (``task_source_snapshot``) to ingest.
        run_id: The run; the row is touched only while it is ``queued`` by this
            run (its ``ingested_by_run_id``).
        fetcher: The ``DocumentFetcher`` seam.
        parse_fn: Parse callable run in the worker process (a test seam).
        deadline: ``time.monotonic()`` value after which no wait or parse is
            started (keeping a 5 s margin); None in process.
        parse_timeout: Hard per-document parse timeout in seconds.
        thin_min: Thin-text guard threshold in characters.
        on_retryable_failure: ``write`` records the failure; ``leave_queued``
            (the cloud handler's first delivery) leaves a retryable failure
            unwritten so the message can be delivered again.

    Returns:
        The outcome. Per-document problems never raise.

    Raises:
        FileNotFoundError: The fixture corpus is missing (a configuration error
            that must fail the run loudly).
    """
    metadata = _read_queued_row(connect, tss_id, run_id)
    if metadata is None:
        log.info("fulltext.not_queued", tss_id=str(tss_id))
        return DocumentOutcome(
            tss_id=tss_id, resolution="not_queued", reason=None, already_in_store=False,
            retryable=False, route=None, bytes_fetched=0,
        )

    doc = _DocState(tss_id=tss_id, metadata=metadata, urls=candidate_urls(metadata))
    # Europe PMC XML first (task 056, N10/S7) for documents with a PubMed Central
    # id, then the PDF-first URL cascade unchanged; only when the fetcher offers
    # the Europe PMC hook (the live fetcher does; fixture replay stays zero-egress).
    if callable(getattr(fetcher, "fetch_europe_pmc_xml", None)):
        xml = europe_pmc_candidate(metadata)
        if xml is not None:
            doc.xml_pmcid, doc.xml_url = xml
            doc.urls = [doc.xml_url, *(u for u in doc.urls if u != doc.xml_url)]
    if not doc.urls:
        # Durable state, distinguishable from not_attempted (adversarial finding 1)
        doc.resolution, doc.reason = "fetch_failed", "no_url"
        doc.fetch_failure_reasons.append("no_url")

    bytes_fetched = 0
    fetch_s = 0.0
    parse_s = 0.0
    deadline_cut = False
    parsed: _Parsed | None = None
    # The body a store hit linked, kept for a fresh parse if its snapshot is
    # pruned under the write (task 057 review, Codex 7 / code-review 2).
    hit_body: tuple[bytes, str] | None = None
    token = FETCH_DEADLINE.set(deadline)
    try:
        while doc.resolution is None:
            left = _seconds_left(deadline)
            if left is not None and left <= 0:
                deadline_cut = True
                break
            fetch_started = time.monotonic()
            step = _fetch_next_body(doc, fetcher)
            fetch_s += time.monotonic() - fetch_started
            bytes_fetched += step.bytes_fetched
            if step.body is None:
                break  # the cascade is exhausted: doc is resolved fetch_failed
            body = step.body
            try:
                body_hash = hashlib.sha256(body).hexdigest()
                try:
                    profile, policy = parse_profile_for(step.content_type)
                except ValueError:
                    result: dict[str, Any] = {"status": "error", "reason": "unsupported_type"}
                else:
                    hit = find_in_store(
                        connect, body_hash=body_hash, parse_profile=profile,
                        segmentation_policy=policy,
                    )
                    if hit is not None:
                        parsed = _Parsed(hit, body_hash, profile, policy, [])
                        hit_body = (body, step.content_type)
                        doc.resolution = "ingested"
                        break
                    budget = parse_timeout
                    left = _seconds_left(deadline)
                    if left is not None:
                        if left <= 0:
                            deadline_cut = True
                            break
                        budget = min(budget, left)
                    parse_started = time.monotonic()
                    result = run_parse_worker(
                        parse_fn, body, step.content_type, thin_min=thin_min, timeout=budget
                    )
                    parse_s += time.monotonic() - parse_started
                    killed = result == {"status": "error", "reason": "timeout"}
                    if killed and budget < parse_timeout:
                        deadline_cut = True  # killed for the deadline, not the 120 s
                        break
            finally:
                _release_fetch_body(fetcher, len(body))
            if result["status"] == "ok":
                parsed = _Parsed(
                    None, body_hash, result["parse_profile"], result["segmentation_policy"],
                    result["chunks"],
                )
                doc.resolution = "ingested"
                break
            doc.attempts.append(f"{_redact_url(doc.fetched_from)}: {result['reason']}")
            doc.reason = result["reason"]
            log.info(
                "fulltext.parse_failed",
                tss_id=str(tss_id),
                url=_redact_url(doc.fetched_from),
                reason=result["reason"],
                detail=result.get("detail"),
            )
            if doc.next_url >= len(doc.urls):
                doc.resolution = "parse_failed"
            # else: the next candidate URL is fetched
    finally:
        FETCH_DEADLINE.reset(token)

    if deadline_cut:
        doc.resolution, doc.reason = "fetch_failed", "timeout"
        doc.attempts.append("deadline: timeout")
    route: str | None = None
    if doc.resolution == "ingested":
        assert parsed is not None and doc.fetched_from is not None
        route = _route_of(doc.fetched_from, doc.xml_url, doc.content_type)
        try:
            written = _write_ingested(
                connect, tss_id=tss_id, run_id=run_id, parsed=parsed,
                fetched_from=doc.fetched_from,
                content_type=doc.content_type or "application/octet-stream", route=route,
            )
        except IntegrityError as exc:
            # task 057 review (Codex 7 / code-review 2): the retention script
            # deleted the store hit's snapshot between the lookup and the link
            # write; parse the same bytes afresh and write again.
            if hit_body is None or getattr(exc.orig, "sqlstate", None) != _FOREIGN_KEY_VIOLATION:
                raise
            log.warning("fulltext.snapshot_pruned_under_write", tss_id=str(tss_id))
            body, content_type = hit_body
            hit_body = None
            budget = parse_timeout
            left = _seconds_left(deadline)
            if left is not None:
                budget = min(budget, left)
            result = (
                run_parse_worker(parse_fn, body, content_type, thin_min=thin_min, timeout=budget)
                if budget > 0
                else {"status": "error", "reason": "timeout"}
            )
            del body
            if result["status"] == "ok":
                parsed = _Parsed(
                    None, parsed.body_hash, result["parse_profile"],
                    result["segmentation_policy"], result["chunks"],
                )
                written = _write_ingested(
                    connect, tss_id=tss_id, run_id=run_id, parsed=parsed,
                    fetched_from=doc.fetched_from,
                    content_type=doc.content_type or "application/octet-stream", route=route,
                )
            elif result["reason"] == "timeout" and budget < parse_timeout:
                deadline_cut = True
                doc.resolution, doc.reason = "fetch_failed", "timeout"
                doc.attempts.append("deadline: timeout")
            else:
                doc.resolution, doc.reason = "parse_failed", result["reason"]
                doc.attempts.append(f"{_redact_url(doc.fetched_from)}: {result['reason']}")
    if doc.resolution == "ingested":
        assert parsed is not None and doc.fetched_from is not None
        log.info(
            "fulltext.ingested",
            tss_id=str(tss_id),
            url=_redact_url(doc.fetched_from),
            chunk_count=len(parsed.chunks),
            already_in_store=parsed.snapshot_id is not None,
            late=not written,
            fetch_s=round(fetch_s, 3),
            parse_s=round(parse_s, 3),
        )
        return DocumentOutcome(
            tss_id=tss_id,
            resolution="ingested" if written else "late",
            reason=None,
            already_in_store=parsed.snapshot_id is not None,
            retryable=False,
            route=route,
            bytes_fetched=bytes_fetched,
            attempts=doc.attempts,
            written=written,
        )

    assert doc.resolution in ("fetch_failed", "parse_failed"), doc.resolution
    if doc.resolution == "fetch_failed":
        _apply_oa_cross_check(doc)
    # failure ⟺ closed-vocabulary reason (the CHECK enforces presence; the
    # vocabulary is code-enforced here, as the FAILURE_REASONS comment claims)
    # task 057 review (Codex 8): the not-read-yet reasons are never this function's.
    assert doc.reason in FAILURE_REASONS and doc.reason not in NOT_READ_YET_REASONS, (
        doc.reason
    )
    retryable = deadline_cut or (
        doc.resolution == "fetch_failed" and doc.reason in _TRANSPORT_FETCH_REASONS
    )
    written = False
    if not (retryable and on_retryable_failure == "leave_queued"):
        written = _write_failed(
            connect, tss_id=tss_id, run_id=run_id, resolution=doc.resolution,
            reason=doc.reason,
        )
    log.info(
        "fulltext.failed",
        tss_id=str(tss_id),
        status=doc.resolution,
        reason=doc.reason,
        attempts=doc.attempts,
        retryable=retryable,
        written=written,
        fetch_s=round(fetch_s, 3),
        parse_s=round(parse_s, 3),
    )
    resolution: Resolution = doc.resolution  # type: ignore[assignment]
    if not written and on_retryable_failure == "write":
        resolution = "late"
    return DocumentOutcome(
        tss_id=tss_id,
        resolution=resolution,
        reason=doc.reason,
        already_in_store=False,
        retryable=retryable,
        route=None,
        bytes_fetched=bytes_fetched,
        attempts=doc.attempts,
        written=written,
    )
