# ADR 0050 — The Responses API as the one model interface, one module that sends, `store=false`, and carried reasoning

- **Status:** Accepted — 2026-11-20 (owner, task 063 plan gate).
- **Date:** 2026-11-20
- **Task:** [063-responses-api](../tasks/063-responses-api/contract.md) (contract revision 5.3
  and plan draft 2, both approved 2026-11-20)
- **Builds on:** [ADR 0041](0041-bedrock-inference-route-and-model-route-file.md) (the route
  file and the `bedrock` route) ·
  [ADR 0042](0042-gpt6-switch-per-call-site-routing-and-caching.md) (one route step for each
  call site; cache modes) ·
  [ADR 0043](0043-queued-ingest-document-store-sql-retrieval-step-timeouts.md) (a timeout
  and three attempts for each step) ·
  [ADR 0044](0044-live-activity-streamed-sections-one-copy-source.md) (streamed sections that
  share a cached prompt start with their gather turns).

## Context

Every model call that uses the OpenAI SDK (software development kit) went to the Chat
Completions endpoint. Two things made that a limit:

- On the current models, Chat Completions allows tools only with reasoning off (Terra) or
  not at all (Sol). The section writer picks evidence without reasoning, and the task 059
  analyst needs a tool loop that reasons.
- The code that sends a request was in two shapes: one shared helper for 62 route steps,
  and 20 request sites that built and sent their own.

Checks on 2026-11-20 on the `bedrock` route showed (figures in the task's contract):

- The Responses endpoint serves every request shape the app uses, on Luna, Terra and Sol.
- On Responses, Bedrock stores the input and output of a call for 30 days unless the call
  says `store=false`. The account setting for zero retention blocks the GPT-6 models and
  cannot be used.
- With `store=false`, the provider's reasoning comes back as an encrypted block that can be
  passed back on the next turn. Bedrock accepts it, and the prompt cache still reads in full.
- A change of reasoning effort between two requests with the same prompt start loses the
  cached discount.
- The endpoint does not change how often calls stall. Stalls were a delivery delay on
  laptop connections; the deployed apps did not show them.

## Decision

1. **One model interface.** Every OpenAI-SDK model call goes to the Responses endpoint.
   Chat Completions is removed, with no switch between the two. Embeddings and the Claude
   path are not part of this.
2. **One module sends.** `core/openai_client.py` is the only module that sends a model
   request. It offers a structured answer (`parse_structured`), a turn (`send_turn`) and a
   streamed turn (`stream_turn`). A test fails if any other file in `backend/src` or
   `scripts/` reaches the SDK's request calls.
3. **The call site keeps what is its own.** It reads its route step's model, effort and
   timeout, builds its messages and tools, applies the cache marker, opens its trace
   observation and owns its retry rule and fallback.
4. **The internal request language stays chat-style, for now.** Call sites build the
   request they built before; the module translates it at the edge. This is a stop-gap
   (§ Consequences).
5. **`store=false` on every call.** The module sets it. No code uses
   `previous_response_id` or background mode. This is the data-protection control; there is
   no account-level setting behind it.
6. **Carried reasoning in tool loops.** A tool turn returns the provider's output items.
   The loop holds them in memory for the life of that one loop and passes them back on the
   next turn, each tool call with one result. They are never written to the database, a
   trace or a log.
7. **Steps that share a cached prompt start run at the same effort.**
8. **Named errors.** An answer cut at the output limit and a refusal each raise a named
   error from all three calls. A site maps it to what it did before with such an answer.
9. **Request ids.** Each traced attempt that got a response records its request id, so a
   call can be found in AWS's audit log.

## Alternatives considered

### Move only the tool-using sites

- For: three call sites need the new endpoint; the rest gain nothing today.
- Against: two model interfaces to keep, test and reason about, and two data-handling
  stories. Once every call goes through one module, moving all of them costs little more
  than moving three.
- Rejected.

### The app's own request types now

- For: no vocabulary borrowed from an endpoint the app has left; features such as carried
  reasoning would not need a special entry in a message list.
- Against: about 40 hash-pinned prompt files would change in the same task, and the proof
  that the move changes nothing a model sees would be much weaker, because requests would
  be built differently and sent differently at once.
- Deferred, not rejected: [docs/deferred.md](../deferred.md), Model routes and model calls.

### Keep a switch back to Chat Completions

- For: a fast way back if the new endpoint misbehaves.
- Against: both paths would have to stay tested; the project replaces and deletes. Rolling
  back is reverting the pull request.
- Rejected (owner ruling).

### Rebuild tool history each turn, without the provider's reasoning

- For: no change to the tool loops; the probe showed Bedrock accepts it.
- Against: the model's reasoning is thrown away after each turn, so it thinks again from
  the start, and most of the gain from reasoning in a multi-step loop is lost.
- Rejected in favour of the standard pattern (decision 6).

### Account-level zero data retention

- Tried on 2026-11-20: Bedrock then refused every GPT-6 call. Reverted within minutes.
- Not available without a grant from AWS for these models. `store=false` is the control.

### A remedy for stalls (streaming watchdog, hedged requests)

- Not built: the deployed apps showed no stalls in 14 days of traces joined to AWS's audit
  log. The timeouts and three attempts of ADR 0043 stay.

## Consequences

- A change of endpoint or SDK now touches one module.
- A request cannot go out without `store=false` unless the one module is wrong, and a test
  checks every step's request.
- The app's internal request language follows the older endpoint. Each Responses feature
  that the old shape cannot express needs a special case in the module; carried reasoning
  is the first. The deferred entry says when to replace it with the app's own types.
- Carried reasoning changes the section writer's and chat's tool loops. A tool call the
  loop does not use now gets a short fixed result, which the model sees.
- Raising one step's effort can lose the cache of a step that shares its prompt start, so
  such steps change and roll back together.
- Even with `store=false`, AWS may keep traffic that its abuse checks flag for up to 30
  days. The DPIA (Data Protection Impact Assessment) notes record this.
- Tasks 059 and the 054 follow-up can build tool loops that reason, on Terra or Sol.
