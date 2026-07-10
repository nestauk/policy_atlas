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
Implementation — task `018-dress-rehearsal`.

Tasks `001-walking-skeleton` through `017-orchestrator` are complete
(merged) — the EB chain runs end-to-end live behind the thin v1
orchestrator: intent → planner conversation → depth-graded plan →
spine-by-construction composition → serial EB capability-runner with
steering. The active slice is the **fifth of the live-demo path**
(014 → 015 → 016 → 017 → **018 dress-rehearsal** → eval slice) and
the repo's **first eval-type slice**: prompt-bearing iteration judged
qualitatively on outputs, not a single code build — the contract's
§ How this slice runs records where task-cycle conventions are
deliberately adapted. 018 lands: (A) code riders — model refresh to
gpt-5.4-mini (+ a provider-neutral reasoning-effort knob;
classify @ xhigh), telemetry sweep (Langfuse sessions, usage-return,
durable per-component wall-clock + counts), standard-depth regrade
(select/extract/group become deep-only; bands re-measured),
planner-history fix (native message arrays, provider-neutral —
Bedrock is infra-ready and queued post-eval), OpenAlex country
filter, and the direction-vocabulary rename
positive/negative → increase/decrease (the one approved schema
migration); (B) the **synthesis output-shape v2** (ADR due,
supersedes 013's claims-are-the-prose emission): authored prose
answering the intent with typed claims anchored as char-offset span
annotations *into* the prose, every grounding invariant preserved,
plus the grounded **conclusion-block front door** and widened
judge/writer envelopes; (C) a **refine-replay loop** (baseline
capture → per-surface replay on recorded projects → before/after
evidence; anti-overfit pins via the v2 question taxonomy) ending in
a live **dress rehearsal** on a Nesta-mission question rendered on
the updated `demo-live-run` surface (throwaway — the frontend
scaffold gate stays untouched). Build per
`docs/tasks/018-dress-rehearsal/contract.md`; stay within its scope
and stop conditions. Bedrock migration, the screen-stage rename,
RAG-quick-run findings, direct plan editing and all other seams
remain deferred (`docs/deferred.md`).

