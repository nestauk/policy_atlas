"""Argument parsing, the transaction, and the order the safety checks run in.

The command tree, with every global option before the subcommand::

    python -m policy_atlas.ops --env {staging,prod} [options] <group> <command>

      org   create    --name NAME
      user  create    --email E --display-name D --org ORG
      user  enrol     --email E --display-name D --org ORG
      user  resync    --email E
      user  de-enrol  (--email E | --sub SUB)
      rows  assign    (--project ID | --portfolio ID) --org ORG
      admin grant     --email E
      admin revoke    --email E

Global options: ``--env`` (required), ``--database-url``, ``--expected-account``,
``--user-pool-id``, ``--operator``, ``--yes``.

**There is no ``--password`` and no ``--temporary-password``**, on any command
(contract § 9). The absence is asserted structurally by
``tests/ops/test_ops_structure.py``, over the built parser rather than over the
source, so a flag added through any route fails the test.

**Order of operations, which is the whole safety design.** One transaction is
opened, the environment is verified *inside it* — leg 3 samples the same session
the command is about to write through, so it proves something about this
connection and not about a different one — and only then does the command run.
Anything that raises rolls the transaction back, and the success line prints
**after** the commit, so no operator ever reads "enrolled" about a write that
did not land.

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
from typing import Protocol

from mypy_boto3_cognito_idp.client import CognitoIdentityProviderClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine

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

#: Exit status for a refusal. Distinct from argparse's 2-for-usage only in
#: intent; both mean "nothing was written", which is the property an operator
#: needs from a non-zero exit.
EXIT_REFUSED = 2


class Outcome(Protocol):
    """Anything a command returns: a record that can describe itself."""

    def summary(self) -> str:
        """One operator-facing line describing what was done."""
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

    The seams mirror ``runtime/orchestrate.main``: every external dependency is
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
            prove itself against; defaults to an interactive prompt, or to
            automatic assent under ``--yes``.

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
        print(f"refused: {error}", file=sys.stderr)
        return EXIT_REFUSED


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
        help="SQLAlchemy URL for the tunnelled database (default: $DATABASE_URL)",
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
        help="who is running this, for the admin trace (default: the AWS caller ARN)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help=(
            "skip the confirmation asked when the database holds no accounts to "
            "check the pool against; never overrides a positive mismatch"
        ),
    )
    groups = parser.add_subparsers(dest="group", required=True)

    org = groups.add_parser("org", help="organisations").add_subparsers(
        dest="command", required=True
    )
    org_create = org.add_parser("create", help="create an organisation")
    org_create.add_argument("--name", required=True)

    user = groups.add_parser("user", help="people").add_subparsers(
        dest="command", required=True
    )
    user_create = user.add_parser(
        "create", help="create a Cognito account (emailed an invitation) and enrol it"
    )
    user_create.add_argument("--email", required=True)
    user_create.add_argument("--display-name", required=True)
    user_create.add_argument("--org", required=True, help="organisation name or id")

    user_enrol = user.add_parser("enrol", help="enrol an existing account, moving its owner's rows")
    user_enrol.add_argument("--email", required=True)
    user_enrol.add_argument("--display-name", required=True)
    user_enrol.add_argument("--org", required=True, help="organisation name or id")

    user_resync = user.add_parser("resync", help="re-resolve a stored address from Cognito")
    user_resync.add_argument("--email", required=True, help="the address as it stands NOW")

    user_de_enrol = user.add_parser("de-enrol", help="remove a person from their organisation")
    de_enrol_subject = user_de_enrol.add_mutually_exclusive_group(required=True)
    de_enrol_subject.add_argument("--email")
    de_enrol_subject.add_argument("--sub")

    rows = groups.add_parser("rows", help="row assignment").add_subparsers(
        dest="command", required=True
    )
    rows_assign = rows.add_parser("assign", help="assign one row to an organisation")
    assign_subject = rows_assign.add_mutually_exclusive_group(required=True)
    assign_subject.add_argument("--project", type=uuid.UUID)
    assign_subject.add_argument("--portfolio", type=uuid.UUID)
    rows_assign.add_argument("--org", required=True, help="organisation name or id")

    admin = groups.add_parser("admin", help="the support role").add_subparsers(
        dest="command", required=True
    )
    admin_grant = admin.add_parser("grant", help="grant the support role")
    admin_grant.add_argument("--email", required=True)
    admin_revoke = admin.add_parser("revoke", help="revoke the support role")
    admin_revoke.add_argument("--email", required=True)

    return parser


def _run(
    args: argparse.Namespace,
    *,
    engine: Engine | None,
    cognito: CognitoIdentityProviderClient | None,
    sts: StsClient | None,
    emit: Callable[[str], None],
    confirm: Callable[[Target], bool] | None,
) -> int:
    """Open the transaction, verify the environment, then dispatch."""
    database_url = args.database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        raise OpsError("no database: pass --database-url or set DATABASE_URL")
    target = resolve_target(
        env=args.env,
        expected_account=args.expected_account,
        user_pool_id=args.user_pool_id,
        database_url=database_url,
    )
    identity = cognito if cognito is not None else cognito_client()
    tokens = sts if sts is not None else sts_client()
    ask = confirm if confirm is not None else _prompt(emit, assume_yes=args.yes)
    db = engine if engine is not None else create_engine(database_url)

    with db.begin() as conn:
        verification = verify_environment(
            target, conn=conn, cognito=identity, sts=tokens, confirm=ask
        )
        outcome = _dispatch(
            args, conn=conn, cognito=identity, target=target, verification=verification
        )
    emit(outcome.summary())
    return 0


def _dispatch(
    args: argparse.Namespace,
    *,
    conn: Connection,
    cognito: CognitoIdentityProviderClient,
    target: Target,
    verification: Verification,
) -> Outcome:
    """Route one verified invocation to its command function."""
    if args.group == "org":
        return commands.create_organisation(conn, name=args.name)

    if args.group == "user":
        if args.command == "resync":
            return commands.resync_user(
                conn, cognito, pool_id=target.user_pool_id, email=args.email
            )
        if args.command == "de-enrol":
            return commands.de_enrol_user(conn, email=args.email, sub=args.sub)
        org = commands.resolve_organisation(conn, args.org)
        create_or_enrol = (
            commands.create_user if args.command == "create" else commands.enrol_user
        )
        return create_or_enrol(
            conn,
            cognito,
            pool_id=target.user_pool_id,
            email=args.email,
            display_name=args.display_name,
            org=org,
        )

    if args.group == "rows":
        org = commands.resolve_organisation(conn, args.org)
        return commands.assign_rows(
            conn, org=org, project_id=args.project, portfolio_id=args.portfolio
        )

    return commands.set_admin(
        conn,
        email=args.email,
        grant=args.command == "grant",
        operator=args.operator or verification.caller_arn,
        env=target.env,
    )


def _prompt(emit: Callable[[str], None], *, assume_yes: bool) -> Callable[[Target], bool]:
    """The interactive confirmation the unprovable database leg falls back to."""

    def ask(target: Target) -> bool:
        if assume_yes:
            return True
        emit(
            f"the database at {target.database} holds no accounts, so it cannot be "
            f"checked against user pool {target.user_pool_id}."
        )
        emit(f"about to act on: env={target.env} account={target.account_id}")
        return input(f'type "{target.env}" to continue: ').strip() == target.env

    return ask


def _stdout(line: str) -> None:
    print(line)
