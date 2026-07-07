# Task contract: 012-group

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md);
specs in [docs/specs/](../../specs/index.md).

> **Status:** **approved** (rev 1.3) — contract-stage adversarial review
> adjudicated (10/10 adopted, none flipping a user-settled decision; the one
> behaviour-shaping adoption — fail-closed scale cap — flagged for the plan 🛑);
> planning next.
> Contract approved (before planning): **2026-07-07 · Shabeer Rauf** (rev 1.2,
> covering the three gated changes — one run-scoped `grouping_result` table ·
> `"group"` registry entry + `extraction_run_id` + `facet_grouping_backend` +
> the `grouping_backend` → `theme_grouping_backend` symmetry rename · the
> `group_facet_v1` generation surface incl. facet-value strings in Langfuse
> traces) ·
> Plan approved (before implementation): _date · who_ · ADR: _due at step 4 if a
> design decision is made or changed_.
>
> **Revision history:**
> - **rev 1** (2026-07-07): initial draft.
> - **rev 1.1** (2026-07-07, user challenges at the gate — adjudicated):
>   **(a) run-local persistence held** (rationale as first stated — superseded
>   by the corrected rev 1.2 rationale below).
>   **(b) same-tool framing adopted** — the spec already models characterise
>   and group as wrappers over the one shared **`cluster`** tool (tool-wiring
>   table: "`cluster` (topic)" vs "`cluster` (facet, over findings)"); the
>   difference is the component wrapper (input record grain, what the output
>   feeds, persistence policy). Build leaning recorded in decision 6: the
>   deterministic skeleton (id-keyed records → schema-constrained call →
>   validation → one targeted repair → counted residual, pre-run budget) is
>   the shared cluster core, factored with 009's `grouping.py` where the code
>   genuinely coincides — exact factoring plan-pinned; no forced generic
>   protocol across the two I/O shapes.
>   **(c) naming adopted** — `GroupingBackend` vs `FacetGroupingBackend` is
>   confusing; the pair becomes **`ThemeGroupingBackend`** (rename of 009's,
>   matching its own `Theme`/`discover_themes` vocabulary) and
>   **`FacetGroupingBackend`**; `run_harness(grouping_backend=…)` renames to
>   `theme_grouping_backend` — a public-interface change riding gate 2.
> - **rev 1.2** (2026-07-07, second round of user challenges — the rev 1.1a
>   rationale corrected against the code; decision 1 still held):
>   **(a) conceded:** characterise's memberships DO persist — `characterise.py`
>   writes one `source_tag` row per (doc, theme) assignment, so each doc↔theme
>   edge lands durably in the tag layer; only the grouping-as-a-structure
>   (descriptions, sizes, the unclustered set) is run-row-only. The asymmetry
>   argument is therefore **not** "characterise doesn't persist memberships";
>   it is: **(i) the persistence target exists there and not here** — a topic
>   tag is a claim *about a document* and documents have a standing accreting
>   annotation layer built for that; group's members are findings/reference
>   values, which have no analogous layer — persisting would mean new
>   information-layer machinery; **(ii) the claim differs in kind** — a
>   facet-group label bundling "Housing First" / "HF programme" / "supported
>   housing" asserts that different sources' strings name the same thing — an
>   entity-resolution judgment, often question-relative — which made canonical
>   becomes ground truth downstream capabilities silently trust before any
>   quality bar for it exists. **(b) future readers affirmed, and already
>   staged:** run-local ≠ ephemeral — the `grouping_result` row is durable,
>   run-referenced, provenance-complete, and the artefact-composition seam
>   reflects groups into durable blocks; Options Assessment is the named
>   future consumer ("resolves descriptive intervention clusters into named,
>   comparable options") and reads a *specific* grouping by reference. What
>   stays deferred is only **canonical promotion**, for which the data-model
>   pins the exact ladder this slice is rung 1 of: *run-local → project-scoped
>   persistent → graph datastore, gated on an entity-resolution-quality bar*.
>   Research-workflow check (user ask): published intervention typologies are
>   reusable outputs, but reuse is deliberate adoption of a specific published
>   taxonomy versioned with its review — reference-mediated reuse mirrors
>   that; a silently-maintained living taxonomy would not. Recorded in the
>   deferred-seams list as the facet-theme promotion seam.
> - **rev 1.3** (2026-07-07): contract-stage adversarial review adjudicated
>   (Codex, 10 findings: 1 blocker · 7 majors · 2 minors — 10/10 adopted; none
>   contradicted a user-settled decision). Blocker: **finding-set resolution
>   re-pinned to the roll-up's `docs[].extraction_record_id`** (extract
>   already records it per doc, fresh and reused; memo-key re-resolution was
>   ambiguous for failed rows) with an integrity cross-check against
>   `counts.findings_total`. Majors: **partition vocabulary fixed** — the
>   partition = named groups + `ungrouped` + `no_value`; direction spreads
>   recorded per group, per residual bucket, and overall (rubric item 9
>   reworded: first-class *in the partition*) · **scale guard = fail closed**
>   — above `FACET_VALUE_CAP` the component fails structurally
>   (`value_cap_exceeded`), never a degraded sample-discover/assign pass
>   (tail-only groups can't be discovered from a head sample — silent
>   `ungrouped` inflation; the real scale algorithm is an eval-gated seam) ·
>   **deterministic label/description validation** added beyond prompt rules
>   (the 009 `validate_themes` precedent): nonempty, length caps, control
>   chars, duplicate labels, exact forbidden generic labels — violations
>   reject the response (one repair), never accepted · **labels/descriptions
>   pinned as untrusted model output**: bounded/validated, rendered escaped,
>   and a carried-forward requirement on synthesise — group labels enter
>   downstream prompts as data, never instructions · **`query-findings`
>   deferral recorded as an explicit spec deviation** (components §8 declares
>   it; "implemented as written" softened accordingly) · **rename ripple
>   corrected** — references span harness/tracing/skeleton/characterise +
>   tests (grep-verified), acceptance is a grep-driven sweep; historical
>   task-docs/ADRs exempt · **inherited provenance payload pinned**:
>   extraction fingerprint + profile, referenced run id, base-ladder counts,
>   finding-set size + sha256 hash over sorted finding ids, and the facet's
>   field-coverage/no-value breakdown. Minors: directive parsing rules
>   inlined (object-only, allowed keys `{"facet"}`, string cap, no control
>   chars, closed enum, unknown keys fail closed) · code-grounding corrected
>   (11 migrations, not 12 — this slice ships migration 12).

## Goal

Add **group** — EB component 8, facet-level theming, the distinct component
between extract and synthesise (not folded into the write-up). Over the findings
of an explicitly referenced extraction run, group on the **intent-derived
facet**: in v3.0 one of the facets the schema supports — **intervention |
outcome | population**, the source-named references — *not* v2's fixed four.
Mechanisms/barriers/conditions stay **landscape-only** until the
`implementation_context_finding` seam lands.

This is the **second clustering** in the chain (topic-level over documents at
characterise; facet-level over extracted findings here), and like the first it
is an **interpretive shape, not a count** (EB provenance grade 3) — recomputable,
never a deterministic fact — with one addition: facet grouping **inherits the
extraction dependency**, so its provenance carries the *(finding-set,
coverage-state, extraction-profile)* base it rests on.

Groups are **run-local execution state** (capability.md § Cluster persistence) —
checkpointed in a run-scoped roll-up row, later reflected in durable artefact
blocks by the composition seam, but **never promoted to canonical, queryable
state**. Unlike 011's durable findings layer, this slice writes no
information-layer records: findings are read, never mutated; no tags are
written (the topic-tag persistence at characterise was that component's spec'd
behaviour, not a pattern group repeats — components §8 names none).

The slice completes the deep chain's penultimate step: synthesise (013) will
read these groups and produce a grounded block per group.

## Deliverable

A PR on `task/012-group` → `dev` that:

- Ships `group.py`: `GroupContext(scope_id, intent, context, extraction_run_id)`;
  `group_findings(...)` — extraction-roll-up load → finding-set resolution →
  facet-value extraction → LLM partition of distinct values → deterministic
  membership derivation → roll-up row write → grouping summary in
  `component.completed`.
- Ships the **`FacetGroupingBackend`** seam (the
  `GroupingBackend`/`RankingBackend`/`ExtractionBackend` pattern): protocol +
  `OpenAIFacetGroupingBackend` (schema-constrained structured outputs, id-keyed
  value records, caller-owned retry/budget) + deterministic sentinel-driven stub
  for the suite, and the **`group_facet_v1` prompt** (lead-authored, versioned,
  recorded in provenance) — the slice's only prompt-bearing surface. Both
  clusterers are wrappers over the one shared `cluster` tool (rev 1.1): 009's
  `GroupingBackend` renames to **`ThemeGroupingBackend`** (and the `run_harness`
  kwarg to `theme_grouping_backend`) so the pair is symmetric, and the shared
  deterministic skeleton is factored with `grouping.py` where it genuinely
  coincides.
- Adds **one table — `grouping_result`** — via one Alembic migration (gated
  change 1; table count 23 → 24), project-scope-guarded per repo discipline.
- Registers `"group"` in `COMPONENT_REGISTRY` (requires `evidence_scope_id` +
  **`extraction_run_id`** — the explicit-reference pattern from 010/011);
  `run_harness` gains one optional **`facet_grouping_backend`** parameter (stub
  default — no default egress; gated change 2).
- Extends `skeleton.py`: … extract → **group**, rendering the grouping summary
  (facet, groups + sizes, ungrouped/no_value counts, direction spreads, flags).
- Records the deferred seams in `docs/deferred.md`; updates `tests/helpers.py`
  delete order for the new table.
- Passes `make verify` — all green, deterministic, egress-free.

## Read first

- [EB components §8 — group](../../specs/capabilities/evidence-base/components.md)
  — the component contract: facet-level theming on the intent-derived facet,
  the v3.0 facet set, the second clustering, `cluster` over finding records /
  dimension values + `query-findings`. Also §5 (the first clustering's shape —
  bounded validated LLM grouping, counted `unclustered`, code-enforced
  exhaustiveness) and §9 (what synthesise will do with the groups — sets what
  the roll-up must carry).
- [EB capability — Cluster persistence](../../specs/capabilities/evidence-base/capability.md)
  — groups are run-local, never canonical; also § Output structure (the
  orchestrator composes sections per facet/intervention family — group's output
  is the substrate for that) and the scope boundary: **precise option
  resolution is out of EB** — groups are *descriptive* corpus-grounded
  clusters; resolving them into named comparable options is Options
  Assessment's (⏸).
- [EB provenance](../../specs/capabilities/evidence-base/provenance.md) —
  grade 3: thematic clustering is an interpretive shape, softest grade; facet
  grouping additionally inherits the extraction dependency.
- [System data-model — the findings layer](../../specs/system/data-model.md) —
  the source-named references being grouped (intervention/outcome/population
  are groupable/canonicalisable *downstream*, never baked-in canonical
  entities); coverage states as gap provenance.
- [System execution-orchestration](../../specs/system/execution-orchestration.md)
  — `query-findings` is a scoped tool (capabilities reading the findings
  layer); components realise as the mechanism their nature demands, invoked as
  one facade.
- [011-extract contract](../011-extract/contract.md) — pattern precedent:
  explicit upstream-run reference, run roll-up shape, injection posture,
  call-budget discipline; and the carried-forward requirement it recorded on
  this slice: **mixed/unclear findings are first-class and must survive
  grouping** (V2 extracted them, then aggregation silently zeroed them).
- [docs/deferred.md](../../deferred.md) — the `group`-component inheritance
  entry (task 009): v2's theming lessons and recorded defects to avoid (dead
  critique stage, silent concept drops, "General Theme" collapse, no scale
  guard, unseeded runs); `implementation_context_finding` (cross-schema linkage
  reference-mediated via group — the seam this slice leaves open, not builds);
  graph-structured synthesis (⏸, never an ingestion-time KG).

**Code grounding (surveyed 2026-07-07; corrected rev 1.3):** 23 tables, 11
migrations (this slice ships migration 12). Findings:
`intervention_outcome_finding` rows carry `intervention`/`outcome` (NOT NULL),
`population`/`comparator` (nullable), `effect_direction` (closed set incl.
`mixed`/`unclear`), `stratum_qualifiers`, `statistics`, `grounding` — FK to
`source_extraction_record (extraction_record_id, project_id)`. The extraction
roll-up: `extraction_result` `UNIQUE (evidence_scope_id, run_id)`, `docs` JSONB
(per doc: pss id, status, basis, finding count, fresh|reused),
`extraction_provenance` carries the executed fingerprint — and each `docs[]`
entry records its **`extraction_record_id`** (fresh and reused alike,
extract.py:803), so a run's finding set resolves directly:
`docs[].extraction_record_id` → findings by FK, project-guarded (rev 1.3
blocker fix — never re-derived via the memo key, which failed rows make
ambiguous); resolved count cross-checked against `counts.findings_total`,
mismatch = structural failure. Backend pattern: protocol +
stub + OpenAI class with pydantic `response_format`, module-constant prompts +
`PROMPT_VERSION`, caller-owned budget, validation separated from the call
(`gpt-5-mini` floor — the 009 nano lesson). The 009 grouping precedent
(`grouping.py`): discovery + batched assignment, code-enforced exhaustiveness
with targeted repair, counted `unclustered`, `1 + ceil(n/batch)` budget.
Component wiring: registry entry + required Config field → context dataclass →
`_run_scope_component` → `component.*` events; `skeleton.py` threads upstream
run ids as optional kwargs and switches stub/live on `OPENAI_API_KEY`.
Directive-parsing precedent: `select.py` parses `evidence_scope.context`
fail-closed with input caps (untrusted JSONB).

## Scope

### Design decisions embedded here (approve or flip at this gate)

1. **One run-scoped table; groups are run-local by spec.** `grouping_result`
   mirrors `characterisation_result`/`selection_result`: one row per
   `(evidence_scope_id, run_id)`, carrying the facet, the executed
   `extraction_run_id`, grouping provenance, the groups themselves, counts and
   flags. No new durable records, no finding mutation, no `source_tag` writes,
   no group entity table — a group's identity lives and dies with its run
   (recomputable interpretive shape). Synthesise will reference this row by
   `grouping_run_id`, exactly as group references `extraction_run_id`.
   Run-local ≠ ephemeral: the row is durable, run-referenced and
   provenance-complete — downstream capabilities (Options Assessment is the
   named one) interrogate a *specific* grouping by reference, and the
   artefact-composition seam reflects groups into durable blocks. What is
   deferred is only **canonical promotion** — a project-level taxonomy trusted
   without a reference — because a facet-group label is an entity-resolution
   judgment over different sources' own vocabularies (often
   question-relative), and the data-model stages its promotion explicitly:
   *run-local → project-scoped persistent → graph datastore, gated on an
   entity-resolution-quality bar*. This slice is rung 1 of that ladder
   (rev 1.2; the asymmetry with characterise's tag persistence is that doc
   topics have a standing annotation layer to land in — findings/reference
   values do not).
2. **Group over distinct facet values; membership derives deterministically.**
   Components §8 allows `cluster` over "finding records / dimension values" —
   this slice clusters the **values**: the distinct source-named strings of the
   chosen facet (with light deterministic context per value: finding count,
   the paired counterpart references — e.g. for the intervention facet, the
   outcome names it was studied against). The LLM's job is exactly one
   judgment: partition source-named values into coherent named groups. Finding
   membership then derives **in code**: finding → its facet value → the value's
   group. This keeps the interpretive surface minimal, makes
   finding-exhaustiveness structural (every finding has a value or lands in
   `no_value`), and sends only reference strings — never quotes, stats or full
   findings — over the wire.
3. **Exhaustiveness is code-enforced; the residual is honest.** The
   **partition** = named groups + `ungrouped` + `no_value` (rev 1.3
   vocabulary). Every distinct value is assigned to exactly one group or
   explicitly returned as ungroupable; validation (the 009 shape) checks the
   partition — unknown ids, missing ids, duplicate assignment all fail the
   response; one targeted repair pass re-asks only the missing values;
   still-missing values land in a counted **`ungrouped`** bucket, never
   silently dropped and never forced into a catch-all. **Validation is
   deterministic output-checking, not just prompt rules** (rev 1.3, the 009
   `validate_themes` precedent): labels/descriptions checked for nonemptiness,
   length caps, control characters, duplicate labels, and an exact
   case-insensitive forbidden-generic-label set ("general", "miscellaneous",
   "other", "misc", "general theme", "uncategorised", "uncategorized" —
   plan-review alignment, minor fold; v2's collapse defect closed in code); a violating
   response is rejected (one repair), never accepted. Broader label *quality*
   stays at the eval seam.
   Findings whose facet value is NULL (population is nullable) land in a
   counted **`no_value`** bucket — coverage, not a group. Empty edge scopes are
   honest skips: an extraction run with zero findings → roll-up row with zero
   groups + `empty_findings` flag; all-null facet → `no_value` carries
   everything, flagged.
4. **Mixed/unclear findings are first-class members** (the 011 carried-forward
   requirement, binding here): the grouped set is **exactly** the referenced
   run's finding set — memo-reused findings included, every effect direction
   included. The roll-up records the **direction spread** per group, **per
   residual bucket (`ungrouped`, `no_value`) and overall** (rev 1.3 — a mixed
   finding in a residual is as visible as one in a group): deterministic
   counts by `effect_direction`, `mixed` and `unclear` as visible classes —
   descriptive counts for synthesise's "5 of 7 positive,
   two null" steer, never a verdict (the weighted consensus roll-up stays ⏸).
   Test-enforced invariants: grouped finding ids == the run's finding set;
   every finding in exactly one group or `ungrouped`-via-value or `no_value`;
   `Σ group sizes + ungrouped + no_value == findings total`; direction-spread
   sums equal group sizes.
5. **The facet is intent-derived, explicitly sourced, fail-closed.** v3.0
   sources it from `evidence_scope.context["grouping"]` (the selection-directive
   precedent): optional `{"facet": "intervention" | "outcome" | "population"}`.
   Parsing rules inline (rev 1.3, the select precedent made explicit): the
   `"grouping"` value must be an object; allowed keys exactly `{"facet"}` —
   unknown keys fail closed; the facet string is capped (≤ 200 chars), control
   characters rejected, and validated against the closed enum; absent/empty
   directive → the default. Any violation raises the directive error — the
   component fails closed, never guesses.
   Default facet: **`intervention`** (capability.md: synthesis sections are
   "typically one per facet/intervention family"). The executed facet + its
   source (`default` | `scope_context`) are recorded in provenance and the
   summary. The agent-authored just-in-time directive stays at the same seam as
   select's.
6. **Mechanics — one partition call, validated, budgeted, scale-guarded.** The
   distinct values enter one schema-constrained call as **id-keyed data
   records** (the standing data/instructions separation; values are
   source-derived untrusted text). Call budget known pre-run:
   `1 + repair_cap` (repair_cap = 1), always. **Scale guard = fail closed**
   (rev 1.3, replacing the rev-1 sample-discover/assign idea — a head sample
   cannot discover tail-only groups, so rare concepts would silently inflate
   `ungrouped`): distinct values above a plan-pinned **`FACET_VALUE_CAP`**
   fail the component structurally (`value_cap_exceeded`, loud, naming the
   cap) — v2's no-scale-guard defect closed by an explicit ceiling, never a
   degraded pass; the real large-corpus algorithm is an eval-gated seam, and
   the fixture corpus sits far under the cap by construction. Value
   ordering into the prompt is deterministic (sorted), so identical inputs
   yield identical prompts (v2's unseeded-runs defect closed at the boundary we
   control; the model call itself stays interpretive-by-nature). Backend
   failure after retries fails the component honestly (`component.failed`) —
   grouping has no deterministic fallback strategy and a partial grouping is
   worse than none; the extraction run is untouched and a retry is a new run.
   **Shared cluster core** (rev 1.1b): this skeleton — id-keyed records in,
   schema-constrained call, validation, one targeted repair, counted residual,
   pre-run budget — is the same shape 009's `grouping.py` runs; both backends
   are wrappers over the spec's one shared `cluster` tool, so the build
   factors the deterministic skeleton with `grouping.py` where the code
   genuinely coincides (exact factoring plan-pinned; prompts and record
   grains stay per-surface, and no generic protocol is forced over the two
   different I/O shapes).
7. **Component wiring mirrors 004–011.** `"group"` in `COMPONENT_REGISTRY`
   requiring `evidence_scope_id` + **`extraction_run_id`** (compile-fails-closed
   without it; no `extraction_result` row for `(scope, extraction_run_id)` →
   honest structural failure). `GroupContext` via `functools.partial`;
   `_run_scope_component`; skeleton chain extends to group, threading
   `extraction_run_id` as the optional-kwarg precedent does. Re-run → new
   run_id, new roll-up row; same-run re-execution loud via
   `UNIQUE (evidence_scope_id, run_id)`. `component.completed` carries the
   grouping summary; **no new event types**.
8. **The stub is sentinel-driven and the suite is deterministic.**
   `StubFacetGroupingBackend` partitions values deterministically (sentinel-
   driven where fixtures declare groups; a stable normalised-value fallback
   otherwise), exercising validation, repair and residual paths for real.
   Suite and library defaults are stub + socket-deny; `make verify` stays
   egress-free. The stub is a test seam, not a strategy.
9. **`query-findings` and the agent realisation stay seams.** Components §8
   marks group's realisation "agent"; v3.0 realises it — like characterise
   ("procedure + agent") and select before it — as a bounded procedure invoked
   as one facade, with `skeleton.py` standing in for the orchestrating agent
   (the capability-run seam owns the upgrade). The **`query-findings`** scoped
   read tool is declared by both group and synthesise; group's v3.0 read is a
   direct deterministic load of the referenced run's findings, and the tool
   lands with its deliberative consumer (synthesise's agent-loop) — recorded in
   `docs/deferred.md`, not silently skipped.

### Schema

**Gated change 1 — one new table** (one migration; table count 23 → 24; exact
DDL plan-pinned, shape here binding):

```
grouping_result   grouping_result_id PK · project_id FK→project
                  · evidence_scope_id · run_id
                  · extraction_run_id (the executed reference)
                  · facet TEXT NOT NULL CHECK (facet IN
                      ('intervention','outcome','population'))
                  · grouping_provenance JSONB NOT NULL (prompt version, model,
                      backend mode, facet source [default|scope_context],
                      call/repair counts, value cap, and the inherited
                      extraction base — pinned rev 1.3: extraction fingerprint
                      + profile id, the referenced extraction_run_id, the
                      run's base-ladder counts (selected/extracted/
                      no_findings/failed/findings_total), finding-set size +
                      sha256 over the sorted finding ids, and the facet's
                      coverage breakdown (values with findings vs no_value
                      count) — the (finding-set, coverage-state,
                      extraction-profile) provenance the spec requires)
                  · groups JSONB NOT NULL (per group: label, description,
                      member values, member finding ids, size, direction
                      spread; plus the ungrouped value/finding sets and the
                      no_value finding set, each with its direction spread —
                      rev 1.3; run-local by design)
                  · counts JSONB NOT NULL (findings total, grouped, ungrouped,
                      no_value, distinct values, groups)
                  · flags JSONB NOT NULL (empty_findings · all_no_value ·
                      ungrouped_values where present)
                  · created_at
                  Composite FKs (evidence_scope_id, project_id),
                  (run_id, project_id) — cross-project guards
                  FK (evidence_scope_id, extraction_run_id) →
                      extraction_result (evidence_scope_id, run_id) — the
                      executed extraction must exist for this scope
                  UNIQUE (evidence_scope_id, run_id)
```

Downgrade drops the table. `tests/helpers.py` `delete_project_data` gains it in
FK-safe order (before `extraction_result`).

### Out of scope

- **`synthesise`** — the next slice; group writes the roll-up, produces no
  grounded blocks, no artefact, no sections. **`produce-grounded-block`** over
  groups belongs to it.
- **`query-findings` as a tool object** — deferred to synthesise's agent-loop
  (decision 9); group reads deterministically.
- **Canonicalisation / option resolution** — group labels are descriptive
  corpus-grounded clusters over source-named values; no canonical entity is
  minted, no cross-source identity asserted (Options Assessment's job, ⏸).
- **Cross-schema linkage** — `implementation_context_finding` stays a named
  seam; reference-mediated linkage via group is the *design property that the
  seam will use* (shared source-named vocabulary), not machinery built now.
- **Weighted consensus / strength roll-up** — direction spreads are counts,
  never verdicts (the ⏸ consensus seam).
- **Cluster persistence beyond the run row** — no group entities, no tags, no
  finding columns; nothing canonical.
- **Embedding-based clustering** of values/findings — the LLM partition is the
  v3.0 mechanism; vectors' first reader remains `retrieve` (009 posture).
- **Graph-structured synthesis** — ⏸, its own seam.
- **Re-grouping/steering UX** — a different facet is simply a new run with a
  different directive; no interactive machinery.

## Constraints & approval gates

**Three gated changes (approval needed at this gate):**

1. **Schema** — one new run-scoped table (above), one migration; table count
   23 → 24. No existing-table changes.
2. **Public interface** — the `"group"` `COMPONENT_REGISTRY` entry +
   `Plan`/`Config` gain `extraction_run_id` (required for group, compile fails
   closed) + `run_harness` gains optional `facet_grouping_backend` (stub
   default — no default egress) + **the symmetry rename** (rev 1.1c):
   `run_harness(grouping_backend=…)` → `theme_grouping_backend`
   (`GroupingBackend` and its `OpenAI`/`Stub`/`Traced` forms → `Theme…`
   internally) — no behaviour change, no back-compat shim (pre-release repo).
   Ripple corrected rev 1.3: references span `harness.py` (kwarg + state),
   `tracing.py`, `skeleton.py`, `characterise.py` and `test_characterise.py`
   (grep-verified); acceptance is a grep-driven sweep over code, tests and
   current docs — historical task-docs/ADRs exempt; stored-data vocabulary
   (`characterise_grouping_v1`, payload keys) unchanged.
3. **Runtime egress — one new generation surface:** `group_facet_v1` sends the
   distinct **source-named facet values** of the referenced run's findings
   (+ per-value counterpart reference names and counts) to the chat API — the
   repo's fourth product prompt. Source-derived text, but a strictly smaller
   class than 011's full text: reference strings only, no quotes, no
   statistics, no document text, **no scope intent** (grouping output is
   facet-relative, not question-relative — and keeping intent out preserves
   recomputability on the same finding set). Same provider route and injection
   posture. Full-I/O Langfuse traces (user-operated dev instance) carry these
   strings — the 009 trace posture, flagged for approval.

No new dependency rides this slice (`openai`, `langfuse`, `pydantic` land it
all).

**Explicitly not crossed:** exactly one prompt-bearing surface
(`group_facet_v1` — no agent loop, no tools, no free text acting on the
world); no new dependency; no auth/tenancy/CI change; no existing-table change;
no artefact/block writes; no new event types; no tag writes.

**Spec flow-backs:** none — but one **explicit recorded deviation** (rev 1.3):
components §8 declares `query-findings` among group's tools, and this slice
defers it to synthesise (decision 9) — that is a deviation from the letter of
the tool table, recorded as such in `docs/deferred.md` (not silently absorbed
into "implemented as written"; no spec change — the tool still lands, with its
deliberative consumer). Decision 9's realisation note follows the standing
skeleton-as-agent posture, not a spec change. Other deferrals ride
`docs/deferred.md` as entries.

## Public / private boundary

- On the live path, what leaves: distinct intervention/outcome/population
  reference strings extracted from the fixture corpus (openly licensed by
  construction) to the OpenAI API; full-I/O traces to the user-operated dev
  Langfuse. For arbitrary future corpora these strings are source-derived text
  and inherit the corpus's sensitivity class — private-by-default otherwise.
- Committed artifacts (schema, prompt text, roll-up shapes, verification
  counts) are public-safe. Group labels/descriptions are **model-generated text
  over source-derived input** — same class as 009's theme labels: public-safe
  for the fixture corpus, private-by-default otherwise. They are also
  **untrusted model output as data** (rev 1.3): bounded and validated at write
  (decision 3), rendered escaped, never executed — and a carried-forward
  requirement on synthesise (013): group labels/descriptions enter downstream
  prompts as data records, never as instructions.

## Model route

**Facet grouping**: a judgment-capable model behind the `FacetGroupingBackend`
seam — `gpt-5-mini`-class floor (the 009 nano lesson is binding); partition
quality on real reference sets is eval territory, not asserted by the build.
→ Bedrock at the seam swap, unchanged. **Prompt-bearing surface:
`group_facet_v1`** — the repo's fourth product prompt, lead-authored,
versioned, recorded in `grouping_provenance` and the event payload; the only
prompt in the slice. Prompt design carries **explicit negative rules**: no
catch-all/generic group labels ("General", "Miscellaneous", "Other" — the
ungroupable path exists instead and is stated in the prompt); no merging of
opposite-direction evidence into evaluative labels (groups name *what* was
studied, never *whether it worked* — the descriptive line); labels must be
grounded in the member values' own vocabulary (corpus-grounded, per
capability.md), never invented policy categories. Values enter as id-keyed
data records under the standing data/instructions separation; the response is
schema-constrained ids-per-group + label + description; an
explicitly-ungroupable list is a legal, expected answer.

## Disciplines binding this slice

- **Interpretive shape, not a count** — the grouping is grade-3 provenance:
  recomputable, base-labelled, never phrased as fact; its provenance carries
  the extraction base it inherits.
- **Flag, don't drop** — ungrouped values counted, never forced or dropped;
  no_value findings counted; mixed/unclear findings first-class members;
  nothing silently excluded from the grouped set.
- **Honest absence** — group sizes and spreads rest on the
  selected/extracted base and say so; nothing phrases the grouping as corpus
  coverage.
- **Model only what behaves** — no group entities, no tags, no finding
  columns, no consensus fields; the roll-up row is the only new state.
- **Deterministic where claimed** — finding-set resolution, membership
  derivation, direction counts, validation and writes are deterministic; only
  the partition call is interpretive, and its entire I/O is attributable
  (provenance, traces).
- **Never silent, never fake** — the stub's mode says it's a stub; missing
  upstream state fails structurally; a failed partition fails the component,
  never writes a partial grouping.

## Stop conditions

- Any gated change (schema · public interface · egress) not yet approved, or
  any change beyond them (existing-table change, new dependency, a second
  prompt surface, tag/artefact writes, new event types).
- Any *suite or library-default* code path would perform network I/O.
- The grouping wants evaluative/consensus output, canonical entities, or
  cross-schema linkage — that's synthesise/Options-Assessment/seam territory;
  halt.
- The backend wants capabilities beyond one schema-constrained partition
  (tools, multi-turn, free text acting on the world) — halt.
- The value set exceeds the cap and any pressure exists to "just batch it" —
  the cap is fail-closed by design; a scale algorithm is a plan-gate decision,
  never grown silently.
- `make verify` red with unclear root cause; or the turn/token budget is spent.

## Acceptance checks

- `make verify` (okf-validate · test · typecheck · lint · build) — green,
  deterministic, zero egress (socket-deny covers a group round-trip; suite runs
  on the stub only).
- **One manual live check** (evidence in verification.md): skeleton end-to-end
  with `OPENAI_API_KEY` (+ `LANGFUSE_*`) against the fixture corpus — real
  `group_facet_v1` call(s) over the extraction run's findings, roll-up row
  written with the invariants holding, grouping summary rendered, the call
  visible in the dev Langfuse trace (prompt version, tokens/cost) with
  run-level scores (partition-valid, ungrouped share — the 009 `score_summary`
  pattern); a second facet (`outcome`) run shown as a new run; per-run counts
  and an honest cost note recorded; keys absent from captured output.
- Deterministic vs AI eval: all suite checks are deterministic (stub backend).
  Grouping *quality* (are the groups coherent/useful?) is eval territory — the
  grouping-quality eval seam (009) extends to facet grouping; this slice's bar
  is machinery correctness, exhaustiveness invariants, honest residuals and
  provenance fidelity. Named explicitly so the review stack doesn't mistake
  machinery tests for a quality claim.

## Verification evidence expected

`verification.md` must include:
- `make verify` table with pass counts; socket-deny result named.
- Migration roundtrip clean; table count 24.
- Named test results: finding-set resolution (grouped set == the referenced
  run's findings via `docs[].extraction_record_id`, memo-reused included;
  failed/`no_findings` docs contribute zero; a foreign run's findings never
  enter; integrity cross-check mismatch → structural failure — rev 1.3),
  exhaustiveness invariants (every finding in exactly one of
  group/ungrouped/no_value; sum identities; direction-spread sums per group,
  per residual bucket and overall — rev 1.3), validation
  + repair (missing value ids → one repair; still-missing → counted
  `ungrouped`; unknown/duplicate ids → response rejected), label/description
  validation (empty, over-length, control-char, duplicate and
  forbidden-generic labels → response rejected, one repair — rev 1.3;
  negative rules additionally asserted on the built prompt), scale cap
  (distinct values > `FACET_VALUE_CAP` → `value_cap_exceeded` structural
  failure, no call — rev 1.3), null-facet
  handling (population facet with null populations → counted `no_value`),
  facet directive (default `intervention`; scope-context override; malformed/
  unknown-key/control-char directive fails closed; facet + source recorded),
  mixed/unclear first-class
  (fixture findings with `mixed`/`unclear` directions appear in groups and
  spreads, including residual spreads), edge scopes (zero-findings run →
  honest skip flag; missing
  extraction row → structural failure; same-run re-execution loud), backend
  failure → `component.failed`, no partial row; determinism (two stub runs →
  identical payload columns; sorted value ordering), injection posture
  (id-keyed value records under data/instructions separation asserted on the
  built prompt; an injection-shaped facet value lands as inert data, never
  instruction-following), provenance required keys (incl. the inherited base:
  fingerprint, profile, base-ladder counts, finding-set size + hash — rev
  1.3), delete-order integrity.
- Live-run evidence per the manual check above.
- Public-safety confirmation (egress was fixture-corpus reference strings
  only; traces on the user-operated instance; keys clean).
- Deferred seams recorded in `docs/deferred.md`: `query-findings` tool —
  recorded as an **explicit deviation from components §8's tool table**
  (rev 1.3; lands with synthesise's agent-loop) · facet-grouping quality evals
  (extends the 009 grouping-quality eval seam; also the cap's calibration) ·
  **large-corpus grouping algorithm** (rev 1.3 — beyond the fail-closed
  `FACET_VALUE_CAP`: tail-group-capable discovery, embedding-assisted value
  clustering; eval-gated) ·
  agent-authored grouping directive (same seam as select's) · cross-schema
  reference-mediated linkage (activates with `implementation_context_finding`)
  · grouping-run steering/re-grouping UX (mode-governed steer-points)
  · **facet-theme promotion** (rev 1.2 — canonical/queryable facet groupings
  for downstream capability agents; the data-model's staged ladder run-local →
  project-scoped persistent → graph datastore, gated on the
  entity-resolution-quality bar; Options Assessment reads run-referenced
  groupings until then).
- Diff summary (data files excluded from review diffs per the 007 retro).

## Risk tier & review focus

**Tier 3** — schema is a hard gate (one new table), a new runtime-egress
generation surface rides the slice, and group sits on the trust path:
synthesise will ground its sections in these memberships, so silent finding
loss or evaluative leakage here corrupts the deep terminus. Contract- and
plan-stage adversarial reviews standard; review stack sized per the
review-economy notes (medium `/code-review`, one security lane, class-split
budget, per-angle diff scoping). ADR at step 4 if the run-local/partition
design is judged consequential (likely: the first findings-layer *reader*).

Review focus:
- **Provenance/honesty (the headline lane)**: the grouped set exactly equals
  the referenced run's finding set; mixed/unclear survive; residuals counted,
  never dropped or forced; the grouping labelled interpretive with its
  extraction base attached; direction spreads are counts, never verdicts.
- **Security / prompt surface**: `group_facet_v1` injection posture — facet
  values are untrusted source-derived (and model-extracted) text; id-keyed
  data records, schema-constrained output, no tools; a hijacked partition can
  at worst mis-group — validation bounds it, and nothing it emits is executed
  or cited as fact. **Output posture** (rev 1.3): labels/descriptions are
  untrusted model output — deterministically validated at write, stored and
  rendered as data (escaped), with the data-not-instruction requirement
  carried forward onto synthesise's prompts. Key hygiene; egress bounded
  (reference strings only,
  pre-run call budget, socket-deny on suite paths).
- **Correctness**: finding-set resolution across fresh/reused records;
  membership derivation; invariant sums; repair-path semantics; FK and delete
  order; deterministic ordering.
- **Scope**: no synthesise reach-through, no canonicalisation, no tags, no
  consensus fields, suite egress-free.
