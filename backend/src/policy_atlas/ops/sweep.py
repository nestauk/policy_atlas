"""Self-signup sweep for waitlist entries with an approved email domain."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import bindparam, func, select
from sqlalchemy.engine import Engine

from policy_atlas.api.deps import Identity
from policy_atlas.api.settings import Settings
from policy_atlas.core.schema import ops_action, organisation, organisation_domain, waitlist_entry
from policy_atlas.ops import commands
from policy_atlas.ops.errors import EnrolledElsewhere

log = structlog.get_logger()


@dataclass(frozen=True, slots=True)
class SweepReport:
    """The outcomes from one self-signup sweep tick.

    Attributes:
        invited: Accounts created and sent an invitation.
        enrolled: Existing unenrolled accounts added without an invitation.
        elsewhere: Accounts already enrolled in another organisation.
        failed: Rows whose processing failed and remain eligible for retry.
        skipped_for_cap: Eligible rows not attempted because the hourly cap was reached.
    """

    invited: int = 0
    enrolled: int = 0
    elsewhere: int = 0
    failed: int = 0
    skipped_for_cap: int = 0


def sweep_once(
    engine: Engine, identity: Identity, settings: Settings, *, now: datetime | None = None
) -> SweepReport:
    """Approve eligible waitlist entries once, respecting the durable hourly cap.

    Each candidate is handled in its own transaction, so a malformed or
    transiently failing entry cannot prevent subsequent requests from being
    processed.

    Args:
        engine: Engine used to read and atomically update durable rows.
        identity: Optional Cognito client and pool metadata for the ops service.
        settings: Self-signup configuration including the hourly invitation cap.
        now: Clock value for request stamps and hourly-cap evaluation.

    Returns:
        Counts for the outcomes observed during this tick.
    """
    if identity.cognito is None or identity.pool_id is None:
        log.info("ops.sweep_skipped", reason="no_identity")
        return SweepReport()

    tick_now = now or datetime.now(UTC)
    with engine.connect() as conn:
        domains = {
            str(row["domain"]): commands.Organisation(org_id=row["org_id"], name=str(row["name"]))
            for row in conn.execute(
                select(
                    organisation_domain.c.domain, organisation.c.org_id, organisation.c.name
                ).join(organisation, organisation.c.org_id == organisation_domain.c.org_id)
            ).mappings()
        }
        if not domains:
            return SweepReport()
        candidates = (
            conn.execute(
                select(waitlist_entry)
                .where(
                    waitlist_entry.c.account_created_at.is_(None),
                    func.lower(func.split_part(waitlist_entry.c.email, "@", 2)).in_(
                        bindparam("domains", expanding=True)
                    ),
                )
                .order_by(waitlist_entry.c.created_at, waitlist_entry.c.entry_id),
                {"domains": list(domains)},
            )
            .mappings()
            .all()
        )
        sent = int(
            conn.execute(
                select(func.count())
                .select_from(ops_action)
                .where(
                    ops_action.c.actor_user_id == "sweep",
                    ops_action.c.action == "invite",
                    ops_action.c.outcome == "invited",
                    ops_action.c.at >= tick_now - timedelta(hours=1),
                )
            ).scalar_one()
        )

    budget = max(0, settings.self_signup_max_per_hour - sent)
    invited = enrolled = elsewhere = failed = skipped_for_cap = 0
    for index, row in enumerate(candidates):
        entry_id = row["entry_id"]
        target = str(entry_id)
        domain = str(row["email"]).rsplit("@", 1)[-1].lower()

        # Once the budget has been spent every later candidate could send an
        # invitation. The next tick can safely reconsider them after old audit
        # rows age out of the hourly window.
        if invited >= budget:
            skipped_for_cap = len(candidates) - index
            break

        try:
            with engine.begin() as conn:
                terminal = conn.execute(
                    select(ops_action.c.action_id).where(
                        ops_action.c.actor_user_id == "sweep",
                        ops_action.c.action == "invite",
                        ops_action.c.target == target,
                        ops_action.c.outcome == "enrolled_elsewhere",
                    )
                ).first()
                if terminal is not None:
                    continue
                approved = commands.approve_request(
                    conn,
                    identity.cognito,
                    pool_id=identity.pool_id,
                    entry_id=entry_id,
                    org=domains[domain],
                    now=tick_now,
                )
                outcome = "invited" if approved.enrolment.invitation_sent else "enrolled"
                commands.record_action(
                    conn, actor="sweep", action="invite", target=target, outcome=outcome
                )
            if outcome == "invited":
                invited += 1
            else:
                enrolled += 1
            log.info("ops.action", actor="sweep", action="invite", target=target, outcome=outcome)
        except EnrolledElsewhere:
            with engine.begin() as conn:
                commands.record_action(
                    conn,
                    actor="sweep",
                    action="invite",
                    target=target,
                    outcome="enrolled_elsewhere",
                )
            elsewhere += 1
            log.info("ops.sweep_enrolled_elsewhere", entry_id=target, org=domains[domain].name)
        except Exception as error:
            with engine.begin() as conn:
                commands.record_action(
                    conn, actor="sweep", action="invite", target=target, outcome="failed"
                )
            failed += 1
            log.info("ops.sweep_failed", entry_id=target, error_class=type(error).__name__)

    report = SweepReport(invited, enrolled, elsewhere, failed, skipped_for_cap)
    if any((invited, enrolled, elsewhere, failed, skipped_for_cap)):
        log.info(
            "ops.sweep_tick",
            invited=invited,
            enrolled=enrolled,
            elsewhere=elsewhere,
            failed=failed,
            skipped_for_cap=skipped_for_cap,
        )
    return report
