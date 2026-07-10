# Agent protocol

- Use the commands in the `Makefile`.
- For non-trivial work, plan before editing.
- Write Google-style docstrings (`Args:`/`Returns:`/`Raises:` sections) for public modules,
  classes and functions; keep them concise. Trivial helpers and test functions need none.
- Use `docs/specs/` for product and system intent — **living intent, not golden**. If building shows
  a spec is wrong or improvable, flag it and flow the change back (`docs/specs/README`); don't
  silently obey it or silently deviate.
- Use `docs/tasks/<task-id>/` for per-task artefacts: `contract.md` (scope), `rubric.md`
  (completion criteria, when risk is medium or high), `verification.md` (evidence, or in the PR).
  `<task-id>` is `NNN-slug` (zero-padded, e.g. `001-example-slice`). Templates live in `docs/tasks/_templates/`.
- Agent-side model routing: the lead (Fable 5) plans, judges, synthesizes; delegate volume via the
  pinned agents in `.claude/agents/` — `deep-reasoner` (Opus) for reasoning offload, `fast-worker`
  (Sonnet) for mechanical sweeps and search — and Codex for the heterogeneous peer (review/rescue).
  **Prompt-bearing work (product prompts, judge rubrics, eval criteria) is lead-only — never
  delegated to a weaker model.** Details: `docs/agentic-ops/harness.md` § Agent-side model routing.
- Deterministic work (date math, parsing, counting, format conversion) runs as a script or command,
  not in latent space — if the same question twice must give the same answer, compute it.
- Do not change schema, auth, dependencies, CI, production config or public interfaces without approval.
- Never edit generated files or secrets.
- Touch only what the task requires.

# Current phase
Implementation — task `017-orchestrator`.

Tasks `001-walking-skeleton` through `016-live-fetch` are complete
(merged) — the EB chain runs end-to-end live: LLM screen/classify,
depth-graded search over OpenAlex + Overton, hardened live full-text
fetch/ingest, and synthesise minting chunk-cited claims over live
text. The active slice is the **fourth of the live-demo path**
(014 → 015 → 016 → **017 orchestrator/planning** → 018 demo
dress-rehearsal → eval slice), re-sequenced by the user 2026-07-10:
nothing in product code turns a user intent into a chain — chains
exist only as test-harness profiles in `skeleton.py`, and the demo's
planner is de-authorised throwaway. 017 lands the **thin v1
orchestrator**: a lead-authored LLM **planner** (intent →
depth-graded plan proposal, ask-only-on-shape, relative
lighter/deeper nudge), a deterministic **composer** (plan → chain
composition, fail-closed against the component registry, honouring
the ADR 0013 mandatory spine acquire(search) → screen → classify →
appraise → ingest(fetch) → synthesise with all other components
orchestrator-discretionary per depth gradation), and a serial
**driver** (topological walk over the existing components,
per-component commits, failure chaining off successful predecessors
only). Gated changes riding this slice: **runtime egress** (the
planner LLM call — one new lead-authored prompt surface) and one new
CLI entrypoint. Adjudicated at the contract 🛑: retrieval-boost
grammar v2 (recommendation: stays eval-gated, not in 017) and the
steering/durability posture (recommendation: Minimal-only steering +
per-component commits, no resume engine). `demo/RETRO.md` on branch
`demo-live-run` is an **anecdotal prior only**. Build per
`docs/tasks/017-orchestrator/contract.md`. Stay within the
contract's scope and stop conditions; the durability/resume engine,
check-in mediation surfaces, section-directive compile, component
progress protocol and all other seams remain deferred
(`docs/deferred.md`).

