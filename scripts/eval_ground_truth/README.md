# Ground-truth eval pilot

Measures the search + screen pipeline's precision/recall against a real
systematic review's reference list.

This is also expanded into conducting the same comparison over 15 real systematic reviews.

## Method

The methodology is:
- Gather the references list for the systematic review or reviews using OpenAlex metadata. These are treated as the ground truth dataset i.e. True Positives (TP).
- Deterministically extract "intent" from the title of the systematic review. Because the reviews chosen are ones with "systematic review" or similar in the title, we use deterministic rules to strip the ": a systematic review" part from the title, leaving just the main content of the title. On the assumption that the title accurately defines the scope of the research, this is treated as the "intent". This is important because it means we're bypassing the Planner, so it's not totally faithful to how a real search in Policy Atlas happens. In the app, the Planner turns the user's raw text into an "intent".
- Feed the extracted "intent" to the search step of the workflow. This is just the rapid search at present. The logic for this is that the rapid search is the simplest type of search. We need to calculate recall on just the simplest form of search as a baseline, and then from there we can measure how much the more advanced types of searches improve recall (standard search where there is one round of reformulation; deep search, where there is reformulation, diversity and citation snowballing). **IMPORTANT**: once the bug with the search quota is fixed, we should do a modified version of rapid search here - 1 round of searching, but maybe with a larger cap than 100.
- The screening step proceeds as normal.
- Recall is calculated both at the search stage and at the screening stage. This is because if we just calculated recall after screening, we wouldn't know if recall was low because screening had filtered out too many relevant papers (i.e. screening was to blame for False Negatives (FN)), or if the search had failed to find TP.

Some other points worth knowing:
- A reference is scored on a **key**, not always on a DOI. The key is the DOI
  where the reference has one, and the Overton policy-document id otherwise
  (`ground_truth.record_key`). This is what makes Overton measurable: a
  government evidence review cites statistical bulletins and departmental
  reports with no DOI at all, and DOI-only scoring drops every one of them from
  the target — so Overton could never score a hit, however well it searched.
  In `--doi` mode there is no citation text to look up, so the target stays
  DOI-only and the numbers are unchanged from before this existed.
- A cited policy document that Overton itself does not hold stays unresolvable
  and is left out of the target rather than counted as a miss. Overton recall
  is therefore measured over documents Overton could in principle return — the
  same shape of ceiling that `resolvable_fraction` states for OpenAlex.
- The date cut off is `<date review published> - 1 month`. The OpenAlex date cut off is inclusive so if the date of publication is used directly, you can end up accidentally including the source review itself. We put the cut off 1 month behind that to be on the safe side, as anything published less than a month before the review's publication is highly unlikely to make it into te systematic review.

## How to run

### Gather ground truth

Gather a single review and run metrics:
```
uv run --project backend --env-file backend/.env python scripts/eval_ground_truth/run_and_score.py \
  --title "<review title>" --doi "10.xxxx/yyyy" --generation-backend v1
```

Gather the top 15 reviews from the OpenAlex query below:
```
uv run --project backend python scripts/eval_ground_truth/fetch_review_corpus.py --limit 15
```
OpenAlex Query in OQL:
```
works where title/abstract has (systematic review and policy)
      and year > (2022)
      and title has (
        systematic review
        or rapid evidence
        or evidence assessment
        or evidence review
      )
      and citation count > (50)
      and open access is (true)
```

### Generate metrics
At present you can run the evaluation for either one single systematic review with:
```
uv run --project backend --env-file backend/.env python scripts/eval_ground_truth/run_and_score.py \
  --title "<review title>" --doi "10.xxxx/yyyy" --generation-backend v2
```
or run it over the set of 15 systematic reviews:

```
uv run --project backend --env-file backend/.env python scripts/eval_ground_truth/run_and_score.py \
  --corpus scripts/eval_ground_truth/results/corpus.json --generation-backend v1
```

`--generation-backend` picks which of the two query-generation methodologies
runs. These are the only two arms compared:

| value | class | prompt files |
|---|---|---|
| `v1` | `OpenAISearchGenerationBackend` | `search_queries_system_v3.txt` — one shared prompt writes both the OpenAlex keyword queries and the Overton paraphrases |
| `v2` | `V2SearchGenerationBackend` | `search_queries_openalex_system_v2.txt` and `search_queries_overton_system_v2.txt` — one prompt per provider, called once per query |

Each backend reads its prompts from the committed files beside
`search_prompts.py`. Nothing is swapped at runtime, so to change an arm's
wording you edit its prompt file.


### Downstream analysis

A snippet of code for getting started analysing the data:
```
import json, pandas as pd

raw = json.load(open('results/corpus.json'))

# one row per review
reviews = pd.json_normalize(raw['reviews']).rename(columns={'doi': 'review_doi'})
# → title, review_doi, publication_date, abstract,
#   ground_truth.dois (list), ground_truth.resolvable_fraction, ground_truth.n_unresolved

# one row per (review, cited paper) — the shape you want for recall
pairs = reviews.explode('ground_truth.dois').rename(columns={'ground_truth.dois': 'cited_doi'})
```

NB the column `ground_truth.resolvable_fraction` refers to the proportion of works cited by the systematic review that can be found in the OpenAlex catalogue. `ground_truth.n_unresolved` is the number of works cited in the systematic review that could not be found in OpenAlex. This is important to know because we need to know if the search step in the pipeline ever had a chance at retrieving all the ground truth references.


---------------------------------------------------------------------------------

## Methodology [written by Claude Code]

1. **Ground truth = the review's full reference list** (`ground_truth.py`).
   In `--doi` mode this comes straight from OpenAlex's `referenced_works` — no
   full-text fetch or LLM extraction needed. In `--url` mode (no OpenAlex work
   record exists) it's transcribed from the fetched full text via a
   lead-authored LLM extraction instead, since there's no `referenced_works`
   API to call. This is a deliberate simplification over trying to isolate
   just the review's *included/screened* studies — that narrower extraction
   proved unreliable in practice. The tradeoff: the full reference list also
   contains background/methods/theory citations the pipeline was never going
   to retrieve for a topical research question, so **recall here is a
   conservative, lower-bound estimate** — see Known limitations.
2. **The seed query is the review's own title, with its generic review-type
   suffix stripped** (`clean_review_title()` — e.g. "...: a systematic
   review", "...: a scoping review of RCTs", "... - A Bibliometric Analysis"
   all get trimmed back to the plain scope statement; a title with no such
   suffix passes through unchanged). Most review titles are already a
   well-formed research-scope statement, so this needs no LLM step (see "What
   query style is expected?" below) — it replaces an earlier design that
   LLM-backsolved 3 different paraphrased questions from the title+abstract,
   which added invented phrasing a step removed from what the review actually
   covers. The same cleaned intent is then run `QUERY_COUNT` (3) times
   independently at **rapid** search depth (single round, no reformulation
   loop) — this resamples the search-generation stage's own stochastic query
   fan-out for one fixed intent, rather than resampling different phrasings.
3. **Recall is reported at two checkpoints per query**: `search_recall`
   (ground-truth DOIs present in the raw search candidates, before screening
   runs) and `screen_recall` (ground-truth DOIs still present after
   screening). The gap between the two isolates screening's contribution to
   any lost recall; a low `search_recall` on its own means the pipeline never
   had a chance — screening can't be blamed for it.
4. **Precision is not scored against the reference list at all** — a
   screened-in result absent from it isn't proven irrelevant (the review had
   its own time cutoff and scope; a genuinely relevant paper can simply fall
   outside it). Instead, a GT-blind LLM judge (`relevance_judge.py`, given only
   the seed query and a candidate's own title/abstract — never told about
   ground-truth membership) is run twice: once over screened-in results that
   *are* in the reference list (`judge_calibration_rate` — how often the judge
   agrees with a known true positive), and once over screened-in results
   *absent* from it (`judge_precision_proxy` — the actual precision signal).
   Read `judge_precision_proxy` only alongside `judge_calibration_rate` from
   the same run — a low calibration rate means discount the proxy.
5. `ground_truth.openalex_resolvable_fraction` is the search-space ceiling:
   the pipeline only searches OpenAlex + Overton, so a ground-truth DOI not
   indexed in OpenAlex can never be found regardless of pipeline quality.
   Always read recall alongside this number.
6. **Search is date-constrained to strictly before the review's own
   publication date** (`published_before`, mapped to the pipeline's native
   `context["search"]["filters"]["shared"]["published_before"]` directive —
   OpenAlex's `to_publication_date` / Overton's `published_before`). Without
   this, the pipeline could be credited with "finding" sources that postdate
   the review and that it could never actually have cited — inflating recall
   for reasons that have nothing to do with search/screen quality. **When
   auto-derived from OpenAlex** (`--doi` mode with no explicit
   `--published-before`, and `--corpus` mode), the date is shifted **one
   month earlier** (`_months_earlier()`) — OpenAlex's date filter is
   inclusive, so without the shift the review's own record passes its own
   cutoff and finds itself in its own search results (observed directly: the
   parental-leave review's own DOI in 8 of its own generated queries). The
   month buffer is also a reasonable floor for the real gap between a
   review's literature-search cutoff and its eventual publication date. An
   explicit `--published-before` (required in `--url` mode) is never
   adjusted — only auto-derived dates get shifted.
7. **Search depth defaults to `rapid`** (single round, no reformulation loop)
   so search and screen stay cleanly attributable to each other. `standard`
   (2 rounds) and `deep` (full
   reformulate/snowball/suggest/diversity loop) are available via `--depth`
   but mix in the loop's own steering behavior, muddying that attribution —
   see `search_loop.py:DEPTH_CONSTANTS` for the exact per-depth caps.
8. **`--record-cap-per-backend` raises the candidate pool without changing
   depth's shape at all** — a `search_loop.DEPTH_CONSTANTS[depth]` override
   applied only inside this script's own process (never touches the committed
   pipeline file). Useful because reference lists (44–240 entries observed)
   are routinely much larger than rapid's default 50-kept-per-backend cap can
   ever surface. See "The two caps" for why this is the cap that matters, and
   "Diagnosing low recall" for the measurement.

## Prerequisites

- Docker Postgres running: `docker compose up -d db` from the repo root (or
  `make setup` if this is the first time). Check with
  `docker compose exec db pg_isready -U policy_atlas -q`.
- `backend/.env` populated with `DATABASE_URL`, `OPENAI_API_KEY`,
  `OPENALEX_API_KEY`, `OVERTON_API_KEY` (see `backend/.env.example` for the
  expected shape). `OPENALEX_EMAIL` is optional (OpenAlex polite pool).
  `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` are optional
  — tracing turns on automatically if all three are set, otherwise every LLM
  call is a no-op trace-wise.
- **`.env` is never auto-loaded** — every invocation below needs
  `--env-file backend/.env` explicitly (this repo's own convention; see
  `backend/Makefile`'s `dev` target).

## Running it

From the repo root, DOI mode (ground truth built from the OpenAlex record;
`--published-before` auto-derived from OpenAlex if omitted):

```
uv run --project backend --env-file backend/.env python scripts/eval_ground_truth/run_and_score.py \
  --title "<review title>" --doi "10.xxxx/yyyy"
```

URL mode (grey-literature review with no DOI — `--published-before` is
**required**, since there's no machine-readable date to fall back to):

```
uv run --project backend --env-file backend/.env python scripts/eval_ground_truth/run_and_score.py \
  --title "<review title>" --url "https://.../review.pdf" --published-before 2018-09-01
```

### The two caps

Search has two per-backend caps with similar names and different jobs. Both
are recorded in every run's JSON, and confusing them wastes a lot of time.

| flag | limits | rapid | standard | deep |
|---|---|---|---|---|
| `--result-cap-per-backend` | records requested **per HTTP call** | 50 | 75 | 100 |
| `--record-cap-per-backend` | candidates acquire **keeps per backend** | 50 | 100 | 200 |

`record_cap_per_backend` is applied after merge and dedup, and is the
`acquire.capped` line in the run log. It is normally the tighter of the two,
so it — not the per-call cap — is what bounds the candidate pool and therefore
the recall ceiling. Records past it were fetched and paid for, then discarded.

This is usually the one to raise. It defaults to `RECORD_CAP_PER_BACKEND`
(200) in this eval, above rapid's built-in 50: measured on
`10.1016/S2468-2667(22)00311-5`, the API calls returned 23 of the review's 60
cited papers and a cap of 50 kept only 5. Pass `--record-cap-per-backend 0` to
use the depth's own value instead.

Raising it also raises cost roughly in proportion — every kept candidate is
embedded on acquisition and screened afterwards.

Both flags keep rapid's single-round, no-reformulation shape.
`--depth standard`/`--depth deep` raise both caps too, but bring in extra
rounds and reformulation with them — a different tradeoff, not a substitute.

### Sweeping the keep cap and generation backend (search only)

`sweep_record_cap.py` answers two questions at once: "how high does
`record_cap_per_backend` have to go before recall stops improving?" and "which
query-generation methodology finds more of the review's references?". It runs one
review at every combination of cap and generation backend, with:

* depth `rapid` — one round, no reformulation, as before;
* `result_cap_per_backend` at 2,000 — 40× the pipeline's own 50, so how many
  records one API call may return stops being the limiting factor and the keep
  cap is the only thing changing. (10,000 was tried first; page-numbered paging
  runs out around there and the APIs push back.);
* caps 50, 100, 250, 500, 1000, 2000 (`--caps`);
* generation backends `v1` and `v2` (`--generation-backends`) — the two
  methodologies compared;
* **screening off** — no screening LLM calls, so no screening bill. Retrieval
  is what is being measured; `screen_recall` is not reported.

The two generation backends are:

| value | class | prompt files |
|---|---|---|
| `v1` | `OpenAISearchGenerationBackend` | `search_queries_system_v3.txt` — one shared prompt writes both the OpenAlex keyword queries and the Overton paraphrases |
| `v2` | `V2SearchGenerationBackend` | `search_queries_openalex_system_v2.txt` and `search_queries_overton_system_v2.txt` — one prompt per provider, called once per query |

All prompt files live beside `search_prompts.py` and are read from the
committed copies, so choosing a backend is the whole choice — nothing is
swapped at runtime. To try a different wording, edit the file for the arm you
want to change.

```
uv run --project backend --env-file backend/.env \
    python scripts/eval_ground_truth/sweep_record_cap.py \
  --title "..." --doi "10.xxxx/yyyy" \
  --generation-backends v1 v2 --repeats 1
```

#### Sweeping several reviews at once

`--reviews` takes a CSV instead of a single `--title`/`--doi`, sweeps every
review in it, and adds mean and median recall across reviews to the summary:

```
uv run --project backend --env-file backend/.env \
    python scripts/eval_ground_truth/sweep_record_cap.py \
  --reviews scripts/eval_ground_truth/input/gt_reviews.csv --repeats 1
```

| column | required | meaning |
|---|---|---|
| `title` | yes | cleaned into the search intent |
| `doi` | one of doi/url | bare (`10.xxxx/yyyy`) or as `https://doi.org/...` |
| `url` | one of doi/url | used only when `doi` is empty, for grey literature |
| `published_before` | only for `url` rows | ISO `YYYY-MM-DD` search cutoff. Derived from OpenAlex for a `doi` row; there is nothing to derive it from for a URL, so it must be given |
| `exclude` | no | any non-empty value skips the row |

Every row is checked before any network call, so a malformed sheet fails in a
second rather than part-way through an expensive run. If a review's ground
truth cannot be built (no OpenAlex record, an unreachable page), it is reported
and skipped rather than killing the batch, and the skipped list is reprinted at
the end so it cannot be missed.

The console summary gives a cap × backend recall table per review, then a
combined table with **mean and median side by side**. Read them together: the
mean moves with one review that has a much larger reference list, the median
does not, so a wide gap between them means a single review is carrying the
result.

Cost scales with the number of reviews. The defaults are 12 runs per review, so
a 5-review CSV is 60 full searches — start with one `--caps` value.

`--url` replaces `--doi` for a review with no DOI (grey literature — a
government evidence review published as a web page, say). Its reference list is
fetched, transcribed by an LLM, then resolved entry by entry: to a DOI where
one exists, and otherwise to an Overton policy document by title lookup. That
second pass is what puts Overton's own performance on the scoreboard, and it
adds about 1.2 seconds per DOI-less citation to the one-off ground-truth build.
`--published-before` is required in this mode, because no machine-readable
publication date exists. See "Method" for how keys are scored.

It writes three CSVs into `results/`, all joinable on `run_id` and all carrying
the review's identifier and title, so several reviews' sweeps concatenate into
one table:

| file | one row per | holds |
|---|---|---|
| `record_cap_sweep_runs.csv` | run × backend | calls made, records returned, candidates kept, papers found, recall. Includes `generation_backend_variant`; a `backend=all` row per run gives the run's own de-duplicated totals |
| `record_cap_sweep_queries.csv` | API call | the generated query text, its wire parameters, how many records came back, how many the review actually cited (`gt_hits`). Includes `generation_backend_variant` |
| `record_cap_sweep_papers.csv` | run × reference-list entry | `key`, `space` (`doi` or `overton`), `returned_by_api` / `returned_by`, `reached_db` / `kept_from`. Includes `generation_backend_variant`. Filter to `reached_db` for the true positives each run found; group by `space` to score OpenAlex and Overton targets apart |

A paper both providers return is kept once, under whichever backend reached it
first, so per-backend `n_found` never double-counts and the backend rows sum to
at most the `all` row.

`--repeats` runs each combination more than once, which averages out the fact
that query generation is an LLM call and gives slightly different queries every
time.

Cost warning: one repeat can pull thousands of records from OpenAlex and
Overton — up to 10 pages per OpenAlex call, 40 per Overton call — and the
defaults are already 2 generation backends × 6 caps = 12 runs. Start with `--repeats 1`.

`run_and_score.py` also accepts `--no-screen` for the same "search only, no
screening bill" behaviour on a normal run.

### Batch mode (many reviews at once)

To get an aggregate recall number across a batch of reviews instead of one,
first build a corpus from OpenAlex (recent, well-cited, open-access
systematic/rapid-evidence reviews — no DB or LLM calls, just OpenAlex
metadata + its `referenced_works`):

```
uv run --project backend python scripts/eval_ground_truth/fetch_review_corpus.py --limit 15
```

Then run the eval over every review in it:

```
uv run --project backend --env-file backend/.env python scripts/eval_ground_truth/run_and_score.py \
  --corpus scripts/eval_ground_truth/results/corpus.json
```

Writes one combined report (`results/corpus_eval_report.json` by default,
`--out` to override) with a per-review report (same shape as single-review
mode) plus `aggregate_across_reviews` — `search_recall`/`screen_recall`
pooled across every review's queries. `fetch_review_corpus.py` always uses
the DOI ground-truth path (every OQL candidate has one) — the full-text/LLM
extraction path stays reserved for `--url` mode.

**The LLM-as-a-judge precision proxy is currently OFF** (`RUN_JUDGE = False`
in `run_and_score.py`) to save tokens while this pilot focuses on getting
recall right — `judge_calibration_rate`/`judge_precision_proxy` will show as
`null` in every report until it's flipped back on.

Prints progress per query (ground-truth mode, the cleaned fixed intent,
per-query metrics) and writes a full JSON report to
`scripts/eval_ground_truth/results/<slug>-<identifier>.json` (gitignored —
these are per-run outputs, not something to commit). Every query runs inside
its own rolled-back transaction; nothing this script does is ever committed to
the database.

Self-check for the pure scoring functions (no network, no DB):

```
uv run --project backend python scripts/eval_ground_truth/test_metrics.py
```

## Diagnosing low recall

**Known finding (2026-07-28, 15-review batch)**: `search_recall` averages
**2.4%** (0–9% range), with `screen_recall` nearly identical to
`search_recall` everywhere — screening isn't discarding true positives, there
simply aren't many in the candidate pool to discard.
`openalex_resolvable_fraction: 1.0` on every review rules out "not indexed" —
the papers are there.

**Root cause (revised 2026-08-24, single-review measurement)**: it is
`record_cap_per_backend`, not `result_cap_per_backend`.

An earlier version of this note blamed rapid's `result_cap_per_backend` (50)
being "split across" the query fan-out. That splitting *was* the behaviour, it
was a bug, and it has since been fixed — `result_cap_per_backend` is now
per-HTTP-call, and `search_loop.py:DepthConstants` says so explicitly. The
diagnosis outlived the bug.

Measured on `10.1016/S2468-2667(22)00311-5` (60 cited papers, all 60 indexed
in OpenAlex, rapid depth), one run:

| stage | ground-truth papers still alive |
|---|---|
| indexed in OpenAlex at all | 60 / 60 |
| returned by some API call | **23 / 60** |
| survived dedup + `record_cap_per_backend` (50) | **5 / 60** → `search_recall` 8.3% |
| screened in | 5 / 60 → `screen_recall` 8.3% |

18 API calls returned 617 records. The APIs *did* return 23 of the cited
papers; the keep-cap then discarded 18 of those 23. So roughly 30 of the 52
lost percentage points were fetched, paid for, and thrown away — not missed by
search. Screening lost nothing.

**Use `--record-cap-per-backend`** (Methodology point 8, "The two caps") to
raise the ceiling without changing rapid's single-round shape, then re-check
whether recall moves. Two further findings from the same run point at query
*diversity* as the next bottleneck once the cap stops binding:

- Only 4 of 18 calls returned any cited paper. The `"systematic review" OR
  "meta-analysis"` and RCT-filtered query variants returned none — expected,
  since the recall target is the primary studies a review *cites*, not other
  reviews.
- Overton returned 150 records carrying 3 DOIs between them. Recall is keyed
  on DOIs, so the Overton leg cannot currently score at all.

`inspect_run.py` reproduces all of the above from a saved report — see
"Unpicking a run" below.

Each `per_query` entry in the report includes `search_calls`: every
OpenAlex/Overton query the search-generation stage actually produced for that
run, and the raw (unnormalized) provider records it returned — captured by
wrapping the live backends in a transparent `_RecordingBackend`
(`run_and_score.py`), which never alters what the pipeline itself does. Shape:

```json
"search_calls": [
  {"backend": "openalex", "method": "search", "query": "...", "wire_params": {...},
   "result_count": 23, "records": [{"...": "raw OpenAlex work JSON"}, ...]},
  {"backend": "overton", "method": "search", "query": "...", "wire_params": {...},
   "result_count": 4, "records": [...]}
]
```

### Unpicking a run

`inspect_run.py` turns that raw data into per-stage tables, so you can see the
**title and DOI** of every record every API call returned instead of only the
counts. Every function is a read-only view over data a run already produced,
so a run sitting in a notebook kernel (or a saved report) can be inspected
without paying for the API calls again.

```python
from inspect_run import call_table, records_table, funnel_table, ground_truth_table

summarize(ground_truth, RUN)                        # the funnel, as counts
call_table(RUN.search_calls, ground_truth.dois)     # one row per API call
records_table(RUN.search_calls, ground_truth.dois)  # one row per returned record
gt = ground_truth_table(ground_truth)               # the recall target, with titles
funnel_table(ground_truth, RUN, gt)                 # where each cited paper was lost
cap_losses(ground_truth, RUN, gt)                   # found by API, dropped by the cap
unexplained_screened(RUN, ground_truth)             # screened in, not cited
```

`funnel_table` answers the question that matters, per cited paper, in pipeline
order:

- `returned_by_api` False → no generated query reached it. A search-generation
  or coverage problem.
- `returned_by_api` True, `reached_db` False → the API found it and
  `record_cap_per_backend` threw it away. Raise the cap; do not rewrite the
  queries.
- `reached_db` True, `screened_in` False → the pipeline had the paper in hand
  and judged it irrelevant.

Titles and DOIs come from the pipeline's own record mappers
(`acquire._MAPPERS`), not a second parse of the provider JSON, so what you see
is what the pipeline saw.

`funnel_table`'s last two columns need `search_docs` / `screened_docs` on
`QueryResult`; a report saved before those fields existed shows them as `None`
rather than failing. The API-call views need only `search_calls`.

`run_and_score.ipynb` drives all of this for a single review, one cell per
stage. Note that the notebook calls `run_one_query` directly and so bypasses
`main()` — it applies the cap override in its own cell.

## Choosing a review

Pick a **policy/social-science review with a real reference list** —
journal-article-heavy bibliographies give OpenAlex the best chance of
indexing them; a review skewed toward grey literature/government reports
leans more on the Overton backend. Since ground truth is now the *whole*
reference list rather than a narrower included-studies set, a bibliometric or
scientometric analysis of a field works fine too (no PRISMA-style
included-studies list required) — its bibliography is simply treated the same
as any other review's.

## What query style is expected?

`evidence_scope.intent` — the field this script writes the cleaned title
into directly — is contractually a single, sharp, planner-refined research
question (`docs/tasks/017-orchestrator/contract.md`), not raw conversational
user input; downstream consumers (search generation, screening) cap it at
2000 characters (`SEARCH_INTENT_MAX` / `SCREEN_INTENT_MAX`). This script
skips the conversational planner entirely — a systematic review's title
(minus its generic review-type suffix) already sits in that same
sharp-research-question register, so no LLM paraphrase is needed to write
something intent-shaped into `intent`.

## Files

- `ground_truth.py` — OpenAlex `referenced_works` resolution (`--doi` mode) or
  full-text fetch + LLM reference-list transcription (`--url` mode), DOI
  resolution, OpenAlex-resolvability ceiling.
- `fetch_review_corpus.py` — builds a batch corpus of reviews from an OpenAlex
  filter query (DOI ground-truth path only), for `run_and_score.py --corpus`.
- `relevance_judge.py` — the GT-blind precision-proxy/calibration judge
  (currently unused — `RUN_JUDGE = False` in `run_and_score.py`).
- `run_and_score.py` — entrypoint: cleans the review title into a fixed
  intent (`clean_review_title()`), seeds a throwaway project/run/scope per
  repeat, runs the real `run_search`/`screen_sources` (through a
  `_RecordingBackend` wrapper that captures every generated query + raw
  provider records for later diagnosis — see "Diagnosing low recall"),
  partitions results against the ground-truth set, runs the judge, computes
  metrics, writes the report. `--corpus` runs this over every review in a
  `fetch_review_corpus.py` corpus and adds an aggregate-across-reviews report.
- `sweep_record_cap.py` — search-only sweep of `record_cap_per_backend` and of
  the query-generation prompt, with the per-call fetch cap effectively removed
  and screening off. Writes three joinable CSVs (runs, queries, papers). See
  "Sweeping the keep cap and the prompt".
- `inspect_run.py` — per-stage diagnosis views over a finished run: titles and
  DOIs per API call, and a per-paper funnel showing where each cited paper was
  lost. Read-only, no network or DB of its own. See "Unpicking a run".
  `python inspect_run.py` runs its own self-check on synthetic data.
- `test_metrics.py` — self-check for the pure scoring functions (DOI
  normalization, recall, partitioning).
- `run_and_score.ipynb` — the same pipeline as `run_and_score.py`, one cell per
  stage, for inspecting a single review interactively.
- `experiment_generate_queries.ipynb` — interactive notebook for the
  query-generation LLM call in isolation (no DB/OpenAlex/Overton needed, just
  `OPENAI_API_KEY`): build an intent, generate queries, see the rapid-depth
  SR/RCT-variant fan-out and quota math locally, and observe run-to-run
  stochasticity. See the notebook's own first cell for how to launch it.

## Known limitations

- Ground truth is the review's full reference list, so recall is a
  conservative/lower-bound estimate — background, methods, and theory
  citations count toward it even though the pipeline was never going to
  retrieve them for a topical research question.
- Rapid search depth only — deep mode's multi-round, screen-steered
  reformulation loop (`search_loop.py:run_deep_rounds`) is not exercised by
  this pilot.
- Reference-list extraction from free-text PDFs (`--url` mode) is imperfect —
  check `ground_truth.unresolved_citations` in the report before trusting a
  run's numbers. `--doi` mode has no such extraction step (OpenAlex
  `referenced_works` is used directly), so this doesn't apply there.
- The relevance judge is itself an LLM call, not ground truth — it's a single
  GT-blind rep, cruder than the real screen's 3-rep consensus, and is only as
  trustworthy as its own calibration rate on the same run.
