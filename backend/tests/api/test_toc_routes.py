"""The theory-of-change read routes (task 054, S14; C17)."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy import update
from sqlalchemy.engine import Engine

from policy_atlas.api.app import create_app
from policy_atlas.core.schema import task
from tests.api.org_support import make_org, ops_enrol, seeded, tenancy_client
from tests.api.resource_support import (
    api_client,
    create_task,
    remove_committed_tasks,  # noqa: F401 — autouse
)
from tests.api.test_api_conformance import _flatten_api_routes
from tests.helpers import seed_toc_task

ROUTES = ["/api/v1/tasks/{task_id}/toc", "/api/v1/tasks/{task_id}/toc/evidence"]


def test_both_reads_are_mounted_and_in_the_openapi_document() -> None:
    app = create_app()
    mounted = {route.path for route in _flatten_api_routes(app.routes)}
    paths = app.openapi()["paths"]
    for route in ROUTES:
        assert route in mounted
        assert "get" in paths[route]


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize(
    "caller,public,expected",
    [
        ("anonymous", True, 200),
        ("anonymous", False, 404),
        ("owner", False, 200),
        ("same_org", False, 200),
        ("cross_org", False, 404),
    ],
)
def test_the_access_matrix(
    engine: Engine, tmp_path: Path, route: str, caller: str, public: bool, expected: int
) -> None:
    with tenancy_client(tmp_path, count=3) as (client, (owner, colleague, outsider)):
        with seeded(engine) as conn:
            org = make_org(conn, name="ToC Org")
            other_org = make_org(conn, name="Other Org")
            ops_enrol(conn, user_id=owner.user_id, org_id=org, display_name="Owner")
            ops_enrol(conn, user_id=colleague.user_id, org_id=org, display_name="Colleague")
            ops_enrol(conn, user_id=outsider.user_id, org_id=other_org, display_name="Outsider")
            ids = seed_toc_task(conn)
            conn.execute(
                update(task)
                .where(task.c.task_id == ids["task_id"])
                .values(owner_user_id=owner.user_id, org_id=org, visibility="org", is_public=public)
            )
        headers = {
            "anonymous": None,
            "owner": owner.headers,
            "same_org": colleague.headers,
            "cross_org": outsider.headers,
        }[caller]
        response = client.get(route.format(task_id=ids["task_id"]), headers=headers)
        assert response.status_code == expected, response.text
        if expected == 404:
            unknown = client.get(route.format(task_id=uuid.uuid4()), headers=headers)
            assert response.content == unknown.content


@pytest.mark.parametrize("route", ROUTES)
def test_a_public_task_that_is_not_a_theory_is_toc_not_found(tmp_path: Path, route: str) -> None:
    with api_client(tmp_path) as (client, owner, _other):
        task_id = create_task(client, owner)
        shared = client.patch(f"/api/v1/tasks/{task_id}", headers=owner, json={"is_public": True})
        assert shared.status_code == 200
        response = client.get(route.format(task_id=task_id))
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "toc_not_found"


def test_the_reads_serve_the_contract_shapes(engine: Engine, tmp_path: Path) -> None:
    with api_client(tmp_path) as (client, owner, _other):
        with seeded(engine) as conn:
            ids = seed_toc_task(conn)
            conn.execute(
                update(task).where(task.c.task_id == ids["task_id"]).values(is_public=True)
            )
        graph = client.get(f"/api/v1/tasks/{ids['task_id']}/toc")
        assert graph.status_code == 200, graph.text
        body = graph.json()
        assert body["check_status"] == "checked"
        [link] = body["links"]
        # The seeded judgement was made for another wording: it does not count.
        assert link["state"] == "unchecked"
        assert link["elsewhere"] == {"grade": "none", "against": 0, "supports": 0}
        assert link["assumption_type"] == "delivery"
        [pathway] = body["pathways"]
        assert pathway["link_ids"] == [str(ids["link"])] and pathway["broken"] is False
        assert body["context"] == ["Context line"]
        assert body["grade_rules"]
        evidence = client.get(f"/api/v1/tasks/{ids['task_id']}/toc/evidence").json()
        [doc] = evidence["links"][0]["documents"]
        assert doc["previous_wording"] is True
        assert doc["elsewhere"] == {"stance": "supports", "quote": "It worked."}
