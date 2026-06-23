# Rubric: 001-walking-skeleton

Completion criteria for this slice (Tier 4 — first scaffold + initial schema + command surface).
**Done only if every box holds** — otherwise it is in progress, not done.

## Core (from the template)

1. [ ] Implementation satisfies [contract.md](contract.md) — the spine is walked **once**, end to
       end, no more.
2. [ ] `make verify` passes (the targets are now wired to real tooling, not honest-red stubs);
       all declared deterministic tests pass. **No AI eval this slice.**
3. [ ] Every approval gate this slice **crosses was explicitly approved before the work began** —
       dependencies, schema/data-model, command surface, the inference seam. *(Inverted from the
       usual "nothing snuck in": this task's purpose is to cross gates, so the bar is prior
       sign-off, recorded.)*
4. [ ] No generated files or secrets edited by hand; no credentials committed.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded ([verification.md](verification.md) or PR).
7. [ ] Known gaps and deferred seams listed (gap → [docs/deferred.md](../../deferred.md)).

## Scaffold / walking-skeleton specific

8. [ ] **Seams are really seams.** Backend seams (egress, retrieval, real models) are present as
       **interfaces with stub/no-egress implementations**; non-backend seams (frontend, CI) are
       **registered deferrals** — not absent, not faked. **No real external egress and no real
       model call happened.**
9. [ ] **Event log is canonical and append-only**, and **separate from LangGraph execution
       checkpoints** (audit plane ≠ telemetry plane). The thread's events are read back in a
       **deterministic order via `(project_id, sequence)`** (not `occurred_at`).
10. [ ] **Plan is canonical; config compiles from it.** The one trivial plan compiles
        deterministically; an invalid config is a **caught error, never a silent run**.
11. [ ] **`produce-grounded-block` deterministic leg holds** — a real verbatim quote passes
        quote-presence; a **fabricated quote on a real (synthetic) source is a hard fail**.
12. [ ] **Model only what behaves** — the schema carries no inert label/type/flag (no sensitivity
        column, no `Library` class, no strand entity); each table earns its place in this slice.
13. [ ] **No premature build** — no real EB content component, no real retrieval/egress/models, no
        frontend, no CI. The skeleton stays the spine.
14. [ ] **Fixtures are synthetic** — no real uploaded/acquired source text in the repo or evidence.
15. [ ] **ADR recorded** for the stack/scaffold/schema choices introduced by this slice (Tier 4
        requirement per the contract's risk section).
16. [ ] **Run record lifecycle holds** — a run record is created, reaches `succeeded` or `failed`
        deterministically, and can be read back.
17. [ ] **Smoke command documented** — the PR records the exact command used for the manual
        end-to-end thread.
