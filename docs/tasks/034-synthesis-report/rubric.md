# Rubric: 034-synthesis-report

Core completion criteria. The task is **done only if every box holds** —
otherwise it is in progress, not done. Terms and defect ids (S1–S9, P1–P10)
are defined in [contract.md](contract.md); this rubric does not restate them.

1. [ ] Implementation satisfies [contract.md](contract.md), including every
       § Reading-the-prototype departure (no Authors, no confidence, softer
       label, 031 count wording, reference format unchanged).
2. [ ] `make verify` and `make frontend-verify` pass; the declared manual
       live check ran (or its blocker is escalated, never silently skipped).
3. [ ] No approval-gated change beyond the two granted gates: the named
       prompt bumps + `synthesise_case_studies_v1`, and the additive
       `SectionRole` value with its card payload. No schema migration, no
       new dependency, no new runtime egress, no other public change.
4. [ ] No generated files or secrets edited by hand (`types.ts` regenerated
       from the OpenAPI export).
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] S1/S2 hold on fixtures: front matter → body → back matter order;
       h1/h2/h3 levels as contracted; contents grouped and relabelled;
       an old artefact (long titles, no case-studies block) renders clean.
7. [ ] S3 holds: v3 pin test; lead-colon bullets bold correctly; a no-colon
       bullet renders whole; a span crossing the split degrades honestly;
       gap bullets are **re-statements** of seed gap claims (validator
       match, ≤2 post-check, distinct marker) and a no-gap-claims report
       emits none.
8. [ ] S4 holds: composition test (0 or 2–4 cards, `role: "case_studies"`,
       produced after key findings, judged/verified); `CaseStudyWire`
       validation (exactly-one-result, title uniqueness, drop-failing-card);
       absence **reasons** recorded; `result_ordinal` → `claim_id` binding
       resolves and degrades to null honestly (S8); metadata omitted when
       unsourced; SSE stream shape untouched; chat-context and other
       `blocks` readers tolerate the role.
9. [ ] S5 holds: block moved and restyled; ranking test unchanged; no
       "why this source matters" prose anywhere.
10. [ ] S6 holds: v5 pin test; title bound enforced at the proposal
        validator; forbidden titles still rejected; the overview-lead
        guidance removed; title consumers swept (anchors, duplicate
        rejection, chat context, markdown).
11. [ ] S7 evidence: per-surface refine-replay notes (≤3 rounds each) with
        before/after excerpts tagged to P-numbers; the shared voice block
        lives in one module constant; prompt-hash guard re-pinned; the v6
        baseline module untouched.
12. [ ] S9 holds: markdown export tests cover order, headings, bold leads
        and cards; one downloaded export compared against the rendered page
        in the live check.
13. [ ] Spec flow-back landed: `web-api.md` read models updated; the ADR
        written (case-studies production ≠ presentation; the S6 reversal of
        028's overview lead); deferred.md case-studies seam discharged and
        the "why this source matters" seam left standing.
14. [ ] Verification evidence recorded in [verification.md](verification.md),
        including the live-run artefact id and the OpenAPI diff.
15. [ ] The review stack ran per Tier 3, with the adversarial-review
        decision made at the contract gate recorded in
        [verification.md](verification.md) and repeated in the PR.
