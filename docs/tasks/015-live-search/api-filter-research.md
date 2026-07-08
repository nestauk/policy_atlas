# API filter research — OpenAlex + Overton (2026-07-09)

Two parallel deep-reasoner web-research recons of the official API
documentation, commissioned at the contract gate (user direction: decide
what `scope_filters` should admit "to allow the Policy Atlas tools'
agents maximum functionality to define the search strategy for the
user's intent"). Full agent reports below, lightly trimmed; the lead
adjudication into the directive grammar is contract rev 3.1
(decision 18).

**Adjudication summary:**

| Finding | Call |
|---|---|
| OpenAlex filter syntax: AND via comma, OR via `\|` (≤100 values), negation `!`, `<`/`>` inequalities, `from_/to_` date pairs; no documented complexity throttle (the R&D's ">5 operators" observation is undocumented folklore) | Grammar admits per-key value lists mapping to `\|` joins; retry hygiene kept regardless |
| Wildcards `*`/`?`/`~` are **stripped** by OpenAlex, not 400-ed (docs-verified current behavior) | Decision 5 rationale corrected: sanitizer still strips proactively — the failure mode is *silent term loss*, worse than an error |
| OpenAlex `type` enum: 28 live-verified values; `oa_status`: 6 values; source `type`: 7 values; SDGs: 17 fixed IRIs | Admitted as validated closed enums (self-describing directive keys) |
| `is_retracted:false` / `is_paratext:false` — near-zero recall cost integrity guards | Admitted, agent-authored opt-in (never baked defaults — fail-open base posture stands) |
| OA family (`is_oa`, `oa_status`, `any_repository_has_fulltext`) predicts 016 fetch success but biases the evidence base toward OA venues if defaulted | Admitted opt-in with bias warning in directive help; never a default; acquire-broadly remains the recommended posture |
| **OpenAlex geography = author affiliation, never study geography** — the highest-risk semantic trap | Admitted under a **self-describing key** `author_affiliation_countries` — the directive vocabulary is ours, so the name itself defuses the trap; same treatment for Overton (`publisher_countries` — the *publishing org's* country) |
| Topic hierarchy (`domain/field/subfield/topic` ids), keywords, funders, venue ids/ISSNs | Seam — needs an id/name-resolution step |
| `type_crossref` dead (live count 0); Concepts deprecated; `has_ngrams`/`mag_only` legacy; premium date filters | Excluded |
| `cited_by_count` floor + `fwci`/percentiles; `has_abstract`/`has_doi` as defaults | Excluded per decision 12 (the silent-recall class); knob stays the eval-gated seam |
| OpenAlex `sample` param (≤10k, seeded paging) | Recorded at the eval seam — the right primitive for eval-set construction |
| OpenAlex boolean search mode: UPPERCASE AND/OR/NOT, quotes, parens, stemming (`.no_stem` variants exist) | Feeds `search_queries_v1` prompt authoring (plan detail) |
| **Overton's public swagger documents almost no filter params** — only `query`, `format`, `api_key`, `page`, `next_page_url`, `plain_dois_cited`, `sort`, `show_search_facets`. All other names ([UI]/[V2] tiers incl. `squery`, `min_similarity`, `pp`, `source_*`, `published_*`, `sdgcategories`) are inferred | **Operator param-pinning session added to the contract** (authenticated "Generate API call" exports + a `show_search_facets=true` facet dump to pin names + enums) — a dev-time, key-bearing step; Overton filters are admitted *contingent* on pinning |
| `min_similarity` range/default/mode-applicability wholly undocumented; V2's 0.3 is an unvalidated convention | Stays a fixed backend constant, never agent-tunable; calibration at the eval seam (decision 2 unchanged) |
| Overton pagination: documented driver is the response `next_page_url` (page size fixed ~20; account-dependent page cap; V2's `pp` param unverified) | Decision 18 pagination follows `next_page_url` **with host validation against the pinned literal + key redaction** (it is a provider-supplied URL carrying the key — the one sanctioned, guarded exception to "never fetch provider URLs") |
| `facets` block empty by default since 2025-07-14 (`show_search_facets=true` to populate) | Nothing to do — v3 never reads the roll-up facets; noted for the pinning session |
| **Overton snowball surface is documented and strong**: `plain_dois_cited` (+ bulk `generate_id_set.php`) = policy docs citing given scholarly DOIs; `open_cited_institution_authors`; UI cites-family filters. Reverse policy→policy inbound is NOT evidenced | Overton-arm-B seam entry upgraded from speculative to documented-edge (cross-backend DOI seeding OpenAlex→Overton is the concrete hook); reverse-inbound marked confirm-with-support |
| Overton advanced `query` syntax: AND/OR/NOT, parens, quotes, `~N` proximity, field prefixes (`title:`, `abstract:`, `full-text:`, `domain:`); diacritics significant | Recorded for the reformulation prompt when Overton keyword mode is ever used; v1 Overton stays semantic-only |
| Overton `sort`, `document_type`, `subject_area`, `tags`: open/unpublished vocabularies that silently zero-match on wrong tokens | Excluded from the directive (fail-closed philosophy); sort fixed to relevance |

---

## Addendum — design-stage OpenAlex select/shape probe (2026-07-09, lead; 9 calls)

Run with the user-supplied `OPENALEX_API_KEY` (env-only, redacted from
all output) to pin retention-candidate shapes and `select=` behavior
for the rev-3.5 persistence adjudication:

- **`grants` is NOT a valid `select` field** (400 with an explicit
  valid-field list) — retaining it would force full-work fetches,
  forfeiting the decision-6 credit-efficiency design. Excluded.
- **Selectable and shape-pinned**: `indexed_in` (array of index names —
  `["crossref"]`, `["crossref","doaj"]` observed) · `publication_date`
  (full ISO date) · `keywords` (objects with `display_name`) ·
  `primary_location` / `open_access` (nested blocks return whole —
  `select` is root-level, so the retained nested fields
  `source.is_core`, `source.is_in_doaj`, `oa_status`,
  `any_repository_has_fulltext` all arrive within their blocks ✓).
- **OpenAlex `keywords` are noisy** — wrong-sense disambiguation
  artifacts observed directly: "Government (linguistics)",
  "State (computer science)", "Stock (firearms)", "Argument (complex
  analysis)" — legacy concept-linking noise. Verdict: keep the existing
  `provider_fields` retention (honest point-in-time record), **never
  promote to the tag layer** (they would pollute `source_tag` with
  absurd labels beside the clean topic/SDG tags).

## Report 1 — OpenAlex Works filter catalog (deep-reasoner, live-verified 2026-07-09)

Verification basis: canonical docs source `github.com/ourresearch/openalex-docs` (docs.openalex.org → developers.openalex.org); closed vocabularies re-verified against the live API (`group_by`) on 2026-07-09.

### 1. Filter syntax rules

- Filter param shape: `filter=attribute:value,attribute2:value2`. Case-insensitive.
- AND across attributes: comma. AND within one attribute: repeat key or `+` join (`+` does NOT work with search/boolean/numeric filters).
- OR within one attribute: pipe `|` — documented cap **100 values per filter**. OR cannot cross attributes.
- Negation: `!` prefix on the value (composable with OR sets).
- Inequalities: `<` / `>` (strict; no `>=`) on numeric fields; dates use `from_*`/`to_*` pairs; `publication_year` accepts `<`/`>`.
- Booleans: `:true`/`:false`. Composes freely with `search`, `select`, `sort`, `per-page` (1–200, live-verified), `page`/`cursor` (cursor for >10k).
- **No documented cap on boolean-operator count and no complexity throttle** — the R&D's ">5 operators" observation is undocumented; treat as folklore unless reproduced.

### 2. Filter catalog (condensed to adjudication-relevant families)

**Dates:** `from_publication_date`/`to_publication_date` (inclusive, `yyyy-mm-dd`); `publication_year` (int, inequalities); `from/to_created_date`, `from/to_updated_date` are **Premium-gated**.

**Type:** `type` — closed enum, 28 live-verified values (desc. by count): `article`, `book-chapter`, `dataset`, `other`, `dissertation`, `preprint`, `book`, `review`, `paratext`, `libguides`, `letter`, `report`, `peer-review`, `reference-entry`, `editorial`, `conference-paper`, `standard`, `erratum`, `software`, `conference-abstract`, `supplementary-materials`, `retraction`, `book-review`, `database`, `book-section`, `data-paper`, `report-component`, `grant`. Note `article` conflates journal/proceedings/posted-content. **`type_crossref` is dead** (live count 0; migrated to non-filterable `raw_type`).

**Language:** `language` — ISO 639-1; auto-detected (`langdetect`) from abstract/title; may be unassigned; bilingual unreliable.

**Open access:** `open_access.is_oa` (alias `is_oa`); `open_access.oa_status` (alias `oa_status`) — 6 live-verified values: `diamond`, `gold`, `green`, `hybrid`, `bronze`, `closed`; `open_access.any_repository_has_fulltext` (best "fetchable repo copy" signal); `best_oa_location.version` (`publishedVersion`/`acceptedVersion`/`submittedVersion`); `best_open_version` (`any`/`acceptedOrPublished`/`published`); `has_oa_accepted_or_published_version`; `has_oa_submitted_version`; per-location `license`/`is_oa`/`is_accepted`/`is_published`.

**Authorship/institution/country (AUTHOR AFFILIATION, not study geography):** `authorships.countries`; `authorships.institutions.country_code` (alias `institutions.country_code`); `.continent`; `.is_global_south` (live-verified ~40.9M works); `.id`/`.ror`/`.lineage`/`.type` (institution type enum: `education`, `healthcare`, `company`, `archive`, `nonprofit`, `government`, `facility`, `other`); `author.id`/`.orcid`; `is_corresponding`; `countries_distinct_count`, `authors_count` (inequalities).

**Topics/SDGs:** `primary_topic.id` / `topics.id` (Topic IDs `Txxxx` — **ids only, no name search**); hierarchy `primary_topic.{domain,field,subfield}.id` (4 domains ⊃ 26 fields ⊃ ~250 subfields ⊃ ~4500 topics); `keywords.keyword`; `sustainable_development_goals.id` — UN IRIs `https://metadata.un.org/sdg/{1..17}`, mBERT-tagged (score>0.4), probabilistic. Concepts (`concepts.id`) **deprecated** in favor of Topics.

**Source/venue:** `primary_location.source.type` — docs-verified enum: `journal`, `repository`, `conference`, `ebook platform`, `book series`, `metadata`, `other` (journal/conference distinction "often wrong" per docs); `.source.id`/`.issn`; `.is_in_doaj`; `.is_core` (CWTS Leiden); `journal`/`repository` conveniences; `indexed_in` enum: `arxiv`, `crossref`, `doaj`, `pubmed`.

**Citation:** `cited_by_count` (the rejected silent-recall floor); `cited_by_percentile_year`, `citation_normalized_percentile`, `fwci` (same pathology); `cites:` (works this work cites), `cited_by:`, `referenced_works`, `related_to` (opaque). Graph verbs for the snowball design.

**Quality flags:** `is_retracted` (Retraction Watch), `is_paratext`, `has_abstract` (recall risk as default — many legit works lack abstracts), `has_doi` (drops grey lit), `has_references`, `has_fulltext` (index presence ≠ fetchable PDF), `has_pmid`/`has_pmcid`/`has_orcid`; `has_ngrams`/`mag_only` deprecated/legacy.

**Search filter forms:** `default.search` (title+abstract+fulltext), `title_and_abstract.search` (ours), `title.search`, `abstract.search`, `fulltext.search` (coverage-limited), `.no_stem` variants on title/abstract.

**Sort/sample/pagination:** `sort` by numeric/date fields + `relevance_score` (`:asc`/`:desc`); `select` projection; `per-page` 1–200; basic paging reaches 10k, `cursor=*` beyond; **`sample`** — random sample ≤10,000, `seed` required for paging, no cursor, composes with `filter` (eval-set primitive).

### 3. Boolean syntax inside the search value

UPPERCASE `AND`/`OR`/`NOT` enable boolean mode; quoted phrases exact-match; parentheses set precedence; unjoined terms = AND; Elasticsearch query-string backend with stemming + stop-word removal; **wildcard/fuzzy (`*`, `?`, `~`) are stripped** (silent loss, not 400 — current behavior); `NOT` keyword is the negation (leading `-` is a Crossref-ism, not OpenAlex); no documented operator-count cap.

### 4. Recommendation tiers

**T1 admit now:** `from/to_publication_date` · `type` allowlists · `language` (with auto-detection caveat) · `is_retracted:false` · `is_paratext:false` · `is_oa`/`oa_status` (opt-in; predicts 016 fetch success; never a silent default — OA-venue bias).

**T2 seam:** topic hierarchy + `topics.id` (needs name→id resolution; domain/field cheapest entry) · SDGs (17 fixed IRIs, trivial map — strong T1 candidate given the policy lens; ML-probabilistic tags) · geography (author-affiliation caveat mandatory) · venue family (`source.type` enum + `is_in_doaj`/`is_core` near-T1; ids/ISSNs need resolution) · `indexed_in` · citation-graph verbs (`cites`/`cited_by`/`related_to` — the snowball design) · `fulltext.search`/`.no_stem` · `grants.funder`.

**T3 exclude:** `cited_by_count` floor + `fwci`/percentiles (the rejected class) · `has_abstract`/`has_doi`/`has_references` as defaults · `type_crossref` (dead) · `has_ngrams`/`mag_only` · premium date filters · `apc_*`/`biblio.*`/`fulltext_origin`/corresponding-author niche · Concepts (deprecated).

### 5. Interaction notes

Silent-recall class must never default (citation-derived, has_* presence flags, any narrowing not agent-authored). Safe opt-ins: retraction/paratext guards, dates, language, type lists, OA slices. Author-affiliation vs study geography is the highest-risk semantic trap — directive help must state it or the agent will mis-scope "UK housing policy" as `country_code:gb`. For 016 fetch yield, prefer acquire-broadly + record OA status over pre-filtering on fetchability. Cost levers: `per-page`, `select`, cursor; `mailto` for the polite pool. `sample`+`seed` for eval sets.

**Caveats:** `type` enum drifts over time (re-verify via `group_by=type`); SDG/topic tags are ML-generated relevance hints, not ground truth.

---

## Report 2 — Overton parameter catalog (deep-reasoner, 2026-07-09)

### 0. Source-reliability preamble (the meta-finding)

**Overton's public API documentation does not enumerate its search-filter parameters.** The live swagger page, its raw HTML, and the newest Wayback snapshot (2026-06-10) document only: `query`, `format`, `api_key`, `page`, `next_page_url`, `plain_dois_cited`, `sort`, `show_search_facets`, and the `generate_id_set.php` flow. Zero hits for `squery`, `min_similarity`, `source_type`, `source_country`, `source_region`, `published_after`, `topics`, `classifications`, `sdgcategories`.

Evidence tiers used throughout: **[DOC]** public API doc/changelog verbatim · **[UI]** filter documented in help.overton.io articles, API param name *inferred* · **[V2]** from Policy Atlas V2 code only. **The authoritative param-name source is the app's Export → "Generate API call" flow (login-gated)** — run it with each intended filter set and record the exact query-string keys before shipping the directive.

### 1. Query modes, sorting, pagination, quotas

- **`query`** [DOC] — keyword/boolean fulltext. Advanced syntax [DOC-UI]: `AND`/`OR`/`NOT`, parentheses, quoted phrases, proximity `~N` (`"data science"~1`), diacritics significant, field prefixes — policy docs: `title:`, `domain:` (cited domains), `abstract:`, `full-text:`; scholarly: `title:`, `abstract:`, `author:`, `ID:` (DOI/PubMed/ORCID/grant).
- **`squery`** [V2] — semantic mode; not in public docs. UI equivalent: `similar:` prefix; matches against AI-generated document descriptions; expects descriptive multi-sentence input (UI requires ≥2 lines).
- **`min_similarity`** [V2, UNVERIFIED] — range/default/semantics unpublished; V2's 0.3 is an unvalidated convention.
- **Sort** [DOC]: `relevance` (default for query; Elasticsearch BM25, field boosts: title/translated_title 20×, snippet 10×, source ids 5×, pdf_title 3×, "current as of July 2024" — this is the retained `es_score`) and `date` (default for `plain_dois_cited`).
- **Pagination** [DOC]: `page` (1-based); **`next_page_url`** in the response `query` block is the recommended driver (absent ⇒ end); `results_per_page` reported as **20**; no public page-size param (`pp` is [V2/UNVERIFIED]); observed **page cap** (`total_results: 454144` but `pages: 5000` — "you may have a page limit on your account").
- **`show_search_facets`** [DOC, changelog 2025-07-14]: the roll-up `facets` block is **empty by default**; pass `true` to populate. Per-result fields unaffected.
- **Rate/quotas** [DOC]: ≤1 req/s "with leeway"; sustained abuse ⇒ automatic key block; over-limit = HTTP 429 with empty results; per-user keys; API access off by default per account; bulk work steered to data snapshots.

### 2. Parameter catalog (condensed)

| Param (tier) | Vocabulary | Notes |
|---|---|---|
| `published_after`/`published_before` [UI/V2] | dates | UI "Published after/before" confirms semantics; names [V2]. A separate UI "Year" filter may be a distinct param |
| `added_after`/`added_before` [UI/V2] | dates | DB-ingestion date, not content recency — operational, not intent |
| `source_country` [UI/V2] | country **names** (`USA`, `Canada`, `Germany`) | Facet key `policy_source_country`; NOT ISO codes; multi-value `\|` [V2] |
| `source_region` [UI/V2] | **opaque internal codes** (`_:uxf` = "All but UK" [V2]) + named groups ("OECD countries") | Needs a maintained mapping table |
| `source_state` [V2] | state names | Federal countries only |
| `source_type` [UI/V2] | UI names: government, think tank, NGO, IGO | Response `source.type` observed `"think tank"`; **enum only partially published** |
| `source_sector` [UI] | public / private / third sector | — |
| `source_function`/`source_subtype` [UI/V2] | unenumerated | — |
| `source_id` [DOC] | internal id (e.g. `izade`) | Needs entity lookup |
| `document_type` [UI] | grouped types (working papers, reports, case studies, policy briefs, testimony, clinical guidelines, gov docs) + "thousands of source-specific categories" | Not a closed enum — wrong tokens silently zero-match |
| `topics` [UI/V2] | topic **names** (~650,000) | Huge open vocabulary |
| `subject_area` [UI] | unenumerated taxonomy | — |
| `classifications` (COFOG) [V2] | COFOG divisions | Response-side already parsed; needs a reference table for the agent |
| `sdgcategories` [UI/V2] | UN SDG 1–17 | The one genuinely clean closed vocabulary |
| `language` [UI/V2] | language **names**? (English, French, …) | ISO-vs-name wire format unverified |
| `plain_dois_cited` [DOC] | DOI or `set:N:<hash>` | Policy docs **citing** given DOI(s); bulk sets via `POST generate_id_set.php` (`dois=` newline-separated) |
| `open_cited_institution_authors` [DOC-gist] | OpenAlex-style person/institution id | Policy docs citing a person/affiliation's works |
| Cites-family [UI] | publisher/journal/funder/policy source/news outlet; "Cites others" (policy/research/both) | API names unknown; implies a `*_cited` family |
| "Excluding policy author"/"Excluding source" [UI] | org/source ids | Native negation exists; wire idiom is the `_:` code family [V2] |

### 3. Snowball capabilities (the deferred seam, now documented)

- **Policy→scholarly (forward from a scholarly seed):** `plain_dois_cited=<DOI>` [DOC] returns every policy doc citing that DOI; bulk via `generate_id_set.php`. **The concrete cross-backend hook: seed Overton with DOIs harvested from OpenAlex.**
- **Policy docs citing a person/institution's works:** `open_cited_institution_authors` [DOC-gist].
- **Per-result outgoing references** [DOC]: each returned doc carries its own `cites` block (already retained) — graph expansion without extra calls.
- **Reverse policy→policy inbound ("what cites THIS policy doc"): NOT evidenced** — confirm with Overton support before designing that edge.

### 4. Recommendation tiers

**T1 (contingent on the param-pinning session):** `published_after`/`published_before` · `source_type` · `source_country` (names, not ISO) · `sdgcategories` · `language` (opt-in only; wire format TBD) · `topics` (open vocab — loose validation; zero-match risk argues for T2, see §5).

**T2 seam:** `source_region` (mapping table first — never let the agent emit raw `_:` codes) · COFOG `classifications` (reference table) · `source_id`/`sector`/`function`/`subtype` (entity directory) · the citation/snowball family (§3) · `added_after/before` (operational freshness, not intent).

**T3 exclude:** `min_similarity` as agent-tunable (undocumented semantics — fixed backend constant) · `sort` (backend-fixed relevance) · `document_type`/`subject_area`/`tags` (open/unpublished vocabularies; silent zero-match) · `show_search_facets`/`page`/`format`/`pp` (mechanical, client-owned).

### 5. Interaction notes

Silent-recall hazards if defaulted: `language` (drops non-English policy evidence), `source_country`/`region` (geographic amputation), `source_type` (excludes IGO/think-tank grey lit), wrong `document_type`/`topics` tokens (zero matches, no error), aggressive `min_similarity`. **`squery` + filter co-behavior is undocumented** — assume filters are orthogonal post-filters and `min_similarity` is squery-only, but verify empirically at the pinning session. Filters are best modeled as set restrictions that don't perturb within-set order; `es_score` semantics differ between query modes. Facets block needs `show_search_facets=true` if ever read.

**To verify before shipping the directive:** exact param spellings (Generate API call) · `min_similarity` semantics · `source_type`/`document_type`/`language` vocabularies (facet dump) · reverse policy-inbound existence · `squery`+filter co-behavior.

### Sources
swagger.php (live + Wayback 2026-06-10) · help.overton.io: policy-document-filters, advanced-search, searching-for-similar-policy-documents, how-does-overton-calculate-relevance, policy-documents-filter-language, search-using-topics, changes-to-overton-api, document-vs-pdf-metadata-in-the-api, which-publications-does-overton-collect · gist.github.com/mrstew/ee7de5d2d62298390043899a6ad317a8
