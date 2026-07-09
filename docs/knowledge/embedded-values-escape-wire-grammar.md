---
type: Convention
title: Values embedded in a structured wire param must exclude that wire's metacharacters
description: OpenAlex's filter param is comma-delimited; a comma surviving sanitization into the embedded search value opens a new, attacker-expressible filter clause — bypassing the fail-closed directive grammar entirely. Sanitizers are wire-grammar-aware, not just content-aware.
tags: [security, injection, transport, sanitization, search]
timestamp: 2026-07-09
---

# Rule

When a free-text value is embedded inside a *structured* wire parameter, the
sanitizer must exclude the structure's own metacharacters — the separators and
key/value syntax of the carrying grammar — not merely characters that break the
value's content. As built: `sanitize_openalex_query` replaces every comma with
a space because OpenAlex's `filter` param is comma-delimited
(`title_and_abstract.search:<value>,<next-clause>`); the transport-side
no-citation-floor guard then only needs to inspect genuine wire clauses.

# Why

015 shipped the sanitizer with v2's scope (commas inside quoted phrases), so a
comma in an LLM-generated query survived to the wire — where it terminated the
search value and everything after it parsed as a new filter clause
(`x,is_retracted:true`, `x,to_publication_date:...`). That bypassed the
fail-closed `scope_filters` grammar: the one validated path for filters didn't
matter when the *query text* could write filters directly. Generated queries
derive from third-party metadata via reformulation, so this was
instruction-shaped-content-reaches-the-wire, the exact class the prompt-side
JSON-record boundary
([untrusted-prompt-fields-json-records](untrusted-prompt-fields-json-records.md))
closes on the prompt side. Both heterogeneous 015 review lanes found it independently.

# Watch out

- The benign case fails too: a natural comma in a query 400s or silently
  narrows the call — this is a correctness rule, not only a security rule.
- Every new wire param that embeds free text (a future backend's query syntax,
  URL path segments) needs the same question asked at review: *what characters
  does the carrier grammar reserve?*
- Escaping is per-wire: what OpenAlex reserves (`,` and leading `key:`) is not
  what Overton or a future backend reserves.
