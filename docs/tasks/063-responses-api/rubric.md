# Rubric: 063-responses-api

The task is **done only if every box holds**. Ids (M, E, S, D, O) and terms are those of
[contract.md](contract.md).

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes; the declared live checks pass.
3. [ ] No approval-gated change went in unapproved: schema, auth, egress beyond the approved
       endpoint, dependencies, CI, production config, public interfaces, scaffold.
4. [ ] No generated files or secrets edited by hand.
5. [ ] No test deleted, skipped or weakened unless its behaviour stays covered by another
       test and the review confirmed it.
6. [ ] Verification evidence recorded in [verification.md](verification.md).
7. [ ] Known gaps and deferred seams listed in [docs/deferred.md](../../deferred.md).
8. [ ] The Tier 3 review stack ran (contract verifier, code review, security lane,
       adversarial review), or a skip is justified in writing; findings in
       [verification.md](verification.md).

Slice-specific:

9. [ ] **M11:** no `chat.completions` call remains in `backend/src` or `scripts/`, and no
       switch between endpoints exists.
10. [ ] **M6 / D1:** every one of the 74 route steps sends `store=false`, proven by one test
        over the golden request fixture; no code uses `previous_response_id`.
11. [ ] **Same results (Part 1):** no prompt text, model, effort or output limit changed in
        Part 1; each prompt-hash re-pin has its diff recorded and shows code only.
12. [ ] **M5, M8:** token and cost totals for one recorded run match the provider's
        audit-log totals for the same calls, the chat prose stream included.
13. [ ] **Caching:** the cached-token share for each step on the after run is not below the
        before run beyond run-to-run noise, with both figures shown.
14. [ ] **M7:** an answer cut at the output limit and a refusal each raise a named error;
        one test for each.
15. [ ] **E2:** each step in the contract's § Efforts sends the effort ruled there (key
        findings `medium`, the rest `low`), with its latency and cost before and after read
        from the live runs; every other step's effort is unchanged.
16. [ ] **E3:** the Sol tool-loop smoke passed on the `bedrock` route.
17. [ ] **S1:** traced attempts carry the request id, and one id is shown to find its call in
        AWS's audit log.
18. [ ] **S2:** the stall findings are in `docs/knowledge/`, and the stale stall entries in
        `docs/deferred.md` are corrected.
19. [ ] No stall remedy was built (O8), and no timeout changed.
20. [ ] **Theory of change:** only the endpoint changed for its steps, unless the colleague
        asked for more (O9), with that request recorded.
21. [ ] **M12:** `core/openai_client.py` is the only module in `backend/src` that calls the
        SDK, proven by a test; each call site kept its own stream handling, retry rule and
        fallback.
22. [ ] **D2:** `verification.md` states whether the account's zero-data-retention setting
        was in place at the production deploy (an owner action; it does not block the task).
23. [ ] **M13:** spec change 1 is applied, with its line in the specs `log.md`.
