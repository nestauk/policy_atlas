# Plan: 018-dress-rehearsal

> **Status:** rev 2 — drafted against contract **rev 3 (approved 2026-07-10)**, then
> the contract-stage adversarial review adjudicated (Codex, 8 findings: 6 MAJOR ·
> 2 MINOR, **8/8 adopted, finding 6 partially** — repair-lane×span redesign ·
> unspanned-prose traceability check · judge test strengthened (unchanged-verdict
> sample + self-certification fixture) · "envelope-basis" wording fixed to
> no-findings-layer (ADR 0013 spine untouched) · loop bounds pinned (3 rounds/surface,
> ≤30 replays) · no-mission-vocabulary check + taxonomy desk review · key-findings
> conditional-required in rubric · rider criteria added). Contract rev 4 carries the
> folds. Plan 🛑 pending.
> The **Phase B fork is decided AT the plan 🛑** — the probe (§ Fork probe) runs during
> this design phase so the gate has its evidence; this plan therefore carries BOTH
> options' task shapes, one of which is struck at approval.
> Contract: [contract.md](contract.md) · research:
> [synthesis-research-notes.md](synthesis-research-notes.md).

Executor routing per harness.md § Agent-side model routing: default = delegate; every
`lead` mark carries a justification. Standing Codex-exhaustion fallback: re-route down
the ladder, record substitutions in verification.md, never stall. **This slice's
prompt-bearing surfaces (extraction rules, synthesis system/repair prompts, judge
prompt, planner prompt) are lead-only throughout — including in the Phase C loop.**

## Plan-pinned design decisions

**Model refresh table (task A1):**

| Constant | File:line | Now | Becomes |
|---|---|---|---|
| `SCREEN_MODEL` | `screen_prompt.py:37` | gpt-5-mini | gpt-5.4-mini |
| `CLASSIFY_MODEL` | `classify_prompt.py:45` | gpt-5.5 | gpt-5.4-mini **+ effort xhigh** |
| `EXTRACTION_MODEL` | `extract_prompt.py:34` | gpt-5-mini | gpt-5.4-mini |
| `DISCOVERY_MODEL` / `ASSIGNMENT_MODEL` | `grouping.py:20,25` | gpt-5-mini | gpt-5.4-mini |
| `FACET_GROUPING_MODEL` | `facet_grouping.py:34` | gpt-5-mini | gpt-5.4-mini |
| `RERANK_MODEL` | `ranking.py:62` | gpt-5-mini | gpt-5.4-mini |
| `JUDGE_MODEL` | `grounding_judge.py:38` | gpt-5-mini | gpt-5.4-mini |
| `SEARCH_*_MODEL` ×3 | `search_prompts.py:38-40` | gpt-5-mini | gpt-5.4-mini |
| `SYNTHESIS_MODEL` | `synthesis_backend.py:60` | gpt-5-mini | **gpt-5.5** (demo-validated; retires demo monkeypatch) |
| `PLANNER_MODEL` | `planner.py:36` | gpt-5.5 (env) | unchanged |
| `EMBEDDING_MODEL` | `embeddings.py:33` | text-embedding-3-small | unchanged |

**Effort knob (lead-designed seam, implemented in A1):** an optional
`reasoning_effort: str | None = None` module constant per prompt module (only
`classify_prompt.py` sets one: `CLASSIFY_REASONING_EFFORT = "xhigh"`), threaded as a
plain optional kwarg through the backend `_call` into the OpenAI request. Provider
-neutral by shape (a Bedrock backend maps or ignores the string); no global config
object, no per-call plumbing beyond the modules that set it.

**Telemetry (A2):**
- *Sessions:* the runner mints one correlation id per composed run (the plan row id)
  and passes it into `component_span` → `update_current_trace(session_id=...)`; all
  component traces of one chain group under one Langfuse session. Planner conversation
  traces join the same session once a plan row exists.
- *Usage-return:* backend `_call`s already return `(wire, usage)`; the ~13
  `_, _usage =` discard sites (explorer-mapped) start returning usage up through the
  public backend methods; components fold `{prompt,completion,total}` into their
  summary payloads (→ `component.completed`); the runner logs a single-line aggregate.
  Discharges the 017 deferred entry.
- *Durable timing:* at `runner.py::_run_step_attempt` completion (wall-clock in hand,
  `runner.py:1106`), append one additive event per step — `component.timing`,
  payload `{component, registry_component, wall_clock_s, usage_totals, headline_counts}`
  — on the runner's transaction. Additive event type, no schema change (task brief
  verifies no event-type CHECK constrains the vocabulary; if one exists → stop
  condition, schema gate).
- *`_discover_themes`*: persist `str(exc)` into the rejection log line + provenance.

**Standard regrade (A3):** `ANALYSIS_DEPTH_TABLE["standard"]` → `deep_chain=False`,
`selection_budget=None` (select/extract/group become deep-only). The ADR 0013 spine is
untouched — standard keeps ingest + stage-2; synthesise grounds in full-text chunks +
characterisation without the findings layer (the landscape path's proven no-findings
shape, plus stage-2 citable full text). `TIME_BANDS[("standard","standard")]` re-seeded
from the fresh measured run in Phase D (displayed-band-is-measured). `FACET_VALUE_CAP`
150 → 400 (demo-validated at 280 live values; eval slice owns final calibration).

**Planner history (A4):** `build_planner_messages` emits a true message array
(`user`/`assistant` roles per turn) instead of the JSON-blob-in-one-user-message;
`PLANNER_HISTORY_TURNS_MAX` bounding + sanitisation + the data-not-instructions framing
for pasted third-party content all preserved; previous plan draft stays a structured
data attachment on the latest turn. No server-side conversation state (Bedrock
constraint). Prompt wording changes = lead.

**Direction rename (A5, the approved migration):** `EFFECT_DIRECTIONS` →
`("increase","decrease","no_effect","mixed","unclear")` (`schema.py:596`); migration =
data `UPDATE` (positive→increase, negative→decrease) + `ck_iof_direction` swap;
`EffectDirection` literal (`extraction_records.py:30`, the schema-parity assert keeps
them locked); `extract_prompt.py` examples + guidance (lead wording); the
synthesis-prompt enum re-description (`synthesis_backend.py:271`, lead); spread readers
iterate the tuple and pass through untouched (test-pinned).

**OpenAlex country filter (A6):** wire-verify the filter key
(`authorships.institutions.country_code` family) against the live API; add to the
`scope_filters` grammar under `openalex` (fail-closed vocabulary, the 015 pattern);
planner prompt gains the capability line (lead); close 017's Overton
`publisher_country` verification in the same probe.

**Writer/judge envelopes (B, fork-independent):**
- `_finding_record` + `_result_for_chunk` (`synthesis_tools.py`) gain the default
  metadata set: `year` · `evidence_type` · `appraisal_label` · `venue` · `cited_by` —
  terse fields on the existing records, sourced from the envelope snapshot +
  classification/appraisal rows (year already queried at `synthesis_tools.py:608`,
  currently dropped). `is_retracted` deliberately NOT surfaced (user strike,
  2026-07-10 — screening-side home, deferred.md). A/B-set fields (author institution,
  FWCI) land behind the same record shape only when their A/B passes.
- Judge envelope v2 (`grounding_judge.py::build_envelope` + prompt, lead): finding
  claims gain their verified quote's chunk text; envelope gains `intent` +
  `section_focus`. Shipped only with the verdict-shift protocol evidence (contract).

**Blocks (B, fork-independent):** key-findings block = a final post-sections emission
pass over the section claim ledger (produced last), artefact-ordered first; conclusions
block = a final section with a dedicated focus ("what this evidence amounts to against
the question"), ordered last, evidence-descriptive rule in its prompt (lead). Both are
ordinary grounded blocks (annotations, citations, judge) — no new block machinery, one
new section-role field in the emission/composition path.

## Fork probe (runs pre-🛑; evidence for the gate)

Replay synthesise on the 017 substrate (project `91d2d684`, existing
selection/grouping/characterisation references) with (a) as-built prompts, (b) the
demo-branch voice rules + gpt-5.5 writer (the demo combo), via a scratch driver that
monkeypatches `SYNTHESIS_MODEL` (the demo's own method). Judge output against the
quality bar: does prompt-only produce an *authored answer* or a *well-written list*?
Judged by lead + user; result + artefact texts recorded in
`fork-probe.md`. Cost: two synthesise runs ≈ 2 × 10–17 min wall, single-digit dollars.
(Delta noted: judge model is still 5-mini at probe time — acceptable, the probe judges
writer output shape, not verdicts.)

## Tasks

**Phase 0 — build-open baseline (full `make verify`) + baseline-0 record** —
**lead** *(operational)*: verify green on branch; record baseline-0 pointers (017
projects `91d2d684` / `128c0a81`, trace ids, artefact ids + exported block texts into
the private scratch dir — NOT committed).

**Phase A — riders**

- A1 model refresh + effort knob (table above; retire demo monkeypatch note left for
  the demo-branch task C4). — **fast-worker** *(exact table; seam designed above)*
- A2 telemetry: sessions + usage-return + `component.timing` + discover-themes exc.
  — **codex** *(multi-file signature refactor with coherence stakes; machine-verifiable:
  tests assert session ids on spans, usage in summaries, timing event per step)*
- A3 regrade: depth-table row + `FACET_VALUE_CAP` + band placeholder ("measured in
  Phase D"). — **fast-worker** *(exact constants; behaviour tests pinned: standard
  composes without select/extract/group; landscape/deep byte-identical)*
- A4 planner history message-array refactor (structure) — **fast-worker** *(mechanical
  against a pinned message shape)*; prompt-text adjustments — **lead** *(prompt-bearing)*
- A5 direction rename: migration + literal + readers + tests — **fast-worker** *(exact
  DDL/UPDATE pinned in brief)*; prompt wording — **lead**
- A6 country filter: grammar + wire verification tests — **fast-worker**; live
  vocabulary probe + planner prompt line — **lead** *(live judgment + prompt)*

Gate: **full `make verify`** at Phase A exit (schema class — A5 migration).

**Phase A′ — baseline-1 (live)** — **lead** *(the loop's reference point)*: replay
extract + synthesise on the pinned substrates with new models, unchanged prompts;
record outputs/traces. One extract replay + one synthesise replay per project.

**Phase B — synthesis output shape (fork-resolved at the plan 🛑)**

*If Option A (prompt-first):*
- B-A1 voice/ordering rules into `synthesis_backend.py` prompts (from demo evidence +
  research notes), claim-text register rules. — **lead** *(prompt-bearing)*
- B-A2 envelope default set + judge envelope v2 + section-role field for the two new
  blocks. — **codex** *(readmodel + envelope plumbing, machine-verifiable)*

*If Option B (gather-then-author):*
- B-B1 emission wire v2: `SectionProseWire` (prose + claims with `span: {start,end}`),
  span-binding validator (exact substring, fail-closed, salvage lanes preserved),
  `_write_section` binds units to spans instead of computing joins; **repair lane v2**
  (adversarial finding 1): repair rewrites the failing claim's prose segment in place,
  re-binds its span, recomputes downstream offsets, re-validates the section; and the
  **unspanned-prose judge check** (finding 2): full section prose + span map to the
  judge lane, `unspanned_assertion` flag, flag-not-drop. — **codex** *(the slice's core
  mechanism; done = the invariant test list: every 013 validator/judge/flag behaviour
  green on the new wire, span round-trip property tests, repair-offset property test,
  unspanned-assertion fixture)*
- B-B2 writer prompt v2 (authored-prose instructions over gathered units, connective
  -tissue rule) + repair prompt v2. — **lead** *(prompt-bearing)*
- B-B3 envelope default set + judge envelope v2 + the two new blocks (as B-A2, plus
  judge envelope carries the span context). — **codex**
- B-B4 fork ADR (drafted at the gate by lead, committed before B opens) + spec
  flow-back: capability.md/provenance-grounding.md two-block refinement + log entry.
  — **lead** *(design prose)*

Gate: **full `make verify`** at Phase B exit (reader-contact class: synthesise write
path). Plus one live synthesise replay (the B smoke) before Phase C opens.

**Phase C — refine-replay loop + surface (iterative; § How this slice runs)**

- C1 replay driver: small scripts to re-run extract / synthesise / planner on pinned
  inputs (the probe driver generalised). — **fast-worker** *(mechanical; the lead
  specs the substrate pins)*
- C2 the loop itself: extraction rules validation → synthesis voice on the shipped
  shape → planner (date inference, country line) — each change lead-authored, replayed,
  judged (user taste where prose; verdict-shift + unchanged-sample + self-certification
  fixture where judge), pinned or reverted; envelope A/B set adjudicated here.
  **Bounds enforced: ≤3 rounds/surface, ≤30 live component replays total** (a running
  tally in verification.md); no-mission-vocabulary check + taxonomy desk review on
  every adopted prompt. — **lead** *(prompt-bearing + adjudication)*
- C3 taxonomy pins: planner replay across the 7 v2-question categories; extraction/
  synthesis spot-check on the non-mission project. — **lead** runs, **fast-worker**
  harness if scripting needed.
- C4 demo surface: merge dev into `demo-live-run`, retire monkeypatches, render
  key-findings first + conclusions foot, planner-turn progress. — **codex** *(bounded
  frontend/server work on the throwaway branch; scaffold gate untouched)*
- C5 contingent junk judge — ONLY on trigger (post-refresh replay still junky):
  prompt + wiring **lead**, plumbing **fast-worker**; flag-not-drop accounting pinned
  in the contract.

Gate: `make verify-fast` per loop landing; **full `make verify`** at Phase C exit.

**Phase D — measured band + rehearsal (live)** — **lead**
- D1 one fresh composed standard run → re-seed `TIME_BANDS` standard×standard; verify
  ~15–20 min target or record honestly and adjudicate.
- D2 rehearsal: morning-of deep pre-run (~90 min wall) + live standard run on the
  Nesta-mission question on the surface; record per rubric 23–25.

**Phase E — records** — spec flow-back commit (if not landed at B-B4), deferred.md
sweep, verification.md, loop-protocol flow-back note. — **lead** writes judgments,
**fast-worker** mechanical sweeps.

Gate: **full `make verify`** at step-6 exit (mandatory class).

## Live-check script (contract pin, restated)

Per-surface replays on recorded projects (the loop unit — extract ≈ minutes,
synthesise ≈ 10–17 min each) · fork probe (2 synthesise replays, pre-🛑) · baseline-1
(one extract + one synthesise replay × 2 projects) · B smoke (one synthesise replay) ·
D1 one composed standard run (~15–20 min target) · D2 rehearsal (deep pre-run ~90 min,
scheduled; live standard run). Planner-only probes: pennies, unrestricted. NO other
full e2e runs without a question replays can't answer.

## Review-stack sizing (conversation C)

Medium `/code-review`, per-angle scoping: A2 telemetry refactor · A5 migration ·
B emission/validator path (the deep angle) · C4 demo-branch diff EXCLUDED (throwaway
branch, never merges — reviewed only for secrets/egress hygiene). **One** security
lane headlined by: prompt-injection posture of the new/changed prompt surfaces (planner
message-array refactor especially), span-binding validator fail-closed completeness
(Option B), migration data-rewrite correctness. Contract-verifier fresh-context.
Prompt surfaces reviewed by evidence trail, not code lanes (contract § How this slice
runs). Budget ≤250K reasoning / ≤500K fast-worker; scripted-IO fixtures and replay
scripts excluded from review diffs.

## Gate consolidation summary

| Boundary | Gate | Why |
|---|---|---|
| Phase 0 open | full `make verify` | mandatory baseline class |
| Phase A exit | full `make verify` | schema migration (mandatory class) |
| Phase B exit | full `make verify` + live smoke | synthesise write-path (reader contact) |
| Phase C landings | `make verify-fast` | prompt/envelope iterations |
| Phase C exit | full `make verify` | pre-rehearsal consolidation |
| Step-6 exit | full `make verify` | mandatory class |
