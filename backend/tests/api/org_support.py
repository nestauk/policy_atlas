"""Tenancy seeding helpers for API tests (task 033).

Plain functions over the session ``conn`` fixture, in the style of
``resource_support`` — not pytest fixtures, so a test seeds exactly the shape
it needs.

Two shared-database hazards these exist to close:

- ``organisation.name`` is ``NOT NULL UNIQUE`` and the test database is shared
  across the whole suite, so a fixed-name organisation fixture passes once and
  fails on the second test that uses it. :func:`make_org` suffixes every name
  with a UUID, the same reason ``resource_support.api_client`` mints unique
  subs.
- ``app_user.user_id`` is the token subject and is a primary key.
  :func:`make_user` mints unique subjects for the same reason.

Cleanup is the ``conn`` fixture's transaction rollback (``tests/conftest.py``);
nothing here commits.
"""

from __future__ import annotations

import uuid

from sqlalchemy.engine import Connection

from policy_atlas.core.schema import app_user, organisation, portfolio, project
from tests.helpers import now


def make_org(conn: Connection, *, name: str = "Org") -> uuid.UUID:
    """Insert one organisation with a suite-unique name and return its id."""
    org_id = uuid.uuid4()
    conn.execute(
        organisation.insert().values(
            org_id=org_id,
            name=f"{name} {uuid.uuid4()}",
            created_at=now(),
        )
    )
    return org_id


def make_user(
    conn: Connection,
    *,
    org_id: uuid.UUID | None = None,
    display_name: str = "Test User",
) -> str:
    """Insert one ``app_user`` row and return its subject.

    Args:
        conn: Open database connection.
        org_id: The organisation the person is enrolled in, or ``None`` for an
            unenrolled user — the NULL-``org_id`` case the tenancy rule turns on.
        display_name: Required by the schema; never the email (contract § 3b).

    Returns:
        The generated token subject.
    """
    user_id = f"user-{uuid.uuid4()}"
    conn.execute(
        app_user.insert().values(
            user_id=user_id,
            org_id=org_id,
            display_name=display_name,
            email=None,
            created_at=now(),
        )
    )
    return user_id


def unregistered_user() -> str:
    """Mint a subject with **no** ``app_user`` row at all.

    A signed-in caller who has never hit ``/me`` is a real state, and it is a
    different one from an enrolled-with-NULL-``org_id`` caller. The org leg
    must refuse both.
    """
    return f"user-{uuid.uuid4()}"


def make_project(
    conn: Connection,
    *,
    owner_user_id: str | None,
    org_id: uuid.UUID | None = None,
    visibility: str = "org",
    status: str = "active",
    portfolio_id: uuid.UUID | None = None,
    name: str = "Task",
) -> uuid.UUID:
    """Insert one project row and return its id."""
    project_id = uuid.uuid4()
    moment = now()
    conn.execute(
        project.insert().values(
            project_id=project_id,
            created_at=moment,
            updated_at=moment,
            archived_at=moment if status == "archived" else None,
            name=name,
            question=None,
            status=status,
            owner_user_id=owner_user_id,
            portfolio_id=portfolio_id,
            org_id=org_id,
            visibility=visibility,
        )
    )
    return project_id


def make_portfolio(
    conn: Connection,
    *,
    owner_user_id: str | None,
    org_id: uuid.UUID | None = None,
    visibility: str = "org",
    name: str = "Project",
) -> uuid.UUID:
    """Insert one portfolio row and return its id."""
    portfolio_id = uuid.uuid4()
    conn.execute(
        portfolio.insert().values(
            portfolio_id=portfolio_id,
            owner_user_id=owner_user_id,
            name=name,
            description=None,
            created_at=now(),
            org_id=org_id,
            visibility=visibility,
        )
    )
    return portfolio_id
