"""The draft and check walks end to end on stub backends (task 054, steps 1.3, 1.4)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.api.routers.runs import _dispatch_run
from policy_atlas.api.toc_start import DRAFT_LANDED_MESSAGE, STRESS_TEST_MESSAGE
from policy_atlas.core.schema import (
    capability_run,
    conversation,
    event_log,
    evidence_scope,
    task,
    task_agent_transcript,
    toc_item_evidence,
    toc_link,
)
from policy_atlas.evidence_search.sourcing.acquire import BackendCaps
from policy_atlas.runtime.agent import persist_approved_plan
from policy_atlas.runtime.capability_registry import latest_approved_plan_row
from policy_atlas.runtime.runner import NullIO, RunnerBackends, run_plan
from policy_atlas.runtime.toc_plan import TocPlan
from policy_atlas.theory_of_change import store
from policy_atlas.theory_of_change.backend import StubTocBackend, stub_draft
from policy_atlas.theory_of_change.draft_prompt import DraftResponse
from policy_atlas.theory_of_change.graph import check_graph
from tests.helpers import now, oa_record


def toc_plan(**overrides: Any) -> TocPlan:
    values: dict[str, Any] = {
        "title": "Healthy weight",
        "question": "How would a junk-food advertising ban reduce childhood obesity?",
        "entry_point": "intervention_first",
        "intended_change": "Fewer children living with obesity",
        "target_population": "children aged 4 to 11",
        "intervention": "a junk-food advertising ban",
        "where": "London",
    }
    values.update(overrides)
    return TocPlan.model_validate(values)


def seed_toc(engine: Engine, plan: TocPlan | None = None) -> tuple[uuid.UUID, dict[str, Any]]:
    """A theory-of-change task with an approved plan; returns ``(task_id, plan_row)``."""
    task_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            task.insert().values(
                task_id=task_id,
                name="Test theory",
                status="active",
                capability="theory_of_change",
                created_at=now(),
                updated_at=now(),
            )
        )
        persist_approved_plan(conn, task_id=task_id, plan=plan or toc_plan())
        row = latest_approved_plan_row(conn, task_id)
        assert row is not None
    return task_id, dict(row)


ABSTRACT = "A ban on junk food adverts cut children's exposure and purchases in the city."


class Records:
    """An OpenAlex-shaped search backend returning fresh records on every call."""

    name = "openalex"
    trust_class = "academic_aggregator"
    mode = "scripted"
    caps = BackendCaps(has_snowball=False, has_title_lookup=False)

    def __init__(self, per_call: int = 2) -> None:
        self.per_call = per_call

    def search(
        self,
        query: str,
        *,
        wire_params: dict[str, str] | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        stem = uuid.uuid4().hex[:12]
        return [
            oa_record(
                f"{stem}n{i}",
                title=f"Advertising ban study {stem} {i}",
                abstract=ABSTRACT,
            )
            for i in range(self.per_call)
        ]

    def fetch_citations(self, record_id: str, *, max_results: int | None = None) -> list[Any]:
        raise NotImplementedError

    def fetch_references(
        self, record_ids: list[str], *, max_results: int | None = None
    ) -> list[Any]:
        raise NotImplementedError

    def lookup_title(self, title: str) -> list[Any]:
        raise NotImplementedError

    def lookup_dois(self, dois: list[str], *, max_results: int | None = None) -> list[Any]:
        raise NotImplementedError


def await_children(engine: Engine, task_id: uuid.UUID) -> None:
    import time

    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        with engine.connect() as conn:
            active = conn.execute(
                select(capability_run.c.capability_run_id)
                .where(capability_run.c.task_id == task_id)
                .where(capability_run.c.status.in_(("running", "paused")))
            ).first()
        if active is None:
            return
        time.sleep(0.05)


def _replies(engine: Engine, task_id: uuid.UUID) -> list[str]:
    with engine.connect() as conn:
        return list(
            conn.execute(
                select(task_agent_transcript.c.reply)
                .where(task_agent_transcript.c.task_id == task_id)
                .order_by(task_agent_transcript.c.turn_index)
            ).scalars()
        )


def _component_events(engine: Engine, task_id: uuid.UUID) -> list[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            select(event_log.c.payload)
            .where(event_log.c.task_id == task_id)
            .where(event_log.c.event_type == "component.completed")
            .order_by(event_log.c.sequence)
        ).scalars()
        return [str(payload.get("component")) for payload in rows]


# --- draft ----------------------------------------------------------------------


def test_the_draft_walk_writes_a_graph_that_passes_the_structure_checks(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    task_id, plan_row = seed_toc(engine)
    cleanup.append(task_id)
    outcome = run_plan(
        engine,
        task_id=task_id,
        evidence_scope_id=plan_row["evidence_scope_id"],
        plan=toc_plan(),
        plan_id=plan_row["plan_id"],
        plan_version=plan_row["version"],
        plan_row_id=plan_row["plan_id"],
        backends=RunnerBackends(search_backends=[]),
        io=NullIO(),
        session_id=task_id,
    )
    assert outcome.status == "succeeded", outcome
    assert [step.component for step in outcome.steps] == ["toc_draft"]
    with engine.connect() as conn:
        graph, rows = store.load_graph(conn, task_id)
        assert check_graph(graph) == []
        assert len(graph.boxes) == 5 and len(graph.links) == 4 and len(graph.pathways) == 2
        assert sum(1 for row in rows.links.values() if row.critical) == 1
        assert {row.band for row in rows.band_items} == {"context", "supporting"}
        changed = (
            conn.execute(
                select(event_log.c.payload).where(
                    event_log.c.task_id == task_id, event_log.c.event_type == "toc.changed"
                )
            )
            .scalars()
            .one()
        )
        assert changed["step"] == "toc_draft" and len(changed["created"]) == 5 + 4 + 2 + 2


def test_a_draft_failing_its_checks_is_retried_once_then_fails_the_walk(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    broken = stub_draft({}).model_copy(update={"pathways": []})
    # Two attempts per component run, and the runner retries a failed run once.
    backend = StubTocBackend({"draft": [broken] * 4})
    task_id, plan_row = seed_toc(engine)
    cleanup.append(task_id)
    outcome = run_plan(
        engine,
        task_id=task_id,
        evidence_scope_id=plan_row["evidence_scope_id"],
        plan=toc_plan(),
        plan_id=plan_row["plan_id"],
        plan_version=plan_row["version"],
        plan_row_id=plan_row["plan_id"],
        backends=RunnerBackends(search_backends=[], toc=backend),
        io=NullIO(),
        session_id=task_id,
    )
    assert outcome.status == "failed"
    assert backend.calls["draft"] == 4
    with engine.connect() as conn:
        assert not store.has_graph(conn, task_id)
        failed = (
            conn.execute(
                select(event_log.c.payload).where(
                    event_log.c.task_id == task_id, event_log.c.event_type == "component.failed"
                )
            )
            .scalars()
            .first()
        )
    assert failed is not None and "no success pathway" in failed["error"]


def test_a_draft_fixed_on_the_retry_lands(engine: Engine, cleanup: list[uuid.UUID]) -> None:
    broken: DraftResponse = stub_draft({}).model_copy(update={"pathways": []})
    backend = StubTocBackend({"draft": [broken]})
    task_id, plan_row = seed_toc(engine)
    cleanup.append(task_id)
    outcome = run_plan(
        engine,
        task_id=task_id,
        evidence_scope_id=plan_row["evidence_scope_id"],
        plan=toc_plan(),
        plan_id=plan_row["plan_id"],
        plan_version=plan_row["version"],
        plan_row_id=plan_row["plan_id"],
        backends=RunnerBackends(search_backends=[], toc=backend),
        io=NullIO(),
        session_id=task_id,
    )
    assert outcome.status == "succeeded"
    assert backend.calls["draft"] == 2


# --- the sequence ---------------------------------------------------------------


def _start(
    engine: Engine, task_id: uuid.UUID, plan_row: dict[str, Any], backends: RunnerBackends
) -> None:
    _dispatch_run(
        engine,
        task_id=task_id,
        capability="theory_of_change",
        plan_row=plan_row,
        backends=backends,
        user_id="test-user",
    )


def _walks(engine: Engine, task_id: uuid.UUID) -> list[Any]:
    with engine.connect() as conn:
        return list(
            conn.execute(
                select(
                    capability_run.c.capability_run_id,
                    capability_run.c.status,
                    evidence_scope.c.context,
                    evidence_scope.c.intent,
                )
                .join(
                    evidence_scope,
                    evidence_scope.c.evidence_scope_id == capability_run.c.evidence_scope_id,
                )
                .where(capability_run.c.task_id == task_id)
                .where(capability_run.c.parent_capability_run_id.is_(None))
                .order_by(capability_run.c.started_at)
            )
        )


def test_start_drafts_then_checks_and_the_thread_stays_open(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    task_id, plan_row = seed_toc(engine)
    cleanup.append(task_id)
    backend = StubTocBackend()
    _start(engine, task_id, plan_row, RunnerBackends(search_backends=[Records()], toc=backend))
    walks = _walks(engine, task_id)
    assert [(w.context["toc_walk"], w.status) for w in walks] == [
        ("draft", "succeeded"),
        ("check", "succeeded"),
    ]
    assert "children aged 4 to 11" in walks[1].intent
    assert "London" not in walks[1].intent
    # The check screens against the steps it covers (arm B), minted from the graph.
    criterion = walks[1].context["screening_criterion"]
    with engine.connect() as conn:
        sentences = conn.execute(
            select(toc_link.c.sentence).where(toc_link.c.task_id == task_id)
        ).scalars()
        assert all(f"- {sentence}" in criterion for sentence in sentences)
    replies = _replies(engine, task_id)
    assert replies[0] == DRAFT_LANDED_MESSAGE
    assert replies[-1].endswith(STRESS_TEST_MESSAGE)
    order = [c for c in _component_events(engine, task_id) if c.startswith("toc_")]
    assert order == [
        "toc_draft",
        "toc_item_searches",
        "toc_discover",
        "toc_merge",
        "toc_judge",
        "toc_choose",
        "toc_summarise",
    ]
    with engine.connect() as conn:
        assert (
            conn.execute(
                select(conversation.c.status).where(
                    conversation.c.task_id == task_id, conversation.c.kind == "task_agent"
                )
            ).scalar_one()
            == "active"
        )
        judged = (
            conn.execute(
                select(toc_item_evidence.c.link_id).where(toc_item_evidence.c.task_id == task_id)
            )
            .scalars()
            .all()
        )
        assert judged
        links = conn.execute(select(toc_link).where(toc_link.c.task_id == task_id)).all()
        assert all(link.counted_hash is not None for link in links)
        assert all(link.elsewhere_sentence for link in links)

    # A second Start on a task with a graph checks it again in full: no redraft.
    _start(engine, task_id, plan_row, RunnerBackends(search_backends=[Records()], toc=backend))
    walks = _walks(engine, task_id)
    assert [w.context["toc_walk"] for w in walks] == ["draft", "check", "check"]
    assert backend.calls["draft"] == 1


def test_a_check_already_following_the_draft_is_not_minted_twice(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    from policy_atlas.api.toc_start import run_toc_sequence

    task_id, plan_row = seed_toc(engine)
    cleanup.append(task_id)
    backends = RunnerBackends(search_backends=[], toc=StubTocBackend())
    draft = run_plan(
        engine,
        task_id=task_id,
        evidence_scope_id=plan_row["evidence_scope_id"],
        plan=toc_plan(),
        plan_id=plan_row["plan_id"],
        plan_version=plan_row["version"],
        plan_row_id=plan_row["plan_id"],
        backends=backends,
        io=NullIO(),
        session_id=task_id,
    )
    assert run_toc_sequence(engine, task_id=task_id, first_outcome=draft, backends=backends)
    assert run_toc_sequence(engine, task_id=task_id, first_outcome=draft, backends=backends) is None
    assert [w.context["toc_walk"] for w in _walks(engine, task_id)] == ["draft", "check"]
