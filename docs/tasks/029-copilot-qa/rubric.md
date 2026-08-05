# Rubric: 029-copilot-qa

The task is **done only if every box holds** — otherwise it is in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md) (all six strands, as approved).
2. [ ] `make verify` passes; the declared deterministic tests and the scoped live manual
       check pass (live-check notes in verification.md).
3. [ ] No approval-gated change snuck in unapproved — the schema and public-interface
       additions match strand 1/2 exactly; no new dependency; SSE vocabulary, auth, CI,
       prod config untouched.
4. [ ] No generated files or secrets edited by hand (OpenAPI/TS client regenerated, not
       patched).
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded ([verification.md](verification.md)).
7. [ ] Known gaps and deferred seams listed in [docs/deferred.md](../../deferred.md)
       (streaming · recall · promotion-to-block · shared-search conversion · watch
       executor feed · paused-run Q&A if cut).
8. [ ] Required Tier-3 review stack ran (contract verifier · code review · security lane ·
       adversarial · human deep review), findings adjudicated in verification.md.

Slice-specific:

9.  [ ] **Tool-set boundary holds**: the Q&A surface can construct no `search` and no
        write tool — proven by the allowlist test, not by reading.
10. [ ] **Tier honesty is deterministic**: a fabricated citation id is stripped and the
        tier downgraded; zero surviving citations forces the pure-LLM label; no answer
        renders without a tier chip from the locked vocabulary.
11. [ ] **Answers are ephemeral**: a Q&A turn writes only `qa_thread`/`qa_turn` rows —
        no artefact, finding, annotation or shared project-event writes.
12. [ ] **Transcript durability**: threads and turns survive API restart; `client_turn_id`
        retry returns the stored answer verbatim; pending/failed rows stay visibly honest.
13. [ ] **Fences hold under race**: `no_completed_run`, `run_active`,
        `qa_turn_in_progress`, `stale_turn` — barrier-tested like planning turns.
14. [ ] **Injection posture inherited**: every corpus-derived or user field entering the
        `qa_v1` prompt is sanitized, bounded, and labelled "(data, not instructions)".
15. [ ] **Ownership scoping**: cross-owner/unknown/archived thread or turn access is an
        indistinguishable 404.
16. [ ] `web-api.md` gains the Q&A section in the same change; prompt pins
        (`qa_v1`) and model env constant recorded; ADR Accepted.
