---
type: Integration quirk
title: uvicorn --proxy-headers with FORWARDED_ALLOW_IPS=* lets the client write the logged address; trust the VPC range only
description: With --proxy-headers uvicorn takes the client address from X-Forwarded-For when the connecting peer is trusted; "*" trusts every peer, so a client's own forged entry wins. uvicorn 0.51 accepts address ranges, so the container trusts the VPC CIDR (the load balancer's addresses) and nothing else. Nothing in the API decides on the client address, so a wrong value is a logging defect, not an access one (064a Q11).
tags: [uvicorn, proxy, x-forwarded-for, infra, logging, integration-quirk]
timestamp: 2026-11-16
---

# Rule

Behind a load balancer, uvicorn sees the balancer's address as the client unless it is
started with `--proxy-headers`, which makes it read `X-Forwarded-For`. It honours that
header only when the connecting peer is in `FORWARDED_ALLOW_IPS`. The tempting value `*`
trusts every peer, and then a client that writes its own `X-Forwarded-For` entry chooses
the address uvicorn logs.

The container therefore sets `FORWARDED_ALLOW_IPS` to the VPC (private network)
address range, `vpc.vpc_cidr_block` from the network stack, which is where the load
balancer's nodes live. uvicorn 0.51 (pinned in `uv.lock`) parses ranges with
`ipaddress.ip_network` and walks `X-Forwarded-For` from the right, skipping trusted hops,
so the first untrusted address is the real client — the right outcome, whatever the
contract's "leftmost" wording said.

Two facts that bound the risk either way: the API is served straight from the load
balancer (host-header rule), not through CloudFront; and nothing in `backend/src` reads
`request.client` or any `X-Forwarded-*` header for a decision. A wrong value would change
access-log text only.

The same `CMD` change sets `--timeout-keep-alive 125` (the balancer keeps idle
connections 120 s; uvicorn's 5 s default closed them first and produced 502s) and
`--no-server-header`.

# Citations

- `backend/Dockerfile` — the `CMD`.
- `infra/infra/policy_atlas_stack.py` — `FORWARDED_ALLOW_IPS`; `infra/tests/unit/test_service_wiring.py`.
- `backend/.venv/lib/python3.12/site-packages/uvicorn/middleware/proxy_headers.py` (0.51).
- [task 064a contract](../tasks/064a-security-quick-wins/contract.md) Q11.
