"""The ``toc_summarise`` step: the header paragraphs and every sentence (task 054, C20).

Each citation is checked against what the item's judgements allow; a sentence
whose citations fail is replaced by the fixed fallback.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from typing import Any

import structlog
from sqlalchemy.engine import Connection, Row

from policy_atlas.core.schema import (
    toc_box,
    toc_link,
)
from policy_atlas.core.usage import UsageAccumulator
from policy_atlas.options_scoping.context import ScopeContext
from policy_atlas.theory_of_change import store
from policy_atlas.theory_of_change.backend import TocBackend
from policy_atlas.theory_of_change.check.grade import (
    VERDICT_LABELS,
    DocAppraisal,
    quality,
)
from policy_atlas.theory_of_change.check.shared import (
    _ask,
    _short_keys,
    _year,
    appraisals_for,
    counted_judgements,
    link_verdict_of,
    row_judgement,
)
from policy_atlas.theory_of_change.draft import _norm, plan_data, walk_toc_plan
from policy_atlas.theory_of_change.graph import (
    Graph,
)

log = structlog.get_logger()


#: The fixed sentence for a question no document spoke to (C20).
NO_EVIDENCE_SENTENCE = "No evidence was found in the documents read."


#: The fixed sentence that replaces a link sentence whose citations fail (C20).
UNSETTLED_SENTENCE = "The documents read do not settle this step."


#: The fixed box description that replaces one whose citations fail (C20).
BOX_FALLBACK_DESCRIPTION = "A step in the theory."


def toc_summarise_scope(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    context: ScopeContext,
    backend: TocBackend,
) -> dict[str, Any]:
    """Write each link's title and evidence sentence and each box's texts (C20).

    Every citation is checked; a sentence that fails is replaced with a fixed
    one, and a "seen in" note that fails is dropped. The texts are written on
    the rows, with the documents each cites. The theory's title, summary and
    narrative are the report's (``toc_report``).

    Args:
        conn: Open connection inside the component transaction.
        task_id: The task.
        run_id: This run.
        context: The check walk's intent record.
        backend: The ToC model seam.

    Returns:
        The count of replaced texts and the usage.

    Raises:
        RuntimeError: If the summary call failed twice.
    """
    plan = walk_toc_plan(conn, task_id=task_id, run_id=run_id, scope_id=context.scope_id)
    graph, rows = store.load_graph(conn, task_id)
    counted = counted_judgements(conn, task_id=task_id)
    every = [row for group in counted.values() for row in group]
    appraisals = appraisals_for(conn, task_id=task_id, evidence_rows=every)
    titles = _titles(conn, task_id=task_id, tss_ids={row.task_source_snapshot_id for row in every})
    short, back = _short_keys(graph)
    theory = _theory_for_summary(graph, rows, counted, appraisals, titles, short)
    usage = UsageAccumulator()
    response = _ask(
        "toc_summarise",
        lambda: backend.summarise(plan=plan_data(plan), theory=theory),
        usage,
    )
    if response is None:
        raise RuntimeError("toc_summarise: the summary call failed")

    allowed = {
        key: {
            str(r.task_source_snapshot_id)
            for r in counted.get(key, [])
            if row_judgement(r).support != "not_about"
        }
        for key in graph.links
    }
    answered = {back.get(item.link): item for item in response.links}
    replaced = 0
    log_ = store.ChangeLog()
    for key, row in rows.links.items():
        item = answered.get(key)
        cites: list[str] = []
        if not allowed[key]:
            sentence = NO_EVIDENCE_SENTENCE
        elif (
            item is not None
            and item.sentence
            and item.sentence.strip()
            # Every cited document is one the item may cite (C20).
            and set(item.cites) <= allowed[key]
        ):
            sentence = item.sentence.strip()
            cites = list(dict.fromkeys(item.cites))
        else:
            replaced += 1
            sentence = UNSETTLED_SENTENCE
        title = item.title.strip() if item is not None and item.title.strip() else None
        store.update(
            conn,
            log_,
            toc_link,
            row.link_id,
            observed_revision=row.revision,
            values={"title": title, "evidence_sentence": sentence, "evidence_cites": cites},
        )
    case_docs: dict[str, set[str]] = {}
    for row in every:
        if row.case_box_id is not None and row.case_study is not None:
            case_docs.setdefault(str(row.case_box_id), set()).add(str(row.task_source_snapshot_id))
    described = {back.get(item.box): item for item in response.boxes}
    for key, row in rows.boxes.items():
        item = described.get(key)
        if item is not None and item.description.strip():
            description = item.description.strip()
        else:
            replaced += 1
            description = BOX_FALLBACK_DESCRIPTION
        # "Seen in" stands only when the box has case studies and it cites only them.
        seen_in: str | None = None
        seen_cites: list[str] = []
        if item is not None and item.seen_in and item.seen_in.strip():
            docs = case_docs.get(key, set())
            if docs and set(item.cites) <= docs:
                seen_in, seen_cites = item.seen_in.strip(), list(dict.fromkeys(item.cites))
            else:
                replaced += 1
        store.update(
            conn,
            log_,
            toc_box,
            row.box_id,
            observed_revision=row.revision,
            values={"description": description, "seen_in": seen_in, "seen_in_cites": seen_cites},
        )
    store.record(conn, task_id=task_id, run_id=run_id, step="toc_summarise", log=log_)
    summary = {
        "replaced": replaced,
        "backend_mode": backend.mode,
        "usage_totals": usage.payload(),
    }
    log.info("toc_summarise.done", replaced=replaced)
    return summary


#: Case studies shown per box, after de-duplication (read time).
CASE_STUDIES_PER_BOX = 5


def top_case_studies[T](
    candidates: Iterable[tuple[T, str, str | None, int, bool]],
) -> list[T]:
    """One box's case studies to show, best first (read time).

    Ranks by the document's quality Q (C36), then supporting documents before
    others, then the given order; keeps the first of each programme and place
    (case and spacing ignored) and at most :data:`CASE_STUDIES_PER_BOX`.

    Args:
        candidates: ``(item, programme, place, quality, supports)`` per case
            study, in their existing order.

    Returns:
        The kept items.
    """
    ranked = sorted(enumerate(candidates), key=lambda p: (-p[1][3], not p[1][4], p[0]))
    seen: set[tuple[str, str]] = set()
    kept: list[T] = []
    for _, (item, programme, place, _score, _supports) in ranked:
        key = (_norm(programme), _norm(place or ""))
        if key in seen:
            continue
        seen.add(key)
        kept.append(item)
        if len(kept) == CASE_STUDIES_PER_BOX:
            break
    return kept


def row_case_score(row: Row[Any], appraisal: DocAppraisal | None) -> tuple[int, bool]:
    """A judgement row's ``(quality, supports)`` for :func:`top_case_studies`."""
    return quality(appraisal, row.robust_model), row_judgement(row).support in ("strong", "weak")


def _titles(
    conn: Connection, *, task_id: uuid.UUID, tss_ids: set[uuid.UUID]
) -> dict[str, tuple[str, int | None]]:
    return {
        str(tss): (str((row.metadata or {}).get("title") or ""), _year(row.metadata or {}))
        for tss, row in store.snapshot_meta(conn, task_id, tss_ids).items()
    }


def _theory_for_summary(
    graph: Graph,
    rows: store.GraphRows,
    counted: dict[str, list[Row[Any]]],
    appraisals: dict[str, DocAppraisal],
    titles: dict[str, tuple[str, int | None]],
    short: dict[str, str],
) -> dict[str, object]:
    candidates: dict[str, list[tuple[dict[str, object], str, str | None, int, bool]]] = {}
    for group in counted.values():
        for row in group:
            if row.case_box_id is not None and row.case_study is not None:
                case = row.case_study
                score, supports = row_case_score(
                    row, appraisals.get(str(row.task_source_snapshot_id))
                )
                candidates.setdefault(str(row.case_box_id), []).append(
                    (
                        {"document_id": str(row.task_source_snapshot_id), **case},
                        str(case.get("programme") or ""),
                        case.get("place"),
                        score,
                        supports,
                    )
                )
    case_studies = {box: top_case_studies(items) for box, items in candidates.items()}
    links = []
    for key, link in graph.links.items():
        group = counted.get(key, [])
        links.append(
            {
                "key": short[key],
                "source": short[link.source],
                "target": short[link.target],
                "sentence": link.sentence,
                "conditions": link.conditions,
                "critical": bool(rows.links[key].critical),
                "verdict": VERDICT_LABELS[link_verdict_of(group, appraisals).verdict],
                "documents": [
                    {
                        "id": str(row.task_source_snapshot_id),
                        "title": titles.get(str(row.task_source_snapshot_id), ("", None))[0],
                        "year": titles.get(str(row.task_source_snapshot_id), ("", None))[1],
                        "support": row_judgement(row).support,
                        "quote": row.quote,
                        "relevance": row_judgement(row).relevance,
                        "relevance_note": row.relevance_reason,
                        "condition": row.condition,
                    }
                    for row in group
                    if row_judgement(row).support != "not_about"
                ],
            }
        )
    return {
        "boxes": [
            {
                "key": short[key],
                "layer": box.layer,
                "text": box.text,
                "result_criteria": {
                    **(rows.boxes[key].result_criteria or {}),
                    "indicator": rows.boxes[key].indicator,
                },
                "case_studies": case_studies.get(key, []),
            }
            for key, box in graph.boxes.items()
        ],
        "links": links,
        "pathways": [
            {
                "kind": p.kind,
                "label": rows.pathways[p.key].label,
                "links": [short[k] for k in p.links if k in short],
            }
            for p in graph.pathways
            if p.status == "kept"
        ],
    }
