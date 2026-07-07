---
type: Integration quirk
title: On reasoning models, max_completion_tokens covers reasoning + output — size caps for both
description: gpt-5-mini spends the completion budget on hidden reasoning tokens before emitting output; a cap tuned for a non-reasoning model's output truncates real answers (LengthFinishReasonError). Keep the cap explicit and fingerprinted, but size it for reasoning + output.
tags: [llm, openai, reasoning-models, token-caps, extraction, model-choice]
timestamp: 2026-07-07
---

# Rule

On OpenAI reasoning models (gpt-5 family), `max_completion_tokens` bounds **reasoning +
visible output together**. A cap that would be generous for a non-reasoning model's output
alone gets consumed by hidden reasoning tokens first: task 011's first live run pinned
8192 and truncated 5 of 9 full-text documents (`LengthFinishReasonError` — honest per-doc
`window_failed` failures; the machinery behaved, the pin was wrong). Raised to 32768 the
same documents extracted cleanly.

Keep the discipline, resize the number: the cap stays **explicit** (V2's uncapped calls
truncated mid-JSON and silently emptied stages) and **a fingerprint component** (changing
it creates records alongside, never stale reuse) — but size it for the model class actually
called.

# Why

The failure mode is quiet on small tasks and bites on real ones: short documents fit under
any cap, so stub suites and thin fixtures never catch it — only a live run on full-length
documents did. And because the truncation surfaces as a per-document failure with a reason
code (not a crash), a pipeline without honest failure accounting would have shipped the
run as "mostly worked".

# Watch out

- Any new generation surface on a reasoning model inherits this: check the cap against
  reasoning overhead, not just expected output size.
- The pin is plan-gate detail — flip it on live evidence without ceremony, but flag the
  deviation (the 011 flip is deviation 2 in verification.md).

# Citations

- [011-extract/verification.md](../tasks/011-extract/verification.md) (§ Live-run evidence,
  run 1; § Diff summary deviation 2)
- `EXTRACT_MAX_OUTPUT_TOKENS` in `src/policy_atlas/extract_prompt.py`;
  fingerprint component `max_output_tokens` in `src/policy_atlas/extract.py`
