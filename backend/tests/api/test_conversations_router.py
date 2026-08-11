"""HTTP coverage for the owner-scoped conversations library and lifecycle routes."""

from __future__ import annotations

import uuid
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.core.schema import artefact, chat_turn, conversation, planning_transcript
from tests.api.resource_support import api_client, create_project
from tests.helpers import now


def _artefact(engine: Engine, project_id: uuid.UUID) -> uuid.UUID:
    """Insert the smallest project-local artefact suitable for a context-chip test."""
    artefact_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            artefact.insert().values(
                artefact_id=artefact_id,
                project_id=project_id,
                capability_run_id=None,
                title="Entry analysis",
                created_at=now(),
                summary=None,
                summary_status=None,
            )
        )
    return artefact_id


def _conversation(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    kind: str = "chat",
    status: str = "active",
    title: str | None = None,
    entry_artefact_id: uuid.UUID | None = None,
    created_at_offset: int = 0,
) -> uuid.UUID:
    """Insert one durable conversation with explicit lifecycle fields."""
    conversation_id = uuid.uuid4()
    created_at = now() + timedelta(seconds=created_at_offset)
    with engine.begin() as conn:
        conn.execute(
            conversation.insert().values(
                id=conversation_id,
                project_id=project_id,
                kind=kind,
                title=title or f"{kind} conversation",
                entry_artefact_id=entry_artefact_id,
                status=status,
                created_at=created_at,
                closed_at=created_at if status == "closed" else None,
                archived_at=created_at if status == "archived" else None,
            )
        )
    return conversation_id


def _chat_turn(
    engine: Engine,
    *,
    conversation_id: uuid.UUID,
    turn_index: int,
    user_message: str,
    answer: str | None,
) -> uuid.UUID:
    """Insert one terminal chat turn with a deterministic index."""
    turn_id = uuid.uuid4()
    stamp = now() + timedelta(seconds=turn_index)
    with engine.begin() as conn:
        conn.execute(
            chat_turn.insert().values(
                id=turn_id,
                conversation_id=conversation_id,
                turn_index=turn_index,
                client_turn_id=uuid.uuid4(),
                user_message=user_message,
                answer=answer,
                answer_payload=None,
                capability_run_id=None,
                status="completed",
                created_at=stamp,
                completed_at=stamp,
            )
        )
    return turn_id


def _planning_turn(engine: Engine, *, project_id: uuid.UUID, conversation_id: uuid.UUID) -> None:
    """Insert one completed planning transcript row for a library preview."""
    stamp = now()
    with engine.begin() as conn:
        conn.execute(
            planning_transcript.insert().values(
                id=uuid.uuid4(),
                project_id=project_id,
                conversation_id=conversation_id,
                client_turn_id=uuid.uuid4(),
                turn_index=0,
                user_message="Plan the evidence review",
                reply="I will prepare the plan.",
                planner_state={},
                response={},
                part=None,
                suggestions=[],
                status="completed",
                created_at=stamp,
                completed_at=stamp,
            )
        )


def test_library_lists_mixed_kinds_filters_archived_and_carries_previews(
    engine: Engine, tmp_path: Path
) -> None:
    """The library is newest-first, owner-scoped, and excludes archived chats by default."""
    with api_client(tmp_path) as (client, owner, _):
        project_id = uuid.UUID(create_project(client, owner))
        chat_id = _conversation(
            engine, project_id=project_id, title="Recent chat", created_at_offset=20
        )
        planning_id = _conversation(
            engine,
            project_id=project_id,
            kind="planning",
            status="closed",
            title="Completed plan",
            created_at_offset=10,
        )
        archived_id = _conversation(
            engine,
            project_id=project_id,
            status="archived",
            title="Archived chat",
            created_at_offset=30,
        )
        _chat_turn(
            engine,
            conversation_id=chat_id,
            turn_index=0,
            user_message="What does the evidence say?",
            answer="The evidence supports the intervention.",
        )
        _planning_turn(engine, project_id=project_id, conversation_id=planning_id)

        listed = client.get(f"/api/v1/projects/{project_id}/conversations", headers=owner)
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()["data"]] == [str(chat_id), str(planning_id)]
        assert listed.json()["data"][0]["latest_turn_preview"] == {
            "user_message": "What does the evidence say?",
            "reply_snippet": "The evidence supports the intervention.",
            "at": listed.json()["data"][0]["latest_turn_preview"]["at"],
        }
        assert listed.json()["data"][1]["latest_turn_preview"]["reply_snippet"] == (
            "I will prepare the plan."
        )

        chats = client.get(
            f"/api/v1/projects/{project_id}/conversations?kind=chat", headers=owner
        )
        assert [item["id"] for item in chats.json()["data"]] == [str(chat_id)]
        active = client.get(
            f"/api/v1/projects/{project_id}/conversations?status=active", headers=owner
        )
        assert [item["id"] for item in active.json()["data"]] == [str(chat_id)]
        closed = client.get(
            f"/api/v1/projects/{project_id}/conversations?status=closed", headers=owner
        )
        assert [item["id"] for item in closed.json()["data"]] == [str(planning_id)]
        archived = client.get(
            f"/api/v1/projects/{project_id}/conversations?status=archived", headers=owner
        )
        assert [item["id"] for item in archived.json()["data"]] == [str(archived_id)]


def test_create_and_patch_chat_context_chip_and_refuse_planning_mutation(
    engine: Engine, tmp_path: Path
) -> None:
    """Only chats are hand-created or editable, and context artefacts stay project-local."""
    with api_client(tmp_path) as (client, owner, _):
        project_id = uuid.UUID(create_project(client, owner))
        entry_artefact_id = _artefact(engine, project_id)
        created = client.post(
            f"/api/v1/projects/{project_id}/conversations",
            headers=owner,
            json={"entry_artefact_id": str(entry_artefact_id)},
        )
        assert created.status_code == 201
        assert created.json()["kind"] == "chat"
        assert created.json()["title"] == "New chat"
        assert created.json()["entry_artefact_id"] == str(entry_artefact_id)
        conversation_id = uuid.UUID(created.json()["id"])
        assert (
            client.post(
                f"/api/v1/projects/{project_id}/conversations",
                headers=owner,
                json={"kind": "planning"},
            ).status_code
            == 422
        )

        renamed = client.patch(
            f"/api/v1/conversations/{conversation_id}",
            headers=owner,
            json={"title": "Useful question"},
        )
        assert renamed.status_code == 200
        assert renamed.json()["title"] == "Useful question"
        cleared = client.patch(
            f"/api/v1/conversations/{conversation_id}",
            headers=owner,
            json={"entry_artefact_id": None},
        )
        assert cleared.status_code == 200
        assert cleared.json()["entry_artefact_id"] is None

        other_project_id = uuid.UUID(create_project(client, owner))
        foreign_artefact_id = _artefact(engine, other_project_id)
        absent = client.post(
            f"/api/v1/projects/{project_id}/conversations",
            headers=owner,
            json={"entry_artefact_id": str(uuid.uuid4())},
        )
        cross_project = client.post(
            f"/api/v1/projects/{project_id}/conversations",
            headers=owner,
            json={"entry_artefact_id": str(foreign_artefact_id)},
        )
        assert cross_project.status_code == absent.status_code == 404
        assert cross_project.json() == absent.json()

        planning_id = _conversation(engine, project_id=project_id, kind="planning")
        refused = client.patch(
            f"/api/v1/conversations/{planning_id}", headers=owner, json={"title": "Nope"}
        )
        assert refused.status_code == 422


def test_archive_round_trip_hides_ordinary_reads_and_turns_until_unarchived(
    engine: Engine, tmp_path: Path
) -> None:
    """Archiving is idempotent and leaves unarchive as the sole archived resolver."""
    with api_client(tmp_path) as (client, owner, _):
        project_id = uuid.UUID(create_project(client, owner))
        chat_id = _conversation(engine, project_id=project_id)
        _chat_turn(
            engine, conversation_id=chat_id, turn_index=0, user_message="Question", answer="Answer"
        )

        archived = client.post(f"/api/v1/conversations/{chat_id}/archive", headers=owner)
        archived_again = client.post(f"/api/v1/conversations/{chat_id}/archive", headers=owner)
        assert archived.status_code == archived_again.status_code == 200
        assert archived.json()["archived_at"] == archived_again.json()["archived_at"]
        for response in (
            client.get(f"/api/v1/conversations/{chat_id}", headers=owner),
            client.patch(f"/api/v1/conversations/{chat_id}", headers=owner, json={"title": "No"}),
            client.get(f"/api/v1/conversations/{chat_id}/turns", headers=owner),
            client.post(
                f"/api/v1/conversations/{chat_id}/turns",
                headers=owner,
                json={"message": "Still there?", "client_turn_id": str(uuid.uuid4())},
            ),
        ):
            assert response.status_code == 404

        restored = client.post(f"/api/v1/conversations/{chat_id}/unarchive", headers=owner)
        restored_again = client.post(f"/api/v1/conversations/{chat_id}/unarchive", headers=owner)
        assert restored.status_code == restored_again.status_code == 200
        assert restored.json()["status"] == restored_again.json()["status"] == "active"
        assert (
            client.get(f"/api/v1/conversations/{chat_id}/turns", headers=owner).status_code == 200
        )

        planning_id = _conversation(engine, project_id=project_id, kind="planning")
        assert (
            client.post(f"/api/v1/conversations/{planning_id}/archive", headers=owner).status_code
            == 422
        )
        assert (
            client.get(f"/api/v1/conversations/{planning_id}/turns", headers=owner).status_code
            == 404
        )


def test_turn_reads_are_ascending_paginated_and_deep_links_hide_archived(
    engine: Engine, tmp_path: Path
) -> None:
    """The rehydration source is ascending, while active and closed deep links resolve."""
    with api_client(tmp_path) as (client, owner, _):
        project_id = uuid.UUID(create_project(client, owner))
        chat_id = _conversation(engine, project_id=project_id)
        for turn_index in range(3):
            _chat_turn(
                engine,
                conversation_id=chat_id,
                turn_index=turn_index,
                user_message=f"Question {turn_index}",
                answer=f"Answer {turn_index}",
            )
        turns = client.get(
            f"/api/v1/conversations/{chat_id}/turns?page=2&page_size=2", headers=owner
        )
        assert turns.status_code == 200
        assert [turn["turn_index"] for turn in turns.json()["data"]] == [2]
        assert turns.json()["pagination"] == {"page": 2, "page_size": 2, "total_items": 3}

        closed_id = _conversation(engine, project_id=project_id, status="closed")
        archived_id = _conversation(engine, project_id=project_id, status="archived")
        assert client.get(f"/api/v1/conversations/{chat_id}", headers=owner).status_code == 200
        assert client.get(f"/api/v1/conversations/{closed_id}", headers=owner).status_code == 200
        assert client.get(f"/api/v1/conversations/{archived_id}", headers=owner).status_code == 404


def test_conversation_routes_keep_cross_owner_and_unknown_resources_indistinguishable(
    engine: Engine, tmp_path: Path
) -> None:
    """Every conversation route preserves the contract's opaque owner boundary."""
    with api_client(tmp_path) as (client, owner, other):
        project_id = uuid.UUID(create_project(client, owner))
        conversation_id = _conversation(engine, project_id=project_id)
        unknown_project = uuid.uuid4()
        unknown_conversation = uuid.uuid4()

        pairs = (
            (
                client.get(f"/api/v1/projects/{project_id}/conversations", headers=other),
                client.get(f"/api/v1/projects/{unknown_project}/conversations", headers=other),
            ),
            (
                client.get(f"/api/v1/conversations/{conversation_id}", headers=other),
                client.get(f"/api/v1/conversations/{unknown_conversation}", headers=other),
            ),
            (
                client.patch(
                    f"/api/v1/conversations/{conversation_id}", headers=other, json={"title": "No"}
                ),
                client.patch(
                    f"/api/v1/conversations/{unknown_conversation}",
                    headers=other,
                    json={"title": "No"},
                ),
            ),
            (
                client.post(f"/api/v1/conversations/{conversation_id}/archive", headers=other),
                client.post(
                    f"/api/v1/conversations/{unknown_conversation}/archive", headers=other
                ),
            ),
            (
                client.get(f"/api/v1/conversations/{conversation_id}/turns", headers=other),
                client.get(f"/api/v1/conversations/{unknown_conversation}/turns", headers=other),
            ),
            (
                client.post(
                    f"/api/v1/projects/{project_id}/conversations", headers=other, json={}
                ),
                client.post(
                    f"/api/v1/projects/{unknown_project}/conversations", headers=other, json={}
                ),
            ),
            (
                client.post(
                    f"/api/v1/conversations/{conversation_id}/turns",
                    headers=other,
                    json={"message": "Hello", "client_turn_id": str(uuid.uuid4())},
                ),
                client.post(
                    f"/api/v1/conversations/{unknown_conversation}/turns",
                    headers=other,
                    json={"message": "Hello", "client_turn_id": str(uuid.uuid4())},
                ),
            ),
            (
                client.post(f"/api/v1/conversations/{conversation_id}/unarchive", headers=other),
                client.post(
                    f"/api/v1/conversations/{unknown_conversation}/unarchive", headers=other
                ),
            ),
            (
                client.post(
                    f"/api/v1/conversations/{conversation_id}/turns/{uuid.uuid4()}/cancel",
                    headers=other,
                ),
                client.post(
                    f"/api/v1/conversations/{unknown_conversation}/turns/{uuid.uuid4()}/cancel",
                    headers=other,
                ),
            ),
        )
        for cross_owner, unknown in pairs:
            assert cross_owner.status_code == unknown.status_code == 404
            assert cross_owner.json() == unknown.json()


def test_chat_chunk_context_resolves_quote(engine: Engine, tmp_path: Path) -> None:
    """A chat citation's chunk id + quote resolves to the clamped context window."""
    from policy_atlas.core.schema import chunk as chunk_table
    from tests.helpers import delete_project_data, seed_source

    project_id: uuid.UUID | None = None
    with api_client(tmp_path) as (client, owner_headers, other_headers):
        try:
            project_id = uuid.UUID(create_project(client, owner_headers))
            chunk_id = uuid.uuid4()
            content = "Before text. " + "x" * 900 + " The quoted evidence span. " + "y" * 900
            with engine.begin() as conn:
                snapshot_id, _ = seed_source(conn, project_id)
                conn.execute(
                    chunk_table.insert().values(
                        chunk_id=chunk_id,
                        source_snapshot_id=snapshot_id,
                        sequence=0,
                        content=content,
                        content_hash="test-hash",
                        locator={"start": 0, "end": len(content)},
                        segmentation_policy="manual_v1",
                        created_at=now(),
                    )
                )
            response = client.get(
                f"/api/v1/projects/{project_id}/chunks/{chunk_id}/context",
                headers=owner_headers,
                params={"quote": "The quoted evidence span."},
            )
            assert response.status_code == 200
            body = response.json()
            assert "The quoted evidence span." in body["context"]
            assert body["clamped"] is True
            cross_owner = client.get(
                f"/api/v1/projects/{project_id}/chunks/{chunk_id}/context",
                headers=other_headers,
                params={"quote": "The quoted evidence span."},
            )
            assert cross_owner.status_code == 404
            missing = client.get(
                f"/api/v1/projects/{project_id}/chunks/{chunk_id}/context",
                headers=owner_headers,
                params={"quote": "not present in the chunk"},
            )
            assert missing.status_code == 404
        finally:
            if project_id is not None:
                with engine.begin() as conn:
                    delete_project_data(conn, project_id)


def test_patch_title_null_is_422(engine: Engine, tmp_path: Path) -> None:
    """Clearing title (unlike entry_artefact_id) is not a legal patch shape."""
    with api_client(tmp_path) as (client, owner, _):
        project_id = uuid.UUID(create_project(client, owner))
        chat_id = _conversation(engine, project_id=project_id)
        response = client.patch(
            f"/api/v1/conversations/{chat_id}", headers=owner, json={"title": None}
        )
        assert response.status_code == 422


def _pending_turn(engine: Engine, *, conversation_id: uuid.UUID) -> uuid.UUID:
    """Insert one pending chat turn with no in-process live cancel handle."""
    turn_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            chat_turn.insert().values(
                id=turn_id,
                conversation_id=conversation_id,
                turn_index=0,
                client_turn_id=uuid.uuid4(),
                user_message="In flight",
                answer=None,
                answer_payload=None,
                capability_run_id=None,
                status="pending",
                created_at=now(),
                completed_at=None,
            )
        )
    return turn_id


def test_cancel_cross_owner_and_unknown_are_byte_identical_404(
    engine: Engine, tmp_path: Path
) -> None:
    """The cancel endpoint keeps the BOLA-opaque 404 rule, like every other route."""
    with api_client(tmp_path) as (client, owner, other):
        project_id = uuid.UUID(create_project(client, owner))
        chat_id = _conversation(engine, project_id=project_id)
        turn_id = _pending_turn(engine, conversation_id=chat_id)
        cross_owner = client.post(
            f"/api/v1/conversations/{chat_id}/turns/{turn_id}/cancel", headers=other
        )
        unknown = client.post(
            f"/api/v1/conversations/{uuid.uuid4()}/turns/{uuid.uuid4()}/cancel", headers=other
        )
        assert cross_owner.status_code == unknown.status_code == 404
        assert cross_owner.json() == unknown.json()


def test_cancel_no_live_generator_cas_and_is_idempotent(engine: Engine, tmp_path: Path) -> None:
    """A pending row with no live handle cancels via CAS, and repeat cancel is a no-op."""
    with api_client(tmp_path) as (client, owner, _):
        project_id = uuid.UUID(create_project(client, owner))
        chat_id = _conversation(engine, project_id=project_id)
        turn_id = _pending_turn(engine, conversation_id=chat_id)

        first = client.post(
            f"/api/v1/conversations/{chat_id}/turns/{turn_id}/cancel", headers=owner
        )
        assert first.status_code == 200
        assert first.json() == {"status": "cancelled"}
        with engine.connect() as conn:
            status = conn.execute(
                select(chat_turn.c.status).where(chat_turn.c.id == turn_id)
            ).scalar_one()
        assert status == "cancelled"

        second = client.post(
            f"/api/v1/conversations/{chat_id}/turns/{turn_id}/cancel", headers=owner
        )
        assert second.status_code == 200
        assert second.json() == {"status": "cancelled"}


def test_cancel_after_completion_is_a_conflict_free_no_op(engine: Engine, tmp_path: Path) -> None:
    """Cancelling an already-terminal turn reports its real status, never an error."""
    with api_client(tmp_path) as (client, owner, _):
        project_id = uuid.UUID(create_project(client, owner))
        chat_id = _conversation(engine, project_id=project_id)
        turn_id = _chat_turn(
            engine, conversation_id=chat_id, turn_index=0, user_message="Q", answer="A"
        )
        response = client.post(
            f"/api/v1/conversations/{chat_id}/turns/{turn_id}/cancel", headers=owner
        )
        assert response.status_code == 200
        assert response.json() == {"status": "completed"}
        with engine.connect() as conn:
            status = conn.execute(
                select(chat_turn.c.status).where(chat_turn.c.id == turn_id)
            ).scalar_one()
        assert status == "completed"
