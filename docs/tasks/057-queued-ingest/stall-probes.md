# Stall probes: where the Bedrock hangs come from

A measurement brief for the review conversation (task 057, written 2026-11-03 after the
build). Bedrock is the route the app uses; `openai-direct` is legacy and is not probed.

## What the build saw

Two kinds of cut call (every figure is in `verification.md`, rounds (a) to (g)):

- **Bursts at the wide fan-outs.** 96 `screen_abstract` cuts in one minute at width 48
  with a 7 s timeout (round (g)), 12 `classify_document` cuts in three seconds while two
  runs classified at once (round (a)). Every one recovered on the next attempt. The
  timeouts were derived from p99s measured at width 12, and the client timeout counts
  queueing and connection setup. The floor is now 15 s (owner, 2026-11-03), which is the
  first fix; the probes below say whether it is enough.
- **Hangs.** Single calls that sit to the cut and then succeed fast on retry: 120 s on a
  4 s `propose_sections` step, three 60 s cuts on one `characterise_assign` batch, two
  80 s `judge_grounding` cuts then 7 s. About 1 to 3% of calls; 4 to 6% of judge calls.
  Connection errors (`APIConnectionError`) appear next to them.

## What is not known

Whether a hung request ever reached the model. Three explanations fit the same client
view: the Bedrock global routing for the OpenAI models holds or drops the request; the
endpoint applies a concurrency limit by holding instead of returning 429; the shared
`httpx` client re-uses a keep-alive connection the server has closed, so the request is
written to a dead socket and the client waits for a reply that never comes.

## Probe 1: did the hung requests reach Bedrock?

Compare the client's sends with the service's invocation count for one fixed-question run.

1. Turn on Bedrock model invocation logging for the account (CloudWatch Logs) for the
   probe window, or read the `Invocations` and `InvocationClientErrors` metrics for the
   three model ids at one-minute grain.
2. Run one fixed question (`scripts/fixed_questions.py --only neet`) from the laptop with
   the HEAD code; keep the server log.
3. For every `model_call.retry` line, look for a matching invocation (by model, minute
   and input size) in the service log.

Reading: if the hung requests are in the service log with normal latency, the response
was lost between the service and the client (connection re-use or the routing layer). If
they are absent, the requests never reached the model (the routing layer or the client).

## Probe 2: connection re-use

Same run twice, same code, one variable: the client's connection pool.

1. Build the OpenAI client with an `httpx.Client` whose limits allow no keep-alive
   (`max_keepalive_connections=0`), so every request opens a fresh connection; a two-line
   change in `core/openai_client.py::resolve_openai_client` for the probe branch only.
2. Run NEET and zonal with it; count `model_call.retry` by step and the hangs that reached
   attempt 3.
3. Run the same two questions with the pool as shipped.

Reading: a hang rate that falls to near zero without keep-alive is a stale-connection
problem; the fix is a keep-alive expiry shorter than the server's idle timeout (or no
keep-alive on the Bedrock route), and it belongs in the route-file client settings. A hang
rate that does not move clears the client.

## Probe 3: the burst shape at width 48

Fire the real `screen_abstract` prompt at the real width with no timeout, and read the
latency distribution.

1. From a script in the scratchpad, send 48 concurrent `screen_abstract` requests (the
   committed fixture abstracts) through the shipped client with `timeout_s = 300`, three
   times, one minute apart; then the same at width 12.
2. Record per request: time to first byte, total time, connection reused or new.

Reading: a p99 at width 48 that is many times the p99 at width 12 is queueing (the
endpoint or the client pool serialises), and the step's timeout must be derived at the
width it runs at; the 15 s floor is right if the width-48 p99 sits under 7.5 s.

## What to do with the results

- Stale connections confirmed: route-file client setting (keep-alive expiry), one commit,
  re-measure one round.
- Routing-layer loss confirmed: an AWS support case with the invocation ids; keep the
  three attempts; nothing to change in the code.
- Queueing confirmed: derive the fan-out steps' timeouts from a week of staging data at
  width 48 (`scripts/step_timeouts.py --min-n 30 --floor 15`), or lower the widths.

Each probe is one afternoon on the laptop with the dev server. None needs a code change
on the branch.
