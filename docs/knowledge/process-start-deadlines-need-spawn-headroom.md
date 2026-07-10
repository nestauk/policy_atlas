---
type: Testing rule
title: A deadline clock that starts at Process.start() is really asserting "spawn + import < deadline"
description: On a loaded host, child-process spawn plus package import can exceed a tight parse deadline before the worker runs a line of real work — mislabelling a healthy worker as the very timeout the test rules out.
tags: [testing, multiprocessing, timeouts, flakiness]
timestamp: 2026-07-10
---

# Rule

When a test's deadline clock starts at `Process.start()`, the deadline bounds
*spawn + interpreter start + package import + work*, not just the work.
Deadlines guarding drain/lapse logic need spawn headroom (5 s → 20 s in
`tests/test_ingest_full_text.py`, task 017) or a start-signal handshake so the
clock starts when the child is actually running.

# Why

During 017's build the host was heavily loaded (swap-exhausted; see
[macOS swap presents as a Docker wedge](macos-swap-presents-as-docker-wedge.md)):
child spawn + import alone exceeded
the 5 s `parse_timeout`, so the lapsed-deadline sibling test failed by
asserting the exact condition it existed to rule out. The asserted property (a
lapsed-deadline sibling's buffered `ok` must be honoured) was never wrong —
the clock was.

# Watch out

This inverts only under load, so it presents as flakiness in CI or busy dev
hosts and passes everywhere else.
