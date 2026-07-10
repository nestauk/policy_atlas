---
type: Live behaviour
title: A 403 from a document host is usually bot-blocking, not a paywall
description: 403 responses from live document hosts are predominantly WAF/bot-blocking of datacenter clients; only corroborated 403s (body markers or an OA cross-check) count as paywalls, or corpus accessibility is silently misstated.
tags: [live-behaviour, fetch_live, http, "016", paywall]
timestamp: 2026-07-10
---

# Rule

Treat a 403 from a document host as bot-blocking, not a paywall, unless it is
corroborated. The decision-8 ladder
(`fetch_live.py::_response_outcome`): 401 → paywall unconditionally; 403 →
paywall **only** with corroboration (body paywall-markers present at fetch
time, or the envelope OA-closed cross-check applied at ingest via
`ingest_full_text.py::_apply_oa_cross_check`); otherwise → `blocked_by_host`.
Fixture replay maps a recorded 403 the same way — `blocked_by_host` — because
a recorded 403 carries no body to corroborate against; this was aligned by
the 016 review stack after Codex caught the divergence between live and
fixture handling.

# Why

5 of 7 live fetch failures in 016's live check were classified
`blocked_by_host`; zero were corroborated paywalls. If 403s were counted as
paywalls outright, this run would have silently overstated how much of the
corpus sits behind access control, when the actual cause was datacenter-IP
WAF blocking. Counting bot-blocks as paywalls misstates corpus accessibility
without ever raising an error — the miscount is silent by construction.

See also [[citation-flag-dont-drop]] for the related flag-don't-drop lineage
on outcome classification.
