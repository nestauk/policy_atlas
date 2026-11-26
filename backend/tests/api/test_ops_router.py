"""The ops-host routes (task 065, B4, B9, B11, B12, C5).

Every case drives the real ops-mode application against the test database;
Cognito is the real client behind a ``botocore`` Stubber (``tests/ops/support``),
so the parameters each route sends are validated against the service model.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator, MutableMapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, NamedTuple

import pytest
from botocore.stub import Stubber
from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select, text, update
from sqlalchemy.engine import Engine, RowMapping
from structlog.testing import capture_logs

from policy_atlas.api.app import create_app
from policy_atlas.api.deps import Identity, get_identity
from policy_atlas.api.dev_issuer import init, mint_token
from policy_atlas.api.settings import Settings
from policy_atlas.core.schema import (
    app_user,
    cohort_member,
    ops_action,
    organisation,
    organisation_domain,
    task,
    waitlist_entry,
)
from tests.api.org_support import (
    Principal,
    make_org,
    make_task,
    ops_enrol,
    seeded,
    tenancy_client,
    unique_email,
)
from tests.api.test_api_conformance import _flatten_api_routes
from tests.ops.support import (
    POOL_ID,
    cognito,
    expect_create,
    expect_enabled,
    expect_lock_out,
    expect_lookup,
    expect_resend,
    expect_sub_lookup,
)

#: Every ops route, pinned: the gate sweep below walks the live table and a new
#: route fails here until it has its 401/403 case and a happy case in this file.
_OPS_ROUTES = {
    ("GET", "/api/v1/ops/organisations"),
    ("POST", "/api/v1/ops/organisations"),
    ("POST", "/api/v1/ops/organisations/{org_id}/quota"),
    ("DELETE", "/api/v1/ops/organisations/{org_id}"),
    ("GET", "/api/v1/ops/cohorts"),
    ("POST", "/api/v1/ops/cohorts"),
    ("POST", "/api/v1/ops/cohorts/{cohort_id}"),
    ("POST", "/api/v1/ops/cohorts/{cohort_id}/quota"),
    ("DELETE", "/api/v1/ops/cohorts/{cohort_id}"),
    ("POST", "/api/v1/ops/people/cohort-add"),
    ("POST", "/api/v1/ops/people/cohort-remove"),
    ("GET", "/api/v1/ops/people"),
    ("POST", "/api/v1/ops/people"),
    ("POST", "/api/v1/ops/people/import-check"),
    ("POST", "/api/v1/ops/people/enrol"),
    ("POST", "/api/v1/ops/people/de-enrol"),
    ("POST", "/api/v1/ops/people/deactivate"),
    ("POST", "/api/v1/ops/people/reactivate"),
    ("POST", "/api/v1/ops/people/resend"),
    ("POST", "/api/v1/ops/people/quota"),
    ("GET", "/api/v1/ops/requests"),
    ("POST", "/api/v1/ops/requests/{entry_id}/approve"),
    ("POST", "/api/v1/ops/requests/{entry_id}/reject"),
    ("DELETE", "/api/v1/ops/requests/{entry_id}"),
}


class Harness(NamedTuple):
    """One ops-mode client, its ops-role caller, the Cognito queue and the database."""

    client: TestClient
    actor: Principal
    stubber: Stubber
    engine: Engine


def _settings(tmp_path: Path) -> Settings:
    """Build ops-mode settings against the test database, with no UI bundle."""
    return Settings(
        "http://dev-issuer.local",
        "ops-router-test",
        None,
        init(tmp_path / "issuer"),
        "http://app.example.test",
        os.environ["DATABASE_URL"],
        service_role="ops",
        ops_ui_dir=None,
    )


def _principal(settings: Settings, tmp_path: Path, label: str) -> Principal:
    """Mint a fresh signed-in subject for the ops application."""
    user_id = f"{label}-{uuid.uuid4()}"
    token = mint_token(
        user_id, settings.oidc_issuer, settings.oidc_client_id, 600, tmp_path / "issuer"
    )
    return Principal(user_id, {"Authorization": f"Bearer {token}"})


@contextmanager
def _ops_app(tmp_path: Path) -> Iterator[tuple[TestClient, Settings, Stubber]]:
    """Yield an ops-mode client whose identity seam is the stubbed Cognito."""
    settings = _settings(tmp_path)
    app = create_app(settings=settings)
    with cognito() as (client, stubber):
        app.dependency_overrides[get_identity] = lambda: Identity(client, POOL_ID, "eu-west-2")
        with TestClient(app, raise_server_exceptions=False) as http:
            yield http, settings, stubber
        stubber.assert_no_pending_responses()


@pytest.fixture
def ops(engine: Engine, tmp_path: Path) -> Iterator[Harness]:
    """An ops client signed in as a caller who holds the ops role."""
    with _ops_app(tmp_path) as (client, settings, stubber):
        actor = _principal(settings, tmp_path, "ops-actor")
        with seeded(engine) as conn:
            ops_enrol(conn, user_id=actor.user_id, email=unique_email("actor"))
            conn.execute(
                update(app_user).where(app_user.c.user_id == actor.user_id).values(is_ops=True)
            )
        yield Harness(client, actor, stubber, engine)


def _audit(h: Harness) -> list[RowMapping]:
    """Every ``ops_action`` row this caller wrote, oldest first."""
    with h.engine.connect() as conn:
        return list(
            conn.execute(
                select(ops_action)
                .where(ops_action.c.actor_user_id == h.actor.user_id)
                .order_by(ops_action.c.at, ops_action.c.action_id)
            ).mappings()
        )


def _user(h: Harness, user_id: str) -> RowMapping | None:
    """The committed ``app_user`` row for one subject."""
    with h.engine.connect() as conn:
        return (
            conn.execute(select(app_user).where(app_user.c.user_id == user_id))
            .mappings()
            .one_or_none()
        )


def _ops_lines(captured: Sequence[MutableMapping[str, Any]]) -> list[dict[str, Any]]:
    """The captured ``ops.action`` lines, in emission order."""
    return [dict(entry) for entry in captured if entry.get("event") == "ops.action"]


def _post(h: Harness, path: str, body: dict[str, Any]) -> tuple[Any, list[dict[str, Any]]]:
    """POST as the ops caller, returning the response and the ``ops.action`` lines it emitted."""
    with capture_logs() as captured:
        response = h.client.post(path, json=body, headers=h.actor.headers)
    return response, _ops_lines(captured)


def _assert_audited(
    h: Harness, lines: list[dict[str, Any]], *, action: str, target: str, outcome: str
) -> uuid.UUID:
    """Assert exactly one audit row and one matching log line, returning the action id."""
    rows = [row for row in _audit(h) if row["action"] == action]
    assert len(rows) == 1
    row = rows[0]
    assert (row["target"], row["outcome"]) == (target, outcome)
    assert len(lines) == 1
    line = lines[0]
    assert line["actor"] == h.actor.user_id
    assert (line["action"], line["target"], line["outcome"]) == (action, target, outcome)
    assert line["action_id"] == str(row["action_id"])
    assert "@" not in str(line)
    action_id = row["action_id"]
    assert isinstance(action_id, uuid.UUID)
    return action_id


def _seed_person(
    h: Harness, *, org_id: uuid.UUID | None, label: str = "person", **values: Any
) -> str:
    """Commit one person with a stored address and return their subject."""
    user_id = f"{label}-{uuid.uuid4()}"
    with seeded(h.engine) as conn:
        ops_enrol(
            conn,
            user_id=user_id,
            org_id=org_id,
            email=unique_email(label),
            display_name=f"{label.title()} {user_id}",
        )
        if values:
            conn.execute(update(app_user).where(app_user.c.user_id == user_id).values(**values))
    return user_id


def _seed_org(h: Harness) -> uuid.UUID:
    """Commit one organisation and return its id."""
    with seeded(h.engine) as conn:
        return make_org(conn)


def _seed_request(h: Harness, *, email: str | None = None, **values: Any) -> uuid.UUID:
    """Commit one waitlist row and return its id."""
    entry_id = uuid.uuid4()
    with seeded(h.engine) as conn:
        conn.execute(
            insert(waitlist_entry).values(
                entry_id=entry_id,
                email=email or unique_email("asker"),
                name="Asker Name",
                organisation="Asker Org",
                role_or_reason="curious",
                created_at=datetime.now(UTC),
                **values,
            )
        )
    return entry_id


# --- the role gate (B4, B9) ---------------------------------------------------


def test_every_ops_route_refuses_without_a_token_or_the_role(
    engine: Engine, tmp_path: Path
) -> None:
    """401 with no token, 403 with no row, 403 with a non-ops row, 200 with the role."""
    with _ops_app(tmp_path) as (client, settings, _stubber):
        routes = {
            (method, route.path)
            for route in _flatten_api_routes(client.app.routes)  # type: ignore[attr-defined]
            for method in route.methods or ()
            if route.path.startswith("/api/v1/ops")
        }
        assert routes == _OPS_ROUTES
        stranger = _principal(settings, tmp_path, "stranger")
        plain = _principal(settings, tmp_path, "plain")
        with seeded(engine) as conn:
            ops_enrol(conn, user_id=plain.user_id)
        ids = {"org_id": uuid.uuid4(), "entry_id": uuid.uuid4(), "cohort_id": uuid.uuid4()}
        filled = [(m, p.format(**ids)) for m, p in routes]
        for method, path in filled:
            assert client.request(method, path).status_code == 401, (method, path)
            assert client.request(method, path, headers=stranger.headers).status_code == 403
            assert client.request(method, path, headers=plain.headers).status_code == 403
        with engine.connect() as conn:
            assert (
                conn.execute(
                    select(func.count()).where(app_user.c.user_id == stranger.user_id)
                ).scalar_one()
                == 0
            )
        with seeded(engine) as conn:
            conn.execute(
                update(app_user).where(app_user.c.user_id == plain.user_id).values(is_ops=True)
            )
        for _method, path in (m for m in filled if m[0] == "GET"):
            assert client.get(path, headers=plain.headers).status_code == 200, path


# --- organisations (B4, B11) -------------------------------------------------


def test_create_organisation_writes_the_row_the_audit_and_the_log_line(ops: Harness) -> None:
    """One command call, one ``ops_action`` row, one ``ops.action`` line after the commit."""
    name = f"Created {uuid.uuid4()}"
    response, lines = _post(ops, "/api/v1/ops/organisations", {"name": name})
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["name"], body["people"], body["domains"]) == (name, 0, [])
    with ops.engine.connect() as conn:
        stored = conn.execute(
            select(organisation.c.name).where(organisation.c.org_id == uuid.UUID(body["org_id"]))
        ).scalar_one()
    assert stored == name
    _assert_audited(ops, lines, action="org.create", target=body["org_id"], outcome="ok")


def test_duplicate_organisation_is_refused_with_no_audit_row_and_no_log_line(
    ops: Harness,
) -> None:
    """A failing write leaves nothing behind: the transaction rolled back, nothing logged."""
    name = f"Twice {uuid.uuid4()}"
    assert _post(ops, "/api/v1/ops/organisations", {"name": name})[0].status_code == 201
    response, lines = _post(ops, "/api/v1/ops/organisations", {"name": name})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ops_refused"
    assert lines == []
    assert [row["action"] for row in _audit(ops)] == ["org.create"]


def test_organisations_list_counts_people_and_lists_domains(ops: Harness) -> None:
    """``people`` is the grouped ``app_user`` count; ``domains`` come from the domain table."""
    org_id = _seed_org(ops)
    _seed_person(ops, org_id=org_id)
    _seed_person(ops, org_id=org_id)
    with seeded(ops.engine) as conn:
        for domain in (f"b-{uuid.uuid4()}.test", f"a-{uuid.uuid4()}.test"):
            conn.execute(
                insert(organisation_domain).values(
                    domain=domain, org_id=org_id, created_at=datetime.now(UTC)
                )
            )
    response = ops.client.get("/api/v1/ops/organisations", headers=ops.actor.headers)
    assert response.status_code == 200
    rows = response.json()
    # Ordered by the database's collation, which is not Python's sort.
    with ops.engine.connect() as conn:
        expected = conn.execute(
            select(organisation.c.name).order_by(organisation.c.name)
        ).scalars().all()
    assert [row["name"] for row in rows] == expected
    mine = next(row for row in rows if row["org_id"] == str(org_id))
    assert mine["people"] == 2
    assert mine["domains"] == sorted(mine["domains"])
    assert len(mine["domains"]) == 2 and all(d.endswith(".test") for d in mine["domains"])


def test_quota_overrides_reach_the_public_me_route(ops: Harness, tmp_path: Path) -> None:
    """Organisation and person overrides written here change ``/me``'s limit; null clears."""
    org_id = _seed_org(ops)
    with tenancy_client(tmp_path / "api", count=1) as (api, [member]):
        with seeded(ops.engine) as conn:
            ops_enrol(conn, user_id=member.user_id, org_id=org_id)

        def limit() -> int | None:
            me = api.get("/api/v1/me", headers=member.headers).json()
            return None if me["task_quota"] is None else me["task_quota"]["limit"]

        assert limit() == 50
        response, lines = _post(
            ops,
            f"/api/v1/ops/organisations/{org_id}/quota",
            {"task_quota_per_year": 7, "runs_per_user": None},
        )
        assert response.status_code == 200, response.text
        assert response.json()["task_quota_per_year"] == 7
        _assert_audited(ops, lines, action="org.quota", outcome="ok", target=(
            f"{org_id}: tasks per year inherit → 7, simultaneous tasks inherit → inherit"))
        assert limit() == 7

        response, lines = _post(
            ops,
            "/api/v1/ops/people/quota",
            {"user_ids": [member.user_id], "task_quota_per_year": 3, "runs_per_user": 1},
        )
        assert response.status_code == 200, response.text
        assert response.json()["results"][0]["outcome"] == "ok"
        _assert_audited(ops, lines, action="person.quota", outcome="ok", target=(
            f"{member.user_id}: tasks per year inherit → 3, simultaneous tasks inherit → 1"))
        row = _user(ops, member.user_id)
        assert row is not None and (row["task_quota_per_year"], row["runs_per_user"]) == (3, 1)
        assert limit() == 3

        response, _ = _post(
            ops,
            "/api/v1/ops/people/quota",
            {"user_ids": [member.user_id], "task_quota_per_year": None, "runs_per_user": None},
        )
        assert response.status_code == 200
        assert limit() == 7
        response, _ = _post(
            ops,
            f"/api/v1/ops/organisations/{org_id}/quota",
            {"task_quota_per_year": None, "runs_per_user": None},
        )
        assert response.status_code == 200 and response.json()["task_quota_per_year"] is None
        assert limit() == 50
    assert (
        ops.client.post(
            f"/api/v1/ops/organisations/{uuid.uuid4()}/quota",
            json={"task_quota_per_year": 1, "runs_per_user": None},
            headers=ops.actor.headers,
        ).status_code
        == 404
    )


# --- people: list and create (B4) --------------------------------------------


def test_people_list_projects_columns_counts_tasks_and_filters_literally(ops: Harness) -> None:
    """Columns, ``tasks_this_year``, ``limits``; ``q`` is case-insensitive and ``%`` is literal."""
    org_id = _seed_org(ops)
    with seeded(ops.engine) as conn:
        org_name = conn.execute(
            select(organisation.c.name).where(organisation.c.org_id == org_id)
        ).scalar_one()
    invited = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    percent = _seed_person(ops, org_id=org_id, label="100%", invited_at=invited, is_admin=True)
    other = _seed_person(ops, org_id=None, label="plain")
    with seeded(ops.engine) as conn:
        make_task(conn, owner_user_id=percent, org_id=org_id)
        make_task(conn, owner_user_id=percent, org_id=org_id)

    def people(q: str | None = None) -> list[dict[str, Any]]:
        response = ops.client.get(
            "/api/v1/ops/people", params={"q": q} if q else None, headers=ops.actor.headers
        )
        assert response.status_code == 200, response.text
        listed: list[dict[str, Any]] = response.json()
        return listed

    everyone = people()
    with ops.engine.connect() as conn:
        # Postgres orders by its collation, so the expected order comes from it, not `sorted`.
        expected = list(
            conn.execute(
                select(app_user.c.user_id).order_by(app_user.c.display_name, app_user.c.user_id)
            ).scalars()
        )
    assert [p["user_id"] for p in everyone] == expected
    row = next(p for p in everyone if p["user_id"] == percent)
    assert row["email"].startswith("100%-") and row["email"].endswith("@example.test")
    assert row["organisation"] == {"org_id": str(org_id), "name": org_name}
    assert (row["is_admin"], row["is_ops"]) == (True, False)
    assert datetime.fromisoformat(row["invited_at"]) == invited
    assert row["tasks_this_year"] == 2
    assert row["last_task_at"] is not None
    admin = {"kind": "administrator", "name": None}
    assert row["limits"] == {"task_quota_per_year": None, "runs_per_user": None,
                             "task_quota_from": admin, "runs_from": admin}
    assert next(p for p in everyone if p["user_id"] == other)["limits"] == {
        "task_quota_per_year": 50,
        "runs_per_user": 3,
        "task_quota_from": {"kind": "default", "name": None},
        "runs_from": {"kind": "default", "name": None},
    }

    by_name = {p["user_id"] for p in people("100% " + percent.upper())}
    assert by_name == {percent}
    assert {p["user_id"] for p in people(org_name.upper())} == {percent}
    assert percent in {p["user_id"] for p in people(row["email"].upper())}
    literal = {p["user_id"] for p in people("%")}
    assert percent in literal and other not in literal


def test_create_person_invites_then_enrols_an_existing_account_without_a_send(
    ops: Harness,
) -> None:
    """A new address gets ``AdminCreateUser`` by email; a known unenrolled one is only enrolled."""
    org_id = _seed_org(ops)
    email, sub = unique_email("new"), f"new-{uuid.uuid4()}"
    expect_lookup(ops.stubber, email=email, sub=None)
    expect_create(ops.stubber, email=email, sub=sub)
    response, lines = _post(
        ops,
        "/api/v1/ops/people",
        {"email": email, "display_name": "New Person", "org_id": str(org_id)},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["invitation_sent"] is True
    assert body["person"]["user_id"] == sub
    assert body["person"]["organisation"]["org_id"] == str(org_id)
    assert body["person"]["invited_at"] is not None
    row = _user(ops, sub)
    assert row is not None and row["org_id"] == org_id and row["invited_at"] is not None
    _assert_audited(ops, lines, action="person.create", target=sub, outcome="invited")

    known = _seed_person(ops, org_id=None, label="known")
    known_row = _user(ops, known)
    assert known_row is not None
    expect_lookup(ops.stubber, email=known_row["email"], sub=known)
    expect_enabled(ops.stubber, sub=known)
    response, lines = _post(
        ops,
        "/api/v1/ops/people",
        {"email": known_row["email"], "display_name": "Known Person", "org_id": str(org_id)},
    )
    assert response.status_code == 201, response.text
    assert response.json()["invitation_sent"] is False
    moved = _user(ops, known)
    assert moved is not None and moved["org_id"] == org_id and moved["invited_at"] is None
    assert [row["outcome"] for row in _audit(ops)] == ["invited", "enrolled"]
    assert lines[0]["outcome"] == "enrolled"


def test_create_person_refuses_an_address_enrolled_elsewhere_and_an_unknown_org(
    ops: Harness,
) -> None:
    """409 ``enrolled_elsewhere`` naming the other organisation; 404 for an unknown org."""
    here, there = _seed_org(ops), _seed_org(ops)
    elsewhere = _seed_person(ops, org_id=there, label="elsewhere")
    row = _user(ops, elsewhere)
    assert row is not None
    expect_lookup(ops.stubber, email=row["email"], sub=elsewhere)
    expect_enabled(ops.stubber, sub=elsewhere)
    response, lines = _post(
        ops, "/api/v1/ops/people", {"email": row["email"], "display_name": "X", "org_id": str(here)}
    )
    assert response.status_code == 409, response.text
    error = response.json()["error"]
    with ops.engine.connect() as conn:
        there_name = conn.execute(
            select(organisation.c.name).where(organisation.c.org_id == there)
        ).scalar_one()
    assert error["code"] == "enrolled_elsewhere" and there_name in error["message"]
    assert lines == [] and _audit(ops) == []
    response, _ = _post(
        ops,
        "/api/v1/ops/people",
        {"email": unique_email("x"), "display_name": "X", "org_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404


# --- bulk actions (B4, B6, B11) ----------------------------------------------


def test_bulk_enrol_continues_past_a_real_sql_failure_and_audits_every_subject(
    ops: Harness,
) -> None:
    """The middle subject's savepoint is rolled back by Postgres; the other two commit."""
    dest = _seed_org(ops)
    first, middle, last = (_seed_person(ops, org_id=None, label=f"bulk{i}") for i in range(3))
    with ops.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(
            text(
                "CREATE FUNCTION pa_test_refuse_middle() RETURNS trigger LANGUAGE plpgsql AS $$ "
                f"BEGIN IF NEW.user_id = '{middle}' THEN "
                "RAISE EXCEPTION 'refused by test trigger'; "
                "END IF; RETURN NEW; END $$"
            )
        )
        conn.execute(
            text(
                "CREATE TRIGGER trg_pa_test_refuse_middle BEFORE UPDATE ON app_user "
                "FOR EACH ROW EXECUTE FUNCTION pa_test_refuse_middle()"
            )
        )
    try:
        response, lines = _post(
            ops,
            "/api/v1/ops/people/enrol",
            {"user_ids": [first, middle, last], "org_id": str(dest)},
        )
    finally:
        with ops.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text("DROP TRIGGER IF EXISTS trg_pa_test_refuse_middle ON app_user"))
            conn.execute(text("DROP FUNCTION IF EXISTS pa_test_refuse_middle()"))
    assert response.status_code == 200, response.text
    results = response.json()["results"]
    assert [(r["user_id"], r["outcome"]) for r in results] == [
        (first, "ok"),
        (middle, "failed"),
        (last, "ok"),
    ]
    # A database error never reaches the browser verbatim: the row names its audit record.
    assert "refused by test trigger" not in results[1]["message"]
    assert results[1]["message"] == f"failed; see action {results[1]['action_id']}"
    assert all(r["action_id"] for r in results)
    for user_id, org in ((first, dest), (middle, None), (last, dest)):
        row = _user(ops, user_id)
        assert row is not None and row["org_id"] == org, user_id
    audit = _audit(ops)
    assert [(r["action"], r["target"], r["outcome"]) for r in audit] == [
        ("person.move", first, "ok"),
        ("person.move", middle, "failed"),
        ("person.move", last, "ok"),
    ]
    assert [str(r["action_id"]) for r in audit] == [r["action_id"] for r in results]
    assert [(line["target"], line["outcome"]) for line in lines] == [
        (first, "ok"),
        (middle, "failed"),
        (last, "ok"),
    ]


def test_bulk_de_enrol_clears_the_row_and_fails_an_unknown_subject(ops: Harness) -> None:
    """De-enrol clears organisation and both roles; an unknown subject is a ``failed`` row."""
    org_id = _seed_org(ops)
    admin = _seed_person(ops, org_id=org_id, label="admin", is_admin=True)
    ghost = f"ghost-{uuid.uuid4()}"
    response, lines = _post(ops, "/api/v1/ops/people/de-enrol", {"user_ids": [admin, ghost]})
    assert response.status_code == 200, response.text
    results = response.json()["results"]
    assert [r["outcome"] for r in results] == ["ok", "failed"]
    assert results[1]["message"] == f"no user {ghost}"
    row = _user(ops, admin)
    assert row is not None and row["org_id"] is None and row["is_admin"] is False
    assert _user(ops, ghost) is None
    assert [(r["action"], r["target"], r["outcome"]) for r in _audit(ops)] == [
        ("person.de_enrol", admin, "ok"),
        ("person.de_enrol", ghost, "failed"),
    ]
    assert len(lines) == 2


def test_bulk_deactivate_locks_the_account_out_and_keeps_the_organisation(ops: Harness) -> None:
    """Cognito disable and sign-out (Stubber-validated), then the mark (owner ruling B)."""
    org_id = _seed_org(ops)
    leaver = _seed_person(ops, org_id=org_id, label="leaver")
    with seeded(ops.engine) as conn:
        task_id = make_task(conn, owner_user_id=leaver, org_id=org_id)
        conn.execute(update(task).where(task.c.task_id == task_id).values(is_public=True))
    expect_sub_lookup(ops.stubber, sub=leaver)
    expect_lock_out(ops.stubber, sub=leaver)
    response, lines = _post(ops, "/api/v1/ops/people/deactivate", {"user_ids": [leaver]})
    assert response.status_code == 200, response.text
    assert response.json()["results"][0]["outcome"] == "ok"
    row = _user(ops, leaver)
    assert row is not None and row["org_id"] == org_id and row["deactivated_at"] is not None
    with ops.engine.connect() as conn:
        assert conn.execute(
            select(task.c.is_public, task.c.org_id).where(task.c.task_id == task_id)
        ).one() == (False, org_id)
    _assert_audited(ops, lines, action="person.deactivate", target=leaver, outcome="ok")
    listed = ops.client.get("/api/v1/ops/people", headers=ops.actor.headers).json()
    assert next(p for p in listed if p["user_id"] == leaver)["deactivated_at"] is not None


def test_bulk_reactivate_turns_the_login_back_on(ops: Harness) -> None:
    org_id = _seed_org(ops)
    person = _seed_person(ops, org_id=org_id, label="returner")
    with seeded(ops.engine) as conn:
        conn.execute(
            update(app_user).where(app_user.c.user_id == person)
            .values(deactivated_at=datetime.now(UTC))
        )
    expect_sub_lookup(ops.stubber, sub=person)
    expect_enabled(ops.stubber, sub=person, enabled=False)
    ops.stubber.add_response("admin_enable_user", {}, {"UserPoolId": POOL_ID, "Username": person})
    response, lines = _post(ops, "/api/v1/ops/people/reactivate", {"user_ids": [person]})
    assert response.status_code == 200, response.text
    row = _user(ops, person)
    assert row is not None and row["deactivated_at"] is None
    _assert_audited(ops, lines, action="person.reactivate", target=person, outcome="ok")


def test_delete_organisation_refuses_a_used_one_and_deletes_an_empty_one(ops: Harness) -> None:
    used = _seed_org(ops)
    _seed_person(ops, org_id=used, label="member")
    refused = ops.client.delete(f"/api/v1/ops/organisations/{used}", headers=ops.actor.headers)
    assert refused.status_code == 409
    assert "still has 1 people" in refused.text
    empty = _seed_org(ops)
    deleted = ops.client.delete(f"/api/v1/ops/organisations/{empty}", headers=ops.actor.headers)
    assert deleted.status_code == 204
    missing = ops.client.delete(f"/api/v1/ops/organisations/{empty}", headers=ops.actor.headers)
    assert missing.status_code == 404


def test_resend_honours_the_cooldown_and_resends_after_it(ops: Harness) -> None:
    """10 minutes ago → 429; 2 hours ago → ``RESEND`` sent; a mixed pair → ok and too_soon."""
    org_id = _seed_org(ops)
    now = datetime.now(UTC)
    cooling = _seed_person(
        ops, org_id=org_id, label="cooling", invited_at=now - timedelta(minutes=10)
    )
    response, lines = _post(ops, "/api/v1/ops/people/resend", {"user_ids": [cooling]})
    assert response.status_code == 429, response.text
    assert response.json()["error"]["code"] == "resend_cooldown"
    assert lines == [] and _audit(ops) == []

    ready = _seed_person(ops, org_id=org_id, label="ready", invited_at=now - timedelta(hours=2))
    expect_sub_lookup(ops.stubber, sub=ready, status="FORCE_CHANGE_PASSWORD")
    expect_resend(ops.stubber, username=ready)
    response, lines = _post(ops, "/api/v1/ops/people/resend", {"user_ids": [ready]})
    assert response.status_code == 200, response.text
    assert response.json()["results"][0]["outcome"] == "ok"
    row = _user(ops, ready)
    assert row is not None and row["invited_at"] > now - timedelta(minutes=1)
    _assert_audited(ops, lines, action="person.resend", target=ready, outcome="ok")

    # Now `ready` is cooling down and `cooling` is still cooling; make a second ready person.
    ready_too = _seed_person(
        ops, org_id=org_id, label="ready2", invited_at=now - timedelta(hours=3)
    )
    expect_sub_lookup(ops.stubber, sub=ready_too, status="FORCE_CHANGE_PASSWORD")
    expect_resend(ops.stubber, username=ready_too)
    response, lines = _post(ops, "/api/v1/ops/people/resend", {"user_ids": [cooling, ready_too]})
    assert response.status_code == 200, response.text
    results = response.json()["results"]
    assert [(r["user_id"], r["outcome"], r["action_id"] is None) for r in results] == [
        (cooling, "too_soon", True),
        (ready_too, "ok", False),
    ]
    assert [r["target"] for r in _audit(ops)] == [ready, ready_too]
    assert len(lines) == 1 and lines[0]["target"] == ready_too


# --- requests (C5) ------------------------------------------------------------


def test_requests_list_shows_the_three_states_and_the_self_signup_block(ops: Harness) -> None:
    """``waiting``, ``invited`` and ``check`` (with the other organisation's name)."""
    other_org = _seed_org(ops)
    waiting = _seed_request(ops)
    invited = _seed_request(ops, account_user_id="someone", account_created_at=datetime.now(UTC))
    elsewhere = _seed_person(ops, org_id=other_org, label="elsewhere")
    elsewhere_row = _user(ops, elsewhere)
    assert elsewhere_row is not None
    check = _seed_request(ops, email=elsewhere_row["email"])
    with seeded(ops.engine) as conn:
        domain = f"d-{uuid.uuid4()}.test"
        conn.execute(
            insert(organisation_domain).values(
                domain=domain, org_id=other_org, created_at=datetime.now(UTC)
            )
        )
        other_name = conn.execute(
            select(organisation.c.name).where(organisation.c.org_id == other_org)
        ).scalar_one()

    def listing() -> dict[str, Any]:
        response = ops.client.get("/api/v1/ops/requests", headers=ops.actor.headers)
        assert response.status_code == 200, response.text
        body: dict[str, Any] = response.json()
        return body

    before = listing()
    with seeded(ops.engine) as conn:
        for target, outcome, at in (
            (str(check), "enrolled_elsewhere", datetime.now(UTC)),
            (str(uuid.uuid4()), "invited", datetime.now(UTC)),
            (str(uuid.uuid4()), "invited", datetime.now(UTC) - timedelta(hours=2)),
        ):
            conn.execute(
                insert(ops_action).values(
                    action_id=uuid.uuid4(),
                    at=at,
                    actor_user_id="sweep",
                    action="invite",
                    target=target,
                    outcome=outcome,
                )
            )
    after = listing()
    items = {uuid.UUID(item["entry_id"]): item for item in after["items"]}
    assert items[waiting]["status"] == "waiting" and items[waiting]["note"] is None
    # An invited request has left the waitlist: the person is on People now.
    assert invited not in items
    assert (items[check]["status"], items[check]["note"]) == ("check", other_name)
    created = [item["created_at"] for item in after["items"]]
    assert created == sorted(created)
    signup = after["self_signup"]
    assert signup["enabled"] is False and signup["max_per_hour"] == 100
    assert domain in signup["domains"]
    assert signup["sent_this_hour"] - before["self_signup"]["sent_this_hour"] == 1


def test_approve_stamps_the_row_and_refuses_a_second_approval(ops: Harness) -> None:
    """Approve invites and stamps; a stamped row is 409; a known account is ``enrolled``."""
    org_id = _seed_org(ops)
    email, sub = unique_email("asker"), f"asker-{uuid.uuid4()}"
    entry_id = _seed_request(ops, email=email)
    expect_lookup(ops.stubber, email=email, sub=None)
    expect_create(ops.stubber, email=email, sub=sub)
    response, lines = _post(
        ops, f"/api/v1/ops/requests/{entry_id}/approve", {"org_id": str(org_id)}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["status"], body["account_user_id"]) == ("invited", sub)
    assert body["account_created_at"] is not None
    with ops.engine.connect() as conn:
        stamped = (
            conn.execute(select(waitlist_entry).where(waitlist_entry.c.entry_id == entry_id))
            .mappings()
            .one()
        )
    assert stamped["account_user_id"] == sub and stamped["account_created_at"] is not None
    row = _user(ops, sub)
    assert row is not None and row["org_id"] == org_id and row["display_name"] == "Asker Name"
    _assert_audited(ops, lines, action="request.approve", target=str(entry_id), outcome="invited")

    response, lines = _post(
        ops, f"/api/v1/ops/requests/{entry_id}/approve", {"org_id": str(org_id)}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ops_refused"
    assert lines == [] and len(_audit(ops)) == 1

    known = _seed_person(ops, org_id=None, label="known")
    known_row = _user(ops, known)
    assert known_row is not None
    second = _seed_request(ops, email=known_row["email"])
    expect_lookup(ops.stubber, email=known_row["email"], sub=known)
    expect_enabled(ops.stubber, sub=known)
    response, lines = _post(ops, f"/api/v1/ops/requests/{second}/approve", {"org_id": str(org_id)})
    assert response.status_code == 200, response.text
    assert response.json()["account_user_id"] == known
    assert [r["outcome"] for r in _audit(ops)] == ["invited", "enrolled"]


def test_approve_of_an_unknown_request_is_not_found(ops: Harness) -> None:
    """A missing waitlist row answers 404, like reject and delete, and writes nothing."""
    org_id = _seed_org(ops)
    response, lines = _post(
        ops, f"/api/v1/ops/requests/{uuid.uuid4()}/approve", {"org_id": str(org_id)}
    )
    assert response.status_code == 404, response.text
    assert lines == []


def test_approve_refuses_an_address_enrolled_elsewhere(ops: Harness) -> None:
    """409 ``enrolled_elsewhere``; the row stays unstamped and nothing is audited."""
    here, there = _seed_org(ops), _seed_org(ops)
    elsewhere = _seed_person(ops, org_id=there, label="elsewhere")
    row = _user(ops, elsewhere)
    assert row is not None
    entry_id = _seed_request(ops, email=row["email"])
    expect_lookup(ops.stubber, email=row["email"], sub=elsewhere)
    expect_enabled(ops.stubber, sub=elsewhere)
    response, lines = _post(ops, f"/api/v1/ops/requests/{entry_id}/approve", {"org_id": str(here)})
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "enrolled_elsewhere"
    with ops.engine.connect() as conn:
        assert (
            conn.execute(
                select(waitlist_entry.c.account_created_at).where(
                    waitlist_entry.c.entry_id == entry_id
                )
            ).scalar_one()
            is None
        )
    assert lines == [] and _audit(ops) == []


# --- rows (B4) ----------------------------------------------------------------


def test_an_operator_cannot_deactivate_or_de_enrol_themselves(ops: Harness) -> None:
    """"Select everyone shown" includes the caller; the row fails and the others proceed."""
    org_id = _seed_org(ops)
    other = _seed_person(ops, org_id=org_id, label="other")
    response, lines = _post(
        ops, "/api/v1/ops/people/de-enrol", {"user_ids": [ops.actor.user_id, other]}
    )
    assert response.status_code == 200, response.text
    results = response.json()["results"]
    assert [r["outcome"] for r in results] == ["failed", "ok"]
    assert "your own account" in results[0]["message"]
    me = _user(ops, ops.actor.user_id)
    assert me is not None and me["is_ops"] is True
    assert [row["outcome"] for row in _audit(ops)] == ["failed", "ok"]
    assert len(lines) == 2


def test_requests_page_survives_two_rows_sharing_an_address(ops: Harness) -> None:
    """``app_user.email`` is not unique; a Check row's note takes the first match, never a 500."""
    org_id = _seed_org(ops)
    email = unique_email("twice")
    _seed_person(ops, org_id=org_id, label="first", email=email)
    _seed_person(ops, org_id=org_id, label="second", email=email)
    entry_id = uuid.uuid4()
    with seeded(ops.engine) as conn:
        conn.execute(
            insert(waitlist_entry).values(
                entry_id=entry_id, email=email, name="Twice", role_or_reason="r",
                created_at=datetime.now(UTC),
            )
        )
        conn.execute(
            insert(ops_action).values(
                action_id=uuid.uuid4(), at=datetime.now(UTC), actor_user_id="sweep",
                action="invite", target=str(entry_id), outcome="enrolled_elsewhere",
            )
        )
    response = ops.client.get("/api/v1/ops/requests", headers=ops.actor.headers)
    assert response.status_code == 200, response.text
    item = next(i for i in response.json()["items"] if i["entry_id"] == str(entry_id))
    assert item["status"] == "check" and item["note"]


def test_a_refused_sweep_row_shows_as_check(ops: Harness) -> None:
    """The sweep's terminal ``refused`` outcome is a Check for an operator, like elsewhere."""
    entry_id = uuid.uuid4()
    with seeded(ops.engine) as conn:
        conn.execute(
            insert(waitlist_entry).values(
                entry_id=entry_id, email=unique_email("refused"), name="R", role_or_reason="r",
                created_at=datetime.now(UTC),
            )
        )
        conn.execute(
            insert(ops_action).values(
                action_id=uuid.uuid4(), at=datetime.now(UTC), actor_user_id="sweep",
                action="invite", target=str(entry_id), outcome="refused",
            )
        )
    response = ops.client.get("/api/v1/ops/requests", headers=ops.actor.headers)
    item = next(i for i in response.json()["items"] if i["entry_id"] == str(entry_id))
    assert item["status"] == "check" and item["note"] is None


def test_create_person_lower_cases_the_address_and_maps_a_cognito_refusal(ops: Harness) -> None:
    """Mixed case reaches Cognito lower-cased; a Cognito error is a 409, not a 500."""
    from botocore.stub import ANY

    org_id = _seed_org(ops)
    email = unique_email("Mixed").replace("mixed", "Mixed")
    assert email != email.lower()
    expect_lookup(ops.stubber, email=email.lower(), sub=None)
    ops.stubber.add_client_error(
        "admin_create_user",
        service_error_code="InvalidParameterException",
        expected_params={
            "UserPoolId": POOL_ID,
            "Username": email.lower(),
            "UserAttributes": ANY,
            "DesiredDeliveryMediums": ["EMAIL"],
        },
    )
    response, lines = _post(
        ops,
        "/api/v1/ops/people",
        {"email": email, "display_name": "Mixed Case", "org_id": str(org_id)},
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "ops_refused"
    assert "InvalidParameterException" in response.json()["error"]["message"]
    assert email.lower() not in response.json()["error"]["message"]
    assert lines == [] and _audit(ops) == []


def test_quota_bodies_must_name_both_fields(ops: Harness) -> None:
    """Leaving a field out is a validation error, never a silent clear (review stack)."""
    org_id = _seed_org(ops)
    response = ops.client.post(
        f"/api/v1/ops/organisations/{org_id}/quota",
        json={"task_quota_per_year": 5},
        headers=ops.actor.headers,
    )
    assert response.status_code == 422, response.text
    person = _seed_person(ops, org_id=org_id, label="q")
    response = ops.client.post(
        "/api/v1/ops/people/quota",
        json={"user_ids": [person], "runs_per_user": 2},
        headers=ops.actor.headers,
    )
    assert response.status_code == 422, response.text


# --- cohorts (owner, 2026-11-18) ---------------------------------------------


def _cohort_body(name: str, **values: Any) -> dict[str, Any]:
    """A full cohort form body."""
    return {"name": name, "description": None, "starts_on": None, "ends_on": None,
            "links": [], **values}


def test_cohort_create_edit_and_delete_are_audited(ops: Harness) -> None:
    """Create, replace and delete each write one audit row; the name stays unique."""
    name = f"Pilot {uuid.uuid4()}"
    response, lines = _post(ops, "/api/v1/ops/cohorts", _cohort_body(
        name, description="DHSC V3 pilot", starts_on="2026-12-01", ends_on="2027-01-31",
        links=["https://example.org/plan"],
    ))
    assert response.status_code == 201, response.text
    created = response.json()
    cohort_id = created["cohort_id"]
    assert (created["people"], created["links"], created["ends_on"]) == (
        0, ["https://example.org/plan"], "2027-01-31")
    _assert_audited(ops, lines, action="cohort.create", target=cohort_id, outcome="ok")

    response, _ = _post(ops, "/api/v1/ops/cohorts", _cohort_body(name))
    assert response.status_code == 409 and response.json()["error"]["code"] == "ops_refused"

    response, lines = _post(ops, f"/api/v1/ops/cohorts/{cohort_id}", _cohort_body(f"{name} b"))
    assert response.status_code == 200, response.text
    assert (response.json()["name"], response.json()["links"]) == (f"{name} b", [])
    _assert_audited(ops, lines, action="cohort.update", target=cohort_id, outcome="ok")

    listed = ops.client.get("/api/v1/ops/cohorts", headers=ops.actor.headers).json()
    assert cohort_id in [row["cohort_id"] for row in listed]

    with capture_logs() as captured:
        response = ops.client.delete(f"/api/v1/ops/cohorts/{cohort_id}", headers=ops.actor.headers)
    assert response.status_code == 204
    _assert_audited(ops, _ops_lines(captured), action="cohort.delete", target=cohort_id,
                    outcome="ok")
    assert ops.client.delete(
        f"/api/v1/ops/cohorts/{cohort_id}", headers=ops.actor.headers
    ).status_code == 404


def test_cohort_form_refuses_bad_links_and_reversed_dates(ops: Harness) -> None:
    """A link must be a web address; the end may not come before the start."""
    for body in (
        _cohort_body(f"Bad {uuid.uuid4()}", links=["javascript:alert(1)"]),
        _cohort_body(f"Bad {uuid.uuid4()}", starts_on="2027-02-01", ends_on="2027-01-01"),
    ):
        response, lines = _post(ops, "/api/v1/ops/cohorts", body)
        assert response.status_code == 409 and lines == [], response.text
    response, _ = _post(ops, "/api/v1/ops/cohorts", _cohort_body("x", links=["a"] * 11))
    assert response.status_code == 422


def test_bulk_cohort_membership_shows_on_people_and_is_idempotent(ops: Harness) -> None:
    """Add twice changes once; the people list names the cohort; remove takes it away."""
    org_id = _seed_org(ops)
    first = _seed_person(ops, org_id=org_id, label="cohort-a")
    second = _seed_person(ops, org_id=None, label="cohort-b")
    name = f"Panel {uuid.uuid4()}"
    cohort_id = _post(ops, "/api/v1/ops/cohorts", _cohort_body(name))[0].json()["cohort_id"]

    response, lines = _post(ops, "/api/v1/ops/people/cohort-add",
                            {"user_ids": [first, second, "no-such-person"],
                             "cohort_id": cohort_id})
    assert [r["outcome"] for r in response.json()["results"]] == ["ok", "ok", "failed"]
    assert "nothing changed" not in response.json()["results"][0]["message"]
    assert len(lines) == 3
    # Each audit row names the cohort, the failed one too.
    assert [line["target"] for line in lines] == [
        f"{who}/cohort/{cohort_id}" for who in (first, second, "no-such-person")]
    again = _post(ops, "/api/v1/ops/people/cohort-add",
                  {"user_ids": [first], "cohort_id": cohort_id})[0].json()["results"][0]
    assert again["outcome"] == "ok" and "nothing changed" in again["message"]

    people = {p["user_id"]: p for p in ops.client.get(
        "/api/v1/ops/people", headers=ops.actor.headers).json()}
    assert [c["name"] for c in people[first]["cohorts"]] == [name]
    assert [c["name"] for c in people[second]["cohorts"]] == [name]
    counted = [c for c in ops.client.get("/api/v1/ops/cohorts", headers=ops.actor.headers).json()
               if c["cohort_id"] == cohort_id]
    assert counted[0]["people"] == 2

    response, _ = _post(ops, "/api/v1/ops/people/cohort-remove",
                        {"user_ids": [first], "cohort_id": cohort_id})
    assert response.json()["results"][0]["outcome"] == "ok"
    people = {p["user_id"]: p for p in ops.client.get(
        "/api/v1/ops/people", headers=ops.actor.headers).json()}
    assert people[first]["cohorts"] == []

    response, lines = _post(ops, "/api/v1/ops/people/cohort-add",
                            {"user_ids": [first], "cohort_id": str(uuid.uuid4())})
    assert response.status_code == 404 and lines == []


def test_cohort_quota_is_audited_and_reaches_its_members_limits(ops: Harness) -> None:
    """A cohort's override applies to a member with none of their own."""
    member = _seed_person(ops, org_id=None, label="cohort-quota")
    cohort_id = _post(ops, "/api/v1/ops/cohorts",
                      _cohort_body(f"Quota {uuid.uuid4()}"))[0].json()["cohort_id"]
    _post(ops, "/api/v1/ops/people/cohort-add", {"user_ids": [member], "cohort_id": cohort_id})
    response, lines = _post(ops, f"/api/v1/ops/cohorts/{cohort_id}/quota",
                            {"task_quota_per_year": 120, "runs_per_user": None})
    assert response.status_code == 200, response.text
    assert (response.json()["task_quota_per_year"], response.json()["runs_per_user"]) == (120, None)
    _assert_audited(ops, lines, action="cohort.quota", outcome="ok", target=(
        f"{cohort_id}: tasks per year inherit → 120, simultaneous tasks inherit → inherit"))
    people = {p["user_id"]: p for p in ops.client.get(
        "/api/v1/ops/people", headers=ops.actor.headers).json()}
    assert people[member]["limits"]["task_quota_per_year"] == 120
    response, _ = _post(ops, f"/api/v1/ops/cohorts/{uuid.uuid4()}/quota",
                        {"task_quota_per_year": 1, "runs_per_user": 1})
    assert response.status_code == 404


def test_reject_takes_a_request_off_the_waitlist_and_a_second_reject_is_refused(
    ops: Harness,
) -> None:
    """Reject writes one audit row and no email; the row leaves the list; rejecting again is 409."""
    entry_id = _seed_request(ops)
    with capture_logs() as captured:
        response = ops.client.post(
            f"/api/v1/ops/requests/{entry_id}/reject", headers=ops.actor.headers
        )
    assert response.status_code == 204, response.text
    _assert_audited(ops, _ops_lines(captured), action="request.reject", target=str(entry_id),
                    outcome="ok")
    listed = ops.client.get("/api/v1/ops/requests", headers=ops.actor.headers).json()["items"]
    assert str(entry_id) not in [item["entry_id"] for item in listed]
    with_rejected = ops.client.get(
        "/api/v1/ops/requests?rejected=true", headers=ops.actor.headers
    ).json()["items"]
    record = next(item for item in with_rejected if item["entry_id"] == str(entry_id))
    assert record["status"] == "rejected" and record["rejected_at"] is not None
    again = ops.client.post(f"/api/v1/ops/requests/{entry_id}/reject", headers=ops.actor.headers)
    assert again.status_code == 409
    ops.stubber.assert_no_pending_responses()


def test_a_rejected_request_can_be_deleted_and_only_a_rejected_one(ops: Harness) -> None:
    """Delete refuses a waiting request, removes a rejected one, and is audited."""
    entry_id = _seed_request(ops)
    refused = ops.client.delete(f"/api/v1/ops/requests/{entry_id}", headers=ops.actor.headers)
    assert refused.status_code == 409
    ops.client.post(f"/api/v1/ops/requests/{entry_id}/reject", headers=ops.actor.headers)
    with capture_logs() as captured:
        response = ops.client.delete(f"/api/v1/ops/requests/{entry_id}", headers=ops.actor.headers)
    assert response.status_code == 204, response.text
    _assert_audited(ops, _ops_lines(captured), action="request.delete", target=str(entry_id),
                    outcome="ok")
    with ops.engine.connect() as conn:
        assert conn.execute(
            select(func.count()).where(waitlist_entry.c.entry_id == entry_id)
        ).scalar_one() == 0
    assert ops.client.delete(
        f"/api/v1/ops/requests/{entry_id}", headers=ops.actor.headers
    ).status_code == 404


def test_approving_a_rejected_request_reverses_the_decision(ops: Harness) -> None:
    """A rejected request can still be approved; the rejection mark is cleared."""
    org_id = _seed_org(ops)
    email, sub = unique_email("second-thoughts"), f"second-{uuid.uuid4()}"
    entry_id = _seed_request(ops, email=email)
    ops.client.post(f"/api/v1/ops/requests/{entry_id}/reject", headers=ops.actor.headers)
    expect_lookup(ops.stubber, email=email, sub=None)
    expect_create(ops.stubber, email=email, sub=sub)
    response, _ = _post(ops, f"/api/v1/ops/requests/{entry_id}/approve", {"org_id": str(org_id)})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "invited"
    with ops.engine.connect() as conn:
        assert conn.execute(
            select(waitlist_entry.c.rejected_at).where(waitlist_entry.c.entry_id == entry_id)
        ).scalar_one() is None


# --- cohorts at Add person and Approve -------------------------------------


def _new_cohort(h: Harness) -> str:
    """Create one cohort through the route and return its id."""
    response, _ = _post(h, "/api/v1/ops/cohorts", _cohort_body(f"Group {uuid.uuid4()}"))
    return str(response.json()["cohort_id"])


def _members(h: Harness, user_id: str) -> set[str]:
    """The cohort ids one person is in."""
    with h.engine.connect() as conn:
        return {str(c) for c in conn.execute(
            select(cohort_member.c.cohort_id).where(cohort_member.c.user_id == user_id)
        ).scalars()}


def _cohort_adds(h: Harness) -> list[str]:
    """The targets of this caller's ``cohort.add`` audit rows, oldest first."""
    return [row["target"] for row in _audit(h) if row["action"] == "cohort.add"]


def test_create_person_joins_the_chosen_cohorts_and_audits_each(ops: Harness) -> None:
    org_id, first, second = _seed_org(ops), _new_cohort(ops), _new_cohort(ops)
    email, sub = unique_email("grouped"), f"grouped-{uuid.uuid4()}"
    expect_lookup(ops.stubber, email=email, sub=None)
    expect_create(ops.stubber, email=email, sub=sub)
    response, lines = _post(ops, "/api/v1/ops/people", {
        "email": email, "display_name": "Grouped", "org_id": str(org_id),
        "cohort_ids": [first, second]})
    assert response.status_code == 201, response.text
    assert {c["cohort_id"] for c in response.json()["person"]["cohorts"]} == {first, second}
    assert _members(ops, sub) == {first, second}
    assert _cohort_adds(ops) == [f"{sub}/cohort/{first}", f"{sub}/cohort/{second}"]
    assert [line["action"] for line in lines] == ["person.create", "cohort.add", "cohort.add"]


def test_an_unknown_cohort_is_not_found_before_any_cognito_call(ops: Harness) -> None:
    """Nothing is queued on the Cognito double, so any call would fail the request."""
    org_id, known = _seed_org(ops), _new_cohort(ops)
    response, lines = _post(ops, "/api/v1/ops/people", {
        "email": unique_email("lost"), "display_name": "Lost", "org_id": str(org_id),
        "cohort_ids": [known, str(uuid.uuid4())]})
    assert response.status_code == 404, response.text
    assert lines == [] and _cohort_adds(ops) == []


@pytest.mark.parametrize(("count", "repeat"), [(11, False), (2, True)])
def test_cohort_ids_refuse_more_than_ten_or_a_repeat(
    ops: Harness, count: int, repeat: bool
) -> None:
    ids = [str(uuid.uuid4()) for _ in range(count)]
    if repeat:
        ids[1] = ids[0]
    for path, body in (
        ("/api/v1/ops/people", {"email": unique_email("x"), "display_name": "X"}),
        (f"/api/v1/ops/requests/{uuid.uuid4()}/approve", {}),
    ):
        response, _ = _post(ops, path, {**body, "org_id": str(uuid.uuid4()), "cohort_ids": ids})
        assert response.status_code == 422, (path, response.text)


def test_an_existing_membership_writes_no_audit_row(ops: Harness) -> None:
    org_id, held, new = _seed_org(ops), _new_cohort(ops), _new_cohort(ops)
    known = _seed_person(ops, org_id=org_id, label="member")
    _post(ops, "/api/v1/ops/people/cohort-add", {"user_ids": [known], "cohort_id": held})
    row = _user(ops, known)
    assert row is not None
    expect_lookup(ops.stubber, email=row["email"], sub=known)
    expect_enabled(ops.stubber, sub=known)
    response, _ = _post(ops, "/api/v1/ops/people", {
        "email": row["email"], "display_name": "Member", "org_id": str(org_id),
        "cohort_ids": [held, new]})
    assert response.status_code == 201, response.text
    assert _members(ops, known) == {held, new}
    # The first row is the bulk add above; this call wrote only the new membership.
    assert _cohort_adds(ops) == [f"{known}/cohort/{held}", f"{known}/cohort/{new}"]


def test_a_refused_create_leaves_no_membership(ops: Harness) -> None:
    here, there, group = _seed_org(ops), _seed_org(ops), _new_cohort(ops)
    elsewhere = _seed_person(ops, org_id=there, label="elsewhere")
    row = _user(ops, elsewhere)
    assert row is not None
    expect_lookup(ops.stubber, email=row["email"], sub=elsewhere)
    expect_enabled(ops.stubber, sub=elsewhere)
    response, _ = _post(ops, "/api/v1/ops/people", {
        "email": row["email"], "display_name": "X", "org_id": str(here), "cohort_ids": [group]})
    assert response.status_code == 409, response.text
    assert _members(ops, elsewhere) == set() and _cohort_adds(ops) == []


def test_a_failed_cohort_write_undoes_the_enrolment_and_a_retry_sends_no_second_invitation(
    ops: Harness,
) -> None:
    org_id, group = _seed_org(ops), _new_cohort(ops)
    email, sub = unique_email("retry"), f"retry-{uuid.uuid4()}"
    body = {"email": email, "display_name": "Retry", "org_id": str(org_id),
            "cohort_ids": [group]}
    with ops.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text(
            "CREATE FUNCTION pa_test_refuse_member() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN RAISE EXCEPTION 'refused by test trigger'; END $$"))
        conn.execute(text(
            "CREATE TRIGGER trg_pa_test_refuse_member BEFORE INSERT ON cohort_member "
            "FOR EACH ROW EXECUTE FUNCTION pa_test_refuse_member()"))
    try:
        expect_lookup(ops.stubber, email=email, sub=None)
        expect_create(ops.stubber, email=email, sub=sub)
        failed, lines = _post(ops, "/api/v1/ops/people", body)
    finally:
        with ops.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text("DROP TRIGGER IF EXISTS trg_pa_test_refuse_member ON cohort_member"))
            conn.execute(text("DROP FUNCTION IF EXISTS pa_test_refuse_member()"))
    assert failed.status_code == 500
    assert _user(ops, sub) is None and lines == []
    assert [row["action"] for row in _audit(ops)] == ["cohort.create"]
    # Cognito kept the account; the second call finds it and creates nothing.
    expect_lookup(ops.stubber, email=email, sub=sub)
    expect_enabled(ops.stubber, sub=sub)
    retried, _ = _post(ops, "/api/v1/ops/people", body)
    assert retried.status_code == 201, retried.text
    assert retried.json()["invitation_sent"] is False
    assert _members(ops, sub) == {group}


def test_approve_joins_the_chosen_cohorts(ops: Harness) -> None:
    org_id, group = _seed_org(ops), _new_cohort(ops)
    email, sub = unique_email("approved"), f"approved-{uuid.uuid4()}"
    entry_id = _seed_request(ops, email=email)
    expect_lookup(ops.stubber, email=email, sub=None)
    expect_create(ops.stubber, email=email, sub=sub)
    response, _ = _post(ops, f"/api/v1/ops/requests/{entry_id}/approve",
                        {"org_id": str(org_id), "cohort_ids": [group]})
    assert response.status_code == 200, response.text
    assert _members(ops, sub) == {group}
    assert _cohort_adds(ops) == [f"{sub}/cohort/{group}"]


def test_adding_the_same_person_again_sends_no_second_invitation(ops: Harness) -> None:
    """A file run twice: the second create finds the account in the organisation."""
    org_id = _seed_org(ops)
    email, sub = unique_email("twice"), f"twice-{uuid.uuid4()}"
    body = {"email": email, "display_name": "Twice", "org_id": str(org_id)}
    expect_lookup(ops.stubber, email=email, sub=None)
    expect_create(ops.stubber, email=email, sub=sub)
    assert _post(ops, "/api/v1/ops/people", body)[0].json()["invitation_sent"] is True
    expect_lookup(ops.stubber, email=email, sub=sub)
    expect_enabled(ops.stubber, sub=sub)
    again, _ = _post(ops, "/api/v1/ops/people", body)
    assert again.status_code == 201, again.text
    assert again.json()["invitation_sent"] is False


# --- the people file check ---------------------------------------------------


def _check_file(h: Harness, text: str) -> dict[str, Any]:
    """POST one file to the check route and return its answer."""
    response, _ = _post(h, "/api/v1/ops/people/import-check", {"csv": text})
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_import_check_answers_rows_for_a_good_file(ops: Harness) -> None:
    """A byte-order mark, any column order and case, a quoted comma, Windows line ends."""
    text = ('﻿Name,EMAIL\r\n"Doe, Jane",Jane@Example.org\r\n'
            "Bob Smith,bob@example.org\r\n")
    assert _check_file(ops, text) == {
        "rows": [
            {"line": 2, "email": "jane@example.org", "display_name": "Doe, Jane"},
            {"line": 3, "email": "bob@example.org", "display_name": "Bob Smith"},
        ],
        "errors": [],
    }


_TOO_MANY = "email,name\n" + "".join(f"p{i}@example.org,P{i}\n" for i in range(501))


@pytest.mark.parametrize(
    ("text", "errors", "row_lines"),
    [
        ("email,name,role\na@example.org,A,x\n", [(None, "only the columns")], []),
        ("email,name,email\na@example.org,A,b@example.org\n", [(None, "only the columns")], []),
        ("email\na@example.org\n", [(None, "needs the columns email and name")], []),
        ('email,name\na@example.org,A\nb@example.org,"Bad"x\n',
         [(3, "do not follow the CSV rules")], []),
        ('email,name\na@example.org,"two\nlines"\nc@example.org,C\n',
         [(2, "a name cannot hold a line break")], [4]),
        ("email,name\na@example.org,Caf�\n", [(None, "not saved as UTF-8")], []),
        ("email,name\na@example.org,A\nA@Example.org,B\n",
         [(3, "this email is already on line 2")], [2]),
        (_TOO_MANY, [(None, "at most 500 people")], []),
        ("email,name\n" + "a" * 200_000, [(None, "at most 200,000 characters")], []),
        ("email,name\nnot-an-address,A\n", [(2, "this is not an email address")], []),
        ("email,name\na@example.org,  \n", [(2, "the name is empty")], []),
        ("email,name\na@example.org," + "n" * 201 + "\n", [(2, "longer than 200")], []),
        ("email,name\na@example.org,A,extra\n", [(2, "this line has 3 values")], []),
        ("email,name\n\na@example.org,A\n\n", [], [3]),
    ],
    ids=["other-column", "repeated-column", "missing-column", "bad-quoting", "line-break",
         "not-utf8", "repeated-email", "too-many", "too-large", "bad-email", "empty-name",
         "long-name", "value-count", "blank-line"],
)
def test_import_check_names_each_fault_with_its_line(
    ops: Harness, text: str, errors: list[tuple[int | None, str]], row_lines: list[int]
) -> None:
    body = _check_file(ops, text)
    assert [error["line"] for error in body["errors"]] == [line for line, _ in errors]
    for error, (_, fragment) in zip(body["errors"], errors, strict=True):
        assert fragment in error["message"]
    assert [row["line"] for row in body["rows"]] == row_lines


def test_import_check_writes_nothing(ops: Harness) -> None:
    def counts() -> list[int]:
        with ops.engine.connect() as conn:
            return [
                int(conn.execute(select(func.count()).select_from(table)).scalar_one())
                for table in (app_user, ops_action, cohort_member)
            ]

    before = counts()
    response, lines = _post(ops, "/api/v1/ops/people/import-check",
                            {"csv": "email,name\nnew@example.org,New Person\n"})
    assert response.status_code == 200 and response.json()["rows"]
    assert counts() == before and lines == []

