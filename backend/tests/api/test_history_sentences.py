"""History lines say what happened, and who did it (task 058, round 10)."""

from __future__ import annotations

import uuid

from sqlalchemy import delete
from sqlalchemy.engine import Engine

from policy_atlas.api.read_models import history, repository
from policy_atlas.core import events
from policy_atlas.core.schema import app_user, capability_run, evidence_scope, runs, task
from tests.helpers import delete_task_data, now


def test_step_lines_name_the_step_and_its_counts() -> None:
    def done(payload: dict[str, object]) -> str:
        return history.step_sentence("component.completed", payload)

    assert (
        done({"component": "acquire", "acquired": 312})
        == "Searching finished: 312 sources found."
    )
    assert done({"component": "acquire", "acquired": 1}) == "Searching finished: 1 source found."
    assert (
        done({"component": "screen", "screened": 435, "relevant": 118, "not_relevant": 300})
        == "Screening finished: 118 of 435 relevant."
    )
    assert (
        done({"component": "screen", "relevant": 2, "not_relevant": 3})
        == "Screening finished: 2 of 5 relevant."
    )
    assert (
        done({"component": "classify", "classified": 118})
        == "Classifying finished: 118 sources."
    )
    assert (
        done(
            {"component": "ingest_full_text", "ingested": 38, "fetch_failed": 4, "parse_failed": 1}
        )
        == "Collecting the full texts finished: 38 collected, 5 failed."
    )
    assert (
        done({"component": "ingest_full_text", "ingested": 38, "fetch_failed": 0})
        == "Collecting the full texts finished: 38 collected."
    )
    assert done({"component": "characterise", "theme_count": 7}) == "Mapping finished: 7 themes."
    assert done({"component": "synthesise", "section_count": 1}) == "Writing finished: 1 section."
    assert done({"component": "appraise", "appraised": 30}) == "Classifying finished."
    assert (
        done({"component": "screen_full", "screened": 38, "relevant": 30})
        == "Screening the full texts finished: 30 of 38 relevant."
    )
    assert done({"component": "not_a_stage"}) == "A step finished."
    assert (
        history.step_sentence("component.skipped", {"component": "select"})
        == "Shortlisting skipped."
    )
    assert (
        history.step_sentence("component.failed", {"component": "synthesise", "error": "x"})
        == "Writing didn't complete."
    )


def test_search_line_quotes_five_queries_then_counts_the_rest() -> None:
    assert history.search_sentence(["school meals"]) == "Searched with 1 query: “school meals”."
    assert (
        history.search_sentence(["a", "b", "c"])
        == "Searched with 3 queries: “a”, “b” and “c”."
    )
    queries = [f"q{n}" for n in range(55)]
    assert history.search_sentence(queries) == (
        "Searched with 55 queries: “q0”, “q1”, “q2”, "
        "“q3”, “q4” and 50 more."
    )
    assert history.search_sentence([]) == "Searched the databases."


def test_run_lines_name_policy_atlas() -> None:
    assert history.run_sentence("run.opened", {}) == "Policy Atlas started the run."
    assert history.run_sentence("run.parked", {}) == "Policy Atlas paused for a check-in."
    assert (
        history.run_sentence("run.finished", {"status": "succeeded"})
        == "Policy Atlas finished the run."
    )
    assert history.run_sentence("run.finished", {"status": "failed"}) == "The run didn't complete."
    assert history.run_sentence("run.finished", {"status": "aborted"}) == "The run was stopped."
    assert history.run_sentence("run.interrupted", {}) == "The run was interrupted."


def test_check_in_lines_name_the_choice() -> None:
    you = history.Actor(subject="You", display="Ada Lovelace", is_viewer=True)
    assert (
        history.check_in_sentence({"decided_by": "user"}, "Looks right, assess these", you)
        == "You chose “Looks right, assess these” at the check-in."
    )
    assert (
        history.check_in_sentence({"decided_by": "user", "response": "abort"}, None, you)
        == "You stopped the run at the check-in."
    )
    assert (
        history.check_in_sentence(
            {"decided_by": "user", "response": "adjust", "user_text": "Add Wales"}, None, you
        )
        == "You asked for a change at the check-in: “Add Wales”."
    )
    assert (
        history.check_in_sentence({"decided_by": "standing_default"}, "Go on", history.SYSTEM)
        == "Policy Atlas applied the standing choice at the check-in."
    )


def test_decisions_page_groups_searches_and_names_the_chooser(engine: Engine) -> None:
    """One row for a run's searches; a check-in names its option and its chooser."""
    owner_id, viewer_id = f"owner-{uuid.uuid4()}", f"colleague-{uuid.uuid4()}"
    task_id, scope_id, walk_id, run_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    plan_id = uuid.uuid4()
    try:
        with engine.begin() as conn:
            conn.execute(
                app_user.insert().values(
                    user_id=owner_id, display_name="Ada Lovelace", created_at=now()
                )
            )
            conn.execute(
                task.insert().values(
                    task_id=task_id,
                    name="History lines",
                    status="active",
                    created_at=now(),
                    updated_at=now(),
                    owner_user_id=owner_id,
                )
            )
            conn.execute(
                evidence_scope.insert().values(
                    evidence_scope_id=scope_id,
                    task_id=task_id,
                    intent="intent",
                    context={},
                    created_at=now(),
                )
            )
            conn.execute(
                capability_run.insert().values(
                    capability_run_id=walk_id,
                    task_id=task_id,
                    evidence_scope_id=scope_id,
                    capability="evidence_search",
                    plan_id=plan_id,
                    plan_version=1,
                    status="running",
                    started_at=now(),
                )
            )
            conn.execute(
                runs.insert().values(
                    run_id=run_id,
                    task_id=task_id,
                    status="running",
                    started_at=now(),
                    capability_run_id=walk_id,
                )
            )
            # Seven sends, six distinct queries (one went to both databases).
            for query in ("school meals", "school meals", "b", "c", "d", "e", "f"):
                events.append(
                    conn,
                    task_id=task_id,
                    run_id=run_id,
                    event_type="search.executed",
                    payload={"query": query, "backend": "openalex", "result_count": 1},
                )
            events.append(
                conn,
                task_id=task_id,
                run_id=run_id,
                event_type="component.completed",
                payload={"component": "screen", "screened": 435, "relevant": 118},
            )
            base = {
                "capability_run_id": str(walk_id),
                "plan_id": str(plan_id),
                "plan_version": 1,
                "boundary": "after_component",
                "component": "screen",
            }
            events.append(
                conn,
                task_id=task_id,
                run_id=run_id,
                event_type="steering.pause",
                payload={
                    **base,
                    "options": [
                        {"id": "continue", "label": "Looks right, assess these"},
                        {"id": "abort", "label": "Stop"},
                    ],
                },
            )
            events.append(
                conn,
                task_id=task_id,
                run_id=run_id,
                event_type="steering.decision",
                payload={
                    **base,
                    "decided_by": "user",
                    "authored_by": "user",
                    "response": "continue",
                    "confirmed": True,
                    "option_id": "continue",
                },
            )
        with engine.connect() as conn:
            as_owner = repository.decisions_page(conn, task_id, 1, 50, viewer_user_id=owner_id)
            as_colleague = repository.decisions_page(
                conn, task_id, 1, 50, viewer_user_id=viewer_id
            )
        summaries = [item.summary for item in as_owner.data]
        assert summaries == [
            "You chose “Looks right, assess these” at the check-in.",
            "Screening finished: 118 of 435 relevant.",
            "Searched with 6 queries: “school meals”, “b”, “c”, "
            "“d”, “e” and 1 more.",
        ]
        search = as_owner.data[-1]
        assert search.kind == "search.executed"
        assert search.detail == {"queries": ["school meals", "b", "c", "d", "e", "f"]}
        assert search.capability_run_id == walk_id
        assert as_owner.pagination.total_items == 3
        chosen = as_colleague.data[0]
        assert chosen.summary == "Ada Lovelace chose “Looks right, assess these” at the check-in."
        assert (chosen.actor_display, chosen.actor_is_viewer) == ("Ada Lovelace", False)
        assert (as_owner.data[0].actor_display, as_owner.data[0].actor_is_viewer) == (
            "Ada Lovelace",
            True,
        )
        assert as_owner.data[1].actor_display is None
    finally:
        with engine.begin() as conn:
            delete_task_data(conn, task_id)
            conn.execute(delete(app_user).where(app_user.c.user_id == owner_id))
