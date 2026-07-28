# Rubric: 027-frontend-uplift

The task is **done only if every box holds** — otherwise it is in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes (incl. frontend lane + drift-check + font-guard);
       `pnpm e2e` (updated mock journey) and `make fe-api-smoke` pass; the pinned
       live check ran and is narrated in [verification.md](verification.md).
3. [ ] No approval-gated change snuck in unapproved — the additive read-model list
       matches what the plan 🛑 approved; schema = exactly the one transcript
       migration; SSE additions = exactly the approved `artefact.*` set; CI
       change = exactly the approved mock-journey e2e lane; no auth, deps, or
       production-config changes.
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
15. [ ] **Transcript durability:** two-phase turn persistence holds (user
        message durable on receipt; reply + draft + approved plan complete it;
        a crash between phases renders an honest incomplete turn — test
        evidence); `client_turn_id` idempotency survives a restart; the
        rehydration mapping table is complete against `planning.py` as-built
        and parity-tested; the thread survives navigation and an API restart
        (live-check evidence); transcript reads paginate with the standard
        envelope; endpoints are owner-scoped (cross-owner → 404); migration
        up/down tested against a populated DB.
16. [ ] **Streaming honesty:** artefact sections render only from durable
        `artefact.*` events — prose-in-event, no partial-artefact read path
        (replay after reconnect shows exactly the completed sections — test
        evidence); events append outside the component transaction and are
        presentation records (the artefact of record lands only at commit);
        the active section is marked as writing; the annotations-attach-at-
        commit footer shows while streaming **and every terminal path
        (failed/aborted/interrupted) shows the honest partial-stream banner**;
        streamed prose passes through `scrub()`.
