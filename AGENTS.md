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
Implementation — task `015-live-search`.

Tasks `001-walking-skeleton` through `014-llm-screen-classify` are complete
(merged) — the EB chain runs end-to-end with live LLM screen/classify. The
active slice is the **second of the live-demo path** (014 LLM
screen+classify → **015 live search** → 016 live fetch/ingest → 017 demo
dress-rehearsal → eval slice): it wires **live HTTP OpenAlex and Overton
implementations** behind the existing `SearchBackend` seam (task 007), so
acquire runs on real search results instead of fixture replay. The fixture
backends stay the zero-egress defaults everywhere — `make verify` stays
deterministic and egress-free. The envelope mappings, dedup guards,
governance events and coverage record are already built and shared; this
slice adds only the live transport plus the carried v2-lesson requirements
(explicit timeouts everywhere · a real Overton rate limiter at 1 call/s ·
the OpenAlex query sanitizer on the production path · per-provider result
caps · keys env-only and never persisted). Gated change riding this slice:
**runtime egress** (search queries carrying the scope intent to OpenAlex +
Overton — the product's first non-LLM egress surface). No schema change,
no new dependency, no public-interface change (`run_harness` already takes
`search_backends`). Build per `docs/tasks/015-live-search/contract.md`.
Stay within the contract's scope and stop conditions; live fetch (016),
the Arm-B agentic search loop, the thin-base re-search trigger and all
other seams remain deferred (`docs/deferred.md`).

