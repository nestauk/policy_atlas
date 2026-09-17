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
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping

import structlog
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import (
    artefact,
    block,
    capability_run,
    runs,
    search_coverage_record,
    synthesis_result,
    task,
    task_link,
    task_plan,
)
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
    artefact_id = conn.execute(
        select(artefact.c.artefact_id).where(
            artefact.c.task_id == source_task_id,
            artefact.c.capability_run_id == run_id,
        )
    ).scalar_one_or_none()
    if artefact_id is None:
        return ""
    specs_raw = conn.execute(
        select(synthesis_result.c.blocks)
        .where(synthesis_result.c.artefact_id == artefact_id)
        .order_by(
            synthesis_result.c.created_at.desc(),
            synthesis_result.c.synthesis_result_id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()
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

    parts: list[str] = []
    for spec in specs:
        block_id = spec.get("block_id")
        raw_content = content_by_id.get(block_id, "") if isinstance(block_id, str) else ""
        title = spec.get("title") if isinstance(spec.get("title"), str) else ""
        cleaned = _TRAILING_SECTION_RE.sub("", raw_content)
        cleaned = _CITATION_MARKER_RE.sub("", cleaned).strip()
        parts.append(f"## {title}\n\n{cleaned}".rstrip())
    return "\n\n".join(parts)


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
