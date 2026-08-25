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
from typing import Any

import boto3
from botocore.stub import Stubber
from mypy_boto3_cognito_idp.client import CognitoIdentityProviderClient

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
