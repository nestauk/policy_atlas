# C.1 design — auth congruence + pool sizing (task 026)

Lead-authored design for the two contracted backend edits (contract decision 7 /
scope item 5; plan pins 8–9). C.2/C.3 implement against this; the security lane
reviews the auth diff at step 7.

## Auth congruence (pin 8 — one verification path, Cognito access-token semantics)

**`settings.py`** — rename field `oidc_audience` → `oidc_client_id`; env
`OIDC_AUDIENCE` → `OIDC_CLIENT_ID`. No back-compat alias (nothing deployed).
Docstring updated. C.2 sweeps every `OIDC_AUDIENCE` reference repo-wide (envs,
docs, tests, smoke fixtures, Makefiles, .env examples).

**`auth.py` `JwtAuthenticator.authenticate`** — the decode call becomes:

```python
claims = jwt.decode(
    token,
    key=self.jwks.get_key(kid),
    algorithms=["RS256"],
    issuer=self._settings.oidc_issuer,
    options={"require": ["exp", "sub"], "verify_aud": False},
)
```

`verify_aud: False` is explicit because PyJWT verifies `aud` by default whenever the
claim is present even without an `audience=` argument (plan-adv F9) — a Cognito
access token has no `aud`, but an attacker-supplied one must not re-enter the generic
path. Then two explicit Cognito claim checks (raising `jwt.InvalidTokenError`):

```python
if claims.get("token_use") != "access":
    raise jwt.InvalidTokenError("token is not an access token")
if claims.get("client_id") != self._settings.oidc_client_id:
    raise jwt.InvalidTokenError("token client_id mismatch")
```

RS256 / issuer / exp / sub handling unchanged. The generic `aud` check is REMOVED,
not kept as a fallback (owner ruling: no dual dialects).

**`dev_issuer.py` + mint CLI** — faithful Cognito imitation: minted claims become
`{sub, iss, client_id, token_use: "access", iat, exp}` — no `aud`. CLI flag
`--audience` → `--client-id` (mint arg validation updated to match). `init` flow
unchanged.

**Conformance suite (C.2, extends the existing auth tests):**
- Cognito-shaped token (`client_id` + `token_use: "access"`, no `aud`) → accepted
- legacy `aud`-only token (no `client_id`/`token_use`) → rejected
- wrong `client_id` → rejected
- `token_use: "id"` (ID token used as credential) → rejected
- token carrying a bogus `aud` alongside correct Cognito claims → accepted
  (proves `verify_aud: False` doesn't resurrect the generic path)

## Pool sizing (pin 9)

`Settings` gains `db_pool_size: int = 5` and `db_max_overflow: int = 10`, loaded from
`DB_POOL_SIZE` (`_positive_int`) and `DB_MAX_OVERFLOW` (zero allowed — new
`_nonnegative_int` helper mirroring `_positive_int`). Threaded into the lifespan's
`create_engine(settings.database_url, pool_pre_ping=True, pool_size=...,
max_overflow=...)` (`api/app.py` line ~145). Prod task env (B.3 map): `DB_POOL_SIZE=15`,
`DB_MAX_OVERFLOW=10`, `RUN_EXECUTOR_MAX=10` — 10 walk threads + request traffic under a
25-connection ceiling. Tests: settings parsing (defaults, override, invalid) + engine
kwargs observed via a stubbed `create_engine`.
