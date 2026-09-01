"""`GET /api/v1/me` — the identity projection and its provisioning write.

Task 033 § 2. The route is the only place an `app_user` row is created by the
application, and the only place the caller's own email is returned.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.api.identity import sub_display
from policy_atlas.core.schema import app_user
from tests.api.org_support import make_org, ops_enrol, seeded, tenancy_client


def test_me_provisions_an_unenrolled_caller_with_the_sub_rendering(
    engine: Engine, tmp_path: Path
) -> None:
    """A first-ever caller gets a row, a derived name and a null organisation.

    This is the dark-launch shape: `organisation: null` is what tells the
    frontend to hide the scope switcher entirely, so someone not yet enrolled
    sees today's application unchanged.
    """
    del engine  # forces the session migration fixture before the first request
    with tenancy_client(tmp_path, count=1) as (client, (caller,)):
        response = client.get("/api/v1/me", headers=caller.headers)

        assert response.status_code == 200, response.text
        assert response.json() == {
            "user_id": caller.user_id,
            "display_name": sub_display(caller.user_id),
            "email": None,
            "organisation": None,
            "is_admin": False,
        }


def test_me_projects_an_enrolled_caller_with_their_organisation(
    engine: Engine, tmp_path: Path
) -> None:
    """An enrolled caller sees their ops-set name, own email and organisation."""
    with tenancy_client(tmp_path, count=1) as (client, (caller,)):
        with seeded(engine) as conn:
            org_id = make_org(conn, name="Enrolled Org")
            ops_enrol(
                conn,
                user_id=caller.user_id,
                org_id=org_id,
                display_name="Priya Nair",
                email="priya@example.test",
            )
            org_name = conn.execute(
                select(app_user.c.org_id).where(app_user.c.user_id == caller.user_id)
            ).scalar_one()
        assert org_name == org_id

        body = client.get("/api/v1/me", headers=caller.headers).json()

        assert body["display_name"] == "Priya Nair"
        # The caller's *own* address is the one place § 3b permits it.
        assert body["email"] == "priya@example.test"
        assert body["organisation"]["org_id"] == str(org_id)
        assert body["organisation"]["name"].startswith("Enrolled Org")
        assert body["is_admin"] is False


def test_me_is_idempotent_and_never_clobbers_ops_set_fields(
    engine: Engine, tmp_path: Path
) -> None:
    """The upsert is `DO NOTHING`: repeated sign-ins cannot undo an enrolment.

    The failure this pins is silent and total. `ON CONFLICT DO UPDATE` here
    would reset `display_name`, `email` and `is_admin` on every single call,
    so an administrator would lose the flag the moment they refreshed the
    page — and a test written from a one-line "upserts the user" spec would
    stay green through all of it.
    """
    with tenancy_client(tmp_path, count=1) as (client, (caller,)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(
                conn,
                user_id=caller.user_id,
                org_id=org_id,
                display_name="Ops Name",
                email="ops@example.test",
                is_admin=True,
            )

        first = client.get("/api/v1/me", headers=caller.headers).json()
        second = client.get("/api/v1/me", headers=caller.headers).json()

        assert first == second
        assert first["display_name"] == "Ops Name"
        assert first["email"] == "ops@example.test"
        assert first["is_admin"] is True
        assert first["organisation"]["org_id"] == str(org_id)

        with seeded(engine) as conn:
            row = conn.execute(
                select(app_user).where(app_user.c.user_id == caller.user_id)
            ).mappings().one()
        assert row["display_name"] == "Ops Name"
        assert row["email"] == "ops@example.test"
        assert row["is_admin"] is True
        assert row["org_id"] == org_id


def test_me_provisioning_writes_exactly_one_row_across_repeated_calls(
    engine: Engine, tmp_path: Path
) -> None:
    """Provisioning is once-per-user, which is what justifies a write in a GET."""
    with tenancy_client(tmp_path, count=1) as (client, (caller,)):
        for _ in range(3):
            assert client.get("/api/v1/me", headers=caller.headers).status_code == 200

        with seeded(engine) as conn:
            rows = conn.execute(
                select(app_user.c.user_id).where(app_user.c.user_id == caller.user_id)
            ).all()
        assert len(rows) == 1


def test_me_requires_authentication(engine: Engine, tmp_path: Path) -> None:
    """`/api/v1/me` sits inside the bearer boundary like every other data route."""
    del engine
    with tenancy_client(tmp_path, count=1) as (client, _principals):
        response = client.get("/api/v1/me")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthenticated"
