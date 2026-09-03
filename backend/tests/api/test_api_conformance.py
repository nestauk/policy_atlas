"""Conformance sweep over the as-built `/api/v1` surface.

Table-driven checks against `docs/specs/system/web-api.md` § Error envelope
and § Pagination: the pagination envelope shape and cap, every error-envelope
code class reachable from real routes, OpenAPI naming hygiene (plural/lower
segments, snake_case properties, no leaked internal names), and a
`response_model` whitelist spot check guarding against ORM leakage.
"""

from __future__ import annotations

import re
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.routing import APIRoute
from sqlalchemy.engine import Engine

from policy_atlas.api.app import create_app
from policy_atlas.api.contract import PAGE_SIZE_DEFAULT, ProjectOut
from policy_atlas.api.dev_issuer import init
from policy_atlas.api.settings import Settings
from policy_atlas.core.schema import capability_run, evidence_scope
from tests.api.resource_support import api_client, create_project

# Routes that intentionally sit outside the bearer-token boundary: process
# liveness/readiness probes, checked before any orchestration or auth I/O.
# `/api/v1/waitlist` is the splash-page Request-access intake — the first
# intentional public write. Health probes sit outside `/api/v1`.
_UNAUTHENTICATED_ALLOWLIST = frozenset({"/healthz", "/readyz", "/api/v1/waitlist"})

# --- Pagination conformance --------------------------------------------------


def test_pagination_envelope_shape_and_defaults(engine: Engine, tmp_path: Path) -> None:
    """List routes return exactly `{data, pagination:{page, page_size, total_items}}`."""
    del engine  # forces the session migration fixture before any request hits the DB
    with api_client(tmp_path) as (client, owner, _other):
        project_id = create_project(client, owner)
        listed = client.get("/api/v1/projects", headers=owner)
        assert listed.status_code == 200
        body = listed.json()
        assert set(body) == {"data", "pagination"}
        assert set(body["pagination"]) == {"page", "page_size", "total_items"}
        assert body["pagination"]["page"] == 1
        assert body["pagination"]["page_size"] == PAGE_SIZE_DEFAULT
        assert body["pagination"]["total_items"] == 1
        assert body["data"][0]["project_id"] == project_id


def test_pagination_respects_page_size_across_pages(tmp_path: Path) -> None:
    """`page_size` is honoured: three projects paged at two yield 2 then 1."""
    with api_client(tmp_path) as (client, owner, _other):
        for _ in range(3):
            create_project(client, owner)

        first = client.get("/api/v1/projects?page=1&page_size=2", headers=owner)
        assert first.status_code == 200
        assert first.json()["pagination"] == {"page": 1, "page_size": 2, "total_items": 3}
        assert len(first.json()["data"]) == 2

        second = client.get("/api/v1/projects?page=2&page_size=2", headers=owner)
        assert second.status_code == 200
        assert second.json()["pagination"] == {"page": 2, "page_size": 2, "total_items": 3}
        assert len(second.json()["data"]) == 1


def test_pagination_rejects_page_size_over_the_server_cap(tmp_path: Path) -> None:
    """A `page_size` above the 200 cap is a 422 `validation_error` envelope."""
    with api_client(tmp_path) as (client, owner, _other):
        response = client.get("/api/v1/projects?page_size=201", headers=owner)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"


# --- Error-envelope conformance ----------------------------------------------


def _flatten_api_routes(routes: Any) -> list[APIRoute]:
    """Recursively flatten `app.routes` into leaf `APIRoute`s.

    This FastAPI version represents an included router as a lazy
    `_IncludedRouter` wrapper rather than inlining its routes directly into
    `app.routes`, so a plain `isinstance(route, APIRoute)` filter over
    `app.routes` silently sees zero routes. Duck-type on `original_router`
    (rather than importing the private `_IncludedRouter` class) to recurse
    into it regardless of FastAPI's internal representation.
    """
    flattened: list[APIRoute] = []
    for route in routes:
        if isinstance(route, APIRoute):
            flattened.append(route)
            continue
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            flattened.extend(_flatten_api_routes(original_router.routes))
    return flattened


def _api_v1_route_cases() -> list[tuple[str, str]]:
    """Every (method, path-template) pair for real `/api/v1` routes.

    Built once, at import time, straight off the live FastAPI route table
    (`app.routes`) rather than a hand-maintained list, so a future route
    that forgets `get_current_user` fails the sweep below instead of
    silently shipping unauthenticated. No lifespan runs and no DB is
    touched: `create_app` only needs a filesystem JWKS key pair to build.
    """
    with tempfile.TemporaryDirectory(prefix="policy-atlas-route-sweep-") as tmp_dir:
        key_dir = Path(tmp_dir) / "issuer"
        settings = Settings(
            "http://dev-issuer.local",
            "route-sweep-conformance-test",
            None,
            init(key_dir),
            "http://app.example.test",
            "postgresql+psycopg://unused/unused",
        )
        app = create_app(settings=settings)
        cases: list[tuple[str, str]] = []
        for route in _flatten_api_routes(app.routes):
            if not route.path.startswith("/api/v1") or route.path in _UNAUTHENTICATED_ALLOWLIST:
                continue
            for method in sorted((route.methods or set()) - {"HEAD", "OPTIONS"}):
                cases.append((method, route.path))
        return cases


def _fill_path_params(path_template: str) -> str:
    """Replace every `{param}` segment in a route path with a dummy UUID."""
    return re.sub(r"\{[^}]+\}", lambda _: str(uuid.uuid4()), path_template)


def _fill_non_project_path_params(path_template: str) -> str:
    """Replace every path param except `{project_id}` with a dummy UUID.

    Leaves the `{project_id}` placeholder intact so the caller can format it
    separately with an absent-vs-cross-owner project id.
    """

    def _replace(match: re.Match[str]) -> str:
        token = match.group(0)
        return token if token == "{project_id}" else str(uuid.uuid4())

    return re.sub(r"\{[^}]+\}", _replace, path_template)


_UNAUTHENTICATED_CASES = _api_v1_route_cases()

_PROJECT_SCOPED_GET_CASES = [
    (method, path)
    for method, path in _UNAUTHENTICATED_CASES
    if method == "GET" and "{project_id}" in path
]


@pytest.mark.parametrize(
    "method,path_template",
    _UNAUTHENTICATED_CASES,
    ids=[f"{method} {path}" for method, path in _UNAUTHENTICATED_CASES],
)
def test_every_api_v1_route_is_unauthenticated_without_a_token(
    tmp_path: Path, method: str, path_template: str
) -> None:
    """Every real `/api/v1` route gives the same 401 envelope and bearer challenge.

    Bodies are `{}` for routes that expect one: 401 must win before any
    request-body validation runs.
    """
    path = _fill_path_params(path_template)
    json_body: dict[str, Any] | None = {} if method in {"POST", "PATCH", "PUT", "DELETE"} else None
    with api_client(tmp_path) as (client, _owner, _other):
        response = client.request(method, path, json=json_body)
        assert response.status_code == 401, (
            f"{method} {path_template} did not 401: {response.status_code} {response.text}"
        )
        assert response.headers["WWW-Authenticate"] == "Bearer"
        body = response.json()
        assert set(body) == {"error"}
        assert set(body["error"]) == {"code", "message"}
        assert body["error"]["code"] == "unauthenticated"


@pytest.mark.parametrize(
    "path_template",
    [path for _, path in _PROJECT_SCOPED_GET_CASES],
    ids=[path for _, path in _PROJECT_SCOPED_GET_CASES],
)
def test_project_scoped_get_routes_hide_ownership_with_byte_identical_404(
    tmp_path: Path, path_template: str
) -> None:
    """404 `not_found` hides ownership on every project-scoped GET route.

    Non-GET routes under `/api/v1/projects/{project_id}...` are skipped here
    (see `_PROJECT_SCOPED_GET_CASES`): their absent/foreign-project 404s are
    covered by mutation-path tests elsewhere (e.g. the archive conflict test
    below), not by this byte-identical read sweep.
    """
    templated = _fill_non_project_path_params(path_template)
    with api_client(tmp_path) as (client, owner, other):
        project_id = create_project(client, owner)

        never_existed = client.get(templated.format(project_id=uuid.uuid4()), headers=other)
        cross_owner = client.get(templated.format(project_id=project_id), headers=other)

        assert never_existed.status_code == cross_owner.status_code == 404, (
            f"{path_template}: expected 404/404, got "
            f"{never_existed.status_code}/{cross_owner.status_code}"
        )
        assert never_existed.content == cross_owner.content, path_template
        assert never_existed.json()["error"]["code"] == "not_found"


def test_validation_error_details_carry_loc_and_type(tmp_path: Path) -> None:
    """422 `validation_error` preserves a `details` list keyed by `loc`/`type`."""
    with api_client(tmp_path) as (client, owner, _other):
        response = client.get("/api/v1/projects?page_size=201", headers=owner)
        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "validation_error"
        details = error["details"]
        assert isinstance(details, list)
        assert len(details) >= 1
        for detail in details:
            assert set(detail) == {"loc", "type"}


def test_archive_while_a_run_is_active_is_run_active_conflict(
    engine: Engine, tmp_path: Path
) -> None:
    """409 `run_active`: archiving a project with a running capability_run row conflicts."""
    with api_client(tmp_path) as (client, owner, _other):
        project_id = create_project(client, owner)
        run_id = uuid.uuid4()
        with engine.begin() as conn:
            scope_id = uuid.uuid4()
            conn.execute(
                evidence_scope.insert().values(
                    evidence_scope_id=scope_id,
                    project_id=uuid.UUID(project_id),
                    intent="conformance sweep",
                    context={},
                    created_at=datetime.now(UTC),
                )
            )
            conn.execute(
                capability_run.insert().values(
                    capability_run_id=run_id,
                    project_id=uuid.UUID(project_id),
                    evidence_scope_id=scope_id,
                    capability="evidence_base",
                    plan_id=uuid.uuid4(),
                    plan_version=1,
                    status="running",
                    session_id=None,
                    started_at=datetime.now(UTC),
                    ended_at=None,
                )
            )
        try:
            response = client.post(f"/api/v1/projects/{project_id}/archive", headers=owner)
            assert response.status_code == 409
            assert response.json()["error"]["code"] == "run_active"
        finally:
            # Leave no `running` row behind: a later test's fresh app lifespan runs
            # the orphan-sweep startup check over every `running` row in the shared
            # test DB, and this row was inserted directly, without an attaching event.
            with engine.begin() as conn:
                conn.execute(
                    capability_run.update()
                    .where(capability_run.c.capability_run_id == run_id)
                    .values(status="aborted", ended_at=datetime.now(UTC))
                )


# --- Naming conformance -------------------------------------------------------

_SEGMENT_RE = re.compile(r"^[a-z0-9_-]+$")
_PROPERTY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_LEAKED_NAMES = ("policy_atlas", "runner", "orchestrate", "harness")


def _built_openapi_schema(tmp_path: Path) -> dict[str, Any]:
    """Build the app in-process and return its generated OpenAPI document."""
    key_dir = tmp_path / "openapi-issuer"
    settings = Settings(
        "http://dev-issuer.local",
        "openapi-conformance-test",
        None,
        init(key_dir),
        "http://app.example.test",
        "postgresql+psycopg://unused/unused",
    )
    document: dict[str, Any] = create_app(settings=settings).openapi()
    return document


def test_path_segments_are_lower_snake_or_params(tmp_path: Path) -> None:
    """Every path segment matches the naming regex, params aside."""
    schema = _built_openapi_schema(tmp_path)
    for path in schema["paths"]:
        for segment in path.split("/"):
            if not segment:
                continue
            if segment.startswith("{") and segment.endswith("}"):
                continue
            assert _SEGMENT_RE.fullmatch(segment), f"non-conforming path segment: {segment!r}"


def test_component_schema_properties_are_snake_case(tmp_path: Path) -> None:
    """Every component schema property key is snake_case."""
    schema = _built_openapi_schema(tmp_path)
    components = schema.get("components", {}).get("schemas", {})
    for schema_name, component in components.items():
        for key in component.get("properties", {}):
            assert _PROPERTY_RE.fullmatch(key), (
                f"non-snake_case property {key!r} on component {schema_name!r}"
            )


def test_no_internal_module_names_leak_into_paths_or_schema_names(tmp_path: Path) -> None:
    """Neither paths nor component schema names surface internal module vocabulary."""
    schema = _built_openapi_schema(tmp_path)
    paths = list(schema["paths"])
    schema_names = list(schema.get("components", {}).get("schemas", {}))
    for leaked in _LEAKED_NAMES:
        assert not any(leaked in path.lower() for path in paths), leaked
        assert not any(leaked in name.lower() for name in schema_names), leaked


# --- response_model whitelist spot check -------------------------------------


def test_get_project_response_contains_only_project_out_fields(tmp_path: Path) -> None:
    """`GET` a project and assert no ORM leakage beyond the `ProjectOut` field set."""
    with api_client(tmp_path) as (client, owner, _other):
        project_id = create_project(client, owner)
        response = client.get(f"/api/v1/projects/{project_id}", headers=owner)
        assert response.status_code == 200
        assert set(response.json()) == set(ProjectOut.model_fields)
