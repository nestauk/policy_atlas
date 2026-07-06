---
type: Integration quirk
title: Langfuse keys without a host silently export traces to the SaaS cloud — the host is required
description: The Langfuse SDK defaults its endpoint to https://cloud.langfuse.com when no host is configured; with full-I/O tracing that is a data-boundary violation, so get_langfuse() refuses to construct a client unless LANGFUSE_HOST/LANGFUSE_BASE_URL is set.
tags: [langfuse, tracing, egress, credentials, telemetry, security]
timestamp: 2026-07-06
---

# Rule

`Langfuse()` constructed with only `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` resolves its
host to `https://cloud.langfuse.com` (verified in langfuse 4.13.0,
`_client/client.py`). Policy Atlas traces carry **full prompt/response I/O including corpus
text** (decision 13), and the contract promises user-operated instances only — so a
forgotten host var would ship the payload to a third party. The export fails auth (401),
but asynchronously: the payload has already left, and the run appears to succeed.

`tracing.get_langfuse()` therefore fails loudly instead of falling back: both keys set
without `LANGFUSE_HOST` (or the SDK-v4 name `LANGFUSE_BASE_URL`) → `RuntimeError`; exactly
one key set → `RuntimeError` (a silent no-op would mean a live run with zero trace record —
wrong for a provenance product). All-unset stays a clean no-op so `make verify` needs no
Langfuse config. Test: `test_judgment_tracing_requires_host_when_keys_present`.

# Why

Found independently by two review families (security lane MEDIUM + Codex HIGH) on task
009's review stack — the exact "developer has keys in the shell, forgets the host" scenario
is the default onboarding path, and `.env.example`'s blank `LANGFUSE_HOST=` read as
optional before the comment was fixed.

# Watch out

- Langfuse v4 deprecates `LANGFUSE_HOST` for `LANGFUSE_BASE_URL`; `get_langfuse()` honours
  both and passes the host explicitly to the constructor — keep that explicit-pass if the
  SDK's env-resolution order ever changes.
- The same reasoning applies to any future exporter of full-I/O telemetry: no silent
  default destination, ever.

# Citations

- [009-characterise/verification.md](../tasks/009-characterise/verification.md)
  (§ Review findings — convergent finding)
- `get_langfuse` in `src/policy_atlas/tracing.py`
- Test: `test_judgment_tracing_requires_host_when_keys_present` in `tests/test_characterise.py`
