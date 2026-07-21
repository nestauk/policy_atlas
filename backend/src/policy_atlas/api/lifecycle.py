"""Transactional project lifecycle operations and their audit events."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select, update
from sqlalchemy.engine import Connection

from policy_atlas.core import events
from policy_atlas.core.schema import project

log = structlog.get_logger()


def rename_project(
    conn: Connection,
    project_id: uuid.UUID,
    new_name: str,
    actor: str,
) -> None:
    """Rename a project and append its audit event in the caller transaction.

    Args:
        conn: Open connection whose transaction owns both writes.
        project_id: Project to rename.
        new_name: New project name.
        actor: Authenticated actor recorded in the event payload.

    Raises:
        LookupError: If ``project_id`` does not identify a project.
    """
    name_from = conn.execute(
        select(project.c.name).where(project.c.project_id == project_id)
    ).scalar_one_or_none()
    if name_from is None:
        raise LookupError(f"unknown project id: {project_id}")

    timestamp = datetime.now(UTC)
    conn.execute(
        update(project)
        .where(project.c.project_id == project_id)
        .values(name=new_name, updated_at=timestamp)
    )
    events.append(
        conn,
        project_id=project_id,
        run_id=None,
        event_type="project.renamed",
        payload={"name_from": name_from, "name_to": new_name, "actor": actor},
    )
    log.info("project.renamed", project_id=str(project_id), actor=actor)


def archive_project(conn: Connection, project_id: uuid.UUID, actor: str) -> bool:
    """Archive a project once and append a same-transaction audit event.

    Args:
        conn: Open connection whose transaction owns both writes.
        project_id: Project to archive.
        actor: Authenticated actor recorded in the event payload.

    Returns:
        ``True`` when this call archived the project, ``False`` when it was
        already archived.

    Raises:
        LookupError: If ``project_id`` does not identify a project.
    """
    status = conn.execute(
        select(project.c.status)
        .where(project.c.project_id == project_id)
        .with_for_update()
    ).scalar_one_or_none()
    if status is None:
        raise LookupError(f"unknown project id: {project_id}")
    if status == "archived":
        return False

    timestamp = datetime.now(UTC)
    conn.execute(
        update(project)
        .where(project.c.project_id == project_id)
        .values(status="archived", archived_at=timestamp, updated_at=timestamp)
    )
    events.append(
        conn,
        project_id=project_id,
        run_id=None,
        event_type="project.archived",
        payload={"actor": actor},
    )
    log.info("project.archived", project_id=str(project_id), actor=actor)
    return True
