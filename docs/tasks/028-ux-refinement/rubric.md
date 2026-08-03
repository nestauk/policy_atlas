# Rubric: 028-ux-refinement

Core completion criteria. The task is **done only if every box holds** —
otherwise it is in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md), including the
       owner-resolved forks (A full sequential flow · B scoped prompt rev ·
       C five-tab IA).
2. [ ] `make verify` passes; `pnpm e2e` + `make fe-api-smoke` pass; the pinned
       scoped live check ran and is narrated in verification.md.
3. [ ] No approval-gated change snuck in unapproved — exactly the gate-listed
       prompt surfaces (versioned, prompt-guard updated), exactly the
       enumerated additive schema (transcript part column · block summary +
       marker · artefact summary + marker, one migration), additive-only API
       params/fields; no deps/CI/auth/prod-config/SSE changes.
4. [ ] No generated files or secrets edited by hand (client regenerated via
       `make drift-check`).
5. [ ] No tests deleted, skipped or weakened without written justification;
       fe-api-smoke pinned names updated in the same commit as any rename.
6. [ ] Verification evidence recorded ([verification.md](verification.md)):
       live-check narration, screenshots, additive list approved-vs-landed,
       fork-B cost spot-check numbers.
7. [ ] Known gaps and deferred seams listed (gap → docs/deferred.md).
8. [ ] Required Tier-3 review stack ran (contract verifier · /code-review
       medium · one security lane · adversarial at contract/plan/code · human
       deep review), or skipped with written justification — findings in
       verification.md.
9. [ ] Type scale lands as tokens: views consume the named scale (no new
       ad-hoc pixel sizes outside it); body prose ≥16px; prose line length
       capped ~66–72ch.
10. [ ] Vocabulary honesty holds on every new surface: raw enum keys never
        render; part cards render only server-supplied labels; section
        summaries come from durable text (focus/first sentence), never
        generated.
11. [ ] Annotation spans verify on every changed render path (bulleted key
        findings, collapsed/expanded sections) — spans that can't render
        degrade honestly, with tests.
12. [ ] Planning-turn machinery invariants hold under fork A: two-phase
        persistence, durable idempotency, 409 run-fence, rehydration parity —
        existing tests untouched and green, new part payload covered
        (persist → rehydrate → re-render).
13. [ ] Sources sorting/filtering is collection-true across pages
        (server-side), URL-addressable, with tests.
14. [ ] 027 substrate invariants confirmed (auth seam, reducer idempotence,
        queryKeys, scrub/safeHref discipline, mock mode) — untouched suites
        green.
15. [ ] The copy diet is recorded: the naming/copy map lands in the
        presentation/vocabulary modules, and no honesty-bearing copy
        (degraded/failed/empty states, coverage bases) was cut.
16. [ ] Summaries honour the spec (provenance-grounding § Summaries): never
        detached from drill-down, no citations, carried-with-status
        epistemic content, `failed` never renders as a summary, flat
        judging only — with tests; legacy artefacts render on the
        first-sentence fallback.
17. [ ] Check-in refinement preserves the 024/025 behaviour contract
        (server-supplied options, compile→confirm ladder, `confirm_token`);
        a paused run is visually distinct from an executing one on every
        tab (e2e-asserted); any option-set thinning happened only via the
        gate-approved composition rev.
