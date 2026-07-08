# Verification: 013-synthesise

Evidence for the synthesise slice (EB component 9, the terminus; the repo's
first agent loop). Public-safe — no secrets, no raw source text, no unredacted
traces. Filled at step 6; **Review findings** + **Rubric status** follow the
review stack (step 7).

> **Status: DRAFT — being filled during step 6.** The `make verify` table and
> live-run evidence are completed at the step-6 exit.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make test` | _pending step-6 exit_ | |
| `make typecheck` | _pending step-6 exit_ | |
| `make lint` | _pending step-6 exit_ | |
| `make build` | _pending step-6 exit_ | |

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

Live mode (the contract's manual check; keys from the operator's `.env`):

```bash
_pending — filled with the live-run evidence below_
```

## Live-run evidence (four substrate profiles)

_pending the live check._

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

## Deferred work

Recorded/updated in [docs/deferred.md](../../deferred.md) — the task-013
section (plan-compile sections, cross-encoder reranking, content-scan pattern
claims, policy-conditioned citable-bar flagging, block summaries, structure
discovery, regeneration-time coherence, quality evals, artefact
discriminator), the narrowed `retrieve`/composition entries, and the closed
entries (`query-findings` discharged; traced-call helper factored; the 009
vectors' first reader landed).
