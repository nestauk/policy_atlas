"""Self-signup sweep for waitlist entries with an approved email domain."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import structlog
from botocore.exceptions import ClientError
from sqlalchemy import bindparam, func, select
from sqlalchemy.engine import Engine

from policy_atlas.api.deps import Identity
from policy_atlas.api.settings import Settings
from policy_atlas.core.schema import ops_action, organisation, organisation_domain, waitlist_entry
from policy_atlas.ops import commands
from policy_atlas.ops.errors import Deactivated, EnrolledElsewhere, OpsError

log = structlog.get_logger()


#: Outcomes that end a row's life on the sweep: the row stays unstamped and the
#: Requests page shows it as "Check" for an operator. ``refused`` is a
#: deterministic refusal (an address Cognito or the command rejects); retrying it
#: every minute would only fill ``ops_action``.
TERMINAL_OUTCOMES: tuple[str, ...] = ("enrolled_elsewhere", "refused", "deactivated")

#: Cognito errors worth retrying next tick; any other ``ClientError`` is terminal.
_TRANSIENT_COGNITO_CODES = frozenset(
    {"TooManyRequestsException", "ThrottlingException", "InternalErrorException",
     "ServiceUnavailable", "LimitExceededException"}
)

#: The most rows one tick looks at, so a backlog never makes a tick run for minutes.
_CANDIDATES_PER_TICK = 200


@dataclass(frozen=True, slots=True)
class SweepReport:
    """The outcomes from one self-signup sweep tick.

    Attributes:
        invited: Accounts created and sent an invitation.
        enrolled: Existing unenrolled accounts added without an invitation.
        elsewhere: Accounts already enrolled in another organisation.
        refused: Rows refused for good (terminal; an operator decides).
        failed: Rows whose processing failed and remain eligible for retry.
        skipped_for_cap: Eligible rows not attempted because the hourly cap was reached.
    """

    invited: int = 0
    enrolled: int = 0
    elsewhere: int = 0
    failed: int = 0
    skipped_for_cap: int = 0
    refused: int = 0


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
                    # An operator rejected it: no email, ever.
                    waitlist_entry.c.rejected_at.is_(None),
                    func.lower(func.split_part(waitlist_entry.c.email, "@", 2)).in_(
                        bindparam("domains", expanding=True)
                    ),
                )
                .order_by(waitlist_entry.c.created_at, waitlist_entry.c.entry_id)
                .limit(_CANDIDATES_PER_TICK),
                {"domains": list(domains)},
            )
            .mappings()
            .all()
        )
        # Sends and failed attempts both spend the hour's allowance, so a row
        # that keeps failing cannot drive unbounded Cognito calls.
        sent = int(
            conn.execute(
                select(func.count())
                .select_from(ops_action)
                .where(
                    ops_action.c.actor_user_id == "sweep",
                    ops_action.c.action == "invite",
                    ops_action.c.outcome.in_(("invited", "failed")),
                    ops_action.c.at >= tick_now - timedelta(hours=1),
                )
            ).scalar_one()
        )

    budget = max(0, settings.self_signup_max_per_hour - sent)
    invited = enrolled = elsewhere = failed = skipped_for_cap = refused = 0
    for index, row in enumerate(candidates):
        entry_id = row["entry_id"]
        target = str(entry_id)
        # The same reading as the SQL filter (split_part(email, '@', 2)): the
        # part after the first @, lower-cased.
        domain = str(row["email"]).split("@", 2)[1].lower() if "@" in str(row["email"]) else ""

        # Once the budget has been spent every later candidate could send an
        # invitation. The next tick can safely reconsider them after old audit
        # rows age out of the hourly window.
        if invited + failed >= budget:
            skipped_for_cap = len(candidates) - index
            break

        try:
            with engine.begin() as conn:
                terminal = conn.execute(
                    select(ops_action.c.action_id).where(
                        ops_action.c.actor_user_id == "sweep",
                        ops_action.c.action == "invite",
                        ops_action.c.target == target,
                        ops_action.c.outcome.in_(TERMINAL_OUTCOMES),
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
        except Deactivated:
            # A deactivated person cannot get back in through the public form
            # (contract 066 B5): the request waits for an operator.
            with engine.begin() as conn:
                commands.record_action(
                    conn, actor="sweep", action="invite", target=target, outcome="deactivated"
                )
            refused += 1
            log.info("ops.sweep_deactivated", entry_id=target)
        except Exception as error:
            outcome = "failed" if _is_transient(error) else "refused"
            with engine.begin() as conn:
                commands.record_action(
                    conn, actor="sweep", action="invite", target=target, outcome=outcome
                )
            if outcome == "failed":
                failed += 1
            else:
                refused += 1
            log.info(
                "ops.sweep_failed",
                entry_id=target,
                error_class=type(error).__name__,
                outcome=outcome,
            )

    report = SweepReport(invited, enrolled, elsewhere, failed, skipped_for_cap, refused)
    if any((invited, enrolled, elsewhere, failed, skipped_for_cap, refused)):
        log.info(
            "ops.sweep_tick",
            invited=invited,
            enrolled=enrolled,
            elsewhere=elsewhere,
            failed=failed,
            refused=refused,
            skipped_for_cap=skipped_for_cap,
        )
    return report


def _is_transient(error: Exception) -> bool:
    """Whether a failure is worth another try next tick.

    A refusal by a command (``OpsError``: an address the lookup cannot take, a
    row already handled) or by Cognito for a reason that will not change is
    terminal. A throttle, an outage or a database error is not.
    """
    if isinstance(error, OpsError):
        return False
    if isinstance(error, ClientError):
        code = error.response.get("Error", {}).get("Code", "")
        return code in _TRANSIENT_COGNITO_CODES
    return True
