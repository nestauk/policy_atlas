"""The entrypoint itself: argument wiring, the transaction, and the refusal path.

The command functions are covered case by case in ``test_ops_commands.py``.
What is left is the part only ``main`` can be wrong about — that the environment
check runs **before** the command and inside the same transaction, that a
refusal writes nothing and exits non-zero, that the success line is printed only
after the commit, and that the **audit line is too**.

The trace cases read the log off stdout rather than through
``structlog.testing.capture_logs``: ``main`` calls ``configure_logging`` (as
every entrypoint must), which reconfigures structlog and would discard a
capture installed around it. ``LOG_FORMAT=json`` plus ``capsys`` asserts against
what an operator's log shipper would actually receive.
"""

from __future__ import annotations

import inspect
import json
import uuid
from typing import Any

import pytest
from sqlalchemy import RootTransaction, select
from sqlalchemy.engine import Engine

from policy_atlas.core.schema import app_user, organisation
from policy_atlas.ops.cli import EXIT_REFUSED, _prompt, build_parser, main
from tests.api.org_support import make_org, ops_enrol, seeded, unique_email
from tests.ops.support import (
    ACCOUNT_ID,
    CALLER_ARN,
    POOL_ID,
    FakeSts,
    cognito,
    expect_environment,
    expect_lookup,
    fresh_sub,
)


def _argv(*command: str, globals_: tuple[str, ...] = ()) -> list[str]:
    return [
        "--env",
        "staging",
        "--expected-account",
        ACCOUNT_ID,
        "--user-pool-id",
        POOL_ID,
        *globals_,
        *command,
    ]


def _traces(output: str) -> list[dict[str, Any]]:
    """Every ``ops.admin_change`` line the run emitted, parsed off stdout."""
    lines: list[dict[str, Any]] = []
    for line in output.splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("event") == "ops.admin_change":
            lines.append(entry)
    return lines


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


def test_cli_refuses_a_database_url_that_carries_a_password(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The argv-secret vector the deleted make targets were killed for.

    A password on the command line is in the shell history and in the process
    table, and ``--database-url`` was the one flag still accepting one. The
    refusal names ``DATABASE_URL`` as the path for the credential — an
    environment variable is not on argv — and the password does not appear in
    what the operator is told.
    """
    with cognito() as (client, _):
        status = main(
            _argv(
                "org",
                "create",
                "--name",
                "X",
                globals_=("--database-url", "postgresql+psycopg://dbadmin:hunter2@h:15432/db"),
            ),
            cognito=client,
            sts=FakeSts(),
            write=lambda _line: None,
        )
    assert status == EXIT_REFUSED
    refusal = capsys.readouterr().err
    assert "DATABASE_URL" in refusal
    assert "hunter2" not in refusal


def test_cli_accepts_a_database_url_without_a_password(engine: Engine) -> None:
    """The flag still does its job: it is the credential, not the flag, that is refused."""
    sub = fresh_sub("cognito")
    with seeded(engine) as conn:
        ops_enrol(conn, user_id=sub, org_id=make_org(conn), email=unique_email("seed"))
    name = f"CLI Org {uuid.uuid4()}"
    with cognito() as (client, stubber):
        expect_environment(stubber, known_subs=[sub], sampled=[sub])
        status = main(
            _argv(
                "org",
                "create",
                "--name",
                name,
                globals_=("--database-url", "postgresql+psycopg://reader@localhost:15432/db"),
            ),
            engine=engine,
            cognito=client,
            sts=FakeSts(),
            write=lambda _line: None,
        )
    assert status == 0


def test_cli_lower_cases_an_address_before_it_reaches_cognito(engine: Engine) -> None:
    """``ListUsers``'s ``=`` is exact and case-sensitive; the pool is not.

    So ``user create --email Alice@x`` against an existing ``alice@x`` used to
    find nothing and go on to ask ``AdminCreateUser`` for a **second identity
    for the same person** — or crash on ``UsernameExistsException``, depending on
    how the pool aliases the address. Normalising at the parser makes the mixed
    case reach the same lookup as the lower case, so the command refuses with the
    ``user enrol`` remediation instead.

    The Stubber's expected-parameter dict is the assertion: it is queued with the
    **lower-cased** filter, so a command that passed the address through as typed
    fails here rather than silently doing the wrong thing.
    """
    seed_sub = fresh_sub("cognito")
    typed = f"Alice-{uuid.uuid4()}@Example.Test"
    with seeded(engine) as conn:
        org_id = make_org(conn, name=f"Case {uuid.uuid4()}")
        ops_enrol(conn, user_id=seed_sub, org_id=org_id, email=unique_email("seed"))
        resolved = conn.execute(
            select(organisation.c.name).where(organisation.c.org_id == org_id)
        ).scalar_one()

    with cognito() as (client, stubber):
        expect_environment(stubber, known_subs=[seed_sub], sampled=[seed_sub])
        expect_lookup(stubber, email=typed.lower(), sub=fresh_sub("cognito"))
        status = main(
            _argv(
                "user",
                "create",
                "--email",
                typed,
                "--display-name",
                "Alice",
                "--org",
                resolved,
            ),
            engine=engine,
            cognito=client,
            sts=FakeSts(),
            write=lambda _line: None,
        )
        stubber.assert_no_pending_responses()
    assert status == EXIT_REFUSED


def test_nothing_can_reach_the_database_leg_confirmation() -> None:
    """The wiring half of "the database leg is not skippable".

    The confirmation builder takes nothing but the output sink, so no argument
    exists through which a flag — an assume-yes flag reintroduced, or any other
    — could reach the prompt. ``test_ops_structure.py`` holds the other half:
    that no such flag is on the parser at all.
    """
    assert list(inspect.signature(_prompt).parameters) == ["emit"]
    with pytest.raises(SystemExit):  # and asking for one is a usage error
        build_parser().parse_args(_argv("org", "create", "--name", "X", globals_=("--yes",)))


def test_cli_traces_the_verified_arn_and_keeps_operator_as_an_annotation(
    engine: Engine, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Contract § 3a: the audit line names the principal that held the permission.

    ``--operator`` used to **replace** the ARN on this line, which made the one
    control the admin leg has a self-declared string — on precisely the entries
    an investigation would be reading. It is an annotation now: ``operator_arn``
    is always the ``GetCallerIdentity`` ARN the environment check verified, and
    ``operator_note`` carries whatever was typed.
    """
    monkeypatch.setenv("LOG_FORMAT", "json")
    # One `app_user` row, which is both the leg-3 sample and the subject: the
    # sample is the *newest* rows in the shared test database, so seeding two in
    # one transaction would leave which one it draws up to timestamp ties.
    subject = fresh_sub("cognito")
    email = unique_email("support")
    with seeded(engine) as conn:
        ops_enrol(conn, user_id=subject, org_id=make_org(conn), email=email)

    with cognito() as (client, stubber):
        expect_environment(stubber, known_subs=[subject], sampled=[subject])
        status = main(
            _argv(
                "admin",
                "grant",
                "--email",
                email,
                globals_=("--operator", "bob-on-call"),
            ),
            engine=engine,
            cognito=client,
            sts=FakeSts(),
            write=lambda _line: None,
        )

    assert status == 0
    traced = _traces(capsys.readouterr().out)
    assert len(traced) == 1
    assert traced[0]["operator_arn"] == CALLER_ARN
    assert traced[0]["operator_note"] == "bob-on-call"
    assert traced[0]["subject"] == subject
    assert traced[0]["direction"] == "grant"
    assert traced[0]["env"] == "staging"


def test_cli_traces_the_revoke_a_de_enrolment_performs(
    engine: Engine, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """``de-enrol`` clears ``is_admin``, and used to do it with no record at all.

    Offboarding is how the support role is most often taken away, so a trace
    that covered only ``admin revoke`` left the common case invisible. One
    mechanism serves both: the record carries the change, the CLI logs it after
    the commit.
    """
    monkeypatch.setenv("LOG_FORMAT", "json")
    leaver = fresh_sub("cognito")
    email = unique_email("leaving")
    with seeded(engine) as conn:
        ops_enrol(conn, user_id=leaver, org_id=make_org(conn), email=email, is_admin=True)

    with cognito() as (client, stubber):
        expect_environment(stubber, known_subs=[leaver], sampled=[leaver])
        status = main(
            _argv("user", "de-enrol", "--email", email),
            engine=engine,
            cognito=client,
            sts=FakeSts(),
            write=lambda _line: None,
        )

    assert status == 0
    traced = _traces(capsys.readouterr().out)
    assert [(line["subject"], line["direction"]) for line in traced] == [(leaver, "revoke")]
    assert traced[0]["operator_arn"] == CALLER_ARN


def test_a_failed_commit_leaves_no_admin_trace(
    engine: Engine, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reason the line moved out of the command: a trace is evidence or it is noise.

    The grant is executed and the commit then fails. Nothing was written, so
    nothing may be claimed — and while the line was emitted inside the
    transaction, a failed commit left a durable audit record of a privilege
    change that never happened. Worse than none: an investigation reading it has
    no way to tell it apart from a real one.
    """
    monkeypatch.setenv("LOG_FORMAT", "json")
    subject = fresh_sub("cognito")
    email = unique_email("uncommitted")
    with seeded(engine) as conn:
        ops_enrol(conn, user_id=subject, org_id=make_org(conn), email=email)

    def failing_commit(_self: RootTransaction) -> None:
        raise RuntimeError("injected commit failure")

    monkeypatch.setattr(RootTransaction, "commit", failing_commit)
    with cognito() as (client, stubber):
        expect_environment(stubber, known_subs=[subject], sampled=[subject])
        with pytest.raises(RuntimeError, match="injected commit failure"):
            main(
                _argv("admin", "grant", "--email", email),
                engine=engine,
                cognito=client,
                sts=FakeSts(),
                write=lambda _line: None,
            )
    output = capsys.readouterr().out
    monkeypatch.undo()

    assert _traces(output) == []
    with seeded(engine) as conn:
        assert (
            conn.execute(
                select(app_user.c.is_admin).where(app_user.c.user_id == subject)
            ).scalar_one()
            is False
        )
