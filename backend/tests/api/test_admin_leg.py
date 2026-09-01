"""The administrator read leg, its trace, and the closed list of flag readers.

Contract § 3, § 3a and § 4; rubric 15–18. Every behavioural case drives a real
route through the real application (the `test_route_grades.py` idiom), seeded
through `org_support`, with the administrator deliberately **outside** every
organisation the rows belong to — an in-organisation administrator would reach
half of these rows through the org leg and prove nothing about `is_admin`.

**What is asserted about the trace is content and grain, never transport.**
`create_app` configures structured logging (Phase 0b), and Phase 12 confirms
one line of each kind reaches CloudWatch; here `structlog.testing.capture_logs`
intercepts the processor chain, so what these cases pin is *which* lines are
emitted, *how many*, and *what they carry*.

Three shapes exist, and the difference between them is the whole of § 3a's
"one line per read is meaningless for a listing":

- `admin_read` — one per row the admin leg resolved (project, portfolio or
  conversation), including the row an SSE subscribe resolves.
- `admin_listing` — one per listing or search **request** served across
  organisations, carrying the filter, the page and the row count. A zero-result
  search still emits.
- `admin_stream_read` — one per SSE re-authorisation batch the leg carried.

And one negative, which is the property that makes the log an audit trail of
the privilege rather than of the traffic: **a read the caller was already
entitled to emits nothing at all.**

`capture_logs()` is always entered **after** the client exists: `create_app`
calls `configure_logging()`, which reconfigures structlog globally, so
capturing first would have the app's own configuration replace the capture
chain and every assertion below would pass vacuously against an empty list.
"""

from __future__ import annotations

import ast
import uuid
from collections.abc import Callable, MutableMapping, Sequence
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.engine import Engine
from structlog.testing import capture_logs

import policy_atlas.api
from policy_atlas.core.schema import app_user
from tests.api.org_support import (
    make_conversation,
    make_org,
    make_portfolio,
    make_project,
    ops_enrol,
    seeded,
    tenancy_client,
    unique_email,
)

# --- trace helpers ------------------------------------------------------------


def _lines(
    captured: Sequence[MutableMapping[str, Any]], event: str
) -> list[MutableMapping[str, Any]]:
    """Every captured entry with one event name, in emission order."""
    return [entry for entry in captured if entry.get("event") == event]


def _reads(captured: Sequence[MutableMapping[str, Any]]) -> list[tuple[str, str]]:
    """The `(kind, row_id)` pairs of every `admin_read` line."""
    return [(entry["kind"], entry["row_id"]) for entry in _lines(captured, "admin_read")]


# --- reading across organisations (rubric 15, 17) -----------------------------


def test_administrator_reads_org_visible_and_private_rows_in_a_foreign_organisation(
    engine: Engine, tmp_path: Path
) -> None:
    """The contract's headline admin case, plus its per-row trace grain.

    An administrator enrolled in organisation B reads, in organisation A: an
    org-visible project, a **private** project, an org-visible portfolio, a
    private portfolio, and — through the conversation-id router (§ 4) — a chat
    they did not create, both as `GET /{id}` and as `GET /{id}/turns`.

    Six requests, six `admin_read` lines: one per row read, each naming the
    administrator, the row kind and the row id. Nothing else is logged, which
    is what makes "one line per row" a grain rather than a lower bound.
    """
    with tenancy_client(tmp_path, count=2) as (client, (owner, admin)):
        with seeded(engine) as conn:
            org_a = make_org(conn, name="Owner Org")
            org_b = make_org(conn, name="Support Org")
            ops_enrol(conn, user_id=owner.user_id, org_id=org_a, display_name="Owner")
            ops_enrol(
                conn,
                user_id=admin.user_id,
                org_id=org_b,
                display_name="Support",
                is_admin=True,
            )
            shared = make_project(
                conn, owner_user_id=owner.user_id, org_id=org_a, visibility="org"
            )
            secret = make_project(
                conn, owner_user_id=owner.user_id, org_id=org_a, visibility="private"
            )
            shared_group = make_portfolio(
                conn, owner_user_id=owner.user_id, org_id=org_a, visibility="org"
            )
            secret_group = make_portfolio(
                conn, owner_user_id=owner.user_id, org_id=org_a, visibility="private"
            )
            chat = make_conversation(
                conn, project_id=secret, kind="chat", created_by=owner.user_id
            )

        with capture_logs() as captured:
            responses = [
                client.get(f"/api/v1/projects/{shared}", headers=admin.headers),
                client.get(f"/api/v1/projects/{secret}", headers=admin.headers),
                client.get(f"/api/v1/portfolios/{shared_group}", headers=admin.headers),
                client.get(f"/api/v1/portfolios/{secret_group}", headers=admin.headers),
                client.get(f"/api/v1/conversations/{chat}", headers=admin.headers),
                client.get(f"/api/v1/conversations/{chat}/turns", headers=admin.headers),
            ]

        assert [response.status_code for response in responses] == [200] * 6
        # The private rows really are private: the leg, not the org, reached them.
        assert responses[1].json()["visibility"] == "private"
        assert responses[3].json()["visibility"] == "private"
        assert _reads(captured) == [
            ("project", str(shared)),
            ("project", str(secret)),
            ("portfolio", str(shared_group)),
            ("portfolio", str(secret_group)),
            ("conversation", str(chat)),
            ("conversation", str(chat)),
        ]
        assert {entry["user_id"] for entry in _lines(captured, "admin_read")} == {
            admin.user_id
        }


def test_administrator_reads_a_null_organisation_row_and_an_ownerless_one(
    engine: Engine, tmp_path: Path
) -> None:
    """Contract § 11: the wider list includes rows with no owning organisation.

    Two shapes nobody else can reach — an unenrolled person's row (`org_id
    IS NULL`, its `visibility='org'` inert) and a `runtime/orchestrate.py` row
    with no owner at all. The latter amends the deferred "pre-025 rows are
    unreachable" posture, so it is pinned rather than assumed.
    """
    with tenancy_client(tmp_path, count=2) as (client, (loner, admin)):
        with seeded(engine) as conn:
            org_b = make_org(conn, name="Support Org")
            ops_enrol(conn, user_id=loner.user_id, org_id=None, display_name="Loner")
            ops_enrol(
                conn,
                user_id=admin.user_id,
                org_id=org_b,
                display_name="Support",
                is_admin=True,
            )
            unenrolled = make_project(conn, owner_user_id=loner.user_id, org_id=None)
            ownerless = make_project(conn, owner_user_id=None, org_id=None)

        with capture_logs() as captured:
            reachable = client.get(
                f"/api/v1/projects/{unenrolled}", headers=admin.headers
            )
            cli_row = client.get(f"/api/v1/projects/{ownerless}", headers=admin.headers)

        assert reachable.status_code == 200
        assert cli_row.status_code == 200
        assert reachable.json()["is_owner"] is False
        assert cli_row.json()["owner_display"] is None
        assert _reads(captured) == [
            ("project", str(unenrolled)),
            ("project", str(ownerless)),
        ]


def test_reads_the_caller_was_already_entitled_to_emit_no_trace_line(
    engine: Engine, tmp_path: Path
) -> None:
    """The negative half of the grain, and the one that makes the log useful.

    Three reads that need no privilege: the owner opening their own row, a
    same-organisation colleague opening an org-visible row, and — the case a
    naive implementation gets wrong — **the administrator opening their own
    row**, and an org-visible row in their own organisation. All four resolve
    on the owner or org leg, so the admin leg served none of them and the
    trace stays empty.
    """
    with tenancy_client(tmp_path, count=3) as (client, (owner, colleague, admin)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
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
            theirs = make_project(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )
            admins_own = make_project(
                conn, owner_user_id=admin.user_id, org_id=org_id, visibility="private"
            )

        with capture_logs() as captured:
            statuses = [
                client.get(f"/api/v1/projects/{theirs}", headers=owner.headers),
                client.get(f"/api/v1/projects/{theirs}", headers=colleague.headers),
                client.get(f"/api/v1/projects/{admins_own}", headers=admin.headers),
                client.get(f"/api/v1/projects/{theirs}", headers=admin.headers),
            ]

        assert [response.status_code for response in statuses] == [200] * 4
        assert _reads(captured) == []
        assert _lines(captured, "admin_listing") == []


# --- read only, no exceptions (rubric 15) -------------------------------------


def test_an_administrator_is_refused_every_mutation(
    engine: Engine, tmp_path: Path
) -> None:
    """Rubric 15. Read is the whole grade; every write path refuses.

    Two refusal codes, and the difference is which grade the route resolves
    through — recorded here rather than asserted loosely, because a reviewer
    reading "an admin is refused every mutation" will want to know what a
    refusal looks like:

    - **403 `forbidden`** on the project/portfolio write grade. The admin leg
      is a read leg: it reaches the row, and then the owner-only write check
      refuses. The 403 is honest — the leg already disclosed the row.
    - **404** on every chat path. Those resolve through `own_estate` /
      `own_chat_leg`, which have no admin leg **by design** (contract § 3: an
      administrator is not a colleague), so an out-of-organisation
      administrator fails the grade outright and is told nothing.

    The trace follows the same split, and that is the assertion that would
    fail if a chat path were ever widened: exactly one `admin_read` per
    403 — the leg disclosed that row — and **none at all** for the 404s.
    """
    with tenancy_client(tmp_path, count=2) as (client, (owner, admin)):
        with seeded(engine) as conn:
            org_a = make_org(conn, name="Owner Org")
            org_b = make_org(conn, name="Support Org")
            ops_enrol(conn, user_id=owner.user_id, org_id=org_a, display_name="Owner")
            ops_enrol(
                conn,
                user_id=admin.user_id,
                org_id=org_b,
                display_name="Support",
                is_admin=True,
            )
            group = make_portfolio(
                conn, owner_user_id=owner.user_id, org_id=org_a, visibility="org"
            )
            project_id = make_project(
                conn, owner_user_id=owner.user_id, org_id=org_a, visibility="org"
            )
            chat = make_conversation(
                conn, project_id=project_id, kind="chat", created_by=owner.user_id
            )

        with capture_logs() as captured:
            forbidden = {
                "patch project": client.patch(
                    f"/api/v1/projects/{project_id}",
                    headers=admin.headers,
                    json={"name": "Renamed by support"},
                ),
                "archive project": client.post(
                    f"/api/v1/projects/{project_id}/archive", headers=admin.headers
                ),
                "cascade portfolio": client.patch(
                    f"/api/v1/portfolios/{group}",
                    headers=admin.headers,
                    json={"visibility": "private"},
                ),
                "respond to check-in": client.post(
                    f"/api/v1/projects/{project_id}/check-ins/{uuid.uuid4()}/response",
                    headers=admin.headers,
                    json={"kind": "abort"},
                ),
                "patch plan": client.patch(
                    f"/api/v1/projects/{project_id}/plan", headers=admin.headers, json={}
                ),
                "create run": client.post(
                    f"/api/v1/projects/{project_id}/runs", headers=admin.headers, json={}
                ),
                "planning turn": client.post(
                    f"/api/v1/projects/{project_id}/planning-turns",
                    headers=admin.headers,
                    json={"message": "Hello", "client_turn_id": str(uuid.uuid4())},
                ),
            }
            forbidden_reads = len(_reads(captured))
            untold = {
                "create conversation": client.post(
                    f"/api/v1/projects/{project_id}/conversations",
                    headers=admin.headers,
                    json={},
                ),
                "post turn": client.post(
                    f"/api/v1/conversations/{chat}/turns",
                    headers=admin.headers,
                    json={"message": "Hello", "client_turn_id": str(uuid.uuid4())},
                ),
                "cancel turn": client.post(
                    f"/api/v1/conversations/{chat}/turns/{uuid.uuid4()}/cancel",
                    headers=admin.headers,
                ),
                "rename conversation": client.patch(
                    f"/api/v1/conversations/{chat}",
                    headers=admin.headers,
                    json={"title": "Renamed by support"},
                ),
                "archive conversation": client.post(
                    f"/api/v1/conversations/{chat}/archive", headers=admin.headers
                ),
                "unarchive conversation": client.post(
                    f"/api/v1/conversations/{chat}/unarchive", headers=admin.headers
                ),
            }

        assert {name: response.status_code for name, response in forbidden.items()} == {
            name: 403 for name in forbidden
        }
        assert {response.json()["error"]["code"] for response in forbidden.values()} == {
            "forbidden"
        }
        assert {name: response.status_code for name, response in untold.items()} == {
            name: 404 for name in untold
        }
        # One disclosure line per 403, and not one more once the chat paths run.
        assert forbidden_reads == len(forbidden)
        assert len(_reads(captured)) == len(forbidden)

        # Nothing was written by any of it, read back through the owner.
        row = client.get(f"/api/v1/projects/{project_id}", headers=owner.headers).json()
        group_row = client.get(
            f"/api/v1/portfolios/{group}", headers=owner.headers
        ).json()
        assert row["name"] != "Renamed by support"
        assert row["status"] == "active"
        assert group_row["visibility"] == "org"


def test_an_administrator_cannot_write_through_the_conversation_id_router(
    engine: Engine, tmp_path: Path
) -> None:
    """Contract § 4: read `GET /{id}` and `GET /{id}/turns`, write none of them.

    The same conversation, the same administrator, in one breath: the two read
    routes succeed and are traced; `PATCH`, `archive` and `unarchive` 404. The
    router's write grade is the creator/owner predicate with **no** admin leg
    disjoined into it, and the 404 (rather than a 403) is this router's
    standing rule — it has no readable-but-not-writable code to spend, and a
    refused write is not a reason to confirm a row exists.
    """
    with tenancy_client(tmp_path, count=2) as (client, (owner, admin)):
        with seeded(engine) as conn:
            org_a = make_org(conn, name="Owner Org")
            org_b = make_org(conn, name="Support Org")
            ops_enrol(conn, user_id=owner.user_id, org_id=org_a, display_name="Owner")
            ops_enrol(
                conn,
                user_id=admin.user_id,
                org_id=org_b,
                display_name="Support",
                is_admin=True,
            )
            project_id = make_project(
                conn, owner_user_id=owner.user_id, org_id=org_a, visibility="private"
            )
            chat = make_conversation(
                conn, project_id=project_id, kind="chat", created_by=owner.user_id
            )
            planning = make_conversation(
                conn, project_id=project_id, kind="planning", created_by=None
            )

        with capture_logs() as captured:
            reads = [
                client.get(f"/api/v1/conversations/{chat}", headers=admin.headers),
                client.get(f"/api/v1/conversations/{chat}/turns", headers=admin.headers),
                # Planning conversations are the owner's steering, and the leg
                # reads them too: § 4 grades this router by route, not by kind.
                client.get(f"/api/v1/conversations/{planning}", headers=admin.headers),
            ]
            writes = [
                client.patch(
                    f"/api/v1/conversations/{chat}",
                    headers=admin.headers,
                    json={"title": "Renamed"},
                ),
                client.post(
                    f"/api/v1/conversations/{chat}/archive", headers=admin.headers
                ),
                client.post(
                    f"/api/v1/conversations/{chat}/unarchive", headers=admin.headers
                ),
            ]

        assert [response.status_code for response in reads] == [200, 200, 200]
        assert [response.status_code for response in writes] == [404, 404, 404]
        assert _reads(captured) == [
            ("conversation", str(chat)),
            ("conversation", str(chat)),
            ("conversation", str(planning)),
        ]


# --- listings and searches (rubric 17) ----------------------------------------


def test_administrator_listing_spans_organisations_and_emits_one_line_per_request(
    engine: Engine, tmp_path: Path
) -> None:
    """`scope=all` for an administrator is every row in every organisation.

    The assertion is made through `owner_email` rather than a bare page,
    because the test database is shared across the whole suite and a global
    listing's contents are not this test's to predict. The filter is pointed
    at **one address held by two `app_user` rows** — legitimate, since
    `app_user.email` carries no unique constraint (contract § 3b names the
    staleness that makes duplicates possible) — one enrolled in organisation
    A and one enrolled nowhere. So a single request must return an
    org-visible row, a `private` row *and* a NULL-`org_id` row, which is
    exactly "spans organisations, private and unowned rows included".

    One request, one `admin_listing` line, carrying the scope, the address,
    the page and the counts.
    """
    address = unique_email("shared")
    with tenancy_client(tmp_path, count=3) as (client, (owner, loner, admin)):
        with seeded(engine) as conn:
            org_a = make_org(conn, name="Owner Org")
            org_b = make_org(conn, name="Support Org")
            ops_enrol(
                conn,
                user_id=owner.user_id,
                org_id=org_a,
                display_name="Owner",
                email=address,
            )
            ops_enrol(
                conn,
                user_id=loner.user_id,
                org_id=None,
                display_name="Loner",
                email=address,
            )
            ops_enrol(
                conn,
                user_id=admin.user_id,
                org_id=org_b,
                display_name="Support",
                email=unique_email("support"),
                is_admin=True,
            )
            shared = make_project(
                conn, owner_user_id=owner.user_id, org_id=org_a, visibility="org"
            )
            secret = make_project(
                conn, owner_user_id=owner.user_id, org_id=org_a, visibility="private"
            )
            unenrolled = make_project(conn, owner_user_id=loner.user_id, org_id=None)

        with capture_logs() as captured:
            response = client.get(
                f"/api/v1/projects?owner_email={address}", headers=admin.headers
            )

        assert response.status_code == 200
        body = response.json()
        assert {row["project_id"] for row in body["data"]} == {
            str(shared),
            str(secret),
            str(unenrolled),
        }
        assert _lines(captured, "admin_listing") == [
            {
                "event": "admin_listing",
                "log_level": "info",
                "user_id": admin.user_id,
                "kind": "project",
                "scope": "all",
                "owner_email": address,
                "page": 1,
                "page_size": 50,
                "row_count": 3,
                "total_items": 3,
            }
        ]
        # A listing is one line per *request*, never one per row.
        assert _reads(captured) == []


def test_scope_mine_is_not_the_admin_leg_and_emits_nothing(
    engine: Engine, tmp_path: Path
) -> None:
    """An administrator asking for their own rows is an ordinary caller.

    `scope=mine` is the owner column and nothing else, so no widening happens
    and there is nothing to record. The same administrator's `scope=all` in
    the same breath *does* widen and *does* emit, which is what stops this
    passing merely because the trace was broken.

    The `scope=all` half is narrowed by `portfolio_id` so it asserts an exact
    set: the test database is shared across the suite **and across runs**, so
    an unfiltered global page is not this test's to predict. The `scope=mine`
    half needs no such care — it asserts an *absence*, and no amount of paging
    can add a row to a page.
    """
    with tenancy_client(tmp_path, count=2) as (client, (owner, admin)):
        with seeded(engine) as conn:
            org_a = make_org(conn, name="Owner Org")
            org_b = make_org(conn, name="Support Org")
            ops_enrol(conn, user_id=owner.user_id, org_id=org_a, display_name="Owner")
            ops_enrol(
                conn,
                user_id=admin.user_id,
                org_id=org_b,
                display_name="Support",
                is_admin=True,
            )
            group = make_portfolio(
                conn, owner_user_id=owner.user_id, org_id=org_a, visibility="private"
            )
            theirs = make_project(
                conn,
                owner_user_id=owner.user_id,
                org_id=org_a,
                visibility="private",
                portfolio_id=group,
            )

        with capture_logs() as mine_captured:
            narrow = client.get(
                f"/api/v1/projects?scope=mine&portfolio_id={group}",
                headers=admin.headers,
            )
        with capture_logs() as all_captured:
            wide = client.get(
                f"/api/v1/projects?scope=all&portfolio_id={group}",
                headers=admin.headers,
            )

        assert narrow.json()["data"] == []
        assert _lines(mine_captured, "admin_listing") == []

        assert {row["project_id"] for row in wide.json()["data"]} == {str(theirs)}
        assert len(_lines(all_captured, "admin_listing")) == 1
        assert _lines(all_captured, "admin_listing")[0]["scope"] == "all"
        assert _lines(all_captured, "admin_listing")[0]["owner_email"] is None


def test_a_zero_result_administrator_search_still_emits_its_line(
    engine: Engine, tmp_path: Path
) -> None:
    """Rubric 17's exact case, and the reason the request grain exists.

    An address that owns nothing returns an empty page rather than a 404, so
    the status code cannot be used to learn whether an address is known to the
    system. An unlogged empty page would restore that oracle in a form nobody
    can see — so the zero-row request is precisely the one that must be
    recorded. Asserted on both listings, because both carry the filter.
    """
    nobody = unique_email("nobody")
    with tenancy_client(tmp_path, count=1) as (client, (admin,)):
        with seeded(engine) as conn:
            org_id = make_org(conn, name="Support Org")
            ops_enrol(
                conn,
                user_id=admin.user_id,
                org_id=org_id,
                display_name="Support",
                email=unique_email("support"),
                is_admin=True,
            )

        with capture_logs() as captured:
            projects = client.get(
                f"/api/v1/projects?owner_email={nobody}", headers=admin.headers
            )
            portfolios = client.get(
                f"/api/v1/portfolios?owner_email={nobody}", headers=admin.headers
            )

        assert projects.status_code == 200
        assert portfolios.status_code == 200
        assert projects.json()["data"] == []
        assert portfolios.json()["data"] == []
        emitted = _lines(captured, "admin_listing")
        assert [(entry["kind"], entry["row_count"], entry["total_items"]) for entry in emitted] == [
            ("project", 0, 0),
            ("portfolio", 0, 0),
        ]
        assert {entry["owner_email"] for entry in emitted} == {nobody}


def test_an_admin_read_line_says_which_request_produced_it(
    engine: Engine, tmp_path: Path
) -> None:
    """Two reads of the same row are two different actions, and the line must say which.

    `admin_read` carried a `kind` and a `row_id` and nothing else, so opening a
    project card and reading a colleague's whole chat transcript looked
    identical in the trail — and the trail is the admin leg's only control
    while the privacy notice stands unedited (contract § 12). A request-scoped
    `structlog` context supplies the missing half.

    The keys are asserted *through the emission site that already existed*:
    nothing in `_access.py` was edited to carry them, because
    `merge_contextvars` is first in the processor chain. `capture_logs` is
    given that processor explicitly — it replaces the configured chain, so
    without it the context is invisible to the capture and this would pass
    against an unbound request.
    """
    with tenancy_client(tmp_path, count=2) as (client, (owner, admin)):
        with seeded(engine) as conn:
            ops_enrol(
                conn,
                user_id=owner.user_id,
                org_id=make_org(conn),
                display_name="Owner",
            )
            ops_enrol(
                conn,
                user_id=admin.user_id,
                org_id=make_org(conn, name="Support Org"),
                display_name="Support",
                is_admin=True,
            )
            project_id = make_project(
                conn, owner_user_id=owner.user_id, org_id=None, visibility="private"
            )
            chat_id = make_conversation(
                conn, project_id=project_id, created_by=owner.user_id
            )

        with capture_logs(
            processors=[structlog.contextvars.merge_contextvars]
        ) as captured:
            card = client.get(f"/api/v1/projects/{project_id}", headers=admin.headers)
            transcript = client.get(
                f"/api/v1/conversations/{chat_id}/turns", headers=admin.headers
            )

        assert card.status_code == 200
        assert transcript.status_code == 200
        lines = _lines(captured, "admin_read")
        assert [(entry["kind"], entry["route"]) for entry in lines] == [
            ("project", "/api/v1/projects/{project_id}"),
            ("conversation", "/api/v1/conversations/{conversation_id}/turns"),
        ]
        assert {entry["http_method"] for entry in lines} == {"GET"}
        # One request id per request, and never the same one twice.
        assert len({entry["request_id"] for entry in lines}) == 2


def test_an_unbounded_or_shapeless_owner_email_never_reaches_the_audit_line(
    engine: Engine, tmp_path: Path
) -> None:
    """The filter is bounded and shaped at the boundary, because the log is verbatim.

    `trace_admin_listing` writes `owner_email` exactly as received — it must,
    or the line cannot say what was searched for — and the admin trace is the
    only control the privileged read has while the privacy notice stands
    unedited (contract § 12). An unbounded query parameter is therefore
    unbounded input into that trail, and the way to keep it out is to refuse
    the request rather than to trim the line.

    Both refusals are 422 `validation_error`, the same code and status a
    non-administrator gets for passing the filter at all: all three are "your
    parameter is wrong", and inventing a fourth semantic for one query
    parameter would buy nothing. Neither refusal emits a line, because neither
    request was served.
    """
    with tenancy_client(tmp_path, count=1) as (client, (admin,)):
        with seeded(engine) as conn:
            ops_enrol(
                conn,
                user_id=admin.user_id,
                org_id=make_org(conn, name="Support Org"),
                display_name="Support",
                email=unique_email("support"),
                is_admin=True,
            )

        too_long = f"{'a' * 250}@example.test"
        with capture_logs() as captured:
            over = client.get(
                f"/api/v1/projects?owner_email={too_long}", headers=admin.headers
            )
            shapeless = client.get(
                "/api/v1/portfolios?owner_email=not-an-address", headers=admin.headers
            )
            at_the_bound = client.get(
                f"/api/v1/projects?owner_email={'a' * 241}@example.test",
                headers=admin.headers,
            )

        assert over.status_code == 422
        assert over.json()["error"]["code"] == "validation_error"
        assert shapeless.status_code == 422
        assert shapeless.json()["error"]["code"] == "validation_error"
        # The bound refuses nothing anyone could be looking for: 254 characters
        # is the longest deliverable address, and one of them is served.
        assert at_the_bound.status_code == 200
        assert at_the_bound.json()["data"] == []

        emitted = _lines(captured, "admin_listing")
        assert [entry["owner_email"] for entry in emitted] == ["a" * 241 + "@example.test"]


def test_a_non_administrators_listing_is_never_traced(
    engine: Engine, tmp_path: Path
) -> None:
    """`scope=all` is the default every caller uses; only the leg is recorded."""
    with tenancy_client(tmp_path, count=2) as (client, (owner, colleague)):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id, display_name="Owner")
            ops_enrol(
                conn, user_id=colleague.user_id, org_id=org_id, display_name="Colleague"
            )
            make_project(
                conn, owner_user_id=owner.user_id, org_id=org_id, visibility="org"
            )

        with capture_logs() as captured:
            client.get("/api/v1/projects", headers=colleague.headers)
            client.get("/api/v1/portfolios", headers=colleague.headers)

        assert _lines(captured, "admin_listing") == []
        assert _reads(captured) == []


# --- the flag itself (rubric 16, 18) ------------------------------------------


def test_is_admin_defaults_false_on_a_bare_me_provisioned_row(
    engine: Engine, tmp_path: Path
) -> None:
    """Rubric 18, at the column. `/me` never writes the field at all.

    The provisioning insert names `user_id`, `display_name` and `created_at`
    and nothing else, so what makes a newly provisioned caller a non-
    administrator is the schema's `NOT NULL DEFAULT false` — asserted against
    the stored row, not the projection, because the projection would be
    equally `False` if the column defaulted NULL and Pydantic coerced it.
    """
    with tenancy_client(tmp_path, count=1) as (client, (caller,)):
        assert client.get("/api/v1/me", headers=caller.headers).status_code == 200

        with seeded(engine) as conn:
            stored = conn.execute(
                select(app_user.c.is_admin).where(app_user.c.user_id == caller.user_id)
            ).scalar_one()

        assert stored is False


def test_no_write_under_the_api_can_set_is_admin() -> None:
    """Rubric 18, at the API. The flag is ops-owned; no HTTP path writes it.

    Structural, because the exhaustive behavioural version is "post
    `is_admin` to every route in the tree". Every column an insert or update
    writes in this codebase arrives through a `.values(...)` call, so the
    assertion is that **no `.values(...)` under `api/` names the column** —
    including `/me`'s provisioning upsert, which lists three columns and this
    is not one of them. The CLI (Phase 9b, outside `api/`) is the legitimate
    writer.

    The only `is_admin=` keyword left under `api/` is `get_me` building the
    **response** model, and it is named here rather than filtered silently:
    reading the flag back to its own holder is reader (iv), not a write.

    The behavioural half is pinned next door: `/me`'s upsert is `ON CONFLICT
    DO NOTHING`, so repeated sign-ins cannot clear an ops-set flag
    (`test_me_is_idempotent_and_never_clobbers_ops_set_fields`).
    """
    root = Path(policy_atlas.api.__file__).parent
    writes: list[str] = []
    keywords: list[str] = []
    for path in _api_modules():
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.Call):
                continue
            named = [keyword.arg for keyword in node.keywords]
            if "is_admin" not in named:
                continue
            site = f"{path.relative_to(root)}::{node.lineno}"
            keywords.append(site)
            if isinstance(node.func, ast.Attribute) and node.func.attr == "values":
                writes.append(site)

    assert writes == []
    assert [site.split("::")[0] for site in keywords] == ["routers/me.py"]
    assert all(
        isinstance(node.func, ast.Name) and node.func.id == "MeOut"
        for path in _api_modules()
        for node in ast.walk(ast.parse(path.read_text()))
        if isinstance(node, ast.Call)
        and "is_admin" in [keyword.arg for keyword in node.keywords]
    )


#: Every code site under `api/` that references `is_admin`, as
#: `module path -> enclosing scope`. Contract § 3a names **four semantic
#: readers**; this is what they are in code, and the mapping between the two
#: lists is deliberate rather than incidental:
#:
#: - `routers/_access.py::admin_read_leg` — the SQL leg. Serves reader **(i)**
#:   the row-access helper's admin leg *and* reader **(ii)** the listing scope
#:   resolver, because both resolve through `_read_legs`, which is the one
#:   seam the leg attaches to.
#: - `routers/_access.py::_is_admin` — the same question asked in Python.
#:   Serves reader **(iii)** the `owner_email` gate (which must raise 422) and
#:   the trace decision inside reader **(ii)** (which must know whether the
#:   request owes an audit line). Neither can be answered by a SQL leg.
#: - `routers/me.py::get_me` — reader **(iv)**, the caller's own row projected
#:   back to the caller. Decides no access.
#: - `contract/tenancy.py::MeOut` — not a reader at all: the field declaration
#:   `get_me` fills in. Named here because an honest closed list enumerates
#:   what the code *contains*, and pretending a field declaration is invisible
#:   would make the assertion weaker, not cleaner.
#:
#: A fifth entry is a defect, and the most likely fifth entry is a write path.
_IS_ADMIN_READERS = {
    "routers/_access.py": {"admin_read_leg", "_is_admin"},
    "routers/me.py": {"get_me"},
    "contract/tenancy.py": {"MeOut"},
}


def _api_modules() -> list[Path]:
    """Every Python module under `policy_atlas/api/`, located from the package."""
    root = Path(policy_atlas.api.__file__).parent
    return sorted(root.rglob("*.py"))


def _scopes_where(path: Path, references: Callable[[ast.AST, ast.Module], bool]) -> set[str]:
    """Names of the scopes in one module holding a node `references` accepts.

    Args:
        path: The module to parse.
        references: Predicate over a node and the parsed module it came from.

    Returns:
        The innermost enclosing `def`/`class` name of each accepted node, or
        `"<module>"` for one at module level.
    """
    tree = ast.parse(path.read_text())
    found: set[str] = set()

    def walk(node: ast.AST, scope: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(
                child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                if references(child, tree):
                    found.add(scope or "<module>")
                walk(child, f"{scope}.{child.name}" if scope else child.name)
                continue
            if references(child, tree):
                found.add(scope or "<module>")
            walk(child, scope)

    walk(tree, "")
    return found


def _scopes_mentioning(path: Path, name: str) -> set[str]:
    """Names of the scopes in one module that reference `name`.

    A reference is an attribute (`app_user.c.is_admin`), a bare name, a
    keyword argument, a parameter, or a string constant **equal** to the name
    — the last catching `getattr(app_user.c, "is_admin")` and
    `row["is_admin"]`. A docstring that merely mentions the flag is never
    equal to it, so prose does not register.

    Args:
        path: The module to parse.
        name: The identifier to look for.

    Returns:
        The innermost enclosing `def`/`class` name of each reference, or
        `"<module>"` for one at module level.
    """

    def references(node: ast.AST, _tree: ast.Module) -> bool:
        if isinstance(node, ast.Attribute):
            return node.attr == name
        if isinstance(node, ast.Name):
            return node.id == name
        if isinstance(node, ast.keyword):
            return node.arg == name
        if isinstance(node, ast.arg):
            return node.arg == name
        if isinstance(node, ast.Constant):
            return isinstance(node.value, str) and node.value == name
        return False

    return _scopes_where(path, references)


def _prose_strings(tree: ast.Module) -> set[int]:
    """The `id()`s of every string constant that is a whole statement.

    Docstrings and the free-standing prose blocks this codebase uses under
    attributes. A string used as a *value* — an argument, a subscript, an
    element — is code and is never in here.
    """
    return {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }


def _scopes_with_a_string_containing(path: Path, name: str) -> set[str]:
    """Names of the scopes whose *code* strings contain `name` as a substring.

    The gap :func:`_scopes_mentioning` leaves. It matches string constants by
    equality, so `text("SELECT ... WHERE is_admin ...")` — the most plausible
    way a future edit reaches this column outside the named helpers, and the
    one way that bypasses SQLAlchemy's column objects entirely — is a string
    the flag's name is merely *inside* and registers nowhere.

    Prose is excluded the way the equality check excluded it for free: a
    string constant that is a whole statement is a docstring or a comment
    block, and this module's own docstrings discuss `is_admin` at length. A
    string passed as an argument is code.

    Args:
        path: The module to parse.
        name: The identifier to look for inside string literals.

    Returns:
        The innermost enclosing `def`/`class` name of each occurrence.
    """

    def references(node: ast.AST, tree: ast.Module) -> bool:
        return (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and name in node.value
            and id(node) not in _prose_strings(tree)
        )

    return _scopes_where(path, references)


def test_only_the_named_code_sites_read_the_is_admin_flag() -> None:
    """Rubric 16, asserted against a closed list rather than "nowhere else".

    Rev 2.0 of the contract claimed the access helper was the only reader
    while simultaneously requiring two listings to consult the flag, so the
    assertion it implied could never have held. Rev 3.0 names the readers, and
    this walks `api/` to check the code agrees — module by module, scope by
    scope, so *adding* a reader fails as loudly as moving one.

    Deliberately not scoped to the helper: the point is that nothing in the
    other twenty-odd modules under `api/` touches the column, which is only
    demonstrable by looking at all of them.
    """
    root = Path(policy_atlas.api.__file__).parent
    actual = {
        str(path.relative_to(root)): scopes
        for path in _api_modules()
        if (scopes := _scopes_mentioning(path, "is_admin"))
    }

    assert actual == _IS_ADMIN_READERS


def test_no_raw_sql_string_reaches_the_is_admin_flag_behind_the_walk() -> None:
    """The closed list again, against the one spelling equality cannot see.

    The walk above matches string constants by equality, which catches
    `row["is_admin"]` and misses `text("… WHERE is_admin …")` — a longer
    string the name is merely inside. That is not a hypothetical spelling:
    this codebase already uses `sa.text` for the statements SQLAlchemy's
    column objects cannot express, and a raw statement is precisely how a
    fifth reader would arrive without touching `app_user.c.is_admin` at all.

    So the same closed list is asserted a second way. Today the only code
    string containing the name is `get_me`'s `row["is_admin"]`, which both
    walks see; the value of this one is what it will say the day the two lists
    stop agreeing.

    Docstrings are excluded, and deliberately not by an allowlist: a string
    that *is* a statement is prose, and this package's docstrings discuss the
    flag on nearly every page.
    """
    root = Path(policy_atlas.api.__file__).parent
    actual = {
        str(path.relative_to(root)): scopes
        for path in _api_modules()
        if (scopes := _scopes_with_a_string_containing(path, "is_admin"))
    }

    assert actual == {"routers/me.py": {"get_me"}}
