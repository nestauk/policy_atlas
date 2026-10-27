"""The theory-of-change read routes (task 054, S14; C17).

Three reads under ``/api/v1/tasks/{task_id}/toc``, public-readable like the
Result and Sources tabs (the read grade or the narrow public leg, through
``_readable``): the graph with both grades, link states and the summary;
every judged document and case study; and one judgement's quote in its
passage. Grades and states are computed on read
(C4, C19). A readable task that is not a theory of change is a 404
``toc_not_found``; an unreadable one keeps the generic ``not_found``.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.engine import Connection, Row

from policy_atlas.api.app import ApiNotFound
from policy_atlas.api.auth import AuthenticatedUser
from policy_atlas.api.contract.read_models import ChunkContextOut
from policy_atlas.api.contract.toc import (
    TocBoxEvidenceOut,
    TocBoxOut,
    TocCaseStudyOut,
    TocDocumentOut,
    TocEvidenceOut,
    TocGradeOut,
    TocGradeRuleOut,
    TocGraphOut,
    TocLinkEvidenceOut,
    TocLinkOut,
    TocPathwayOut,
    TocResultCriteriaOut,
    TocStanceOut,
    TocSummaryOut,
)
from policy_atlas.api.deps import get_conn, get_optional_user
from policy_atlas.api.readmodels.repository import _authorships, _clamped_quote_window, _url
from policy_atlas.api.routers._access import readable_or_public_task
from policy_atlas.core.schema import (
    capability_run,
    event_log,
    evidence_scope,
    source_appraisal_result,
    source_classification_result,
    source_snapshot,
    task_source_snapshot,
    toc_item_evidence,
    toc_pathway_link,
)
from policy_atlas.runtime.capability_registry import THEORY_OF_CHANGE
from policy_atlas.runtime.option_search import TOC_ITEM_SEARCHES_STAGE
from policy_atlas.runtime.toc_plan import TOC_PURPOSE, TOC_WALK_CHECK, TOC_WALK_KEY
from policy_atlas.theory_of_change import store
from policy_atlas.theory_of_change.check import (
    MODELLING_TYPE,
    Document,
    appraisals_for,
    counted_judgements,
    is_merged,
    link_grades,
    row_case_score,
    top_case_studies,
)
from policy_atlas.theory_of_change.evidence.grade import DocAppraisal, lower, rule_text
from policy_atlas.theory_of_change.graph import assumption_type, item_hash, link_state

router = APIRouter(prefix="/api/v1/tasks/{task_id}/toc", tags=["theory-of-change"])

CheckStatus = Literal["none", "drafting", "checking", "checked", "failed"]


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
    return "failed"


def _summary(conn: Connection, task_id: uuid.UUID) -> TocSummaryOut | None:
    payload = conn.execute(
        select(event_log.c.payload)
        .where(event_log.c.task_id == task_id)
        .where(event_log.c.event_type == "component.completed")
        .where(event_log.c.payload["component"].astext == "toc_summarise")
        .order_by(event_log.c.sequence.desc())
        .limit(1)
    ).scalar_one_or_none()
    if not isinstance(payload, dict) or "about" not in payload:
        return None
    return TocSummaryOut(
        about=str(payload["about"]),
        evidence_says=str(payload.get("evidence_says") or ""),
        evaluation_questions=[str(q) for q in payload.get("evaluation_questions") or []],
    )


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
    appraisals = appraisals_for(
        conn, task_id=task_id, evidence_rows=[r for group in counted.values() for r in group]
    )
    judged_hashes = {
        (str(row.link_id), row.item_hash)
        for row in conn.execute(
            select(toc_item_evidence.c.link_id, toc_item_evidence.c.item_hash)
            .where(toc_item_evidence.c.task_id == task_id)
            .distinct()
        )
    }
    links: list[TocLinkOut] = []
    for key, row in rows.links.items():
        link = graph.links[key]
        source, target = graph.boxes[link.source], graph.boxes[link.target]
        current = item_hash(link, source.text, target.text)
        elsewhere, here = link_grades(counted.get(key, []), appraisals)
        links.append(
            TocLinkOut(
                link_id=row.link_id,
                source_box_id=row.source_box_id,
                target_box_id=row.target_box_id,
                sentence=row.sentence or "",
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
                    checking=status == "checking" and (key, current) not in judged_hashes,
                ),
                elsewhere=TocGradeOut(**elsewhere.__dict__),
                here=TocGradeOut(**here.__dict__),
                lower_grade=lower(elsewhere.grade, here.grade),
                elsewhere_sentence=row.elsewhere_sentence,
                here_sentence=row.here_sentence,
                merged=is_merged(counted.get(key, [])),
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
                text=row.text,
                dosage=row.dosage,
                result_criteria=TocResultCriteriaOut(
                    definition=(row.result_criteria or {}).get("definition"),
                    indicator=row.indicator,
                    timing=(row.result_criteria or {}).get("timing"),
                ),
                description=row.description,
                origin=row.origin,
                revision=row.revision,
            )
            for row in rows.boxes.values()
        ],
        links=links,
        pathways=pathways,
        context=[row.text for row in rows.band_items if row.band == "context"],
        supporting_activities=[row.text for row in rows.band_items if row.band == "supporting"],
        summary=_summary(conn, task_id),
        grade_rules=[TocGradeRuleOut(label=label, rule=rule) for label, rule in rule_text()],
        links_left_out=_links_left_out(conn, task_id),
    )


def _source_type(metadata: dict[str, Any]) -> Literal["academic", "policy", "web"]:
    backend = metadata.get("backend")
    if backend == "web":
        return "web"
    return "policy" if backend == "overton" else "academic"


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
    documents: dict[str, dict[uuid.UUID, TocDocumentOut]] = {key: {} for key in rows.links}
    case_studies: dict[str, list[tuple[TocCaseStudyOut, str, str | None, int, bool]]] = {
        key: [] for key in rows.boxes
    }
    indicators: dict[str, list[str]] = {key: [] for key in rows.boxes}
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
        previous = row.item_hash != link_row.counted_hash
        existing = documents[key].get(row.task_source_snapshot_id)
        # One entry per document: the counted judgement wins over an earlier wording's.
        if existing is None or (existing.previous_wording and not previous):
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
                elsewhere=TocStanceOut(stance=row.stance_elsewhere, quote=row.quote_elsewhere),
                here=TocStanceOut(stance=row.stance_here, quote=row.quote_here),
                condition=row.condition,
                previous_wording=previous,
            )
        box = str(row.case_box_id) if row.case_box_id is not None else None
        if box in case_studies and row.case_study is not None:
            case = row.case_study
            out = TocCaseStudyOut(
                task_source_snapshot_id=row.task_source_snapshot_id,
                programme=str(case.get("programme") or ""),
                place=case.get("place"),
                note=str(case.get("note") or ""),
                quote=str(case.get("quote") or ""),
                title=title,
                year=year,
                url=url,
                source_type=source_type,
            )
            appraisal = DocAppraisal(
                score=row.quality_score, modelling=row.primary_evidence_type == MODELLING_TYPE
            )
            case_studies[box].append(
                (out, out.programme, out.place, *row_case_score(row, appraisal))
            )
        if box in indicators and row.indicator and row.indicator not in indicators[box]:
            indicators[box].append(row.indicator)
    return TocEvidenceOut(
        links=[
            TocLinkEvidenceOut(link_id=uuid.UUID(key), documents=list(docs.values()))
            for key, docs in documents.items()
        ],
        boxes=[
            TocBoxEvidenceOut(
                box_id=uuid.UUID(key),
                case_studies=top_case_studies(case_studies[key]),
                indicators=indicators[key],
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
    """Return the theory: boxes, links with both grades and states, pathways, summary."""
    _readable_toc(conn, task_id, user)
    return toc_graph_out(conn, task_id)


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
    conn: Connection, task_id: uuid.UUID, evidence_id: uuid.UUID, question: str
) -> ChunkContextOut | None:
    """One judgement's verified quote, highlighted in the text the judge read.

    The judge read the document's title and abstract (``check.Document.text``),
    so the passage comes from the same text, through the window helper the
    report's citation sidebar uses.

    Args:
        conn: Open connection.
        task_id: The task; another task's judgement is not found.
        evidence_id: The ``toc_item_evidence`` row.
        question: ``elsewhere`` or ``here``, the stance whose quote to show.

    Returns:
        The window, or ``None`` when the row is unknown, has no quote for that
        question, or the quote is not found once in the text.
    """
    row = conn.execute(
        select(
            toc_item_evidence.c.task_source_snapshot_id,
            toc_item_evidence.c.quote_elsewhere,
            toc_item_evidence.c.quote_here,
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
    quote = row.quote_elsewhere if question == "elsewhere" else row.quote_here
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
    question: Literal["elsewhere", "here"] | None = None,
) -> ChunkContextOut:
    """Return one judgement's quote highlighted in its passage.

    ``question`` (``elsewhere`` or ``here``) picks the stance. It is checked
    after access, so an unreadable task stays the same 404 with or without it.
    """
    _readable_toc(conn, task_id, user)
    if question is None:
        raise HTTPException(status_code=422, detail="question is required")
    result = toc_evidence_context_out(conn, task_id, evidence_id, question)
    if result is None:
        raise HTTPException(status_code=404, detail="resource not found")
    return result
