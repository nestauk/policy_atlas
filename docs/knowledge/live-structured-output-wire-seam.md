---
type: Integration quirk
title: Live structured-output wire models — strict schemas, envelope variance, and why stubs can't prove them
description: OpenAI strict response-format rejects open dict[str, Any] fields and the SDK's local converter does NOT catch it (400s surface only live); live models wrap deltas in variant envelopes. Pattern — transport twins carrying JSON-string payloads decoded fail-closed, a normaliser BEFORE validation, a schema-strictness regression test, and a pinned live check.
tags: [openai, structured-output, wire-model, strict-schema, transport-twin, normaliser, live-check]
timestamp: 2026-07-16
---

# The three lessons (task 024 live check — three real bugs the 1,761-test stub suite could not catch)

1. **Strict response-format rejects open objects.** A wire model with a
   `dict[str, Any]` field passes the SDK's `to_strict_json_schema` locally and
   400s only on the live call. Pattern: **transport twins** — the wire model
   carries the open payload as a JSON *string* field, decoded fail-closed at
   the seam into the real typed model. `tests/runtime/test_wire_schema_strictness.py`
   pins every live wire model closed; add new wire models to it.
2. **Live models wrap deltas in variant envelopes** (component-name wrapping,
   dotted family names). Normalise **before** fail-closed validation, never
   after — a normaliser may widen what *parses*, never what *validates*. Beware
   components whose family key equals their component name (characterise):
   never unwrap those.
3. **Stub-backed e2e cannot prove the live seam.** Schema strictness and
   prompt-shape failures exist only against the real endpoint — a contract that
   includes a live LLM seam needs a **pinned live check** in its acceptance
   (017/024 precedent), scoped and budgeted, not "we'll notice in prod".
