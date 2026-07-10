# Task contract: 018-dress-rehearsal

> **Status:** drafted (rev 2 — user feedback 2026-07-10: key-findings and conclusions are
> separate blocks; writer-envelope widening is evidence-gated not assumed; baselines come
> from the 017 slice runs with a post-model-refresh re-baseline; the output-shape change
> is a design fork, not a pre-commitment). Contract approved (before planning):
> **2026-07-10 · user (rev 3)** · Plan approved (before implementation): _pending_ ·
> ADR: due (synthesis output-shape — records the fork decision; supersedes/amends the
> 013 emission decision accordingly).

## Goal

Make the real chain's *output* demo-worthy and prove it with a live dress rehearsal on a
Nesta-mission question. The centre of gravity is the **synthesis output-shape redesign**
(the artefact must read as authored prose answering the user's intent, with the grounding
annotation layer anchored *into* that prose) plus an **iterative prompt-refine loop with
per-surface replay** — flanked by a set of small code riders (model refresh, telemetry
sweep, standard-depth regrade, direction-vocabulary rename, planner-history fix, OpenAlex
country filter).

**This is not a typical implementation slice** (user note, 2026-07-10): it is the repo's
first eval-type slice — much of the work is prompt-bearing iteration judged qualitatively
on outputs, not a single code build judged on a diff. § How this slice runs replaces the
standard build/review conventions where they don't fit; whatever loop discipline works
here flows back as the eval-slice convention.

## Deliverable

1. **Code riders** (conventional diffs, Phase A below) landed on `dev` via PR.
2. **Synthesis output quality** (Phase B): the prompt-vs-structural fork decided on
   evidence and shipped; the grounded key-findings block (produced last, shown first) and
   the separate bottom conclusions block; judge envelope v2; evidence-gated writer-envelope
   widening. ADR + spec flow-back recorded.
3. **Refined prompt surfaces** (Phase C) with before/after replay evidence per change and
   anti-overfit pins against the v2 question taxonomy.
4. **A completed dress rehearsal**: pre-run deep project + live standard run on a
   Nesta-mission question, rendered on the updated demo surface, meeting the rubric's
   quality bars.

## Read first

- [provenance-grounding](../../specs/system/provenance-grounding.md) — the annotation
  layer, gap grading, summaries, and the front door ("the 'what did it conclude' front
  door is a grounded key-findings/conclusion block, inside the grounding economy" —
  note the owner's 2026-07-10 refinement splits this into two blocks; Phase B). Any
  redesign must stay inside this spec; the spec speaks of "the prose **and its epistemic
  annotations**" — block-text-as-claim-join was a 013 implementation choice, not spec
  intent, so both fork options are spec-compatible.
- [EB capability](../../specs/capabilities/evidence-base/capability.md) +
  [components](../../specs/capabilities/evidence-base/components.md) — synthesise §,
  extract §.
- [execution-orchestration](../../specs/system/execution-orchestration.md) — depth
  gradation, steering (for the standard-depth regrade).
- `demo/RETRO.md` (branch `demo-live-run`) — locked product decisions (§2), live-run
  numbers (§4). Anecdotal prior for everything else.
- `docs/tasks/017-orchestrator/verification.md` § Review handoff — the live-run economy
  rule and 018 input list.
- ADRs 0009/0010 (synthesise composition/emission) — what the Phase B ADR supersedes.

## Scope

### Phase A — code riders (conventional)

1. **Model refresh.** `gpt-5-mini` → `gpt-5.4-mini` at every pinned constant
   (`screen_prompt.py:37`, `extract_prompt.py:34`, `grouping.py:20,25`,
   `facet_grouping.py:34`, `ranking.py:62`, `grounding_judge.py:38`,
   `search_prompts.py:38-40`). Classify (`classify_prompt.py:45`): `gpt-5.5` →
   `gpt-5.4-mini` **with reasoning effort xhigh** — no call site currently passes a
   reasoning-effort parameter, so this adds a small provider-neutral effort knob at the
   backend call layer. Synthesis writer (`synthesis_backend.py:60`): `gpt-5-mini` →
   `gpt-5.5` in src (the demo-validated choice — retires the demo monkeypatch); judge
   stays mini-class (owner call, RETRO §4); planner stays `gpt-5.5`. Model choices are
   loop-revisable only with before/after replay evidence.
2. **Telemetry sweep.** (a) Langfuse **sessions**: one session id per composed run so a
   chain is one correlated view (today: N disconnected traces sharing only metadata).
   (b) **Usage-return refactor**: stop discarding `_usage` at the ~13 call sites; land
   token counts in `component.completed` payloads + a runner-line aggregate (discharges
   the 017 "runner-visible usage aggregate" deferred item). (c) **Durable timing**:
   persist per-component wall-clock + headline in/out counts at the runner seam
   (`runner.py` step-attempt completion; event payload, no schema change) — the
   time-estimate *model* stays deferred, the data starts accruing now. (d) Persist
   `str(exc)` from `_discover_themes` validator rejections (recorded 015 gap).
   (e) Assess (don't adopt by default) prompt-registry/datasets — likely eval-slice.
3. **Standard-depth regrade.** `ANALYSIS_DEPTH_TABLE` standard row: `deep_chain=False`
   — select/extract/group become deep-only. **The ADR 0013 mandatory spine is untouched**
   (adversarial finding 4): standard still runs acquire → screen → classify → appraise →
   ingest → stage-2 → characterise → synthesise; full-text chunks remain citable;
   what standard drops is only the **findings layer** (no extracted findings, so
   synthesis grounds in chunks + characterisation — never "envelope-basis absent
   ingest", which ADR 0013 rejected). Re-seed
   `TIME_BANDS[("standard","standard")]` from a fresh measured run (target ~15–20 min;
   displayed-band-is-measured discipline). `FACET_VALUE_CAP` 150 → 400 (demo-validated at
   live scale: 280 distinct values, 19 coherent groups) — retires the second demo
   monkeypatch; eval slice still owns final calibration.
4. **Planner history fix.** Replace the JSON-blob-in-one-user-message shape
   (`planner_prompt.py:222-271`) with native message arrays — **provider-neutral by
   constraint** (no OpenAI `previous_response_id`/server-side state; Bedrock migration is
   queued post-eval and must not be deepened against). Keep turn bounding, sanitisation
   and the anti-injection framing for any pasted third-party text.
5. **OpenAlex country filter.** It exists (user-verified) — the prior assumption it
   didn't is wrong. Add the wire-verified vocabulary to the `scope_filters` grammar +
   planner prompt. Also close 017's open item: verify Overton's `publisher_country`
   filter key against a live filtered search.
6. **Direction-vocabulary rename** (⚠️ schema gate): `EFFECT_DIRECTIONS`
   `positive`/`negative` → `increase`/`decrease` (`no_effect`/`mixed`/`unclear`
   unchanged) — observational, not evaluative. One migration (rewrite `ck_iof_direction`
   + data `UPDATE` on existing rows), the `EffectDirection` literal, extraction prompt
   examples/guidance, spread readers pass through untouched (they iterate the tuple).

### Phase B — synthesis output quality (the core; design fork + ADR)

**The problem, honestly stated with both bodies of evidence.** The as-built structure is
claims-are-the-prose: block text is literally the `\n\n` join of independently validated
claim texts (`synthesise.py:2182`), the writer is forbidden free prose, and no field
exists for connective tissue — a structural ceiling on authored narrative. *But* the
demo branch's prompt-level changes alone (voice rules + gpt-5.5 writer, decisions made
fast and not thought through) produced a report the owner judged quite good. So whether
the ceiling actually binds at the quality bar is an open question, and the redesign is a
**fork decided at the plan step, not a contract pre-commitment**:

- **Option A — prompt-first, structure kept.** Claim texts written as flowing,
  takeaway-first prose; ordering guidance; the demo voice rules carried into src;
  possibly softer joins. Cheapest; annotation layer unchanged by construction.
- **Option B — gather-then-author prose, claims as spans.** Shape pinned by the
  product posture (user, 2026-07-10): grounding IS the product, so **write-then-attribute
  (Anthropic-CitationAgent-style post-hoc citation retrofit) is disfavoured as the
  primary mechanism** — a claim that exists before its evidence is found is the
  `unsupported_mis_cited` class by construction. Option B's correct form is
  PaperQA2-shaped and already half-built: the section loop's **gather phase stays as
  is** (`search_chunks`/`query_findings` turns collect evidence units first); the writer
  then authors section prose *over the gathered units*, anchoring typed claims as
  **char-offset spans into that prose** as it writes (`addressable_unit` locators
  already carry start/end — no DB migration expected); span-binding validated
  deterministically (exact substring). **Repair lane v2 (adversarial finding 1):** the
  current repair rewrites failing claim objects only — under spans that breaks the text
  the offsets point into, so Option B redesigns repair to rewrite the failing claim's
  prose segment *in place*, re-bind its span, recompute downstream offsets, and re-run
  span validation on the repaired section; salvage lanes preserved. **Unspanned-prose
  traceability (adversarial finding 2):** the spec's traceability rule covers every
  significant statement, not just emitted claims — so the judge lane additionally
  receives the full section prose + span map and flags evidential assertions outside
  any claim span (`unspanned_assertion`, flag-not-drop); connective tissue is what
  survives that check, not what avoids it. Structurally removes the ceiling; more
  machinery, and the annotation layer must be re-proven.

**Fork protocol (plan step):** (1) cheap probe first — replay the demo-branch prompt
approach on a recorded 017 substrate with the Phase A models and judge whether the
residual gap to the quality bar is structural or prompt-reachable; (2) web research on
attributed report generation (prose-first vs claim-first, attribution-vs-fluency
evidence) feeds the same decision; (3) options laid out side by side (Artifact) with
pros/cons for **both prose quality and annotation-layer quality**; (4) user decides at
the plan 🛑. The ADR records the fork, the evidence, and the decision — superseding or
amending 013's emission decision accordingly.

**Invariant under either option**: per-type deterministic validators, judge lanes
(finding/chunk/reasoning), pattern-count recomputation, gap grading + coverage base,
flag-not-drop, honesty flags, verified-verbatim citations all survive unweakened. Under
Option B, prose outside claim spans is connective tissue and must carry no evidential
assertion — the judge rubric owns that line.

**Independent of the fork, Phase B also lands:**

- **Two new block kinds, per spec + owner direction (2026-07-10) — distinct blocks,
  never merged:**
  - **Grounded key-findings block** — the headline evidence claims at their appropriate
    grade, cited to sources, **produced last, shown first** (capability spec § artefact:
    production ≠ presentation), conditional-required (present iff headline claims are
    made), distinct from the citation-free artefact summary.
  - **Conclusions block** — sits at the **bottom** of the report: what this evidence
    amounts to against the user's question. Evidence-descriptive per the EB scope rule —
    **no recommendations / decision-answer content**. Grounded, cited to sources, never
    to sibling blocks. *Spec refinement rides this slice*: the written specs carry the
    key-findings block but no separate bottom conclusions block (only
    provenance-grounding's compound "key-findings/conclusion block" phrase) — the
    two-block structure is an owner decision (2026-07-10) flowing back into
    capability.md + provenance-grounding.md with a log entry.
- **Judge envelope v2 — evidence-gated with a verification-grade test (user,
  2026-07-10; strengthened per adversarial finding 3).** Candidate additions: for
  finding claims the finding's verified source quote *and its chunk text*, plus the
  intent/section focus (today the judge is blind to the question). The judge is a
  **verification surface**, so its A/B is not output taste: replay the same claim set
  through both envelopes, diff the verdict distributions, **hand-inspect every flipped
  verdict** (watching for intent-induced leniency), **plus a stratified sample of
  unchanged verdicts per lane** (flips alone miss unchanged-but-wrong), **plus a
  scripted adversarial fixture** for the recorded 013 self-certification case (a chunk
  whose text instructs the judge to up-tier claims citing it must not sway the verdict —
  mandatory here because envelope v2 feeds the judge *more* chunk text). Full judge
  calibration remains eval-workstream property; this is the honest 018-level check.
- **Writer envelope widening — default set + A/B set (user, 2026-07-10).**
  *Default-adopt* (PaperQA2-precedented + the product's own quality ladder):
  publication year · evidence type · **appraisal label** (our journal-quality analogue,
  done properly) · venue/publisher · cited-by count · **`is_retracted`** as a visible
  flag (flag-not-block — gives the recorded retained-but-unread field its first reader).
  *A/B-gated* (adopted per replay evidence): **author institution(s)** (first in the
  queue) · FWCI · further fields the loop suggests. All fields terse, structured, and
  attached **adjacent to the evidence unit they describe** (never mid-context bulk — the
  measured distraction shape). Rationale + evidence in
  [synthesis-research-notes.md](synthesis-research-notes.md); the noise question has no
  controlled literature answer, so the A/B set stays experimental by design.
- **Slice-wide prompt-change discipline (generalised from the loop rule):** every LLM
  prompt or envelope change on any surface in this slice ships with before/after replay
  evidence on pinned inputs — **generation surfaces judged on output quality,
  verification surfaces on verdict-shift inspection**. This is the pattern that flows
  back as the eval-slice convention.

### Phase C — refine-replay loop + rehearsal

- **Baselines — two-stage (user pin, 2026-07-10).** *Baseline-0*: the most recent runs
  from the **017 slice itself** (dev-DB project `91d2d684`, the composed live run, plus
  the first-attempt project `128c0a81`, with their Langfuse traces) — NOT the
  demo-branch runs. These predate the Phase A model refresh, so they are the historical
  reference only. *Baseline-1* (the true loop baseline): after Phase A lands, replay the
  same substrates on the new models with unchanged prompts — every prompt refinement is
  judged against baseline-1, so model effects and prompt effects are never conflated.
- **Loop protocol** per surface: change (lead-authored) → **per-component replay** on
  pinned inputs (extract on the same selected docs; synthesise on the same substrate) →
  judge (user taste + lead) → pin or revert. Full composed live runs are NOT the loop
  unit (017 live-run economy rule carries over: ~40 min + spend needs a specific
  question a replay can't answer). **Bounds (adversarial finding 5):** at most **3
  refinement rounds per surface** against the same quality bar — a surface not
  converging by round 3 stops and re-scopes rather than iterating (the bounded-repair
  philosophy applied to the loop itself); the loop's total live-replay budget is
  **≤ 30 component replays** (baselines, fork probe, B smoke, D-phase runs excluded);
  either bound breached = the stop condition fires.
- **Surfaces in the loop**: extraction rules (validating the RETRO's never-validated
  fixes: self-contained naming, expanded acronyms, no hortatory statements, concrete
  outcomes), synthesis prose/voice on the new shape, planner (incl.
  publication-date-range inference from intent/topic).
- **Anti-overfit pins**: each refined prompt is checked against at least one question
  per v2-question-taxonomy category (7 categories) at planner level, and
  extraction/synthesis spot-checks run on the *other* recorded project (different
  intent) — refinements must not encode the mission question. **Strengthened
  (adversarial finding 6, adopted partially):** every refined extraction/synthesis
  prompt additionally passes (a) a deterministic no-mission-vocabulary check (the
  prompt text contains no question-specific terms) and (b) a recorded desk review of
  each rule against the 7 taxonomy question *shapes* (would this rule misfire on a
  what-works / landscape / comparative / … question?). Full per-category chain runs for
  extraction/synthesis are eval-slice scale, not 018 — recorded as a known limit in
  verification.md.
- **Contingent: extraction junk judge.** Built ONLY if post-refresh replay still shows
  junk findings (the RETRO's "next lever"). One new lead-authored prompt surface on the
  approved OpenAI route (pre-approved at this gate, bounds: post-extract filter,
  flag-not-drop — junk findings are flagged/excluded with honest accounting, never
  silently dropped).
- **Rendering surface**: `demo-live-run` branch updated (merge dev; retire the model/cap
  monkeypatches as the src riders land), key-findings block rendered first and the
  conclusions block at the report foot, planner-turn progress/streaming (planner runs
  ~20–30 s/turn). This is the throwaway demo surface, not a production front-end — the
  **frontend-scaffold gate is untouched**.
- **Dress rehearsal** (terminal check): morning-of deep pre-run + live standard run on a
  Nesta-mission question on the updated surface, inside the re-seeded standard band.

## Out of scope

- **Bedrock migration** — infra ready on the DevOps side (2026-07-10) but sequenced
  **after the eval slice** (the regression net for a model-family swap); 018's only
  obligation is the no-deepening constraint in Phase A.4. Recorded in deferred.md.
- **screen/screen_stage2 rename** (`screen_abstract`/`screen_full`) — DB already stores
  integers; the rename touches only plan-vocabulary strings + persisted plan/event
  payloads. Cosmetic, UI never shows component names. Deferred.
- **RAG-based findings layer for quick runs** — legitimate only as an explicit
  coverage-base rung (retrieval-scoped extraction was declined for exactly the
  false-absence risk); needs its own design gate. Recorded in deferred.md.
- **Direct plan editing on the right pane** (edit → sync to planner → confirm) — web-app
  slice. Recorded in deferred.md.
- **Characterise-outputs → facet-grouping hints; mapper-produced per-document open
  tags** — eval-gated quality changes; the second aggravates the recorded
  tag-fragmentation trigger. Deferred.
- **Time-estimate model** — data accrual starts in Phase A.2(c); the model is eval work.
- The eval harness proper; everything else in deferred.md.

## Constraints & approval gates

- **Schema** ⚠️: the direction-rename migration (Phase A.6) — approved by approving this
  contract. No other DB change expected (Phase B uses existing locators; if the design
  step finds otherwise, that's a stop condition).
- **Egress**: no new egress class. All LLM surfaces stay on the approved OpenAI route;
  prompt changes are edits to already-approved surfaces; the contingent junk judge is one
  new prompt surface on the same route, pre-approved above with named bounds.
- **Dependencies / CI / prod config / public interfaces**: none expected.
- **Frontend scaffold gate**: untouched (demo branch only).
- **Provider-neutrality**: nothing new couples to OpenAI-specific API surface (A.4).

## Public / private boundary

Prompts, code, ADR, contract docs: committable. Live-run content (Nesta-mission outputs,
dev-DB rows, Langfuse traces): private — verification cites project ids/trace pointers,
never content. Demo sidecar registry stays on the demo branch.

## Model route

OpenAI (approved v3.0 route). Models per Phase A.1. **Prompt-bearing work is lead-only**:
extraction rules, synthesis system/repair prompts, judge prompt + envelope, planner
prompt. Mechanical volume (constant sweeps, telemetry plumbing, migration boilerplate)
delegates per the routing ladder.

## How this slice runs (task-cycle deviations, recorded)

- **Phases replace the single build**: A (riders — conventional build/verify), B
  (redesign — design-heavy, ADR), C (loop + rehearsal — iterative, judged on outputs).
  A and B are ordinary diffs and get the normal review stack (per review-stack economy:
  `/code-review` medium, one security lane, contract verifier). C's prompt iterations
  are **reviewed by before/after replay evidence, not code-review lanes** — the review
  stack sees the final prompt state + the evidence trail in verification.md.
- **Verification is partly qualitative**: the rubric names judgeable bars; the user is
  the taste judge (CEO-proxy stands in the RETRO; the user directly here).
- **The rehearsal is the terminal acceptance check** — an event with recorded evidence
  (timings, artefact id, trace pointers, surface screenshots), not a diff.
- Whatever loop protocol survives contact becomes the eval-slice convention (flow-back
  note in verification.md).

## Stop conditions

- Phase B needs a real schema change → stop, reopen the gate.
- Standard-without-findings-layer synthesis proves dishonest or empty on live corpora →
  stop, re-adjudicate the regrade (fallback: keep deep_chain at standard, accept the
  band).
- A loop bound breaches (3 rounds/surface · 30 replays total) → stop and re-scope.
- A grounding invariant can't survive the chosen Phase B option without weakening → stop
  (for Option B that includes the annotation layer failing to re-prove on replay).
- Prompt-refine loop stops converging (taste bar not met after bounded rounds) → stop and
  re-scope rather than overfit.
- Any other approval gate, or budget spent.

## Acceptance checks

- `make verify` green (A, B land test-covered: span-binding validators, regrade table,
  migration round-trip, effort knob, planner message shape).
- **Live-check scope (contract-time pin)**: per-surface replays on recorded projects
  (cheap, the loop unit) · ONE fresh composed standard run to re-seed the band (~15–20 min
  target) · the rehearsal itself (deep pre-run ~90 min wall, scheduled morning-of + live
  standard run). No other full e2e runs without a specific question replays can't answer.
- Taxonomy pins: planner replay across the 7 v2-question categories recorded.
- Rubric bars (rubric.md) hold on the rehearsal output.

## Verification evidence expected

Baseline + before/after replay evidence per refined prompt (trace pointers) · migration
up/down evidence · regrade timing measurement → band re-seed · rehearsal record (project
id, artefact id, wall-clock, surface state) · taxonomy-pin results · monkeypatch
retirement noted on the demo branch · known gaps → deferred.md · flow-back note on the
loop protocol for the eval slice.

## Risk tier & review focus

**Tier 3** — schema migration + prompt-bearing changes on egress surfaces. Review focus:
grounding/provenance integrity through the Phase B redesign (the annotation layer must
not weaken), migration correctness, honest bands/labels, scope creep in Phase C (the
loop invites it), no silent OpenAI-coupling. Review economy per the standing rule:
`/code-review` medium, one security lane, per-angle diff scoping; Phase C prompts
reviewed by evidence trail.
