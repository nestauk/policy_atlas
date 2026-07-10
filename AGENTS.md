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
Implementation — task `016-live-fetch`.

Tasks `001-walking-skeleton` through `015-live-search` are complete
(merged) — the EB chain runs end-to-end with live LLM screen/classify
and live depth-graded search over OpenAlex + Overton. The active slice
is the **third of the live-demo path** (014 LLM screen+classify → 015
live search → **016 live fetch/ingest** → 017 demo dress-rehearsal →
eval slice): it makes full-text ingestion **live** — a hardened live
`DocumentFetcher` behind the unchanged 008 seam, carrying every
pre-registered requirement from `docs/deferred.md` § Full-text
ingestion (explicit timeouts · SSRF/redirect policy for
provider-supplied URLs · per-host politeness + bounded-concurrency
prefetch · retry/backoff · magic-byte content-type sniffing · charset
handling · size caps + bounded buffering · paywall-detection signal
ladder · landing-page PDF-link discovery + DOI fallback · per-link
exception isolation: a fetcher raise becomes a reason-coded outcome,
never a component failure) — plus the **chain-composition rule**
(user call, 2026-07-09): the mandatory EB spine is acquire(search) →
screen → classify → appraise → ingest(fetch) → synthesise; all other
components are orchestrator-discretionary per depth gradation;
synthesise's substrate gate is untouched. The fixture fetcher stays
the zero-egress default — `make
verify` stays deterministic and egress-free. Gated change riding this
slice: **runtime egress** (live document fetching). `demo/RETRO.md`
§4 on branch `demo-live-run` is an **anecdotal prior only** (user
call: the demo was throwaway; no demo shape or number is design
authority) — it names which live hazards are real (paywalls, empty
bodies behind DOI redirects, parse failures on grey lit). Build per
`docs/tasks/016-live-fetch/contract.md`. Stay within the contract's
scope and stop conditions; docling/OCR parse tiers, multi-PDF Overton
assembly, cross-run fetch caching and all other seams remain deferred
(`docs/deferred.md`).

