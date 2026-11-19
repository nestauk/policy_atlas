"""Private contract-projection helpers shared by API routers.

The owner-only row helpers this module used to carry (``owned_task``,
``owned_project``, ``_owned_conversation``) are gone: every task-,
project- and conversation-scoped route now resolves through the graded
helpers in ``access`` (task 033). What is left is projection and display.
"""

from __future__ import annotations

import uuid
from collections.abc import Collection
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, cast

from sqlalchemy import ColumnElement, Text, case, exists, func, select
from sqlalchemy import cast as cast_sql
from sqlalchemy.engine import Connection, RowMapping

from policy_atlas.api.contract import LatestRun, RunOut, StageKey, TaskLinkOut, TaskOut
from policy_atlas.api.contract.runs import TocWalkKind
from policy_atlas.api.identity import owner_display_for
from policy_atlas.api.routers.access import readable_task_leg
from policy_atlas.api.settings import Settings
from policy_atlas.api.stage_vocabulary import presentation, stage_for_payload
from policy_atlas.core.schema import (
    app_user,
    artefact,
    capability_run,
    cohort,
    cohort_member,
    event_log,
    evidence_scope,
    longlist_result,
    organisation,
    project_membership,
    runs,
    task,
    task_link,
)
from policy_atlas.evidence_search.assess.screen import effective_screen_rows
from policy_atlas.runtime.capability_registry import OPTIONS_SCOPING, THEORY_OF_CHANGE
from policy_atlas.runtime.toc_plan import (
    TOC_CHECK_MODE_KEY,
    TOC_DRAFT_WALK_KEY,
    TOC_PURPOSE,
    TOC_REVIEW_FIRST_KEY,
    TOC_WALK_CHECK,
    TOC_WALK_DRAFT,
    TOC_WALK_KEY,
)

#: Sentinel for "resolve the owner's display name yourself". Distinct from
#: ``None``, which is a legitimate resolved value (an ownerless row).
_RESOLVE = object()


#: A walk that is still going: the admission fences and ``active_run`` read these.
ACTIVE_WALK_STATUSES: tuple[str, ...] = ("running", "paused")


LimitKind = Literal["person", "cohort", "organisation", "default", "administrator"]


@dataclass(frozen=True)
class LimitSource:
    """Where one limit came from: a fixed kind, plus the cohort's or organisation's name."""

    kind: LimitKind
    name: str | None = None


@dataclass(frozen=True)
class Limits:
    """Effective task and simultaneous-run limits for one person."""

    task_quota: int | None
    runs: int | None
    # Where each limit came from, for the ops pages. Not part of equality:
    # callers compare the numbers.
    task_quota_from: LimitSource = field(
        default_factory=lambda: LimitSource("default"), compare=False
    )
    runs_from: LimitSource = field(default_factory=lambda: LimitSource("default"), compare=False)


def parentless_walk() -> ColumnElement[bool]:
    """Return the predicate "this walk has no parent walk" (task 045, S15).

    The admission fences — ``POST /runs``, ``confirm-baseline`` and the Task
    Agent turn route — consider parentless walks only, so a longlist walk's
    option searches (its children) never block a user action; the parent
    itself is parentless and still does. An option search the chat verb
    *add* starts has no parent by design, so it blocks like any walk.

    Returns:
        A clause over ``capability_run`` for a ``.where()``.
    """
    return capability_run.c.parent_capability_run_id.is_(None)


def active_parentless_walk(conn: Connection, task_id: uuid.UUID) -> RowMapping | None:
    """Return the task's running or paused parentless walk, or ``None`` (task 045, S15).

    The admission fences' one question: any such walk refuses a new walk,
    a plan edit and a longlist action.

    Args:
        conn: Open database connection.
        task_id: The task.

    Returns:
        The walk's ``capability_run_id``, ``status`` and ``plan_version``.
    """
    return conn.execute(
        select(
            capability_run.c.capability_run_id,
            capability_run.c.status,
            capability_run.c.plan_version,
        )
        .where(capability_run.c.task_id == task_id)
        .where(capability_run.c.status.in_(ACTIVE_WALK_STATUSES))
        .where(parentless_walk())
        .limit(1)
    ).mappings().one_or_none()


def tasks_created_since(conn: Connection, user_id: str, *, days: int) -> int:
    """Count the tasks one person created in the last ``days`` days (task 064a, Q8).

    By the database clock, never the API's. Archived tasks count: archiving
    does not give a task back to the quota.

    Args:
        conn: Open database connection.
        user_id: The person, matched on ``task.owner_user_id``.
        days: The window's length.

    Returns:
        How many of the person's task rows were created inside the window.
    """
    return int(
        conn.execute(
            select(func.count())
            .select_from(task)
            .where(task.c.owner_user_id == user_id)
            .where(created_in_last_days(days))
        ).scalar_one()
    )


def created_in_last_days(days: int) -> ColumnElement[bool]:
    """The predicate "this task was created in the last ``days`` days", by the database clock.

    Shared by the quota check and the ops people list (task 065), so the two
    counts never drift. ``make_interval(years, months, weeks, days)``: the
    length is a bound parameter, not text spliced into the statement.
    """
    return task.c.created_at >= func.now() - func.make_interval(0, 0, 0, days)


def effective_limits(conn: Connection, user_id: str, *, settings: Settings) -> Limits:
    """Resolve one person's limits: their own override, a cohort's, their organisation's, settings.

    Task 065 (B12, plan P7). A stored ``0`` means no limit and comes back as
    ``None``. An administrator's limits are both ``None`` (the exemptions of
    task 064a, ADR 0045, moved here from the task-create route and from
    ``user_at_run_cap``). The task-create check, the run-cap sites and
    ``/me`` call this and nothing else reads the six override columns. A
    cohort's number (owner, 2026-11-18) sits between the person's and the
    organisation's; in several cohorts that set one, the most recently
    joined wins, per limit.

    Args:
        conn: Open database connection.
        user_id: The person's Cognito subject.
        settings: Application settings providing the default limits.

    Returns:
        Effective task and run limits, with ``None`` meaning unlimited.
    """
    def from_cohort(column: ColumnElement[Any]) -> Any:
        """The latest-joined cohort that sets this limit: its value and name, as a row."""
        return (
            select(column, cohort.c.name)
            .select_from(
                cohort_member.join(cohort, cohort.c.cohort_id == cohort_member.c.cohort_id)
            )
            .where(cohort_member.c.user_id == user_id, column.is_not(None))
            # Equal join times (rare: the command stamps each with the clock)
            # fall back to the cohort id, which never changes, not the name,
            # which an operator may rename.
            .order_by(cohort_member.c.added_at.desc(), cohort.c.cohort_id)
            .limit(1)
        )

    row = conn.execute(
        select(
            app_user.c.is_admin,
            app_user.c.task_quota_per_year.label("user_task_quota"),
            app_user.c.runs_per_user.label("user_runs"),
            organisation.c.name.label("org_name"),
            organisation.c.task_quota_per_year.label("org_task_quota"),
            organisation.c.runs_per_user.label("org_runs"),
        )
        .select_from(app_user.outerjoin(organisation, organisation.c.org_id == app_user.c.org_id))
        .where(app_user.c.user_id == user_id)
    ).mappings().one_or_none()
    if row is None:
        default = LimitSource("default")
        return _limits((settings.task_quota_per_year, default), (settings.runs_per_user, default))
    if row["is_admin"]:
        # Administrators are exempt from both limits (owner rulings
        # 2026-11-16: the task quota in 064a Q8, the run cap in 064a's
        # review); an override on their row does not pull them back under.
        admin = LimitSource("administrator")
        return _limits((0, admin), (0, admin))

    def resolve(own: int | None, cohort_column: ColumnElement[Any], org_value: int | None,
                default: int) -> tuple[int, LimitSource]:
        if own is not None:
            return own, LimitSource("person")
        found = conn.execute(from_cohort(cohort_column)).one_or_none()
        if found is not None:
            return int(found[0]), LimitSource("cohort", str(found[1]))
        if org_value is not None:
            return org_value, LimitSource("organisation", str(row["org_name"]))
        return default, LimitSource("default")

    return _limits(
        resolve(row["user_task_quota"], cohort.c.task_quota_per_year, row["org_task_quota"],
                settings.task_quota_per_year),
        resolve(row["user_runs"], cohort.c.runs_per_user, row["org_runs"],
                settings.runs_per_user),
    )


def _limits(task_quota: tuple[int, LimitSource], runs: tuple[int, LimitSource]) -> Limits:
    """Build limits from (value, source) pairs; a stored 0 means no limit."""
    return Limits(
        task_quota=None if task_quota[0] == 0 else task_quota[0],
        runs=None if runs[0] == 0 else runs[0],
        task_quota_from=task_quota[1],
        runs_from=runs[1],
    )


def executor_walk() -> ColumnElement[bool]:
    """Return the predicate "this walk runs on the walk executor" (task 045, A12).

    An option search (a walk under a ``targeted`` intent record) runs on the
    option-search pool, never on an executor worker — including the one the
    chat verb *add* starts with no parent — so the capacity counts leave it
    out. The per-task active fence still counts a parentless one.

    Returns:
        A clause over ``capability_run`` for a ``.where()``.
    """
    return ~exists().where(
        evidence_scope.c.evidence_scope_id == capability_run.c.evidence_scope_id,
        evidence_scope.c.task_id == capability_run.c.task_id,
        evidence_scope.c.purpose == "targeted",
    )


def _latest_run_row(conn: Connection, row: RowMapping | dict[str, Any]) -> RowMapping | None:
    """Return the walk ``TaskOut.latest_run`` reports.

    Unchanged for an Evidence search: the most recent walk. For an
    options-scoping task, the most recent walk that is neither a child walk
    nor an option search (a ``targeted`` intent record) — ADR 0039 decision
    5 — so an option search never becomes "the task's run" to a reader that
    has not yet moved to ``active_run`` and the existence flags. A theory of
    change filters the same way: its item searches are child walks (task 054).
    """
    query = select(capability_run).where(capability_run.c.task_id == row["task_id"])
    if row["capability"] in (OPTIONS_SCOPING, THEORY_OF_CHANGE):
        query = (
            query.select_from(
                capability_run.join(
                    evidence_scope,
                    (evidence_scope.c.evidence_scope_id == capability_run.c.evidence_scope_id)
                    & (evidence_scope.c.task_id == capability_run.c.task_id),
                )
            )
            .where(parentless_walk())
            .where(evidence_scope.c.purpose.is_distinct_from("targeted"))
        )
    return (
        conn.execute(
            query.order_by(
                capability_run.c.started_at.desc(), capability_run.c.capability_run_id.desc()
            ).limit(1)
        )
        .mappings()
        .one_or_none()
    )


#: The events that start or end a pause. They are the ones the live stream
#: turns into a run status, so a read and the stream give the same times.
_PAUSE_EVENT_TYPES = ("run.parked", "continuation.claimed", "run.interrupted", "run.finished")


def walk_pauses(
    conn: Connection, *, task_id: uuid.UUID, walk_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, float]:
    """Each walk's seconds paused at check-ins, read from the event log.

    A run that waits hours for an answer did not work for hours, so its timer
    leaves the wait out. The event log is the one record of when a walk
    paused and when it carried on; nothing extra is stored. A pause the walk
    is still in is not counted: it has no end yet.

    Args:
        conn: Open database connection.
        task_id: The task.
        walk_ids: The walks to read.

    Returns:
        Walk id → the total seconds of its finished pauses (absent when none).
    """
    wanted = {str(walk_id) for walk_id in walk_ids}
    if not wanted:
        return {}
    walk = event_log.c.payload["capability_run_id"].astext
    rows = conn.execute(
        select(event_log.c.event_type, event_log.c.occurred_at, walk)
        .where(event_log.c.task_id == task_id)
        .where(event_log.c.event_type.in_(_PAUSE_EVENT_TYPES))
        .where(walk.in_(wanted))
        .order_by(event_log.c.sequence)
    )
    paused_at: dict[str, datetime] = {}
    seconds: dict[uuid.UUID, float] = {}
    for event_type, occurred_at, walk_id in rows:
        if event_type == "run.parked":
            paused_at.setdefault(walk_id, occurred_at)
        elif walk_id in paused_at:
            waited = (occurred_at - paused_at.pop(walk_id)).total_seconds()
            seconds[uuid.UUID(walk_id)] = seconds.get(uuid.UUID(walk_id), 0.0) + max(0.0, waited)
    return seconds


def _latest_run_out(
    walk: RowMapping,
    stage: StageKey | None = None,
    paused_seconds: float = 0,
) -> LatestRun:
    return LatestRun(
        capability_run_id=walk["capability_run_id"],
        status=walk["status"],
        started_at=walk["started_at"],
        ended_at=walk["ended_at"],
        paused_seconds=paused_seconds,
        stage=stage,
        stage_label=presentation(stage)[0] if stage is not None else None,
    )


def _active_stage(conn: Connection, task_id: uuid.UUID, active: RowMapping) -> StageKey | None:
    """Return the public stage the task's active walk last started (task 058, N15).

    The walk read is the parentless active walk when there is one, else the
    active row itself: a scoping task whose option searches are running shows
    the longlist walk's stage ("Searching for each option"), not a child's.
    The stage is the walk's latest ``run.started`` event, the row the event
    stream turns into ``stage.started``: either a component run of the walk,
    or, for the option-search fan-out, a row with no component run that
    names the walk in its payload. The full-text screen starts no stage of
    its own, so its rows are skipped. One statement.

    Args:
        conn: Open database connection.
        task_id: The task.
        active: The task's latest running or paused walk, children included.

    Returns:
        The stage key, or ``None`` when the walk has not started a stage.
    """
    parentless = (
        select(capability_run.c.capability_run_id)
        .where(capability_run.c.task_id == task_id)
        .where(capability_run.c.status.in_(ACTIVE_WALK_STATUSES))
        .where(parentless_walk())
        .order_by(capability_run.c.started_at.desc(), capability_run.c.capability_run_id.desc())
        .limit(1)
        .scalar_subquery()
    )
    walk_id = func.coalesce(parentless, active["capability_run_id"])
    payload = event_log.c.payload
    row = conn.execute(
        select(payload)
        .select_from(
            event_log.outerjoin(
                runs,
                (runs.c.run_id == event_log.c.run_id) & (runs.c.task_id == event_log.c.task_id),
            )
        )
        .where(event_log.c.task_id == task_id)
        .where(event_log.c.event_type == "run.started")
        .where(
            (runs.c.capability_run_id == walk_id)
            | (
                event_log.c.run_id.is_(None)
                & (payload["capability_run_id"].astext == cast_sql(walk_id, Text))
            )
        )
        .where(func.coalesce(payload["component"].astext, "") != "screen_full")
        .where(func.coalesce(payload["registry_component"].astext, "") != "screen_full")
        .order_by(event_log.c.sequence.desc())
        .limit(1)
    ).scalar_one_or_none()
    return stage_for_payload(row) if isinstance(row, dict) else None


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


def run_purpose_column() -> Any:
    """The walk's intent-record purpose, as a labelled scalar subquery.

    Selected beside ``capability_run`` so :func:`run_out` can say what kind of
    walk it is (task 045): the thread keeps option searches out of its run
    blocks. ``None`` for a walk whose scope carries no purpose (an Evidence
    search).
    """
    return (
        select(evidence_scope.c.purpose)
        .where(evidence_scope.c.evidence_scope_id == capability_run.c.evidence_scope_id)
        .where(evidence_scope.c.task_id == capability_run.c.task_id)
        .limit(1)
        .scalar_subquery()
        .label("purpose")
    )


def run_scope_context_column() -> Any:
    """The walk's intent-record context, as a labelled scalar subquery.

    Selected beside ``capability_run`` so :func:`run_out` can name a theory of
    change walk's kind and the draft a check follows (task 054, S3).
    """
    return (
        select(evidence_scope.c.context)
        .where(evidence_scope.c.evidence_scope_id == capability_run.c.evidence_scope_id)
        .where(evidence_scope.c.task_id == capability_run.c.task_id)
        .limit(1)
        .scalar_subquery()
        .label("scope_context")
    )


def _toc_walk(row: RowMapping | dict[str, Any]) -> tuple[TocWalkKind | None, uuid.UUID | None]:
    """A theory-of-change walk's kind and the draft walk a check follows (task 054, S3).

    Args:
        row: A capability-run row selected with :func:`run_purpose_column` and
            :func:`run_scope_context_column`.

    Returns:
        ``(kind, follows)``: ``draft``, ``read`` (an uploaded theory's draft
        walk), ``check`` or ``report_update``, and the draft walk's id for a
        check the server started after it; ``(None, None)`` for any other walk.
    """
    context = row.get("scope_context")
    if row.get("purpose") != TOC_PURPOSE or not isinstance(context, dict):
        return None, None
    walk = context.get(TOC_WALK_KEY)
    kind: TocWalkKind | None = None
    if walk == TOC_WALK_DRAFT:
        kind = "read" if context.get(TOC_REVIEW_FIRST_KEY) else "draft"
    elif walk == TOC_WALK_CHECK:
        kind = "report_update" if context.get(TOC_CHECK_MODE_KEY) == "report" else "check"
    draft = context.get(TOC_DRAFT_WALK_KEY)
    return kind, uuid.UUID(draft) if isinstance(draft, str) else None


def run_out(row: RowMapping | dict[str, Any]) -> RunOut:
    """Project one capability-run row into its public contract shape.

    ``artefact_id``, ``purpose`` and the theory-of-change walk fields are read
    when the row was selected with :func:`run_artefact_id_column`,
    :func:`run_purpose_column` and :func:`run_scope_context_column`; a bare
    ``capability_run`` row reports none.
    """
    toc_walk, follows = _toc_walk(row)
    return RunOut(
        capability_run_id=row["capability_run_id"],
        task_id=row["task_id"],
        plan_id=row["plan_id"],
        plan_version=row["plan_version"],
        status=row["status"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        artefact_id=row.get("artefact_id"),
        parent_capability_run_id=row.get("parent_capability_run_id"),
        purpose=row.get("purpose"),
        toc_walk=toc_walk,
        follows_capability_run_id=follows,
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
    (:func:`access.readable_task_leg`), so this costs no extra query.

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
    latest = _latest_run_row(conn, row)
    latest_out = None
    source_count = None
    # What exists and what is active (scoping readers see what exists and
    # what is active): one ``SELECT … LIMIT 1`` for any
    # running or paused walk, children included, and one ``EXISTS`` for the
    # longlist — a fixed two statements per task, whatever it has run. An
    # active walk adds one more for its stage and one for the
    # time it has paused, which its timer leaves out.
    active = conn.execute(
        select(capability_run)
        .where(capability_run.c.task_id == row["task_id"])
        .where(capability_run.c.status.in_(ACTIVE_WALK_STATUSES))
        .order_by(capability_run.c.started_at.desc(), capability_run.c.capability_run_id.desc())
        .limit(1)
    ).mappings().one_or_none()
    has_longlist = row["capability"] == OPTIONS_SCOPING and bool(
        conn.execute(
            select(exists().where(longlist_result.c.task_id == row["task_id"]))
        ).scalar()
    )
    if latest is not None:
        latest_out = _latest_run_out(latest)
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
        # Redacted shape: no owner display, no project membership —
        # skip the membership lookup entirely rather than compute and discard.
        project_ids = []
        display = None
        is_owner = False
        links = []
    else:
        if links is None:
            links = links_for_tasks(conn, [row["task_id"]], user_id=user_id)[row["task_id"]]
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
        active_run=(
            _latest_run_out(
                active,
                _active_stage(conn, row["task_id"], active),
                walk_pauses(
                    conn, task_id=row["task_id"], walk_ids=[active["capability_run_id"]]
                ).get(active["capability_run_id"], 0),
            )
            if active is not None
            else None
        ),
        has_longlist=has_longlist,
        project_ids=project_ids,
        source_count=source_count,
        visibility=row["visibility"],
        is_owner=is_owner,
        owner_display=display,
        is_public=row["is_public"],
        access=access,
        capability=row["capability"],
        links=links,
    )
