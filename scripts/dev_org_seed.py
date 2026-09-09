"""Seed the LOCAL dev database with an organisation and three enrolled people.

Dev-only quality-of-life (owner request, 2026-08-25): local dev is
deliberately the dark-launch state — org-less — so seeing the 033 tenancy UI
(the Organisation·Mine switcher, colleague read-only views, the admin wide
list) locally means seeding `organisation`/`app_user` rows. This script does
that through the REAL enrolment logic (`policy_atlas.ops.commands`), with
Cognito replaced by a tiny in-process fake that resolves three fixed dev
subjects — the same substitution the ops test suite makes.

Seeded (idempotent — re-running re-enrols, which re-privatises rows, the
same semantics a real re-enrolment has):

- organisation  "Dev Org"
- dev-user      (the sub `make dev` signs the SPA in as) — enrolled owner
- dev-colleague — enrolled colleague
- dev-admin     — enrolled + granted the admin flag

Guards: refuses any non-localhost database and any database named `*_test`
(the test DB is a shared resource the suite owns). Run via `make dev-seed`.
"""

from __future__ import annotations

import os
import re
import sys

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url

from policy_atlas.ops import commands
from policy_atlas.ops.errors import OpsError

_DEV_URL = "postgresql+psycopg://policy_atlas:policy_atlas@localhost:5432/policy_atlas"
_ORG_NAME = "Dev Org"
_POOL_ID = "local_dev_pool"

#: Fixed dev identities: address → (sub, display name). `dev-user` matches the
#: sub the dev issuer mints for `make dev`, so the default session is the owner.
_PEOPLE = {
    "dev-user@local.test": ("dev-user", "Dev User"),
    "dev-colleague@local.test": ("dev-colleague", "Dev Colleague"),
    "dev-admin@local.test": ("dev-admin", "Dev Admin"),
}


class _FakeCognito:
    """Just enough of the Cognito client for `_find_sub_by_email`."""

    def list_users(self, *, UserPoolId: str, Filter: str, Limit: int) -> dict:
        match = re.match(r'email = "(.+)"', Filter)
        email = match.group(1) if match else ""
        entry = _PEOPLE.get(email)
        if entry is None:
            return {"Users": []}
        sub, _ = entry
        return {"Users": [{"Attributes": [{"Name": "sub", "Value": sub}]}]}


def main() -> int:
    url = make_url(os.environ.get("DATABASE_URL", _DEV_URL))
    if url.host not in ("localhost", "127.0.0.1"):
        print(f"refusing non-local database host {url.host!r} — dev seed only", file=sys.stderr)
        return 2
    if (url.database or "").endswith("_test"):
        print(
            "refusing the test database — the suite owns it "
            "(see docs/knowledge/testing-database.md)",
            file=sys.stderr,
        )
        return 2

    engine = create_engine(url)
    if not inspect(engine).has_table("organisation"):
        print(
            "the dev database has no `organisation` table — run:\n"
            "  cd backend && uv run alembic upgrade head",
            file=sys.stderr,
        )
        return 2

    cognito = _FakeCognito()
    with engine.begin() as conn:
        try:
            org = commands.resolve_organisation(conn, _ORG_NAME)
        except OpsError:
            org = commands.create_organisation(conn, name=_ORG_NAME)
        for email, (sub, display_name) in _PEOPLE.items():
            enrolment = commands.enrol_user(
                conn,
                cognito,  # type: ignore[arg-type]  # duck-typed; list_users only
                pool_id=_POOL_ID,
                email=email,
                display_name=display_name,
                org=org,
            )
            print(f"enrolled {sub}: {enrolment.summary()}")
        change = commands.set_admin(conn, grant=True, email="dev-admin@local.test")
        print(f"admin: {change.summary()}")

    print(
        f"""
Seeded "{_ORG_NAME}" with dev-user (owner), dev-colleague, dev-admin (admin flag).
Any rows dev-user already owned are now org-stamped and PRIVATE — flip a task to
Organisation visibility in the UI to see the colleague view.

`make dev` signs in as dev-user. To browse as another identity, mint its token
and run a second frontend:

  cd backend && uv run python -m policy_atlas.api.dev_issuer mint \\
    --dir .dev-issuer --sub dev-colleague --client-id policy-atlas-dev --ttl 14400
  cd frontend && VITE_DEV_TOKEN=<that token> pnpm dev --port 5174

(same for dev-admin)"""
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
