# Verification: 023-codebase-health

Evidence for the pre-eval codebase-health slice. Public-safe. Filled at step 6;
§ Review findings + § Rubric status await the review stack (fresh conversation).

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (full: okf-validate · test · typecheck · lint · build) | pass | step-6 exit gate: **1328 passed**, mypy `Success: no issues found in 154 source files`, ruff clean, wheel+sdist built. Run on a freshly reset `policy_atlas_test`. Exit code captured directly (`MAKE_EXIT=0`), not via a pipe. |
| Full `make verify` at phase gates | pass | baseline (1349 pre-slice) · post-C (1328) · post-D (1328) · post-E (1328) · exit (1328). Count drops C→ onwards are deleted dead-path tests, itemised per phase below. |
| `make verify-fast` at A/B/F gates | pass | F's first run was red — see § Incidents. |
| Prompt pin tests | pass, **unmodified** | every pinned surface byte-identical through the vetter merge + renames + moves: `extract_iof_v7`, `extract_icf_v2` (+ both vetter prompts `extract_finding_vetter_v3`/`extract_icf_vetter_v2`), `planner_v5`, screen/classify surfaces, `synthesise_section_v7`/frozen v6, `synthesise_sections_v2`. Named pin tests listed in the C2 lane report (task notes). |
| Contract grep gates | pass (all zero) | every retired flat path (`policy_atlas.grouping`, `.plan`, `.extraction_records`, `.extract_prompt`, `.implementation_context_*`, `.icf_finding_vetter`, `.ingest\b`, `.facet_grouping`, `.skeleton`, `policy-atlas-skeleton`, `.synthesis_prompts_v6` old path) → 0 live module-path/import hits (the word "skeleton" survives as prose describing the retirement in ADR 0019 and the smoke runbook — descriptions, not paths in use); catch-all flat-import scan → 0. |
| `uv lock` audit (WP9) | pass | **0 version-line changes, 0 package add/removes**; 14 requires-dist metadata lines = the approved declarations themselves. Contract's lock pin held in intent (resolved versions identical) — flagged deviation, not a stop. |

## End-to-end command

**The zero-egress full-chain check is automated in the gate** (owner correction at step-6
close, 2026-07-14 — the review stack should verify this reframing):
`tests/runtime/test_orchestrate.py::test_full_stub_end_to_end_mints_artefact` drives the
scripted five-prompt stub flow through `main()`, asserts the artefact is minted, and
cleans up its committed rows — it ran green inside every full `make verify` gate of this
build. Together with the runner-level
`test_full_stub_chain_commits_each_step_and_checks_in`, that is the behaviour evidence;
the pin tests carry the prompt-surface byte-identity.

The manual form was additionally run twice during the build (post-E and at the exit
gate) as an ad-hoc check of the `python -m` entry under the new layout:

```sh
printf 'What works to reduce childhood obesity?\n1\napprove\n1\n1\n' \
  | env -u OPENAI_API_KEY \
    DATABASE_URL="postgresql+psycopg://policy_atlas:policy_atlas@localhost:5432/policy_atlas_test" \
    uv run python -m policy_atlas.runtime.orchestrate
# exit 0 · "Run status: succeeded" · "Artefact minted: True"
# Ad-hoc runs commit rows and don't clean up — reset a shared DB afterwards
# (see Incidents; the suite test needs no such ceremony).
```

Its ongoing role is ad-hoc demos and the **live-check form** (same command with keys) —
see `docs/knowledge/orchestrate-stub-smoke.md`. No live run this slice (contract pin):
no prompt/model/schema/egress change.

## Diff summary

**172 files, +4,067/−4,894 (net −827 against dev), 8 commits (design + A–G).** All
behaviour-preserving except the three contract-named WP10 optimisations.

- **A — test pre-hardening** (`ac4e6c6`): 9 string-path monkeypatch sites → object form
  (lane-4's "11" counted one multi-line call as 3 — flagged); 4 country-filter fail-closed
  branches covered via **direct-call tests, not matrix rows** (flagged deviation: the
  existing matrix routes through `validate_scope_filters`, whose upstream checks intercept
  those inputs; direct calls are the only way to hit the branches); first
  `OpenAISearchGenerationBackend` wire test.
- **B — embeddings split + WP10c** (`a89f2b6`): 6 generic client/usage helpers →
  `openai_client.py` + `usage.py` (14 importers repointed; `theme_grouping`'s `_log_usage`
  dup deleted). Flagged deviation: `usage.py`'s narrower public `usage_metadata` renamed
  private, public fn widened + delegates (behaviour-identical, `test_usage`
  unchanged-green). WP10c: retrieval cosine → `math.sumprod` + unit norms precomputed at
  `ChunkRetriever` init; `_cosine` deleted (zero callers after inlining); precision class
  commented in code.
- **C — dead-code cuts** (`3ed86a8`, −647): facet_values one-call-partition path (−406 with
  tests); vetter plumbing merged into one `finding_vetter.py` (−1 module, prompts
  byte-identical); echo chain cut (harness/plan/state fields; 7 test sites repointed —
  `block.written` event type retired with it, event-log canon 6→5, a named consequence of
  the approved cut; `test_echo_requires_source_snapshot_id` deleted as dead-path — it
  asserted `Plan(component="echo")` raises without `source_snapshot_id`, and both the echo
  component and the `source_snapshot_id` field were removed with the cut [rationale
  corrected by the review stack: the original "duplicates per-component tests" framing was
  wrong — surviving tests assert payload presence, a different contract]); characterise dead wrapper; acquire legacy path
  (`executed_calls` now required; tests build real `ExecutedCall`s via a new
  `tests/helpers.executed_calls_for`); 24/25 anchored small items (item 20 `_scrub_nul`
  delegation declined — function live, edit cosmetic; `parse_structured()` reached 10 call
  sites vs the estimated 6, incl. a verified-equivalent `planner._parse_once` signature
  change). Lead fixed 15 test-side mypy errors the lanes missed (they checked `src` only).
- **D — renames + skeleton retirement + WP10a/b** (`3304df4`, −1,272): IOF/ICF symmetry
  set (`iof_records`/`icf_records`, `iof_prompt`/`icf_prompt`), `theme_grouping`,
  `run_spec` (+`test_run_spec`; `compile()` collapsed to
  `Config.model_validate(plan.model_dump())` — models verified field-identical),
  `ingest_upload`; `select_document_fetcher` → `fetch_live`. **Skeleton retired** (owner
  reversal 2026-07-14): module deleted, `policy-atlas-skeleton` console script removed
  (`[project.scripts]` now empty → removed), zero live references. WP10a: group assignment
  fan-out 1→4 (local literal + parity comment; deliberately not an import). WP10b:
  appraise bulk insert with empty-rows guard; event appends stay per-row.
- **E — capability-aware regroup** (`83d26c6`): 60 src modules + 71 test files →
  `runtime/` · `evidence_base/{sourcing,assess,corpus,extract,group,synthesis}` (+
  `clustering_engine` at capability root) · `core/`; `data/` stays at package root
  (top-package `importlib.resources` anchors unchanged). Content steps per contract:
  facet_grouping's 5 live constants folded into `facet_values` (module deleted);
  `ingest_full_text` repo-root anchor `parents[2]`→`parents[4]`. Flagged move-fallout
  fixes beyond the plan's list (all path-anchor class): `test_acquire` src-dir anchors,
  `test_ingest_full_text` package-data/tests-data anchors, `test_screen`'s
  criteria-confinement filenames. Lead audit: moved-file diffs path/import-only;
  `evidence_base` imports nothing from `runtime`; `planner → extract._scrub_nul` edge
  one-way (acyclicity holds).
- **F — docs truth + WP9 + riders** (`6a988e2`): README rewritten from 5 stale
  pre-implementation lines; readiness.md 022 line corrected; `lxml`+`pymupdf` declared
  direct + floors raised to locked majors + `[tool.pyright]` pruned; 24 docstrings gain
  `Args:` (diff verified docstring-only).
- **G — test consolidation top-2** (`7f23cc4`, −122): `fake_parse_client()` replaces 5
  fake-client stacks (`test_synthesis_backend`'s tool-call variant honestly left local —
  no shared shape); `ScriptedSynthesisBackend` absorbs 9 scripted doubles' plumbing.
  **Assertion parity AST-verified: identical assert + `pytest.raises` counts in every
  touched file.**

## Incidents (root-caused, not guessed)

1. **Test-DB contamination, twice.** Parallel C-lane done-checks ran pytest concurrently
   against the shared `policy_atlas_test`; interrupted migration roundtrips left committed
   rows → `CheckViolation` on downgrade, persisting across sessions (conftest migrates but
   never wipes). Second instance: the orchestrate smoke's minted artefact re-contaminated
   the same quartet before the F gate. Both fixed by `dropdb`+`createdb` (quartet green in
   2s) and gate re-runs.
2. **Process violation, self-caught:** the F commit initially landed on the red gate via a
   `&&`-chained command; DB reset → gate re-run green on the identical tree → commit
   amended with the incident recorded in its message. Related trap, same class: `make
   verify | tail` reports the pipe's exit code — one C-gate run read as exit-0 while red.
3. **C1 lane died mid-edit** on a transient API server error; resumed with context intact;
   completed cleanly.
4. **WP9 near-miss:** the lead's pyright-prune regex swallowed `[dependency-groups]`; the
   first re-lock dropped two dev packages and re-resolved 5 newer. Caught by auditing the
   lock diff pre-commit; fixed by restoring the committed lock and re-locking (final audit:
   0 version changes).

## Review handoff

**Flagged deviations for the stack to confirm/contest** (each resolved within contract
vocabulary): the Phase A direct-call-tests-not-matrix-rows choice · B1's `usage_metadata`
rename/widen · C4's 10-site `parse_structured` reach + planner signature change · C3's
five harness-test repoints to characterise + `block.written` retirement + one test deleted
as duplicate · E's unenumerated path-anchor fixes · WP9's requires-dist-only lock delta ·
the C4 `_scrub_nul` decline.

**Flagged, NOT cut (scope guard — new findings for adjudication/deferred):**
- `grounding.py`'s `produce_grounded_block` + `GroundingError` are production-caller-less
  post-echo-cut (`content_hash` is the live part).
- `run_harness(provider=…)` has zero component readers (echo was the last); makes
  `inference.py`'s provider seam near-dead on the harness path.
- `core/tracing.py` imports evidence_base domain modules (`theme_grouping`, PROFILE_IDs)
  — the `*_score_summary` renderers are EB-domain-aware; pre-existing coupling made
  visible by the regroup.

**Knowledge candidates** (step-8 authors from these + stack findings):
- `math.sumprod` (py≥3.12) as the stdlib answer to pure-Python vector maths on hot paths;
  extended-precision accumulation can reorder near-ties (precision class).
- Parallel build lanes: the file fence must include **done-check resources** — the shared
  test DB is part of the fence; concurrent DB-backed pytest runs contaminate migration
  roundtrips across sessions.
- The zero-egress full-chain check belongs in the suite, and already was there
  (`test_full_stub_end_to_end_mints_artefact`, self-cleaning) — the manual orchestrate
  command is the ad-hoc/live vehicle only, and ad-hoc runs against a shared DB **commit
  rows** and need a reset (owner correction at step-6 close; runbook amended in-slice —
  review stack: verify the reframing).
- Gate results must be read from the gate's exit code directly: `| tail` eats it, zsh
  spells it `pipestatus`, and `&&`-chaining a commit onto a gate is how a red-gate commit
  happens.
- Lane done-checks must be the GATE's exact commands (`mypy src tests`, not `mypy
  src/policy_atlas`) — 15 errors slipped through narrower approximations.
- The unmarked-default naming smell (first-built variant hoards generic names; the second
  variant gets marked names) as a repeatable review lens — IOF/ICF was the instance.

**Executor routing note:** Codex exhausted (2026-07-14) — adversarial reviews (contract +
plan) and the C2 judgment lane ran on deep-reasoner; family heterogeneity NOT achieved
this slice, per the recorded fallback. Fast-workers took A, B1, C1, C3, C4, D, E, F-rider,
G; lead kept B2/WP10a, the taste/gated surfaces (README, deps), audits, and adjudication.

## Public safety

All changes are code moves/deletions, tests, docs and manifest edits. No acquired text,
credentials, traces or secrets. Fixture-sanitizer consolidation (C4 item 24) verified by
re-running both recorder scripts against raw recordings — committed fixtures byte-identical
(date-only diffs reverted).

## Known gaps

- `tests/` E501-class ruff findings in `scripts/record_fulltext_fixtures.py` (21)
  pre-exist and sit outside the lint gate (`ruff check src tests`).
- The plan's Phase E note about `importlib.resources` anchors needing updates was
  withdrawn at contract-adversarial stage (they're top-package); recorded here for the
  paper trail.
- deferred.md entries and the smoke knowledge concept land in the Phase H commit alongside
  this file.

## Post-exit rider (owner-directed, 2026-07-14 — review stack: verify alongside the smoke reframing)

After the smoke reframing exposed that the suite's stub e2e injects empty search
backends, the owner directed moving the provider fixture data out of the package:
`src/policy_atlas/data/` → `tests/data/provider_records/`; `OpenAlexFixtureBackend`/
`OvertonFixtureBackend` + loaders → `tests/provider_fixtures.py` (importing
`BackendCaps`/`_normalize_doi` from acquire); `harness._default_search_backends` → empty
for every scope (docstring records why); recorder scripts write the tests path; five
test files repoint imports/anchors; `test_harness_acquire_component` now injects the
fixture pair explicitly (all assertions preserved). Observable-change note: the ad-hoc
no-key demo's acquire step now adds nothing (seeded corpus only) — accepted by the owner
as part of the rider. README/ADR 0019/runbook/contract amended in the same commit.
Gates re-run post-rider: full `make verify` + grep gates (zero
`files("policy_atlas")` anchors remain).

## Post-review rider (owner-directed, 2026-07-15, at the step-9 gate)

The owner renamed the per-source judgment bucket `evidence_base/screen/` →
`evidence_base/assess/` (it holds three peer components — screen, classify, appraise —
so the bucket carried its first member's name: the unmarked-default smell at directory
level). Mechanical rename: `git mv` on the src + tests mirrors, import rewrites
(`evidence_base.screen` → `evidence_base.assess`, zero residual hits), ruff import-sort
fixes, and the living-doc sweep (README tree, ADR 0019 tree + amendment note, AGENTS.md,
this file's phase-E line). Historical records (review-findings.md, plan.md) keep the
name that was correct when they were written. Module names inside the bucket are
unchanged (`screen.py` still names the screen component). Full `make verify` re-run
green post-rename.

Second rider, same gate: the owner directed **dissolving `grounding.py`** (raised as
"shouldn't it live in synthesis/?"; the facts said neither bucket — its only live export
`content_hash` had three sourcing importers + one synthesis importer, and the
grounded-block leg was production-dead post-echo-cut, per the stack's scope-guard
finding). Resolution: `content_hash` (+ `_normalize`) → new `core/hashing.py` (generic
utility, cross-bucket use); `produce_grounded_block`/`GroundingError`/`quote_present` +
`test_grounding.py` **deleted** (owner-approved cut beyond the adjudicated list — this
paragraph is the approval record; the two content_hash tests survive as
`tests/core/test_hashing.py`). The deferred.md dead-leg entry is discharged in the same
PR that added it; the `citation-flag-dont-drop` knowledge concept is marked RETIRED
(the principle stays spec-level; `quote_verify.py` is the live verification mechanism).
Full `make verify` re-run green post-dissolution.

## Review findings

Stack run 2026-07-14 in a fresh conversation (this file's author-of-record for this
section is the review-phase lead, not the build chat). Lanes: contract-verifier (pinned
Opus, read-only) · security-auditor · adversarial pass on **deep-reasoner** (Codex
exhausted — recorded fallback; family heterogeneity NOT achieved, both heavyweight lanes
Claude-family) · `/code-review` medium (8 lens-scoped finder angles, fast-workers).
Self-verify gate before lanes: full `make verify` green (1328 passed, mypy `Success: no
issues found in 155 source files`, ruff clean, wheel+sdist). The 154→155 mypy delta vs
the step-6 record is the post-exit rider's `tests/provider_fixtures.py` — explained,
benign. Live-trace lane n/a (no live runs, contract pin).

**Adopted (fixed in-stack, gate re-run after):**
1. **Migration comment edit disclosed** (contract-verifier MINOR + conventions finder —
   convergent across two lanes): `alembic/versions/0f4e2d8c9b1a_extract_schema_v2.py:26`
   had its comment cross-reference repointed `extract_prompt→iof_prompt` — comment-only,
   zero DDL change, but it crosses the contract's "alembic/versions content is never
   edited" absolute and was not in the build's flagged-deviations list. Adjudication:
   **kept** (reverting would leave the comment pointing at a deleted module; the edit is
   doc-truth, exactly this slice's business) and recorded here as the named exception
   under rubric item 4 — owner ratifies at PR review.
2. **Stale egress docstrings in `runtime/harness.py`** (security lane LOW + adversarial
   NOTE): module docstring still claimed the retired `block.written` event; `run_harness`'s
   `search_backends` arg doc still described the pre-rider fixture-backend default ("the
   default remains both backends") — the code is *stricter* than the doc claimed. Both
   rewritten to the as-built behaviour.
3. **Dead `if executed_calls is not None:` guard in `acquire.py:542`** (`/code-review`
   cross-file angle): the legacy-path cut made `executed_calls` required (non-Optional),
   leaving the wrapper dead — and worse, it would silently skip unknown-backend validation
   if the type contract were ever violated. Guard removed; validation now unconditional.
4. **Two verification.md corrections** (contract-verifier NOTE + adversarial NOTE),
   applied above in place: the `test_echo_requires_source_snapshot_id` deletion rationale
   (dead-path, not duplicate) and the skeleton grep-gate phrasing (prose mentions in
   living docs vs module paths).

**Flagged deviations — all seven confirmed/ratified** (adopt as-is, no contract
escalation): Phase A direct-call fail-closed tests (lead re-traced: wire-level typing
upstream intercepts malformed input, so direct calls are the only way to exercise
`validate_iso_alpha2`'s defense-in-depth branches; coverage present and asserts the exact
error type) · B1 `usage_metadata` rename/widen (adversarial: emitted metadata identical,
handles both usage forms) · C4 `parse_structured` 10-site reach + planner signature
(adversarial: error strings byte-identical via `label="planner"`) · C3 repoints +
`block.written` retirement (adversarial: zero live emitters/consumers; canon-5 test
exists) · E path-anchor fixes (all path-anchor class) · WP9 requires-dist-only lock delta
(lead-verified: 0 resolved-version changes) · `_scrub_nul` decline (live at
`extract.py:663` + `planner.py:125`). Plus one the stack surfaced: **WP10a used a local
literal `4` with parity comment instead of importing `MAX_CONCURRENT_BATCHES`**
(deliberate — avoids a `group→corpus` import edge; residual risk is silent drift if the
corpus constant changes; ratified).

**Declined (recorded reasons):**
- `core/tracing.py` flat-counts branch deletion + `_embedding_rate_limit_jitter_s` inline
  (adversarial enumeration challenges): both matched to adjudicated review-findings line
  items ("tracing.py:501 dead branch", "embeddings jitter wrapper"); the tracing branch
  independently verified unreachable (group counts are facet-keyed; no top-level
  `findings_total`).
- `core/tracing.py` EB-domain imports (altitude + adversarial): pre-existing coupling,
  disclosed in § Review handoff, deferred.md entry exists; no module-level cycle (verified
  — the DAG check legitimately passes at module granularity).
- `parents[4]` anchor fragility (altitude + security INFO): contract-adopted decision;
  the suite exercises the anchor, so a wrong depth fails `make verify` loudly.
- `scripts/_fixture_sanitizer.py` helper docstrings (conventions): underscore-private
  module with a module docstring; helpers are one-liners below the public-surface bar.
- Recorder-script retry-loop removal (removed-behavior finder): adjudicated cut ("curl
  retry in script"); dev-time, operator-run.
- Extraction-backend double message-build (simplification finder): identical on dev —
  pre-existing, out of diff scope.
- test_harness.py:31 comment mentioning `block.written` (adversarial): accurate
  historical note explaining the repoint, not a live claim.

**Deferred (new entries riding this PR):** two security-lane INFO items routed to the
Bedrock whole-repo pass — consider `<N+1` ceilings on the untrusted-input parsers
(`lxml`, `trafilatura`), and `FixtureFetcher`'s `assert`-based basename-traversal guard
→ `ValueError` (vanishes under `python -O`; dev/test-only surface).

**Convergence notes:** the migration comment edit was found independently by two lanes
(high confidence); the WP10 optimisations were verified correct by two independent lanes
(efficiency finder + adversarial F-pass: deterministic submit-order merge, empty-rows
guard, zero-norm guard + frozen vector set). Unique-to-one-lane catches justifying their
lanes: the harness egress docstring (security), the dead `executed_calls` guard
(`/code-review` cross-file), the deletion-rationale inaccuracy (adversarial). The
security lane additionally verified all load-bearing controls intact through the regroup
(pinned-IP SSRF transport, 015 query sanitizers, credential-excluding cache key,
pytest-socket denial, fail-closed country validation). Fake-done check on the stack's own
fixes: doc rewrites + one dead-guard removal — no test touched, no error swallowed; gate
re-run green below.

**Post-fix gate:** full `make verify` green after the three fixes (1328 passed, mypy
clean, ruff clean, wheel+sdist built).

## Rubric status

| # | Item | Status |
|---|---|---|
| 1 | All nine WPs + WP10 landed or deferred with sign-off | **HOLDS** (contract-verifier: WP1–WP10 all present as-built; exclusions in deferred.md) |
| 2 | `make verify` green · stub smoke under new layout · grep gates zero | **HOLDS** (gate green pre- and post-stack; `test_full_stub_end_to_end_mints_artefact` asserts minting, not just exit-0; all gates 0 live hits) |
| 3 | No unapproved gated change; deps = WP9 set; lock unchanged in resolution | **HOLDS** (pyproject diff = exactly WP9 + approved script removal + pyright prune; uv.lock 0 version changes) |
| 4 | No generated files hand-edited | **HOLDS with one named exception** — the comment-only cross-reference fix in migration 0f4e2d8c9b1a (finding 1 above; DDL untouched; owner ratifies at PR review) |
| 5 | No tests deleted/weakened without justification; pins unmodified | **HOLDS** (pins byte-identical; all 27 directive tests survive; every deleted test traced to deleted code; consolidated doubles preserve raise-on-unexpected guards) |
| 6 | Behaviour preservation; deletions match line items; keeps untouched | **HOLDS** (adversarial: no smuggled behaviour change; both enumeration challenges matched to line items; v6 lane/ChunkReranker/search cache/leg_directive untouched; skeleton fully retired) |
| 7 | Verification evidence recorded incl. routing note | **HOLDS** (this file; codex-exhaustion routing note in § Review handoff and above) |
| 8 | Known gaps + deferred seams listed | **HOLDS** (all contract-named seams in deferred.md + two new security-lane items this stack) |
| 9 | Docs truth vs as-built tree | **HOLDS** (README/AGENTS.md/readiness.md verified by two lanes; two stale harness docstrings found and fixed in-stack) |
| 10 | Tier-3 stack ran, adjudicated in fresh conversation | **HOLDS** (this section; heterogeneity caveat recorded — both heavyweight lanes Claude-family per the Codex-exhaustion fallback) |
