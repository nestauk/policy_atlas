"""Private contract-projection helpers shared by API routers.

The owner-only row helpers this module used to carry (``owned_task``,
``owned_project``, ``_owned_conversation``) are gone: every task-,
project- and conversation-scoped route now resolves through the graded
helpers in ``_access`` (task 033). What is left is projection and display.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal, cast

from sqlalchemy import case, func, select
from sqlalchemy.engine import Connection, RowMapping

from policy_atlas.api.contract import LatestRun, RunOut, TaskLinkOut, TaskOut
from policy_atlas.api.identity import owner_display_for
from policy_atlas.api.routers._access import readable_task_leg
from policy_atlas.core.schema import (
    app_user,
    artefact,
    capability_run,
    project_membership,
    task,
    task_link,
)
from policy_atlas.evidence_search.assess.screen import effective_screen_rows

#: Sentinel for "resolve the owner's display name yourself". Distinct from
#: ``None``, which is a legitimate resolved value (an ownerless row).
_RESOLVE = object()


def resolve_owner_display(conn: Connection, owner_user_id: str | None) -> str | None:
    """Look up one row owner's display name.

    The single-row path. Listings must **not** call this per row — they join
    ``app_user`` once and hand the joined value to :func:`task_out` — but
    for a route that has already loaded exactly one row, one more indexed
    primary-key lookup is cheaper than reshaping the query.

    Args:
        conn: Open database connection.
        owner_user_id: The row's owner, or ``None`` for an ownerless row.

    Returns:
        The owner's display name, the sub rendering when they have no
        ``app_user`` row, or ``None`` when the row has no owner. Never an
        email (contract § 3b).
    """
    if owner_user_id is None:
        return None
    display_name = conn.execute(
        select(app_user.c.display_name).where(app_user.c.user_id == owner_user_id)
    ).scalar_one_or_none()
    return owner_display_for(owner_user_id, display_name)


def run_artefact_id_column() -> Any:
    """The artefact a capability-run row wrote, as a labelled scalar subquery.

    Selected beside ``capability_run`` so :func:`run_out` can say whether the
    walk produced anything — the fact the scoping start states and the
    baseline band read, instead of guessing from the walk's status.
    """
    return (
        select(artefact.c.artefact_id)
        .where(artefact.c.capability_run_id == capability_run.c.capability_run_id)
        .order_by(artefact.c.created_at.desc())
        .limit(1)
        .scalar_subquery()
        .label("artefact_id")
    )


def run_out(row: RowMapping | dict[str, Any]) -> RunOut:
    """Project one capability-run row into its public contract shape.

    ``artefact_id`` is read when the row was selected with
    :func:`run_artefact_id_column`; a bare ``capability_run`` row reports none.
    """
    return RunOut(
        capability_run_id=row["capability_run_id"],
        task_id=row["task_id"],
        plan_id=row["plan_id"],
        plan_version=row["plan_version"],
        status=row["status"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        artefact_id=row.get("artefact_id"),
    )


def memberships_for_tasks(
    conn: Connection, task_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[uuid.UUID]]:
    """Return each task's project ids, ordered by membership age then id."""
    grouped: dict[uuid.UUID, list[uuid.UUID]] = {task_id: [] for task_id in task_ids}
    if not task_ids:
        return grouped
    rows = conn.execute(
        select(project_membership.c.task_id, project_membership.c.project_id)
        .where(project_membership.c.task_id.in_(task_ids))
        .order_by(project_membership.c.created_at, project_membership.c.project_id)
    ).all()
    for task_id, project_id in rows:
        grouped[task_id].append(project_id)
    return grouped


def links_for_tasks(
    conn: Connection, target_task_ids: list[uuid.UUID], *, user_id: str
) -> dict[uuid.UUID, list[TaskLinkOut]]:
    """Read several tasks' "Starts from" Links at once, oldest link first.

    Three queries for the whole page, not three per row: the tasks list is the
    app's main screen and ``task_out`` runs once per row on it.

    **A Link grants no read** (ADR 0037 decision 2), so the source's *name* is
    graded: it is shown only to a caller who holds a read leg on that source
    anyway, and a reader who does not sees ``source_task_name=None``. The
    link's own facts — that this task starts from *that* id, on that pinned
    walk, currently flagged or not — are the target's provenance and stay
    visible, because they are properties of the row the caller is reading.
    The grade is decided inside the join that already fetches the source
    (:func:`_access.readable_task_leg`), so this costs no extra query.

    ``flagged`` is derived here rather than stored (C12): a Link whose two
    tasks stop sharing a project is **marked, not broken**. The inheritance
    already happened — the target's plan and its Task Agent context were built
    from that source — so deleting the row would rewrite the target's
    provenance to make a membership change look tidy. Marking it says what is
    true: this came from over there, and over there is no longer alongside.

    Args:
        conn: Open database connection.
        target_task_ids: The tasks whose sources are wanted.
        user_id: The calling subject, whose read grade decides whether each
            source's name is disclosed.

    Returns:
        One list per requested task id, empty where the task starts from
        nothing.
    """
    grouped: dict[uuid.UUID, list[TaskLinkOut]] = {
        target_id: [] for target_id in target_task_ids
    }
    if not target_task_ids:
        return grouped
    rows = conn.execute(
        select(
            task_link.c.link_id,
            task_link.c.source_task_id,
            task_link.c.target_task_id,
            task_link.c.source_capability_run_id,
            case((readable_task_leg(user_id), task.c.name), else_=None).label(
                "source_task_name"
            ),
        )
        .select_from(task_link.join(task, task.c.task_id == task_link.c.source_task_id))
        .where(task_link.c.target_task_id.in_(target_task_ids))
        .order_by(task_link.c.created_at, task_link.c.link_id)
    ).mappings().all()
    if not rows:
        return grouped
    # Both sides' memberships in one query, keyed by task.
    wanted = set(target_task_ids) | {row["source_task_id"] for row in rows}
    memberships: dict[uuid.UUID, set[uuid.UUID]] = {task_id: set() for task_id in wanted}
    for member_task_id, project_id in conn.execute(
        select(project_membership.c.task_id, project_membership.c.project_id).where(
            project_membership.c.task_id.in_(list(wanted))
        )
    ).all():
        memberships[member_task_id].add(project_id)
    for row in rows:
        target_id = row["target_task_id"]
        grouped[target_id].append(
            TaskLinkOut(
                link_id=row["link_id"],
                source_task_id=row["source_task_id"],
                source_task_name=row["source_task_name"],
                source_capability_run_id=row["source_capability_run_id"],
                flagged=not (
                    memberships[target_id] & memberships[row["source_task_id"]]
                ),
            )
        )
    return grouped


def task_links_for(
    conn: Connection, target_task_id: uuid.UUID, *, user_id: str
) -> list[TaskLinkOut]:
    """Read one task's "Starts from" Links. The single-row form of
    :func:`links_for_tasks`.

    Args:
        conn: Open database connection.
        target_task_id: The task whose sources are wanted.
        user_id: The calling subject, whose read grade decides whether each
            source's name is disclosed.

    Returns:
        One :class:`TaskLinkOut` per link, oldest link first.
    """
    return links_for_tasks(conn, [target_task_id], user_id=user_id)[target_task_id]


def included_source_count(conn: Connection, task_id: uuid.UUID) -> int:
    """Count effective screens with status ``relevant`` for one task.

    Same population the funnel's Included / ``relevant`` count uses.
    """
    effective = effective_screen_rows()
    return int(
        conn.execute(
            select(func.count())
            .select_from(effective)
            .where(effective.c.task_id == task_id)
            .where(effective.c.status == "relevant")
        ).scalar_one()
    )


def task_out(
    conn: Connection,
    row: RowMapping | dict[str, Any],
    *,
    user_id: str,
    owner_display: str | None | object = _RESOLVE,
    project_ids: list[uuid.UUID] | None = None,
    links: list[TaskLinkOut] | None = None,
    access: Literal["full", "public"] = "full",
) -> TaskOut:
    """Project a task row with its derived read models, for one caller.

    Two of the three task-033 fields are **caller-relative**, not properties
    of the row: ``is_owner`` answers "does *this* caller own it", and
    ``owner_display`` is what *this* caller is shown about the owner. That is
    why the caller's subject is a required argument rather than something the
    row carries.

    Args:
        conn: Open database connection.
        row: The task row.
        user_id: The calling subject, for ``is_owner``.
        owner_display: The owner's display name when the caller already
            joined ``app_user`` (listings do, to avoid one query per row).
            Left unset, this resolves it with one lookup — correct for
            single-row routes, an N+1 in a listing.
        project_ids: The task's project memberships when the caller
            already batch-loaded them (listings do). Left unset, this
            resolves them with one lookup — correct for single-row routes,
            an N+1 in a listing.
        links: The task's "Starts from" Links when the caller already
            batch-loaded them with :func:`links_for_tasks` (listings do).
            Left unset, this resolves them — again, correct for a single row,
            an N+1 in a listing.
        access: ``"public"`` when this read was served by the public leg
            (task 037) — the returned shape is then redacted
            (``is_owner=False``, ``owner_display=None``,
            ``project_ids=[]``), skipping the membership lookup entirely.
            ``"full"`` (default) leaves behaviour unchanged.

    Returns:
        The public task shape.
    """
    latest = conn.execute(
        select(capability_run)
        .where(capability_run.c.task_id == row["task_id"])
        .order_by(capability_run.c.started_at.desc(), capability_run.c.capability_run_id.desc())
        .limit(1)
    ).mappings().one_or_none()
    latest_out = None
    source_count = None
    if latest is not None:
        latest_out = LatestRun(
            capability_run_id=latest["capability_run_id"],
            status=latest["status"],
            started_at=latest["started_at"],
            ended_at=latest["ended_at"],
        )
        # Same population the funnel's ``relevant`` (Included) counts. Derived
        # per read and only once a run exists: before that, ``None`` says the
        # question has not been asked, which is not the same as a run that
        # found nothing Included.
        source_count = included_source_count(conn, row["task_id"])
    # The Links are a property of the row, but each source's *name* is graded
    # against this caller (a link grants no read — ADR 0037 decision 2), which
    # is why ``links_for_tasks`` takes the subject. The public leg still omits
    # them entirely: the redacted shape carries nothing relational.
    if access == "public":
        # Redacted shape (D5): no owner display, no project membership —
        # skip the membership lookup entirely rather than compute and discard.
        project_ids = []
        display = None
        is_owner = False
        links = []
    else:
        if links is None:
            links = task_links_for(conn, row["task_id"], user_id=user_id)
        if project_ids is None:
            project_ids = memberships_for_tasks(conn, [row["task_id"]])[row["task_id"]]
        display = (
            resolve_owner_display(conn, row["owner_user_id"])
            if owner_display is _RESOLVE
            else cast(str | None, owner_display)
        )
        # Safe in Python: SQL has already decided visibility, and a NULL
        # ``owner_user_id`` never equals a subject string.
        is_owner = row["owner_user_id"] == user_id
    return TaskOut(
        task_id=row["task_id"],
        name=row["name"],
        question=row["question"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        archived_at=row["archived_at"],
        latest_run=latest_out,
        project_ids=project_ids,
        source_count=source_count,
        visibility=row["visibility"],
        is_owner=is_owner,
        owner_display=display,
        is_public=row["is_public"],
        access=access,
        capability=row["capability"],
        from_task_ids=[link.source_task_id for link in links],
        links=links,
    )
