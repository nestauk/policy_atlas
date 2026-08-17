"""HTTP coverage for the user-feedback write routes (task 032)."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, cast

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.core.schema import user_feedback
from tests.api.resource_support import api_client, create_project
from tests.helpers import seed_source


def _evidence_row(
    client: TestClient,
    headers: dict[str, str],
    project_id: uuid.UUID,
    source_id: uuid.UUID,
) -> dict[str, Any]:
    """Return the one evidence row for `source_id` from the list read model."""
    response = client.get(f"/api/v1/projects/{project_id}/evidence", headers=headers)
    assert response.status_code == 200, response.text
    rows = [row for row in response.json()["data"] if row["source_id"] == str(source_id)]
    assert len(rows) == 1
    return cast(dict[str, Any], rows[0])


def test_source_flag_is_idempotent_and_reads_back(tmp_path: Path, engine: Engine) -> None:
    """Flag on/off is idempotent in both directions and shows in both read models."""
    with api_client(tmp_path) as (client, owner, _other):
        project_id = uuid.UUID(create_project(client, owner))
        with engine.begin() as conn:
            _snap_id, pss_id = seed_source(conn, project_id, {"title": "Flag me"})
        route = f"/api/v1/projects/{project_id}/sources/{pss_id}"

        before = _evidence_row(client, owner, project_id, pss_id)
        assert before["not_relevant"] is False

        first = client.patch(route, headers=owner, json={"not_relevant": True})
        assert first.status_code == 200, first.text
        assert first.json() == {"source_id": str(pss_id), "not_relevant": True}
        # Repeating the flag must not create a second row.
        assert client.patch(route, headers=owner, json={"not_relevant": True}).status_code == 200
        with engine.connect() as conn:
            rows = conn.execute(
                select(user_feedback).where(
                    user_feedback.c.project_source_snapshot_id == pss_id
                )
            ).all()
        assert len(rows) == 1
        assert rows[0].kind == "source_not_relevant"
        assert rows[0].body is None

        after = _evidence_row(client, owner, project_id, pss_id)
        assert after["not_relevant"] is True
        dossier = client.get(route, headers=owner)
        assert dossier.status_code == 200
        assert dossier.json()["not_relevant"] is True

        # The flag is feedback only: nothing else on the row may move.
        assert {key: value for key, value in after.items() if key != "not_relevant"} == {
            key: value for key, value in before.items() if key != "not_relevant"
        }

        cleared = client.patch(route, headers=owner, json={"not_relevant": False})
        assert cleared.status_code == 200
        assert cleared.json()["not_relevant"] is False
        # Clearing an absent flag is a no-op, not an error.
        assert client.patch(route, headers=owner, json={"not_relevant": False}).status_code == 200
        assert _evidence_row(client, owner, project_id, pss_id)["not_relevant"] is False


def test_source_flag_owner_scope_is_opaque(tmp_path: Path, engine: Engine) -> None:
    """Cross-owner, absent project and foreign source all 404 identically."""
    with api_client(tmp_path) as (client, owner, other):
        project_id = uuid.UUID(create_project(client, owner))
        foreign_id = uuid.UUID(create_project(client, other))
        with engine.begin() as conn:
            _snap, pss_id = seed_source(conn, project_id, {"title": "Mine"})
            _snap, foreign_pss = seed_source(conn, foreign_id, {"title": "Theirs"})
        body = {"not_relevant": True}

        cross_owner = client.patch(
            f"/api/v1/projects/{project_id}/sources/{pss_id}", headers=other, json=body
        )
        absent = client.patch(
            f"/api/v1/projects/{uuid.uuid4()}/sources/{pss_id}", headers=other, json=body
        )
        foreign_source = client.patch(
            f"/api/v1/projects/{project_id}/sources/{foreign_pss}", headers=owner, json=body
        )
        assert cross_owner.status_code == absent.status_code == foreign_source.status_code == 404
        assert cross_owner.json() == absent.json() == foreign_source.json()
        assert (
            client.patch(
                f"/api/v1/projects/{project_id}/sources/{pss_id}", json=body
            ).status_code
            == 401
        )
        with engine.connect() as conn:
            assert (
                conn.execute(
                    select(user_feedback.c.user_feedback_id).where(
                        user_feedback.c.project_id.in_((project_id, foreign_id))
                    )
                ).all()
                == []
            )


def test_issue_report_persists_and_rejects_empty_body(tmp_path: Path, engine: Engine) -> None:
    """A report stores body and page path; a blank body is a validation error."""
    with api_client(tmp_path) as (client, owner, other):
        project_id = uuid.UUID(create_project(client, owner))
        route = f"/api/v1/projects/{project_id}/issue-reports"

        rejected = client.post(route, headers=owner, json={"body": "   "})
        assert rejected.status_code == 422
        assert rejected.json()["error"]["code"] == "validation_error"
        too_long = client.post(route, headers=owner, json={"body": "x" * 4001})
        assert too_long.status_code == 422

        created = client.post(
            route,
            headers=owner,
            json={"body": "  The strength column is wrong  ", "page_path": "/projects/x/sources"},
        )
        assert created.status_code == 201, created.text
        feedback_id = uuid.UUID(created.json()["feedback_id"])
        with engine.connect() as conn:
            row = conn.execute(
                select(user_feedback).where(user_feedback.c.user_feedback_id == feedback_id)
            ).one()
        assert row.kind == "issue_report"
        assert row.body == "The strength column is wrong"
        assert row.page_path == "/projects/x/sources"
        assert row.project_source_snapshot_id is None

        cross_owner = client.post(route, headers=other, json={"body": "not mine"})
        assert cross_owner.status_code == 404
        assert client.post(route, json={"body": "anonymous"}).status_code == 401
