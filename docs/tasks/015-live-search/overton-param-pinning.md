# Overton param-pinning session — 2026-07-09 (design stage)

Operator-sanctioned dev-time probe of `https://app.overton.io/documents.php`
(user supplied `OVERTON_API_KEY` via `.env`, 2026-07-09 — "the key is in
env, go ahead"). 17 calls total, strictly 1 req/s-spaced (1.2 s), 30 s
timeouts, `User-Agent: policy-atlas-pinning/0.1`. The key was redacted
from every byte before it touched disk; raw (redacted) response bodies
live in the session scratchpad only — never the repo. Method: baseline +
facet dump, then per-param probes verified **against the returned
records** (not `total_results` — see finding 2), with a bogus-param
control validating the methodology (unknown params are silently
ignored).

This discharges the contract's rev-3.1 "param-pinning session"
acceptance item at the design stage (rubric 12b). Anything marked
UNTESTED below is re-checked cheaply during the build's live check.

## Pinned facts

1. **All decision-18 candidate params are live and compose with
   `squery`** (each verified on returned records, n=50/probe):
   - `published_after` / `published_before` (`YYYY-MM-DD`) — all
     returned `published_on` values respected the bound.
   - `source_type` — `government` and `think tank` each returned
     uniformly-typed records. (`igo`, `other` observed in facet
     vocabulary; UNTESTED as filter values.)
   - `source_country` — `UK` returned all-UK. Value form = **names**
     (`USA`, `UK`, `Australia`, `Canada`, `Netherlands`), plus
     hierarchical sub-national forms (`USA > Washington`,
     `Australia > New South Wales`) and **`IGO` as a country value** —
     all observed in the facet vocabulary.
   - `language` — **three-letter codes** (`fre` returned all-`fre`;
     facet vocabulary: `eng`, `dut`, `spa`, `jpn`, `fre`, `ger`, `fin`,
     `chi` — ISO 639-2/B-style, NOT ISO 639-1, NOT names).
   - `sdgcategories` — **full label form only**:
     `SDG 11: Sustainable Cities and Communities` filtered correctly;
     bare `11` → **0 results (silent zero-match)**. Label pattern
     `SDG {n}: {UN name}`; 8 labels observed in facets (SDGs 1, 2, 3,
     7, 8, 10, 11, 16), remaining 9 derived from standard UN names —
     spot-check one derived label at the build live check.
   - **Combined filters AND together correctly** (`source_type=
     government` + `source_country=UK` + `published_after=2024-01-01`
     → 50/50 records satisfying all three).
   - `min_similarity` is live and sharp (`0.3` → 1000-doc pool; `0.9` →
     0 results). Stays a backend constant per rev 3.1.
   - `pp` (page size) is live (`pp=5` → 5/page). Default page size
     observed **50** (the API doc's "20" is stale or account-specific).

2. **`total_results` is the PRE-FILTER semantic pool in `squery` mode**
   — it stayed 1000 (the observed semantic candidate cap) under every
   filter, while the returned records were fully filtered and the
   `pages` count shifted. **Client rule: never read `total_results` as
   the filtered count in semantic mode; count returned records.**
   (`acquire_sources` already counts records — no change needed, but
   the coverage/summary code must never "upgrade" to `total_results`.)

3. **No working multi-value OR form exists for these params.** Tested
   on `source_type` with `government` + `think tank`: pipe
   `a|b` → 0 results (literal zero-match — **V2's `safe='|'` urlencode
   assumption does not hold here**); comma `a,b` → 0; repeated key →
   **last-one-wins** (all think tank); PHP `key[]=` array → 0.
   **Grammar consequence: Overton directive keys are single-valued in
   v1**; multi-value needs fan-out into separate rate-limited calls (a
   plan-time call) or stays a seam.

4. **Unknown params are silently ignored** (bogus-param control:
   identical results) — confirms the research's zero-match/silent-
   ignore hazard class and the fail-closed grammar rationale: only
   pinned spellings may ship, and wrong *values* (not wrong *keys*)
   are the residual risk the validated vocabularies close.

5. **`next_page_url` echoes the API key** (confirmed on the baseline
   response) and points at the pinned host — decision 9's
   strip/redact-before-persist requirement and decision 18's
   host-validation rule are both evidence-backed.

6. **Facet vocabulary bonus** (`show_search_facets=true` — the block is
   empty without it, per the 2025-07-14 changelog): richer taxonomy
   than the directive admits — `policy_source_type` is hierarchical
   (`government > city`, `think tank > university affiliated`);
   `policy_source_region` uses **named groups** (`OECD members`,
   `G20`, `G7`, `Europe`, `North America`, `APAC` — friendlier than
   V2's `_:` codes, but the *filter param* for region is UNTESTED);
   three-level source classifications (`Public Sector` /
   `Third Sector` / `Private Sector` → secondary → tertiary);
   `overton_policy_document_series` (`Working paper`, `White paper`,
   `Clinical guidance`, …); rich cites-family facets
   (`publishers_cited`, `journals_cited`, `policy_sources_cited`,
   `news_outlets_cited`, `oa_cited_funders`, ROR-keyed affiliation
   facets) — recorded for the Overton-arm-B and filter-growth seams.

7. **Semantic mode candidate pool caps at 1000** (`total_results`
   exactly 1000 on a broad query; `query` mode on the same string:
   224,427). Deep-mode reformulation diversity matters more than
   paging depth on this backend.

## Residual-probe round (same session, +4 calls — 21 total)

All residual items DISCHARGED; nothing left for the build live check:

- `source_type=igo` → 50/50 `igo`; `source_type=other` → 50/50
  `other`. **Full pinned token set: `government` · `think tank` ·
  `igo` · `other`.**
- `sdgcategories=SDG 13: Climate Action` (a *derived* label, not among
  the 8 facet-observed) → 50/50 carry SDG 13 — the
  `SDG {n}: {UN name}` derivation pattern holds; all 17 label
  constants are safe to pin.
- **`source_region` pinned and PROMOTED**: `source_region=OECD members`
  → 50/50 sources carry `OECD members` in their `source.region` list.
  Named groups work directly — no `_:` code mapping needed for
  affirmative groups. Observed group vocabulary (facets + record
  region lists): `OECD members` · `G7` · `G20` · `Europe` ·
  `North America` · `APAC` · `Oceania` · `EU27` · `EEA` ·
  `Very high human development`. The V2 `_:` negation idiom
  (`All but UK`) remains UNTESTED — exclusion groups stay at the seam.

## Contract deltas (folded as revs 3.3–3.4)

- Overton `languages` values = three-letter codes (pinned vocabulary).
- Overton `sdgs` mapping = full-label constants (bare numbers rejected
  by validation — they silently zero-match on the wire).
- **All Overton keys single-valued** in the v1 grammar (finding 3).
- Coverage/summary code must not read semantic-mode `total_results`
  (finding 2).
- `source_type` tokens `government` · `think tank` pinned; `igo` ·
  `other` admitted pending one live-check confirmation each.
- Default page size 50; `pp` is the working page-size param.
