# scripts/scratchpad — search verification tooling

This directory is just for scrappy work for testing small pieces of the evidence base pipeline (or anything else).

Notebooks in here should be deleted before merging.

**Everything here spends real money and writes real rows.** All three tools
call the live provider APIs and the live LLMs, and write to whatever
`DATABASE_URL` in the repo `.env` points at (normally your dev database, which
must be at alembic head). Each prints the `project_id` it created so you can
find or delete the rows afterwards.

## Setup

You need these keys in the root-level `.env`: `OPENALEX_API_KEY`, `OVERTON_API_KEY`,
`OPENAI_API_KEY`.

## The search pipeline

The pipeline for one round of search should be:
- create fan-out queries from the "intent"; run all of these to completion (i.e. no cap on how many records are returned by OpenAlex or Overton)
- merge the results within a source (OpenAlex or Overton) by rank-interleaving (because the relevance score is not calibrated across queries, but results come back in order of relevance, so we use their ordering to merge them and make sure we get the most relevant)
- deduplicate
- take the top N: 50 for rapid search, 100 for standard, 200 for deep
- save and embed these
- screen for relevance

This process can be repeated
- with reformulation, for 1 more round, in standard search
- with reformulation, diversity, citation snowballing, and LLM suggestions, for 2 more rounds, in deep search

The loop stops early only if a round's yield collapses
(fewer than 1 new confidently-relevant document per 50 screened).

## The files

### `run_live_deep.py` — one live run through the real production path

Drives the runner (`run_plan`) exactly the way the API does, then reads the
event log back and prints per round: which search arms fired and what they
returned, documents screened, new confidently-relevant documents, and why the
loop stopped. This is the tool that answers "does multi-round search actually
work against real providers?"

```
uv run --project backend python scripts/scratchpad/run_live_deep.py                 # deep
uv run --project backend python scripts/scratchpad/run_live_deep.py --depth standard
uv run --project backend python scripts/scratchpad/run_live_deep.py --intent "..."
```

**Cost:** a deep run's worst case is 3 rounds × up to 400 documents, each
screened 3 times — roughly 3,600 small-model calls plus embeddings and a
handful of query-generation calls. Expect tens of minutes (Overton enforces a
1.2 s gap between requests). The script prints the estimate and asks before
running; `--yes` skips the prompt.

**What to look for in the output:**

- **Both providers show calls in every round.** A provider at zero calls was
  the historical failure (the old wall clock silently skipped the whole
  Overton leg).
- **Deep reaches round 3** (or stops earlier with `short_circuit`, which is
  legitimate — it means a round stopped paying for itself).
- **Snowball / suggest rows appear at rounds 2–3.** If they never fire, round
  1 produced no confidently-relevant OpenAlex documents to seed them — a
  finding about screening yield, not a bug in the arms.
- **The final round's stop condition** — `budget_exhausted` (ran to the round
  cap), `short_circuit` (yield collapsed), or `re_searched_still_thin`
  (finished with fewer than 8 confidently-relevant documents — the "we looked
  and there isn't much out there" signal).

### `search_caps_by_depth.ipynb` — the acquisition funnel, round 1 only

Runs the same question at all three depths (round-1 fan-out only, no arms) and
shows the funnel per stage: fetched → unusable → duplicate → over cap → saved.
Use it to see how the per-round caps behave and how much the providers
actually return. Includes a repeat-run section (N runs, median/IQR) for
checking stability. Cheap: no screening, a few query-generation calls.

### `search_rounds_and_arms.ipynb` — the round loop, step by step

Steps through what `run_live_deep.py` does in one shot, but cell by cell —
acquire round 1, screen it, evaluate the stop decision, acquire round 2 (watch
the arms fire), and so on — so each stage's inputs and outputs are
inspectable. It mirrors the runner's round gate rather than invoking the
runner; for the production path itself, use `run_live_deep.py`.
**This one screens between rounds, so it costs real screening money** — it
prints the estimate up front.
