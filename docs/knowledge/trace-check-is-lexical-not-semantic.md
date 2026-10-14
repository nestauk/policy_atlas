---
type: Invariant
title: The place-sentence trace check verifies that words come from the input, not that the sentence is true; its sentence-start rule runs after every terminator
description: `place_sentences.trace_check` has three rules — numbers equal a document count, strength words equal a document's tier, capitalised runs occur in the input — and a start token (the first, or one after ".", ":", ";", "!" or "?") may also be a number or function word. A lower-case false claim passes; an accurate second sentence beginning "One was …" was rejected on the live obesity run until the full stop joined the start rule. Every template fallback stores its reason with the entry.
tags: [place-sentences, trace-check, option-profile, mini-model, validation, task-046]
timestamp: 2026-10-12
---

# Rule

- The check is lexical by design (plan S31; contract review C2): it guards numbers, strength
  words and names against invention and leaves truth to the loop's hand read. A sentence such
  as "the evaluations measured diet quality" with a false predicate passes; the render is a
  plain text node, so the bounded risk is a wrong sentence, not an injection
  (security lane, 2026-10-12; a token-containment check is a deferred seam).
- `_START_AFTER` names every sentence terminator. With `[:;]` only, "… at year 6. One was
  Families for Health …" failed the name rule on "One" and the template that replaced it was
  less accurate ("3 moderate observational studies" for one strong trial and two moderate
  observational studies). The fixture set holds the case and the invented-name-after-a-full-stop
  case ("… diet quality. Bristol ran one." → `name`).
- A stored entry says why it is a template: `reason` is `call`, `missing`, `length` or the
  failing rule (`number`, `strength`, `name`), beside `generated`; the counts per kind are in
  `provenance.option_profile.place_sentences`. A card's sentence is diagnosable from the row.
- An id the answer gives that is not in the input is dropped before the duplicate check, so an
  unknown id repeated twice never makes the whole answer malformed.

# Why

The review's live-trace lane replayed the two rejected obesity sentences through the real
`trace_check` with the trace's own input (rule `name`; with "; one was" they passed) — the
method of [the 013 lesson](../agentic-ops/failure-log.md): pull the call's exact input and
output from the trace and replay it through the real validator. The reason persisted with the
entry follows the same lesson's corollary.
