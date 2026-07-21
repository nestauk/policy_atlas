"""Owner-scoped durable read-model routes."""

from __future__ import annotations

import uuid
from typing import Annotated

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
    FindingOut,
    FunnelOut,
    GroupsOut,
    LandscapeOut,
    Page,
)
from policy_atlas.api.deps import get_conn, get_current_user
from policy_atlas.api.readmodels import repository
from policy_atlas.api.routers._common import owned_project

router = APIRouter(
    prefix="/api/v1/projects",
    tags=["read-models"],
    dependencies=[Depends(get_current_user)],
)


def _owned(conn: Connection, project_id: uuid.UUID, user: AuthenticatedUser) -> None:
    """Enforce the API's indistinguishable missing/cross-owner 404 once per route."""
    owned_project(conn, project_id=project_id, user_id=user.user_id)


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
) -> LandscapeOut:
    """Return screened-in-only landscape distributions."""
    _owned(conn, project_id, user)
    return repository.landscape_out(conn, project_id)


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
) -> Page[EvidenceItemOut]:
    """Return a bounded page from the evidence status ladder."""
    _owned(conn, project_id, user)
    return repository.evidence_page(conn, project_id, page, page_size)


@router.get("/{project_id}/findings", response_model=Page[FindingOut])
def findings(
    project_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAX)] = PAGE_SIZE_DEFAULT,
) -> Page[FindingOut]:
    """Return a bounded page of IOF and ICF findings."""
    _owned(conn, project_id, user)
    return repository.findings_page(conn, project_id, page, page_size)


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
