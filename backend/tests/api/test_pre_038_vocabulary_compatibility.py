"""Pre-038 stored values still read correctly (task 038, plan D5 / contract A2–A5).

The 038 migration renames the catalog but rewrites only one stored value
(``capability_run.capability``). ``event_log`` is append-only and plan payloads
are left alone, so rows written before the slice still carry the old words:
``decided_by``/``authored_by`` = ``orchestrator``, the ``project.*`` lifecycle
event types, and the old P2 steer-point id. Three compatibility helpers map them
on read; each test here feeds the OLD stored value in and asserts the new one
comes out of the real read path.
"""

from __future__ import annotations

import uuid

from sqlalchemy.engine import Connection

from policy_atlas.api import checkin_read
from policy_atlas.api.lifecycle import both_generations
from policy_atlas.api.readmodels.repository import decisions_page
from policy_atlas.api.routers import sse
from policy_atlas.core import events
from policy_atlas.core.schema import capability_run, event_log
from policy_atlas.runtime.steering_events import canonical_actor
from policy_atlas.runtime.task_plan import TaskPlan, canonical_steer_point
from tests.helpers import now, seed_scope, seed_task_and_run

_OLD_STEER_POINT = "evidence_base_coverage"


def _seed_walk(conn: Connection) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Seed a task, a run and one capability-run walk; return their ids."""
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    walk_id = uuid.uuid4()
    conn.execute(
        capability_run.insert().values(
            capability_run_id=walk_id,
            task_id=task_id,
            evidence_scope_id=scope_id,
            capability="evidence_search",
            plan_id=uuid.uuid4(),
            plan_version=1,
            status="running",
            session_id=None,
            started_at=now(),
            ended_at=None,
        )
    )
    return task_id, run_id, walk_id


def _rows(conn: Connection, task_id: uuid.UUID) -> list[dict[str, object]]:
    """Every durable event for the task, in the shape ``_map_rows`` expects."""
    return sse._event_rows(conn, task_id=task_id, after=0, through=None)


def test_canonical_actor_maps_only_the_retired_actor_word() -> None:
    """The map is one entry; every other value and every non-string is inert."""
    assert canonical_actor("orchestrator") == "agent"
    assert canonical_actor("user") == "user"
    assert canonical_actor("standing_default") == "standing_default"
    assert canonical_actor(None) is None
    assert canonical_actor(7) is None


def test_a_decision_stored_by_the_old_actor_word_reads_as_agent(conn: Connection) -> None:
    """REST and SSE both project a pre-038 decision as decided by the Agent.

    Without ``canonical_actor`` the literal ``{"user", "agent",
    "standing_default"}`` filter on both paths would drop the stored value and
    render the decision as attributed to nobody.
    """
    task_id, run_id, walk_id = _seed_walk(conn)
    check_in_id = events.append(
        conn,
        task_id=task_id,
        run_id=run_id,
        event_type="steering.pause",
        payload={
            "capability_run_id": str(walk_id),
            "plan_id": str(uuid.uuid4()),
            "plan_version": 1,
            "boundary": "after_component",
            "component": "acquire",
            "kind": "steer_point",
            "steer_point": "search_review",
            "options": [{"id": "proceed", "label": "Proceed"}],
        },
    )
    events.append(
        conn,
        task_id=task_id,
        run_id=run_id,
        event_type="steering.decision",
        payload={
            "capability_run_id": str(walk_id),
            "plan_id": str(uuid.uuid4()),
            "plan_version": 1,
            "boundary": "after_component",
            "component": "acquire",
            "check_in_id": str(check_in_id),
            # The pre-038 wire word, exactly as the old image wrote it.
            "decided_by": "orchestrator",
            "authored_by": "orchestrator",
            "response": "continue",
            "interpreted_action": None,
            "confirmed": True,
        },
    )

    page = decisions_page(conn, task_id, 1, 50)
    decisions = [item for item in page.data if item.kind == "steering.decision"]
    assert [item.decided_by for item in decisions] == ["agent"]
    # The raw payload is untouched — nothing rewrote the stored row.
    detail = decisions[0].detail or {}
    assert detail["decided_by"] == "orchestrator"

    frames = sse._map_rows(conn, task_id=task_id, rows=_rows(conn, task_id), through=None)
    resolved = [frame for frame in frames if frame["type"] == "checkin.resolved"]
    assert [frame["decided_by"] for frame in resolved] == ["agent"]


def test_canonical_steer_point_maps_the_retired_p2_id() -> None:
    """One entry, and anything else — including a non-string — passes through."""
    assert canonical_steer_point(_OLD_STEER_POINT) == "evidence_search_coverage"
    assert canonical_steer_point("search_review") == "search_review"
    assert canonical_steer_point(None) is None


def test_a_stored_plan_with_the_old_steer_point_id_still_validates() -> None:
    """``TaskPlan.model_validate`` canonicalises before the fail-closed check.

    ``validate_steer_point`` rejects anything outside ``STEER_POINTS``, and
    plan payloads are re-validated at every read, so without the ``mode=
    "before"`` validator a pre-038 plan would fail to load at all (contract A3).
    """
    plan = TaskPlan.model_validate(
        {
            "title": "A pre-038 plan",
            "question": "What works?",
            "scoping_notes": [],
            "screening_criteria": ["Include empirical sources"],
            "backend_scope": "both",
            "scope_constraints": {},
            "search_effort": "rapid",
            "analysis_depth": "landscape",
            "components": [],
            "component_rationale": {},
            "grouping_facets": None,
            "steering_mode": "moderate",
            "steer_point_defaults": [
                {"steer_point": _OLD_STEER_POINT, "action": "proceed_flag"}
            ],
        }
    )
    assert [rule.steer_point for rule in plan.steer_point_defaults] == [
        "evidence_search_coverage"
    ]


def test_a_pause_record_with_the_old_steer_point_id_still_projects_its_bundle() -> None:
    """The pause-record reader shares the plan's map, so the P2 bundle survives."""
    check_in = checkin_read._check_in(
        {
            "event_id": uuid.uuid4(),
            "occurred_at": now(),
            "sequence": 1,
            "payload": {
                "kind": "steer_point",
                "boundary": "after_component",
                "component": "screen_abstract",
                "steer_point": _OLD_STEER_POINT,
                "options": [{"id": "proceed", "label": "Proceed"}],
                "bundle": {"themes": [{"label": "Alpha"}]},
            },
        },
        decided=False,
    )
    assert check_in.bundle == {"themes": [{"label": "Alpha"}]}


def test_both_generations_pairs_each_lifecycle_kind_with_its_pre_038_name() -> None:
    """The declared pairing, and its refusal of anything that is not a kind."""
    assert both_generations("renamed") == {"task.renamed", "project.renamed"}
    assert both_generations("shared_publicly", "unshared") == {
        "task.shared_publicly",
        "project.shared_publicly",
        "task.unshared",
        "project.unshared",
    }
    try:
        both_generations("exploded")
    except ValueError as error:
        assert "exploded" in str(error)
    else:  # pragma: no cover - the guard must fire
        raise AssertionError("both_generations accepted a non-lifecycle kind")


def test_pre_038_lifecycle_events_still_reach_both_read_paths(conn: Connection) -> None:
    """A ``project.renamed``/``project.archived`` row reads as today's sentence.

    ``event_log`` is append-only: these rows exist and their words are never
    rewritten, so the decisions read model and the SSE projection must accept
    both generations of the kind (contract V1).
    """
    task_id, run_id = seed_task_and_run(conn)
    for event_type, payload in (
        ("project.renamed", {"name_from": "Before", "name_to": "After", "actor": "user"}),
        ("project.archived", {"actor": "user"}),
    ):
        events.append(
            conn, task_id=task_id, run_id=run_id, event_type=event_type, payload=payload
        )

    summaries = {item.kind: item.summary for item in decisions_page(conn, task_id, 1, 50).data}
    assert summaries["project.renamed"] == "Renamed the task."
    assert summaries["project.archived"] == "Archived the task."

    frames = sse._map_rows(conn, task_id=task_id, rows=_rows(conn, task_id), through=None)
    updates = [frame for frame in frames if frame["type"] == "task.updated"]
    assert [frame.get("name") for frame in updates] == ["After", None]
    assert [frame.get("status") for frame in updates] == [None, "archived"]
    # The stored rows keep their words.
    stored = conn.execute(
        event_log.select().where(event_log.c.task_id == task_id)
    ).mappings().all()
    assert {row["event_type"] for row in stored} == {"project.renamed", "project.archived"}
