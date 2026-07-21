"""Project-scoped serialization primitives for API mutations."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.engine import Connection, RowMapping

from policy_atlas.core.schema import project


def project_lock(conn: Connection, project_id: uuid.UUID) -> RowMapping:
    """Lock one project row for the duration of the caller transaction.

    Args:
        conn: Open transaction that owns the lock.
        project_id: Project to serialise mutations for.

    Returns:
        The locked project row.

    Raises:
        LookupError: If the project does not exist.
    """
    row = conn.execute(
        select(project).where(project.c.project_id == project_id).with_for_update()
    ).mappings().one_or_none()
    if row is None:
        raise LookupError(f"unknown project id: {project_id}")
    return row
