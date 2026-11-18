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
    ("GET", "/api/v1/ops/people"),
    ("POST", "/api/v1/ops/people"),
    ("POST", "/api/v1/ops/people/enrol"),
    ("POST", "/api/v1/ops/people/de-enrol"),
    ("POST", "/api/v1/ops/people/offboard"),
    ("POST", "/api/v1/ops/people/resend"),
    ("POST", "/api/v1/ops/people/quota"),
    ("GET", "/api/v1/ops/requests"),
    ("POST", "/api/v1/ops/requests/{entry_id}/approve"),
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
        filled = [(m, p.format(org_id=uuid.uuid4(), entry_id=uuid.uuid4())) for m, p in routes]
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
        _assert_audited(ops, lines, action="org.quota", target=str(org_id), outcome="ok")
        assert limit() == 7

        response, lines = _post(
            ops,
            "/api/v1/ops/people/quota",
            {"user_ids": [member.user_id], "task_quota_per_year": 3, "runs_per_user": 1},
        )
        assert response.status_code == 200, response.text
        assert response.json()["results"][0]["outcome"] == "ok"
        _assert_audited(ops, lines, action="person.quota", target=member.user_id, outcome="ok")
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
    assert row["limits"] == {"task_quota_per_year": None, "runs_per_user": None}
    assert next(p for p in everyone if p["user_id"] == other)["limits"] == {
        "task_quota_per_year": 50,
        "runs_per_user": 3,
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


def test_bulk_offboard_locks_the_account_out_then_de_enrols(ops: Harness) -> None:
    """Cognito disable and sign-out (Stubber-validated), then the database half."""
    org_id = _seed_org(ops)
    leaver = _seed_person(ops, org_id=org_id, label="leaver")
    with seeded(ops.engine) as conn:
        task_id = make_task(conn, owner_user_id=leaver, org_id=org_id)
        conn.execute(update(task).where(task.c.task_id == task_id).values(is_public=True))
    expect_sub_lookup(ops.stubber, sub=leaver)
    expect_lock_out(ops.stubber, sub=leaver)
    response, lines = _post(ops, "/api/v1/ops/people/offboard", {"user_ids": [leaver]})
    assert response.status_code == 200, response.text
    assert response.json()["results"][0]["outcome"] == "ok"
    row = _user(ops, leaver)
    assert row is not None and row["org_id"] is None
    with ops.engine.connect() as conn:
        assert conn.execute(
            select(task.c.is_public, task.c.org_id).where(task.c.task_id == task_id)
        ).one() == (False, None)
    _assert_audited(ops, lines, action="person.offboard", target=leaver, outcome="ok")


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
    assert items[invited]["status"] == "invited"
    assert items[invited]["account_user_id"] == "someone"
    assert (items[check]["status"], items[check]["note"]) == ("check", other_name)
    created = [item["created_at"] for item in after["items"]]
    assert created == sorted(created)
    signup = after["self_signup"]
    assert signup["enabled"] is False and signup["max_per_hour"] == 20
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
    response, lines = _post(ops, f"/api/v1/ops/requests/{second}/approve", {"org_id": str(org_id)})
    assert response.status_code == 200, response.text
    assert response.json()["account_user_id"] == known
    assert [r["outcome"] for r in _audit(ops)] == ["invited", "enrolled"]


def test_approve_refuses_an_address_enrolled_elsewhere(ops: Harness) -> None:
    """409 ``enrolled_elsewhere``; the row stays unstamped and nothing is audited."""
    here, there = _seed_org(ops), _seed_org(ops)
    elsewhere = _seed_person(ops, org_id=there, label="elsewhere")
    row = _user(ops, elsewhere)
    assert row is not None
    entry_id = _seed_request(ops, email=row["email"])
    expect_lookup(ops.stubber, email=row["email"], sub=elsewhere)
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


def test_an_operator_cannot_offboard_or_de_enrol_themselves(ops: Harness) -> None:
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
