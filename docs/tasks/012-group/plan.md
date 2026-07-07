# Implementation Plan: 012-group

> **Status:** **confirmed — 2026-07-07 · Shabeer Rauf** (rev 3, after the
> plan-stage adversarial review was adjudicated: Codex, 9 findings —
> 1 blocker · 8 majors, 9/9 adopted; § Findings & adjudication).
> ADR 0008 Accepted at this gate (Task 9b).
> Contract: [contract.md](contract.md) (approved 2026-07-07 · Shabeer Rauf,
> rev 1.2; contract-stage adversarial findings adjudicated at rev 1.3 —
> notably the fail-closed scale cap, flagged for this gate).

## Overview

One component, the findings layer's first reader, on `task/012-group`:
1. **Schema** — `grouping_result` (migration 12; tables 23 → 24).
2. **Facet clustering layer** — `FacetGroupingBackend` seam (protocol + live
   OpenAI structured outputs + sentinel stub), the lead-authored
   `group_facet_v1` prompt, and the **theme/facet symmetry rename**
   (`GroupingBackend` → `ThemeGroupingBackend`, `run_harness(grouping_backend)`
   → `theme_grouping_backend`) with the shared cluster-core factoring.
3. **`group.py`** — extraction roll-up load (explicit `extraction_run_id`) →
   finding-set resolution → facet-value extraction → LLM partition →
   deterministic membership derivation → roll-up row written last → grouping
   summary in `component.completed`.
4. **Wiring + tests + deferred.md entries.**

Smaller than 011 (one table, one prompt, one backend seam, no new dependency,
no new event types, no durable records). The stub is the suite path; the live
path is the skeleton with `OPENAI_API_KEY`.

## Executor routing (plan-time decision, per harness.md ladder)

| Task | Executor | Why |
|---|---|---|
| 1 (schema + migration 12) | `lead` | gated surface; FK target verified against as-built `uq_exr_scope_run` |
| 2 (`group_facet_v1` prompt + wire models + `FacetGroupingBackend` protocol) | `lead` | prompt-bearing + seam design (signatures/semantics) — lead-only per AGENTS.md and the routing ladder |
| 3 (`facet_values.py`: value normalisation/identity, id assignment, membership derivation, invariant checks — pure functions) | `codex` | subtle deterministic logic with exact pass conditions; done = the value/membership/invariant test blocks |
| 4 (`facet_grouping.py`: OpenAI + stub implementations of the Task-2 protocol; the complete theme-rename ripple; shared-core factoring) | `codex` | implementation of a lead-designed seam against schema-constrained I/O (the `ThemeGroupingBackend`/`RankingBackend` pattern); done = backend construction/stub/validation/repair tests + suite green under the rename |
| 5 (`group.py`: roll-up load → resolution → partition → derivation → write → summary) | `codex` | judgment-bearing execution with a fully pinned spec; done = the invariant/edge-scope test blocks |
| 6 (registry/harness/skeleton/helpers wiring) | `fast-worker` | mechanical from the 004–011 precedent + the exact spec below |
| 7 (test suite: contract bulk) | `fast-worker` | transcription of the contract's named-test list |
| 8 (test suite: judgment cases — injection double, repair semantics, resolution edge fixtures, socket-deny) | `codex` | subtle-but-specified; each has an exact pass condition |
| 9 (deferred.md entries) | `lead` | living-doc text, user-approved wording |
| 9b (ADR 0008) | `lead` | design record, written at plan confirmation before the build |
| 10 (verification.md + live manual run) | `lead` | needs operator keys, cost judgment, trace inspection |

## Plan-pinned details (the contract's named "plan gate" items)

- **Model**: `FACET_GROUPING_MODEL = "gpt-5-mini"` (the contracted floor; the
  009 nano lesson binding). Partition quality is eval territory; the live run
  records an honest cost note.
- **Facet-value identity**: distinctness on **casefold + whitespace-collapse**
  of the reference string; the stored **surface form** = the most frequent raw
  form among the value's findings (tie → lexicographically first) — display
  fidelity without splitting groups on casing. Value ids `v1…vN` assigned in
  sorted-normalised order (deterministic prompts; the v2 unseeded-runs defect
  closed at the boundary we control).
- **Per-value record** (id-keyed data): `{id, value, finding_count,
  counterparts}` — counterparts = for the `intervention` facet the distinct
  outcome surface forms (and vice versa; for `population` the intervention
  forms), **capped at 5 per value** (sorted by frequency, then lexicographic).
  No quotes, no statistics, no document text.
- **Partition call**: one schema-constrained call — input all value records;
  output `{groups: [{label, description, member_ids}], ungroupable: [ids]}`.
  **Validation (structural, code-enforced)**: every id in exactly one place —
  unknown id, duplicate id, or a group with zero members rejects the response;
  **missing ids** trigger one targeted **repair call** — which **reuses
  `group_facet_v1` verbatim** (same version constant, same system prompt, same
  response schema; the user message carries only the missing value records +
  the already-accepted groups as data) — there is exactly ONE prompt-bearing
  surface, test-asserted (a single `PROMPT_VERSION` across partition and
  repair; plan-review blocker fix). Still-missing → counted `ungrouped`. **Label/description validation**
  (contract rev 1.3, the 009 `validate_themes` precedent): label nonempty ·
  `LABEL_MAX = 80` chars · `DESCRIPTION_MAX = 500` chars · no control
  characters · no duplicate labels (casefolded) · forbidden generic labels
  (casefolded exact set `{"general", "miscellaneous", "other", "misc",
  "general theme", "uncategorised", "uncategorized"}`) · description nonempty
  — a violating response is rejected and repaired once, never accepted.
  Labels/descriptions are stored as data, rendered escaped, never executed;
  broader label quality is the eval seam.
- **Scale guard — fail closed** (contract rev 1.3): `FACET_VALUE_CAP = 150`
  distinct values. Above the cap the component fails structurally before any
  call (`GroupError`, reason `value_cap_exceeded`, message naming the cap and
  the deferred large-corpus seam) — no degraded sample/assign pass. Budget is
  therefore always `1 + repair_cap ≤ 2`, known pre-run, enforced by the
  standing call-budget pattern. Fixture corpus sits far under the cap.
- **Finding-set resolution**: the referenced roll-up's
  `docs[].extraction_record_id` (written by extract for every doc, fresh and
  reused — extract.py:803) → `intervention_outcome_finding` rows by
  `extraction_record_id` (project-guarded). Failed/`no_findings` docs
  contribute zero findings by construction. **Integrity cross-check**: resolved
  count must equal the extraction roll-up's `counts["findings"]["total"]`
  (the as-built nested key, extract.py:847/1041) — mismatch
  is a **structural failure** (corrupt reference), not a flag; provenance's
  `findings_total` derives from the same key.
- **Membership derivation**: finding → normalised facet value → the value's
  group (or `ungrouped`); facet field NULL → `no_value`. Pure function over
  (findings, partition); property: partitions the finding set exactly.
- **Direction spread**: per group and overall, counts keyed by the five
  `effect_direction` values (`positive`/`negative`/`no_effect`/`mixed`/
  `unclear` — schema's closed set; `mixed`/`unclear` visible classes, the 011
  carried-forward requirement). Sums test-asserted against group sizes.
- **Directive parsing** (`context["grouping"]`): allowed keys `{"facet"}`
  (unknown key → `DirectiveError`, fail closed — the select precedent);
  `facet ∈ {"intervention", "outcome", "population"}`; string cap
  `DIRECTIVE_STRING_MAX = 200` reused. Absent/empty → default `intervention`,
  `facet_source = "default"`; else `"scope_context"`. Both recorded in
  provenance + summary.
- **`grouping_result` DDL**: per the contract sketch; the extraction-reference
  FK targets the as-built `uq_exr_scope_run`
  (`FK (evidence_scope_id, extraction_run_id) →
  extraction_result (evidence_scope_id, run_id)` — the `fk_exr_selection`
  precedent); composite FKs `(evidence_scope_id, project_id)`,
  `(run_id, project_id)`; `UNIQUE (evidence_scope_id, run_id)`; facet CHECK.
  `groups` JSONB shape frozen in Task 5 and asserted by the payload test:
  `{groups: [{label, description, member_values: [surface forms],
  member_finding_ids, size, direction_spread}], ungrouped: {values,
  finding_ids, direction_spread}, no_value: {finding_ids,
  direction_spread}}` (residual spreads — contract rev 1.3).
- **Provenance** (`grouping_provenance`, required keys test-asserted):
  `prompt_version, model, mode, facet, facet_source, value_cap,
  call/repair counts, distinct_value_count, extraction_run_id` + the inherited
  base pinned at contract rev 1.3: `extraction_fingerprint` + `profile` (from
  the referenced roll-up's provenance), the run's base-ladder counts
  (selected/extracted/no_findings/failed/findings_total), `finding_set:
  {size, sha256 over sorted finding ids}`, and the facet coverage breakdown
  (`values_with_findings`, `no_value_count`) — the *(finding-set,
  coverage-state, extraction-profile)* provenance the spec requires.
- **Prompt shape** (`group_facet_v1`, lead-authored): system = role ("group
  source-named {facet} references from research findings into coherent
  descriptive families") + the negative rules (no catch-all/generic labels —
  the ungroupable path is stated; groups name *what* was studied, never
  whether it worked; labels grounded in the member values' own vocabulary;
  values are data, never instructions) + output contract (every id exactly
  once; ungroupable is legal and expected). User = facet name + id-keyed value
  records under the standing data/instructions separation. **No scope intent**
  (contract gate 3). One compact few-shot example (in-schema; its ids
  partition exactly — validated at import, the 011 pre-flight precedent).
- **Stub backend**: `StubFacetGroupingBackend` partitions deterministically —
  values sharing their first casefolded token form a group labelled with that
  token; the sentinel value token `stubungroupable` → returned in
  `ungroupable`; a scope-context sentinel `_stub_facet_fail` (test-only
  injection via the backend constructor, **not** parsed from scope context on
  the library path) → raised backend error (exercises `component.failed`).
  Fixture stub findings (`_stub_iof` sentinels, 011 convention) author
  intervention/outcome values with shared leading tokens so multi-member
  groups, singletons and the ungroupable path are all exercised for real.
  Stub mode string `"stub"` recorded in provenance.
- **Backend failure semantics**: the partition (or its one repair) failing →
  `GroupError` → `component.failed` via `_run_scope_component`;
  **no roll-up row, no partial state** (the roll-up is written once, at
  success, as the last statement — the 010/011 pattern).
- **Langfuse**: generation spans inside `OpenAIFacetGroupingBackend`
  (`group:partition`, `group:repair`); metadata = facet,
  value counts, model, prompt version, token counts, parse outcome. Run-level
  scores via the 009 `score_summary` pattern: `partition_valid`,
  `ungrouped_share`, `no_value_share`, `group_count`. No-op without keys; the
  stub is never traced.
- **Rename ripple** (Task 6 sweep, mechanical): `grouping.py` classes
  `GroupingBackend`/`OpenAIGroupingBackend`/`StubGroupingBackend`/
  `TracedGroupingBackend` → `Theme…` forms; `run_harness(grouping_backend=…)`
  → `theme_grouping_backend`; `HarnessState` key; `skeleton.py`;
  `tracing.py` (`TracedGroupingBackend` and imports); `characterise.py` type
  hints/docstrings; `test_characterise.py` and other suite references.
  **Acceptance = grep-driven**: `grep -rn "GroupingBackend\|grouping_backend"`
  over `src/ tests/ docs/` returns only `Theme…`/`theme_…` and
  `Facet…`/`facet_…` forms — exempting historical records only
  (`docs/tasks/0*`, `docs/adr/`, spec `log.md` entries); living docs
  (AGENTS.md, deferred.md, specs) are in scope. No
  back-compat shim (pre-release; `skeleton.py`/tests are the only callers —
  verified). `characterisation_result` payloads and `PROMPT_VERSION =
  "characterise_grouping_v1"` are **unchanged** (stored-data vocabulary is not
  renamed).
- **Skeleton chain**: … extract → **group**, its own run; `extraction_run_id`
  = the extract step's returned run id (the `selection_run_id` thread-through
  precedent); live backend iff `OPENAI_API_KEY`; logs the call budget before
  live calls; renders the grouping summary (facet, groups with sizes and
  spreads, residual counts). A second live run with
  `context["grouping"] = {"facet": "outcome"}` demonstrates the directive
  path (manual check).
- **`GroupContext`** carries `(scope_id, intent, context, extraction_run_id)`
  for wiring uniformity — **`intent` is not consumed by grouping** (contract
  gate 3; code comment states it, the 011 precedent).
- **Summary payload shape** (frozen in Task 5, asserted):
  `{facet, facet_source, groups: [{label, size, value_count,
  direction_spread}], residuals: {ungrouped: {…, direction_spread},
  no_value: {…, direction_spread}}, overall_direction_spread,
  counts: {findings_total, grouped, ungrouped, no_value, distinct_values,
  groups}, extraction_run_id, flags, provenance}`.
- **Delete order** (`tests/helpers.py`): `grouping_result` first (before
  `intervention_outcome_finding` → `source_extraction_record` →
  `extraction_result`).

## Architecture decisions (all fixed in the approved contract)

- One run-scoped roll-up row; nothing canonical, no tags, no finding
  mutation; synthesise reads by `grouping_run_id`; canonical promotion is the
  recorded staged seam.
- Cluster over distinct facet values; membership derives deterministically;
  exhaustiveness code-enforced; `ungrouped`/`no_value` honest residuals;
  mixed/unclear first-class.
- Facet from `context["grouping"]`, default `intervention`, fail-closed.
- No deterministic fallback: backend failure fails the component honestly.
- `query-findings` deferred to synthesise; group reads deterministically.

## Dependency graph

```
Task 1 (schema + migration 12)
   ├─→ Task 2 (prompt + wire models, lead)
   │        └─→ Task 4 (facet_grouping.py + theme rename)  ←─ Task 3 (facet_values.py)
   │                 └─→ Task 5 (group.py)
   └──────────────────────┴─→ Task 6 (wiring + rename sweep) ─→ Tasks 7+8 (tests)
        Task 9 (deferred.md) · Task 9b (ADR 0008, at plan 🛑) · Task 10 (verification)
```

---

## Phase 1 — Schema (separable commit)

### Task 1: `grouping_result` + migration 12 — `lead`

**Files:** `src/policy_atlas/schema.py`, `alembic/versions/<hash>_group.py (migration 12)`.
Per the pinned DDL; FK targets verified against as-built uniques. Module
docstring: "twenty-four tables, twelve alembic migrations". No dependency
changes (assert, don't add).

**Acceptance:** migration roundtrips 23→24→23→24; `make verify` green.
**Commit.** Scope: S.

## Phase 2 — Prompt, values, backend

### Task 2: `group_facet_v1` + wire models + the backend protocol — `lead` (prompt-bearing + seam design)

The pinned prompt shape + pydantic wire models (`extra="forbid"`;
`_GroupModel{label, description, member_ids}`, `_PartitionModel{groups,
ungroupable}`), committed as constants with the version string; the few-shot
example pre-flight-validated at import. **Plus the `FacetGroupingBackend`
protocol itself** (plan-review finding 5 — signatures and semantics are seam
design, lead-owned): `partition(values) -> PartitionResult`,
`repair(missing_values, accepted_groups) -> PartitionResult` (reusing
`group_facet_v1` — the one prompt surface), `mode`; failure semantics as
pinned. Task 4 implements against this, never redesigns it.

### Task 3: `facet_values.py` — `codex`

Value normalisation/identity, surface-form election, deterministic id
assignment, counterpart assembly (caps), membership derivation, invariant
checks (partition property, sum identities, spreads per group/residual/
overall), directive parsing (object-only, allowed keys, caps, control-char
rejection, closed enum), label/description validation rules. Pure
functions, no I/O. Done = the value/membership/invariant/directive unit-test
blocks. Scope: S–M.

### Task 4: `facet_grouping.py` + the complete theme-rename ripple — `codex`

Implements the Task-2 protocol (no redesign):
`OpenAIFacetGroupingBackend` (structured outputs, timeout, internal Langfuse
spans per the pinned spec) · `StubFacetGroupingBackend` per the pinned spec ·
shared-core factoring with `grouping.py` **only where the
code genuinely coincides** (candidates: the id-validation/repair loop and the
records-JSON assembly; do not force a generic protocol). **The rename ripple
lands whole in this task's commit** (plan-review finding 4 — a partial rename
breaks harness/skeleton/tracing imports): `grouping.py` classes + every
reference (`harness.py` kwarg/state, `tracing.py`, `skeleton.py`,
`characterise.py`, `test_characterise.py`, living docs) in one sweep, the
grep acceptance run then. Done = construction/
stub-determinism/validation/repair/no-keys-no-op tests + the full existing
suite green under the rename + the grep sweep clean. Scope: M. **Commit**
after Phase 2 verify green.

## Phase 3 — The component

### Task 5: `group.py` — `codex`

Roll-up load by `(scope, extraction_run_id)` (missing → structural failure) →
finding-set resolution + integrity cross-check → facet-value extraction →
cap check (fail closed) → budget check → partition (+ one repair) →
membership derivation → invariants → roll-up row **last** → summary in
`component.completed`. Edge scopes: zero findings → `empty_findings` flag,
zero-group row, **no backend call**; all-null facet → everything `no_value`,
`all_no_value` flag, no call (no values to partition). Done = the
invariant/edge-scope/failure-semantics test blocks. Scope: M (~250 lines).
**Commit** after Phase 3 verify green.

## Phase 4 — Wiring

### Task 6: Registry/harness/skeleton/helpers wiring — `fast-worker` (rename already landed in Task 4)

- `plan.py`: `"group": {"requires": ["evidence_scope_id",
  "extraction_run_id"]}`; `Plan`/`_ValidatedRunSpec`/`Config` gain optional
  `extraction_run_id` (required-by-registry for group; compile fails closed —
  the 011 `selection_run_id` clone).
- `harness.py`: `facet_grouping_backend` param (stub resolved inside),
  `HarnessState`, `_run_group` via `_run_scope_component` with
  `functools.partial(GroupContext, extraction_run_id=…)`; node + conditional
  edge + edge to finish.
- `skeleton.py`: group step after extract per the pinned spec.
- `tests/helpers.py`: delete order; `test_compile.py`: registry case.
  Scope: S–M. **Commit** with Phase 4.

## Phase 5 — Tests

### Task 7: Contract bulk — `fast-worker` (the contract's named-test list is the brief)

Migration roundtrip + 24 tables + constraint/CHECK/FK rejections ·
finding-set resolution (exact set, memo-reused included; foreign-run findings
never enter; integrity cross-check failure; **a mixed-status referenced run —
extracted + `no_findings` + failed docs — contributes findings from extracted
records only**, plan-review finding 7) · **no-side-effects invariants**
(plan-review finding 8: grouping writes only `grouping_result`; `source_tag`
and `intervention_outcome_finding` rows byte-identical before/after; no
consensus/verdict/evaluative keys anywhere in the row or payload,
key-name-asserted) · **single prompt surface** (one `PROMPT_VERSION`; the
repair call's built prompt carries the same system prompt + schema,
asserted) · exhaustiveness invariants (sum
identities; direction-spread sums; every finding exactly once) · validation +
repair (missing → repair → ungrouped; unknown/duplicate → rejected) ·
value identity (casefold/whitespace collapse; surface-form election) ·
no-catch-all + descriptive-labels negative rules asserted on the built prompt
· null-facet handling (`no_value` counted; all-null → no call) · facet
directive (default; override; malformed fails closed; facet+source recorded)
· mixed/unclear first-class fixtures · edge scopes (zero-findings honest
skip, no call; missing roll-up row → structural failure; same-run loud) ·
backend failure → `component.failed`, no row · determinism (two stub runs →
identical payload columns; sorted value ordering) · delete-order integrity ·
summary payload shape · provenance required keys.

### Task 8: Judgment cases — `codex`

Injection double (an injection-shaped facet value lands as inert id-keyed
data — no instruction-following, asserted on output and on the built prompt;
**no intent anywhere in the built prompt**) · cap-exceeded double (>cap
values → `value_cap_exceeded` structural failure, zero calls) · counting
double (partition called once; repair only on missing ids; no call on
empty/all-null) · misbehaving-backend doubles (duplicate ids across groups;
unknown ids; empty groups; empty/oversized/control-char/duplicate/forbidden
labels — validation rejects then repairs once; repair
still-missing → ungrouped) · socket-deny around a group round-trip · key
hygiene against captured output. Scope: M. **Commit** (tests).

## Phase 6 — Deferred + verification

### Task 9: deferred.md — `lead`

The contract's seam list: `query-findings` with synthesise — recorded as an
explicit deviation from components §8's tool table (contract rev 1.3) ·
facet-grouping quality evals (extends the 009 seam; cap calibration) ·
large-corpus grouping algorithm (beyond the fail-closed cap: tail-capable
discovery, embedding-assisted value clustering; eval-gated) · agent-authored
grouping directive · cross-schema reference-mediated linkage ·
re-grouping/steering UX ·
**facet-theme promotion** (the staged ladder; Options Assessment reads
run-referenced groupings until then). Discharge note on the 009
"`group`-component inheritance" entry (the five v2 defects: dead critique
stage — no critique stage built; silent concept drops — code-enforced
exhaustiveness; "General Theme" collapse — negative rule + honest residual;
no scale guard — value cap + two-stage; unseeded runs — deterministic
ordering/ids). `make okf-validate` green.

### Task 9b: ADR 0008 — `lead` — **at plan confirmation, NOT a build task**

`docs/adr/0008-facet-grouping-run-local.md`: the findings layer's first
reader · run-local grouping vs canonical promotion (the staged ladder;
entity-resolution bar; the characterise-tag asymmetry rationale from contract
rev 1.2) · value-grain clustering with derived membership · no-fallback
failure semantics · the theme/facet cluster-core symmetry. **Written and
Accepted at the plan 🛑, before the build conversation opens.**

### Task 10: `verification.md` + live manual run — `lead`

Per the contract's evidence list: `make verify` table; migration roundtrip +
24 tables; the named test results; live skeleton run (`OPENAI_API_KEY` +
`LANGFUSE_*` dev): real partition over the fixture extraction's findings,
invariants holding on the written row, summary rendered, trace with scores,
the second-facet (`outcome`) run as a new run, honest cost note;
public-safety confirmation (reference strings only; keys clean). **Commit**
(verification).

### Review stack (rubric box 8 — owned by conversation C, not this plan)

Per the task-cycle spine: fresh conversation, Tier-3 lanes sized per the
review-economy notes (diff well under 011's — expect ~3 finder angles or
src-subset scoping).

---

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Facet values too terse for coherent grouping (name-only clustering) | Poor groups | Counterpart context (capped) gives the pairing signal; quality is the eval seam, machinery correctness is this slice's bar |
| Value normalisation merges genuinely distinct references ("housing" vs "Housing") | Wrong memberships | Identity is deliberately conservative (casefold + whitespace only — no stemming/fuzzy); surface forms retained per group; fuzzier identity is the promotion/eval seam |
| Model returns near-partition (missing/duplicated ids) | Broken invariants | Structural validation + one targeted repair + honest `ungrouped`; invariants re-checked in code after derivation |
| Repair loop divergence | Budget overrun | Pre-run enforced budget; one repair, hard; still-missing → ungrouped, never re-asked |
| Real corpus exceeds the value cap | Component unusable at scale | Fail-closed by design (`value_cap_exceeded` names the cap + seam); the large-corpus algorithm is the recorded eval-gated seam |
| Rename ripple breaks 009 suite | Red verify | Task 4 runs the full 009 grouping suite under the rename before the component lands; mechanical sweep is one commit |
| Direction spread read as consensus | Trust leak | Counts keyed by raw `effect_direction` only; no verdict field representable; rubric item 10 |
| Cost runaway on live run | Spend | Single partition call at fixture scale; pre-call budget; cost note required |
| Injection via facet values | Hijacked labels | Values are id-keyed data; schema-constrained output; labels stored as data, rendered never executed; injection double |

## Plan-phase adversarial review — findings & adjudication (Codex, 2026-07-07)

Nine findings, verified against the repo before adoption; **9/9 adopted**:

1. Rename grep acceptance narrower than the contract (src/tests only):
   **adopted** — sweep covers `src/ tests/ docs/`, exempting historical
   records only.
2. Forbidden-label set drift (plan's seven vs contract's four): **adopted** —
   contract amended to the plan's seven-label set (minor fold, noted in the
   contract).
3. Integrity cross-check pinned to a non-existent flat key: **adopted** —
   `counts["findings"]["total"]` (as-built nested shape).
4. Task-4 rename left importers broken until Task 6 (sequencing): **adopted**
   — the whole rename ripple lands in Task 4's commit; Task 6 is wiring only.
5. Backend protocol design routed to codex (seam design is lead work):
   **adopted** — protocol signatures/semantics move to Task 2 (lead); Task 4
   implements.
6. Repair call risked a second prompt-bearing surface (blocker): **adopted**
   — repair reuses `group_facet_v1` verbatim (same version/system
   prompt/schema, missing records as data); single-prompt-surface
   test-asserted.
7. No test for mixed-status referenced runs (failed/`no_findings` docs):
   **adopted** — fixture + assertion added to Task 7.
8. Rubric item 10's no-side-effects claims untested: **adopted** —
   before/after invariants on `source_tag` and IOF rows + no-evaluative-keys
   assertion added.
9. Stray "assign batch" language survived the rev-2 scale-guard change:
   **adopted** — removed; partition + one repair is the entire call surface.

## Open questions

None blocking — design decisions are fixed in the approved contract (rev 1.2).
