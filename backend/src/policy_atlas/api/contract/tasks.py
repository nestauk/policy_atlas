"""Task resource contract: creation, partial update and the read shape.

Run state is never cached on the task row (spec § Tasks); the
landing card derives running/paused/complete/interrupted from the derived
`latest_run` read model carried on every listed task.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common import reject_explicit_nulls
from .runs import RunStatus
from .tenancy import Visibility

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
        project_ids: Projects to assign this task to. Omit to leave
            membership unchanged; `[]` unassigns every project; a list
            replaces the set.
        visibility: How widely to share this task. Owner-only. Omit to
            leave unchanged; an explicit `null` is refused 422. Cannot be
            combined with `project_ids` in one body — see
            :meth:`reject_visibility_with_project`.
        is_public: Owner-only public-sharing flag (task 037). Omit to leave
            unchanged; an explicit `null` is refused 422 — see
            :meth:`reject_nulls_without_meaning`.

    Note:
        `name`, `visibility` and `is_public` back NOT NULL columns, so an
        explicit `null` on any of them is refused rather than treated as
        "unchanged" — see :meth:`reject_nulls_without_meaning`. `question`
        and `project_ids` are not: null clears the question, and null on
        `project_ids` is read as `[]` (unassign every project).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=TASK_NAME_MAX)
    question: str | None = None
    project_ids: list[uuid.UUID] | None = None
    visibility: Visibility | None = None
    is_public: bool | None = None

    @model_validator(mode="after")
    def reject_nulls_without_meaning(self) -> TaskUpdate:
        """Refuse an explicit null on `name`, `visibility` or `is_public` rather than 500.

        All three back NOT NULL columns, and the route dumps with
        `exclude_unset`, so an explicit null was *included* in the changes
        and written: `name` reached `rename_task`, `visibility` and
        `is_public` reached the UPDATE, and each produced a constraint
        violation rendered as **500 internal**. A malformed body is a 422,
        and `ProjectUpdate` already said so about its own `visibility`.

        Returns:
            The validated model.

        Raises:
            ValueError: When any of the three fields was supplied as null.
        """
        reject_explicit_nulls(self, "name", "visibility", "is_public")
        return self

    @model_validator(mode="after")
    def reject_visibility_with_project(self) -> TaskUpdate:
        """Refuse a body carrying both `visibility` and `project_ids`.

        Contract 033 § 6: the two orderings give different results — assign
        then set flips the row into a conflict, set then assign inherits the
        project's visibility and discards what the caller asked for — so
        "the UI and a direct API caller get identical results" would be
        untestable. Rejecting the combination is the only reading that keeps
        the invariant deterministic.

        Tested against `model_fields_set`, not against `None`: an explicit
        `{"project_ids": null, "visibility": "private"}` (unassign *and*
        set) is exactly the ambiguous case, and a `None` check would wave it
        through.

        Returns:
            The validated model.

        Raises:
            ValueError: When both fields were supplied. FastAPI renders this
                as the contract's **422 `validation_error`**.
        """
        supplied = self.model_fields_set
        if "visibility" in supplied and "project_ids" in supplied:
            raise ValueError(
                "visibility and project_ids cannot be changed in the same request"
            )
        return self


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
        project_ids: Projects this task belongs to. Empty means
            unassigned, which is a normal state, not an error.
        source_count: How many Included sources this task has (funnel
            `relevant`), or `None` when no run has started. `None` and `0`
            differ: `None` means the question has not been asked yet, `0`
            means a run asked and none are Included.
        visibility: How widely the row is shared (task 033). `org` where the
            organisation may read it, `private` where only its owner may.
        is_owner: Whether the *calling* user owns this row. Per-caller, not a
            property of the row: the same task is `true` for its owner and
            `false` for a colleague reading it. Every read-only affordance on
            screen keys off this.
        owner_display: How to name the row's owner — the owner's display
            name, or a rendering derived from their subject when they have no
            identity row yet. **Never an email** (contract § 3b). `None` when
            the row has no owner at all (the CLI-created rows), leaving the
            placeholder glyph to the frontend.
        is_public: Whether the owner has turned public sharing on for this
            row (task 037). A property of the row, not the caller.
        access: **Caller-relative**, not a property of the row: `"public"`
            means this read was served by the public leg and the shape is
            redacted (`owner_display = None`, `project_ids = []`,
            `is_owner = False`); a graded read (owner, colleague or admin)
            always says `"full"`.
    """

    task_id: uuid.UUID
    name: str
    question: str | None = None
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None
    latest_run: LatestRun | None = None
    project_ids: list[uuid.UUID] = Field(default_factory=list)
    source_count: int | None = None
    visibility: Visibility
    is_owner: bool
    owner_display: str | None
    is_public: bool
    access: Literal["full", "public"]
