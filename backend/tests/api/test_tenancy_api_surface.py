"""The task-033 API surface at route level: scope, filters, counts, shapes.

Contract § 8. Every case drives a real route through the real application, so
what is asserted is what a caller observes — not what a helper returns.

`GET /projects/{id}` and `GET /portfolios/{id}` moved onto the graded
accessor in phase 4 along with the rest of the call-site cutover; a
colleague who can see a row in their listing can now also open it. Route-
level coverage for the graded read/write split across every cut-over route
lives in `test_route_grades.py`, not here.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.api.identity import sub_display
from policy_atlas.core.schema import portfolio as portfolio_table
from policy_atlas.core.schema import portfolio_membership as membership_table
from policy_atlas.core.schema import project as project_table
from tests.api.org_support import (
    make_org,
    make_portfolio,
    make_project,
    ops_enrol,
    ops_set_admin,
    seeded,
    tenancy_client,
    unique_email,
)


def _ids(body: dict[str, Any], key: str) -> set[str]:
    """Collect one identity field out of a page of rows."""
    return {row[key] for row in body["data"]}


# --- scope (contract § 8) -----------------------------------------------------


def test_projects_scope_defaults_to_all(engine: Engine, tmp_path: Path) -> None:
    """The default is `all`, not `mine`.

    Stated in the plan because a cautious implementer picks `mine` and the
    whole feature then hides behind a switcher nobody turns on.
    """
    with tenancy_client(tmp_path, count=2) as (client, (owner, colleague)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(
                conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague"
            )
            shared = make_project(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )

        default_page = client.get("/api/v1/projects", headers=colleague.headers).json()
        explicit = client.get(
            "/api/v1/projects?scope=all", headers=colleague.headers
        ).json()

        assert str(shared) in _ids(default_page, "project_id")
        assert default_page["data"] == explicit["data"]


def test_projects_scope_mine_excludes_the_organisations_rows(
    engine: Engine, tmp_path: Path
) -> None:
    """`scope=mine` is the pre-033 owner-only listing, unchanged."""
    with tenancy_client(tmp_path, count=2) as (client, (owner, colleague)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(
                conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague"
            )
            theirs = make_project(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )
            mine = make_project(
                conn, owner_user_id=colleague.user_id, org_id=org_id, visibility="org"
            )

        body = client.get("/api/v1/projects?scope=mine", headers=colleague.headers).json()

        assert _ids(body, "project_id") == {str(mine)}
        assert str(theirs) not in _ids(body, "project_id")
        assert body["pagination"]["total_items"] == 1


def test_colleague_sees_org_rows_and_never_private_ones(
    engine: Engine, tmp_path: Path
) -> None:
    """`scope=all` is owner ∪ same-org org-visible — the private row stays out.

    Also covers the outsider: a caller in no shared organisation sees neither.
    """
    with tenancy_client(tmp_path, count=3) as (client, (owner, colleague, outsider)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            other_org = make_org(conn, name="Other")
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(
                conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague"
            )
            ops_enrol(
                conn,
                user_id=outsider.user_id,
                org_id=other_org,
                display_name="Outsider",
            )
            shared = make_project(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )
            secret = make_project(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="private"
            )

        seen = _ids(client.get("/api/v1/projects", headers=colleague.headers).json(), "project_id")
        assert str(shared) in seen
        assert str(secret) not in seen

        outside = _ids(
            client.get("/api/v1/projects", headers=outsider.headers).json(), "project_id"
        )
        assert str(shared) not in outside
        assert str(secret) not in outside


def test_portfolios_scope_all_and_mine_match_the_project_listing(
    engine: Engine, tmp_path: Path
) -> None:
    """`GET /portfolios` carries the same scope semantics as `GET /projects`."""
    with tenancy_client(tmp_path, count=2) as (client, (owner, colleague)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(
                conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague"
            )
            shared = make_portfolio(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )
            secret = make_portfolio(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="private"
            )

        wide = _ids(
            client.get("/api/v1/portfolios", headers=colleague.headers).json(),
            "portfolio_id",
        )
        narrow = _ids(
            client.get("/api/v1/portfolios?scope=mine", headers=colleague.headers).json(),
            "portfolio_id",
        )

        assert str(shared) in wide
        assert str(secret) not in wide
        assert str(shared) not in narrow


def test_unenrolled_callers_never_see_each_others_rows_through_a_listing(
    engine: Engine, tmp_path: Path
) -> None:
    """The NULL rule, at route level.

    `None == None` is `True` in Python, so a loaded-value org comparison would
    hand every unenrolled user every other unenrolled user's work through the
    default listing on day one.
    """
    with tenancy_client(tmp_path, count=2) as (client, (first, second)):
        with seeded(engine) as conn:
            theirs = make_project(conn, owner_user_id=first.user_id, org_id=None)

        body = client.get("/api/v1/projects", headers=second.headers).json()
        assert str(theirs) not in _ids(body, "project_id")


# --- portfolio_id filter (contract § 8) ---------------------------------------


def test_projects_portfolio_id_filter_narrows_the_page(
    engine: Engine, tmp_path: Path
) -> None:
    """`portfolio_id` filters server-side.

    `PortfolioDetailView` filtered the default 50-row global page client-side
    and would silently under-report a Project's Tasks once the visible estate
    spans an organisation.
    """
    with tenancy_client(tmp_path, count=1) as (client, (owner,)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            group = make_portfolio(conn, owner_user_id=owner.user_id, org_id=org_id)
            member = make_project(
                conn, owner_user_id=owner.user_id, org_id=org_id, portfolio_id=group
            )
            loose = make_project(conn, owner_user_id=owner.user_id, org_id=org_id)

        body = client.get(
            f"/api/v1/projects?portfolio_id={group}", headers=owner.headers
        ).json()

        assert _ids(body, "project_id") == {str(member)}
        assert str(loose) not in _ids(body, "project_id")
        assert body["pagination"]["total_items"] == 1


# --- owner_email, admin-only (contract § 8) -----------------------------------


def test_owner_email_is_422_for_a_non_admin_caller(engine: Engine, tmp_path: Path) -> None:
    """A non-admin passing `owner_email` gets 422 `validation_error`, not 403.

    Contract § 8 is explicit: reuse the code the envelope map already assigns
    to a bad parameter rather than inventing a third "your parameter is
    wrong" semantic.
    """
    with tenancy_client(tmp_path, count=1) as (client, (caller,)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(
                conn,
                user_id=caller.user_id,
                org_id=org_id,
                display_name="Ordinary",
                email=unique_email("ordinary"),
            )

        for path in (
            "/api/v1/projects?owner_email=someone@example.test",
            "/api/v1/portfolios?owner_email=someone@example.test",
        ):
            response = client.get(path, headers=caller.headers)
            assert response.status_code == 422, path
            assert response.json()["error"]["code"] == "validation_error"


def test_owner_email_is_422_for_an_unenrolled_caller(engine: Engine, tmp_path: Path) -> None:
    """A caller with no `app_user` row is refused on the same branch."""
    del engine
    with tenancy_client(tmp_path, count=1) as (client, (caller,)):
        response = client.get(
            "/api/v1/projects?owner_email=someone@example.test", headers=caller.headers
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"


def test_owner_email_filters_an_admins_visible_set(engine: Engine, tmp_path: Path) -> None:
    """For an admin the filter resolves an address to an owner and narrows.

    The cross-organisation *reach* arrives with the admin read leg; the
    filter's plumbing — address to `owner_user_id` — lands with the API
    surface, so the leg only widens what this already narrows.
    """
    target_email = unique_email("colleague")
    with tenancy_client(tmp_path, count=2) as (client, (admin, colleague)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(
                conn,
                user_id=admin.user_id,
                org_id=org_id,
                display_name="Support",
                email=unique_email("support"),
                is_admin=True,
            )
            ops_enrol(
                conn,
                user_id=colleague.user_id,
                org_id=org_id,
                display_name="Colleague",
                email=target_email,
            )
            theirs = make_project(
                conn, owner_user_id=colleague.user_id, org_id=org_id, visibility="org"
            )
            mine = make_project(conn, owner_user_id=admin.user_id, org_id=org_id)

        body = client.get(
            f"/api/v1/projects?owner_email={target_email}", headers=admin.headers
        ).json()

        assert _ids(body, "project_id") == {str(theirs)}
        assert str(mine) not in _ids(body, "project_id")


def test_owner_email_matching_nobody_returns_an_empty_page_not_an_error(
    engine: Engine, tmp_path: Path
) -> None:
    """An unknown address is an empty page, so the status code is not an oracle.

    A 404 here would let an administrator probe whether an address is known to
    the system, repeatedly. (The zero-row request is exactly the one the trace
    must still record, for the same reason.)
    """
    with tenancy_client(tmp_path, count=1) as (client, (admin,)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(
                conn,
                user_id=admin.user_id,
                org_id=org_id,
                display_name="Support",
                email=unique_email("support"),
                is_admin=True,
            )

        response = client.get(
            f"/api/v1/projects?owner_email={unique_email('nobody')}", headers=admin.headers
        )

        assert response.status_code == 200
        assert response.json()["data"] == []
        assert response.json()["pagination"]["total_items"] == 0


# --- derived counts move to the tenancy predicate (contract § 8) --------------


def test_task_count_excludes_members_the_caller_cannot_read(
    engine: Engine, tmp_path: Path
) -> None:
    """A colleague's count omits a private member they cannot open.

    Counted unconditionally before this slice, which would have told a
    colleague the true size of a Project whose Tasks they cannot see.
    """
    with tenancy_client(tmp_path, count=2) as (client, (owner, colleague)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(
                conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague"
            )
            group = make_portfolio(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )
            make_project(
                conn,
                owner_user_id=owner.user_id,
                org_id=org_id,
                visibility="org",
                portfolio_id=group,
            )
            make_project(
                conn,
                owner_user_id=owner.user_id,
                org_id=org_id,
                visibility="private",
                portfolio_id=group,
            )

        colleague_card = next(
            row
            for row in client.get("/api/v1/portfolios", headers=colleague.headers).json()["data"]
            if row["portfolio_id"] == str(group)
        )
        owner_card = next(
            row
            for row in client.get("/api/v1/portfolios", headers=owner.headers).json()["data"]
            if row["portfolio_id"] == str(group)
        )

        assert colleague_card["task_count"] == 1
        assert owner_card["task_count"] == 2


def test_task_count_excludes_members_outside_the_callers_organisation(
    engine: Engine, tmp_path: Path
) -> None:
    """A member stamped to another organisation is not counted.

    The invariant will stop this pairing arising through the API, but the row
    shape allows it (an operator assignment, or a pre-invariant row), and the
    count must not be the surface that leaks it.
    """
    with tenancy_client(tmp_path, count=2) as (client, (owner, stranger)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            elsewhere = make_org(conn, name="Elsewhere")
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(
                conn, user_id=stranger.user_id, org_id=elsewhere, display_name="Stranger"
            )
            group = make_portfolio(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )
            make_project(
                conn,
                owner_user_id=owner.user_id,
                org_id=org_id,
                visibility="org",
                portfolio_id=group,
            )
            make_project(
                conn,
                owner_user_id=stranger.user_id,
                org_id=elsewhere,
                visibility="org",
                portfolio_id=group,
            )

        card = next(
            row
            for row in client.get("/api/v1/portfolios", headers=owner.headers).json()["data"]
            if row["portfolio_id"] == str(group)
        )

        assert card["task_count"] == 1


def test_listing_totals_track_the_scope_they_were_asked_for(
    engine: Engine, tmp_path: Path
) -> None:
    """`total_items` counts the same rows the page draws from, per scope."""
    with tenancy_client(tmp_path, count=2) as (client, (owner, colleague)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(
                conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague"
            )
            make_project(conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org")
            make_project(conn, owner_user_id=colleague.user_id, org_id=org_id)

        wide = client.get("/api/v1/projects", headers=colleague.headers).json()
        narrow = client.get("/api/v1/projects?scope=mine", headers=colleague.headers).json()

        assert wide["pagination"]["total_items"] == 2
        assert narrow["pagination"]["total_items"] == 1


# --- the three new read fields (contract § 8, § 3b) ---------------------------


def test_project_rows_carry_visibility_is_owner_and_owner_display(
    engine: Engine, tmp_path: Path
) -> None:
    """`is_owner` is per-caller, and `owner_display` names the row's owner."""
    with tenancy_client(tmp_path, count=2) as (client, (owner, colleague)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Ada Owner")
            ops_enrol(
                conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague"
            )
            shared = make_project(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )

        as_owner = next(
            row
            for row in client.get("/api/v1/projects", headers=owner.headers).json()["data"]
            if row["project_id"] == str(shared)
        )
        as_colleague = next(
            row
            for row in client.get("/api/v1/projects", headers=colleague.headers).json()["data"]
            if row["project_id"] == str(shared)
        )

        assert as_owner["visibility"] == "org"
        assert as_owner["is_owner"] is True
        assert as_owner["owner_display"] == "Ada Owner"
        assert as_colleague["is_owner"] is False
        assert as_colleague["owner_display"] == "Ada Owner"


def test_portfolio_rows_carry_visibility_is_owner_and_owner_display(
    engine: Engine, tmp_path: Path
) -> None:
    """The same three fields on the portfolio shape."""
    with tenancy_client(tmp_path, count=2) as (client, (owner, colleague)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Ada Owner")
            ops_enrol(
                conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague"
            )
            shared = make_portfolio(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )

        as_colleague = next(
            row
            for row in client.get("/api/v1/portfolios", headers=colleague.headers).json()["data"]
            if row["portfolio_id"] == str(shared)
        )

        assert as_colleague["visibility"] == "org"
        assert as_colleague["is_owner"] is False
        assert as_colleague["owner_display"] == "Ada Owner"


def test_owner_display_is_never_the_email(engine: Engine, tmp_path: Path) -> None:
    """§ 3b's hardest rule: no surface shows one user's address to another.

    An email fallback would print every colleague's address on every row and
    card, and would let an administrator harvest `{email, organisation}` for
    every owner in the system — the user directory this contract declares
    Out, reached by another door.

    Two owner shapes are covered: an enrolled owner whose row *does* carry an
    address (the schema makes `display_name` NOT NULL, so there is no
    "display name missing, email present" row to construct), and an owner who
    has never called `/me` and so has no identity row at all.
    """
    ada_email = unique_email("ada")
    with tenancy_client(tmp_path, count=3) as (client, (owner, colleague, ghost)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(
                conn,
                user_id=owner.user_id,
                org_id=org_id,
                display_name="Ada Owner",
                email=ada_email,
            )
            ops_enrol(
                conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague"
            )
            enrolled_row = make_project(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )
            # An owner with no `app_user` row: `org_id` is stamped by ops, the
            # identity row simply does not exist yet.
            ghost_row = make_project(
                conn, owner_user_id=ghost.user_id, org_id=org_id, visibility="org"
            )
            # An ownerless row — what `runtime/orchestrate.py` leaves behind.
            orphan_row = make_project(conn, owner_user_id=None, org_id=org_id)

        body = client.get("/api/v1/projects", headers=colleague.headers).json()
        rows = {row["project_id"]: row for row in body["data"]}

        assert rows[str(enrolled_row)]["owner_display"] == "Ada Owner"
        assert rows[str(ghost_row)]["owner_display"] == sub_display(ghost.user_id)
        assert rows[str(orphan_row)]["owner_display"] is None
        assert ada_email not in client.get(
            "/api/v1/projects", headers=colleague.headers
        ).text


# --- PATCH visibility (contract § 6, § 8) -------------------------------------


def test_patch_with_both_visibility_and_portfolio_id_is_422(
    engine: Engine, tmp_path: Path
) -> None:
    """The two orderings give different results, so the combination is refused."""
    with tenancy_client(tmp_path, count=1) as (client, (owner,)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            row = make_project(conn, owner_user_id=owner.user_id, org_id=org_id)
            group = make_portfolio(conn, owner_user_id=owner.user_id, org_id=org_id)

        response = client.patch(
            f"/api/v1/projects/{row}",
            headers=owner.headers,
            json={"visibility": "private", "portfolio_ids": [str(group)]},
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"


def test_patch_with_visibility_and_an_explicit_null_portfolio_is_also_422(
    engine: Engine, tmp_path: Path
) -> None:
    """Unassign-and-set is the ambiguous case, so `None` cannot be the test."""
    with tenancy_client(tmp_path, count=1) as (client, (owner,)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            row = make_project(conn, owner_user_id=owner.user_id, org_id=org_id)

        response = client.patch(
            f"/api/v1/projects/{row}",
            headers=owner.headers,
            json={"visibility": "private", "portfolio_ids": None},
        )

        assert response.status_code == 422


def test_owner_can_set_a_loose_projects_visibility(engine: Engine, tmp_path: Path) -> None:
    """A project in no portfolio is unconstrained, so the write lands."""
    with tenancy_client(tmp_path, count=1) as (client, (owner,)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            row = make_project(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )

        response = client.patch(
            f"/api/v1/projects/{row}", headers=owner.headers, json={"visibility": "private"}
        )

        assert response.status_code == 200, response.text
        assert response.json()["visibility"] == "private"
        with seeded(engine) as conn:
            stored = conn.execute(
                select(project_table.c.visibility).where(project_table.c.project_id == row)
            ).scalar_one()
        assert stored == "private"


def test_setting_visibility_on_a_project_in_a_portfolio_is_409(
    engine: Engine, tmp_path: Path
) -> None:
    """i.5: the row follows its portfolio, so there is no honest write here."""
    with tenancy_client(tmp_path, count=1) as (client, (owner,)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            group = make_portfolio(conn, owner_user_id=owner.user_id, org_id=org_id)
            row = make_project(
                conn, owner_user_id=owner.user_id, org_id=org_id, portfolio_id=group
            )

        response = client.patch(
            f"/api/v1/projects/{row}", headers=owner.headers, json={"visibility": "private"}
        )

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "visibility_conflict"
        with seeded(engine) as conn:
            stored = conn.execute(
                select(project_table.c.visibility).where(project_table.c.project_id == row)
            ).scalar_one()
        assert stored == "org"


def test_a_colleague_cannot_write_a_row_they_can_read(engine: Engine, tmp_path: Path) -> None:
    """403 `forbidden`, not 404: they are already looking at the row.

    Write is owner-only. Hiding a colleague's row from a colleague whose
    listing already shows it would be theatre, which is why contract § 8
    spends the 403 `web-api.md` § Auth boundary pre-reserved.
    """
    with tenancy_client(tmp_path, count=2) as (client, (owner, colleague)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(
                conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague"
            )
            row = make_project(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )

        assert str(row) in _ids(
            client.get("/api/v1/projects", headers=colleague.headers).json(), "project_id"
        )
        response = client.patch(
            f"/api/v1/projects/{row}",
            headers=colleague.headers,
            json={"visibility": "private"},
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "forbidden"


def test_an_outsider_still_gets_404_on_patch(engine: Engine, tmp_path: Path) -> None:
    """The BOLA rule is untouched for a caller with no read leg at all."""
    with tenancy_client(tmp_path, count=2) as (client, (owner, outsider)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            row = make_project(conn, owner_user_id=owner.user_id, org_id=org_id)

        response = client.patch(
            f"/api/v1/projects/{row}",
            headers=outsider.headers,
            json={"visibility": "private"},
        )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"


def test_portfolio_patch_accepts_visibility_only_as_the_cascade(
    engine: Engine, tmp_path: Path
) -> None:
    """`PortfolioUpdate` gained `visibility` **together with** the cascade.

    This case asserted 422 while the field was absent, and its docstring said
    what would change it: "`PATCH /portfolios/{id}` gains it together with the
    cascade that makes it honest." The cascade landed, so the refusal did too
    — deliberately, not by weakening a check. What the phase-3 assertion
    protected still holds and is asserted here: the field never reaches the
    column on its own. The member follows in the same request.

    The full i.4 surface — archived members, the count, the owner-only grade,
    the splat allow-list — lives in `test_visibility_invariant.py`.
    """
    with tenancy_client(tmp_path, count=1) as (client, (owner,)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            group = make_portfolio(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )
            member = make_project(
                conn,
                owner_user_id=owner.user_id,
                org_id=org_id,
                visibility="org",
                portfolio_id=group,
            )

        response = client.patch(
            f"/api/v1/portfolios/{group}", headers=owner.headers, json={"visibility": "private"}
        )

        assert response.status_code == 200, response.text
        with seeded(engine) as conn:
            stored = conn.execute(
                select(portfolio_table.c.visibility).where(
                    portfolio_table.c.portfolio_id == group
                )
            ).scalar_one()
            stored_member = conn.execute(
                select(project_table.c.visibility).where(project_table.c.project_id == member)
            ).scalar_one()
        assert stored == "private"
        assert stored_member == "private"


# --- POST /portfolios {from_project_id} (contract § 6, i.1) -------------------


def test_from_project_id_inherits_visibility_and_organisation_and_takes_the_member(
    engine: Engine, tmp_path: Path
) -> None:
    """i.1: the new portfolio matches its first member on both fields.

    Rev 2.0 covered `visibility` only, which let an operator assign a project
    to org A and its portfolio to org B and have org B's members read and
    count a row belonging to org A.
    """
    with tenancy_client(tmp_path, count=1) as (client, (owner,)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            source = make_project(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="private"
            )

        response = client.post(
            "/api/v1/portfolios",
            headers=owner.headers,
            json={"name": "Seeded project", "from_project_id": str(source)},
        )

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["visibility"] == "private"
        assert body["task_count"] == 1
        with seeded(engine) as conn:
            created = conn.execute(
                select(portfolio_table).where(
                    portfolio_table.c.portfolio_id == uuid.UUID(body["portfolio_id"])
                )
            ).mappings().one()
            member = conn.execute(
                select(project_table).where(project_table.c.project_id == source)
            ).mappings().one()
        assert created["org_id"] == org_id
        assert created["visibility"] == "private"
        with seeded(engine) as conn:
            memberships = conn.execute(
                select(membership_table.c.portfolio_id).where(
                    membership_table.c.project_id == source
                )
            ).scalars().all()
        assert memberships == [uuid.UUID(body["portfolio_id"])]
        assert member["visibility"] == created["visibility"]
        assert member["org_id"] == created["org_id"]


def test_from_project_id_resolves_under_the_write_grade(
    engine: Engine, tmp_path: Path
) -> None:
    """A colleague gets 403 and an outsider 404 — neither creates anything.

    Under a read grade a colleague (or, once the admin leg lands, an
    administrator) could pull a row they do not own into a portfolio and
    change its visibility. That is the concrete admin-write escape.
    """
    with tenancy_client(tmp_path, count=3) as (client, (owner, colleague, outsider)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(
                conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague"
            )
            source = make_project(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )

        forbidden = client.post(
            "/api/v1/portfolios",
            headers=colleague.headers,
            json={"name": "Not yours", "from_project_id": str(source)},
        )
        missing = client.post(
            "/api/v1/portfolios",
            headers=outsider.headers,
            json={"name": "Not yours", "from_project_id": str(source)},
        )

        assert forbidden.status_code == 403
        assert forbidden.json()["error"]["code"] == "forbidden"
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "not_found"
        with seeded(engine) as conn:
            still_loose = conn.execute(
                select(membership_table.c.portfolio_id).where(
                    membership_table.c.project_id == source
                )
            ).scalars().all()
        assert still_loose == []


# --- org stamping on create (contract § 7) ------------------------------------


def test_create_stamps_the_creators_organisation_onto_both_row_kinds(
    engine: Engine, tmp_path: Path
) -> None:
    """Without this, every row created after the migration is invisible to its org."""
    with tenancy_client(tmp_path, count=1) as (client, (owner,)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")

        project_id = client.post(
            "/api/v1/projects", headers=owner.headers, json={"name": "Fresh"}
        ).json()["project_id"]
        portfolio_id = client.post(
            "/api/v1/portfolios", headers=owner.headers, json={"name": "Fresh"}
        ).json()["portfolio_id"]

        with seeded(engine) as conn:
            stamped_project = conn.execute(
                select(project_table.c.org_id).where(
                    project_table.c.project_id == uuid.UUID(project_id)
                )
            ).scalar_one()
            stamped_portfolio = conn.execute(
                select(portfolio_table.c.org_id).where(
                    portfolio_table.c.portfolio_id == uuid.UUID(portfolio_id)
                )
            ).scalar_one()
        assert stamped_project == org_id
        assert stamped_portfolio == org_id


def test_a_new_row_is_private_until_its_owner_shares_it(
    engine: Engine, tmp_path: Path
) -> None:
    """Owner amendment 2026-08-26 (staging canary): the column default is `private`.

    The create paths deliberately write no `visibility`, so this pins the
    DATABASE default — an enrolled creator's fresh project and portfolio are
    invisible to a same-org colleague until the owner deliberately shares.
    """
    with tenancy_client(tmp_path, count=2) as (client, (owner, colleague)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(
                conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague"
            )

        project_id = client.post(
            "/api/v1/projects", headers=owner.headers, json={"name": "Fresh"}
        ).json()["project_id"]
        portfolio_id = client.post(
            "/api/v1/portfolios", headers=owner.headers, json={"name": "Fresh"}
        ).json()["portfolio_id"]

        with seeded(engine) as conn:
            stored = {
                conn.execute(
                    select(project_table.c.visibility).where(
                        project_table.c.project_id == uuid.UUID(project_id)
                    )
                ).scalar_one(),
                conn.execute(
                    select(portfolio_table.c.visibility).where(
                        portfolio_table.c.portfolio_id == uuid.UUID(portfolio_id)
                    )
                ).scalar_one(),
            }
        assert stored == {"private"}

        assert (
            client.get(f"/api/v1/projects/{project_id}", headers=colleague.headers).status_code
            == 404
        )
        assert uuid.UUID(portfolio_id) not in {
            uuid.UUID(row) for row in _ids(
                client.get("/api/v1/portfolios", headers=colleague.headers).json(),
                "portfolio_id",
            )
        }

        shared = client.patch(
            f"/api/v1/projects/{project_id}",
            headers=owner.headers,
            json={"visibility": "org"},
        )
        assert shared.status_code == 200
        assert (
            client.get(f"/api/v1/projects/{project_id}", headers=colleague.headers).status_code
            == 200
        )


def test_create_leaves_an_unenrolled_creators_rows_without_an_organisation(
    engine: Engine, tmp_path: Path
) -> None:
    """NULL `org_id` is the dark launch: reachable by its owner and nobody else."""
    with tenancy_client(tmp_path, count=2) as (client, (creator, stranger)):
        project_id = client.post(
            "/api/v1/projects", headers=creator.headers, json={"name": "Unenrolled"}
        ).json()["project_id"]

        with seeded(engine) as conn:
            stamped = conn.execute(
                select(project_table.c.org_id).where(
                    project_table.c.project_id == uuid.UUID(project_id)
                )
            ).scalar_one()
        assert stamped is None

        mine = client.get("/api/v1/projects", headers=creator.headers).json()
        theirs = client.get("/api/v1/projects", headers=stranger.headers).json()
        assert project_id in _ids(mine, "project_id")
        assert project_id not in _ids(theirs, "project_id")


# --- colleague assignment (owner ruling 2026-08-27) ---------------------------


def test_colleague_can_add_their_task_to_an_org_visible_portfolio(
    engine: Engine, tmp_path: Path
) -> None:
    """A same-org colleague may join an org-visible portfolio they did not create.

    The target resolves under the colleague-mutation grade, so the old 403
    is gone; the task inherits the derived visibility (org — the portfolio
    is org-visible) and the portfolio's organisation, and the portfolio
    owner sees it counted.
    """
    with tenancy_client(tmp_path, count=2) as (client, (owner, colleague)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague")
            group = make_portfolio(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )
            row = make_project(
                conn, owner_user_id=colleague.user_id, org_id=org_id, visibility="private"
            )

        response = client.patch(
            f"/api/v1/projects/{row}",
            headers=colleague.headers,
            json={"portfolio_ids": [str(group)]},
        )

        assert response.status_code == 200, response.text
        assert response.json()["portfolio_ids"] == [str(group)]
        assert response.json()["visibility"] == "org"

        owners_card = next(
            card
            for card in client.get("/api/v1/portfolios", headers=owner.headers).json()["data"]
            if card["portfolio_id"] == str(group)
        )
        assert owners_card["task_count"] == 1


def test_colleague_cannot_join_a_private_or_cross_org_portfolio(
    engine: Engine, tmp_path: Path
) -> None:
    """Outside the caller's estate the target stays an indistinguishable 404."""
    with tenancy_client(tmp_path, count=3) as (client, (owner, colleague, outsider)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            elsewhere = make_org(conn, name="Elsewhere")
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague")
            ops_enrol(conn, user_id=outsider.user_id, org_id=elsewhere, display_name="Outsider")
            hidden = make_portfolio(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="private"
            )
            foreign = make_portfolio(
                conn, owner_user_id=outsider.user_id, org_id=elsewhere, visibility="org"
            )
            row = make_project(
                conn, owner_user_id=colleague.user_id, org_id=org_id, visibility="private"
            )

        for target in (hidden, foreign):
            response = client.patch(
                f"/api/v1/projects/{row}",
                headers=colleague.headers,
                json={"portfolio_ids": [str(target)]},
            )
            assert response.status_code == 404, (target, response.text)

        untouched = client.get(f"/api/v1/projects/{row}", headers=colleague.headers)
        assert untouched.json()["portfolio_ids"] == []


def test_the_admin_leg_never_grants_assignment(engine: Engine, tmp_path: Path) -> None:
    """An out-of-organisation administrator can read the portfolio but not join it.

    The colleague-mutation grade resolves through `own_estate`, which has no
    admin leg — the same structural guarantee the chat mutations rely on. The
    admin gets the grade's 404, not a 403: there is no read grade here to
    disclose the row with.
    """
    with tenancy_client(tmp_path, count=2) as (client, (owner, admin)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            elsewhere = make_org(conn, name="Elsewhere")
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(conn, user_id=admin.user_id, org_id=elsewhere, display_name="Admin")
            ops_set_admin(conn, user_id=admin.user_id, is_admin=True)
            group = make_portfolio(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )
            row = make_project(
                conn, owner_user_id=admin.user_id, org_id=elsewhere, visibility="private"
            )

        readable = client.get(f"/api/v1/portfolios/{group}", headers=admin.headers)
        assert readable.status_code == 200

        refused = client.patch(
            f"/api/v1/projects/{row}",
            headers=admin.headers,
            json={"portfolio_ids": [str(group)]},
        )
        assert refused.status_code == 404


def test_a_kept_membership_survives_the_portfolio_going_private(
    engine: Engine, tmp_path: Path
) -> None:
    """Replace-all never locks an owner out of a set they are already in.

    The colleague joins an org-visible portfolio; its owner then cascades it
    private, which takes the colleague's task private with it (derived) and
    makes the portfolio unreadable to the colleague. Re-sending the same set
    still succeeds — ids the task already belongs to are kept without
    re-resolving the grade — and `[]` still removes.
    """
    with tenancy_client(tmp_path, count=2) as (client, (owner, colleague)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague")
            group = make_portfolio(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )
            row = make_project(
                conn, owner_user_id=colleague.user_id, org_id=org_id, visibility="private"
            )

        joined = client.patch(
            f"/api/v1/projects/{row}",
            headers=colleague.headers,
            json={"portfolio_ids": [str(group)]},
        )
        assert joined.status_code == 200, joined.text

        cascaded = client.patch(
            f"/api/v1/portfolios/{group}", headers=owner.headers, json={"visibility": "private"}
        )
        assert cascaded.status_code == 200, cascaded.text

        resent = client.patch(
            f"/api/v1/projects/{row}",
            headers=colleague.headers,
            json={"portfolio_ids": [str(group)]},
        )
        assert resent.status_code == 200, resent.text
        assert resent.json()["visibility"] == "private"

        removed = client.patch(
            f"/api/v1/projects/{row}", headers=colleague.headers, json={"portfolio_ids": []}
        )
        assert removed.status_code == 200, removed.text
        assert removed.json()["portfolio_ids"] == []
