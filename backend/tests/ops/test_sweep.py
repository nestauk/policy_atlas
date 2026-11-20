"""Acceptance tests for the synchronous, clock-injected self-signup sweep."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select
from sqlalchemy.engine import Engine
from structlog.testing import capture_logs

from policy_atlas.api.deps import Identity
from policy_atlas.api.routers.ops import list_requests
from policy_atlas.api.settings import Settings
from policy_atlas.core.schema import (
    app_user,
    ops_action,
    organisation,
    organisation_domain,
    waitlist_entry,
)
from policy_atlas.ops import commands
from policy_atlas.ops.sweep import SweepReport, sweep_once
from tests.api.org_support import make_org, ops_enrol
from tests.helpers import now as real_now
from tests.ops.support import (
    POOL_ID,
    cognito,
    expect_create,
    expect_enabled,
    expect_lookup,
    fresh_sub,
)

_NOW = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)


#: A listed domain of this module's own, so rows other test modules leave on the
#: waitlist (nesta.org.uk addresses from the route tests) are never swept here.
_DOMAIN = f"sweep-{uuid.uuid4().hex[:8]}.test"


def _settings() -> Settings:
    """Return the minimal settings shape consumed by the pure sweep."""
    return Settings(
        "http://dev-issuer.local", "sweep-test", None, None, "http://app.example.test", "unused"
    )


@pytest.fixture(autouse=True)
def _clean_sweep_rows(engine: Engine) -> None:
    """Start each test from no sweep state.

    The sweep reads the whole table, and every row this module commits is
    named ``Sweep Person``, so a leftover from an earlier test (or an earlier
    run on a kept database) would be swept again with no Cognito stub queued.
    """
    with engine.begin() as conn:
        conn.execute(delete(waitlist_entry).where(waitlist_entry.c.name == "Sweep Person"))
        conn.execute(delete(ops_action).where(ops_action.c.actor_user_id == "sweep"))
        # Other modules list nesta.org.uk and leave rows under it; unlist
        # everything but this module's domain so the sweep sees only its rows.
        conn.execute(delete(organisation_domain).where(organisation_domain.c.domain != _DOMAIN))


def _entry(engine: Engine, *, email: str, created_at: datetime = _NOW) -> uuid.UUID:
    """Commit a waitlist row and return its identifier."""
    entry_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            waitlist_entry.insert().values(
                entry_id=entry_id,
                email=email,
                name="Sweep Person",
                organisation=None,
                role_or_reason="Testing self signup",
                created_at=created_at,
            )
        )
    return entry_id


def _domain(engine: Engine, *, domain: str = _DOMAIN) -> tuple[uuid.UUID, str]:
    """Commit an approved domain and return its organisation identity."""
    with engine.begin() as conn:
        existing = conn.execute(
            select(organisation_domain.c.org_id).where(organisation_domain.c.domain == domain)
        ).scalar_one_or_none()
        if existing is not None:
            name = conn.execute(
                select(organisation.c.name).where(organisation.c.org_id == existing)
            ).scalar_one()
            return existing, str(name)
        org_id = make_org(conn, name="Sweep Org")
        name = conn.execute(
            select(organisation.c.name).where(organisation.c.org_id == org_id)
        ).scalar_one()
        conn.execute(
            organisation_domain.insert().values(domain=domain, org_id=org_id, created_at=real_now())
        )
    return org_id, str(name)


def _identity(client: object) -> Identity:
    """Wrap a stubbed Cognito client in the operations identity seam."""
    return Identity(client, POOL_ID, "eu-west-2")


def test_sweep_matches_exact_domains_case_insensitively(engine: Engine) -> None:
    """Only a listed exact email domain is eligible for automatic approval."""
    _domain(engine)
    exact = _entry(engine, email=f"case@{_DOMAIN.upper()}")
    subdomain = _entry(engine, email=f"sub@a.{_DOMAIN}")
    unlisted = _entry(engine, email="other@example.test")
    sub = fresh_sub("exact")
    with cognito() as (client, stubber):
        expect_lookup(stubber, email=f"case@{_DOMAIN.upper()}", sub=None)
        expect_create(stubber, email=f"case@{_DOMAIN.upper()}", sub=sub)
        report = sweep_once(engine, _identity(client), _settings(), now=_NOW)
    assert report == SweepReport(invited=1)
    with engine.connect() as conn:
        approved = (
            conn.execute(select(waitlist_entry).where(waitlist_entry.c.entry_id == exact))
            .mappings()
            .one()
        )
        assert approved["account_user_id"] == sub
        assert approved["account_created_at"] == _NOW
        assert conn.execute(
            select(waitlist_entry.c.account_created_at).where(
                waitlist_entry.c.entry_id.in_([subdomain, unlisted])
            )
        ).scalars().all() == [None, None]


def test_sweep_stamps_success_and_records_invitation(engine: Engine) -> None:
    """An invited account leaves the request and audit stamps in one committed tick."""
    _domain(engine)
    entry_id = _entry(engine, email=f"person@{_DOMAIN}")
    sub = fresh_sub("stamp")
    with cognito() as (client, stubber):
        expect_lookup(stubber, email=f"person@{_DOMAIN}", sub=None)
        expect_create(stubber, email=f"person@{_DOMAIN}", sub=sub)
        assert sweep_once(engine, _identity(client), _settings(), now=_NOW) == SweepReport(
            invited=1
        )
    with engine.connect() as conn:
        user = conn.execute(
            select(app_user.c.invited_at).where(app_user.c.user_id == sub)
        ).scalar_one()
        action = (
            conn.execute(select(ops_action).where(ops_action.c.target == str(entry_id)))
            .mappings()
            .one()
        )
    assert user is not None
    assert action["actor_user_id"] == "sweep"
    assert action["action"] == "invite"
    assert action["outcome"] == "invited"


def test_sweep_skips_already_stamped_rows(engine: Engine) -> None:
    """A manually approved row is excluded before Cognito can be called."""
    _domain(engine)
    entry_id = _entry(engine, email=f"stamped@{_DOMAIN}")
    with engine.begin() as conn:
        conn.execute(
            waitlist_entry.update()
            .where(waitlist_entry.c.entry_id == entry_id)
            .values(account_user_id="already", account_created_at=_NOW)
        )
    with cognito() as (client, _stubber):
        assert sweep_once(engine, _identity(client), _settings(), now=_NOW) == SweepReport()


def test_sweep_skips_a_rejected_row(engine: Engine) -> None:
    """An operator's rejection means no email, ever (owner, 2026-11-18)."""
    _domain(engine)
    entry_id = _entry(engine, email=f"rejected@{_DOMAIN}")
    with engine.begin() as conn:
        conn.execute(
            waitlist_entry.update().where(waitlist_entry.c.entry_id == entry_id)
            .values(rejected_at=_NOW)
        )
    with cognito() as (client, _stubber):
        assert sweep_once(engine, _identity(client), _settings(), now=_NOW) == SweepReport()


def test_sweep_retries_a_failed_row(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed audit outcome does not become a terminal request state."""
    _domain(engine)
    entry_id = _entry(engine, email=f"retry@{_DOMAIN}")
    original = commands.approve_request

    def fail_once(*args: object, **kwargs: object) -> object:
        monkeypatch.setattr(commands, "approve_request", original)
        raise RuntimeError("transient")

    monkeypatch.setattr(commands, "approve_request", fail_once)
    with cognito() as (client, stubber):
        assert sweep_once(engine, _identity(client), _settings(), now=_NOW) == SweepReport(failed=1)
        sub = fresh_sub("retry")
        expect_lookup(stubber, email=f"retry@{_DOMAIN}", sub=None)
        expect_create(stubber, email=f"retry@{_DOMAIN}", sub=sub)
        assert sweep_once(engine, _identity(client), _settings(), now=_NOW) == SweepReport(
            invited=1
        )
    with engine.connect() as conn:
        outcomes = (
            conn.execute(
                select(ops_action.c.outcome)
                .where(ops_action.c.target == str(entry_id))
                .order_by(ops_action.c.at)
            )
            .scalars()
            .all()
        )
    assert outcomes == ["failed", "invited"]


def test_sweep_enrols_existing_unenrolled_account_without_sending(engine: Engine) -> None:
    """An existing Cognito account is enrolled without AdminCreateUser."""
    _domain(engine)
    _entry(engine, email=f"existing@{_DOMAIN}")
    sub = fresh_sub("existing")
    with cognito() as (client, stubber):
        expect_lookup(stubber, email=f"existing@{_DOMAIN}", sub=sub)
        expect_enabled(stubber, sub=sub)
        assert sweep_once(engine, _identity(client), _settings(), now=_NOW) == SweepReport(
            enrolled=1
        )


def test_sweep_records_elsewhere_once(engine: Engine) -> None:
    """A terminal elsewhere result is logged and recorded only on its first tick."""
    other_org, _ = _domain(engine, domain="other.test")
    _domain(engine)
    entry_id = _entry(engine, email=f"elsewhere@{_DOMAIN}")
    sub = fresh_sub("elsewhere")
    with engine.begin() as conn:
        ops_enrol(conn, user_id=sub, org_id=other_org, email=f"elsewhere@{_DOMAIN}")
    with cognito() as (client, stubber), capture_logs() as logs:
        expect_lookup(stubber, email=f"elsewhere@{_DOMAIN}", sub=sub)
        expect_enabled(stubber, sub=sub)
        assert sweep_once(engine, _identity(client), _settings(), now=_NOW) == SweepReport(
            elsewhere=1
        )
        assert sweep_once(engine, _identity(client), _settings(), now=_NOW) == SweepReport()
    terminal = [event for event in logs if event["event"] == "ops.sweep_enrolled_elsewhere"]
    assert len(terminal) == 1
    with engine.connect() as conn:
        assert (
            conn.execute(
                select(ops_action.c.outcome).where(ops_action.c.target == str(entry_id))
            ).scalar_one()
            == "enrolled_elsewhere"
        )
        requests = list_requests(conn, _settings())
    assert next(item for item in requests.items if item.entry_id == entry_id).status == "check"


def test_sweep_never_reactivates_a_disabled_account(engine: Engine) -> None:
    """Task 066 B5: the public form is no way back in; the request waits as "check"."""
    org_id, _ = _domain(engine)
    entry_id = _entry(engine, email=f"gone@{_DOMAIN}")
    sub = fresh_sub("gone")
    with engine.begin() as conn:
        ops_enrol(conn, user_id=sub, org_id=org_id, email=f"gone@{_DOMAIN}")
    with cognito() as (client, stubber):
        expect_lookup(stubber, email=f"gone@{_DOMAIN}", sub=sub)
        expect_enabled(stubber, sub=sub, enabled=False)
        assert sweep_once(engine, _identity(client), _settings(), now=_NOW) == SweepReport(
            refused=1
        )
        assert sweep_once(engine, _identity(client), _settings(), now=_NOW) == SweepReport()
        stubber.assert_no_pending_responses()  # no AdminEnableUser, no invitation
    with engine.connect() as conn:
        assert conn.execute(
            select(ops_action.c.outcome).where(ops_action.c.target == str(entry_id))
        ).scalar_one() == "deactivated"
        requests = list_requests(conn, _settings())
    item = next(item for item in requests.items if item.entry_id == entry_id)
    assert (item.status, item.account_created_at) == ("check", None)


def test_sweep_stops_at_the_hourly_invitation_cap(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only invitation sends consume the durable hourly allowance."""
    _domain(engine)
    clock = [_NOW]
    monkeypatch.setattr(commands, "_now", lambda: clock[0])
    entries = [
        _entry(
            engine, email=f"cap-{index}@{_DOMAIN}", created_at=_NOW + timedelta(seconds=index)
        )
        for index in range(3)
    ]
    settings = replace(_settings(), self_signup_max_per_hour=2)
    with cognito() as (client, stubber):
        for index in range(2):
            email = f"cap-{index}@{_DOMAIN}"
            expect_lookup(stubber, email=email, sub=None)
            expect_create(stubber, email=email, sub=fresh_sub(f"cap-{index}"))
        assert sweep_once(engine, _identity(client), settings, now=_NOW) == SweepReport(
            invited=2, skipped_for_cap=1
        )
        expect_lookup(stubber, email=f"cap-2@{_DOMAIN}", sub=None)
        expect_create(stubber, email=f"cap-2@{_DOMAIN}", sub=fresh_sub("cap-2"))
        clock[0] = _NOW + timedelta(hours=1, seconds=1)
        assert sweep_once(
            engine, _identity(client), settings, now=_NOW + timedelta(hours=1, seconds=1)
        ) == SweepReport(invited=1)
    with engine.connect() as conn:
        assert conn.execute(
            select(waitlist_entry.c.account_created_at).where(
                waitlist_entry.c.entry_id == entries[-1]
            )
        ).scalar_one() == _NOW + timedelta(hours=1, seconds=1)


def test_sweep_without_identity_does_nothing(engine: Engine) -> None:
    """Local development without Cognito leaves the waitlist untouched."""
    _domain(engine)
    entry_id = _entry(engine, email=f"local@{_DOMAIN}")
    assert sweep_once(engine, Identity(None, None, None), _settings(), now=_NOW) == SweepReport()
    with engine.connect() as conn:
        assert (
            conn.execute(
                select(waitlist_entry.c.account_created_at).where(
                    waitlist_entry.c.entry_id == entry_id
                )
            ).scalar_one()
            is None
        )


def test_sweep_refuses_for_good_a_request_the_command_rejects(engine: Engine) -> None:
    """A deterministic refusal is terminal: no retry, no Cognito call, shown as Check."""
    _domain(engine)
    # A quote cannot be a Cognito filter literal, so the command refuses it every time.
    entry_id = _entry(engine, email=f'a"b@{_DOMAIN}')
    with cognito() as (client, stubber):
        assert sweep_once(engine, _identity(client), _settings(), now=_NOW) == SweepReport(
            refused=1
        )
        # The second tick skips it without a Cognito call (nothing queued on the stub).
        assert sweep_once(engine, _identity(client), _settings(), now=_NOW) == SweepReport()
        stubber.assert_no_pending_responses()
    with engine.connect() as conn:
        outcomes = (
            conn.execute(select(ops_action.c.outcome).where(ops_action.c.target == str(entry_id)))
            .scalars()
            .all()
        )
        stamped = conn.execute(
            select(waitlist_entry.c.account_created_at).where(waitlist_entry.c.entry_id == entry_id)
        ).scalar_one()
    assert outcomes == ["refused"]
    assert stamped is None


def test_failed_attempts_spend_the_hourly_budget(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A row that keeps failing cannot drive unbounded Cognito calls: it counts against the cap."""
    _domain(engine)
    _entry(engine, email=f"flaky@{_DOMAIN}", created_at=_NOW)
    _entry(engine, email=f"next@{_DOMAIN}", created_at=_NOW + timedelta(seconds=1))
    monkeypatch.setattr(commands, "_now", lambda: _NOW)

    def always_fail(*args: object, **kwargs: object) -> object:
        raise RuntimeError("transient")

    monkeypatch.setattr(commands, "approve_request", always_fail)
    settings = replace(_settings(), self_signup_max_per_hour=1)
    with cognito() as (client, _stubber):
        # One failure spends the hour's single allowance; the next row waits.
        assert sweep_once(engine, _identity(client), settings, now=_NOW) == SweepReport(
            failed=1, skipped_for_cap=1
        )
        # The hour has not passed: nothing is attempted.
        assert sweep_once(engine, _identity(client), settings, now=_NOW) == SweepReport(
            skipped_for_cap=2
        )
