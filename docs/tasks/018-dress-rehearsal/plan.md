# Plan: 018-dress-rehearsal

> **Status:** rev 2 — drafted against contract **rev 3 (approved 2026-07-10)**, then
> the contract-stage adversarial review adjudicated (Codex, 8 findings: 6 MAJOR ·
> 2 MINOR, **8/8 adopted, finding 6 partially** — repair-lane×span redesign ·
> unspanned-prose traceability check · judge test strengthened (unchanged-verdict
> sample + self-certification fixture) · "envelope-basis" wording fixed to
> no-findings-layer (ADR 0013 spine untouched) · loop bounds pinned (3 rounds/surface,
> ≤30 replays) · no-mission-vocabulary check + taxonomy desk review · key-findings
> conditional-required in rubric · rider criteria added). Contract rev 4 carries the
> folds.
> **Rev 3 — plan-stage adversarial review adjudicated (Codex, 10 findings:
> 2 BLOCKER · 6 MAJOR · 2 MINOR, 10/10 adopted).** Blockers: fork ADR + spec flow-back
> made a fork-independent lead task (B0) — an Option A win no longer loses the
> deliverable; Phase A split into A-model (constants only) → **baseline-1 capture** →
> A-rest (migration + prompt-touching riders), so baseline-1 is truly
> new-models-unchanged-prompts. Majors: judge-envelope v2 evidence (verdict-shift +
> unchanged-sample + self-cert fixture) ships WITH Phase B, gate-checked at B exit;
> key-findings block gains the explicit no-headline absence path + test owner;
> `component.timing` moves to a fresh transaction covering success AND failure attempts;
> Langfuse session = one conversation uuid minted at CLI start, threaded to planner
> traces and `component_span` (new param); effort knob re-specced as a small shared
> request-kwargs helper + fake-client test pinning the SDK literal (live-verify `xhigh`,
> fallback `high` recorded honestly); usage-return re-scoped honestly as a public
> backend-protocol signature change (all callers); judge envelope plumbing (codex) split
> from judge prompt + envelope semantics (lead) in B task rows. Minors: stale "step-6"
> labels → Phase E exit; direction-rename check scoped to effect-direction *values*
> (search-reformulate positive/negative example fields are exempt, named).
> **Fork resolved at the gate (2026-07-10 · user): OPTION B** — gather-then-author
> prose with span-anchored claims (probe evidence: [fork-probe.md](fork-probe.md)).
> **Voice posture (user, same gate): the demo voice rules are a validated LESSON, not
> a copy source** — they were written without deliberation; the writer's voice is
> re-authored deliberately at B-B2 (lead), informed by the probe + research notes,
> and validated in the C2 loop. The Option A task rows below stay
> as the recorded FALLBACK (fires only via the Phase B stop condition — invariants
> failing to re-prove). Plan 🛑 still pending (user: revisions first).
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

**Effort knob (lead-designed seam, implemented in A1; re-specced per plan-review
finding 6):** there is no shared `_call` — each backend has its own OpenAI call helper
(`classification_backend.py:90`, `screening_backend.py:107`, `extraction_backend.py:77`,
`planner.py:159`, multiple sites in `synthesis_backend.py`). So: one small shared
helper (e.g. `openai_kwargs(model, *, reasoning_effort: str | None = None) -> dict` in
a common module) that omits the key when `None`; only `classify_prompt.py` sets
`CLASSIFY_REASONING_EFFORT = "xhigh"` and only `_classify_once` passes it. A focused
fake-client test pins the emitted kwarg; **the `xhigh` literal is live-verified against
the installed SDK before adoption — if rejected, fall back to `high` and record the
substitution honestly**. Provider-neutral by shape (a Bedrock backend maps or ignores
the string). **Effort level is a hypothesis, not a setting (prompting research,
2026-07-10: reasoning effort is NOT monotonic on judgment tasks — medium has beaten
high on judging accuracy per dollar in published evals): classify@xhigh is verified
against baseline-1 classification outputs like any other change, with high/medium as
the comparison arms if it underperforms.** See
[prompting-research-notes.md](prompting-research-notes.md).

**Telemetry (A2; re-specced per plan-review findings 5 + 7):**
- *Sessions:* **one conversation uuid minted at CLI/orchestrate start**, threaded (new
  parameter) into planner tracing (`planner.py` call sites have no session argument
  today) and into `component_span` (no `session_id` param today — gains one) →
  `update_current_trace(session_id=...)`. Planner turns and every component trace of
  runs composed from that conversation share one Langfuse session.
- *Usage-return — honestly scoped as a protocol change:* the internal `_call`s return
  `(wire, usage)` but the **public backend protocols return wire objects only**
  (`ClassificationBackend.classify`, `ExtractionBackend.extract`, `SynthesisBackend`
  section methods, `GroundingJudgeBackend.judge_block`, …). The task changes those
  protocol signatures (wire → `(wire, usage)` or a usage-carrying envelope), updates
  every caller including stubs and tests, folds `{prompt,completion,total}` into
  component summary payloads (→ `component.completed`), and logs the runner's
  single-line aggregate. Discharges the 017 deferred entry.
- *Durable timing:* `_run_step_attempt`'s status write commits and exits its
  transaction before the wall-clock is final (`runner.py:1009,1108`) — so
  `component.timing` appends on a **fresh transaction after the attempt resolves,
  emitted on BOTH success and failure paths** (the failure backstop pattern), payload
  `{component, registry_component, wall_clock_s, status, usage_totals,
  headline_counts}`. `event_log.event_type` is plain text, no CHECK (verified,
  `schema.py:101`) — additive, no schema gate.
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
- Judge envelope v2 (`grounding_judge.py::build_envelope` + prompt): finding claims
  gain their verified quote's chunk text; envelope gains `intent` + `section_focus`.
  **Ownership split (plan-review finding 8): envelope plumbing = codex; the judge
  prompt text + envelope semantics (what the judge is told about the new fields) =
  lead, as a separate task row.** **Evidence timing (finding 3): the verdict-shift
  diff + unchanged-sample inspection + self-certification fixture run INSIDE Phase B
  and gate its exit — the envelope change never reaches Phase C unevidenced.**

**Blocks (B, fork-independent; conditional path per plan-review finding 4):**
key-findings block = a final post-sections emission pass over the section claim ledger
(produced last), artefact-ordered first, **conditional-required: the pass may return
"no headline claims" and then NO block is minted — the absence path is explicit,
test-owned in the same B task (a thin/landscape substrate fixture proves no forced
block)**; conclusions block = a final section with a dedicated focus ("what this
evidence amounts to against the question"), ordered last, evidence-descriptive rule in
its prompt (lead). Both are ordinary grounded blocks (annotations, citations, judge) —
no new block machinery, one new section-role field in the emission/composition path
(today no role field exists — `synthesise.py:2362` roll-up carries none).

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

**Phase A-model — model-only changes (plan-review blocker 2: nothing prompt-bearing
lands before baseline-1)**

- A1 model refresh + effort knob (table + helper above; `xhigh` SDK literal verified,
  fake-client test; demo monkeypatch retirement noted for C4). — **fast-worker**
  *(exact table; seam designed above)*

Gate: `make verify-fast` (constants + one helper; no schema/reader contact).

**Phase A′ — baseline-1 (live)** — **lead** *(the loop's reference point)*: replay
extract + synthesise on the pinned substrates with new models, **prompts byte-identical
to merged dev**; record outputs/traces. One extract replay + one synthesise replay per
project.

**Phase A-rest — remaining riders (post-baseline; prompt-touching work now safe)**

- A2 telemetry: sessions (conversation-uuid threading) + usage-return protocol change +
  fresh-transaction `component.timing` (success AND failure paths) + discover-themes
  exc. — **codex** *(multi-file signature refactor with coherence stakes;
  machine-verifiable: tests assert session ids on spans, usage in summaries, timing
  event per step incl. a fault-injected failure attempt)*
- A3 regrade: depth-table row + `FACET_VALUE_CAP` + band placeholder ("measured in
  Phase D"). — **fast-worker** *(exact constants; behaviour tests pinned: standard
  composes without select/extract/group; landscape/deep byte-identical)*
- A4 planner history message-array refactor (structure) — **fast-worker** *(mechanical
  against a pinned message shape)*; prompt-text adjustments — **lead** *(prompt-bearing)*
- A5 direction rename: migration + literal + readers + tests — **fast-worker** *(exact
  DDL/UPDATE pinned in brief; the check is "no positive/negative **effect-direction
  value** reachable" — `search_prompts.py`'s reformulate positive/negative example
  fields are a different vocabulary and exempt, plan-review finding 10)*; prompt
  wording — **lead**
- A6 country filter: grammar + wire verification tests — **fast-worker**; live
  vocabulary probe + planner prompt line — **lead** *(live judgment + prompt)*

Gate: **full `make verify`** at Phase A-rest exit (schema class — A5 migration).

**Phase B — synthesis output shape (fork-resolved at the plan 🛑)**

- B0 (fork-independent, **before B opens** — plan-review blocker 1): the fork ADR
  (evidence + decision, whichever option wins) + the two-block spec flow-back
  (capability.md + provenance-grounding.md + log entry). — **lead** *(design prose)*

*Option A (prompt-first) — STRUCK to fallback at the gate (fires only via the Phase B
stop condition):*
- B-A1 voice/ordering rules into `synthesis_backend.py` prompts (from demo evidence +
  research notes), claim-text register rules. — **lead** *(prompt-bearing)*
- B-A2 envelope default set + judge-envelope **plumbing** + section-role field +
  key-findings conditional pass (incl. the no-headline absence path + fixture) +
  conclusions section role. — **codex** *(readmodel + envelope plumbing,
  machine-verifiable)*
- B-A3 judge prompt + envelope semantics + the in-B verdict-shift/unchanged-sample/
  self-cert evidence run; key-findings + conclusions prompts. — **lead**
  *(prompt-bearing + verification adjudication)*

*Option B (gather-then-author) — DECIDED (2026-07-10 · user):*
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
  -tissue rule) + repair prompt v2, **including the deliberate voice design** (user
  pin, 2026-07-10): the demo rules are evidence of what works (register ban, analyst
  number restatement, takeaway-first) but are re-thought from scratch — audience,
  environment-context preamble (context-not-content), register, and argument/narrative
  structure designed as one coherent voice, then validated against baseline-1 in the
  C2 loop like any prompt change. — **lead** *(prompt-bearing; the slice's
  taste-bearing core)*
- B-B3 envelope default set + judge-envelope **plumbing** + the two new blocks (as
  B-A2, plus the envelope carries span context). — **codex**
- B-B4 judge prompt + envelope semantics + the in-B verdict-shift/unchanged-sample/
  self-cert evidence run; key-findings + conclusions prompts. — **lead**
  *(prompt-bearing + verification adjudication)*

Gate: **full `make verify`** at Phase B exit (reader-contact class: synthesise write
path) **+ the judge-envelope evidence recorded (finding 3) + one live synthesise
replay (the B smoke)** before Phase C opens.

**Phase C — refine-replay loop + surface (iterative; § How this slice runs)**

- C1 replay driver: small scripts to re-run extract / synthesise / planner on pinned
  inputs (the probe driver generalised). — **fast-worker** *(mechanical; the lead
  specs the substrate pins)*
- C2 the loop itself: extraction rules validation → synthesis voice on the shipped
  shape → planner (date inference, country line) — each change lead-authored, replayed,
  judged (user taste where prose; verdict-shift + unchanged-sample + self-certification
  fixture where judge), pinned or reverted; envelope A/B set adjudicated here.
  **Named loop hypothesis (user, 2026-07-10): environment-context preamble** — a short
  shared constant telling the model what Policy Atlas is, who reads its output, and
  what upstream produced its inputs, ALWAYS paired with an explicit context-not-content
  rule (pipeline vocabulary is known but banned from output — the arm-A leak is the
  evidence for the ban). Candidate surfaces in order: writer (register), extractor
  (motivates self-containedness), judge (verdict semantics, rides envelope v2);
  screen/classify excluded (dilution). Adopted per surface only on before/after replay
  evidence, like every other prompt change.
  **Bounds enforced: ≤3 rounds/surface, ≤30 live component replays total** (a running
  tally in verification.md); no-mission-vocabulary check + taxonomy desk review on
  every adopted prompt. **Loop method per the prompting research
  ([prompting-research-notes.md](prompting-research-notes.md)): every touched surface
  gets a conflict audit first; accumulated ritual/emphatic language is stripped as
  prior-generation tech debt (fresh-minimal-baseline discipline); CoT scaffolding
  deleted on reasoning-enabled surfaces; verbosity/format bounds made numeric;
  hard rules carry their motivation.** — **lead** *(prompt-bearing + adjudication)*
- C3 taxonomy pins: planner replay across the 7 v2-question categories, drawing one
  real question per category from the V2 user-question list (user-provided 2026-07-10;
  product-internal data held outside the repo — ask the owner or the lead's notes),
  **recording a per-category composition-adequacy verdict**. The bar per the owner
  posture (2026-07-10, deferred.md § Capabilities mapping): for statistics/fact-finding
  and opinions shapes — whose ideal homes are future capabilities — EB neither refuses
  nor pretends: honest intent-fit composition producing a somewhat-useful
  evidence-descriptive artefact, with NO prompt work biased toward these shapes.
  Extraction/synthesis spot-check on the non-mission project. — **lead** runs,
  **fast-worker** harness if scripting needed.
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

Gate: **full `make verify`** at Phase E exit (the mandatory final-exit class).

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
| Phase A-model exit | `make verify-fast` | constants + helper only |
| Phase A-rest exit | full `make verify` | schema migration (mandatory class) |
| Phase B exit | full `make verify` + live smoke | synthesise write-path (reader contact) |
| Phase C landings | `make verify-fast` | prompt/envelope iterations |
| Phase C exit | full `make verify` | pre-rehearsal consolidation |
| Phase E exit | full `make verify` | mandatory final-exit class |
