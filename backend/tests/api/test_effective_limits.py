"""Task 065 (B12): one resolver for a person's task quota and run cap.

``effective_limits`` reads the four override columns (own row, then
organisation, then settings) and nothing else does. The unit cases drive the
resolver on the rolled-back ``conn``; the route cases prove the task-create
check and ``/me`` read it, through ``tenancy_client`` against committed rows.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection, Engine

from policy_atlas.api.routers.common import Limits, LimitSource, effective_limits
from policy_atlas.api.routers.runs import user_at_run_cap
from policy_atlas.api.settings import Settings
from policy_atlas.core.schema import app_user, cohort, cohort_member, organisation, task
from tests.api.org_support import (
    make_org,
    make_task,
    make_user,
    ops_enrol,
    seeded,
    tenancy_client,
    unregistered_user,
)
from tests.helpers import delete_task_data, seed_walk

SETTINGS = Settings("i", "c", None, None, "o", "db", runs_per_user=3, task_quota_per_year=50)


def _limits(conn: Connection, user_id: str) -> Limits:
    return effective_limits(conn, user_id, settings=SETTINGS)


def _set_user(conn: Connection, user_id: str, **values: object) -> None:
    conn.execute(update(app_user).where(app_user.c.user_id == user_id).values(**values))


def _set_org(conn: Connection, org_id: uuid.UUID, **values: object) -> None:
    conn.execute(update(organisation).where(organisation.c.org_id == org_id).values(**values))


# --- the resolver --------------------------------------------------------------


def test_a_person_with_no_row_gets_the_settings_defaults(conn: Connection) -> None:
    assert _limits(conn, unregistered_user()) == Limits(task_quota=50, runs=3)


def test_precedence_is_person_then_organisation_then_settings_per_field(
    conn: Connection,
) -> None:
    org_id = make_org(conn)
    user_id = make_user(conn, org_id=org_id)
    assert _limits(conn, user_id) == Limits(task_quota=50, runs=3)

    _set_org(conn, org_id, task_quota_per_year=20, runs_per_user=2)
    assert _limits(conn, user_id) == Limits(task_quota=20, runs=2)

    # Each field resolves on its own: the person overrides one, inherits the other.
    _set_user(conn, user_id, task_quota_per_year=10)
    assert _limits(conn, user_id) == Limits(task_quota=10, runs=2)
    _set_user(conn, user_id, runs_per_user=1)
    assert _limits(conn, user_id) == Limits(task_quota=10, runs=1)

    # An unenrolled person has no organisation to inherit from.
    _set_user(conn, user_id, org_id=None, task_quota_per_year=None)
    assert _limits(conn, user_id) == Limits(task_quota=50, runs=1)


def _cohort(conn: Connection, user_id: str, *, joined_days_ago: int, **values: object) -> None:
    """One cohort with these overrides, joined by the person that many days ago."""
    cohort_id = uuid.uuid4()
    now = datetime.now(UTC)
    conn.execute(insert(cohort).values(
        cohort_id=cohort_id, name=f"cohort {cohort_id}", created_at=now, **values))
    conn.execute(insert(cohort_member).values(
        cohort_id=cohort_id, user_id=user_id, added_at=now - timedelta(days=joined_days_ago)))


def latest_cohort(conn: Connection, user_id: str, days_ago: int) -> str:
    """The id of the cohort the person joined that many days ago (the helper names it after it)."""
    rows = conn.execute(select(cohort_member.c.cohort_id, cohort_member.c.added_at)
                        .where(cohort_member.c.user_id == user_id)).all()
    now = datetime.now(UTC)
    return str(min(rows, key=lambda r: abs((now - r[1]).days - days_ago))[0])


def test_a_cohort_sits_between_the_person_and_the_organisation(conn: Connection) -> None:
    """Person, then cohort, then organisation; the latest-joined cohort that sets a field wins."""
    org_id = make_org(conn)
    user_id = make_user(conn, org_id=org_id)
    _set_org(conn, org_id, task_quota_per_year=20, runs_per_user=2)
    _cohort(conn, user_id, joined_days_ago=10, task_quota_per_year=200, runs_per_user=None)
    assert _limits(conn, user_id) == Limits(task_quota=200, runs=2)
    # A later cohort that sets only runs leaves tasks to the earlier one.
    _cohort(conn, user_id, joined_days_ago=1, runs_per_user=5)
    assert _limits(conn, user_id) == Limits(task_quota=200, runs=5)
    _cohort(conn, user_id, joined_days_ago=0, task_quota_per_year=0)
    assert _limits(conn, user_id) == Limits(task_quota=None, runs=5)
    limits = _limits(conn, user_id)
    assert (limits.task_quota_from, limits.runs_from) == (
        LimitSource("cohort", f"cohort {latest_cohort(conn, user_id, 0)}"),
        LimitSource("cohort", f"cohort {latest_cohort(conn, user_id, 1)}"),
    )
    _set_user(conn, user_id, task_quota_per_year=7)
    assert _limits(conn, user_id) == Limits(task_quota=7, runs=5)
    assert _limits(conn, user_id).task_quota_from == LimitSource("person")


def test_cohorts_joined_at_the_same_moment_tie_break_on_id_not_name(conn: Connection) -> None:
    """Equal join times pick the lowest cohort id; renaming a cohort cannot change the answer."""
    user_id = make_user(conn)
    now = datetime.now(UTC)
    # Name order and id order disagree, so a name tie-break picks the other one.
    for number, name, quota in ((1, "zz tie", 11), (2, "aa tie", 22)):
        cohort_id = uuid.UUID(int=number)
        conn.execute(insert(cohort).values(cohort_id=cohort_id, name=name, created_at=now,
                                           task_quota_per_year=quota))
        conn.execute(insert(cohort_member).values(cohort_id=cohort_id, user_id=user_id,
                                                  added_at=now))
    limits = _limits(conn, user_id)
    assert (limits.task_quota, limits.task_quota_from) == (11, LimitSource("cohort", "zz tie"))


def test_a_cohort_zero_lifts_one_limit_and_a_cleared_cohort_value_falls_back(
    conn: Connection,
) -> None:
    """A cohort's 0 is no limit for that field only; clearing it hands back to the organisation."""
    org_id = make_org(conn)
    user_id = make_user(conn, org_id=org_id)
    _set_org(conn, org_id, task_quota_per_year=20, runs_per_user=2)
    _cohort(conn, user_id, joined_days_ago=0, runs_per_user=0)
    assert _limits(conn, user_id) == Limits(task_quota=20, runs=None)
    conn.execute(update(cohort).values(runs_per_user=None).where(
        cohort.c.cohort_id == uuid.UUID(latest_cohort(conn, user_id, 0))))
    limits = _limits(conn, user_id)
    assert limits == Limits(task_quota=20, runs=2)
    assert limits.runs_from.kind == "organisation"


def test_a_cleared_override_falls_back(conn: Connection) -> None:
    org_id = make_org(conn)
    user_id = make_user(conn, org_id=org_id)
    _set_org(conn, org_id, task_quota_per_year=20, runs_per_user=2)
    _set_user(conn, user_id, task_quota_per_year=10, runs_per_user=1)
    assert _limits(conn, user_id) == Limits(task_quota=10, runs=1)

    _set_user(conn, user_id, task_quota_per_year=None, runs_per_user=None)
    assert _limits(conn, user_id) == Limits(task_quota=20, runs=2)
    _set_org(conn, org_id, task_quota_per_year=None, runs_per_user=None)
    assert _limits(conn, user_id) == Limits(task_quota=50, runs=3)


def test_zero_means_no_limit_on_either_field_at_either_level(conn: Connection) -> None:
    org_id = make_org(conn)
    user_id = make_user(conn, org_id=org_id)
    _set_user(conn, user_id, task_quota_per_year=0, runs_per_user=0)
    assert _limits(conn, user_id) == Limits(task_quota=None, runs=None)

    # A person's 0 beats an organisation's number, and vice versa.
    _set_org(conn, org_id, task_quota_per_year=20, runs_per_user=0)
    _set_user(conn, user_id, task_quota_per_year=0, runs_per_user=4)
    assert _limits(conn, user_id) == Limits(task_quota=None, runs=4)
    _set_user(conn, user_id, task_quota_per_year=None, runs_per_user=None)
    assert _limits(conn, user_id) == Limits(task_quota=20, runs=None)


def test_an_administrator_is_exempt_from_both_limits(conn: Connection) -> None:
    """Owner rulings of 2026-11-16 (task 064a): no task quota and no run cap for an admin."""
    org_id = make_org(conn)
    user_id = make_user(conn, org_id=org_id)
    _set_user(conn, user_id, is_admin=True)
    assert _limits(conn, user_id) == Limits(task_quota=None, runs=None)
    # An explicit override does not pull an administrator back under either limit.
    _set_user(conn, user_id, task_quota_per_year=10, runs_per_user=7)
    assert _limits(conn, user_id) == Limits(task_quota=None, runs=None)
    _set_org(conn, org_id, runs_per_user=2)
    _set_user(conn, user_id, runs_per_user=None)
    assert _limits(conn, user_id) == Limits(task_quota=None, runs=None)


def test_user_at_run_cap_with_no_cap_is_never_at_the_cap(conn: Connection) -> None:
    """``None`` is unlimited, not zero: a running walk fills a cap of one and no cap at all."""
    owner = make_user(conn)
    seed_walk(
        conn, make_task(conn, owner_user_id=owner), capability="evidence_search", status="running"
    )
    assert user_at_run_cap(conn, user_id=owner, cap=1) is True
    assert user_at_run_cap(conn, user_id=owner, cap=None) is False
    assert user_at_run_cap(conn, user_id=None, cap=None) is False


# --- the routes that read it -----------------------------------------------------


def _create(client: TestClient, headers: dict[str, str]) -> Response:
    return cast(
        Response,
        client.post("/api/v1/tasks", headers=headers, json={"name": "N", "question": "Q?"}),
    )


def _drop_owned(engine: Engine, owner: str) -> None:
    with engine.begin() as conn:
        for task_id in conn.execute(
            select(task.c.task_id).where(task.c.owner_user_id == owner)
        ).scalars():
            delete_task_data(conn, task_id)


def test_a_personal_quota_of_one_refuses_the_second_task_and_shows_on_me(
    engine: Engine, tmp_path: Path
) -> None:
    with tenancy_client(tmp_path, count=1) as (client, (caller,)):
        try:
            with seeded(engine) as conn:
                ops_enrol(conn, user_id=caller.user_id)
                _set_user(conn, caller.user_id, task_quota_per_year=1)
            first = _create(client, caller.headers)
            assert first.status_code == 201, first.text
            second = _create(client, caller.headers)
            assert second.status_code == 409, second.text
            assert second.json()["error"]["code"] == "task_quota"
            assert "limit of 1 tasks per year" in second.json()["error"]["message"]
            me = client.get("/api/v1/me", headers=caller.headers).json()
            assert me["task_quota"] == {"used": 1, "limit": 1}
            assert me["is_admin"] is False
        finally:
            _drop_owned(engine, caller.user_id)


def test_a_personal_quota_of_zero_hides_the_quota_band_and_admits_the_task(
    engine: Engine, tmp_path: Path
) -> None:
    with tenancy_client(tmp_path, count=1) as (client, (caller,)):
        try:
            with seeded(engine) as conn:
                ops_enrol(conn, user_id=caller.user_id)
                _set_user(conn, caller.user_id, task_quota_per_year=0)
            me = client.get("/api/v1/me", headers=caller.headers).json()
            assert (me["task_quota"], me["is_admin"]) == (None, False)
            assert _create(client, caller.headers).status_code == 201
        finally:
            _drop_owned(engine, caller.user_id)


def test_an_organisation_override_applies_to_its_member(engine: Engine, tmp_path: Path) -> None:
    with tenancy_client(tmp_path, count=1) as (client, (member,)):
        try:
            with seeded(engine) as conn:
                org_id = make_org(conn)
                _set_org(conn, org_id, task_quota_per_year=1)
                ops_enrol(conn, user_id=member.user_id, org_id=org_id)
            assert _create(client, member.headers).status_code == 201
            refused = _create(client, member.headers)
            assert refused.status_code == 409, refused.text
            assert refused.json()["error"]["code"] == "task_quota"
            assert client.get("/api/v1/me", headers=member.headers).json()["task_quota"] == {
                "used": 1,
                "limit": 1,
            }
        finally:
            _drop_owned(engine, member.user_id)
