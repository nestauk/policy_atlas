---
type: Convention
title: A max_length on a structured-output wire field truncates the answer mid-word; a length ceiling belongs in the code check, with the target stated in the prompt
description: In task 055 a `max_length=400` on the Potential impact wire field made the constrained decoder stop at the limit mid-word (sometimes a few characters short of it) instead of failing the attempt, so the plan's "a longer answer fails and is re-asked" never fired. The ceiling moved to the code check after the call, the prompt states a target (about 300, never more than 380), and on a spine step the code check is a hard bound above the target (600), not the target itself, because two over-target answers in a row would otherwise fail the whole walk.
tags: [prompting, structured-output, pydantic, option-profile, spine, retry, task-055]
timestamp: 2026-10-27
---

# Rule

Do not put a length limit on a structured-output wire field and expect a long answer to
fail. The constrained decoder honours the limit by **stopping** — mid-word, and sometimes
short of the number — so the attempt succeeds with a cut sentence. Put the ceiling in the
code check that runs after the call, and tell the model the target in the prompt (with
headroom: "about 300 characters, never more than 380" for a 400 ceiling).

On a **spine step** (one whose failure fails the walk), the code check must not be strict at
the target. Use two numbers: the target the prompt states, and a hard bound well above it
that fails the attempt; an answer between them is kept with a warning. Task 055's live run
produced 405- and 427-character lines on two attempts in a row; a strict 400 check failed
the profile step and only the runner's retry saved the walk.

# Why

Task 055, Potential impact line: round 1 of the prompt loop found four lines cut mid-clause
at exactly 400 characters; round 2 gave the prompt headroom and ten lines were still cut, some
short of 400 without a full stop — which showed the wire `max_length` was the cause, not the
words. Round 3 removed the wire limit and moved the ceiling to code
(`option_profile.py` `_checked_line`; constants in `option_profile_prompt.py`). The 204 lines
of the staged check then had none over 400 (longest 397) and every one ended with a full stop.

# Watch out

- The runner retries a failed model-calling step once on top of a component's own re-ask, so
  a step that fails its check twice can have made four model calls before the walk degrades.
- A hard bound is a contract deviation when the contract states one number; record it as such
  (055 verification.md § Diff summary, item 15) rather than describing the target as the
  ceiling. See [mini-model limits live in the schema and code](mini-model-limits-live-in-the-schema-and-code.md)
  for the opposite lesson on small models: a limit stated in prose does not bind at all.
