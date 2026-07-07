# Task contract: 011-extract

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md);
specs in [docs/specs/](../../specs/index.md).

> **Status:** drafted (rev 1.1) — awaiting human approval before planning.
> Contract approved (before planning): _pending_ ·
> Plan approved (before implementation): _pending_ · ADR: _due at step 4_.
>
> **Revision history:**
> - **rev 1** (2026-07-07): initial draft.
> - **rev 1.1** (2026-07-07, user challenges at the gate — both adjudicated,
>   decisions held, seams sharpened): **(a) table-per-schema held** — the
>   data-model's "coherent typed record, dimensions intact and queryable" +
>   the build spec's "related-but-distinct, never blended" evidence kinds favour
>   typed tables with CHECK-enforced vocabularies (repo discipline); cross-schema
>   linkage is reference-mediated via `group`, never a SQL join; the schema set
>   grows at spec-level pace (exactly one further schema named). *Generic finding
>   container declined* — recorded seam, revisit trigger = a third finding schema
>   specced. **(b) full-text extraction held; retrieval-scoped extraction
>   declined** — reading a retrieved subset makes `no_findings`/`not_extracted`
>   unverifiable (a silent new base-ladder rung — the false-absence machinery EB
>   exists to prevent), inverts the recall-critical trade ("false negatives are
>   the dangerous failure mode"), re-treads v2's truncation anti-pattern, and
>   would pull the unbuilt `retrieve` seam in-slice; `select` is the designed
>   cost control. **(c) retrieval-*augmented* extraction (full read + targeted
>   in-doc retrieval repair / cross-window context assembly) acknowledged as
>   composable and legitimate** — the full read licenses coverage; deferred as an
>   eval-gated seam (needs `retrieve` + extraction-quality evals showing a
>   field-completeness gap on multi-window docs). The cheap in-slice mitigation
>   lands instead: the **cross-window document-context header** (decision 5).
> - **rev 1.2** (2026-07-07, user challenge held): the rev-1.1 header **slimmed
>   to the envelope block** (title + abstract in every call — plain prompt
>   assembly). The running-names element was cut: it would serialize per-doc
>   windows (window N depends on N−1) and add state/provenance/test machinery
>   for a path the corpus barely exercises — most documents fit in one call;
>   windowing is the honest rare path, not the norm. Windows stay independent
>   and parallel; naming consistency across windows rides the eval-gated seam.
> - **rev 1.3** (2026-07-07, field-research pass — /last30days sweep of current
>   LLM-extraction practice; raw file
>   `~/Documents/Last30Days/llm-structured-information-extraction-raw-v3.md`):
>   three adoptions, none moving a gate. **(a) Verified quotes record their
>   match location** (chunk id + char interval found by the presence check —
>   the data-model's "location is the recorded by-product of the verify step";
>   also localizes anchors inside the 008-known giant-chunk PDFs; LangExtract
>   convergence). **(b) Deterministic field-rule validation** post-parse
>   (decision 4): bounds/consistency checks over the stats bundle — violations
>   flagged `unclear`, counted, never silently accepted ("Valid JSON, Wrong
>   Answer" — schema validity is the easy part). **(c) Explicit negative rules
>   in the prompt** (what NOT to extract), per the schema-constrained
>   biomedical-extraction evidence. Declined/deferred with triggers:
>   LangExtract as dependency (techniques absorbed, library declined) ·
>   multi-pass recall extraction (eval-gated; pass count recorded in
>   provenance now) · reason-then-constrain (eval-gated remedy; closed-weight
>   API models resist the format tax) · LLM-judge schema-consistency pass
>   (grounding-tier/eval territory). Findings that confirmed the design
>   unchanged: grounding-or-flag anchoring, span-level verification as best
>   practice, mini-class model floor.
> - **rev 1.4** (2026-07-07, two code-grounded studies — LangExtract source
>   dissection + V2 extraction autopsy (`../discovery_policy_atlas`), both
>   subagent reports adjudicated by the lead):
>   **From LangExtract** (all quote-check mechanics, decision 4): ordered
>   occurrence cursor (repeated quotes map to successive occurrences, never all
>   to the first — a silent grounding bug class) · normalisation pinned as
>   lowercase + whitespace-collapse + punctuation folding (smart quotes/dashes/
>   NBSP) on both sides, **offsets always recorded into raw frozen text** (their
>   deliberate NFC-avoidance lesson: normalising the offset substrate makes
>   intervals drift) · graded match-status vocabulary (record the match method,
>   not a binary flag) · pre-flight few-shot example validation (the
>   quote-verifier runs over the prompt's own examples at load; a non-verbatim
>   demonstration fails loudly). Confirmed: keep-on-failure; our
>   concatenate-before-matching beats their per-chunk alignment for
>   boundary-spanning quotes; their multi-pass merge recipe (identical prompt,
>   char-interval overlap, first-pass-wins) recorded at the seam.
>   **From V2 — what quietly worked, kept** (decision 3): the SR pooled grain
>   (one finding per outcome × stratum; k/N/I²/τ²; pooled effect-size-type
>   vocabulary; an estimate-level discriminator {study | pooled | claim}) · the
>   **outcome-⊥-stratum rule** (outcome = base measure only, never "BMI at 12
>   months"; timepoint/subgroup are structured stratum qualifiers — what makes
>   cross-document grouping tractable) · **comparator** as a source-named
>   nullable reference (effect direction is vs-something) · the prevalence-only
>   guard semantics with skip/extract examples and unsure→prevalence default ·
>   control-arms-are-not-interventions. ⚑ *Stratum qualifiers + comparator +
>   estimate level slightly extend the data-model's literal base-field list —
>   within its source-groundability line ("what the source reports"), flagged
>   at this gate; candidate minor flow-back to the data-model base-field list
>   rides the contract.*
>   **From V2 — failure modes closed** (decisions 4, 5): null-like-string
>   coercion joins field-rule validation ("null"/"n/a"/"none"/"unknown" in
>   nullable fields → real null + coverage marker; V2 instructed the literal
>   string "null" and paid in permanent downstream cleanup) · the pydantic
>   record model is the **single source of truth** for API schema and prompt
>   field docs, `extra="forbid"` (V2's prompt/schema drift silently deleted
>   three requested fields incl. the SR evidence-volume signal) · prompt
>   receives the doc's `primary_evidence_type` as context with pooled-vs-study
>   guidance; **an empty findings list is explicitly legal** and "never force
>   effect fields onto documents that don't report them" joins the negative
>   rules (V2 ran RCT prompts on qualitative/policy docs → forced stats) ·
>   **within-doc exact-duplicate dedup**, deterministic, flagged and counted
>   (V2 requested MECE in the prompt but never enforced it; verbose extraction
>   inflated evidence weight downstream) · explicit max-output-tokens
>   plan-pinned (V2's uncapped calls truncated mid-JSON, silently emptying
>   stages) · grounding-rate instrumentation from day one: roll-up counts +
>   Langfuse run scores make extraction quality measurable (V2's ">95%
>   grounding" had no measurement artifact behind it).
>   Seams recorded: per-intervention focused-call decomposition (V2's
>   cross-contamination remedy — eval-gated, same family as multi-pass) ·
>   V2's CFIR implementation-profile field definitions noted as input to the
>   `implementation_context_finding` seam · mixed/unclear findings are
>   first-class and must survive into group/synthesise (V2 extracted then
>   discarded them at aggregation).

## Goal

Add **extract** — EB component 7, Tier-1 extraction, the step `select` exists to
gate. Per selected document, extract **`intervention_outcome_finding`** records:
the framework's first reusable findings-layer schema. Grain: one *(intervention,
outcome, effect)* claim grounded in a **single source**; intervention, outcome and
study population carried as **source-named references** (groupable downstream,
never canonical entities). **Base fields only** — what the source reports; the
line is **source-groundability**. Question-relative judgements (normalised
magnitude, causal weighting, is-beneficial) are analysis enrichment for Impact/VfM
and stay out.

This is the repo's first write into the **findings layer** (data-model): findings
are **durable, reusable information-layer records** — unlike the run-local
characterisation and selection rows — memoised by *(source snapshot,
extraction-task fingerprint)* so a later run, scope or capability reusing the same
profile does not re-pay extraction. The full extraction *service* (profile
resolution, per-source task creation) stays a seam; this slice lands the minimal
honest form: a per-document extraction record with a unique memo key, checked
before any call.

Extraction is the repo's third product prompt surface and its first over **full
text**: per selected document, the segmented frozen chunks (or the abstract
envelope where `text_basis="abstract_only"` — text-in-hand, flag-not-drop, per
008) go to a judgment model under a schema-constrained extraction prompt
(`extract_iof_v1`, lead-authored). Every finding anchors back to its source:
verbatim supporting quote + chunk reference, **deterministically checked** against
the frozen text at write time — the provenance anchor *(source, verbatim quote,
recorded location)* the data-model commits to, applied at the finding grain.

The gap-provenance ladder gains its last rungs: the extracted base becomes real,
`not_selected` vs `not_extracted` vs `extraction_failed` vs a **reported null**
(a finding, never a gap) are all now representable and counted — and nothing in
this component's output can phrase any of them as corpus absence.

## Deliverable

A PR on `task/011-extract` → `dev` that:

- Ships `extract.py`: `ExtractContext(scope_id, intent, context,
  selection_run_id)`; `extract_scope(...)` — selection-row load → per-document
  basis assembly (chunks or abstract) → memo check → per-source fan-out extraction
  → quote verification → finding + record writes → run roll-up row → extraction
  summary in `component.completed`.
- Ships the `ExtractionBackend` seam (the `GroupingBackend`/`RankingBackend`
  pattern): protocol + `OpenAIExtractionBackend` (schema-constrained structured
  outputs, windowed id-keyed segment records, caller-owned retry/budget) +
  deterministic sentinel-driven stub for the suite, and the **`extract_iof_v1`
  prompt** (lead-authored, versioned, recorded in provenance) — the slice's only
  prompt-bearing surface.
- Adds **three tables — `source_extraction_record`,
  `intervention_outcome_finding`, `extraction_result`** — via one Alembic
  migration (gated change 1; table count 20 → 23), project-scope-guarded per repo
  discipline.
- Registers `"extract"` in `COMPONENT_REGISTRY` (requires `evidence_scope_id` +
  `selection_run_id` — the explicit-reference pattern rev 7 of 010 set);
  `run_harness` gains one optional **`extraction_backend`** parameter (stub
  default — no default egress; gated change 2).
- Extends `skeleton.py`: … select → **extract**, rendering the extraction summary
  (per-doc statuses, finding counts, coverage/base-ladder counts, fresh vs
  reused, flags).
- Records the deferred seams in `docs/deferred.md`; updates `tests/helpers.py`
  delete order for the new tables.
- Passes `make verify` — all green, deterministic, egress-free.

## Read first

- [EB components §7 — extract](../../specs/capabilities/evidence-base/components.md)
  — the component contract: per-source fan-out over the **selected** subset, the
  base-fields commitment, the second-schema seam. Also §4's Tier-0/Tier-1 split
  (full text already ingested for all screened-in; extraction is the scoped,
  expensive step) and §6's rationale (extract works on what select chose —
  including its `text_basis` mix and `thin_full_text` flag).
- [System data-model — the findings layer](../../specs/system/data-model.md) —
  the schema's owner: grain, base fields, source-named references, coverage
  states as gap provenance, memoisation by *(source snapshot, extraction-task
  fingerprint)*, "one coherent typed record with its dimensions intact and
  queryable", model/prompt upgrades never invalidate existing findings.
- [EB provenance](../../specs/capabilities/evidence-base/provenance.md) +
  [system provenance-grounding](../../specs/system/provenance-grounding.md) —
  the acute rule this slice makes real: the extracted set is a **strict subset**
  of the corpus; `not_extracted`/`extraction_failed`/`unclear` never license
  absence; a reported null is a finding; finding-query patterns inherit the
  extraction dependency and carry *(finding-set, coverage-state,
  extraction-profile)* provenance.
- [System execution-orchestration](../../specs/system/execution-orchestration.md)
  — extract realises as **deterministic per-source fan-out** (procedure, not
  agent-loop); `extract` is a declared component tool, invoked as one facade;
  ingestion is not a tool; `search` stays the only agent-invocable egress verb.
- [010-select contract](../010-select/contract.md) — pattern precedent: explicit
  upstream-run reference, injection posture, call-budget discipline,
  fallback-not-failure vocabulary, run roll-up row shape.
- [docs/deferred.md](../../deferred.md) — `implementation_context_finding`
  (named, not built); graph-structured synthesis; cross-project finding reuse
  (deferred, sits next to the rejected global KG).

**Code grounding (surveyed 2026-07-07):** 20 tables, 10 migrations; no findings
table exists. `selection_result.selected` is a JSONB list of per-doc records
carrying `pss_id`, `stratum`, `reason`, `text_basis`, signals — extract reads
`(scope, selection_run_id)` via the `UNIQUE (evidence_scope_id, run_id)` row. A
document's full text: `project_source_snapshot.full_text_snapshot_id` →
`chunk` rows ordered by `sequence` (`content`, `locator`, `segmentation_policy`);
`abstract_only` docs (14 of the 24-doc fixture corpus; 10 have real segmented
full text) have no chunks — the envelope snapshot's metadata carries the
abstract. Backend pattern: protocol + stub + OpenAI class with
`pydantic` `response_format`, module-constant prompts + `PROMPT_VERSION`,
caller-owned call-budget dataclass (`baseline × (1 + retry_cap)` hard ceiling),
`ThreadPoolExecutor` concurrency, validation separated from the call
(`gpt-5-mini` floor — the nano lesson is encoded in both grouping and ranking).
Component wiring: registry entry + required Config field → context dataclass →
`_run_scope_component` → `component.started/completed/failed`;
`skeleton.py` threads upstream run ids as optional kwargs
(`characterisation_run_id` precedent) and switches stub/live on
`OPENAI_API_KEY`. Langfuse: wrapper-class tracing (`TracedGroupingBackend`) or
internal (`OpenAIRankingBackend`) — either precedent stands.

## Scope

### Design decisions embedded here (approve or flip at this gate)

1. **Findings are durable information-layer records; the run row is a roll-up.**
   Three tables with three distinct lifetimes:
   - **`intervention_outcome_finding`** — the reusable record. Project-scoped
     (cross-project finding reuse stays deferred), FK to the per-doc extraction
     record, surviving across runs; never superseded by a later run (model/prompt
     upgrades set future defaults via a new fingerprint — they **never
     invalidate existing findings**, data-model).
   - **`source_extraction_record`** — one row per document-extraction:
     `UNIQUE (project_id, source_snapshot_id, extraction_fingerprint)` — the
     **memo key**. Carries doc-level status (`extracted` | `no_findings` |
     `extraction_failed`), the extraction basis (`full_text` | `abstract_only`),
     error reason, finding count, the creating run. `no_findings` is a real,
     honest state: the document was processed and reports nothing
     intervention–outcome-shaped — distinct from failure and from never-tried
     (the memo needs all three distinguishable, else "extracted, found nothing"
     is re-paid every run).
   - **`extraction_result`** — the run-scoped roll-up mirroring
     `characterisation_result`/`selection_result`: one row per
     `(evidence_scope_id, run_id)`, carrying the executed fingerprint, per-doc
     status list, fresh-vs-reused counts, base-ladder counts and flags. This is
     the row `group` (the next slice) will reference by `extraction_run_id`,
     exactly as extract references `selection_run_id`.
2. **The memo (reuse) check is v3.0-minimal, the service is a seam.** Before any
   call, each selected document's `(source_snapshot_id, fingerprint)` is looked
   up; a hit reuses the existing record + findings (counted `reused` in the
   roll-up, no call, no new finding rows). The **extraction fingerprint** is a
   deterministic key: `profile_id · prompt_version · model · backend mode`
   (indicatively `eb_iof_base_v1:extract_iof_v1:gpt-5-mini:live`) — stub results
   carry a `stub`-moded fingerprint and can never masquerade as live extraction.
   The framework's extraction *service* (a capability commit declaring a profile,
   resolved against existing records) stays deferred; EB's profile is this
   slice's named constant (`eb_iof_base_v1` = the base fields over the selected
   subset). Evidence dataset snapshots (pinned point-in-time consumption) stay
   deferred with it — `group` will read the run roll-up, not a pinned dataset,
   until that seam lands.
3. **The field set is the spec's, sharpened by the V2 autopsy — and the line is
   enforced both ways.**
   Base fields: `intervention`, `outcome`, `population` (source-named text
   references; nullable population), `effect_direction` (closed set:
   `positive` | `negative` | `null` | `mixed` | `unclear` — a reported null is a
   **finding**, first-class), effect size + type, uncertainty (CI/SE), p-value,
   study-design/sample metadata (design, N, k, I², τ²), the descriptive
   **causality-by-design** label (closed set, plan-pinned, derived from the
   design the source reports), primacy/prevalence flags. Three V2-derived
   sharpenings (rev 1.4, ⚑ flagged at this gate — all inside the
   source-groundability line; candidate minor data-model flow-back):
   - **Outcome ⊥ stratum**: `outcome` is the **base measure only** ("BMI",
     never "BMI at 12 months"); timepoint/subgroup/setting qualifiers are
     structured **stratum qualifiers** on the finding (nullable
     type + value). One finding per (intervention, outcome, effect, stratum) —
     the decomposition that keeps outcome references groupable downstream
     (V2's best prompt rule, lifted).
   - **Comparator**: a nullable source-named reference — an effect direction
     is *versus something* (control, usual care, another arm); reported by the
     source, so a base field.
   - **Estimate level**: closed discriminator {`study` | `pooled` | `claim`} —
     a systematic review's pooled estimate (with k/I²/τ² and pooled
     effect-size types) and a primary study's estimate (with N) are different
     evidence shapes sharing one schema; cross-checked by field rules (pooled
     ⇢ k expected; study ⇢ N expected — violations flag, never block).
   The typed record keeps its dimensions **intact and queryable** —
   `intervention`/`outcome`/`population`/`effect_direction`/`study_design` as
   real columns (filterable now; hybrid-indexing waits at the `retrieve`
   seam), the stats bundle + qualifiers as structured JSONB (exact
   column-vs-JSONB split plan-pinned). **The pydantic record model is the
   single source of truth** for the API response schema *and* the prompt's
   field documentation, `extra="forbid"` — prompt/schema drift is structurally
   impossible (V2 silently discarded three requested fields this way).
   **Not present anywhere** — schema, prompt, or output: normalised magnitude,
   causal weighting, is-beneficial (test-asserted absent from the schema; the
   prompt actively forbids them).
4. **Every finding anchors to its frozen source text — deterministically
   checked.** Each finding carries ≥1 grounding anchor: verbatim supporting
   quote + chunk reference (`chunk_id`; null for abstract-basis findings, which
   anchor against the envelope abstract). At write time the quote is checked by
   normalised string match against the document's frozen text (concatenated
   chunk content, so a boundary-spanning quote isn't a spurious miss — the
   produce-grounded-block presence-check discipline applied at the finding
   grain). **A verified quote records its match location** (chunk id + char
   interval the check found — rev 1.3: the recorded by-product of verify, per
   the data-model; localizes anchors within the coarse-chunk PDFs 008
   documented). Quote-check mechanics pinned from the LangExtract dissection
   (rev 1.4): **normalisation = lowercase + whitespace-collapse + punctuation
   folding** (smart quotes, dashes, NBSP) applied to both sides, with offsets
   always recorded into the **raw** frozen text (never normalise the offset
   substrate); an **ordered occurrence cursor** per document so repeated
   identical quotes map to successive occurrences, never all to the first; a
   **graded match status** recorded per anchor (exact | normalised | failed —
   the method, not just a bit). A finding whose quote fails the check after
   one repair attempt lands **flagged `quote_unverified`, never dropped and
   never silently kept** — the flag rides the finding row and the roll-up
   counts it. **Deterministic
   field-rule validation runs after schema parse** (rev 1.3): bounds and
   consistency checks over the reported statistics (indicatively: p-value ∈
   [0,1], CI lower ≤ upper, N a positive integer, closed vocabularies
   enforced; estimate-level coherence [pooled ⇢ k, study ⇢ N]; **null-like
   strings — "null"/"n/a"/"none"/"unknown"/"" — in nullable fields coerced to
   real null + coverage marker** (rev 1.4: V2's literal-"null" instruction
   polluted every downstream consumer); exact rule set plan-pinned) — a
   violating field is flagged
   `unclear` and counted, never silently accepted (schema validity is the easy
   part; rule checks catch schema-valid nonsense). **Within-doc exact-duplicate
   dedup** (rev 1.4): two findings from one document identical on
   (intervention, outcome, effect direction, stratum, quote) collapse to one,
   deterministically, flagged and counted — MECE is enforced in code, never
   merely requested in the prompt (V2's counting unit was result rows, so
   verbose extraction silently inflated a document's evidence weight).
   Field-level coverage:
   nullable base fields carry a per-field coverage map with values
   `not_extracted` (the source does not report it) | `unclear` (reported
   ambiguously, or failed a validation rule) — the data-model's field-level
   vocabulary; a null field with a marker is coverage, never a claim.
5. **Extraction mechanics — per-source fan-out, windowed, budgeted, honest.**
   Per document: the basis text enters the prompt as **id-keyed segment records**
   (chunk ids as keys) under the standing data/instructions separation; the
   model returns schema-constrained findings, each naming its supporting segment
   id(s) + quote. Documents whose basis exceeds the per-call token budget are
   **windowed** (ordered segment windows, per-window calls, findings
   concatenated; window overlap and size plan-pinned). Every call — single or
   windowed — carries the document's **envelope block** (title + abstract) as
   identity/framing context, assembled by code, data-not-instruction (rev 1.2:
   this is plain prompt assembly, not a header mechanism). Windows are
   **independent and parallelizable** — no cross-window state: the rev-1.1
   running-names header was cut at the gate (it would serialize per-doc windows
   and add state threading for a path ~zero real documents exercise; windowing
   fires only past the per-call token budget, i.e. multi-hundred-page documents
   — the majority of documents fit in one call). Cross-window naming
   consistency, if evals ever show it matters, belongs to the eval-gated
   retrieval-augmented seam. The call budget is known
   pre-run — `Σ_docs ceil(segments/window) × (1 + retry_cap)` — and enforced by
   the existing call-budget pattern before any live call. Failure semantics:
   per-window retry once; a window still failing fails the **document**
   (`extraction_failed`, reason-coded, no partial per-doc finding sets in v1 —
   a failed doc is cleanly retryable as a new run); other documents proceed.
   Extraction failure is **never** selection failure: the component completes
   with failures counted, flagged in the roll-up (`extraction_failures` flag),
   and only fails structurally (missing selection row, scope mismatch).
   Concurrency follows the ingest pattern: parallel calls, **writes in
   selected-set order in the parent** — deterministic DB state regardless of
   completion order.
6. **Abstract-basis extraction is in, honestly labelled.** `select` chose the
   set knowing its full-text mix (`thin_full_text` flag); extract works on what
   select chose. `abstract_only` documents are extracted from the abstract
   envelope — thinner yield expected, never skipped (skipping would silently
   manufacture `not_extracted` for exactly the paywalled/dead-link literature
   the corpus was built not to drop). Every finding and every extraction record
   carries its **basis**; the roll-up reports basis shares; downstream
   grounding sees which text a finding rests on (the data-model's stated purpose
   for `text_basis`).
7. **Coverage accounting — the ladder's last rungs, countable.** Invariants,
   test-enforced: per-doc statuses cover **exactly** the selection row's
   selected set (must-includes included; nothing added, nothing dropped);
   `selected == extracted + no_findings + extraction_failed` (with fresh/reused
   as orthogonal provenance counts); every finding belongs to exactly one
   extraction record belonging to a selected document. Nothing in the payload
   phrases `no_findings`, `extraction_failed` or `not_extracted` as absence —
   they are coverage states; the deep base (`selected/extracted`) is what
   synthesise will later label its gaps with, and this slice's roll-up carries
   those counts so the base is citable. The event summary mirrors 009/010:
   `component.completed` carries the extraction summary (statuses, counts,
   basis shares, flags); no new event types.
8. **Component wiring mirrors 004–010.** `"extract"` in `COMPONENT_REGISTRY`
   requiring `evidence_scope_id` + **`selection_run_id`** (explicit reference,
   compile-fails-closed without it, recorded in provenance and summary — the
   rev-7 pattern from 010; no row for `(scope, selection_run_id)` → honest
   structural failure). `ExtractContext` via `functools.partial`;
   `_run_scope_component`; conditional-edge wiring; skeleton chain extends to
   extract. Edge scopes: empty selection (`selected == []`) → skip honestly
   (`empty_selection` flag, roll-up row records zero-doc run); re-run → new
   run_id, new roll-up row; same-run re-execution loud via
   `UNIQUE (evidence_scope_id, run_id)`. Memo collisions across runs are the
   *point* (reuse), and the per-doc record's unique key makes double-fresh
   extraction of the same `(snapshot, fingerprint)` structurally impossible.
9. **The stub is sentinel-driven and the suite is deterministic.**
   `StubExtractionBackend` returns findings from `_stub_*` metadata sentinels
   (the `_stub_screen`/`_stub_classify` convention): fixture docs can declare
   deterministic findings (including quote text that genuinely occurs in their
   frozen chunks, so the verification path is exercised for real) and failure
   sentinels. Suite and library defaults are stub + socket-deny; `make verify`
   stays egress-free. There is no non-LLM production extraction path —
   the stub is a test seam, not a strategy (unlike select's two strategies).

### Schema

**Gated change 1 — three new tables** (one migration; table count 20 → 23;
exact DDL plan-pinned, shape here binding):

```
source_extraction_record   extraction_record_id PK · project_id FK→project
                           · source_snapshot_id FK→source_snapshot   -- the extracted
                           ·                                            snapshot (full-text
                           ·                                            or envelope)
                           · project_source_snapshot_id (project link)
                           · extraction_fingerprint TEXT NOT NULL
                           · status TEXT CHECK (status IN
                               ('extracted','no_findings','extraction_failed'))
                           · basis TEXT CHECK (basis IN ('full_text','abstract_only'))
                           · error TEXT NULL (reason-coded on failure)
                           · finding_count INT NOT NULL DEFAULT 0
                           · run_id (creating run; assertion provenance)
                           · created_at
                           UNIQUE (project_id, source_snapshot_id,
                                   extraction_fingerprint)      -- the memo key
                           Composite FK (run_id, project_id) — cross-project guard

intervention_outcome_finding
                           finding_id PK · project_id FK→project
                           · extraction_record_id FK→source_extraction_record
                           · intervention TEXT NOT NULL · outcome TEXT NOT NULL
                           · population TEXT NULL
                           · effect_direction TEXT CHECK (effect_direction IN
                               ('positive','negative','null','mixed','unclear'))
                           · study_design TEXT NULL
                           · statistics JSONB      (effect size + type, CI/SE,
                               p-value, N, k, I² — reported values only)
                           · causality_by_design TEXT (closed set, plan-pinned)
                           · primacy/prevalence flags (exact form plan-pinned)
                           · field_coverage JSONB  (per absent field:
                               not_extracted | unclear)
                           · grounding JSONB NOT NULL (anchors: chunk_id NULL for
                               abstract basis · verbatim quote · quote_verified BOOL
                               · match location [chunk id + char interval] when
                               verified — rev 1.3)
                           · created_at

extraction_result          extraction_result_id PK · project_id FK→project
                           · evidence_scope_id · run_id
                           · selection_run_id (the executed reference)
                           · extraction_provenance JSONB NOT NULL (fingerprint,
                               profile id, prompt version, model, backend mode,
                               window/batch params, pass count [1 in v1 —
                               rev 1.3, opens the multi-pass seam cheaply],
                               call budget, retry counts)
                           · docs JSONB NOT NULL (per doc: pss id, status, basis,
                               finding count, fresh|reused, error reason)
                           · counts JSONB NOT NULL (base ladder: selected,
                               extracted, no_findings, failed, fresh, reused,
                               findings total, quote_unverified, basis shares)
                           · flags JSONB NOT NULL (extraction_failures ·
                               empty_selection · thin_extraction where computed)
                           · created_at
                           Composite FKs (evidence_scope_id, project_id),
                           (run_id, project_id) — cross-project guard
                           UNIQUE (evidence_scope_id, run_id)
```

Downgrade drops the three tables. `tests/helpers.py` `delete_project_data`
gains them in FK-safe order (findings → extraction records → extraction_result,
before their ancestors).

### Out of scope

- **`group` and `synthesise`** — the next slices; extract writes findings, reads
  none. The **`query-findings` tool** belongs to them.
- **`implementation_context_finding`** — the second schema stays a named seam
  (mechanisms/barriers/conditions); no field of it sneaks into this schema.
- **The extraction service** — profile resolution against existing records,
  per-source task objects, capability commits; this slice's memo lookup is the
  minimal honest form. **Evidence dataset snapshots** (pinned consumption)
  defer with it.
- **Hybrid-indexing of `intervention`/`outcome`** — committed for v3.0 but its
  mechanism is the `retrieve` adapter's second index target; lands with
  `retrieve`. Columns are filterable now; the seam is recorded.
- **Analysis enrichment** — normalised magnitude, causal weighting,
  is-beneficial (Impact/VfM's layer); any consensus/roll-up machinery.
- **Reference canonicalisation** — intervention/outcome/population strings stay
  source-named; grouping them is component 8's job (`cluster` over findings).
- **The full-text appraisal pass** on the selected subset (the
  appraisal-improvement seam) — still deferred; extract doesn't appraise.
- **Retry/recovery loops** for failed extractions beyond the in-run window
  retry — a failed doc re-enters via a new run (the screen_failed precedent).
- **EB artefact composition** — unchanged; extract writes no artefact/blocks.

## Constraints & approval gates

**Three gated changes (approval needed at this gate):**

1. **Schema** — three new tables (above), one migration; table count 20 → 23.
   No existing-table changes.
2. **Public interface** — the `"extract"` `COMPONENT_REGISTRY` entry +
   `Plan`/`Config` gain `selection_run_id` (required for extract, compile fails
   closed) + `run_harness` gains optional `extraction_backend` (stub default —
   no default egress; the `ranking_backend` precedent).
3. **Runtime egress — one new generation surface, and a materially larger text
   class than 009/010:** `extract_iof_v1` sends **full document text** (the
   frozen chunks, windowed) — not just titles/abstracts — plus the scope intent
   to the chat API. Same provider route and injection posture; the *content*
   crossing the wire grows from envelope to full text. On the live verification
   path this is the openly-licensed fixture corpus only. Full-I/O Langfuse
   traces (user-operated dev instance) will therefore carry document full text —
   flagged here explicitly for approval, per the 009 trace posture.

No new dependency rides this slice (`openai`, `langfuse`, `pydantic` land it
all).

**Explicitly not crossed:** exactly one prompt-bearing surface
(`extract_iof_v1` — no agent loop, no tools, no free text acting on the world);
no new dependency; no auth/tenancy/CI change; no existing-table change; no
artefact/block writes; no new event types; no doc-level status columns on
existing tables (`not_selected`/`not_extracted` stay derivable/recorded, never
canonical doc state).

**Spec flow-backs:** one **candidate minor clarification** rides this contract
(rev 1.4, ⚑ approve or strike at this gate): the data-model's
`intervention_outcome_finding` base-field list gains three source-groundable
sharpenings surfaced by the V2 autopsy — **stratum qualifiers**
(timepoint/subgroup/setting; outcome stays the base measure), **comparator**
(source-named, nullable), and the **estimate-level discriminator**
(study | pooled | claim, with τ² joining the pooled stats). All are "what the
source reports" — the spec's own line — made explicit; `log.md` entry rides
the slice if approved. Components §7 is implemented as written. Other
deferrals ride `docs/deferred.md` as entries, not spec changes.

## Public / private boundary

- On the live path, what leaves: the scope intent and the **full frozen text**
  of selected fixture documents (openly licensed by construction — the
  sanitized-fixtures policy's full-text amendment) to the OpenAI API; full-I/O
  traces to the user-operated dev Langfuse. For arbitrary future corpora this
  surface is private-by-default — the fingerprint/basis machinery keeps
  extraction attributable per document.
- Committed artifacts (schema, prompt text, field vocabularies, verification
  counts) are public-safe. **Finding rows are source-derived text by
  construction** (quotes, source-named references) — they inherit the corpus's
  sensitivity class: public-safe for the fixture corpus, private-by-default
  otherwise (the 010 reason-strings precedent, stronger here).

## Model route

**Extraction**: a judgment-capable model behind the `ExtractionBackend` seam —
`gpt-5-mini`-class floor (the 009 nano lesson is binding); whether extraction
quality on real full text needs a step up from mini is a **plan-gate pin** with
a live-run cost note (extraction is the deliberately-expensive Tier-1 step; the
budget arithmetic must make the cost visible pre-run). → Bedrock at the seam
swap, unchanged. **Prompt-bearing surface: `extract_iof_v1`** — the repo's third
product prompt, lead-authored, versioned, recorded in `extraction_provenance`
and the event payload; the only prompt in the slice. Prompt design carries
**explicit negative rules** (rev 1.3): it states what must NOT be extracted
(question-relative judgements, cross-source claims, anything this document
does not itself report) — actively limiting degrees of freedom, not just
omitting the ask; enrichment absence stays test-asserted on the schema side.
Further prompt requirements (rev 1.4): quotes must be **verbatim exact text,
never paraphrased**; the prompt receives the document's
`primary_evidence_type` as context, with pooled-vs-study guidance (an SR
reports meta-analytic estimates per outcome × stratum; a primary study reports
its own) — one prompt surface, evidence-type-conditioned, not prompt families;
**an empty findings list is explicitly legal** ("this document reports no
intervention–outcome findings" is a valid, expected answer — V2 forced
effect-shaped output onto qualitative/policy documents and got fabricated
stats); V2's prevalence-only skip/extract examples and
control-arms-are-not-interventions rule are mined into the prompt (unsure →
`prevalence_only = true`). **Pre-flight example validation** (rev 1.4,
LangExtract's guardrail): at load, the quote-verifier runs over the prompt's
own few-shot examples — a demonstration whose quote is not verbatim in its
example text fails loudly before any API call.

## Disciplines binding this slice

- **Source-groundability is the schema line** — every field is something the
  source reports; every finding anchors to frozen text; no judgement fields.
- **Flag, don't drop** — abstract-only docs extracted, basis-flagged; unverified
  quotes flagged, never silently kept or dropped; failed docs counted and
  reason-coded, never skipped silently; absent fields carry coverage markers.
- **Honest absence** — `no_findings`, `extraction_failed`, `not_extracted` are
  coverage, never phrased as absence; the roll-up carries the base ladder so
  every downstream claim can cite its base.
- **Durable means durable** — findings are never invalidated by later runs;
  new model/prompt = new fingerprint = new records alongside, never overwrite.
- **Deterministic where claimed** — the fan-out, memo, windowing, quote check
  and writes are deterministic; only the model call is interpretive, and its
  entire I/O is attributable (fingerprint, provenance, traces).
- **Model only what behaves** — no enrichment columns, no second schema's
  fields, no index machinery before its reader.
- **Never silent, never fake** — the stub's fingerprint says it's a stub;
  missing upstream state fails structurally; partial writes don't exist.

## Stop conditions

- Any gated change (schema · public interface · egress) not yet approved, or
  any change beyond them (existing-table change, new dependency, a second
  prompt surface, doc-level status columns).
- Any *suite or library-default* code path would perform network I/O.
- The extraction wants question-relative fields, canonicalisation, or
  cross-source reasoning — that's enrichment/group/synthesise territory; halt.
- The backend wants capabilities beyond schema-constrained findings per
  document (tools, multi-turn, free text acting on the world) — halt.
- Windowing/merge complexity grows past "ordered windows, concatenated
  findings" (e.g. cross-window dedup heuristics) — stop and bring the design
  back to the plan gate rather than growing it silently.
- `make verify` red with unclear root cause; or the turn/token budget is spent.

## Acceptance checks

- `make verify` (okf-validate · test · typecheck · lint · build) — green,
  deterministic, zero egress (socket-deny covers an extract round-trip; suite
  runs on the stub only).
- **One manual live check** (evidence in verification.md): skeleton end-to-end
  with `OPENAI_API_KEY` (+ `LANGFUSE_*`) against the fixture corpus — real
  `extract_iof_v1` calls over the selected set (10-full-text/14-abstract mix
  flowing through select's budget), findings written with verified quotes,
  memo behaviour shown (a second run reuses, zero fresh calls for unchanged
  docs), extraction summary rendered, calls visible in the dev Langfuse trace
  (prompt version, tokens/cost) with **run-level grounding scores** (rev 1.4:
  quote-verified share, field-coverage shares, dedup/fallback counts — the 009
  `score_summary` pattern; V2's extraction quality was never measured, ours is
  measurable from the first live run); per-run counts and an honest cost note
  recorded; keys absent from captured output.
- Deterministic vs AI eval: all suite checks are deterministic (stub backend).
  Extraction *quality* (are the findings right/complete?) is eval territory —
  the finding-level ground truth needs the eval workstream; this slice's bar is
  machinery correctness, schema fidelity, honest coverage accounting, and
  verified anchoring. Named explicitly so the review stack doesn't mistake
  machinery tests for a quality claim.

## Verification evidence expected

`verification.md` must include:
- `make verify` table with pass counts; socket-deny result named.
- Migration roundtrip clean; table count 23.
- Named test results: memo semantics (hit → reuse, no call, no new rows; stub
  vs live fingerprints distinct; `no_findings` memoised and not re-paid),
  coverage invariants (statuses cover exactly the selected set;
  `selected == extracted + no_findings + failed`; findings ↔ records ↔ selected
  docs), quote verification (verbatim hit passes; boundary-spanning quote
  passes; fabricated quote → flagged `quote_unverified`, kept, counted),
  abstract-basis extraction (no chunks; anchors against envelope abstract;
  basis recorded end-to-end), verified-quote match location recorded (chunk +
  char interval present on verified anchors, absent on unverified — rev 1.3),
  field-rule validation (out-of-bounds p-value / inverted CI / non-positive N →
  field flagged `unclear`, counted, finding kept — rev 1.3; null-like string →
  real null + coverage marker; estimate-level coherence — rev 1.4),
  repeated-quote cursor (two findings citing the same sentence twice ground to
  successive occurrences — rev 1.4), match-status grading recorded per anchor
  (rev 1.4), within-doc exact-duplicate dedup (collapsed, flagged, counted —
  rev 1.4), pre-flight example validation (a deliberately non-verbatim few-shot
  example fails at load — rev 1.4), empty-findings-is-legal (a fixture doc with
  no IOF content yields `no_findings`, no forced stats — rev 1.4), windowing
  (multi-window doc: budget arithmetic,
  ordered concatenation, window-failure → doc `extraction_failed`, others
  proceed), schema line (enrichment fields absent from schema and prompt,
  test-asserted; prompt carries explicit negative rules, asserted on the built
  prompt — rev 1.3), field coverage (absent field → marker, never a fabricated
  value), edge scopes (empty selection honest-skip; missing selection row →
  structural failure; same-run re-execution loud), determinism (two stub runs →
  identical payload columns; parallel-vs-serial write order), injection posture
  (id-keyed segment records under data/instructions separation asserted on the
  built prompt; a prompt-injection-shaped chunk lands as inert finding data or
  no finding, never instruction-following), delete-order integrity.
- Live-run evidence per the manual check above.
- Public-safety confirmation (full-text egress was fixture-corpus only; traces
  on the user-operated instance; keys clean).
- Deferred seams recorded in `docs/deferred.md`: extraction service + evidence
  dataset snapshots · hybrid-indexing of intervention/outcome at the `retrieve`
  seam · `implementation_context_finding` (pointer exists — extend with the
  extract-side note) · extraction-quality evals (finding-level ground truth;
  also unblocks 010's recorded rerank-quality eval seam — note the pointer) ·
  failed-extraction recovery loop · cross-window dedup if observed in practice ·
  **generic finding container, declined** (rev 1.1 — revisit only if a third
  finding schema is specced) · **retrieval-scoped extraction, declined**
  (rev 1.1 — coverage-honesty violation; any future retrieval scoping must be an
  explicit, recorded coverage-base rung, never silent) ·
  **retrieval-augmented extraction** (full read + targeted in-doc repair pass /
  cross-window context assembly — eval-gated behind `retrieve` +
  extraction-quality evals, rev 1.1) · **multi-pass recall extraction**
  (rev 1.3 — a second extraction pass raises recall on long documents; can't be
  measured without ground truth, so eval-gated with the same trigger family;
  provenance records pass count from day one) · **reason-then-constrain
  extraction** (rev 1.3 — draft free-form then bind to schema; demonstrated
  gains are on small open-weight models, closed-weight API models resist the
  format tax; eval-gated remedy if judgment-heavy fields show errors) ·
  **LangExtract dependency, declined** (rev 1.3 — techniques absorbed [span
  recording, negative rules, multi-pass seam]; the library itself is
  Gemini-first and outside our provenance model) · **parse-quality escalation
  pointer** (rev 1.3 — extraction yield/failures on the 008-documented
  collapsed-chunk PDFs become the first downstream consumer signal for the
  docling ML-escalation seam; note on the existing entry) ·
  **per-intervention focused-call decomposition** (rev 1.4 — V2's
  cross-contamination remedy: one intervention per call; eval-gated remedy if
  quality evals show cross-finding contamination in the per-doc call) ·
  **bounded fuzzy quote fallback** (rev 1.4 — LangExtract's coverage+density
  gated LCS tier, fuzzy-only-on-failure; adopt only if evals show
  exact-normalised recall insufficient, and never inside the verified-verbatim
  guarantee) · **V2 CFIR implementation-profile fields**
  (cost/staffing/complexity + the inner-setting rule) recorded as design input
  to the `implementation_context_finding` seam · **mixed/unclear findings are
  first-class** — carried forward as a requirement on group/synthesise (V2
  extracted them, then aggregation silently zeroed them; flag-not-drop must
  survive the whole deep chain).
- Diff summary (data files excluded from review diffs per the 007 retro).

## Risk tier & review focus

**Tier 3** — schema is a hard gate (three new tables, the framework's first
findings-layer records), runtime egress grows to full-text content, and the
component is the trust path's sharpest edge: findings are what synthesise will
ground claims in, and extraction is where a model could fabricate
source-attributed content at scale. Contract- and plan-stage adversarial
reviews standard; review stack sized per the review-economy notes (medium
`/code-review`, one security lane, class-split budget, per-angle diff scoping).
ADR due at step 4 (findings-layer landing: durable records, memo fingerprint,
quote anchoring, three-table shape).

Review focus:
- **Provenance/honesty (the headline lane)**: every finding single-source,
  anchored, verified-or-flagged; coverage states never phrased as absence; the
  base ladder countable end-to-end; reused findings attributed to their
  creating run/fingerprint; nothing invalidates or overwrites prior findings.
- **Security / prompt surface**: `extract_iof_v1` injection posture — full
  document text is the largest untrusted input yet; id-keyed data records,
  schema-constrained output, no tools; quotes/references are untrusted model
  output stored as data; a hijacked model can at worst emit wrong findings for
  its own document — flagged-or-verified, never instruction-following. Key
  hygiene; egress bounded (selected docs only, pre-run call budget, socket-deny
  on suite paths).
- **Correctness**: memo-key semantics (no double-extraction, no stale reuse
  across fingerprints); window arithmetic and budget enforcement; quote
  normalisation (boundary-spanning, whitespace/unicode); invariant sums; FK
  and delete order; concurrency-safe write ordering.
- **Schema fidelity**: the field set matches data-model verbatim; closed
  vocabularies enforced by CHECK or validation; no enrichment leakage.
- **Scope**: no group/synthesise reach-through, no canonicalisation, no
  service machinery, no second schema fields, suite egress-free.
