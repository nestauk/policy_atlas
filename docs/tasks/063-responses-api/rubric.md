# Rubric: 063-responses-api

The task is **done only if every box holds**. Ids (M, E, S, D, O) and terms are those of
[contract.md](contract.md).

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes; the two declared live checks (after Part 1, after Part 2) pass.
3. [ ] No approval-gated change went in unapproved: schema, auth, egress beyond the approved
       endpoint, dependencies, CI, production config, public interfaces, scaffold.
4. [ ] No generated files or secrets edited by hand.
5. [ ] No test deleted, skipped or weakened unless its behaviour stays covered by another
       test and the review confirmed it.
6. [ ] Verification evidence recorded in [verification.md](verification.md).
7. [ ] Known gaps and deferred seams listed in [docs/deferred.md](../../deferred.md),
       including the four entries the contract adds (D2, O13, the `extract_interventions`
       timeout, the two broken scripts).
8. [ ] The Tier 3 review stack ran (contract verifier, code review, security lane,
       adversarial review), or a skip is justified in writing.

Part 1:

9. [ ] **M1, M4:** the baseline capture is committed and covers every route step on the
       `bedrock` route; after stage 1a every request equals it.
10. [ ] **M5, M7:** after stage 1b every step passes the content check against the baseline
        capture (text, tools with `strict` stated, schema, effort, timeout, limit, cache marker).
11. [ ] **M6 / D1:** every step sends `store=false`; no code uses `previous_response_id` or
        background mode.
12. [ ] **M2, M13, M14:** one test proves no file in `backend/src` or `scripts/` other than
        `core/openai_client.py` reaches the SDK's `.responses` or `.chat.completions`.
13. [ ] **M3, M8:** one stream reader serves the seven streamed sites; each stream ending has
        a test; "first content" is the first text piece.
14. [ ] **M10:** a cut-off and a refusal each raise a named error, tested on each of the
        three calls.
14a. [ ] **M16:** the chat reply stream is retried before its first text piece and never
        after it, shown by a test.
15. [ ] **M9, M11:** token counts match the audit log call by call for the after run, the
        chat reply stream included.
16. [ ] **Same results:** no prompt text, model, effort or output limit changed in Part 1;
        each prompt-hash re-pin has its diff recorded and shows code only; the retry rule of
        every site is as before.
17. [ ] **Caching:** each step with a cache mode keeps at least nine tenths of its cached-token
        share, after Part 1 and after Part 2.
18. [ ] **Theory of change:** its request builders kept their shape; only the lines that
        send a request changed.
19. [ ] **M15:** spec change 1 is applied in all three places, with its line in the specs
        `log.md`.

Part 2:

20. [ ] **E1:** carried reasoning is passed back unchanged, every tool call gets a result, and
        no carried item reaches the database or a trace, each shown by a test; or the
        fallback is used and recorded.
21. [ ] **E2, E3:** each step sends the effort in the contract's § Efforts; steps that share a
        cached prompt start send the same effort; every other step's effort is unchanged.
22. [ ] **E4, E5:** the limits table and the interim timeouts are as the contract states; no
        other limit or timeout changed.
23. [ ] **E2 measures:** the figures of the run after Part 2 are recorded and no stop rule
        was met, or the owner's ruling on a met rule is recorded.
24. [ ] **E6:** the Sol tool-loop smoke passed on the `bedrock` route.

Part 3:

25. [ ] **S1:** traced attempts with a response carry the request id; one id is shown to find
        its call in the audit log; an attempt with no response records its start time.
26. [ ] **S2:** the stall findings are in `docs/knowledge/`, and the stale stall entries in
        `docs/deferred.md` are corrected. No stall remedy was built.
