"""Owner-scoped durable read-model routes."""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.engine import Connection

from policy_atlas.api.auth import AuthenticatedUser
from policy_atlas.api.contract import (
    PAGE_SIZE_DEFAULT,
    PAGE_SIZE_MAX,
    ArtefactOut,
    ChunkContextOut,
    CoverageOut,
    DecisionOut,
    EvidenceItemOut,
    EvidenceStatusFilter,
    ExtractProfile,
    FindingOut,
    FunnelOut,
    GroupsOut,
    LandscapeOut,
    Page,
    SourceDossierOut,
)
from policy_atlas.api.deps import get_conn, get_current_user
from policy_atlas.api.readmodels import repository
from policy_atlas.api.routers._access import accessible_project

router = APIRouter(
    prefix="/api/v1/projects",
    tags=["read-models"],
    dependencies=[Depends(get_current_user)],
)


def _owned(conn: Connection, project_id: uuid.UUID, user: AuthenticatedUser) -> None:
    """Enforce the read grade (owner or same-org colleague) once per route."""
    accessible_project(conn, project_id=project_id, user_id=user.user_id, write=False)


@router.get("/{project_id}/funnel", response_model=FunnelOut)
def funnel(
    project_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> FunnelOut:
    """Return the durable acquisition-to-citation funnel."""
    _owned(conn, project_id, user)
    return repository.funnel_out(conn, project_id)


@router.get("/{project_id}/landscape", response_model=LandscapeOut)
def landscape(
    project_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
    scope: Annotated[Literal["cited"] | None, Query()] = None,
) -> LandscapeOut:
    """Return screened-in-only or cited-only landscape distributions."""
    _owned(conn, project_id, user)
    return repository.landscape_out(conn, project_id, scope=scope)


@router.get("/{project_id}/groups", response_model=GroupsOut)
def groups(
    project_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> GroupsOut:
    """Return the latest grouping facets and residual counts."""
    _owned(conn, project_id, user)
    return repository.groups_out(conn, project_id)


@router.get("/{project_id}/evidence", response_model=Page[EvidenceItemOut])
def evidence(
    project_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAX)] = PAGE_SIZE_DEFAULT,
    status: Annotated[list[EvidenceStatusFilter] | None, Query()] = None,
    cited: Annotated[bool | None, Query()] = None,
    sort: Annotated[
        Literal["title", "year", "type", "strength", "status", "relevance"] | None, Query()
    ] = None,
    order: Annotated[Literal["asc", "desc"] | None, Query()] = None,
    theme: Annotated[uuid.UUID | None, Query()] = None,
    origin: Annotated[Literal["OpenAlex", "Overton", "Uploaded"] | None, Query()] = None,
    evidence_type: Annotated[str | None, Query(max_length=200)] = None,
    strength: Annotated[
        Literal["Very strong", "Strong", "Moderate", "Limited", "Weak"] | None, Query()
    ] = None,
    year_from: Annotated[int | None, Query(ge=1000, le=3000)] = None,
    year_to: Annotated[int | None, Query(ge=1000, le=3000)] = None,
) -> Page[EvidenceItemOut]:
    """Return a bounded page from the evidence status ladder, optionally filtered."""
    _owned(conn, project_id, user)
    if order is not None and sort is None:
        raise HTTPException(status_code=422, detail="order requires sort")
    return repository.evidence_page(
        conn,
        project_id,
        page,
        page_size,
        statuses=status,
        cited=cited,
        sort=sort,
        order=order,
        theme=theme,
        origin=origin,
        evidence_type=evidence_type,
        strength=strength,
        year_from=year_from,
        year_to=year_to,
    )


@router.get("/{project_id}/findings", response_model=Page[FindingOut])
def findings(
    project_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAX)] = PAGE_SIZE_DEFAULT,
    profile: Annotated[ExtractProfile | None, Query()] = None,
    facet: Annotated[str | None, Query()] = None,
    group: Annotated[str | None, Query()] = None,
    group_id: Annotated[str | None, Query()] = None,
    source_id: Annotated[uuid.UUID | None, Query()] = None,
) -> Page[FindingOut]:
    """Return a bounded page of IOF and ICF findings, optionally filtered."""
    _owned(conn, project_id, user)
    if group_id is not None and (facet is not None or group is not None):
        raise HTTPException(status_code=422, detail="group_id cannot be combined with facet/group")
    if (facet is None) != (group is None):
        raise HTTPException(status_code=422, detail="facet and group must be provided together")
    return repository.findings_page(
        conn,
        project_id,
        page,
        page_size,
        profile=profile,
        facet=facet,
        group=group,
        group_id=group_id,
        source_id=source_id,
    )


@router.get("/{project_id}/sources/{source_id}", response_model=SourceDossierOut)
def source_dossier(
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> SourceDossierOut:
    """Return one owner-scoped source dossier or an indistinguishable 404."""
    _owned(conn, project_id, user)
    result = repository.source_dossier_out(conn, project_id, source_id)
    if result is None:
        raise HTTPException(status_code=404, detail="resource not found")
    return result


@router.get("/{project_id}/decisions", response_model=Page[DecisionOut])
def decisions(
    project_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAX)] = PAGE_SIZE_DEFAULT,
) -> Page[DecisionOut]:
    """Return the allowlisted audit and steering decision history."""
    _owned(conn, project_id, user)
    return repository.decisions_page(conn, project_id, page, page_size)


@router.get("/{project_id}/artefact", response_model=ArtefactOut)
def artefact(
    project_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> ArtefactOut:
    """Return the latest persisted synthesis artefact or a shaped absence."""
    _owned(conn, project_id, user)
    result = repository.artefact_out(conn, project_id)
    if result is None:
        raise HTTPException(status_code=404, detail="resource not found")
    return result


@router.get("/{project_id}/coverage", response_model=CoverageOut)
def coverage(
    project_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> CoverageOut:
    """Return the composed latest search coverage statement."""
    _owned(conn, project_id, user)
    result = repository.coverage_out(conn, project_id)
    if result is None:
        raise HTTPException(status_code=404, detail="resource not found")
    return result


@router.get("/{project_id}/citations/{citation_key}/context", response_model=ChunkContextOut)
def chunk_context(
    project_id: uuid.UUID,
    citation_key: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> ChunkContextOut:
    """Return a clamped context window for an artefact citation id."""
    _owned(conn, project_id, user)
    result = repository.chunk_context_out(conn, project_id, citation_key)
    if result is None:
        raise HTTPException(status_code=404, detail="resource not found")
    return result

@router.get("/{project_id}/chunks/{chunk_id}/context", response_model=ChunkContextOut)
def chat_chunk_context(
    project_id: uuid.UUID,
    chunk_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
    quote: Annotated[str | None, Query(min_length=1, max_length=500)] = None,
) -> ChunkContextOut:
    """Return a clamped context window for a chat citation's chunk + quote.

    Chat citations carry durable chunk ids (not artefact citation-table ids),
    so the hover quote-in-context read resolves the quote inside the cited
    chunk directly — same window mechanics as the artefact citation seam.
    ``quote`` is validated AFTER ownership so cross-owner and unknown ids stay
    404-indistinguishable (the conformance sweep's byte-identical rule).
    """
    _owned(conn, project_id, user)
    if quote is None:
        raise HTTPException(status_code=422, detail="quote is required")
    result = repository.chunk_quote_context_out(conn, project_id, chunk_id, quote)
    if result is None:
        raise HTTPException(status_code=404, detail="resource not found")
    return result
