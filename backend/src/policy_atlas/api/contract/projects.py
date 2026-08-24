"""Project resource contract: creation, partial update and the read shape.

Run state is never cached on the project row (spec § Projects); the
landing card derives running/paused/complete/interrupted from the derived
`latest_run` read model carried on every listed project.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .runs import RunStatus
from .tenancy import Visibility

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
        visibility: How widely to share this project. Owner-only. Omit to
            leave unchanged. Cannot be combined with `portfolio_id` in one
            body — see :meth:`reject_visibility_with_portfolio`.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=PROJECT_NAME_MAX)
    question: str | None = None
    portfolio_id: uuid.UUID | None = None
    visibility: Visibility | None = None

    @model_validator(mode="after")
    def reject_visibility_with_portfolio(self) -> ProjectUpdate:
        """Refuse a body carrying both `visibility` and `portfolio_id`.

        Contract 033 § 6: the two orderings give different results — assign
        then set flips the row into a conflict, set then assign inherits the
        portfolio's visibility and discards what the caller asked for — so
        "the UI and a direct API caller get identical results" would be
        untestable. Rejecting the combination is the only reading that keeps
        the invariant deterministic.

        Tested against `model_fields_set`, not against `None`: an explicit
        `{"portfolio_id": null, "visibility": "private"}` (unassign *and*
        set) is exactly the ambiguous case, and a `None` check would wave it
        through.

        Returns:
            The validated model.

        Raises:
            ValueError: When both fields were supplied. FastAPI renders this
                as the contract's **422 `validation_error`**.
        """
        supplied = self.model_fields_set
        if "visibility" in supplied and "portfolio_id" in supplied:
            raise ValueError(
                "visibility and portfolio_id cannot be changed in the same request"
            )
        return self


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
        visibility: How widely the row is shared (task 033). `org` where the
            organisation may read it, `private` where only its owner may.
        is_owner: Whether the *calling* user owns this row. Per-caller, not a
            property of the row: the same project is `true` for its owner and
            `false` for a colleague reading it. Every read-only affordance on
            screen keys off this.
        owner_display: How to name the row's owner — the owner's display
            name, or a rendering derived from their subject when they have no
            identity row yet. **Never an email** (contract § 3b). `None` when
            the row has no owner at all (the CLI-created rows), leaving the
            placeholder glyph to the frontend.
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
    visibility: Visibility
    is_owner: bool
    owner_display: str | None
