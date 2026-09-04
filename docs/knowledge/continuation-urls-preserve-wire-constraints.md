---
type: Invariant
title: Provider-supplied continuation URLs must provably preserve the request's wire constraints
description: Overton pagination follows next_page_url verbatim with empty params, so every filter guarantee (source=apo, publisher_country, …) rides on the provider echoing it back; the follow now fails closed if a wire filter param is missing from the next-page URL.
tags: [egress, pagination, fail-closed, overton, transport]
timestamp: 2026-09-04
---

# Rule

When pagination (or any continuation) follows a provider-composed URL, the
request's constraint parameters are only as durable as the provider's echo.
Host validation is not enough: a next-page URL on the right host with the
filters missing is an *unfiltered* search. As built:
`search_live.py::_validate_overton_next_page_url` takes the original wire
filter params and raises `SearchTransportError` unless every one survives in
the next-page URL's query string — a buggy or hostile response degrades to a
loud transport error, never to silent unscoped egress.

# Why

038's contract required `source=apo` on **every** Overton call. Page one
carried it; follow-up pages were fetched verbatim with `{}` params
(deliberately — httpx's `params=` *replaces* a URL's query, and 015 pinned
that live `next_page_url` echoes the request's params including the API
key). The Codex adversarial lane flagged that the guarantee was assumption,
not enforcement; the same exposure covered every other Overton filter
(`publisher_country`, `language`, …) since 015. The guard converts the
assumption into an invariant, scoped to the wire *filter* params (not
`squery`/`api_key`/`pp`, whose absence fails server-side anyway).

# Watch out

- Test stubs must now be realistic: a stubbed `next_page_url` that omits the
  request's filters correctly *fails* — include the filter params in stub
  URLs (mirrors live behaviour per 015 param-pinning §5).
- The check is exact key=value presence via `parse_qsl`; a provider that
  legitimately *renames* a param on continuation would need a mapping, not a
  guard removal.
- Any future backend with continuation URLs (or cursors that encode filters
  opaquely) needs its own answer to "how do we know page N is still the
  filtered query?".
