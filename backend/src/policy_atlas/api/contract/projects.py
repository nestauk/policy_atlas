"""Project resource contract: a named grouping above the task row.

The screen calls a project a **Task** and calls a `task` row a **Task**
(task 032 § Terms). A project holds no plan, no run and no evidence of its
own: it carries a name, a description and an owner, and its task count is
derived at read time rather than cached on the row.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

#: Project display-name length bound, matching the task row's bound.
PROJECT_NAME_MAX = 200


class ProjectCreate(BaseModel):
    """Inbound body for `POST /api/v1/projects`.

    Args:
        name: Project display name, 1-200 characters. Outer whitespace is
            stripped before the length constraint is applied.
        description: Optional free-text description.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=PROJECT_NAME_MAX)
    description: str | None = None


class ProjectUpdate(BaseModel):
    """Inbound body for `PATCH /api/v1/projects/{id}` (partial update).

    Args:
        name: New display name, when renaming. Omit to leave unchanged.
        description: New description, when changing it. Omit to leave
            unchanged.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=PROJECT_NAME_MAX)
    description: str | None = None


class ProjectOut(BaseModel):
    """A project resource.

    Args:
        project_id: The project's identity.
        name: Current display name.
        description: Current description, or `None` if not set.
        created_at: When the project was created.
        task_count: How many of the caller's active tasks are assigned to
            this project, derived per request and never cached on the row.
    """

    project_id: uuid.UUID
    name: str
    description: str | None = None
    created_at: datetime
    task_count: int
