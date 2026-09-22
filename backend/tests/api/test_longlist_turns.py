"""The Task Agent's longlist verbs (task 045 Phase 7.2, S11; deliverable 10).

The contract's verbs bullet: a turn while the longlist exists and no walk is
active is sorted; a question is answered over the union of the longlist and
targeted scopes with citations, including a document only an option search
found; a document screened in under two scopes is one row with the longlist
scope's labels; a verb is confirmed before it is applied and never inferred;
*add* proposes a design through ``option_design_v1``, mints *added by you*
and opens a child walk with no parent that never closes the conversation;
*exclude* records the reason; the buttons and the verbs write the same state
and one History event each; a turn while a walk runs is ``run_active``; an
Evidence search task's turns are unchanged; the ordinary chat resolves the
longlist walk after it runs; ``RetrievalUnitCapError`` is answered honestly.

The longlist is the real component's, built by 6.1's fixture
(``test_longlist_routes._build``) and committed.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.engine import Connection, Engine

from policy_atlas.api import longlist_turns
from policy_atlas.api.chat_scope import build_chat_readers, resolve_terminal_run_components
from policy_atlas.api.deps import (
    get_agent_backend,
    get_chat_backend,
    get_chat_embedding_backend,
    get_runner_backends,
    get_scoping_task_agent_backend,
)
from policy_atlas.core import events
from policy_atlas.core.embeddings import StubEmbeddingBackend
from policy_atlas.core.schema import (
    EVIDENCE_TYPES,
    capability_run,
    conversation,
    evidence_scope,
    longlist_result,
    option,
    runs,
    source_appraisal_result,
    source_classification_result,
    source_screening_result,
    source_snapshot,
    task_agent_transcript,
    task_link,
    task_source_snapshot,
)
from policy_atlas.evidence_search.assess.appraise import DEFAULT_RUBRIC_VERSION
from policy_atlas.evidence_search.synthesis.synthesis_tools import RetrievalUnitCapError
from policy_atlas.options_scoping.design import OptionDesign
from policy_atlas.runtime import option_search
from policy_atlas.runtime.agent_backend import StubAgentBackend
from policy_atlas.runtime.chat_backend import StubChatBackend
from policy_atlas.runtime.conversation_lifecycle import ensure_active_task_agent_conversation
from policy_atlas.runtime.longlist_verbs_prompt import LonglistVerbWire
from policy_atlas.runtime.option_design_prompt import OptionDesignWire
from tests.api.resource_support import api_client, create_task
from tests.api.test_longlist_routes import (
    _await_walks_ended,
    _Built,
    _clients,
    _decisions,
    _org_build,
    _remove_committed_tasks,  # noqa: F401 — the autouse teardown applies here too
)
from tests.helpers import now, seed_ingested_full_text
from tests.options_scoping.test_longlist import RCT
from tests.runtime.test_option_search import (
    _design,
    _longlist_plan,
    _seed_longlist,
    _seed_option,
)
from tests.runtime.test_runner import _cleanup, _runner_backends

_CONFIRM = f"Confirm\n\n[confirm part={longlist_turns.ACTION_PART_ID} option=confirm]"
_OTHER_TYPE = next(kind for kind in EVIDENCE_TYPES if kind != RCT)

# --- doubles ---------------------------------------------------------------------


class _NoPlanner:
    """The scoping planner: never reached while a longlist exists."""

    def scope_turn(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("a longlist turn reached the planner")


def _sort(kind: str, **values: Any) -> LonglistVerbWire:
    return LonglistVerbWire(kind=kind, sort_reason="scripted", **values)


def _assent() -> LonglistVerbWire:
    return _sort("other", assents_to_pending=True)


def _agent(*sorts: LonglistVerbWire, design: OptionDesignWire | None = None) -> StubAgentBackend:
    # The stub repeats its last entry once the queue drains; a trailing
    # ``other`` keeps an unscripted turn honest.
    return StubAgentBackend(
        longlist_sort_responses=[*sorts, _sort("other")],
        option_design_responses=design,
    )


class _Holder:
    """The agent a test scripts once it knows the option ids (resolved per request)."""

    def __init__(self, agent: StubAgentBackend | None = None) -> None:
        self.agent = agent if agent is not None else _agent()


def _overrides(
    agent: StubAgentBackend | _Holder,
) -> dict[Callable[..., object], Callable[..., object]]:
    holder = agent if isinstance(agent, _Holder) else _Holder(agent)
    return {
        get_agent_backend: lambda: holder.agent,
        get_scoping_task_agent_backend: lambda: _NoPlanner(),
        get_chat_backend: lambda: StubChatBackend(),
        get_chat_embedding_backend: lambda: StubEmbeddingBackend(),
        get_runner_backends: _runner_backends,
    }


def _turn(
    client: TestClient, headers: dict[str, str], task_id: uuid.UUID | str, message: str
) -> Any:
    return client.post(
        f"/api/v1/tasks/{task_id}/task-agent-turns",
        headers=headers,
        json={"message": message, "client_turn_id": str(uuid.uuid4())},
    )


def _option_row(engine: Engine, option_id: uuid.UUID) -> Any:
    with engine.connect() as conn:
        return conn.execute(select(option).where(option.c.option_id == option_id)).one()


def _latest_row(engine: Engine, task_id: uuid.UUID) -> Any:
    with engine.connect() as conn:
        return conn.execute(
            select(task_agent_transcript)
            .where(task_agent_transcript.c.task_id == task_id)
            .order_by(task_agent_transcript.c.turn_index.desc())
            .limit(1)
        ).one()


# --- evidence helpers -----------------------------------------------------------------


def _walk(
    conn: Connection,
    built: _Built,
    *,
    parent: uuid.UUID | None,
    status: str = "succeeded",
    purpose: str = "targeted",
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """An option search's walk (a child, or parentless like *add*'s) and one run.

    Returns:
        ``(scope_id, walk_id, run_id)``.
    """
    scope_id, walk_id, run_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    conn.execute(
        evidence_scope.insert().values(
            evidence_scope_id=scope_id,
            task_id=built.task_id,
            intent=f"{purpose} intent",
            context={},
            created_at=now(),
            purpose=purpose,
        )
    )
    conn.execute(
        capability_run.insert().values(
            capability_run_id=walk_id,
            task_id=built.task_id,
            evidence_scope_id=scope_id,
            capability="options_scoping",
            plan_id=uuid.uuid4(),
            plan_version=2,
            status=status,
            started_at=now(),
            ended_at=now() if status in ("succeeded", "degraded") else None,
            parent_capability_run_id=parent,
        )
    )
    conn.execute(
        runs.insert().values(
            run_id=run_id,
            task_id=built.task_id,
            status="succeeded",
            started_at=now(),
            capability_run_id=walk_id,
        )
    )
    return scope_id, walk_id, run_id


def _doc(conn: Connection, task_id: uuid.UUID, title: str) -> uuid.UUID:
    snapshot_id, tss_id = uuid.uuid4(), uuid.uuid4()
    conn.execute(
        source_snapshot.insert().values(
            source_snapshot_id=snapshot_id,
            content_hash=str(uuid.uuid4()),
            text_basis="abstract_only",
            source_locator=f"https://example.org/{snapshot_id}",
            metadata={"title": title},
            created_at=now(),
        )
    )
    conn.execute(
        task_source_snapshot.insert().values(
            task_source_snapshot_id=tss_id,
            task_id=task_id,
            source_snapshot_id=snapshot_id,
            origin="acquired",
            run_id=None,
            ingested_at=now(),
        )
    )
    return tss_id


def _screen(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    scope_id: uuid.UUID,
    tss_id: uuid.UUID,
    run_id: uuid.UUID,
    evidence_type: str | None = None,
    score: int | None = None,
    age: timedelta = timedelta(0),
) -> None:
    """Screen a document in under a scope, with that scope's labels when given."""
    at = now() - age
    conn.execute(
        source_screening_result.insert().values(
            source_screening_result_id=uuid.uuid4(),
            evidence_scope_id=scope_id,
            task_source_snapshot_id=tss_id,
            task_id=task_id,
            screened_by_run_id=run_id,
            status="relevant",
            screen_basis="title_abstract",
            screen_decision_confidence=0.9,
            screen_stage=1,
            screen_generation=0,
            screened_at=at,
        )
    )
    if evidence_type is not None:
        conn.execute(
            source_classification_result.insert().values(
                source_classification_result_id=uuid.uuid4(),
                evidence_scope_id=scope_id,
                task_source_snapshot_id=tss_id,
                task_id=task_id,
                classified_by_run_id=run_id,
                primary_evidence_type=evidence_type,
                classified_at=at,
            )
        )
    if score is not None:
        conn.execute(
            source_appraisal_result.insert().values(
                source_appraisal_result_id=uuid.uuid4(),
                evidence_scope_id=scope_id,
                task_source_snapshot_id=tss_id,
                task_id=task_id,
                appraised_by_run_id=run_id,
                quality_score=score,
                rubric_version=DEFAULT_RUBRIC_VERSION,
                appraised_at=at,
            )
        )


def _release_shared_document(engine: Engine, tss_id: uuid.UUID) -> None:
    """Undo what this file added to a document two tasks share, before the teardown.

    6.1's teardown deletes the target's row for a shared snapshot first; a
    screening row and a full-text snapshot on it would block or orphan that.
    """
    from policy_atlas.core.schema import chunk, chunk_embedding

    with engine.begin() as conn:
        conn.execute(
            source_screening_result.delete().where(
                source_screening_result.c.task_source_snapshot_id == tss_id
            )
        )
        full = conn.execute(
            select(task_source_snapshot.c.full_text_snapshot_id).where(
                task_source_snapshot.c.task_source_snapshot_id == tss_id
            )
        ).scalar_one()
        conn.execute(
            update(task_source_snapshot)
            .where(task_source_snapshot.c.task_source_snapshot_id == tss_id)
            .values(full_text_snapshot_id=None, full_text_status="not_attempted")
        )
        if full is not None:
            chunk_ids = select(chunk.c.chunk_id).where(chunk.c.source_snapshot_id == full)
            conn.execute(chunk_embedding.delete().where(chunk_embedding.c.chunk_id.in_(chunk_ids)))
            conn.execute(chunk.delete().where(chunk.c.source_snapshot_id == full))
            conn.execute(
                source_snapshot.delete().where(source_snapshot.c.source_snapshot_id == full)
            )


def _chunk_ids(conn: Connection, tss_id: uuid.UUID) -> set[str]:
    from policy_atlas.core.schema import chunk

    full = conn.execute(
        select(task_source_snapshot.c.full_text_snapshot_id).where(
            task_source_snapshot.c.task_source_snapshot_id == tss_id
        )
    ).scalar_one()
    return {
        str(value)
        for value in conn.execute(
            select(chunk.c.chunk_id).where(chunk.c.source_snapshot_id == full)
        ).scalars()
    }


# --- the sort, the scope set and a question ------------------------------------------


def test_a_question_is_answered_over_the_longlist_and_its_option_searches(
    engine: Engine, tmp_path: Path
) -> None:
    """A document only an option search found is searched and cited."""
    agent = _agent(_sort("question"))
    with _clients(tmp_path, engine, _overrides(agent)) as (client, (owner, colleague, _)):
        built = _org_build(engine, owner, colleague, linked=False)
        with engine.begin() as conn:
            child_scope, _child, child_run = _walk(conn, built, parent=built.walk_id)
            found = _doc(conn, built.task_id, "Only the option search found this")
            _screen(
                conn,
                task_id=built.task_id,
                scope_id=child_scope,
                tss_id=found,
                run_id=child_run,
                evidence_type=RCT,
                score=4,
            )
            seed_ingested_full_text(
                conn, tss_id=found, chunks=["Mentoring cut the NEET rate by a third."]
            )
            chunk_ids = _chunk_ids(conn, found)

        response = _turn(client, owner.headers, built.task_id, "Which options have evidence?")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["kind"] == "answer"
        citation = body["answer"]["citations"][0]
        assert citation["id"] in chunk_ids
        assert citation["source_id"] == str(found)
        assert citation["source_title"] == "Only the option search found this"
        assert citation["appraisal_label"] and "appraisal_score" not in citation
        # The sort saw the longlist, and a question applies nothing.
        sent = agent.longlist_sort_inputs[0]
        assert {o["id"] for o in sent["options"]} == {str(v) for v in built.options.values()}
        assert {o["state"] for o in sent["options"]} <= {"included", "excluded"}
        assert sent["pending"] is None
        assert _decisions(client, built, owner.headers) == []


def test_an_inherited_document_is_cited_with_its_inherited_label(
    engine: Engine, tmp_path: Path
) -> None:
    """Labels read across a link reach the retriever and the citation alike."""
    agent = _agent(_sort("question"))
    with _clients(tmp_path, engine, _overrides(agent)) as (client, (owner, colleague, _)):
        built = _org_build(engine, owner, colleague, linked=True)
        with engine.begin() as conn:
            link = conn.execute(
                select(task_link).where(task_link.c.target_task_id == built.task_id)
            ).one()
            source_scope = conn.execute(
                select(capability_run.c.evidence_scope_id).where(
                    capability_run.c.capability_run_id == link.source_capability_run_id
                )
            ).scalar_one()
            source_tss, snapshot_id = conn.execute(
                select(
                    task_source_snapshot.c.task_source_snapshot_id,
                    task_source_snapshot.c.source_snapshot_id,
                ).where(task_source_snapshot.c.task_id == built.source_task_id)
            ).one()
            own = conn.execute(
                select(task_source_snapshot.c.task_source_snapshot_id)
                .where(task_source_snapshot.c.task_id == built.task_id)
                .where(task_source_snapshot.c.source_snapshot_id == snapshot_id)
            ).scalar_one()
            source_run = conn.execute(
                select(runs.c.run_id).where(runs.c.task_id == built.source_task_id)
            ).scalar_one()
            conn.execute(
                source_appraisal_result.insert().values(
                    source_appraisal_result_id=uuid.uuid4(),
                    evidence_scope_id=source_scope,
                    task_source_snapshot_id=source_tss,
                    task_id=built.source_task_id,
                    appraised_by_run_id=source_run,
                    quality_score=5,
                    rubric_version=DEFAULT_RUBRIC_VERSION,
                    appraised_at=now(),
                )
            )
            # Screened in under the longlist scope, never labelled there.
            _screen(
                conn,
                task_id=built.task_id,
                scope_id=built.scope_id,
                tss_id=own,
                run_id=built.run_id,
            )
            seed_ingested_full_text(conn, tss_id=own, chunks=["The deep read found gains."])

        try:
            response = _turn(client, owner.headers, built.task_id, "What did the deep read find?")
            assert response.status_code == 200, response.text
            citation = response.json()["answer"]["citations"][0]
            assert citation["source_id"] == str(own)
            assert citation["evidence_type"] == RCT
            assert citation["appraisal_label"]
        finally:
            _release_shared_document(engine, own)


def test_a_document_in_two_scopes_is_one_row_with_the_longlist_labels(
    engine: Engine, tmp_path: Path
) -> None:
    """P13: the longlist scope's row wins; between two others, the latest."""
    with _clients(tmp_path, engine) as (_client, (owner, colleague, _)):
        built = _org_build(engine, owner, colleague, linked=False)
        with engine.begin() as conn:
            child_scope, _c, child_run = _walk(conn, built, parent=built.walk_id)
            added_scope, _a, added_run = _walk(conn, built, parent=None)
            both = _doc(conn, built.task_id, "Screened in twice")
            # The child screened it later, with other labels: the longlist's win.
            _screen(
                conn,
                task_id=built.task_id,
                scope_id=built.scope_id,
                tss_id=both,
                run_id=built.run_id,
                evidence_type=RCT,
                score=5,
                age=timedelta(hours=1),
            )
            _screen(
                conn,
                task_id=built.task_id,
                scope_id=child_scope,
                tss_id=both,
                run_id=child_run,
                evidence_type=_OTHER_TYPE,
                score=2,
            )
            seed_ingested_full_text(conn, tss_id=both, chunks=["One", "Two"])
            # In two option searches only: the later screen's labels.
            pair = _doc(conn, built.task_id, "Found by two option searches")
            _screen(
                conn,
                task_id=built.task_id,
                scope_id=child_scope,
                tss_id=pair,
                run_id=child_run,
                evidence_type=_OTHER_TYPE,
                score=2,
                age=timedelta(hours=1),
            )
            _screen(
                conn,
                task_id=built.task_id,
                scope_id=added_scope,
                tss_id=pair,
                run_id=added_run,
                evidence_type=RCT,
                score=3,
            )

        scope = resolve_terminal_run_components(engine, task_id=built.task_id)
        assert scope is not None
        assert set(scope.extra_scope_ids) == {child_scope, added_scope}
        retriever, _findings, lookup = build_chat_readers(engine, scope, built.task_id)
        docs = retriever._scope.docs  # noqa: SLF001 — the frozen retrieval substrate
        assert docs[str(both)]["primary_evidence_type"] == RCT
        assert docs[str(both)]["appraisal_tier"] == "5"
        units = [u for u in retriever._scope.units if u["tss_id"] == str(both)]  # noqa: SLF001
        assert len(units) == 2  # one row per document: its chunks are not doubled
        assert docs[str(pair)]["primary_evidence_type"] == RCT
        assert docs[str(pair)]["appraisal_tier"] == "3"
        assert lookup({"kind": "classification_by_doc", "doc_id": str(both)})["result"] == {
            "primary_evidence_type": RCT
        }
        assert lookup({"kind": "appraisal_by_doc", "doc_id": str(both)})["result"][
            "quality_score"
        ] == 5


def test_the_ordinary_chat_resolves_the_longlist_walk_after_it_runs(
    engine: Engine, tmp_path: Path
) -> None:
    """A8: the longlist walk and every option search once it runs; the baseline before."""
    with _clients(tmp_path, engine) as (_client, (owner, colleague, _)):
        built = _org_build(engine, owner, colleague, linked=False)
        with engine.begin() as conn:
            baseline_scope, baseline_walk, _run = _walk(
                conn, built, parent=None, purpose="baseline"
            )
            conn.execute(
                update(capability_run)
                .where(capability_run.c.capability_run_id == baseline_walk)
                .values(started_at=now() - timedelta(days=1))
            )
            child_scope, _c, _r = _walk(conn, built, parent=built.walk_id)
            added_scope, _a, _r2 = _walk(conn, built, parent=None)

        after = resolve_terminal_run_components(engine, task_id=built.task_id)
        assert after is not None
        assert after.capability_run_id == built.walk_id
        assert after.evidence_scope_id == built.scope_id
        assert after.extra_scope_ids == (child_scope, added_scope)

        # Before the longlist walk has run to the end, the chat reads the
        # baseline — never an option search, which is newer.
        with engine.begin() as conn:
            conn.execute(
                update(capability_run)
                .where(capability_run.c.capability_run_id == built.walk_id)
                .values(status="running", ended_at=None)
            )
        before = resolve_terminal_run_components(engine, task_id=built.task_id)
        assert before is not None
        assert before.capability_run_id == baseline_walk
        assert before.evidence_scope_id == baseline_scope
        assert before.extra_scope_ids == ()
        with engine.begin() as conn:
            conn.execute(longlist_result.delete().where(longlist_result.c.task_id == built.task_id))
            conn.execute(
                update(capability_run)
                .where(capability_run.c.capability_run_id == built.walk_id)
                .values(status="aborted", ended_at=now())
            )
        assert resolve_terminal_run_components(engine, task_id=built.task_id) == before


def test_a_retrieval_cap_is_answered_honestly(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _too_many(*_args: Any, **_kwargs: Any) -> Any:
        raise RetrievalUnitCapError(unit_count=10, cap=1)

    monkeypatch.setattr(longlist_turns, "answer_over_scope", _too_many)
    agent = _agent(_sort("question"))
    with _clients(tmp_path, engine, _overrides(agent)) as (client, (owner, colleague, _)):
        built = _org_build(engine, owner, colleague, linked=False)
        response = _turn(client, owner.headers, built.task_id, "What works?")
        assert response.status_code == 200, response.text
        assert response.json()["kind"] == "reply"
        assert response.json()["reply"] == longlist_turns.TOO_MANY_DOCUMENTS_REPLY
        assert _latest_row(engine, built.task_id).status == "completed"


def test_other_with_nothing_pending_says_what_the_chat_can_do(
    engine: Engine, tmp_path: Path
) -> None:
    agent = _agent()
    with _clients(tmp_path, engine, _overrides(agent)) as (client, (owner, colleague, _)):
        built = _org_build(engine, owner, colleague, linked=False)
        response = _turn(client, owner.headers, built.task_id, "Assess the options for me")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["reply"] == longlist_turns.OTHER_REPLY
        assert body["kind"] == "reply" and body["part"] is None
        assert agent.longlist_sort_calls == 1


# --- the verbs: proposed, then applied ------------------------------------------------


def test_exclude_is_proposed_then_applied_on_assent_and_writes_what_the_button_writes(
    engine: Engine, tmp_path: Path
) -> None:
    """Two turns; the reason is recorded; the same rows as the button route."""
    holder = _Holder()
    with _clients(tmp_path, engine, _overrides(holder)) as (client, (owner2, colleague, _)):
        built = _org_build(engine, owner2, colleague, linked=False)
        mentoring = built.options["Mentoring"]
        agent = holder.agent = _agent(
            _sort("exclude", option_id=str(mentoring), reason="volunteers cannot deliver it"),
            _assent(),
        )
        proposed = _turn(
            client,
            owner2.headers,
            built.task_id,
            "Exclude mentoring, volunteers cannot deliver it",
        )
        assert proposed.status_code == 200, proposed.text
        body = proposed.json()
        assert body["reply"] == (
            "Exclude *Mentoring*? Reason: *volunteers cannot deliver it*. Confirm to apply."
        )
        assert body["kind"] == "reply" and body["action"] is None
        assert body["part"]["id"] == "longlist_action"
        assert [o["id"] for o in body["part"]["options"]] == ["confirm"]
        # Never applied on the turn that names it.
        assert _option_row(engine, mentoring).state == "included"
        assert _decisions(client, built, owner2.headers) == []
        assert _latest_row(engine, built.task_id).task_agent_state["pending"]["verb"] == "exclude"

        applied = _turn(client, owner2.headers, built.task_id, "Yes, go ahead")
        assert applied.status_code == 200, applied.text
        action = applied.json()
        assert action["kind"] == "action"
        assert action["action"] == {
            "verb": "exclude",
            "option_id": str(mentoring),
            "label": "Mentoring",
            "capability_run_id": None,
        }
        assert action["reply"] == "Excluded *Mentoring*."
        assert agent.longlist_sort_inputs[1]["pending"] == {
            "verb": "exclude",
            "label": "Mentoring",
        }
        verb_row = _option_row(engine, mentoring)
        assert verb_row.state == "excluded"
        assert verb_row.exclusion == {
            "constraint": "your decision",
            "reason": "volunteers cannot deliver it",
            "by": "user",
        }
        assert _latest_row(engine, built.task_id).task_agent_state is None

        # The button writes the same rows for another option.
        other = built.options["Guarantee package"]
        pressed = client.post(
            f"/api/v1/tasks/{built.task_id}/options/{other}/exclude",
            headers=owner2.headers,
            json={"reason": "volunteers cannot deliver it"},
        )
        assert pressed.status_code == 200, pressed.text
        button_row = _option_row(engine, other)
        assert (button_row.state, button_row.exclusion) == (verb_row.state, verb_row.exclusion)
        history = _decisions(client, built, owner2.headers)
        assert [h["kind"] for h in history] == ["option.excluded", "option.excluded"]
        assert {h["decided_by"] for h in history} == {"user"}
        with engine.connect() as conn:
            logged = [
                e["payload"]
                for e in events.read(conn, built.task_id)
                if e["event_type"] == "option.excluded"
            ]
        assert len(logged) == 2
        assert {tuple(sorted(p)) for p in logged} == {tuple(sorted(logged[0]))}
        assert {p["actor"] for p in logged} == {owner2.user_id}
        assert {p["reason"] for p in logged} == {"volunteers cannot deliver it"}
        assert {p["option_id"] for p in logged} == {str(mentoring), str(other)}

        # Reloaded, the applied turn is still an action.
        listed = client.get(
            f"/api/v1/tasks/{built.task_id}/task-agent-turns", headers=owner2.headers
        ).json()["data"]
        assert listed[-1]["kind"] == "action"
        assert listed[-1]["action"]["verb"] == "exclude"
        assert listed[-2]["part"]["id"] == "longlist_action"


def test_the_button_confirms_include_again_without_a_second_sort(
    engine: Engine, tmp_path: Path
) -> None:
    holder = _Holder()
    with _clients(tmp_path, engine, _overrides(holder)) as (client, (owner2, colleague, _)):
        built = _org_build(engine, owner2, colleague, linked=False)
        guarantee = built.options["Youth guarantee"]
        agent = holder.agent = _agent(_sort("include_again", option_id=str(guarantee)))
        excluded = client.post(
            f"/api/v1/tasks/{built.task_id}/options/{guarantee}/exclude",
            headers=owner2.headers,
            json={"reason": "We ran one already."},
        )
        assert excluded.status_code == 200, excluded.text
        proposed = _turn(client, owner2.headers, built.task_id, "Bring the youth guarantee back")
        assert proposed.json()["reply"] == "Include *Youth guarantee* again? Confirm to apply."
        assert _option_row(engine, guarantee).state == "excluded"

        confirmed = _turn(client, owner2.headers, built.task_id, _CONFIRM)
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["kind"] == "action"
        assert confirmed.json()["action"]["verb"] == "include_again"
        assert agent.longlist_sort_calls == 1  # the button is never sorted
        assert _option_row(engine, guarantee).state == "included"
        history = _decisions(client, built, owner2.headers)
        assert [h["kind"] for h in history] == ["option.included", "option.excluded"]

        # Pressed again: nothing is waiting any more.
        again = _turn(client, owner2.headers, built.task_id, _CONFIRM)
        assert again.json()["reply"] == longlist_turns.NOTHING_PENDING_REPLY
        assert len(_decisions(client, built, owner2.headers)) == 2


def test_a_question_never_applies_and_keeps_the_pending_action(
    engine: Engine, tmp_path: Path
) -> None:
    """A question-shaped turn is answered, even one the sort marks as assent."""
    holder = _Holder()
    with _clients(tmp_path, engine, _overrides(holder)) as (client, (owner2, colleague, _)):
        built = _org_build(engine, owner2, colleague, linked=False)
        mentoring = built.options["Mentoring"]
        holder.agent = _agent(
            _sort("exclude", option_id=str(mentoring)),
            _sort("question", assents_to_pending=True),
            _assent(),
        )
        proposed = _turn(client, owner2.headers, built.task_id, "Drop mentoring")
        assert proposed.json()["reply"] == (
            "Exclude *Mentoring*? Reason: *none given*. Confirm to apply."
        )
        asked = _turn(client, owner2.headers, built.task_id, "Should we? Is there UK evidence?")
        assert asked.status_code == 200, asked.text
        assert asked.json()["kind"] == "answer"
        assert _option_row(engine, mentoring).state == "included"
        assert _latest_row(engine, built.task_id).task_agent_state["pending"]["option_id"] == str(
            mentoring
        )
        applied = _turn(client, owner2.headers, built.task_id, "Yes")
        assert applied.json()["kind"] == "action"
        row = _option_row(engine, mentoring)
        # Confirmed with "none given" showing: recorded empty, never invented.
        assert row.state == "excluded" and row.exclusion["reason"] == ""
        assert len(_decisions(client, built, owner2.headers)) == 1


def test_a_different_verb_replaces_the_pending_action_and_other_keeps_it(
    engine: Engine, tmp_path: Path
) -> None:
    holder = _Holder()
    with _clients(tmp_path, engine, _overrides(holder)) as (client, (owner2, colleague, _)):
        built = _org_build(engine, owner2, colleague, linked=False)
        mentoring = built.options["Mentoring"]
        guarantee = built.options["Youth guarantee"]
        holder.agent = _agent(
            _sort("exclude", option_id=str(mentoring)),
            _sort("exclude", option_id=str(guarantee), reason="too costly"),
            _sort("exclude", option_id=str(uuid.uuid4())),
            _sort("other"),
        )
        _turn(client, owner2.headers, built.task_id, "Exclude mentoring")
        replaced = _turn(
            client, owner2.headers, built.task_id, "No, exclude the guarantee, too costly"
        )
        assert replaced.json()["reply"] == (
            "This replaces the earlier proposal to exclude *Mentoring*. "
            "Exclude *Youth guarantee*? Reason: *too costly*. Confirm to apply."
        )
        unmatched = _turn(client, owner2.headers, built.task_id, "Exclude the other one")
        assert unmatched.json()["reply"] == longlist_turns.WHICH_OPTION_REPLY
        # An unmatched verb leaves the pending action where it was.
        pending = _latest_row(engine, built.task_id).task_agent_state["pending"]
        assert pending["option_id"] == str(guarantee)
        kept = _turn(client, owner2.headers, built.task_id, "Hmm, not sure")
        assert kept.json()["reply"] == (
            f"{longlist_turns.OTHER_REPLY}\n\nStill waiting: Exclude *Youth guarantee*? "
            "Reason: *too costly*. Confirm to apply."
        )
        assert _latest_row(engine, built.task_id).task_agent_state["pending"]["option_id"] == str(
            guarantee
        )
        assert _option_row(engine, mentoring).state == "included"
        assert _option_row(engine, guarantee).state == "included"
        assert _decisions(client, built, owner2.headers) == []
        applied = _turn(client, owner2.headers, built.task_id, _CONFIRM)
        assert applied.json()["kind"] == "action"
        assert _option_row(engine, guarantee).state == "excluded"
        assert _option_row(engine, mentoring).state == "included"
        nothing = _turn(client, owner2.headers, built.task_id, _CONFIRM)
        assert nothing.json()["reply"] == longlist_turns.NOTHING_PENDING_REPLY
        assert len(_decisions(client, built, owner2.headers)) == 1


def test_add_proposes_a_design_then_mints_it_and_opens_a_parentless_walk(
    engine: Engine, tmp_path: Path
) -> None:
    """The design is proposed back; the child walk never closes the thread (P3)."""
    design = OptionDesignWire.model_validate(
        {
            "name": "Wage subsidy",
            "description": "Employers are paid part of a young recruit's wage.",
            "design_features": ["a wage subsidy for six months", "for 16 to 24 year olds"],
            "outcomes_served": ["the NEET rate"],
            "assumed": ["a wage subsidy for six months"],
        }
    )
    agent = _agent(
        _sort("add", design_words="pay employers to hire young people"),
        _assent(),
        design=design,
    )
    with _clients(tmp_path, engine, _overrides(agent)) as (client, (owner2, colleague, _)):
        built = _org_build(engine, owner2, colleague, linked=False)
        proposed = _turn(
            client,
            owner2.headers,
            built.task_id,
            "Add an option: pay employers to hire young people",
        )
        assert proposed.status_code == 200, proposed.text
        assert proposed.json()["reply"] == (
            "Add *Wage subsidy* — Employers are paid part of a young recruit's wage? "
            "Design: a wage subsidy for six months; for 16 to 24 year olds. "
            "Confirm to add it and search for it."
        )
        assert agent.option_design_words == ["pay employers to hire young people"]
        with engine.connect() as conn:
            names = set(
                conn.execute(select(option.c.name).where(option.c.task_id == built.task_id))
                .scalars()
            )
        assert "Wage subsidy" not in names  # not minted until confirmed
        conversation_id = uuid.UUID(proposed.json()["conversation_id"])

        applied = _turn(client, owner2.headers, built.task_id, "Go ahead")
        assert applied.status_code == 200, applied.text
        action = applied.json()["action"]
        assert applied.json()["kind"] == "action"
        assert action["verb"] == "add" and action["label"] == "Wage subsidy"
        opened = uuid.UUID(action["capability_run_id"])
        row = _option_row(engine, uuid.UUID(action["option_id"]))
        assert row.origin == "added_by_you"
        assert row.design["assumed"] == ["a wage subsidy for six months"]
        with engine.connect() as conn:
            walk = conn.execute(
                select(capability_run, evidence_scope.c.purpose)
                .select_from(
                    capability_run.join(
                        evidence_scope,
                        evidence_scope.c.evidence_scope_id == capability_run.c.evidence_scope_id,
                    )
                )
                .where(capability_run.c.capability_run_id == opened)
            ).one()
        assert walk.parent_capability_run_id is None and walk.purpose == "targeted"
        history = _decisions(client, built, owner2.headers)
        assert [h["kind"] for h in history] == ["option.added"]

        _await_walks_ended(engine, [built.task_id])
        with engine.connect() as conn:
            status = conn.execute(
                select(capability_run.c.status).where(capability_run.c.capability_run_id == opened)
            ).scalar_one()
            thread = conn.execute(
                select(conversation.c.status).where(conversation.c.id == conversation_id)
            ).scalar_one()
        assert status in {"succeeded", "degraded"}
        assert thread == "active"


def test_a_parentless_option_search_never_closes_the_conversation(engine: Engine) -> None:
    """P3 for *add*: a finished walk under a ``targeted`` record leaves the thread active."""
    task_id: uuid.UUID | None = None
    try:
        plan = _longlist_plan("Own")
        task_id, _scope_id, plan_id = _seed_longlist(engine, plan)
        option_id = _seed_option(engine, task_id, "Own", "added_by_you")
        with engine.begin() as conn:
            conversation_id = ensure_active_task_agent_conversation(
                conn, task_id=task_id, now=now()
            )
        walk = option_search.run_option_search(
            engine,
            task_id=task_id,
            plan_row={"plan_id": plan_id, "version": 1, "payload": plan.model_dump(mode="json")},
            design=_design("Own"),
            option_id=option_id,
            parent_capability_run_id=None,
            backends=_runner_backends(),
            user_id="user-1",
        )
        deadline = time.monotonic() + 60
        status = "running"
        while time.monotonic() < deadline:
            with engine.connect() as conn:
                status = conn.execute(
                    select(capability_run.c.status).where(
                        capability_run.c.capability_run_id == walk
                    )
                ).scalar_one_or_none() or "running"
            if status not in ("running", "paused"):
                break
            time.sleep(0.1)
        with engine.connect() as conn:
            thread = conn.execute(
                select(conversation.c.status).where(conversation.c.id == conversation_id)
            ).scalar_one()
        assert status in {"succeeded", "degraded"}
        assert thread == "active"
    finally:
        _cleanup(engine, task_id)


# --- the fences -------------------------------------------------------------------------


def test_a_turn_while_a_walk_runs_is_run_active(engine: Engine, tmp_path: Path) -> None:
    agent = _agent(_sort("question"))
    with _clients(tmp_path, engine, _overrides(agent)) as (client, (owner, colleague, _)):
        built = _org_build(engine, owner, colleague, linked=False)
        with engine.begin() as conn:
            conn.execute(
                update(capability_run)
                .where(capability_run.c.capability_run_id == built.walk_id)
                .values(status="running", ended_at=None)
            )
        response = _turn(client, owner.headers, built.task_id, "Which options work?")
        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "run_active"
        assert agent.longlist_sort_calls == 0


def test_an_evidence_search_task_never_reaches_the_longlist_sort(tmp_path: Path) -> None:
    agent = _agent(_sort("question"))
    overrides = _overrides(agent)
    del overrides[get_scoping_task_agent_backend]
    with api_client(tmp_path, overrides) as (client, owner, _other):
        task_id = create_task(client, owner)
        response = _turn(client, owner, task_id, "What works to reduce NEET rates?")
        assert response.status_code == 200, response.text
        assert response.json()["capability"] == "evidence_search"
        assert response.json()["kind"] is None
        assert agent.longlist_sort_calls == 0


def test_the_pending_state_is_never_read_as_a_plan_draft() -> None:
    state = longlist_turns.PendingAction(
        verb="add",
        option_id=None,
        label="Wage subsidy",
        design=OptionDesign(name="Wage subsidy", description="d", design_features=["f"]),
        words="pay employers",
    ).as_state()
    assert longlist_turns.is_longlist_state(state)
    assert not longlist_turns.is_longlist_state({"question": "x", "ready": False})
    assert not longlist_turns.is_longlist_state(None)
    assert longlist_turns.button_confirms(_CONFIRM)
    assert not longlist_turns.button_confirms("[confirm part=question option=confirm]")
    assert not longlist_turns.button_confirms(f"{_CONFIRM}\nand more")



def test_the_stub_sort_defaults_to_other() -> None:
    agent = StubAgentBackend()
    sort = agent.sort_longlist_turn("anything", [], pending=None)
    assert sort.kind == "other" and sort.assents_to_pending is False
    assert agent.longlist_sort_calls == 1
