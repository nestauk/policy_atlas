# Bedrock integration: what AWS recommends, what we built, what the probes showed

Written at the task 057 review (2026-11-03) at the owner's request, after the review stack
found 1 to 14% of model-call attempts hanging to their timeout on the `bedrock` route. Four
sourced research notes are in [research/](research/) (every claim with its URL; read on
2026-11-03); the probe results are in `verification.md` § Review findings and § Stall
probes 2 and 4. Decisions already made by the owner: production moves to the `bedrock`
route; the GPT-6 models exist only as `global.` inference profiles, so the model ids stay.

## 1. What the probes established

| probe | question | result |
|---|---|---|
| 3 (burst at width 48) | are the 15 s cuts on the wide steps queueing at the endpoint? | no: the server wait is the same at width 12 and 48; the extra time is the client opening 48 TLS connections at once |
| 2 (keep-alive off vs on, inside the pipeline, 4 runs) | is a stale pooled connection the cause? | no: the hang rate did not fall with every request on a fresh connection (0.39% against 0.25%) |
| 4 (90 serial judge-sized calls, 3 arms) | does the bare OpenAI SDK, outside our code, hang at our rate? | yes: 3 of 30 on the plain SDK with its defaults, 13 of 90 across arms (14%), the arms indistinguishable (p = 0.53); 4 of the 13 hung attempts returned on their own after 126 to 246 s |

So the hangs are the provider's or the path's, not ours: no threads, no pool, no schema, no
cache mode, no wrapper is needed to reproduce them, and some of them are very slow answers
rather than lost ones. The rate moves with the hour (probe 2's runs saw 0.3%, round (h) saw
0.8% overall and 7% on the long steps) and with how long a call is in flight.

## 2. What AWS documents (the research notes, condensed)

- **No server-side timeout, no maximum duration** is documented for the OpenAI-compatible
  Chat Completions endpoint; AWS says only that "requests can be queued" under high demand.
  Capacity trouble is documented as 503 / 529 errors, never as a silent stall.
  ([endpoint note](research/bedrock-openai-endpoint.md) § 1, 8;
  [hung-requests note](research/hung-requests-aws.md) § 3.)
- **The one documented silent-hang cause** is the 350 s idle drop at NAT gateways, VPC
  interface endpoints and Network Load Balancers on a pooled connection; the fix is TCP
  keep-alive in the client *and* an OS keep-alive under 350 s, and AWS names ECS behind a
  NAT as the case. The OpenAI SDK's default transport has no TCP keep-alive and its
  maintainers declined to add it (openai-python #3269). **It cannot be our cause:** the SDK's
  pool closes a connection idle for 5 s, so no connection of ours is ever idle for 350 s,
  and the hangs happen on the laptop with no NAT.
  ([hung-requests note](research/hung-requests-aws.md) § 1, 4.)
- **Retries and timeouts.** AWS's guidance is bounded retries with exponential backoff and
  jitter on 429 / 503 / 529, honouring `Retry-After`, an example budget of six attempts, and
  timeouts "no shorter than a legitimate inference" because a short timeout "can cause
  avoidable retries and duplicate work". The boto3 guidance (`tcp_keepalive`, retry modes,
  `max_pool_connections`) does not reach calls made through the OpenAI SDK.
  ([throughput note](research/bedrock-throughput-resilience.md) § 2, 3.)
- **Quotas.** On `bedrock-runtime` a model's quota is shared across Chat Completions,
  Converse and InvokeModel; the `global.` profiles have their own quota lines, managed in
  the source Region. At admission a request reserves **input + `max_tokens`**, and output
  tokens count 10× against tokens per minute. Default global TPM: GPT-6 Luna 4,000,000, Sol
  2,000,000; a quota hit is a fast 429, not a hang. Embedding models are throttled by
  requests per minute (as the build found).
  ([endpoint note](research/bedrock-openai-endpoint.md) § 8; [throughput note](research/bedrock-throughput-resilience.md) § 1, 10.)
- **Global routing.** `global.` profiles route "to supported commercial AWS Regions
  worldwide"; AWS does not document how the Region is chosen or what latency it adds;
  CloudTrail's `additionalEventData.inferenceRegion` says where each request ran.
  ([endpoint note](research/bedrock-openai-endpoint.md) § 7.)
- **Observability.** Model invocation logging covers the OpenAI-compatible endpoint on
  `bedrock-runtime` (full request and response bodies unless text delivery is off; storage
  cost only); the `AWS/Bedrock` metrics (`Invocations`, `InvocationLatency`,
  `Invocation*Errors`, `InvocationThrottles`, per model id) are free at one-minute grain;
  the request id comes back in the response headers. Not documented: whether a request the
  client cut appears in the invocation log.
  ([observability note](research/bedrock-observability.md) § 1 to 4.)
- **Authentication.** Long-term Bedrock API keys are "for exploration only"; production
  guidance is short-term keys (up to 12 h, from `aws-bedrock-token-generator`) or SigV4.
  ([endpoint note](research/bedrock-openai-endpoint.md) § 12.)
- **Precedent.** The closest reported pattern is openai-python #3054: 8 to 28% of
  concurrent requests hanging on OpenAI direct, fixed server-side. Nothing equivalent is
  reported for Bedrock.

## 3. Recommendations, ranked, against what we have

1. **Keep the per-step timeouts and the traced attempts; they are the documented shape.**
   Bounded retries on the same error classes, `Retry-After` honoured, and each attempt
   visible. AWS's example budget is six attempts; our three is conservative, which supports
   keeping three on every step (owner ruling 2) and arguing for more, not fewer, on the
   once-per-component steps. The one thing AWS asks for that we lack is jitter on the wait
   between attempts; for hangs it does not matter (the retry answers in seconds), for 429
   waves it would. Small, deferred.
2. **Keep cutting slow calls rather than waiting.** AWS warns that short timeouts cause
   duplicate work, but probe 4 shows the trade on this provider: a hung judge call that
   would return after 126 to 246 s is answered in about 6 s by a retry. The owner's floor of
   15 s and 2 × p99 are the right size for that; a steady 1 to 3% stall tax at 15 to 80 s
   each is the cost of the route, not a defect to engineer away.
3. **File the AWS support case with probe 4's evidence.** Request ids were captured for
   the four calls that returned after 126 to 246 s (a 6 s call), with timestamps, region,
   the model id and the inference profile. That is exactly what AWS asks for, it needs no
   account change, and it is the only path to the cause of the hangs themselves.
4. **Before the production route flip: three cheap observability moves** (the
   observability note's list). Record the response's request-id header on every traced
   attempt (a hung attempt has none, which is itself evidence); graph `AWS/Bedrock`
   `Invocations` per minute per model id against the attempts Langfuse shows starting in
   that minute (free; a shortfall means requests never arrived); turn on model invocation
   logging in eu-west-2 to S3 only if the DPIA allows the stored bodies (text delivery off
   if that setting works; unverified).
5. **Before the production route flip: the key.** The long-term API key in the route's
   `api_key_env` is "exploration only" by AWS's own words. Short-term keys (12 h) need a
   refresh in the task; SigV4 needs a signing transport under the OpenAI SDK. An auth and
   infra change, approval-gated; raise it as its own task.
6. **Trim `max_completion_tokens` to real output sizes on the wide steps.** The screen step
   sends 8,192 and the classify step 16,384 against outputs of a few hundred tokens
   (`SCREEN_MAX_OUTPUT_TOKENS`, `CLASSIFY_MAX_OUTPUT_TOKENS`). Bedrock admits a request
   only if `input + max_tokens` fits in the quota that minute (the 10× burndown applies to
   the real output at settlement, not to the reservation), so one 48-wide classify burst
   reserves about 786,000 output tokens plus its inputs, roughly a fifth to a quarter of
   Luna's 4,000,000 global TPM, for its few seconds; a screen burst about a tenth. Today
   that costs nothing visible (no Bedrock 429s in any round), but several components'
   bursts in one minute, or production traffic joining staging's, is where it would first
   turn into throttling. One constant per step, measured by the recorded output sizes.
7. **Do not add TCP keep-alive or the NAT sysctl for this.** The documented 350 s class
   cannot reach a pool that expires idle connections at 5 s; add them only if someone raises
   the keep-alive expiry (write that constraint next to the client).
8. **Do not switch to streaming for the long steps.** AWS suggests streaming for long
   generations, but on Bedrock the first token arrives at 71 to 97% of a call's total (ADR
   0043 decision 6), so a streaming watchdog detects a stall no sooner than the timeout.
9. **A token-aware client-side limiter is a later seam, not now.** AWS recommends one
   (concurrency plus tokens per minute over a rolling window) for sustained fan-outs; our
   widths and the embedding pool are the current bound, and no round has hit a chat 429.
   Revisit when production and staging share the account's quota.

## 4. What stays unknown

Whether a request the client cut ever reached the model (invocation logging would say,
subject to the DPIA), why the long steps hang more at some hours than others, and where the
`global.` profile sends each request (CloudTrail's `inferenceRegion`, not yet read). None of
these block the merge or the route flip; items 3 and 4 above are how they get answered.
