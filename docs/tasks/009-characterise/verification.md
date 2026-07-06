# Verification: 009-characterise

Evidence for the characterise slice (EB shallow terminus + both egress fronts +
the Langfuse trace baseline). Build sections filled at step 6; **Review findings** +
**Rubric status** to be added by the step-7 review stack (fresh conversation).

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make test` | pass | 261 passed (207 pre-Phase-5 + 54 in `test_embeddings.py` (20) / `test_characterise.py` (34)); stub backends throughout — deterministic, zero egress. 267 after the step-7 review fixes (+6 guard tests) |
| `make typecheck` | pass | mypy strict, 37 source files |
| `make lint` | pass | ruff |
| `make build` | pass | sdist + wheel |
| `make okf-validate` | pass | 21 concepts, 0 violations (three spec flow-backs this slice) |
| migration roundtrip | pass | `alembic upgrade head` → `downgrade -1` → `upgrade head` clean, twice (revision `b3c7e5a9d2f4`); table count 16 → **19** (verified via inspector); `open_tags` + `ck_scr_open_tags_array` gone; downgrade restores them with `'[]'::jsonb` default |

Composite-FK note (plan Task 1): all three referenced composite uniques
(`uq_evidence_scope_id_project`, `uq_runs_run_project`, `uq_pss_id_project`) pre-existed
from the screening-result precedent — no new unique constraints were needed.

## Checks beyond the build

All suite checks are deterministic (stub embedder + stub grouper; misbehaving doubles for
the repair paths). Named results:

- **Zero-egress / socket-deny** — `test_judgment_socket_deny_characterise_harness_round_trip`:
  a full characterise harness round-trip with `socket.socket` patched to raise completes
  green (scoped after the DB connection, 008 pattern). `test_judgment_tracing_noop_without_keys`:
  no `LANGFUSE_*` keys → `get_langfuse()` is `None`; span/score/flush helpers no-op.
- **Key hygiene** — `test_judgment_openai_key_hygiene`: a canary `OPENAI_API_KEY` never
  appears in any `event_log` payload or captured log output;
  `test_openai_embedding_backend_requires_api_key`: live backends without a key fail
  loudly at construction. Live-run audit below extends this to the real keys.
- **Counting invariants** — grouping: `screened_in == grouped + unclustered` asserted on
  the happy path, edge scopes and the harness round-trip; embed:
  `embedded + failed == pending_at_start` via
  `test_embed_pending_chunks_idempotent_and_stamps_every_row` and
  `test_embed_pending_chunks_failure_isolation_and_retry`.
- **Idempotency** — second embed pass all `already_embedded` (anti-join); second
  characterise run → new characterisation row, tags accreted not duplicated
  (`test_judgment`-suffixed re-run tests + `uq_char_scope_run` constraint test).
- **Eager-uniform** — `test_eager_uniform_upload_and_acquire_embed_every_chunk`: every
  chunk of every snapshot class carries rows for the active profile after ingestion.
- **Unit derivation** — deterministic and gap-free
  (`test_judgment_derive_units_deterministic_and_gap_free`); in-budget chunk → one unit;
  oversized → sentence-boundary units with ~200-char overlap and offsets back into the
  untouched canonical chunk; `test_judgment_one_vector_per_unit_no_mean_pooling_path`:
  every stored vector equals the stub embedding of exactly its unit text — no pooled
  vector representable.
- **Validation/repair by case** (decision 4) — invented ids dropped in code with **no**
  repair call (call-count asserted); missing ∪ unknown-theme ids form the residue and the
  **one** targeted repair call receives exactly those ids with first-round valid
  assignments kept; repair exhaustion → honest `CharacteriseFailure` carrying the full
  coverage dict, nothing persisted, no placeholder theme anywhere; invalid discovery
  retried exactly once; duplicate-same-theme collapsed at the OpenAI seam in code.
- **Call budget** — the counting double's total calls equal the enforced maximum
  `(1+1) + ceil(n/40) × (1+1)`; `_CallBudget` raises on over-reserve.
- **Injection posture** — injection-shaped abstract flows through as inert data (no
  "PWNED" theme; raw text in no theme name/description); instruction-shaped-but-valid
  theme name stored and rendered as data; prompt-structure test proves corpus text enters
  prompts only as id-keyed JSON data records and never reaches the system prompts.
- **Coverage honesty** — distributions match hand-computed values over a seeded corpus;
  every distribution carries `base: "screened"` with the base ladder
  (screened_in/not_relevant/screen_failed/unscreened) alongside; coverage payload has
  exactly `{base, base_counts, distributions, rates}` — **no absence-claim field**
  (test-asserted); tag distributions keyed `(tag_type, asserted_by)` with provenance
  classes never merged; provider materialisation fixture-tested over mixed Overton
  string/list shapes; `llm_document_theme` lands only under `overton_llm`; uploads get no
  provider tags; `provider_fields` untouched.
- **Determinism evidence** — `test_stub_runs_byte_identical`: two stub characterise runs
  over the same corpus produce byte-identical `(coverage, themes, grouping_provenance)`
  (JSON, sorted keys).

## End-to-end command

```
set -a; source .env; set +a   # OPENAI_API_KEY + LANGFUSE_PUBLIC_KEY/SECRET_KEY/HOST + DATABASE_URL
uv run python -m policy_atlas.skeleton
```

## Live-run evidence (manual check, 2026-07-06)

Skeleton end-to-end against the fixture corpus with real keys: `skeleton.backends
mode=live traced=True`; exit 0; `characterisation_row present=True`.

- **Embeddings (live `text-embedding-3-small`)**: upload 2 units · acquire envelopes
  `{embedded: 24, units: 24}` · full-text
  `{embedded: 490 chunks, units_embedded: 1013, failed: 0, budget_exceeded: 0}`;
  10 embeddings API calls (128-text batches); `failed_embedding_share=0.0` in the
  landscape rates.
- **Grouping (two-stage, live)**: n=25 → budget `baseline=2, maximum=4` logged before any
  call; discovery one call (6,289 tokens), **no retry**; assignment one batch (8,777
  tokens), **25/25 assigned, no repair** (`flags=[]`, `repair_calls_used=0`);
  `unclustered {count: 0, share: 0.0}` — invariant holds:
  25 screened-in == 25 grouped (1+4+4+8+8) + 0 unclustered.
- **Landscape summary as rendered** (sanitized fixture corpus — the "themes" reflect its
  random-word vocabulary, which is the machinery-correctness bar, not a quality claim):
  - `Landscape and place motifs (meadow, prairie, harbor, tundra, glacier)` — size 1
  - `Materials and construction terms (timber, marble, onyx, quartz, pewter)` — size 4
  - `Color and decorative vocabulary (saffron, cobalt, velvet, pigment, orchid)` — size 4
  - `Ornamental and motif tokens (sonnet, quill, mosaic, tapestry, zephyr, lantern)` — size 8
  - `Synthetic/test documents and long generated token lists` — size 8
  - Coverage rendered with bases: origin `{acquired: 24, uploaded: 1}`, backend
    `{openalex: 12, overton: 12, unknown: 1}`, text_basis `{full_text: 11,
    abstract_only: 14}`, evidence types (24 Unknown — stub-classification reality,
    honestly shown), rates `{full_text_coverage: 0.4, unknown_classification_share: 0.96,
    failed_embedding_share: 0.0}`, tag layer `{topic_theme/openalex: 43,
    topic_theme/overton: 311, topic_theme/overton_llm: 12}` — classes separate.
- **Dev-instance trace (user-operated Langfuse)**: `run:{run_id}` traces present for the
  live runs; the characterise run trace carries the component span, the `discover`
  generation (model, prompt_version `characterise_grouping_v1`, token usage, full I/O)
  and scores (`unclustered_share`, `grouping_repair_taken`) attached in-span (0 context
  errors after the score-placement fix). The full-text run trace carries the 10 embed
  batch observations. **Known wart**: the first `assign` call surfaces as a detached
  trace — OTel context does not propagate into the `ThreadPoolExecutor` worker that runs
  concurrent assignment batches. Recorded under the Langfuse observability seam
  (docs/deferred.md at step 8); span content itself is complete.
- **Honest cost note**: successful run ≈ 0.5M embedding tokens (~$0.01) + ~15K gpt-5-mini
  tokens (<$0.03). Including the first (failed) live run and the assignment-model
  diagnostics, total live spend for the slice ≈ $0.10.
- **Key hygiene (live)**: the three real key values substring-audited against the full
  captured run output — all absent.

### Live-check failure that shaped the build (honest record)

The **first** live run failed honestly: `gpt-5-nano` (the plan-pinned assignment model)
returned a schema-valid but **empty** assignments list for the realistic 25-doc batch —
16.5K reasoning tokens, `finish_reason=stop`, `{"assignments":[]}` — on both the first
call and the targeted repair, so characterise emitted `component.failed` with coverage in
the payload and persisted nothing (decision 11 working as designed). Reproduced
standalone; nano remained unreliable at every reasoning effort (11/25 at minimal;
invented/duplicate ids at low) while `gpt-5-mini` assigned 25/25 cleanly. **Deviation
(flagged)**: `ASSIGNMENT_MODEL` flipped `gpt-5-nano` → `gpt-5-mini`. The exact pin was
plan-gate detail ("gpt-5-nano-class … exact pins at the plan gate"); the two-stage
design, budget arithmetic and validation/repair machinery are unchanged and demonstrably
converge on the live corpus with the corrected pin — this is not the contract's
"machinery cannot converge" stop condition.

## Diff summary

Five commits on `task/009-characterise` (one per plan phase + flow-backs):

1. **Phase 1** — three tables (`chunk_embedding` unit-grain JSONB vectors ·
   `characterisation_result` run-local, composite-FK-guarded · `source_tag` single tag
   home with assertion provenance) + `open_tags` retirement with full reader/writer/test
   cleanup; `openai`/`langfuse` deps; SDK surfaces verified (scratch note).
2. **Phase 2** — `embeddings.py` (seam, unit policy, project-scoped anti-join embed pass,
   budget guard, failure isolation) + eager-uniform wiring into all three ingestion paths
   + provider-tag materialisation in acquire.
3. **Phase 3** — lead-authored `characterise_grouping_v1` prompt pair; `GroupingBackend`
   seam (live strict-structured two-stage + deterministic stub); `characterise.py`
   (coverage → budget-enforced grouping → validation/repair → tags → row → summary).
4. **Phase 4** — `tracing.py` (env-guarded Langfuse, full-I/O spans, scores, no-op
   without keys); registry/harness (`_run_characterise` with coverage-carrying failure
   payload; `embedding_backend`/`grouping_backend` params defaulting to stubs)/skeleton
   wiring; protocols' `mode` made a read-only property.
5. **Phase 5** — 54 tests (contract bulk + judgment cases). Plus the spec flow-backs
   commit (components §5 ×2, §4 embed seam, data-model tag provenance, log.md).

**Deviations, all flagged** (minor, within the contract's own vocabulary):
- `ASSIGNMENT_MODEL` `gpt-5-nano` → `gpt-5-mini` on live evidence (above).
- `tests/helpers.py` delete-order update pulled forward from Task 8 into Phase 2
  (acquire/ingest write the new tables from Phase 2 on; Phase 2's gate needed it).
- Lead threaded `embedder=state["embedding_backend"]` through the harness
  acquire/ingest_full_text partials (without it a live embedder handed to `run_harness`
  would silently stub the embed passes — wiring gap found in review of Task 8 output).
- Skeleton scores moved inside the characterise component span (scores were silently
  skipped outside any active OTel context — caught by the first live run).
- Upload-ingest embed counts go to a structured log line (`ingest_upload.embed_counts`)
  rather than a component payload — pre-agreed contract wording alignment (plan finding 3).

## Intent & assumptions

- The live check's bar is machinery correctness (bounded calls, validation, honest
  counts, provenance, traces) — theme *quality* on a sanitized random-word fixture corpus
  is meaningless by construction and belongs to the grouping-quality eval seam.
- Grouping memberships are run-local; only theme labels persist (as provenance-stamped
  tags). Re-runs may group differently — `grouping_provenance` makes each attributable.

## Known unverified items

- Live behaviour at n ≫ batch (concurrent multi-batch waves, rate-limit backoff under
  real 429s) — fixture corpus is single-batch; the concurrency path is exercised with
  stub/double backends only.
- Langfuse span nesting for **concurrent** assign calls (the detached-trace wart above).
- Bedrock routes, pgvector/retrieval, and everything in Out of scope — deferred seams.

## Public safety

- No credentials in code, logs, events, or this file (test-asserted + live substring
  audit). `.env` untouched and gitignored.
- The live run sent only openly-licensed/sanitized fixture text (008's licence guard) to
  OpenAI and the user-operated Langfuse dev instance — committable content only.
- Theme names quoted above derive from the sanitized fixture vocabulary — public-safe.

## Deferred work

Per the plan, `docs/deferred.md` entries (EB artefact composition · very-large-corpus
grouping · grouping-quality + adversarial-content evals · TopicGPT refinement +
quotation-verified assignment · contextual retrieval/late chunking/exact-token budgeting ·
steer-point pause · dual-view coverage · pgvector/retrieval · Bedrock swaps ·
provider-signal prompt enrichment · `group`-seam v2 lessons · tag namespace consolidation ·
Langfuse follow-ons incl. the thread-context span-nesting wart · upload audit-event seam ·
`open_tags` entry revisions · class-1 vectorisation entry discharge) land at **step 8**,
after the review stack finalises the code.

## Review findings (step 7, 2026-07-06 — fresh conversation)

Tier-3 stack as specified: **contract verifier** (pinned Opus, read-only) ·
**security lane** (security-auditor subagent) · **heterogeneous pair** = Codex
adversarial (read-only rescue brief) + `/code-review medium` (8 scoped finder angles →
per-file 3-state verify). `make verify` green before and after. Diff scoped
`':!uv.lock' ':!docs/tasks'` throughout.

**Convergent across families (high-confidence):**
- **Langfuse host default** (security MEDIUM + Codex HIGH, found independently):
  keys-without-host silently exported full-I/O traces to the SDK's SaaS cloud default.
  **Adopted**: `get_langfuse()` now requires a host (`LANGFUSE_BASE_URL`/`LANGFUSE_HOST`)
  when keys are set and raises loudly on partial config (tracing.py; test-asserted).
- **Stale `.env.example` model comment** (security note + contract-verifier minor):
  still documented `gpt-5-nano` assignment. **Adopted**: comment fixed.

**Unique-to-one-lane adoptions (each justifies its lane):**
- *Codex*: embed anti-join race — plain INSERT loses to a concurrent pass on the unit
  unique constraint → bulk `ON CONFLICT DO NOTHING` per API batch (also batches the
  per-chunk inserts the efficiency finder flagged). Whitespace-only units inside long
  padding were embedded → dropped and renumbered in `derive_units` (offset anchors
  test-asserted). Budget-vs-SDK-retry semantics documented at the client seam
  (logical budget × (1+max_retries) HTTP ceiling — comment, no behaviour change).
- *Security lane*: `unclustered` theme-name/sentinel collision → rejected in
  `validate_themes`; provider tags unbounded → `_normalize_tag` caps length (200),
  rejects control chars (shared `tags.has_control_character`), 50-tag/record cap;
  dependency pins tightened to what the live check ran (`openai>=2.44,<3`,
  `langfuse>=4.13,<5` — the first `<2` attempt was wrong, the lock ran openai 2.44);
  `str(exc)`-into-events constraint comment in harness.
- */code-review* line-by-line + verify: whitespace-only chunks were re-marked `failed`
  every pass forever → now a `skipped_no_units` count, never `failed`; both
  `embed_pending_chunks` paths return one key set (shape divergence refuted as a crash,
  fixed as cleanup). Skeleton score-summary read the *oldest* characterise event
  (ascending log + `next()`) → newest-first with a `run_id` pin — the multi-run
  scenario is already a tested reality.
- */code-review* cleanup angles: `_pending_chunks` hydrated the full backlog before the
  budget check → cheap COUNT guard first; hand-built `_AssignmentValidation` branch
  proved byte-identical to `_validate_assignments(batch, {})` → deleted; `source_tag`
  writes consolidated into `tags.insert_source_tags` + `schema.TOPIC_THEME` (kills the
  acquire/characterise near-verbatim duplication, the 3× `topic_theme` literal, and the
  per-record insert round-trips in one move); OpenAI key/client resolution shared
  (`embeddings.resolve_openai_client`) so key policy lives in one place.

**Declined, with reasons:**
- Multi-scope "unscreened" conflation (finder CONFIRMED): correct semantics —
  screening screens *all project sources against a scope* (screen.py contract), so a
  source screened only under scope B is honestly unscreened for scope A. Noted: no
  two-scope test exists; grouped with the eval seam.
- Embed pass runs after an inadequate acquire verdict: flag-not-block posture —
  acquired chunks are real and the pass is idempotent.
- Second explicit live flag (security note): user reversed exactly this at contract
  rev 6.1 ("egress is the product").
- Zero-support discovered themes persist with `size: 0` (Codex HIGH): honest counts,
  no document misattributed — theme *quality* pruning belongs to the grouping-quality
  eval seam (deferred). Not the rubric's "placeholder theme" (that bans absorbing
  docs into an invented bucket, which repair exhaustion already prevents).
- Conflicted-assignment ids counted as missing in repair telemetry: the backend logs
  `assign_conflicting_duplicates` with counts; repair handles the ids correctly.
- Unified OpenAI call-telemetry shape: false economy — embeddings and chat usage are
  structurally different objects.
- `mode`-protocol base class, stub-default triplication, traced-counter dedup: below
  the abstraction-payback line (2–6 line idioms).
- Batch failure blast radius (one bad unit fails all chunks sharing the API batch):
  transient over-reporting only — failed chunks re-embed next pass; retry/backoff
  granularity is the recorded live-robustness seam (deferred.md at step 8, with the
  `_provider_tags`/`_MAPPERS` dual-dispatch note for a third backend).

**Already recorded:** detached first-`assign` trace (ThreadPool context propagation) —
verify pass confirmed code matches the recorded wart exactly; stays under the Langfuse
seam. Contract-verifier notes: decision-12 invariant wording imprecise in the contract
(code/tests/verification are correct; historical doc, untouched); `deferred.md`
`open_tags` lines contradict the shipped migration (step-8 revision, already
scheduled); commit 982e19e (specs fidelity restoration, separately logged) rides in
this branch and inflates the review diff — scope it out when reading the PR.

**`/simplify` lane:** skipped with justification (per the review-phase rule): the
`/code-review` run already carried dedicated reuse/simplification/efficiency/altitude
finder angles and their adopted fixes are applied above — a separate same-family
cleanup pass would re-read the same diff for the same lenses.

**Fake-done check:** no tests deleted/relaxed; fixes added 6 tests (sentinel, host
guard, tag bounds, skipped-not-failed, uniform shape, whitespace units); all suite
changes are additive; `make verify` re-run green after fixes.

**Lane economics (honest):** reasoning-class ≈ 263K (contract-verifier 162K,
security 81K, Codex wrapper 20K) — at the ≤250K target. Fast-worker ≈ 886K
(8 finders 620K + 5 batched verifiers 266K) vs the ≤500K target — the per-angle
pathspecs were applied but this diff's product-code share is large; verifiers were
batched per-file (5 agents for 24 candidates) to cut the overrun. Note for the next
retro: on a ~5K-line product-code diff, 8 angles × full lens scope is the dominant
cost; consider 6 angles or shared-context finder pairs.

## Rubric status (step 7)

| # | Item | Status |
|---|---|---|
| 1 | Contract's 13 decisions | ✅ verified by contract-verifier lane (evidence per decision) |
| 2 | `make verify` green + zero-egress + live check | ✅ suite independently re-run by verifier; live evidence documented above (not re-runnable without keys) |
| 3 | No unapproved gated change | ✅ exactly the four approved changes |
| 4 | No secrets committed; key hygiene test-asserted | ✅ (canary + live substring audit) |
| 5 | No tests deleted/weakened | ✅ net +60 tests after review fixes |
| 6 | Verification evidence recorded | ✅ |
| 7 | Deferred seams listed / class-1 discharge | ⏳ step 8 (this PR); in-tree `open_tags` contradiction noted above |
| 8 | Spec flow-backs + log.md | ✅ verified in diff (commit 9e98800) |
| 9 | Honesty properties | ✅ verified in code, incl. in-code invariant (characterise.py:836) — strengthened by the sentinel + skipped-not-failed fixes |
| 10 | ADR 0005 Accepted; prompts co-versioned | ✅ |
| 11 | Tier-3 review stack + adjudication | ✅ this section |
