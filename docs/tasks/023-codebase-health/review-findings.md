# Pre-eval codebase review — merged findings (lead adjudication in progress)

Lanes: 1 over-engineering (deep-reasoner) · 2 naming+structure (deep-reasoner) · 3 docs drift (fast-worker, DONE) · 4 test quality (test-engineer) · 5 deps+hygiene (fast-worker) · 6 conventions (fast-worker)

## Lane 3 — docs drift (COMPLETE, 6 findings, verified with evidence)

1. **README.md — entirely stale (5 lines, every sentence wrong).** Claims "pre-implementation repository / specification preparation"; reality: full working package, 24 migrations, tasks 001–022 merged. Last touched at commit f2c64cf. → REWRITE (describe pipeline, setup, layout).
2. **AGENTS.md Current phase** still says 022 in build; 022 merged (PR #29, 7d0d7d7). → per task-cycle close-out rule, Current phase moves with the *next* slice's design step — this cleanup slice or eval slice will update it. Known-process item, not a surprise.
3. **AGENTS.md pinned prompt surfaces stale, 4 of 6 wrong:**
   - says planner_v3 → code pins planner_v5 (planner_prompt.py:29)
   - says extract_iof_v6 → code pins extract_iof_v7 (extract_prompt.py:43)
   - says extract_icf_v1 → code pins extract_icf_v2 (implementation_context_prompt.py:34)
   - says synthesise_section_v5 → code pins synthesise_section_v7 (synthesis_backend.py:63); v6 frozen as cost-harness fixture only
   - synthesise_sections_v2 accurate.
4. **docs/agentic-ops/readiness.md:23–25** — "022 in review" → merged.

Clean (verified): Makefile targets vs docs, pyproject scripts, docs/specs/README, docs/knowledge/README + index (all 64 concepts linked, no orphans), alembic/README, CLAUDE.md. Coverage limit noted: large agentic-ops files only target-grepped, not fully re-read.

## Lane 1 — over-engineering (COMPLETE — net −1,300 lines possible: ~830 unconditional, ~470 owner-gated)

Agent self-verified all findings by grep; dropped 4 of its own candidates as NOT over-engineering (scope_filters is live; pinned-IP transport is a real SSRF control; InferenceProvider/SynthesisBackend Protocols have real impls/Bedrock seam; no removable deps).

### Owner-gated (deliberate seams — decide, don't auto-cut, ~470 lines)
- **synthesis_prompts_v6.py + v6 branches in synthesis_backend (~240)** — no caller passes v6; BUT it's the frozen cost-protocol baseline for the imminent eval slice. Owner call. [synthesis_backend.py:1399,1419,1432]
- **echo component chain (~70)** — harness.py:101, plan.py:14; only tests use it. Is it the retained smoke? Owner confirm.
- **ChunkRerankerBackend Protocol (~25)** — single no-op impl; docstring says real one "lands with Bedrock" (near roadmap). Defer.
- **leg_directive identity fn (~25)** — runner.py:271; named seam + c4-demo monkeypatch hook.
- **search_live TTL+LRU cache (~55)** — LOW confidence; may save egress; per-run dict would cover.

### Unconditional cuts, biggest first (~830 lines)
- delete: facet_values.py:261 orphaned one-call-partition path (validate_partition, merge_repair, value_records, ValidatedPartition, …) — superseded by two-stage engine, tests-only callers (~160 + half of test_facet_values)
- shrink: finding_vetter.py / icf_finding_vetter.py near-identical plumbing → share (prompts/Literals stay per-file, product surfaces; ADR 0017 schemas untouched) (~150) [icf_finding_vetter.py:200]
- shrink: ThreadPoolExecutor fan-out reimplemented 4× (extract.py:674, screen.py:404,842, classify.py:231) → one fan_out_with_retry; land LAST, subtle per-site diffs (~60)
- delete: grouping.py:140 validate_themes + local InvalidDiscoveryOutput — superseded by clustering_engine.validate_discovered_labels; caller = test only (~58)
- delete: characterise.py:533 production-dead clustering wrapper (5 pieces); repoint test_tracing.py:284 (~55)
- delete: acquire.py:180,858 _LegacySearchCall + None-fabrication branch — prod always passes executed_calls (~40)
- shrink: skeleton.py:373 four payload accessors → inline (~40)
- shrink: structured-parse boilerplate 6× → parse_structured() (~30) [screening_backend.py:122]
- shrink: synthesise.py:1647 _substrate_view pass-through called once → inline (~28)
- shrink: skeleton/orchestrate duplicated live-backend construction → shared bundle (~25, partial)
- delete: country_filters.py:505 GROUP_PROVENANCE zero readers (~22)
- delete: facet_grouping.py:41 wire TypedDicts (dead with partition path) (~22)
- shrink: 3 identical call-budget dataclasses → one CallBudget (~20) [extract.py:284, screen.py:77, select.py:253]
- ~15 smaller: runner payload-scan 3× (~15), fingerprint tails (~15), turn-assembly (~15), fixture-sanitizer scripts (~24), search_live dead re-exports (~14), OrchestratorIO Protocol (~14) [runner.py:154], _single_int_value (~14), render_field_docs dup (~12), tracing preamble 6× (~12), _metadata helper 3× (~10), curl retry in script (~10), _FLOAT_FIELDS (~9), generation_call_cap dead config (~8) [search_loop.py:104], plan.py compile hand-copy (~9), tracing.py:501 dead branch (~6, medium conf), PlannerBackend.mode (~6), StopDecision.overlay_applied (~3), _scrub_nul leaf (~2), REPAIR_ROUND_CAP (~2), ProjectionKind dup (~2), _coverage_for_run test helper (~5), embeddings jitter wrapper (~4)

### Cross-lane convergence (high confidence)
- skeleton.py: lane 1 (payload accessors, dup backend construction) + lane 2 (1,290-line legacy CLI, one test importer) → demote/trim skeleton is a real theme
- grouping.py: lane 1 (dead validate_themes) + lane 2 (rename theme_grouping) → same module, one combined fix
- plan.py: lane 1 (compile hand-copy shrink) + lane 2 (rename run_spec) → combine
- log_usage: lane 1 didn't flag, lane 2 found grouping.py:226 _log_usage dup → folds into usage.py move

## Lane 2 — naming + structure (COMPLETE)

**Import graph: clean DAG, no cycles.** runtime layer (harness ~27 imports, runner/orchestrate ~25) sits on top; nothing imports back up.

### Headline: 8-subpackage grouping (behaviour-preserving, git mv + import rewrites)
```
runtime/:   orchestrate, runner, harness, skeleton, steering, orchestration_plan, planner, planner_prompt, plan
sourcing/:  search_generation, search_live, search_loop, search_prompts, acquire, ingest, ingest_full_text, fetch_live, country_filters, grounding
screen/:    screen, screening_backend, screen_prompt, classify, classification_backend, classify_prompt, appraise
corpus/:    characterise, select, ranking, grouping
extract/:   extract, extraction_backend, extraction_records, extract_prompt, implementation_context_prompt, implementation_context_records, finding_vetter, icf_finding_vetter, finding_references, quote_verify
group/:     group, group_clustering, facet_grouping, facet_values, clustering_engine
synthesis/: synthesise, synthesis_backend, synthesis_tools, synthesis_prompts_v6, grounding_judge
infra/:     schema, db, events, logging, tracing, usage, inference, embeddings, prompt_fields, tags, fixtures, windowing
```
Prompts deliberately co-located with phases (each *_prompt imports its phase's records/fields). Debatable bucket: grounding (sourcing vs infra — agent chose creation site, one synthesise→sourcing read-edge accepted).

### Pre-bucket blocker (3.1, HEADLINE misplacement): embeddings.py hosts 6 generic OpenAI-client/usage helpers
resolve_openai_client (:144), openai_kwargs (:170), usage_metadata (:182), log_usage (:195), require_parsed (:205), require_single_tool_call (:226) — imported by ~13 modules most of which use nothing embedding-related. This single mis-scope makes embeddings.py look like a universal dep. Fix: client helpers → new infra/openai_client.py; usage_metadata/log_usage → existing usage.py. Then embeddings.py drops out of ~10 import lists. **Do before bucketing.**

### Renames (ranked)
| current → proposed | why |
|---|---|
| grouping.py → theme_grouping.py | it's the CHARACTERISE theme backend (ThemeGroupingBackend :238); name collides with group/group_clustering/facet_grouping — worst offender; rest of "group family" is fine once this moves |
| plan.py → run_spec.py | holds Plan/Config/compile() (:59-67) — run-spec→config compile, not orchestration plan; collides with planner.py + orchestration_plan.py |
| synthesis_prompts_v6.py → singular/unversioned convention | only version-suffixed prompt module; frozen-baseline intent legit; prompt surface = lead-only call |
| ingest.py → ingest_upload.py | it's upload-ingest specifically; general phase is ingest_full_text.py |

### Other misplacements
- 3.2 select_document_fetcher stranded in skeleton.py:93 — skeleton (1,290-line task-001 CLI) imported ONLY by tests/test_ingest_full_text.py:788 for this one fn → move to fetch_live.py; skeleton itself = candidate for demotion/legacy flag (feeds lane 1)
- 3.3 grouping.py:226 _log_usage duplicates embeddings.log_usage → both → usage.log_usage
- 3.4 tags.py:20 has_control_character generic predicate — minor

### Watch items
- planner.py imports extract — confirm it's type/constant-only before finalising runtime/extract boundary
- steering.py imports orchestration_plan + search_loop + facet_values — widest non-orchestrator fan-in

### tests/
1:1 mirror, sensible. If plan.py renames, test_compile.py → test_run_spec.py. No test_grouping.py (coverage lives in characterise tests — correct but invisible; rename fixes legibility). Bucket-mirroring of tests/ = separable second move, not needed now.
## Lane 4 — test-suite quality (COMPLETE — suite is unusually refactor-friendly)

- **Rename blast radius: 3 files, 11 string-path patch sites** (test_extract.py:533,810,1170-1173; test_extract_judgment.py:580,598; test_search_wire.py:85,208) — the only silent breakers; fix = switch to object-form setattr BEFORE/during the regroup. Plus test_search_live.py:668,683 (importlib.resources anchor) and test_ingest_full_text.py:476,480 (disk-path guard) to update alongside. Other 71/74 files: direct imports, mechanical rewrite.
- **Weak tests: ~0** (AST scan, 1,156 tests): 1 intentional assert-free no-raise check; no assert True, no swallowed exceptions, no MagicMock, tight approx tolerances. Do NOT spend the slice here.
- **Prompt-pin tests are change-detectors BY DESIGN** — not move-hostile, do not "fix".
- **Consolidation wins (separable, none block the regroup):** (1) 5-class fake OpenAI parse-client stack copy-pasted 5× → tests/helpers.py, ~200–250 lines; (2) 9 scripted synthesis backends in 3 files → base class in existing tests/synthesis_wire.py, ~200–300; (3) 4 finding-record factories → IOF twin beside existing make_icf_wire_record, ~80–100; (4) fake-Langfuse dup, ~50; (5) 24 capture closures in test_search_live.py → factory, ~60.
- **Money-path coverage:** quote-verify STRONG, envelope fencing STRONG, kind-typed query_findings COVERED, clustering validate/repair COVERED. **One partial hole: country_filters fail-closed** — validate_iso_alpha2 has 6 raise branches, only unknown-code tested; empty list / non-string / duplicates / expand_tier1 unknown-label untested → add 4 rows to existing test_search_directives matrix. **One adjacent gap:** OpenAISearchGenerationBackend (search_generation.py:91) has zero wire tests (every peer backend has one) → add using consolidated fake client.
- **Speed: fine.** ingest_full_text minutes-long cost is documented + mitigated (module-scoped fixture, make test-fast); pytest-socket denies network suite-wide, pinned by its own test.

---

# LEAD RE-SWEEP — naming + structure (supersedes lane 2's proposal; owner-requested, spec-informed)

Read: product.md, capabilities/evidence-base/components.md, data-model.md header, all 63 module docstrings.

## Spec facts that change the structure
- Entity hierarchy is **tools → components → capabilities → artefacts**; evidence sits in a shared information layer **reused across capabilities**. EB is the only v3.0 capability; Options Assessment, Impact, Transferability, VfM, ToC, Risk are named future capabilities (product.md scope table; owner confirms roadmap incl. baseline assessment).
- "Universal core tools, ambient to every component": search, retrieve, lookup, appraise, produce-grounded-block, escalate, clarify. So the search stack and grounding are TOOL-layer, not EB-phase code — this resolves lane 2's grounding sourcing-vs-infra dilemma with spec vocabulary.
- Component modules are already named exactly by the nine spec components (acquire, screen, classify, appraise, characterise, select, extract, group, synthesise — verbs). The support-module noun forms (synthesis_backend etc.) are a consistent pattern, not drift.
- runner.py self-describes "EB capability-runner" — today's runtime is EB-bound in vocabulary but generic in mechanics; capability #2 will force a planner/runner vocab split LATER (seam noted, not built — "build light, leave seams").

## The unmarked-default family (the miss the owner caught) — IOF built first got generic names, ICF got marked names
| current | proposed | note |
|---|---|---|
| extraction_records.py | **iof_records.py** | pairs with icf |
| implementation_context_records.py | **icf_records.py** | |
| extract_prompt.py | **iof_prompt.py** (hosts extract_iof_v7) | module rename only, prompt text untouched |
| implementation_context_prompt.py | **icf_prompt.py** (hosts extract_icf_v2) | |
| finding_vetter.py + icf_finding_vetter.py | **one finding_vetter.py** | lane 1's plumbing merge yields symmetry for free; if merge deferred → iof_vetter/icf_vetter |
| extraction_backend.py | keep name (serves BOTH kinds — OpenAIICFExtractionBackend :177) | **NEW finding: docstring stale, claims IOF-only** |

Also standing from lane 2: grouping→theme_grouping, plan→run_spec, ingest→ingest_upload (note: spec component "ingest(fetch)" is actually implemented by ingest_full_text.py — deeper option: ingest_full_text→ingest post-rename; not required).
Noted, not doing: backend-seam suffix inconsistency (*_backend vs planner/ranking/grouping/search_generation) — mostly dissolves under buckets.

## Revised structure — FINAL, owner-amended 2026-07-14 (replaces lane 2's flat 8 buckets)

Owner rulings: (1) `infra/` name REJECTED — collides with the future top-level CDK `infra/` dir (V2 repo `../discovery_policy_atlas` precedent; this repo becomes a backend+frontend monorepo once the demo frontend is finalised and pulled in) → **`core/`** (owner call — fits the contents; the "core capability" phrasing in specs is not in active use). (2) NO `tools/` bucket — search stays with the evidence base; search-as-shared-tool only becomes real if a web-search capability or new data sources land (incoming capabilities work off the EB-gathered corpus). (3) `evidence_base/`, not `eb/`.

```
policy_atlas/
  runtime/        orchestrate, runner, harness, steering, orchestration_plan,
                  planner, planner_prompt, run_spec(=plan), [skeleton → demote/legacy]
  evidence_base/  # the capability — future capabilities (baseline/options/VfM…) land as siblings
    clustering_engine.py   # shared by corpus/ + group/ only — stays EB-internal until a 2nd capability needs it
    sourcing/   acquire, ingest_upload, ingest_full_text, fetch_live, search_loop,
                search_live, search_generation, search_prompts, country_filters, grounding
    screen/     screen, screening_backend, screen_prompt, classify,
                classification_backend, classify_prompt, appraise
    corpus/     characterise, select, ranking, theme_grouping
    extract/    extract, extraction_backend, iof_records, icf_records,
                iof_prompt, icf_prompt, finding_vetter, finding_references, quote_verify
    group/      group, group_clustering, facet_values (facet_grouping residue folded in)
    synthesis/  synthesise, synthesis_backend, synthesis_tools,
                synthesis_prompts_v6 (frozen), grounding_judge
  core/           schema, db, events, logging, tracing, usage, inference,
                  openai_client (new, ex-embeddings), embeddings (post-split),
                  prompt_fields, tags, fixtures, windowing
```
Rationale: one extra directory level (`evidence_base/`) is the entire cost of capability-readiness; runtime/ + core/ are what future capabilities reuse. Search-tool extraction deferred as a recorded seam (docs/deferred.md candidate), not built. Test blast radius unchanged (lane 4's 3 files + 2 resource anchors + disk guard).

## Lane 7 — wall-clock optimisation (COMPLETE, owner-requested rider 2026-07-14; deep-reasoner; lead-adjudicated)

Brief scope: wall-clock and non-LLM waste only (LLM token cost belongs to the eval slice; prompt-cache prefix work shipped in 022). Static analysis, impact magnitudes structural/unmeasured unless stated. Six findings + a coverage map; adjudication tags added by lead.

### Findings (agent ranking, lead adjudication in brackets)

**#1 — Facet loop in `group` runs 5 independent LLM clustering pipelines serially** `[impact: high — deep runs only] [safety: concurrency-risk]` → **DEFER**
group.py:464 iterates facets one at a time; each iteration (`_run_value_facet` group.py:566 / `_run_claim_theme_facet` group.py:662) is a complete, independent clustering-engine pipeline (discovery + assignment batches + repair → its own FacetAssembly). A deep run requests 5 facets (DEEP_GROUPING_FACETS, orchestration_plan.py:78). Order-independence VERIFIED by the agent: every facet's outputs are facet-keyed; usage_totals is an order-free sum; the single DB insert happens after the loop (group.py:519); assert_grouping_invariants runs after the join. Why not clean: the 3 claim-theme facets read via a shared SQLAlchemy Connection (`_load_claim_theme_units(conn,…)` group.py:670) — NOT thread-safe. Smallest safe diff: hoist per-facet conn reads before the parallel region, fan out pure clustering workers (mirror extract.py:1011). Standard/rapid runs group on 1 facet (DEFAULT_FACETS, facet_values.py:22) → zero benefit there; win is up to ~facet-count speedup on the group phase of deep runs. Stacks with #2.
*Lead ruling: defer to docs/deferred.md — wrong risk profile for a behaviour-preserving slice; candidate to ride the eval slice if deep-run wall-time hurts eval throughput.*

**#2 — `group`'s clustering policy leaves assignment fan-out at `max_workers=1`** `[impact: med] [safety: behaviour-preserving]` → **ADOPT (WP10a)**
The engine already fans out first-round assignment batches (clustering_engine.py:523, ThreadPoolExecutor(max_workers=policy.max_concurrent_batches)), but ClusteringPolicy.max_concurrent_batches defaults to 1 (clustering_engine.py:216) and `_group_policy` (group.py:765) never sets it → grouping assignment batches run one model call at a time. Characterise uses the SAME engine at `grouping.MAX_CONCURRENT_BATCHES = 4` (characterise.py:599, grouping.py:28) — proving the concurrency path safe; attempts merge in batch order regardless of completion order (clustering_engine.py:536-568). With GROUP_ASSIGNMENT_BATCH_SIZE=50 (group.py:83) and FACET_VALUE_CAP in the high-100s, a busy facet is ~4 batches serialised needlessly. Fix: one line — `max_concurrent_batches=MAX_CONCURRENT_BATCHES` in the ClusteringPolicy(...) at group.py:766. Stacks multiplicatively with #1.

**#3 — `appraise` per-row INSERT + per-row event append in the source loop** `[impact: low-med] [safety: behaviour-preserving]` → **ADOPT (WP10b)**
appraise.py:236 loops appraisable sources issuing one source_appraisal_result.insert() (:242) plus one events.append() (:255 → single event_log.insert(), events.py:57) per row. Appraisal is a deterministic rubric lookup (DEFAULT_RUBRIC[evidence_type], :238) — no LLM, no inter-row dependency → textbook bulk insert (collect dicts, one insert().values([...])). Scales with relevant-source count (tens–low-hundreds). Event rows carry per-project `sequence` uniqueness — LEAVE per-row (do not batch without confirming sequence assignment is batch-safe).

**#4 — `embed_pending_chunks` processes embedding batches serially** `[impact: low] [safety: concurrency-risk]` → **DEFER**
embeddings.py:685 walks all_units in API_BATCH_SIZE=128 slices (embeddings.py:49); texts ARE batched into one API call per slice (good), but slices run serially with a conn.execute(insert…) after each (:734). Batches independent but share conn (not thread-safe); OpenAI embeddings call is fast with its own backoff; a handful of batches at typical corpus sizes. Agent's own call: note, don't rush — not smallest-diff to parallelise safely.

**#5 — Search HTTP calls run serially within a round** `[impact: low-med] [safety: concurrency-risk — agent recommends NOT actioning]` → **DECLINE**
search_loop.py execute_plan (:1407-1474) runs backend × query × filter-variant calls in nested serial loops per round. Independent within a round, BUT they share the early-stop guard (stop_all) and per-episode budget/quota accounting (episode_remaining, _distribute_quota), and rounds are legitimately order-dependent (round ≥2 reformulates from prior-round exemplars, :1417-1436). Parallelising means giving up the early-stop budget guard and juggling shared counters against rate-limited providers. Risk > win; flagged for completeness only.

**#6 — search_live cache deepcopies on get and set** `[impact: low / probably net-zero] [safety: behaviour-preserving]` → **DECLINE (checked and dismissed)**
Hypothesised as hot waste; on inspection it is defensive isolation of a cache HIT (`_search_cache_get` deepcopies out :748; `_search_cache_set` deepcopies in :752). A hit means the HTTP round-trip was skipped — the deepcopy is noise relative to what the cache saved; a json round-trip wouldn't beat deepcopy on these dicts. Leave it.

### Coverage map — checked and ALREADY FINE (do not re-flag)

Fan-outs correctly in place: per-doc extraction + vetter judgment (extract.py:712, :1011, 4-wide); screen stage-1/-2 (screen.py:422 12-wide / :856 4-wide); classify (classify.py:243, 4-wide); select rerank batches (select.py:770 → ranking.py, 4-wide); characterise clustering (max_concurrent_batches=4, characterise.py:599); full-text fetch (ingest_full_text.py:1122).

Correctly SEQUENTIAL BY DESIGN (a parallelisation claim here would be a bug): synthesise section loop + section-turn loop (rolling prior-section claim ledger + per-turn transcript — synthesis_tools.py:2779, build_ledger/ADR 0015); search rounds (round ≥2 reformulates from prior exemplars, search_loop.py:1417); grounding judge (inside the sequential section flow).

DB patterns fine: hot-filter indexes exist (ix_ssr_scope_status, ix_scr_scope_type, ix_sar_scope_score — schema.py:302/360/404; ix_iof_record/ix_icf_record :773/825); anti-join exists() prefix-covered by uq_chunk_embedding_unit (schema.py:476) and uq_chunk_snapshot_sequence (:196); one transaction per component via engine.begin() (runner.py, orchestrate.py) — no per-row commits; _failed_embedding_count is set-based (characterise.py:411-433); extract/screen/embeddings writers already bulk-insert; acquire dedup preload is one query, JSONB ->> scan acknowledged + bounded at v3.0 sizes (acquire.py:694-718).

Redundant work / startup fine: all re.compile at module level (embeddings.py:56, synthesis_tools.py:448, search_live.py:104, …); embeddings batched at 128/call; no repeated table reflection or per-iteration client construction on hot paths.

### Lead re-sweep addition (2026-07-14, owner-requested second pass)

**#7 — Pure-Python cosine on the retrieval hot path** `[impact: med, unmeasured] [safety: observable-change (numeric precision only)]` → **ADOPT (WP10c)**
`_cosine` (synthesis_tools.py:1228-1238) hand-rolls the dot product over 1536-dim vectors with a per-element Python loop + `zip(strict=True)`, recomputing BOTH norms per pair — and `ChunkRetriever.search()` (:1327-1330) runs it against every filtered unit in the pool on every `search_chunks` call from the synthesis writer (multiple calls per section turn; pool = full screened-corpus unit set, CANDIDATE_POOL_PER_LEG=200 caps the *output*, not the scoring). At hundreds–thousands of units this is plausibly tens of seconds of interpreter arithmetic per run. Fix (stdlib, zero deps — repo requires-python ≥3.12): `math.sumprod` for the dot product (C speed, verified available) + precompute unit norms once in `__init__` (vectors are frozen for the retriever's lifetime — the class already does exactly this for lexical tokens, :1293-1297) + query norm once per search. Same formula, ~50-100× on the arithmetic. Precision caveat named: sumprod accumulates in extended precision → last-ulp score differences could reorder a near-tie (ties themselves are already unit_id-stabilised, _ranked_pool :1245) — hence observable-change class, not output-identical.

Lead pass also checked and cleared (beyond the agent's coverage map): quote_verify span search (C-speed str.find + occurrence cache, quote_verify.py:292 — no scan problem), lexical leg (tokens precomputed once), _ranked_pool full-sort-vs-heapq (negligible next to cosine).

### Lane 7 adjudication summary
ADOPT #2 (WP10a, one line) + #3 (WP10b, bulk appraisal insert; events stay per-row) + #7 (WP10c, sumprod cosine + precomputed norms). DEFER #1 (five-facet fan-out — conn-hoisting design note recorded; eval-slice candidate) + #4 (embeddings slices). DECLINE #5 + #6 with the agent's own reasons. WP10 items are output-identical or numerically-equivalent, not timing-identical — named in the contract as the one explicit exception to the behaviour-preservation fence.

# LEAD ADJUDICATION (all lanes in)

## Slice backlog — 023-codebase-health (behaviour-preserving), in land-order
1. **Test pre-hardening:** object-form the 11 string-path sites (3 files); add 4 country-filter fail-closed matrix rows; add OpenAISearchGenerationBackend wire test. (Lane 4)
2. **embeddings.py split:** client helpers → infra/openai_client.py; usage_metadata/log_usage → usage.py; kill grouping.py:226 _log_usage dup. (Lane 2 headline — BEFORE bucketing)
3. **Dead-code cuts** (~830 lines, lane 1 unconditional list; fan-out 4×-consolidation LAST or deferred — subtle per-site diffs).
4. **Renames:** the IOF/ICF symmetry set (iof_records/icf_records, iof_prompt/icf_prompt, merged finding_vetter) + grouping→theme_grouping, plan→run_spec (+test_compile→test_run_spec), ingest→ingest_upload; move select_document_fetcher skeleton→fetch_live; repoint its single test importer; fix extraction_backend stale docstring.
5. **Capability-aware regroup** (FINAL owner-amended structure: runtime/ evidence_base/{sourcing,screen,corpus,extract,group,synthesis} core/; no tools/ bucket — search stays in evidence_base/sourcing, seam recorded in deferred.md; update the 2 importlib.resources anchors + disk-path guard).
6. **Docs:** README full rewrite; AGENTS.md prompt-pin corrections (v5/v7/v2/v7) + Current phase; readiness.md 022 line. (Lane 3)
7. **Optional riders (cheap):** docstring Args: on the 19-site backend-protocol cluster; prune [tool.pyright].
8. **Separable phase 2 (test consolidation, ~600–750 lines):** top-2 wins first (fake parse-client stack, scripted synthesis backends).

## Owner decisions — ADJUDICATED (owner, 2026-07-14)
- **v6 prompt lane (~240 lines): KEEP** through eval slice (frozen cost baseline); delete in first post-eval cleanup.
- **echo component chain (~70): CUT** — full-chain skeleton smoke covers dispatch; repoint test_harness/test_compile at a real component.
- **ChunkReranker Protocol (~25): KEEP** — documented Bedrock seam; dies at Bedrock if still unused.
- **skeleton.py: RETIRED IN-SLICE** (owner, 2026-07-14, REVERSING the same-day "stays" ruling on new evidence: 019–021 never ran the stub skeleton smoke; 022's skeleton use was the LIVE e2e which could run through orchestrate; tests/test_runner.py:318 test_full_stub_chain already covers the full stub chain in make verify; skeleton's only importers = one test (fetcher, moving anyway) + the pyproject script). Delete module (~1,290 lines) after the fetcher move; remove policy-atlas-skeleton console script (approved public-interface removal). **orchestrate = the standardised smoke + live-check vehicle from 023 on** (no-key stub mode → deterministic stubs + harness default fixture backends; injectable ConsoleIO for scripted drives). Corollary: src/policy_atlas/data/ STAYS in the package — orchestrate's stub mode consumes it in production (harness.py:609-614 default fixture backends); it is not test data.
- **Dependency edits: ALL THREE APPROVED** — declare lxml+pymupdf direct; raise floors to locked majors (langgraph>=1 sharpest); prune [tool.pyright] (owner confirmed: not used even ad hoc; NOT integrating pyright — mypy strict in CI is the single gate, Pylance works off .vscode interpreter setting without the block).
- **search_live TTL+LRU cache (~55): KEEP** (tested, may save egress across multi-question projects).
- **leg_directive identity fn: KEEP** until c4-demo lane closes; delete with C4 close-out.

## Not doing (recorded)
- Exception-hierarchy standardisation (lane 6): consistent in use; redesign = churn without payoff.
- Perf work: eval slice measures cost properly.
- Whole-repo security pass: deferred to Bedrock task.
- ~~Test-dir bucket mirroring~~ — REVERSED by owner 2026-07-14: tests mirror the new tree in-slice (WP5; tests/ is a package with absolute helper imports, so the move is cheap and avoids a second churn wave).

Lane spend: ~462K subagent tokens total (deep-reasoner 159K, test-engineer 72K, fast-workers 230K) — within review-stack economy envelopes.

## Lane 5 — deps + hygiene (COMPLETE, 12 findings, mostly minor)

**Actionable (needs owner approval — dependency-file edits are gated per AGENTS.md):**
1. **Undeclared direct imports on transitive deps:** ingest_full_text.py:41-42 imports `lxml.html` + `pymupdf` directly; scripts/record_fulltext_fixtures.py:21 imports `fitz`. Neither lxml nor pymupdf declared in pyproject (ride in via trafilatura / pymupdf4llm). Fix: declare both as direct deps.
2. **Stale version floors vs locked reality:** langgraph>=0.2 (locked 1.2.6 — a clean re-resolve could land pre-1.0!), trafilatura>=1.12 (locked 2.1.0), structlog>=24 (locked 26.1.0), mypy>=1.10 (locked 2.1.0), pytest>=8 (locked 9.1.1). Fix: raise floors to locked majors. pymupdf4llm <1 ceiling is DELIBERATE (commented, contract decision 5) — leave.
3. **Orphaned config:** [tool.pyright] in pyproject has no consumer (not in Makefile/CI/vscode/cursor). Prune or wire.

**Informational (no action):**
- 0 unused declared deps (all verified by AST import scan); psycopg invisible to import-grep by design (dialect string).
- Licences: all compatible with AGPL-3.0. Notable: psycopg LGPL-3.0 (one-directional OK), pymupdf4llm + pymupdf AGPL/Artifex dual (AGPL horn compatible — and a reason the repo's own AGPL licence is load-bearing).
- Tracked-file hygiene: clean. No junk/artefacts tracked, dist/ and demo/ untracked, .gitignore complete. Large tracked files = tests/data/fulltext PDFs (5MB max) — sanctioned per amended fixtures policy; location outside src/policy_atlas/data/ is a visibility note only.
- Tool config: single source of truth (pyproject only), CI = make verify. No drift.
## Lane 6 — conventions (COMPLETE — near-clean; AST-verified, not eyeballed)

- **Docstrings: 0 missing outright** (346 substantive public defs). 26 have params but no Args: section — 19 of those are one cluster: fixture/live backend classes in acquire.py (:227-308) + search_live.py (:554-570) implementing the SearchBackend protocol with terse one-liners. Judgment call: protocol impls with self-evident signatures — arguably fine as-is, or fix the cluster in one sweep. 7 one-off stragglers.
- **Logging: zero deviations.** `log = structlog.get_logger()` uniform across 23 modules; no stdlib logging anywhere; print() confined to orchestrate.py's ConsoleIO interactive seam (correct separation). traced_call/component_span consistent across backend tier.
- **Exceptions: consistent use, unstandardised design.** Per-module custom exceptions used pervasively and correctly; deliberate split (RuntimeError = transport/parse, custom types = content validation) holds codebase-wide. Two nits: InvalidDiscoveryOutput defined TWICE (clustering_engine.py:116 + grouping.py:110 — lane 1's validate_themes delete removes the dup); base classes vary (Exception vs ValueError, select.py unique two-tier) with no shared base. Standardising = low value, skip unless a slice touches them anyway.
- **Type hints: 100% on public surfaces. PEP8 naming mechanics: 0 violations.**
