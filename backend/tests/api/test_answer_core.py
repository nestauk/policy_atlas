"""Contract tests for the shared, row-free grounded-answer core.

The chat route and a Task Agent turn held at a scoping walk's baseline gate
answer the same way. These tests pin the half that is shared: an answer over a
**paused** walk's pinned scope, with citations resolved to real documents and
nothing durable written — and the half that is not: the chat route still
refuses to open a turn while a walk is paused.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.engine import Engine

from policy_atlas.api.answer_core import AnswerBackends, answer_over_scope
from policy_atlas.api.app import ApiConflict
from policy_atlas.api.chat_scope import resolve_run_components
from policy_atlas.core import events
from policy_atlas.core.schema import (
    capability_run,
    chat_turn,
    chunk,
    conversation,
    runs,
    source_snapshot,
    task,
    task_source_snapshot,
)
from policy_atlas.runtime.chat_backend import StubChatBackend
from tests.api.test_chat_turns import _chat
from tests.helpers import now
from tests.runtime.test_runner import _cleanup, _seed_task

_SCOPING_COMPONENTS = ("characterise", "select", "extract", "group")


def _paused_scoping_walk(
    engine: Engine, *, task_id: uuid.UUID, scope_id: uuid.UUID
) -> uuid.UUID:
    """Persist an options-scoping walk parked on its baseline gate.

    The walk's component attempts are seeded the way the chat-scope tests seed
    a completed walk's — ``run.started`` events over ``runs`` rows — because the
    resolver reduces both identically; only the walk's status differs.
    """
    capability_run_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            update(task)
            .where(task.c.task_id == task_id)
            .values(capability="options_scoping")
        )
        conn.execute(
            capability_run.insert().values(
                capability_run_id=capability_run_id,
                task_id=task_id,
                evidence_scope_id=scope_id,
                capability="options_scoping",
                plan_id=uuid.uuid4(),
                plan_version=1,
                status="paused",
                started_at=now(),
                ended_at=None,
            )
        )
        for component in _SCOPING_COMPONENTS:
            run_id = uuid.uuid4()
            conn.execute(
                runs.insert().values(
                    run_id=run_id,
                    task_id=task_id,
                    status="succeeded",
                    started_at=now(),
                    ended_at=now(),
                    capability_run_id=capability_run_id,
                )
            )
            events.append(
                conn,
                task_id=task_id,
                run_id=run_id,
                event_type="run.started",
                payload={"component": component, "registry_component": component},
            )
    return capability_run_id


def _first_seeded_chunk(engine: Engine, task_id: uuid.UUID) -> tuple[str, str]:
    """Return one of the fixture's real chunk ids and its document title."""
    with engine.connect() as conn:
        row = (
            conn.execute(
                select(chunk.c.chunk_id, source_snapshot.c.metadata)
                .select_from(
                    chunk.join(
                        source_snapshot,
                        source_snapshot.c.source_snapshot_id == chunk.c.source_snapshot_id,
                    ).join(
                        task_source_snapshot,
                        task_source_snapshot.c.source_snapshot_id
                        == source_snapshot.c.source_snapshot_id,
                    )
                )
                .where(task_source_snapshot.c.task_id == task_id)
                .order_by(chunk.c.sequence.asc())
                .limit(1)
            )
            .mappings()
            .one()
        )
    metadata = row["metadata"] if isinstance(row["metadata"], dict) else {}
    return str(row["chunk_id"]), str(metadata.get("title"))


def _citing_tools(chunk_record_id: str) -> object:
    """Build a tool set returning one appraised chunk, as the chat tests do."""

    def _build(**_: object) -> dict[str, object]:
        return {
            "search_chunks": lambda _arguments: {
                "chunks": [
                    {
                        "chunk_record_id": chunk_record_id,
                        "content": "Evidence text.",
                        "appraised": True,
                    }
                ]
            },
            "query_findings": lambda _arguments: {"findings": []},
            "lookup": lambda _arguments: {"result": {}},
        }

    return _build


def test_answers_over_a_paused_walk_without_writing_a_row(engine: Engine) -> None:
    """A paused walk's scope answers with resolved citations and no durable row."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = _seed_task(engine)
        capability_run_id = _paused_scoping_walk(
            engine, task_id=task_id, scope_id=scope_id
        )
        chunk_id, title = _first_seeded_chunk(engine, task_id)

        scope = resolve_run_components(
            engine, task_id, capability_run_id=capability_run_id
        )
        assert scope is not None
        assert scope.capability_run_id == capability_run_id

        deltas: list[str] = []
        prose, payload = answer_over_scope(
            engine,
            task_id=task_id,
            trace_session_id=task_id,
            scope=scope,
            entry_artefact_id=None,
            window=[],
            question="What does the baseline say?",
            backends=AnswerBackends(
                chat=StubChatBackend(),
                tools_builder=_citing_tools(chunk_id),  # type: ignore[arg-type]
            ),
            trace_run_id=uuid.uuid4(),
            on_delta=deltas.append,
        )

        assert prose
        assert "".join(deltas) == prose
        assert payload.citations[0]["id"] == chunk_id
        # Resolved to a document, not left as a durable id (the chat rule).
        assert payload.citations[0]["source_title"] == title
        assert payload.citations[0]["source_id"]
        assert payload.evidence_not_held is False
        assert payload.stopped_before_evidence_check is False
        assert payload.as_payload()["enrichment"] == {"status": "pending"}

        with engine.connect() as conn:
            conversations = conn.execute(
                select(func.count())
                .select_from(conversation)
                .where(conversation.c.task_id == task_id)
            ).scalar_one()
            turns = conn.execute(
                select(func.count())
                .select_from(chat_turn)
                .join(conversation, chat_turn.c.conversation_id == conversation.c.id)
                .where(conversation.c.task_id == task_id)
            ).scalar_one()
        assert conversations == 0
        assert turns == 0
    finally:
        _cleanup(engine, task_id)


def test_paused_walk_resolver_is_bound_to_its_task_and_status(engine: Engine) -> None:
    """The pinned resolver refuses another task's walk and a non-answerable one."""
    task_id: uuid.UUID | None = None
    other_task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = _seed_task(engine)
        other_task_id, _other_scope_id = _seed_task(engine)
        capability_run_id = _paused_scoping_walk(
            engine, task_id=task_id, scope_id=scope_id
        )

        assert (
            resolve_run_components(
                engine, other_task_id, capability_run_id=capability_run_id
            )
            is None
        )
        with engine.begin() as conn:
            conn.execute(
                update(capability_run)
                .where(capability_run.c.capability_run_id == capability_run_id)
                .values(status="aborted")
            )
        assert (
            resolve_run_components(engine, task_id, capability_run_id=capability_run_id)
            is None
        )
    finally:
        _cleanup(engine, other_task_id)
        _cleanup(engine, task_id)


def test_chat_route_still_refuses_a_paused_walk(engine: Engine) -> None:
    """Lifting the answer core does not open the chat route while a walk is paused."""
    from policy_atlas.api import chat_turns

    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id, conversation_id = _chat(engine)
        _paused_scoping_walk(engine, task_id=task_id, scope_id=scope_id)
        with pytest.raises(ApiConflict) as raised:
            chat_turns.run_chat_turn(
                engine,
                task_id=task_id,
                conversation_id=conversation_id,
                user_id="chat-owner",
                message="What does the baseline say?",
                client_turn_id=uuid.uuid4(),
                chat_backend=StubChatBackend(),
            )
        assert raised.value.code == "run_active"
    finally:
        _cleanup(engine, task_id)
