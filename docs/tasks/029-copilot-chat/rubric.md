# Rubric: 029-copilot-chat

The task is **done only if every box holds** — otherwise it is in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md) (all seven strands, as approved).
2. [ ] `make verify` passes; the declared deterministic tests and the scoped live manual
       check pass (live-check notes in verification.md).
3. [ ] No approval-gated change snuck in unapproved — schema and public-interface
       additions match strands 1/3 exactly; no new dependency; SSE vocabulary, auth, CI,
       prod config untouched; planning endpoints keep their paths.
4. [ ] No generated files or secrets edited by hand (OpenAPI/TS client regenerated, not
       patched).
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded ([verification.md](verification.md)), including
       migration/backfill evidence and the rollback rehearsal note (Tier 4).
7. [ ] Known gaps and deferred seams listed in [docs/deferred.md](../../deferred.md)
       (streaming · recall/rationale carry · promotion-to-block · shared-search
       conversion · watch executor feed · multi-artefact widening · paused-run chats if
       cut).
8. [ ] Required Tier-4 review stack ran (contract verifier · code review · security lane ·
       adversarial · human deep review), findings adjudicated in verification.md.

Slice-specific:

9.  [ ] **Tool-set boundary holds**: the chat surface can construct no `search` and no
        write tool — proven by the allowlist test, not by reading.
10. [ ] **Tier honesty is deterministic, on durable-id citations**: every `citations[]`
        entry resolves to an id the tool loop returned this turn (fabricated or
        out-of-range → stripped + tier downgraded); inline `[n]` markers index the
        citations array and are stripped with a stripped citation; the persisted
        display payload is compacted (surviving citations numbered by first
        appearance, uncited entries never displayed); zero surviving citations forces
        the pure-LLM label; no answer renders without a tier chip from the locked
        vocabulary; marker/hover/footer all resolve only to surviving citations.
11. [ ] **Chats are ephemeral and read-only**: a chat turn writes only `conversation`/
        `chat_turn` rows — no artefact, finding, annotation, plan or shared
        project-event writes; the evidence-not-held hand-off is a link, never a plan
        mutation.
12. [ ] **Unified-model invariants hold**: at most one active planning conversation per
        project (under race); a completed run closes its planning conversation; "Run the
        analysis again" seeds a new one from the executed plan; planner rehydration
        reads only the active conversation's turns.
13. [ ] **Lineage chain walkable**: conversation → plan → run → artefact resolves on a
        new run end-to-end; legacy rows carry honest `NULL`s, never fabricated links.
14. [ ] **Backfill honesty**: every pre-029 project ends the migration with exactly one
        legacy planning conversation whose status matches its real plan/run state
        (fixture cases: no-run · completed-run · mid-replan); rollback rehearsed.
15. [ ] **Transcript durability**: conversations and turns survive API restart;
        `client_turn_id` retry returns the stored answer verbatim; pending/failed rows
        stay visibly honest.
16. [ ] **Fences hold under race**: `no_completed_run`, `run_active`,
        `chat_turn_in_progress`, `stale_turn` — barrier-tested like planning turns.
17. [ ] **Injection posture inherited**: every corpus-derived or user field entering the
        `chat_v1` prompt is sanitized, bounded, and labelled "(data, not instructions)".
18. [ ] **Ownership scoping**: cross-owner/unknown/archived conversation or turn access
        is an indistinguishable 404.
19. [ ] `web-api.md` gains the Conversations section in the same change; prompt pin
        (`chat_v1`) and model env constant recorded; ADR Accepted; no user-facing or
        code-level "qa" naming anywhere in the slice.
20. [ ] **Streaming honesty (rev 2.2/2.3)**: typed progress events (user-facing tool
        labels) + text deltas + exactly one terminal validated payload per turn; the
        persisted answer equals the streamed prose; the wire shape is provider-neutral
        (no partial-JSON passthrough); mid-stream failure leaves an honest failed row
        and the client recovers; client cancel cleans up the generator and leaves an
        honest terminal turn state, never a silent pending; an idempotent retry of a
        completed turn replays the stored answer without re-generation; the project
        SSE vocabulary is untouched.
21. [ ] **Cross-chat isolation (rev 2.3)**: concurrent turns in different chats of one
        project share no turn state (register, tool budgets, stream buffers) — proven
        by the concurrency test, not by reading.
