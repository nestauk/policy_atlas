---
type: Convention
title: A limit for a mini model lives in the response schema or in code, never in the prose
description: On gpt-5.4-mini a ceiling stated in words did not bind (three rounds of "at most 12 kinds" gave 53–125; "at most 220 characters" did nothing; a ban on slash-joined kinds was answered with quote-joined ones), while a maxItems on the Pydantic field held on the first try and a code cut or a one-retry did the rest. The memo key of a prompt-backed step is its prompt VERSION, so a text change without a version bump reuses old records.
tags: [prompting, structured-output, mini-model, pydantic, folding, place-sentences, task-046]
timestamp: 2026-10-12
---

# Rule

When a step on the mini model must respect a hard limit, put the limit where the model
cannot ignore it:

1. **A count limit goes in the schema.** `max_length` on a `list[...]` field becomes a
   `maxItems` constraint in the structured-output schema (`folding_prompt.py`,
   `FoldingResponse.kinds`, `max_length=12`). The same rule in the system prompt and in the
   field description was ignored on every long list (046 amendment 3, loop 20L).
2. **A length limit on one item goes in code, with one retry.** A schema `max_length` on a
   sentence fails the whole call for one long sentence (plan review PA4-9), so the place
   sentences check the ceiling per sentence, refuse the first attempt once so the retry can
   come in under it, and fall back to a template on the last attempt
   (`option_profile._checked_places_within_ceiling`). "At most 220 characters" in the prompt
   did nothing; "sum a place up: the count, the commonest kind, at most one programme name"
   halved the over-length answers (loop 26L).
3. **A ban on one joiner is answered with another.** Forbidding "a / b / c" kinds produced
   quote-joined kinds and thirty unfolded words; the code cut (take the first member, counted
   as `slash_cuts` in provenance) is the lever, not the ban (loop 28, round 7–8).
4. **A catch-all needs a guard with a floor from the data.** One kind holding more than half
   of at least twenty words is retried once (`FOLDING_CATCH_ALL_SHARE`); the target unit's own
   kind rightly holds a third of the words on some lists, so a lower share needs the plan in the
   rule.
5. **The memo key is the prompt version, not its text.** A profile-record prompt edited without
   a `SCHEMA_VERSION`/prompt-version bump reuses the stored records; every loop round that
   changes a prompt bumps the version (see [fingerprint covers sub-component knobs](fingerprint-covers-subcomponent-knobs.md)).

# Why

Each of these was paid for in a refine loop of task 046 (amendments 3 and 4): rounds spent on
wording that a one-line schema or code change then settled. See also
[the refine loop's revert-not-iterate exit](refine-replay-revert-exit.md).
