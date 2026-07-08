# Rubric: 015-live-search

Core completion criteria (rev 2 — depth-graded search capability). The
task is **done only if every box holds** — otherwise it is in progress,
not done.

1. [ ] Implementation satisfies [contract.md](contract.md) (rev 2).
2. [ ] `make verify` passes — deterministic and egress-free (fixture
       defaults; scripted backends + seeded RNG for loop logic; live
       transport stubbed in the suite).
3. [ ] No approval-gated change snuck in unapproved — the approved set is
       exactly: runtime egress (transport + the four named generation
       surfaces) · one `ck_scov_stop_condition` CHECK migration · the
       `search_backend_scope` Plan/Config field. Table count stays 25;
       no new dependency; `run_harness` signature untouched.
4. [ ] No generated files or secrets edited by hand; no key material in
       any committed file, snapshot, event payload, log line or raised
       error message (redacted-HTTP-error tests + grep audit recorded).
5. [ ] No tests deleted, skipped or weakened without written
       justification — specifically the 007 zero-egress guard is
       extended, not loosened.
6. [ ] The carried v2-lesson transport requirements each have a test:
       explicit timeout on every request · Overton 1 call/s limiter
       gating every path incl. page loops · both sanitizer transforms on
       the production path (and on generated queries) · per-depth
       per-provider caps · retry-cap-then-honest-failure ·
       `select=` superset · **no citation floor** (decision 12,
       user-approved).
7. [ ] Depth gradation is fail-closed and complete: unknown depth is a
       structural failure; rapid = multi-query fan-out with no single
       LLM query load-bearing; deep = the bounded Arm-B loop with every
       budget (LLM calls · HTTP calls · rounds · wall-clock · results)
       enforced as an honest stop (`short_circuit` /
       `budget_exhausted`), never a silent trim.
8. [ ] Governance boundaries hold, test-enforced: the in-loop judge
       never writes screening rows (everything acquired still screens);
       every egress call — search, snowball, lookup — emits a
       `search.executed` event; one fail-closed coverage record per run
       carries depth + executed `scope_filters`; ungrounded suggestions
       are dropped and counted.
9. [ ] Loop prompt inputs are token-bounded exemplar records
       (the rev-2 latency requirement): caps test-enforced; injection
       fixtures pass on the judge and reformulation surfaces
       (instruction-shaped metadata cannot steer decisions).
10. [ ] The thin-base trigger fires at most once per run, escalates to
        deep, re-screens incrementally, and lands
        `re_searched_still_thin` honestly when still thin — all
        test-covered; migration roundtrips clean on both DBs.
11. [ ] Live failure modes land in the as-built honesty machinery:
        backend error → `search.executed` error payload + `inadequate`
        verdict + run completes; loop-verb failures counted-and-skipped;
        junk records → `skipped_unusable`; nothing silent, nothing
        raising past isolation.
12. [ ] The decision-11 live check ran as pinned (rapid run · dedup
        re-run · limiter + key hygiene · comparative result-count
        probe · deep run with wall-clock and cost measured against the
        budgets · trigger fired once · rapid-profile chain smoke; no
        deep-chain e2e) — evidence in [verification.md](verification.md).
13. [ ] Known gaps and deferred seams recorded — live-`SearchBackend` +
        Arm-B entries in [docs/deferred.md](../../deferred.md) marked
        discharged; the rev-2 seam set recorded (Overton-arm-B
        cross-backend snowball · blend ranking · S2 · region mapping ·
        caching if plan-declined · citation-floor knob · eval-reuse
        pointers).
14. [ ] Components §1 spec flow-back landed with a `log.md` entry; the
        ADR (depth-graded agentic search adoption) is Accepted and
        signed off.
15. [ ] Tier-3 review stack ran (contract verifier · code review ·
        security lane · adversarial review · human deep review), or
        skipped with written justification — findings in
        [verification.md](verification.md).
