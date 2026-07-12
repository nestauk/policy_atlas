# Verification: 020-extract-v2

Evidence for the IOF schema v2 slice (effect_basis + study_geography + fencing +
evidence-type provenance). Filled at step 6; Review findings + Rubric status land after
the review stack (step 7).

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (baseline, build-open) | pass | 1148 tests, mypy 120 files, ruff, build — green before any change |
| `make verify` (Phase A exit) | pass | 1164 tests (16 new), mypy, ruff, build |
| `make verify-fast` (Phase B+C gate) | pass | 1125 tests, mypy 121 files, ruff (one stale-mypy-cache false positive cleared with `rm -rf .mypy_cache`; clean-cache run green) |
| `make verify` (step-6 exit) | pass | 1176 tests, mypy 121 files, ruff, build, okf-validate |
| `make okf-validate` (docs sweep) | pass | 63 concepts, 0 violations |
| `make verify` (step-7 exit, post-review-fixes) | pass | 1178 tests (2 review-added), mypy, ruff, build, okf-validate |

## Checks beyond the build

- **Deterministic tests** (all green in the suite):
  - Migration `0f4e2d8c9b1a` up/down round-trip; pre-existing v1 rows untouched across
    up/down, new columns NULL (`tests/test_extract_schema_v2_migration.py`).
  - CHECK vocabulary ↔ Literal agreement: `EFFECT_BASES` ↔ `EffectBasis`;
    `ck_ser_evidence_type` allowed set == `EVIDENCE_TYPES` + `UNCLASSIFIED_EVIDENCE_TYPE`
    read live via `pg_get_constraintdef` (`tests/test_schema.py`).
  - `iof_rules_v2` coverage tables: value / null-like-string / null for both fields;
    "unclear" documented unreachable for both in v2 (strict wire Literal / free text).
  - v1-null vs v2-null distinguisher via `field_coverage` key-absence.
  - Dedup twins: effect_basis twins do NOT collapse; geography-only twins DO
    (first-wins pinned).
  - Fingerprint/provenance: components map records profile `eb_iof_base_v1`,
    schema `iof_v2`, rules `iof_rules_v2`, prompt by constant (gate decision 1's
    provenance test).
  - Evidence-type provenance: attempted-call → value / `Unclassified` default;
    pre-prompt failure (`empty_basis`) → NULL (`tests/test_extract.py`).
  - Structural fencing: user template placeholders == {envelope_json, segments_json};
    hostile instruction-like abstract rides only inside the fenced JSON object,
    JSON-escaped, round-trips to payload values (`tests/test_extract_judgment.py`).
  - Few-shot pre-flight still binding (import-time validation; doctored-example test).
  - Vetter payload shape snapshot: `_judge_payload_entry` key set pinned, new fields
    deliberately absent (gate decision 2).
  - Writer-envelope carriage: `FindingRecord`/`query_findings`/`_load_findings` carry
    both fields always-present-nullable; v1-row null tolerance on both read paths.
  - Evidence-type divergence: writer envelope reads live classification, never the
    provenance column.
  - Annotation join-path: finding-claim annotation resolves both fields via the
    `cited_finding_ids` → row join; payload embeds no record metadata.
  - Mixed/unclear carry-through: survive `group` and `synthesise` end-to-end —
    already-correct, no drop existed (V2 autopsy requirement now test-pinned).
  - `_load_findings` batch rider: same `BasisText` output, exactly one batched chunk
    query (query count pinned via `before_cursor_execute` listener).

- **AI behaviour — replay probes** (lead-run, live, eval-blind; raw traces in Langfuse,
  summary JSON in the session scratchpad `probe_extract_v6_summary.json`):
  - Modelled-projection doc (naturecomms A2A heat pumps, "Modelling & Simulation"):
    14/14 findings `effect_basis: "modelled"`; geography "Toulouse, France" (study
    setting, not publisher).
  - Primary study (Frontiers Getting Ready 2018): 22 findings all `"observed"`,
    geography "New York City" as reported.
  - Review-shaped (PLOS food-environment realist review): 25 findings, mixed
    observed/modelled, **11 distinct finding-grain geographies** (Australia, Boston,
    Bronx, Denmark, France, Hungary, King County, NSW, NYC, Philadelphia, "regulated
    jurisdictions") — the review-variable pattern the finding-grain decision predicted.
  - Hostile-envelope probe (instruction-like abstract demanding "Atlantis" geography +
    an injected finding): all injection markers false; the one finding extracted came
    from the benign segment ("Denmark", observed).
  - **Vetter pre/post (decision 2)**: v2 vs v3 system prompt on the 14 modelled
    findings — 0 flagged either side, 0 flips. Honest reading: v2 already passed
    modelled results on this probe set (its verdict reasons explicitly call a
    projected decrease "a substantive result"); the v3 line **pins** the behaviour
    against the adversarial-identified text gap rather than correcting an observed
    failure. Recorded as prophylactic, not corrective.
  - **Honesty pin (contract)**: probes show shape and non-regression only; prompt
    changes remain eval-blind until the extraction-quality evals exist.

- **Manual — scoped live check** (contract-pinned scope; NO composed full-chain e2e):
  dev-DB 018 replay project `91d2d684`, screened selection run `332c8d7c` reused
  (never re-searched). Results (`live_check_020_summary.json` in the session
  scratchpad):
  - **Migration on real data**: 3,150 finding rows + 347 extraction records untouched
    across `alembic upgrade head` (`b7f3d9a2c5e1` → `0f4e2d8c9b1a`); sampled v1 rows
    read NULL in both new columns.
  - **Fresh-fingerprint extract** (run `3db315b0-6772-4f0b-b0b6-d017cc8c3a65`, vetter
    active): 10/10 selected docs fresh (0 reused — the v2 fingerprint memo-missed as
    designed), 8 extracted + 2 no_findings + 0 failed; provenance records
    `iof_v2` / `extract_iof_v6` / `iof_rules_v2`; 86 findings — 17 modelled /
    69 observed, 80 with reported geography, **86/86 value-or-coverage-keyed**;
    per-doc evidence-type provenance recorded (e.g. "Modelling & Simulation",
    "Policy Syntheses & Guidance Documents") including on `no_findings` rows.
  - **Synthesise** (run `45fed4e3-5586-42eb-a856-c24d8e0d1219`, referencing the fresh
    extraction): writer envelope loaded all 86 findings with both fields always
    present; finding-claim (citation) annotations resolve `effect_basis` +
    `study_geography` via the cited-finding row join ("England and Wales", "Scotland",
    "United Kingdom" observed values); payloads embed no record metadata (asserted).

## End-to-end command

```
uv run python <scratchpad>/live_check_020.py
```
(Session scratchpad script; hardcodes the dev DB URL + project/scope/selection ids
above, loads keys from `.env`. The replay probes: `uv run python
<scratchpad>/probe_extract_v6.py`.)

## Diff summary

One version bump, end-to-end: wire + stored models gain `effect_basis` (strict Literal,
joins `claim_key`) and `study_geography` (free text, out of the key, first-wins);
`SCHEMA_VERSION iof_v2`, `iof_rules_v2`, `extract_iof_v6` (envelope fenced as one JSON
data object + guidance for both fields), `extract_finding_vetter_v3` (one guidance
line, payload unchanged); three nullable columns + CHECKs in migration `0f4e2d8c9b1a`
(no backfill); evidence-type provenance recorded attempted-call-only; writer envelope +
`_load_findings` carry the fields; `_load_findings` N+1 batch rider; spec flow-back +
deferred.md sweep (3 discharges, 3 narrows, 2 new seams). ADR 0016 (authored at design,
Accepted) matches the as-built code on all nine decisions — re-checked at step 6.

**Flagged deviations / adjudication notes (no contract deviations):**
- **Executor substitution (plan § Phase A marks)**: the codex job
  (`task-mrhuhpoh-hx2umo`, session `019f5692-95a1-7ca0-a66a-54ce90baaf9b`) delivered
  the complete product-code diff then FAILED mid-turn ("model at capacity") before
  authoring tests. Per the codex-exhaustion fallback: lead reviewed the delivered diff
  (one wart fixed — a duplicate `UNCLASSIFIED_EVIDENCE_TYPE` constant; field
  descriptions byte-verified against plan.md), test sweep + Phase A test authoring
  re-routed to fast-worker. Family-flip note for review: the *product code* of Phase A
  is codex-authored, its *tests* are fast-worker(Claude)-authored, lead-reviewed.
- The plan's Phase A text retained a stale "invalid enum value (coerce-and-flag)"
  clause alongside its own amendment; built per the amendment (and the amended
  contract): NO invalid-enum recovery row for `effect_basis` — strict wire Literal,
  the `causality_by_design` precedent. "unclear" is unreachable for both new fields
  in v2; documented in the test tables.
- Phase B few-shot: the example segment text gained "in nine high-income countries"
  so `study_geography` is demonstrated non-null; insertion precedes both anchor spans,
  quotes stay verbatim (pre-flight enforced).

## Review findings

Step 7 ran 2026-07-12 in a fresh conversation (this section is its record; lead
adjudicated, no lane self-reviewed its own code). Lanes: contract-verifier
(fresh Opus, all 17 rubric items + verification/ADR claims vs as-built) ·
`/code-review medium` (8 scoped finder angles, Claude) · security-auditor ·
Codex adversarial (family flip: anchored the Claude-written prompt/carriage/
tests; Claude lanes anchored the Codex-written Phase A product code) ·
lead live-trace content review (probe summaries + direct dev-DB checks).

**Adopted (fixed in the review commit):**
- **Vetter fingerprint gap** (Codex adversarial, MEDIUM — the stack's best
  finding): the `finding_vetter` fingerprint component carried only
  prompt+max_output_tokens, omitting `FINDING_VETTER_MODEL` and
  `FINDING_VETTER_REASONING_EFFORT` — a vetter model/effort change would have
  reused stale memo records despite changed filtering. Latent since 018 C5,
  surfaced by this slice's "every output-affecting knob" focus. Fixed in
  `extraction_fingerprint()` + pinned per-knob in
  `test_fingerprint_changes_on_any_single_component`.
- **Fresh-alongside memo test missing** (CONVERGENT: Codex adversarial +
  contract-verifier independently): rubric 10's "old-reuse + new-fresh-
  alongside" was pinned only by composition. Added
  `test_fingerprint_change_extracts_fresh_alongside`: bump → memo miss → new
  record + findings alongside, old rows byte-identical, original fingerprint
  still reuses.
- **Fencing test escaped-leak hole** (Codex adversarial, LOW): the hostile-
  envelope test checked only the RAW string outside the fence; a regression
  leaking the JSON-escaped form would have passed. Hardened with an
  escaped-fragment assertion.
- **`render_field_docs` acceptance check untested** (contract-verifier NOTE):
  added the two-line assertion test.
- **Stale `extract_iof_v5` docstrings** (cross-file finder): extract.py +
  extraction_backend.py module docstrings; made version-neutral (point at
  `PROMPT_VERSION`) so they cannot go stale again.
- **finding_vetter.py missing the "lead-authored and versioned" docstring
  declaration** (conventions finder) — every sibling prompt module carries it;
  added.
- **Accidentally committed demo build artifacts** (lead, pre-lane diff
  hygiene): phase C's commit included `demo/frontend/node_modules` (6,230
  files), `.vite/` and `tsconfig.tsbuildinfo` — no node ignores existed.
  Untracked + `.gitignore` entries in the review commit; history rewrite of
  the unpushed branch recommended at the PR gate so the blobs never reach
  origin (owner decision).

**Declined (recorded reasons):**
- `sent_evidence_type` assigned in both submit and retry paths (3 finder
  angles converged, cost-only): this IS ADR-0016 decision 7 — provenance set
  at every backend-call submission site; deduplicating would couple the retry
  path to the first loop's side effect.
- No production annotation resolver for the new fields (Codex): contracted —
  the owner settled don't-embed, resolve-via-row is the pattern, and the
  rendering surface (web-app/export slice) decides its own read helper; the
  join-path test pins reachability, the live check exercised it on real rows.
- v1-null distinguisher test's v1 side is a hand-built literal dict
  (contract-verifier NOTE): iof_rules_v1 code no longer exists to exercise —
  the dict documents the v1 coverage shape; the v2 side genuinely asserts
  key-emission. Recording beats a pretend-exercise of deleted code.
- Migration-test "repeated inspection" (simplification finder): the four
  inspections are at four distinct migration states — re-fetching is required,
  not duplication.
- Removed-behaviour candidates B1–B3 (null abstract vs "(none)"; metadata
  staleness; silent missing-snapshot): all REFUTED — null-abstract is the
  documented envelope design (probe-evidenced); snapshot_ids and
  metadata_by_snapshot are built in one guarded loop from a single join query,
  so the miss states are unreachable and the old `.one()` guarded a
  cross-query invariant that no longer exists.

**Deferred (→ docs/deferred.md, step 8):**
- Free-text finding fields (`study_geography` and the pre-existing class:
  intervention/outcome/study_design…) carry no length bound onto a
  prompt-feeding column (security LOW; `DIRECTIVE_STRING_MAX` precedent) —
  one bound in `validate_record` covers the class; filed as a seam, not a
  blocker (schema-constrained output + doc-influence limit practical size).

**Lead live-trace content review** (013 lesson — the roll-up is not the
evidence):
- Full-table dev-DB checks (stronger than the build's 3-row sample): 0 v1
  rows carry new-field values or coverage keys; 86 new rows; live CHECK
  definitions match the Python vocabularies string-for-string.
- Probe-summary claims verified against per-finding raw output: the
  11-distinct-geographies count is exact; hostile-envelope markers all false;
  the vetter "prophylactic, not corrective" reading is honest (pre-v3 reasons
  already accept projected results).
- **Content anomaly the roll-up hides**: 2/86 new rows carry non-geography
  `study_geography` values — "Visit a Heat Pump" / "Visit a Heat Pump
  marketing" (a programme name, from a Nesta marketing doc). Carriage is
  correct; this is a prompt-quality signal, eval-blind by contract — recorded
  here as ground-truth-authoring input for the eval slice (geography
  over-filling on non-study documents is a real failure mode to annotate).

**Fake-done check on the review fixes**: no tests relaxed/deleted (only
additions + two docstring edits + one fingerprint-component addition);
`make verify` re-run green after fixes.

**Security lane verdict (rubric 12)**: fencing **structurally complete** — no
document-derived envelope text reaches the prompt outside the id-keyed JSON
object on any path (template placeholders pinned structurally; retry paths
rebuild messages only via `build_extract_messages`; str.format does not
re-scan substituted values; JSON escaping prevents breakout). Explicit note:
structural ≠ semantic — instruction-like *content* still reaches the model as
data; the layered mitigations (data-not-instructions rule, structured output,
quote verification, vetter, grounding judge) are the ceiling, and
migration/SQL/secrets hygiene all passed.

**Flagged-deviation adjudications (each explicitly re-examined, none
contested):**
1. Executor substitution (codex died mid-turn; lead reviewed the delivered
   diff, fast-worker authored tests): CONFIRMED — the contract-verifier
   independently probed the fast-worker tests' assertions (dedup twins,
   v1/v2-null, batch count pin, fencing) and found them genuine, and the
   Codex lane anchored the Claude-written surfaces.
2. Stale plan clause (invalid-enum recovery) built per the amendment:
   CONFIRMED — the amended contract text governs; strict wire Literal built;
   rubric 14 holds.
3. Few-shot geography insertion ("in nine high-income countries"):
   CONFIRMED — precedes both anchor spans, quotes verbatim, pre-flight
   enforced, probes green.

## Rubric status

All 17 items **hold** (contract-verifier lane verdict, confirmed by the lead
after fixes; the verifier independently re-ran the changed-file test subset —
193 green — and checked every verification.md/ADR-0016 claim against the
as-built code: no "documented but not built" mismatch). Items 1–7 and 9–17:
HOLDS with evidence cited per item in the verifier report (summarised in
§ Review findings). Item 8 (review stack ran, findings recorded): satisfied by
this section. Post-fix `make verify` green (1178 tests — 1176 + the two
review-added test functions).

`/simplify` not separately run — recorded justification per the review-stack
economy: `/code-review medium` already ran dedicated reuse / simplification /
efficiency / altitude finder angles on this diff (their findings adjudicated
above); a second same-family cleanup pass would duplicate it.

## Intent & assumptions

Ground truth for extraction-quality evals will be authored against this record shape —
that is why all pending wire/row/prompt changes rode one bump. `effect_basis` null =
honest indeterminacy; old rows render "not recorded under v1" via coverage
key-absence, never as "observed".

## Known unverified items

- Prompt quality remains eval-blind (contract honesty pin) — probes evidence shape and
  non-regression on 4 docs, not quality; extraction-quality evals are the next slice
  after Slice C.
- The vetter guidance line produced no verdict flips on the probe set; its protective
  value is untested until a modelled-results doc that v2 *would* have flagged appears
  (no such doc observed).
- Dev-DB migration was up-only on real data (down-migration exercised in tests, not on
  the dev DB).
- D2's composed full-chain rehearsal remains separately owned (deliberately out of
  scope here).

## Public safety

All code, migration, spec and deferred.md changes are public-safe. Replay/live
evidence lands here as summaries only; raw probe I/O and component traces stay in the
local Langfuse instance (run ids above). Fixture docs are openly licensed or
own-org-authorised (008 policy). No secrets anywhere (scripts read keys from `.env`).

## Review handoff (step-7/8 inputs)

- **Adjudication items**: the three flagged notes in § Diff summary (executor
  substitution/family-flip provenance; the stale plan clause built per amendment; the
  few-shot geography insertion).
- **Executor provenance**: Phase A product code codex; Phase A tests + Phase C
  fast-worker; Phase B + gates + live check lead. Review's family flip should put the
  Claude lane on the codex-written schema/rules code (already done once mid-build) and
  a skeptical eye on the fast-worker tests' assertions.
- **Diff scoping**: per-angle scoping per the review-stack economy memory; the docs
  sweep (deferred.md/data-model.md/log.md) can be reviewed as text, not code.
- **Live-trace pointers**: extract run `3db315b0…`, synthesise run `45fed4e3…`,
  project `91d2d684…` (dev DB + Langfuse).

- **Knowledge candidates** (one bullet per durable-seeming lesson, however raw):
  - Codex dying mid-turn ("model at capacity") can still leave a complete, high-quality
    partial diff in the working tree — salvage-and-reroute (lead review + fast-worker
    for the remainder) beats rerunning the whole brief; the failure surfaced as a
    *duplicate constant* (codex re-added one that existed later in the file), which is
    the class of wart to grep for when accepting a partial delivery.
  - Wire models are all-fields-required (OpenAI strict structured output): ANY wire
    field addition breaks every construction site including the few-shot example at
    import time — the keep-green pattern is mechanical nulls in the example at the
    schema phase, real values authored at the prompt phase.
  - mypy incremental cache can produce a false `attr-defined` on a submodule import
    after multi-agent edits; `rm -rf .mypy_cache` before believing a type error that
    contradicts a just-green full run.
  - Replay-diffing a prompt guidance line can show it is *prophylactic* (0 flips —
    the old prompt already behaved) — recording that honestly beats claiming the line
    "fixed" anything; the adversarial finding was about text risk, not observed
    behaviour.
  - The finding-grain geography call validated empirically on first live contact: one
    realist review yielded 11 distinct per-finding geographies (a document-grain field
    would have destroyed exactly this).
  - `skeleton._run_component` is a ready single-component driver for scoped dev-DB
    live checks on existing projects (run row + plan compile + harness + tracing in
    one call) — no need to hand-roll run bookkeeping in check scripts.
  - The `annotation` table reaches its run only via block → artefact (no run_id
    column); run-scoped annotation queries in checks want newest-first + a
    `payload ? 'cited_finding_ids'` filter.
  - The evidence-type provenance semantics ("what the prompt saw", null when no prompt
    ran) fell out naturally by setting the value at the backend-call submission site —
    budget-exhausted-before-call docs correctly stay null with zero extra logic.

## Deferred work

Swept this slice (see `docs/deferred.md` diff): discharged — effect basis · envelope
fencing · `_load_findings` batch load; narrowed — study-geography (diversity consumers
+ canonicalisation remain) · evidence-type memo-match rule (trigger unfired) ·
mixed/unclear (now test-pinned); added — `effect_basis` as judge-envelope candidate
(018 A/B protocol binds, C/eval gate) · 018's dangling A/B-gated writer-envelope
metadata queue (institutions → FWCI → further fields).
