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

(To be added by the review stack — step 7, fresh conversation.)

## Rubric status

(To be filled with the review stack; all acceptance checks from the contract are
covered above and green.)

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
