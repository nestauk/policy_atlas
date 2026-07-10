---
type: Integration quirk
title: SSRF-safe IP pinning belongs in the NetworkBackend, not a rewritten URL
description: httpcore pools connections by URL origin and derives SNI/Host from that origin, not the dial target — so pinning a validated IP means overriding connect_tcp, not swapping the host in the URL.
tags: [httpcore, ssrf, fetch_live, integration-quirk, "016", security]
timestamp: 2026-07-10
---

# Rule

httpcore pools connections by URL origin, and SNI/Host derive from that same
origin — not from wherever the socket actually dials. So SSRF-safe IP pinning
must live in a custom `NetworkBackend`'s `connect_tcp`: the URL keeps its
hostname (so connection pooling and TLS verification stay intact), while the
dial itself is redirected to the pre-validated resolved address. Do **not**
implement pinning by rewriting the URL to swap the hostname for the resolved
IP — that corrupts both pooling (a different origin per resolved IP) and SNI
(the certificate no longer matches). See `fetch_live.py::_PinnedIPNetworkBackend`.

# Why

This was the plan-stage adversarial review's blocker #3, and it was confirmed
working in the build without needing a non-pooled fallback path. It also has
a bonus property, verified by the 016 security lane: because the backend
dials the *exact validated sockaddr* returned by the same `getaddrinfo` call
that produced the address being checked, it closes the classic
check-then-re-resolve (TOCTOU) window — there is no second DNS lookup between
validation and dial for an attacker to race.

See also [[ip-refusal-allowlist-not-denylist]] — the classifier this backend
pins against.
