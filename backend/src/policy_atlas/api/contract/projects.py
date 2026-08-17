"""Project resource contract: creation, partial update and the read shape.

Run state is never cached on the project row (spec § Projects); the
landing card derives running/paused/complete/interrupted from the derived
`latest_run` read model carried on every listed project.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .runs import RunStatus

#: Project lifecycle status. Contract (spec § Projects; soft-delete only).
ProjectStatus = Literal["active", "archived"]

#: Project display-name length bound (spec § Projects: `POST .../projects`).
PROJECT_NAME_MAX = 200


class ProjectCreate(BaseModel):
    """Inbound body for `POST /api/v1/projects`.

    Args:
        name: Project display name, 1-200 characters. Outer whitespace is
            stripped before the length constraint is applied
            (`str_strip_whitespace`).
        question: Optional initial evidence question.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=PROJECT_NAME_MAX)
    question: str | None = None


class ProjectUpdate(BaseModel):
    """Inbound body for `PATCH /api/v1/projects/{id}` (partial update).

    Args:
        name: New display name, when renaming. Omit to leave unchanged.
        question: New evidence question, when changing it. Omit to leave
            unchanged.
        portfolio_id: Portfolio to assign this project to, or an explicit
            `null` to unassign it. Omit to leave the assignment unchanged.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=PROJECT_NAME_MAX)
    question: str | None = None
    portfolio_id: uuid.UUID | None = None


class LatestRun(BaseModel):
    """The derived latest-run read model carried on a project.

    Args:
        capability_run_id: Identity of the project's most recent run.
        status: That run's current status.
        started_at: When that run started executing.
        ended_at: When that run reached a terminal status, or `None` while
            still running or paused.
    """

    capability_run_id: uuid.UUID
    status: RunStatus
    started_at: datetime
    ended_at: datetime | None = None


class ProjectOut(BaseModel):
    """A project resource.

    Args:
        project_id: The project's identity.
        name: Current display name.
        question: Current evidence question, or `None` if not yet set.
        status: Lifecycle status (`active` unless archived; no hard delete).
        created_at: When the project was created.
        updated_at: When the project row was last written.
        archived_at: When the project was archived, or `None` if active.
        latest_run: The derived latest-run read model, or `None` before any
            run has been created.
        portfolio_id: The portfolio this project belongs to, or `None` when it
            belongs to none. Unassigned is a normal state, not an error.
        source_count: How many sources this project has gathered, or `None`
            when no run has started. `None` and `0` differ: `None` means the
            question has not been asked yet, `0` means a run asked and found
            nothing.
    """

    project_id: uuid.UUID
    name: str
    question: str | None = None
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None
    latest_run: LatestRun | None = None
    portfolio_id: uuid.UUID | None = None
    source_count: int | None = None
