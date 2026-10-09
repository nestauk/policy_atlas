# Verification: 051-improve-production-search-screen

Evidence for the build of the single-pass search and the adaptive screen
([contract.md](contract.md), [plan.md](plan.md)). Public-safe: no keys, no abstracts, no
full text, no raw traces.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (Phase 0a, build-open baseline on `5d5c044`) | pass | 2589 tests, typecheck, lint, build and eval-check green. The first run failed only at `eval-check` because the new, unformatted `probe_051.py` was created while the run was in progress; after `ruff format`, `make eval-check` passed on its own. |
| `make verify-fast` (Phase 0b/0c gate) | pass | probes, fixtures and the two scripts added; no package code changed |
| `make verify` (step-6 exit) | _pending_ | |
| `make prompt-guard` | _pending_ | |

## Probes (Phase 0b, 2026-10-09)

Script: `scripts/evals/search/experiments/probe_051.py`, run as
`uv run --project backend --env-file backend/.env python scripts/evals/search/experiments/probe_051.py --id govuk-b1e2465b51126438862aa25a92cbe6b3`.
Sanitised excerpts: `backend/tests/data/probes_051/` (ids, titles, scores, dates and
counts only). Probe text: "interventions to reduce loneliness in older adults".

**(a) OpenAlex `search.semantic` with each filter the directive grammar can emit.** One
request per key, the wire part computed by the production mapper `openalex_wire_params`,
`per-page=5`, one second apart.

| directive key | wire filter sent | status | accepted |
|---|---|---:|---|
| (none) | - | 200 | yes |
| `published_after` | `from_publication_date:2015-01-01` | 400 | no |
| `published_before` | `to_publication_date:2024-12-31` | 400 | no |
| `sdgs` | `sustainable_development_goals.id:https://metadata.un.org/sdg/3` | 400 | no |
| `types` | `type:article` | 200 | yes |
| `languages` | `language:en` | 200 | yes |
| `exclude_retracted` | `is_retracted:false` | 200 | yes |
| `exclude_paratext` | `is_paratext:false` | 400 | no |
| `oa_status` | `oa_status:gold` | 400 | no |
| `author_affiliation_countries` | `authorships.countries:GB` | 400 | no |
| (reference, not a directive key) | `publication_year:<2025` | 200 | yes |
| (reference) | `publication_year:2015-2024` | 200 | yes |
| (reference) | `publication_year:>2014` | 200 | yes |

`SEMANTIC_ACCEPTED_FILTER_KEYS = {"exclude_retracted", "languages", "types"}`.

Extra row: a keyword search with `per-page=200` is served with 200 results
(`meta.per_page` 200, 1,674 matches), so one keyword call of 200 is one HTTP page (D3,
D12).

**Consequence for D13, raised to the owner before Phase 3a (see § Review handoff):** the
date fence (`published_before`, `published_after`) is rejected by the semantic endpoint.
Every eval item carries `published_before`, so under the contract's fail-closed rule as
written the semantic calls would be skipped on every eval run and the live check would
measure keyword-only seeds. The experiments that set the thresholds sent
`publication_year:<cutoff year + 1>` and applied the exact date locally.

**(b) Overton `documents.php` with `sort=relevance`.** Status 200. The relevance page
carries `es_score` descending (0.953, 0.939, 0.936, ...); the default page carries no
`es_score` and is ordered by `published_on` descending (2026-10-05, 2026-09-30, ...); the
first result differs between the two orders. Confirms P1 and D8.

**(c) Overton `documents.php?policy_document_id=<id>`.** Status 200, one result, the id
matches, `cites.policy` has 67 entries (the id is a landmark from the task 049 obesity
run: "10 Year Health Plan for England"). Confirms the landmark fetch of D8.

## Fixtures (Phase 0c)

`scripts/evals/search/experiments/export_test_fixtures.py` wrote
`backend/tests/data/pool_fixture.json` (loneliness review, Luna run of experiment 1,
trimmed to 60 seeds / 100 reference ids / 80 forward works; 80 backward records resolved;
220 ranked candidates with `expected_order`) and
`backend/tests/data/policy_replay/{policies-to-reduce-obesity-in-the-uk,
interventions-to-decarbonise-heating,interventions-to-improve-early-years-attainment}.json`
(three relevance-ordered result lists of 40, plus two synthetic title duplicates and one
synthetic titleless record; 13 / 12 / 15 of the 15 landmark ids resolved by fetch-by-id,
the missing ones absent from the service). Two consecutive runs produce identical files
(checksums compared). No snippet, abstract, description, URL or key field is present
(grep over the fixture files). The experiment's reference counter iterates a `set`, so
tie order varied between processes; the export counts in list order (ties by first
appearance) and asserts the counts equal the experiment's, which is the rule production
follows.

## Checks beyond the build

_filled at step 6_

## End-to-end command

_filled at step 6_

## Diff summary

_filled at step 6_

## Review findings

- **Contract verifier:**
- **`/code-review`:**
- **`/security-review`:**
- **Adversarial review** (Tier 3):
- **`/simplify`:**
- **`/okf validate`:**

## Rubric status

_filled at step 7_

## Intent & assumptions

## Known unverified items

## Public safety

## Review handoff (step-7/8 inputs)

- **Knowledge candidates:**
  - OpenAlex `search.semantic` rejects the date-range, SDG, paratext, OA-status and
    country filters and accepts `type`, `language`, `is_retracted` and
    `publication_year` (probe 2026-10-09). A date directive on the semantic leg needs a
    year fence plus a local date check.
  - Overton's default `documents.php` order is by date and carries no `es_score`; only
    `sort=relevance` returns scores.
  - A `Counter` fed from a `set` of strings orders ties differently per process (hash
    randomisation); any "most common, ties by first appearance" rule must iterate lists.
  - The experiment's forward chase with `--forward-top 20` ignores the 300-citation
    ceiling (the `top > 0` branch of `forward_chase` does not filter by `max_cites`);
    the contract D5 applies both. Production follows the contract; the measured run did
    not apply the ceiling.

## Deferred work

_filled at step 6_
