---
type: Testing rule
title: pytest-socket denies only the current process and raises SocketConnectBlockedError
description: The suite-wide socket deny patches socket in the pytest process only — multiprocessing-worker guards must stay — and a blocked connect raises SocketConnectBlockedError, which is NOT a subclass of SocketBlockedError.
tags: [pytest-socket, testing, egress, multiprocessing]
timestamp: 2026-07-12
---

# Rule

The suite runs under `pytest-socket`'s deny-by-default (`--disable-socket
--allow-hosts=localhost,127.0.0.1,::1` in `pyproject.toml` addopts) — that is the
egress belt for every test. Two sharp edges:

1. **Process-local**: pytest-socket monkeypatches `socket` in the pytest process only.
   Code that spawns workers (`multiprocessing`, the 016 ingest parse pool) escapes the
   deny — the 016 worker-process guard and the fetch_live SSRF-assertion monkeypatches
   are deliberately kept, not redundant.
2. **Exception taxonomy**: a blocked *connect* (allow-hosts mode) raises
   `SocketConnectBlockedError`, which is **not** a subclass of `SocketBlockedError`
   (raised in full-deny mode). A test asserting the wrong one passes under one config
   and fails under the other.

# Why

019 item 7b replaced five per-test deny patterns with the suite-wide deny; the pin
(`tests/test_socket_policy.py`) proves the policy on the whole suite including ingest
integration. The two edges above are exactly what the retirement sweep could NOT
retire — recorded so the next sweep doesn't "finish the job" and open egress holes.

# Watch out

- A future test helper that spawns a process gets no socket protection for free; add
  its own guard.
- The DB allowlist is loopback-shaped; a containerised DB on a non-loopback host would
  need an explicit `--allow-hosts` change (an approval-gated test-infra edit).

# Citations

- `pyproject.toml` (addopts), `tests/test_socket_policy.py` (suite-wide pin)
- [019 verification.md](../tasks/019-folding-pass/verification.md) (A3 phase; gate 4)
