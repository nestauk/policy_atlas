"""The operator commands, one acceptance row at a time (contract § 9, rubric 26-30).

Every test here calls the **real command function** against the real test
database with a stubbed identity provider. Nothing re-implements what the CLI is
believed to write — that mistake is the reason phase 6's simulated cascade case
was kept *and* replaced by one driving the actual route.

Most cases use the rolled-back ``conn`` fixture. The three that must observe
commits — the two-operator race and the ``FOR UPDATE`` proof — use ``engine``
and seed through ``org_support.seeded``.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError
from structlog.testing import capture_logs

from policy_atlas.core.schema import app_user, organisation, portfolio, project
from policy_atlas.ops import commands
from policy_atlas.ops.errors import OpsError
from tests.api.org_support import (
    make_org,
    make_portfolio,
    make_project,
    ops_enrol,
    seeded,
    unique_email,
)
from tests.ops.support import (
    POOL_ID,
    cognito,
    expect_create,
    expect_create_manual,
    expect_lookup,
    fresh_sub,
)


def _org(conn: Connection, name: str = "Org") -> commands.Organisation:
    org_id = make_org(conn, name=name)
    resolved = conn.execute(
        select(organisation.c.name).where(organisation.c.org_id == org_id)
    ).scalar_one()
    return commands.Organisation(org_id=org_id, name=resolved)


def _project_row(conn: Connection, project_id: uuid.UUID) -> Any:
    return conn.execute(
        select(project.c.org_id, project.c.visibility, project.c.updated_at).where(
            project.c.project_id == project_id
        )
    ).one()


def _portfolio_row(conn: Connection, portfolio_id: uuid.UUID) -> Any:
    return conn.execute(
        select(portfolio.c.org_id, portfolio.c.visibility).where(
            portfolio.c.portfolio_id == portfolio_id
        )
    ).one()


def _user_row(conn: Connection, sub: str) -> Any:
    return conn.execute(
        select(app_user.c.org_id, app_user.c.email, app_user.c.is_admin, app_user.c.display_name)
        .where(app_user.c.user_id == sub)
    ).one_or_none()


# --- organisations -----------------------------------------------------------


def test_org_create_inserts_the_organisation(conn: Connection) -> None:
    name = f"Nesta {uuid.uuid4()}"
    created = commands.create_organisation(conn, name=name)
    stored = conn.execute(
        select(organisation.c.name).where(
            organisation.c.org_id == created.org_id
        )
    ).scalar_one()
    assert stored == name
    assert name in created.summary()


def test_org_create_refuses_a_duplicate_name(conn: Connection) -> None:
    name = f"Nesta {uuid.uuid4()}"
    commands.create_organisation(conn, name=name)
    with pytest.raises(OpsError, match="already exists"):
        commands.create_organisation(conn, name=name)


def test_resolve_organisation_accepts_a_name_or_an_id(conn: Connection) -> None:
    org = _org(conn)
    assert commands.resolve_organisation(conn, org.name).org_id == org.org_id
    assert commands.resolve_organisation(conn, str(org.org_id)).name == org.name
    with pytest.raises(OpsError, match="no organisation named"):
        commands.resolve_organisation(conn, "Nowhere Ltd")


# --- user create -------------------------------------------------------------


def test_user_create_sends_the_email_delivery_medium_explicitly(conn: Connection) -> None:
    """Rubric 28. AWS defaults this to SMS; the pool holds no phone numbers.

    The assertion is the Stubber's expected-parameter dict
    (``support.expect_create``): botocore raises if the outgoing call differs in
    any key, so this fails if the medium is dropped, if ``MessageAction:
    SUPPRESS`` reappears, or if any password parameter is added.
    """
    org = _org(conn)
    email = unique_email("new")
    sub = fresh_sub()
    with cognito() as (client, stubber):
        expect_lookup(stubber, email=email, sub=None)
        expect_create(stubber, email=email, sub=sub)
        enrolment = commands.create_user(
            conn,
            client,
            pool_id=POOL_ID,
            email=email,
            display_name="New Person",
            org=org,
        )
        stubber.assert_no_pending_responses()
    assert enrolment.user_id == sub
    row = _user_row(conn, sub)
    assert row is not None
    assert (row.org_id, row.email, row.display_name) == (org.org_id, email, "New Person")


def test_user_create_manual_invite_mints_and_prints_a_single_use_password(
    conn: Connection,
) -> None:
    """Owner amendment 2026-08-26: `--invite manual` for spam-swallowed inboxes.

    The Stubber pins the wire shape (``MessageAction: SUPPRESS``, a minted
    ``TemporaryPassword``, and NO ``DesiredDeliveryMediums``). The minted value
    is generated, never accepted — rubric 30 stands — and appears exactly once,
    in the operator-facing summary, with every Cognito-default character class
    so the pool's password policy cannot refuse it.
    """
    org = _org(conn)
    email = unique_email("manual")
    sub = fresh_sub()
    with cognito() as (client, stubber):
        expect_lookup(stubber, email=email, sub=None)
        expect_create_manual(stubber, email=email, sub=sub)
        with capture_logs() as logged:
            enrolment = commands.create_user(
                conn,
                client,
                pool_id=POOL_ID,
                email=email,
                display_name="Manual Person",
                org=org,
                invite="manual",
            )
        stubber.assert_no_pending_responses()

    minted = enrolment.temporary_password
    assert minted is not None
    assert len(minted) == 20
    assert any(c.islower() for c in minted)
    assert any(c.isupper() for c in minted)
    assert any(c.isdigit() for c in minted)
    assert any(not c.isalnum() for c in minted)
    assert minted in enrolment.summary()
    assert "single-use" in enrolment.summary()
    # The credential reaches stdout once, and structlog never sees it.
    assert not any(minted in str(event) for event in logged)
    assert _user_row(conn, sub) is not None


def test_user_create_email_invite_carries_no_temporary_password(
    conn: Connection,
) -> None:
    """The default mode is byte-identical to before the amendment."""
    org = _org(conn)
    email = unique_email("emailed")
    with cognito() as (client, stubber):
        expect_lookup(stubber, email=email, sub=None)
        expect_create(stubber, email=email, sub=fresh_sub())
        enrolment = commands.create_user(
            conn, client, pool_id=POOL_ID, email=email, display_name="E", org=org
        )
        stubber.assert_no_pending_responses()
    assert enrolment.temporary_password is None
    assert "temporary password" not in enrolment.summary()


def test_a_kept_account_failure_still_surfaces_the_minted_password(
    conn: Connection,
) -> None:
    """Losing the minted value would strand the account.

    In manual mode no email was ever sent and `user create` refuses existing
    addresses, so if the database write fails after Cognito succeeded, the
    refusal is the only place the credential can survive.
    """
    ghost = commands.Organisation(org_id=uuid.uuid4(), name="Ghost Org")
    email = unique_email("manual-orphan")
    sub = fresh_sub()
    with cognito() as (client, stubber):
        expect_lookup(stubber, email=email, sub=None)
        expect_create_manual(stubber, email=email, sub=sub)
        with conn.begin_nested() as savepoint:
            with pytest.raises(OpsError) as refusal:
                commands.create_user(
                    conn,
                    client,
                    pool_id=POOL_ID,
                    email=email,
                    display_name="X",
                    org=ghost,
                    invite="manual",
                )
            savepoint.rollback()
        stubber.assert_no_pending_responses()
    message = str(refusal.value)
    assert "KEPT" in message
    assert "temporary password is:" in message


def test_user_create_refuses_an_existing_address_and_says_use_enrol(conn: Connection) -> None:
    """Rubric 28's third clause."""
    org = _org(conn)
    email = unique_email("already")
    with cognito() as (client, stubber):
        expect_lookup(stubber, email=email, sub=fresh_sub())
        with pytest.raises(OpsError, match="use `user enrol"):
            commands.create_user(
                conn, client, pool_id=POOL_ID, email=email, display_name="X", org=org
            )
        stubber.assert_no_pending_responses()


def test_user_create_keeps_the_account_and_prints_the_remediation_on_a_database_failure(
    conn: Connection,
) -> None:
    """Rubric 28's second clause, and rubric 30's ``AdminDeleteUser`` clause.

    The database failure is a real one — an organisation id with no row behind
    it, so the ``app_user`` foreign key rejects the insert — rather than a
    patched-in exception, because the property under test is what the command
    does when Postgres says no.

    Two things are asserted: the message names the ``user enrol`` remediation
    and says the account was kept, and **the stub queue is empty** — a call to
    ``AdminDeleteUser`` would have raised ``UnStubbedResponseError`` instead.
    """
    ghost = commands.Organisation(org_id=uuid.uuid4(), name="Ghost Org")
    email = unique_email("orphan")
    sub = fresh_sub()
    with cognito() as (client, stubber):
        expect_lookup(stubber, email=email, sub=None)
        expect_create(stubber, email=email, sub=sub)
        with conn.begin_nested() as savepoint:
            with pytest.raises(OpsError) as refusal:
                commands.create_user(
                    conn, client, pool_id=POOL_ID, email=email, display_name="X", org=ghost
                )
            savepoint.rollback()
        stubber.assert_no_pending_responses()
    message = str(refusal.value)
    assert "KEPT" in message
    assert "user enrol" in message
    assert _user_row(conn, sub) is None


def test_user_create_turns_a_cognito_refusal_into_a_refusal_not_a_traceback(
    conn: Connection,
) -> None:
    """``AdminCreateUser`` can fail for reasons the pre-flight lookup cannot see.

    The lookup is Cognito's own exact-match filter, so it can lose a race, and
    it cannot see an account whose *alias* rather than whose ``email``
    attribute carries the address. Either way the answer is
    ``UsernameExistsException``, and an operator mid-provisioning is owed the
    ``user enrol`` remediation rather than a botocore stack trace on their
    terminal.
    """
    org = _org(conn)
    email = unique_email("racing")
    with cognito() as (client, stubber):
        expect_lookup(stubber, email=email, sub=None)
        stubber.add_client_error(
            "admin_create_user",
            service_error_code="UsernameExistsException",
            http_status_code=400,
        )
        with pytest.raises(OpsError) as refusal:
            commands.create_user(
                conn, client, pool_id=POOL_ID, email=email, display_name="X", org=org
            )
        stubber.assert_no_pending_responses()
    message = str(refusal.value)
    assert "UsernameExistsException" in message
    assert "user enrol" in message


# --- user enrol --------------------------------------------------------------


def test_user_enrol_moves_every_owned_row_private_and_reports_the_counts(
    conn: Connection,
) -> None:
    """Rubric 29, owner call (j): the rows travel, and they arrive private."""
    org = _org(conn)
    sub = fresh_sub()
    email = unique_email("mover")
    portfolio_id = make_portfolio(conn, owner_user_id=sub, visibility="org")
    member = make_project(conn, owner_user_id=sub, visibility="org", portfolio_id=portfolio_id)
    loose = make_project(conn, owner_user_id=sub, visibility="org")
    stranger = make_project(conn, owner_user_id=fresh_sub("other"), visibility="org")

    with cognito() as (client, stubber):
        expect_lookup(stubber, email=email, sub=sub)
        enrolment = commands.enrol_user(
            conn, client, pool_id=POOL_ID, email=email, display_name="Mover", org=org
        )

    assert (enrolment.projects_moved, enrolment.portfolios_moved) == (2, 1)
    assert "moved 2 project(s), 1 portfolio(s), all private" in enrolment.summary()
    for row_id in (member, loose):
        row = _project_row(conn, row_id)
        assert (row.org_id, row.visibility) == (org.org_id, "private")
    assert _portfolio_row(conn, portfolio_id) == (org.org_id, "private")
    # (d) still holds for the database at large: nobody else's row moved.
    assert _project_row(conn, stranger)[:2] == (None, "org")


def test_user_enrol_is_one_transaction_and_moves_nothing_when_the_move_fails(
    conn: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rubric 29's "in one transaction": the upsert rolls back with the move.

    The failure is injected at the module's ``update`` symbol on its **second**
    call — so the ``app_user`` upsert has landed and the project stamp has
    landed, and only the portfolio stamp fails. If the three writes were not one
    unit, the person would be left enrolled with half their estate moved, which
    is the exact state owner call (j) chose the single transaction to prevent.
    """
    org = _org(conn)
    sub = fresh_sub()
    email = unique_email("atomic")
    portfolio_id = make_portfolio(conn, owner_user_id=sub, visibility="org")
    project_id = make_project(conn, owner_user_id=sub, visibility="org")

    calls = {"n": 0}

    def failing_update(*args: Any, **kwargs: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("injected mid-move failure")
        return update(*args, **kwargs)

    monkeypatch.setattr(commands, "update", failing_update)
    with cognito() as (client, stubber):
        expect_lookup(stubber, email=email, sub=sub)
        with conn.begin_nested() as savepoint:
            with pytest.raises(RuntimeError, match="injected"):
                commands.enrol_user(
                    conn, client, pool_id=POOL_ID, email=email, display_name="A", org=org
                )
            savepoint.rollback()

    assert _user_row(conn, sub) is None
    assert _project_row(conn, project_id)[:2] == (None, "org")
    assert _portfolio_row(conn, portfolio_id) == (None, "org")


def test_re_enrolment_into_a_second_organisation_re_privatises_a_shared_row(
    conn: Connection,
) -> None:
    """Rubric 29: work deliberately shared with org A does not arrive shared in B."""
    first = _org(conn, "First")
    second = _org(conn, "Second")
    sub = fresh_sub()
    email = unique_email("rejoiner")
    project_id = make_project(conn, owner_user_id=sub, visibility="org")

    with cognito() as (client, stubber):
        expect_lookup(stubber, email=email, sub=sub)
        commands.enrol_user(
            conn, client, pool_id=POOL_ID, email=email, display_name="R", org=first
        )
        # The person opts the row back into their organisation, deliberately.
        conn.execute(
            update(project).where(project.c.project_id == project_id).values(visibility="org")
        )
        expect_lookup(stubber, email=email, sub=sub)
        again = commands.enrol_user(
            conn, client, pool_id=POOL_ID, email=email, display_name="R", org=second
        )

    assert again.created is False
    assert "re-enrolled" in again.summary()
    assert _project_row(conn, project_id)[:2] == (second.org_id, "private")


def test_user_enrol_refuses_when_the_stored_address_is_a_different_one(
    conn: Connection,
) -> None:
    """Contract § 3b's staleness rule: act on a stale view and be told to resync."""
    org = _org(conn)
    sub = fresh_sub()
    ops_enrol(conn, user_id=sub, org_id=org.org_id, email=unique_email("old"))
    with cognito() as (client, stubber):
        new_email = unique_email("new")
        expect_lookup(stubber, email=new_email, sub=sub)
        with pytest.raises(OpsError, match="user resync"):
            commands.enrol_user(
                conn, client, pool_id=POOL_ID, email=new_email, display_name="A", org=org
            )


def test_user_enrol_never_touches_the_support_role(conn: Connection) -> None:
    """Enrolment is not a grant path — which is also what keeps it off the race."""
    org = _org(conn)
    sub = fresh_sub()
    email = unique_email("admin")
    ops_enrol(conn, user_id=sub, org_id=None, email=email, is_admin=True)
    with cognito() as (client, stubber):
        expect_lookup(stubber, email=email, sub=sub)
        commands.enrol_user(
            conn, client, pool_id=POOL_ID, email=email, display_name="A", org=org
        )
    assert _user_row(conn, sub).is_admin is True


def test_user_enrol_refuses_an_address_the_pool_does_not_know(conn: Connection) -> None:
    org = _org(conn)
    email = unique_email("ghost")
    with cognito() as (client, stubber):
        expect_lookup(stubber, email=email, sub=None)
        with pytest.raises(OpsError, match="user create"):
            commands.enrol_user(
                conn, client, pool_id=POOL_ID, email=email, display_name="A", org=org
            )


# --- user resync -------------------------------------------------------------


def test_user_resync_writes_the_new_address_onto_the_subject(conn: Connection) -> None:
    org = _org(conn)
    sub = fresh_sub()
    old, new = unique_email("was"), unique_email("now")
    ops_enrol(conn, user_id=sub, org_id=org.org_id, email=old)
    with cognito() as (client, stubber):
        expect_lookup(stubber, email=new, sub=sub)
        resync = commands.resync_user(conn, client, pool_id=POOL_ID, email=new)
    assert (resync.previous_email, resync.email, resync.changed) == (old, new, True)
    assert _user_row(conn, sub).email == new


def test_user_resync_reports_an_address_that_was_already_current(conn: Connection) -> None:
    org = _org(conn)
    sub = fresh_sub()
    email = unique_email("same")
    ops_enrol(conn, user_id=sub, org_id=org.org_id, email=email)
    with cognito() as (client, stubber):
        expect_lookup(stubber, email=email, sub=sub)
        resync = commands.resync_user(conn, client, pool_id=POOL_ID, email=email)
    assert resync.changed is False
    assert "already current" in resync.summary()


def test_user_resync_refuses_a_subject_that_was_never_enrolled(conn: Connection) -> None:
    email = unique_email("stranger")
    with cognito() as (client, stubber):
        expect_lookup(stubber, email=email, sub=fresh_sub())
        with pytest.raises(OpsError, match="not enrolled"):
            commands.resync_user(conn, client, pool_id=POOL_ID, email=email)


def test_user_resync_refuses_a_de_enrolled_row_rather_than_restoring_its_address(
    conn: Connection,
) -> None:
    """Rubric 27's interlock, from the side that reverses it.

    De-enrolment clears ``email`` and ``admin grant`` resolves *by* address:
    that pairing is the whole guard. ``resync`` writing the address back onto a
    de-enrolled row restores the selector, so the guard is defeated by two
    commands neither of which looks wrong on its own. The row keeps its cleared
    address, and the operator is sent to ``user enrol`` — the only command that
    also names the organisation the address is for.
    """
    org = _org(conn)
    sub = fresh_sub()
    email = unique_email("offboarded")
    ops_enrol(conn, user_id=sub, org_id=org.org_id, email=email)
    commands.de_enrol_user(conn, sub=sub)

    with cognito() as (client, stubber):
        expect_lookup(stubber, email=email, sub=sub)
        with pytest.raises(OpsError, match="user enrol"):
            commands.resync_user(conn, client, pool_id=POOL_ID, email=email)

    assert _user_row(conn, sub).email is None


def test_resync_then_grant_cannot_reinstate_an_administrator_for_an_offboarded_person(
    conn: Connection,
) -> None:
    """The two-command sequence, run as a sequence — which is how it would happen.

    An offboarded person, a support ticket, and an operator who reaches for
    ``resync`` because ``admin grant`` said it could not find the address. Both
    halves refuse: the first because the row has no organisation, and the second
    because the address is still cleared. The role is not resurrected either way,
    and the remediation both messages name is the one that is actually correct —
    re-enrol the person first, deliberately.
    """
    org = _org(conn)
    sub = fresh_sub()
    email = unique_email("returning")
    ops_enrol(conn, user_id=sub, org_id=org.org_id, email=email, is_admin=True)
    commands.de_enrol_user(conn, sub=sub)

    with cognito() as (client, stubber):
        expect_lookup(stubber, email=email, sub=sub)
        with pytest.raises(OpsError, match="user enrol"):
            commands.resync_user(conn, client, pool_id=POOL_ID, email=email)
    with pytest.raises(OpsError, match="de-enrolled"):
        commands.set_admin(conn, email=email, grant=True)

    row = _user_row(conn, sub)
    assert (row.email, row.org_id, row.is_admin) == (None, None, False)


# --- de-enrol ----------------------------------------------------------------


def test_de_enrol_clears_the_organisation_on_every_row_they_own(conn: Connection) -> None:
    """Rubric 29: the organisation they left loses sight of their work."""
    org = _org(conn)
    sub = fresh_sub()
    email = unique_email("leaver")
    ops_enrol(conn, user_id=sub, org_id=org.org_id, email=email, is_admin=True)
    portfolio_id = make_portfolio(conn, owner_user_id=sub, org_id=org.org_id, visibility="org")
    project_id = make_project(
        conn, owner_user_id=sub, org_id=org.org_id, visibility="org", portfolio_id=portfolio_id
    )

    result = commands.de_enrol_user(conn, email=email)

    assert (result.projects_cleared, result.portfolios_cleared) == (1, 1)
    assert result.admin_revoked is True
    row = _user_row(conn, sub)
    assert (row.org_id, row.email, row.is_admin) == (None, None, False)
    # visibility is untouched: the NULL-org rule already hides these rows.
    assert _project_row(conn, project_id)[:2] == (None, "org")
    assert _portfolio_row(conn, portfolio_id) == (None, "org")


def test_de_enrol_refuses_a_second_time(conn: Connection) -> None:
    org = _org(conn)
    sub = fresh_sub()
    ops_enrol(conn, user_id=sub, org_id=org.org_id, email=unique_email("once"))
    commands.de_enrol_user(conn, sub=sub)
    with pytest.raises(OpsError, match="already de-enrolled"):
        commands.de_enrol_user(conn, sub=sub)


def test_de_enrol_refuses_an_ambiguous_address(conn: Connection) -> None:
    """``app_user.email`` carries no unique constraint, so this is reachable."""
    org = _org(conn)
    shared = unique_email("shared")
    for _ in range(2):
        ops_enrol(conn, user_id=fresh_sub(), org_id=org.org_id, email=shared)
    with pytest.raises(OpsError, match="share the address"):
        commands.de_enrol_user(conn, email=shared)


# --- rows assign -------------------------------------------------------------


def test_rows_assign_moves_a_portfolio_and_every_member_together(conn: Connection) -> None:
    """Contract § 9 via § 6: there is no assigning half a membership."""
    org = _org(conn)
    owner = fresh_sub()
    portfolio_id = make_portfolio(conn, owner_user_id=owner, visibility="private")
    members = [
        make_project(conn, owner_user_id=owner, visibility="org", portfolio_id=portfolio_id),
        make_project(
            conn,
            owner_user_id=owner,
            visibility="org",
            portfolio_id=portfolio_id,
            status="archived",
        ),
    ]

    assignment = commands.assign_rows(conn, org=org, portfolio_id=portfolio_id)

    assert (assignment.portfolios_moved, assignment.projects_moved) == (1, 2)
    assert _portfolio_row(conn, portfolio_id) == (org.org_id, "private")
    for member in members:  # archived members follow too
        assert _project_row(conn, member)[:2] == (org.org_id, "private")


def test_rows_assign_of_a_member_project_moves_its_portfolio_and_siblings(
    conn: Connection,
) -> None:
    """The closed set: assigning a member cannot leave its portfolio behind."""
    org = _org(conn)
    owner = fresh_sub()
    portfolio_id = make_portfolio(conn, owner_user_id=owner, visibility="org")
    named = make_project(conn, owner_user_id=owner, portfolio_id=portfolio_id)
    sibling = make_project(conn, owner_user_id=owner, portfolio_id=portfolio_id)

    assignment = commands.assign_rows(conn, org=org, project_id=named)

    assert assignment.followed_membership is True
    assert assignment.projects_moved == 2
    assert "moved together" in assignment.summary()
    assert _portfolio_row(conn, portfolio_id) == (org.org_id, "private")
    for row_id in (named, sibling):
        assert _project_row(conn, row_id)[:2] == (org.org_id, "private")


def test_rows_assign_privatises_the_rows_it_moves(conn: Connection) -> None:
    """Rubric 29's last clause, ADR 0033 decision 7: no operator action exposes a row.

    The row this pins is the one the previous revision of the command got
    wrong. ``visibility`` defaults to ``org``, and a row whose ``org_id`` is
    NULL is reachable by its owner alone whatever that column says — the org leg
    is ``org_id IS NOT NULL AND visibility = 'org'``. So an unenrolled owner's
    estate is *full* of rows marked ``org`` that nobody can see, and an
    assignment that stamped ``org_id`` while preserving ``visibility`` handed
    every one of them to every member of the destination, instantly, with the
    owner never acting. They arrive private instead, and the summary says so.
    """
    org = _org(conn)
    owner = fresh_sub()
    project_id = make_project(conn, owner_user_id=owner, visibility="org")
    other = make_project(conn, owner_user_id=owner, visibility="org")

    assignment = commands.assign_rows(conn, org=org, project_id=project_id)

    assert (assignment.projects_moved, assignment.portfolios_moved) == (1, 0)
    assert assignment.privatised is True
    assert "all private" in assignment.summary()
    assert org.name in assignment.summary()
    assert _project_row(conn, project_id)[:2] == (org.org_id, "private")
    # (d) still holds: only the named row moved, and nothing else was privatised.
    assert _project_row(conn, other)[:2] == (None, "org")


def test_rows_assign_of_an_org_visible_portfolio_across_organisations_arrives_private(
    conn: Connection,
) -> None:
    """The cross-org case: work shared with A does not arrive shared with B.

    Same rule as re-enrolment, reached the other way. The portfolio was
    deliberately shared inside its first organisation; assigning it to a second
    is an operator act, and carrying that share across would disclose a whole
    back catalogue to an audience nobody chose.
    """
    first = _org(conn, "First")
    second = _org(conn, "Second")
    owner = fresh_sub()
    portfolio_id = make_portfolio(
        conn, owner_user_id=owner, org_id=first.org_id, visibility="org"
    )
    member = make_project(
        conn,
        owner_user_id=owner,
        org_id=first.org_id,
        visibility="org",
        portfolio_id=portfolio_id,
    )

    assignment = commands.assign_rows(conn, org=second, portfolio_id=portfolio_id)

    assert assignment.privatised is True
    assert _portfolio_row(conn, portfolio_id) == (second.org_id, "private")
    assert _project_row(conn, member)[:2] == (second.org_id, "private")


def test_rows_assign_into_the_organisation_a_row_is_already_in_keeps_its_visibility(
    conn: Connection,
) -> None:
    """Privatising is for moves, not for re-stating where a row already is.

    A no-op assignment changes nobody's audience, so flipping ``visibility``
    would be a gratuitous edit to a choice the owner made. What it still does is
    the ``i.4`` repair: the member takes its portfolio's visibility.
    """
    org = _org(conn)
    owner = fresh_sub()
    portfolio_id = make_portfolio(
        conn, owner_user_id=owner, org_id=org.org_id, visibility="org"
    )
    member = make_project(
        conn,
        owner_user_id=owner,
        org_id=org.org_id,
        visibility="private",
        portfolio_id=portfolio_id,
    )

    assignment = commands.assign_rows(conn, org=org, portfolio_id=portfolio_id)

    assert assignment.privatised is False
    assert "all private" not in assignment.summary()
    assert _portfolio_row(conn, portfolio_id) == (org.org_id, "org")
    assert _project_row(conn, member)[:2] == (org.org_id, "org")


def test_rows_assign_refuses_without_exactly_one_target(conn: Connection) -> None:
    org = _org(conn)
    with pytest.raises(OpsError, match="exactly one"):
        commands.assign_rows(conn, org=org)


# --- admin grant and revoke --------------------------------------------------


def test_admin_grant_and_revoke_hand_the_trace_to_the_caller_and_emit_nothing(
    conn: Connection,
) -> None:
    """Contract § 3a's record, moved off the write path deliberately.

    The command carries the change it made — subject and direction — and logs
    **nothing**. A ``log.info`` here would run inside the operator's
    transaction, so a commit that then failed would leave a durable audit line
    claiming a privilege change that never landed. The line is emitted by
    ``cli._trace`` after the commit instead, which is where the operator ARN
    lives anyway; ``test_ops_cli`` pins that end.
    """
    org = _org(conn)
    sub = fresh_sub()
    email = unique_email("support")
    ops_enrol(conn, user_id=sub, org_id=org.org_id, email=email)

    with capture_logs() as logs:
        granted = commands.set_admin(conn, email=email, grant=True)
        revoked = commands.set_admin(conn, email=email, grant=False)

    assert [line["event"] for line in logs] == []
    assert [change.direction for change in granted.admin_changes()] == ["grant"]
    assert [change.direction for change in revoked.admin_changes()] == ["revoke"]
    assert {change.subject for change in granted.admin_changes()} == {sub}
    assert _user_row(conn, sub).is_admin is False


def test_de_enrolling_an_administrator_carries_a_revoke_to_trace(conn: Connection) -> None:
    """The other way the support role is taken away, and the one offboarding runs.

    ``de-enrol`` clears ``is_admin`` in the same statement that clears the
    organisation. Contract § 3a asks for a record of privilege changes, not of
    ``admin revoke`` invocations, so this counts — and an investigation asking
    "when did they stop being an administrator" is most likely asking about
    exactly this command.
    """
    org = _org(conn)
    admin_sub, plain_sub = fresh_sub(), fresh_sub()
    admin_email, plain_email = unique_email("leaving-admin"), unique_email("leaving")
    ops_enrol(conn, user_id=admin_sub, org_id=org.org_id, email=admin_email, is_admin=True)
    ops_enrol(conn, user_id=plain_sub, org_id=org.org_id, email=plain_email)

    admin_leaver = commands.de_enrol_user(conn, email=admin_email)
    plain_leaver = commands.de_enrol_user(conn, email=plain_email)

    assert [
        (change.subject, change.direction) for change in admin_leaver.admin_changes()
    ] == [(admin_sub, "revoke")]
    # Nothing to record when nothing changed: a de-enrolment is not a privilege
    # change on its own.
    assert plain_leaver.admin_changes() == ()


def test_admin_grant_refuses_when_the_role_is_already_held(conn: Connection) -> None:
    org = _org(conn)
    sub = fresh_sub()
    email = unique_email("twice")
    ops_enrol(conn, user_id=sub, org_id=org.org_id, email=email, is_admin=True)
    with pytest.raises(OpsError, match="already an administrator"):
        commands.set_admin(conn, email=email, grant=True)


def test_admin_grant_refuses_an_address_no_row_carries(conn: Connection) -> None:
    with pytest.raises(OpsError, match="de-enrolled"):
        commands.set_admin(conn, email=unique_email("nobody"), grant=True)


def test_admin_grant_refuses_a_subject_in_no_organisation(conn: Connection) -> None:
    """Defence in depth behind ``user resync``'s refusal (the interlock's other end).

    Only ``user enrol --org`` writes an address, so a row carrying one with no
    organisation should not exist. If one ever does — a hand-written row, a
    future command, a bug — it is not a row that gets the support role, and
    ``--sub`` must not be a way around that either.
    """
    sub = fresh_sub()
    email = unique_email("orphaned")
    ops_enrol(conn, user_id=sub, org_id=None, email=email)

    with pytest.raises(OpsError, match="no organisation"):
        commands.set_admin(conn, email=email, grant=True)
    with pytest.raises(OpsError, match="no organisation"):
        commands.set_admin(conn, sub=sub, grant=True)
    assert _user_row(conn, sub).is_admin is False


def test_admin_revoke_still_reaches_a_subject_in_no_organisation(conn: Connection) -> None:
    """Taking the role away must never be the blocked direction.

    The grant refusal above is a guard on privilege *arriving*. Applying it to
    revoke would strand any pre-existing administrator whose row lost its
    organisation — the one case where an operator most needs the command to work.
    """
    sub = fresh_sub()
    ops_enrol(conn, user_id=sub, org_id=None, email=None, is_admin=True)

    revoked = commands.set_admin(conn, sub=sub, grant=False)

    assert revoked.direction == "revoke"
    assert _user_row(conn, sub).is_admin is False


def test_admin_revoke_resolves_an_ambiguous_address_by_sub(conn: Connection) -> None:
    """The refusal recommends ``--sub``, so ``--sub`` has to exist (both directions).

    ``app_user.email`` carries no unique constraint, so two rows can share an
    address — and the command that most needs to work under that condition is
    revoking a compromised administrator. Before ``--sub``, the refusal named a
    flag the parser did not accept: a dead end on the defensive path.
    """
    org = _org(conn)
    shared = unique_email("shared-admin")
    subs = [fresh_sub(), fresh_sub()]
    for sub in subs:
        ops_enrol(conn, user_id=sub, org_id=org.org_id, email=shared, is_admin=True)

    with pytest.raises(OpsError, match="resolve with --sub"):
        commands.set_admin(conn, email=shared, grant=False)

    revoked = commands.set_admin(conn, sub=subs[0], grant=False)

    assert revoked.user_id == subs[0]
    assert _user_row(conn, subs[0]).is_admin is False
    assert _user_row(conn, subs[1]).is_admin is True


# --- concurrency (rubric 27) -------------------------------------------------


def test_a_de_enrolment_stops_a_concurrent_operator_resurrecting_admin(
    engine: Engine,
) -> None:
    """Rubric 27, the named hazard, over two real committed connections.

    Operator A de-enrols and commits. Operator B — who resolved the same person
    by address a moment earlier — then runs ``admin grant``. B's ``FOR UPDATE``
    read finds no row carrying that address, because de-enrolment cleared it,
    and refuses. The support role is not resurrected.
    """
    email = unique_email("race")
    sub = fresh_sub()
    with seeded(engine) as conn:
        org_id = make_org(conn)
        ops_enrol(conn, user_id=sub, org_id=org_id, email=email)

    with seeded(engine) as operator_a:
        commands.de_enrol_user(operator_a, email=email)

    with seeded(engine) as operator_b, pytest.raises(OpsError, match="de-enrolled"):
        commands.set_admin(operator_b, email=email, grant=True)

    with seeded(engine) as check:
        assert check.execute(
            select(app_user.c.is_admin).where(app_user.c.user_id == sub)
        ).scalar_one() is False


def test_admin_grant_takes_a_real_row_lock_by_address_and_by_sub(engine: Engine) -> None:
    """The refusal above is only sound if the read genuinely locks — either selector.

    Proved without threads: operator A holds the row ``FOR UPDATE`` in an open
    transaction while operator B, given a 250ms ``lock_timeout``, tries the same
    read. Postgres raises rather than letting B proceed on a stale view — which
    is what serialises the two operators in the first place.

    ``--sub`` is asserted alongside ``--email`` because the recorded objection to
    resolving by subject at all was that it "bypasses the address-mediated
    compare-and-refuse". It bypasses the address as a *selector*; it does not
    bypass the lock, and the interlock it would otherwise weaken is carried by
    the grant path's organisation check instead
    (``test_admin_grant_refuses_a_subject_in_no_organisation``).
    """
    email = unique_email("locked")
    sub = fresh_sub()
    with seeded(engine) as conn:
        org_id = make_org(conn)
        ops_enrol(conn, user_id=sub, org_id=org_id, email=email)

    with engine.connect() as operator_a:
        held = operator_a.begin()
        operator_a.execute(
            select(app_user).where(app_user.c.user_id == sub).with_for_update()
        ).mappings().one()
        for selector in ("email", "sub"):
            with engine.connect() as operator_b:
                attempt = operator_b.begin()
                operator_b.execute(text("SET LOCAL lock_timeout = '250ms'"))
                with pytest.raises(DBAPIError, match="lock timeout"):
                    if selector == "email":
                        commands.set_admin(operator_b, email=email, grant=True)
                    else:
                        commands.set_admin(operator_b, sub=sub, grant=True)
                attempt.rollback()
        held.rollback()
