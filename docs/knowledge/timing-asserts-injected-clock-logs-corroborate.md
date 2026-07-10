---
type: Testing rule
title: Timing/politeness properties are asserted on an injected clock, not live logs
description: Live log timestamps only corroborate timing behaviour; thread-scheduling jitter can make individual sub-interval gaps appear in a live run even when the enforced spacing is correct.
tags: [testing, timing, fetch_live, politeness, "016"]
timestamp: 2026-07-10
---

# Rule

Timing and politeness properties (e.g. minimum spacing between requests to a
host) are asserted with **injected clocks** in tests; live log timestamps only
**corroborate**, they never carry the assertion. Spacing enforced on an
internal monotonic clock can still show sub-interval gaps between log-line
*timestamps* under ordinary thread-scheduling jitter — the clock the code
reasons about and the wall-clock timestamps a log line happens to carry are
not the same measurement. The pin is the injected-clock test
(`test_fetch_live.py`'s politeness tests); a live run is read-only evidence.

# Why

The 016 live check produced exactly this signature: one 0.845s gap directly
following a 1.22s gap between two log lines — the pair still sums to two full
1.0s intervals, and every other one of the 21 hosts logged a gap ≥ 1.0s. The
review stack confirmed this was jitter (emission timing), not a spacing
violation, by checking the raw log against the pairing. Had timing been
asserted against the live log instead of the injected clock, this run would
have failed a correct implementation.
