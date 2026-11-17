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
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError
from structlog.testing import capture_logs

from policy_atlas.core.schema import (
    app_user,
    ops_action,
    organisation,
    organisation_domain,
    project,
    project_membership,
    task,
)
from policy_atlas.ops import commands
from policy_atlas.ops.errors import EnrolledElsewhere, OpsError, ResendTooSoon
from tests.api.org_support import (
    make_org,
    make_project,
    make_task,
    ops_enrol,
    seeded,
    unique_email,
)
from tests.helpers import now
from tests.ops.support import (
    POOL_ID,
    cognito,
    expect_create,
    expect_create_manual,
    expect_lookup,
    expect_reissue,
    expect_resend,
    expect_status_lookup,
    expect_sub_lookup,
    fresh_sub,
)


def _org(conn: Connection, name: str = "Org") -> commands.Organisation:
    org_id = make_org(conn, name=name)
    resolved = conn.execute(
        select(organisation.c.name).where(organisation.c.org_id == org_id)
    ).scalar_one()
    return commands.Organisation(org_id=org_id, name=resolved)


def _task_row(conn: Connection, task_id: uuid.UUID) -> Any:
    return conn.execute(
        select(task.c.org_id, task.c.visibility, task.c.updated_at).where(task.c.task_id == task_id)
    ).one()


def _project_row(conn: Connection, project_id: uuid.UUID) -> Any:
    return conn.execute(
        select(project.c.org_id, project.c.visibility).where(project.c.project_id == project_id)
    ).one()


def _user_row(conn: Connection, sub: str) -> Any:
    return conn.execute(
        select(
            app_user.c.org_id, app_user.c.email, app_user.c.is_admin, app_user.c.display_name
        ).where(app_user.c.user_id == sub)
    ).one_or_none()


# --- organisations -----------------------------------------------------------


def test_org_create_inserts_the_organisation(conn: Connection) -> None:
    name = f"Nesta {uuid.uuid4()}"
    created = commands.create_organisation(conn, name=name)
    stored = conn.execute(
        select(organisation.c.name).where(organisation.c.org_id == created.org_id)
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


def test_user_create_without_an_org_stores_the_name_and_the_address(
    conn: Connection,
) -> None:
    """Omitting the organisation leaves a findable account and no organisation.

    The address is stored so an operator can look the person up. The support
    role still requires an organisation: ``admin grant`` refuses this row.
    """
    email = unique_email("bare")
    sub = fresh_sub()
    with cognito() as (client, stubber):
        expect_lookup(stubber, email=email, sub=None)
        expect_create(stubber, email=email, sub=sub)
        created = commands.create_user(
            conn, client, pool_id=POOL_ID, email=email, display_name="Bare Person"
        )
        stubber.assert_no_pending_responses()
    assert isinstance(created, commands.CreatedAccount)
    assert created.created is True
    assert "not in an organisation" in created.summary()
    assert "temporary password" not in created.summary()
    row = _user_row(conn, sub)
    assert row is not None
    assert (row.org_id, row.email, row.is_admin, row.display_name) == (
        None,
        email,
        False,
        "Bare Person",
    )
    with pytest.raises(OpsError, match="no organisation"):
        commands.set_admin(conn, email=email, grant=True)
    assert _user_row(conn, sub).is_admin is False


def test_user_create_without_an_org_records_an_account_that_already_exists(
    conn: Connection,
) -> None:
    """A kept Cognito account can be recorded by re-running the same command."""
    email = unique_email("kept")
    sub = fresh_sub()
    with cognito() as (client, stubber):
        expect_lookup(stubber, email=email, sub=sub)
        created = commands.create_user(
            conn, client, pool_id=POOL_ID, email=email, display_name="Kept Person"
        )
        stubber.assert_no_pending_responses()
    assert created.created is False
    assert "recorded" in created.summary()
    row = _user_row(conn, sub)
    assert (row.org_id, row.email, row.display_name) == (None, email, "Kept Person")


def test_user_create_without_an_org_refuses_someone_already_enrolled(conn: Connection) -> None:
    org = _org(conn)
    email = unique_email("placed")
    sub = fresh_sub()
    ops_enrol(conn, user_id=sub, org_id=org.org_id, email=email, display_name="Placed")
    with cognito() as (client, stubber):
        expect_lookup(stubber, email=email, sub=sub)
        with pytest.raises(OpsError, match="already in an organisation"):
            commands.create_user(conn, client, pool_id=POOL_ID, email=email, display_name="Placed")
        stubber.assert_no_pending_responses()
    assert _user_row(conn, sub).org_id == org.org_id


# --- user enrol --------------------------------------------------------------


def test_user_enrol_moves_every_owned_row_private_and_reports_the_counts(
    conn: Connection,
) -> None:
    """Rubric 29, owner call (j): the rows travel, and they arrive private."""
    org = _org(conn)
    sub = fresh_sub()
    email = unique_email("mover")
    project_id = make_project(conn, owner_user_id=sub, visibility="org")
    member = make_task(conn, owner_user_id=sub, visibility="org", project_id=project_id)
    loose = make_task(conn, owner_user_id=sub, visibility="org")
    stranger = make_task(conn, owner_user_id=fresh_sub("other"), visibility="org")

    with cognito() as (client, stubber):
        expect_lookup(stubber, email=email, sub=sub)
        enrolment = commands.enrol_user(
            conn, client, pool_id=POOL_ID, email=email, display_name="Mover", org=org
        )

    assert (enrolment.tasks_moved, enrolment.projects_moved) == (2, 1)
    assert "moved 2 task(s), 1 project(s), all private" in enrolment.summary()
    for row_id in (member, loose):
        row = _task_row(conn, row_id)
        assert (row.org_id, row.visibility) == (org.org_id, "private")
    assert _project_row(conn, project_id) == (org.org_id, "private")
    # (d) still holds for the database at large: nobody else's row moved.
    assert _task_row(conn, stranger)[:2] == (None, "org")


def test_user_enrol_severs_memberships_linking_their_rows_to_colleagues_rows(
    conn: Connection,
) -> None:
    """An org move cuts cross-owner membership links, and says so.

    Colleague assignment (owner ruling 2026-08-27) lets a colleague's task sit
    in someone else's project. When either person's rows move organisation,
    those links would leave a member and a project disagreeing on `org_id`,
    so the move severs them — both directions — and reports the count. The
    rows on each side keep the visibility and organisation the move gives
    them; only the links go.
    """
    org = _org(conn)
    mover = fresh_sub()
    email = unique_email("severed")
    colleague = fresh_sub("colleague")
    movers_project = make_project(conn, owner_user_id=mover, visibility="org")
    movers_task = make_task(conn, owner_user_id=mover, visibility="org")
    colleagues_project = make_project(conn, owner_user_id=colleague, visibility="org")
    colleagues_task = make_task(
        conn, owner_user_id=colleague, visibility="org", project_id=movers_project
    )
    # The mover's task sits in the colleague's project; the colleague's task
    # sits in the mover's project; the mover's own pairing must survive.
    conn.execute(
        project_membership.insert().values(
            project_id=colleagues_project, task_id=movers_task, created_at=now()
        )
    )
    own_link = make_task(conn, owner_user_id=mover, visibility="org", project_id=movers_project)

    with cognito() as (client, stubber):
        expect_lookup(stubber, email=email, sub=mover)
        enrolment = commands.enrol_user(
            conn, client, pool_id=POOL_ID, email=email, display_name="Mover", org=org
        )

    assert enrolment.memberships_severed == 2
    assert "cut 2 membership(s)" in enrolment.summary()
    remaining = {
        (row.project_id, row.task_id) for row in conn.execute(select(project_membership)).all()
    }
    assert (movers_project, own_link) in remaining
    assert (movers_project, colleagues_task) not in remaining
    assert (colleagues_project, movers_task) not in remaining
    # The colleague's rows did not move; they just lost the links.
    assert _task_row(conn, colleagues_task)[:2] == (None, "org")


def test_user_enrol_is_one_transaction_and_moves_nothing_when_the_move_fails(
    conn: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rubric 29's "in one transaction": the upsert rolls back with the move.

    The failure is injected at the module's ``update`` symbol on its **second**
    call — so the ``app_user`` upsert has landed and the task stamp has
    landed, and only the project stamp fails. If the three writes were not one
    unit, the person would be left enrolled with half their estate moved, which
    is the exact state owner call (j) chose the single transaction to prevent.
    """
    org = _org(conn)
    sub = fresh_sub()
    email = unique_email("atomic")
    project_id = make_project(conn, owner_user_id=sub, visibility="org")
    task_id = make_task(conn, owner_user_id=sub, visibility="org")

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
    assert _task_row(conn, task_id)[:2] == (None, "org")
    assert _project_row(conn, project_id) == (None, "org")


def test_re_enrolment_into_a_second_organisation_re_privatises_a_shared_row(
    conn: Connection,
) -> None:
    """Rubric 29: work deliberately shared with org A does not arrive shared in B."""
    first = _org(conn, "First")
    second = _org(conn, "Second")
    sub = fresh_sub()
    email = unique_email("rejoiner")
    task_id = make_task(conn, owner_user_id=sub, visibility="org")

    with cognito() as (client, stubber):
        expect_lookup(stubber, email=email, sub=sub)
        commands.enrol_user(conn, client, pool_id=POOL_ID, email=email, display_name="R", org=first)
        # The person opts the row back into their organisation, deliberately.
        conn.execute(update(task).where(task.c.task_id == task_id).values(visibility="org"))
        expect_lookup(stubber, email=email, sub=sub)
        again = commands.enrol_user(
            conn, client, pool_id=POOL_ID, email=email, display_name="R", org=second
        )

    assert again.created is False
    assert "re-enrolled" in again.summary()
    assert _task_row(conn, task_id)[:2] == (second.org_id, "private")


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
        commands.enrol_user(conn, client, pool_id=POOL_ID, email=email, display_name="A", org=org)
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

    De-enrolment keeps the address and clears the organisation. ``resync`` will
    not rewrite that address until the person is enrolled again, and the
    operator is sent to ``user enrol``.
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

    assert _user_row(conn, sub).email == email


def test_resync_then_grant_cannot_reinstate_an_administrator_for_an_offboarded_person(
    conn: Connection,
) -> None:
    """The two-command sequence, run as a sequence — which is how it would happen.

    An offboarded person, a support ticket, and an operator who reaches for
    ``resync`` and then ``admin grant``. Both refuse because the row has no
    organisation. The address is still there, and the role is not resurrected.
    Re-enrol the person first.
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
    with pytest.raises(OpsError, match="no organisation"):
        commands.set_admin(conn, email=email, grant=True)

    row = _user_row(conn, sub)
    assert (row.email, row.org_id, row.is_admin) == (email, None, False)


# --- user reissue ------------------------------------------------------------


def test_user_reissue_mints_a_non_permanent_password_for_a_never_signed_in_account() -> None:
    email = unique_email("reissue")
    sub = fresh_sub()
    with cognito() as (client, stubber):
        expect_status_lookup(stubber, email=email, sub=sub, status="FORCE_CHANGE_PASSWORD")
        expect_reissue(stubber, sub=sub)
        with capture_logs() as logged:
            reissue = commands.reissue_temporary_password(client, pool_id=POOL_ID, email=email)
        stubber.assert_no_pending_responses()

    minted = reissue.temporary_password
    assert len(minted) == 20
    assert reissue.user_id == sub
    assert minted in reissue.summary()
    assert "single-use" in reissue.summary()
    assert not any(minted in str(event) for event in logged)


@pytest.mark.parametrize("status", ["CONFIRMED", "RESET_REQUIRED", "UNCONFIRMED"])
def test_user_reissue_refuses_an_account_not_awaiting_first_sign_in(status: str) -> None:
    """A person who set their own password recovers it themselves.

    No ``AdminSetUserPassword`` is queued, so the Stubber fails the test if the
    refusal comes after the password was already replaced.
    """
    email = unique_email("confirmed")
    with cognito() as (client, stubber):
        expect_status_lookup(stubber, email=email, sub=fresh_sub(), status=status)
        with pytest.raises(OpsError, match="Nothing was changed"):
            commands.reissue_temporary_password(client, pool_id=POOL_ID, email=email)
        stubber.assert_no_pending_responses()


def test_user_reissue_refuses_an_unknown_address() -> None:
    email = unique_email("nobody")
    with cognito() as (client, stubber):
        expect_lookup(stubber, email=email, sub=None)
        with pytest.raises(OpsError, match="no account in the pool"):
            commands.reissue_temporary_password(client, pool_id=POOL_ID, email=email)
        stubber.assert_no_pending_responses()


def test_user_reissue_turns_a_cognito_refusal_into_an_ops_error() -> None:
    email = unique_email("refused")
    sub = fresh_sub()
    with cognito() as (client, stubber):
        expect_status_lookup(stubber, email=email, sub=sub, status="FORCE_CHANGE_PASSWORD")
        stubber.add_client_error(
            "admin_set_user_password", service_error_code="InvalidPasswordException"
        )
        with pytest.raises(OpsError, match="InvalidPasswordException"):
            commands.reissue_temporary_password(client, pool_id=POOL_ID, email=email)
        stubber.assert_no_pending_responses()


# --- de-enrol ----------------------------------------------------------------


def test_de_enrol_clears_the_organisation_on_every_row_they_own(conn: Connection) -> None:
    """Rubric 29: the organisation they left loses sight of their work."""
    org = _org(conn)
    sub = fresh_sub()
    email = unique_email("leaver")
    ops_enrol(conn, user_id=sub, org_id=org.org_id, email=email, is_admin=True)
    project_id = make_project(conn, owner_user_id=sub, org_id=org.org_id, visibility="org")
    task_id = make_task(
        conn, owner_user_id=sub, org_id=org.org_id, visibility="org", project_id=project_id
    )

    result = commands.de_enrol_user(conn, email=email)

    assert (result.tasks_cleared, result.projects_cleared) == (1, 1)
    assert result.admin_revoked is True
    row = _user_row(conn, sub)
    assert (row.org_id, row.email, row.is_admin) == (None, email, False)
    # visibility is untouched: the NULL-org rule already hides these rows.
    assert _task_row(conn, task_id)[:2] == (None, "org")
    assert _project_row(conn, project_id) == (None, "org")


def test_de_enrol_refuses_a_second_time(conn: Connection) -> None:
    org = _org(conn)
    sub = fresh_sub()
    ops_enrol(conn, user_id=sub, org_id=org.org_id, email=unique_email("once"))
    commands.de_enrol_user(conn, sub=sub)
    with pytest.raises(OpsError, match="no organisation"):
        commands.de_enrol_user(conn, sub=sub)
    assert _user_row(conn, sub).email is not None


def test_de_enrol_refuses_an_ambiguous_address(conn: Connection) -> None:
    """``app_user.email`` carries no unique constraint, so this is reachable."""
    org = _org(conn)
    shared = unique_email("shared")
    for _ in range(2):
        ops_enrol(conn, user_id=fresh_sub(), org_id=org.org_id, email=shared)
    with pytest.raises(OpsError, match="share the address"):
        commands.de_enrol_user(conn, email=shared)


# --- rows assign -------------------------------------------------------------


def test_rows_assign_moves_a_project_and_every_member_together(conn: Connection) -> None:
    """Contract § 9 via § 6: there is no assigning half a membership."""
    org = _org(conn)
    owner = fresh_sub()
    project_id = make_project(conn, owner_user_id=owner, visibility="private")
    members = [
        make_task(conn, owner_user_id=owner, visibility="org", project_id=project_id),
        make_task(
            conn,
            owner_user_id=owner,
            visibility="org",
            project_id=project_id,
            status="archived",
        ),
    ]

    assignment = commands.assign_rows(conn, org=org, project_id=project_id)

    assert (assignment.projects_moved, assignment.tasks_moved) == (1, 2)
    assert _project_row(conn, project_id) == (org.org_id, "private")
    for member in members:  # archived members follow too
        assert _task_row(conn, member)[:2] == (org.org_id, "private")


def test_rows_assign_of_a_member_task_moves_its_project_and_siblings(
    conn: Connection,
) -> None:
    """The closed set: assigning a member cannot leave its project behind."""
    org = _org(conn)
    owner = fresh_sub()
    project_id = make_project(conn, owner_user_id=owner, visibility="org")
    named = make_task(conn, owner_user_id=owner, project_id=project_id)
    sibling = make_task(conn, owner_user_id=owner, project_id=project_id)

    assignment = commands.assign_rows(conn, org=org, task_id=named)

    assert assignment.followed_membership is True
    assert assignment.tasks_moved == 2
    assert "moved together" in assignment.summary()
    assert _project_row(conn, project_id) == (org.org_id, "private")
    for row_id in (named, sibling):
        assert _task_row(conn, row_id)[:2] == (org.org_id, "private")


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
    task_id = make_task(conn, owner_user_id=owner, visibility="org")
    other = make_task(conn, owner_user_id=owner, visibility="org")

    assignment = commands.assign_rows(conn, org=org, task_id=task_id)

    assert (assignment.tasks_moved, assignment.projects_moved) == (1, 0)
    assert assignment.privatised is True
    assert "all private" in assignment.summary()
    assert org.name in assignment.summary()
    assert _task_row(conn, task_id)[:2] == (org.org_id, "private")
    # (d) still holds: only the named row moved, and nothing else was privatised.
    assert _task_row(conn, other)[:2] == (None, "org")


def test_rows_assign_of_an_org_visible_project_across_organisations_arrives_private(
    conn: Connection,
) -> None:
    """The cross-org case: work shared with A does not arrive shared with B.

    Same rule as re-enrolment, reached the other way. The project was
    deliberately shared inside its first organisation; assigning it to a second
    is an operator act, and carrying that share across would disclose a whole
    back catalogue to an audience nobody chose.
    """
    first = _org(conn, "First")
    second = _org(conn, "Second")
    owner = fresh_sub()
    project_id = make_project(conn, owner_user_id=owner, org_id=first.org_id, visibility="org")
    member = make_task(
        conn,
        owner_user_id=owner,
        org_id=first.org_id,
        visibility="org",
        project_id=project_id,
    )

    assignment = commands.assign_rows(conn, org=second, project_id=project_id)

    assert assignment.privatised is True
    assert _project_row(conn, project_id) == (second.org_id, "private")
    assert _task_row(conn, member)[:2] == (second.org_id, "private")


def test_rows_assign_into_the_organisation_a_row_is_already_in_keeps_its_visibility(
    conn: Connection,
) -> None:
    """Privatising is for moves, not for re-stating where a row already is.

    A no-op assignment changes nobody's audience, so flipping ``visibility``
    would be a gratuitous edit to a choice the owner made. What it still does is
    the ``i.4`` repair: the member takes its project's visibility.
    """
    org = _org(conn)
    owner = fresh_sub()
    project_id = make_project(conn, owner_user_id=owner, org_id=org.org_id, visibility="org")
    member = make_task(
        conn,
        owner_user_id=owner,
        org_id=org.org_id,
        visibility="private",
        project_id=project_id,
    )

    assignment = commands.assign_rows(conn, org=org, project_id=project_id)

    assert assignment.privatised is False
    assert "all private" not in assignment.summary()
    assert _project_row(conn, project_id) == (org.org_id, "org")
    assert _task_row(conn, member)[:2] == (org.org_id, "org")


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

    assert [(change.subject, change.direction) for change in admin_leaver.admin_changes()] == [
        (admin_sub, "revoke")
    ]
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
    with pytest.raises(OpsError, match="no user with the address"):
        commands.set_admin(conn, email=unique_email("nobody"), grant=True)


def test_admin_grant_refuses_a_subject_in_no_organisation(conn: Connection) -> None:
    """The support role requires an organisation, whichever selector finds the row.

    ``user create`` without an organisation stores an address, and de-enrolment
    keeps it. Neither shape gets the support role, and ``--sub`` is not a way
    around that.
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
    read finds the row, sees no organisation, and refuses. The support role is
    not resurrected.
    """
    email = unique_email("race")
    sub = fresh_sub()
    with seeded(engine) as conn:
        org_id = make_org(conn)
        ops_enrol(conn, user_id=sub, org_id=org_id, email=email)

    with seeded(engine) as operator_a:
        commands.de_enrol_user(operator_a, email=email)

    with seeded(engine) as operator_b, pytest.raises(OpsError, match="no organisation"):
        commands.set_admin(operator_b, email=email, grant=True)

    with seeded(engine) as check:
        assert (
            check.execute(select(app_user.c.is_admin).where(app_user.c.user_id == sub)).scalar_one()
            is False
        )


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


# --- user offboard -------------------------------------------------------------
#
# The Stubber answers calls strictly in the order they were queued, and fails the
# call on any other operation or parameter. So queuing `admin_disable_user` before
# `admin_user_global_sign_out` *is* the order assertion: a swapped order fails.


def _expect_lookup_by_sub(stubber: Any, *, sub: str) -> None:
    stubber.add_response(
        "list_users",
        {"Users": [{"Username": sub, "Attributes": [{"Name": "sub", "Value": sub}]}]},
        {"UserPoolId": POOL_ID, "Filter": f'sub = "{sub}"', "Limit": 1},
    )


def _expect_lock_out(stubber: Any, *, sub: str, fail: str | None = None) -> None:
    """Queue the disable then the global sign-out; ``fail`` names the one that errors."""
    for operation in ("admin_disable_user", "admin_user_global_sign_out"):
        params = {"UserPoolId": POOL_ID, "Username": sub}
        if operation == fail:
            stubber.add_client_error(
                operation, service_error_code="InternalErrorException", expected_params=params
            )
            return
        stubber.add_response(operation, {}, params)


def _public_task(conn: Connection, *, owner: str, org_id: uuid.UUID | None) -> uuid.UUID:
    task_id = make_task(conn, owner_user_id=owner, org_id=org_id, visibility="org")
    conn.execute(update(task).where(task.c.task_id == task_id).values(is_public=True))
    return task_id


def _is_public(conn: Connection, task_id: uuid.UUID) -> bool:
    return bool(
        conn.execute(select(task.c.is_public).where(task.c.task_id == task_id)).scalar_one()
    )


def test_offboard_disables_then_signs_out_then_de_enrols_and_privatises_links(
    conn: Connection,
) -> None:
    org = _org(conn)
    sub = fresh_sub()
    email = unique_email("offboard")
    ops_enrol(conn, user_id=sub, org_id=org.org_id, email=email)
    public = _public_task(conn, owner=sub, org_id=org.org_id)
    private = make_task(conn, owner_user_id=sub, org_id=org.org_id)
    someone_elses = _public_task(conn, owner=fresh_sub(), org_id=org.org_id)

    with cognito() as (client, stubber):
        _expect_lookup_by_sub(stubber, sub=sub)
        _expect_lock_out(stubber, sub=sub)
        result = commands.offboard_user(conn, client, pool_id=POOL_ID, email=email)
        stubber.assert_no_pending_responses()

    assert result.de_enrolment is not None
    assert result.links_made_private == 1
    assert (_is_public(conn, public), _is_public(conn, private)) == (False, False)
    assert _is_public(conn, someone_elses) is True
    assert _user_row(conn, sub).org_id is None
    assert result.admin_changes() == ()  # not an administrator: nothing to trace
    assert "disabled the Cognito account" in result.summary()


def test_offboard_of_an_already_de_enrolled_person_skips_de_enrol(conn: Connection) -> None:
    """M-02's main case: removed from the organisation earlier, login still working."""
    sub = fresh_sub()
    email = unique_email("gone")
    ops_enrol(conn, user_id=sub, org_id=None, email=email)
    public = _public_task(conn, owner=sub, org_id=None)

    with cognito() as (client, stubber):
        _expect_lookup_by_sub(stubber, sub=sub)
        _expect_lock_out(stubber, sub=sub)
        result = commands.offboard_user(conn, client, pool_id=POOL_ID, sub=sub)
        stubber.assert_no_pending_responses()

    assert result.de_enrolment is None
    assert "de-enrol skipped: not enrolled" in result.steps
    assert result.links_made_private == 1
    assert _is_public(conn, public) is False


def test_offboard_of_an_account_with_no_app_user_row_is_cognito_only(conn: Connection) -> None:
    sub = fresh_sub()
    email = unique_email("never-arrived")
    with cognito() as (client, stubber):
        expect_lookup(stubber, email=email, sub=sub)
        _expect_lock_out(stubber, sub=sub)
        result = commands.offboard_user(conn, client, pool_id=POOL_ID, email=email)
        stubber.assert_no_pending_responses()

    assert (result.user_id, result.de_enrolment, result.links_made_private) == (sub, None, 0)
    assert any("Cognito only" in step for step in result.steps)
    assert _user_row(conn, sub) is None


def test_offboard_of_a_row_whose_cognito_account_is_gone_still_cleans_the_database(
    conn: Connection,
) -> None:
    """The account was deleted from the pool by hand; the row and the links remain."""
    org = _org(conn)
    sub = fresh_sub()
    ops_enrol(conn, user_id=sub, org_id=org.org_id, email=unique_email("deleted-upstream"))
    public = _public_task(conn, owner=sub, org_id=org.org_id)

    with cognito() as (client, stubber):
        stubber.add_response(
            "list_users",
            {"Users": []},
            {"UserPoolId": POOL_ID, "Filter": f'sub = "{sub}"', "Limit": 1},
        )
        result = commands.offboard_user(conn, client, pool_id=POOL_ID, sub=sub)
        stubber.assert_no_pending_responses()  # no disable, no sign-out

    assert result.steps[0].startswith("no Cognito account in the pool")
    assert result.de_enrolment is not None
    assert result.links_made_private == 1
    assert _is_public(conn, public) is False
    assert _user_row(conn, sub).org_id is None


def test_offboard_refuses_when_neither_the_pool_nor_the_database_knows_them(
    conn: Connection,
) -> None:
    sub = fresh_sub()
    with cognito() as (client, stubber):
        stubber.add_response(
            "list_users",
            {"Users": []},
            {"UserPoolId": POOL_ID, "Filter": f'sub = "{sub}"', "Limit": 1},
        )
        with pytest.raises(OpsError, match="Nothing was changed"):
            commands.offboard_user(conn, client, pool_id=POOL_ID, sub=sub)


@pytest.mark.parametrize("failing", ["admin_disable_user", "admin_user_global_sign_out"])
def test_offboard_leaves_the_database_untouched_when_cognito_fails(
    conn: Connection, failing: str
) -> None:
    org = _org(conn)
    sub = fresh_sub()
    email = unique_email("stuck")
    ops_enrol(conn, user_id=sub, org_id=org.org_id, email=email, is_admin=True)
    public = _public_task(conn, owner=sub, org_id=org.org_id)

    with cognito() as (client, stubber):
        _expect_lookup_by_sub(stubber, sub=sub)
        _expect_lock_out(stubber, sub=sub, fail=failing)
        with pytest.raises(OpsError, match="InternalErrorException"):
            commands.offboard_user(conn, client, pool_id=POOL_ID, email=email)
        stubber.assert_no_pending_responses()

    row = _user_row(conn, sub)
    assert (row.org_id, row.is_admin) == (org.org_id, True)
    assert _is_public(conn, public) is True


def test_offboarding_an_administrator_carries_the_admin_revoke_trace(conn: Connection) -> None:
    org = _org(conn)
    sub = fresh_sub()
    ops_enrol(conn, user_id=sub, org_id=org.org_id, email=unique_email("admin-out"), is_admin=True)
    with cognito() as (client, stubber):
        _expect_lookup_by_sub(stubber, sub=sub)
        _expect_lock_out(stubber, sub=sub)
        result = commands.offboard_user(conn, client, pool_id=POOL_ID, sub=sub)
    assert [(c.subject, c.direction) for c in result.admin_changes()] == [(sub, "revoke")]
    assert _user_row(conn, sub).is_admin is False


def test_cli_user_offboard_reaches_the_command_and_traces_the_revoke(
    engine: Engine, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """``user offboard --email`` through the real entrypoint, environment check and all.

    The trace is the same ``ops.admin_change`` line ``admin revoke`` writes
    (``cli._trace``), read off stdout as ``test_ops_cli`` does.
    """
    import json

    from policy_atlas.ops.cli import main
    from tests.ops.support import FakeSts, expect_environment

    monkeypatch.setenv("LOG_FORMAT", "json")
    sub = fresh_sub("cognito")
    email = unique_email("cli-offboard")
    with seeded(engine) as setup:
        ops_enrol(setup, user_id=sub, org_id=make_org(setup), email=email, is_admin=True)
        public = _public_task(setup, owner=sub, org_id=None)

    lines: list[str] = []
    with cognito() as (client, stubber):
        expect_environment(stubber, known_subs=[sub], sampled=[sub])
        _expect_lookup_by_sub(stubber, sub=sub)
        _expect_lock_out(stubber, sub=sub)
        status = main(
            [
                "--env",
                "staging",
                "--expected-account",
                "111122223333",
                "--user-pool-id",
                POOL_ID,
                "user",
                "offboard",
                "--email",
                email,
            ],
            engine=engine,
            cognito=client,
            sts=FakeSts(),
            write=lines.append,
        )
        stubber.assert_no_pending_responses()

    assert status == 0
    assert any("offboarded" in line for line in lines)
    traced = [
        entry
        for entry in (
            json.loads(line)
            for line in capsys.readouterr().out.splitlines()
            if line.startswith("{")
        )
        if entry.get("event") == "ops.admin_change"
    ]
    assert [(entry["subject"], entry["direction"]) for entry in traced] == [(sub, "revoke")]
    with seeded(engine) as check:
        assert _is_public(check, public) is False
        assert _user_row(check, sub).org_id is None


# --- task 065: the ensure-account command (B4, B9, § Terms) --------------------
#
# The same Stubber discipline as `user create`: `expect_create` pins
# `DesiredDeliveryMediums=["EMAIL"]`, and an empty queue is the proof that no
# second invitation went out.


def _row(conn: Connection, sub: str) -> Any:
    """The whole ``app_user`` row, for the columns task 065 added."""
    return conn.execute(select(app_user).where(app_user.c.user_id == sub)).mappings().one_or_none()


def _set_flags(conn: Connection, sub: str, **flags: Any) -> None:
    conn.execute(update(app_user).where(app_user.c.user_id == sub).values(**flags))


def test_ensure_account_creates_sends_and_enrols_an_address_the_pool_does_not_know(
    conn: Connection,
) -> None:
    """Branch one: no account, so create it (emailed invitation), enrol, stamp ``invited_at``."""
    org = _org(conn)
    email = unique_email("ensure-new")
    sub = fresh_sub()
    with cognito() as (client, stubber):
        expect_lookup(stubber, email=email, sub=None)
        expect_create(stubber, email=email, sub=sub)
        enrolment = commands.ensure_account_enrolled(
            conn, client, pool_id=POOL_ID, email=email, display_name="New", org=org
        )
        stubber.assert_no_pending_responses()
    assert (enrolment.user_id, enrolment.created, enrolment.invitation_sent) == (sub, True, True)
    row = _row(conn, sub)
    assert (row["org_id"], row["email"], row["display_name"]) == (org.org_id, email, "New")
    assert row["invited_at"] is not None


@pytest.mark.parametrize("stored", [False, True])
def test_ensure_account_enrols_an_existing_unenrolled_account_without_a_send(
    conn: Connection, stored: bool
) -> None:
    """Branch two: the pool knows the address; nothing is created and nothing is sent.

    ``stored`` covers both unenrolled shapes: no ``app_user`` row at all, and a
    row with no organisation (``user create`` without ``--org``, or a de-enrolment).
    """
    org = _org(conn)
    email = unique_email("ensure-existing")
    sub = fresh_sub()
    if stored:
        ops_enrol(conn, user_id=sub, org_id=None, email=email, display_name="Old Name")
    task_id = make_task(conn, owner_user_id=sub, visibility="org")
    with cognito() as (client, stubber):
        expect_lookup(stubber, email=email, sub=sub)
        enrolment = commands.ensure_account_enrolled(
            conn, client, pool_id=POOL_ID, email=email, display_name="Ensured", org=org
        )
        stubber.assert_no_pending_responses()
    assert enrolment.invitation_sent is False
    assert enrolment.created is (not stored)
    assert enrolment.tasks_moved == 1
    row = _row(conn, sub)
    assert (row["org_id"], row["display_name"], row["invited_at"]) == (org.org_id, "Ensured", None)
    assert _task_row(conn, task_id)[:2] == (org.org_id, "private")


def test_ensure_account_is_a_no_op_for_a_person_already_in_the_organisation(
    conn: Connection,
) -> None:
    """Branch three (same organisation): idempotent — no send, no move, no re-privatising."""
    org = _org(conn)
    email = unique_email("ensure-same")
    sub = fresh_sub()
    ops_enrol(conn, user_id=sub, org_id=org.org_id, email=email, display_name="Kept Name")
    shared = make_task(conn, owner_user_id=sub, org_id=org.org_id, visibility="org")
    with cognito() as (client, stubber):
        expect_lookup(stubber, email=email, sub=sub)
        enrolment = commands.ensure_account_enrolled(
            conn, client, pool_id=POOL_ID, email=email, display_name="Other Name", org=org
        )
        stubber.assert_no_pending_responses()
    assert (enrolment.user_id, enrolment.created, enrolment.invitation_sent) == (sub, False, False)
    assert (enrolment.tasks_moved, enrolment.projects_moved) == (0, 0)
    row = _row(conn, sub)
    assert (row["org_id"], row["display_name"], row["invited_at"]) == (
        org.org_id,
        "Kept Name",
        None,
    )
    # A row the person deliberately shared stays shared: nothing moved.
    assert _task_row(conn, shared)[:2] == (org.org_id, "org")


def test_ensure_account_refuses_a_person_enrolled_elsewhere_and_names_the_organisation(
    conn: Connection,
) -> None:
    """Branch three (another organisation): refuse, name where they are, write nothing."""
    first = _org(conn, "First")
    second = _org(conn, "Second")
    email = unique_email("ensure-elsewhere")
    sub = fresh_sub()
    ops_enrol(conn, user_id=sub, org_id=first.org_id, email=email)
    with cognito() as (client, stubber):
        expect_lookup(stubber, email=email, sub=sub)
        with pytest.raises(EnrolledElsewhere) as refusal:
            commands.ensure_account_enrolled(
                conn, client, pool_id=POOL_ID, email=email, display_name="X", org=second
            )
        stubber.assert_no_pending_responses()
    assert (refusal.value.sub, refusal.value.org_id, refusal.value.org_name) == (
        sub,
        first.org_id,
        first.name,
    )
    assert first.name in str(refusal.value)
    assert isinstance(refusal.value, OpsError)
    assert _row(conn, sub)["org_id"] == first.org_id


def test_ensure_account_retry_after_a_database_failure_enrols_without_a_second_send(
    conn: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Contract § Terms: "a retry after Cognito created, database write failed lands on branch two".

    First call: ``AdminCreateUser`` succeeds, then the row move fails and the
    transaction rolls back — the account is real, the database knows nothing.
    Second call: the lookup finds the account, and the person is enrolled with
    **no** second ``AdminCreateUser`` (the queue holds only the lookup).
    """
    org = _org(conn)
    email = unique_email("ensure-retry")
    sub = fresh_sub()

    def failing_stamp(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("injected database failure after the Cognito create")

    with cognito() as (client, stubber):
        expect_lookup(stubber, email=email, sub=None)
        expect_create(stubber, email=email, sub=sub)
        with monkeypatch.context() as patched:
            patched.setattr(commands, "_stamp_owned_rows", failing_stamp)
            with conn.begin_nested() as savepoint:
                with pytest.raises(RuntimeError, match="injected"):
                    commands.ensure_account_enrolled(
                        conn, client, pool_id=POOL_ID, email=email, display_name="R", org=org
                    )
                savepoint.rollback()
        stubber.assert_no_pending_responses()
        assert _row(conn, sub) is None

        expect_lookup(stubber, email=email, sub=sub)
        retried = commands.ensure_account_enrolled(
            conn, client, pool_id=POOL_ID, email=email, display_name="R", org=org
        )
        stubber.assert_no_pending_responses()

    assert (retried.user_id, retried.created, retried.invitation_sent) == (sub, True, False)
    assert _row(conn, sub)["org_id"] == org.org_id


# --- task 065: resend invitation (B4) -----------------------------------------


def test_resend_refuses_inside_the_hour_and_says_when_to_retry(conn: Connection) -> None:
    """The queue is empty: a refusal that came after the send would raise on the lookup."""
    sub = fresh_sub()
    email = unique_email("resend-soon")
    ops_enrol(conn, user_id=sub, org_id=_org(conn).org_id, email=email)
    moment = now()
    sent = moment - timedelta(minutes=30)
    _set_flags(conn, sub, invited_at=sent)
    with cognito() as (client, stubber):
        with pytest.raises(ResendTooSoon) as refusal:
            commands.resend_invitation(conn, client, pool_id=POOL_ID, sub=sub, now=moment)
        stubber.assert_no_pending_responses()
    assert refusal.value.retry_after == sent + timedelta(hours=1)
    assert isinstance(refusal.value, OpsError)
    assert _row(conn, sub)["invited_at"] == sent


@pytest.mark.parametrize("hours_ago", [None, 2])
def test_resend_after_the_hour_sends_with_message_action_resend_and_stamps_invited_at(
    conn: Connection, hours_ago: int | None
) -> None:
    """``support.expect_resend`` pins ``MessageAction=RESEND`` on the wire.

    ``None`` is a person never invited through this path (``user create`` from
    the CLI stamps nothing); two hours is a cooldown that has lapsed.
    """
    sub = fresh_sub()
    email = unique_email("resend-ok")
    ops_enrol(conn, user_id=sub, org_id=_org(conn).org_id, email=email)
    moment = now()
    if hours_ago is not None:
        _set_flags(conn, sub, invited_at=moment - timedelta(hours=hours_ago))
    with cognito() as (client, stubber):
        expect_sub_lookup(stubber, sub=sub, status="FORCE_CHANGE_PASSWORD")
        expect_resend(stubber, username=sub)
        resend = commands.resend_invitation(conn, client, pool_id=POOL_ID, sub=sub, now=moment)
        stubber.assert_no_pending_responses()
    assert (resend.user_id, resend.email, resend.sent_at) == (sub, email, moment)
    assert email in resend.summary()
    assert _row(conn, sub)["invited_at"] == moment


def test_resend_refuses_a_confirmed_account(conn: Connection) -> None:
    """Cognito cannot resend to an account past its first sign-in; nothing is sent or stamped."""
    sub = fresh_sub()
    ops_enrol(conn, user_id=sub, org_id=_org(conn).org_id, email=unique_email("resend-done"))
    with cognito() as (client, stubber):
        expect_sub_lookup(stubber, sub=sub, status="CONFIRMED")
        with pytest.raises(OpsError, match="CONFIRMED"):
            commands.resend_invitation(conn, client, pool_id=POOL_ID, sub=sub, now=now())
        stubber.assert_no_pending_responses()
    assert _row(conn, sub)["invited_at"] is None


# --- task 065: move, ops role, quotas, domains, the action record -------------


def test_move_user_re_enrols_a_stored_person_elsewhere_and_privatises_their_rows(
    conn: Connection,
) -> None:
    first = _org(conn, "First")
    second = _org(conn, "Second")
    sub = fresh_sub()
    email = unique_email("mover")
    ops_enrol(conn, user_id=sub, org_id=first.org_id, email=email, display_name="Mover")
    task_id = make_task(conn, owner_user_id=sub, org_id=first.org_id, visibility="org")

    moved = commands.move_user(conn, sub=sub, org=second)

    assert (moved.user_id, moved.email, moved.org, moved.created) == (sub, email, second, False)
    assert moved.tasks_moved == 1
    row = _row(conn, sub)
    assert (row["org_id"], row["email"], row["display_name"]) == (second.org_id, email, "Mover")
    assert _task_row(conn, task_id)[:2] == (second.org_id, "private")


def test_move_user_refuses_an_unknown_subject(conn: Connection) -> None:
    with pytest.raises(OpsError, match="no user"):
        commands.move_user(conn, sub=fresh_sub(), org=_org(conn))


def test_ops_grant_and_revoke_write_the_flag_and_carry_an_is_ops_trace(
    conn: Connection,
) -> None:
    """Contract B1: mirrors ``admin grant``/``revoke``, trace included, logging nothing."""
    org = _org(conn)
    sub = fresh_sub()
    email = unique_email("ops-role")
    ops_enrol(conn, user_id=sub, org_id=org.org_id, email=email)

    with capture_logs() as logs:
        granted = commands.set_ops(conn, email=email, grant=True)
        assert (_row(conn, sub)["is_ops"], _row(conn, sub)["is_admin"]) == (True, False)
        revoked = commands.set_ops(conn, sub=sub, grant=False)

    assert [line["event"] for line in logs] == []
    assert [(c.subject, c.direction, c.flag) for c in granted.admin_changes()] == [
        (sub, "grant", "is_ops")
    ]
    assert [(c.subject, c.direction, c.flag) for c in revoked.admin_changes()] == [
        (sub, "revoke", "is_ops")
    ]
    assert _row(conn, sub)["is_ops"] is False


def test_ops_grant_refuses_a_subject_in_no_organisation(conn: Connection) -> None:
    sub = fresh_sub()
    email = unique_email("ops-orphan")
    ops_enrol(conn, user_id=sub, org_id=None, email=email)
    with pytest.raises(OpsError, match="no organisation"):
        commands.set_ops(conn, email=email, grant=True)
    with pytest.raises(OpsError, match="no organisation"):
        commands.set_ops(conn, sub=sub, grant=True)
    assert _row(conn, sub)["is_ops"] is False


def test_ops_grant_and_revoke_refuse_when_nothing_would_change(conn: Connection) -> None:
    org = _org(conn)
    sub = fresh_sub()
    email = unique_email("ops-twice")
    ops_enrol(conn, user_id=sub, org_id=org.org_id, email=email)
    with pytest.raises(OpsError, match="does not hold the ops role"):
        commands.set_ops(conn, email=email, grant=False)
    _set_flags(conn, sub, is_ops=True)
    with pytest.raises(OpsError, match="already holds the ops role"):
        commands.set_ops(conn, email=email, grant=True)
    with pytest.raises(OpsError, match="no user with the address"):
        commands.set_ops(conn, email=unique_email("nobody"), grant=True)


def test_ops_revoke_still_reaches_a_subject_in_no_organisation(conn: Connection) -> None:
    """Taking the role away is never the blocked direction (as for ``admin revoke``)."""
    sub = fresh_sub()
    ops_enrol(conn, user_id=sub, org_id=None, email=None)
    _set_flags(conn, sub, is_ops=True)
    revoked = commands.set_ops(conn, sub=sub, grant=False)
    assert revoked.direction == "revoke"
    assert _row(conn, sub)["is_ops"] is False


def test_de_enrol_clears_the_ops_role_and_traces_it_with_the_flag(conn: Connection) -> None:
    """Contract B1: de-enrol clears both flags; each cleared flag is one trace line."""
    org = _org(conn)
    both, ops_only = fresh_sub(), fresh_sub()
    ops_enrol(conn, user_id=both, org_id=org.org_id, email=unique_email("both"), is_admin=True)
    _set_flags(conn, both, is_ops=True)
    # Holds the ops role with no organisation: still something to clear.
    ops_enrol(conn, user_id=ops_only, org_id=None, email=unique_email("ops-only"))
    _set_flags(conn, ops_only, is_ops=True)

    both_left = commands.de_enrol_user(conn, sub=both)
    ops_left = commands.de_enrol_user(conn, sub=ops_only)

    assert (both_left.admin_revoked, both_left.ops_revoked) == (True, True)
    assert [(c.subject, c.direction, c.flag) for c in both_left.admin_changes()] == [
        (both, "revoke", "is_admin"),
        (both, "revoke", "is_ops"),
    ]
    assert "support role revoked" in both_left.summary()
    assert "ops role revoked" in both_left.summary()
    assert (ops_left.admin_revoked, ops_left.ops_revoked) == (False, True)
    assert [(c.flag) for c in ops_left.admin_changes()] == ["is_ops"]
    for sub in (both, ops_only):
        row = _row(conn, sub)
        assert (row["org_id"], row["is_admin"], row["is_ops"]) == (None, False, False)
    with pytest.raises(OpsError, match="nothing to do"):
        commands.de_enrol_user(conn, sub=ops_only)


def test_offboard_de_enrols_a_person_who_only_holds_the_ops_role(conn: Connection) -> None:
    """``offboard`` used to skip de-enrol for a row with no organisation; the ops role counts."""
    sub = fresh_sub()
    ops_enrol(conn, user_id=sub, org_id=None, email=unique_email("ops-out"))
    _set_flags(conn, sub, is_ops=True)
    with cognito() as (client, stubber):
        _expect_lookup_by_sub(stubber, sub=sub)
        _expect_lock_out(stubber, sub=sub)
        result = commands.offboard_user(conn, client, pool_id=POOL_ID, sub=sub)
        stubber.assert_no_pending_responses()
    assert result.de_enrolment is not None
    assert result.de_enrolment.ops_revoked is True
    assert "ops role revoked" in result.summary()
    assert [(c.subject, c.direction, c.flag) for c in result.admin_changes()] == [
        (sub, "revoke", "is_ops")
    ]
    assert _row(conn, sub)["is_ops"] is False


def test_set_quota_writes_both_overrides_on_a_person_and_none_clears_them(
    conn: Connection,
) -> None:
    sub = fresh_sub()
    ops_enrol(conn, user_id=sub, org_id=_org(conn).org_id, email=unique_email("quota"))

    first = commands.set_quota(conn, user_id=sub, task_quota_per_year=100, runs_per_user=0)
    row = _row(conn, sub)
    assert (row["task_quota_per_year"], row["runs_per_user"]) == (100, 0)
    assert first.summary() == (
        f"quota for {sub}: tasks per year inherit → 100, simultaneous tasks inherit → 0"
    )

    cleared = commands.set_quota(conn, user_id=sub, task_quota_per_year=None, runs_per_user=None)
    row = _row(conn, sub)
    assert (row["task_quota_per_year"], row["runs_per_user"]) == (None, None)
    assert "tasks per year 100 → inherit, simultaneous tasks 0 → inherit" in cleared.summary()


def test_set_quota_writes_both_overrides_on_an_organisation(conn: Connection) -> None:
    org = _org(conn)
    change = commands.set_quota(conn, org_id=org.org_id, task_quota_per_year=20, runs_per_user=5)
    stored = conn.execute(
        select(organisation.c.task_quota_per_year, organisation.c.runs_per_user).where(
            organisation.c.org_id == org.org_id
        )
    ).one()
    assert tuple(stored) == (20, 5)
    assert (change.who, change.task_quota_before, change.runs_before) == (
        str(org.org_id),
        None,
        None,
    )
    commands.set_quota(conn, org_id=org.org_id, task_quota_per_year=None, runs_per_user=5)
    assert conn.execute(
        select(organisation.c.task_quota_per_year).where(organisation.c.org_id == org.org_id)
    ).scalar_one() is None


def test_set_quota_refuses_a_negative_value_a_missing_row_and_a_bad_selector(
    conn: Connection,
) -> None:
    sub = fresh_sub()
    ops_enrol(conn, user_id=sub, org_id=None, email=unique_email("quota-bad"))
    with pytest.raises(OpsError, match="negative"):
        commands.set_quota(conn, user_id=sub, task_quota_per_year=-1, runs_per_user=None)
    with pytest.raises(OpsError, match="negative"):
        commands.set_quota(conn, user_id=sub, task_quota_per_year=None, runs_per_user=-3)
    assert _row(conn, sub)["task_quota_per_year"] is None
    with pytest.raises(OpsError, match="no user"):
        commands.set_quota(conn, user_id=fresh_sub(), task_quota_per_year=1, runs_per_user=1)
    with pytest.raises(OpsError, match="no organisation"):
        commands.set_quota(conn, org_id=uuid.uuid4(), task_quota_per_year=1, runs_per_user=1)
    with pytest.raises(OpsError, match="exactly one"):
        commands.set_quota(conn, task_quota_per_year=1, runs_per_user=1)
    with pytest.raises(OpsError, match="exactly one"):
        commands.set_quota(
            conn, user_id=sub, org_id=uuid.uuid4(), task_quota_per_year=1, runs_per_user=1
        )


def _domain(label: str = "Team") -> str:
    """A suite-unique domain, mixed-case on purpose (the table stores lower-case)."""
    return f"{label}-{uuid.uuid4()}.Example.Test"


def test_domain_add_lower_cases_and_remove_deletes_whatever_the_case_typed(
    conn: Connection,
) -> None:
    org = _org(conn)
    typed = _domain()
    added = commands.add_domain(conn, domain=typed, org=org)
    assert (added.domain, added.added, added.org) == (typed.lower(), True, org)
    assert typed.lower() in added.summary()
    assert org.name in added.summary()
    stored = conn.execute(
        select(organisation_domain.c.org_id).where(organisation_domain.c.domain == typed.lower())
    ).scalar_one()
    assert stored == org.org_id

    removed = commands.remove_domain(conn, domain=typed.upper())
    assert (removed.domain, removed.added, removed.org) == (typed.lower(), False, None)
    assert "removed domain" in removed.summary()
    assert (
        conn.execute(
            select(organisation_domain.c.domain).where(
                organisation_domain.c.domain == typed.lower()
            )
        ).scalar_one_or_none()
        is None
    )
    with pytest.raises(OpsError, match="no organisation domain"):
        commands.remove_domain(conn, domain=typed)


def test_domain_add_refuses_a_duplicate_even_for_another_organisation(conn: Connection) -> None:
    first, second = _org(conn, "First"), _org(conn, "Second")
    typed = _domain()
    commands.add_domain(conn, domain=typed, org=first)
    with pytest.raises(OpsError, match="already belongs"):
        commands.add_domain(conn, domain=typed.upper(), org=second)
    with pytest.raises(OpsError, match="already belongs"):
        commands.add_domain(conn, domain=typed, org=first)


@pytest.mark.parametrize("bad", ["", " ", "nes ta.org.uk", "a@example.test", "@example.test"])
def test_domain_commands_refuse_an_empty_blank_or_address_shaped_value(
    conn: Connection, bad: str
) -> None:
    org = _org(conn)
    with pytest.raises(OpsError, match="domain must be"):
        commands.add_domain(conn, domain=bad, org=org)
    with pytest.raises(OpsError, match="domain must be"):
        commands.remove_domain(conn, domain=bad)


def test_record_action_inserts_one_row_and_returns_its_id(conn: Connection) -> None:
    actor = fresh_sub("actor")
    action_id = commands.record_action(
        conn, actor=actor, action="quota.set", target="someone", outcome="ok"
    )
    rows = conn.execute(select(ops_action).where(ops_action.c.actor_user_id == actor)).mappings()
    (stored,) = rows.all()
    assert (stored["action_id"], stored["action"], stored["target"], stored["outcome"]) == (
        action_id,
        "quota.set",
        "someone",
        "ok",
    )
    assert stored["at"] is not None
    # `target` is optional: an organisation-wide action has none.
    second = commands.record_action(conn, actor=actor, action="org.list", target=None, outcome="ok")
    assert second != action_id
    assert (
        conn.execute(
            select(ops_action.c.target).where(ops_action.c.action_id == second)
        ).scalar_one()
        is None
    )
