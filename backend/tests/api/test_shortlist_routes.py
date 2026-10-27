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

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.api.deps import get_executor, get_runner_backends
from policy_atlas.core import events
from policy_atlas.core.schema import capability_run, evidence_scope, longlist_result, option
from policy_atlas.options_scoping.shortlist.shortlist import SHORTLIST_PROPOSED
from tests.api.org_support import tenancy_client
from tests.api.resource_support import (  # noqa: F401 — autouse teardown
    api_client,
    create_task,
    remove_committed_tasks_after_walks,
)
from tests.api.test_longlist_routes import _Built, _org_build
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
        assert history[0]["summary"] == "Added “Mentoring” to the shortlist."


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
        assert history[1]["summary"] == "Removed “Mentoring” from the shortlist."
        assert history[0]["detail"]["previous_state"] == "added_by_you"


def test_exclude_clears_a_place_and_include_again_does_not_restore_it(
    engine: Engine, tmp_path: Path
) -> None:
    with tenancy_client(tmp_path) as (client, (owner, colleague, _)):
        built = _org_build(engine, owner, colleague, linked=False)
        for state in ("proposed", "added_by_you", "set_aside"):
            oid = built.options["Mentoring"]
            _set(engine, oid, shortlist_state=state, shortlist_reason="A reason.")
            excluded = client.post(
                f"/api/v1/tasks/{built.task_id}/options/{oid}/exclude",
                headers=owner.headers,
                json={"reason": "No."},
            )
            assert excluded.status_code == 200, excluded.text
            assert excluded.json()["shortlist"] is None
            assert (_row(engine, oid).shortlist_state, _row(engine, oid).shortlist_reason) == (
                None,
                None,
            )
            included = _post(client, built, oid, "include", owner.headers)
            assert included.status_code == 200, included.text
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


def test_suggest_more_opens_a_shortlist_walk_and_a_second_press_is_run_active(
    engine: Engine, tmp_path: Path
) -> None:
    executor = RecordingExecutor()
    with tenancy_client(tmp_path, overrides=_overrides(executor)) as (
        client,
        (owner, colleague, _),
    ):
        built = _org_build(engine, owner, colleague, linked=False)
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


def test_suggest_more_with_nothing_left_is_refused(engine: Engine, tmp_path: Path) -> None:
    executor = RecordingExecutor()
    with tenancy_client(tmp_path, overrides=_overrides(executor)) as (
        client,
        (owner, colleague, _),
    ):
        built = _org_build(engine, owner, colleague, linked=False)
        states = ["proposed", "added_by_you", "set_aside"]
        for oid, state in zip(built.options.values(), states, strict=False):
            _set(engine, oid, shortlist_state=state)
        refused = client.post(
            f"/api/v1/tasks/{built.task_id}/shortlist/suggest", headers=owner.headers
        )
        assert refused.status_code == 409, refused.text
        assert refused.json()["error"]["code"] == "nothing_to_propose"
        assert executor.submitted == []


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
