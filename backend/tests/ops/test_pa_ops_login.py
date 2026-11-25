"""The ``pa_ops`` login has only task 065's intended database privileges."""

from __future__ import annotations

import uuid
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

import pytest
from psycopg import sql
from psycopg.errors import InsufficientPrivilege
from sqlalchemy import create_engine, select, text, update
from sqlalchemy.engine import URL, Connection, Engine
from sqlalchemy.exc import ProgrammingError

from policy_atlas.core.schema import app_user, ops_action, organisation, waitlist_entry
from policy_atlas.ops import commands
from tests.api.org_support import make_org, make_project, make_task, make_user, seeded
from tests.ops.support import (
    POOL_ID,
    cognito,
    expect_create,
    expect_enabled,
    expect_lock_out,
    expect_lookup,
    expect_sub_lookup,
)

_PASSWORD = "p@ss:w/rd#1"


@pytest.fixture(scope="module")
def pa_ops_engine(engine: Engine) -> Generator[Engine, None, None]:
    """Yield a local second engine authenticated as the constrained ops role."""
    master_url = engine.url
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        driver_connection = conn.connection.driver_connection
        assert driver_connection is not None
        driver_connection.execute(
            sql.SQL("ALTER ROLE pa_ops LOGIN PASSWORD {}").format(sql.Literal(_PASSWORD))
        )
    role_url = URL.create(
        drivername=master_url.drivername,
        username="pa_ops",
        password=_PASSWORD,
        host=master_url.host,
        port=master_url.port,
        database=master_url.database,
    )
    role_engine = create_engine(role_url)
    try:
        yield role_engine
    finally:
        role_engine.dispose()
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text("ALTER ROLE pa_ops NOLOGIN"))


@pytest.fixture
def seeded_user(engine: Engine) -> str:
    """Commit an unprivileged row visible to the second login and return its subject."""
    return _seed_user(engine, is_admin=False)


@pytest.fixture
def seeded_admin_user(engine: Engine) -> str:
    """Commit an admin row that the constrained login may clear."""
    return _seed_user(engine, is_admin=True)


def _seed_user(engine: Engine, *, is_admin: bool) -> str:
    """Commit one account row with the requested existing admin state."""
    user_id = f"pa-ops-{uuid.uuid4()}"
    with seeded(engine) as conn:
        conn.execute(
            app_user.insert().values(
                user_id=user_id,
                org_id=None,
                display_name="Ops test person",
                email=f"{user_id}@example.test",
                is_admin=is_admin,
                is_ops=False,
                created_at=datetime.now(UTC),
            )
        )
    return user_id


def _assert_refused(statement: str, pa_ops_engine: Engine) -> None:
    """Assert that PostgreSQL denies the statement to the constrained login."""
    with pa_ops_engine.connect() as conn, pytest.raises(ProgrammingError) as error:
        conn.execute(text(statement))
    original = error.value.orig
    assert isinstance(original, InsufficientPrivilege)
    assert original.sqlstate == "42501"


@pytest.mark.parametrize(
    "statement",
    [
        "DELETE FROM app_user",
        "DELETE FROM task",
        "SELECT 1 FROM capability_run",
        "SELECT 1 FROM alembic_version",
        "UPDATE task SET name = name",
        "CREATE TABLE pa_ops_probe (x int)",
        "INSERT INTO capability_run DEFAULT VALUES",
        # The ops service reads these two tables and stamps one; it inserts neither.
        "INSERT INTO organisation_domain (domain, org_id, created_at) "
        "VALUES ('probe.test', gen_random_uuid(), now())",
        "INSERT INTO waitlist_entry (entry_id, email, name, role_or_reason, created_at) "
        "VALUES (gen_random_uuid(), 'probe@example.test', 'Probe', 'probe', now())",
    ],
)
def test_pa_ops_refuses_ungranted_statements(pa_ops_engine: Engine, statement: str) -> None:
    """The ops login cannot read or write outside its precise grant list."""
    _assert_refused(statement, pa_ops_engine)


def test_pa_ops_cannot_grant_admin_or_ops(pa_ops_engine: Engine, seeded_user: str) -> None:
    """The trigger rejects each privilege escalation with SQLSTATE 42501.

    By an UPDATE, and by an INSERT of a row that already carries the flag
    (review stack, 2026-11-17): the role may insert rows, never privileged ones.
    """
    for column in ("is_admin", "is_ops"):
        with pa_ops_engine.connect() as conn, pytest.raises(ProgrammingError) as error:
            conn.execute(
                text(f"UPDATE app_user SET {column} = true WHERE user_id = :user_id"),
                {"user_id": seeded_user},
            )
        original = error.value.orig
        assert isinstance(original, InsufficientPrivilege)
        assert original.sqlstate == "42501"
        with pa_ops_engine.connect() as conn, pytest.raises(ProgrammingError) as error:
            conn.execute(
                text(
                    f"INSERT INTO app_user (user_id, display_name, created_at, {column}) "
                    "VALUES (:user_id, 'Probe', now(), true)"
                ),
                {"user_id": f"pa-ops-insert-{uuid.uuid4()}"},
            )
        assert error.value.orig.sqlstate == "42501"  # type: ignore[union-attr]


def test_pa_ops_deletes_only_a_rejected_request(pa_ops_engine: Engine, engine: Engine) -> None:
    """The trigger refuses the ops login a delete of a request still waiting (42501)."""
    waiting, rejected = uuid.uuid4(), uuid.uuid4()
    with seeded(engine) as conn:
        for entry_id, rejected_at in ((waiting, None), (rejected, datetime.now(UTC))):
            conn.execute(waitlist_entry.insert().values(
                entry_id=entry_id, email=f"{entry_id}@example.test", name="Asker",
                role_or_reason="curious", created_at=datetime.now(UTC), rejected_at=rejected_at,
            ))
    _assert_refused(f"DELETE FROM waitlist_entry WHERE entry_id = '{waiting}'", pa_ops_engine)
    with _as_pa_ops(pa_ops_engine) as conn:
        deleted = conn.execute(
            text("DELETE FROM waitlist_entry WHERE entry_id = :id"), {"id": rejected}
        )
        assert deleted.rowcount == 1
    with engine.begin() as conn:
        conn.execute(
            waitlist_entry.delete().where(waitlist_entry.c.entry_id.in_((waiting, rejected)))
        )


def test_pa_ops_allows_the_current_positive_smoke(
    pa_ops_engine: Engine, seeded_admin_user: str
) -> None:
    """The role may clear a privilege, audit an action, and delete memberships."""
    with pa_ops_engine.begin() as conn:
        conn.execute(
            text("UPDATE app_user SET is_admin = false WHERE user_id = :user_id"),
            {"user_id": seeded_admin_user},
        )
        conn.execute(
            text(
                "INSERT INTO ops_action "
                "(action_id, at, actor_user_id, action, target, outcome) "
                "VALUES (:action_id, :at, 'operator', 'test', NULL, 'ok')"
            ),
            {"action_id": uuid.uuid4(), "at": datetime.now(UTC)},
        )
        conn.execute(text("DELETE FROM project_membership WHERE false"))


# --- the positive half (contract B13, plan P6) --------------------------------


@contextmanager
def _as_pa_ops(pa_ops_engine: Engine) -> Iterator[Connection]:
    """Yield one ``pa_ops`` transaction that is always rolled back.

    The seeded rows are committed through the master engine so the second
    login can see them; the command's own writes are discarded here, so the
    shared test database keeps nothing from these cases.
    """
    with pa_ops_engine.connect() as conn:
        transaction = conn.begin()
        try:
            yield conn
        finally:
            transaction.rollback()


def _org(engine: Engine) -> commands.Organisation:
    """Commit one organisation and return it as the command functions take it."""
    with seeded(engine) as conn:
        org_id = make_org(conn)
        name = conn.execute(
            select(organisation.c.name).where(organisation.c.org_id == org_id)
        ).scalar_one()
    return commands.Organisation(org_id=org_id, name=name)


def test_pa_ops_runs_every_ops_write_of_this_slice(
    pa_ops_engine: Engine, engine: Engine, seeded_admin_user: str
) -> None:
    """Each command function the ops routes call succeeds as the constrained login."""
    org = _org(engine)
    moment = datetime.now(UTC)
    email, sub = f"asker-{uuid.uuid4()}@example.test", f"pa-ops-new-{uuid.uuid4()}"
    with seeded(engine) as conn:
        mover = make_user(conn)
        other = make_user(conn)
        # A membership pairing the mover's task with someone else's project is
        # what `_sever_cross_owner_memberships` deletes on a move.
        foreign_project = make_project(conn, owner_user_id=other)
        make_task(conn, owner_user_id=mover, project_id=foreign_project)
        conn.execute(
            update(app_user).where(app_user.c.user_id == mover).values(email=email)
        )
        entry_id = uuid.uuid4()
        conn.execute(
            waitlist_entry.insert().values(
                entry_id=entry_id, email=email, name="Asker", organisation=None,
                role_or_reason="curious", created_at=moment,
            )
        )

    with _as_pa_ops(pa_ops_engine) as conn:
        assert commands.create_organisation(conn, name=f"pa-ops {uuid.uuid4()}").name

    with _as_pa_ops(pa_ops_engine) as conn, cognito() as (client, stubber):
        expect_lookup(stubber, email=email, sub=None)
        expect_create(stubber, email=email, sub=sub)
        enrolled = commands.ensure_account_enrolled(
            conn, client, pool_id=POOL_ID, email=email, display_name="Asker", org=org
        )
        assert enrolled.invitation_sent and enrolled.user_id == sub
        stubber.assert_no_pending_responses()

    with _as_pa_ops(pa_ops_engine) as conn:
        moved = commands.move_user(conn, sub=mover, org=org)
        assert moved.org == org and moved.memberships_severed == 1

    with _as_pa_ops(pa_ops_engine) as conn:
        assert commands.de_enrol_user(conn, sub=seeded_admin_user).admin_revoked

    with _as_pa_ops(pa_ops_engine) as conn, cognito() as (client, stubber):
        expect_sub_lookup(stubber, sub=seeded_admin_user)
        expect_lock_out(stubber, sub=seeded_admin_user)
        deactivated = commands.deactivate_user(conn, client, pool_id=POOL_ID, sub=seeded_admin_user)
        assert deactivated.admin_revoked is True
        stubber.assert_no_pending_responses()

    with _as_pa_ops(pa_ops_engine) as conn, cognito() as (client, stubber):
        expect_sub_lookup(stubber, sub=seeded_admin_user)
        expect_enabled(stubber, sub=seeded_admin_user, enabled=False)
        stubber.add_response(
            "admin_enable_user", {}, {"UserPoolId": POOL_ID, "Username": seeded_admin_user}
        )
        assert commands.reactivate_user(
            conn, client, pool_id=POOL_ID, sub=seeded_admin_user
        ).changed
        stubber.assert_no_pending_responses()

    with _as_pa_ops(pa_ops_engine) as conn:
        empty = commands.create_organisation(conn, name=f"pa-ops empty {uuid.uuid4()}")
        assert commands.delete_organisation(conn, org_id=empty.org_id).name == empty.name

    with _as_pa_ops(pa_ops_engine) as conn:
        person = commands.set_quota(conn, user_id=mover, task_quota_per_year=5, runs_per_user=0)
        organisation_change = commands.set_quota(
            conn, org_id=org.org_id, task_quota_per_year=None, runs_per_user=2
        )
        assert (person.task_quota_after, organisation_change.runs_after) == (5, 2)

    with _as_pa_ops(pa_ops_engine) as conn:
        made = commands.save_cohort(
            conn, cohort_id=None, name=f"pa-ops {uuid.uuid4()}", description=None,
            starts_on=None, ends_on=None, links=[],
        )
        commands.save_cohort(
            conn, cohort_id=made.cohort_id, name=made.name, description="renamed",
            starts_on=None, ends_on=None, links=["https://example.test"],
        )
        quota = commands.set_quota(
            conn, cohort_id=made.cohort_id, task_quota_per_year=9, runs_per_user=None
        )
        assert quota.task_quota_after == 9
        assert commands.add_to_cohort(conn, target=made, user_id=mover).changed
        assert commands.remove_from_cohort(conn, target=made, user_id=mover).changed
        assert commands.delete_cohort(conn, cohort_id=made.cohort_id) == made

    with _as_pa_ops(pa_ops_engine) as conn:
        commands.reject_request(conn, entry_id=entry_id, now=moment)
        commands.delete_request(conn, entry_id=entry_id)
        assert conn.execute(
            select(waitlist_entry.c.entry_id).where(waitlist_entry.c.entry_id == entry_id)
        ).one_or_none() is None

    with _as_pa_ops(pa_ops_engine) as conn:
        action_id = commands.record_action(
            conn, actor="operator", action="test", target=None, outcome="ok"
        )
        assert conn.execute(
            select(ops_action.c.outcome).where(ops_action.c.action_id == action_id)
        ).scalar_one() == "ok"

    with _as_pa_ops(pa_ops_engine) as conn, cognito() as (client, stubber):
        expect_lookup(stubber, email=email, sub=None)
        expect_create(stubber, email=email, sub=sub)
        approved = commands.approve_request(
            conn, client, pool_id=POOL_ID, entry_id=entry_id, org=org, now=moment
        )
        assert approved.enrolment.user_id == sub
        assert conn.execute(
            select(waitlist_entry.c.account_user_id)
            .where(waitlist_entry.c.entry_id == entry_id)
        ).scalar_one() == sub
        stubber.assert_no_pending_responses()


def test_pa_ops_cannot_grant_a_role_through_the_command_functions(
    pa_ops_engine: Engine, engine: Engine
) -> None:
    """`set_admin` and `set_ops` grants pass their interlocks and are refused by the trigger."""
    org = _org(engine)
    with seeded(engine) as conn:
        enrolled = make_user(conn, org_id=org.org_id)
    for grant in (commands.set_admin, commands.set_ops):
        with (
            _as_pa_ops(pa_ops_engine) as conn,
            pytest.raises(ProgrammingError) as error,
        ):
            grant(conn, grant=True, sub=enrolled)
        original = error.value.orig
        assert isinstance(original, InsufficientPrivilege)
        assert original.sqlstate == "42501"


#: Contract B13 (revision 3.1) as the review stack narrowed it: the ops login's
#: whole grant surface, read back from the catalogue. An extra grant on any
#: table, or a wider column list, fails here.
_EXPECTED_TABLE_GRANTS: dict[str, set[str]] = {
    "app_user": {"SELECT", "INSERT"},
    "organisation": {"SELECT", "INSERT", "DELETE"},
    "organisation_domain": {"SELECT"},
    "waitlist_entry": {"SELECT", "DELETE"},
    "ops_action": {"SELECT", "INSERT"},
    "task": {"SELECT"},
    "project": {"SELECT"},
    "project_membership": {"SELECT", "DELETE"},
    "cohort": {"SELECT", "INSERT", "DELETE"},
    "cohort_member": {"SELECT", "INSERT", "DELETE"},
    "invite_link": {"SELECT", "INSERT"},
    "invite_link_cohort": {"SELECT", "INSERT"},
}
_EXPECTED_COLUMN_UPDATES: dict[str, set[str]] = {
    "app_user": {
        "org_id", "email", "display_name", "is_admin", "is_ops", "invited_at",
        "task_quota_per_year", "runs_per_user", "deactivated_at",
    },
    "organisation": {"name", "task_quota_per_year", "runs_per_user"},
    "waitlist_entry": {"account_user_id", "account_created_at", "rejected_at", "invite_link_id"},
    "task": {"org_id", "visibility", "is_public"},
    "project": {"org_id", "visibility"},
    "cohort": {
        "name", "description", "starts_on", "ends_on", "links", "task_quota_per_year",
        "runs_per_user",
    },
    "invite_link": {"label", "max_uses", "expires_at", "revoked_at"},
}


def test_pa_ops_grants_are_exactly_the_contract_list(engine: Engine) -> None:
    """The catalogue agrees with B13: every table-level and column-level grant, no more."""
    with engine.connect() as conn:
        table_grants: dict[str, set[str]] = {}
        for table_name, privilege in conn.execute(
            text(
                "SELECT table_name, privilege_type FROM information_schema.role_table_grants "
                "WHERE grantee = 'pa_ops' AND table_schema = 'public'"
            )
        ):
            table_grants.setdefault(table_name, set()).add(privilege)
        column_updates: dict[str, set[str]] = {}
        for table_name, column_name in conn.execute(
            text(
                "SELECT table_name, column_name FROM information_schema.column_privileges "
                "WHERE grantee = 'pa_ops' AND table_schema = 'public' "
                "AND privilege_type = 'UPDATE'"
            )
        ):
            column_updates.setdefault(table_name, set()).add(column_name)
    # A column-level UPDATE grant shows in role_table_grants as UPDATE on the
    # table too; strip it so the table map states the table-wide grants only.
    table_only = {
        table: {p for p in privileges if p != "UPDATE" or table not in column_updates}
        for table, privileges in table_grants.items()
    }
    assert table_only == _EXPECTED_TABLE_GRANTS
    assert column_updates == _EXPECTED_COLUMN_UPDATES


def test_pa_ops_can_resend_an_invitation(pa_ops_engine: Engine, engine: Engine) -> None:
    """The resend path (a lock, a Cognito call, an invited_at write) runs as the ops login."""
    from datetime import timedelta

    from policy_atlas.ops import commands
    from tests.ops.support import POOL_ID, cognito, expect_resend, expect_sub_lookup

    sub = _seed_user(engine, is_admin=False)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE app_user SET invited_at = :at WHERE user_id = :sub"),
            {"at": datetime.now(UTC) - timedelta(hours=2), "sub": sub},
        )
    with cognito() as (client, stubber), pa_ops_engine.begin() as conn:
        expect_sub_lookup(stubber, sub=sub, status="FORCE_CHANGE_PASSWORD")
        expect_resend(stubber, username=sub)
        sent = commands.resend_invitation(
            conn, client, pool_id=POOL_ID, sub=sub, now=datetime.now(UTC)
        )
        assert sent.user_id == sub
        conn.rollback()
