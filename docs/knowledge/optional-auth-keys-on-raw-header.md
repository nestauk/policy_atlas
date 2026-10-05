---
type: Invariant
title: Optional auth keys anonymity on the raw Authorization header, never on HTTPBearer's parsed credentials
description: HTTPBearer(auto_error=False) returns None for a wrong-scheme or malformed Authorization header, so a dependency keyed on the parsed credentials silently treats a present-but-broken header as anonymous. get_optional_user checks request.headers first — only a truly absent header is anonymous; every present header follows the strict 401 path.
tags: [auth, fastapi, public-surface, task-037]
timestamp: 2026-09-04
---

# Rule

An optional-auth dependency must decide "anonymous or not" from the **raw
`Authorization` header**, not from `HTTPBearer`'s parse result.

`HTTPBearer(auto_error=False)` yields `None` in three distinct cases: no
header, a non-Bearer scheme (`Basic …`, `Token …`), and a malformed bearer
value. Only the first is anonymous. Keying on the parsed credentials makes
a present-but-broken header pass as anonymous — on a conditionally-public
route that turns an expired-token retry (which the signed-in refresh flow
relies on getting a 401 for) into a silent redacted-public response.

`policy_atlas.api.auth.get_optional_user` implements the rule: absent raw
header → `None`; anything else → the strict `get_current_user` path, so
every present header that does not authenticate is 401. Pinned by the D2
header matrix in `tests/api/test_public_access.py` on both routers that
carry optional auth.

Found at 037 contract adversarial review (finding 4) before it shipped.
