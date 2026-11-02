---
type: Testing rule
title: A poll-deadline test that fails under load is re-run alone, then checked for a race, then widened, never its assertion
description: Thread tests with a fixed deadline or sleep fail under the parallel suite or several agents' load; re-run the file alone to tell a flake from a red; a second failure is usually a race (a child cancelled before it started, a sleep real work outlasts) fixed with an event or sentinel, not a wider margin; only a genuine bound is widened, never the assertion; two xdist suites on one Postgres also collide on worker names, so the per-worker database carries the process id.
tags: [testing, xdist, timing, flake, postgres, "056"]
timestamp: 2026-11-02
---

# Rule

1. **Re-run alone first.** A test that polls with a fixed deadline (10 s for a child status,
   5 s for a vitest interaction, 2 s for "fails fast") can miss it under the eight-worker suite,
   a full `make verify` beside running agents, or a dependency install. Re-run the file alone
   before calling the base red; a pass alone with a fail in the suite is a load flake.
2. **Then ask whether it is a deadline at all.** A test that fails in the suite more than
   once, or fails again after one widening, is usually a **race** the deadline was hiding: a
   child cancelled before its pool thread started (so it never wrote the row the test waits
   for), or a fixed sleep that real work outlasts under load. Make it deterministic with an
   event or a sentinel the code under test sets (the child signals "row open" before the
   fault is injected; the slow job returns when the quick jobs' sentinel files exist) and
   leave what is asserted untouched.
3. **Only then widen the deadline, never the assertion.** A genuine deadline (a "fails fast"
   bound, a vitest interaction timeout) is widened once (2 → 10 s) and recorded in the slice's
   verification.md as a test change.
4. **Two suites on one Postgres need the process id in the worker database name.**
   pytest-xdist workers are named `gw0, gw1, ...` in every suite, so a second suite's `gw0`
   drops the first's database mid-run; `tests/conftest.py` names each copy
   `<base>_test_<worker>_<pid>`.

# Why

Task 056's gates hit this six times. The build widened a 10 s child-status deadline to 30 s
and a 4 s slow-job sleep to 10 s; both failed again at review under the eight-worker suite,
and both were races: the fan-out test raised before the pool had started the child it then
cancelled (no row, ever), and the scheduler order test's quick jobs each paid a forkserver
start that outlasted the slow job's sleep. An `opened` event and sentinel files fixed them for
good; only the billion-laughs "fails fast" bound (2 → 10 s at load average 60) was a real
deadline. The build's two knowledge candidates ("re-run alone before calling it red" and "the
fix is the deadline") read as a contradiction until ordered as above. Related:
[timing asserts on an injected clock](timing-asserts-injected-clock-logs-corroborate.md).
