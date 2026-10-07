"""Validation and verification for the SSM-backed Metabase source-IP allowlist.

Both entry points read ``aws`` CLI JSON from stdin and never echo an address:
deploy logs are public for this repository, so every message reports positions
and counts rather than the CIDRs themselves.

* ``validate`` (the default) checks an SSM ``get-parameter`` payload before CDK
  runs.
* ``verify-rule`` checks, after CDK has run, that the shared listener's rule for
  the Metabase hostname carries exactly the allowlisted CIDRs. It reads
  ``describe-rules`` output from stdin and the expected parameter value from
  the ``METABASE_ALLOWLIST_VALUE`` environment variable.
"""

import argparse
import ipaddress
import json
import os
import sys

MAX_ALLOWLIST_ENTRIES = 3
EXPECTED_VALUE_ENVIRONMENT_VARIABLE = "METABASE_ALLOWLIST_VALUE"


def parse_allowlist(raw_value: str) -> list[ipaddress.IPv4Network]:
    """Parse the comma-separated allowlist into canonical IPv4 networks.

    Args:
        raw_value: The SSM ``StringList`` value, entries separated by commas.

    Returns:
        The allowlisted networks in their original order.

    Raises:
        ValueError: If the list is empty, too long, contains whitespace, or holds
            an entry that is malformed, non-canonical, universal, IPv6 (the shared
            ALB is IPv4-only, so an IPv6 entry can never match a client) or the
            broadcast address.
    """
    entries = raw_value.split(",") if raw_value else []
    if not 1 <= len(entries) <= MAX_ALLOWLIST_ENTRIES:
        raise ValueError(
            f"Metabase allowlist must contain one to {MAX_ALLOWLIST_ENTRIES} CIDRs"
        )

    networks: list[ipaddress.IPv4Network] = []
    for position, entry in enumerate(entries, start=1):
        if entry != entry.strip() or not entry:
            raise ValueError(
                f"Metabase allowlist entry {position} is empty or contains whitespace"
            )
        try:
            network = ipaddress.ip_network(entry, strict=True)
        except ValueError as error:
            raise ValueError(
                f"Metabase allowlist entry {position} is not a canonical CIDR"
            ) from error
        if isinstance(network, ipaddress.IPv6Network):
            raise ValueError(
                f"Metabase allowlist entry {position} is IPv6; the shared ALB is "
                "IPv4-only, so IPv6 entries can never match a client"
            )
        if network.prefixlen == 0:
            raise ValueError(
                f"Metabase allowlist entry {position} is a universal CIDR, which "
                "does not form an IP allowlist"
            )
        if network.network_address == ipaddress.IPv4Address("255.255.255.255"):
            raise ValueError(
                f"Metabase allowlist entry {position} is the broadcast address, "
                "which is not valid for an ALB rule"
            )
        networks.append(network)
    return networks


def validate_parameter_payload(payload: object) -> None:
    """Validate an AWS SSM ``get-parameter`` response payload.

    Args:
        payload: Decoded SSM parameter object containing ``Type`` and ``Value``.

    Raises:
        ValueError: If the parameter is not a one-to-three-entry IPv4 CIDR list.
    """
    if not isinstance(payload, dict):
        raise ValueError("SSM parameter payload must be an object")
    if payload.get("Type") != "StringList":
        raise ValueError("Metabase allowlist parameter must use type StringList")

    raw_value = payload.get("Value")
    if not isinstance(raw_value, str):
        raise ValueError("Metabase allowlist parameter value must be a string")
    parse_allowlist(raw_value)


def _condition_values(condition: dict, config_key: str) -> list[str]:
    config = condition.get(config_key)
    if isinstance(config, dict) and isinstance(config.get("Values"), list):
        return [str(value) for value in config["Values"]]
    values = condition.get("Values")
    return [str(value) for value in values] if isinstance(values, list) else []


def metabase_rule_source_cidrs(rules: object, host: str) -> set[str]:
    """Return the ``source-ip`` values of the listener rule for ``host``.

    Args:
        rules: Decoded ``aws elbv2 describe-rules`` output, either the ``Rules``
            list or the full response object.
        host: The Metabase hostname the rule must match on ``host-header``.

    Returns:
        The rule's source-IP CIDRs as written on the load balancer.

    Raises:
        ValueError: If there is not exactly one rule for the hostname, or that
            rule has no ``source-ip`` condition.
    """
    if isinstance(rules, dict):
        rules = rules.get("Rules")
    if not isinstance(rules, list):
        raise ValueError("describe-rules output must contain a Rules list")

    matching_rules = []
    for rule in rules:
        if not isinstance(rule, dict) or rule.get("IsDefault"):
            continue
        conditions = rule.get("Conditions", [])
        if any(
            condition.get("Field") == "host-header"
            and host in _condition_values(condition, "HostHeaderConfig")
            for condition in conditions
        ):
            matching_rules.append(rule)
    if len(matching_rules) != 1:
        raise ValueError(
            f"expected exactly one listener rule for the Metabase hostname, "
            f"found {len(matching_rules)}"
        )

    source_conditions = [
        condition
        for condition in matching_rules[0].get("Conditions", [])
        if condition.get("Field") == "source-ip"
    ]
    if len(source_conditions) != 1:
        raise ValueError(
            "the Metabase listener rule has no single source-ip condition"
        )
    return set(_condition_values(source_conditions[0], "SourceIpConfig"))


def verify_listener_rule(rules: object, host: str, expected_value: str) -> None:
    """Check that the live Metabase listener rule matches the SSM allowlist.

    Args:
        rules: Decoded ``aws elbv2 describe-rules`` output for the shared listener.
        host: The Metabase hostname.
        expected_value: The SSM allowlist value the rule must carry.

    Raises:
        ValueError: If the rule cannot be identified or its source-IP set differs
            from the allowlist. The message reports counts, never addresses.
    """
    expected = {str(network) for network in parse_allowlist(expected_value)}
    applied = set()
    for value in metabase_rule_source_cidrs(rules, host):
        try:
            applied.add(str(ipaddress.ip_network(value, strict=False)))
        except ValueError:
            applied.add(value)
    if applied != expected:
        raise ValueError(
            "the Metabase listener rule does not match the SSM allowlist: "
            f"{len(applied)} CIDR(s) applied, {len(expected)} allowlisted, "
            f"{len(applied ^ expected)} differ; redeploy the analytics stack"
        )


def _main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.set_defaults(command="validate")
    subcommands = parser.add_subparsers(dest="command")
    subcommands.add_parser("validate", help="validate a get-parameter payload")
    verify = subcommands.add_parser(
        "verify-rule", help="compare the live listener rule with the allowlist"
    )
    verify.add_argument("--host", required=True, help="Metabase hostname")
    arguments = parser.parse_args(argv)

    try:
        if arguments.command == "verify-rule":
            expected_value = os.environ.get(EXPECTED_VALUE_ENVIRONMENT_VARIABLE)
            if expected_value is None:
                raise ValueError(
                    f"{EXPECTED_VALUE_ENVIRONMENT_VARIABLE} must carry the SSM value"
                )
            verify_listener_rule(json.load(sys.stdin), arguments.host, expected_value)
        else:
            validate_parameter_payload(json.load(sys.stdin))
    except (json.JSONDecodeError, ValueError) as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    _main(sys.argv[1:])
