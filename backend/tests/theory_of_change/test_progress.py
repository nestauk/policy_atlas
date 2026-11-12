"""The theory of change's server progress (task 054's 058 alignment, phase 3).

The ToC steps report under their own stage keys with the server's words and
counts (S1, S2), the upload's read under ``toc_read`` (A21), the loops publish
live counts (A3, A4), the run read names the walk kind and the draft a check
follows (A5), and the automatic chain posts no "draft landed" line (A8).
"""

from __future__ import annotations

import threading
import uuid
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy import select, update
from sqlalchemy.engine import Engine

from policy_atlas.api.routers.common import _active_stage, _latest_run_out
from policy_atlas.api.routers.sse import walk_stages
from policy_atlas.api.stage_vocabulary import STAGE_COUNTS, STAGE_PRESENTATION
from policy_atlas.api.toc_start import (
    DRAFT_LANDED_MESSAGE,
    STRESS_TEST_MESSAGE,
    run_toc_sequence,
)
from policy_atlas.core import liveness
from policy_atlas.core.schema import capability_run, event_log, evidence_scope, task
from policy_atlas.runtime.agent import persist_approved_plan
from policy_atlas.runtime.capability_registry import latest_approved_plan_row
from policy_atlas.runtime.runner import NullIO, RunnerBackends, run_plan
from policy_atlas.runtime.toc_plan import TOC_REVIEW_FIRST_KEY
from policy_atlas.theory_of_change.backend import StubTocBackend
from policy_atlas.theory_of_change.check.shared import _map_traced
from tests.api.resource_support import api_client, create_task
from tests.theory_of_change.test_walks import (
    Records,
    _replies,
    _start,
    _walks,
    seed_toc,
    toc_plan,
)

# --- helpers --------------------------------------------------------------------


def _draft(engine: Engine, task_id: uuid.UUID, plan_row: dict[str, Any]) -> Any:
    """Run the plan's draft walk on stub backends and return its outcome."""
    return run_plan(
        engine,
        task_id=task_id,
        evidence_scope_id=plan_row["evidence_scope_id"],
        plan=toc_plan(),
        plan_id=plan_row["plan_id"],
        plan_version=plan_row["version"],
        plan_row_id=plan_row["plan_id"],
        backends=RunnerBackends(search_backends=[], toc=StubTocBackend()),
        io=NullIO(),
        session_id=task_id,
    )


def _review_first(engine: Engine, plan_row: dict[str, Any]) -> None:
    """Mark the plan's draft walk as an uploaded theory's read."""
    with engine.begin() as conn:
        context = conn.execute(
            select(evidence_scope.c.context).where(
                evidence_scope.c.evidence_scope_id == plan_row["evidence_scope_id"]
            )
        ).scalar_one()
        conn.execute(
            update(evidence_scope)
            .where(evidence_scope.c.evidence_scope_id == plan_row["evidence_scope_id"])
            .values(context={**context, TOC_REVIEW_FIRST_KEY: True})
        )


def _started_payloads(engine: Engine, task_id: uuid.UUID, component: str) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        return [
            dict(payload)
            for payload in conn.execute(
                select(event_log.c.payload)
                .where(event_log.c.task_id == task_id)
                .where(event_log.c.event_type == "run.started")
                .where(event_log.c.payload["component"].astext == component)
            ).scalars()
        ]


class _Ticks:
    """Records every tick published to the shared hub, sending none."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.ticks: list[dict[str, Any]] = []

    def __call__(self, task_id: uuid.UUID, **payload: Any) -> None:
        with self.lock:
            self.ticks.append(payload)

    def of(self, stage: str) -> list[dict[str, Any]]:
        with self.lock:
            return [tick for tick in self.ticks if tick["stage"] == stage]


# --- A21: the upload's read -------------------------------------------------------


def test_the_draft_component_reports_toc_draft_in_a_draft_and_toc_read_in_an_upload(
    engine: Engine, cleanup: list[uuid.UUID], monkeypatch: pytest.MonkeyPatch
) -> None:
    ended: list[str] = []
    real_end = liveness.tick_hub.end_stage

    def end_stage(task_id: uuid.UUID, stage: str, run_id: uuid.UUID | None = None) -> None:
        ended.append(stage)
        real_end(task_id, stage, run_id)

    monkeypatch.setattr(liveness.tick_hub, "end_stage", end_stage)

    drafted, drafted_row = seed_toc(engine)
    cleanup.append(drafted)
    draft = _draft(engine, drafted, drafted_row)
    uploaded, uploaded_row = seed_toc(engine)
    cleanup.append(uploaded)
    _review_first(engine, uploaded_row)
    read = _draft(engine, uploaded, uploaded_row)
    assert draft.status == read.status == "succeeded"

    # The runner stamps the upload's read only.
    [plain] = _started_payloads(engine, drafted, "toc_draft")
    [stamped] = _started_payloads(engine, uploaded, "toc_draft")
    assert "stage" not in plain
    assert stamped["stage"] == "toc_read"
    with engine.connect() as conn:
        started = conn.execute(
            select(event_log.c.payload)
            .where(event_log.c.task_id == uploaded)
            .where(event_log.c.event_type.in_(["component.started", "component.completed"]))
        ).scalars().all()
    assert started and all(payload["stage"] == "toc_read" for payload in started)

    with engine.connect() as conn:
        [drafted_step] = walk_stages(conn, task_id=drafted, walk_ids=[draft.capability_run_id])[
            draft.capability_run_id
        ]
        [read_step] = walk_stages(conn, task_id=uploaded, walk_ids=[read.capability_run_id])[
            read.capability_run_id
        ]
    assert (drafted_step.stage, drafted_step.label) == ("toc_draft", "Drafting the theory")
    assert (read_step.stage, read_step.label) == ("toc_read", "Reading your diagram")
    for step in (drafted_step, read_step):
        assert step.status == "completed" and step.started_at is not None
        assert [c.noun for c in step.counts] == ["boxes", "connections", "pathways"]
        # The stamp names the frame's stage; it is no count.
        assert "stage" not in step.summary
    # The harness bound each run's live progress to its reported stage.
    assert ended == ["toc_draft", "toc_read"]


# --- A2 and S2: a check walk's stage frames ----------------------------------------


def test_a_check_walk_reports_each_step_with_the_server_words_and_counts(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    task_id, plan_row = seed_toc(engine)
    cleanup.append(task_id)
    _start(
        engine,
        task_id,
        plan_row,
        RunnerBackends(search_backends=[Records()], toc=StubTocBackend()),
    )
    draft, check = _walks(engine, task_id)
    with engine.connect() as conn:
        stages = walk_stages(
            conn, task_id=task_id, walk_ids=[draft.capability_run_id, check.capability_run_id]
        )
        active = _active_stage(
            conn, task_id, cast(Any, {"capability_run_id": check.capability_run_id})
        )
        walk = (
            conn.execute(
                select(capability_run).where(
                    capability_run.c.capability_run_id == check.capability_run_id
                )
            )
            .mappings()
            .one()
        )

    assert [step.stage for step in stages[draft.capability_run_id]] == ["toc_draft"]
    steps = stages[check.capability_run_id]
    keys = [step.stage for step in steps]
    for key in (
        "toc_item_searches",
        "toc_select",
        "toc_discover",
        "toc_merge",
        "toc_search_new",
        "toc_judge",
        "toc_search_again",
        "toc_figures",
        "classify",
        "appraise",
        "toc_choose",
        "toc_summarise",
        "toc_report",
    ):
        assert key in keys, key
    assert keys.index("toc_item_searches") < keys.index("toc_select") < keys.index("toc_report")
    for step in steps:
        # A started frame and a completed frame per step, in the server's words.
        assert step.status == "completed", step
        assert step.started_at is not None and step.ended_at is not None, step
        assert step.label == STAGE_PRESENTATION[step.stage][0]
        # The counts the table names, from the step's integer summary keys (a
        # second search with no thin connection has nothing to judge).
        wanted = [noun for key, noun in STAGE_COUNTS[step.stage] if key in step.summary]
        assert [count.noun for count in step.counts] == wanted, step
        if step.stage != "toc_search_again":
            assert len(wanted) == len(STAGE_COUNTS[step.stage]), step
    by_key = {step.stage: step for step in steps}
    judge = by_key["toc_judge"]
    assert isinstance(judge.summary["test_them"], int)
    assert 0 < judge.summary["test_them"] <= cast(int, judge.summary["judgements"])
    choose = by_key["toc_choose"]
    assert isinstance(choose.summary["kept"], int) and isinstance(choose.summary["set_aside"], int)
    assert by_key["toc_item_searches"].counts[0].noun == "searches"

    # The run status bar's stage: the walk's latest step, with its label.
    assert active == "toc_report"
    latest = _latest_run_out(walk, active)
    assert latest.stage_label == "Writing the report"


# --- A3 and A4: the live counts --------------------------------------------------


def test_the_check_loops_publish_their_live_counts_under_toc_stages(
    engine: Engine, cleanup: list[uuid.UUID], monkeypatch: pytest.MonkeyPatch
) -> None:
    ticks = _Ticks()
    monkeypatch.setattr(liveness.tick_hub, "publish_tick", ticks)
    task_id, plan_row = seed_toc(engine)
    cleanup.append(task_id)
    _start(
        engine,
        task_id,
        plan_row,
        RunnerBackends(search_backends=[Records()], toc=StubTocBackend()),
    )

    # Never Options scoping's row or words (A3).
    assert ticks.of("option_searches") == []
    assert not any("sources" in str(tick["activity"]) for tick in ticks.ticks)

    searches = ticks.of("toc_item_searches")
    assert searches
    last = searches[-1]
    assert last["unit"] == "searches" and last["done"] == last["total"]
    assert last["activity"].startswith(f"{last['done']} of {last['total']} searches done · ")
    assert last["activity"].endswith(" found")

    screening = ticks.of("toc_select")
    assert screening
    assert all(tick["unit"] == "abstracts" for tick in screening)
    final = screening[-1]
    assert final["done"] == final["total"] > 0
    assert final["activity"].startswith(f"{final['done']} of {final['total']} read · ")
    assert final["activity"].endswith(" relevant")

    judging = ticks.of("toc_judge")
    assert judging
    assert judging[0]["done"] == 0
    assert [tick["done"] for tick in judging] == sorted(tick["done"] for tick in judging)
    end = judging[-1]
    assert end["done"] == end["total"] > 0
    assert end["activity"] == f"{end['done']} of {end['total']} documents"
    assert all("so far" not in str(tick["activity"]) for tick in ticks.ticks)


def test_map_traced_reports_each_item_as_it_finishes_on_the_calling_thread() -> None:
    caller = threading.get_ident()
    seen: list[tuple[int, int, int]] = []

    def square(n: int) -> int:
        if n == 3:
            raise ValueError("three")
        return n * n

    def done(item: int, result: int) -> None:
        seen.append((item, result, threading.get_ident()))

    with pytest.raises(ValueError, match="three"):
        _map_traced(square, [1, 2, 3, 4], 2, on_done=done)
    # The item that raised is not reported; the others each once, on the caller.
    assert sorted((item, result) for item, result, _ in seen) == [(1, 1), (2, 4), (4, 16)]
    assert {thread for _, _, thread in seen} == {caller}
    assert _map_traced(square, [4, 1, 2], 3) == [16, 1, 4]


# --- A8: no "draft landed" line in the automatic chain -----------------------------


def test_the_automatic_chain_posts_no_draft_landed_line(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    task_id, plan_row = seed_toc(engine)
    cleanup.append(task_id)
    _start(
        engine,
        task_id,
        plan_row,
        RunnerBackends(search_backends=[Records()], toc=StubTocBackend()),
    )
    replies = _replies(engine, task_id)
    assert DRAFT_LANDED_MESSAGE not in replies
    # The check's end message stays.
    assert len(replies) == 1 and replies[0].endswith(STRESS_TEST_MESSAGE)


def test_an_uploaded_theory_keeps_its_review_line(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    task_id, plan_row = seed_toc(engine)
    cleanup.append(task_id)
    _review_first(engine, plan_row)
    backends = RunnerBackends(search_backends=[], toc=StubTocBackend())
    read = _draft(engine, task_id, plan_row)
    assert run_toc_sequence(engine, task_id=task_id, first_outcome=read, backends=backends) is None
    # The reader acts here: the review line is posted and no check starts.
    assert len(_replies(engine, task_id)) == 1
    assert [w.context["toc_walk"] for w in _walks(engine, task_id)] == ["draft"]


# --- A5: the walk kind on the run read ---------------------------------------------


def test_the_run_read_names_the_toc_walk_kind_and_the_draft_a_check_follows(
    engine: Engine, tmp_path: Path, cleanup: list[uuid.UUID]
) -> None:
    with api_client(tmp_path) as (client, owner, _other):
        # Made through the route for its owner, then turned into a theory of
        # change (the test server does not enable the capability).
        task_id = uuid.UUID(create_task(client, owner))
        cleanup.append(task_id)
        with engine.begin() as conn:
            conn.execute(
                update(task).where(task.c.task_id == task_id).values(capability="theory_of_change")
            )
            persist_approved_plan(conn, task_id=task_id, plan=toc_plan())
            row = latest_approved_plan_row(conn, task_id)
            assert row is not None
        _start(
            engine,
            task_id,
            dict(row),
            RunnerBackends(search_backends=[Records()], toc=StubTocBackend()),
        )
        draft, check = _walks(engine, task_id)
        response = client.get(f"/api/v1/tasks/{task_id}/runs?parentless=true", headers=owner)
        assert response.status_code == 200, response.text
        runs = {run["capability_run_id"]: run for run in response.json()["data"]}
        drafted = runs[str(draft.capability_run_id)]
        checked = runs[str(check.capability_run_id)]
        assert (drafted["toc_walk"], drafted["follows_capability_run_id"]) == ("draft", None)
        assert (checked["toc_walk"], checked["follows_capability_run_id"]) == (
            "check",
            str(draft.capability_run_id),
        )
        one = client.get(f"/api/v1/tasks/{task_id}/runs/{check.capability_run_id}", headers=owner)
        assert one.json()["follows_capability_run_id"] == str(draft.capability_run_id)
        # The child item searches are no ToC walk of their own.
        children = client.get(f"/api/v1/tasks/{task_id}/runs?page_size=100", headers=owner)
        for run in children.json()["data"]:
            if run["parent_capability_run_id"] is not None:
                assert run["toc_walk"] is None and run["follows_capability_run_id"] is None


def test_the_walk_kind_reads_the_upload_and_the_report_update() -> None:
    from policy_atlas.api.routers.common import run_out

    base = {
        "capability_run_id": uuid.uuid4(),
        "task_id": uuid.uuid4(),
        "plan_id": uuid.uuid4(),
        "plan_version": 1,
        "status": "succeeded",
        "started_at": "2026-11-09T10:00:00Z",
        "ended_at": None,
    }

    def kind(purpose: str | None, context: dict[str, Any] | None) -> Any:
        out = run_out({**base, "purpose": purpose, "scope_context": context})
        return out.toc_walk, out.follows_capability_run_id

    assert kind("toc", {"toc_walk": "draft", TOC_REVIEW_FIRST_KEY: True}) == ("read", None)
    assert kind("toc", {"toc_walk": "check", "mode": "report"}) == ("report_update", None)
    assert kind("toc", {"toc_walk": "check", "mode": "find_more"}) == ("check", None)
    # Any other walk carries neither field, whatever its context holds.
    assert kind(None, None) == (None, None)
    assert kind("targeted", {"toc_walk": "draft"}) == (None, None)
    assert kind("longlist", {}) == (None, None)
