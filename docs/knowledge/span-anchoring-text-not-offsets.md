---
type: Invariant
title: Span anchoring asks the model for verbatim text and binds offsets code-side
description: LLMs cannot emit reliable char offsets — model-facing wires carry claim TEXT; exact-substring binding computes offsets fail-closed. After a splice, offsets are recomputed by construction (one-pass rebuild), never delta-shifted, with a round-trip assertion at persist time.
tags: [synthesis, spans, adr-0015, grounding, offsets, fail-closed]
timestamp: 2026-07-11
---

# Rule

Never put character offsets on a model-facing wire. The ADR 0015 emission wire asks the
writer for **verbatim claim text**; `bind_spans` locates it in the authored prose by
exact substring (ordered-cursor with a non-overlapping fallback), fail-closed —
`prose[start:end] == text` holds by construction or the claim doesn't bind
(`span_bind_failures`, routed to repair).

Offset arithmetic after prose mutation is where span bugs live. `splice_and_rebind`
does a **one-pass rebuild**: emit the prose pieces in order, record each kept/replaced
segment's new position as it lands — every offset is recomputed by construction, no
delta-shifting of old offsets. `_write_section` is the terminal gate: it re-derives
trust from nothing but the substring equality at persist time, so an upstream bug
fails the component instead of shipping a mislocated claim.

# Why

Both halves came out of the 018 B3 build of the prose-first wire, and the B smoke
re-proof (132 addressable units, 0 span violations on a live substrate) is the
verification. Models asked for offsets directly produce plausible-but-wrong integers;
delta-shift repair code accumulates edge cases (adjacent segments, repeated substrings,
empty replacements) that a rebuild-by-construction never has.

# Watch out

- Repeated substrings: binding attaches to the first non-overlapping occurrence — the
  content is right by construction, but the *instance* pointed at can differ from the
  author's intent. Excerpt binding blocks claim spans for this reason
  (`_bind_unspanned`); anything new binding text into shared prose should pass a
  blocked-span list too.
- The judge's unspanned-excerpt lane rides the same exact-substring rule: a
  hallucinated excerpt simply fails to bind (`unspanned_unbound`) — that's the
  fail-closed behaving, not a bug.

# Citations

- [ADR 0015](../adr/0015-prose-first-synthesis-with-span-anchored-claims.md) §2
- `bind_spans`, `splice_and_rebind`, `_write_section` in `src/policy_atlas/synthesise.py`
- [018 verification.md § B3](../tasks/018-dress-rehearsal/verification.md) (B smoke
  re-proof: run `5a044d71`, 132 units / 0 violations)
