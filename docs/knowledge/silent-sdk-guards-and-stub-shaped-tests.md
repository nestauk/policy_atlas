---
type: Testing rule
title: A getattr-guarded SDK call silently no-ops across upgrades — and a stub shaped to it proves nothing
description: langfuse 4.x removed update_current_trace; core.tracing's getattr guard silently skipped session attachment for every conversation (chat AND planning), while the tests stubbed the missing method and passed. Import optional SDK APIs loud, test the real mechanism, and verify observable behaviour live once.
tags: [langfuse, tracing, sessions, sdk-upgrade, stubs, testing, mock-shaped-to-code]
timestamp: 2026-08-11
---

# Rule

Three parts, all binding:

1. **Import SDK APIs loud.** `core/tracing.py` imports `propagate_attributes`
   at module top — if a future langfuse drops it, the app fails at import, not
   silently in telemetry. Never `getattr(client, "maybe_method", None)` for a
   capability the product claims to deliver.
2. **Session attachment is scope-shaped in SDK v4**: attributes propagate to
   observations *opened inside* `with propagate_attributes(session_id=...)`.
   Updating after the observation opens (the old `update_current_trace` shape)
   does not exist. `component_span` and `traced_call` open their observations
   inside `_session_scope`.
3. **Test the real mechanism.**
   `test_session_scope_propagates_session_id_into_the_real_otel_context`
   exercises the unpatched SDK and reads the propagated value out of the OTel
   context — no client, no network. Stubs that mirror what the code calls
   (`update_current_trace` on a fake) verify the code against itself.

# Why

Found by the 029 review stack's live-trace lane: every trace since the SDK sat
at 4.13 had `sessionId: null` — chat and planning alike — while the tracing
tests passed, because the test double implemented the method the real SDK had
removed. Same failure class as the 029 G-phase frontend mock (shaped to the
component, hiding the server's real payload shape) and the 013 zero-group
anomaly (diagnosable only from live traces). The pattern: the cheaper the
double, the more it must be anchored to something real — the wire shape, the
SDK's actual surface, or one live observation.

# Watch out

When a dependency majors, grep for `getattr(`-guarded calls into it — each one
is a place an upgrade can silently amputate behaviour. And when a review claims
"tests cover X", check what the double is shaped to.

Fixtures are doubles too: the 029 review's own task-scoping fix shipped
broken for full-text chunks because its new fixture seeded only the
uploaded/envelope snapshot linkage — `task_source_snapshot` reaches chunks
by TWO arms (`source_snapshot_id` and `full_text_snapshot_id`), and a fixture
covering one arm green-lights a join missing the other. When a table has
alternative linkage shapes, the fixture set must span them.
