"""Tenancy grades on the graded access helper (task 033, contract § 3).

Helper-level: every case calls ``accessible_project`` / ``accessible_portfolio``
directly against seeded rows. Route-level enforcement arrives in phase 4, when
the 19 call sites adopt the helper; nothing here goes through a router.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi import FastAPI, HTTPException
from sqlalchemy import event, select, update
from sqlalchemy.engine import Connection

from policy_atlas.api.routers._access import (
    FORBIDDEN_DETAIL,
    NOT_FOUND_DETAIL,
    _read_legs,
    accessible_portfolio,
    accessible_project,
    listing_scope,
    may_read_project,
)
from policy_atlas.core.schema import app_user, project
from tests.api.org_support import (
    make_org,
    make_portfolio,
    make_project,
    make_user,
    unregistered_user,
)
from tests.api.resource_support import api_client


def _statements(conn: Connection) -> list[str]:
    """Record every SQL statement the connection issues from now on."""
    recorded: list[str] = []

    def _record(
        _conn: Any, _cursor: Any, statement: str, *_rest: Any
    ) -> None:  # pragma: no cover - trivial
        recorded.append(statement)

    event.listen(conn, "before_cursor_execute", _record)
    return recorded


# --- The NULL rule (contract § 3) -----------------------------------------


def test_two_unenrolled_callers_cannot_see_each_others_null_org_rows(conn: Connection) -> None:
    """The highest-blast-radius mistake in the slice, pinned.

    Two callers with no organisation, two rows with no organisation. In Python
    ``None == None`` is ``True``, so a loaded-value comparison would hand each
    unenrolled user every other unenrolled user's work on day one. In SQL the
    org leg's equality is against a non-NULL ``org_id``, so it matches nothing.

    Both flavours of "no organisation" are covered: an ``app_user`` row whose
    ``org_id`` is NULL, and a subject with no ``app_user`` row at all.
    """
    enrolled_nowhere = make_user(conn, org_id=None)
    never_provisioned = unregistered_user()
    theirs = make_project(conn, owner_user_id=enrolled_nowhere, org_id=None)
    others = make_project(conn, owner_user_id=never_provisioned, org_id=None)

    assert accessible_project(conn, project_id=theirs, user_id=enrolled_nowhere).is_owner
    assert accessible_project(conn, project_id=others, user_id=never_provisioned).is_owner

    with pytest.raises(HTTPException) as first:
        accessible_project(conn, project_id=others, user_id=enrolled_nowhere)
    assert first.value.status_code == 404
    with pytest.raises(HTTPException) as second:
        accessible_project(conn, project_id=theirs, user_id=never_provisioned)
    assert second.value.status_code == 404


def test_unenrolled_caller_cannot_read_an_org_row(conn: Connection) -> None:
    """A NULL-``org_id`` caller matches no org leg, however shared the row is."""
    org_id = make_org(conn)
    owner = make_user(conn, org_id=org_id)
    outsider = make_user(conn, org_id=None)
    project_id = make_project(conn, owner_user_id=owner, org_id=org_id, visibility="org")

    with pytest.raises(HTTPException) as refused:
        accessible_project(conn, project_id=project_id, user_id=outsider)
    assert refused.value.status_code == 404


def test_org_read_leg_is_a_correlated_sql_predicate(conn: Connection) -> None:
    """Structural pin: the org leg is SQL, not a Python comparison.

    Compiling it is the only way to assert that ``app_user.org_id`` is
    equated to the row's ``org_id`` inside the database, which is what makes
    the NULL rule hold.
    """
    compiled = str(select(project).where(_read_legs(project, "caller")).compile(conn))
    assert "project.owner_user_id = %(owner_user_id_1)s" in compiled
    assert "project.org_id IS NOT NULL" in compiled
    assert "project.visibility = %(visibility_1)s" in compiled
    # The org membership test is an EXISTS correlated back to the row's own
    # `org_id`, so the equality is against a non-NULL value in SQL. `app_user`
    # is the subquery's only FROM — the outer `project` is correlated out, not
    # re-selected, which would have turned the leg into a cross join.
    assert "EXISTS (SELECT 1 \nFROM app_user \nWHERE" in compiled
    assert (
        "app_user.user_id = %(user_id_1)s::VARCHAR AND app_user.org_id = project.org_id"
        in compiled
    )


# --- The read grade --------------------------------------------------------


def test_same_org_colleague_reads_an_org_visible_project(conn: Connection) -> None:
    """Two enrolled colleagues, one shared row: the org leg grants the read."""
    org_id = make_org(conn)
    owner = make_user(conn, org_id=org_id)
    colleague = make_user(conn, org_id=org_id)
    project_id = make_project(conn, owner_user_id=owner, org_id=org_id, visibility="org")

    access = accessible_project(conn, project_id=project_id, user_id=colleague)
    assert access.row["project_id"] == project_id
    assert access.is_owner is False


def test_cross_org_caller_gets_an_indistinguishable_404(conn: Connection) -> None:
    """Enrolled in org A, row shared with org B: absent and forbidden read alike."""
    org_a = make_org(conn, name="A")
    org_b = make_org(conn, name="B")
    owner = make_user(conn, org_id=org_b)
    outsider = make_user(conn, org_id=org_a)
    project_id = make_project(conn, owner_user_id=owner, org_id=org_b, visibility="org")

    with pytest.raises(HTTPException) as refused:
        accessible_project(conn, project_id=project_id, user_id=outsider)
    with pytest.raises(HTTPException) as absent:
        accessible_project(conn, project_id=uuid.uuid4(), user_id=outsider)
    assert refused.value.status_code == absent.value.status_code == 404
    assert refused.value.detail == absent.value.detail == NOT_FOUND_DETAIL


def test_private_project_is_hidden_from_the_organisation(conn: Connection) -> None:
    """``visibility='private'`` withholds the row from an enrolled colleague."""
    org_id = make_org(conn)
    owner = make_user(conn, org_id=org_id)
    colleague = make_user(conn, org_id=org_id)
    project_id = make_project(conn, owner_user_id=owner, org_id=org_id, visibility="private")

    with pytest.raises(HTTPException) as refused:
        accessible_project(conn, project_id=project_id, user_id=colleague)
    assert refused.value.status_code == 404


def test_owner_reads_and_writes_regardless_of_org_and_visibility(conn: Connection) -> None:
    """The owner leg is unconditional on ``org_id`` and ``visibility``."""
    org_id = make_org(conn)
    owner = make_user(conn, org_id=org_id)
    shapes = (
        make_project(conn, owner_user_id=owner, org_id=org_id, visibility="org"),
        make_project(conn, owner_user_id=owner, org_id=org_id, visibility="private"),
        make_project(conn, owner_user_id=owner, org_id=None, visibility="org"),
        make_project(conn, owner_user_id=owner, org_id=None, visibility="private"),
    )
    for project_id in shapes:
        assert accessible_project(conn, project_id=project_id, user_id=owner).is_owner
        assert accessible_project(conn, project_id=project_id, user_id=owner, write=True).is_owner


def test_ownerless_rows_stay_unreachable(conn: Connection) -> None:
    """``orchestrate.py`` rows carry ``owner_user_id=NULL`` and belong to nobody.

    A NULL owner must not match a caller through the owner leg, and a NULL
    ``org_id`` must not match through the org leg — a row unreachable before
    this slice stays unreachable after it.
    """
    caller = make_user(conn, org_id=None)
    project_id = make_project(conn, owner_user_id=None, org_id=None)

    with pytest.raises(HTTPException) as refused:
        accessible_project(conn, project_id=project_id, user_id=caller)
    assert refused.value.status_code == 404


def test_the_two_read_checks_agree_on_a_project_that_has_no_owner_at_all(
    conn: Connection,
) -> None:
    """``accessible_project`` and ``may_read_project`` are one grade, or nothing works.

    An administrator reaches an ownerless, organisation-less row through the
    admin leg and nothing else (contract § 11). Both readers select
    ``own_estate`` as a boolean beside their answer — and on this row every
    disjunct of it compares a NULL column, so the predicate is **SQL NULL**.
    That reached `may_read_project`'s ``scalar_one_or_none()`` as "no row" and
    the administrator's stream closed as revoked on its first
    re-authorisation, while their ``GET`` on the same project succeeded.

    Asserted as an agreement between the two rather than as one value, because
    a divergence is the defect: the SSE tail exists to ask the same question
    the snapshot asked.
    """
    org_id = make_org(conn)
    admin = make_user(conn, org_id=org_id)
    conn.execute(
        update(app_user).where(app_user.c.user_id == admin).values(is_admin=True)
    )
    ownerless = make_project(conn, owner_user_id=None, org_id=None)

    direct = accessible_project(conn, project_id=ownerless, user_id=admin)
    assert direct.via_admin is True
    assert direct.is_owner is False

    recheck = may_read_project(conn, project_id=ownerless, user_id=admin)
    assert recheck.allowed is True
    assert recheck.via_admin is True


def test_a_caller_without_the_flag_still_cannot_read_an_ownerless_project(
    conn: Connection,
) -> None:
    """The COALESCE that fixed the check above widened nothing.

    NULL and ``FALSE`` mean the same thing for the own-leg column — "no leg
    the caller held without ``is_admin``" — so folding one into the other
    cannot admit a caller. The re-check refuses this one on the same terms the
    direct read does.
    """
    caller = make_user(conn, org_id=make_org(conn))
    ownerless = make_project(conn, owner_user_id=None, org_id=None)

    assert may_read_project(conn, project_id=ownerless, user_id=caller) == (False, False)
    with pytest.raises(HTTPException) as refused:
        accessible_project(conn, project_id=ownerless, user_id=caller)
    assert refused.value.status_code == 404


def test_a_listings_predicate_and_its_audit_decision_come_from_one_flag_read(
    conn: Connection,
) -> None:
    """One read of ``is_admin`` per listing, or the page and its line can disagree.

    The natural spelling asks twice: ``_read_legs`` for the predicate (whose
    admin leg is an ``EXISTS`` over ``app_user``) and ``_is_admin`` for the
    trace decision — and the route then runs its count and page queries, each
    re-evaluating the leg again. A grant or revoke committing in any of those
    gaps serves rows across organisations with **no** ``admin_listing`` line,
    or logs one for a page the leg never widened.

    Both halves are asserted structurally, because the race is a race: the
    resolver issues exactly one statement, and the predicate it hands back
    carries no second reading of the flag. An administrator's is ``true`` —
    which is what the admin leg already meant, being unconditional on the row —
    and everybody else's is the org estate with no flag in it at all.
    """
    org_id = make_org(conn)
    admin = make_user(conn, org_id=org_id)
    conn.execute(
        update(app_user).where(app_user.c.user_id == admin).values(is_admin=True)
    )
    colleague = make_user(conn, org_id=org_id)

    recorded = _statements(conn)
    admin_scope = listing_scope(conn, project, user_id=admin, scope="all")
    assert admin_scope.via_admin is True
    assert len(recorded) == 1, recorded
    assert "is_admin" in recorded[0]
    assert str(admin_scope.predicate.compile(conn)) == "true"

    recorded.clear()
    plain_scope = listing_scope(conn, project, user_id=colleague, scope="all")
    assert plain_scope.via_admin is False
    assert len(recorded) == 1, recorded
    assert "is_admin" not in str(plain_scope.predicate.compile(conn))

    # `scope=mine` still costs no query at all: the owner column cannot be
    # widened by the flag, so there is nothing to ask.
    recorded.clear()
    mine = listing_scope(conn, project, user_id=admin, scope="mine")
    assert mine.via_admin is False
    assert recorded == []


# --- The write grade -------------------------------------------------------


def test_same_org_colleague_is_refused_the_write_grade(conn: Connection) -> None:
    """The read leg passes and the mutation is still refused: 403 ``forbidden``.

    404 would be wrong here — the colleague can already see the row, so hiding
    it at the mutation would be theatre.
    """
    org_id = make_org(conn)
    owner = make_user(conn, org_id=org_id)
    colleague = make_user(conn, org_id=org_id)
    project_id = make_project(conn, owner_user_id=owner, org_id=org_id, visibility="org")

    assert accessible_project(conn, project_id=project_id, user_id=colleague).is_owner is False
    with pytest.raises(HTTPException) as refused:
        accessible_project(conn, project_id=project_id, user_id=colleague, write=True)
    assert refused.value.status_code == 403
    assert refused.value.detail == FORBIDDEN_DETAIL


def test_unreadable_row_stays_404_under_the_write_grade(conn: Connection) -> None:
    """403 is only ever reachable from a row the caller can already read."""
    org_a = make_org(conn, name="A")
    org_b = make_org(conn, name="B")
    owner = make_user(conn, org_id=org_b)
    outsider = make_user(conn, org_id=org_a)
    project_id = make_project(conn, owner_user_id=owner, org_id=org_b, visibility="org")

    with pytest.raises(HTTPException) as refused:
        accessible_project(conn, project_id=project_id, user_id=outsider, write=True)
    assert refused.value.status_code == 404


# --- Archived rows: unchanged from ``owned_project`` -----------------------


def test_archived_project_needs_include_archived_for_owner_and_colleague(
    conn: Connection,
) -> None:
    """The status leg is orthogonal to tenancy and behaves exactly as today."""
    org_id = make_org(conn)
    owner = make_user(conn, org_id=org_id)
    colleague = make_user(conn, org_id=org_id)
    project_id = make_project(
        conn, owner_user_id=owner, org_id=org_id, visibility="org", status="archived"
    )

    for caller in (owner, colleague):
        with pytest.raises(HTTPException) as hidden:
            accessible_project(conn, project_id=project_id, user_id=caller)
        assert hidden.value.status_code == 404
        access = accessible_project(
            conn, project_id=project_id, user_id=caller, include_archived=True
        )
        assert access.row["project_id"] == project_id
    assert accessible_project(
        conn, project_id=project_id, user_id=owner, include_archived=True, write=True
    ).is_owner


# --- Locking (contract § 4) ------------------------------------------------


def test_for_update_without_the_write_grade_is_a_programming_error(conn: Connection) -> None:
    """A read-grade caller must never lock the owner's row, so the call refuses.

    Contract § 4: a colleague holding their own chat blocking the owner's
    rename, archive and run-start is the defect this guard makes unreachable.
    Phase 4 fixes ``for_update`` per call site from an explicit table.
    """
    owner = make_user(conn, org_id=None)
    project_id = make_project(conn, owner_user_id=owner, org_id=None)

    with pytest.raises(ValueError, match="write-path lock"):
        accessible_project(conn, project_id=project_id, user_id=owner, for_update=True)
    with pytest.raises(ValueError, match="write-path lock"):
        accessible_portfolio(
            conn,
            portfolio_id=make_portfolio(conn, owner_user_id=owner),
            user_id=owner,
            for_update=True,
        )


def test_locking_can_only_ever_land_on_the_callers_own_row(conn: Connection) -> None:
    """Every ``FOR UPDATE`` the helper issues is bounded by the owner leg.

    That bound is what keeps a colleague from blocking the owner's rename,
    archive or run-start: their locking select matches no row, so it takes no
    lock, and the unlocked read behind it decides the 403. The owner's own
    path still costs a single round trip.
    """
    org_id = make_org(conn)
    owner = make_user(conn, org_id=org_id)
    colleague = make_user(conn, org_id=org_id)
    project_id = make_project(conn, owner_user_id=owner, org_id=org_id, visibility="org")

    issued = _statements(conn)
    assert accessible_project(
        conn, project_id=project_id, user_id=owner, write=True, for_update=True
    ).is_owner
    assert len(issued) == 1
    assert "FOR UPDATE" in issued[0]

    with pytest.raises(HTTPException) as refused:
        accessible_project(
            conn, project_id=project_id, user_id=colleague, write=True, for_update=True
        )
    assert refused.value.status_code == 403

    locking = [statement for statement in issued if "FOR UPDATE" in statement]
    assert len(locking) == 2
    for statement in locking:
        assert "project.owner_user_id = %(owner_user_id_1)s" in statement
        assert "EXISTS" not in statement


# --- Portfolio mirror ------------------------------------------------------


def test_portfolio_mirrors_the_project_grades(conn: Connection) -> None:
    """Owner call (e): ``portfolio`` takes the same tenancy grades as ``project``."""
    org_a = make_org(conn, name="A")
    org_b = make_org(conn, name="B")
    owner = make_user(conn, org_id=org_a)
    colleague = make_user(conn, org_id=org_a)
    outsider = make_user(conn, org_id=org_b)
    unenrolled = make_user(conn, org_id=None)

    shared = make_portfolio(conn, owner_user_id=owner, org_id=org_a, visibility="org")
    private = make_portfolio(conn, owner_user_id=owner, org_id=org_a, visibility="private")
    unstamped = make_portfolio(conn, owner_user_id=unenrolled, org_id=None)

    assert accessible_portfolio(conn, portfolio_id=shared, user_id=owner).is_owner
    assert accessible_portfolio(conn, portfolio_id=shared, user_id=colleague).is_owner is False
    with pytest.raises(HTTPException) as write_refused:
        accessible_portfolio(conn, portfolio_id=shared, user_id=colleague, write=True)
    assert write_refused.value.status_code == 403

    for hidden_id, caller in (
        (private, colleague),
        (shared, outsider),
        (shared, unenrolled),
        (unstamped, colleague),
    ):
        with pytest.raises(HTTPException) as refused:
            accessible_portfolio(conn, portfolio_id=hidden_id, user_id=caller)
        assert refused.value.status_code == 404
        assert refused.value.detail == NOT_FOUND_DETAIL


def test_two_unenrolled_callers_cannot_see_each_others_null_org_portfolios(
    conn: Connection,
) -> None:
    """The NULL rule again, on the portfolio leg."""
    first = make_user(conn, org_id=None)
    second = unregistered_user()
    theirs = make_portfolio(conn, owner_user_id=first, org_id=None)

    assert accessible_portfolio(conn, portfolio_id=theirs, user_id=first).is_owner
    with pytest.raises(HTTPException) as refused:
        accessible_portfolio(conn, portfolio_id=theirs, user_id=second)
    assert refused.value.status_code == 404


# --- Error envelope --------------------------------------------------------


def test_forbidden_renders_the_forbidden_error_code(tmp_path: Path) -> None:
    """403 leaves the app as ``forbidden``, not the catch-all ``internal``.

    ``web-api.md`` § Auth boundary pre-reserved the status; contract § 8 spends
    it. Probed through a route mounted on the real application so the assertion
    covers the installed handler rather than a reconstruction of it.
    """
    with api_client(tmp_path) as (client, owner, _):
        app = cast(FastAPI, client.app)

        @app.get("/api/v1/_forbidden_probe")
        def _probe() -> None:
            raise HTTPException(status_code=403, detail=FORBIDDEN_DETAIL)

        response = client.get("/api/v1/_forbidden_probe", headers=owner)
        assert response.status_code == 403
        assert response.json() == {
            "error": {"code": "forbidden", "message": FORBIDDEN_DETAIL}
        }
