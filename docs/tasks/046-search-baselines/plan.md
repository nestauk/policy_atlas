# Plan: 046-search-baselines

Problems P1–P4, decisions D1–D8, the terms and the arms table are defined in
[contract.md](contract.md). This plan cites them and adds nothing to scope.

> Plan approved (before implementation): _pending · owner_.
> Plan-stage adversarial review: ran 2026-09-25 (read-only Codex brief). Its seven
> findings are folded into S1, S4–S7 and Phase 4 below.

Executor marks follow AGENTS.md § Agent-side model routing. Every `lead` mark carries
its reason.

**Verify gates.** Full `make verify` at Phase 0 (build-open baseline) and Phase 5
(step-6 exit). Phases 1–3 touch only `scripts/evals/search/` and `.env.example`, no
backend code, no schema. Each gates on `make verify-fast` plus the eval self-test
(`uv run --project backend python scripts/evals/search/test_metrics.py`). Three phases
share one class of risk, so they share one full-verify gate at the exit.

## Decisions fixed here (lead seam design)

S1. **One module, one function per arm, paging pinned per service.** `baseline_recall.py`
holds four functions with one signature: `fetch_<arm>(intent, cutoff, cap, *, get) ->
ArmResult`. `get` is the HTTP function (default `httpx.get` wrapped with the arm's minimum
interval and the retry rule) so tests pass a stub. `ArmResult` is a dataclass: `records`
(list of envelope dicts with `doi`, `backend`, `backend_record_id`, `title`), `n_calls`,
`n_failed_calls`, `n_api_records`, `api_cost_usd`. Paging, per arm:
- Semantic Scholar: `limit=min(100, remaining)`, `offset` from the previous response's
  `next`; stop when `next` is absent, when `data` is empty, or at the cap.
- Consensus: `page` from 1, `page_size` from the preflight; stop when `is_end` is true,
  when the page is empty, or at the cap.
- OpenAlex: `per-page=200`, `page` from 1; stop when a page has fewer than 200 results
  or at the cap.
- Overton: first request as in the arms table; then the response's next-page URL,
  exactly as `search_live.OvertonLiveBackend._search` reads it; stop when absent, when
  the page is empty, or at the cap.
Retry rule for every arm: on 429 or 5xx wait 1, 2, 4 s and retry; after the fourth failure
count the request in `n_failed_calls` and stop paging that review, never raise. Records
are de-duplicated on scoring key before counting `n_candidates_kept`.

S2. **Cutoff conversion is one pure function per arm**, tested in isolation:
- Semantic Scholar: `publicationDateOrYear = f":{cutoff}"`.
- OpenAlex: `filter = f"to_publication_date:{cutoff}"`.
- Overton: `published_before = cutoff`.
- Consensus: `year_max = cutoff[:4]`, `month_max = str(int(cutoff[5:7]))` (D2).

S3. **Price table is one dict at the top of the module**, with the pricing date in a
comment. Keys are arm names; values `(usd_per_request, usd_per_100_papers)`. OpenAlex is
special-cased: its cost is the sum of `meta.cost_usd` over its responses. Consensus's
credit price is filled in from the owner's plan in the Phase 4 preflight; until then it
is `0.0` with a `# ponytail:` comment naming the gap.

S4. **Own score list, own evaluator.** `BASELINE_SCORE_KEYS = ["search_recall",
"n_found", "n_api_calls", "n_failed_calls", "n_api_records", "n_candidates_kept",
"api_cost_usd"]` (D6). `score_baseline(*, output, **_)` returns one `Evaluation` per key
present in the task output. The Langfuse call is `client.run_experiment(
name="retrieval-baseline", run_name=f"{label}/{arm}-cap{cap}", data=items, task=...,
evaluators=[score_baseline], metadata=meta, max_concurrency=1,
_dataset_version=dataset.version)`, the same shape as `production_recall._run_depth`,
with `meta` per D6. The task output also carries `n_ground_truth`, `n_found_doi`,
`n_target_doi`, `n_found_overton`, `n_target_overton` for the printed per-space summary
(D3); these are not uploaded as scores.

S5. **Printed summary only, no CSV.** After all runs the script prints one table: arm,
cap, mean recall, mean scholarly-space recall, mean grey-space recall, total candidates
kept, total HTTP requests, failed requests, total `api_cost_usd`, and the Langfuse run
URL. Per review, one line during the run in the style of `production_recall._describe`.

S6. **D5 lives in `ground_truth_dataset.py` as three small functions plus a flag.**
- `normalize_title(text) -> str`: lowercase, drop punctuation, collapse spaces.
- `openalex_candidates(title, get) -> list[Candidate]` and `overton_candidates(title,
  get, api_key) -> list[Candidate]`, each one request as pinned in D5 (OpenAlex through
  `ground_truth.openalex_get` with `**{"per-page": "10"}`; Overton `query=`), returning
  only records whose normalised title equals the reference's and which have a key.
  `Candidate` is a dataclass: `key`, `title`, `year`, `source` (OpenAlex venue or Overton
  publisher name). A request that fails after retries returns a sentinel so the caller
  prints `LOOKUP FAILED`.
- `suggest_keys(references, ...)` prints the `EXACT` / `AMBIGUOUS` / `NONE` / `LOOKUP
  FAILED` lines and exits. It runs only under `--suggest-keys`; the default path makes
  zero lookup requests.
- Default path change: `build_items` adds `unscorable_titles` (sorted list) to item
  metadata; `load_references` collects the titles it already counts.

S7. **`history.py` cost column, summed.** For each run, over its items: if the item's
scores include `api_cost_usd`, sum those and label the run `api`; otherwise fetch
`client.api.trace.get(item.trace_id).total_cost` for each item, sum, and label `llm`
(field confirmed in the installed SDK: `TraceWithFullDetails.total_cost`). Print one
column headed `variable cost` as `$1.23 api` or `$0.45 llm`; `n/a` when neither source
has a number. A two-review stub test proves sum, not mean, and both labels.

## Phase 0 — Build-open baseline — `lead` (inline)

Full `make verify` on the branch. One command, nothing to brief.

## Phase 1 — Baselines script: S1–S5, P1, P3 — `codex`

Judgment-bearing execution against four APIs, multi-function coherence,
machine-verifiable done. The brief carries the contract's arms table, D1–D4, D6, D7 and
S1–S5. Codex may probe OpenAlex and Semantic Scholar's bulk endpoint keyless for shape;
Consensus needs the key and is probed by the lead in Phase 4.

Done when:
1. `baseline_recall.py` exists with the four `fetch_*` functions, the four cutoff
   converters, the price table, `score_arm(records, ground_truth) -> dict`,
   `score_baseline`, the Langfuse upload and the printed summary. Command line: `--arms`,
   `--caps`, `--reviews`, `--run-label`, `--dry-run` (fetch and score, upload nothing).
   Module docstring in plain language; Google-style docstrings on public functions.
2. `test_metrics.py` gains self-checks with saved sample responses (small JSON literals,
   one per arm) and a stub `get`: record-to-key mapping per arm; each cutoff converter;
   per arm, paging stops at the cap, stops on the end signal, handles a full last page
   with no continuation, and handles an empty page; a 429 is retried with the pinned
   waits and a fourth failure is counted in `n_failed_calls` without raising; cost sum
   per arm including the OpenAlex `meta.cost_usd` path; `score_baseline` emits
   `api_cost_usd`; duplicates on key count once in `n_candidates_kept`.
3. `.env.example` lists `SEMANTIC_SCHOLAR_API_KEY=` and `CONSENSUS_API_KEY=` with a
   one-line comment each.
4. `make verify-fast` and `test_metrics.py` green. Commit.

## Phase 2 — Key suggestion: S6, P2 — `codex`

Small, but the matching rule is the thing that can invent hits, so it is
judgment-bearing. Brief carries D5 and S6. Done when:
1. The three functions, the `Candidate` dataclass, `--suggest-keys` and the
   `unscorable_titles` metadata exist.
2. `test_metrics.py` gains: `normalize_title` cases (case, punctuation, spaces, an
   en-dash); a near-miss title yields no candidate; an exact match after normalisation
   does; a matching title with no key is skipped; one candidate → `EXACT`, two → `AMBIGUOUS`,
   none → `NONE`, a failing stub → `LOOKUP FAILED`; the default path calls the stub zero
   times; `build_items` puts the unscorable titles into metadata.
3. `--dry-run` on a two-row fixture CSV pair (built in the test, not committed under
   `input/`) prints the expected lines.
4. `make verify-fast` and `test_metrics.py` green. Commit.

## Phase 3 — History cost column: S7, P4 — `fast-worker`

Exact spec in S7; mechanical. Done when `history.py` prints the column with its label,
`--since` still works, and the two-review stub test covers sum-not-mean and both labels.
`make verify-fast` green. Commit.

## Phase 4 — Preflight, live run and history rows: P1–P4, D8 — `lead`

Needs the owner's keys and CSVs, spends money, and the notes are judgment. Order matters:
nothing live runs before step 3 passes.

1. Owner places `gt_reviews.csv` and `references.csv` in `scripts/evals/search/input/`.
2. Read the Consensus plan page: included credits this month, credit price, largest
   `page_size`, and any stated rate limit. Fill the price table (S3) and the page size.
3. **Spend and time preflight.** Requests for the full run = 4 reviews × pages for caps
   50, 100, 200, 1,000 at the confirmed page size (68 pages per review at size 20, 272
   requests, $13.60 above credits plus about 55 paper credits). If the expected spend is
   above £30, stop (contract § Stop conditions). Then one probe: `baseline_recall.py
   --arms consensus --caps 50 --reviews <one review> --dry-run`, timed, to see the rate
   limit and confirm the response shape. Record both.
4. `ground_truth_dataset.py --suggest-keys` → read the report. The owner accepts or
   rejects each `EXACT` and `AMBIGUOUS` candidate against the review's bibliography and
   pastes accepted keys into `references.csv`. Then `ground_truth_dataset.py --dry-run`,
   then upload.
5. `baseline_recall.py` over all arms and caps. Expected wall time: Semantic Scholar about
   1 minute; OpenAlex under 1 minute; Overton about 2 minutes (20 pages × 1.2 s × 4
   reviews); Consensus as measured in step 3.
6. `make eval-search-recall ARGS="--depths rapid"` (D8).
7. `history.py --since <today>` → copy rows into `results/history.md` with notes: D1
   favours relevance-ranked services; D2 Consensus month rounding; which references
   gained keys and how the denominators changed; scholarly versus grey space; the
   raw-versus-pipeline comparison is a sign, not a controlled test; any failed requests;
   what the cost column leaves out.
8. README section: what the baselines are, how to run them, how to read them next to the
   pipeline rows, what `--suggest-keys` does and how to pin its results.
9. Commit.

## Phase 5 — Step-6 exit — `lead`

Full `make verify`; `verification.md` with everything the contract's § Verification
evidence expected lists; the deferred entries (rubric item 11) in `docs/deferred.md`.
Commit. Stop. Review runs in a fresh conversation.
