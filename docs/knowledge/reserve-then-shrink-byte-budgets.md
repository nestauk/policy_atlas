---
type: Invariant
title: Byte/resource budgets must reserve-then-shrink, never grow-on-release
description: Any shared budget where in-flight holders can block mid-stream on releases only other holders can produce is a deadlock; reserve the full per-item cap up front, then shrink to actual size on completion.
tags: [concurrency, deadlock, budgets, fetch_live, "016", invariant]
timestamp: 2026-07-10
---

# Rule

Any byte/resource budget shared across concurrent in-flight holders must be
**reserved at the per-item cap before streaming starts**, then **shrunk to
the actual size on completion** — never grown incrementally as bytes arrive.
Growing-on-demand means a holder can block mid-stream waiting for budget that
only another holder — itself blocked mid-stream — can release: a deadlock,
reachable in 016's shape at 10 workers × 25MB per-item cap against a 100MB
total budget. The composable form (`fetch_live.py::_read_capped_body`):
reserve the full per-item cap up front, blocking only while holding nothing;
stream; shrink the reservation to the actual size when the read completes.

# Why

This was found by lead review of the *composed* pipeline, not by any single
component's tests — each component in isolation looked correct. Two
review-verified corollaries follow from the same reserve-then-shrink shape:

- **Content-Length cannot size the reservation.** httpx's `iter_bytes()`
  yields *decoded* bytes while `Content-Length` is the *compressed* transfer
  size, so a CL-based reservation under-reserves on routinely compressed
  responses — the 016 review stack refuted that "optimization" outright.
- **The budget wait is bounded (300s) and fails loudly**, so a lease-
  accounting leak can never become a silent wedge — it becomes a loud
  timeout instead.
