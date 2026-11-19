"""Tests for the deploy-time operations database-login synchronisation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from structlog.testing import capture_logs

from policy_atlas.ops import db_role

_PASSWORD = "p@ss:w/rd#1&x"


class FakeSecretsManager:
    """Dictionary-backed fake retaining the exact JSON the sync replaces."""

    def __init__(self, value: Mapping[str, Any]) -> None:
        self.value = dict(value)

    def get_secret_value(self, *, SecretId: str) -> Mapping[str, Any]:
        """Return the fake's current complete secret JSON."""
        assert SecretId == "arn:aws:secretsmanager:region:account:secret:ops_db"
        return {"SecretString": json.dumps(self.value)}

    def put_secret_value(self, *, SecretId: str, SecretString: str) -> Mapping[str, Any]:
        """Replace the fake's complete secret JSON."""
        assert SecretId == "arn:aws:secretsmanager:region:account:secret:ops_db"
        self.value = json.loads(SecretString)
        return {}


def test_sync_sets_login_preserves_secret_and_does_not_log_credentials(engine: Engine) -> None:
    """The stored URL round-trips reserved characters and authenticates as pa_ops."""
    secret_arn = "arn:aws:secretsmanager:region:account:secret:ops_db"
    secrets = FakeSecretsManager({"username": "pa_ops", "password": _PASSWORD, "keep": "value"})
    # ``str(engine.url)`` hides the password; the sync needs the real master URL.
    master_url = engine.url.update_query_dict(
        {"application_name": "ops_db_role_test"}
    ).render_as_string(hide_password=False)
    with capture_logs() as logs:
        db_role.sync(database_url=master_url, secret_arn=secret_arn, secrets=secrets)

    connection_string = secrets.value["db_connection_string"]
    assert secrets.value["username"] == "pa_ops"
    assert secrets.value["password"] == _PASSWORD
    assert secrets.value["keep"] == "value"
    assert make_url(connection_string).password == _PASSWORD
    assert make_url(connection_string).query["application_name"] == "ops_db_role_test"
    role_engine = create_engine(connection_string)
    try:
        with role_engine.connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        role_engine.dispose()
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            connection.execute(text("ALTER ROLE pa_ops NOLOGIN"))

    rendered_logs = json.dumps(logs)
    assert _PASSWORD not in rendered_logs
    assert connection_string not in rendered_logs
