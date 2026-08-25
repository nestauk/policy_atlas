"""The environment guard — rubric 26, the highest-consequence check in the slice.

The failure being defended against is not a bug, it is a workflow: a production
SSM tunnel is still open on ``localhost:15432``, the operator switches their AWS
profile to staging, and every subsequent command writes staging identities into
the production database with no error from anything.

The three legs are asserted separately because they fail for different reasons
and an operator needs to be told which one refused. The database leg's two
outcomes — a proved pairing and a proved *mismatch* — are the ones that matter;
the third, an empty ``app_user`` table with nothing to prove against, is pinned
here as confirmation-only so the limit is recorded in the suite rather than only
in prose.
"""

from __future__ import annotations

import pytest
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import app_user
from policy_atlas.ops.environment import Target, resolve_target, verify_environment
from policy_atlas.ops.errors import OpsError
from tests.api.org_support import make_org, ops_enrol, unique_email
from tests.ops.support import ACCOUNT_ID, POOL_ID, FakeSts, cognito, expect_environment, fresh_sub


def _target(env: str = "staging") -> Target:
    return Target(
        env=env,
        account_id=ACCOUNT_ID,
        user_pool_id=POOL_ID,
        database="localhost:15432/policy_atlas_db",
    )


def _refuse(_: Target) -> bool:
    return False


def _accept(_: Target) -> bool:
    return True


def _seed_subject(conn: Connection) -> str:
    """Put one enrolled subject in the connected database for the leg-3 sample."""
    org_id = make_org(conn)
    sub = fresh_sub("cognito")
    ops_enrol(conn, user_id=sub, org_id=org_id, email=unique_email("member"))
    return sub


def test_resolve_target_requires_the_operator_supplied_account_and_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Neither identifier is committed: the repository is public (task 026 decision 4)."""
    monkeypatch.delenv("PA_OPS_ACCOUNT_STAGING", raising=False)
    monkeypatch.delenv("PA_OPS_USER_POOL_STAGING", raising=False)
    with pytest.raises(OpsError, match="PA_OPS_ACCOUNT_STAGING"):
        resolve_target(
            env="staging",
            expected_account=None,
            user_pool_id=POOL_ID,
            database_url="postgresql+psycopg://u:p@localhost:15432/db",
        )
    with pytest.raises(OpsError, match="PA_OPS_USER_POOL_STAGING"):
        resolve_target(
            env="staging",
            expected_account=ACCOUNT_ID,
            user_pool_id=None,
            database_url="postgresql+psycopg://u:p@localhost:15432/db",
        )


def test_resolve_target_renders_the_database_without_its_password() -> None:
    """The resolved triple is printed and echoed into scrollback."""
    target = resolve_target(
        env="prod",
        expected_account=ACCOUNT_ID,
        user_pool_id=POOL_ID,
        database_url="postgresql+psycopg://dbadmin:hunter2@localhost:15432/policy_atlas_db",
    )
    assert target.database == "localhost:15432/policy_atlas_db"
    assert "hunter2" not in target.database


def test_resolve_target_refuses_an_unknown_environment() -> None:
    with pytest.raises(OpsError, match="unknown environment"):
        resolve_target(
            env="qa",
            expected_account=ACCOUNT_ID,
            user_pool_id=POOL_ID,
            database_url="postgresql+psycopg://u:p@localhost:5432/db",
        )


def test_environment_refuses_when_the_credentials_are_another_account(
    conn: Connection,
) -> None:
    """Leg 1, and the cheapest: a wrong profile costs one API call and no database read."""
    with cognito() as (client, _), pytest.raises(OpsError, match="expects AWS account"):
        verify_environment(
            _target(),
            conn=conn,
            cognito=client,
            sts=FakeSts(account="999988887777"),
            confirm=_accept,
        )


def test_environment_refuses_a_pool_that_is_not_in_the_account(conn: Connection) -> None:
    """Leg 2: the configured pool must exist where leg 1 says the operator is."""
    with cognito() as (client, stubber):
        stubber.add_client_error(
            "list_users", service_error_code="ResourceNotFoundException", http_status_code=400
        )
        with pytest.raises(OpsError, match="not reachable"):
            verify_environment(
                _target(), conn=conn, cognito=client, sts=FakeSts(), confirm=_accept
            )


def test_environment_passes_when_the_pool_knows_a_subject_in_this_database(
    conn: Connection,
) -> None:
    """Leg 3, the pairing proved: ``app_user.user_id`` *is* the Cognito subject."""
    sub = _seed_subject(conn)
    with cognito() as (client, stubber):
        expect_environment(stubber, known_subs=[sub], sampled=[sub])
        verification = verify_environment(
            _target(), conn=conn, cognito=client, sts=FakeSts(), confirm=_refuse
        )
        stubber.assert_no_pending_responses()
    assert verification.database_leg == "verified"
    assert verification.caller_arn.startswith("arn:aws:sts::")


def test_environment_refuses_when_the_pool_does_not_know_this_databases_subjects(
    conn: Connection,
) -> None:
    """Leg 3, the mismatch — the prod-tunnel/staging-credentials case itself.

    ``confirm`` is wired to accept, and the command is refused anyway: this
    outcome is a hard refusal that ``--yes`` cannot lift, because an operator
    who is wrong about which estate they are in is exactly the operator who
    would pass ``--yes``.
    """
    subs = [_seed_subject(conn) for _ in range(3)]
    with cognito() as (client, stubber):
        expect_environment(stubber, known_subs=[], sampled=list(reversed(subs)))
        with pytest.raises(OpsError, match="not the same environment"):
            verify_environment(
                _target(), conn=conn, cognito=client, sts=FakeSts(), confirm=_accept
            )


def test_environment_falls_back_to_confirmation_when_there_is_nothing_to_sample(
    conn: Connection,
) -> None:
    """The recorded limit: with no accounts in the database, leg 3 can prove nothing.

    Its blast radius is also nil — a database with no ``app_user`` rows is one
    nobody has ever signed in to. Both halves are pinned: assent proceeds and is
    reported as ``unproven``, refusal stops the command.
    """
    # The test database is shared across the suite, so the empty-table state
    # has to be made rather than assumed. The `conn` fixture rolls it back, and
    # nothing else needs clearing: the tenancy foreign keys on `project` and
    # `portfolio` point at `organisation`, not at `app_user`.
    conn.execute(app_user.delete())
    with cognito() as (client, stubber):
        expect_environment(stubber)
        verification = verify_environment(
            _target(), conn=conn, cognito=client, sts=FakeSts(), confirm=_accept
        )
    assert verification.database_leg == "unproven"

    with cognito() as (client, stubber):
        expect_environment(stubber)
        with pytest.raises(OpsError, match="refused at the environment confirmation"):
            verify_environment(
                _target(), conn=conn, cognito=client, sts=FakeSts(), confirm=_refuse
            )
