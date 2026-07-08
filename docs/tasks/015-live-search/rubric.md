# Rubric: 015-live-search

Core completion criteria. The task is **done only if every box holds** —
otherwise it is in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes — deterministic and egress-free (fixture
       defaults; live module transport-stubbed in the suite).
3. [ ] No approval-gated change snuck in unapproved — the one approved gate
       is runtime egress; schema, deps, CI, public interfaces all unchanged
       (table count 25; `run_harness` signature untouched).
4. [ ] No generated files or secrets edited by hand; no key material in any
       committed file, snapshot, event payload or log line (grep audit
       recorded).
5. [ ] No tests deleted, skipped or weakened without written justification —
       specifically the 007 zero-egress guard is extended, not loosened.
6. [ ] The carried v2-lesson requirements each have a test: explicit
       timeout on every request · Overton 1 call/s limiter · OpenAlex query
       sanitizer on the production path · per-provider result caps ·
       retry-cap-then-honest-failure landing in error isolation.
7. [ ] Live failure modes land in the as-built honesty machinery: backend
       error → `search.executed` error payload + `inadequate` coverage
       verdict + run completes; junk records → `skipped_unusable`; nothing
       silent, nothing raising past isolation.
8. [ ] The decision-11 live check ran as pinned (live acquire both
       providers · dedup re-run · rate-limit + key-hygiene evidence · one
       rapid-profile chain smoke; no deep-chain e2e) — evidence in
       [verification.md](verification.md).
9. [ ] Known gaps and deferred seams recorded — the live-`SearchBackend`
       seam entry in [docs/deferred.md](../../deferred.md) marked
       discharged; follow-on seams (pagination, Arm-B, filters, thin-base
       trigger, multi-process rate limiting) stay recorded.
10. [ ] Tier-3 review stack ran (contract verifier · code review · security
        lane · adversarial review · human deep review), or skipped with
        written justification — findings in
        [verification.md](verification.md).
