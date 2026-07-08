# Task contract: 014-llm-screen-classify

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md);
specs in [docs/specs/](../../specs/index.md).

> **Status:** **approved rev 1.5.1 → adjudicated rev 1.6** — Codex review 10/10 adopted; two ⚑ remedies (title-only unanimity-to-exclude · ≥2-rep quorum) USER-CONFIRMED 2026-07-08; planning (step 3) in progress.
>
> Contract approved (before planning): **2026-07-08 · Shabeer Rauf**
> (rev 1.5.1, covering the gated changes: runtime egress on two
> generation surfaces across two models [`gpt-5-mini` screen ×3 reps ·
> judgment-class classify, id plan-pinned] · `run_harness` gains
> `screening_backend` + `classification_backend` · one migration:
> `ck_stag_tag_type` CHECK widen + `uq_ssr_scope_source` → partial
> unique index) ·
> Plan approved (before implementation): _pending_ · ADR: _expected — first
> product read of third-party corpus text; injection posture enforcement._
>
> **Revision history:**
> - **rev 1** (2026-07-08): initial draft. Sequencing context: the post-013
>   design conversation adjudicated the live-demo path ahead of the eval
>   slice — 014 LLM screen+classify → 015 live search → 016 live
>   fetch/ingest → 017 demo dress-rehearsal → eval slice (measuring the
>   real pipeline, not the stubs). The 011-era condition ("stub-swap waits
>   for a live-demo milestone") has fired.
> - **rev 1.1** (2026-07-08, user gate challenges): **(a) three-way wire
>   vocabulary for screen** — the model may answer `unsure`; code maps it
>   to `relevant` at capped-low confidence (recall-preserving by
>   construction), counted + event-recorded; `unsure` is deliberately NOT
>   a status value (decision 3, amended). **(b) screen-failure retry
>   semantics pulled in-slice** — the deferred "recovery loop" entry's own
>   condition ("until a real inference provider makes failure transient")
>   fires in this slice; `uq_ssr_scope_source` becomes a partial unique
>   index excluding `failed` (the 011 extraction-memo precedent), so
>   re-runs retry failed docs as new rows with attempt history preserved
>   (decision 5, amended; schema gate grows within the same migration).
> - **rev 1.2** (2026-07-08, external validation round — /last30days field
>   scan, raw file `~/Documents/Last30Days/llm-abstract-screening-and-
>   document-classification-for-evidence-synthesis-raw-v3.md`).
>   **Validated as designed, no change** (citations added in place):
>   recall-first posture + accuracy-misleads-at-screening
>   (LLM4SCREENLIT, arXiv 2511.12635); **unsure → referred-back positive
>   is the published recommendation verbatim** (same paper — the rev-1.1
>   mapping is field-endorsed); confidence stored-never-trusted, single-
>   model calibration consistently weak (OLIVER, arXiv 2512.20022);
>   mini-class models validated for screening sensitivity (PMC12873614);
>   closed single-label + honest Unknown matches observed per-element
>   accuracy variance (PMC12407223); prompt wording is a control surface
>   (MDPI Info 16(5):378 — reinforces PROMPT_VERSION discipline).
>   **Adopted**: (a) **wire-level `reason` field** on both components
>   (≤ 240 chars, the select-rerank bound) — recorded in event payload +
>   Langfuse trace, NOT a column; enables the borderline review below
>   and Mäntylä-style disagreement autopsies (decision 3/4 amended);
>   (b) **live-check variance probe + borderline review** — screening's
>   decision variance measured (second run over the same corpus, flip
>   rate reported) and the lowest-confidence band read with reasons
>   (Mäntylä: focus validation on borderline cases) (decision 10, new).
>   **Recorded as seams, not built**: screening consensus/ensemble
>   voting (majority-vote N-reps / dual-model — eval-gated: measure
>   single-pass variance first; cost ×N unjustified before evidence);
>   structured inclusion-criteria screening directive (plan-compile
>   seam, mirrors select's directive pattern); LLM4SCREENLIT eval
>   metrics (full confusion matrix · lost-evidence/recall · WMCC ·
>   stub-as-non-LLM-baseline) flow to the eval slice's screening
>   dataset.
> - **rev 1.3** (2026-07-08, user gate call): **consensus screening
>   ADOPTED** — the rev-1.2 deferral reversed at the gate; screen calls
>   are envelope-grain mini-class (cents at fixture scale, low
>   single-digit dollars at ~1K docs), so the ×N cost objection was
>   overweighted, and a recall-preserving vote is a variance reduction
>   with no plausible recall downside (dual-model ensemble precedent).
>   Shape: **repeated-sampling consensus of the one screen surface**
>   (`SCREEN_REPS = 3`, the `--reps` pattern) — decision 3/10 rewritten;
>   per-rep unsure→relevant then majority; ties break to relevant;
>   per-rep records in the event payload; agreement stats in the
>   summary (subsumes the rev-1.2 two-run variance probe). **Scope:
>   screen only** — classify stays single-call (a 9-label vote
>   splinters; forced tie-breaks would inflate `Unknown`s). Newly
>   recorded seams: classify-consensus (eval-gated) ·
>   heterogeneous-model ensemble (needs the Bedrock/routing seam —
>   v3.0 is single-provider).
> - **rev 1.4** (2026-07-08, user gate challenge held): **consensus
>   confidence = probability over ALL reps, not mean-of-majority** —
>   the user caught that mean-of-majority makes a 2/3 doc
>   indistinguishable from a 3/3 doc in the persisted column (the only
>   signal downstream readers see). Each rep contributes p(relevant)
>   (= conf if relevant, 1 − conf if not_relevant, flat 0.5 if
>   unsure); persisted confidence = confidence in the recorded
>   decision. UNSURE_CONFIDENCE_CAP retired (unanimous-unsure lands
>   at 0.5 naturally). Vote/probability divergence explicitly legal
>   (relevant at < 0.5 = kept-in-but-shaky, borderline-review
>   surfaced). Decision 3 rewritten.
> - **rev 1.5** (2026-07-08, V2 autopsy adjudicated — deep-reasoner
>   recon of `../discovery_policy_atlas`, fourth in the series; full
>   record [v2-screen-classify-autopsy.md](v2-screen-classify-autopsy.md)).
>   **Contradiction held → decision 8 rewritten to a split model
>   route**: V2's human-labelled eval measured mini-class ≈ 50% vs
>   gpt-5.2 ≈ 76% top-1 on the identical 9-value taxonomy, and V2
>   shipped gpt-5.2 for classify as its remedy — classify moves to the
>   judgment-class model (single-pass, gates appraisal coverage, a
>   coherent wrong label passes not-all-Unknown); screen stays mini ×3
>   reps; eval-slice swap-down recorded (priors may close the gap).
>   **Adopted**: classify wire gains `confidence` (payload/trace only,
>   no column — V2 found classify confidence positively correlated
>   with correctness + strength-gating precedent); `screen_v1`
>   prompt-authoring note (holistic probability, never V2's additive
>   facet rubric — root cause of FP 0.880 ≈ TP 0.904 miscalibration);
>   classify face-validity spot-check in the live check. **Citations
>   added in place**: silent-exclusion fix (dec 5 — V2 defaulted
>   failed screens to not-relevant), consensus precedent (dec 10 —
>   V2 `SCREENING_RUNS=5` tooling + recall 0.400 worst-corpus), display
>   conflation anchors (dec 3iii — `PapersTable.tsx:261-278`). **New
>   seams**: classify-confidence threshold-gating · V2 screening-eval
>   baseline seeds the eval slice (incl. hard corpora) · heat_pump
>   study re-scoped to 015/016 (search recall, not screening
>   accuracy).
> - **rev 1.5.1** (2026-07-08, user challenge at the gate): classify's
>   model = **current judgment-class tier, exact id plan-pinned
>   (default candidate `gpt-5.5`; assess `gpt-5.6-terra`)**, replacing
>   the rev-1.5 `gpt-5.2` pin — the V2 lesson generalises to the
>   tier, not the checkpoint; 5.2 is legacy-path (repriced upward
>   2026-07-02) and classify cost is immaterial at any tier
>   (flagship ≈ 1¢/doc). Decision 8 + Model route amended.
> - **rev 1.6** (2026-07-08, contract-stage adversarial review
>   adjudicated — Codex, 10 findings: 2 blockers · 7 majors · 1 minor,
>   **10/10 adopted**): **B2 fail-open made structural** — ⚑
>   title-only docs need a UNANIMOUS not_relevant to be excluded (any
>   dissent → relevant, flagged) + prompt rule "missing abstract is
>   never evidence of irrelevance; unjudgeable from title → unsure"
>   (decision 3). **B4 internal contradiction fixed** — scope + rubric
>   now name BOTH schema changes. **M1 quorum pinned** — ⚑ failed reps
>   leave the vote AND the probability denominator; a decision needs
>   ≥ 2 surviving reps, else `status='failed'` (retryable) — no
>   single-rep decision can persist (decisions 3/5). **M3
>   Unknown-vs-Other prompt requirement** (evidence-like but
>   insufficient info → Unknown; genuinely non-evidence → Other;
>   tested — decision 4). **M5 tags helper API change pinned**
>   (`insert_source_tags` gains `tag_type`, default `TOPIC_THEME`;
>   `METHODOLOGICAL_STRUCTURAL` constant beside it — decision 6).
>   **M7 read-path ripple widened** — `characterise._base_counts`
>   named (negative-`unscreened` failure); effective-status
>   distinct-source counting required for EVERY screening-status
>   reader (decision 5). **M8 concurrency race** — explicit reliance
>   on v3.0's single-process/serial posture recorded (007 precedent);
>   the partial-index race joins the concurrent-run hardening seam.
>   **M9 injection test strengthened** — paired clean/adversarial
>   fixtures with semantic-invariance assertion (valid-but-steered
>   labels caught), live-check probe + injection-eval seam
>   (decision 7). **M10 input-side bounds pinned** — closed allowlist
>   of provider fields entering prompts, per-field caps,
>   control-char stripping (decision 7). **m6 rubric wording split**
>   (failed-row retry discharged vs automated recovery sweep still
>   deferred). Both ⚑ remedies awaiting user confirmation.

## Goal

Replace the deterministic `screen` and `classify` stubs with live LLM
tools — the two class-1 sequenced capabilities ("the product cannot …
reason without them", [deferred.md](../../deferred.md) header). After this
slice, every judgment-bearing component in the EB chain is live; the only
fixture-bound surfaces left are search (015) and fetch (016).

Screen becomes a real recall-oriented relevance filter over the metadata
envelope (title + abstract, degrading to title-only, fail-open). Classify
becomes a real evidence-type classifier producing both spec-required
outputs: the closed `primary_evidence_type` **and** the open
methodological/structural tag proposals that the stub never produced
(components §3's second output — currently a silent gap, closed here).

## Deliverable

PR landing:

- Two backend seams mirroring the seven existing ones:
  `ScreeningBackend` + `ClassificationBackend` protocols (`mode`
  property), `OpenAI…` live implementations, stub implementations
  preserving today's sentinel behaviour verbatim (the suite's semantics
  are untouched and stay egress-free).
- Two lead-authored product prompts — `screen_v1` · `classify_v1`, the
  8th and 9th product prompt surfaces.
- Classify's open-tag output: `source_tag` writes via
  `tags.insert_source_tags` (`asserted_by='classify'`,
  `tag_type='methodological_structural'`), with the one-line
  CHECK-widening migration.
- `run_harness` gains `screening_backend` + `classification_backend`
  (stub-default injection, same pattern as the other seven).
- Langfuse tracing on both backends (traced_call pattern, full I/O,
  in-span validity scores); skeleton live-mode wiring.
- Tests + `verification.md` with a live end-to-end check.

## Read first

- [EB components §2 (screen) + §3 (classify) + tool wiring](../../specs/capabilities/evidence-base/components.md)
- [data-model](../../specs/system/data-model.md) — tag layer ("nothing
  hangs off a tag" governs the label; assignment rows carry assertion
  provenance), result-row grain
- [provenance-grounding](../../specs/system/provenance-grounding.md) —
  injection posture
- [execution-orchestration](../../specs/system/execution-orchestration.md)
  — per-document fan-out realisation
- [deferred.md](../../deferred.md) — the LLM screen/classify seam entries,
  the injection-screening posture (task 007 decision 9), and the
  **downstream-consumers-of-the-envelope** note (2026-07-05 API
  exploration): screen reads `abstract_source`; classify consumes
  structured provider priors to cut `Unknown`s
- Knowledge concepts: [per-doc-fanout-isolates-decision-call](../../knowledge/per-doc-fanout-isolates-decision-call.md)
  · [per-doc-fanout-idempotent](../../knowledge/per-doc-fanout-idempotent.md)
  · [llm-schema-valid-empty-output](../../knowledge/llm-schema-valid-empty-output.md)
  · [model-output-nul-scrub](../../knowledge/model-output-nul-scrub.md)
  · [validation-reject-at-fault-grain](../../knowledge/validation-reject-at-fault-grain.md)

## Decisions

1. **Two seams, not one.** Screen and classify each get their own backend
   protocol and prompt, mirroring the existing per-component seams
   (theme grouping, ranking, extraction, facet grouping, synthesis,
   judge). They are different judgments (relevance-to-intent vs
   what-kind-of-document) with different inputs — a shared "envelope
   decision backend" would couple them for no saving.

2. **Per-document fan-out preserved; batching declined.** The spec's
   realisation for both components is per-doc fan-out, and both
   knowledge invariants stay load-bearing: only the decision call is
   wrapped (fallback to an already-constraint-valid outcome), inserts
   run unguarded, `WHERE NOT EXISTS` idempotency untouched. Calls run
   under bounded concurrency (extract precedent). Batching multiple
   docs per call is declined: the decisions are independent per
   document, batching couples their failure modes and invites
   cross-document leakage, and the cost profile at mini-class over
   envelope text is trivial.

3. **Screen semantics** *(amended revs 1.1, 1.2, 1.3)*. Each screen
   decision is a **consensus over `SCREEN_REPS = 3` independent
   samples** of the one screen surface (rev 1.3; the repeated-
   questioning `--reps` pattern — same prompt, same model, independent
   calls; heterogeneous-model ensembles wait on the Bedrock/routing
   seam). Each rep returns a schema-constrained
   `{decision, confidence, reason}` where decision is **three-way on
   the wire**: `relevant` | `not_relevant` | `unsure` — forcing a
   binary answer invites overconfident exclusion, exactly the failure
   a recall-oriented filter must not have. `reason` (≤ 240 chars, the
   select-rerank bound) is untrusted model text recorded in the event
   payload + trace only — never a column, never rendered as
   instruction — enabling borderline review and disagreement autopsies
   (rev 1.2; Mäntylä 2606.17588). **Aggregation is recall-preserving
   at every step** *(confidence formula rev 1.4)*: the **decision** is
   a majority vote in which `unsure` counts as `relevant` — the
   published recommendation verbatim ("treat unclassifiable outputs
   as referred-back positives", LLM4SCREENLIT 2511.12635) — with ties
   (possible only when a rep failed) breaking to `relevant`, flagged.
   *(rev 1.6, M1)*: a failed rep (post-retry) leaves both the vote
   AND the probability denominator — an API error carries no
   information about the document, so treating it as 0.5 would
   fabricate neutrality; and a decision requires a **quorum of ≥ 2
   surviving reps** — 0 or 1 survivors → `status='failed'`
   (retryable), so no single-rep decision can ever persist under a
   consensus contract. *(rev 1.6, B2 — fail-open made structural)*:
   for `title_only` docs (no abstract), exclusion requires a
   **unanimous** not_relevant among surviving reps — any dissent →
   `relevant`, flagged; and `screen_v1` pins the rule "a missing
   abstract is never evidence of irrelevance; if the title alone
   cannot support a judgment, answer `unsure`" — together these make
   the spec's fail-open a code property, not a hope.
   The **confidence** is a consensus probability over ALL SURVIVING
   reps: each rep contributes p(relevant) = its
   confidence if it said `relevant`, 1 − its confidence if it said
   `not_relevant` (dissent lowers the number in proportion to the
   dissenter's conviction), and a flat 0.5 if it said `unsure`
   (conviction in "unsure" has no direction — this retires the
   separate UNSURE_CONFIDENCE_CAP; unanimous-unsure lands at 0.5,
   which IS referred-back-positive-at-low-confidence). Persisted
   `screen_decision_confidence` = confidence in the recorded decision
   (mean p for `relevant` rows, 1 − mean p for `not_relevant` rows),
   keeping the column's semantics stable for its readers (select's
   composite, `thin_base`). *Clarity notes (2026-07-08, user
   deliberation):* (i) every current downstream reader consumes only
   `relevant` rows, where decision confidence ≡ p(relevant) — so the
   value consumers see is always relevance confidence; the 1 − p flip
   affects only `not_relevant` rows (no current reader; kept so an
   inspected excluded row reads honestly, matching stub semantics).
   (ii) `unsure`'s 0.5 is not a discarded confidence: `unsure` is a
   first-class wire answer, not a threshold over some underlying
   relevance score, and its attached confidence is conviction that
   the doc is *undecidable* — direction-less. Using it as p(relevant)
   would let a 0.9-confident-unsure rep outvote an 0.8-confident-
   relevant one; 0.5 is the unique zero-directional-evidence value.
   The rev-1.1 unsure→relevant mapping lives in the VOTE leg only
   (recall device); the probability leg honours unsure's neutrality.
   (iii) *Display seam (user, 2026-07-08 — observed V2 failure mode;
   anchors confirmed by the V2 autopsy):* decision confidence on
   `not_relevant` rows must never be rendered alongside relevant
   rows' confidence as if one column of "relevance scores" — V2's
   documents table does exactly this (`PapersTable.tsx:261-278`:
   column headed "Relevance", renders `relevance_confidence*100` for
   every row, default-sorted descending; same conflation in the CSV
   export, V2 `projects.py:1848-1850`) and users misread exclusion
   confidence as a relevance score. Recorded for the front-end/
   web-app seam (deferred.md at step 8); no v3.0 surface renders it
   yet. (iv) *Prompt-authoring note (rev 1.5, V2 root cause):* V2's
   screen confidence was an additive +0.2-per-facet rubric (V2
   `prompts.py:122-124`) — a coverage score, not a probability — and
   was measurably uncalibrated (FP mean 0.880 ≈ TP mean 0.904;
   committed eval `backend/testing/evals/screening/results/
   20251120_135440/`). `screen_v1` must elicit a holistic probability
   judgment, never an additive facet rubric.
   Vote and probability may legally diverge
   (two weak relevants against one high-conviction dissenter →
   `relevant` at confidence < 0.5): that is the honest recall-first
   outcome — kept in, marked shaky — surfaced to the borderline
   review, never silently reconciled. The event payload records every
   rep's `{decision, confidence, reason}` plus the agreement count
   (3/3 · 2/3 · …); non-unanimous docs are counted in the component
   summary — the standing per-run variance evidence. `unsure` is
   deliberately **not** a status value:
   every downstream reader filters on `status='relevant'`, so a third
   status would silently behave as exclusion — the one thing the spec
   forbids ("confidence … never a hard exclusion cutoff"); the durable
   representation of "unsure" IS relevant-at-low-confidence, which
   feeds `thin_base` and select's composite as designed.
   `screen_basis` is computed **in code** from abstract presence
   (`title_abstract` | `title_only`) exactly as today — the fail-open
   rule ("no abstract must never behave like not-relevant") is
   structural, not prompted. The prompt is recall-oriented (the
   dangerous failure is the false negative). Confidence is stored
   as-is; calibration belongs to the eval seam. `abstract_source` is
   passed as a data field so provider-LLM summaries (Overton
   `llm_description`) are visible to the model as secondhand text.
   Screen relevance is judged **against the scope intent** — intent
   enters the prompt as an id-keyed data record, never instructions
   (011/012 carried requirement).

4. **Classify is intent-free.** Classification is a property of the
   document, not the question (the 011 precedent: intent was removed
   from `extract_iof_v1` for the same reason). The model returns a
   schema-constrained single choice over the closed 9-value
   `EVIDENCE_TYPES` list plus bounded tag proposals, a `reason`
   field (same bounds and event/trace-only handling as screen's, rev
   1.2), **and a `confidence`** *(rev 1.5)* — event payload + trace
   only, NO column ("model only what behaves": nothing reads it in
   v3.0; the column arrives with its first reader). V2 precedent for
   keeping it: classifier confidence was the one confidence V2 found
   *positively correlated with correctness*, and downstream strength
   scoring hard-gated on it (V2 `strength.py:456-461`) — the
   threshold-gating pattern is a recorded seam for when a consumer
   lands. Structured provider priors enter as data fields —
   `record_type`, Overton `source.type` / `organisation_type`, provider
   topic labels — to cut `Unknown`s on acquired documents
   (classification quality gates appraisal coverage).
   `Unknown / Insufficient information` remains a legal, honest model
   output — per-element accuracy variance in the field (PMC12407223)
   says a closed single label with an honest Unknown is the right
   grain. *(rev 1.6, M3 — the distinction has consequences)*:
   `Other (Non-evidence documents)` excludes a doc from
   select/extract eligibility while `Unknown` is kept-and-eligible
   (components §3, enforced in select's candidate query), so
   `classify_v1` must define BOTH boundaries explicitly —
   evidence-like doc with insufficient methodological info →
   `Unknown`, genuinely non-evidence artefact (editorial, news item,
   website scrap) → `Other` — with fixtures testing each side.

5. **Live failure semantics: failures never block retry** *(amended
   rev 1.1)*. The deferred `screen_failed`-recovery entry's own
   condition — "until a real inference provider makes failure
   transient" — fires in this slice, so retry semantics land with the
   live backends rather than as a follow-on:
   - **In-call:** one retry (cap 1) per call before that call counts
     as failed — per rep for screen, per document for classify. Screen
     call budget is known pre-run: ≤ docs × SCREEN_REPS × 2.
   - **Screen rep failure** *(rev 1.3; quorum rev 1.6 M1)*: a failed
     rep (post-retry) drops out of both the vote and the confidence
     denominator; the vote runs over survivors (2-survivor 1-1 tie →
     relevant, flagged); **fewer than 2 surviving reps** →
     `status='failed'` for the doc (retryable — no single-rep
     decision persists). Rep failures are counted in the
     summary and visible in the event payload.
   - **Screen doc failure:** `status='failed'`
     persisted. `uq_ssr_scope_source` — `source_screening_result`'s
     unique constraint over (evidence_scope_id,
     project_source_snapshot_id), i.e. "one screening result per doc
     per scope" — becomes a **partial unique index
     excluding `status='failed'`** (the 011 extraction-memo precedent:
     "failures never block retry"), and the NOT-EXISTS candidate guard
     becomes "no **non-failed** result exists" — a subsequent run
     re-attempts failed docs as a **new row**, preserving failed rows
     as attempt history. At most one non-failed row per
     (scope, source) still holds; re-screening of *successful* results
     remains the deferred seam.
   - **Classify:** call failure (post-retry) → **no row written**
     (changed from the stub-era fallback): `Unknown` is a
     classification claim and an API failure is not one; the NOT
     EXISTS guard makes the next run retry exactly those docs.
   - *V2 evidence for this decision (rev 1.5):* V2 did the opposite
     on both components and both failures were silent — failed screen
     calls defaulted to `is_relevant=False` (**silent exclusion**, V2
     `relevance.py:194-197`) and failed classify calls left a NaN
     category (V2 `category.py:348-364`). Never-silent failure is the
     direct fix.
   - Failures are counted in both component summaries, never silent.
   - **Read-path adjustment (named; widened rev 1.6 M7):** every
     reader of screening-status rows must count at **effective-status,
     distinct-source grain**, not raw rows — attempt history otherwise
     corrupts counts. Two named instances: `classify_sources`'
     `skipped` count (`classify.py:109`) inflates with failed
     attempts, and `characterise._base_counts`
     (`characterise.py:162-179`) can drive `unscreened` NEGATIVE
     (failed attempts + a later success make one doc count twice
     against `project_sources`). The plan enumerates all remaining
     readers; each gets a regression test.
   - **Concurrency posture (rev 1.6 M8):** two concurrent screen runs
     on one scope could both pass the NOT-EXISTS guard and collide on
     the partial unique index. v3.0 execution is single-process/serial
     (the recorded 007 posture) — this slice explicitly RELIES on
     that invariant rather than hardening the writer; the
     partial-index collision case joins the existing concurrent-run
     hardening seam in deferred.md.

6. **Open tags land, bounded and untrusted.** Tag proposals are
   untrusted model output: per-record cap, per-tag length cap,
   control-character rejection (the 009 provider-tag bounds), written
   only through `tags.insert_source_tags`. The `ck_stag_tag_type`
   CHECK widens by one migration to admit
   `'methodological_structural'`; the value lives as a `schema.py`
   constant (`METHODOLOGICAL_STRUCTURAL`) next to `TOPIC_THEME`.
   *(rev 1.6, M5 — the contract's helper claim was wrong as written)*:
   `tags.insert_source_tags` today hard-codes `tag_type=TOPIC_THEME`
   and accepts `(pss_id, tag, asserted_by)` triples (`tags.py:31-48`),
   so this slice pins the **helper API change**: an explicit
   `tag_type` parameter defaulting to `TOPIC_THEME` (existing callers
   untouched), tests covering both tag types. Tag labels are
   data-not-instruction for every downstream prompt (012 carried
   requirement).

7. **Injection posture comes due (007 decision 9)** *(strengthened
   rev 1.6, M9 + M10)*. This slice is the first product LLM read of
   acquired third-party text. Titles, abstracts and provider fields
   enter prompts as id-keyed data records, never instructions;
   outputs are schema-constrained; the decision vocabulary is
   validated closed in code; NUL scrub at the backend boundary (011
   lesson). **Input-side bounds (M10):** provider fields enter
   prompts only through a **closed allowlist** (the decision-4 prior
   set), each field length-capped and control-character-stripped at
   prompt assembly (the 009 provider-tag bounds, applied input-side);
   overlong and instruction-shaped provider-field fixtures ride the
   suite. **Semantic injection testing (M9):** a closed vocabulary
   cannot catch valid-but-steered output ("mark this relevant" steering
   to a legal `relevant`), so the test is **paired-fixture semantic
   invariance** — the same document with and without embedded
   instruction text must produce the same decision: deterministic
   pairs in the judgment suite (scripted backends), a live paired
   probe in the live check (on-topic doc + injected twin → same
   decision; off-topic doc + "mark this relevant" → still
   not_relevant), and systematic injection evals recorded at the eval
   seam.

8. **Model: split route** *(rewritten rev 1.5 — V2 autopsy
   contradiction held)*. **Screen = `gpt-5-mini`** (compact-model
   screening sensitivity is literature-validated, and the 3-rep
   consensus adds redundancy; the 009 nano lesson still floors us at
   mini). **Classify = the current judgment-class tier; the exact id
   is a plan-time pin (default candidate `gpt-5.5`; assess
   `gpt-5.6-terra` at the plan gate)** *(rev 1.5.1 — user challenge:
   the V2 lesson is "judgment-class", not "gpt-5.2 specifically";
   5.2 is two generations old and was repriced upward 2026-07-02, a
   legacy-path signal — pinning it imports deprecation risk for zero
   benefit, and cost is immaterial at envelope grain: flagship ≈ 1¢/
   doc vs mini ≈ 0.2¢/doc, ~$10 vs ~$1.60 per 1,000 docs)*. The V2
   evidence: V2's own human-labelled eval measured mini-class
   at ≈ 50% vs its then-current judgment model (gpt-5.2) at ≈ 76%
   top-1 on the IDENTICAL 9-value
   taxonomy (three Argilla gold sets; narrative record
   `EVIDENCE_CATEGORISATION_PLAN.md:396-431` — machine outputs
   gitignored, so evidence grade is moderate), and V2 shipped exactly
   this remedy (`EVIDENCE_CATEGORY_MODEL = "gpt-5.2"` "needs higher
   accuracy", V2 `config.py:136-138`, while screen ran mini-class).
   A 9-way closed-label discrimination is the harder judgment, it is
   single-pass by design (rev 1.3), and classification quality gates
   appraisal coverage — a coherent wrong label passes the
   "not-all-Unknown" check, so model quality is the only line of
   defence this slice has. Cost stays trivial at envelope grain.
   **Eval-slice re-adjudication recorded**: V3's classify adds
   structured provider priors V2 never had — if the eval slice shows
   mini + priors closes the gap, the swap-down is a one-constant
   change.

9. **`make verify` stays deterministic and egress-free.** Stub backends
   default everywhere; the skeleton extends its existing
   `live = bool(OPENAI_API_KEY)` pattern to the two new backends.

10. **Consensus screening adopted; variance visible on every run**
    *(new rev 1.2; rewritten rev 1.3 — user gate call reversing the
    rev-1.2 deferral)*. Single-pass LLM screening has unmeasured
    decision variance (majority-vote `--reps` consensus PRs,
    dual-model ensembles reaching near-perfect sensitivity, Mäntylä's
    run-multiple-LLMs recommendation), and at envelope-grain
    mini-class cost the ×N objection was overweighted. Decision 3's
    `SCREEN_REPS = 3` consensus is the adopted remedy; because every
    doc now carries per-rep records + an agreement count, the
    **per-run disagreement rate is standing variance evidence** — the
    rev-1.2 second-run flip probe is subsumed and dropped. The live
    check reports the agreement distribution (share unanimous · 2/3 ·
    tie-broken) and runs the **borderline review** (lowest-confidence
    band + all non-unanimous docs, read with `reason`s). Scope:
    screen only — classify stays single-call (a 9-label vote
    splinters; tie-breaks would inflate `Unknown`s);
    classify-consensus and heterogeneous-model ensembles are recorded
    eval-gated seams. *V2 evidence (rev 1.5):* single-pass mini
    screening is not uniformly recall-safe (V2 committed eval: 3ie
    overall recall 0.727, worst corpus 0.400 with 1,352 false
    negatives), and V2's own blueprint eval already tooled multi-run
    screening (`SCREENING_RUNS=5`,
    `blueprint_comparison/screening/evaluate_screening.py`) — the
    consensus adoption has V2 precedent on both the problem and the
    remedy.

## Scope / Out of scope

- **In:** `screen.py`, `classify.py` (fan-out loops take a backend),
  new backend module(s), the two prompts, `harness.py` + `skeleton.py`
  wiring, one migration carrying BOTH schema changes (rev 1.6 B4 fix:
  `ck_stag_tag_type` CHECK widen + `uq_ssr_scope_source` → partial
  unique index; table count stays 25), `tags.py` helper API change +
  `schema.py` constant, effective-status count fixes in
  `classify.py` + `characterise.py`, tests (bulk + judgment +
  paired injection fixtures), `deferred.md` + knowledge updates,
  `verification.md`.
- **Out:** live search backends (015) · live `DocumentFetcher` (016) ·
  the thin-base **re-search trigger** (needs live search; note: live
  screen confidence makes select's `thin_base` flag meaningful
  automatically — no code change here) · tiered content peek — now
  sharpened (user deliberation, 2026-07-08) to a **stage-2 full-text
  re-screen seam**: post-ingestion re-screen scoped to the borderline
  band (title-only basis ∪ non-unanimous ∪ lowest-confidence decile),
  precision-only by construction (fetch is screen-gated, so stage 2
  can demote false includes but never rescue excludes — recall is won
  at stage 1 or not at all); mirrors human SR two-stage practice;
  eval-gated on the borderline-band size the decision-10 agreement
  stats will measure; the concrete exposure it closes is
  envelope-only rerank selecting a plausible-envelope irrelevant doc
  into extraction. *Sharpened again (user deliberation, second
  round): if built, stage 2 should re-screen the WHOLE screened-in
  corpus, not just the borderline band — selective re-measurement
  creates a two-regime confidence scale that select's composite and
  `thin_base` would compare as commensurable (the band version
  survives only as the sizing probe). Uniform stage-2 needs: a
  schema answer (the partial unique index admits one non-failed row
  per doc — supersede vs staged-result surface) and stage provenance
  on confidence so consumers never unknowingly mix measurement
  regimes; stage 2 plausibly single-rep (full text carries the
  signal consensus compensates for). Material stake, quantified by
  the V2 baseline (precision 0.634): ~⅓ junk in screened-in sets,
  and every junk doc ranking into select's bounded budget (default
  25) displaces a real doc from extraction. Spec home (user, third
  round): stage 2 is a **plan-selectable registry component under
  the thoroughness gradation** (ADR 0009: components = registry the
  plan selects from; depth = the plan's thoroughness) — deep runs
  compile it in post-ingestion, rapid runs skip it; the eval gate
  decides whether to BUILD it, thoroughness decides whether it RUNS.
  Same family as classify's Unknown full-text resolution and the
  two-stage appraisal pass: envelope always, full-text second pass
  at depth* ·
  **screen-confidence retrieval boost** (user, 2026-07-08 — new
  seam): in no-selection runs `search_chunks` has NO doc-level
  prior; `screen_decision_confidence` (meaningful from this slice)
  is the natural directive-expressible boost. Design notes: the
  013 boost grammar is categorical (per-value weights) — a
  continuous column needs banding or a clamped functional
  multiplier; steerable-never-baked (rev-7.5 ruling) → directive
  column, not a standing prior; double-count guard where a
  selection reference already prices confidence in. A 013-surface
  change — lands via its own gate, not 014 ·
  re-screening of **successful** results (the failed-row retry landed
  in-slice, rev 1.1; superseding a relevant/not_relevant decision is a
  different seam) · `Unknown` full-text resolution · grey-lit category
  split · appraise changes (its
  coverage improves for free as `Unknown`s drop) · eval harness ·
  consensus roll-up · multi-execution fan-in · **classify-consensus
  voting** (rev 1.3 — eval-gated; screen consensus is IN-slice per
  decision 10) · **heterogeneous-model screening ensemble** (rev 1.3 —
  needs the Bedrock/routing seam; v3.0 is single-provider) ·
  **structured inclusion-criteria screening directive** (rev 1.2 —
  plan-compile seam mirroring select's directive pattern;
  intent-as-data is the v3.0 surface). These seams + the
  LLM4SCREENLIT eval-metric pointers (full confusion matrix ·
  lost-evidence/recall · WMCC · the deterministic stub as the non-LLM
  baseline) land as `deferred.md` entries at step 8, joined by the
  rev-1.5 V2-autopsy seams: classify-confidence threshold-gating
  (V2 `strength.py:456-461` precedent — arrives with its first
  consumer) · the V2 screening eval baseline as eval-slice seed
  (13,740 docs, recall 0.836 / precision 0.634 / WSS@95 0.187 —
  committed results in V2 `backend/testing/evals/screening/`; the
  eval must include hard corpora, where V2 recall fell to 0.400) ·
  the heat_pump manual-vs-automated study re-scoped as
  search/coverage-recall evidence for 015/016 (it measures document
  identity, not screening accuracy).

## Constraints & approval gates

Gated changes riding this slice — **all need explicit approval at the
contract 🛑**:

1. **Runtime egress:** two new generation surfaces (`screen_v1` ·
   `classify_v1`, 8th/9th product prompts) — the first product LLM read
   of acquired third-party envelope text (injection posture above).
2. **Public interface:** `run_harness` gains `screening_backend` +
   `classification_backend` (stub defaults; no behaviour change when
   omitted).
3. **Schema:** one migration carrying two changes *(rev 1.1)*:
   widening `ck_stag_tag_type` to admit `'methodological_structural'`,
   and replacing `uq_ssr_scope_source` with a partial unique index
   excluding `status='failed'` (retry semantics, decision 5). No new
   tables, no new columns.
4. **Dependencies:** none.

## Public / private boundary

Prompts, code, migration, sanitized-fixture tests: committable. Live-run
traces contain acquired titles/abstracts (fixture corpus: sanitized
records + openly-licensed documents) — traces stay in Langfuse dev,
never committed. Keys env-only; grep audit before PR.

## Model route

OpenAI via the existing client resolution (`resolve_openai_client`);
**split route (revs 1.5/1.5.1)**: `gpt-5-mini` for `screen_v1`
(×3 reps), the current judgment-class tier for `classify_v1` —
exact id plan-pinned, default candidate `gpt-5.5` (see decision 8).
Bedrock swap remains the routing seam. Prompt-bearing work
(`screen_v1`, `classify_v1`) is lead-authored.

## Disciplines binding this slice

Template set, plus: fail-open screen basis is structural, not prompted ·
failures counted never silent · tags flag-not-drop within bounds,
rejected loudly beyond them · deferred seams stay seams.

## Stop conditions

Template set. Additionally: if live screening of the fixture corpus
surfaces a corpus-composition problem (e.g. everything not_relevant),
halt and report — don't tune the prompt to the fixtures.

## Acceptance checks

- `make verify` green — deterministic, zero egress (stub backends).
- Bulk tests: fan-out loops against both stub backends, idempotency,
  failure isolation (decision 5 semantics, including a
  failed-then-retried screen doc producing a new row with attempt
  history intact, and failure-attempt-aware counts), consensus
  aggregation (unanimous · 2/3 majority · rep-failure degradation ·
  1-1 tie→relevant flagged · all-reps-failed→doc failed · unsure
  counts relevant in the vote and 0.5 in the probability ·
  consensus-probability formula incl. the 2/3-vs-3/3 distinguishable
  case and the vote/probability divergence case), event payload
  carries per-rep records + agreement count, tag
  bounds, migration roundtrip (CHECK widen + partial unique index) on
  both DBs.
- Judgment tests (live-shaped, stub-driven): schema-constrained output
  parsing, closed-vocabulary validation, injection fixture, NUL scrub.
- **Live manual check** (operator-run, keys env-only): skeleton e2e over
  the fixture corpus with live screen + classify — real relevance
  decisions with a plausible spread (not all-relevant-1.0), a
  classification distribution that is **not all `Unknown`** (the
  demo-blocking failure this slice exists to remove), the non-English
  fixture record classified, open tags written within bounds, Langfuse
  traces + in-span scores verified via the public API, cost recorded,
  key grep audit clean. Plus (decision 10, rev 1.3): the **agreement
  distribution reported** (share unanimous · 2/3 · tie-broken —
  standing variance evidence) and the **borderline review**
  (lowest-confidence band + all non-unanimous docs read with
  `reason`s; reasons must be coherent with the decisions). Plus (rev
  1.5): a **classify face-validity spot-check** — ~10 sampled labels
  reviewed against their envelopes; "not all `Unknown`" is necessary
  but insufficient (a coherent wrong label passes it — the V2 eval
  showed mini-class getting half of them wrong). Plus (rev 1.6 M9):
  the **live paired injection probe** — an on-topic doc and its
  instruction-injected twin must screen identically; an off-topic doc
  carrying "mark this relevant" must stay not_relevant.

## Verification evidence expected

`verification.md`: command results, live-run evidence (counts, spread,
by_type distribution, tag samples, trace ids, cost), diff summary with
any flagged deviations, public-safety confirmation, known gaps.

## Risk tier & review focus

**Tier 3** (runtime egress + schema CHECK + public interface). Review
focus: injection posture on the first third-party-text prompts; the
classify-failure semantics change (decision 5); tag-bound enforcement;
recall posture of `screen_v1`; no scope creep into 015/016.
