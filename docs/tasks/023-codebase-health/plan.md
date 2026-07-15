# Plan: 023-codebase-health

> Status: drafted (pending contract-adversarial adjudication + plan-adversarial + owner 🛑).
> Contract: [contract.md](contract.md) (approved 2026-07-14 · owner). Tier 3.
> Executor routing note: **Codex exhausted 2026-07-14** — per the recorded fallback, all
> would-be `codex` marks route down the ladder (`deep-reasoner`/`fast-worker`); family
> heterogeneity is not achievable this slice (recorded for verification.md).

## Shape

Ten work packages land as eight build phases. The ordering rule the whole plan serves:
**harden the tests → shrink the code → rename → move → then everything that reads the new
tree** (docs, consolidation). Renames (Phase D) and moves (Phase E) are deliberately two
commits, not one — each wave is independently `git diff --find-renames`-auditable, which is
the review stack's main defence against behaviour change smuggled into a move.

Verify gates (consolidation argued per phase, reviewed at this 🛑): full `make verify` at
**baseline · after C (mass deletion) · after D (behaviour-bearing WP10 edits + the
ingest-adjacent `ingest`→`ingest_upload` rename — mandatory-class, not consolidatable) ·
after E (regroup) · step-6 exit**; `make verify-fast` after A and B only. Rationale: A/B are
narrow, grep-verifiable test/move surfaces whose failures the next full gate catches
identically; C, D and E each carry structural or behavioural weight.

## Phases

### Phase 0 — baseline (lead, inline)
`make verify` full, green, on branch open (mandatory class). Record runtime as the
baseline for later gates.

### Phase A — WP1 test pre-hardening — `fast-worker`
Precise-site mechanical work from review-findings § Lane 4:
- Object-form the 11 string-path `monkeypatch.setattr` sites (test_extract.py:533,810,1170-1173;
  test_search_wire.py:85,208; and test_extract_judgment.py:580,598 — these two are DYNAMIC
  f-string forms `m.setattr(f"policy_atlas.extract.{name}", value)`: convert to the
  module+attr-name object form `m.setattr(extract_module, name, value)`, not a string swap).
- +4 fail-closed rows in the country-filter matrix (test_search_directives.py) covering
  validate_iso_alpha2 empty-list / non-string / duplicates + expand_tier1 unknown-label.
- New `OpenAISearchGenerationBackend` wire test (mirror the existing per-backend wire-test
  shape; use the current fake-client pattern — WP8's consolidated helper doesn't exist yet).
Gate: `verify-fast`.

### Phase B — WP2 embeddings split + WP10c cosine — split executors
- **B1 (`fast-worker`)**: move `resolve_openai_client`/`openai_kwargs`/`require_parsed`/
  `require_single_tool_call` → new `openai_client.py`; `usage_metadata`/`log_usage` →
  `usage.py`; delete `grouping._log_usage`; repoint all ~13 importers. Done = grep shows
  zero imports of the moved names from `embeddings`, verify-fast green.
- **B2 (`lead`, inline — justification: ~20-line numerically-sensitive edit; smaller than a
  delegation brief)**: `math.sumprod` cosine + unit norms precomputed at `ChunkRetriever.__init__`
  + query norm once per `search()` (synthesis_tools.py:1228,1327). Keep a one-line
  `ponytail:`-style comment noting the precision class.
Gate: `verify-fast`.

### Phase C — WP3 dead-code cuts — `fast-worker` ×3 lanes + `deep-reasoner` ×1
Every cut anchors to a review-findings line item (rubric #6). Four parallel lanes, disjoint
files:
- **C1 (`fast-worker`)**: facet_values partition path + facet_grouping TypedDicts + the
  matching test_facet_values halves.
- **C2 (`deep-reasoner` — justification: the one judgment-bearing cut; merging two modules
  while keeping both prompt surfaces byte-identical, pin tests as the done-check)**: vetter
  plumbing merge → single `finding_vetter.py` (prompts/Literals per-kind, verbatim).
- **C3 (`fast-worker`)**: echo chain cut (harness/plan/state fields) + repoint
  test_harness/test_compile at a real component; characterise dead wrapper (repoint
  test_tracing.py:284); acquire legacy path (update its tests to build ExecutedCall).
- **C4 (`fast-worker`)**: the ~20 small items (findings § Lane 1 list, **minus** the
  plan.py compile hand-copy — moved to Phase D to ride the run_spec rename, resolving the
  C3/C4 `plan.py` collision; **minus** the skeleton trims — moot, skeleton is retired in
  Phase D) + extraction_backend docstring fix. **The lead resolves every C4 item to an
  explicit file:line in the dispatch brief** (several Lane-1 lines carry none). ⚠️ The
  `_scrub_nul leaf` item means: extract._scrub_nul's str base case delegates to
  `prompt_fields.scrub_nul` — the function itself is LIVE (extract.py:669, planner.py:130)
  and must NOT be deleted; the Phase-E acyclicity audit depends on that edge.
Gate: **full `make verify`** (mass deletion).

### Phase D — WP4 renames + WP10a/b — `fast-worker` (+ lead one-liner)
- Renames as pure `git mv` + import/test rewrites: iof_records, icf_records, iof_prompt,
  icf_prompt, theme_grouping, run_spec (+test_run_spec, + the plan.py compile hand-copy
  shrink riding the rename per the convergence note), ingest_upload; move
  `select_document_fetcher` → fetch_live (repoint its one test import,
  test_ingest_full_text.py:788).
- **Skeleton retirement (owner reversal 2026-07-14)**: after the fetcher move — delete
  `skeleton.py`; remove `[project.scripts] policy-atlas-skeleton` from pyproject
  (approved); grep gate `policy_atlas.skeleton|policy-atlas-skeleton` → zero outside
  historical docs. (`fixtures.py` stays — orchestrate's stub corpus and tests use it.)
- **WP10a (`lead`, inline — one line)**: `max_concurrent_batches=4` in `_group_policy`
  with a comment naming the parity ("matches theme_grouping.MAX_CONCURRENT_BATCHES") —
  a local literal, NOT an import from theme_grouping: the constant lives in a `corpus/`
  module and importing it would manufacture a `group/`→`corpus/` edge re-pathed twice
  across D and E (adversarial finding m4).
- **WP10b (`fast-worker`)**: appraise bulk insert (events stay per-row) — with an
  empty-`rows` guard (`insert().values([])` raises where the per-row loop no-op'd;
  finding m4 build note).
Done-check: grep gates for retired names return zero; pin tests untouched and green.
Gate: **full `make verify`** (behaviour-bearing WP10 edits + ingest-adjacent rename;
promoted per adversarial finding m3).

### Phase E — WP5 regroup — `fast-worker` (bucket map is the spec) + `lead` audit
- `git mv` per the contract's final bucket map (src + mirrored tests tree with per-dir
  `__init__.py` — skeleton absent, retired in D); rewrite imports; alembic/env.py imports;
  update the ~5 cross-test-file imports. (No pyproject script edit — the sole script was
  removed in D.)
- Adversarial-review adoptions (explicit steps): **facet_grouping residue fold** — 5 live
  constants → `facet_values.py`, repoint ~5 src + ~5 test importers, delete the module;
  **`ingest_full_text.py` repo-root anchor** `parents[2]`→`parents[4]` + comment.
  `src/policy_atlas/data/` stays at package root (all top-package `resources.files`
  anchors unaffected — no anchor edits).
- **Lead audit (justification: adjudication-class check, the slice's core risk)**: after the
  sweep, `git diff --find-renames` review confirming every moved file's diff is
  path/import-only (+ the two explicit steps above); includes a one-line acyclicity
  confirmation of the `runtime/planner → evidence_base/extract` edge (planner.py:23 imports
  the private `_scrub_nul` — DAG holds; hoisting is out of scope, noted).
Gate: **full `make verify`** + orchestrate stub-mode smoke (no `OPENAI_API_KEY`, scripted
console input → full chain on harness default fixture backends, zero egress).

### Phase F — WP6 docs + WP7 riders + WP9 deps — `lead` + `fast-worker`
- **README rewrite (`lead` — justification: product-voice/taste surface)**.
- readiness.md line + `[tool.pyright]` prune + WP9 dependency edits (`lead`, inline —
  justification: approval-gated surface, trivial diffs; `uv lock --check` proves the lock
  is untouched, else stop condition).
- Docstring `Args:` cluster, 19 sites + 7 stragglers (`fast-worker`).
Gate: `verify-fast`.

### Phase G — WP8 test consolidation (top-2) — `fast-worker`, lead assertion-parity check
- Fake parse-client stack → one `tests/helpers.py` helper (5 files repointed).
- Scripted synthesis backends → base class in `tests/synthesis_wire.py` (9 classes, 3 files).
- **Lead check (justification: rubric #5 — consolidation may not drop an assertion)**:
  before/after assertion inventory on the touched files.
Gate: **full `make verify`** (step-6 exit class) + grep gates + skeleton smoke re-run.

### Phase H — records (lead)
verification.md (per-WP evidence per the contract's list) · deferred.md entries (fan-out
consolidation · search-as-shared-tool seam · test consolidations 3–5 · five-facet group
fan-out with the conn-hoisting design note · embeddings batch-slice parallelism · v6
deletion post-eval) · **knowledge record: orchestrate is the standardised smoke +
live-check vehicle** (skeleton retired; stub mode = no-key default; scripted-console
drive) · living-doc sweep for renamed module citations (docs/knowledge + agentic-ops;
historical docs/tasks/** untouched) · commit.

## Lead-mark summary (plan-gate review line)

Lead keeps: B2 (small numeric edit), WP10a (one line), Phase-E move audit + Phase-G
assertion parity (adjudication-class), README (taste), deps/pyright (gated surface),
Phase H records. Everything else is delegated. No `codex` marks (exhausted).

## Live-check scope

None (contract pin) — pin tests + stub skeleton smoke are the behaviour evidence.

## Risks the plan accepts

- Two import-rewrite waves (D then E) instead of one — paid deliberately for auditability.
- Phase-C parallel lanes touch disjoint files by construction; C4's small-items list is the
  only lane with breadth — its brief enumerates exact file:line items, nothing else.
- WP10c precision class (recorded); if any pin/judgment test proves sensitive to score
  ordering, stop and surface rather than adjust the test (rubric #5).
