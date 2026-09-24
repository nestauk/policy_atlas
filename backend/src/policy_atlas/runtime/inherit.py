"""Linked-task context for the Options scoping Task Agent (task 044, D4/S8).

An Options scoping task may start from one or more Evidence search tasks (a
``task_link`` row, task 044 phase 2). :func:`linked_context` reads, for each
link, exactly what the scoping Task Agent's prompt fences as data: the
linked task's whole plan, its Result artefact rendered as markdown with
citation markers and the reference list dropped, and its search coverage
statement in plain sentences. Nothing here is copied into the scoping
task's own rows — the read happens fresh every turn.

Every read is pinned to the link's ``source_capability_run_id`` (the walk
that was finished when the link was written), never to "whatever the source
task looks like now": a source task that runs again must not silently
change what a scoping task already inherited.

Task 045 adds the **document part** of inherit (S6, A3; ADR 0039 decision
9): :func:`inherit_documents`, the longlist walk's first (non-spine) step,
gives the scoping task one ``task_source_snapshot`` row per screened-in
document of each link's pinned walk, pointing at the same content-addressed
snapshot with its origin unchanged — the row is inherited because the
inherit step created it (its ``run_id``). It is the only writer here.
:func:`linked_reports` hands the ``suggest`` step each link's report body.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from policy_atlas.api.routers._access import readable_task_leg
from policy_atlas.core.schema import (
    artefact,
    block,
    capability_run,
    evidence_scope,
    runs,
    search_coverage_record,
    synthesis_result,
    task,
    task_link,
    task_plan,
    task_source_snapshot,
)
from policy_atlas.evidence_search.assess.screen import effective_screen_rows
from policy_atlas.runtime.task_agent_scoping_prompt import LinkedTaskContext

logger = structlog.get_logger(__name__)

# Matches the inline "[1]" / "[1,2]" citation markers the frontend's
# `citationMarker` (frontend/src/views/artefactPresentation.ts) paints back
# into report prose from claim spans at export time. Stored block prose
# never carries these markers to begin with — that same file's comment on
# `proseWithCitationMarkers` says so explicitly ("Report prose does not
# store those markers"). This strip is therefore defensive, not routine: it
# uses the identical marker shape the frontend paints on, so the two
# definitions of "a citation marker" can never quietly drift apart.
_CITATION_MARKER_RE = re.compile(r"\[\d+(?:,\d+)*\]")

# Drops a trailing references/sources section a block's prose might carry,
# from its heading to the end of that block's content. Case-insensitive,
# matches "References", "Sources" or "Most relevant sources" at any heading
# level (mirrors the headings `artefactMarkdown` writes for the same
# concepts — see MOST_RELEVANT_SOURCES_INTRO and the "### References" line
# in frontend/src/views/artefactPresentation.ts).
_TRAILING_SECTION_RE = re.compile(
    r"^\s*#{1,6}\s*(?:references|sources|most relevant sources)\s*$.*",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)


def linked_context(conn: Connection, task_id: uuid.UUID) -> list[LinkedTaskContext]:
    """Read every task this task starts from, in link order.

    Read-only: no writes, no network calls, no new tables. Two calls against
    unchanged data return byte-identical results — every value read is
    either a stored fact of the pinned walk or a deterministic rendering of
    one.

    Args:
        conn: An open connection.
        task_id: The scoping task doing the reading (``task_link.target_task_id``).

    Returns:
        One :class:`LinkedTaskContext` per ``task_link`` row targeting
        ``task_id``, ordered by ``created_at, link_id`` — an empty list when
        nothing is linked.
    """
    rows = conn.execute(
        select(
            task_link.c.source_task_id,
            task_link.c.source_capability_run_id,
        )
        .where(task_link.c.target_task_id == task_id)
        .order_by(task_link.c.created_at, task_link.c.link_id)
    ).all()
    return [
        _one_context(conn, source_task_id=row.source_task_id, run_id=row.source_capability_run_id)
        for row in rows
    ]


def _one_context(
    conn: Connection, *, source_task_id: uuid.UUID, run_id: uuid.UUID
) -> LinkedTaskContext:
    title = conn.execute(
        select(task.c.name).where(task.c.task_id == source_task_id)
    ).scalar_one()
    return LinkedTaskContext(
        title=title,
        plan=_plan_payload(conn, source_task_id=source_task_id, run_id=run_id),
        report_markdown=_report_markdown(conn, source_task_id=source_task_id, run_id=run_id),
        coverage_text=_coverage_text(conn, source_task_id=source_task_id, run_id=run_id),
    )


def _plan_payload(
    conn: Connection, *, source_task_id: uuid.UUID, run_id: uuid.UUID
) -> dict[str, object]:
    """The payload of the plan version the pinned walk ran.

    Fails closed: a walk whose own plan row is gone (a data fault, or a future
    retention sweep) inherits nothing and logs a warning. Substituting the
    source task's latest approved plan would put a plan the linked report was
    never written against into the Task Agent's context, under the link's claim
    that this is what that walk ran — worse than an empty fenced block.
    """
    plan_id = conn.execute(
        select(capability_run.c.plan_id).where(
            capability_run.c.capability_run_id == run_id,
            capability_run.c.task_id == source_task_id,
        )
    ).scalar_one_or_none()
    payload = (
        conn.execute(
            select(task_plan.c.payload).where(
                task_plan.c.plan_id == plan_id, task_plan.c.task_id == source_task_id
            )
        ).scalar_one_or_none()
        if plan_id is not None
        else None
    )
    if payload is None:
        logger.warning(
            "inherit.plan_row_missing",
            source_task_id=str(source_task_id),
            source_capability_run_id=str(run_id),
        )
        return {}
    return payload if isinstance(payload, dict) else {}


def _report_markdown(
    conn: Connection, *, source_task_id: uuid.UUID, run_id: uuid.UUID
) -> str:
    """The pinned walk's Result artefact, rendered as markdown.

    One ``## {title}`` heading per artefact block, in the order the
    synthesis wrote them, with any citation markers stripped and any
    trailing references/sources section dropped. A walk whose artefact has
    no blocks (or no artefact at all) renders as the empty string.
    """
    return "\n\n".join(
        f"## {title}\n\n{body}".rstrip()
        for title, body in _walk_report_sections(
            conn, source_task_id=source_task_id, run_id=run_id
        )
    )


def _walk_report_sections(
    conn: Connection, *, source_task_id: uuid.UUID, run_id: uuid.UUID
) -> list[tuple[str, str]]:
    """The pinned walk's Result artefact as ``(title, body)`` sections."""
    artefact_id = conn.execute(
        select(artefact.c.artefact_id).where(
            artefact.c.task_id == source_task_id,
            artefact.c.capability_run_id == run_id,
        )
    ).scalar_one_or_none()
    if artefact_id is None:
        return []
    specs_raw = conn.execute(
        select(synthesis_result.c.blocks)
        .where(synthesis_result.c.artefact_id == artefact_id)
        .order_by(
            synthesis_result.c.created_at.desc(),
            synthesis_result.c.synthesis_result_id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()
    return report_sections_from_blocks(conn, specs_raw)


def report_sections_from_blocks(conn: Connection, specs_raw: Any) -> list[tuple[str, str]]:
    """Render a synthesis result's block specs as ``(title, body)`` sections.

    The one rendering both readers share: a linked walk's report (here) and a
    scoping task's own baseline (the ``suggest`` step). Each section's body
    has any citation markers stripped and any trailing references/sources
    section dropped, in the order the synthesis wrote the blocks.

    Args:
        conn: An open connection.
        specs_raw: ``synthesis_result.blocks`` as stored (a list of
            ``{block_id, title, ...}`` specs), or ``None``.

    Returns:
        One ``(title, body)`` pair per block spec; empty when there is none.
    """
    specs = (
        [item for item in specs_raw if isinstance(item, Mapping)]
        if isinstance(specs_raw, list)
        else []
    )
    block_ids = {
        item["block_id"]
        for item in specs
        if isinstance(item.get("block_id"), str)
    }
    content_by_id: dict[str, str] = {}
    if block_ids:
        parsed_ids = [uuid.UUID(raw_id) for raw_id in block_ids]
        for row in conn.execute(
            select(block.c.block_id, block.c.content).where(block.c.block_id.in_(parsed_ids))
        ):
            content_by_id[str(row.block_id)] = row.content

    sections: list[tuple[str, str]] = []
    for spec in specs:
        block_id = spec.get("block_id")
        raw_content = content_by_id.get(block_id, "") if isinstance(block_id, str) else ""
        raw_title = spec.get("title")
        title = raw_title if isinstance(raw_title, str) else ""
        cleaned = _TRAILING_SECTION_RE.sub("", raw_content)
        cleaned = _CITATION_MARKER_RE.sub("", cleaned).strip()
        sections.append((title, cleaned))
    return sections


def _coverage_text(
    conn: Connection, *, source_task_id: uuid.UUID, run_id: uuid.UUID
) -> str:
    """The pinned walk's search coverage record, as one plain sentence.

    Pinned to the walk itself, not to its evidence scope: a record is written
    per acquire run (``search_coverage_record.acquired_by_run_id``), and a
    rerun of the same approved plan writes a second record into the same
    scope, so a scope-scoped read would silently hand the link a later walk's
    verdict. The join through ``runs.capability_run_id`` keeps the read to the
    acquire runs of the pinned walk, and a walk with no record of its own
    inherits no coverage sentence rather than the newest one. Within one walk
    (a deep run acquires more than once) the last record stands. The sentence
    formula is the backend's own coverage composition
    (``api.readmodels.repository.coverage_out``), ported here scoped-by-walk
    rather than latest-for-task; no frontend equivalent exists to reuse.
    """
    row = conn.execute(
        select(
            search_coverage_record.c.stop_condition,
            search_coverage_record.c.adequacy_verdict,
        )
        .select_from(
            search_coverage_record.join(
                runs,
                (runs.c.run_id == search_coverage_record.c.acquired_by_run_id)
                & (runs.c.task_id == search_coverage_record.c.task_id),
            )
        )
        .where(
            search_coverage_record.c.task_id == source_task_id,
            runs.c.capability_run_id == run_id,
        )
        .order_by(search_coverage_record.c.created_at.desc())
        .limit(1)
    ).one_or_none()
    if row is None:
        return ""
    return _compose_coverage_sentence(row.stop_condition, row.adequacy_verdict)


def _compose_coverage_sentence(stop_condition: str, adequacy_verdict: str) -> str:
    """Port of the stop-condition/adequacy sentence in ``coverage_out``.

    ``api.readmodels.repository.coverage_out`` composes exactly this two
    -sentence shape for the latest coverage record of a whole task; this is
    the same formula, kept local because that function is task-latest and
    unscoped to one evidence scope, which is not what a pinned walk needs.
    """
    adequacy = (
        "Coverage was judged adequate."
        if adequacy_verdict == "adequate"
        else "Coverage was judged inadequate."
    )
    stop_sentence = {"completed": "Searching completed."}.get(
        stop_condition, f"Searching stopped because {stop_condition.replace('_', ' ')}."
    )
    return f"{stop_sentence} {adequacy}"


# --- The document part of inherit (task 045, S6) -------------------------------


class InheritLinkError(Exception):
    """One link's documents cannot be read; the link is skipped and named."""


@dataclass
class InheritSummary:
    """What one ``inherit`` run did.

    Attributes:
        links: Inbound links read (every ``task_link`` targeting the task).
        documents: ``task_source_snapshot`` rows this run created.
        already_present: Screened-in documents of a readable link this task
            already held (a baseline or earlier inherit row, or a document two
            links share) — never duplicated.
        failed_link_ids: The links that could not be read, oldest first.
        failed_reasons: One short reason per failed link, in the same order.
    """

    links: int = 0
    documents: int = 0
    already_present: int = 0
    failed_link_ids: list[uuid.UUID] = field(default_factory=list)
    failed_reasons: list[str] = field(default_factory=list)

    @property
    def degraded(self) -> bool:
        """``True`` when any link could not be read."""
        return bool(self.failed_link_ids)

    def as_summary(self) -> dict[str, Any]:
        """Return the component summary (``component.completed`` payload).

        ``degrades_walk`` is the runner's signal (``runner.DEGRADES_WALK_KEY``)
        that the step completed but the walk must end ``degraded``: the
        documents of the readable links are kept, the unreadable ones named.

        Returns:
            ``{links, documents, already_present, failed_links,
            failed_link_ids, failed_reasons, degrades_walk}``.
        """
        return {
            "links": self.links,
            "documents": self.documents,
            "already_present": self.already_present,
            "failed_links": len(self.failed_link_ids),
            "failed_link_ids": [str(link_id) for link_id in self.failed_link_ids],
            "failed_reasons": list(self.failed_reasons),
            "degrades_walk": self.degraded,
        }


def _inherit_one_link(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    source_task_id: uuid.UUID,
    source_capability_run_id: uuid.UUID,
) -> tuple[int, int]:
    """Insert this task's rows for one link's screened-in documents.

    Returns:
        ``(created, already_present)``.

    Raises:
        InheritLinkError: If the pinned walk or its scope is missing.
    """
    scope_id = conn.execute(
        select(capability_run.c.evidence_scope_id).where(
            capability_run.c.capability_run_id == source_capability_run_id,
            capability_run.c.task_id == source_task_id,
        )
    ).scalar_one_or_none()
    if scope_id is None:
        raise InheritLinkError("pinned walk missing")
    scope_exists = conn.execute(
        select(evidence_scope.c.evidence_scope_id).where(
            evidence_scope.c.evidence_scope_id == scope_id,
            evidence_scope.c.task_id == source_task_id,
        )
    ).scalar_one_or_none()
    if scope_exists is None:
        raise InheritLinkError("pinned walk's scope missing")

    effective = effective_screen_rows()
    rows = conn.execute(
        select(
            task_source_snapshot.c.source_snapshot_id,
            task_source_snapshot.c.origin,
            task_source_snapshot.c.full_text_snapshot_id,
            task_source_snapshot.c.full_text_status,
            task_source_snapshot.c.full_text_error,
        )
        .join(
            effective,
            (effective.c.task_source_snapshot_id
             == task_source_snapshot.c.task_source_snapshot_id)
            & (effective.c.task_id == task_source_snapshot.c.task_id),
        )
        .where(task_source_snapshot.c.task_id == source_task_id)
        .where(effective.c.evidence_scope_id == scope_id)
        .where(effective.c.status == "relevant")
        .order_by(task_source_snapshot.c.ingested_at, task_source_snapshot.c.source_snapshot_id)
    ).all()

    created = 0
    for row in rows:
        inserted = conn.execute(
            pg_insert(task_source_snapshot)
            .values(
                task_source_snapshot_id=uuid.uuid4(),
                task_id=task_id,
                source_snapshot_id=row.source_snapshot_id,
                # Origin unchanged (A3): the row is inherited because this
                # step created it, not because of an origin value.
                origin=row.origin,
                run_id=run_id,
                ingested_at=datetime.now(UTC),
                # Copied so ingest does not refetch what the source task holds.
                full_text_snapshot_id=row.full_text_snapshot_id,
                full_text_status=row.full_text_status,
                full_text_error=row.full_text_error,
            )
            .on_conflict_do_nothing(constraint="uq_task_source_snapshot")
            .returning(task_source_snapshot.c.task_source_snapshot_id)
        ).scalar_one_or_none()
        if inserted is not None:
            created += 1
    return created, len(rows) - created


def _sources_owner_reads(conn: Connection, *, task_id: uuid.UUID) -> set[uuid.UUID]:
    """Return the linked source tasks this task's owner may read right now."""
    owner = conn.execute(
        select(task.c.owner_user_id).where(task.c.task_id == task_id)
    ).scalar_one_or_none()
    if owner is None:
        return set()
    return set(
        conn.execute(
            select(task_link.c.source_task_id)
            .join(task, task.c.task_id == task_link.c.source_task_id)
            .where(task_link.c.target_task_id == task_id)
            .where(readable_task_leg(owner))
        ).scalars()
    )


def inherit_documents(
    conn: Connection, *, task_id: uuid.UUID, run_id: uuid.UUID
) -> InheritSummary:
    """Give this task a row for every screened-in document of each linked walk.

    For each inbound ``task_link`` (oldest first): the source task's
    screened-in documents (effective screening row ``relevant``) in the scope
    of the link's pinned walk; one ``task_source_snapshot`` row per document
    this task lacks, sharing the content-addressed ``source_snapshot_id``,
    **origin unchanged** (A3), ``run_id`` = this inherit run, and the
    full-text attachment copied so ingest does not refetch. Idempotent on
    ``uq_task_source_snapshot``: a document the task already holds (from the
    baseline, an earlier inherit, or another link) is left alone.

    A link that cannot be read (its pinned walk or scope missing, or any
    database error) is rolled back to its own savepoint, recorded and
    skipped; the other links' documents are kept. The caller completes the
    step and the runner ends the walk ``degraded`` (owner: "inherit
    non-spine" — the walk continues without the linked documents, the
    missing link named).

    Args:
        conn: Open connection inside the component transaction.
        task_id: The scoping task inheriting (``task_link.target_task_id``).
        run_id: This inherit run (the rows' ``run_id``).

    Returns:
        The run's :class:`InheritSummary`.
    """
    links = conn.execute(
        select(
            task_link.c.link_id,
            task_link.c.source_task_id,
            task_link.c.source_capability_run_id,
        )
        .where(task_link.c.target_task_id == task_id)
        .order_by(task_link.c.created_at, task_link.c.link_id)
    ).all()
    summary = InheritSummary(links=len(links))
    readable = _sources_owner_reads(conn, task_id=task_id)
    for link in links:
        try:
            # A link grants no read (ADR 0037): the owner must still read the
            # source at every build, not only when the link was made (owner,
            # 2026-09-24, task 045 review S1: "Recheck access only").
            if link.source_task_id not in readable:
                raise InheritLinkError("source not readable by the task owner")
            with conn.begin_nested():
                created, present = _inherit_one_link(
                    conn,
                    task_id=task_id,
                    run_id=run_id,
                    source_task_id=link.source_task_id,
                    source_capability_run_id=link.source_capability_run_id,
                )
        except (InheritLinkError, SQLAlchemyError) as exc:
            reason = str(exc) if isinstance(exc, InheritLinkError) else type(exc).__name__
            logger.warning(
                "inherit.link_unreadable",
                task_id=str(task_id),
                link_id=str(link.link_id),
                source_task_id=str(link.source_task_id),
                reason=reason,
            )
            summary.failed_link_ids.append(link.link_id)
            summary.failed_reasons.append(reason)
            continue
        summary.documents += created
        summary.already_present += present
    logger.info(
        "inherit.documents",
        task_id=str(task_id),
        links=summary.links,
        documents=summary.documents,
        already_present=summary.already_present,
        failed_links=len(summary.failed_link_ids),
    )
    return summary


def linked_reports(conn: Connection, task_id: uuid.UUID) -> list[tuple[str, str]]:
    """Return each linked task's report body, for the ``suggest`` step (A15).

    Read-only, pinned to each link's walk like :func:`linked_context`. A link
    whose report cannot be read, or that has no report, is left out (logged):
    ``suggest`` reads what is there and never fails on a link.

    Args:
        conn: An open connection.
        task_id: The scoping task.

    Returns:
        ``(linked task name, report markdown)`` per link with a report, in
        link order.
    """
    rows = conn.execute(
        select(
            task_link.c.link_id,
            task_link.c.source_task_id,
            task_link.c.source_capability_run_id,
            task.c.name,
        )
        .join(task, task.c.task_id == task_link.c.source_task_id)
        .where(task_link.c.target_task_id == task_id)
        .order_by(task_link.c.created_at, task_link.c.link_id)
    ).all()
    reports: list[tuple[str, str]] = []
    readable = _sources_owner_reads(conn, task_id=task_id)
    for row in rows:
        if row.source_task_id not in readable:
            logger.warning(
                "inherit.report_unreadable",
                task_id=str(task_id),
                link_id=str(row.link_id),
                error="source not readable by the task owner",
            )
            continue
        try:
            with conn.begin_nested():
                markdown = _report_markdown(
                    conn,
                    source_task_id=row.source_task_id,
                    run_id=row.source_capability_run_id,
                )
        except SQLAlchemyError as exc:
            logger.warning(
                "inherit.report_unreadable",
                task_id=str(task_id),
                link_id=str(row.link_id),
                error=type(exc).__name__,
            )
            continue
        if markdown:
            reports.append((row.name, markdown))
    return reports
