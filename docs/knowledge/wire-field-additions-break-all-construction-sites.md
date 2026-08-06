---
type: Convention
title: Wire-model field additions break every construction site at import — stage nulls first
description: Extraction wire models are all-fields-required (OpenAI strict structured output forbids defaults), so ANY field addition breaks every construction site — including the few-shot example, whose import-time pre-flight fails the whole module. The keep-green pattern is mechanical nulls at the schema phase, real values authored at the prompt phase (task 020 phases A/B).
tags: [wire-models, structured-output, pydantic, extraction, build-sequencing]
timestamp: 2026-07-12
---

# Rule

A field added to an all-fields-required wire model (`IOFRecordWire` and kin —
strict structured output forbids defaulted/optional-key fields) is not a local
change: **every** construction site fails immediately, and because the few-shot
example is validated by an import-time pre-flight, the failure surfaces as a
module import error, not a test failure. Sequence multi-phase builds
accordingly: the schema phase adds the field everywhere with mechanical
`None`s (example included), and the prompt phase replaces the example's nulls
with real authored values.

# Why

Task 020 added `effect_basis`/`study_geography` in phase A (Codex-authored
models) with the prompt work deliberately deferred to phase B (lead-only).
Without the nulls-first staging, phase A could not have landed green at all —
the few-shot example would have failed the import-time pre-flight before any
test ran. The staging is what lets schema work and prompt authorship live in
different commits (and different executors) without a red intermediate state.

# Watch out

- Construction sites hide in: stub backends' sentinel payloads, shared test
  record factories, the few-shot example, and back-compat shims
  (`_with_iof_v2_defaults`) — grep for the model name, not just callers.
- **Transport-twin wires double every site** (028): where a domain wire has
  a JSON-string transport twin (`AuthoredOptionWire` /
  `AuthoredOptionTransport`, delta as `delta_json`), a new field must
  thread through BOTH twins **and** `to_wire()` or it silently drops
  (`endorses_option_id`). And a schema that *requires* fields the prompt
  tells the model to omit makes honest outputs unserialisable — 028's
  endorsements needed `component`/`delta` nullable-on-endorsement with the
  requiredness moved into consumer-side validation (`watch_authoring_v2`).
- The import-time pre-flight is the guard doing its job: do not weaken it to
  make a partial addition pass.
- Same family: [structured-output-prompts-pin-key-vocabulary](structured-output-prompts-pin-key-vocabulary.md)
  (strict schemas move correctness work into the prompt and its examples).
