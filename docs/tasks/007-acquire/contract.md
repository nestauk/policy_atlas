# Task contract: 007-acquire

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md);
specs in [docs/specs/](../../specs/index.md).

> **Status:** approved — contract-stage adversarial review next, then planning.  
> Contract approved (before planning): 2026-07-05 · Shabeer Rauf (rev 7; shaped across
> review rounds: both backends + trust-class names + `evidence_scope` rename + sanitized
> fixtures for both + `abstract_source` provenance + retained-provider-fields tier +
> Arm-B R&D direction as seam context — all user-settled at this gate).  
> Contract approved (before planning): _date · who_ ·
> Plan approved (before implementation): _date · who_ · ADR: none expected
> (the fixture-backed-backends and rename decisions are contract-recorded; promote to an ADR
> only if the human wants them durable beyond this slice).

## Goal

Add the `acquire` component — the EB **front edge** — so the pipeline runs on **authentic
acquired documents**, not only uploads. Reprioritised by the user (2026-07-03): acquired
documents will be the majority of what Policy Atlas processes; downstream components built
against upload-only fixtures risk baking in wrong assumptions about what real acquired
documents look like.

Acquire gathers a **metadata-only** corpus via the `search` seam over the **two v3.0
configured backends the spec names — OpenAlex (academic) and Overton (policy / grey
literature)**. Processing both literatures is core to Policy Atlas (user, 2026-07-03; v2 used
both), and their metadata shapes differ in exactly the ways downstream components must not be
allowed to ignore: OpenAlex ships abstracts as an inverted index, carries DOIs and publication
years; Overton's policy documents are sparser — often no DOI, no abstract, a publishing
organisation instead of a journal. Per spec, **no full text is fetched here** (full-text
ingestion is gated by `screen` and is the next slice). Each accepted result is snapshotted
**on the text in hand**, joined to the project with `origin="acquired"`. Every `search` call
emits the canonical **`search.executed` governance event**; every acquire run writes a
**`search_coverage_record`** — the record that operationalises "adequately-searched" and which
`docs/deferred.md` explicitly defers "to the `acquire` slice where it becomes load-bearing".

**Zero runtime egress.** The `search` verb is realised as a `SearchBackend` seam whose v3.0
implementations replay **sanitized fixtures derived from dev-time-recorded real API
responses** (same pattern as `StubEchoProvider`/`_stub_screen`, but carrying authentic
document *structure* — field names, nullability, shape quirks recorded from the live APIs —
with fabricated values; user decision 2026-07-05: a public repo's test suite should hold no
real third-party records). The live HTTP backends are the recorded seam behind the same
protocol, gated on their own runtime-egress approval.

**Rename riding this slice:** `screening_scope` → **`evidence_scope`** (decision 10). The
name was coined at task 004 when screen was its only consumer; it now anchors the whole chain
(acquire → screen → classify → appraise → …), and "screening" misdescribes it. User invited
the rename (2026-07-03); pre-launch is the cheap moment.

## Deliverable

A PR on `task/007-acquire` → `dev` that:
- Renames `screening_scope` → `evidence_scope` (table, columns, constraint/index names,
  `Plan`/`Config` field, module code, event payload keys, tests) + its Alembic migration.
- Adds a `search_coverage_record` table + Alembic migration.
- Ships `acquire.py` with `SearchBackend` (protocol), `OpenAlexFixtureBackend`,
  `OvertonFixtureBackend`, `AcquireContext`, the per-backend envelope mappings (including
  OpenAlex abstract-inverted-index reconstruction), and `acquire_sources()`.
- Ships committed **sanitized** fixture data + `scripts/record_openalex_fixtures.py` and
  `scripts/record_overton_fixtures.py` (dev-time, stdlib-only record-and-sanitize scripts —
  not part of the runtime; raw recordings stay gitignored; the Overton recorder reads
  `OVERTON_API_KEY` from the environment).
- Registers `"acquire"` in `COMPONENT_REGISTRY`; wires an `_run_acquire` harness node.
- Updates `skeleton.py` to demonstrate acquire (both backends) → screen → classify → appraise
  over a mixed corpus (one upload + the acquired fixture sets).
- One-line spec clarification in EB components §1 (acquire-time snapshotting — see decision 3)
  + `log.md` entry.
- Records the deferred seams in `docs/deferred.md`.
- Passes `make verify` (test · typecheck · lint · build) — all green.

## Read first

- [EB components §1 — acquire](../../specs/capabilities/evidence-base/components.md) (metadata
  only; breadth intent-derived; ingestion is not a tool)
- [System execution-orchestration](../../specs/system/execution-orchestration.md) — `search` as
  the only agent-invocable egress verb **"over configured backends each carrying a declared
  trust class (v3.0: OpenAlex, Overton)"**; every call emits a governance event; "ingestion is
  not a tool" (indirect-injection surface)
- [System data-model](../../specs/system/data-model.md) — § Corpus & source snapshots
  (text-in-hand snapshots, `text_basis`, content-hash identity, origin)
- [System provenance-grounding](../../specs/system/provenance-grounding.md) +
  [EB provenance](../../specs/capabilities/evidence-base/provenance.md) —
  `search_coverage_record` shape (boundary · stop condition · adequacy verdict + origin ·
  queries by reference); fail-closed absence
- [docs/deferred.md](../../deferred.md) — `search_coverage_record` deferred to this slice;
  acquired-dedup follow-on; "acquired sources always screen" (confirmed direction)
- Search-strategy R&D (June 2026): presentation at
  `docs/research-and-development/Search methods [Policy Atlas R&D] - June 2026.pdf`; code
  on v2 branch `search-experiment-pr` (PR nestauk/discovery_policy_atlas#184),
  `backend/testing/r_and_d/search_experiments/` — chosen direction **Arm B, the agentic
  loop** (see the R&D adjudication in Scope)

**API grounding** (checked 2026-07-03, per `source-driven-development` — re-verify at plan
time against live docs):
- **OpenAlex** — Work object ([developers.openalex.org](https://developers.openalex.org/),
  formerly docs.openalex.org): `display_name`, `abstract_inverted_index` (nullable — no
  plain abstract exists), `publication_year` / `publication_date` (date nullable), `doi`
  (nullable), `type`, `language` (nullable), `authorships`, `primary_location` / `source`,
  `open_access`, `ids`, `referenced_works`, `topics`. Keyless access works; an API key
  (user holds one) is optional but metered access is more generous with it. Live-search
  form v2 used: `filter=title_and_abstract.search:<query>` (populates `relevance_score`);
  known quirk: commas inside quoted phrases break queries. Recorders mirror that call form.
- **Overton** — REST API ([help.overton.io](https://help.overton.io/article/using-the-overton-api/);
  full spec: app.overton.io/swagger.php): API-key auth (one key per user); response =
  `query` (pagination) + optional `facets` + `results`. Two-level identity:
  `policy_document_id` (document) / `pdf_document_id` (PDF). Document-level fields: title,
  translated title, `document_url`, series, authors, **snippet** (short description — the
  abstract analogue, often absent), `published_on`, policy source (publishing org).
  PDF-level: `pdf_url`, language, topics/entities/subject areas (COFOG), SDG
  classifications, outgoing scholarly/policy references (where DOIs appear). V2-confirmed
  response details: `snippet` + `llm_document_description` (the abstract-analogue pair),
  `keyed_other_identifiers.doi` (list), `source.title`/`source.type`/`source.country`,
  `authors`/`topics` as string **or** list, pagination via a server-provided
  `next_page_url`, semantic mode via `squery`/`min_similarity`. **No full text in the API**
  (licensing); **rate limit: max 1 call/second** (429 + key-block on abuse).

## Scope

### Design decisions embedded here (approve or flip at this gate)

1. **Slice split: 007 = acquire (metadata envelope); 008 = full-text ingestion.** The spec
   separates them (acquire is metadata-only by design; full-text fetch + Tier-0 ingestion is
   gated by `screen`), and full-text ingestion carries its own design fork (new snapshot vs.
   attach-to-existing under snapshot immutability) that deserves its own contract. This slice
   must not foreclose that fork.
2. **Both v3.0 backends, fixture-backed, authentic data — no runtime egress.**
   `SearchBackend` is the seam (protocol, like `InferenceProvider`); **OpenAlex and Overton**
   each get a fixture implementation replaying raw API responses recorded at dev time
   (stdlib `urllib` only — **no new dependency**; dev-time network use is explicitly not
   gated). Academic + grey literature together is core to Policy Atlas, and the spec names
   both as the v3.0 configured backends — a one-backend slice would bake single-shape
   assumptions into the code paths this slice exists to keep honest. Each backend declares
   its **trust class** (v3.0 values, user-named 2026-07-03: OpenAlex
   `"academic_aggregator"`, Overton `"grey_literature_aggregator"`). Fixture sets are chosen
   to carry each side's authentic quirks, **grounded in the official API docs** (see the API
   grounding note under Read first) — OpenAlex Work objects: `abstract_inverted_index`
   (nullable; reconstruction is real product code — OpenAlex ships no plain abstract),
   nullable `doi`/`language`/`publication_date`, non-article `type` values (report,
   preprint, book chapter), non-English records; Overton policy documents: a `snippet`
   rather than a real abstract (and often neither — include one record with only
   `llm_document_description` and one with neither), **no DOI of their own** in the common
   case (when present it hides in the `keyed_other_identifiers.doi` list), `published_on`
   (YYYY-MM-DD), a policy source (government / IGO / think tank) instead of a journal, the
   two-level `policy_document_id` / `pdf_document_id` identity (plus a multi-PDF grouped
   document), empty-string `snippet` alongside a populated `llm_document_description`
   (live-observed), translated titles, and `authors`/`topics` in both their string and
   list shapes (v2-confirmed quirk). The live HTTP backends are the recorded seam behind
   the same protocol, deferred to their own runtime-egress approval.
3. **Acquired results are snapshotted on the text in hand — with the summary's provenance
   made explicit.** Each accepted record becomes a `source_snapshot` whose single chunk is
   the title + the best available summary text, `content_hash` over that text,
   `segmentation_policy="metadata_envelope_v1"`; joined via `project_source_snapshot` with
   `origin="acquired"` and `run_id` set (both columns already exist). This reuses the
   existing snapshot machinery, keeps snapshots immutable, and gives screen/classify their
   metadata substrate.
   - `text_basis` stays the spec's **coarse axis** — `"abstract_only"` means "the metadata
     envelope in hand, **not full text**"; it names the grounding-basis *class*, not the
     chunk's composition (the chunk always includes the title; the spec's two values
     distinguish fetched-full-text from everything short of it).
   - The finer provenance the coarse axis can't carry goes in the envelope metadata as
     **`abstract_source`**: `"publisher_abstract"` (OpenAlex, reconstructed) · `"snippet"`
     (Overton excerpt) · `"llm_description"` (**Overton's `llm_document_description` is
     LLM-generated text, not the document's own words** — user flag, 2026-07-05: its use
     must always be visible) · `"none"` (title-only chunk). Queryable via JSONB; when
     grounding lands, claims resting on `llm_description` text are flagged distinctly
     (flag-not-drop discipline).
   Spec flow-back: components.md §1 "no full text" gets a one-line clarification (v3.0
   acquire snapshots the metadata envelope as text-in-hand; full-text fetch + Tier-0
   ingestion remain post-screen) + a `log.md` line — approved together with this contract.
4. **The metadata envelope is normalized per backend, raw stays in fixtures.** One shared
   envelope vocabulary — `title`, `abstract` (plain text), `year`, `doi`, `language`,
   `backend`, `backend_record_id`, `record_type`, `publisher_org` — populated by each
   backend's mapping with `None`/absent where the source has no such concept; absence is
   authentic data, not an error. Grounded mappings: OpenAlex — `display_name` → `title`,
   reconstructed `abstract_inverted_index` → `abstract`, `publication_year` → `year`,
   `doi`, `language`, `type` → `record_type` (OpenAlex's native `type`; v2 read
   `type_crossref` — flip only if the plan finds the Crossref taxonomy earns it),
   `primary_location.source.display_name` → `publisher_org`, OpenAlex `id` →
   `backend_record_id`. Overton — `title` (falling back to translated title), **`snippet`
   → `abstract`, falling back to `llm_document_description`** (v2 confirmed both fields;
   Overton ships no real abstract — recorded as such, not upgraded), `published_on`
   (YYYY-MM-DD) year → `year`, `doi` from `keyed_other_identifiers.doi[0]` when present
   (a list; v2-confirmed location — normally absent), policy `source.title` →
   `publisher_org`, `source.type` → `record_type`, `policy_document_id` →
   `backend_record_id`. Overton's `authors` and `topics` arrive as **either string or
   list** (v2-confirmed) — the mapping tolerates both. The normalized `abstract` key is
   exactly what `_stub_screen` already reads, so missing abstracts/snippets flow through
   the built fail-open path (`title_only`, confidence 0.7) with no screen changes.

   **Retained provider fields (user direction, 2026-07-05; grounded in live exploratory
   calls to both APIs, 2026-07-05).** Beyond the envelope keys, the snapshot's `metadata`
   JSONB retains a **curated per-backend field set** for future components — a snapshot is
   a point-in-time record of what the provider said, and upstream data drifts (citation
   counts grow, records get corrected or retracted), so re-fetching later cannot recover
   today's view. Retention is honest optionality at zero schema cost. The lists (final
   trim at plan time):
   - **OpenAlex retain:** the URL/OA block (`primary_location`, `best_oa_location`,
     `open_access` — landing/pdf URLs, licence, version; **required by slice 008**);
     `topics`/`primary_topic`/`keywords` (characterise thematic shape); `authorships`
     slimmed to names + institution names + countries (geography coverage);
     `cited_by_count`, `fwci` (selection signals); `is_retracted`, `is_paratext`
     (quality flags); `ids` (pmid/mag — cross-referencing); `language`;
     `sustainable_development_goals`.
   - **Overton retain:** `document_url`/`pdf_url` + `grouped_pdf_ids_in_result`
     (**slice 008**; multi-PDF documents are real); the full `source` block
     (country/state/type/subtype/sector/organisation_type/function/region — geography +
     publisher typing for characterise); `topics`, `classifications`, `sdgcategories`,
     `cofog_divisions` (classification stack); `cites` summary (scholarly/policy/news/
     people — snowball-seam signal); `citation_count` (+`_including_self`); `es_score`
     (provider relevance); `published_on` + `added_on`; `languages` (a list — envelope
     `language` takes the first); `authors_are_organizations`; `llm_document_theme`
     (**LLM-generated, like `llm_document_description` — retained but always identifiable
     as machine text, never mixed into document-own-words fields**).
   - **Excluded:** heavy refetchable arrays (OpenAlex `referenced_works`,
     `related_works`, `counts_by_year`, full `locations`, deprecated `concepts`);
     query-relative material that isn't a document fact (Overton `highlights` — it
     describes the match, not the document; the search event is its home if ever kept);
     display chrome (`thumbnail*`, `dont_show_pdf`); and fields nothing foreseeably reads
     (`apc_*`, `biblio`, `mesh`).
   The **full raw record** still stays in fixtures only — the DB retains the curated set.
   Live-confirmed mapping detail: **Overton expresses absence as empty strings/lists on
   always-present keys** (e.g. `snippet: ""` with a populated `llm_document_description`
   observed on page one) — the mapping treats empty-string/empty-list as absent.
5. **Acquire keys off the (renamed) `evidence_scope` as the intent carrier.** Breadth is
   intent-derived and the scope row already holds `intent` + `context`; a parallel
   "acquisition scope" table would duplicate it. `"acquire"` therefore requires
   `evidence_scope_id` like the other components. Acquired sources **always screen**
   (confirmed direction, deferred.md).
6. **Query derivation is deterministic in v3.0.** One `search` call per backend per acquire
   run, query = the scope's `intent` verbatim, no filters. LLM query expansion / breadth
   derivation / multi-query strategies are the deferred seam (they need a real inference
   provider) — and the chosen future shape of that seam is the **Arm-B agentic loop** (see
   the R&D adjudication below), which the one-call-per-backend rule is a v3.0 placeholder
   for, not a constraint on. Stop condition recorded as `breadth_truncated` (each backend
   returns a bounded page); `re_searched_still_thin` belongs to the thin-base re-search
   seam; `error` when any backend fails.
7. **Idempotency and cross-backend dedup are project-scoped.** A result is skipped as
   `already_acquired` when (a) its envelope content hash already has a `source_snapshot`
   linked to this project — exact-duplicate guard, covers reruns — or (b) it carries a DOI
   that another snapshot in this project already carries (DOI is the only cheap
   cross-backend identity). Grounded expectation: Overton policy documents rarely carry a
   DOI of their own (their DOIs are outgoing scholarly references), so the DOI guard mainly
   catches duplicate *scholarly* records (e.g. a report indexed by both providers, or
   future backends); the rule is kept because it is cheap and its absence would silently
   double-process exactly the overlap cases that do occur. Backend ordering is fixed
   (OpenAlex then Overton) so dedup outcomes are deterministic. **Cross-project snapshot
   reuse** (the shared content-addressed substrate) stays deferred as recorded; fuzzy
   near-dup matching (title similarity) is a recorded seam, not built.
8. **One `search_coverage_record` per acquire run**, spanning both backends (the `backends`
   array is the search-space boundary), adequacy decided by a deterministic v3.0 rule: any
   backend `error` or zero total results → `inadequate`; otherwise `adequate`;
   `verdict_origin = "model"`. **What `verdict_origin` means:** the spec requires the
   adequacy verdict to carry *who made the call* — `"model"` = the system's own judgment
   (v3.0: this deterministic rule standing in for it), `"human"` = a person confirmed or
   overrode adequacy at a steer-point (e.g. accepts a thin-but-adequate search, or marks a
   large result set inadequate for a known blind spot). The distinction matters because a
   non-`inadequate` coverage record is what licenses corpus-level absence claims
   downstream — "we searched enough" signed by a human carries different weight than the
   system's self-assessment. v3.0 writes only `"model"`; `"human"` becomes writable when
   check-in steer-points land. Queries travel **by reference**: the record links to the
   run whose `search.executed` events carry them — no query text duplicated into the
   record.
9. **Untrusted-text posture recorded now.** Acquired titles/abstracts/snippets are
   third-party text entering the corpus — grey literature especially so; v3.0's
   deterministic stubs never interpret them, but the LLM screen/classify seams will. The
   injection-screening consideration ("ingestion is not a tool") is recorded in
   `docs/deferred.md` against the live-backend/LLM seams — this slice's security review
   confirms no code path executes or interprets acquired text.
10. **Rename: `screening_scope` → `evidence_scope`** — **user-approved (2026-07-03)**
    (table, `screening_scope_id` → `evidence_scope_id` everywhere: result-table columns,
    constraint/index names, `Plan`/`Config` field, `*Context.scope_id` docstrings, event
    payload keys, registry `requires`, tests). Rationale: the object is "a research
    question / intent within the project" (004's own words) and now scopes the entire
    chain — `evidence_scope` says what it actually delimits (one evidence-gathering
    exercise) and matches the Evidence Base capability name. Implementation-invented name
    (task 004), so no spec flow-back. The rename is **clean and total** — code, schema,
    and event payload keys all use the new name with no compatibility shims; existing dev
    databases are disposable and pre-launch event history carries no obligation (user
    call, 2026-07-05). Lands as the slice's **first, mechanically separable commit** so
    all acquire code is born under the new name.

### V2 integration review — adjudicated lessons (2026-07-05)

Subagent review of the v2 repo (`../discovery_policy_atlas`, read-only) at the user's
direction: what to consider or improve, **not** port verbatim. Adjudication:

**Carried into this slice** (already reflected in decisions 4/7 above): Overton
`snippet` + `llm_document_description` as the abstract-analogue pair; Overton DOI location
(`keyed_other_identifiers.doi[0]`, a list); string-or-list tolerance for Overton
`authors`/`topics`; `published_on` year extraction with a digit guard; DOI as the only
reliable cross-provider identity (v2's `stable_doc_id` deduped DOI → provider id →
title+year hash, and cross-provider collisions in practice happened via DOI).

**Improvements over v2, by construction in this slice:**
- v2 had **no Overton rate limiting at all** (no limiter, no backoff, no
  `OVERTON_RATE_LIMIT` setting) and its `OPENALEX_RATE_LIMIT=10` setting was defined but
  never enforced; our recorder honours Overton's 1 req/s, and rate handling becomes an
  explicit requirement on the live-backend seam.
- v2's OpenAlex search path had **no request timeout** (unbounded hang risk through
  pyalex); our recorders set explicit timeouts, and the live seam inherits the requirement.
- v2's query-quirk sanitizer (OpenAlex breaks on **commas inside quoted phrases**) existed
  but was applied on a non-production method only; recorded on the live seam so the fix
  lands on the path that runs.
- v2 synchronously blocked its event loop on every Overton call (sync `requests` inside
  `async def`); moot in v3.0 (no live calls), noted for the live seam.

**Recorded at the seams (deferred.md), not built:**
- **LLM query derivation**: v2's central lesson — a single LLM-generated boolean query is
  unstable/low-recall (it built a dedicated query-stability eval to prove it), and its
  answer was multi-query fan-out (5 diverse generations) + systematic-review/RCT variant
  clauses + priority-aware dedup. That design and its eval harness are the starting point
  when the seam opens; v3.0's intent-verbatim query is stable by construction.
- **Per-backend query mode is a backend property, not one-size-fits-all** (user,
  2026-07-05): v2 production ran **semantic-only on Overton** (`squery` +
  `min_similarity` — cheap) and **boolean-only on OpenAlex** (OpenAlex offers semantic
  too, but at much higher cost — v2 bet on good query generation instead). To explore at
  the seam: a semantic/keyword mix per backend; and whether Overton's semantic mode is
  already hybrid under the hood (unverified). The richer Overton filters
  (`source_country`/`source_region` with v2's region-label mapping, `source_type`, date
  bounds) sit at the same seam; v3.0 sends none (`scope_filters` stays `{}`).
- **Per-provider result caps** — v2 deliberately trimmed OpenAlex to the limit while
  keeping all Overton rows so the verbose provider couldn't crowd out grey literature;
  becomes load-bearing when live backends return unbounded results.
- **Slice 008 (full-text) inputs**: v2's OA-location precedence for pdf URLs
  (`primary_location` → `best_oa_location` → `open_access.oa_url`), its fetch cascade
  (pdf_url → landing-page scrape with PDF-link discovery → DOI URL), parse caps
  (50 MB/50 pages/100K chars) and failure manifest — plus its fragilities to avoid
  (fetch errors swallowed at debug level; thin DOI-landing text still reported `ok`).

**Deliberately not carried:** LLM boolean-query generation at acquire time (deterministic
intent-verbatim in v3.0); pandas/DataFrame merge pipeline (our persistence is the DB);
v2's 1000-char abstract truncation (we snapshot the full text in hand); hardcoded
`source_type="Academic Paper"` provenance (ours is the declared trust class per backend).

### Search-strategy R&D (June 2026, PR #184) — direction adjudicated (2026-07-05)

Colleague R&D (v2 branch `search-experiment-pr`; presentation:
`docs/research-and-development/Search methods [Policy Atlas R&D] - June 2026.pdf`;
handover: `backend/testing/r_and_d/search_experiments/ONBOARDING.md`, maintainer Aidan
Kelly) compared three retrieval arms; **the chosen direction is Arm B — the agentic loop**
(user, 2026-07-05): iterative search with query reformulation from judged exemplars,
citation snowballing (forward + backward), LLM-suggested-paper grounding, Thompson-sampling
adaptive judging with a short-circuit stop, and blend ranking (0.9·LLM-judge +
0.075·rerank). Measured: ~2× the single-pass baseline's recall@k_est (means ≈ 0.20 vs
0.06), ~$0.44/query, ~6 min latency. It is LLM- and egress-heavy, so it lands behind the
already-deferred seams — **not in this slice**. What this slice must not foreclose,
verified against the arm-B implementation:

- **`SearchBackend` grows into the R&D's `SourceClient` shape.** The loop needs more verbs
  than `search(query)`: fetch-citations / fetch-references (snowball), title-grounding
  lookup (hallucination filter for LLM suggestions), optionally dense search — plus
  per-backend capability flags. v3.0 ships `search()` only; adding methods to the protocol
  later breaks nothing shipped here.
- **N search calls per run.** Reformulated queries and snowball fetches mean many calls
  per acquire run — our per-call `search.executed` events + one per-run coverage record
  (queries by reference) already fit that shape unchanged.
- **`stop_condition` vocabulary grows.** The loop stops on quota / exhausted /
  short-circuit — cousins of the deferred `saturated`. Extending the CHECK constraint is
  a one-line migration; the three v3.0 values stay honest for the deterministic pass.
- **Semantic Scholar is a candidate third backend** (Arm C was a close second; dense
  `/snippet/search`, `x-api-key`, ~1 req/s) — the multi-backend protocol + trust-class
  design already accommodates it.
- **Snowball-discovered records enter as acquired sources** like search hits — the
  envelope and project-scoped dedup (content hash + DOI; the R&D's candidate-merge
  semantics are the richer future version) apply unchanged.

Recorded at the seams (deferred.md, step 8): the arm-B mechanics summary with pointers to
the PR/presentation/handover; an Overton arm-B as named future work (presentation calls it
a novel open-source contribution); the Campbell/3ie/EPPI golden-dataset recommendation
(eval workstream, per data-model's judge-calibration ownership); blend-rank + LLM-judge
relevance belong to the screen / retrieval-rerank seams, not acquire.

### Schema

**Gated change 1 — rename migration:** `screening_scope` → `evidence_scope`;
`screening_scope_id` → `evidence_scope_id` on `source_screening_result`,
`source_classification_result`, `source_appraisal_result`; constraint/index renames to match
(`uq_screening_scope_id_project` → `uq_evidence_scope_id_project`, FK names keep their
`_scope_project` suffixes). Pure rename — no shape change, no data change; downgrade renames
back.

**Gated change 2 — new table: `search_coverage_record`**

```
search_coverage_record_id   UUID         PK
evidence_scope_id           UUID         NOT NULL
project_id                  UUID         NOT NULL   -- denormalized; cross-project guard
acquired_by_run_id          UUID         NOT NULL
backends                    JSONB        NOT NULL   -- [{"backend": "openalex", "trust_class": "academic_aggregator", "mode": "fixture"},
                                                    --  {"backend": "overton",  "trust_class": "grey_literature_aggregator", "mode": "fixture"}]
scope_filters               JSONB        NOT NULL   -- v3.0: {} (no filters); shape reserved
stop_condition              TEXT         NOT NULL   -- breadth_truncated | re_searched_still_thin | error
adequacy_verdict            TEXT         NOT NULL   -- adequate | inadequate
verdict_origin              TEXT         NOT NULL   -- model | human
created_at                  TIMESTAMPTZ  NOT NULL
```

Constraints (same pattern as the result tables):

```
ForeignKeyConstraint(["evidence_scope_id", "project_id"],
    ["evidence_scope.evidence_scope_id", "evidence_scope.project_id"],
    name="fk_scov_scope_project")
ForeignKeyConstraint(["acquired_by_run_id", "project_id"],
    ["runs.run_id", "runs.project_id"],
    name="fk_scov_run_project")
UniqueConstraint("acquired_by_run_id", name="uq_scov_run")   # one record per acquire run
CheckConstraint(stop_condition IN ('breadth_truncated', 're_searched_still_thin', 'error'))
CheckConstraint(adequacy_verdict IN ('adequate', 'inadequate'))
CheckConstraint(verdict_origin IN ('model', 'human'))
CheckConstraint(jsonb_typeof(backends) = 'array')
```

`saturated` is deliberately **not** a valid `stop_condition` (spec: saturation-based stopping
is a ⏸ seam). Table count goes 15 → 16.

### Python

**`acquire.py`** — new module (public surface carries Google-style docstrings):

```python
@dataclass
class AcquireContext:
    scope_id: uuid.UUID
    intent: str
    context: dict[str, Any]

class SearchBackend(Protocol):
    name: str
    trust_class: str
    def search(self, query: str) -> list[dict[str, Any]]:
        """Return raw provider records for the query."""

class OpenAlexFixtureBackend:
    """Replays committed, dev-time-recorded OpenAlex responses. Zero egress."""

class OvertonFixtureBackend:
    """Replays committed, dev-time-recorded Overton responses. Zero egress."""
```

Plus the mapping layer (private helpers): OpenAlex abstract reconstruction from
`abstract_inverted_index` (position-ordered token join), and per-backend raw record →
normalized envelope (decision 4) + the text-in-hand chunk string. Records with no title are
counted and skipped (`skipped_unusable`) — a snapshot needs at least a title to be
screenable; skip is visible, never silent.

`acquire_sources(conn, *, project_id, run_id, context: AcquireContext,
backends: list[SearchBackend]) -> dict`:
1. Per backend, in list order: `backend.search(context.intent)` — one call each — and emit
   one **`search.executed`** event: `{backend, trust_class, mode, query, filters,
   result_count, evidence_scope_id}`.
2. Per usable result: build envelope + chunk text; if its content hash — or its DOI, when
   present — already has a snapshot linked to this project → count `already_acquired`; else
   create `source_snapshot` (+ its one chunk) and `project_source_snapshot`
   (`origin="acquired"`, `run_id=run_id`) and emit one **`source.acquired`** event:
   `{source_snapshot_id, project_source_snapshot_id, evidence_scope_id, backend,
   backend_record_id}`.
3. Write the run's `search_coverage_record` (decision 8).
4. Return:

```
{"acquired": n,
 "already_acquired": m,
 "skipped_unusable": s,
 "results_returned": r,          # total across backends; invariant: n + m + s == r
 "by_backend": {"openalex": {"results_returned": …, "acquired": …,
                             "already_acquired": …, "skipped_unusable": …},
                "overton":  {…}},
 "stop_condition": "breadth_truncated",
 "adequacy_verdict": "adequate",
 "coverage_record_id": "<uuid>"}
```

Counting semantics (rerun-stable): the invariant holds per backend and in total; a second run
over the same fixtures returns `acquired == 0`, `already_acquired == n + m`, a **new**
coverage record (records are per-run audit state, not deduped).

**Fixture data** — committed **sanitized** JSON as package data (e.g.
`src/policy_atlas/data/openalex_works.json`, `overton_documents.json`; exact paths are a plan
detail), loaded via `importlib.resources`. ~10–20 records per backend spanning the quirks in
decision 2. Pipeline: each dev-time recorder script fetches real responses **in the mode
production would use** — Overton via semantic (`squery`, v2's production mode for it;
honouring the **1 call/second** rate limit), OpenAlex via the keyword
`title_and_abstract.search` filter form — into a **gitignored** raw path, then a
sanitizer derives the committed fixture — **real field names, structure, nesting,
nullability patterns and shape quirks; fabricated values** (fabricated tokens in a
structurally real `abstract_inverted_index`, fabricated titles/orgs/DOIs with realistic
formats). Each committed file's header documents the recorder query, record date and quirk
coverage. Keys via environment only: `OVERTON_API_KEY` (required by its recorder),
`OPENALEX_API_KEY` (optional — OpenAlex works keyless). CI and tests never touch the network.

**Fixture policy (user decision, 2026-07-05): sanitized for both backends.** The repo is
public; a test suite should ship no real third-party records regardless of licence.
(OpenAlex's CC0 licence would permit raw commits; repo policy is stricter than the licence.
For Overton — a subscription service — sanitization is also what keeps the commit clearly
within the Terms of Use.) Raw recordings never leave the gitignored path. API keys are
never committed and never read by package code.

**`plan.py`** — add `"acquire": {"requires": ["evidence_scope_id"]}` to
`COMPONENT_REGISTRY`; field rename per decision 10. No new `Plan`/`Config` fields.

**`harness.py`** — add `_run_acquire` node (mirror `_run_classify`): load scope, build
`AcquireContext`, emit `component.started`, call `acquire_sources` with
`[OpenAlexFixtureBackend(), OvertonFixtureBackend()]` (the backend list is an injection
point exactly like `provider`; plan decides whether it rides `run_harness`'s signature or a
default), emit `component.completed` with the return counts. Wire into conditional edges.

**`skeleton.py`** — create scope → **acquire** (both backends) → screen → classify → appraise
over the mixed corpus (existing synthetic upload + acquired fixtures); log the acquired
counts per backend and the screen-basis distribution so the authentic-shapes path (missing
abstracts → `title_only`) is visible in the smoke run. Acquired records classify as
`Unknown / Insufficient information` under the classify stub (no sentinels in real metadata)
and are `skipped_unknown` at appraise — that is the honest v3.0 behaviour, not a defect.

**`tests/helpers.py`** — extend `delete_project_data`: add `search_coverage_record` in
FK-safe order; rename sweep.

**Spec flow-back** — components.md §1: one line clarifying acquire-time snapshotting
(decision 3) + `log.md` entry. (The rename needs none — implementation-invented name.)

**`test_acquire.py`** — new file, covering:
- Table count is 16.
- OpenAlex abstract reconstruction: correct ordering from a structurally real inverted
  index (multi-position tokens, punctuation — sanitized fixture preserves the structure);
  empty/missing index → no abstract.
- Envelope mapping per backend: normalized keys present; Overton records map
  `publisher_org`/`record_type`, take `abstract` from `snippet` falling back to
  `llm_document_description`, read `doi` from the `keyed_other_identifiers.doi` list,
  tolerate string-or-list `authors`/`topics`, and tolerate absence of all of these;
  no-title record → `skipped_unusable`.
- `abstract_source` provenance: `publisher_abstract` (OpenAlex with inverted index),
  `snippet` vs `llm_description` (Overton, in fallback order), `none` (title-only) — each
  case asserted on the persisted metadata; retained provider fields present per the
  plan-finalized list (URL/OA block at minimum).
- Round-trip: fixtures from both backends → snapshots with `origin="acquired"`, `run_id`
  set, `text_basis="abstract_only"`, exactly one chunk each,
  `segmentation_policy="metadata_envelope_v1"`, content hash matches the chunk text.
- Idempotency: second call → `acquired == 0`, `already_acquired` = prior `acquired +
  already_acquired`, no duplicate snapshots; invariant holds per backend and in total, on
  both calls.
- Cross-backend DOI dedup: two fixture records sharing a DOI (one per backend) → one
  snapshot, one `already_acquired`; deterministic winner (backend list order).
- `search.executed` events: one per backend per call, payload keys/values as specified.
- `source.acquired` events: one per newly acquired snapshot; none for skipped/deduped.
- Coverage record: one row per run; `backends` array carries both backend entries with trust
  classes; verdict rule (`adequate` on results; `inadequate` on an empty/erroring backend —
  use a throwaway in-test backend for the error path); `verdict_origin == "model"`; check
  constraints reject invalid values (`IntegrityError`); cross-project FK rejected;
  `uq_scov_run` rejects a second record for the same run.
- Downstream flow: acquired sources screen (missing-abstract fixtures → `title_only` basis,
  confidence 0.7; abstract-bearing → `title_abstract`), classify to `Unknown`, and are
  `skipped_unknown` at appraise — full-chain test over both fixture corpora.
- Harness round-trip: `Plan(component="acquire")` → snapshots + coverage record in DB,
  events emitted, `component.completed` payload carries the counts incl. `by_backend`.
- `delete_project_data` removes coverage records (and acquired project links); acquired
  `source_snapshot` rows themselves are content-addressed and project-less — deletion
  semantics follow task-003 precedent for uploads.
- Zero-egress guard: `acquire.py` and its imports contain no HTTP client usage; the recorder
  scripts are not imported by the package (a lightweight import-graph or grep-style test,
  per plan).
- Rename: existing screen/classify/appraise/compile tests pass under `evidence_scope` /
  `evidence_scope_id` (sweep, not new tests); migration roundtrips the rename cleanly.

Updates to existing tests:
- `tests/test_screen.py` / `test_classify.py` — table-count assertions 15 → 16; rename sweep.
- `test_compile.py` — `"acquire"` valid with a scope id; rejected without
  `evidence_scope_id`; unknown component still rejected; rename sweep.

### Out of scope

- **Live HTTP backends** (OpenAlex, Overton) — the `SearchBackend` seam and both mappings are
  built; wiring live calls is runtime egress, its own gated slice.
- **Full-text fetch + Tier-0 ingestion** (parse/segment/embed of fetched documents) — slice
  008; its snapshot-identity fork must not be foreclosed here.
- LLM query expansion / intent-derived breadth strategies / multi-query plans — ⏸ (needs a
  real inference provider).
- Thin-base re-search trigger (`re_searched_still_thin` is representable, nothing fires it) —
  already-recorded seam.
- Saturation-based stopping (`saturated` stop value) — ⏸ per spec.
- Cross-project content-hash dedup / shared acquired substrate + reference-counted GC — ⏸
  (project-scoped dedup only in this slice). Fuzzy near-dup matching (title similarity)
  likewise — DOI-only cross-backend identity in v3.0.
- Injection screening of acquired text — recorded posture only (decision 9); enforcement
  lands with the LLM seams / live backends.
- `characterise` and everything downstream of appraise — subsequent slices.
- Vectorisation/embeddings, retrieval changes — untouched.

## Constraints & approval gates

**Two gated changes:**

1. **Schema (rename)** — `screening_scope` → `evidence_scope` + column/constraint renames
   across the result tables; one Alembic migration. Also touches the public interface
   (`Plan`/`Config` field name, event payload keys going forward) — approved together.
2. **Schema (new table)** — `search_coverage_record` with composite FKs and check
   constraints; one Alembic migration.

Plus one spec clarification (components.md §1 acquire-time snapshotting line) — approved with
this contract per the spec-refinement flow.

**Explicitly not crossed:** no runtime egress (fixture replay only; recorder scripts are
dev-time and never imported by the package), no new dependencies (stdlib `urllib` +
`importlib.resources`), no auth, no CI change, no Plan/Config interface change beyond the
registry entry + the approved rename.

## Public / private boundary

- **Committed fixtures are sanitized for both backends** (user decision, 2026-07-05): real
  structure, fabricated values — no real third-party record ships in the public repo. Raw
  recordings stay in a gitignored path on the recording machine only.
- API keys (`OVERTON_API_KEY`, optional `OPENALEX_API_KEY`) stay in the environment — never
  committed, never read by package code.
- Table/column names, protocol/dataclass/function names, event payload keys, envelope keys —
  durable/committable.
- No full-text content, credentials, or runtime egress in any committed file.

## Model route

`n/a` — deterministic mapping + fixture replay. No LLM call, no inference provider, no runtime
network I/O. (The `search` seam is where the live backends plug in; the LLM query-derivation
seam sits above it — both deferred.)

## Disciplines binding this slice

- **Every search call emits a governance event** — `search.executed` per backend, even
  against fixtures, so the live backends inherit the discipline unchanged.
- **Coverage record per run, fail-closed** — absence claims downstream can only reference a
  non-`inadequate` record; the deterministic verdict rule is conservative (`inadequate` on
  empty/error); the `backends` array is the honest search-space boundary.
- **Skip is visible, never silent** — `skipped_unusable`, `already_acquired` counted and
  reported per backend and in total; the counting invariant is test-enforced.
- **Snapshots immutable; text-in-hand honestly labelled** — `text_basis="abstract_only"`
  means "metadata envelope, not full text"; no snapshot mutation when full text arrives
  later (008 decides its own shape).
- **Acquired sources always screen** — origin never bypasses the relevance filter, for
  either backend.
- **Origin/backend drives nothing downstream by stealth** — trust class lives on the backend
  + coverage record, not as a snapshot column; appraisal stays document-type-based (an
  Overton-acquired SR appraises the same as an uploaded one, per data-model spec).
- **Model only what behaves** — normalized envelope keys only; raw records stay in fixtures;
  no `search_coverage_record` fields v3.0 doesn't write.
- **Deterministic** — same fixtures + same intent → same snapshots, hashes, counts, events;
  fixed backend order makes dedup outcomes reproducible.

## Stop conditions

- A schema approval gate hit and not yet approved, or any schema change beyond the two gated
  items.
- Any code path would perform runtime network I/O (including "just fetch one missing
  abstract").
- Any new dependency would be needed.
- Scope would grow past the contract (full-text fetch, live backends, query expansion,
  cross-project dedup, characterise).
- `make verify` red with unclear root cause.

## Acceptance checks

- `make verify` (test · typecheck · lint · build) — green.
- All checks deterministic (fixture replay; no LLM, no egress). Every check is a test.
- One manual dev-time check per backend, documented in verification.md: each recorder script
  was run once and its sanitizer produced the committed fixtures (date + query recorded in
  the file header; raw recordings confirmed gitignored).

## Verification evidence expected

`verification.md` must include:
- `make verify` table with pass counts.
- Named test results from `test_acquire.py`, including the full-chain
  (acquire → screen → classify → appraise) test over both backends' authentic fixtures and
  the cross-backend DOI dedup test.
- Migration roundtrips (`alembic downgrade` / `upgrade`) for **both** migrations — rename and
  new table — clean.
- Table count: `assert len(metadata.tables) == 16`.
- Check-constraint and cross-project FK coverage for `search_coverage_record`.
- End-to-end command: harness invoked with `component="acquire"`, snapshots + coverage record
  visible in DB, two `search.executed` events in the log.
- Fixture provenance per backend: recorder query, record date, record count, which authentic
  structural quirks the set covers, confirmation both committed files are sanitized and raw
  recordings are gitignored.
- Diff summary (rename sweep separable from acquire feature).
- Public-safety confirmation (sanitized fixtures only; no real records; no credentials).
- Deferred seams recorded in `docs/deferred.md` (live backends behind `SearchBackend` —
  carrying the v2-lesson requirements: explicit timeouts, Overton rate limiter, query
  sanitization on the production path, per-provider caps; **the Arm-B agentic search loop**
  as the chosen direction for query derivation / iterative search — carrying the R&D
  pointers (PR #184, presentation PDF, ONBOARDING.md), the protocol growth path
  (citation-fetch / grounding-lookup / dense verbs + capability flags), the stop-condition
  vocabulary growth, Semantic Scholar as candidate backend, the Overton arm-B future-work
  note, and the Campbell/3ie/EPPI golden-dataset recommendation for the eval workstream;
  Overton semantic mode + filters; thin-base re-search; cross-project dedup + fuzzy
  near-dup; injection screening posture; full-text ingestion = slice 008 — carrying v2's
  OA-precedence, fetch cascade, parse caps and failure-manifest patterns).

## Risk tier & review focus

**Tier 3** — two schema changes (rename + new table), a public-interface rename, plus the
slice builds the seam through which runtime egress and untrusted third-party text will
eventually enter the product.

Review focus:
- **Correctness:** abstract reconstruction; per-backend envelope mapping; content-hash + DOI
  dedup scoped to the project; counting invariants; coverage-record verdict rule; rename
  sweep completeness (no stale `screening_scope` reference in code, tests, or migrations'
  upgrade path).
- **Provenance/governance:** `search.executed` per backend per call; one coverage record per
  run spanning both backends; queries by reference; fail-closed adequacy.
- **Security:** no runtime egress anywhere (fixture replay only); recorder scripts isolated
  from the package import graph; API keys never committed/read at runtime; acquired
  text never executed/interpreted; committed fixtures sanitized (no real third-party
  records) with raw recordings gitignored.
- **Cross-project integrity:** composite FKs on the new table; project-scoped dedup can't
  link another project's snapshots.
- **Migrations:** rename + new table both roundtrip clean.
- **Scope:** no live HTTP, no full-text fetch, no new deps, no query expansion, no
  cross-project dedup.
