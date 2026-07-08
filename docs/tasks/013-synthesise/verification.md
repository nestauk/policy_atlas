# Verification: 013-synthesise

Evidence for the synthesise slice (EB component 9, the terminus; the repo's
first agent loop). Public-safe — no secrets, no raw source text, no unredacted
traces. Filled at step 6; **Review findings** + **Rubric status** follow the
review stack (step 7).

> **Status: step 7 complete (2026-07-08).** `make verify` fully green at the
> step-6 exit and again after the review-stack fixes (629 tests); four-profile
> live check recorded below. Review findings + rubric status recorded in
> § Review findings.

## Commands run

Step-6 exit (`make verify`, 2026-07-08):

| Command | Result | Notes |
|---|---:|---|
| `make okf-validate` | pass | |
| `make test` | pass | **620 passed**, 0 failed (full suite incl. the ingest integration tests) |
| `make typecheck` | pass | mypy, 72 source files, no issues |
| `make lint` | pass | ruff, all checks passed |
| `make build` | pass | sdist + wheel built |

Socket-deny: `test_socket_deny_synthesise_harness_round_trip` (judgment
suite) covers the synthesise harness round-trip with `socket.socket` denied —
zero egress on the suite path; the pre-existing select/extract socket-deny
tests stay green alongside.

Migration roundtrip: **clean on both DBs** (dev and test): 24 → 25 → 24 → 25
tables (`alembic downgrade -1` / `upgrade head`, table counts asserted;
phase 1 commit 98bc672).

## Checks beyond the build

- **Deterministic tests** — the contract's named-test list is covered across:
  - `tests/test_synthesis_prompts.py` — negative rules asserted on the three
    built prompt surfaces (verdict-section prohibition, descriptive posture,
    verbatim-quote rule, absence discipline, ledger context-never-evidence,
    strict routing, topical-relevance ≠ support, closed tool set + emission
    schema, loop-free reword-down repair message).
  - `tests/test_synthesis_tools.py` — directive parser (fail-closed grammar,
    clamp-not-reject weights, forbidden titles, group-ids-without-grouping
    malformed), staged retrieval (deterministic ranking, lexical reachability,
    selection prior reorders-never-excludes, boost never surfaces
    zero-relevance, unmatched_boosts, reranker seam exercised by a fake,
    top-k + tie-break determinism, `RETRIEVAL_UNIT_CAP` error names the cap),
    tools factory (substrate availability, char budget tail-drop),
    loop runner (voluntary emission, cap-forced emission, ≤ cap−1 tool turns,
    unknown tool rejected-never-executed, multi-call rejection, forced-emit
    protocol violations raise), `gathered_ids`.
  - `tests/test_synthesis_backend.py` — stub proposal/turn/emission semantics,
    scripted turns through the real runner, verbatim chunk quotes +
    fabrication sentinel, reword-down repair, judge verdict routing,
    traced_call paths.
  - `tests/test_synthesise_pure.py` — per-type validators (every reject reason
    reachable), artefact title bounds, budget formula, ledger marker.
  - `tests/test_synthesise_core.py` — zero substrate → structural failure (no
    artefact, no roll-up), characterisation-only end-to-end, chunk substrate
    with verified citations + `unselected_screened` origin, explicit-shallower
    reference mismatch → structural failure, fabricated quote excluded +
    counted + never persisted anywhere, same-run re-execution loud, backend
    failure → no roll-up row, uploaded full-text doc feeds the chunk lane.
  - `tests/test_synthesise.py` — contract-bulk suite (transitive resolution,
    directive paths, determinism, boundary-spanning citation rows, judge
    persistence keys, provenance required keys, delete-order …).
  - `tests/test_synthesise_judgment.py` — judgment suite (caps bind, unknown
    tool, sibling-repair guard, injection doubles, scope guards, ledger
    citability, socket-deny, judge coverage).
  - `tests/test_compile.py` / `tests/test_harness.py` — registry entry, the
    grouping_run_id Plan→Config round-trip (plan review M2 guard), the
    `_run_synthesise` node end-to-end.
- **AI evals** — none in this slice by design: judge calibration, section/
  prose/retrieval quality are the eval workstream's (recorded as the
  recommended next slice in `docs/deferred.md` § Synthesise).
- **Manual** — the four-profile live check (below) + the stub-mode skeleton
  driven end-to-end during the build.

## End-to-end command

Stub mode (deterministic, zero egress; drives the full chain and all four
synthesise profiles):

```bash
DATABASE_URL="postgresql+psycopg://policy_atlas:policy_atlas@localhost:5432/policy_atlas" \
OPENAI_API_KEY= LANGFUSE_PUBLIC_KEY= LANGFUSE_SECRET_KEY= LANGFUSE_HOST= LANGFUSE_BASE_URL= \
uv run policy-atlas-skeleton
```

Live mode (the contract's manual check; keys from the operator's `.env` via
the app's own dotenv path — the wrapper only sets a default `DATABASE_URL`):

```bash
uv run python - <<'EOF'
import os
from dotenv import load_dotenv
load_dotenv("/Users/shabeer.rauf/repos/policy_atlas/.env")
os.environ.setdefault("DATABASE_URL",
    "postgresql+psycopg://policy_atlas:policy_atlas@localhost:5432/policy_atlas")
from policy_atlas.skeleton import main
main()
EOF
```

(Run as a file, not stdin — the full-text parse workers use multiprocessing
spawn and must re-import a real `__main__` path.)

## Live-run evidence (four substrate profiles, 2026-07-08)

The full skeleton chain live (`mode=live`, `traced=True` — full-I/O traces on
the user-operated dev Langfuse; `llm_rerank_v1` selection), then the four
synthesise profiles over the same scope. All four completed; every profile's
roll-up row persisted with the full provenance key set.

| Profile | Sections | Claims (by type) | Citations verified | Citations from unselected | Verdict lanes | Flags |
|---|---:|---|---:|---:|---|---|
| rapid (no refs) | 8 | chunk 8 · gap 7 · reasoning 7 | 8 | 8 (no selection referenced — all `unselected_screened`, honestly) | tier_1 ×8, tier_4 ×7 | uncited_sections, repair_path_taken |
| characterisation_only | 6 | chunk 5 · theme 3 · pattern 7 · gap 5 · reasoning 4 | 5 | 5 | tier_1 ×5, tier_4 ×4 | uncited_sections, repair_path_taken |
| characterisation + selection (no extract) | 7 | chunk 6 · theme 3 · pattern 3 · gap 3 · reasoning 5 | 6 | 0 — but see the confound note below: NOT usable as steering evidence | tier_1 ×6, tier_4 ×5 | uncited_sections, repair_path_taken |
| full_chain (grouping ref; transitive resolution) | 6 | chunk 4 · theme 2 · pattern 6 · gap 7 · reasoning 4 | 4 | 0 | tier_1 ×4, tier_4 ×4 | uncited_sections, repair_path_taken |

Honest notes (two corrected 2026-07-08 after post-run interrogation — the
first write-up of both was wrong/overstated):
- **finding claims are 0 on the full chain — CORRECTED: findings DID exist.**
  The live extraction extracted **179 findings from 9/10 docs** (mode `live`;
  the earlier "no findings existed" note conflated a stub-mode run's
  `no_findings ×10` with the live run). Two compounding causes: (a) the
  referenced **intervention-facet grouping produced 0 groups** — 96 distinct
  values, all 179 findings ungrouped through the repair (the same-project
  outcome-facet run produced 13 groups; the demo passes the first grouping
  run) — so every section seed's member-finding set was empty and finding
  citability flowed only through `query_findings` returns (the rev 8 M6
  path); (b) the writer called `query_findings` in 3 of 6 sections and
  received records, but emitted chunk/pattern/gap claims instead of
  finding-type claims — prompt-adherence/emphasis behaviour, not a gate (the
  type was available; nothing rejected). (a) is a 012-lane anomaly flagged
  for the review stack (012's live check grouped 94 values into 16 groups);
  (b) is the synthesis-quality eval seam.
- **The "selection prior visibly steering" reading of the 0
  unselected-origin citations is CONFOUNDED and withdrawn.** On this fixture
  corpus the only citable (appraised, text-bearing) docs are the two uploads,
  and both sat inside the selected set — zero citable-but-unselected docs
  existed, so the M4 citability gate alone fully explains the 0. The
  prior-steers-never-filters property is proven **deterministically** instead
  (`test_retriever_selection_prior_reorders_without_excluding_unselected`);
  isolating live steering needs a corpus with citable docs on both sides of
  the selection — eval-seam territory.
- **The repair path was exercised on every profile** (`repair_path_taken`);
  per-claim salvage caught structurally malformed live emissions (e.g.
  `gap.sparsity` emitted as a float; `citations: null`) — counted into
  `claims_rejected_structural`, logged bounded, never silent, never fatal.
- **Proposal normalisations** fired and were recorded in provenance
  (`group_ids_stripped_no_grouping`, `focus_truncated`) — the rev 8 M5
  clamp-over-reject posture; integrity rules still reject.
- `uncited_sections` flags honestly: some proposed sections (e.g. gap-focused
  ones) carried only gap/reasoning claims.
- The rapid profile's chunk-groundable substrate is the sentinel-classified,
  appraised uploaded review (`syn-002`) — the acquired fixture docs classify
  Unknown under the stub classifier and are never appraised, so their chunks
  are readable but honestly uncitable (the M4 rule, visible per-chunk via
  `appraised`).

**Cost (honest actuals):** the synthesise-bearing live run = 136 generation
calls, ~1.31M prompt + ~0.27M completion tokens at `gpt-5-mini`
(≈ $0.9); the build's full live-check cycle (five runs while three
live-robustness defects were found and fixed) ≈ $3–4 total, plus embedding
calls on `text-embedding-3-small` (negligible). Well inside the plan's
single-digit-dollar budget.

**Key hygiene:** no `sk-` material in any captured log (grep-audited); keys
env-only; traces on the user-operated instance.

## Diff summary

One slice, seven phase commits on `task/013-synthesise`:

1. **Schema (98bc672)** — `synthesis_result` (migration 13, tables 24 → 25):
   run-scoped roll-up, artefact_id NOT NULL, four nullable resolved references
   each composite-FK-guarded against its parent's `(scope, run)` unique;
   `delete_project_data` order; plan/contract approval recorded.
2. **Prompts + seams (8ad858e)** — the three lead-authored prompt surfaces
   (`synthesise_sections_v1`, `synthesise_section_v1` incl. the three tool
   JSON schemas + `emit_claims` emission schema as one versioned unit,
   `grounding_judge_v1`), claim wire models, deterministic message builders,
   `SynthesisBackend`/`GroundingJudgeBackend`/`ChunkRerankerBackend` protocols
   + pass-through reranker.
3. **Tools + loop (cdd8d31)** — fail-closed directive parser, retrieval scope
   + staged `ChunkRetriever` (content-only hybrid → RRF → soft priors →
   reranker seam → caps), the three read-only tools, the bounded loop runner
   (the repo's first agent loop).
4. **Backends + factoring (d54a731)** — OpenAI + stub synthesis/judge
   backends; `tracing.traced_call` factored across all five OpenAI backends
   (the 012-deferred trigger); keyed-Langfuse smoke of the traced path passed.
5. **The component (e414232)** — `synthesise.py`: resolution → mint →
   proposal → serial section loops with the rolling ledger → six per-type
   validators → batched judge → one loop-free reword-down repair → block/
   unit/annotation/citation writes → roll-up last; bespoke `_run_synthesise`
   harness node.
6. **Wiring (3982e0c)** — registry entry, `grouping_run_id` through
   Plan/Config, skeleton four-profile demo, `synthesis_score_summary`.
7. **Build-time fixes (3de72ca, d975ae9)** — see deviations below.
8. **Phase 6 test suites + this document** — final commits.

Data files are excluded from review diffs per the 007 retro.

Build-time live-robustness fixes (commits 467b45e, c4db451, 20ca351 — found
by the live check, each root-caused and regression-covered):

- **Section-proposal group_ids discipline** — with a characterisation present
  the live writer stuffed theme ids into `group_ids`; prompt rule tightened,
  validation reasons made instructive (they are the repair call's
  instructions).
- **Malformed live emission is recoverable** — `MalformedEmissionError` is a
  turn-consuming error exchange (structural failure on the forced final
  turn); a malformed repair emission means the repair produced nothing.
- **Per-claim salvage** — live emissions malform at claim grain; valid claims
  salvage, malformed ones count into `claims_rejected_structural`.

### Minor deviations, resolved within the contract's vocabulary (flagged, not silent)

- **Retrieval scope follows text availability, not fetch-pipeline state
  (3de72ca).** `build_retrieval_scope` initially gated on
  `full_text_status='ingested'`; that column describes the *fetch pipeline*
  only (008 schema comment) — an uploaded document carries its full text on
  the envelope snapshot and never enters the fetch pipeline, so the skeleton's
  deliberately-appraised uploaded seed was invisible to the chunk lane. The
  contract's own vocabulary ("screened-in ingested documents") decides it:
  upload ingest IS ingestion. Regression-tested.
- **`search_chunks` records carry `appraised` (d975ae9).** The M4 rule
  (produce-grounded-block cites only appraised evidence) combined with
  screen-bounds-reading means the model may read chunks it must not cite; the
  record now says which is which and the section prompt carries the rule.
  Without it, every chunk claim on a thin-appraisal corpus died at validation
  — mechanically honest but useless. Additive to the contracted record shape.
- **Structurally unvalidatable claims after repair are excluded and counted**
  (`claims_rejected_structural`): a claim whose *type* is still unavailable or
  content-scan-shaped after its one repair has no honest persistence path
  (there is no validator to validate it against). The contract's flag-not-drop
  lists one exclusion (fabricated chunk quotes); this second, narrow exclusion
  is the same shape — counted, never silent. Everything judge-rejected but
  type-valid persists soft-flagged as contracted.
- **Codex lane substitution (build-time, recorded):** plan Task 8 (judgment
  suite) was routed to Codex; the Codex workspace ran out of credits mid-build
  and the suite ran on the fresh-context deep-reasoner substitute (the 011
  fallback pattern, same brief). Tasks 3–5 ran on Codex as planned.

## Intent & assumptions

- The slice's bar is **mechanism correctness, invariant enforcement, honest
  flags and provenance fidelity** — never section/prose/retrieval quality or
  judge calibration (eval-workstream territory, deferred entry recorded).
- The suite is deterministic and egress-free: stub backends, 009 stub vectors,
  the scripted stub driving the real loop runner; socket-deny covers the
  synthesise round-trips.
- Plan-pinned constants are the enforced values (caps-bind tests); the budget
  ceiling 2 + SECTION_CAP × (SECTION_TURN_CAP + 3) is asserted binding.

## Known unverified items

- **Live selection-prior steering** — not isolatable on this corpus (the
  citable set ⊆ the selected set, see the confound note); the property holds
  deterministically in the suite. Needs a corpus with citable docs on both
  sides of the selection.
- **Zero-group intervention partition on the live run — ROOT-CAUSED at step 7
  (trace replay, 2026-07-08): a 012 validation defect, not model drift.** The
  model proposed 16 coherent groups covering all 96 values in every call, but
  `validate_partition` is all-or-nothing and one group label over
  `LABEL_MAX=80` rejects the whole partition: partition group 6 (92 chars)
  and repair group 8 (89 chars) on run b423032b; same shape on e50939bb —
  4/4 intervention calls lost to a single over-long label each. The outcome
  runs survived at a max label of 78 chars (two under the cliff), which is
  why 012's own live check passed. Systematic driver: intervention values
  are long compound policy phrases, and the prompt's own
  ground-labels-in-member-vocabulary rule pushes labels long. **FIXED in
  this PR (user decision, 2026-07-08):** `validate_partition` now rejects
  label/description violations at group grain (members flow to the repair;
  id-integrity violations stay whole-response), and rejection reasons
  persist into `grouping_provenance.rejection_reasons` + a `groups_rejected`
  flag — the reason previously existed only in the trace. Regression tests
  replay the live shape; the task-cycle-review skill gained a structural
  live-trace content-review lane from the same lesson.
- **Writer under-uses finding claims** — with an extraction referenced and
  `query_findings` returning records, the live writer emitted no finding-type
  claims; synthesis-quality eval seam (prompt emphasis), not a gate.

- Live judge/writer behaviour beyond the four-profile smoke — the eval
  workstream owns quality; this slice persists judge I/O for eval-readiness.
- The pass-through reranker's live slot (Bedrock Rerank) — lands with the
  Bedrock slice; the seam is exercised by a test fake only.
- Stub-mode skeleton emits no chunk claims on the fixture corpus (noise-vector
  ranking over a topically homogeneous corpus) — the chunk mechanism is
  DB-test-proven and live-check-exercised instead.

## Public safety

- Committed artifacts (schema, prompt text, tool schemas, wire models,
  roll-up shapes, synthetic fixtures) are public-safe; syn-002 is authored
  synthetic text.
- Live-run egress was fixture-corpus text (openly licensed by construction) +
  the scope intent to the OpenAI API; full-I/O traces on the user-operated dev
  Langfuse only; keys env-only and absent from all captured output
  (_confirmed at the live check_).

## Review findings (step 7, 2026-07-08 — fresh conversation)

Tier-3 stack as contracted: **contract verifier** (pinned fresh reviewer,
read-only) · **`/code-review` medium** (8 lens-scoped finder angles → 14
candidates → 1-vote verify: 13 CONFIRMED / 1 PLAUSIBLE / 0 refuted) · **one
security lane** (headline: the agent loop) · **Codex adversarial** (read-only
brief; 7 claims, each independently verified — 2 refuted as
intended-by-contract, 5 confirmed) · `/simplify` **skipped with
justification** (the `/code-review` reuse/simplification/efficiency/altitude
angles ran and their adopted fixes were applied in this phase; a second
same-family cleanup pass would duplicate them).

**Headline outcomes:** the contract verifier found **no violated rubric
items** (all satisfied except the two step-8-pending ones) and no
documented-but-not-built claims. The security lane found **no critical or
high** issues — closed tool dispatch, binding caps, parameterised SQL, no
citation escape, clean egress/keys all held under adversarial review.

**Convergent findings (multi-lane, high confidence), all adopted:**

- **`lookup` tag reads were project-wide, not screened-scope** (security ·
  Codex · contract verifier): `docs_by_tag` / `tag_aggregate` /
  `tags_by_doc` now join through this scope's screened-in set
  (`_screened_in_doc_ids`); regression-tested.
- **Reasoning-claim cap could leak by one on a type-changing repair**
  (`/code-review` · contract verifier): `validate_claims` now takes
  `reasoning_count_start` seeded with the surviving initial batch;
  regression-tested.

**Unique-lane findings adopted (each justifies its lane):**

- **Codex:** `claims_rejected_structural` was counted in memory but never
  reached the persisted roll-up — contradicting this document's own
  "counted, never silent" claim (doc-vs-code catch). Now in per-block
  roll-ups, run counts and flags. · **Same-run re-execution wrote an orphan
  artefact + blocks before failing at the roll-up UNIQUE, and the harness's
  failure-event write then died on the aborted transaction** (no audit
  event, cascading driver error): a pre-write existence check now fails loud
  before any write; UNIQUE stays as the concurrent backstop; harness-level
  regression test added. · **A finding claim citing a finding with an empty
  grounding array passed unflagged** (the one anchor-failure shape that
  skipped the flagging branch): now `quote_unverified` + weakly-grounded
  cap; regression-tested.
- **`/code-review`:** `citation_verified_share` divided mixed units
  (citation rows ÷ rows+flagged-claims) — new per-anchor
  `anchors_verified`/`anchors_unverified` counts feed the trace score. ·
  `how_resolved` mislabelled an explicitly-supplied-and-consistent reference
  as `transitive:*` — now records `explicit`; regression-tested. · Repair
  replacements bind positionally with no count check — mismatches now flag
  `repair_count_mismatch` (id-carrying repair schema → deferred.md). ·
  Efficiency: chunk-claim validation reuses the cached per-document basis;
  retriever unit tokens memoised; section persistence uses bulk inserts. ·
  Cleanup: shared `_spans_to_citations` / `require_parsed` /
  `require_single_tool_call` / `_transcript_records` helpers; the test-suite
  `seed_ingested_full_text` fixture moved to `tests/helpers.py`; the
  defensive `getattr(config, "grouping_run_id")` replaced with the direct,
  fail-loud attribute.
- **Security:** per-emission bounds (`EMISSION_CLAIMS_MAX`=50,
  `CLAIM_TEXT_MAX`=5000, enforced at salvage, overflow counted structural —
  closing the one hole in the cap discipline) · `repair_unparseable`
  roll-up flag (systematic backend malformation now distinguishable from
  honest sparsity) · bounded harness catch-all error strings (type name +
  200 chars; raw exception text no longer lands in durable events) · one
  adversarial line in the judge prompt (chunk text discussing
  verdicts/tiers/reviewers is evidence of nothing).

**Declined / deferred, with reasons:**

- **Pattern/theme/gap claim text is never judged** (security MEDIUM + Codex
  HIGH, convergent): contract-mandated — `JUDGED_TYPES` is the approved
  design (deterministic validation, not judgment, for computed-payload
  types). Real residual (injected prose can ride an unjudged claim type into
  the artefact); recorded as a hardening candidate on the quality-evals
  seam, not silently dropped.
- **Fabricated quotes appear in Langfuse traces** (Codex): the contract's
  operative invariant ("no citation row, no stored quote") is
  domain-model-scoped and holds; traces are deliberately full-I/O on the
  operator's own instance. Adjudicated as in-contract; the rubric's
  "persisted anywhere" phrasing is clarified as DB-scoped here. Trace-store
  trust boundary noted in deferred.md.
- **`_load_findings` per-snapshot N+1** (`/code-review` efficiency):
  premature at current corpus scale; folded into the existing
  corpus-scale-retrieval deferred entry.
- **Harness node triplication** (`_run_scope_component` /
  `_run_characterise` / `_run_synthesise` share ~30 boilerplate lines;
  `/code-review` altitude): author-documented deliberate choice; a
  mid-review refactor of shared 011-landed infrastructure is worse than the
  duplication. Deferred-cleanup entry instead.
- **Second exclusion class ratified** (contract verifier finding A): the
  lead ratifies `claims_rejected_structural` as the narrow second exclusion
  beyond fabricated quotes — a claim whose *type* has no validator after its
  one repair has no honest persistence path — now that it is visible in the
  persisted roll-up (the fix above made this document's claim true).
- **Block ordering lives in the roll-up JSONB, not an ordering column**
  (contract verifier, INFO): consistent with the deferred
  composition-conventions seam; no change.

**Fake-done check on this phase's fixes:** no test deleted/weakened (the
same-run test was *strengthened*: SynthesiseFailure + no-orphan-writes +
harness-event assertions replaced a bare IntegrityError expectation); no
swallowed errors introduced (the new guards fail loud); all fixes carry
regression tests (629 total, was 620).

**Budget actuals (cost proxy, split by class):** reasoning-class ≈ **356K**
(contract verifier 169K · security 164K · Codex 23K) vs the ≤250K routine
target; fast-worker ≈ **1.05M** (finders 488K · candidate verifiers 186K ·
Codex-claim verifiers 173K · test batch 202K) vs ≤500K. Overrun is the slice
size (13.9K added lines, ~3× a routine slice — sized deliberately, 008
retro) plus the two-stage verification of Codex's claims, which refuted two
"critical" findings before they cost adjudication churn. Per-angle diff
scoping was applied; no data files needed excluding.

**Live-trace content review (step 7 follow-up, 2026-07-08):** the four
synthesise profile traces were read for content, not just cost/hygiene.
Structure is sane (one proposal per run, section turns within caps, embed
batches ≤ turns, repair→re-judge chains present). The judge's strict lane
fires correctly live: every `unsupported_mis_cited` sampled was a reasoning
claim smuggling empirical assertions or recommendations — exactly the
Tier-4 escape the contract targets — and the repairs reworded down to
computed-count pattern claims and verbatim chunk excerpts. No empty
rationales, no empty judge envelopes. The same trace review root-caused the
zero-group anomaly (§ Known unverified items): a 012 `validate_partition`
all-or-nothing rejection on one over-long label, not model drift — the
model's grouping was good all four times.

**Rubric status:** items 1–7 and 9–19 SATISFIED (contract-verifier report,
file:line + named-test evidence; two overlap-verified here); item 8
satisfied by this section. The step-8 records (deferred.md seam updates from
this review, knowledge/agentic-ops entries) ride in the PR.

## Deferred work

Recorded/updated in [docs/deferred.md](../../deferred.md) — the task-013
section (plan-compile sections, cross-encoder reranking, content-scan pattern
claims, policy-conditioned citable-bar flagging, block summaries, structure
discovery, regeneration-time coherence, quality evals, artefact
discriminator), the narrowed `retrieve`/composition entries, and the closed
entries (`query-findings` discharged; traced-call helper factored; the 009
vectors' first reader landed). The review stack added: the id-carrying
repair-schema seam, the harness event-write-on-aborted-transaction seam, the
unjudged-claim-text hardening candidate (quality-evals entry), the trace-store
trust boundary note, `_load_findings` batching (corpus-scale entry), and the
harness-node generalisation cleanup.
