"""Unit tests for the Metabase SSM allowlist validator and rule verifier."""

import pytest

from infra.metabase_allowlist import (
    metabase_rule_source_cidrs,
    parse_allowlist,
    validate_parameter_payload,
    verify_listener_rule,
)

METABASE_HOST = "metabase.v3.policyatlas.uk"


def _rule(host: str, source_cidrs: list[str] | None, priority: str = "20") -> dict:
    conditions = [
        {
            "Field": "host-header",
            "Values": [host],
            "HostHeaderConfig": {"Values": [host]},
        }
    ]
    if source_cidrs is not None:
        conditions.append(
            {
                "Field": "source-ip",
                "Values": [],
                "SourceIpConfig": {"Values": source_cidrs},
            }
        )
    return {"Priority": priority, "Conditions": conditions, "IsDefault": False}


DEFAULT_RULE = {"Priority": "default", "Conditions": [], "IsDefault": True}
API_RULE = _rule("api.v3.policyatlas.uk", None, priority="10")


@pytest.mark.parametrize(
    "value",
    [
        "192.0.2.10/32",
        "192.0.2.0/24,198.51.100.0/24",
        "192.0.2.10/32,198.51.100.0/24,203.0.113.0/25",
    ],
)
def test_valid_allowlists_are_accepted(value):
    validate_parameter_payload({"Type": "StringList", "Value": value})


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {"Type": "String", "Value": "192.0.2.10/32"},
        {"Type": "StringList", "Value": ""},
        {
            "Type": "StringList",
            "Value": "192.0.2.1/32,192.0.2.2/32,192.0.2.3/32,192.0.2.4/32",
        },
        {"Type": "StringList", "Value": "192.0.2.0/24, 198.51.100.0/24"},
        {"Type": "StringList", "Value": "192.0.2.10/24"},
        {"Type": "StringList", "Value": "not-a-cidr"},
        {"Type": "StringList", "Value": "0.0.0.0/0"},
        {"Type": "StringList", "Value": "::/0"},
        {"Type": "StringList", "Value": "255.255.255.255/32"},
        # The shared ALB is IPv4-only: an IPv6 entry can never match a client,
        # and an IPv6-only list would lock everyone out with a silent 404.
        {"Type": "StringList", "Value": "2001:db8::/48"},
        {"Type": "StringList", "Value": "192.0.2.0/24,2001:db8::/48"},
        {"Type": "StringList", "Value": "2001:db8::1/128"},
    ],
)
def test_invalid_allowlists_are_rejected(payload):
    with pytest.raises(ValueError):
        validate_parameter_payload(payload)


@pytest.mark.parametrize(
    "value",
    [
        "192.0.2.10/24",
        "192.0.2.0/24,2001:db8::/48",
        "192.0.2.0/24, 198.51.100.0/24",
        "0.0.0.0/0",
    ],
)
def test_error_messages_never_echo_the_offending_entry(value):
    with pytest.raises(ValueError) as error:
        parse_allowlist(value)
    message = str(error.value)
    assert not any(entry.strip() in message for entry in value.split(","))
    assert "entry" in message


def test_rule_lookup_returns_the_metabase_rule_source_cidrs():
    rules = [DEFAULT_RULE, API_RULE, _rule(METABASE_HOST, ["192.0.2.10/32"])]
    assert metabase_rule_source_cidrs({"Rules": rules}, METABASE_HOST) == {
        "192.0.2.10/32"
    }
    assert metabase_rule_source_cidrs(rules, METABASE_HOST) == {"192.0.2.10/32"}


@pytest.mark.parametrize(
    "rules",
    [
        [DEFAULT_RULE, API_RULE],
        [
            DEFAULT_RULE,
            _rule(METABASE_HOST, ["192.0.2.10/32"]),
            _rule(METABASE_HOST, ["198.51.100.0/24"], priority="21"),
        ],
        [DEFAULT_RULE, _rule(METABASE_HOST, None)],
        {"Rules": "not-a-list"},
    ],
)
def test_rule_lookup_rejects_missing_duplicate_or_unrestricted_rules(rules):
    with pytest.raises(ValueError):
        metabase_rule_source_cidrs(rules, METABASE_HOST)


def test_verify_listener_rule_accepts_a_matching_rule_in_any_order():
    rules = [
        DEFAULT_RULE,
        API_RULE,
        _rule(METABASE_HOST, ["198.51.100.0/24", "192.0.2.10/32"]),
    ]
    verify_listener_rule(rules, METABASE_HOST, "192.0.2.10/32,198.51.100.0/24")


@pytest.mark.parametrize(
    "applied",
    [
        ["192.0.2.10/32"],
        ["192.0.2.10/32", "198.51.100.0/24", "203.0.113.0/24"],
        ["192.0.2.11/32", "198.51.100.0/24"],
    ],
)
def test_verify_listener_rule_reports_drift_without_printing_addresses(applied):
    rules = [DEFAULT_RULE, _rule(METABASE_HOST, applied)]
    with pytest.raises(ValueError) as error:
        verify_listener_rule(rules, METABASE_HOST, "192.0.2.10/32,198.51.100.0/24")
    message = str(error.value)
    assert "does not match" in message
    assert not any(cidr in message for cidr in applied)
    assert "192.0.2.10/32" not in message


def test_verify_listener_rule_rejects_an_invalid_expected_value():
    rules = [DEFAULT_RULE, _rule(METABASE_HOST, ["2001:db8::/48"])]
    with pytest.raises(ValueError):
        verify_listener_rule(rules, METABASE_HOST, "2001:db8::/48")
