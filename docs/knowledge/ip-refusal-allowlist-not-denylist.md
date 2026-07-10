---
type: Convention
title: IP refusal for SSRF safety is allowlist-shaped, not denylist-shaped
description: Enumerating denylist properties (is_private/is_loopback/is_link_local/...) chases reserved ranges forever — Python's is_private misses RFC 6598 CGNAT space; the safe refusal is "refuse anything not is_global".
tags: [convention, security, ssrf, fetch_live, "016"]
timestamp: 2026-07-10
---

# Rule

Refusing "internal" IPs by enumerating denylist properties
(`is_private`/`is_loopback`/`is_link_local`/…) chases reserved ranges forever
and misses gaps. Python's `ipaddress.is_private` is `False` for the RFC 6598
CGNAT space `100.64.0.0/10` — a range that routes to internal infrastructure
in common cloud deployments. The refusal must instead be allowlist-shaped:
refuse anything where `not ip.is_global`, after unwrapping IPv4-mapped IPv6
addresses first (`::ffff:x.x.x.x` must resolve to the underlying IPv4
address before the check, or the wrapper bypasses it). See
`fetch_live.py::_is_refused_ip`; the explicit denylist is retained alongside
this as belt-and-braces, not as the primary check. The test matrix includes
both `100.64.0.1` and `::ffff:100.64.0.1` as required bypass-family cases.

# Why

Found by the 016 security lane, which empirically tested the classifier
against known bypass families rather than trusting the denylist's apparent
completeness. A denylist is a list of things you remembered to exclude; an
allowlist on `is_global` is a list of the one thing that's actually safe —
the failure mode of the former is silent (a valid-looking IP sails through
because nobody added its range to the list), while the latter fails closed
by construction.
