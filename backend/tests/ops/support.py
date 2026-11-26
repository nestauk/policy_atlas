"""Stubbed AWS for the operator CLI's tests — no real call is ever made.

Two different shapes, chosen for two different reasons.

**Cognito is the real client behind a :class:`botocore.stub.Stubber`.** The
identity-provider calls are the ones whose *parameters* are load-bearing —
rubric 28 turns on ``DesiredDeliveryMediums=["EMAIL"]`` actually being sent, and
a hand-written fake would only prove that the test and the code agree with each
other. Stubber validates the outgoing parameters against botocore's own service
model and short-circuits before anything is signed or sent, so the assertion is
against the real API shape. The suite also runs under ``pytest-socket``'s
``--disable-socket``: if any of this ever did reach the network, the test would
fail loudly rather than quietly cost money.

**STS is a four-line fake.** ``boto3-stubs`` ships only the ``cognito-idp``
service package (contract § 10), so there is no typed client to stub and no
parameters worth validating — ``GetCallerIdentity`` takes none.
:class:`policy_atlas.ops.environment.StsClient` exists precisely so this can be
an object with one method.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.stub import ANY, Stubber
from mypy_boto3_cognito_idp.client import CognitoIdentityProviderClient
from sqlalchemy import insert
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import app_user, cohort, cohort_member, organisation
from policy_atlas.ops.announcements import Audience

#: A pool id shaped like a real one. Never reached — the Stubber answers first.
POOL_ID = "eu-west-2_TESTPOOL1"

#: The account the fake STS client claims by default.
ACCOUNT_ID = "111122223333"

#: The principal the fake STS client reports, and therefore the default
#: operator identity on the admin trace.
CALLER_ARN = "arn:aws:sts::111122223333:assumed-role/Operator/alice"


class FakeSts:
    """The whole of the STS surface this CLI uses.

    Attributes:
        account: What ``GetCallerIdentity`` reports as ``Account``.
        arn: What it reports as ``Arn`` — the default operator on the trace.
    """

    def __init__(self, account: str = ACCOUNT_ID, arn: str = CALLER_ARN) -> None:
        self.account = account
        self.arn = arn

    def get_caller_identity(self) -> Mapping[str, Any]:
        """Return the calling identity."""
        return {"Account": self.account, "Arn": self.arn, "UserId": "AIDATEST"}


@contextmanager
def cognito() -> Iterator[tuple[CognitoIdentityProviderClient, Stubber]]:
    """Yield a stubbed Cognito client and its queue.

    Credentials are explicit dummies so no credential chain is walked — an
    instance-metadata lookup would be a socket call, and the suite forbids
    those.

    Yields:
        The client to hand to a command, and the stubber to queue responses on.
    """
    client: CognitoIdentityProviderClient = boto3.client(
        "cognito-idp",
        region_name="eu-west-2",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )
    stubber = Stubber(client)
    stubber.activate()
    try:
        yield client, stubber
    finally:
        stubber.deactivate()


def expect_lookup(stubber: Stubber, *, email: str, sub: str | None) -> None:
    """Queue one ``ListUsers`` by address, answering with ``sub`` or nothing."""
    users: list[dict[str, Any]] = []
    if sub is not None:
        users = [{"Username": sub, "Attributes": [{"Name": "sub", "Value": sub}]}]
    stubber.add_response(
        "list_users",
        {"Users": users},
        {"UserPoolId": POOL_ID, "Filter": f'email = "{email}"', "Limit": 1},
    )


def expect_enabled(stubber: Stubber, *, sub: str, enabled: bool = True) -> None:
    """Queue the ``AdminGetUser`` that reads whether an existing account can sign in."""
    stubber.add_response(
        "admin_get_user",
        {"Username": sub, "Enabled": enabled},
        {"UserPoolId": POOL_ID, "Username": sub},
    )


def expect_status_lookup(stubber: Stubber, *, email: str, sub: str, status: str) -> None:
    """Queue one ``ListUsers`` by address answering with an account in ``status``.

    ``Username`` is the subject, as it is in a pool whose sign-in alias is the
    email: the reissue must address the account by it, not by the address.
    """
    stubber.add_response(
        "list_users",
        {
            "Users": [
                {
                    "Username": sub,
                    "UserStatus": status,
                    "Attributes": [{"Name": "sub", "Value": sub}],
                }
            ]
        },
        {"UserPoolId": POOL_ID, "Filter": f'email = "{email}"', "Limit": 1},
    )


def expect_reissue(stubber: Stubber, *, sub: str) -> None:
    """Queue the ``AdminSetUserPassword`` of ``user reissue``.

    ``Password`` is ``ANY`` because the CLI mints it; ``Permanent: False`` is
    exact-matched, so a reissue that skipped the forced change fails here.
    """
    stubber.add_response(
        "admin_set_user_password",
        {},
        {"UserPoolId": POOL_ID, "Username": sub, "Password": ANY, "Permanent": False},
    )


def expect_create_manual(stubber: Stubber, *, email: str, sub: str) -> None:
    """Queue the suppressed-invitation ``AdminCreateUser`` of ``--invite manual``.

    ``TemporaryPassword`` is ``ANY`` because the CLI mints it (never accepts
    one — rubric 30 stands); ``MessageAction: SUPPRESS`` and the ABSENCE of
    ``DesiredDeliveryMediums`` are exact-matched, so an email leaking out of
    manual mode fails here.
    """
    stubber.add_response(
        "admin_create_user",
        {"User": {"Username": sub, "Attributes": [{"Name": "sub", "Value": sub}]}},
        {
            "UserPoolId": POOL_ID,
            "Username": email,
            "UserAttributes": [
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "true"},
            ],
            "TemporaryPassword": ANY,
            "MessageAction": "SUPPRESS",
        },
    )


def expect_create(stubber: Stubber, *, email: str, sub: str) -> None:
    """Queue the ``AdminCreateUser`` the CLI must send, parameters and all.

    The expected-parameter dict is the assertion for rubric 28: Stubber raises
    if the call differs in any key, so ``DesiredDeliveryMediums=["EMAIL"]``
    being dropped — leaving AWS to default it to SMS against a pool with no
    phone numbers — fails here. So does any password parameter appearing, and
    so does ``MessageAction: SUPPRESS``, which is what the deleted make target
    sent.
    """
    stubber.add_response(
        "admin_create_user",
        {"User": {"Username": sub, "Attributes": [{"Name": "sub", "Value": sub}]}},
        {
            "UserPoolId": POOL_ID,
            "Username": email,
            "UserAttributes": [
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "true"},
            ],
            "DesiredDeliveryMediums": ["EMAIL"],
        },
    )


def expect_environment(
    stubber: Stubber, *, known_subs: Sequence[str] = (), sampled: Sequence[str] = ()
) -> None:
    """Queue the calls :func:`~policy_atlas.ops.environment.verify_environment` makes.

    Args:
        stubber: The queue.
        known_subs: Subjects the pool will admit to knowing.
        sampled: The subjects the check will sample, in order — normally the
            newest ``app_user`` rows in the connected database. The queue stops
            at the first one the pool knows, because the check does.
    """
    stubber.add_response("list_users", {"Users": []}, {"UserPoolId": POOL_ID, "Limit": 1})
    for sub in sampled:
        known = sub in known_subs
        users: list[dict[str, Any]] = (
            [{"Username": sub, "Attributes": [{"Name": "sub", "Value": sub}]}] if known else []
        )
        stubber.add_response(
            "list_users",
            {"Users": users},
            {"UserPoolId": POOL_ID, "Filter": f'sub = "{sub}"', "Limit": 1},
        )
        if known:
            return


def fresh_sub(label: str = "ops") -> str:
    """Mint a subject unique across the shared test database."""
    return f"{label}-{uuid.uuid4()}"


def expect_sub_lookup(
    stubber: Stubber, *, sub: str, status: str | None = None, email: str | None = None
) -> None:
    """Queue one ``ListUsers`` by subject, answering with the account (and its status).

    ``Username`` is the subject, as in a pool whose sign-in alias is the email;
    the resend addresses the account by it. ``email``, when given, is the
    account's address attribute in the pool.
    """
    user: dict[str, Any] = {"Username": sub, "Attributes": [{"Name": "sub", "Value": sub}]}
    if email is not None:
        user["Attributes"].append({"Name": "email", "Value": email})
    if status is not None:
        user["UserStatus"] = status
    stubber.add_response(
        "list_users",
        {"Users": [user]},
        {"UserPoolId": POOL_ID, "Filter": f'sub = "{sub}"', "Limit": 1},
    )


def expect_resend(stubber: Stubber, *, username: str) -> None:
    """Queue the ``AdminCreateUser`` of a resent invitation (task 065, B4).

    ``MessageAction: RESEND`` and ``DesiredDeliveryMediums: ["EMAIL"]`` are
    exact-matched, and so is the ABSENCE of ``UserAttributes`` and of any
    password parameter: a resend that re-created the account fails here.
    """
    stubber.add_response(
        "admin_create_user",
        {"User": {"Username": username}},
        {
            "UserPoolId": POOL_ID,
            "Username": username,
            "MessageAction": "RESEND",
            "DesiredDeliveryMediums": ["EMAIL"],
        },
    )


def expect_lock_out(stubber: Stubber, *, sub: str) -> None:
    """Queue the disable then the global sign-out of ``user deactivate``, in that order."""
    for operation in ("admin_disable_user", "admin_user_global_sign_out"):
        stubber.add_response(operation, {}, {"UserPoolId": POOL_ID, "Username": sub})


def add_person(
    conn: Connection,
    *,
    name: str = "Example Person",
    email: str | None = "",
    org_id: uuid.UUID | None = None,
    signed_in: bool = True,
    unsubscribed: bool = False,
    deactivated: bool = False,
) -> str:
    """Insert one account and return its subject.

    Args:
        conn: Open database connection.
        name: The display name.
        email: The address; the default ``""`` mints a unique ``example.org``
            address, ``None`` leaves the account without one.
        org_id: The person's organisation, if any.
        signed_in: Whether the person has signed in at least once.
        unsubscribed: Whether the person stopped product updates.
        deactivated: Whether the account is deactivated.
    """
    user_id = fresh_sub("person")
    at = datetime.now(UTC)
    conn.execute(
        insert(app_user).values(
            user_id=user_id,
            org_id=org_id,
            display_name=name,
            email=f"{user_id}@example.org" if email == "" else email,
            created_at=at,
            first_signed_in_at=at if signed_in else None,
            updates_unsubscribed_at=at if unsubscribed else None,
            deactivated_at=at if deactivated else None,
        )
    )
    return user_id


@dataclass(frozen=True)
class AnnouncementExample:
    """The design annex's example audience, as stored rows.

    Cohort "Spring pilot" (18 people) and organisation "Nesta" (64 people), one
    person in both, plus Tomás Ferreira in neither: 82 chosen. Two of them
    unsubscribed from product updates and one is deactivated; all have signed in.
    Names carry a unique suffix because both names are unique in the database.

    Attributes:
        cohort_id: The cohort.
        cohort_name: Its stored name.
        org_id: The organisation.
        org_name: Its stored name.
        tomas: Tomás Ferreira's subject.
        in_both: The subject of the person in the cohort and the organisation.
        unsubscribed: The two people who stopped product updates.
        deactivated: The deactivated person.
        people: All 82 subjects.
    """

    cohort_id: uuid.UUID
    cohort_name: str
    org_id: uuid.UUID
    org_name: str
    tomas: str
    in_both: str
    unsubscribed: tuple[str, str]
    deactivated: str
    people: tuple[str, ...]

    @property
    def audience(self) -> Audience:
        """The operator's choice: the cohort, the organisation and Tomás."""
        return Audience(
            cohort_ids=(self.cohort_id,), org_ids=(self.org_id,), user_ids=(self.tomas,)
        )


def announcement_example(conn: Connection) -> AnnouncementExample:
    """Insert the design annex's example audience and return its ids."""
    at = datetime.now(UTC)
    suffix = uuid.uuid4().hex[:8]
    org_id, cohort_id = uuid.uuid4(), uuid.uuid4()
    org_name, cohort_name = f"Nesta {suffix}", f"Spring pilot {suffix}"
    conn.execute(insert(organisation).values(org_id=org_id, name=org_name, created_at=at))
    conn.execute(insert(cohort).values(cohort_id=cohort_id, name=cohort_name, created_at=at))
    staff = [
        add_person(conn, name=f"Nesta person {n}", org_id=org_id, unsubscribed=n in (1, 2),
                   deactivated=n == 3)
        for n in range(64)
    ]
    pilot = [add_person(conn, name=f"Pilot person {n}") for n in range(17)] + [staff[0]]
    conn.execute(
        insert(cohort_member),
        [{"cohort_id": cohort_id, "user_id": user_id, "added_at": at} for user_id in pilot],
    )
    tomas = add_person(conn, name="Tomás Ferreira")
    return AnnouncementExample(
        cohort_id=cohort_id,
        cohort_name=cohort_name,
        org_id=org_id,
        org_name=org_name,
        tomas=tomas,
        in_both=staff[0],
        unsubscribed=(staff[1], staff[2]),
        deactivated=staff[3],
        people=tuple(staff + pilot[:-1] + [tomas]),
    )
