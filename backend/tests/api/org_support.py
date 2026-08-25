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

import os
import uuid
from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import NamedTuple

from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.engine import Connection, Engine

from policy_atlas.api.app import create_app
from policy_atlas.api.dev_issuer import init, mint_token
from policy_atlas.api.settings import Settings
from policy_atlas.core.schema import (
    app_user,
    conversation,
    organisation,
    portfolio,
    project,
)
from tests.helpers import now


class Principal(NamedTuple):
    """One signed-in caller: their token subject and their bearer header.

    Route-level tenancy tests need the *subject* as well as the header,
    because the fixtures they seed (`app_user` rows, owned projects) are keyed
    on it. ``resource_support.api_client`` keeps its subjects private and
    hands back two opaque header dicts, which is right for owner-scoped tests
    and not enough here.
    """

    user_id: str
    headers: dict[str, str]


@contextmanager
def tenancy_client(
    tmp_path: Path,
    *,
    count: int = 3,
    overrides: dict[Callable[..., object], Callable[..., object]] | None = None,
) -> Iterator[tuple[TestClient, list[Principal]]]:
    """Yield an application client plus ``count`` distinct signed-in callers.

    Three is the usual shape: an owner, a same-org colleague, and a third
    party who is in no organisation with either.

    Args:
        tmp_path: Per-test temporary directory for the development issuer key.
        count: How many distinct subjects to mint.
        overrides: FastAPI dependency overrides, the way
            ``resource_support.api_client`` takes them. Task 033's phase-5
            chat cases need them — a colleague's turn POST has to run the
            real route end to end, which means substituting the provider
            backends, while still driving *named* subjects this file can
            enrol.

    Yields:
        The client and the minted principals, in order.
    """
    key_dir = tmp_path / "issuer"
    settings = Settings(
        "http://dev-issuer.local",
        "tenancy-router-test",
        None,
        init(key_dir),
        "http://app.example.test",
        os.environ["DATABASE_URL"],
    )
    # Unique subs per client for the same reason `resource_support` mints
    # them: the test database is shared across the suite and listings would
    # otherwise see other tests' rows.
    principals = []
    for index in range(count):
        user_id = f"tenancy-{index}-{uuid.uuid4()}"
        token = mint_token(
            user_id, settings.oidc_issuer, settings.oidc_client_id, 60, key_dir
        )
        principals.append(Principal(user_id, {"Authorization": f"Bearer {token}"}))
    app = create_app(settings=settings)
    if overrides:
        app.dependency_overrides.update(overrides)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, principals


@contextmanager
def seeded(engine: Engine) -> Generator[Connection, None, None]:
    """Yield a connection whose writes **commit** on exit.

    The session ``conn`` fixture rolls back, which is right for helper-level
    tests but invisible to a route: the application opens its own connection
    from its own engine. Route-level tenancy tests therefore seed through
    this instead. Nothing needs cleaning up afterwards — every organisation
    name and every subject minted here is UUID-suffixed, so rows left behind
    are unreachable from any other test.

    Args:
        engine: The session-scoped engine (which also applies the migration).

    Yields:
        A connection inside a transaction that commits.
    """
    with engine.begin() as connection:
        yield connection


def ops_enrol(
    conn: Connection,
    *,
    user_id: str,
    org_id: uuid.UUID | None = None,
    display_name: str = "Ops Name",
    email: str | None = None,
    is_admin: bool = False,
) -> None:
    """Write an ``app_user`` row the way ops enrolment will, for an existing subject.

    Distinct from :func:`make_user`, which mints its own subject: this enrols
    a subject that already exists because a :func:`tenancy_client` principal
    is signed in as it.

    Args:
        conn: Open database connection.
        user_id: The subject to enrol.
        org_id: The organisation, or ``None`` for an unenrolled row.
        display_name: Required by the schema; never the email.
        email: The ops-resolved address — ops- and admin-facing only.
        is_admin: Whether this person holds the support role.
    """
    conn.execute(
        app_user.insert().values(
            user_id=user_id,
            org_id=org_id,
            display_name=display_name,
            email=email,
            is_admin=is_admin,
            created_at=now(),
        )
    )


def ops_set_admin(conn: Connection, *, user_id: str, is_admin: bool) -> None:
    """Grant or revoke the support role on an already-enrolled subject.

    The phase-9b CLI's `admin grant` / `admin revoke` reduced to the row write
    they perform. Phase 8 needs the **revoke** as a lever an open SSE stream
    can react to (contract § 5's fourth revocation event), and needs it
    without waiting for the CLI, exactly as the de-enrolment cases in
    `test_sse.py` write `app_user.org_id` directly.

    Args:
        conn: Open database connection.
        user_id: The subject to grant or revoke.
        is_admin: The new state.
    """
    conn.execute(
        update(app_user).where(app_user.c.user_id == user_id).values(is_admin=is_admin)
    )


def make_conversation(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    kind: str = "chat",
    created_by: str | None = None,
    status: str = "active",
    title: str = "Conversation",
) -> uuid.UUID:
    """Insert one durable conversation row and return its id.

    `created_by` is explicit and defaults to `None` — the legacy pre-033
    shape — because every tenancy question on this table turns on it.

    Args:
        conn: Open database connection.
        project_id: The project the conversation belongs to.
        kind: `chat` or `planning`.
        created_by: The authoring subject, or `None` for a legacy row.
        status: `active`, `closed` or `archived`.
        title: The conversation's title.

    Returns:
        The generated conversation id.
    """
    conversation_id = uuid.uuid4()
    moment = now()
    conn.execute(
        conversation.insert().values(
            id=conversation_id,
            project_id=project_id,
            kind=kind,
            title=title,
            entry_artefact_id=None,
            status=status,
            created_at=moment,
            closed_at=None,
            archived_at=moment if status == "archived" else None,
            created_by=created_by,
        )
    )
    return conversation_id


def unique_email(local: str) -> str:
    """Mint a suite-unique address.

    ``app_user.email`` carries no unique constraint and the test database is
    shared across the suite *and* across runs, so a fixed address accumulates
    owners: the `owner_email` filter would then legitimately return rows a
    previous run created, and the assertion — not the code — would be wrong.
    Same reason :func:`make_org` suffixes organisation names.

    Args:
        local: A readable local part, e.g. ``"colleague"``.

    Returns:
        An address unique to this test.
    """
    return f"{local}-{uuid.uuid4()}@example.test"


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
