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

#: Portfolio display-name length bound, matching the project row's bound.
PORTFOLIO_NAME_MAX = 200


class PortfolioCreate(BaseModel):
    """Inbound body for `POST /api/v1/portfolios`.

    Args:
        name: Portfolio display name, 1-200 characters. Outer whitespace is
            stripped before the length constraint is applied.
        description: Optional free-text description.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=PORTFOLIO_NAME_MAX)
    description: str | None = None


class PortfolioUpdate(BaseModel):
    """Inbound body for `PATCH /api/v1/portfolios/{id}` (partial update).

    Args:
        name: New display name, when renaming. Omit to leave unchanged.
        description: New description, when changing it. Omit to leave
            unchanged.
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
        task_count: How many of the caller's active projects are assigned to
            this portfolio, derived per request and never cached on the row.
    """

    portfolio_id: uuid.UUID
    name: str
    description: str | None = None
    created_at: datetime
    task_count: int
