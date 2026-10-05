## What / why

Task: `docs/tasks/046-search-baselines/`

The pipeline's search recall (5.6% rapid, 15.3% deep on four evidence reviews) had nothing
to be compared with. This slice adds **baselines**: one plain search of each review's
intent text on Semantic Scholar (keyword and semantic engines), Consensus and OpenAlex, no
language model, no screening, fetched once to 1,000 results into a git-ignored local cache
and scored at caps 50, 100, 200 and 1,000 with the pipeline's own scoring key and recall
formula. Every run lands in Langfuse and as a row in `scripts/evals/search/results/history.md`
next to the pipeline rows from 2026-09-22. A **variable cost** column (computed `api` price
for baselines, Langfuse `llm` spend for pipeline runs) lets recall and money be traded off.

Headline: Semantic Scholar's semantic (snippet) search reaches **18.1%** at the ceiling with
one free request per review, above the pipeline's deep depth; Consensus 13.6%; one raw
OpenAlex search 6.5%; Semantic Scholar's keyword search 1.5% (a verbatim title is the wrong
shape for an all-words engine). Strong sign that retrieval method, not corpus, is the
pipeline's weak part. All numbers are scholarly recall only: every ground-truth key is a DOI
(P2 deferred to the owner's ground-truth expansion).

**Amendment 2 (owner-directed, folded in post hoc, contract § Amendment 2):** four
ground-truth **fetchers** that start the expansion from four hand-made reviews towards about
one hundred: `get_campbell.py` (Campbell Systematic Reviews via OpenAlex, reference lists
resolved to DOIs), `get_3ie.py` (every evidence gap map on 3ie's Development Evidence Portal,
one review per map and per intervention row), `get_yef.py` (the Youth Endowment Fund gap map
and its toolkit strands) and `get_sr4all.py` (the Webis-SR4ALL-26 corpus, social-science
fields, most-cited reviews). Each writes the two CSV shapes `ground_truth/upload.py` already
reads (D10); gap-map rows are labelled `content`, reference lists stay unlabelled until the
labelling pass (D11). Shared helpers land in `ground_truth.py`. P2 itself stays deferred.

**Amendment 3 (owner-directed, 2026-10-05):** the ground-truth **sample**. The fetchers moved
to `getters/`; `ground_truth/select_sample.py` applies a simple quality check (one specific question,
20 to 300 references with a DOI, at least 70% with a DOI, cutoff in the past and from 2010) and
picks 30 Campbell, 30 3ie, 30 SR4ALL and 10 YEF rows by rotating across topics, plus ten
hand-chosen rows out of those for cheap checks, leaning towards Nesta's missions. The owner chose to skip the labelling pass, so the Campbell
and SR4ALL lists are used whole and their recall ceiling is about 50% (README § 7). The mini
dataset (`retrieval-ground-truth-mini`) is the ten plus the four original reviews, fourteen
items, copied in with the uploader's new `--include-from`; `retrieval-ground-truth-full` is
the hundred.

**Layout (2026-10-05):** the folder is split by purpose: `evals_search_utils.py` (shared),
`ground_truth/` (getters, sample selection, upload), `measure/` (engine and the three
runners), `history.py`, `tests/`. A new `make eval-check` (the two test files plus ruff on the
folder) runs inside `make verify` and `make verify-fast`.

Files: `scripts/evals/search/measure/baseline_recall.py` (new), `history.py` (cost column),
`tests/test_ground_truth.py`, `tests/test_measure.py` (self-checks), `README.md` § 5 and § 6, `results/history.md`,
`backend/.env.example` (two empty key names), `get_campbell.py`, `get_3ie.py`, `get_yef.py`,
`get_sr4all.py` (new, under `getters/`), `ground_truth/select_sample.py` (new), `ground_truth.py`
(shared fetcher helpers), `docs/deferred.md`,
`docs/knowledge/` (four concepts, one update), `docs/agentic-ops/environment.md`.

## Proof it works

Evidence in `docs/tasks/046-search-baselines/verification.md`.

- **`make verify`:** pass (build-open, step-6 exit, review-open, and after the review fixes,
  at `36596c2`). Not yet re-run on the Amendment 2 commit.
- **Self-checks:** `uv run --project backend python scripts/evals/search/tests/`
  → `ok` (eleven new checks, extended by the review stack: paging per arm incl. Consensus's
  refusal to cross 1,000, retry pacing, cache round trip and staleness, cost at a cap,
  snippet arm, history cost column and 404 guard).
- **Live check:** one full fetch of every arm over the four reviews, then all scoring from
  the cache; about 85 Consensus calls (about $4.25) for the whole build, $0.00 in review.
  A cache re-score with the paid keys blanked made zero requests and reproduced every row.
- **Langfuse:** dataset `retrieval-ground-truth`, runs `2026-09-25-8b4a61b/<arm>-cap<cap>`
  and `2026-09-25-af1c86e/semantic-scholar-snippet-cap<cap>`; exactly the seven D6 scores
  and six metadata keys per run, values equal to `history.md`.

## Risk tier

Tier 2 — new developer-run eval scripts and docs; nothing under `backend/src`, no schema,
auth, dependency, CI or product-egress change. The owner asked for adversarial review of the
contract and plan at design time; both ran and are folded in.

## AI role

Agent: contract, rubric and plan (owner-approved, two owner changes: P2 deferral, fetch-once
cache); implementation (first version of the script and tests by Codex from the lead's
brief, cost column by a Sonnet worker, snippet arm and live runs by the lead); the review
stack (four lanes plus the lead's live-evidence review) and its 19 adopted fixes; these
records. Human: approvals, the Consensus billing statement, the arm-1b amendment, review
and merge.

## Review focus

Fairness of the comparison (same intent, cutoff, key, cap rule, formula; the three named
asymmetries in the `history.md` notes) · honesty of the cost label (page-priced, not
cap-priced; see verification § Review findings 3) · the cache path scoring identically to
the live path · scope (no pipeline or ground-truth change).

## Reviews run

**Status: the review stack ran on the baselines slice (commits through `36596c2`) and its
fixes are in. Amendment 2 (the fetchers, `d483c29`) landed after that review and is not yet
reviewed; the review cycle will run again on the whole branch before merge.**

Baselines-slice findings are in `verification.md` § Review findings (22 findings, 19
adopted, 3 declined with reasons).

- [x] Contract verifier (pinned Opus, read-only)
- [x] `/code-review` (medium)
- [x] `/security-review` (no findings)
- [x] Adversarial review (Codex, read-only brief)
- [x] `/simplify` — not run separately: `/code-review` ran the reuse, simplification and
  efficiency angles and their findings (shared `usd` formatter, `--since` before the item
  loop) were applied.

## Known gaps & deferred seams

The fetchers and the sample selection are unreviewed (see above). Their outputs are not yet in Langfuse: the CSVs are
inputs to the labelling pass and to `ground_truth/upload.py`, not part of this PR's numbers.

`docs/deferred.md` § Search recall baselines: P2 grey-literature keys with the raw Overton
arm (design at `37d496c`), the "swap" slice (with the cap-sized cost note), S3 upload of the
cache, a ranking-stability test. Unverified: the snippet arm's cutoff filter live (its
responses carry no dates); Consensus's 400 past 1,000 is a single-observation live fact.
Twelve superseded Langfuse runs (`2026-09-25-2815a59`) remain in the dataset and are printed
by `history.py`; delete them if that matters.

## Public safety

- [x] No secrets, credentials, or real/acquired source text in the diff or evidence (keys in
  `backend/.env` only; the cache with abstracts is git-ignored; key-substring audit clean).
- [x] Logs / traces / screenshots are public-safe (`history.md` holds means, counts and
  computed dollar figures; Langfuse traces carry the intent text, scores and metadata).
- [x] No approval-gated change snuck in unapproved (dev-time egress to search services only,
  not product egress).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
