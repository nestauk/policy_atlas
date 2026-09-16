"""Unit tests for the Metabase SSM allowlist validator."""

import pytest

from infra.metabase_allowlist import validate_parameter_payload


@pytest.mark.parametrize(
    "value",
    [
        "192.0.2.10/32",
        "192.0.2.0/24,2001:db8::/48",
        "192.0.2.10/32,198.51.100.0/24,2001:db8::1/128",
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
        {"Type": "StringList", "Value": "192.0.2.0/24, 2001:db8::/48"},
        {"Type": "StringList", "Value": "192.0.2.10/24"},
        {"Type": "StringList", "Value": "not-a-cidr"},
        {"Type": "StringList", "Value": "0.0.0.0/0"},
        {"Type": "StringList", "Value": "::/0"},
        {"Type": "StringList", "Value": "255.255.255.255/32"},
    ],
)
def test_invalid_allowlists_are_rejected(payload):
    with pytest.raises(ValueError):
        validate_parameter_payload(payload)
