"""The review after edits (task 054, C45): read the theory, ask the model, store a proposal.

Runs off the request path on the walk executor, like a check: it reads the
plan with the user's clarifications, the theory with verdicts and pathways,
the user's edits since the last review and the report; one ``toc_review`` call
returns edits and report findings; they are stored as one proposal and the Task
Agent says how many there are and where to find them.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine

from policy_atlas.core.schema import event_log, toc_proposal
from policy_atlas.runtime.capability_registry import (
    THEORY_OF_CHANGE,
    expect_toc_plan,
    latest_approved_plan_row,
    validate_plan,
)
from policy_atlas.theory_of_change import edits, proposals, store
from policy_atlas.theory_of_change.backend import TocBackend
from policy_atlas.theory_of_change.check import (
    appraisals_for,
    counted_judgements,
    link_verdict_of,
)
from policy_atlas.theory_of_change.draft import plan_data, with_clarifications
from policy_atlas.theory_of_change.evidence.grade import VERDICT_LABELS

log = structlog.get_logger()

#: Edits since the last review after which the Task Agent suggests one (C45).
REVIEW_AFTER_EDITS = 5


def edits_since_review(conn: Connection, task_id: uuid.UUID) -> list[str]:
    """The user's edit lines since the last review's proposal, oldest first."""
    since = conn.execute(
        select(toc_proposal.c.created_at)
        .where(toc_proposal.c.task_id == task_id, toc_proposal.c.source == "review")
        .order_by(toc_proposal.c.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    query = (
        select(event_log.c.payload)
        .where(event_log.c.task_id == task_id)
        .where(event_log.c.event_type == store.TOC_CHANGED_EVENT)
        .where(event_log.c.payload["step"].astext == edits.USER_EDIT)
        .order_by(event_log.c.sequence)
    )
    if since is not None:
        query = query.where(event_log.c.occurred_at > since)
    lines: list[str] = []
    for payload in conn.execute(query).scalars():
        lines.extend(
            str(change) for change in payload.get("changes", []) if isinstance(change, str)
        )
    return lines


def _theory(conn: Connection, task_id: uuid.UUID) -> dict[str, Any]:
    graph, rows = store.load_graph(conn, task_id)
    counted = counted_judgements(conn, task_id=task_id)
    appraisals = appraisals_for(
        conn, task_id=task_id, evidence_rows=[r for group in counted.values() for r in group]
    )
    code = {key: row.code for key, row in rows.boxes.items()}
    link_code = {key: row.code for key, row in rows.links.items()}
    on_pathways: dict[str, list[str]] = {}
    pathways = []
    for i, pathway in enumerate(graph.pathways, start=1):
        if pathway.status != "kept":
            continue
        chain = [graph.links.get(key) for key in pathway.links]
        broken = any(link is None for link in chain) or any(
            a is not None and b is not None and a.target != b.source
            for a, b in zip(chain, chain[1:], strict=False)
        )
        pathways.append(
            {
                "key": f"p{i}",
                "kind": pathway.kind,
                "label": rows.pathways[pathway.key].label,
                "links": [link_code.get(key) for key in pathway.links],
                "broken": broken,
            }
        )
        for key in pathway.links:
            on_pathways.setdefault(key, []).append(f"p{i}")
    return {
        "boxes": [
            {
                "code": code[key],
                "layer": box.layer,
                "text": box.text,
                "by_user": rows.boxes[key].origin == "user" or bool(rows.boxes[key].user_edited),
            }
            for key, box in graph.boxes.items()
        ],
        "links": [
            {
                "code": link_code[key],
                "from": code.get(link.source),
                "to": code.get(link.target),
                "sentence": link.sentence,
                "verdict": VERDICT_LABELS[
                    link_verdict_of(counted.get(key, []), appraisals).verdict
                ],
                "by_user": rows.links[key].origin == "user" or bool(rows.links[key].user_edited),
                "on_pathways": on_pathways.get(key, []),
            }
            for key, link in graph.links.items()
        ],
        "pathways": pathways,
    }


def _report(conn: Connection, task_id: uuid.UUID) -> dict[str, Any] | None:
    payload = conn.execute(
        select(event_log.c.payload)
        .where(event_log.c.task_id == task_id)
        .where(event_log.c.event_type == "component.completed")
        .where(event_log.c.payload["component"].astext == "toc_report")
        .order_by(event_log.c.sequence.desc())
        .limit(1)
    ).scalar_one_or_none()
    report = (payload or {}).get("report")
    if not isinstance(report, dict):
        return None
    return {
        "title": report.get("title"),
        "summary": report.get("summary_text"),
        "if_then_because": (report.get("summary") or {}).get("if_then_because"),
        "how_change_happens": [
            f"{item.get('title')}: {item.get('paragraph')}" for item in report.get("pathways", [])
        ],
        "tests": [
            f"{item.get('link')}: {item.get('question')}" for item in report.get("tests", [])
        ],
    }


def run_review(engine: Engine, *, task_id: uuid.UUID, backend: TocBackend) -> uuid.UUID | None:
    """Review the theory after edits and store the proposal (C45).

    Returns:
        The proposal's id, or ``None`` when the review proposed nothing.
    """
    from policy_atlas.api.toc_start import post_agent_message

    with engine.connect() as conn:
        row = latest_approved_plan_row(conn, task_id)
        if row is None:
            return None
        plan = with_clarifications(
            conn, task_id, expect_toc_plan(validate_plan(THEORY_OF_CHANGE, row["payload"]))
        )
        plan_fields = plan_data(plan)
        theory = _theory(conn, task_id)
        made = edits_since_review(conn, task_id)
        report = _report(conn, task_id)
    response, _usage = backend.review(plan=plan_fields, theory=theory, edits=made, report=report)
    with engine.begin() as conn:
        proposal_id = proposals.create_proposal(
            conn,
            task_id=task_id,
            source="review",
            summary=response.summary,
            ops=list(response.edits),
            report_findings=[finding.model_dump() for finding in response.report_findings],
        )
    count = len(response.edits)
    findings = len(response.report_findings)
    if proposal_id is None:
        text = (
            f"I reviewed the theory after your edits. {response.summary} "
            "I have no changes to suggest."
        )
    else:
        parts = []
        if count:
            parts.append(f"{count} change{'s' if count != 1 else ''} to suggest")
        if findings:
            parts.append(f"{findings} report section{'s' if findings != 1 else ''} to update")
        text = (
            f"I reviewed the theory after your edits. {response.summary} "
            f"I have {' and '.join(parts)}: see Suggestions above the canvas. "
            "Nothing changes until you accept."
        )
    post_agent_message(engine, task_id=task_id, text=text)
    log.info("toc_review.done", task_id=str(task_id), edits=count, report_findings=findings)
    return proposal_id
