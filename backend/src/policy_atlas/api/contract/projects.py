"""Project resource contract: a named grouping above the task row.

Since task 038 the screen word and the code word agree: this row is a **Project**
and a `task` row is a **Task**. A project holds no plan, no run and no evidence of its
own: it carries a name, a description and an owner, and its task count is
derived at read time rather than cached on the row.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common import reject_explicit_nulls
from .tenancy import Visibility

#: Project display-name length bound, matching the task row's bound.
PROJECT_NAME_MAX = 200


class ProjectCreate(BaseModel):
    """Inbound body for `POST /api/v1/projects`.

    Args:
        name: Project display name, 1-200 characters. Outer whitespace is
            stripped before the length constraint is applied.
        description: Optional free-text description.
        from_task_id: Seed the new project from an existing task the
            caller **owns**: the project inherits that task's
            `visibility` and organisation and takes it as its first member,
            in one transaction (contract § 6, i.1). Omit to create an empty
            project. This amends ADR 0031 decision 4 ("assignment is a
            PATCH, not a field on create"); ADR 0033 records the amendment.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=PROJECT_NAME_MAX)
    description: str | None = None
    from_task_id: uuid.UUID | None = None


class ProjectUpdate(BaseModel):
    """Inbound body for `PATCH /api/v1/projects/{id}` (partial update).

    Args:
        name: New display name, when renaming. Omit to leave unchanged; an
            explicit `null` is refused 422 (the column is NOT NULL).
        description: New description, when changing it, or an explicit `null`
            to clear it. Omit to leave unchanged.
        visibility: How widely to share this project **and every task
            assigned to it** — supplying it runs the i.4 cascade, not a field
            write (contract § 6). Owner-only. Omit to leave unchanged; an
            explicit `null` is refused 422, because there is no such thing as
            "no visibility" (the column is NOT NULL) and silently ignoring it
            would give one request shape two outcomes.

    Note:
        The field arrives here **with** the cascade and never without it
        (contract § 6, i.4: the cascade is the only writer of
        `project.visibility`, because a project's visibility change must
        carry every member with it). The route keeps it out of its patchable
        column list and routes it explicitly, so no splat can ever hand the
        column to this field: an owner setting a Project private and leaving
        its Tasks readable by the whole organisation is not a state this
        route can produce.

        Unlike `TaskUpdate`, no pairing is rejected: `name`, `description`
        and `visibility` are independent writes with no ordering between
        them, so one body carrying all three has exactly one outcome. The
        pairing `TaskUpdate` refuses is ambiguous for the opposite reason —
        there `visibility` and `project_id` fight over the same column.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=PROJECT_NAME_MAX)
    description: str | None = None
    visibility: Visibility | None = None

    @model_validator(mode="after")
    def reject_nulls_without_meaning(self) -> ProjectUpdate:
        """Refuse `{"visibility": null}` and `{"name": null}` as "unchanged".

        For `visibility`, `None` is the *absent* value, so the route can read
        "the caller asked for a cascade" straight off `visibility is not
        None`. An explicit null that validated would make that reading false
        for one body shape only — the kind of near-miss the invariant cannot
        afford — and it cannot mean anything else: `project.visibility` is
        NOT NULL.

        `name` joins it for the same reason and one more: the route writes it
        by splat from an `exclude_unset` dump, so an explicit null was written
        to a NOT NULL column and the request 500d. `description` does **not**
        join them — that column is nullable and null clears it.

        Returns:
            The validated model.

        Raises:
            ValueError: When either field was supplied as null. FastAPI
                renders this as the contract's **422 `validation_error`**.
        """
        reject_explicit_nulls(self, "name", "visibility")
        return self


class ProjectOut(BaseModel):
    """A project resource.

    Args:
        project_id: The project's identity.
        name: Current display name.
        description: Current description, or `None` if not set.
        created_at: When the project was created.
        task_count: How many active tasks **the caller may read, in the
            caller's own organisation** are assigned to this project,
            derived per request and never cached on the row (contract § 8).
            A colleague's private member is not counted, and an
            administrator's count stays their own organisation's count rather
            than a cross-organisation sum.
        visibility: How widely the row is shared (task 033). `org` where the
            organisation may read it, `private` where only its owner may.
        is_owner: Whether the *calling* user owns this row. Per-caller, not a
            property of the row.
        owner_display: How to name the row's owner — the owner's display
            name, or a rendering derived from their subject when they have no
            identity row yet. **Never an email** (contract § 3b). `None` when
            the row has no owner at all.
    """

    project_id: uuid.UUID
    name: str
    description: str | None = None
    created_at: datetime
    task_count: int
    visibility: Visibility
    is_owner: bool
    owner_display: str | None
