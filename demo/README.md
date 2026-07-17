# Policy Atlas live demo (branch `demo-live-run` — never merges to dev)

A temporary, polished demo slice: the full EB chain running live (search → screen →
quality-check → read → findings → evidence base) behind a React front-end, with the
orchestrator narrating and checking in mid-run. Laissez-faire by agreement: no tests,
no contract docs; the API contract is `API.md`.

> **Rewired onto the real backend (2026-07-10, post-016/017 merge):** planning is the
> real 017 planner (`policy_atlas.planner`), execution is the real runner
> (`runner.run_plan` over `orchestration_plan.compose`, per-component commits,
> real steering check-ins with functional answers), full-text fetch is 016's
> `LiveDocumentFetcher`. The demo's own planner/chain-walker/fetcher are gone.
> Still demo-only glue, kept by explicit decision: LLM narration + check-in prose,
> the SSE bus + structlog→SSE bridge + `leg_directive` step-start shim, stage labels,
> and the gpt-5.5-synthesis / facet-cap-400 monkeypatches.
>
> **024 steering surface wired in (2026-07-17):** runs pass the real
> `OpenAIOrchestratorBackend` — the watch authors run-specific suggestions at the
> four lattice steer points, free-text steering compiles through the router behind
> the confirm gate (nothing applies unconfirmed), the steering mode can be changed
> mid-run, and the Decision Log renders the durable steering record from `event_log`.

## Run it

Prereqs: DB container up (`docker compose up -d db`), migrations applied, and in the
shell: `OPENAI_API_KEY`, `OVERTON_API_KEY` (+ Langfuse vars if you want traces).

```bash
# backend (port 8100)
uv run --group demo uvicorn demo.server.app:app --port 8100

# frontend (port 5173, proxies /api → 8100)
cd demo/frontend && npm install && npm run dev

# frontend against the in-browser mock (no backend, no keys — for UI polish)
cd demo/frontend && VITE_MOCK=1 npm run dev

# seed the pre-run fallback project (run the morning of the demo)
uv run --group demo python -m demo.server.seed \
  "What works to reduce childhood obesity in the UK?" \
  --name "Childhood obesity — what works" --band deeper
```

## Demo arc (~12 min)

1. **Landing** — the seeded, complete project sits beside a fresh one (3 min): open the
   fresh project, plan the question conversationally, watch the plan form, hit
   **Start the analysis**.
2. **Journey view** (6 min) — narrate over the live stream: search fan-out, screen ticks,
   the funnel filling, landscape charts sliding in; answer the check-in on stage.
3. **Evidence base** (3 min) — walk the seeded project's artefact: sections, citations,
   Detail panels (quotes, grounding, appraisal), the sources table with honest
   screened-out/paywalled states.

If the live run misbehaves, the seeded project carries the whole walk-through.

## Carry-back notes (design input for real slices — jot observations here)

- 016 live fetch: paywall rates, parse failures, timing per host, redirect behaviour…
- Web-app slice: read-model shapes that worked, SSE event grain, check-in UX…
