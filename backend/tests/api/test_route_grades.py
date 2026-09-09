"""Route-level coverage for the phase-4 grade cutover (task 033).

Every case drives a real route through the real application (the
`test_tenancy_api_surface.py` idiom), seeded through `org_support`. Where the
underlying resolution is shared across many routes (`read_models.py`'s
`_owned` wrapper, the conformance sweep's cross-owner 404 suite), one
representative route stands in for the family; every route the grade table
names individually gets its own case.

Phase 5 extends the file with the three colleague chat mutations — create a
conversation, post a turn to your own conversation, cancel your own turn —
under the "--- Colleague chat mutations" heading below. `sse.py`'s `_tail`
re-authorisation (phase 6) is *not* here: it needs the incremental streaming
harness, so it lives with the rest of the SSE coverage in `test_sse.py`. This
file keeps only the `_snapshot` grade, which is an ordinary route response.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.engine import Connection, Engine

from policy_atlas.api import chat_turns
from policy_atlas.api.app import create_app
from policy_atlas.api.deps import get_chat_backend, get_chat_embedding_backend
from policy_atlas.api.dev_issuer import init, mint_token
from policy_atlas.api.settings import Settings
from policy_atlas.core.embeddings import StubEmbeddingBackend
from policy_atlas.core.schema import (
    app_user,
    capability_run,
    chat_turn,
    conversation,
    evidence_scope,
    planning_transcript,
    task_plan,
)
from policy_atlas.core.schema import task as task_table
from policy_atlas.runtime.chat_backend import StubChatBackend
from tests.api.org_support import (
    make_org,
    make_project,
    make_task,
    ops_enrol,
    seeded,
    tenancy_client,
)
from tests.api.test_chat_turns import _citable_tools, _cleanup, _walk
from tests.api.test_sse import _StreamingAsgiTransport
from tests.helpers import now
from tests.runtime.test_runner import _base_plan, _seed_task


def _seed_run(conn: Connection, *, task_id: uuid.UUID) -> uuid.UUID:
    """Insert one terminal capability run so `GET .../runs/{run_id}` has a row to find."""
    run_id = uuid.uuid4()
    scope_id = uuid.uuid4()
    conn.execute(
        evidence_scope.insert().values(
            evidence_scope_id=scope_id,
            task_id=task_id,
            intent="route-grade test",
            context={},
            created_at=now(),
        )
    )
    conn.execute(
        capability_run.insert().values(
            capability_run_id=run_id,
            task_id=task_id,
            evidence_scope_id=scope_id,
            capability="evidence_search",
            plan_id=uuid.uuid4(),
            plan_version=1,
            status="succeeded",
            session_id=None,
            started_at=now(),
            ended_at=now(),
        )
    )
    return run_id


def _seed_approved_plan(conn: Connection, *, task_id: uuid.UUID) -> None:
    """Insert one approved plan so `GET .../plan` has something to return.

    `evidence_scope_id` is left NULL: the composite FK guard on
    `task_plan` uses MATCH SIMPLE, so a NULL scope skips the check
    (schema comment, `core/schema.py`) and this test needs no separate
    `evidence_scope` row.
    """
    plan = _base_plan(
        analysis_depth="landscape",
        components=["characterise"],
        grouping_facets=None,
        steering_mode="unattended",
    )
    conn.execute(
        task_plan.insert().values(
            plan_id=uuid.uuid4(),
            task_id=task_id,
            conversation_id=None,
            evidence_scope_id=None,
            version=1,
            status="approved",
            payload=plan.model_dump(mode="json"),
            created_at=now(),
            created_by="planner",
            approved_at=now(),
        )
    )


def _insert_conversation(
    conn: Connection,
    *,
    conversation_id: uuid.UUID,
    task_id: uuid.UUID,
    kind: str,
    created_by: str | None,
    status: str = "active",
) -> None:
    """Insert one durable conversation row with an explicit `created_by`."""
    conn.execute(
        conversation.insert().values(
            id=conversation_id,
            task_id=task_id,
            kind=kind,
            title=f"{kind} conversation",
            entry_artefact_id=None,
            status=status,
            created_at=now(),
            closed_at=None,
            archived_at=None,
            created_by=created_by,
        )
    )


# --- READ grade: a same-org colleague reaches the row (200), not 404 --------


def test_get_task_read_grade_lets_a_colleague_open_the_row(
    engine: Engine, tmp_path: Path
) -> None:
    with tenancy_client(tmp_path, count=2) as (client, (owner, colleague)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague")
            task_id = make_task(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )

        response = client.get(f"/api/v1/tasks/{task_id}", headers=colleague.headers)

        assert response.status_code == 200
        assert response.json()["is_owner"] is False


def test_get_project_read_grade_lets_a_colleague_open_the_row(
    engine: Engine, tmp_path: Path
) -> None:
    with tenancy_client(tmp_path, count=2) as (client, (owner, colleague)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague")
            project_id = make_project(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )

        response = client.get(f"/api/v1/projects/{project_id}", headers=colleague.headers)

        assert response.status_code == 200
        assert response.json()["is_owner"] is False


def test_read_models_route_read_grade_lets_a_colleague_read(
    engine: Engine, tmp_path: Path
) -> None:
    """`funnel` stands in for all eleven `read_models.py` routes: one shared `_owned` wrapper."""
    with tenancy_client(tmp_path, count=2) as (client, (owner, colleague)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague")
            task_id = make_task(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )

        response = client.get(f"/api/v1/tasks/{task_id}/funnel", headers=colleague.headers)

        assert response.status_code == 200


def test_runs_read_grade_lets_a_colleague_list_and_get(engine: Engine, tmp_path: Path) -> None:
    with tenancy_client(tmp_path, count=2) as (client, (owner, colleague)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague")
            task_id = make_task(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )
            run_id = _seed_run(conn, task_id=task_id)

        listed = client.get(f"/api/v1/tasks/{task_id}/runs", headers=colleague.headers)
        fetched = client.get(
            f"/api/v1/tasks/{task_id}/runs/{run_id}", headers=colleague.headers
        )

        assert listed.status_code == 200
        assert str(run_id) in {row["capability_run_id"] for row in listed.json()["data"]}
        assert fetched.status_code == 200
        assert fetched.json()["capability_run_id"] == str(run_id)


def test_check_ins_and_planning_turns_read_grade_let_a_colleague_list(
    engine: Engine, tmp_path: Path
) -> None:
    with tenancy_client(tmp_path, count=2) as (client, (owner, colleague)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague")
            task_id = make_task(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )

        check_ins = client.get(
            f"/api/v1/tasks/{task_id}/check-ins", headers=colleague.headers
        )
        planning_turns = client.get(
            f"/api/v1/tasks/{task_id}/planning-turns", headers=colleague.headers
        )

        assert check_ins.status_code == 200
        assert planning_turns.status_code == 200


def test_get_plan_read_grade_lets_a_colleague_read(engine: Engine, tmp_path: Path) -> None:
    with tenancy_client(tmp_path, count=2) as (client, (owner, colleague)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague")
            task_id = make_task(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )
            _seed_approved_plan(conn, task_id=task_id)

        response = client.get(f"/api/v1/tasks/{task_id}/plan", headers=colleague.headers)

        assert response.status_code == 200
        assert response.json()["status"] == "approved"


def _stale_pending_turn(conn: Connection, *, task_id: uuid.UUID) -> uuid.UUID:
    """Insert one planning turn old enough for the sweeper to fail, and return its id."""
    turn_id = uuid.uuid4()
    conn.execute(
        planning_transcript.insert().values(
            id=turn_id,
            task_id=task_id,
            conversation_id=None,
            client_turn_id=uuid.uuid4(),
            turn_index=0,
            user_message="a turn whose process died",
            reply=None,
            planner_state=None,
            response=None,
            suggestions=[],
            status="pending",
            created_at=now() - timedelta(minutes=11),
            completed_at=None,
        )
    )
    return turn_id


def _turn_status(engine: Engine, turn_id: uuid.UUID) -> str:
    """Read one planning transcript row's status."""
    with engine.connect() as conn:
        return str(
            conn.execute(
                select(planning_transcript.c.status).where(
                    planning_transcript.c.id == turn_id
                )
            ).scalar_one()
        )


def test_a_read_graded_planning_get_by_anyone_but_the_owner_writes_nothing(
    engine: Engine, tmp_path: Path
) -> None:
    """The stale-turn sweeper is a write, so it belongs to the owner alone.

    `GET .../planning-turns` and `GET .../plan` carry the **read** grade —
    owner, same-org colleague, administrator — and both used to run
    `_expire_stale_pending_turns` unconditionally. That made a colleague's page
    load, and an administrator's support read, fail the owner's in-flight
    planning turn: a mutation on a read grade, and for the admin leg a
    mutation the contract's read-only guarantee forbids outright.

    Both non-owner callers are exercised against the same row, and the row is
    still `pending` after four reads. The owner's read then sweeps it, which is
    what keeps this a statement about *who* rather than about the sweeper
    having been deleted.
    """
    with tenancy_client(tmp_path, count=3) as (client, (owner, colleague, admin)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            support_org = make_org(conn, name="Support Org")
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(
                conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague"
            )
            ops_enrol(
                conn,
                user_id=admin.user_id,
                org_id=support_org,
                display_name="Support",
                is_admin=True,
            )
            task_id = make_task(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )
            _seed_approved_plan(conn, task_id=task_id)
            turn_id = _stale_pending_turn(conn, task_id=task_id)

        for caller in (colleague, admin):
            for path in ("planning-turns", "plan"):
                response = client.get(
                    f"/api/v1/tasks/{task_id}/{path}", headers=caller.headers
                )
                assert response.status_code == 200, (path, response.text)
                assert _turn_status(engine, turn_id) == "pending"

        owner_read = client.get(
            f"/api/v1/tasks/{task_id}/planning-turns", headers=owner.headers
        )
        assert owner_read.status_code == 200
        assert _turn_status(engine, turn_id) == "failed"


def test_sse_snapshot_read_grade_lets_a_colleague_open_the_stream(
    engine: Engine, tmp_path: Path
) -> None:
    """`_snapshot`'s resolution: a same-org colleague may open the event stream.

    A live SSE success never completes (an infinite tail loop follows the
    replay), so — following `test_sse.py`'s own idiom — this opens the stream
    with the buffering-safe transport and reads only the status line before
    closing, rather than draining the body. The cross-org refusal completes
    immediately (no stream ever opens) and needs no special transport.
    """

    async def exercise() -> None:
        key_dir = tmp_path / "sse-grade-issuer"
        settings = Settings(
            "http://dev-issuer.local",
            "route-grades-sse-test",
            None,
            init(key_dir),
            "http://app.example.test",
            os.environ["DATABASE_URL"],
            sse_poll_interval_seconds=0.01,
            sse_heartbeat_seconds=15.0,
        )
        owner_id = f"owner-{uuid.uuid4()}"
        colleague_id = f"colleague-{uuid.uuid4()}"
        stranger_id = f"stranger-{uuid.uuid4()}"
        colleague_token = mint_token(
            colleague_id, settings.oidc_issuer, settings.oidc_client_id, 60, key_dir
        )
        stranger_token = mint_token(
            stranger_id, settings.oidc_issuer, settings.oidc_client_id, 60, key_dir
        )
        with seeded(engine) as conn:
            org_id = make_org(conn)
            other_org = make_org(conn, name="Other")
            ops_enrol(conn, user_id=owner_id, org_id=org_id, display_name="Owner")
            ops_enrol(conn, user_id=colleague_id, org_id=org_id, display_name="Colleague")
            ops_enrol(conn, user_id=stranger_id, org_id=other_org, display_name="Stranger")
            task_id = make_task(
                conn, owner_user_id=owner_id, org_id=org_id, visibility="org"
            )

        app = create_app(settings=settings)
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=_StreamingAsgiTransport(app), base_url="http://testserver"
            ) as client,
        ):
            context = client.stream(
                "GET",
                f"/api/v1/tasks/{task_id}/events",
                headers={"Authorization": f"Bearer {colleague_token}"},
            )
            response = await context.__aenter__()
            try:
                assert response.status_code == 200, await response.aread()
            finally:
                await context.__aexit__(None, None, None)

            cross_org = await client.get(
                f"/api/v1/tasks/{task_id}/events",
                headers={"Authorization": f"Bearer {stranger_token}"},
            )
            assert cross_org.status_code == 404

    asyncio.run(exercise())


def test_list_conversations_colleague_sees_empty_not_404_owner_sees_legacy_rows(
    engine: Engine, tmp_path: Path
) -> None:
    """Read-graded on the task, then narrowed to the caller's own chats.

    A colleague who can read the task sees an **empty page**, not a 404 —
    chat creation for colleagues arrives in phase 5, so today they simply have
    none. The owner keeps seeing every legacy pre-033 row (`created_by IS
    NULL`) as their own.
    """
    with tenancy_client(tmp_path, count=2) as (client, (owner, colleague)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague")
            task_id = make_task(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )
            _insert_conversation(
                conn,
                conversation_id=uuid.uuid4(),
                task_id=task_id,
                kind="chat",
                created_by=None,
            )

        colleague_page = client.get(
            f"/api/v1/tasks/{task_id}/conversations", headers=colleague.headers
        )
        owner_page = client.get(
            f"/api/v1/tasks/{task_id}/conversations", headers=owner.headers
        )

        assert colleague_page.status_code == 200
        assert colleague_page.json()["data"] == []
        assert owner_page.status_code == 200
        assert len(owner_page.json()["data"]) == 1


# --- WRITE grade: a same-org colleague who can read gets 403, not 404 -------


def test_archive_task_write_grade_colleague_403_outsider_404(
    engine: Engine, tmp_path: Path
) -> None:
    with tenancy_client(tmp_path, count=3) as (client, (owner, colleague, outsider)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague")
            task_id = make_task(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )

        forbidden = client.post(
            f"/api/v1/tasks/{task_id}/archive", headers=colleague.headers
        )
        missing = client.post(
            f"/api/v1/tasks/{task_id}/archive", headers=outsider.headers
        )

        assert forbidden.status_code == 403
        assert forbidden.json()["error"]["code"] == "forbidden"
        assert missing.status_code == 404


def test_update_project_write_grade_colleague_403_outsider_404(
    engine: Engine, tmp_path: Path
) -> None:
    with tenancy_client(tmp_path, count=3) as (client, (owner, colleague, outsider)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague")
            project_id = make_project(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )

        forbidden = client.patch(
            f"/api/v1/projects/{project_id}", headers=colleague.headers, json={"name": "X"}
        )
        missing = client.patch(
            f"/api/v1/projects/{project_id}", headers=outsider.headers, json={"name": "X"}
        )

        assert forbidden.status_code == 403
        assert forbidden.json()["error"]["code"] == "forbidden"
        assert missing.status_code == 404


def test_respond_to_check_in_write_grade_colleague_403_outsider_404(
    engine: Engine, tmp_path: Path
) -> None:
    """The write grade gates before any check-in id is even consulted."""
    with tenancy_client(tmp_path, count=3) as (client, (owner, colleague, outsider)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague")
            task_id = make_task(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )

        body = {"kind": "abort"}
        forbidden = client.post(
            f"/api/v1/tasks/{task_id}/check-ins/{uuid.uuid4()}/response",
            headers=colleague.headers,
            json=body,
        )
        missing = client.post(
            f"/api/v1/tasks/{task_id}/check-ins/{uuid.uuid4()}/response",
            headers=outsider.headers,
            json=body,
        )

        assert forbidden.status_code == 403
        assert missing.status_code == 404


def test_create_planning_turn_write_grade_colleague_403_outsider_404(
    engine: Engine, tmp_path: Path
) -> None:
    with tenancy_client(tmp_path, count=3) as (client, (owner, colleague, outsider)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague")
            task_id = make_task(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )

        body = {"message": "Hello", "client_turn_id": str(uuid.uuid4())}
        forbidden = client.post(
            f"/api/v1/tasks/{task_id}/planning-turns", headers=colleague.headers, json=body
        )
        missing = client.post(
            f"/api/v1/tasks/{task_id}/planning-turns",
            headers=outsider.headers,
            json={**body, "client_turn_id": str(uuid.uuid4())},
        )

        assert forbidden.status_code == 403
        assert missing.status_code == 404


def test_patch_plan_write_grade_colleague_403_outsider_404(
    engine: Engine, tmp_path: Path
) -> None:
    with tenancy_client(tmp_path, count=3) as (client, (owner, colleague, outsider)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague")
            task_id = make_task(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )

        forbidden = client.patch(
            f"/api/v1/tasks/{task_id}/plan", headers=colleague.headers, json={}
        )
        missing = client.patch(
            f"/api/v1/tasks/{task_id}/plan", headers=outsider.headers, json={}
        )

        assert forbidden.status_code == 403
        assert missing.status_code == 404


def test_create_run_write_grade_colleague_403_outsider_404(
    engine: Engine, tmp_path: Path
) -> None:
    with tenancy_client(tmp_path, count=3) as (client, (owner, colleague, outsider)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague")
            task_id = make_task(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )

        forbidden = client.post(
            f"/api/v1/tasks/{task_id}/runs", headers=colleague.headers, json={}
        )
        missing = client.post(
            f"/api/v1/tasks/{task_id}/runs", headers=outsider.headers, json={}
        )

        assert forbidden.status_code == 403
        assert missing.status_code == 404


# --- Conversation-id router: kind-graded, never a 403 -----------------------


def test_conversation_id_router_closes_the_deep_link_leak_for_a_colleague(
    engine: Engine, tmp_path: Path
) -> None:
    """A colleague who can read the task must never learn a chat exists.

    `GET /{id}` and `GET /{id}/turns` are the deep-link surfaces this grading
    closes: both 404 for a colleague who did not create the chat, even though
    the task itself shows up in their listing. The chat's creator (the
    owner, here) still reaches every lifecycle route.
    """
    with tenancy_client(tmp_path, count=2) as (client, (owner, colleague)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague")
            task_id = make_task(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )
            conversation_id = uuid.uuid4()
            _insert_conversation(
                conn,
                conversation_id=conversation_id,
                task_id=task_id,
                kind="chat",
                created_by=owner.user_id,
            )

        colleague_sees_task = str(task_id) in {
            row["task_id"]
            for row in client.get("/api/v1/tasks", headers=colleague.headers).json()["data"]
        }
        assert colleague_sees_task

        deep_link = client.get(
            f"/api/v1/conversations/{conversation_id}", headers=colleague.headers
        )
        turns_deep_link = client.get(
            f"/api/v1/conversations/{conversation_id}/turns", headers=colleague.headers
        )
        assert deep_link.status_code == 404
        assert turns_deep_link.status_code == 404

        owner_get = client.get(f"/api/v1/conversations/{conversation_id}", headers=owner.headers)
        owner_patch = client.patch(
            f"/api/v1/conversations/{conversation_id}",
            headers=owner.headers,
            json={"title": "Renamed"},
        )
        owner_archive = client.post(
            f"/api/v1/conversations/{conversation_id}/archive", headers=owner.headers
        )
        owner_unarchive = client.post(
            f"/api/v1/conversations/{conversation_id}/unarchive", headers=owner.headers
        )
        owner_turns = client.get(
            f"/api/v1/conversations/{conversation_id}/turns", headers=owner.headers
        )

        assert owner_get.status_code == 200
        assert owner_patch.status_code == 200
        assert owner_archive.status_code == 200
        assert owner_unarchive.status_code == 200
        assert owner_turns.status_code == 200


def test_planning_conversation_get_is_404_for_a_colleague(
    engine: Engine, tmp_path: Path
) -> None:
    """Planning conversations stay owner-only, whoever else can read the task."""
    with tenancy_client(tmp_path, count=2) as (client, (owner, colleague)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague")
            task_id = make_task(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )
            conversation_id = uuid.uuid4()
            _insert_conversation(
                conn,
                conversation_id=conversation_id,
                task_id=task_id,
                kind="planning",
                created_by=None,
            )

        colleague_get = client.get(
            f"/api/v1/conversations/{conversation_id}", headers=colleague.headers
        )
        owner_get = client.get(f"/api/v1/conversations/{conversation_id}", headers=owner.headers)

        assert colleague_get.status_code == 404
        assert owner_get.status_code == 200


# --- Private rows and cross-org callers --------------------------------------


def test_private_task_is_404_for_a_colleague_on_a_read_graded_route(
    engine: Engine, tmp_path: Path
) -> None:
    with tenancy_client(tmp_path, count=2) as (client, (owner, colleague)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague")
            task_id = make_task(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="private"
            )

        response = client.get(f"/api/v1/tasks/{task_id}", headers=colleague.headers)

        assert response.status_code == 404


def test_cross_org_caller_gets_404_across_read_and_write_graded_routes(
    engine: Engine, tmp_path: Path
) -> None:
    """No shared organisation means no read leg at all — 404 everywhere, never 403."""
    with tenancy_client(tmp_path, count=2) as (client, (owner, stranger)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            other_org = make_org(conn, name="Other")
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(conn, user_id=stranger.user_id, org_id=other_org, display_name="Stranger")
            task_id = make_task(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )
            project_id = make_project(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )

        assert (
            client.get(f"/api/v1/tasks/{task_id}", headers=stranger.headers).status_code
            == 404
        )
        assert (
            client.get(
                f"/api/v1/projects/{project_id}", headers=stranger.headers
            ).status_code
            == 404
        )
        assert (
            client.get(
                f"/api/v1/tasks/{task_id}/funnel", headers=stranger.headers
            ).status_code
            == 404
        )
        assert (
            client.get(
                f"/api/v1/tasks/{task_id}/runs", headers=stranger.headers
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"/api/v1/tasks/{task_id}/archive", headers=stranger.headers
            ).status_code
            == 404
        )
        assert (
            client.patch(
                f"/api/v1/projects/{project_id}",
                headers=stranger.headers,
                json={"name": "x"},
            ).status_code
            == 404
        )


# --- Colleague chat mutations (phase 5, contract § 4) ------------------------
#
# Owner call (b) grants a same-org colleague exactly three mutations and
# nothing else: create a conversation on a readable task, post a turn to
# their own conversation, cancel their own turn. These cases drive all three
# through the real routes.


def _chat_ready_task(
    engine: Engine, *, owner_user_id: str, org_id: uuid.UUID, visibility: str = "org"
) -> uuid.UUID:
    """Seed a task a chat turn can actually run against, stamped for one org.

    `make_task` is too thin here: a turn needs the evidence fixtures and a
    terminal capability run, which is what `tests.runtime.test_runner`'s
    `_seed_task` builds. This wraps it and applies the tenancy columns the
    seeder knows nothing about.
    """
    task_id, scope_id = _seed_task(engine)
    with engine.begin() as conn:
        conn.execute(
            update(task_table)
            .where(task_table.c.task_id == task_id)
            .values(owner_user_id=owner_user_id, org_id=org_id, visibility=visibility)
        )
    _walk(engine, task_id=task_id, scope_id=scope_id, status="succeeded")
    return task_id


def _pending_turn(engine: Engine, *, conversation_id: uuid.UUID, turn_index: int = 0) -> uuid.UUID:
    """Insert one fresh pending turn and return its id, for the cancel routes."""
    turn_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            chat_turn.insert().values(
                id=turn_id,
                conversation_id=conversation_id,
                turn_index=turn_index,
                client_turn_id=uuid.uuid4(),
                user_message="in flight",
                answer=None,
                answer_payload=None,
                capability_run_id=None,
                status="pending",
                created_at=now(),
                completed_at=None,
            )
        )
    return turn_id


def _created_by(engine: Engine, conversation_id: uuid.UUID) -> str | None:
    """Read one conversation's recorded author."""
    with engine.connect() as conn:
        return conn.execute(  # type: ignore[no-any-return]
            select(conversation.c.created_by).where(conversation.c.id == conversation_id)
        ).scalar_one()


def _chat_overrides() -> dict[Callable[..., object], Callable[..., object]]:
    """Substitute the provider seams so a turn POST completes deterministically."""
    return {
        get_chat_backend: StubChatBackend,
        get_chat_embedding_backend: StubEmbeddingBackend,
    }


def test_create_conversation_read_grade_lets_a_colleague_start_their_own_chat(
    engine: Engine, tmp_path: Path
) -> None:
    """Colleague mutation 1: create a conversation on a task you can read.

    The widening from phase 4's write grade. A colleague gets 201 and the row
    records *them* as its author, so it is theirs and not the owner's — the
    owner cannot see it in their library and 404s on its deep link. An
    outsider, and a colleague on a `private` task, still get 404.
    """
    with tenancy_client(tmp_path, count=3) as (client, (owner, colleague, outsider)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague")
            shared = make_task(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )
            private = make_task(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="private"
            )

        created = client.post(
            f"/api/v1/tasks/{shared}/conversations", headers=colleague.headers, json={}
        )
        assert created.status_code == 201, created.text
        conversation_id = uuid.UUID(created.json()["id"])
        assert created.json()["kind"] == "chat"
        assert _created_by(engine, conversation_id) == colleague.user_id

        assert (
            client.post(
                f"/api/v1/tasks/{shared}/conversations", headers=outsider.headers, json={}
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"/api/v1/tasks/{private}/conversations", headers=colleague.headers, json={}
            ).status_code
            == 404
        )

        colleague_library = client.get(
            f"/api/v1/tasks/{shared}/conversations", headers=colleague.headers
        ).json()["data"]
        owner_library = client.get(
            f"/api/v1/tasks/{shared}/conversations", headers=owner.headers
        ).json()["data"]
        assert [row["id"] for row in colleague_library] == [str(conversation_id)]
        assert owner_library == []
        assert (
            client.get(
                f"/api/v1/conversations/{conversation_id}", headers=owner.headers
            ).status_code
            == 404
        )


def test_create_conversation_can_never_mint_a_planning_conversation(
    engine: Engine, tmp_path: Path
) -> None:
    """A planning conversation can only ever be created by the task owner.

    Enforced by the *shape of the request body*, not by a branch: this route
    writes the literal `kind="chat"`, and `ConversationCreate` forbids extras,
    so a caller asking for a planning conversation is rejected **422** before
    the route function runs. Owner and colleague are refused identically —
    the owner's planning conversations are minted by the runtime under
    `planning.py`'s owner-graded lock, never through this route.
    """
    with tenancy_client(tmp_path, count=2) as (client, (owner, colleague)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague")
            task_id = make_task(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )

        for principal in (owner, colleague):
            asked = client.post(
                f"/api/v1/tasks/{task_id}/conversations",
                headers=principal.headers,
                json={"kind": "planning"},
            )
            assert asked.status_code == 422, asked.text

        plain = client.post(
            f"/api/v1/tasks/{task_id}/conversations", headers=colleague.headers, json={}
        )
        assert plain.status_code == 201
        assert plain.json()["kind"] == "chat"


def test_colleague_posts_and_cancels_a_turn_in_their_own_chat(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Colleague mutations 2 and 3, end to end on the real routes.

    The colleague opens a chat on the owner's task, posts a turn that runs
    to a terminal `completed` NDJSON event, and cancels a second pending turn
    of their own. None of it requires anything of the owner.
    """
    monkeypatch.setattr(chat_turns, "build_section_tools", _citable_tools)
    task_id: uuid.UUID | None = None
    try:
        with tenancy_client(tmp_path, count=2, overrides=_chat_overrides()) as (
            client,
            (owner, colleague),
        ):
            with seeded(engine) as conn:
                org_id = make_org(conn)
                ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
                ops_enrol(
                    conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague"
                )
            task_id = _chat_ready_task(
                engine, owner_user_id=owner.user_id, org_id=org_id
            )

            created = client.post(
                f"/api/v1/tasks/{task_id}/conversations",
                headers=colleague.headers,
                json={},
            )
            assert created.status_code == 201, created.text
            conversation_id = uuid.UUID(created.json()["id"])

            posted = client.post(
                f"/api/v1/conversations/{conversation_id}/turns",
                headers=colleague.headers,
                json={
                    "message": "What does the evidence say?",
                    "client_turn_id": str(uuid.uuid4()),
                },
            )
            assert posted.status_code == 200, posted.text
            events = [json.loads(line) for line in posted.iter_lines() if line]
            assert events[-1]["type"] == "completed"

            # The colleague reads their own transcript back, then stops a
            # second turn of their own.
            transcript = client.get(
                f"/api/v1/conversations/{conversation_id}/turns", headers=colleague.headers
            )
            assert transcript.status_code == 200
            assert transcript.json()["pagination"]["total_items"] == 1

            turn_id = _pending_turn(engine, conversation_id=conversation_id, turn_index=1)
            cancelled = client.post(
                f"/api/v1/conversations/{conversation_id}/turns/{turn_id}/cancel",
                headers=colleague.headers,
            )
            assert cancelled.status_code == 200, cancelled.text
            assert cancelled.json()["status"] == "cancelled"
    finally:
        _cleanup(engine, task_id)


def test_turn_routes_are_isolated_in_both_directions(
    engine: Engine, tmp_path: Path
) -> None:
    """Own-chats isolation on the turn routes, both ways, with turns present.

    Neither direction is a 403: the row's existence is not the other party's
    to learn, so every refusal is the indistinguishable 404. The deep-link
    `GET /{id}/turns` is re-asserted here with a real transcript behind it —
    phase 4 closed it on an empty conversation.
    """
    with tenancy_client(tmp_path, count=2) as (client, (owner, colleague)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague")
            task_id = make_task(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )
            owners_chat, colleagues_chat = uuid.uuid4(), uuid.uuid4()
            _insert_conversation(
                conn,
                conversation_id=owners_chat,
                task_id=task_id,
                kind="chat",
                created_by=owner.user_id,
            )
            _insert_conversation(
                conn,
                conversation_id=colleagues_chat,
                task_id=task_id,
                kind="chat",
                created_by=colleague.user_id,
            )
        owners_turn = _pending_turn(engine, conversation_id=owners_chat)
        colleagues_turn = _pending_turn(engine, conversation_id=colleagues_chat)

        body = {"message": "Whose chat is this?", "client_turn_id": str(uuid.uuid4())}
        cases = [
            # (intruder, the other party's conversation, the other party's turn)
            (colleague, owners_chat, owners_turn),
            (owner, colleagues_chat, colleagues_turn),
        ]
        for intruder, target_chat, target_turn in cases:
            assert (
                client.post(
                    f"/api/v1/conversations/{target_chat}/turns",
                    headers=intruder.headers,
                    json=body,
                ).status_code
                == 404
            )
            assert (
                client.post(
                    f"/api/v1/conversations/{target_chat}/turns/{target_turn}/cancel",
                    headers=intruder.headers,
                ).status_code
                == 404
            )
            assert (
                client.get(
                    f"/api/v1/conversations/{target_chat}/turns", headers=intruder.headers
                ).status_code
                == 404
            )

        # Neither turn was touched by the refused calls.
        with engine.connect() as conn:
            statuses = conn.execute(
                select(chat_turn.c.status).where(
                    chat_turn.c.id.in_([owners_turn, colleagues_turn])
                )
            ).scalars().all()
        assert sorted(statuses) == ["pending", "pending"]


def test_owner_posts_into_a_legacy_null_created_by_conversation(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The legacy disjunct on the turn routes, not just on the listing.

    A pre-033 chat records no author. It belongs to the task owner and to
    nobody else: the owner posts and cancels into it, a colleague who can read
    the task 404s on both.
    """
    monkeypatch.setattr(chat_turns, "build_section_tools", _citable_tools)
    task_id: uuid.UUID | None = None
    try:
        with tenancy_client(tmp_path, count=2, overrides=_chat_overrides()) as (
            client,
            (owner, colleague),
        ):
            with seeded(engine) as conn:
                org_id = make_org(conn)
                ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
                ops_enrol(
                    conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague"
                )
            task_id = _chat_ready_task(
                engine, owner_user_id=owner.user_id, org_id=org_id
            )
            legacy = uuid.uuid4()
            with seeded(engine) as conn:
                _insert_conversation(
                    conn,
                    conversation_id=legacy,
                    task_id=task_id,
                    kind="chat",
                    created_by=None,
                )

            body = {"message": "What does the evidence say?", "client_turn_id": str(uuid.uuid4())}
            refused = client.post(
                f"/api/v1/conversations/{legacy}/turns", headers=colleague.headers, json=body
            )
            assert refused.status_code == 404

            posted = client.post(
                f"/api/v1/conversations/{legacy}/turns", headers=owner.headers, json=body
            )
            assert posted.status_code == 200, posted.text
            events = [json.loads(line) for line in posted.iter_lines() if line]
            assert events[-1]["type"] == "completed"

            turn_id = _pending_turn(engine, conversation_id=legacy, turn_index=1)
            assert (
                client.post(
                    f"/api/v1/conversations/{legacy}/turns/{turn_id}/cancel",
                    headers=colleague.headers,
                ).status_code
                == 404
            )
            assert (
                client.post(
                    f"/api/v1/conversations/{legacy}/turns/{turn_id}/cancel",
                    headers=owner.headers,
                ).status_code
                == 200
            )
    finally:
        _cleanup(engine, task_id)


def test_de_enrolment_kills_a_colleagues_chat_mutations(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A colleague's chat access dies with their org leg, not with `created_by`.

    Matching `created_by` is not enough to keep posting: the turn routes also
    require the task under `own_estate`, so clearing the person's `org_id`
    — what ops de-enrolment does — takes every one of their three mutations
    to 404 on the very next request, with nothing else changed and no deploy.
    """
    monkeypatch.setattr(chat_turns, "build_section_tools", _citable_tools)
    task_id: uuid.UUID | None = None
    try:
        with tenancy_client(tmp_path, count=2, overrides=_chat_overrides()) as (
            client,
            (owner, colleague),
        ):
            with seeded(engine) as conn:
                org_id = make_org(conn)
                ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
                ops_enrol(
                    conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague"
                )
            task_id = _chat_ready_task(
                engine, owner_user_id=owner.user_id, org_id=org_id
            )

            created = client.post(
                f"/api/v1/tasks/{task_id}/conversations",
                headers=colleague.headers,
                json={},
            )
            assert created.status_code == 201
            conversation_id = uuid.UUID(created.json()["id"])
            posted = client.post(
                f"/api/v1/conversations/{conversation_id}/turns",
                headers=colleague.headers,
                json={"message": "Before I leave.", "client_turn_id": str(uuid.uuid4())},
            )
            assert posted.status_code == 200

            turn_id = _pending_turn(engine, conversation_id=conversation_id, turn_index=1)
            with seeded(engine) as conn:
                conn.execute(
                    update(app_user)
                    .where(app_user.c.user_id == colleague.user_id)
                    .values(org_id=None)
                )

            assert (
                client.post(
                    f"/api/v1/tasks/{task_id}/conversations",
                    headers=colleague.headers,
                    json={},
                ).status_code
                == 404
            )
            assert (
                client.post(
                    f"/api/v1/conversations/{conversation_id}/turns",
                    headers=colleague.headers,
                    json={"message": "After.", "client_turn_id": str(uuid.uuid4())},
                ).status_code
                == 404
            )
            assert (
                client.post(
                    f"/api/v1/conversations/{conversation_id}/turns/{turn_id}/cancel",
                    headers=colleague.headers,
                ).status_code
                == 404
            )
            # The reads die with the org leg too: matching `created_by` must
            # not keep a transcript open on a task the caller can no
            # longer reach (contract § 5 — de-enrolment is a revocation
            # event; the owner's evidence base rides in those turns).
            assert (
                client.get(
                    f"/api/v1/conversations/{conversation_id}",
                    headers=colleague.headers,
                ).status_code
                == 404
            )
            assert (
                client.get(
                    f"/api/v1/conversations/{conversation_id}/turns",
                    headers=colleague.headers,
                ).status_code
                == 404
            )
    finally:
        _cleanup(engine, task_id)


def test_a_chat_creator_can_archive_their_own_chat_standing_behaviour_pending_owner_call(
    engine: Engine, tmp_path: Path
) -> None:
    """The lifecycle routes as they behave today, pinned while the owner rules.

    Contract § 4 grants a same-org colleague "exactly three mutations and
    nothing else" — create a conversation, post a turn to it, cancel their
    turn. `PATCH /{id}`, `archive` and `unarchive` are not on that list, and a
    colleague who *created* the chat passes all three anyway: the write path's
    predicate is the creator/owner conjunction, and they are the creator.

    Two readings are available and this test takes neither. Either the three
    are the *mutations on somebody else's task* and renaming your own chat
    was never in scope of the sentence — or the list is exhaustive and this is
    an unintended fourth. **Escalated to the owner**; the name of this case
    says so, and it changes with the ruling rather than quietly outliving it.

    What is asserted is only what is true: the creator reaches their own
    chat's lifecycle routes, and *nobody else* does — not the task owner,
    not an administrator. That second half is the property no reading disputes
    and no existing case covered, because this router has no 403 to spend: a
    refused write here is the same opaque 404 as an absent row.
    """
    with tenancy_client(tmp_path, count=3) as (client, (owner, colleague, admin)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(
                conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague"
            )
            ops_enrol(
                conn,
                user_id=admin.user_id,
                org_id=make_org(conn, name="Support Org"),
                display_name="Support",
                is_admin=True,
            )
            task_id = make_task(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )
            chat_id = uuid.uuid4()
            _insert_conversation(
                conn,
                conversation_id=chat_id,
                task_id=task_id,
                kind="chat",
                created_by=colleague.user_id,
            )

        # The owner of the task and an administrator are refused all three,
        # indistinguishably from the chat not existing.
        for stranger in (owner, admin):
            assert (
                client.patch(
                    f"/api/v1/conversations/{chat_id}",
                    headers=stranger.headers,
                    json={"title": "Renamed by someone else"},
                ).status_code
                == 404
            )
            for action in ("archive", "unarchive"):
                assert (
                    client.post(
                        f"/api/v1/conversations/{chat_id}/{action}",
                        headers=stranger.headers,
                    ).status_code
                    == 404
                ), (stranger.user_id, action)

        # The creator reaches all three. Standing behaviour, pending the ruling.
        renamed = client.patch(
            f"/api/v1/conversations/{chat_id}",
            headers=colleague.headers,
            json={"title": "The colleague's own chat"},
        )
        assert renamed.status_code == 200, renamed.text
        assert renamed.json()["title"] == "The colleague's own chat"

        archived = client.post(
            f"/api/v1/conversations/{chat_id}/archive", headers=colleague.headers
        )
        assert archived.status_code == 200, archived.text
        assert archived.json()["status"] == "archived"

        unarchived = client.post(
            f"/api/v1/conversations/{chat_id}/unarchive", headers=colleague.headers
        )
        assert unarchived.status_code == 200, unarchived.text
        assert unarchived.json()["status"] == "active"
