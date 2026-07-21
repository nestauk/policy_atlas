"""Shared response envelope, pagination and error shapes for `/api/v1`.

These are the building blocks every other contract module composes: the
error envelope every non-2xx response uses, and the generic paginated-list
envelope unbounded list resources return. Nothing here imports outside the
contract package.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

#: Default page size when the caller omits `page_size`.
PAGE_SIZE_DEFAULT = 50

#: Server-enforced page-size cap (`Query(le=PAGE_SIZE_MAX)` at the route).
PAGE_SIZE_MAX = 200


class ErrorBody(BaseModel):
    """The machine-readable body of a non-2xx error envelope.

    Args:
        code: Machine-readable error code. Contract — stable across releases.
        message: Human-readable error message. Not contract; text may change.
        details: Optional structured detail (e.g. a Pydantic validation error
            list, keyed by `loc`/`type`).
    """

    code: str
    message: str
    details: Any | None = None


class ErrorEnvelope(BaseModel):
    """The top-level shape of every non-2xx `/api/v1` response.

    Args:
        error: The error body.
    """

    error: ErrorBody


class PageMeta(BaseModel):
    """Pagination metadata attached to a paginated list response.

    Args:
        page: 1-indexed page number returned.
        page_size: Number of items requested per page (server-capped at
            `PAGE_SIZE_MAX`).
        total_items: Total number of items across all pages.
    """

    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=PAGE_SIZE_MAX)
    total_items: int = Field(ge=0)


class Page[T](BaseModel):
    """A generic paginated list response envelope.

    Args:
        data: The page's items, in server-defined order.
        pagination: Pagination metadata for this page.
    """

    data: list[T]
    pagination: PageMeta
