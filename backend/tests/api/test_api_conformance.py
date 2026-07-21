"""Conformance sweep over the as-built `/api/v1` surface.

Table-driven checks against `docs/specs/system/web-api.md` § Error envelope
and § Pagination: the pagination envelope shape and cap, every error-envelope
code class reachable from real routes, OpenAPI naming hygiene (plural/lower
segments, snake_case properties, no leaked internal names), and a
`response_model` whitelist spot check guarding against ORM leakage.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.engine import Engine

from policy_atlas.api.app import create_app
from policy_atlas.api.contract import PAGE_SIZE_DEFAULT, ProjectOut
from policy_atlas.api.dev_issuer import init
from policy_atlas.api.settings import Settings
from policy_atlas.core.schema import capability_run, evidence_scope
from tests.api.resource_support import api_client, create_project

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

_UNAUTHENTICATED_CASES: tuple[tuple[str, str, dict[str, Any] | None], ...] = (
    ("GET", "/api/v1/projects", None),
    ("GET", "/api/v1/projects/{project_id}", None),
    ("GET", "/api/v1/projects/{project_id}/runs", None),
    ("GET", "/api/v1/projects/{project_id}/check-ins", None),
    ("POST", "/api/v1/projects/{project_id}/planning-turns", {}),
)


@pytest.mark.parametrize(
    "method,path_template,json_body",
    _UNAUTHENTICATED_CASES,
    ids=[case[1] for case in _UNAUTHENTICATED_CASES],
)
def test_every_router_prefix_is_unauthenticated_without_a_token(
    tmp_path: Path, method: str, path_template: str, json_body: dict[str, Any] | None
) -> None:
    """Every data route gives the same 401 envelope shape and bearer challenge."""
    with api_client(tmp_path) as (client, _owner, _other):
        path = path_template.format(project_id=uuid.uuid4())
        response = client.request(method, path, json=json_body)
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"
        body = response.json()
        assert set(body) == {"error"}
        assert set(body["error"]) == {"code", "message"}
        assert body["error"]["code"] == "unauthenticated"


def test_not_found_is_byte_identical_for_absent_and_cross_owner_projects(
    tmp_path: Path,
) -> None:
    """404 `not_found` hides ownership: unknown and other-owned bodies match exactly."""
    with api_client(tmp_path) as (client, owner, other):
        project_id = create_project(client, owner)

        never_existed = client.get(f"/api/v1/projects/{uuid.uuid4()}", headers=other)
        cross_owner = client.get(f"/api/v1/projects/{project_id}", headers=other)

        assert never_existed.status_code == cross_owner.status_code == 404
        assert never_existed.content == cross_owner.content
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
    return create_app(settings=settings).openapi()


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
