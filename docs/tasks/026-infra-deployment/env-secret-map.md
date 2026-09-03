# Environment and secret map

Task B.3 inventory, generated from the required command plus every
`_required`/`_optional` call in `backend/src/policy_atlas/api/settings.py`.
`LANGFUSE_HOST` is what the provisioned secret carries (v2's key name); tracing
accepts it natively, so deployment injects it directly (E.1 deviation).  `POLICY_ATLAS_*` tuning and
the fixture corpus are intentionally omitted from the deployed task.

| Var | Source | Consumer file |
| --- | --- | --- |
| `APP_ORIGIN` | config value: `https://{domain_name}` | `api/settings.py` |
| `DATABASE_URL` | Secrets Manager field: DB secret `db_connection_string` | `api/settings.py`, `core/db.py` |
| `DB_MAX_OVERFLOW` | config value: `backend.db_max_overflow` | `api/settings.py` |
| `DB_POOL_SIZE` | config value: `backend.db_pool_size` | `api/settings.py` |
| `LANGFUSE_HOST` | Secrets Manager field: `policy_atlas_v3/app` `LANGFUSE_HOST` | `core/tracing.py` |
| `LANGFUSE_BASE_URL` | omitted (equivalent alias of `LANGFUSE_HOST`) | `core/tracing.py` |
| `LANGFUSE_PUBLIC_KEY` | Secrets Manager field: `policy_atlas_v3/app` `LANGFUSE_PUBLIC_KEY` | `core/tracing.py` |
| `LANGFUSE_SECRET_KEY` | Secrets Manager field: `policy_atlas_v3/app` `LANGFUSE_SECRET_KEY` | `core/tracing.py` |
| `LOG_LEVEL` | config value: `INFO` | container runtime (no current backend reader) |
| `OIDC_CLIENT_ID` | config value: Cognito SPA client ID | `api/settings.py` |
| `OIDC_ISSUER` | config value: Cognito issuer | `api/settings.py` |
| `OIDC_JWKS_CACHE_TTL_SECONDS` | omitted (application default: 300) | `api/settings.py` |
| `OIDC_JWKS_PATH` | omitted (development issuer only; mutually exclusive with JWKS URL) | `api/settings.py` |
| `OIDC_JWKS_URL` | config value: Cognito JWKS URL | `api/settings.py` |
| `OPENAI_API_KEY` | Secrets Manager field: `policy_atlas_v3/app` `OPENAI_API_KEY` | `api/deps.py`, `core/openai_client.py`, `runtime/orchestrate.py` |
| `OPENALEX_API_KEY` | Secrets Manager field: `policy_atlas_v3/app` `OPENALEX_API_KEY` | `api/deps.py`, `evidence_base/sourcing/search_live.py` |
| `OPENALEX_EMAIL` | Secrets Manager field: `policy_atlas_v3/app` `OPENALEX_EMAIL` | `evidence_base/sourcing/search_live.py` |
| `OVERTON_API_KEY` | Secrets Manager field: `policy_atlas_v3/app` `OVERTON_API_KEY` | `api/deps.py`, `evidence_base/sourcing/search_live.py` |
| `PA_BACKEND_MODE` | config value: `live` | `api/deps.py` |
| `POLICY_ATLAS_FIXTURE_CORPUS` | omitted (development/test fixture override) | `evidence_base/sourcing/ingest_full_text.py` |
| `POLICY_ATLAS_ORCHESTRATOR_MODEL` | omitted (development tuning; application default) | `runtime/orchestrator_backend.py` |
| `POLICY_ATLAS_ORCHESTRATOR_TRIAGE_MODEL` | omitted (development tuning; application default) | `runtime/orchestrator_backend.py` |
| `POLICY_ATLAS_PLANNER_MODEL` | omitted (development tuning; application default) | `runtime/planner.py` |
| `POLICY_ATLAS_RELEVANCE_MODEL` | omitted (development tuning; application default) | `evidence_base/extract/relevance_annotator.py` |
| `POLICY_ATLAS_SEARCH_CACHE_TTL_S` | omitted (development tuning; application default) | `evidence_base/sourcing/search_live.py` |
| `POLICY_ATLAS_SYNTHESIS_MODEL` | omitted (development tuning; application default `gpt-5.6-terra`) | `evidence_base/synthesis/synthesis_backend.py` |
| `RUN_EXECUTOR_MAX` | config value: `backend.run_executor_max` | `api/settings.py` |
| `SSE_HEARTBEAT_SECONDS` | omitted (application default: 15) | `api/settings.py` |
| `SSE_POLL_INTERVAL_SECONDS` | omitted (application default: 0.4) | `api/settings.py` |
