"""Tenancy contract: who the caller is, and how widely a row is shared.

Task 033 puts an organisation above the entity hierarchy. Two shapes are
shared across resources and so live here rather than on one of them:

- :data:`Visibility`, carried identically by `task` and `project`.
- :class:`MeOut`, the single place the caller learns their own identity,
  organisation and administrator state.

**The email appears here and in the admin-only `owner_email` listing filter,
and nowhere else** (contract § 3b). `MeOut.email` is the *caller's own*
address; no shape in this package carries another person's. What a row shows
about its owner is `owner_display`, which never falls back to an address.
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel

#: How widely a `task` or `project` row is shared. `org` means every
#: enrolled member of the row's organisation may read it; `private` means its
#: owner only. A row whose `org_id` is NULL is its owner's alone whatever this
#: says — "org" is an inert default where there is no organisation
#: (contract § 7).
Visibility = Literal["org", "private"]


class OrganisationRef(BaseModel):
    """The organisation the caller belongs to.

    Args:
        org_id: The organisation's identity.
        name: Its display name.
    """

    org_id: uuid.UUID
    name: str


class TaskQuotaOut(BaseModel):
    """How many tasks the caller created in the last 365 days, against the limit.

    The frontend shows a banner when ``used >= limit`` (task 064a, Q8).

    Args:
        used: Tasks the caller created in the last 365 days, archived included.
        limit: The yearly limit (``settings.task_quota_per_year``).
    """

    used: int
    limit: int


class MeOut(BaseModel):
    """The authenticated caller's own identity row.

    Returned by `GET /api/v1/me`, which also provisions the row on first call
    (contract § 2). The frontend keys the whole tenancy UI off this shape: a
    `null` organisation hides the scope switcher entirely, which is what makes
    the slice a dark launch for anyone not yet enrolled.

    Args:
        user_id: The caller's token subject — the identity the API keys on.
        display_name: How the caller is named on screen. Never an address:
            the ops-set name, or a rendering derived from `user_id` for a
            caller provisioned by their first `/me` call.
        email: The caller's own address once ops has resolved it, else
            `None`. Ops- and admin-facing; never another person's.
        organisation: The caller's organisation, or `None` when unenrolled.
        is_admin: Whether the caller holds the read-across-organisations
            support role. Read-only in every sense: no route and no request
            body can set it. The one write path that consults it is task
            creation, whose quota it exempts (ADR 0045).
        task_quota: The caller's task quota, or `None` when the caller is
            exempt (an administrator).
    """

    user_id: str
    display_name: str
    email: str | None = None
    organisation: OrganisationRef | None = None
    is_admin: bool
    task_quota: TaskQuotaOut | None = None
