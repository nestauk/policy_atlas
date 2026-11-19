"""Route-table and lifespan boundaries for the isolated operations service."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Literal
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.engine import Engine

import policy_atlas.api.app as app_module
import policy_atlas.api.deps as deps_module
from policy_atlas.api import continuation
from policy_atlas.api.app import create_app
from policy_atlas.api.dev_issuer import init, mint_token
from policy_atlas.api.settings import Settings
from policy_atlas.core.schema import app_user
from tests.api.org_support import Principal, ops_enrol, seeded


def _settings(
    tmp_path: Path, *, service_role: Literal["api", "ops"], ops_ui_dir: Path | None
) -> Settings:
    """Build explicit settings for one service-role application."""
    return Settings(
        "http://dev-issuer.local",
        "service-role-test",
        None,
        init(tmp_path / "issuer"),
        "http://app.example.test",
        os.environ["DATABASE_URL"],
        service_role=service_role,
        ops_ui_dir=ops_ui_dir,
    )


def _ui_bundle(tmp_path: Path) -> Path:
    """Write the minimal built operations UI used by static-route tests."""
    ui_dir = tmp_path / "ops-ui"
    (ui_dir / "assets").mkdir(parents=True)
    (ui_dir / "index.html").write_text("<main>ops</main>", encoding="utf-8")
    (ui_dir / "assets" / "app-abc.js").write_text("export {}", encoding="utf-8")
    (ui_dir / "favicon.svg").write_text("<svg />", encoding="utf-8")
    return ui_dir


def _route_paths(app: FastAPI) -> set[str]:
    """Flatten FastAPI's included routers into their route paths."""
    paths: set[str] = set()
    for route in app.routes:
        if isinstance(route, APIRoute):
            paths.add(route.path)
        else:
            router = getattr(route, "original_router", None)
            if router is not None:
                paths.update(_route_paths(router))
    return paths


@contextmanager
def _ops_client(tmp_path: Path, *, ui_dir: Path | None) -> Iterator[tuple[TestClient, Principal]]:
    """Yield an operations client and one signed-in caller for route tests."""
    settings = _settings(tmp_path, service_role="ops", ops_ui_dir=ui_dir)
    user_id = f"ops-user-{uuid.uuid4()}"
    token = mint_token(
        user_id, settings.oidc_issuer, settings.oidc_client_id, 600, tmp_path / "issuer"
    )
    with TestClient(create_app(settings=settings), raise_server_exceptions=False) as client:
        yield client, Principal(user_id, {"Authorization": f"Bearer {token}"})


def test_api_mode_excludes_ops_routes_and_static_bundle(tmp_path: Path) -> None:
    """The public API mounts neither operations routes nor its UI bundle."""
    app = create_app(
        settings=_settings(
            tmp_path, service_role="api", ops_ui_dir=_ui_bundle(tmp_path)
        )
    )
    paths = _route_paths(app)

    assert not any(path.startswith("/api/v1/ops") for path in paths)
    assert "/api/v1/me" in paths
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get("/people").json()["error"]["code"] == "not_found"
        assert client.get("/assets/x.js").status_code == 404


def test_ops_mode_has_only_ops_and_health_api_routes(tmp_path: Path) -> None:
    """The ops route table excludes product and account-creating routes."""
    app = create_app(
        settings=_settings(
            tmp_path, service_role="ops", ops_ui_dir=_ui_bundle(tmp_path)
        )
    )
    paths = _route_paths(app)

    assert "/healthz" in paths
    assert "/readyz" in paths
    assert "/api/v1/ops/organisations" in paths
    assert "/api/v1/me" not in paths
    assert not any(path.startswith("/api/v1/tasks") for path in paths)
    assert not any(path.startswith("/api/v1/projects") for path in paths)
    assert not any(path.startswith("/api/v1/runs") for path in paths)
    assert "/api/v1/tasks/{task_id}/events" not in paths


def test_ops_mode_serves_pages_assets_and_rejects_api_fallback(tmp_path: Path) -> None:
    """The SPA fallback is last, serves only contained direct files, and hides APIs."""
    with _ops_client(tmp_path, ui_dir=_ui_bundle(tmp_path)) as (client, _principal):
        for path in ("/", "/people", "/people/abc/quota"):
            response = client.get(path)
            assert response.status_code == 200
            assert response.text == "<main>ops</main>"
            assert response.headers["content-type"].startswith("text/html")
        assert "javascript" in client.get("/assets/app-abc.js").headers["content-type"]
        assert client.get("/favicon.svg").text == "<svg />"
        assert client.get("/api/v1/tasks").json()["error"]["code"] == "not_found"
        assert client.get("/api/v1/me").status_code == 404
        escaped = client.get("/../../etc/passwd")
        assert escaped.status_code in {200, 404}
        if escaped.status_code == 200:
            assert escaped.text == "<main>ops</main>"


def test_ops_mode_starts_without_a_ui_bundle(tmp_path: Path) -> None:
    """A missing build does not prevent health checks or accidentally serve pages."""
    with _ops_client(tmp_path, ui_dir=tmp_path / "absent") as (client, _principal):
        assert client.get("/people").status_code == 404


def test_ops_lifespan_does_not_start_api_work(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only the API role starts the executor, key warning, and continuation sweep."""
    del engine
    executor = MagicMock(spec=ThreadPoolExecutor)
    sweep = MagicMock()
    warning = MagicMock()
    monkeypatch.setattr(app_module, "ThreadPoolExecutor", executor)
    monkeypatch.setattr(continuation, "startup_sweep", sweep)
    monkeypatch.setattr(deps_module, "warn_on_partial_live_keys", warning)

    ops_app = create_app(
        settings=_settings(
            tmp_path / "ops",
            service_role="ops",
            ops_ui_dir=_ui_bundle(tmp_path / "ops"),
        )
    )
    with TestClient(ops_app):
        assert not hasattr(ops_app.state, "run_executor")
    executor.assert_not_called()
    sweep.assert_not_called()
    warning.assert_not_called()

    api_app = create_app(
        settings=_settings(
            tmp_path / "api",
            service_role="api",
            ops_ui_dir=_ui_bundle(tmp_path / "api"),
        )
    )
    with TestClient(api_app):
        pass
    sweep.assert_called_once()


@pytest.mark.parametrize("enabled", [False, True])
def test_ops_self_signup_task_is_optional_and_cancelled(tmp_path: Path, enabled: bool) -> None:
    """The optional sweep task is created only when enabled and stops before disposal."""
    settings = _settings(tmp_path, service_role="ops", ops_ui_dir=_ui_bundle(tmp_path))
    settings = replace(settings, self_signup_enabled=enabled)
    app = create_app(settings=settings)
    with TestClient(app):
        task = getattr(app.state, "sweep_task", None)
        assert (task is not None) is enabled
    if enabled:
        assert task is not None
        assert task.cancelled()
        assert task.done()


def test_require_ops_refuses_missing_non_ops_and_unknown_users(
    engine: Engine, tmp_path: Path
) -> None:
    """The stub route authenticates first and never creates a user row."""
    with _ops_client(tmp_path, ui_dir=_ui_bundle(tmp_path)) as (client, principal):
        assert client.get("/api/v1/ops/organisations").status_code == 401
        with engine.connect() as conn:
            before = conn.execute(select(func.count()).select_from(app_user)).scalar_one()
        response = client.get("/api/v1/ops/organisations", headers=principal.headers)
        with engine.connect() as conn:
            after = conn.execute(select(func.count()).select_from(app_user)).scalar_one()
        assert response.status_code == 403
        assert after == before


def test_require_ops_allows_only_an_ops_row(engine: Engine, tmp_path: Path) -> None:
    """The operations role is read from the existing identity row only."""
    with _ops_client(tmp_path, ui_dir=_ui_bundle(tmp_path)) as (client, principal):
        with seeded(engine) as conn:
            ops_enrol(conn, user_id=principal.user_id)
        response = client.get("/api/v1/ops/organisations", headers=principal.headers)
        assert response.status_code == 403
        with seeded(engine) as conn:
            conn.execute(
                update(app_user)
                .where(app_user.c.user_id == principal.user_id)
                .values(is_ops=True)
            )
        response = client.get("/api/v1/ops/organisations", headers=principal.headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
