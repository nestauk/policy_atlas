# Plan: 046-search-baselines

Problems P1–P4, decisions D1–D9, the terms and the arms table are defined in
[contract.md](contract.md). This plan cites them and adds nothing to scope. P2 and D5 are
deferred and have no phase.

> Plan approved (before implementation): 2026-09-25 · owner.
> Plan-stage adversarial review: ran 2026-09-25 (read-only Codex brief). Its findings are
> folded into S1, S4–S6 and Phase 3 below. Two owner changes followed: the P2 deferral
> removed the key-suggestion phase and the raw Overton arm; D9 (fetch once, cache) split
> fetching from scoring (S1, S7).

Executor marks follow AGENTS.md § Agent-side model routing. Every `lead` mark carries
its reason.

**Verify gates.** Full `make verify` at Phase 0 (build-open baseline) and Phase 4
(step-6 exit). Phases 1–2 touch only `scripts/evals/search/` and `.env.example`, no
backend code, no schema. Each gates on `make verify-fast` plus the eval self-test
(`uv run --project backend python scripts/evals/search/test_metrics.py`). Two phases
share one class of risk, so they share one full-verify gate at the exit.

## Decisions fixed here (lead seam design)

S1. **One module, one fetch function per arm, paging pinned per service.**
`baseline_recall.py` holds three functions with one signature:
`fetch_<arm>(intent, cutoff, *, get) -> Fetched`. `get` is the HTTP function (default
`httpx.get` wrapped with the arm's minimum interval and the retry rule) so tests pass a
stub. `Fetched` is a dataclass: `pages` (raw response bodies in order), `request` (the
parameters sent, key removed), `page_size` (as echoed or as sent), `n_failed_calls`,
`complete` (false if the fetch stopped on a failure). Each function pages to 1,000
results or the service's end signal. Paging, per arm:
- Semantic Scholar: header `x-api-key`; `query` with hyphens replaced by spaces (D1);
  `limit=100`; `offset` from the previous response's `next`; stop when `next` is absent,
  when `data` is empty, or when 1,000 results are in hand.
- Consensus: header `x-api-key`; `page` from **0**; `page_size=1000` on the first
  request, then the echoed `page_size` for every later one; stop when `is_end` is true,
  when `results` is empty, or when `(page + 1) × page_size` would exceed 1,000.
- OpenAlex: `per-page=200`, `page` from 1 through `ground_truth.openalex_get`; stop when
  a page has fewer than 200 results or after page 5.
Retry rule for every arm: on 429 wait the `retry-after` header if present, else 1, 2, 4 s;
on 5xx the same waits; after the fourth failure count the request in `n_failed_calls`,
set `complete=False`, and stop paging that review, never raise.

S2. **Cutoff conversion is one pure function per arm**, tested in isolation:
- Semantic Scholar: `publicationDateOrYear = f":{cutoff}"`.
- OpenAlex: `filter = f"to_publication_date:{cutoff}"`.
- Consensus: `year_max = cutoff[:4]`, `month_max = str(int(cutoff[5:7]))` (D2).

S3. **Price table is one dict at the top of the module**, with the pricing date
(2026-09-25) in a comment. `CONSENSUS_USD_PER_CALL = 0.05`; `consensus_calls(n_papers)
= max(1, ceil(n_papers / 100))` per request. Semantic Scholar `0.0`. OpenAlex is
special-cased: its cost is the sum of `meta.cost_usd` over the pages used.

S4. **Own score list, own evaluator.** `BASELINE_SCORE_KEYS = ["search_recall",
"n_found", "n_api_calls", "n_failed_calls", "n_api_records", "n_candidates_kept",
"api_cost_usd"]` (D6). `score_baseline(*, output, **_)` returns one `Evaluation` per key
present in the task output. The Langfuse call is `client.run_experiment(
name="retrieval-baseline", run_name=f"{label}/{arm}-cap{cap}", data=items, task=...,
evaluators=[score_baseline], metadata=meta, max_concurrency=1,
_dataset_version=dataset.version)`, the same shape as `production_recall._run_depth`,
with `meta` per D6 including `fetched_at`. The task output also carries
`n_ground_truth` for the printed lines; it is not uploaded as a score.

S5. **Printed summary only, no CSV.** After all runs the script prints one table: arm,
cap, mean recall, total candidates kept, HTTP requests, failed requests, total
`api_cost_usd`, cache age, and the Langfuse run URL. Per review, one line during scoring
in the style of `production_recall._describe`.

S6. **`history.py` cost column, summed.** For each run, over its items: if the item's
scores include `api_cost_usd`, sum those and label the run `api`; otherwise fetch
`client.api.trace.get(item.trace_id).total_cost` for each item, sum, and label `llm`
(field confirmed in the installed SDK: `TraceWithFullDetails.total_cost`). Print one
column headed `variable cost` as `$1.23 api` or `$0.45 llm`; `n/a` when neither source
has a number. A two-review stub test proves sum, not mean, and both labels.

S7. **Cache and slicing (D9).** `cache_path(arm, item) -> Path` is
`results/cache/<arm>/<item.id sha256[:16]>.json`. `load_or_fetch(arm, item, *, refresh)`
returns a `Fetched` from the file when it exists, is `complete`, and `refresh` is false;
otherwise it fetches, writes `{"arm", "intent", "cutoff", "request", "page_size",
"fetched_at", "complete", "n_failed_calls", "pages"}` and returns it. `records_of(arm,
fetched) -> list[dict]` flattens the pages, in order, into envelope dicts (`doi`,
`backend=<arm>`, `backend_record_id`, `title`). `slice_at_cap(records, cap)` is the first
`cap` records then dedup on `record_key`, in one place so every arm slices the same way.
`requests_for_cap(fetched, cap)` is the number of pages needed to reach `cap` at the
fetched page size; `n_api_calls`, `n_api_records` and `api_cost_usd` for a cap are
computed from those pages only.

## Phase 0 — Build-open baseline — `lead` (inline)

Full `make verify` on the branch. One command, nothing to brief.

## Phase 1 — Baselines script: S1–S5, S7, P1, P3 — `codex`

Judgment-bearing execution against three APIs, multi-function coherence,
machine-verifiable done. The brief carries the contract's arms table, D1–D4, D6, D7, D9
and S1–S5, S7. Codex may probe OpenAlex and Semantic Scholar's bulk endpoint keyless for
shape; Consensus needs the key and is probed by the lead in Phase 3.

Done when:
1. `baseline_recall.py` exists with the three `fetch_*` functions, the three cutoff
   converters, the price table, the S7 cache and slicing functions, `score_arm(records,
   ground_truth) -> dict`, `score_baseline`, the Langfuse upload and the printed summary.
   Command line: `--arms`, `--caps`, `--reviews`, `--run-label`, `--refresh` (ignore the
   cache), `--dry-run` (fetch or load, score, upload nothing). Module docstring in plain
   language; Google-style docstrings on public functions.
2. `test_metrics.py` gains self-checks with saved sample responses (small JSON literals,
   one per arm, the Consensus one shaped like the owner's example response) and a stub
   `get`: record-to-key mapping per arm; each cutoff converter; the hyphen rule; per arm,
   paging stops at 1,000, stops on the end signal, handles a full last page with no
   continuation, and handles an empty page; Consensus starts at page 0 and switches to
   the echoed `page_size`; a 429 with `retry-after` is waited and retried and a fourth
   failure sets `complete=False` and counts in `n_failed_calls` without raising; cache
   round trip (write then load gives equal `pages`; an incomplete file is refetched;
   `refresh=True` refetches); `slice_at_cap` takes the first N then dedups; the cost
   computation per arm and cap including OpenAlex `meta.cost_usd` and Consensus call
   rounding (20 papers = 1 call, 150 = 2, 300 = 3); `score_baseline` emits
   `api_cost_usd`.
3. `.env.example` lists `SEMANTIC_SCHOLAR_API_KEY=` and `CONSENSUS_API_KEY=` with a
   one-line comment each.
4. `make verify-fast` and `test_metrics.py` green. Commit.

## Phase 2 — History cost column: S6, P4 — `fast-worker`

Exact spec in S6; mechanical. Done when `history.py` prints the column with its label,
`--since` still works, and the two-review stub test covers sum-not-mean and both labels.
`make verify-fast` green. Commit.

## Phase 3 — Preflight, live fetch, scoring and history rows: P1, P3, P4 — `lead`

Needs the owner's keys, spends Consensus calls, and the notes are judgment. Order
matters: nothing live runs before step 2 passes.

1. Open the Consensus API & MCP Dashboard: note the plan (Pro, Teams or Deep), included
   calls remaining this month, and whether "additional usage" is on.
2. **Preflight.** The fetch needs at most 10 calls per review (1,000 papers ÷ 100), 40
   calls for four reviews, in 16 requests at page size 300 or 8 at 750. If fewer than 40
   included calls remain and additional usage is off, stop (contract § Stop conditions).
   Otherwise one probe: `baseline_recall.py --arms consensus --reviews <one review>
   --dry-run`, which fetches and caches that review; check the echoed `page_size`, the
   `doi` field, and the timing. Record all three.
3. `baseline_recall.py` over all arms and reviews, all caps. Expected: Semantic Scholar
   40 requests in about 1 minute; OpenAlex 20 requests in under 1 minute; Consensus 12 to
   15 further requests in about 1 minute. Then run it once more with no flags and confirm
   it made zero requests and produced the same table.
4. `history.py --since <today>` → copy rows into `results/history.md` with notes: D1
   favours relevance-ranked services, and the hyphen rule; D2 Consensus month rounding;
   the target is scholarly only (P2 deferred); the comparison rows are the 2026-09-22
   pipeline rows at commit `b16f859` (D8); the raw-versus-pipeline comparison is a sign,
   not a controlled test; the cost figure is computed, not spent, and what it leaves out;
   `fetched_at` of the cache; any failed requests.
5. README section: what the baselines are, how to run them, what the cache is and when
   to pass `--refresh`, how to read the rows next to the pipeline rows, and what the cost
   column does and does not include.
6. Commit.

## Phase 4 — Step-6 exit — `lead`

Full `make verify`; `verification.md` with everything the contract's § Verification
evidence expected lists; the deferred entries (rubric item 10: P2 with the raw Overton arm
and the suggest-only key lookup design at commit `37d496c`; the "swap" slice; S3 upload
of the cache; the ranking-stability test) in `docs/deferred.md`. Commit. Stop. Review runs
in a fresh conversation.
