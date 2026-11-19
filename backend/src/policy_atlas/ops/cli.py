"""Argument parsing, the transaction, and the order the safety checks run in.

The command tree, with every global option before the subcommand::

    python -m policy_atlas.ops --env {staging,prod} [options] <group> <command>

      org   create    --name NAME
      org   delete    --org ORG
      org   quota     --org ORG --tasks-per-year N|inherit --runs N|inherit
      org   domain add --domain D --org ORG
      org   domain remove --domain D
      user  create    --email E --display-name D [--org ORG]
      user  enrol     --email E --display-name D --org ORG
      user  resync    --email E
      user  reissue   --email E
      user  de-enrol  (--email E | --sub SUB)
      user  deactivate (--email E | --sub SUB)
      user  reactivate (--email E | --sub SUB)
      user  quota     (--email E | --sub SUB) --tasks-per-year N|inherit --runs N|inherit
      rows  assign    (--task ID | --project ID) --org ORG
      admin grant     (--email E | --sub SUB)
      admin revoke    (--email E | --sub SUB)
      ops   grant     (--email E | --sub SUB)
      ops   revoke    (--email E | --sub SUB)

Global options: ``--env`` (required), ``--database-url``, ``--expected-account``,
``--user-pool-id``, ``--operator``. **There is no ``--yes``**: the only
confirmation this CLI asks is the environment check's database leg, and that one
is not skippable (:func:`_prompt`).

**There is no ``--password`` and no ``--temporary-password``**, on any command.
The absence is asserted structurally by
``tests/ops/test_ops_structure.py``, over the built parser rather than over the
source, so a flag added through any route fails the test. ``--database-url``
refuses a URL carrying a password for the same reason the make targets went:
argv is in the shell history and in the process table. The credential belongs
in ``DATABASE_URL``.

**Order of operations, which is the whole safety design.** One transaction is
opened, the environment is verified *inside it* — leg 3 samples the same session
the command is about to write through, so it proves something about this
connection and not about a different one — and only then does the command run.
Anything that raises rolls the transaction back, and the success line prints
**after** the commit, so no operator ever reads "enrolled" about a write that
did not land.

**The admin trace is emitted here, after that commit**, from whatever
:class:`~policy_atlas.ops.commands.AdminTrace` values the record carries
(:func:`_trace`). The line must be evidence, and a line
written inside the transaction is a durable claim about a write a failed commit
then threw away. One mechanism serves every command that moves ``is_admin`` —
``admin grant``, ``admin revoke``, and the ``is_admin`` a ``user de-enrol`` or
``user deactivate`` clears.

The one place that ordering cannot save anything is ``user create``: the Cognito
account is made before the database is touched, because its ``sub`` is the key.
That command's own docstring covers what happens when the second half fails.
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Protocol

import structlog
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine, make_url

from policy_atlas.core.logging import configure_logging
from policy_atlas.ops import commands
from policy_atlas.ops.environment import (
    ENVIRONMENTS,
    StsClient,
    Target,
    Verification,
    cognito_client,
    resolve_target,
    sts_client,
    verify_environment,
)
from policy_atlas.ops.errors import OpsError

if TYPE_CHECKING:
    from mypy_boto3_cognito_idp.client import CognitoIdentityProviderClient

log = structlog.get_logger()

#: Exit status for a refusal. Distinct from argparse's 2-for-usage only in
#: intent; both mean "nothing was written", which is the property an operator
#: needs from a non-zero exit.
EXIT_REFUSED = 2


class Outcome(Protocol):
    """Anything a command returns: a record that can describe itself."""

    def summary(self) -> str:
        """One operator-facing line describing what was done."""
        ...

    def admin_changes(self) -> Sequence[commands.AdminTrace]:
        """Privilege changes to trace once the transaction has committed."""
        ...


def main(
    argv: Sequence[str] | None = None,
    *,
    engine: Engine | None = None,
    cognito: CognitoIdentityProviderClient | None = None,
    sts: StsClient | None = None,
    write: Callable[[str], None] | None = None,
    confirm: Callable[[Target], bool] | None = None,
) -> int:
    """Run one operator command.

    The seams mirror ``runtime/agent.main``: every external dependency is
    an optional argument that defaults to the real thing, so the suite can drive
    the actual entrypoint against the test database with a stubbed identity
    provider and no AWS call is ever made.

    Args:
        argv: Command-line arguments excluding the program name.
        engine: Database engine; defaults to one built from ``--database-url``
            or ``DATABASE_URL``.
        cognito: Cognito client; defaults to ambient operator credentials.
        sts: Security-token client; defaults to ambient operator credentials.
        write: Where operator-facing lines go; defaults to stdout.
        confirm: Asked when the environment check's database leg has nothing to
            prove itself against; defaults to the interactive prompt, which no
            flag can lift.

    Returns:
        Process exit status: ``0`` on success, :data:`EXIT_REFUSED` on a refusal.
    """
    configure_logging()
    emit = write if write is not None else _stdout
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return _run(args, engine=engine, cognito=cognito, sts=sts, emit=emit, confirm=confirm)
    except OpsError as error:
        print(f"refused: {error}", file=sys.stderr)  # noqa: T201 - command-line output
        return EXIT_REFUSED


def _email(value: str) -> str:
    """Normalise an address once, at the boundary every command shares.

    Cognito's ``ListUsers`` filter is an exact, case-sensitive match, while the
    pool treats ``Alice@x`` and ``alice@x`` as one account. Left alone, the two
    spellings are two different commands: ``user create --email Alice@x`` finds
    no account under the address it was given and goes on to ask
    ``AdminCreateUser`` for a second identity for the same person. Normalising
    at the parser means every command downstream — Cognito lookups *and* the
    ``app_user.email`` selector ``admin grant`` resolves by — sees one spelling.

    Args:
        value: The address as typed.

    Returns:
        The address, trimmed and lower-cased.
    """
    return value.strip().lower()


def build_parser() -> argparse.ArgumentParser:
    """Build the full command tree.

    Exposed rather than private so the structural test can assert over the
    parser — the absence of a password flag is a property of the interface, and
    asserting it against the built tree covers flags added by any route,
    including ones a grep over the source would miss.

    Returns:
        The configured top-level parser.
    """
    parser = argparse.ArgumentParser(
        prog="python -m policy_atlas.ops",
        description="Policy Atlas organisation operations (task 033, contract § 9).",
    )
    parser.add_argument(
        "--env",
        required=True,
        choices=ENVIRONMENTS,
        help="the environment to act on; verified against AWS and the database before acting",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help=(
            "SQLAlchemy URL for the tunnelled database, without a password "
            "(default: $DATABASE_URL, which is where the credential belongs)"
        ),
    )
    parser.add_argument(
        "--expected-account",
        default=None,
        help="AWS account id this environment must resolve to (default: $PA_OPS_ACCOUNT_<ENV>)",
    )
    parser.add_argument(
        "--user-pool-id",
        default=None,
        help="Cognito user pool to act on (default: $PA_OPS_USER_POOL_<ENV>)",
    )
    parser.add_argument(
        "--operator",
        default=None,
        help=(
            "a note annotating the admin trace; the verified AWS caller ARN is "
            "logged either way and this never replaces it"
        ),
    )
    # There is deliberately no `--yes`. It existed to skip the environment
    # check's database-leg confirmation, that confirmation is now un-skippable
    # (see `_prompt`), and a flag that no longer does what its name promises is
    # an operator trap: the operator most likely to reach for it is the one it
    # would have hurt. `tests/ops/test_ops_cli.py` asserts its absence over the
    # built parser, so it cannot come back by any route.
    groups = parser.add_subparsers(dest="group", required=True)

    org = groups.add_parser("org", help="organisations").add_subparsers(
        dest="command", required=True
    )
    org_create = org.add_parser("create", help="create an organisation")
    org_create.add_argument("--name", required=True)
    org_delete = org.add_parser(
        "delete", help="delete an organisation no person, task, project or domain points at"
    )
    org_delete.add_argument("--org", required=True)
    org_quota = org.add_parser("quota", help="set organisation quota overrides")
    org_quota.add_argument("--org", required=True)
    _quota_args(org_quota)
    domain = org.add_parser("domain", help="manage self-signup domains").add_subparsers(
        dest="domain_command", required=True
    )
    domain_add = domain.add_parser("add", help="map a domain to an organisation")
    domain_add.add_argument("--domain", required=True)
    domain_add.add_argument("--org", required=True)
    domain_remove = domain.add_parser("remove", help="remove a domain mapping")
    domain_remove.add_argument("--domain", required=True)

    user = groups.add_parser("user", help="people").add_subparsers(dest="command", required=True)
    user_create = user.add_parser(
        "create",
        help="create a Cognito account (emailed an invitation); enrol it when --org is given",
    )
    user_create.add_argument("--email", required=True, type=_email)
    user_create.add_argument("--display-name", required=True)
    user_create.add_argument(
        "--org",
        default=None,
        help="organisation name or id; omit to leave the account in no organisation",
    )
    user_create.add_argument(
        "--invite",
        choices=("email", "manual"),
        default="email",
        help=(
            "email: Cognito emails the invitation (COGNITO_DEFAULT sender). "
            "manual: suppress the email; the CLI mints a single-use temporary "
            "password and prints it once for out-of-band handover — it never "
            "accepts one (owner amendment 2026-08-26)"
        ),
    )

    user_enrol = user.add_parser("enrol", help="enrol an existing account, moving its owner's rows")
    user_enrol.add_argument("--email", required=True, type=_email)
    user_enrol.add_argument("--display-name", required=True)
    user_enrol.add_argument("--org", required=True, help="organisation name or id")

    user_resync = user.add_parser("resync", help="re-resolve a stored address from Cognito")
    user_resync.add_argument(
        "--email", required=True, type=_email, help="the address as it stands NOW"
    )

    user_reissue = user.add_parser(
        "reissue",
        help=(
            "mint and print a new single-use temporary password for an account that "
            "has never signed in (FORCE_CHANGE_PASSWORD) — it never accepts one"
        ),
    )
    user_reissue.add_argument("--email", required=True, type=_email)

    user_de_enrol = user.add_parser("de-enrol", help="remove a person from their organisation")
    de_enrol_subject = user_de_enrol.add_mutually_exclusive_group(required=True)
    de_enrol_subject.add_argument("--email", type=_email)
    de_enrol_subject.add_argument("--sub")

    user_deactivate = user.add_parser(
        "deactivate",
        help=(
            "lock a person out: disable their Cognito account, sign them out everywhere, "
            "clear their admin and ops roles and make their public task links private; "
            "they keep their organisation and work"
        ),
    )
    deactivate_subject = user_deactivate.add_mutually_exclusive_group(required=True)
    deactivate_subject.add_argument("--email", type=_email)
    deactivate_subject.add_argument("--sub")
    user_reactivate = user.add_parser(
        "reactivate", help="turn a deactivated person's login back on (roles are not restored)"
    )
    reactivate_subject = user_reactivate.add_mutually_exclusive_group(required=True)
    reactivate_subject.add_argument("--email", type=_email)
    reactivate_subject.add_argument("--sub")
    user_quota = user.add_parser("quota", help="set a person's quota overrides")
    user_quota_subject = user_quota.add_mutually_exclusive_group(required=True)
    user_quota_subject.add_argument("--email", type=_email)
    user_quota_subject.add_argument("--sub")
    _quota_args(user_quota)

    rows = groups.add_parser("rows", help="row assignment").add_subparsers(
        dest="command", required=True
    )
    rows_assign = rows.add_parser("assign", help="assign one row to an organisation")
    assign_subject = rows_assign.add_mutually_exclusive_group(required=True)
    assign_subject.add_argument("--task", type=uuid.UUID)
    assign_subject.add_argument("--project", type=uuid.UUID)
    rows_assign.add_argument("--org", required=True, help="organisation name or id")

    admin = groups.add_parser("admin", help="the support role").add_subparsers(
        dest="command", required=True
    )
    # Both take `--sub` for the reason `de-enrol` does: `app_user.email` carries
    # no unique constraint, so the ambiguous-address refusal recommends `--sub`
    # and has to be able to. Revoking a compromised administrator is the last
    # place a stale duplicate address should be a dead end.
    for direction in ("grant", "revoke"):
        subject = admin.add_parser(
            direction, help=f"{direction} the support role"
        ).add_mutually_exclusive_group(required=True)
        subject.add_argument("--email", type=_email)
        subject.add_argument("--sub")

    ops = groups.add_parser("ops", help="the operations role").add_subparsers(
        dest="command", required=True
    )
    for direction in ("grant", "revoke"):
        subject = (
            ops.add_parser(direction, help=f"{direction} the operations role")
            .add_mutually_exclusive_group(required=True)
        )
        subject.add_argument("--email", type=_email)
        subject.add_argument("--sub")

    return parser


def _quota_value(value: str) -> int | None:
    """Parse a non-negative override or the explicit inherit sentinel."""
    if value == "inherit":
        return None
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected a non-negative integer or inherit") from error
    if parsed < 0:
        raise argparse.ArgumentTypeError("expected a non-negative integer or inherit")
    return parsed


def _quota_args(parser: argparse.ArgumentParser) -> None:
    """Add the two required quota override flags to one subcommand."""
    parser.add_argument("--tasks-per-year", required=True, type=_quota_value)
    parser.add_argument("--runs", required=True, type=_quota_value)


def _run(
    args: argparse.Namespace,
    *,
    engine: Engine | None,
    cognito: CognitoIdentityProviderClient | None,
    sts: StsClient | None,
    emit: Callable[[str], None],
    confirm: Callable[[Target], bool] | None,
) -> int:
    """Open the transaction, verify the environment, dispatch, then trace."""
    database_url = _database_url(args)
    target = resolve_target(
        env=args.env,
        expected_account=args.expected_account,
        user_pool_id=args.user_pool_id,
        database_url=database_url,
    )
    identity = cognito if cognito is not None else cognito_client()
    tokens = sts if sts is not None else sts_client()
    ask = confirm if confirm is not None else _prompt(emit)
    db = engine if engine is not None else create_engine(database_url, hide_parameters=True)

    with db.begin() as conn:
        verification = verify_environment(
            target, conn=conn, cognito=identity, sts=tokens, confirm=ask
        )
        outcome = _dispatch(args, conn=conn, cognito=identity, target=target)
        if isinstance(outcome, commands.QuotaChange):
            # A quota change is recorded wherever it is made:
            # the operator's verified AWS principal is the actor.
            commands.record_action(
                conn,
                actor=verification.caller_arn,
                action="org.quota" if args.group == "org" else "person.quota",
                target=outcome.who,
                outcome="ok",
            )
    # Both of these are after the commit, and for the same reason: neither a
    # printed line nor a logged one may claim a write the transaction discarded.
    _trace(outcome, verification=verification, target=target, note=args.operator)
    emit(outcome.summary())
    return 0


def _database_url(args: argparse.Namespace) -> str:
    """Resolve the database URL, refusing a credential passed on the command line.

    ``--database-url`` is a convenience for the tunnel's host and port. A
    password in it lands in the shell history and in the process table, which is
    exactly what the deleted ``cognito-user`` make target did with the Cognito
    password and exactly why it went. ``DATABASE_URL`` is the
    credential path, and it is unchanged: an environment variable is not on argv.

    Raises:
        OpsError: If no URL is configured, or ``--database-url`` carries a
            password.
    """
    if args.database_url:
        if make_url(args.database_url).password:
            raise OpsError(
                "--database-url carries a password, which puts it in your shell history "
                "and in the process table. Pass the credential through DATABASE_URL "
                "instead (export DATABASE_URL=...), or give a URL with no password. "
                "Nothing was written."
            )
        url: str = args.database_url
        return url
    from_env = os.environ.get("DATABASE_URL")
    if not from_env:
        raise OpsError("no database: pass --database-url or set DATABASE_URL")
    return from_env


def _trace(
    outcome: Outcome,
    *,
    verification: Verification,
    target: Target,
    note: str | None,
) -> None:
    """Emit one ``ops.admin_change`` per privilege change, after the commit.

    ``operator_arn`` is **always** the ARN ``GetCallerIdentity`` returned during
    the environment check — the AWS principal that actually held the permission.
    ``--operator`` annotates that as ``operator_note`` and can never replace it:
    a self-declared operator identity on an audit line is not an audit line, and
    the previous ``--operator or caller_arn`` let one string be typed over the
    other on precisely the entries an investigation would be reading.

    Args:
        outcome: The record the command returned.
        verification: What the environment check proved, for the caller ARN.
        target: The verified estate, for the environment name.
        note: The ``--operator`` annotation, or ``None``.
    """
    for change in outcome.admin_changes():
        log.info(
            "ops.admin_change",
            operator_arn=verification.caller_arn,
            operator_note=note,
            subject=change.subject,
            direction=change.direction,
            flag=change.flag,
            env=target.env,
        )


def _dispatch(
    args: argparse.Namespace,
    *,
    conn: Connection,
    cognito: CognitoIdentityProviderClient,
    target: Target,
) -> Outcome:
    """Route one verified invocation to its command function."""
    if args.group == "org":
        if args.command == "create":
            return commands.create_organisation(conn, name=args.name)
        if args.command == "delete":
            org = commands.resolve_organisation(conn, args.org)
            return commands.delete_organisation(conn, org_id=org.org_id)
        if args.command == "quota":
            org = commands.resolve_organisation(conn, args.org)
            return commands.set_quota(
                conn,
                org_id=org.org_id,
                task_quota_per_year=args.tasks_per_year,
                runs_per_user=args.runs,
            )
        if args.domain_command == "add":
            org = commands.resolve_organisation(conn, args.org)
            return commands.add_domain(conn, domain=args.domain, org=org)
        return commands.remove_domain(conn, domain=args.domain)

    if args.group == "user":
        if args.command == "resync":
            return commands.resync_user(
                conn, cognito, pool_id=target.user_pool_id, email=args.email
            )
        if args.command == "reissue":
            return commands.reissue_temporary_password(
                cognito, pool_id=target.user_pool_id, email=args.email
            )
        if args.command == "de-enrol":
            return commands.de_enrol_user(conn, email=args.email, sub=args.sub)
        if args.command == "deactivate":
            return commands.deactivate_user(
                conn, cognito, pool_id=target.user_pool_id, email=args.email, sub=args.sub
            )
        if args.command == "reactivate":
            row = commands._resolve_and_lock(conn, email=args.email, sub=args.sub)
            return commands.reactivate_user(
                conn, cognito, pool_id=target.user_pool_id, sub=str(row["user_id"])
            )
        if args.command == "quota":
            row = commands._resolve_and_lock(conn, email=args.email, sub=args.sub)
            return commands.set_quota(
                conn,
                user_id=str(row["user_id"]),
                task_quota_per_year=args.tasks_per_year,
                runs_per_user=args.runs,
            )
        if args.command == "create" and args.org is None:
            return commands.create_user(
                conn,
                cognito,
                pool_id=target.user_pool_id,
                email=args.email,
                display_name=args.display_name,
                invite=args.invite,
            )
        org = commands.resolve_organisation(conn, args.org)
        if args.command == "create":
            return commands.create_user(
                conn,
                cognito,
                pool_id=target.user_pool_id,
                email=args.email,
                display_name=args.display_name,
                org=org,
                invite=args.invite,
            )
        return commands.enrol_user(
            conn,
            cognito,
            pool_id=target.user_pool_id,
            email=args.email,
            display_name=args.display_name,
            org=org,
        )

    if args.group == "rows":
        org = commands.resolve_organisation(conn, args.org)
        return commands.assign_rows(conn, org=org, task_id=args.task, project_id=args.project)

    if args.group == "ops":
        return commands.set_ops(conn, email=args.email, sub=args.sub, grant=args.command == "grant")
    return commands.set_admin(conn, email=args.email, sub=args.sub, grant=args.command == "grant")


def _prompt(emit: Callable[[str], None]) -> Callable[[Target], bool]:
    """The interactive confirmation the unprovable database leg falls back to.

    **It takes no flag, and there is no flag to take.** An unproven database leg
    is the state every fresh deployment is in — the 033 migration seeds no
    ``app_user`` rows, so the very first ``org create`` against a new
    environment reaches here — and it is the state in which the tunnel is least
    accounted for. An earlier revision let ``--yes`` skip it, which made "wrong
    tunnel plus one flag writes production" the cheapest mistake in the tool, in
    exactly the window where nothing else is watching. That flag is gone rather
    than made inert, because a flag whose name still promises to skip something
    is read by exactly the operator it would have hurt. The environment name is
    typed, every time, by a person.

    That is also why there is no non-interactive fallback: with no terminal
    there is nobody to be sure, and the command refuses rather than assenting on
    somebody's behalf.
    """

    def ask(target: Target) -> bool:
        emit(
            f"the database at {target.database} holds no accounts, so it cannot be "
            f"checked against user pool {target.user_pool_id}."
        )
        emit(f"about to act on: env={target.env} account={target.account_id}")
        if not sys.stdin.isatty():
            raise OpsError(
                "the environment cannot be proved and there is no terminal to confirm "
                "on. Nothing was written. There is no flag for this: run the command "
                "interactively."
            )
        return input(f'type "{target.env}" to continue: ').strip() == target.env

    return ask


def _stdout(line: str) -> None:
    print(line)  # noqa: T201 - command-line output
