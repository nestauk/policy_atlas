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
from sqlalchemy import RootTransaction, select, update
from sqlalchemy.engine import Engine

from policy_atlas.core.schema import app_user, ops_action, organisation, organisation_domain
from policy_atlas.ops.cli import EXIT_REFUSED, _prompt, _quota_value, build_parser, main
from tests.api.org_support import make_org, ops_enrol, seeded, unique_email
from tests.helpers import now
from tests.ops.support import (
    ACCOUNT_ID,
    CALLER_ARN,
    POOL_ID,
    FakeSts,
    cognito,
    expect_environment,
    expect_lock_out,
    expect_lookup,
    expect_sub_lookup,
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
    assert any("moved 0 task(s), 0 project(s), all private" in line for line in lines)
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

    Deactivation is how the support role is most often taken away, so a trace
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
    assert traced[0]["flag"] == "is_admin"
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


# --- task 065: the ops role, quotas and domains through the entrypoint (B1, B12, C1) ---


def _seed_person(engine: Engine, *, is_ops: bool = False) -> tuple[str, str, uuid.UUID]:
    """One enrolled row — the leg-3 sample and the subject, as the trace cases seed."""
    sub = fresh_sub("cognito")
    email = unique_email("cli-065")
    with seeded(engine) as conn:
        org_id = make_org(conn)
        ops_enrol(conn, user_id=sub, org_id=org_id, email=email)
        if is_ops:
            conn.execute(update(app_user).where(app_user.c.user_id == sub).values(is_ops=True))
    return sub, email, org_id


def _person(engine: Engine, sub: str) -> Any:
    with seeded(engine) as conn:
        return conn.execute(select(app_user).where(app_user.c.user_id == sub)).mappings().one()


def test_cli_ops_grant_traces_the_ops_flag_after_the_commit(
    engine: Engine, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Contract B1: the same post-commit ``ops.admin_change`` line, with ``flag=is_ops``."""
    monkeypatch.setenv("LOG_FORMAT", "json")
    sub, email, _org_id = _seed_person(engine)
    lines: list[str] = []
    with cognito() as (client, stubber):
        expect_environment(stubber, known_subs=[sub], sampled=[sub])
        status = main(
            _argv("ops", "grant", "--email", email),
            engine=engine,
            cognito=client,
            sts=FakeSts(),
            write=lines.append,
        )
    assert status == 0
    assert any("grant" in line and email in line for line in lines)
    traced = _traces(capsys.readouterr().out)
    assert [(t["subject"], t["direction"], t["flag"]) for t in traced] == [
        (sub, "grant", "is_ops")
    ]
    assert traced[0]["operator_arn"] == CALLER_ARN
    assert (_person(engine, sub)["is_ops"], _person(engine, sub)["is_admin"]) == (True, False)


def test_cli_user_quota_writes_the_overrides(engine: Engine) -> None:
    sub, email, _org_id = _seed_person(engine)
    lines: list[str] = []
    with cognito() as (client, stubber):
        expect_environment(stubber, known_subs=[sub], sampled=[sub])
        status = main(
            _argv(
                "user", "quota", "--email", email, "--tasks-per-year", "100", "--runs", "inherit"
            ),
            engine=engine,
            cognito=client,
            sts=FakeSts(),
            write=lines.append,
        )
    assert status == 0
    expected = "tasks per year inherit → 100, simultaneous tasks inherit → inherit"
    assert any(expected in line for line in lines)
    row = _person(engine, sub)
    assert (row["task_quota_per_year"], row["runs_per_user"]) == (100, None)


def test_cli_org_quota_writes_the_overrides(engine: Engine) -> None:
    sub, _email, org_id = _seed_person(engine)
    lines: list[str] = []
    with cognito() as (client, stubber):
        expect_environment(stubber, known_subs=[sub], sampled=[sub])
        status = main(
            _argv(
                "org", "quota", "--org", str(org_id), "--tasks-per-year", "100", "--runs", "inherit"
            ),
            engine=engine,
            cognito=client,
            sts=FakeSts(),
            write=lines.append,
        )
    assert status == 0
    assert any(str(org_id) in line and "inherit → 100" in line for line in lines)
    with seeded(engine) as conn:
        stored = conn.execute(
            select(organisation.c.task_quota_per_year, organisation.c.runs_per_user).where(
                organisation.c.org_id == org_id
            )
        ).one()
    assert tuple(stored) == (100, None)


def test_quota_flags_take_a_non_negative_integer_or_inherit() -> None:
    """The parser refuses what ``set_quota`` would: no negative value reaches the command."""
    assert (_quota_value("inherit"), _quota_value("0"), _quota_value("7")) == (None, 0, 7)
    for bad in ("-1", "abc", "1.5"):
        with pytest.raises(SystemExit):
            build_parser().parse_args(
                _argv("user", "quota", "--sub", "s", "--tasks-per-year", bad, "--runs", "1")
            )


def test_cli_org_domain_add_then_remove(engine: Engine) -> None:
    sub, _email, org_id = _seed_person(engine)
    typed = f"Cli-{uuid.uuid4()}.Example.Test"
    lines: list[str] = []
    with cognito() as (client, stubber):
        expect_environment(stubber, known_subs=[sub], sampled=[sub])
        status = main(
            _argv("org", "domain", "add", "--domain", typed, "--org", str(org_id)),
            engine=engine,
            cognito=client,
            sts=FakeSts(),
            write=lines.append,
        )
    assert status == 0
    assert any(f"added domain {typed.lower()}" in line for line in lines)
    with seeded(engine) as conn:
        assert (
            conn.execute(
                select(organisation_domain.c.org_id).where(
                    organisation_domain.c.domain == typed.lower()
                )
            ).scalar_one()
            == org_id
        )

    with cognito() as (client, stubber):
        expect_environment(stubber, known_subs=[sub], sampled=[sub])
        status = main(
            _argv("org", "domain", "remove", "--domain", typed),
            engine=engine,
            cognito=client,
            sts=FakeSts(),
            write=lines.append,
        )
    assert status == 0
    assert any(f"removed domain {typed.lower()}" in line for line in lines)
    with seeded(engine) as conn:
        assert (
            conn.execute(
                select(organisation_domain.c.domain).where(
                    organisation_domain.c.domain == typed.lower()
                )
            ).scalar_one_or_none()
            is None
        )


def test_cli_user_deactivate_says_the_ops_role_was_revoked(
    engine: Engine, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """``user deactivate`` clears ``is_ops`` as it clears ``is_admin``, and says so."""
    monkeypatch.setenv("LOG_FORMAT", "json")
    sub, email, _org_id = _seed_person(engine, is_ops=True)
    lines: list[str] = []
    with cognito() as (client, stubber):
        expect_environment(stubber, known_subs=[sub], sampled=[sub])
        expect_sub_lookup(stubber, sub=sub)
        expect_lock_out(stubber, sub=sub)
        status = main(
            _argv("user", "deactivate", "--email", email),
            engine=engine,
            cognito=client,
            sts=FakeSts(),
            write=lines.append,
        )
        stubber.assert_no_pending_responses()
    assert status == 0
    assert any(
        "deactivated" in line and "cleared the admin and ops roles" in line for line in lines
    )
    traced = _traces(capsys.readouterr().out)
    assert [(t["subject"], t["direction"], t["flag"]) for t in traced] == [
        (sub, "revoke", "is_ops")
    ]
    row = _person(engine, sub)
    assert (row["org_id"] is not None, row["is_ops"]) == (True, False)  # keeps the organisation


# --- user reset-app ---------------------------------------------------------------------
#
# The Stubber answers calls strictly in the order they were queued and fails any
# call it was not given, so the queue is both the order assertion and the proof
# that a refusal made no Cognito write.


def _expect_reset(
    stubber: Any, *, sub: str, fail_delete: bool = False, fail_sign_out: bool = False
) -> None:
    """Queue the enabled read, the global sign-out, then the app unlink.

    A failing sign-out queues no unlink: the Stubber fails a call it was not given.
    """
    params = {"UserPoolId": POOL_ID, "Username": sub}
    stubber.add_response("admin_get_user", {"Username": sub, "Enabled": True}, params)
    if fail_sign_out:
        stubber.add_client_error(
            "admin_user_global_sign_out",
            service_error_code="InternalErrorException",
            expected_params=params,
        )
        return
    stubber.add_response("admin_user_global_sign_out", {}, params)
    if fail_delete:
        stubber.add_client_error(
            "admin_delete_software_token",
            service_error_code="InternalErrorException",
            expected_params=params,
        )
    else:
        stubber.add_response("admin_delete_software_token", {}, params)


def _reset_app(engine: Engine, stubber_setup: Any, *command: str, arn: str) -> int:
    with cognito() as (client, stubber):
        stubber_setup(stubber)
        status = main(
            _argv("user", "reset-app", *command),
            engine=engine,
            cognito=client,
            sts=FakeSts(arn=arn),
            write=lambda _line: None,
        )
        stubber.assert_no_pending_responses()
    return status


def _actions_by(engine: Engine, arn: str) -> list[tuple[Any, ...]]:
    with seeded(engine) as conn:
        rows = conn.execute(
            select(
                ops_action.c.actor_user_id,
                ops_action.c.action,
                ops_action.c.target,
                ops_action.c.outcome,
            ).where(ops_action.c.actor_user_id == arn)
        ).all()
    return [tuple(row) for row in rows]


def _operator() -> str:
    """A caller identity unique to one test, so its audit rows are its own."""
    return f"arn:aws:sts::{ACCOUNT_ID}:assumed-role/Operator/{uuid.uuid4()}"


def test_cli_user_reset_app_signs_out_then_unlinks_the_app_and_records_one_action(
    engine: Engine,
) -> None:
    sub, email, _org_id = _seed_person(engine)
    arn = _operator()

    def queue(stubber: Any) -> None:
        expect_environment(stubber, known_subs=[sub], sampled=[sub])
        expect_sub_lookup(stubber, sub=sub, email=email.upper())
        _expect_reset(stubber, sub=sub)

    assert _reset_app(engine, queue, "--email", email, arn=arn) == 0
    assert _actions_by(engine, arn) == [(arn, "person.reset_app", sub, "ok")]


def test_cli_user_reset_app_refuses_an_unknown_address(engine: Engine) -> None:
    sub, _email, _org_id = _seed_person(engine)
    unknown = unique_email("nobody")
    arn = _operator()

    def queue(stubber: Any) -> None:
        expect_environment(stubber, known_subs=[sub], sampled=[sub])
        expect_lookup(stubber, email=unknown, sub=None)

    assert _reset_app(engine, queue, "--email", unknown, arn=arn) == EXIT_REFUSED
    assert _actions_by(engine, arn) == []


@pytest.mark.parametrize("where", ["marked in the database", "disabled in Cognito"])
def test_cli_user_reset_app_refuses_a_deactivated_account(engine: Engine, where: str) -> None:
    sub, email, _org_id = _seed_person(engine)
    if where == "marked in the database":
        with seeded(engine) as conn:
            conn.execute(
                update(app_user).where(app_user.c.user_id == sub).values(deactivated_at=now())
            )
    arn = _operator()

    def queue(stubber: Any) -> None:
        expect_environment(stubber, known_subs=[sub], sampled=[sub])
        expect_sub_lookup(stubber, sub=sub, email=email)
        if where == "disabled in Cognito":
            stubber.add_response(
                "admin_get_user",
                {"Username": sub, "Enabled": False},
                {"UserPoolId": POOL_ID, "Username": sub},
            )

    assert _reset_app(engine, queue, "--email", email, arn=arn) == EXIT_REFUSED
    assert _actions_by(engine, arn) == []


def test_cli_user_reset_app_failing_unlink_writes_no_action_and_a_rerun_finishes(
    engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    sub, _email, _org_id = _seed_person(engine)
    arn = _operator()

    def failing(stubber: Any) -> None:
        expect_environment(stubber, known_subs=[sub], sampled=[sub])
        expect_sub_lookup(stubber, sub=sub)
        _expect_reset(stubber, sub=sub, fail_delete=True)

    assert _reset_app(engine, failing, "--sub", sub, arn=arn) == EXIT_REFUSED
    err = capsys.readouterr().err
    assert "signed out everywhere" in err and "InternalErrorException" in err
    assert "again is safe" in err
    assert _actions_by(engine, arn) == []

    def working(stubber: Any) -> None:
        expect_environment(stubber, known_subs=[sub], sampled=[sub])
        expect_sub_lookup(stubber, sub=sub)
        _expect_reset(stubber, sub=sub)

    assert _reset_app(engine, working, "--sub", sub, arn=arn) == 0
    assert _actions_by(engine, arn) == [(arn, "person.reset_app", sub, "ok")]


def test_cli_user_reset_app_refuses_when_the_pool_holds_another_address_for_that_person(
    engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    sub, email, _org_id = _seed_person(engine)
    arn = _operator()

    def queue(stubber: Any) -> None:
        expect_environment(stubber, known_subs=[sub], sampled=[sub])
        # Nothing after the lookup is queued, so any further Cognito call fails the test.
        expect_sub_lookup(stubber, sub=sub, email=unique_email("moved"))

    assert _reset_app(engine, queue, "--email", email, arn=arn) == EXIT_REFUSED
    assert "no longer matches Cognito" in capsys.readouterr().err
    assert _actions_by(engine, arn) == []


def test_cli_user_reset_app_refuses_a_row_with_no_account_in_the_pool(engine: Engine) -> None:
    sub, _email, _org_id = _seed_person(engine)
    arn = _operator()

    def queue(stubber: Any) -> None:
        expect_environment(stubber, known_subs=[sub], sampled=[sub])
        stubber.add_response(
            "list_users",
            {"Users": []},
            {"UserPoolId": POOL_ID, "Filter": f'sub = "{sub}"', "Limit": 1},
        )

    assert _reset_app(engine, queue, "--sub", sub, arn=arn) == EXIT_REFUSED
    assert _actions_by(engine, arn) == []


def test_cli_user_reset_app_failing_sign_out_never_unlinks_and_writes_no_action(
    engine: Engine,
) -> None:
    sub, _email, _org_id = _seed_person(engine)
    arn = _operator()

    def queue(stubber: Any) -> None:
        expect_environment(stubber, known_subs=[sub], sampled=[sub])
        expect_sub_lookup(stubber, sub=sub)
        _expect_reset(stubber, sub=sub, fail_sign_out=True)

    assert _reset_app(engine, queue, "--sub", sub, arn=arn) == EXIT_REFUSED
    assert _actions_by(engine, arn) == []


def test_user_reset_app_takes_exactly_one_of_email_or_sub() -> None:
    parser = build_parser()
    assert parser.parse_args(_argv("user", "reset-app", "--email", "A@x.org")).email == "a@x.org"
    assert parser.parse_args(_argv("user", "reset-app", "--sub", "s")).sub == "s"
    for selectors in ((), ("--email", "a@x.org", "--sub", "s")):
        with pytest.raises(SystemExit):
            parser.parse_args(_argv("user", "reset-app", *selectors))
