---
type: Integration quirk
title: PyJWT verifies aud by default whenever the claim is present — removing an audience check needs verify_aud False plus hand-rolled checks
description: jwt.decode with no audience= argument still rejects any token carrying an aud claim. Moving from audience semantics to Cognito access-token semantics (token_use + client_id) requires options={"verify_aud": False} and explicit claim checks, or valid tokens bounce.
tags: [auth, jwt, pyjwt, cognito]
timestamp: 2026-07-28
---

# Rule

PyJWT's `jwt.decode` enforces `aud` **whenever the claim exists in the token**, even
with no `audience=` argument — absence of configuration is not absence of the check.
Cognito *access* tokens carry no `aud` (identity lives in `client_id` + `token_use`),
but third-party tokens might: `auth.py` sets `options={"verify_aud": False}` and
enforces `token_use == "access"` and `client_id == settings.oidc_client_id` by hand.

# Why

Plan-adversarial finding F9 predicted this and it held in practice (026 C.2). The
conformance suite pins the property from both directions: `aud`-only tokens rejected,
and a bogus `aud` *alongside* correct Cognito claims accepted — proving
`verify_aud: False` doesn't resurrect the generic audience path
(`backend/tests/api/test_auth_conformance.py`).
