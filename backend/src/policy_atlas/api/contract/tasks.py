"""Task resource contract: creation, partial update and the read shape.

Run state is never cached on the task row (spec § Tasks); the
landing card derives running/paused/complete/interrupted from the derived
`latest_run` read model carried on every listed task.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .runs import RunStatus

#: Task lifecycle status. Contract (spec § Tasks; soft-delete only).
TaskStatus = Literal["active", "archived"]

#: Task display-name length bound (spec § Tasks: `POST .../tasks`).
TASK_NAME_MAX = 200


class TaskCreate(BaseModel):
    """Inbound body for `POST /api/v1/tasks`.

    Args:
        name: Task display name, 1-200 characters. Outer whitespace is
            stripped before the length constraint is applied
            (`str_strip_whitespace`).
        question: Optional initial evidence question.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=TASK_NAME_MAX)
    question: str | None = None


class TaskUpdate(BaseModel):
    """Inbound body for `PATCH /api/v1/tasks/{id}` (partial update).

    Args:
        name: New display name, when renaming. Omit to leave unchanged.
        question: New evidence question, when changing it. Omit to leave
            unchanged.
        project_id: Project to assign this task to, or an explicit
            `null` to unassign it. Omit to leave the assignment unchanged.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=TASK_NAME_MAX)
    question: str | None = None
    project_id: uuid.UUID | None = None


class LatestRun(BaseModel):
    """The derived latest-run read model carried on a task.

    Args:
        capability_run_id: Identity of the task's most recent run.
        status: That run's current status.
        started_at: When that run started executing.
        ended_at: When that run reached a terminal status, or `None` while
            still running or paused.
    """

    capability_run_id: uuid.UUID
    status: RunStatus
    started_at: datetime
    ended_at: datetime | None = None


class TaskOut(BaseModel):
    """A task resource.

    Args:
        task_id: The task's identity.
        name: Current display name.
        question: Current evidence question, or `None` if not yet set.
        status: Lifecycle status (`active` unless archived; no hard delete).
        created_at: When the task was created.
        updated_at: When the task row was last written.
        archived_at: When the task was archived, or `None` if active.
        latest_run: The derived latest-run read model, or `None` before any
            run has been created.
        project_id: The project this task belongs to, or `None` when it
            belongs to none. Unassigned is a normal state, not an error.
        source_count: How many sources this task has gathered, or `None`
            when no run has started. `None` and `0` differ: `None` means the
            question has not been asked yet, `0` means a run asked and found
            nothing.
    """

    task_id: uuid.UUID
    name: str
    question: str | None = None
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None
    latest_run: LatestRun | None = None
    project_id: uuid.UUID | None = None
    source_count: int | None = None
