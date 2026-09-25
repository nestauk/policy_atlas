---
type: Integration quirk
title: Semantic Scholar has two search engines — paper/search needs every word to match, snippet/search ranks by meaning
description: The Academic Graph API's paper/search is an all-words keyword match (a title-length query returned totals of 0, 1 and 22 for three of four review intents); the same API's snippet/search is a dense retriever over title, abstract and body passages, returns up to 1,000 snippets in one request keyed by corpusId only (map to DOIs with paper/batch, 500 ids per call), collapses to about 550 unique papers, and leans towards open-access papers because only they have body text.
tags: [search-backends, semantic-scholar, retrieval, evaluation, rate-limits]
timestamp: 2026-09-25
---

# Rules

- **`GET /graph/v1/paper/search` is a keyword engine.** Every word of the query must be
  present in the paper (the bulk variant's docs say so; the plain endpoint behaved the
  same live). A verbatim review title is the wrong shape for it: 046 saw the service's own
  `total` of 0, 1, 22 and 29,628 for the four intents. Hyphenated terms match nothing;
  send hyphens as spaces. Pages of `limit=100` by `offset`, `next` absent on the last
  page, 1,000-result ceiling.
- **`GET /graph/v1/snippet/search` is a semantic engine** (`retrievalVersion` `pa1-v1` on
  2026-09-25). It ranks passages from title, abstract and body text by meaning; a verbatim
  intent works. One request returns up to 1,000 snippets (`limit=1000`), no paging.
- **Snippets name papers by `corpusId` only.** To score on DOIs, collect the unique ids in
  first-appearance order and `POST /graph/v1/paper/batch?fields=externalIds,title` with
  `{"ids": ["CorpusId:<id>", ...]}`, 500 ids per call. In 046, 1,000 snippets collapsed
  to 417-638 unique papers, and 7 of 2,204 had no DOI.
- **Body-text snippets exist only for open-access papers** (69-92% of the snippets were
  body text), so the engine leans towards them. Say so next to its numbers.
- **The free tier throttles below one request per second in practice** even with a key;
  a 3 s interval plus the retry rule fetched four reviews cleanly. Keyless requests hit
  the shared pool and get 429 at once.
- Both endpoints take `publicationDateOrYear=:<YYYY-MM-DD>` as an inclusive upper bound.
  The snippet response carries no dates, so the filter cannot be audited from the response.

# Why

046's first arm was meant to show what Semantic Scholar's relevance ranking does with a
plain intent and instead measured the query's shape: 1.5% recall at the ceiling. The
snippet engine on the same intents reached 18.1%, above the pipeline's deep depth, with one
free request per review. The two numbers belong to the same service and must not be read
as one.

# Watch out

- A cap of N on the snippet arm is the first N **unique papers**; the other arms take the
  first N results and then remove duplicates. Name that asymmetry with the results.
- Every cap needs the search plus its lookups, so a per-cap request count is a fetch
  count, not a "requests to reach this cap" count.

# Citations

- [046 contract § Arms (arm 1 and 1b)](../tasks/046-search-baselines/contract.md)
- [046 verification § Phase 5 addendum and § Review findings](../tasks/046-search-baselines/verification.md)
- `scripts/evals/search/baseline_recall.py` `fetch_semantic_scholar`,
  `fetch_semantic_scholar_snippet`; `test_metrics.py::test_baseline_snippet_arm`
- `scripts/evals/search/results/history.md` rows dated 2026-09-25
