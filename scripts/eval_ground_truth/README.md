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
- At present this only evaluates against academic reviews - **still need to add a policy source(s) of ground truth**
- The date cut off is `<date review published> - 1 month`. The OpenAlex date cut off is inclusive so if the date of publication is used directly, you can end up accidentally including the source review itself. We put the cut off 1 month behind that to be on the safe side, as anything published less than a month before the review's publication is highly unlikely to make it into te systematic review.

## How to run

### Gather ground truth

Gather a single review and run metrics:
```
uv run --project backend --env-file backend/.env python scripts/eval_ground_truth/run_and_score.py \
  --title "<review title>" --doi "10.xxxx/yyyy"
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
  --title "<review title>" --doi "10.xxxx/yyyy"
```
or run it over the set of 15 systematic reviews:

```
uv run --project backend --env-file backend/.env python scripts/eval_ground_truth/run_and_score.py \
  --corpus scripts/eval_ground_truth/results/corpus.json
```


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
   (75 results/backend, 2 rounds) and `deep` (150/backend, full
   reformulate/snowball/suggest/diversity loop) are available via `--depth`
   but mix in the loop's own steering behavior, muddying that attribution —
   see `search_loop.py:DEPTH_CONSTANTS` for the exact per-depth caps.
8. **`--result-cap-per-backend` raises the candidate pool without changing
   depth's shape at all** — a `search_loop.DEPTH_CONSTANTS[depth]` override
   applied only inside this script's own process (never touches the committed
   pipeline file). Useful because reference lists (44–240 entries observed)
   are routinely much larger than rapid's default 50-per-backend cap can ever
   surface — see "Diagnosing low recall."

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

Add `--result-cap-per-backend 200` (or any value) to raise rapid's default
50-per-backend cap while keeping its single-round, no-reformulation shape —
see "Diagnosing low recall". `--depth standard`/`--depth deep` also raise the
cap (75/150 per backend) but bring in a second round and reformulation with
it — a different tradeoff, not a substitute.

A large cap may need `--disable-wall-clock` alongside it: rapid's 30-second
wall-clock budget (`RAPID_WALL_CLOCK_S`) is untouched by
`--result-cap-per-backend` and can cut a run off before it finishes fetching
a big cap's worth of results — remaining planned calls are silently skipped
when that happens, which reads as a mysteriously small result count rather
than an obvious error. `--disable-wall-clock` removes the depth's wall-clock
budget entirely (same eval-local `DEPTH_CONSTANTS` override mechanism,
never touches the pipeline file).

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
simply aren't many in the candidate pool to discard. Root cause: rapid depth's
`result_cap_per_backend` (50) is split across up to 5 OpenAlex queries + 2
Overton paraphrases (`search_prompts.py:N_QUERIES`), so raw candidate counts
land around 17–36 total per run — while reference lists run 44–240 entries.
Recall is capped by that ratio before search quality even matters (e.g. 240
GT DOIs vs. 20-ish candidates caps recall at ~8% even with perfect precision).
`openalex_resolvable_fraction: 1.0` on every review rules out "not indexed" —
the papers are there, just not pulled in given the tiny per-query quota.
**Use `--result-cap-per-backend`** (Methodology point 8) to raise the ceiling
without changing rapid's single-round shape, then re-check `search_calls`
(below) to see whether recall moves with a bigger candidate pool, or whether
query *diversity* (not just depth) is the remaining bottleneck.

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

Load a report's JSON in a notebook (`json.load` + `pandas.json_normalize` on
`report["per_query"][i]["search_calls"]`) to inspect exactly what queries were
generated and what came back, e.g. to check whether a known ground-truth DOI
ever appeared in any raw result set (if not, that's a search-generation/
OpenAlex-coverage problem) versus appeared but got dropped before screening
(a different problem — check `result_count` vs. what ends up in
`source_snapshot` for that project).

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
- `test_metrics.py` — self-check for the pure scoring functions (DOI
  normalization, recall, partitioning).
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
