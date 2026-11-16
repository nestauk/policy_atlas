"""Names written by a model: a task's from its confirmed question, a chat's (task 058, round 14)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.api.lifecycle import rename_task
from policy_atlas.api.routers.task_agent import _confirmed_question
from policy_atlas.api.titles import name_chat_from_message, name_task_from_question
from policy_atlas.core import events
from policy_atlas.core.schema import conversation, task
from policy_atlas.runtime.agent_backend import StubAgentBackend
from policy_atlas.runtime.title_prompt import TASK_TITLE_PROMPT_VERSION, TITLE_MAX_CHARS
from tests.helpers import delete_task_data, now, seed_task_and_run

QUESTION = "What works to reduce childhood obesity in primary schools in Leeds?"


@pytest.fixture
def task_id(engine: Engine) -> Iterator[uuid.UUID]:
    with engine.begin() as conn:
        created, _run = seed_task_and_run(conn)
        conn.execute(task.update().where(task.c.task_id == created).values(name=QUESTION[:-1]))
    yield created
    with engine.begin() as conn:
        delete_task_data(conn, created)


def _name(engine: Engine, task_id: uuid.UUID) -> str:
    with engine.connect() as conn:
        return str(conn.execute(select(task.c.name).where(task.c.task_id == task_id)).scalar_one())


def _renames(engine: Engine, task_id: uuid.UUID) -> list[dict[str, object]]:
    with engine.connect() as conn:
        return [
            entry["payload"]
            for entry in events.read(conn, task_id)
            if entry["event_type"] == "task.renamed"
        ]


def test_the_confirmed_question_names_the_task_as_policy_atlas(
    engine: Engine, task_id: uuid.UUID
) -> None:
    agent = StubAgentBackend(title_responses='"Childhood obesity in Leeds schools."')
    assert name_task_from_question(engine, agent, task_id=task_id, question=QUESTION) == (
        "Childhood obesity in Leeds schools"
    )
    assert _name(engine, task_id) == "Childhood obesity in Leeds schools"
    assert agent.title_calls == [("task", QUESTION)]
    [renamed] = _renames(engine, task_id)
    assert renamed["actor"] == "agent"
    assert renamed["prompt_version"] == TASK_TITLE_PROMPT_VERSION
    assert renamed["question"] == QUESTION
    # The same question again: no second call.
    assert name_task_from_question(engine, agent, task_id=task_id, question=QUESTION) is None
    assert len(agent.title_calls) == 1
    # A new confirmed question names it again.
    agent2 = StubAgentBackend(title_responses="School meals in Leeds")
    assert (
        name_task_from_question(engine, agent2, task_id=task_id, question="What about meals?")
        == "School meals in Leeds"
    )


def test_a_task_the_user_renamed_keeps_its_name(engine: Engine, task_id: uuid.UUID) -> None:
    with engine.begin() as conn:
        rename_task(conn, task_id, "My own name", "user-subject")
    agent = StubAgentBackend(title_responses="Childhood obesity in Leeds")
    assert name_task_from_question(engine, agent, task_id=task_id, question=QUESTION) is None
    assert agent.title_calls == []
    assert _name(engine, task_id) == "My own name"


def test_a_failed_or_empty_call_keeps_the_name(engine: Engine, task_id: uuid.UUID) -> None:
    class _Down(StubAgentBackend):
        def write_title(self, kind: str, text: str, **_: object) -> str | None:
            raise RuntimeError("model unavailable")

    before = _name(engine, task_id)
    assert name_task_from_question(engine, _Down(), task_id=task_id, question=QUESTION) is None
    assert name_task_from_question(
        engine, StubAgentBackend(), task_id=task_id, question=QUESTION
    ) is None
    assert _name(engine, task_id) == before
    assert _renames(engine, task_id) == []


def test_the_turn_hook_reads_the_question_part_answer() -> None:
    class _Draft:
        question = "The refined question"

    confirm = [{"role": "user", "text": "Yes\n\n[confirm part=question option=as_written]"}]
    other = [{"role": "user", "text": "Yes\n\n[confirm part=scope option=uk]"}]
    assert _confirmed_question(confirm, _Draft()) == "The refined question"
    # Another part's answer, or a plain message, names nothing (round 14:
    # the name comes at the question's decision, not at plan approval).
    assert _confirmed_question(other, _Draft()) is None
    assert _confirmed_question([{"role": "user", "text": "Go"}], _Draft()) is None
    assert _confirmed_question([], _Draft()) is None


def test_a_chats_first_message_is_titled_in_place_of_its_cut(
    engine: Engine, task_id: uuid.UUID
) -> None:
    conversation_id = uuid.uuid4()
    message = "Which of the trials measured attendance as well as weight, and over what period?"
    cut = message[:TITLE_MAX_CHARS]
    with engine.begin() as conn:
        conn.execute(
            conversation.insert().values(
                id=conversation_id,
                task_id=task_id,
                kind="chat",
                title=cut,
                status="active",
                created_at=now(),
            )
        )

    def title() -> str:
        with engine.connect() as conn:
            return str(
                conn.execute(
                    select(conversation.c.title).where(conversation.c.id == conversation_id)
                ).scalar_one()
            )

    # Nothing written: the cut stays.
    assert (
        name_chat_from_message(
            engine,
            StubAgentBackend(),
            conversation_id=conversation_id,
            message=message,
            placeholder=cut,
        )
        is None
    )
    assert title() == cut
    written = name_chat_from_message(
        engine,
        StubAgentBackend(title_responses="Attendance and weight trials"),
        conversation_id=conversation_id,
        message=message,
        placeholder=cut,
    )
    assert written == title() == "Attendance and weight trials"
    # A chat titled meanwhile (the user renamed it) is left alone.
    assert (
        name_chat_from_message(
            engine,
            StubAgentBackend(title_responses="Something else"),
            conversation_id=conversation_id,
            message=message,
            placeholder=cut,
        )
        is None
    )
    assert title() == "Attendance and weight trials"
