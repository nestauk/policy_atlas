# Rubric: 027-frontend-uplift

The task is **done only if every box holds** — otherwise it is in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes (incl. frontend lane + drift-check + font-guard);
       `pnpm e2e` (updated mock journey) and `make fe-api-smoke` pass; the pinned
       live check ran and is narrated in [verification.md](verification.md).
3. [ ] No approval-gated change snuck in unapproved — the additive read-model list
       matches what the plan 🛑 approved; no schema, auth, SSE-vocabulary, deps,
       CI, or production-config changes beyond it.
4. [ ] No generated files (`src/api/gen/`, `openapi.json`) or secrets edited by hand.
5. [ ] No tests deleted, skipped or weakened without written justification — the
       substrate test files (auth, sse, authMiddleware, reducer, scrub, feedback,
       CheckInCard behaviour) pass unweakened; accessible-name updates in e2e specs
       are renames, not deletions.
6. [ ] Verification evidence recorded per the contract's list (incl. screenshots of
       each uplifted surface and the substrate-invariant confirmation).
7. [ ] Known gaps and deferred seams listed (live-artefact streaming →
       [docs/deferred.md](../../deferred.md) unless owner-promoted).
8. [ ] Required Tier-3 review stack ran (contract verifier · code review at medium ·
       one scoped security lane · adversarial review · human deep review), or a
       skip is justified in writing — findings in [verification.md](verification.md).
9. [ ] **No raw enum/key leaks:** every user-visible label is server-supplied or
       from the locked vocabulary; unknown keys omit rather than render
       `snake_case`; grep evidence for the demo's `replace(/_/g` fallback pattern.
10. [ ] **Honest surfaces:** every new data-driven card hides when its data is
        absent; empty ≠ loading ≠ error (each new view distinguishes the three);
        dropped annotation spans skip cleanly.
11. [ ] **Scrub discipline:** every model-authored/source-derived string added in
        this slice renders through `scrub()` (or `<Scrubbed>`); source URLs through
        `safeHref()`; `dangerouslySetInnerHTML` lint ban intact.
12. [ ] **Motion budget:** every new animation marks real data arriving; all quiet
        under `prefers-reduced-motion` (e2e reduced-motion run stays zero-error).
13. [ ] **URL-addressable state preserved:** `?source=`, `?status=`, `?page=` still
        work; any new named UI state (filters, expanded panels that name a thing)
        is URL-addressable or its exclusion justified.
14. [ ] **Vocabulary:** archive (never delete) on landing; appraisal labels never
        numbers; tags grouped by asserter never merged; the publication-country
        caveat renders with that distribution.
