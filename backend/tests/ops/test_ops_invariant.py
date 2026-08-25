"""Phase 7's invariant, re-run across the three enrolment moves (rubric 29).

Contract § 6's invariant — **a project with a portfolio carries that portfolio's
``visibility`` *and* its ``org_id``** — was pinned in
``tests/api/test_visibility_invariant.py`` against the API's write paths. The
operator CLI is a *second* writer of both columns, and it writes them without
going through any of those paths: `_stamp_owned_rows` is two UPDATE statements
over an owner's whole estate.

That is deliberate (contract § 7: "the move is a set operation, not a row-by-row
walk through the cascade path — which would transiently violate it"), and it is
exactly why the property has to be re-run here rather than assumed to carry
over. The argument the set operation rests on is that **a portfolio's members are
always owned by the portfolio's owner** (032, ``projects.py``), so one person's
rows form a closed set. If that ever stops holding, this file fails and the API
suite does not.

``_breaches`` is imported from the phase-7 module rather than reimplemented, on
purpose: a second reading of "what counts as a breach" — particularly of how the
nullable ``org_id`` compares — is precisely the drift that would let both suites
pass while the rule was broken.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.engine import Engine

from policy_atlas.core.schema import organisation, portfolio, project
from policy_atlas.ops import commands
from tests.api.org_support import make_org, make_portfolio, make_project, seeded, unique_email
from tests.api.test_visibility_invariant import _breaches
from tests.ops.support import POOL_ID, cognito, expect_lookup, fresh_sub


def _org(engine: Engine, label: str) -> commands.Organisation:
    name = f"{label} {uuid.uuid4()}"
    with seeded(engine) as conn:
        org_id = make_org(conn, name=name)
        stored = conn.execute(
            select(organisation.c.name).where(organisation.c.org_id == org_id)
        ).scalar_one()
    return commands.Organisation(org_id=org_id, name=stored)


def _estate(engine: Engine, owner: str) -> tuple[uuid.UUID, list[uuid.UUID], uuid.UUID]:
    """One owner with a portfolio, two members (one archived), and a loose project."""
    with seeded(engine) as conn:
        portfolio_id = make_portfolio(conn, owner_user_id=owner, visibility="org")
        members = [
            make_project(conn, owner_user_id=owner, portfolio_id=portfolio_id),
            make_project(
                conn, owner_user_id=owner, portfolio_id=portfolio_id, status="archived"
            ),
        ]
        loose = make_project(conn, owner_user_id=owner)
    return portfolio_id, members, loose


def _fields(engine: Engine, owner: str) -> dict[str, set[tuple[object, str]]]:
    with seeded(engine) as conn:
        projects = {
            (row.org_id, row.visibility)
            for row in conn.execute(
                select(project.c.org_id, project.c.visibility).where(
                    project.c.owner_user_id == owner
                )
            )
        }
        portfolios = {
            (row.org_id, row.visibility)
            for row in conn.execute(
                select(portfolio.c.org_id, portfolio.c.visibility).where(
                    portfolio.c.owner_user_id == owner
                )
            )
        }
    return {"projects": projects, "portfolios": portfolios}


def test_the_invariant_holds_across_enrol_re_enrol_and_de_enrol(engine: Engine) -> None:
    """Rubric 29's last clause, over all three moves, on a deliberately shared row.

    The sequence is the one the contract describes and the one an operator will
    actually run: enrol into A, the person shares a Project with A, re-enrol into
    B, then de-enrol. The invariant is asserted after each move, and so is the
    thing the invariant does not by itself say — that nothing arrives *shared*.
    """
    first = _org(engine, "Alpha")
    second = _org(engine, "Beta")
    owner = fresh_sub("cognito")
    email = unique_email("traveller")
    portfolio_id, members, loose = _estate(engine, owner)

    with cognito() as (client, stubber):
        # --- move 1: enrolment ------------------------------------------------
        expect_lookup(stubber, email=email, sub=owner)
        with seeded(engine) as conn:
            enrolment = commands.enrol_user(
                conn, client, pool_id=POOL_ID, email=email, display_name="T", org=first
            )
        assert (enrolment.projects_moved, enrolment.portfolios_moved) == (3, 1)
        assert _breaches(engine, owner) == []
        assert _fields(engine, owner) == {
            "projects": {(first.org_id, "private")},
            "portfolios": {(first.org_id, "private")},
        }

        # The person deliberately opts the whole Project back into organisation A.
        with seeded(engine) as conn:
            conn.execute(
                update(portfolio)
                .where(portfolio.c.portfolio_id == portfolio_id)
                .values(visibility="org")
            )
            conn.execute(
                update(project)
                .where(project.c.portfolio_id == portfolio_id)
                .values(visibility="org")
            )
        assert _breaches(engine, owner) == []

        # --- move 2: re-enrolment into a second organisation -------------------
        expect_lookup(stubber, email=email, sub=owner)
        with seeded(engine) as conn:
            again = commands.enrol_user(
                conn, client, pool_id=POOL_ID, email=email, display_name="T", org=second
            )
        assert (again.projects_moved, again.portfolios_moved) == (3, 1)
        assert _breaches(engine, owner) == []
        # Re-privatised: what was shared with A does not arrive shared in B.
        assert _fields(engine, owner) == {
            "projects": {(second.org_id, "private")},
            "portfolios": {(second.org_id, "private")},
        }

    # --- move 3: de-enrolment -------------------------------------------------
    with seeded(engine) as conn:
        departure = commands.de_enrol_user(conn, email=email)
    assert (departure.projects_cleared, departure.portfolios_cleared) == (3, 1)
    assert _breaches(engine, owner) == []
    # Organisation cleared on every row; visibility deliberately untouched.
    assert _fields(engine, owner) == {
        "projects": {(None, "private")},
        "portfolios": {(None, "private")},
    }
    # Nothing was lost or created along the way: the same estate, three moves on.
    assert _project_ids(engine, owner) == set(members) | {loose}


def _project_ids(engine: Engine, owner: str) -> set[uuid.UUID]:
    with seeded(engine) as conn:
        return set(
            conn.execute(
                select(project.c.project_id).where(project.c.owner_user_id == owner)
            ).scalars()
        )
