# Rubric: 015-live-search

Core completion criteria (rev 3.1 — depth-graded search capability,
screen-in-the-loop, adjudicated filter grammar). The task is **done only
if every box holds** — otherwise it is in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md) — the
       approved contract as amended at the gate (rev 3.12 approved;
       revs 3.13–3.14 amendments included).
2. [ ] `make verify` passes — deterministic and egress-free (fixture
       defaults; scripted backends for loop logic, no RNG anywhere
       (rev 3.10 — fixed allocation); live transport stubbed in the
       suite).
3. [ ] No approval-gated change snuck in unapproved — the approved set is
       exactly: runtime egress (transport + the three named generation
       surfaces + the in-loop `screen_v1` call-volume change + the
       revs-3.7/3.8 prompt-input restructure on the 014 surfaces:
       label priors from the tag layer, indexed_in into classify,
       title_source into screen + classify, all M10-bounded) · one
       `ck_scov_stop_condition` CHECK migration · the
       `search_backend_scope` Plan/Config field. Table count stays 25;
       no new dependency beyond the rev-3.13 approved `httpx`
       declaration-only promotion; `run_harness` grows only the approved
       generation-surface backend parameter (wording reconciled at the
       015 review stack — the pre-3.13 text read "no new dependency;
       signature untouched").
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
       LLM query load-bearing (generated queries validated;
       all-zero → verbatim fallback with an honest note); deep =
       bounded acquire↔screen rounds (cap 3) with every budget (LLM
       calls incl. in-loop screen reps · HTTP calls · rounds ·
       wall-clock · results) enforced as an honest stop
       (discovery-rate `short_circuit` / `budget_exhausted`), never a
       silent trim; stopping reaches each of its four conditions in
       tests; the anti-drift triple holds test-enforced (reformulation
       context = graded exemplars with negatives, anchored to the
       original intent, strictly per-round non-accumulating; the
       diversity-reserve fraction runs every round).
8. [ ] The one-relevance-surface property holds, test-enforced: acquire
       writes no screening rows itself and contains no shadow relevance
       judgment — loop steering reads only the effective-screen helper
       over rows the unmodified 014 screen component wrote; every
       egress call — search, snowball, lookup — emits a
       `search.executed` event; each acquire round writes its
       fail-closed coverage record carrying depth + executed
       `scope_filters`; ungrounded suggestions are dropped and counted.
9. [ ] Loop prompt inputs are token-bounded exemplar records
       (the rev-2 latency requirement): caps test-enforced; the
       injection fixture passes on the reformulation/suggestion
       surfaces (instruction-shaped metadata cannot steer output
       structure).
10. [ ] The rapid-thin escalation runs at most one bounded deep
        continuation, resumes incrementally (no re-screening of
        already-screened docs), and lands `re_searched_still_thin`
        honestly when still thin — all test-covered; migration
        roundtrips clean on both DBs.
11. [ ] Live failure modes land in the as-built honesty machinery:
        backend error → `search.executed` error payload + `inadequate`
        verdict + run completes; loop-verb failures counted-and-skipped;
        junk records → `skipped_unusable`; nothing silent, nothing
        raising past isolation.
12. [ ] The decision-11 live check ran as pinned (rapid run · dedup
        re-run · limiter + key hygiene · comparative result-count
        probe · deep run with per-round evidence and wall-clock/cost
        measured against the budgets · escalation exercised once ·
        one filtered rapid run with wire params visible in events +
        coverage record · rapid-profile chain smoke; no deep-chain
        e2e) — evidence in [verification.md](verification.md).
12b. [ ] Every shipped Overton filter key matches the design-stage
        param-pinning record (revs 3.3–3.4,
        [overton-param-pinning.md](overton-param-pinning.md)) — wire
        spellings, single-valued keys, four pinned `source_type`
        tokens, named region groups, three-letter language codes,
        full-label SDGs, and the never-read-semantic-`total_results`
        client rule. No residual pinning items remain.
13. [ ] Known gaps and deferred seams recorded — live-`SearchBackend`,
        Arm-B and thin-base-trigger entries in
        [docs/deferred.md](../../deferred.md) marked discharged; the
        **full seam list in contract.md § Verification evidence
        expected** recorded verbatim (rev 3.14: incl. retrieval-boost
        grammar v2 · select-as-tool · tool-wide depth/time-budget
        gradation · the rev-3.10 loop seams · filter-vocabulary
        growth · study-geography extraction field · the eval-reuse
        pointer set).
14. [ ] Components §1 + §2 spec flow-back landed with a `log.md` entry; the
        ADR (depth-graded agentic search adoption) is Accepted and
        signed off.
15. [ ] Tier-3 review stack ran (contract verifier · code review ·
        security lane · adversarial review · human deep review), or
        skipped with written justification — findings in
        [verification.md](verification.md).
