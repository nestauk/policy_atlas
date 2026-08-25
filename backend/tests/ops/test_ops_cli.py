"""The entrypoint itself: argument wiring, the transaction, and the refusal path.

The command functions are covered case by case in ``test_ops_commands.py``.
What is left is the part only ``main`` can be wrong about — that the environment
check runs **before** the command and inside the same transaction, that a
refusal writes nothing and exits non-zero, and that the success line is printed
only after the commit.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.core.schema import app_user, organisation
from policy_atlas.ops.cli import EXIT_REFUSED, main
from tests.api.org_support import make_org, ops_enrol, seeded, unique_email
from tests.ops.support import (
    ACCOUNT_ID,
    POOL_ID,
    FakeSts,
    cognito,
    expect_environment,
    expect_lookup,
    fresh_sub,
)


def _argv(*command: str) -> list[str]:
    return [
        "--env",
        "staging",
        "--expected-account",
        ACCOUNT_ID,
        "--user-pool-id",
        POOL_ID,
        *command,
    ]


def test_cli_creates_an_organisation_end_to_end(engine: Engine) -> None:
    """The whole path: parse, verify, act, commit, then print."""
    sub = fresh_sub("cognito")
    with seeded(engine) as conn:
        ops_enrol(
            conn, user_id=sub, org_id=make_org(conn), email=unique_email("seed")
        )
    name = f"CLI Org {uuid.uuid4()}"
    lines: list[str] = []
    with cognito() as (client, stubber):
        expect_environment(stubber, known_subs=[sub], sampled=[sub])
        status = main(
            _argv("org", "create", "--name", name),
            engine=engine,
            cognito=client,
            sts=FakeSts(),
            write=lines.append,
        )
    assert status == 0
    assert any(name in line for line in lines)
    with seeded(engine) as conn:
        assert (
            conn.execute(
                select(organisation.c.org_id).where(organisation.c.name == name)
            ).scalar_one_or_none()
            is not None
        )


def test_cli_enrols_through_the_real_entrypoint(engine: Engine) -> None:
    """`user enrol` wired end to end, including the row move it reports."""
    seed_sub = fresh_sub("cognito")
    subject = fresh_sub("cognito")
    email = unique_email("cli")
    org_name = f"CLI Enrol {uuid.uuid4()}"
    with seeded(engine) as conn:
        org_id = make_org(conn, name=org_name)
        ops_enrol(conn, user_id=seed_sub, org_id=org_id, email=unique_email("seed"))
        resolved = conn.execute(
            select(organisation.c.name).where(organisation.c.org_id == org_id)
        ).scalar_one()

    lines: list[str] = []
    with cognito() as (client, stubber):
        expect_environment(stubber, known_subs=[seed_sub], sampled=[seed_sub])
        expect_lookup(stubber, email=email, sub=subject)
        status = main(
            _argv(
                "user",
                "enrol",
                "--email",
                email,
                "--display-name",
                "CLI Person",
                "--org",
                resolved,
            ),
            engine=engine,
            cognito=client,
            sts=FakeSts(),
            write=lines.append,
        )
        stubber.assert_no_pending_responses()

    assert status == 0
    assert any("moved 0 project(s), 0 portfolio(s), all private" in line for line in lines)
    with seeded(engine) as conn:
        assert (
            conn.execute(
                select(app_user.c.org_id).where(app_user.c.user_id == subject)
            ).scalar_one()
            == org_id
        )


def test_cli_refuses_an_environment_mismatch_and_writes_nothing(engine: Engine) -> None:
    """Rubric 26 through the real entrypoint: the guard runs before the command.

    The stub queue is loaded with **nothing**. If the check did not refuse on the
    account first, the very next call would raise ``UnStubbedResponseError``
    rather than the clean refusal asserted here — so this also pins the ordering.
    """
    name = f"Never Created {uuid.uuid4()}"
    lines: list[str] = []
    with cognito() as (client, _):
        status = main(
            _argv("org", "create", "--name", name),
            engine=engine,
            cognito=client,
            sts=FakeSts(account="999988887777"),
            write=lines.append,
        )
    assert status == EXIT_REFUSED
    assert lines == []
    with seeded(engine) as conn:
        assert (
            conn.execute(
                select(organisation.c.org_id).where(organisation.c.name == name)
            ).scalar_one_or_none()
            is None
        )


def test_cli_refuses_without_a_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with cognito() as (client, _):
        status = main(
            ["--env", "staging", "--expected-account", ACCOUNT_ID, "--user-pool-id", POOL_ID,
             "org", "create", "--name", "X"],
            cognito=client,
            sts=FakeSts(),
            write=lambda _line: None,
        )
    assert status == EXIT_REFUSED
