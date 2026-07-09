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
dress-rehearsal → eval slice): it makes acquire a **live, depth-graded
search capability** over OpenAlex + Overton (contract rev 2, user scope
call): live HTTP transport behind the 007 `SearchBackend` seam carrying
every v2-lesson requirement (timeouts · Overton 1 call/s limiter · query
sanitizers · per-depth caps · key hygiene · no citation floor), plus the
search capability itself — **rapid** = LLM multi-query fan-out with
SR/RCT variants; **deep** = the Arm-B agentic loop realised as
**acquire↔screen rounds** (contract rev 3: the loop's judge IS the
unmodified 014 screen — reformulation from graded screened exemplars
with token-bounded per-round inputs · citation snowballing ·
suggestion grounding · fixed arm allocation with a diversity reserve ·
stopping on real confident-relevant counts and discovery rate, round
cap 3), all budget-governed; the thin-base re-search behaviour lives
in the loop's stopping rule (rapid-thin runs escalate to one bounded
deep continuation); pagination; `scope_filters`; the backend-scope
field. Fixture backends stay the zero-egress defaults — `make verify`
stays deterministic and egress-free; acquire itself never writes
screening rows (one relevance surface). Gated changes riding this
slice: **runtime egress** (transport + three generation surfaces,
`search_queries_v1` · `search_reformulate_v1` · `search_suggest_v1`,
the 11th–13th product prompts, plus the in-loop `screen_v1` call-volume
change) · **schema** (one `ck_scov_stop_condition` CHECK widening) ·
**public interface** (`search_backend_scope` Plan/Config field). Build
per
`docs/tasks/015-live-search/contract.md`. Stay within the contract's
scope and stop conditions; live fetch (016), Semantic Scholar, Overton
cross-backend snowballing, blend ranking and all other seams remain
deferred (`docs/deferred.md`).

