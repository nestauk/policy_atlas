"""Portfolio resource contract: a named grouping above the project row.

The screen calls a portfolio a **Project** and calls a `project` row a **Task**
(task 032 § Terms). A portfolio holds no plan, no run and no evidence of its
own: it carries a name, a description and an owner, and its task count is
derived at read time rather than cached on the row.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .tenancy import Visibility

#: Portfolio display-name length bound, matching the project row's bound.
PORTFOLIO_NAME_MAX = 200


class PortfolioCreate(BaseModel):
    """Inbound body for `POST /api/v1/portfolios`.

    Args:
        name: Portfolio display name, 1-200 characters. Outer whitespace is
            stripped before the length constraint is applied.
        description: Optional free-text description.
        from_project_id: Seed the new portfolio from an existing project the
            caller **owns**: the portfolio inherits that project's
            `visibility` and organisation and takes it as its first member,
            in one transaction (contract § 6, i.1). Omit to create an empty
            portfolio. This amends ADR 0031 decision 4 ("assignment is a
            PATCH, not a field on create"); ADR 0032 records the amendment.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=PORTFOLIO_NAME_MAX)
    description: str | None = None
    from_project_id: uuid.UUID | None = None


class PortfolioUpdate(BaseModel):
    """Inbound body for `PATCH /api/v1/portfolios/{id}` (partial update).

    Args:
        name: New display name, when renaming. Omit to leave unchanged.
        description: New description, when changing it. Omit to leave
            unchanged.

    Note:
        **`visibility` is deliberately absent** and stays absent until the
        cascade lands (contract § 6, i.4: the cascade is the only writer of
        `portfolio.visibility`, because a portfolio's visibility change must
        carry every member with it). Adding the field here without the
        cascade would let an owner set a Project private, watch the UI agree,
        and leave its Tasks readable by the whole organisation. `PATCH
        /projects/{id}` accepts `visibility` today; `PATCH /portfolios/{id}`
        gains it together with the cascade that makes it honest.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=PORTFOLIO_NAME_MAX)
    description: str | None = None


class PortfolioOut(BaseModel):
    """A portfolio resource.

    Args:
        portfolio_id: The portfolio's identity.
        name: Current display name.
        description: Current description, or `None` if not set.
        created_at: When the portfolio was created.
        task_count: How many active projects **the caller may read, in the
            caller's own organisation** are assigned to this portfolio,
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

    portfolio_id: uuid.UUID
    name: str
    description: str | None = None
    created_at: datetime
    task_count: int
    visibility: Visibility
    is_owner: bool
    owner_display: str | None
