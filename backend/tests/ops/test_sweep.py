"""Acceptance tests for the synchronous, clock-injected self-signup sweep."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import delete, insert, select, text
from sqlalchemy.engine import Engine
from structlog.testing import capture_logs

from policy_atlas.api.deps import Identity
from policy_atlas.api.routers.ops import list_requests
from policy_atlas.api.settings import Settings
from policy_atlas.core import invite_code
from policy_atlas.core.schema import (
    app_user,
    cohort_member,
    invite_link,
    invite_link_cohort,
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

#: An email domain that is never listed; only an invite link lets it in.
_LINK_DOMAIN = f"link-{uuid.uuid4().hex[:8]}.test"
_LINK_LABEL = "Sweep link"


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
        links = select(invite_link.c.invite_link_id).where(invite_link.c.label == _LINK_LABEL)
        conn.execute(delete(invite_link_cohort).where(invite_link_cohort.c.invite_link_id.in_(links)))
        conn.execute(delete(invite_link).where(invite_link.c.label == _LINK_LABEL))
        # Other modules list nesta.org.uk and leave rows under it; unlist
        # everything but this module's domain so the sweep sees only its rows.
        conn.execute(delete(organisation_domain).where(organisation_domain.c.domain != _DOMAIN))


def _entry(
    engine: Engine, *, email: str, created_at: datetime = _NOW, **values: Any
) -> uuid.UUID:
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
                **values,
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
    """A failed request is not terminal: it waits fifteen minutes, then is tried again."""
    _domain(engine)
    entry_id = _entry(engine, email=f"retry@{_DOMAIN}")
    monkeypatch.setattr(commands, "_now", lambda: _NOW)
    original = commands.approve_request

    def fail_once(*args: object, **kwargs: object) -> object:
        monkeypatch.setattr(commands, "approve_request", original)
        raise RuntimeError("transient")

    monkeypatch.setattr(commands, "approve_request", fail_once)
    with cognito() as (client, stubber):
        assert sweep_once(engine, _identity(client), _settings(), now=_NOW) == SweepReport(failed=1)
        assert sweep_once(
            engine, _identity(client), _settings(), now=_NOW + timedelta(minutes=14)
        ) == SweepReport()
        sub = fresh_sub("retry")
        expect_lookup(stubber, email=f"retry@{_DOMAIN}", sub=None)
        expect_create(stubber, email=f"retry@{_DOMAIN}", sub=sub)
        assert sweep_once(
            engine, _identity(client), _settings(), now=_NOW + timedelta(minutes=15)
        ) == SweepReport(invited=1)
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
        # The hour has not passed: nothing is attempted. The failed row waits
        # out its retry pause, so only the next row is held back by the cap.
        assert sweep_once(engine, _identity(client), settings, now=_NOW) == SweepReport(
            skipped_for_cap=1
        )


# --- invite links ---------------------------------------------------------------


def _org(engine: Engine) -> commands.Organisation:
    """Commit an organisation with no listed domain."""
    with engine.begin() as conn:
        org_id = make_org(conn, name="Link Org")
        name = conn.execute(
            select(organisation.c.name).where(organisation.c.org_id == org_id)
        ).scalar_one()
    return commands.Organisation(org_id=org_id, name=str(name))


def _cohort(engine: Engine) -> commands.Cohort:
    """Commit a cohort."""
    with engine.begin() as conn:
        return commands.save_cohort(
            conn, cohort_id=None, name=f"Sweep cohort {uuid.uuid4()}", description=None,
            starts_on=None, ends_on=None, links=[],
        )


def _link(
    engine: Engine,
    *,
    org: commands.Organisation,
    domains: tuple[str, ...] = (_LINK_DOMAIN,),
    max_uses: int = 5,
    cohorts: tuple[commands.Cohort, ...] = (),
    made: datetime = _NOW,
    expires_at: datetime | None = None,
) -> commands.InviteLink:
    """Commit an invite link, made at ``made``."""
    with engine.begin() as conn:
        return commands.create_invite_link(
            conn, label=_LINK_LABEL, org=org, cohorts=cohorts, allowed_domains=domains,
            max_uses=max_uses, expires_at=expires_at or made + timedelta(days=30),
            created_by="operator", now=made,
        )


def _used(engine: Engine, link: commands.InviteLink) -> None:
    """Commit one earlier request that the link already redeemed."""
    _entry(
        engine, email=f"earlier-{uuid.uuid4().hex[:8]}@{_LINK_DOMAIN}",
        created_at=_NOW - timedelta(days=1), account_user_id="earlier",
        account_created_at=_NOW - timedelta(days=1), invite_link_id=link.invite_link_id,
    )


def _request(engine: Engine, entry_id: uuid.UUID) -> Any:
    """Read one waitlist row."""
    with engine.connect() as conn:
        return conn.execute(
            select(waitlist_entry).where(waitlist_entry.c.entry_id == entry_id)
        ).mappings().one()


def _org_of(engine: Engine, sub: str) -> Any:
    """Read the organisation of one account."""
    with engine.connect() as conn:
        return conn.execute(
            select(app_user.c.org_id).where(app_user.c.user_id == sub)
        ).scalar_one()


def _cohorts_of(engine: Engine, sub: str) -> set[uuid.UUID]:
    """Read the cohorts one account is in."""
    with engine.connect() as conn:
        return set(conn.execute(
            select(cohort_member.c.cohort_id).where(cohort_member.c.user_id == sub)
        ).scalars())


def _sweep_audit(engine: Engine) -> list[tuple[str, str | None, str]]:
    """Read every audit row the sweep wrote, oldest first."""
    with engine.connect() as conn:
        return [
            (row.action, row.target, row.outcome)
            for row in conn.execute(
                select(ops_action).where(ops_action.c.actor_user_id == "sweep")
                .order_by(ops_action.c.at, ops_action.c.action)
            )
        ]


def _expect_invitation(stubber: Any, email: str, label: str) -> str:
    """Queue the lookup and create of a new account; return its subject."""
    sub = fresh_sub(label)
    expect_lookup(stubber, email=email, sub=None)
    expect_create(stubber, email=email, sub=sub)
    return sub


_REASONS = ("revoked", "expired", "full", "wrong_domain", "unknown_code")


def _unredeemable(
    engine: Engine, reason: str, *, org: commands.Organisation, domain: str,
    cohort: commands.Cohort,
) -> str:
    """Return a code that does not redeem a request in ``domain``, for ``reason``."""
    if reason == "unknown_code":
        return invite_code.new_code()
    if reason == "wrong_domain":
        return _link(engine, org=org, domains=("elsewhere.test",), cohorts=(cohort,)).code
    if reason == "expired":
        return _link(
            engine, org=org, domains=(domain,), cohorts=(cohort,),
            made=_NOW - timedelta(days=40), expires_at=_NOW - timedelta(days=1),
        ).code
    link = _link(engine, org=org, domains=(domain,), max_uses=1, cohorts=(cohort,))
    if reason == "revoked":
        with engine.begin() as conn:
            commands.revoke_invite_link(conn, invite_link_id=link.invite_link_id, now=_NOW)
    else:
        _used(engine, link)
    return link.code


def test_sweep_redeems_a_link_when_no_domain_is_listed(engine: Engine) -> None:
    """The account lands in the link's organisation and cohort; the request records the link."""
    with engine.begin() as conn:
        conn.execute(delete(organisation_domain))
    org, group = _org(engine), _cohort(engine)
    link = _link(engine, org=org, cohorts=(group,))
    email = f"pilot@{_LINK_DOMAIN}"
    entry_id = _entry(engine, email=email, invite_code=link.code)
    with cognito() as (client, stubber):
        sub = _expect_invitation(stubber, email, "pilot")
        assert sweep_once(engine, _identity(client), _settings(), now=_NOW) == SweepReport(
            invited=1
        )
    row = _request(engine, entry_id)
    assert (row["account_user_id"], row["invite_link_id"]) == (sub, link.invite_link_id)
    assert _org_of(engine, sub) == org.org_id
    assert _cohorts_of(engine, sub) == {group.cohort_id}
    assert sorted(_sweep_audit(engine)) == [
        ("cohort.add", f"{sub}/cohort/{group.cohort_id}", "ok"),
        ("invite", str(entry_id), "invited"),
    ]


def test_a_link_with_two_domains_redeems_a_request_from_each(engine: Engine) -> None:
    """Each of a link's domains lets a request in."""
    second = f"second-{_LINK_DOMAIN}"
    link = _link(engine, org=_org(engine), domains=(_LINK_DOMAIN, second))
    emails = [f"one@{_LINK_DOMAIN}", f"two@{second}"]
    entries = [
        _entry(engine, email=email, invite_code=link.code, created_at=_NOW + timedelta(seconds=i))
        for i, email in enumerate(emails)
    ]
    with cognito() as (client, stubber):
        for i, email in enumerate(emails):
            _expect_invitation(stubber, email, f"domain-{i}")
        assert sweep_once(engine, _identity(client), _settings(), now=_NOW) == SweepReport(
            invited=2
        )
    assert [_request(engine, e)["invite_link_id"] for e in entries] == [link.invite_link_id] * 2


@pytest.mark.parametrize("reason", _REASONS)
def test_an_unredeemable_code_in_an_unlisted_domain_waits_untouched(
    engine: Engine, reason: str
) -> None:
    """No account, no Cognito call and no audit row: the request just waits."""
    code = _unredeemable(
        engine, reason, org=_org(engine), domain=_LINK_DOMAIN, cohort=_cohort(engine)
    )
    entry_id = _entry(engine, email=f"waits@{_LINK_DOMAIN}", invite_code=code)
    with cognito() as (client, stubber):
        assert sweep_once(engine, _identity(client), _settings(), now=_NOW) == SweepReport()
        stubber.assert_no_pending_responses()
    row = _request(engine, entry_id)
    assert (row["account_created_at"], row["invite_link_id"]) == (None, None)
    assert _sweep_audit(engine) == []


@pytest.mark.parametrize("reason", _REASONS)
def test_an_unredeemable_code_in_a_listed_domain_gets_the_listed_domain_account(
    engine: Engine, reason: str
) -> None:
    """A code never holds back a listed-domain request; the link gives no cohort and no use."""
    org_id, _ = _domain(engine)
    code = _unredeemable(engine, reason, org=_org(engine), domain=_DOMAIN, cohort=_cohort(engine))
    email = f"listed@{_DOMAIN}"
    entry_id = _entry(engine, email=email, invite_code=code)
    with cognito() as (client, stubber):
        sub = _expect_invitation(stubber, email, "listed")
        assert sweep_once(engine, _identity(client), _settings(), now=_NOW) == SweepReport(
            invited=1
        )
    assert _org_of(engine, sub) == org_id
    assert _cohorts_of(engine, sub) == set()
    assert _request(engine, entry_id)["invite_link_id"] is None


def test_a_redeemable_code_in_a_listed_domain_gives_the_link_organisation(engine: Engine) -> None:
    """A link takes precedence over the listed domain."""
    _domain(engine)
    org = _org(engine)
    link = _link(engine, org=org, domains=(_DOMAIN,))
    email = f"both@{_DOMAIN}"
    entry_id = _entry(engine, email=email, invite_code=link.code)
    with cognito() as (client, stubber):
        sub = _expect_invitation(stubber, email, "both")
        assert sweep_once(engine, _identity(client), _settings(), now=_NOW) == SweepReport(
            invited=1
        )
    assert _org_of(engine, sub) == org.org_id
    assert _request(engine, entry_id)["invite_link_id"] == link.invite_link_id


def test_a_link_with_one_use_left_redeems_one_of_two_requests(engine: Engine) -> None:
    """The second request finds the link full under its lock and waits."""
    link = _link(engine, org=_org(engine), max_uses=1)
    first = _entry(engine, email=f"first@{_LINK_DOMAIN}", invite_code=link.code)
    second = _entry(
        engine, email=f"second@{_LINK_DOMAIN}", invite_code=link.code,
        created_at=_NOW + timedelta(seconds=1),
    )
    with cognito() as (client, stubber):
        _expect_invitation(stubber, f"first@{_LINK_DOMAIN}", "first")
        assert sweep_once(engine, _identity(client), _settings(), now=_NOW) == SweepReport(
            invited=1
        )
        stubber.assert_no_pending_responses()
    assert _request(engine, first)["invite_link_id"] == link.invite_link_id
    assert _request(engine, second)["account_created_at"] is None
    assert [row[2] for row in _sweep_audit(engine)] == ["invited"]


def test_two_redemptions_of_one_link_at_once_end_with_one_use(engine: Engine) -> None:
    """Two connections redeem against a link with one use left: no deadlock, one use."""
    link = _link(engine, org=_org(engine), max_uses=1)
    emails = [f"race-a@{_LINK_DOMAIN}", f"race-b@{_LINK_DOMAIN}"]
    entries = [_entry(engine, email=email, invite_code=link.code) for email in emails]
    first_redeemed, release = threading.Event(), threading.Event()
    second_pid: list[int] = []
    results: dict[uuid.UUID, object] = {}
    errors: list[BaseException] = []

    def redeem(entry_id: uuid.UUID, client: Any, *, hold: bool) -> None:
        try:
            with engine.begin() as conn:
                conn.execute(text("SET LOCAL lock_timeout = '20s'"))
                if not hold:
                    second_pid.append(conn.execute(text("SELECT pg_backend_pid()")).scalar_one())
                results[entry_id] = commands.redeem_request(
                    conn, client, pool_id=POOL_ID, entry_id=entry_id, now=_NOW
                )
                if hold:
                    first_redeemed.set()
                    release.wait(20)
        except BaseException as error:  # surfaced by the assertion below
            errors.append(error)

    def waiting_on_a_lock(pid: int) -> bool:
        with engine.connect() as conn:
            return conn.execute(
                text("SELECT wait_event_type = 'Lock' FROM pg_stat_activity WHERE pid = :pid"),
                {"pid": pid},
            ).scalar_one_or_none() is True

    with cognito() as (client_a, stub_a), cognito() as (client_b, stub_b):
        _expect_invitation(stub_a, emails[0], "race-a")
        holder = threading.Thread(
            target=redeem, args=(entries[0], client_a), kwargs={"hold": True}
        )
        holder.start()
        assert first_redeemed.wait(20)
        waiter = threading.Thread(
            target=redeem, args=(entries[1], client_b), kwargs={"hold": False}
        )
        waiter.start()
        deadline = time.monotonic() + 20
        while not (second_pid and waiting_on_a_lock(second_pid[0])):
            assert time.monotonic() < deadline, "the second redemption never waited on the link"
            time.sleep(0.05)
        release.set()
        holder.join(30)
        waiter.join(30)
        assert not holder.is_alive() and not waiter.is_alive()
        stub_b.assert_no_pending_responses()
    assert errors == []
    assert results[entries[0]] is not None and results[entries[1]] is None
    with engine.connect() as conn:
        assert commands.invite_link_uses(conn, link.invite_link_id) == 1


def test_a_tick_that_finds_another_running_does_nothing(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second tick that starts while one runs makes no attempt and says so."""
    _domain(engine)
    email = f"first@{_DOMAIN}"
    _entry(engine, email=email)
    original = commands.approve_request
    inner: list[SweepReport] = []

    def approve_while_a_second_tick_starts(*args: Any, **kwargs: Any) -> Any:
        if inner:  # the second tick reached an attempt: fail it visibly
            raise RuntimeError("a second tick ran")
        inner.append(SweepReport(failed=-1))
        inner[0] = sweep_once(engine, _identity(args[1]), _settings(), now=_NOW)
        return original(*args, **kwargs)

    monkeypatch.setattr(commands, "approve_request", approve_while_a_second_tick_starts)
    with cognito() as (client, stubber), capture_logs() as logs:
        _expect_invitation(stubber, email, "first")
        assert sweep_once(engine, _identity(client), _settings(), now=_NOW) == SweepReport(
            invited=1
        )
    assert inner == [SweepReport()]
    assert [e.get("reason") for e in logs if e["event"] == "ops.sweep_skipped"] == [
        "tick_running"
    ]


def test_unknown_codes_never_crowd_out_a_redeemable_request(engine: Engine) -> None:
    """250 older requests with unknown codes do not stop a redeemable one in the same tick."""
    link = _link(engine, org=_org(engine))
    with engine.begin() as conn:
        conn.execute(insert(waitlist_entry), [
            {"entry_id": uuid.uuid4(), "email": f"stranger-{i}@{_LINK_DOMAIN}",
             "name": "Sweep Person", "role_or_reason": "r", "invite_code": invite_code.new_code(),
             "created_at": _NOW - timedelta(days=1) + timedelta(seconds=i)}
            for i in range(250)
        ])
    email = f"invited@{_LINK_DOMAIN}"
    entry_id = _entry(engine, email=email, invite_code=link.code)
    with cognito() as (client, stubber):
        _expect_invitation(stubber, email, "crowd")
        assert sweep_once(engine, _identity(client), _settings(), now=_NOW) == SweepReport(
            invited=1
        )
    assert _request(engine, entry_id)["invite_link_id"] == link.invite_link_id


def test_a_request_that_always_fails_spends_at_most_four_of_the_hour(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ticked every minute for an hour it is tried every fifteen; a later request is served."""
    _domain(engine)
    flaky = _entry(engine, email=f"flaky@{_DOMAIN}")
    later = _entry(engine, email=f"later@{_DOMAIN}", created_at=_NOW + timedelta(seconds=1))
    clock = [_NOW]
    monkeypatch.setattr(commands, "_now", lambda: clock[0])
    original = commands.approve_request

    def fail_for_flaky(*args: Any, **kwargs: Any) -> Any:
        if kwargs["entry_id"] == flaky:
            raise RuntimeError("transient")
        return original(*args, **kwargs)

    monkeypatch.setattr(commands, "approve_request", fail_for_flaky)
    with cognito() as (client, stubber):
        _expect_invitation(stubber, f"later@{_DOMAIN}", "later")
        for minute in range(60):
            clock[0] = _NOW + timedelta(minutes=minute)
            sweep_once(engine, _identity(client), _settings(), now=clock[0])
    assert _request(engine, later)["account_created_at"] == _NOW
    assert [row for row in _sweep_audit(engine) if row[2] == "failed"] == [
        ("invite", str(flaky), "failed")
    ] * 4


def test_a_deactivated_person_and_a_rejected_request_get_no_account_through_a_link(
    engine: Engine,
) -> None:
    """Deactivated is refused as Check; rejected is never tried; neither counts a use."""
    org = _org(engine)
    link = _link(engine, org=org)
    gone_email = f"gone@{_LINK_DOMAIN}"
    gone = _entry(engine, email=gone_email, invite_code=link.code)
    rejected = _entry(
        engine, email=f"rejected@{_LINK_DOMAIN}", invite_code=link.code, rejected_at=_NOW,
        created_at=_NOW + timedelta(seconds=1),
    )
    sub = fresh_sub("gone")
    with engine.begin() as conn:
        ops_enrol(conn, user_id=sub, org_id=org.org_id, email=gone_email)
    with cognito() as (client, stubber):
        expect_lookup(stubber, email=gone_email, sub=sub)
        expect_enabled(stubber, sub=sub, enabled=False)
        assert sweep_once(engine, _identity(client), _settings(), now=_NOW) == SweepReport(
            refused=1
        )
        stubber.assert_no_pending_responses()
    assert [_request(engine, e)["account_created_at"] for e in (gone, rejected)] == [None, None]
    assert _sweep_audit(engine) == [("invite", str(gone), "deactivated")]
    with engine.connect() as conn:
        assert commands.invite_link_uses(conn, link.invite_link_id) == 0


def test_raising_the_maximum_makes_a_waiting_request_redeemable(engine: Engine) -> None:
    """A full link redeems its waiting request at the next tick after the edit."""
    link = _link(engine, org=_org(engine), max_uses=1)
    _used(engine, link)
    email = f"waiting@{_LINK_DOMAIN}"
    entry_id = _entry(engine, email=email, invite_code=link.code)
    with cognito() as (client, stubber):
        assert sweep_once(engine, _identity(client), _settings(), now=_NOW) == SweepReport()
        with engine.begin() as conn:
            commands.update_invite_link(
                conn, invite_link_id=link.invite_link_id, label=_LINK_LABEL, max_uses=2,
                expires_at=link.expires_at, now=_NOW,
            )
        _expect_invitation(stubber, email, "raised")
        assert sweep_once(engine, _identity(client), _settings(), now=_NOW) == SweepReport(
            invited=1
        )
    assert _request(engine, entry_id)["invite_link_id"] == link.invite_link_id


def test_redemptions_and_listed_domain_invitations_share_the_hourly_cap(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A redemption spends the cap as an invitation does."""
    _domain(engine)
    monkeypatch.setattr(commands, "_now", lambda: _NOW)
    link = _link(engine, org=_org(engine))
    redeemed = _entry(engine, email=f"link@{_LINK_DOMAIN}", invite_code=link.code)
    listed = _entry(engine, email=f"listed@{_DOMAIN}", created_at=_NOW + timedelta(seconds=1))
    held = _entry(engine, email=f"held@{_DOMAIN}", created_at=_NOW + timedelta(seconds=2))
    settings = replace(_settings(), self_signup_max_per_hour=2)
    with cognito() as (client, stubber):
        _expect_invitation(stubber, f"link@{_LINK_DOMAIN}", "cap-link")
        _expect_invitation(stubber, f"listed@{_DOMAIN}", "cap-listed")
        assert sweep_once(engine, _identity(client), settings, now=_NOW) == SweepReport(
            invited=2, skipped_for_cap=1
        )
        assert sweep_once(engine, _identity(client), settings, now=_NOW) == SweepReport(
            skipped_for_cap=1
        )
    assert [_request(engine, e)["account_created_at"] is not None
            for e in (redeemed, listed, held)] == [True, True, False]


def test_the_invite_code_is_in_no_sweep_log_line_or_audit_row(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Neither a redemption nor a failed one writes the code anywhere."""
    link = _link(engine, org=_org(engine), cohorts=(_cohort(engine),))
    redeemed_email = f"logged@{_LINK_DOMAIN}"
    _entry(engine, email=redeemed_email, invite_code=link.code)
    failing = _entry(
        engine, email=f"failing@{_LINK_DOMAIN}", invite_code=link.code,
        created_at=_NOW + timedelta(seconds=1),
    )
    original = commands.approve_request

    def fail_one(*args: Any, **kwargs: Any) -> Any:
        if kwargs["entry_id"] == failing:
            raise RuntimeError("transient")
        return original(*args, **kwargs)

    monkeypatch.setattr(commands, "approve_request", fail_one)
    with cognito() as (client, stubber), capture_logs() as logs:
        _expect_invitation(stubber, redeemed_email, "logged")
        assert sweep_once(engine, _identity(client), _settings(), now=_NOW) == SweepReport(
            invited=1, failed=1
        )
    with engine.connect() as conn:
        rows = [dict(row) for row in conn.execute(select(ops_action)).mappings()]
    assert logs and rows
    for written in (str(logs), str(rows)):
        assert link.code not in written and invite_code.display(link.code) not in written
