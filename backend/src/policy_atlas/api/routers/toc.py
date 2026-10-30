"""The theory-of-change read routes (task 054, S14; C17).

Three reads under ``/api/v1/tasks/{task_id}/toc``, public-readable like the
Result and Sources tabs (the read grade or the narrow public leg, through
``_readable``): the graph with one evidence verdict per link, link states and
the narrative report; every judged document and case study; and one judgement's quote
in its passage. Verdicts and states are computed on read (C36, C19). A
readable task that is not a theory of change is a 404 ``toc_not_found``; an
unreadable one keeps the generic ``not_found``.
"""

from __future__ import annotations

import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated, Any, Literal, cast

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine, Row

from policy_atlas.api.app import ApiConflict, ApiNotFound, ApiUnprocessable
from policy_atlas.api.auth import AuthenticatedUser
from policy_atlas.api.contract.read_models import ChunkContextOut
from policy_atlas.api.contract.toc import (
    TocBoxCreate,
    TocBoxEvidenceOut,
    TocBoxOut,
    TocBoxPatch,
    TocCaseStudyOut,
    TocCheckIn,
    TocCheckOut,
    TocClarificationIn,
    TocCountOut,
    TocCreatedOut,
    TocDecideIn,
    TocDocumentOut,
    TocEvidenceOut,
    TocEvidencePatch,
    TocFigureOut,
    TocGradeRuleOut,
    TocGraphOut,
    TocHistoryEntryOut,
    TocLinkCreate,
    TocLinkEvidenceOut,
    TocLinkOut,
    TocLinkPatch,
    TocLinksIn,
    TocMoveIn,
    TocPathwayOut,
    TocPositionOut,
    TocProblemsOut,
    TocProposalDecideIn,
    TocProposalEditOut,
    TocProposalOut,
    TocReportFindingOut,
    TocReportOut,
    TocResultCriteriaOut,
    TocRevisionOut,
    TocStudyIn,
    TocUndoOut,
    TocWeightsOut,
)
from policy_atlas.api.deps import (
    get_conn,
    get_current_user,
    get_engine,
    get_executor,
    get_optional_user,
    get_runner_backends,
    get_settings,
)
from policy_atlas.api.readmodels.repository import (
    _authorships,
    _clamped_quote_window,
    _url,
    _venue,
)
from policy_atlas.api.routers._access import accessible_task, readable_or_public_task
from policy_atlas.api.routers.runs import start_toc_check
from policy_atlas.api.settings import Settings
from policy_atlas.core import events, tracing
from policy_atlas.core.schema import (
    capability_run,
    event_log,
    evidence_scope,
    source_appraisal_result,
    source_classification_result,
    source_snapshot,
    task_source_snapshot,
    toc_box,
    toc_figure,
    toc_item_evidence,
    toc_link,
    toc_pathway_link,
)
from policy_atlas.runtime.capability_registry import THEORY_OF_CHANGE
from policy_atlas.runtime.option_search import TOC_ITEM_SEARCHES_STAGE
from policy_atlas.runtime.runner import RunnerBackends
from policy_atlas.runtime.toc_plan import (
    TOC_CHECK_MODE_KEY,
    TOC_LINKS_KEY,
    TOC_PURPOSE,
    TOC_STOP_EVENT,
    TOC_WALK_CHECK,
    TOC_WALK_KEY,
)
from policy_atlas.theory_of_change import edits, proposals, store
from policy_atlas.theory_of_change.backend import StubTocBackend
from policy_atlas.theory_of_change.check import (
    Document,
    appraisals_for,
    counted_judgements,
    link_verdict_of,
    pending_judgements,
    row_case_score,
    row_judgement,
    top_case_studies,
)
from policy_atlas.theory_of_change.draft import TOC_CLARIFICATION_EVENT
from policy_atlas.theory_of_change.edits import EditRefused
from policy_atlas.theory_of_change.evidence.grade import lowest, quality, rule_text, weight
from policy_atlas.theory_of_change.graph import assumption_type, item_hash, link_state
from policy_atlas.theory_of_change.review import edits_since_review, run_review

router = APIRouter(prefix="/api/v1/tasks/{task_id}/toc", tags=["theory-of-change"])
log = structlog.get_logger()

CheckStatus = Literal["none", "drafting", "checking", "checked", "stopped", "failed"]


def _readable_toc(conn: Connection, task_id: uuid.UUID, user: AuthenticatedUser | None) -> None:
    access = readable_or_public_task(
        conn, task_id=task_id, user_id=None if user is None else user.user_id
    )
    if access.row["capability"] != THEORY_OF_CHANGE:
        raise ApiNotFound("toc_not_found", "this task is not a theory of change")


def _latest_walk(conn: Connection, task_id: uuid.UUID) -> Row[Any] | None:
    return conn.execute(
        select(
            capability_run.c.capability_run_id, capability_run.c.status, evidence_scope.c.context
        )
        .select_from(
            capability_run.join(
                evidence_scope,
                (evidence_scope.c.evidence_scope_id == capability_run.c.evidence_scope_id)
                & (evidence_scope.c.task_id == capability_run.c.task_id),
            )
        )
        .where(capability_run.c.task_id == task_id)
        .where(capability_run.c.parent_capability_run_id.is_(None))
        .where(evidence_scope.c.purpose == TOC_PURPOSE)
        .order_by(capability_run.c.started_at.desc())
        .limit(1)
    ).one_or_none()


def check_status(walk: Row[Any] | None) -> CheckStatus:
    """The theory's check status from its latest walk."""
    if walk is None:
        return "none"
    kind = (walk.context or {}).get(TOC_WALK_KEY)
    if walk.status in ("running", "paused"):
        return "checking" if kind == TOC_WALK_CHECK else "drafting"
    if walk.status in ("succeeded", "degraded"):
        # A draft that landed is followed at once by its check (S4).
        return "checked" if kind == TOC_WALK_CHECK else "checking"
    if walk.status == "aborted" and kind == TOC_WALK_CHECK:
        return "stopped"  # the user's Stop (C48)
    return "failed"


def _report(conn: Connection, task_id: uuid.UUID) -> TocReportOut | None:
    """The latest check walk's narrative report (C38), from its step payload."""
    payload = conn.execute(
        select(event_log.c.payload)
        .where(event_log.c.task_id == task_id)
        .where(event_log.c.event_type == "component.completed")
        .where(event_log.c.payload["component"].astext == "toc_report")
        .order_by(event_log.c.sequence.desc())
        .limit(1)
    ).scalar_one_or_none()
    if not isinstance(payload, dict) or not isinstance(payload.get("report"), dict):
        return None
    return TocReportOut.model_validate(payload["report"])


def _links_left_out(conn: Connection, task_id: uuid.UUID) -> int:
    payload = conn.execute(
        select(event_log.c.payload)
        .where(event_log.c.task_id == task_id)
        .where(event_log.c.event_type == "run.started")
        .where(event_log.c.payload["component"].astext == TOC_ITEM_SEARCHES_STAGE)
        .order_by(event_log.c.sequence.desc())
        .limit(1)
    ).scalar_one_or_none()
    return int(payload.get("links_left_out") or 0) if isinstance(payload, dict) else 0


def _steps(conn: Connection, task_id: uuid.UUID) -> dict[str, list[tuple[int, uuid.UUID]]]:
    out: dict[str, list[tuple[int, uuid.UUID]]] = {}
    for row in conn.execute(
        select(
            toc_pathway_link.c.pathway_id, toc_pathway_link.c.position, toc_pathway_link.c.link_id
        )
        .where(toc_pathway_link.c.task_id == task_id)
        .order_by(toc_pathway_link.c.pathway_id, toc_pathway_link.c.position)
    ):
        out.setdefault(str(row.pathway_id), []).append((row.position, row.link_id))
    return out


def toc_graph_out(conn: Connection, task_id: uuid.UUID) -> TocGraphOut:
    """Build the graph read for one theory-of-change task."""
    graph, rows = store.load_graph(conn, task_id)
    walk = _latest_walk(conn, task_id)
    status = check_status(walk)
    counted = counted_judgements(conn, task_id=task_id)
    pending = pending_judgements(conn, task_id=task_id)
    appraisals = appraisals_for(
        conn,
        task_id=task_id,
        evidence_rows=[r for group in [*counted.values(), *pending.values()] for r in group],
    )
    judged_hashes = {
        (str(row.link_id), row.item_hash)
        for row in conn.execute(
            select(toc_item_evidence.c.link_id, toc_item_evidence.c.item_hash)
            .where(toc_item_evidence.c.task_id == task_id)
            .distinct()
        )
    }
    names = edits.names_of(
        conn, {row.edited_by for row in [*rows.boxes.values(), *rows.links.values()]}
    )
    # A check named on links (C40) is "checking" only those links; updating the
    # report checks none.
    walk_context = (walk.context or {}) if walk is not None else {}
    named = set(walk_context.get(TOC_LINKS_KEY) or [])
    report_only = walk_context.get(TOC_CHECK_MODE_KEY) == "report"
    links: list[TocLinkOut] = []
    for key, row in rows.links.items():
        link = graph.links[key]
        source, target = graph.boxes[link.source], graph.boxes[link.target]
        current = item_hash(link, source.text, target.text)
        verdict = link_verdict_of(counted.get(key, []), appraisals)
        links.append(
            TocLinkOut(
                link_id=row.link_id,
                code=row.code,
                source_box_id=row.source_box_id,
                target_box_id=row.target_box_id,
                sentence=row.sentence or "",
                title=row.title,
                if_text=row.if_text,
                for_text=row.for_text,
                then_text=row.then_text,
                because_text=row.because_text,
                conditions=list(row.conditions or []),
                assumption_type=assumption_type(source.layer, target.layer),
                critical=row.critical,
                origin=row.origin,
                revision=row.revision,
                state=link_state(
                    current_hash=current,
                    counted_hash=row.counted_hash,
                    kept_hash=row.kept_hash,
                    kept_by=row.kept_by,
                    checking=status == "checking"
                    and not report_only
                    and (not named or key in named)
                    and (key, current) not in judged_hashes,
                ),
                verdict=verdict.verdict,
                near_threshold=verdict.near_threshold,
                weights=TocWeightsOut(
                    total_weight=round(verdict.total_weight, 3),
                    mean_support=round(verdict.mean_support, 3),
                    refute_share=round(verdict.refute_share, 3),
                    n_documents=verdict.n_documents,
                ),
                evidence_sentence=row.evidence_sentence,
                evidence_cites=list(row.evidence_cites or []),
                edited_by=names.get(row.edited_by) if row.edited_by else None,
                edited_at=row.edited_at,
                pending_count=len(pending.get(key, [])),
                verdict_if_accepted=(
                    link_verdict_of([*counted.get(key, []), *pending[key]], appraisals).verdict
                    if pending.get(key)
                    else None
                ),
            )
        )
    steps = _steps(conn, task_id)
    pathways: list[TocPathwayOut] = []
    for key, row in rows.pathways.items():
        ordered = steps.get(key, [])
        positions = [position for position, _ in ordered]
        chain = [graph.links.get(str(link_id)) for _, link_id in ordered]
        broken = positions != list(range(len(positions))) or any(
            a is None or b is None or a.target != b.source
            for a, b in zip(chain, chain[1:], strict=False)
        )
        pathways.append(
            TocPathwayOut(
                pathway_id=row.pathway_id,
                kind=row.kind,
                status=row.status,
                label=row.label,
                reason=row.reason,
                origin=row.origin,
                link_ids=[link_id for _, link_id in ordered],
                broken=broken,
            )
        )
    return TocGraphOut(
        task_id=task_id,
        check_status=status,
        boxes=[
            TocBoxOut(
                box_id=row.box_id,
                layer=row.layer,
                code=row.code,
                text=row.text,
                dosage=row.dosage,
                result_criteria=TocResultCriteriaOut(
                    definition=(row.result_criteria or {}).get("definition"),
                    indicator=row.indicator,
                    timing=(row.result_criteria or {}).get("timing"),
                ),
                description=row.description,
                seen_in=row.seen_in,
                seen_in_cites=list(row.seen_in_cites or []),
                origin=row.origin,
                revision=row.revision,
                position=TocPositionOut(**row.position) if row.position else None,
                edited_by=names.get(row.edited_by) if row.edited_by else None,
                edited_at=row.edited_at,
            )
            for row in rows.boxes.values()
        ],
        links=links,
        pathways=pathways,
        context=[row.text for row in rows.band_items if row.band == "context"],
        supporting_activities=[row.text for row in rows.band_items if row.band == "supporting"],
        grade_rules=[TocGradeRuleOut(label=label, rule=rule) for label, rule in rule_text()],
        confidence=lowest(link.verdict for link in links if link.critical),
        report=_report(conn, task_id),
        links_left_out=_links_left_out(conn, task_id),
    )


def _source_type(metadata: dict[str, Any]) -> Literal["academic", "policy", "web"]:
    backend = metadata.get("backend")
    if backend == "web":
        return "web"
    return "policy" if backend == "overton" else "academic"


#: Least relevance of a document whose levels a box shows (fit review, 2026-10-30).
BOX_FIGURE_RELEVANCE = 2


def toc_evidence_out(conn: Connection, task_id: uuid.UUID) -> TocEvidenceOut:
    """Build the evidence read: every judged document per link, case studies per box."""
    _, rows = store.load_graph(conn, task_id)
    evidence = list(
        conn.execute(
            select(
                toc_item_evidence,
                source_snapshot.c.metadata,
                source_snapshot.c.source_locator,
                source_appraisal_result.c.quality_score,
                source_classification_result.c.primary_evidence_type,
            )
            .select_from(
                toc_item_evidence.join(
                    task_source_snapshot,
                    (
                        task_source_snapshot.c.task_source_snapshot_id
                        == toc_item_evidence.c.task_source_snapshot_id
                    )
                    & (task_source_snapshot.c.task_id == toc_item_evidence.c.task_id),
                )
                .join(
                    source_snapshot,
                    source_snapshot.c.source_snapshot_id
                    == task_source_snapshot.c.source_snapshot_id,
                )
                .join(
                    capability_run,
                    (capability_run.c.capability_run_id == toc_item_evidence.c.capability_run_id)
                    & (capability_run.c.task_id == toc_item_evidence.c.task_id),
                )
                .outerjoin(
                    source_appraisal_result,
                    (
                        source_appraisal_result.c.evidence_scope_id
                        == capability_run.c.evidence_scope_id
                    )
                    & (source_appraisal_result.c.task_id == toc_item_evidence.c.task_id)
                    & (
                        source_appraisal_result.c.task_source_snapshot_id
                        == toc_item_evidence.c.task_source_snapshot_id
                    ),
                )
                .outerjoin(
                    source_classification_result,
                    (
                        source_classification_result.c.evidence_scope_id
                        == capability_run.c.evidence_scope_id
                    )
                    & (source_classification_result.c.task_id == toc_item_evidence.c.task_id)
                    & (
                        source_classification_result.c.task_source_snapshot_id
                        == toc_item_evidence.c.task_source_snapshot_id
                    ),
                )
            )
            .where(toc_item_evidence.c.task_id == task_id)
            .order_by(toc_item_evidence.c.created_at, toc_item_evidence.c.evidence_id)
        )
    )
    appraisals = appraisals_for(conn, task_id=task_id, evidence_rows=evidence)
    names = edits.names_of(
        conn,
        {
            uid
            for row in evidence
            for uid in (row.override_by, row.excluded_by, row.added_by)
            if uid is not None
        },
    )
    documents: dict[str, dict[uuid.UUID, TocDocumentOut]] = {key: {} for key in rows.links}
    case_studies: dict[str, list[tuple[TocCaseStudyOut, str, str | None, int, bool]]] = {
        key: [] for key in rows.boxes
    }
    indicators: dict[str, list[str]] = {key: [] for key in rows.boxes}
    # Each judged document's short citation, for its figures (C37).
    cites: dict[uuid.UUID, dict[str, Any]] = {}
    # The current judgement of each (link, document), for its figures' quote in context.
    judgement_of: dict[tuple[str, uuid.UUID], uuid.UUID] = {}
    #: The counted judgement's relevance, for which box figures show.
    relevance_of: dict[tuple[str, uuid.UUID], int] = {}
    #: Judgements that count now: accepted and not removed (C42, C44); only their figures show.
    countable: set[tuple[str, uuid.UUID]] = set()
    for row in evidence:
        key = str(row.link_id)
        link_row = rows.links.get(key)
        if link_row is None:
            continue
        metadata = cast(dict[str, Any], row.metadata or {})
        title = str(metadata.get("title") or "")
        year_value = metadata.get("publication_year", metadata.get("year"))
        year = int(year_value) if isinstance(year_value, int) else None
        url = _url(metadata, row.source_locator)
        source_type = _source_type(metadata)
        cites[row.task_source_snapshot_id] = {
            "task_source_snapshot_id": row.task_source_snapshot_id,
            "source_title": title,
            "source_authors": [author.name for author in _authorships(metadata)],
            "source_year": year,
            "source_venue": _venue(metadata),
            "source_type": source_type,
            "evidence_type": row.primary_evidence_type,
            "url": url,
        }
        previous = row.item_hash != link_row.counted_hash
        if not previous:
            judgement_of[(key, row.task_source_snapshot_id)] = row.evidence_id
            if row.status == "counted" and row.excluded_at is None:
                countable.add((key, row.task_source_snapshot_id))
            effective = row_judgement(row)
            relevance_of[(key, row.task_source_snapshot_id)] = (
                effective.relevance
                if effective.support != "not_about"
                and row.status == "counted"
                and row.excluded_at is None
                else 0
            )
        appraisal = appraisals.get(str(row.task_source_snapshot_id))
        existing = documents[key].get(row.task_source_snapshot_id)
        # One entry per document: the counted judgement wins over an earlier wording's.
        if existing is None or (existing.previous_wording and not previous):
            effective = row_judgement(row)
            documents[key][row.task_source_snapshot_id] = TocDocumentOut(
                evidence_id=row.evidence_id,
                task_source_snapshot_id=row.task_source_snapshot_id,
                title=title,
                authors=[author.name for author in _authorships(metadata)],
                year=year,
                url=url,
                source_type=source_type,
                evidence_type=row.primary_evidence_type,
                appraisal_score=row.quality_score,
                support=cast(Any, effective.support),
                quote=row.quote,
                relevance=effective.relevance,
                relevance_reason=row.relevance_reason,
                quality=quality(appraisal, row.robust_model),
                weight=round(weight(appraisal, effective), 3),
                condition=row.condition,
                previous_wording=previous,
                judge_support=row.support,
                judge_relevance=row.relevance,
                scored_by=names.get(row.override_by) if row.override_by else None,
                removed_by=names.get(row.excluded_by) if row.excluded_by else None,
                added_by=names.get(row.added_by) if row.added_by else None,
                status=row.status,
                revision=row.revision,
            )
        box = str(row.case_box_id) if row.case_box_id is not None else None
        if box in case_studies and row.case_study is not None:
            case = row.case_study
            out = TocCaseStudyOut(
                evidence_id=row.evidence_id,
                task_source_snapshot_id=row.task_source_snapshot_id,
                programme=str(case.get("programme") or ""),
                place=case.get("place"),
                note=str(case.get("note") or ""),
                quote=str(case.get("quote") or ""),
                title=title,
                authors=[author.name for author in _authorships(metadata)],
                year=year,
                url=url,
                source_type=source_type,
            )
            case_studies[box].append(
                (out, out.programme, out.place, *row_case_score(row, appraisal))
            )
        if box in indicators and row.indicator and row.indicator not in indicators[box]:
            indicators[box].append(row.indicator)
    link_figures: dict[str, list[TocFigureOut]] = {key: [] for key in rows.links}
    box_figures: dict[str, list[TocFigureOut]] = {key: [] for key in rows.boxes}
    for figure in conn.execute(
        select(toc_figure)
        .where(toc_figure.c.task_id == task_id)
        .order_by(toc_figure.c.created_at, toc_figure.c.figure_id)
    ):
        key = str(figure.link_id)
        link_row = rows.links.get(key)
        cite = cites.get(figure.task_source_snapshot_id)
        # Only the link's current wording counts, as for its judgements (C19).
        judgement = judgement_of.get((key, figure.task_source_snapshot_id))
        if (
            link_row is None
            or cite is None
            or judgement is None
            or figure.item_hash != link_row.counted_hash
            or (key, figure.task_source_snapshot_id) not in countable
        ):
            continue
        shown = TocFigureOut(
            **{
                name: getattr(figure, name)
                for name in TocFigureOut.model_fields
                if name not in cite and name in figure._mapping
            },
            evidence_id=judgement,
            **cite,
        )
        if figure.box == "link":
            link_figures[key].append(shown)
        elif relevance_of.get((key, figure.task_source_snapshot_id), 0) >= BOX_FIGURE_RELEVANCE:
            # A level of the link's source or target belongs to that box, when its
            # document applies here: a level from another country or setting misleads.
            end = str(link_row.source_box_id if figure.box == "source" else link_row.target_box_id)
            if end in box_figures:
                box_figures[end].append(shown)
    return TocEvidenceOut(
        links=[
            TocLinkEvidenceOut(
                link_id=uuid.UUID(key), documents=list(docs.values()), figures=link_figures[key]
            )
            for key, docs in documents.items()
        ],
        boxes=[
            TocBoxEvidenceOut(
                box_id=uuid.UUID(key),
                case_studies=top_case_studies(case_studies[key]),
                indicators=indicators[key],
                figures=box_figures[key],
            )
            for key in rows.boxes
        ],
    )


@router.get("", response_model=TocGraphOut)
def get_toc(
    task_id: uuid.UUID,
    user: Annotated[AuthenticatedUser | None, Depends(get_optional_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> TocGraphOut:
    """Return the theory: boxes, links with their verdicts and states, pathways, summary."""
    _readable_toc(conn, task_id, user)
    out = toc_graph_out(conn, task_id)
    out.can_edit = user is not None and _can_edit(conn, task_id, user.user_id)
    if out.can_edit:
        out.edits_since_review = len(edits_since_review(conn, task_id))
    return out


def _can_edit(conn: Connection, task_id: uuid.UUID, user_id: str) -> bool:
    """Whether the caller holds the write grade (C50); never raises."""
    try:
        accessible_task(conn, task_id=task_id, user_id=user_id, write=True)
    except HTTPException:
        return False
    return True


@router.get("/evidence", response_model=TocEvidenceOut)
def get_toc_evidence(
    task_id: uuid.UUID,
    user: Annotated[AuthenticatedUser | None, Depends(get_optional_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> TocEvidenceOut:
    """Return every judged document per link and every case study per box."""
    _readable_toc(conn, task_id, user)
    return toc_evidence_out(conn, task_id)


def toc_evidence_context_out(
    conn: Connection, task_id: uuid.UUID, evidence_id: uuid.UUID, quote: str | None = None
) -> ChunkContextOut | None:
    """One judgement's verified quote, highlighted in the text the judge read.

    The judge read the document's title and abstract (``check.Document.text``),
    so the passage comes from the same text, through the window helper the
    report's citation sidebar uses.

    Args:
        conn: Open connection.
        task_id: The task; another task's judgement is not found.
        evidence_id: The ``toc_item_evidence`` row.
        quote: Another passage of the same document to highlight (a figure's or
            a case study's quote); the judgement's own quote when ``None``.

    Returns:
        The window, or ``None`` when the row is unknown, has no quote, or the
        quote is not found once in the text.
    """
    row = conn.execute(
        select(
            toc_item_evidence.c.task_source_snapshot_id,
            toc_item_evidence.c.quote,
            source_snapshot.c.source_snapshot_id,
            source_snapshot.c.metadata,
        )
        .select_from(
            toc_item_evidence.join(
                task_source_snapshot,
                (
                    task_source_snapshot.c.task_source_snapshot_id
                    == toc_item_evidence.c.task_source_snapshot_id
                )
                & (task_source_snapshot.c.task_id == toc_item_evidence.c.task_id),
            ).join(
                source_snapshot,
                source_snapshot.c.source_snapshot_id == task_source_snapshot.c.source_snapshot_id,
            )
        )
        .where(toc_item_evidence.c.task_id == task_id)
        .where(toc_item_evidence.c.evidence_id == evidence_id)
    ).one_or_none()
    if row is None:
        return None
    quote = quote or row.quote
    if not quote:
        return None
    metadata = cast(dict[str, Any], row.metadata or {})
    text = Document(
        tss_id=row.task_source_snapshot_id,
        title=str(metadata.get("title") or ""),
        year=None,
        abstract=str(metadata.get("abstract") or ""),
        evidence_type=None,
        score=None,
    ).text
    return _clamped_quote_window(conn, task_id, text, quote, None, row.source_snapshot_id)


@router.get("/evidence/{evidence_id}/context", response_model=ChunkContextOut)
def get_toc_evidence_context(
    task_id: uuid.UUID,
    evidence_id: uuid.UUID,
    user: Annotated[AuthenticatedUser | None, Depends(get_optional_user)],
    conn: Annotated[Connection, Depends(get_conn)],
    quote: Annotated[str | None, Query(max_length=2_000)] = None,
) -> ChunkContextOut:
    """Return one judgement's quote, or another passage of its document, in its passage."""
    _readable_toc(conn, task_id, user)
    result = toc_evidence_context_out(conn, task_id, evidence_id, quote)
    if result is None:
        raise HTTPException(status_code=404, detail="resource not found")
    return result


# --- Editing (C41, C47, C10, C40) ---------------------------------------------------------


def _editable_toc(conn: Connection, task_id: uuid.UUID, user: AuthenticatedUser) -> None:
    """The write grade on a theory-of-change task (C50), or 403/404."""
    access = accessible_task(conn, task_id=task_id, user_id=user.user_id, write=True)
    if access.row["capability"] != THEORY_OF_CHANGE:
        raise ApiNotFound("toc_not_found", "this task is not a theory of change")


def _edit(fn: Any, **kwargs: Any) -> Any:
    """Run one edit, turning a refusal into the API's 409, 404 or 422."""
    try:
        return fn(**kwargs)
    except EditRefused as exc:
        if exc.status == 404:
            raise ApiNotFound("toc_not_found", exc.message) from exc
        if exc.status == 422:
            raise ApiUnprocessable("toc_invalid", exc.message) from exc
        raise ApiConflict(exc.code, exc.message) from exc


@router.post("/boxes", response_model=TocCreatedOut, status_code=201)
def create_toc_box(
    task_id: uuid.UUID,
    body: TocBoxCreate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> TocCreatedOut:
    """Add a box the user wrote (C41)."""
    _editable_toc(conn, task_id, user)
    box_id = _edit(
        edits.create_box,
        conn=conn,
        task_id=task_id,
        actor=edits.Actor(user.user_id),
        layer=body.layer,
        text=body.text,
        position=body.position.model_dump() if body.position else None,
    )
    return TocCreatedOut(id=box_id)


@router.patch("/boxes/{box_id}", response_model=TocRevisionOut)
def patch_toc_box(
    task_id: uuid.UUID,
    box_id: uuid.UUID,
    body: TocBoxPatch,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> TocRevisionOut:
    """Edit a box's text, layer, description or how we'd know it happened (C41)."""
    _editable_toc(conn, task_id, user)
    fields: dict[str, Any] = body.model_dump(
        exclude_unset=True, exclude={"expected_revision", "criteria"}
    )
    if body.criteria is not None:
        given = body.criteria.model_dump(exclude_unset=True)
        if "indicator" in given:
            fields["indicator"] = given.pop("indicator")
        if given:
            current = conn.execute(
                select(toc_box.c.result_criteria).where(
                    toc_box.c.box_id == box_id, toc_box.c.task_id == task_id
                )
            ).scalar_one_or_none()
            fields["result_criteria"] = {**(current or {}), **given}
    _edit(
        edits.edit_box,
        conn=conn,
        task_id=task_id,
        actor=edits.Actor(user.user_id),
        box_id=box_id,
        expected_revision=body.expected_revision,
        fields=fields,
    )
    return TocRevisionOut(revision=body.expected_revision + 1)


@router.delete("/boxes/{box_id}", status_code=204)
def delete_toc_box(
    task_id: uuid.UUID,
    box_id: uuid.UUID,
    expected_revision: Annotated[int, Query()],
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> None:
    """Delete a box and its links; Undo restores them with their evidence (C41)."""
    _editable_toc(conn, task_id, user)
    _edit(
        edits.delete_box,
        conn=conn,
        task_id=task_id,
        actor=edits.Actor(user.user_id),
        box_id=box_id,
        expected_revision=expected_revision,
    )


@router.patch("/boxes/{box_id}/position", response_model=TocRevisionOut)
def move_toc_box(
    task_id: uuid.UUID,
    box_id: uuid.UUID,
    body: TocMoveIn,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> TocRevisionOut:
    """Save where the user dropped a box (C47)."""
    _editable_toc(conn, task_id, user)
    revision = _edit(
        edits.move_box,
        conn=conn,
        task_id=task_id,
        actor=edits.Actor(user.user_id),
        box_id=box_id,
        expected_revision=body.expected_revision,
        position={"x": body.x, "y": body.y},
    )
    return TocRevisionOut(revision=revision)


@router.post("/layout/reset", status_code=204)
def reset_toc_layout(
    task_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> None:
    """Return every moved box to the computed layout (C47)."""
    _editable_toc(conn, task_id, user)
    edits.reset_layout(conn, task_id=task_id, actor=edits.Actor(user.user_id))


@router.post("/links", response_model=TocCreatedOut, status_code=201)
def create_toc_link(
    task_id: uuid.UUID,
    body: TocLinkCreate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> TocCreatedOut:
    """Connect two boxes (C41). The sentence starts from the box texts."""
    _editable_toc(conn, task_id, user)
    link_id = _edit(
        edits.create_link,
        conn=conn,
        task_id=task_id,
        actor=edits.Actor(user.user_id),
        source_box_id=body.source_box_id,
        target_box_id=body.target_box_id,
    )
    return TocCreatedOut(id=link_id)


@router.patch("/links/{link_id}", response_model=TocRevisionOut)
def patch_toc_link(
    task_id: uuid.UUID,
    link_id: uuid.UUID,
    body: TocLinkPatch,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> TocRevisionOut:
    """Edit a link's title, parts or conditions, or mark it critical (C41)."""
    _editable_toc(conn, task_id, user)
    actor = edits.Actor(user.user_id)
    if body.critical:
        _edit(
            edits.set_critical,
            conn=conn,
            task_id=task_id,
            actor=actor,
            link_id=link_id,
            expected_revision=body.expected_revision,
        )
        return TocRevisionOut(revision=body.expected_revision + 1)
    _edit(
        edits.edit_link,
        conn=conn,
        task_id=task_id,
        actor=actor,
        link_id=link_id,
        expected_revision=body.expected_revision,
        fields=body.model_dump(exclude_unset=True, exclude={"expected_revision", "critical"}),
    )
    return TocRevisionOut(revision=body.expected_revision + 1)


@router.delete("/links/{link_id}", status_code=204)
def delete_toc_link(
    task_id: uuid.UUID,
    link_id: uuid.UUID,
    expected_revision: Annotated[int, Query()],
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> None:
    """Delete a link; Undo restores it with its evidence (C41)."""
    _editable_toc(conn, task_id, user)
    _edit(
        edits.delete_link,
        conn=conn,
        task_id=task_id,
        actor=edits.Actor(user.user_id),
        link_id=link_id,
        expected_revision=expected_revision,
    )


@router.get("/history", response_model=list[TocHistoryEntryOut])
def get_toc_history(
    task_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> list[TocHistoryEntryOut]:
    """Who changed what, newest first (C41). Editors only: it names people."""
    _editable_toc(conn, task_id, user)
    return [
        TocHistoryEntryOut(
            event_id=entry.event_id,
            at=entry.at,
            who=entry.who,
            what=entry.what,
            undoable=entry.undoable,
        )
        for entry in edits.history(conn, task_id)
    ]


@router.post("/events/{event_id}/undo", response_model=TocUndoOut)
def undo_toc_edit(
    task_id: uuid.UUID,
    event_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> TocUndoOut:
    """Put back the state before one edit; rows changed since are skipped and named (C10)."""
    _editable_toc(conn, task_id, user)
    skipped = _edit(
        edits.undo,
        conn=conn,
        task_id=task_id,
        actor=edits.Actor(user.user_id),
        event_id=event_id,
    )
    return TocUndoOut(skipped=skipped)


@router.post("/check", response_model=TocCheckOut, status_code=202)
def start_toc_link_check(
    task_id: uuid.UUID,
    body: TocCheckIn,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
    settings: Annotated[Settings, Depends(get_settings)],
    executor: Annotated[ThreadPoolExecutor, Depends(get_executor)],
    backends: Annotated[RunnerBackends, Depends(get_runner_backends)],
) -> TocCheckOut:
    """Check named links only (C40): search, pick, judge, figures, summarise."""
    with engine.begin() as conn:
        _editable_toc(conn, task_id, user)
        known = set(
            conn.execute(
                select(toc_link.c.link_id).where(
                    toc_link.c.task_id == task_id, toc_link.c.link_id.in_(body.link_ids)
                )
            ).scalars()
        )
    if known != set(body.link_ids):
        raise ApiNotFound("toc_not_found", "a named connection is not in this theory")
    walk_id = start_toc_check(
        engine,
        task_id=task_id,
        link_ids=body.link_ids,
        user_id=user.user_id,
        settings=settings,
        executor=executor,
        backends=backends,
        mode=body.mode,
    )
    return TocCheckOut(capability_run_id=walk_id)


@router.patch("/evidence/{evidence_id}", response_model=TocRevisionOut)
def patch_toc_evidence(
    task_id: uuid.UUID,
    evidence_id: uuid.UUID,
    body: TocEvidencePatch,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> TocRevisionOut:
    """Remove a document from its link, restore it, or set or clear the user's scores (C42)."""
    _editable_toc(conn, task_id, user)
    _edit(
        edits.edit_evidence,
        conn=conn,
        task_id=task_id,
        actor=edits.Actor(user.user_id),
        evidence_id=evidence_id,
        expected_revision=body.expected_revision,
        action=body.action,
        support=body.support,
        relevance=body.relevance,
    )
    return TocRevisionOut(revision=body.expected_revision + 1)


@router.post("/links/keep", response_model=TocCountOut)
def keep_toc_evidence(
    task_id: uuid.UUID,
    body: TocLinksIn,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> TocCountOut:
    """Keep the evidence of edited links for their new wording (C43)."""
    _editable_toc(conn, task_id, user)
    return TocCountOut(
        count=edits.keep_evidence(
            conn, task_id=task_id, actor=edits.Actor(user.user_id), link_ids=body.link_ids
        )
    )


#: A DOI anywhere in what the user pasted: bare, ``doi:``, or a doi.org address.
_DOI = re.compile(r"10\.\d{4,9}/[^\s\"<>]+", re.IGNORECASE)


@router.post("/links/{link_id}/studies", response_model=TocCheckOut, status_code=202)
def add_toc_study(
    task_id: uuid.UUID,
    link_id: uuid.UUID,
    body: TocStudyIn,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
    settings: Annotated[Settings, Depends(get_settings)],
    executor: Annotated[ThreadPoolExecutor, Depends(get_executor)],
    backends: Annotated[RunnerBackends, Depends(get_runner_backends)],
) -> TocCheckOut:
    """Add a study to a link by its DOI (C42): Policy Atlas fetches, judges and adds it.

    A check named on the link runs with the DOI as its only search; the judge,
    figures, classify and appraise read it as any other document, and its
    judgement is marked as added by the user.
    """
    with engine.begin() as conn:
        _editable_toc(conn, task_id, user)
        known = conn.execute(
            select(toc_link.c.link_id).where(
                toc_link.c.task_id == task_id, toc_link.c.link_id == link_id
            )
        ).first()
    if known is None:
        raise ApiNotFound("toc_not_found", "that connection is not in this theory")
    found = _DOI.search(body.identifier)
    if found is None:
        raise ApiUnprocessable(
            "toc_invalid",
            "Paste the study's DOI (for example 10.1016/j.appet.2016.02.017) or its doi.org "
            "address. Other web addresses will work once web search is built.",
        )
    doi = found.group(0).rstrip(".,;)").lower()
    walk_id = start_toc_check(
        engine,
        task_id=task_id,
        link_ids=[link_id],
        user_id=user.user_id,
        settings=settings,
        executor=executor,
        backends=backends,
        mode="add_study",
        studies={str(link_id): [doi]},
    )
    return TocCheckOut(capability_run_id=walk_id)


@router.post("/links/{link_id}/decide", response_model=TocCountOut)
def decide_toc_pending(
    task_id: uuid.UUID,
    link_id: uuid.UUID,
    body: TocDecideIn,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> TocCountOut:
    """Accept or reject all the new evidence Find more evidence found on one link (C44)."""
    _editable_toc(conn, task_id, user)
    return TocCountOut(
        count=edits.decide_pending(
            conn,
            task_id=task_id,
            actor=edits.Actor(user.user_id),
            link_id=link_id,
            accept=body.accept,
        )
    )


@router.post("/check/stop", status_code=202)
def stop_toc_check(
    task_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> dict[str, str]:
    """Stop the running check before its next step; what it finished stays (C48)."""
    _editable_toc(conn, task_id, user)
    walk = _latest_walk(conn, task_id)
    if walk is None or walk.status != "running":
        raise ApiConflict("toc_not_running", "no check is running")
    events.append(
        conn,
        task_id=task_id,
        run_id=None,
        event_type=TOC_STOP_EVENT,
        payload={"capability_run_id": str(walk.capability_run_id), "by": user.user_id},
    )
    return {"status": "stopping"}


# --- Review, suggestions, the report and clarifications (C45, C46, C49) ----------------


@router.post("/review", status_code=202)
def start_toc_review(
    task_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
    executor: Annotated[ThreadPoolExecutor, Depends(get_executor)],
    backends: Annotated[RunnerBackends, Depends(get_runner_backends)],
) -> dict[str, str]:
    """Review the theory after edits, off the request path; the Task Agent reports (C45)."""
    with engine.begin() as conn:
        _editable_toc(conn, task_id, user)
    backend = backends.toc if backends.toc is not None else StubTocBackend()

    def review() -> None:
        try:
            with tracing.trace_scope(user_id=user.user_id):
                run_review(engine, task_id=task_id, backend=backend)
        except Exception:
            log.exception("toc_review.failed", task_id=str(task_id))

    executor.submit(review)
    return {"status": "reviewing"}


@router.get("/proposals", response_model=list[TocProposalOut])
def get_toc_proposals(
    task_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> list[TocProposalOut]:
    """The open suggestions, newest first (C45, C46)."""
    _editable_toc(conn, task_id, user)
    return [
        TocProposalOut(
            proposal_id=row.proposal_id,
            source=row.source,
            summary=row.summary,
            created_at=row.created_at,
            edits=[
                TocProposalEditOut(
                    index=i,
                    op=str(op.get("op")),
                    line=str(op.get("line") or proposals.describe(op)),
                    reason=str(op.get("reason") or ""),
                    status=op.get("status", "pending"),
                )
                for i, op in enumerate(row.edits)
            ],
            report_findings=[
                TocReportFindingOut(section=str(f.get("section")), why=str(f.get("why")))
                for f in row.report_findings
            ],
        )
        for row in proposals.open_proposals(conn, task_id)
    ]


@router.post("/proposals/{proposal_id}/decide", response_model=TocProblemsOut)
def decide_toc_proposal(
    task_id: uuid.UUID,
    proposal_id: uuid.UUID,
    body: TocProposalDecideIn,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> TocProblemsOut:
    """Accept or reject one suggested edit, or all; accepted edits apply as the user's (C45)."""
    _editable_toc(conn, task_id, user)
    problems = _edit(
        proposals.decide,
        conn=conn,
        task_id=task_id,
        actor=edits.Actor(user.user_id),
        proposal_id=proposal_id,
        index=body.index,
        accept=body.accept,
    )
    return TocProblemsOut(problems=problems)


@router.post("/proposals/{proposal_id}/dismiss", status_code=204)
def dismiss_toc_proposal(
    task_id: uuid.UUID,
    proposal_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> None:
    """Close a suggestion without acting on what is left of it."""
    _editable_toc(conn, task_id, user)
    proposals.close(conn, task_id=task_id, proposal_id=proposal_id)


@router.post("/report/update", response_model=TocCheckOut, status_code=202)
def update_toc_report(
    task_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
    settings: Annotated[Settings, Depends(get_settings)],
    executor: Annotated[ThreadPoolExecutor, Depends(get_executor)],
    backends: Annotated[RunnerBackends, Depends(get_runner_backends)],
    proposal_id: Annotated[uuid.UUID | None, Query()] = None,
) -> TocCheckOut:
    """Rewrite the titles, sentences and the report for the theory as it is now (C45)."""
    with engine.begin() as conn:
        _editable_toc(conn, task_id, user)
        if proposal_id is not None:
            proposals.close(conn, task_id=task_id, proposal_id=proposal_id)
    walk_id = start_toc_check(
        engine,
        task_id=task_id,
        link_ids=[],
        user_id=user.user_id,
        settings=settings,
        executor=executor,
        backends=backends,
        mode="report",
    )
    return TocCheckOut(capability_run_id=walk_id)


@router.post("/clarifications", status_code=204)
def add_toc_clarification(
    task_id: uuid.UUID,
    body: TocClarificationIn,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> None:
    """Add a clarification to the plan; the next check, search and review read it (C49)."""
    _editable_toc(conn, task_id, user)
    events.append(
        conn,
        task_id=task_id,
        run_id=None,
        event_type=TOC_CLARIFICATION_EVENT,
        payload={"text": body.text.strip(), "by": user.user_id},
    )
