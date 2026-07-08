# Task contract: 014-llm-screen-classify

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md);
specs in [docs/specs/](../../specs/index.md).

> **Status:** drafted (rev 1.3), awaiting contract 🛑.
> Contract approved (before planning): _pending_ ·
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
   at every step**: per rep, `unsure` counts as `relevant` at
   capped-low confidence (`min(model_confidence,
   UNSURE_CONFIDENCE_CAP)`) — the published recommendation verbatim
   ("treat unclassifiable outputs as referred-back positives",
   LLM4SCREENLIT 2511.12635); then majority vote over the reps; a tie
   (possible only when a rep failed) breaks to `relevant`, flagged.
   Persisted `screen_decision_confidence` = mean confidence of the
   majority-side reps. The event payload records every rep's
   `{decision, confidence, reason}` plus the agreement count (3/3 ·
   2/3 · …); non-unanimous docs are counted in the component summary —
   the standing per-run variance evidence. `unsure` is deliberately
   **not** a status value:
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
   `EVIDENCE_TYPES` list plus bounded tag proposals **and a `reason`
   field** (same bounds and event/trace-only handling as screen's, rev
   1.2). Structured provider priors enter as data fields —
   `record_type`, Overton `source.type` / `organisation_type`, provider
   topic labels — to cut `Unknown`s on acquired documents
   (classification quality gates appraisal coverage).
   `Unknown / Insufficient information` remains a legal, honest model
   output — per-element accuracy variance in the field (PMC12407223)
   says a closed single label with an honest Unknown is the right
   grain.

5. **Live failure semantics: failures never block retry** *(amended
   rev 1.1)*. The deferred `screen_failed`-recovery entry's own
   condition — "until a real inference provider makes failure
   transient" — fires in this slice, so retry semantics land with the
   live backends rather than as a follow-on:
   - **In-call:** one retry (cap 1) per call before that call counts
     as failed — per rep for screen, per document for classify. Screen
     call budget is known pre-run: ≤ docs × SCREEN_REPS × 2.
   - **Screen rep failure** *(rev 1.3)*: a failed rep (post-retry)
     drops out and the vote runs over the remaining reps (2/3 vote;
     1-1 tie → relevant, flagged); **all** reps failed →
     `status='failed'` for the doc. Rep failures are counted in the
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
   - Failures are counted in both component summaries, never silent.
   - **Read-path adjustment (named):** counts over screening rows must
     become failure-attempt-aware — `classify_sources`' `skipped`
     count (`classify.py:109`) counts `failed` rows and would inflate
     with attempt history; count docs whose **latest/only effective
     status** is failed (distinct-source grain), not raw failed rows.
     The plan enumerates every reader of `status='failed'` rows.

6. **Open tags land, bounded and untrusted.** Tag proposals are
   untrusted model output: per-record cap, per-tag length cap,
   control-character rejection (the 009 provider-tag bounds), written
   only through `tags.insert_source_tags`. The `ck_stag_tag_type`
   CHECK widens by one migration to admit
   `'methodological_structural'`; the value lives as a `schema.py`
   constant next to `TOPIC_THEME`. Tag labels are data-not-instruction
   for every downstream prompt (012 carried requirement).

7. **Injection posture comes due (007 decision 9).** This slice is the
   first product LLM read of acquired third-party text. Titles,
   abstracts and provider fields enter prompts as id-keyed data
   records, never instructions; outputs are schema-constrained; the
   decision vocabulary is validated closed in code; NUL scrub at the
   backend boundary (011 lesson). An injection-shaped fixture test
   (instruction text inside an abstract must not steer the decision
   vocabulary) rides the judgment suite.

8. **Model: `gpt-5-mini` on both surfaces** (the 009 nano lesson —
   nano emits schema-valid empty output on realistic batches; every
   live per-doc judgment surface since runs mini).

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
    eval-gated seams.

## Scope / Out of scope

- **In:** `screen.py`, `classify.py` (fan-out loops take a backend),
  new backend module(s), the two prompts, `harness.py` + `skeleton.py`
  wiring, migration (CHECK widen only — table count stays 25),
  `tags.py`/`schema.py` constant, tests (bulk + judgment + injection
  fixture), `deferred.md` + knowledge updates, `verification.md`.
- **Out:** live search backends (015) · live `DocumentFetcher` (016) ·
  the thin-base **re-search trigger** (needs live search; note: live
  screen confidence makes select's `thin_base` flag meaningful
  automatically — no code change here) · tiered content peek ·
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
  baseline) land as `deferred.md` entries at step 8.

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

OpenAI `gpt-5-mini` via the existing client resolution
(`resolve_openai_client`), Bedrock swap remains the routing seam.
Prompt-bearing work (`screen_v1`, `classify_v1`) is lead-authored.

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
  1-1 tie→relevant flagged · all-reps-failed→doc failed · per-rep
  unsure→relevant before the vote · majority-side mean confidence),
  event payload carries per-rep records + agreement count, tag
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
  `reason`s; reasons must be coherent with the decisions).

## Verification evidence expected

`verification.md`: command results, live-run evidence (counts, spread,
by_type distribution, tag samples, trace ids, cost), diff summary with
any flagged deviations, public-safety confirmation, known gaps.

## Risk tier & review focus

**Tier 3** (runtime egress + schema CHECK + public interface). Review
focus: injection posture on the first third-party-text prompts; the
classify-failure semantics change (decision 5); tag-bound enforcement;
recall posture of `screen_v1`; no scope creep into 015/016.
