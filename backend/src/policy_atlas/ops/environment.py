"""Environment safety: prove the AWS account and the database are the same estate.

Contract § 9 calls this "the single highest-consequence operational failure in
the design", and it is an unusual shape of failure: **the two halves of an
operator command are addressed completely differently.** Cognito is reached
through ambient AWS credentials (a profile, a role, an SSO session); Postgres is
reached through an SSM port-forward that always lands on ``localhost:15432``
whichever cluster is on the far end. Neither half can see the other. An operator
who leaves a production tunnel open and switches their AWS profile to staging
gets no error from anything — they get staging identities written into the
production database.

So every command runs :func:`verify_environment` before it acts, and it has
three legs.

**Leg 1 — the account.** ``sts:GetCallerIdentity`` must return the account id the
operator has configured for ``--env``. The expected id comes from the operator's
own environment (``PA_OPS_ACCOUNT_STAGING`` / ``PA_OPS_ACCOUNT_PROD``, or
``--expected-account``) and **never from the repository**: this repo is public
and account ids are env-injected by policy (task 026 decision 4).

**Leg 2 — the pool.** The user-pool id likewise comes from operator
configuration (``PA_OPS_USER_POOL_STAGING`` / ``PA_OPS_USER_POOL_PROD``, or
``--user-pool-id``) and is proved to exist *in that account* by a one-row
``ListUsers`` — a pool id belonging to the other account raises
``ResourceNotFoundException`` and the command refuses. Legs 1 and 2 together pin
the AWS half.

**Leg 3 — the database, which is the leg that actually matters.** Legs 1 and 2
say which AWS account the operator is in. They say nothing about which cluster
the tunnel reaches, and that is the failure being defended against. There is no
environment marker in the schema to read: contract § 9 offered "a row in
``organisation`` or a settings table naming the environment", but the schema
gate (§ Constraints) enumerated exactly two new tables and neither is a settings
table, and a magic ``organisation`` row would be a value the tenancy code could
join against by accident. So this leg proves the pairing from data that is
already there and already load-bearing: **``app_user.user_id`` is the Cognito
``sub``.** Sample the most recently created subjects from the connected database
and ask the resolved pool whether it knows them.

- **At least one sub resolves** → the database and the pool are the same estate.
  Verified; the command proceeds.
- **Subjects exist and none resolve** → they are somebody else's pool's subjects.
  This is precisely the prod-tunnel/staging-credentials case, and it is a **hard
  refusal with no override** — ``--yes`` does not lift it, because an operator
  who is wrong about which estate they are in is exactly the operator who would
  pass ``--yes``.
- **The table is empty** → nothing to prove against. The command prints the
  resolved triple and requires the operator to type the environment name back
  (``--yes`` skips this, for scripting). Stated plainly rather than dressed up:
  in this one state the database leg is operator confirmation. Its blast radius
  is also nil — a database with no ``app_user`` rows is one nobody has ever
  signed in to.

The residual gap is honest and worth naming: this leg proves *the database and
the pool agree*, so it catches the mismatched pair. It cannot catch an operator
who is consistently and entirely in the wrong environment — right account, right
pool, right database, wrong intent. That is what ``--env`` being explicit and
echoed on every line is for.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import boto3
import structlog
from botocore.exceptions import ClientError
from mypy_boto3_cognito_idp.client import CognitoIdentityProviderClient
from sqlalchemy import desc, select
from sqlalchemy.engine import Connection, make_url

from policy_atlas.core.schema import app_user
from policy_atlas.ops.errors import OpsError

log = structlog.get_logger()

#: The deployment's only region (``infra/pa_config.json``; the deleted
#: ``cognito-user`` make target hard-coded the same value). Overridable by the
#: usual boto3 environment variables for an operator whose shell already sets
#: them.
DEFAULT_REGION = "eu-west-2"

#: Environments this CLI will act against. Not an open set: ``--env`` selecting
#: an unknown name would silently look up configuration variables that do not
#: exist and fail with a confusing message instead of a refusal.
ENVIRONMENTS = ("staging", "prod")

#: How many subjects leg 3 samples. Small on purpose — one ``ListUsers`` call
#: each, and the newest rows are the ones most likely to still have a live
#: account behind them. More than one because a single sampled subject whose
#: Cognito account was since removed would refuse a correct pairing.
_SUB_SAMPLE = 3


class StsClient(Protocol):
    """The one STS call this CLI makes.

    A :class:`~typing.Protocol` rather than the generated stub type because
    ``boto3-stubs`` ships only the ``cognito-idp`` service package (contract
    § 10 pins that extra, and widening an approved dependency line is not this
    phase's to do). ``boto3.client("sts")`` therefore types as ``Any``; naming
    the surface here keeps the call site strict-clean and lets a test pass a
    four-line fake instead of a stubbed client.
    """

    def get_caller_identity(self) -> Mapping[str, Any]:
        """Return the calling identity, including ``Account`` and ``Arn``."""
        ...


@dataclass(frozen=True)
class Target:
    """The estate one command was told to act on, before anything is verified.

    Attributes:
        env: ``staging`` or ``prod``, as the operator typed it.
        account_id: The AWS account id the operator's configuration expects.
        user_pool_id: The Cognito user pool the operator's configuration names.
        database: A display rendering of the connected database — host, port
            and name, never the password. Printed in the confirmation prompt,
            so it must be safe to put on a terminal and in a scrollback.
    """

    env: str
    account_id: str
    user_pool_id: str
    database: str


@dataclass(frozen=True)
class Verification:
    """What :func:`verify_environment` proved, for the record it prints.

    Attributes:
        target: The estate that was checked.
        caller_arn: The IAM principal that answered ``GetCallerIdentity`` —
            also the default operator identity on the admin trace, which is why
            it is carried out of here rather than looked up twice.
        database_leg: ``verified`` when a sampled subject resolved in the pool,
            ``unproven`` when the database held no subjects to sample and the
            operator confirmed instead. Never anything else: a mismatch raises.
    """

    target: Target
    caller_arn: str
    database_leg: str


def resolve_target(
    *,
    env: str,
    expected_account: str | None,
    user_pool_id: str | None,
    database_url: str,
) -> Target:
    """Resolve the estate from flags and the operator's own environment.

    Args:
        env: The ``--env`` value.
        expected_account: ``--expected-account``, or ``None`` to read
            ``PA_OPS_ACCOUNT_<ENV>``.
        user_pool_id: ``--user-pool-id``, or ``None`` to read
            ``PA_OPS_USER_POOL_<ENV>``.
        database_url: The SQLAlchemy URL the command will connect with.

    Returns:
        The unverified target.

    Raises:
        OpsError: If ``env`` is unknown, or either identifier is unconfigured.
    """
    if env not in ENVIRONMENTS:
        raise OpsError(f"unknown environment {env!r} — expected one of {', '.join(ENVIRONMENTS)}")
    suffix = env.upper()
    account = expected_account or os.environ.get(f"PA_OPS_ACCOUNT_{suffix}")
    pool = user_pool_id or os.environ.get(f"PA_OPS_USER_POOL_{suffix}")
    if not account:
        raise OpsError(
            f"no expected AWS account for --env {env}: set PA_OPS_ACCOUNT_{suffix} "
            "or pass --expected-account. It is not committed to this repository "
            "because the repository is public."
        )
    if not pool:
        raise OpsError(
            f"no user pool for --env {env}: set PA_OPS_USER_POOL_{suffix} or pass "
            "--user-pool-id (aws ssm get-parameter --name "
            "/policy_atlas_v3/auth/user_pool_id)."
        )
    return Target(
        env=env,
        account_id=account,
        user_pool_id=pool,
        database=_render_database(database_url),
    )


def verify_environment(
    target: Target,
    *,
    conn: Connection,
    cognito: CognitoIdentityProviderClient,
    sts: StsClient,
    confirm: Callable[[Target], bool],
) -> Verification:
    """Prove the AWS estate and the connected database are the same environment.

    Runs the three legs in the module docstring's order — cheapest and most
    decisive first, so a wrong profile costs one API call and never touches the
    database.

    Args:
        conn: The connection the command is about to write through. Leg 3 must
            sample the *same* connection, not a fresh one: proving something
            about a different session would prove nothing.
        cognito: The client bound to ``target.user_pool_id``.
        sts: The security-token client.
        confirm: Asked only when leg 3 has nothing to sample. Returning
            ``False`` refuses the command.

    Returns:
        The verification record, for the summary line the CLI prints.

    Raises:
        OpsError: On any mismatch, or a declined confirmation.
    """
    identity = sts.get_caller_identity()
    account = str(identity.get("Account", ""))
    caller_arn = str(identity.get("Arn", ""))
    if account != target.account_id:
        raise OpsError(
            f"environment mismatch: --env {target.env} expects AWS account "
            f"{target.account_id}, but these credentials are account {account}. "
            "Nothing was written. Check AWS_PROFILE."
        )

    _require_pool_in_account(target, cognito=cognito)
    database_leg = _check_database_leg(target, conn=conn, cognito=cognito, confirm=confirm)

    log.info(
        "ops.environment_verified",
        env=target.env,
        account=target.account_id,
        user_pool=target.user_pool_id,
        database=target.database,
        database_leg=database_leg,
        caller=caller_arn,
    )
    return Verification(target=target, caller_arn=caller_arn, database_leg=database_leg)


def cognito_client(region: str | None = None) -> CognitoIdentityProviderClient:
    """Build the Cognito client from ambient operator credentials."""
    client: CognitoIdentityProviderClient = boto3.client(
        "cognito-idp", region_name=region or _region()
    )
    return client


def sts_client(region: str | None = None) -> StsClient:
    """Build the STS client from ambient operator credentials."""
    client: StsClient = boto3.client("sts", region_name=region or _region())
    return client


def _region() -> str:
    return os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or DEFAULT_REGION


def _render_database(database_url: str) -> str:
    """Render a URL as ``host:port/name``, with the password left behind."""
    url = make_url(database_url)
    port = f":{url.port}" if url.port else ""
    return f"{url.host or 'localhost'}{port}/{url.database or '?'}"


def _require_pool_in_account(
    target: Target, *, cognito: CognitoIdentityProviderClient
) -> None:
    """Leg 2: the configured pool must exist in the account leg 1 just proved."""
    try:
        cognito.list_users(UserPoolId=target.user_pool_id, Limit=1)
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code", "")
        if code in {"ResourceNotFoundException", "AccessDeniedException"}:
            raise OpsError(
                f"environment mismatch: user pool {target.user_pool_id} is not reachable "
                f"in AWS account {target.account_id} ({code}). Nothing was written."
            ) from error
        raise


def _check_database_leg(
    target: Target,
    *,
    conn: Connection,
    cognito: CognitoIdentityProviderClient,
    confirm: Callable[[Target], bool],
) -> str:
    """Leg 3: do the connected database's subjects belong to the resolved pool?"""
    subs = _sample_subjects(conn)
    if not subs:
        if confirm(target):
            return "unproven"
        raise OpsError("refused at the environment confirmation. Nothing was written.")
    for sub in subs:
        if _pool_knows(cognito, pool_id=target.user_pool_id, sub=sub):
            return "verified"
    raise OpsError(
        f"environment mismatch: the database at {target.database} holds accounts that user "
        f"pool {target.user_pool_id} does not know, so the tunnel and the AWS credentials "
        f"are not the same environment. Nothing was written, and --yes does not override "
        "this."
    )


def _sample_subjects(conn: Connection) -> Sequence[str]:
    """The newest subjects in the connected database, filter-safe ones only.

    A subject containing a quote or a backslash cannot be expressed in Cognito's
    ``ListUsers`` filter grammar. Such a subject can only have been written by
    something other than a real token, so it is skipped rather than escaped.
    """
    rows = conn.execute(
        select(app_user.c.user_id).order_by(desc(app_user.c.created_at)).limit(_SUB_SAMPLE * 2)
    ).scalars()
    return [sub for sub in rows if _filter_safe(sub)][:_SUB_SAMPLE]


def _pool_knows(
    cognito: CognitoIdentityProviderClient, *, pool_id: str, sub: str
) -> bool:
    response = cognito.list_users(UserPoolId=pool_id, Filter=f'sub = "{sub}"', Limit=1)
    return bool(response.get("Users"))


def _filter_safe(value: str) -> bool:
    """Whether a value can be embedded in a Cognito ``ListUsers`` filter literal."""
    return '"' not in value and "\\" not in value
