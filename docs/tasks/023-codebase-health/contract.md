# Task contract: 023-codebase-health

One implementation slice. Boundaries: [AGENTS.md](../../../AGENTS.md); specs: [docs/specs/](../../specs/index.md).

> **Status:** approved. Contract approved (before planning): 2026-07-14 · owner
> (amended same day by owner direction: skeleton retirement + orchestrate-standardised checks) ·
> Plan approved (before implementation): 2026-07-14 · owner · ADR: 0019 Accepted.

## Goal

A behaviour-preserving codebase-health slice before the eval slice: land the owner-adjudicated
findings of the 2026-07-14 whole-codebase review ([review-findings.md](review-findings.md) —
six review lanes + lead naming/structure re-sweep + a trailing optimisation lane). The runtime
behaviour of every pipeline component is identical before and after; what changes is dead
weight (~830 lines + echo chain), names (IOF/ICF symmetry, the grouping/plan/ingest renames),
package structure (capability-aware regroup), docs truth, test hardening, and the dependency
manifest (three approved edits) — identical save the three named WP10 output-/numerically-
equivalent optimisations. Rationale for sequencing: renames/moves are cheap now and
expensive after eval baselines pin trace shapes and import paths.

## Deliverable

One PR: the regrouped `src/policy_atlas/` package (`runtime/` ·
`evidence_base/{sourcing,assess,corpus,extract,group,synthesis}` · `core/`), the rename set,
the dead-code cuts, hardened tests, a truthful README, the approved `pyproject.toml` edits,
and `verification.md` evidence that behaviour is preserved (prompt pin tests byte-identical,
full `make verify`, stub full-chain skeleton smoke).

## Read first

- [review-findings.md](review-findings.md) — the primary input; every item below is
  adjudicated there (owner, 2026-07-14). This contract selects and sequences; it does not
  re-argue.
- [product.md](../../specs/product.md) + [EB components](../../specs/capabilities/evidence-base/components.md)
  — the structure rationale (tools → components → capabilities; EB one of several future
  capabilities).
- AGENTS.md (docstring convention; hard gates; Current phase already points here).

## Scope / Out of scope

**In (nine work packages):**

1. **Test pre-hardening** (before any move): object-form the 11 string-path
   `monkeypatch.setattr` sites (tests/test_extract.py, test_extract_judgment.py,
   test_search_wire.py — line anchors shifted post-022; locate by grep, and note
   test_extract_judgment.py uses dynamic f-string forms
   `m.setattr(f"policy_atlas.extract.{name}", …)` that need object-form equivalents,
   not a mechanical string swap); add 4 fail-closed rows to the country-filter matrix
   (test_search_directives.py) covering validate_iso_alpha2's untested raise branches +
   expand_tier1 unknown-label; add the missing `OpenAISearchGenerationBackend` wire test.
2. **embeddings.py split**: `resolve_openai_client`/`openai_kwargs`/`require_parsed`/
   `require_single_tool_call` → new `openai_client.py`; `usage_metadata`/`log_usage` →
   existing `usage.py`; delete `grouping.py:226 _log_usage` dup. (~13 importer modules
   repointed.)
3. **Dead-code cuts** — the review's unconditional list (~830 lines: facet_values partition
   path, vetter plumbing merge, grouping.validate_themes, characterise dead wrapper,
   acquire legacy path, and the ~20 smaller items) **plus** the adjudicated echo-chain cut
   (harness/plan/state fields; repoint test_harness + test_compile at a real component)
   **plus skeleton retirement** (owner reversal, 2026-07-14, superseding the earlier
   "stays" ruling): delete `skeleton.py` (~1,290 lines) after WP4 moves
   `select_document_fetcher` out; remove the `policy-atlas-skeleton` console script from
   pyproject (approved public-interface removal — owner, same date); **`orchestrate` is
   the standardised smoke + live-check vehicle from this slice on** (it has a full stub
   mode — no `OPENAI_API_KEY` → deterministic stubs + the egress-free fixture corpus via
   the harness default fixture backends — and an injectable `ConsoleIO` seam for scripted
   runs). The lane-1 skeleton trims (payload accessors, shared backend bundle) are moot —
   resolved by deletion; orchestrate keeps its own `_live_planner_and_backends`.
   **Excluded from the cut list:** the 4× ThreadPoolExecutor fan-out consolidation →
   deferred.md (subtle per-site diffs, wrong risk profile for this slice).
4. **Renames** (git mv + import/test rewrites; no content changes beyond module paths):
   `extraction_records→iof_records`, `implementation_context_records→icf_records`,
   `extract_prompt→iof_prompt`, `implementation_context_prompt→icf_prompt`,
   `finding_vetter`+`icf_finding_vetter`→ one `finding_vetter` (rides the WP3 plumbing
   merge), `grouping→theme_grouping`, `plan→run_spec` (+`test_compile→test_run_spec`),
   `ingest→ingest_upload`; move `select_document_fetcher` skeleton→fetch_live (repoint its
   one test importer); fix the stale extraction_backend docstring (it serves both kinds).
5. **Package regroup** — the owner-amended final structure (review-findings § Revised
   structure — FINAL): `runtime/`, `evidence_base/` (clustering_engine at its root +
   sourcing/screen/corpus/extract/group/synthesis), `core/` — skeleton absent (retired,
   WP3); `[project.scripts]` needs no path update (the sole script is removed with
   skeleton). Includes: alembic/env.py import updates.
   No `tools/` bucket (owner ruling — search stays in evidence_base/sourcing; the
   search-as-shared-tool seam → deferred.md).
   **Adversarial-review adoptions (2026-07-14):** (a) `facet_grouping.py` residue fold is
   an explicit step — move its 5 LIVE constants (`FACET_VALUE_CAP`, `VALUE_SURFACE_MAX`,
   `LABEL_MAX`, `DESCRIPTION_MAX`, `FORBIDDEN_GROUP_LABELS`) into `facet_values.py`,
   repoint the ~5 src + ~5 test importers, then delete the module (WP3 removes only its
   dead TypedDicts; the fold is move-work, not deletion — "flag, don't drop" respected);
   (b) `ingest_full_text.py` `parents[2]` repo-root anchor becomes `parents[4]` (+ comment)
   when the module moves two levels deeper — it is the one move-fragile production disk
   path, and `make verify` exercises it (`POLICY_ATLAS_FIXTURE_CORPUS` unset in CI);
   (c) `src/policy_atlas/data/` **stays at package root** — all five
   `importlib.resources.files("policy_atlas")` anchors (prod + tests) are top-package and
   need no change (the earlier "update 2 anchors" instruction is withdrawn as misdirected);
   the test-side disk-path guard (`Path(ingest_full_text.__file__).parent`) is depth-robust.
   **Tests mirror the same tree** (owner, 2026-07-14): test files move into
   `tests/{runtime,evidence_base/{…},core}/` matching their subject module (with
   `__init__.py` per new dir); `conftest.py`, `helpers.py`, `synthesis_wire.py` stay at
   `tests/` root as shared infrastructure; the ~5 cross-test-file imports
   (`tests.test_group`/`test_runner`/`test_acquire`) are updated — absolute
   `from tests.helpers import …` imports and the root conftest fixtures are unaffected
   by design (tests/ is a package).
6. **Docs truth**: README.md full rewrite (pipeline, setup, layout — its current 5 lines
   are 100% stale); readiness.md "022 in review"→merged (the carried step-8 miss);
   AGENTS.md Current phase + prompt pins already corrected at design open (this branch).
7. **Riders**: docstring `Args:` sections on the 19-site backend-protocol cluster
   (acquire.py/search_live.py) + 7 stragglers; prune `[tool.pyright]`.
8. **Test consolidation — top-2 wins only**: the 5×-copied fake OpenAI parse-client stack
   → one helper in tests/helpers.py; the 9 scripted synthesis backends → a base class in
   the existing tests/synthesis_wire.py. (Consolidations 3–5 → deferred.md.)
9. **Dependency manifest** (owner-approved 2026-07-14): declare `lxml` and `pymupdf` as
   direct dependencies (already directly imported); raise stale floors to locked majors
   (`langgraph>=1`, `trafilatura>=2`, `structlog>=26`, `mypy>=2`, `pytest>=9`);
   `pymupdf4llm<1` ceiling untouched (deliberate). Lockfile expected unchanged
   (floors ≤ locked versions).

10. **Wall-clock optimisations — adopted subset** (lane 7, lead-adjudicated; these two are
    *output-identical* rather than strictly no-change — the one deliberate exception to the
    behaviour-preservation fence, named here so the gate approves it explicitly):
    (a) set `max_concurrent_batches=MAX_CONCURRENT_BATCHES` in `_group_policy`
    (group.py:766) — one line; unserialises grouping assignment batches; the identical
    engine path already runs at 4-wide for characterise, and batch-order merging is
    deterministic; (b) bulk-insert the appraisal rows (appraise.py:236-267) — deterministic
    rubric loop, collect + one `insert().values([...])`; event rows stay per-row (sequence
    uniqueness); (c) replace the pure-Python `_cosine` loop with `math.sumprod` (stdlib,
    ≥3.12) + unit norms precomputed once at `ChunkRetriever` construction + query norm once
    per search (synthesis_tools.py:1228,1327) — retrieval hot path scored per unit per
    `search_chunks` call; ~50-100× on the arithmetic, zero new deps; numeric-precision
    caveat recorded in review-findings § Lane 7 #7 (last-ulp score differences could
    reorder a near-tie). **Deferred from the same lane** (→ deferred.md): the five-facet group
    fan-out (high-impact for deep runs but needs conn-read hoisting — candidate to ride the
    eval slice if deep-run wall-time hurts throughput) and embeddings batch-slice
    parallelism. **Declined with reasons** (review-findings § Lane 7): in-round search
    parallelisation, cache-deepcopy removal.

**Out (owner-adjudicated keeps and deferrals — do not touch):**
- `synthesis_prompts_v6.py` + v6 branches (frozen cost baseline; deletes first post-eval
  cleanup) · `ChunkRerankerBackend` (Bedrock seam) · search_live TTL/LRU cache ·
  `leg_directive` (c4-demo hook; deletes with C4 close-out). (Skeleton's earlier "stays"
  ruling is REVERSED — retirement is now WP3 scope, see above.)
- ~~`src/policy_atlas/data/` stays in the package~~ — SUPERSEDED (owner rider at step-6
  close, 2026-07-14): once the smoke reframing showed the suite's stub e2e runs with
  empty search backends, the packaged data's only production reader was the ad-hoc
  demo's acquire enrichment. Rider moved `data/` → `tests/data/provider_records/` and
  the fixture backends → `tests/provider_fixtures.py`; harness default search backends
  are now empty. Gates re-run; recorded in verification.md § Post-exit rider.
- Any prompt **text** change — module renames only; every pinned prompt surface stays
  byte-identical (pin tests are the proof).
- Schema, migrations, runtime behaviour, exception-hierarchy standardisation, test-dir
  bucket mirroring, whole-repo security pass (Bedrock task), LLM cost work (eval slice).

## Constraints & approval gates

- **Deps**: gated surface — the WP9 set is pre-approved (review-findings § Owner decisions,
  2026-07-14); anything beyond it is a stop condition.
- **Public interface**: the `policy-atlas-skeleton` console script is REMOVED with the
  skeleton retirement (owner-approved 2026-07-14; `python -m policy_atlas.runtime.orchestrate`
  is the entry point). `policy_atlas` is an internal package — import-path changes inside
  it are not a public-interface change.
- No schema, auth, CI-semantics, or prod-config changes. CI must stay green through the
  same `make verify` entry point (Makefile targets unchanged).
- Generated files untouched (alembic/versions/* content is never edited — only env.py
  imports).

## Public / private boundary

Everything in this slice is public-safe (code moves, docs, tests). No acquired text, traces
or credentials are touched.

## Model route

n/a — no inference-bearing change. Prompt surfaces move between modules byte-identically;
no prompt-version bumps.

**Live-check scope (contract-time pin):** NO live run this slice. Rationale: no
prompt/model/schema/egress change; behaviour preservation is evidenced by the pin tests
(byte-identical prompt surfaces), the full test suite — including
`test_full_stub_chain_commits_each_step_and_checks_in` (tests/test_runner.py), the
primary full-chain stub evidence — and an **orchestrate stub-mode smoke** (no
`OPENAI_API_KEY`, scripted console input, zero egress): the standardised check vehicle
from this slice on, replacing the retired skeleton smoke. A live run would spend
wall-time to evidence surfaces this slice cannot have changed. Future slices' live
checks also run through `orchestrate` (record the standard in Phase H).

## Disciplines binding this slice

Template defaults apply. Slice-specific: **flag, don't drop** governs the cut list — every
deletion in WP3 must match a review-findings line item; a deletion not on the list is scope
growth (stop condition).

## Stop conditions

Template defaults, plus: any WP requiring a runtime-behaviour change to complete (that's a
finding for deferred.md, not a fix); any dependency change beyond the WP9 set; `uv.lock`
churn from WP9 (floors should be no-ops against the lock — if the lock moves, stop and show
the owner).

## Acceptance checks

- `make verify` green (okf-validate · test · typecheck · lint · build).
- All prompt pin tests pass **unmodified** — the byte-identity proof for every pinned
  surface (planner_v5, extract_iof_v7, extract_icf_v2, screen/classify surfaces,
  synthesise_section_v7/v6-frozen, synthesise_sections_v2, vetters).
- Orchestrate stub-mode smoke completes (scripted console; all components dispatch under
  the new layout via the harness default fixture backends; zero egress).
- Grep gate: zero references to `policy_atlas.skeleton` / `policy-atlas-skeleton` outside
  historical docs.
- Grep gates: zero references to retired module paths (`policy_atlas.grouping`,
  `policy_atlas.plan`, `policy_atlas.extraction_records`, `policy_atlas.extract_prompt`,
  `policy_atlas.implementation_context_*`, `policy_atlas.icf_finding_vetter`,
  `policy_atlas.ingest\b` (word-boundary — must not match `ingest_full_text`),
  `policy_atlas.facet_grouping`, `policy_atlas.synthesis_prompts_v6` → new path, etc.)
  anywhere in src/tests/scripts/alembic/docs (living docs only — historical
  `docs/tasks/**` **and `docs/verification/private/**`** stay untouched). Plus a
  **catch-all**: every `from policy_atlas\.\w+ import` hit outside the exempt paths must
  resolve to a module under `runtime/` · `evidence_base/` · `core/` (or the root `data/`)
  — catches stale flat paths for the ~55 modules that move without renaming.
- No import cycles in the new layout (the review-verified DAG property holds).
- Deterministic checks only — no AI-judge eval applies (no judged surface changes).

## Verification evidence expected

`verification.md`: per-WP diff summary; the pin-test and skeleton-smoke command outputs;
the grep-gate outputs; before/after `git ls-files src | wc -l` and line-count delta vs the
review's estimates; confirmation `uv.lock` is unchanged; the deferred.md entries added
(fan-out consolidation, search-tool seam, test consolidations 3–5, plus any optimisation
deferrals); public-safety confirmation.

## Risk tier & review focus

**Tier 3** — the deps hard gate binds it (WP9), and the surface area (60+ files moved) earns
adversarial review even though every change is behaviour-preserving. Codex is exhausted
(2026-07-14): adversarial lanes route down the ladder per the recorded fallback — family
heterogeneity will NOT be achieved this slice; record it in verification.md.

Review focus: fake renames presented as fixes · silently weakened tests during WP1/WP8 ·
behaviour change smuggled into a "move" (diff of moved files must be path-only plus the
adjudicated cuts) · scope creep beyond the adjudicated findings list.
