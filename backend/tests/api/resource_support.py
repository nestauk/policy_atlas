"""Shared dev-issuer client support for API resource-router tests."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import cast

from fastapi.testclient import TestClient

from policy_atlas.api.app import create_app
from policy_atlas.api.dev_issuer import init, mint_token
from policy_atlas.api.settings import Settings


@contextmanager
def api_client(
    tmp_path: Path,
    overrides: dict[Callable[..., object], Callable[..., object]] | None = None,
) -> Iterator[tuple[TestClient, dict[str, str], dict[str, str]]]:
    """Yield an application client and bearer headers for two distinct users.

    Args:
        tmp_path: Per-test temporary directory for a development issuer key.

    Yields:
        Client plus owner and other-user authorization headers.
    """
    key_dir = tmp_path / "issuer"
    settings = Settings(
        "http://dev-issuer.local",
        "resource-router-test",
        None,
        init(key_dir),
        "http://app.example.test",
        os.environ["DATABASE_URL"],
    )
    # Unique subs per client: the test DB is shared across the suite, and
    # owner-scoped listings would otherwise see other tests' projects.
    owner = mint_token(
        f"owner-{uuid.uuid4()}", settings.oidc_issuer, settings.oidc_client_id, 60, key_dir
    )
    other = mint_token(
        f"other-{uuid.uuid4()}", settings.oidc_issuer, settings.oidc_client_id, 60, key_dir
    )
    app = create_app(settings=settings)
    if overrides:
        app.dependency_overrides.update(overrides)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, {"Authorization": f"Bearer {owner}"}, {"Authorization": f"Bearer {other}"}


def create_project(client: TestClient, headers: dict[str, str]) -> str:
    """Create one ordinary project and return its public identity."""
    response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "Test project", "question": "What works?"},
    )
    assert response.status_code == 201, response.text
    return cast(str, response.json()["project_id"])
