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


def reject_explicit_nulls(model: BaseModel, *fields: str) -> None:
    """Refuse `{"field": null}` on partial-update fields that have no null meaning.

    A PATCH body's fields are `T | None` so that *absence* can mean "leave this
    alone". That makes `null` a second spelling of absence — and for a field
    backed by a NOT NULL column it is a spelling with no meaning at all. Left
    unchecked it does not behave as "unchanged" either: the route's
    `exclude_unset` dump *includes* the field, so the null reaches the UPDATE
    and the request 500s on the constraint. A caller's malformed body should
    not be an internal error.

    Contrast the fields deliberately **not** passed here. `project_id: null`
    is contract § 6's i.6 (unassign), and `question: null` / `description:
    null` clear nullable columns. Null is a real instruction on those, so this
    guard is per-field and never blanket.

    Args:
        model: The validated partial-update model, inside a `mode="after"`
            validator so `model_fields_set` distinguishes null from absent.
        fields: The field names for which null is not a valid instruction.

    Raises:
        ValueError: When any named field was supplied as null. FastAPI renders
            this as the contract's **422 `validation_error`**.
    """
    nulled = [
        field
        for field in fields
        if field in model.model_fields_set and getattr(model, field) is None
    ]
    if nulled:
        raise ValueError(
            f"{', '.join(nulled)} cannot be null; omit to leave unchanged"
        )


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
