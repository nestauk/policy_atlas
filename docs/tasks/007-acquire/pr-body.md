## What / why

Task: `docs/tasks/007-acquire/` ([contract](../../docs/tasks/007-acquire/contract.md))

Adds the **`acquire` component** — the Evidence Base front edge — so the pipeline runs on
authentic acquired documents, not only uploads. Metadata-only acquisition through the
`search` seam: a `SearchBackend` protocol with **fixture-backed OpenAlex and Overton
backends** (the two v3.0 backends the spec names, trust classes `academic_aggregator` /
`grey_literature_aggregator`) replaying **sanitized fixtures derived from dev-time-recorded
real API responses** — authentic structure and shape quirks, fabricated values, **zero
runtime egress**. Each accepted result snapshots the text in hand (`origin="acquired"`,
`text_basis="abstract_only"`, one chunk, `metadata_envelope_v1`), with `abstract_source`
provenance (`publisher_abstract` / `snippet` / `llm_description` — Overton's LLM-generated
summaries always visible as machine text / `none`) and a curated retained-provider-field
set. Every search call emits a **`search.executed`** governance event; every acquire run
writes one **`search_coverage_record`** (fail-closed adequacy verdict) — the record that
operationalises "adequately-searched". Project-scoped three-guard dedup
(`backend_record_id` · normalized DOI · content hash), per-backend error isolation, and the
full chain demonstrated in the skeleton: acquire → screen (missing abstracts fail open to
`title_only`) → classify → appraise over a mixed corpus.

Riding this slice, as approved: the **`screening_scope` → `evidence_scope` rename** (first,
mechanically separable commit) and the **`search_coverage_record`** table (15 → 16 tables,
migrations 6 + 7, both roundtrip clean).

## Proof it works

Evidence: [`docs/tasks/007-acquire/verification.md`](../../docs/tasks/007-acquire/verification.md).

- **`make verify`:** pass — okf-validate · **167 tests** (59 in `test_acquire.py`) ·
  mypy · ruff · build (wheel verified to ship the fixture package data).
- **Manual / end-to-end:** `uv run --env-file .env python -m policy_atlas.skeleton` —
  exit 0; acquire 12+12 per backend, coverage record visible in DB
  (`breadth_truncated | adequate | model`, backends length 2), two `search.executed`
  events, screen-basis distribution `title_abstract=21 / title_only=4`, classify
  `Unknown`s, appraise `skipped_unknown` — the honest v3.0 stub behaviour.
- Both migrations roundtrip (`alembic downgrade -2` → `upgrade head`).

## Risk tier

Tier **3** — two schema changes (rename + new table), a public-interface rename + one
optional `run_harness` parameter, and the slice builds the seam through which runtime
egress and untrusted third-party text will eventually enter the product.

## AI role

Agent (Claude, task-cycle conversation B/C) implemented the approved contract/plan
end-to-end: rename sweep + migrations, recorder scripts + sanitizer (ran dev-time
recordings against both live APIs), `acquire.py`, harness wiring, tests, spec flow-back,
verification evidence, and the Tier-3 review stack with fixes. Human approved the contract
(rev 7 + three gated changes, 2026-07-05), the plan, and the fixture policy; contract- and
plan-stage adversarial reviews were adjudicated at their own gates. All review-stack
findings and their adjudication are in verification.md § Review findings.

## Review focus

- **Sanitized fixtures / public safety** — the security lane already caught one sanitizer
  miss (real grant IDs, fixed + test-enforced); a skeptical eye on
  `src/policy_atlas/data/*.json` is the highest-value human pass.
- **Dedup correctness** — three identity guards, preload normalization, fixed backend
  order (`test_identity_guards_each_separately`, `test_cross_backend_doi_dedup_*`).
- **Coverage-record verdict rule** (decision 8) and per-backend error isolation.
- **Rename completeness** — `grep -ri screening_scope src tests` is empty; migration 6
  renames table + 4 columns + pkey + unique constraint both directions.
- **Scope** — no live HTTP, no full-text fetch, no new deps, no query expansion.

## Reviews run

Findings recorded in `verification.md` (§ Review findings).

- [x] Contract verifier (fresh-context agent — all 19 rubric items verified)
- [x] `/code-review` medium (3 correctness findings, fixed)
- [x] Security lane — `security-auditor` subagent (Tier-3 lane; 1 Medium + 3 Low, fixed;
      `/security-review` intentionally not duplicated on the same diff)
- [x] Adversarial review (Codex — 5 findings: 4 fixed, 1 deferred with note)
- [x] `/simplify` (via the review's reuse/simplification/efficiency/altitude angles,
      fixes applied; separate same-family pass skipped per review-stack economy)

## Known gaps & deferred seams

Recorded in `docs/deferred.md` (new **Search / acquisition** section): live
`SearchBackend` implementations (with the v2-lesson requirements — timeouts, Overton
rate limiter, production-path query sanitization, per-provider caps); the **Arm-B agentic
search loop** as the chosen query-derivation direction (R&D pointers, protocol growth
path, stop-condition growth, Semantic Scholar candidate, Campbell/3ie/EPPI eval note);
backend-scope selection; Overton semantic mode + filters; thin-base re-search;
cross-project dedup + fuzzy near-dup + concurrent-run dedup hardening; injection-screening
posture; slice-008 full-text inputs (URL/OA blocks retained in `provider_fields`);
downstream envelope consumers (`abstract_source`-aware screen, provider-prior-aware
classify, `is_retracted` flag).

## Public safety

- [x] No secrets, credentials, or real/acquired source text in the diff or evidence —
  fixtures are sanitized (fabricated values, leak-guard test-enforced: `10.99999/` DOIs,
  `example.org` URLs, hashed award ids); raw recordings gitignored and key-scrubbed;
  API keys env-only, never read by package code (test-enforced).
- [x] Logs / traces / screenshots are public-safe.
- [x] No approval-gated change snuck in unapproved — schema limited to the two approved
  migrations; the one public-interface addition (`run_harness(search_backends=…)`) is
  approved gated change 3; zero runtime egress (fixture replay; recorders are dev-time
  and never imported by the package).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
