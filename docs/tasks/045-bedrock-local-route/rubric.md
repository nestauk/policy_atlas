# Rubric: 045-bedrock-local-route

The task is **done only if every box holds**. Otherwise it is in progress, not done.
Terms and need numbers (N1 to N8) are defined in [contract.md](contract.md). This file
does not restate them.

## Standard items

1. [ ] Implementation satisfies [contract.md](contract.md), including decisions D1 to D8
       and the owner's answers to O1 (frontier tier is Terra) and O2 (Claude covers query
       generation only).
2. [ ] `make verify` passes. The three live checks in the contract's § Acceptance checks
       ran inside their time budget and their results are recorded.
3. [ ] No approval-gated change went in unapproved. The two gates this slice hits, runtime
       egress and dependencies, carry the owner's written approval in the contract's Status
       line. No schema, auth, CI, production config, public interface or scaffold change.
4. [ ] No generated files or secrets edited by hand. No key, `.env` or trace in the diff.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded in [verification.md](verification.md).
7. [ ] Known gaps and deferred seams listed in [docs/deferred.md](../../deferred.md):
       Luna quality unmeasured, Claude tier choice unmeasured, Cohere grouping quality
       unmeasured, deployed vectors not yet re-embedded under the Cohere profile, staging
       key minting, Langfuse pricing by hand. The old "Bedrock routes" entry is superseded,
       not left standing.
8. [ ] The Tier 3 review stack ran: contract verifier, code review, security review,
       adversarial review of contract and plan, human deep review. Findings and how each
       was settled are in [verification.md](verification.md).

## Slice-specific items

9. [ ] **Unset means unchanged (N1, N2, N3).** With `POLICY_ATLAS_MODEL_ROUTE` unset,
       tests show every step's resolved model, the embedding profile and the client
       address at each shared client seam equal today's literal values. The PR diff shows
       no other request field changed, so requests are the same as before this slice.
10. [ ] **No literal model name left in code (N2).** A test imports all 25 constants in
        the plan's inventory under the default route and each equals its pre-045 value.
        A grep of `backend/src` for assignment lines matching `= "gpt-` or
        `= "text-embedding-` finds none (comments and docstrings are not assignments and
        are allowed to mention model names). The two former string comparisons on
        `gpt-5.6-terra` and the chat pin read the route's knob. The loader fails loud on
        an unknown route, unknown step, missing tier or malformed file, shown by tests.
        No `os.environ.get("POLICY_ATLAS_..._MODEL")` read remains in `backend/src`; a
        retired variable set in the environment changes nothing and is named in one
        warning, shown by a test.
11. [ ] **Claude fails loud (N4).** Tests show `ClaudeSearchGenerationBackend` raises
        `RuntimeError` on an empty reply and on JSON that does not match
        `SearchQueriesWire`. There is no silent fallback to OpenAI.
12. [ ] **Only the named step moved (N4, O2).** `reformulate` and `suggest` on the Claude
        backend reach the inner OpenAI backend, shown by a test.
13. [ ] **Usage and tracing hold for Claude (N4).** The Claude call records `TokenUsage`
        with prompt and completion counts, and its Langfuse trace carries the Claude model
        name and the new prompt version.
14. [ ] **Prompt text unchanged; pins honest (N2, N5).** `make prompt-guard` is green.
        `scripts/prompt_hashes.json` gains exactly one entry, the Claude prompt file. The
        three `.txt` prompt files and the synthesis prompt modules keep their hashes. The
        five prompt modules that lost a model constant are re-pinned, and
        `verification.md` shows each diff contains only the constant lines.
15. [ ] **Tests stay offline (N6).** `tests/conftest.py` scrubs `POLICY_ATLAS_MODEL_ROUTE`,
        `POLICY_ATLAS_MODEL_ROUTE_FILE`, `OPENAI_BASE_URL` and `AWS_BEARER_TOKEN_BEDROCK`,
        so a developer's `.env` cannot flip a test onto a live route. The socket-deny
        policy is untouched.
26. [ ] **Overlay file works and is bounded (N2).** Tests show an overlay replaces a route
        by name, adds a new route, cannot change `[steps]`, and a missing or malformed
        overlay raises. The live check's Sonnet and Opus calls ran through an overlay, not
        an edit to the committed file.
16. [ ] **Dependency change is exactly as approved (N7).** `boto3` is in the main list,
        `boto3-stubs[bedrock-runtime]` sits beside the existing stubs, no other package was
        added, and `make audit` was green after the lock change and again at exit, with
        both outputs in `verification.md`.
17. [ ] **A cold reader can set it up (N8).** `.env.example` names every new variable, says
        in one or two plain sentences what it does, and gives the working values for
        London. A developer who has only that file and a Bedrock key can reach step 2 of
        the live check.
18. [ ] **Nothing under `infra/` changed.** `git diff --stat` on the PR shows no file in
        that folder.
19. [ ] **Embeddings follow the route (N3).** Under `openai-direct` the OpenAI class and
        the old profile are used. Under `bedrock-local` the Cohere class and
        `cohere_embed_v4_1536_v1` are used, and a test shows a stored OpenAI vector is not
        returned by a reader under the new profile.
20. [ ] **Cohere batching and input types (N3).** Tests show 100 texts go out as batches of
        96 and 4, documents are sent as `search_document`, and the two query calls in
        `synthesis_tools.py` are sent as `search_query`.
21. [ ] **Claude tier is a one-line swap (N4).** Mechanical: a test loads a route fixture
        with a different `search_queries` model and shows the request differs only in the
        model id. Manual: the live check records one successful call on each of Haiku 4.5,
        Sonnet 5 and Opus 5.
24. [ ] **The web API follows the route too (N3, F2).** A test shows
        `api/deps.py:get_chat_embedding_backend` returns the OpenAI class under
        `openai-direct` and the Cohere class under `bedrock-local`.
25. [ ] **Claude reply shape is enforced (N4, F4).** Tests cover the six failure shapes in
        contract D5 and each raises `RuntimeError`.
23. [ ] **The route file is committed, shipped and readable (N2, N8).**
        `backend/src/policy_atlas/model_routes.toml` is in the PR with the `[steps]` table
        (23 steps), the three routes and a comment beside each non-obvious choice. A cold
        reader can tell from the file alone which model every step uses on every route.
        A test reads it through the loader's own path, the path the wheel ships. Every
        step name the code asks for appears in `[steps]`, shown by the default-route test.
22. [ ] **Nothing built from § Future work.** No key minting, no `infra/` change, no
        shared Converse layer, no deletion of old vectors, no change to live mode
        detection.
