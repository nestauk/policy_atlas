# Plan-stage adversarial review: 034-synthesis-report

Reviewer: Codex (`codex-rescue`, read-only brief), 2026-08-26. Target:
`plan.md` against the post-adjudication contract. Lead adjudication the
same day; owner asked not to over-specify remaining synthesis-wire
details before the build.

| # | Sev | Finding | Adjudication |
|---|---|---|---|
| F1 | BLOCKER | D1 assumed the key-findings ledger already carries gap grade/base; `_key_findings_ledger` serializes only text/type/verdict/citations | **Adopted (cheap)** — Phase A extends the ledger with the surviving gap's `payload["gap"]`; contract § S3 records it |
| F2 | BLOCKER | Model-route check sat in Phase E; contract says confirm before conversation B / halt at baseline | **Adopted (one line)** — Phase 0 confirms a working model route or the build does not open |
| F3 | MAJOR | "Judged like key findings" would reuse `repair_section`; card-to-claim persistence underspecified | **Parked for the build** — intent stands (drop failing cards, persist mapping on the block payload); exact shapes land in Phase B, not another design round |
| F4 | MAJOR | New lane missing from `generation_budget_max`, provenance, call_counts | **Adopted (one line)** — Phase B owns the cap/provenance bump |
| F5 | MAJOR | No phase owns the 033-merge rebase | **Noted, no new phase** — contract already requires rebase onto `dev` before this slice's review; Phase F names it |
| F6 | MAJOR | Codex assigned judgment-heavy persistence; briefs not writable from the plan alone | **Parked** — executor table stays; remaining wire details are a build concern, not a plan rewrite |

**Verdict handling:** two cheap facts folded in (seed shape, route-at-baseline).
The rest is parked for Phase B with the owner's "we'll figure it as we go"
steer, not pre-specified here.
