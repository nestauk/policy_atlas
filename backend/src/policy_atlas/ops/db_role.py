"""Synchronise the isolated operations database login from its secret."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

import boto3
import structlog
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

from policy_atlas.core.logging import configure_logging

_ROLE_NAME = "pa_ops"
log = structlog.get_logger()


class SecretsManager(Protocol):
    """The narrow Secrets Manager seam used by this module."""

    def get_secret_value(self, *, SecretId: str) -> Mapping[str, Any]:
        """Read one secret value."""

    def put_secret_value(self, *, SecretId: str, SecretString: str) -> Mapping[str, Any]:
        """Replace one secret value."""


def sync(*, database_url: str, secret_arn: str, secrets: SecretsManager) -> None:
    """Set the ops role password and store its connection URL in the secret.

    Args:
        database_url: Master SQLAlchemy database URL.
        secret_arn: ARN of the JSON secret holding the ops password.
        secrets: Secrets Manager client used to read and replace the full JSON value.

    Raises:
        ValueError: If the secret is not JSON containing a string password.
    """
    secret = _secret_json(secrets.get_secret_value(SecretId=secret_arn))
    password = secret.get("password")
    if not isinstance(password, str) or not password:
        raise ValueError("ops database secret must contain a non-empty password")

    master_url = make_url(database_url)
    engine = create_engine(master_url)
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            driver_connection = connection.connection.driver_connection
            assert driver_connection is not None
            driver_connection.execute(
                sql.SQL("ALTER ROLE pa_ops LOGIN PASSWORD {}").format(sql.Literal(password))
            )
    finally:
        engine.dispose()

    ops_url = URL.create(
        drivername=master_url.drivername,
        username=_ROLE_NAME,
        password=password,
        host=master_url.host,
        port=master_url.port,
        database=master_url.database,
        query=dict(master_url.query),
    ).render_as_string(hide_password=False)
    secret["db_connection_string"] = ops_url
    secrets.put_secret_value(SecretId=secret_arn, SecretString=json.dumps(secret))
    log.info("ops.db_role_synced", secret_name=_secret_name(secret_arn), role=_ROLE_NAME)


def check(*, secret_arn: str, secrets: SecretsManager) -> None:
    """Connect as the stored ops login and issue a minimal query.

    Args:
        secret_arn: ARN of the JSON secret holding the generated URL.
        secrets: Secrets Manager client used to read the secret.

    Raises:
        ValueError: If the secret does not contain an ops connection URL.
    """
    secret = _secret_json(secrets.get_secret_value(SecretId=secret_arn))
    connection_string = secret.get("db_connection_string")
    if not isinstance(connection_string, str) or not connection_string:
        raise ValueError("ops database secret must contain db_connection_string")
    engine = create_engine(connection_string)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    finally:
        engine.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    """Run the database-role synchronisation or its connectivity check.

    Args:
        argv: Command-line arguments excluding the program name.

    Returns:
        Zero on success and one when the requested operation fails.
    """
    configure_logging()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("sync", "check"))
    arguments = parser.parse_args(argv)
    secret_arn = _required_environment("OPS_DB_SECRET_ARN")
    secrets: SecretsManager = boto3.client("secretsmanager")
    try:
        if arguments.command == "sync":
            sync(
                database_url=_required_environment("DATABASE_URL"),
                secret_arn=secret_arn,
                secrets=secrets,
            )
        else:
            check(secret_arn=secret_arn, secrets=secrets)
    except Exception as error:  # noqa: BLE001 - the command must return a safe failure status
        # The class names the cause; the message could carry the URL, so it stays out.
        log.error(
            "ops.db_role_failed",
            secret_name=_secret_name(secret_arn),
            role=_ROLE_NAME,
            error_class=type(error).__name__,
        )
        return 1
    return 0


def _secret_json(response: Mapping[str, Any]) -> dict[str, Any]:
    """Decode the complete JSON value returned by Secrets Manager."""
    secret_string = response.get("SecretString")
    if not isinstance(secret_string, str):
        raise ValueError("ops database secret must have a SecretString")
    decoded = json.loads(secret_string)
    if not isinstance(decoded, dict):
        raise ValueError("ops database secret must be a JSON object")
    return decoded


def _required_environment(name: str) -> str:
    """Return a required, non-empty environment value."""
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"{name} environment variable is required")
    return value


def _secret_name(secret_arn: str) -> str:
    """Return only the name component of a secret ARN for safe logging."""
    return secret_arn.rsplit(":", maxsplit=1)[-1]


if __name__ == "__main__":  # pragma: no cover - exercised through the module entrypoint
    raise SystemExit(main())
