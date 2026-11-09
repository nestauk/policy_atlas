"""The shortlist buttons and their History lines (task 055, items 2 and 5; P9).

Contract acceptance, item 2: *add to shortlist* on a pick turns it the
user's place; *remove* on a pick sets it aside and opens no walk; *remove*
on the user's place clears it; *exclude* clears a place and *include again*
does not restore it; the events carry the actor. Item 5's route: Suggest
more opens a shortlist walk (202 with the walk) and is refused while a walk
runs, when nothing is left to propose, and when there is no longlist. The
History lines: the two user events read as the user's decision with the
option's name; ``shortlist.proposed`` reads as Policy Atlas's.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.api.deps import get_executor, get_runner_backends
from policy_atlas.core import events
from policy_atlas.core.schema import (
    capability_run,
    evidence_scope,
    longlist_result,
    option,
    task_plan,
)
from policy_atlas.options_scoping.shortlist.shortlist import SHORTLIST_PROPOSED
from policy_atlas.runtime.capability_registry import latest_approved_plan_row
from tests.api.org_support import tenancy_client
from tests.api.resource_support import (  # noqa: F401 — autouse teardown
    api_client,
    create_task,
    end_walks,
    remove_committed_tasks_after_walks,
)
from tests.api.test_longlist_routes import _build, _Built, _org_build
from tests.api.test_longlist_start import RecordingExecutor
from tests.runtime.test_runner import _runner_backends


def _overrides(executor: RecordingExecutor) -> dict[Callable[..., object], Callable[..., object]]:
    return {get_executor: lambda: executor, get_runner_backends: _runner_backends}


def _set(engine: Engine, option_id: uuid.UUID, **values: Any) -> None:
    with engine.begin() as conn:
        conn.execute(option.update().where(option.c.option_id == option_id).values(**values))


def _row(engine: Engine, option_id: uuid.UUID) -> Any:
    with engine.connect() as conn:
        return conn.execute(select(option).where(option.c.option_id == option_id)).one()


def _post(client: TestClient, built: _Built, oid: uuid.UUID, verb: str, headers: Any) -> Any:
    return client.post(f"/api/v1/tasks/{built.task_id}/options/{oid}/{verb}", headers=headers)


def _history(client: TestClient, built: _Built, headers: Any) -> list[dict[str, Any]]:
    response = client.get(
        f"/api/v1/tasks/{built.task_id}/decisions?page_size=200", headers=headers
    )
    assert response.status_code == 200, response.text
    return [
        d
        for d in response.json()["data"]
        if d["kind"] == SHORTLIST_PROPOSED or d["kind"].startswith("option.")
    ]


def _proposed_under(engine: Engine, built: _Built, appetite: str) -> None:
    """Record a stored proposal made under ``appetite`` on the built longlist."""
    with engine.begin() as conn:
        conn.execute(
            longlist_result.update()
            .where(longlist_result.c.task_id == built.task_id)
            .values(shortlist={"note": "A note.", "provenance": {"appetite": appetite}})
        )


def _set_appetite(engine: Engine, built: _Built, appetite: str) -> None:
    """Move the current approved plan to ``appetite``; the longlist inputs stay as built."""
    with engine.begin() as conn:
        row = latest_approved_plan_row(conn, built.task_id)
        assert row is not None
        conn.execute(
            task_plan.update()
            .where(task_plan.c.plan_id == row["plan_id"])
            .values(payload={**row["payload"], "risk_appetite": appetite})
        )


def _scope_context(engine: Engine, executor: RecordingExecutor) -> dict[str, Any]:
    with engine.connect() as conn:
        record = conn.execute(
            select(evidence_scope).where(
                evidence_scope.c.evidence_scope_id == executor.submitted[-1]["evidence_scope_id"]
            )
        ).one()
    assert record.purpose == "shortlist"
    return dict(record.context)


def _walks(engine: Engine, task_id: uuid.UUID) -> int:
    with engine.connect() as conn:
        return len(
            conn.execute(
                select(capability_run.c.capability_run_id).where(
                    capability_run.c.task_id == task_id
                )
            ).all()
        )


def test_add_on_a_pick_makes_it_yours_and_a_repeat_changes_nothing(
    engine: Engine, tmp_path: Path
) -> None:
    with tenancy_client(tmp_path) as (client, (owner, colleague, _)):
        built = _org_build(engine, owner, colleague, linked=False)
        oid = built.options["Mentoring"]
        _set(engine, oid, shortlist_state="proposed", shortlist_reason="A reason.")

        added = _post(client, built, oid, "shortlist", owner.headers)
        assert added.status_code == 200, added.text
        assert added.json()["shortlist"] == {"state": "added_by_you", "reason": None}
        assert (_row(engine, oid).shortlist_state, _row(engine, oid).shortlist_reason) == (
            "added_by_you",
            None,
        )
        again = _post(client, built, oid, "shortlist", owner.headers)
        assert again.status_code == 200, again.text
        assert again.json()["shortlist"]["state"] == "added_by_you"

        history = _history(client, built, owner.headers)
        assert [h["kind"] for h in history] == ["option.shortlisted"]  # one event, not two
        assert history[0]["decided_by"] == "user"
        assert history[0]["detail"]["actor"] == owner.user_id
        assert history[0]["summary"] == "You added “Mentoring” to the shortlist."
        assert history[0]["actor_is_viewer"] is True
        # Task 058, round 10: "You" is the reader's word only; a colleague
        # reads the owner's name.
        seen_by_colleague = _history(client, built, colleague.headers)
        name = seen_by_colleague[0]["actor_display"]
        assert name and name != "You"
        assert seen_by_colleague[0]["actor_is_viewer"] is False
        assert seen_by_colleague[0]["summary"] == f"{name} added “Mentoring” to the shortlist."


def test_add_on_an_option_with_no_place_makes_it_yours(engine: Engine, tmp_path: Path) -> None:
    with tenancy_client(tmp_path) as (client, (owner, colleague, _)):
        built = _org_build(engine, owner, colleague, linked=False)
        oid = built.options["Mentoring"]
        added = _post(client, built, oid, "shortlist", owner.headers)
        assert added.status_code == 200, added.text
        assert _row(engine, oid).shortlist_state == "added_by_you"


def test_add_refuses_an_excluded_or_merged_option_and_404s_an_unknown_one(
    engine: Engine, tmp_path: Path
) -> None:
    with tenancy_client(tmp_path) as (client, (owner, colleague, _)):
        built = _org_build(engine, owner, colleague, linked=False)
        excluded = built.options["Mentoring"]
        merged = built.options["Guarantee package"]
        _set(engine, excluded, state="excluded")
        _set(engine, merged, merged_into_option_id=built.options["Youth guarantee"])
        for oid in (excluded, merged):
            refused = _post(client, built, oid, "shortlist", owner.headers)
            assert refused.status_code == 409, refused.text
            assert refused.json()["error"]["code"] == "not_included"
            assert _row(engine, oid).shortlist_state is None
        unknown = _post(client, built, uuid.uuid4(), "shortlist", owner.headers)
        assert unknown.status_code == 404
        assert _post(client, built, uuid.uuid4(), "unshortlist", owner.headers).status_code == 404
        assert _history(client, built, owner.headers) == []


def test_remove_sets_a_pick_aside_clears_your_place_and_opens_no_walk(
    engine: Engine, tmp_path: Path
) -> None:
    with tenancy_client(tmp_path) as (client, (owner, colleague, _)):
        built = _org_build(engine, owner, colleague, linked=False)
        pick = built.options["Mentoring"]
        mine = built.options["Youth guarantee"]
        none = built.options["Guarantee package"]
        _set(engine, pick, shortlist_state="proposed", shortlist_reason="A reason.")
        _set(engine, mine, shortlist_state="added_by_you")
        walks = _walks(engine, built.task_id)

        removed = _post(client, built, pick, "unshortlist", owner.headers)
        assert removed.status_code == 200, removed.text
        assert removed.json()["shortlist"] == {"state": "set_aside", "reason": None}
        cleared = _post(client, built, mine, "unshortlist", owner.headers)
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()["shortlist"] is None
        nothing = _post(client, built, none, "unshortlist", owner.headers)
        assert nothing.status_code == 200, nothing.text
        assert nothing.json()["shortlist"] is None

        assert _walks(engine, built.task_id) == walks  # no refill, no walk
        history = _history(client, built, owner.headers)
        assert [h["kind"] for h in history] == ["option.unshortlisted"] * 2
        assert all(h["decided_by"] == "user" for h in history)
        assert history[1]["summary"] == "You removed “Mentoring” from the shortlist."
        assert history[0]["detail"]["previous_state"] == "added_by_you"


def test_exclude_clears_a_place_and_include_again_does_not_restore_it(
    engine: Engine, tmp_path: Path
) -> None:
    """A place is cleared; a set-aside stays set aside, so it is never re-proposed (S9)."""
    with tenancy_client(tmp_path) as (client, (owner, colleague, _)):
        built = _org_build(engine, owner, colleague, linked=False)
        for state in ("proposed", "added_by_you", "set_aside"):
            oid = built.options["Mentoring"]
            _set(engine, oid, shortlist_state=state, shortlist_reason="A reason.")
            expected = (
                ("set_aside", "A reason.") if state == "set_aside" else (None, None)
            )
            excluded = client.post(
                f"/api/v1/tasks/{built.task_id}/options/{oid}/exclude",
                headers=owner.headers,
                json={"reason": "No."},
            )
            assert excluded.status_code == 200, excluded.text
            assert (_row(engine, oid).shortlist_state, _row(engine, oid).shortlist_reason) == (
                expected
            )
            included = _post(client, built, oid, "include", owner.headers)
            assert included.status_code == 200, included.text
            assert _row(engine, oid).shortlist_state == expected[0]
            if state != "set_aside":
                assert excluded.json()["shortlist"] is None
                assert included.json()["shortlist"] is None


def test_the_buttons_are_run_active_while_a_parentless_walk_runs(
    engine: Engine, tmp_path: Path
) -> None:
    executor = RecordingExecutor()
    with tenancy_client(tmp_path, overrides=_overrides(executor)) as (
        client,
        (owner, colleague, _),
    ):
        built = _org_build(engine, owner, colleague, linked=False)
        oid = built.options["Mentoring"]
        with engine.begin() as conn:
            conn.execute(
                capability_run.update()
                .where(capability_run.c.capability_run_id == built.walk_id)
                .values(status="running", ended_at=None)
            )
        for response in (
            _post(client, built, oid, "shortlist", owner.headers),
            _post(client, built, oid, "unshortlist", owner.headers),
            client.post(f"/api/v1/tasks/{built.task_id}/shortlist/suggest", headers=owner.headers),
        ):
            assert response.status_code == 409, response.text
            assert response.json()["error"]["code"] == "run_active"
        assert executor.submitted == []
        end_walks(engine, built.task_id)


def test_suggest_more_opens_a_shortlist_walk_and_a_second_press_is_run_active(
    engine: Engine, tmp_path: Path
) -> None:
    executor = RecordingExecutor()
    with tenancy_client(tmp_path, overrides=_overrides(executor)) as (
        client,
        (owner, colleague, _),
    ):
        built = _org_build(engine, owner, colleague, linked=False)
        _proposed_under(engine, built, "mostly_tried")
        opened = client.post(
            f"/api/v1/tasks/{built.task_id}/shortlist/suggest", headers=owner.headers
        )
        assert opened.status_code == 202, opened.text
        body = opened.json()
        assert body["status"] == "running"
        assert [str(call["capability_run_id"]) for call in executor.submitted] == [
            body["capability_run_id"]
        ]
        with engine.connect() as conn:
            record = conn.execute(
                select(evidence_scope).where(
                    evidence_scope.c.evidence_scope_id
                    == executor.submitted[0]["evidence_scope_id"]
                )
            ).one()
        assert (record.purpose, record.context.get("suggest")) == ("shortlist", True)

        again = client.post(
            f"/api/v1/tasks/{built.task_id}/shortlist/suggest", headers=owner.headers
        )
        assert again.status_code == 409, again.text
        assert again.json()["error"]["code"] == "run_active"
        end_walks(engine, built.task_id)


def test_suggest_more_with_nothing_left_is_refused(engine: Engine, tmp_path: Path) -> None:
    executor = RecordingExecutor()
    with tenancy_client(tmp_path, overrides=_overrides(executor)) as (
        client,
        (owner, colleague, _),
    ):
        built = _org_build(engine, owner, colleague, linked=False)
        _proposed_under(engine, built, "mostly_tried")
        states = ["proposed", "added_by_you", "set_aside"]
        for oid, state in zip(built.options.values(), states, strict=False):
            _set(engine, oid, shortlist_state=state)
        refused = client.post(
            f"/api/v1/tasks/{built.task_id}/shortlist/suggest", headers=owner.headers
        )
        assert refused.status_code == 409, refused.text
        assert refused.json()["error"]["code"] == "nothing_to_propose"
        assert executor.submitted == []


def test_suggest_more_on_a_stale_proposal_re_proposes(engine: Engine, tmp_path: Path) -> None:
    """After an appetite change Suggest more proposes again, even with every option placed."""
    executor = RecordingExecutor(status="succeeded")  # no 60-second teardown wait
    with tenancy_client(tmp_path, overrides=_overrides(executor)) as (
        client,
        (owner, colleague, _),
    ):
        built = _org_build(engine, owner, colleague, linked=False)
        for oid in built.options.values():
            _set(engine, oid, shortlist_state="proposed", shortlist_reason="A reason.")
        _proposed_under(engine, built, "tried_only")
        _set_appetite(engine, built, "open_to_untested")
        opened = client.post(
            f"/api/v1/tasks/{built.task_id}/shortlist/suggest", headers=owner.headers
        )
        assert opened.status_code == 202, opened.text
        assert "suggest" not in _scope_context(engine, executor)


def test_suggest_more_on_a_current_proposal_keeps_the_places(
    engine: Engine, tmp_path: Path
) -> None:
    executor = RecordingExecutor(status="succeeded")  # no 60-second teardown wait
    with tenancy_client(tmp_path, overrides=_overrides(executor)) as (
        client,
        (owner, colleague, _),
    ):
        built = _org_build(engine, owner, colleague, linked=False)
        _proposed_under(engine, built, "open_to_untested")
        _set_appetite(engine, built, "open_to_untested")
        opened = client.post(
            f"/api/v1/tasks/{built.task_id}/shortlist/suggest", headers=owner.headers
        )
        assert opened.status_code == 202, opened.text
        assert _scope_context(engine, executor).get("suggest") is True


def test_suggest_more_without_a_longlist_is_a_404(engine: Engine, tmp_path: Path) -> None:
    executor = RecordingExecutor()
    with tenancy_client(tmp_path, overrides=_overrides(executor)) as (
        client,
        (owner, colleague, _),
    ):
        built = _org_build(engine, owner, colleague, linked=False)
        with engine.begin() as conn:
            conn.execute(
                longlist_result.delete().where(longlist_result.c.task_id == built.task_id)
            )
        refused = client.post(
            f"/api/v1/tasks/{built.task_id}/shortlist/suggest", headers=owner.headers
        )
        assert refused.status_code == 404, refused.text
        assert executor.submitted == []


def test_suggest_more_after_a_longlist_input_change_is_plan_stale(
    engine: Engine, tmp_path: Path
) -> None:
    executor = RecordingExecutor()
    with tenancy_client(tmp_path, overrides=_overrides(executor)) as (
        client,
        (owner, colleague, _),
    ):
        built = _org_build(engine, owner, colleague, linked=False)
        patched = client.patch(
            f"/api/v1/tasks/{built.task_id}/plan",
            headers=owner.headers,
            json={"scoping": {"where": {"text": "England", "origin": "your_call"}}},
        )
        assert patched.status_code == 200, patched.text
        assert patched.json()["opened_run"] is None
        refused = client.post(
            f"/api/v1/tasks/{built.task_id}/shortlist/suggest", headers=owner.headers
        )
        assert refused.status_code == 409, refused.text
        assert refused.json()["error"]["code"] == "plan_stale"
        assert executor.submitted == []


def test_the_proposal_reads_as_policy_atlas_s_decision(engine: Engine, tmp_path: Path) -> None:
    with tenancy_client(tmp_path) as (client, (owner, colleague, _)):
        built = _org_build(engine, owner, colleague, linked=False)
        with engine.begin() as conn:
            events.append(
                conn,
                task_id=built.task_id,
                run_id=None,
                event_type=SHORTLIST_PROPOSED,
                payload={
                    "actor": "agent",
                    "places": [
                        {"option_id": str(oid), "name": name, "state": "proposed", "reason": "r"}
                        for name, oid in built.options.items()
                    ],
                    "note": "A note.",
                },
            )
        history = [
            h for h in _history(client, built, owner.headers) if h["kind"] == SHORTLIST_PROPOSED
        ]
        assert len(history) == 1
        assert history[0]["decided_by"] == "agent"
        count = len(built.options)
        assert history[0]["summary"] == f"Policy Atlas proposed {count} places."


def test_the_buttons_are_422_on_an_evidence_search_task(engine: Engine, tmp_path: Path) -> None:
    executor = RecordingExecutor()
    with api_client(tmp_path, _overrides(executor)) as (client, owner, _other):
        task_id = create_task(client, owner)
        oid = uuid.uuid4()
        for response in (
            client.post(f"/api/v1/tasks/{task_id}/options/{oid}/shortlist", headers=owner),
            client.post(f"/api/v1/tasks/{task_id}/options/{oid}/unshortlist", headers=owner),
            client.post(f"/api/v1/tasks/{task_id}/shortlist/suggest", headers=owner),
        ):
            assert response.status_code == 422, response.text
        assert executor.submitted == []


def test_the_shortlist_routes_are_the_owner_s(engine: Engine, tmp_path: Path) -> None:
    """An outsider gets 404, a same-organisation reader 403, another task's option 404."""
    executor = RecordingExecutor()
    with tenancy_client(tmp_path, overrides=_overrides(executor)) as (
        client,
        (owner, colleague, stranger),
    ):
        built = _org_build(engine, owner, colleague, linked=False)
        other = _build(engine, owner=owner.user_id, linked=False)
        oid = built.options["Mentoring"]
        suggest = f"/api/v1/tasks/{built.task_id}/shortlist/suggest"
        for caller, status in ((stranger, 404), (colleague, 403)):
            for verb in ("shortlist", "unshortlist"):
                refused = _post(client, built, oid, verb, caller.headers)
                assert refused.status_code == status, (verb, refused.text)
            refused = client.post(suggest, headers=caller.headers)
            assert refused.status_code == status, refused.text
        foreign = other.options["Mentoring"]
        for verb in ("shortlist", "unshortlist"):
            refused = _post(client, built, foreign, verb, owner.headers)
            assert refused.status_code == 404, (verb, refused.text)
        assert _row(engine, foreign).shortlist_state is None
        assert _row(engine, oid).shortlist_state is None
        assert executor.submitted == []


def test_the_note_is_rewritten_only_when_the_places_have_moved(
    engine: Engine, tmp_path: Path
) -> None:
    """Task 058, round 14: ``note_stale`` once the places differ from the ones
    the note was written against; the refresh writes the note through its one
    writer with the places, logs one History line, and is a no-op when fresh."""
    with tenancy_client(tmp_path) as (client, (owner, colleague, _)):
        built = _org_build(engine, owner, colleague, linked=False)
        guarantee = built.options["Youth guarantee"]
        with engine.begin() as conn:
            conn.execute(
                longlist_result.update()
                .where(longlist_result.c.task_id == built.task_id)
                .values(
                    shortlist={
                        "note": "Old note.",
                        "provenance": {"appetite": "mostly_tried"},
                        "places_at": [],
                    }
                )
            )

        def shortlist() -> dict[str, Any]:
            body = client.get(
                f"/api/v1/tasks/{built.task_id}/longlist", headers=owner.headers
            ).json()
            return dict(body["shortlist"])

        def note_lines() -> list[str]:
            response = client.get(
                f"/api/v1/tasks/{built.task_id}/decisions?page_size=200", headers=owner.headers
            )
            return [
                row["summary"]
                for row in response.json()["data"]
                if row["kind"] == "shortlist.note_updated"
            ]

        url = f"/api/v1/tasks/{built.task_id}/shortlist/note"
        # Fresh: no places then, none now. The refresh changes nothing.
        assert shortlist()["note_stale"] is False
        fresh = client.post(url, headers=owner.headers)
        assert fresh.status_code == 200, fresh.text
        assert fresh.json()["note"] == "Old note." and note_lines() == []

        # The reader adds a place by hand: the note is stale.
        assert _post(client, built, guarantee, "shortlist", owner.headers).status_code == 200
        assert shortlist()["note_stale"] is True
        # A colleague cannot rewrite it.
        assert client.post(url, headers=colleague.headers).status_code in (403, 404)

        written = client.post(url, headers=owner.headers)
        assert written.status_code == 200, written.text
        assert written.json()["note"] == "stub note"
        assert written.json()["note_stale"] is False
        assert note_lines() == ["Policy Atlas updated the shortlist note."]
        with engine.connect() as conn:
            stored = conn.execute(
                select(longlist_result.c.shortlist).where(
                    longlist_result.c.task_id == built.task_id
                )
            ).scalar_one()
        assert stored["places_at"] == [str(guarantee)]
        assert stored["provenance"] == {"appetite": "mostly_tried"}
        # Fresh again: a second press writes nothing.
        assert client.post(url, headers=owner.headers).json()["note"] == "stub note"
        assert note_lines() == ["Policy Atlas updated the shortlist note."]


def test_a_note_refresh_opens_no_run_and_writes_only_its_history_line(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Round 15 (owner): the refresh runs inline under the request: no
    capability or component run, no ``run.*`` or stage event, so the Task
    Agent thread gets no new progress card; only its one History line."""
    with tenancy_client(tmp_path) as (client, (owner, colleague, _)):
        built = _org_build(engine, owner, colleague, linked=False)
        guarantee = built.options["Youth guarantee"]
        with engine.begin() as conn:
            conn.execute(
                longlist_result.update()
                .where(longlist_result.c.task_id == built.task_id)
                .values(
                    shortlist={
                        "note": "Old note.",
                        "provenance": {"appetite": "mostly_tried"},
                        "places_at": [],
                    }
                )
            )
        assert _post(client, built, guarantee, "shortlist", owner.headers).status_code == 200

        def runs() -> list[Any]:
            response = client.get(
                f"/api/v1/tasks/{built.task_id}/runs?page_size=200", headers=owner.headers
            )
            assert response.status_code == 200, response.text
            return list(response.json()["data"])

        def event_types() -> list[str]:
            with engine.connect() as conn:
                return [entry["event_type"] for entry in events.read(conn, built.task_id)]

        runs_before, events_before = runs(), event_types()
        # The live half of the stream: nothing reaches the tick hub.
        from policy_atlas.api.routers import sse
        from policy_atlas.core import liveness

        hub_ticks: list[Any] = []
        original_publish = liveness.tick_hub.publish_tick

        def capture(task: uuid.UUID, **payload: Any) -> None:
            hub_ticks.append(payload)
            original_publish(task, **payload)

        monkeypatch.setattr(liveness.tick_hub, "publish_tick", capture)
        with engine.connect() as conn:
            capability_runs_before = conn.execute(
                select(capability_run.c.capability_run_id).where(
                    capability_run.c.task_id == built.task_id
                )
            ).all()
        refreshed = client.post(
            f"/api/v1/tasks/{built.task_id}/shortlist/note", headers=owner.headers
        )
        assert refreshed.status_code == 200, refreshed.text
        assert refreshed.json()["note_stale"] is False
        assert runs() == runs_before
        with engine.connect() as conn:
            capability_runs_after = conn.execute(
                select(capability_run.c.capability_run_id).where(
                    capability_run.c.task_id == built.task_id
                )
            ).all()
        assert capability_runs_after == capability_runs_before
        assert event_types()[len(events_before) :] == ["shortlist.note_updated"]
        assert hub_ticks == []
        # The persisted half: the stream maps the new event to no frame at all.
        with engine.connect() as conn:
            rows = sse._event_rows(conn, task_id=built.task_id, after=0, through=None)
            new_rows = rows[len(events_before) :]
            assert [row["event_type"] for row in new_rows] == ["shortlist.note_updated"]
            frames = sse._map_rows(conn, task_id=built.task_id, rows=new_rows, through=None)
        assert frames == []
