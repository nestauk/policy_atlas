"""The visibility and organisation invariant, i.1-i.6 (contract § 6, owner call (i)).

**A `project` with a non-NULL `portfolio_id` carries its portfolio's
`visibility` *and* its `org_id`. A project in no portfolio is unconstrained.**

The invariant spans two tables, so no CHECK can express it: enforcement is the
write paths plus the property at the bottom of this file. Every case here
drives real routes, because the invariant is a statement about what the API
does, not about what a helper returns.

The six paths and where each is enforced:

- **i.1** `POST /portfolios {from_project_id}` — `portfolios.create_portfolio`.
  Pinned in `test_tenancy_api_surface.py`, where the create surface lives.
- **i.2 / i.3** assignment — `projects.update_project`, here.
- **i.4** the cascade — `portfolios._cascade_visibility`, here.
- **i.5** setting a member's visibility → 409 — `projects.update_project`.
  Pinned in `test_tenancy_api_surface.py` alongside the both-fields 422.
- **i.6** removal — `projects.update_project`, here.
"""

from __future__ import annotations

import random
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import or_, select
from sqlalchemy.engine import Engine

from policy_atlas.api.routers.portfolios import _PATCHABLE_COLUMNS
from policy_atlas.core.schema import portfolio as portfolio_table
from policy_atlas.core.schema import project as project_table
from tests.api.org_support import (
    Principal,
    make_org,
    make_portfolio,
    make_project,
    ops_enrol,
    seeded,
    tenancy_client,
)


def _row(engine: Engine, project_id: uuid.UUID | str) -> Any:
    """Read one project's invariant-bearing fields straight from the database."""
    with seeded(engine) as conn:
        return conn.execute(
            select(
                project_table.c.portfolio_id,
                project_table.c.visibility,
                project_table.c.org_id,
                project_table.c.status,
            ).where(project_table.c.project_id == uuid.UUID(str(project_id)))
        ).mappings().one()


def _portfolio_row(engine: Engine, portfolio_id: uuid.UUID | str) -> Any:
    """Read one portfolio's invariant-bearing fields straight from the database."""
    with seeded(engine) as conn:
        return conn.execute(
            select(portfolio_table.c.visibility, portfolio_table.c.org_id).where(
                portfolio_table.c.portfolio_id == uuid.UUID(str(portfolio_id))
            )
        ).mappings().one()


def _members(engine: Engine, owner_user_id: str) -> list[Any]:
    """Return every portfolio member one owner has, each flagged for breach.

    The breach test is computed **in SQL** (`IS DISTINCT FROM` for the
    nullable organisation), for the same reason the access legs are: two
    NULLs are equal for this question and unequal for that one, and asking
    the database keeps a single reading of it. Scoped to one owner because the
    test database is shared across the suite — another test's rows are not
    this test's property.

    Args:
        engine: The session engine.
        owner_user_id: The owner whose estate the invariant is asserted over.

    Returns:
        One mapping per member project, carrying both sides of the comparison
        and a `breached` flag, so a failure names the offending pair.
    """
    with seeded(engine) as conn:
        return list(
            conn.execute(
                select(
                    project_table.c.project_id,
                    project_table.c.status,
                    project_table.c.visibility.label("member_visibility"),
                    portfolio_table.c.visibility.label("portfolio_visibility"),
                    project_table.c.org_id.label("member_org"),
                    portfolio_table.c.org_id.label("portfolio_org"),
                    or_(
                        project_table.c.visibility != portfolio_table.c.visibility,
                        project_table.c.org_id.is_distinct_from(portfolio_table.c.org_id),
                    ).label("breached"),
                )
                .select_from(
                    project_table.join(
                        portfolio_table,
                        project_table.c.portfolio_id == portfolio_table.c.portfolio_id,
                    )
                )
                .where(project_table.c.owner_user_id == owner_user_id)
            ).mappings()
        )


def _breaches(engine: Engine, owner_user_id: str) -> list[Any]:
    """The subset of :func:`_members` that violates the invariant."""
    return [member for member in _members(engine, owner_user_id) if member["breached"]]


def _enrolled_owner(
    engine: Engine, owner: Principal, *, display_name: str = "Owner"
) -> uuid.UUID:
    """Seed one organisation with `owner` enrolled in it."""
    with seeded(engine) as conn:
        org_id = make_org(conn)
        ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name=display_name)
    return org_id


# --- i.2 and i.3: assignment (the same rule in two directions) ----------------


def test_assigning_a_private_project_to_an_org_portfolio_promotes_it(
    engine: Engine, tmp_path: Path
) -> None:
    """i.2. The member follows the portfolio, and the response says so.

    Silent by design and not silent in effect: the response carries the
    resulting `visibility`, so a direct API caller and the screen observe the
    same outcome. Nothing prompts (owner call (i)).
    """
    with tenancy_client(tmp_path, count=1) as (client, (owner,)):
        org_id = _enrolled_owner(engine, owner)
        with seeded(engine) as conn:
            group = make_portfolio(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )
            row = make_project(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="private"
            )

        response = client.patch(
            f"/api/v1/projects/{row}", headers=owner.headers, json={"portfolio_id": str(group)}
        )

        assert response.status_code == 200, response.text
        assert response.json()["visibility"] == "org"
        stored = _row(engine, row)
        assert stored["visibility"] == "org"
        assert stored["org_id"] == org_id
        assert _breaches(engine, owner.user_id) == []


def test_assigning_an_org_project_to_a_private_portfolio_demotes_it(
    engine: Engine, tmp_path: Path
) -> None:
    """i.3, the non-exposing direction — same rule, read the other way."""
    with tenancy_client(tmp_path, count=1) as (client, (owner,)):
        org_id = _enrolled_owner(engine, owner)
        with seeded(engine) as conn:
            group = make_portfolio(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="private"
            )
            row = make_project(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )

        response = client.patch(
            f"/api/v1/projects/{row}", headers=owner.headers, json={"portfolio_id": str(group)}
        )

        assert response.status_code == 200, response.text
        assert response.json()["visibility"] == "private"
        assert _row(engine, row)["visibility"] == "private"
        assert _breaches(engine, owner.user_id) == []


def test_assignment_carries_the_portfolios_organisation_not_only_its_visibility(
    engine: Engine, tmp_path: Path
) -> None:
    """The `org_id` half of the invariant, which rev 2.0 of the contract missed.

    A member matching on `visibility` alone lets a project stamped to
    organisation A sit inside a portfolio stamped to organisation B, where
    B's members read and count it. The row shape permits that pairing (an
    operator assignment, a pre-invariant row); the assignment path must not.
    """
    with tenancy_client(tmp_path, count=1) as (client, (owner,)):
        org_id = _enrolled_owner(engine, owner)
        with seeded(engine) as conn:
            elsewhere = make_org(conn, name="Elsewhere")
            group = make_portfolio(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )
            # Stamped to another organisation, as only an operator or a
            # pre-invariant row could be.
            row = make_project(
                conn, owner_user_id=owner.user_id, org_id=elsewhere, visibility="org"
            )

        response = client.patch(
            f"/api/v1/projects/{row}", headers=owner.headers, json={"portfolio_id": str(group)}
        )

        assert response.status_code == 200, response.text
        assert _row(engine, row)["org_id"] == org_id
        assert _breaches(engine, owner.user_id) == []


# --- i.6: removal -------------------------------------------------------------


def test_removing_a_project_from_a_portfolio_changes_neither_field(
    engine: Engine, tmp_path: Path
) -> None:
    """i.6. Leaving is not a way to change visibility or organisation.

    Both directions are covered in one case, because "removal keeps what it
    had" is only meaningful if it holds for the private member too: a row that
    was org-visible stays org-visible, and a row that was private stays
    private. Unconstrained afterwards — that is what makes the loop test
    below the interesting one.
    """
    with tenancy_client(tmp_path, count=1) as (client, (owner,)):
        org_id = _enrolled_owner(engine, owner)
        with seeded(engine) as conn:
            shared_group = make_portfolio(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )
            secret_group = make_portfolio(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="private"
            )
            shared_member = make_project(
                conn,
                owner_user_id=owner.user_id,
                org_id=org_id,
                visibility="org",
                portfolio_id=shared_group,
            )
            secret_member = make_project(
                conn,
                owner_user_id=owner.user_id,
                org_id=org_id,
                visibility="private",
                portfolio_id=secret_group,
            )

        for member, expected in ((shared_member, "org"), (secret_member, "private")):
            response = client.patch(
                f"/api/v1/projects/{member}", headers=owner.headers, json={"portfolio_id": None}
            )
            assert response.status_code == 200, response.text
            assert response.json()["portfolio_id"] is None
            assert response.json()["visibility"] == expected
            stored = _row(engine, member)
            assert stored["portfolio_id"] is None
            assert stored["visibility"] == expected
            assert stored["org_id"] == org_id


# --- i.4: the cascade ---------------------------------------------------------


def test_the_cascade_carries_every_member_including_archived_ones(
    engine: Engine, tmp_path: Path
) -> None:
    """i.4. `PATCH /portfolios/{id}` with `visibility` is the cascade.

    Archived members are included (contract § 6). They are excluded from the
    derived task count, not from the row's visibility — leaving them behind
    would keep exactly the rows nobody is looking at readable by the whole
    organisation after their owner made the Project private.
    """
    with tenancy_client(tmp_path, count=1) as (client, (owner,)):
        org_id = _enrolled_owner(engine, owner)
        with seeded(engine) as conn:
            group = make_portfolio(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )
            active_member = make_project(
                conn,
                owner_user_id=owner.user_id,
                org_id=org_id,
                visibility="org",
                portfolio_id=group,
            )
            archived_member = make_project(
                conn,
                owner_user_id=owner.user_id,
                org_id=org_id,
                visibility="org",
                status="archived",
                portfolio_id=group,
            )
            loose = make_project(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )

        response = client.patch(
            f"/api/v1/portfolios/{group}",
            headers=owner.headers,
            json={"visibility": "private"},
        )

        assert response.status_code == 200, response.text
        assert response.json()["visibility"] == "private"
        assert _portfolio_row(engine, group)["visibility"] == "private"
        assert _row(engine, active_member)["visibility"] == "private"
        assert _row(engine, archived_member)["visibility"] == "private"
        assert _row(engine, archived_member)["status"] == "archived"
        # A project in no portfolio is unconstrained: the cascade is bounded
        # by membership, not by the owner's estate.
        assert _row(engine, loose)["visibility"] == "org"
        assert _breaches(engine, owner.user_id) == []


def test_the_cascade_reports_the_member_count_the_caller_can_see(
    engine: Engine, tmp_path: Path
) -> None:
    """The i.4 outcome number is the caller's readable set, not the write count.

    The response's `task_count` is what the outcome copy may claim (phase
    10b). It is derived per caller — read grade minus the admin leg, active
    rows only — so it can never name rows the reader cannot see. For this
    route the two coincide bar archived members: the write grade means the
    caller owns the portfolio, and a portfolio's members are always owned by
    its owner (032), so the owner reads every one of them.
    """
    with tenancy_client(tmp_path, count=1) as (client, (owner,)):
        org_id = _enrolled_owner(engine, owner)
        with seeded(engine) as conn:
            group = make_portfolio(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )
            for _ in range(2):
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
                visibility="org",
                status="archived",
                portfolio_id=group,
            )

        response = client.patch(
            f"/api/v1/portfolios/{group}",
            headers=owner.headers,
            json={"visibility": "private"},
        )

        assert response.status_code == 200, response.text
        assert response.json()["task_count"] == 2
        members = _members(engine, owner.user_id)
        # All three followed, the archived one included; only two are counted.
        assert len(members) == 3
        assert all(member["member_visibility"] == "private" for member in members)


def test_the_cascade_repairs_a_member_stamped_to_another_organisation(
    engine: Engine, tmp_path: Path
) -> None:
    """The cascade writes **both** invariant fields, so it is self-healing.

    A visibility change does not move a row between organisations, and every
    member the API itself produced already matches — i.1 inherits the
    organisation, assignment syncs it, enrolment moves a person's rows as one
    set. So this write is a no-op in normal operation.

    It is made anyway because the alternative is worse. A member that *does*
    mismatch (an operator assignment, a pre-invariant row) is a row the wrong
    organisation can reach, and the choice is between repairing it in the
    write path the owner just ran and leaving it in place for the property
    test to report afterwards. "Every member follows its portfolio" is the
    rule; the cascade makes both halves of it true.
    """
    with tenancy_client(tmp_path, count=1) as (client, (owner,)):
        org_id = _enrolled_owner(engine, owner)
        with seeded(engine) as conn:
            elsewhere = make_org(conn, name="Elsewhere")
            group = make_portfolio(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )
            stray = make_project(
                conn,
                owner_user_id=owner.user_id,
                org_id=elsewhere,
                visibility="org",
                portfolio_id=group,
            )
        assert _breaches(engine, owner.user_id) != []

        response = client.patch(
            f"/api/v1/portfolios/{group}",
            headers=owner.headers,
            json={"visibility": "private"},
        )

        assert response.status_code == 200, response.text
        assert _row(engine, stray)["org_id"] == org_id
        assert _row(engine, stray)["visibility"] == "private"
        assert _breaches(engine, owner.user_id) == []


def test_the_cascade_is_refused_to_a_colleague_and_to_an_administrator(
    engine: Engine, tmp_path: Path
) -> None:
    """Rubric 25: cascades are owner-only.

    The colleague and the administrator are seeded **in the same
    organisation**, which was the honest shape while the admin read leg did
    not exist: an administrator outside the organisation would have 404'd here
    for a reason that has nothing to do with being an administrator. An in-org
    administrator reaches the row through the org leg and is refused the
    write, and phase 8 left that unchanged. The out-of-organisation case the
    phase-6 handoff asked for is the next test down, where the refusal is a
    403 reached through the admin leg itself.

    An outsider still gets the indistinguishable 404: refusing a write is not
    a reason to confirm the row exists.
    """
    with tenancy_client(tmp_path, count=4) as (client, principals):
        owner, colleague, admin, outsider = principals
        org_id = _enrolled_owner(engine, owner)
        with seeded(engine) as conn:
            ops_enrol(
                conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague"
            )
            ops_enrol(
                conn,
                user_id=admin.user_id,
                org_id=org_id,
                display_name="Support",
                is_admin=True,
            )
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

        refusals = {
            caller.user_id: client.patch(
                f"/api/v1/portfolios/{group}",
                headers=caller.headers,
                json={"visibility": "private"},
            )
            for caller in (colleague, admin, outsider)
        }

        assert refusals[colleague.user_id].status_code == 403
        assert refusals[colleague.user_id].json()["error"]["code"] == "forbidden"
        assert refusals[admin.user_id].status_code == 403
        assert refusals[admin.user_id].json()["error"]["code"] == "forbidden"
        assert refusals[outsider.user_id].status_code == 404
        assert _portfolio_row(engine, group)["visibility"] == "org"
        assert _row(engine, member)["visibility"] == "org"


def test_the_cascade_is_refused_to_an_out_of_organisation_administrator(
    engine: Engine, tmp_path: Path
) -> None:
    """Rubric 25, re-asserted through the admin leg itself (phase 6 handoff).

    The previous case seeded the administrator *inside* the organisation, so
    the org leg could have been what reached the portfolio and the refusal
    proved nothing about `is_admin`. Here the administrator is enrolled
    elsewhere and the portfolio is **private**, so every other leg is closed:
    the admin leg is the only thing that reaches the row, and the answer is
    still 403 `forbidden`, not 200.

    That combination — reachable, unwritable — is the concrete "admin write
    escape" contract § 6 names. The cascade is the highest-value target for
    it: one write flips a Project and every Task inside it.
    """
    with tenancy_client(tmp_path, count=2) as (client, (owner, admin)):
        org_id = _enrolled_owner(engine, owner)
        with seeded(engine) as conn:
            support_org = make_org(conn, name="Support Org")
            ops_enrol(
                conn,
                user_id=admin.user_id,
                org_id=support_org,
                display_name="Support",
                is_admin=True,
            )
            group = make_portfolio(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="private"
            )
            member = make_project(
                conn,
                owner_user_id=owner.user_id,
                org_id=org_id,
                visibility="private",
                portfolio_id=group,
            )

        # Reachable: the leg really does open the row for reading.
        assert (
            client.get(f"/api/v1/portfolios/{group}", headers=admin.headers).status_code
            == 200
        )

        refusal = client.patch(
            f"/api/v1/portfolios/{group}",
            headers=admin.headers,
            json={"visibility": "org"},
        )

        assert refusal.status_code == 403
        assert refusal.json()["error"]["code"] == "forbidden"
        assert _portfolio_row(engine, group)["visibility"] == "private"
        assert _row(engine, member)["visibility"] == "private"


def test_portfolio_visibility_never_reaches_the_column_through_the_splat(
    engine: Engine, tmp_path: Path
) -> None:
    """Rubric 24. Structural, then observable.

    Structural: `visibility` is not in the route's patchable column list, so
    the `.values(**changes)` splat cannot carry it however `PortfolioUpdate`
    grows. The field now exists on that model, which is exactly when this
    assertion starts earning its keep.

    Observable: a body carrying both a rename and a visibility change applies
    both, and **the member follows**. If the field had reached the column
    through the splat the portfolio would have flipped alone — the silent
    failure i.4 exists to prevent, and the one a column-level assertion alone
    could not tell apart.
    """
    assert "visibility" not in _PATCHABLE_COLUMNS

    with tenancy_client(tmp_path, count=1) as (client, (owner,)):
        org_id = _enrolled_owner(engine, owner)
        with seeded(engine) as conn:
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
            f"/api/v1/portfolios/{group}",
            headers=owner.headers,
            json={"name": "Renamed", "visibility": "private"},
        )

        assert response.status_code == 200, response.text
        assert response.json()["name"] == "Renamed"
        assert response.json()["visibility"] == "private"
        assert _row(engine, member)["visibility"] == "private"


def test_portfolio_patch_refuses_an_explicit_null_visibility(
    engine: Engine, tmp_path: Path
) -> None:
    """`{"visibility": null}` is 422, not "leave it unchanged".

    The route reads "the caller asked for a cascade" off `visibility is not
    None`. An explicit null that validated would make that reading false for
    one body shape only, and it cannot mean anything else — the column is NOT
    NULL.
    """
    with tenancy_client(tmp_path, count=1) as (client, (owner,)):
        org_id = _enrolled_owner(engine, owner)
        with seeded(engine) as conn:
            group = make_portfolio(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )

        response = client.patch(
            f"/api/v1/portfolios/{group}", headers=owner.headers, json={"visibility": None}
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"
        assert _portfolio_row(engine, group)["visibility"] == "org"


# --- the i.5-then-i.2 loop (rubric 23) ----------------------------------------


def test_the_i5_then_i2_loop_ends_org_visible(engine: Engine, tmp_path: Path) -> None:
    """The loop rev 2.0 of the contract offered as i.5's way out, run to its end.

    Sequence: an org-visible Task inside an org-visible Project; the owner
    tries to make the Task private (**i.5**, 409); takes it out of the Project
    (**i.6** — it stays org-visible); makes it private (now unconstrained, so
    it lands); puts it back (**i.2** — promoted to org again).

    **The row ends org-visible.** That is the API's answer and it is the right
    one: assignment to an org-visible Project is an explicit act, and its
    outcome is deterministic and stated in the response. What is *not*
    available is the reading rev 2.0 offered — "remove it first" as a way to
    hold a private Task inside a shared Project. i.5's honest ways out are
    changing the Project's visibility (the i.4 cascade) and **leaving the Task
    out of the Project**, which is why the 409's message names those two and
    the screen's copy repeats them (phase 10b).

    Re-exposure is therefore not silent: it is the announced result of the
    last step. This test exists so that any future change that makes the loop
    end somewhere else has to say so out loud.
    """
    with tenancy_client(tmp_path, count=1) as (client, (owner,)):
        org_id = _enrolled_owner(engine, owner)
        with seeded(engine) as conn:
            group = make_portfolio(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )
            row = make_project(
                conn,
                owner_user_id=owner.user_id,
                org_id=org_id,
                visibility="org",
                portfolio_id=group,
            )

        blocked = client.patch(
            f"/api/v1/projects/{row}", headers=owner.headers, json={"visibility": "private"}
        )
        assert blocked.status_code == 409
        assert blocked.json()["error"]["code"] == "visibility_conflict"
        assert "leave the task out of the project" in blocked.json()["error"]["message"].lower()

        removed = client.patch(
            f"/api/v1/projects/{row}", headers=owner.headers, json={"portfolio_id": None}
        )
        assert removed.status_code == 200
        assert removed.json()["visibility"] == "org"

        privatised = client.patch(
            f"/api/v1/projects/{row}", headers=owner.headers, json={"visibility": "private"}
        )
        assert privatised.status_code == 200
        assert privatised.json()["visibility"] == "private"

        readded = client.patch(
            f"/api/v1/projects/{row}", headers=owner.headers, json={"portfolio_id": str(group)}
        )

        assert readded.status_code == 200, readded.text
        assert readded.json()["visibility"] == "org"
        assert _row(engine, row)["visibility"] == "org"
        assert _breaches(engine, owner.user_id) == []


# --- the property over all six paths (rubric 22) ------------------------------

#: Every operation the walk draws from. The six invariant paths plus the two
#: plain creates that produce the rows they act on.
_OPERATIONS = (
    "create_project",
    "create_portfolio",
    "create_portfolio_from_project",  # i.1
    "assign",  # i.2 / i.3
    "remove",  # i.6
    "cascade",  # i.4
    "set_visibility",  # i.5 when the row is in a portfolio, a plain set otherwise
)

#: How many operations the walk runs. Long enough that every operation fires
#: several times against several states (asserted at the end, so a shorter
#: walk fails loudly rather than passing thinly); short enough to stay a
#: fast test — one request and one invariant query per step.
_WALK_LENGTH = 90

#: Fixed, so a failure is reproducible from the test name alone. `hypothesis`
#: is not a dependency of this repository and this phase does not add one.
_WALK_SEED = 20260824


def _walk_step(
    client: TestClient,
    owner: Principal,
    engine: Engine,
    *,
    operation: str,
    step: int,
    rng: random.Random,
    projects: list[str],
    portfolios: list[str],
) -> None:
    """Apply one operation and assert the status code that operation must give.

    The status assertions are half the property: an operation that started
    silently 4xx-ing would otherwise leave the invariant trivially intact.

    Args:
        client: The application client.
        owner: The acting principal — the walk is one owner's estate.
        engine: The session engine, for the one state read i.5 needs.
        operation: Which of :data:`_OPERATIONS` to run.
        step: The step index, for unique names and failure messages.
        rng: The seeded generator; every choice comes from it.
        projects: Pool of project ids, extended in place by the creates.
        portfolios: Pool of portfolio ids, extended in place by the creates.
    """
    headers = owner.headers
    if operation == "create_project":
        response = client.post(
            "/api/v1/projects", headers=headers, json={"name": f"walk task {step}"}
        )
        assert response.status_code == 201, response.text
        projects.append(response.json()["project_id"])
        return
    if operation == "create_portfolio":
        response = client.post(
            "/api/v1/portfolios", headers=headers, json={"name": f"walk group {step}"}
        )
        assert response.status_code == 201, response.text
        portfolios.append(response.json()["portfolio_id"])
        return
    if operation == "create_portfolio_from_project":
        response = client.post(
            "/api/v1/portfolios",
            headers=headers,
            json={"name": f"walk seeded {step}", "from_project_id": rng.choice(projects)},
        )
        assert response.status_code == 201, response.text
        portfolios.append(response.json()["portfolio_id"])
        return
    if operation == "assign":
        response = client.patch(
            f"/api/v1/projects/{rng.choice(projects)}",
            headers=headers,
            json={"portfolio_id": rng.choice(portfolios)},
        )
        assert response.status_code == 200, response.text
        return
    if operation == "remove":
        response = client.patch(
            f"/api/v1/projects/{rng.choice(projects)}",
            headers=headers,
            json={"portfolio_id": None},
        )
        assert response.status_code == 200, response.text
        return
    if operation == "cascade":
        response = client.patch(
            f"/api/v1/portfolios/{rng.choice(portfolios)}",
            headers=headers,
            json={"visibility": rng.choice(("org", "private"))},
        )
        assert response.status_code == 200, response.text
        return
    target = rng.choice(projects)
    # i.5 is a statement about the row's state, so the expectation is read
    # from the database rather than modelled in the test: a shadow copy of
    # the state machine could agree with a broken implementation.
    in_portfolio = _row(engine, target)["portfolio_id"] is not None
    response = client.patch(
        f"/api/v1/projects/{target}",
        headers=headers,
        json={"visibility": rng.choice(("org", "private"))},
    )
    assert response.status_code == (409 if in_portfolio else 200), response.text
    if in_portfolio:
        assert response.json()["error"]["code"] == "visibility_conflict"


def test_the_invariant_holds_after_every_operation_in_a_deterministic_walk(
    engine: Engine, tmp_path: Path
) -> None:
    """Rubric 22: the property over i.1-i.6, on **both** fields.

    Not six examples. A fixed-seed walk over every operation, asserting after
    *every single one* that each of the owner's projects with a `portfolio_id`
    matches its portfolio on `visibility` and on `org_id`. Interleavings the
    examples above never reach — a cascade landing on a portfolio whose member
    arrived from i.1, a removal between two assignments, a create-from that
    steals a member out of another portfolio — are what this covers, and they
    are where an invariant written as six independent write paths breaks.

    Deterministic rather than generative: `hypothesis` is not a dependency
    here and this phase does not add one. The seed is fixed, so a failure
    reproduces exactly; the coverage assertions at the end are what stop the
    walk passing thinly.
    """
    rng = random.Random(_WALK_SEED)
    performed: Counter[str] = Counter()
    with tenancy_client(tmp_path, count=1) as (client, (owner,)):
        org_id = _enrolled_owner(engine, owner)
        with seeded(engine) as conn:
            projects = [
                str(
                    make_project(
                        conn,
                        owner_user_id=owner.user_id,
                        org_id=org_id,
                        visibility=visibility,
                    )
                )
                for visibility in ("org", "private", "org")
            ]
            portfolios = [
                str(
                    make_portfolio(
                        conn,
                        owner_user_id=owner.user_id,
                        org_id=org_id,
                        visibility=visibility,
                    )
                )
                for visibility in ("org", "private")
            ]

        widest_membership = 0
        for step in range(_WALK_LENGTH):
            operation = rng.choice(_OPERATIONS)
            performed[operation] += 1
            _walk_step(
                client,
                owner,
                engine,
                operation=operation,
                step=step,
                rng=rng,
                projects=projects,
                portfolios=portfolios,
            )
            members = _members(engine, owner.user_id)
            widest_membership = max(widest_membership, len(members))
            breached = [dict(member) for member in members if member["breached"]]
            assert breached == [], f"step {step} ({operation}) broke the invariant: {breached}"

        # Non-vacuity. An invariant over an empty set holds for the wrong
        # reason, and every operation must have actually run.
        assert set(performed) == set(_OPERATIONS), performed
        assert widest_membership >= 2, widest_membership
