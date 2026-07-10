# Demo build retro — carry-back for the real front-end / web-app slice

> **2026-07-10 addendum (post-016/017 rewire):** this branch has since been rebuilt on
> the merged real backend — the hand-rolled planner/driver/fetcher this retro describes
> are gone (`demo/server` now wraps `planner`, `orchestration_plan.compose`,
> `runner.run_plan`, `steering`, `fetch_live`), check-ins use the real steering
> vocabulary and are functional, and the plan shape is the real `OrchestrationPlan`.
> §§1–3's descriptions of the demo's own orchestration are therefore historical;
> the product decisions (§2), contract-discipline lessons (§3) and live-run numbers
> (§4) still stand. Narration + check-in prose + the model/cap monkeypatches were
> kept as demo-only glue by explicit owner decision.

**Audience:** the implementation agent of the future web-app / front-end task-cycle slice
(and the 016 live-fetch, eval, and orchestrator slices, each of which gets a section).
**Status of this branch (`demo-live-run`):** throwaway, never merges; everything here is
evidence, not code to reuse verbatim. Built 2026-07-09 in one long session with the
product owner iterating live against real runs. The four `src/policy_atlas/` edits on
this branch (search query/result log lines, extraction prompt rules, synthesis voice
rules) are candidates to carry forward deliberately — see § Prompt learnings.

## 1. What exists

- `demo/server/` — FastAPI app wrapping the real chain: `orchestrator.py` (planning
  conversation + narration + check-ins, gpt-5.5, structured plan output incl. a derived
  project `title`), `driver.py` (fixed chain walker: per-stage transactions, depth
  gating, failure fallbacks, structlog→SSE bridge with an allowlist translator, module
  patches: SYNTHESIS_MODEL→gpt-5.5, FACET_VALUE_CAP→400 in BOTH defining and consuming
  modules), `readmodels.py` (12 read models over the real schema), `fetcher.py`
  (parallel demo DocumentFetcher), `app.py` (REST + SSE), `seed.py`.
- `demo/frontend/` — React 18 + TS strict + Tailwind + recharts. ~15 files, written
  from scratch in one pass after three earlier delegated passes accumulated too many
  seams (owner verdict: rewrite > patch). `VITE_MOCK=1` swaps in an in-browser mock
  implementing the SAME `DemoApi` interface with a scripted 90s journey.
- `demo/API.md` — the API/SSE contract. Still accurate; read it first.

## 2. Product decisions validated with the CEO-proxy user (keep these)

- **Terminology is locked** (fought over repeatedly): "Start the analysis" (never
  Build/Run), "Screening" (NOT "sift" — was renamed twice), "quality-check",
  "shortlist", "read in full", "pull out findings", "evidence base". Component names
  (screen/classify/…) never reach the UI; stage labels come from the server.
- **One orchestrator, one thread, two postures**: the same agent (same history) plans
  conversationally, then narrates the run and mediates check-ins. Execution itself is a
  fixed driver (plan-time authority — matches execution-orchestration spec).
- **Chat shrinks when analysis starts** (55/45 → 35/65 animated): focus follows density.
- **Right pane**: strictly one card per line; execution-order stage timeline (plan
  steps only scaffold PENDING rows); outcome-first when complete (DONE card leads);
  sticky section mini-nav; a "View plan ▾" disclosure keeps the agreed plan visible
  post-start; `scrollbar-gutter: stable` (width jitter was user-visible).
- **The annotation layer renders IN the prose**: claims are typed spans
  (citation/gap/reasoning/pattern/theme) with char offsets into block text —
  `addressable_unit` supports this natively. Gap sentences get amber underline + `gap`
  chip; NO separate callout cards; NO per-block "Detail" footer (units carry it all).
- **Hover → click ladder everywhere**: citation hover = provenance tooltip; click =
  quote amber-highlighted inside prev/current/next chunk context
  (`/chunks/{id}/context`; `chunk.sequence` makes neighbours trivial). Source names
  are clickable everywhere → one shared dossier slide-over (status ladder, screening
  confidence/basis/stage, quality labels, abstract, DOI/publisher/cited-by/FWCI, tags
  grouped by asserter, citing claims, findings from that source).
- **Labels, not numbers**: appraisal shows SCORE_LABELS (Weak…Very strong), never 1–5.
- **Decision log is user-facing**: projection over the real event_log with an ALLOWLIST
  of friendly-labelled numbers per entry (never raw payload keys/ids), plus the exact
  search query strings (currently merged from the in-memory bus — a real slice should
  persist queries durably, e.g. on the coverage record or an event).
- **Data-driven surfaces**: the Findings tab exists only when findings exist; landscape
  cards render only when their data exists; a card must hide rather than show fake or
  empty content. All landscape distributions are over the SCREENED-IN set only
  (characterise loads `status == "relevant"` — verified); only the funnel spans the
  full flow. Mock data must sum consistently across every surface (a 214-vs-74
  mismatch was caught by the owner instantly).
- **Publication country** is derivable read-time (OpenAlex
  `primary_location.source.country_code`, Overton `source.country`) but MUST be
  labelled "where sources were published, not where the studies were conducted"
  (study geography is a recorded deferred extraction field). The provider tag layer is
  too dirty for a headline chart (owner removed it); tags belong in the per-source
  dossier, grouped by asserter, never merged across asserters.
- **Coverage honesty needs one sentence**: stop condition and adequacy verdict rendered
  as separate lines confused the owner ("found enough" beside "judged inadequate");
  compose them server-side into one sentence.
- **Motion budget**: count-up numbers, growing bars, breathing progress segment, rising
  cards, amber check-in glow — every animation marks data arriving; respect
  prefers-reduced-motion. This register landed well.

## 3. Contract discipline (the recurring failure class)

Most UI bugs in this build were **mock/live contract divergence**: live `/plan` omitted
`steps` → white-screen crash; mock facet names didn't match live grouping vocabulary
(`intervention`) → filters missing live; `year_range` string vs `{min,max}`. Rules that
fixed it: the mock implements the SAME TypeScript interface as the live client; mock
fixture shapes mirror live vocabulary exactly; the front-end never trusts optional
fields (`plan?.steps ?? []`). A real slice should generate types from one schema.

Also: SSE backlog replay is the resilience model — on (re)connect the server replays
everything, the store rebuilds idempotently from events alone (chat turns are re-emitted
on the bus as `user.message`/`narration`, with text-dedup against local copies). This
survived server restarts and tab navigation. In-memory bus = history lost on restart
(fine for demo; real slice needs durable events — mostly already true via event_log).

## 4. Live-run observations (real numbers, feed the eval slice)

- **characterise discovery is the #1 live wobbler**: failed twice-in-a-row (2 attempts)
  on a 47-doc corpus → whole tail collapsed. Driver now retries the stage once and
  synthesise skips honestly on zero substrate. The rejection *reason* is still only in
  Langfuse (`_discover_themes` discards validator detail — recorded in deferred.md).
- **FACET_VALUE_CAP=150 binds at real scale**: 25 selected docs → 427 findings → 280
  distinct facet values. Demo cap 400 worked (19 intervention groups). NOTE the
  monkeypatch gotcha: `group.py` imports the constant by value — patch both modules.
- **Failure chaining**: a failed stage must never feed its run id downstream
  (synthesise `missing_referenced_row`). Driver pattern: stages chain only off
  successful predecessors; synthesise takes the deepest successful reference.
- **Extraction quality on live grey lit is the weakest link** (mini model): vague
  labels ("The strategic plan" → "quality"), unexpanded acronyms ("SCOs → MCS"),
  aspirational communiqué boilerplate extracted as findings. Prompt rules added
  (self-contained naming, expand acronyms, no hortatory statements, concrete
  outcomes) — NOT yet validated by a post-fix run. A findings quality gate/judge is
  the next lever if rules aren't enough.
- **Synthesis voice**: the grounding-rigorous section prompt had no prose guidance →
  claims read as tool returns ("the computed direction spread is 7 positive…"), and
  pattern claims recited pipeline statuses (fetch_failed counts) into the artefact.
  Voice rules added: banned internal vocabulary, analyst-style number restatement,
  takeaway-first claim ordering, one citation per source per claim, patterns describe
  evidence never processing. NOT yet validated by a post-fix run.
- **References/titles**: full-text snapshots carry no title metadata — reference
  entries must resolve display metadata via the owning source's ENVELOPE snapshot
  (read-model fix; otherwise references render as bare URLs, years empty).
- **Fetch reality (for 016)**: one deep run: 222 fetch attempts, 81 ingested, ~39
  fetch_failed + 22 parse_failed; reasons observed: paywall (Lancet/Elsevier), empty
  bodies behind DOI redirects. Prefetch-parallel (10-way) + serial cache-hit ingest
  worked well. OpenAlex rate-limits back-to-back runs (cache-before-throttle note).
- **Timing (live, gpt-5-mini chain)**: quick ≈ 8–12 min bottlenecked by screening
  (~900 consensus calls for ~214 docs) and characterise; deep run of the
  finance-ministries question ≈ 95 min end-to-end, extraction ≈ 35 min for 25 docs.
  For a 12-min demo: pre-run deep project + live QUICK run.
- **Depth must gate the chain**: quick = acquire→screen→classify→appraise→
  characterise→synthesise (envelope basis, plan says "headline evidence base — from
  titles and abstracts"). The real orchestrator should compile this (the tool-wide
  depth-gradation seam in deferred.md).
- **Liveness gap in components**: nothing emits user-grade progress (only token-usage
  telemetry). Demo added 4 log lines in `search_live.py` (query issued / results per
  backend) and proxied `.usage` ticks into generic plain-English activity with
  client-side ×N collapse (count at ingest, not display — buffer caps under-count).
  A real slice wants a designed component-progress protocol instead.
- **Model routing observed**: screen (mini ×3) fine; classify fine; characterise
  discovery + extraction wobble on mini; synthesis needed gpt-5.5 to be readable.
  Judge stayed mini (owner call).

## 5. Known rough edges left on this branch

- The obesity quick-run project sits failed-at-characterise (pre-retry-fix); dud
  "Untitled project" cards litter the landing (no delete endpoint; sidecar
  `demo/server/projects.json` is the project registry).
- Landing "Paused — waiting on your input" state exists but nothing feeds it
  (needs a paused signal on `/projects`).
- One analysis at a time (server 409s); bus history in-memory only.
- Prompt fixes (extraction rules, synthesis voice) unvalidated by a fresh run.
- Branch uncommitted at time of writing.

## 6. Demo-day quickstart

See `demo/README.md`. Backend `uv run --env-file .env --group demo uvicorn
demo.server.app:app --port 8100`; frontend `npm run dev -- --port 5180` (live) or
`VITE_MOCK=1 …` (rehearsal). Seed the fallback deep project the morning of. Langfuse
has full traces of every live run this session.
