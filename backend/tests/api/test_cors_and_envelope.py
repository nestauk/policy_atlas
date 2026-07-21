"""CORS, health, validation and opaque-error boundary tests."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy.engine import Engine

from policy_atlas.api.app import create_app
from policy_atlas.api.auth import AuthenticatedUser, get_current_user
from policy_atlas.api.dev_issuer import init, mint_token
from policy_atlas.api.settings import Settings


class _Payload(BaseModel):
    """Minimal request model for validating the 422 envelope shape."""

    count: int


def test_cors_health_validation_and_opaque_errors(engine: Engine, tmp_path: Path) -> None:
    """Exercise the HTTP-wide constraints around a normal protected route."""
    del engine
    key_dir = tmp_path / "issuer"
    settings = Settings(
        "http://dev-issuer.local",
        "cors-test",
        None,
        init(key_dir),
        "http://app.example.test",
        os.environ["DATABASE_URL"],
    )
    token = mint_token("user", settings.oidc_issuer, settings.oidc_client_id, 60, key_dir)
    headers = {"Authorization": f"Bearer {token}"}

    with _client(settings) as client:
        allowed = client.options(
            "/probe",
            headers={
                "Origin": settings.app_origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert allowed.status_code == 200
        assert allowed.headers["access-control-allow-origin"] == settings.app_origin
        denied = client.options(
            "/probe",
            headers={"Origin": "http://other.example.test", "Access-Control-Request-Method": "GET"},
        )
        assert "access-control-allow-origin" not in denied.headers

        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 200
        _assert_unauthenticated(client.get("/probe"))

        validation = client.post("/validate", headers=headers, json={"count": "not-an-int"})
        assert validation.status_code == 422
        error = validation.json()["error"]
        assert error["code"] == "validation_error"
        assert error["details"][0]["loc"] == ["body", "count"]
        assert error["details"][0]["type"]

        failure = client.get("/boom", headers=headers)
        assert failure.status_code == 500
        assert failure.json()["error"]["code"] == "internal"
        assert "Traceback" not in failure.text
        assert "intentional test error" not in failure.text


@contextmanager
def _client(settings: Settings) -> Iterator[TestClient]:
    """Run a small D.3-like protected surface with the real application lifespan."""
    router = APIRouter()

    @router.get("/probe")
    def probe(_: Annotated[AuthenticatedUser, Depends(get_current_user)]) -> dict[str, str]:
        """Provide one protected endpoint for generic boundary assertions."""
        return {"status": "ok"}

    @router.post("/validate")
    def validate(
        _: Annotated[AuthenticatedUser, Depends(get_current_user)],
        payload: Annotated[_Payload, Body()],
    ) -> dict[str, int]:
        """Require a validated payload to exercise FastAPI's validation handler."""
        return {"count": payload.count}

    @router.get("/boom")
    def boom(_: Annotated[AuthenticatedUser, Depends(get_current_user)]) -> None:
        """Raise an internal exception to prove opaque error serialisation."""
        raise RuntimeError("intentional test error")

    app = create_app(settings=settings, routers=(router,))
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def _assert_unauthenticated(response: Any) -> None:
    """Assert missing bearer authentication uses the common error envelope."""
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "unauthenticated"
