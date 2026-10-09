---
type: Integration quirk
title: OpenAlex search.semantic rejects the date, SDG, paratext, open-access and country filters — fence by publication_year and check the rest locally
description: The OpenAlex semantic endpoint (search.semantic) returns HTTP 400 for from/to_publication_date, sustainable_development_goals, is_paratext, oa_status and authorships.countries, and accepts type, language, is_retracted and publication_year (including <, > and ranges); a directive that carries a rejected filter is sent as a publication_year fence where one exists and the exact rule is applied locally to the semantic results, recorded on the coverage record as semantic_local_filters, and the local predicate must span every variant of a split filter, not the first.
tags: [openalex, search, filters, egress, probe]
timestamp: 2026-10-09
---

# Rules

- **Probe before you trust a filter on the semantic endpoint.** On 2026-10-09 the
  endpoint returned 400 for `from_publication_date`, `to_publication_date`,
  `sustainable_development_goals.id`, `is_paratext`, `oa_status` and
  `authorships.countries`, and 200 for `type`, `language`, `is_retracted` and
  `publication_year` (`<2025`, `>2014`, `2015-2024` all accepted). The probe table is in
  the task 051 verification record and the fixture in `backend/tests/data/probes_051/`.
- **Date directives become a year fence plus a local check.** `published_after` and
  `published_before` go on the wire as `publication_year:>=start-year`/`<=end-year` and
  the exact dates are checked on each returned record before it can become a seed. The
  other rejected keys are checked locally only. `search_loop._semantic_filter_parts`
  and `_semantic_record_passes`; the coverage record lists the keys under
  `semantic_local_filters`. The semantic calls are never skipped (contract D13 as
  amended by the owner).
- **A split filter's local predicate spans the union.** More than 100 affiliation
  countries split the keyword calls into two variants (OpenAlex's clause limit); the
  semantic, resolve and forward calls are made once with no country clause and the local
  check must use *all* the countries, not the first variant's. The 051 review found the
  first-variant bug in two places; `test_two_variant_country_filter_runs_semantic_once_and_filters_locally`
  pins the 101st country.

# Why

Every ground-truth review carries a cutoff date, so a fail-closed skip of the semantic
leg on any rejected filter would have removed the semantic seeds from every dated plan
(about 4 recall points in the design experiments). The amendment keeps the seeds and
keeps the directive exact.

# Citations

- [051 contract D13 and its status-line amendment](../tasks/051-improve-production-search-screen/contract.md)
- [051 verification § Probes, § Owner decision on D13, § Review findings](../tasks/051-improve-production-search-screen/verification.md)
- `backend/src/policy_atlas/evidence_search/sourcing/search_loop.py` (`_semantic_filter_parts`, `_semantic_record_passes`, `_openalex_leg`)
