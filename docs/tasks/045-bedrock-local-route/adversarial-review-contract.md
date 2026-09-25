# Contract-stage adversarial review: 045-bedrock-local-route

Reviewer: Codex (`codex-rescue`, read-only brief), 2026-09-25, job
`task-mugukl80-zyn15k`. Target: contract.md revision 3 and rubric.md as approved by the
owner the same day. Adjudicated by the lead the same day. Every adopted remedy is folded
into the contract, rubric and plan before the plan gate. None of the changes narrows or
widens the approved scope; they complete the specification, so the owner's approval
stands and the changes are flagged at the plan gate.

| # | Severity | Finding, in plain words | Adjudication |
|---|---|---|---|
| F1 | Blocker | The route file was placed at `backend/model_routes.toml`, but the built package and the Docker image only include `src/policy_atlas`. In a deployed container the loader would not find the file. | **Adopted.** The file moves to `backend/src/policy_atlas/model_routes.toml` and is read relative to the package, the same way the prompt `.txt` files are read today. No Docker change needed. Contract D3, Scope and plan P2 updated. |
| F2 | Blocker | The web API builds its own embedding backend in `api/deps.py` for chat retrieval, hard-coded to OpenAI. Only `runtime/agent.py` was in scope, so local chat would still embed queries with OpenAI under a Bedrock route. | **Adopted.** `api/deps.py` is in scope; `get_chat_embedding_backend` uses the same factory as the command line. A test covers the API path under each route. |
| F3 | Blocker | The Langfuse embedding wrapper only accepts `embed_texts(texts)`. Passing the new "query or document" argument through it would fail before Cohere is called, and live runs always go through the wrapper. | **Adopted.** The wrapper accepts and forwards the argument and records it in the trace. A test exercises the traced Cohere path. Contract D4 and plan Phase B updated. |
| F4 | Should fix | The Claude backend did not say which part of the Converse reply is the tool call, how exactly one is chosen, or what happens with several. | **Adopted.** Contract D5 now states the reply shape and the rule: exactly one tool-use block with the expected tool name, else fail. Tests for no block, several blocks, wrong tool name, non-object input and malformed usage. |
| F5 | Should fix | "Refused, not cut" for over-length Cohere input was not tied to a request setting or a test. | **Adopted.** The request sends `truncate = "NONE"`. Tests assert the full request body, an over-limit input error, a missing vector, and a malformed response body. |
| F6 | Should fix | The OpenAI library would still read `OPENAI_BASE_URL` from the environment, so a stray variable could change where a selected route sends requests. | **Adopted.** The route file names the address explicitly on every route, including OpenAI's own address for `openai-direct`, and the client always receives it from the route. The environment variable is never consulted. A test proves a stray value cannot alter a selected route. |
| F7 | Should fix | The deferred log still says the Bedrock move waits for the evaluation slice because it is a model-family swap. A cold planner would read that as "do not proceed". | **Adopted.** The deferred log update in this slice explicitly supersedes that entry: the OpenAI models keep their family on Bedrock, Claude gets the fresh prompt the spec requires, and the remaining quality decisions are named and deferred. |
| F8 | Should fix | Rubric item 7 asked the deferred log to say "embeddings still on OpenAI", which is no longer true. | **Adopted.** Reworded to "deployed vectors not yet re-embedded under the Cohere profile". |
| F9 | Should fix | Rubric items 9 and 21 claimed more than their tests prove ("byte-identical requests", "one-line swap") and mixed manual and mechanical evidence. | **Adopted with rewording.** Item 9 now requires the resolved model and address at each shared client seam to equal today's values, checked by tests, with the byte-identical claim resting on the diff showing no other request field changed. Item 21 separates the mechanical test (a route fixture edit changes only the model id sent) from the manual live evidence. |
| F10 | Minor | The contract said 15 modules; the sweep touches 16 (one has a pin, not a constant). An inventory table would make the sweep auditable. | **Adopted.** Count corrected to 16 and the contract points at the plan's inventory table, which lists module, constant, step name and default tier. |

**Verdict handling.** The reviewer judged the contract "a strong technical direction but
not yet a self-sufficient handoff" because of the three blockers. All ten remedies are
folded in. The owner's approval of the two gates and the two open questions is unchanged
by any of them.
