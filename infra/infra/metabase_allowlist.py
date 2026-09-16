"""Validation for the SSM-backed Metabase source-IP allowlist."""

import ipaddress
import json
import sys


def validate_parameter_payload(payload: object) -> None:
    """Validate an AWS SSM ``get-parameter`` response payload.

    Args:
        payload: Decoded SSM parameter object containing ``Type`` and ``Value``.

    Raises:
        ValueError: If the parameter is not a one-to-three-entry CIDR list.
    """
    if not isinstance(payload, dict):
        raise ValueError("SSM parameter payload must be an object")
    if payload.get("Type") != "StringList":
        raise ValueError("Metabase allowlist parameter must use type StringList")

    raw_value = payload.get("Value")
    if not isinstance(raw_value, str):
        raise ValueError("Metabase allowlist parameter value must be a string")
    cidrs = raw_value.split(",") if raw_value else []
    if not 1 <= len(cidrs) <= 3:
        raise ValueError("Metabase allowlist must contain one to three CIDRs")

    for cidr in cidrs:
        if cidr != cidr.strip() or not cidr:
            raise ValueError("Metabase allowlist CIDRs must not contain whitespace")
        try:
            network = ipaddress.ip_network(cidr, strict=True)
        except ValueError as error:
            raise ValueError(f"Invalid or non-canonical CIDR: {cidr}") from error
        if network.prefixlen == 0:
            raise ValueError("Universal CIDRs do not form an IP allowlist")
        if (
            isinstance(network, ipaddress.IPv4Network)
            and network.prefixlen == 32
            and network.network_address == ipaddress.IPv4Address("255.255.255.255")
        ):
            raise ValueError("255.255.255.255/32 is not valid for an ALB rule")


def _main() -> None:
    try:
        validate_parameter_payload(json.load(sys.stdin))
    except (json.JSONDecodeError, ValueError) as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    _main()
