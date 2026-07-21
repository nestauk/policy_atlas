# Contract-stage adversarial review — task 026

Codex (read-only), 2026-07-21, after owner approval of the contract. 15 findings; all
lead-verified against the v3 code and v2 CDK source before adjudication. Every claim
checked held. Dispositions below; contract/rubric amendments are marked `adversarial
FNN` in place.

| # | Sev | Finding (compressed) | Disposition |
|---|-----|----------------------|-------------|
| F1 | BLOCKER | Cognito access tokens carry `client_id`, not `aud`; `auth.py` unconditionally validates `aud` → every Cognito token rejected; "config-only auth" promise false | **Material — reopens owner gate.** Gated `auth.py` amendment added (accept `client_id`-as-audience when `aud` absent, per AWS verification guidance); ID-token-as-credential and pre-token trigger rejected |
| F2 | BLOCKER | v2 `Vpc.from_lookup` has no name filter; two VPCs in the account → v3 resources can bind to v2's VPC | Folded: `vpc_name` filter added to the namespacing constraint's systematic edit list |
| F3 | BLOCKER | Deleting `load_secret` removes the only composer of the single `DATABASE_URL` both API and Alembic require | Folded: `load_secret` moved delete→keep (it was mis-sorted; it is DB plumbing, not Supabase). Targeted edit: SQLAlchemy/psycopg3 URL format |
| F4 | BLOCKER | SSM tunnel contradicts rubric 13 (Aurora ingress restricted to API+migration SGs) | Folded: rubric 13 now names the fck-nat tunnel ingress as deliberate |
| F5 | BLOCKER | No `backend/Dockerfile` exists in v3; v2's is incompatible (entrypoint/src-layout) and its `COPY . .` would ship `.env`/dev-issuer keys | Folded: backend image authoring added to scope (ported Dockerfile + `.dockerignore` excluding gitignored/secret material) |
| F6 | MAJOR | Migration one-shot task has no cluster to run on (DB stack's cluster belonged to deleted Studio) | Folded: task def placed in app stack beside its cluster; deploy script sequences it |
| F7 | MAJOR | Deliverable claims bare `cdk deploy` yields a running system; migrations/frontend/fonts are imperative | Folded: deliverable reworded — the deploy script is the unit |
| F8 | MAJOR | v2 TG health check probes `/`; v3 serves only `/healthz`//`readyz` → service permanently unhealthy | Folded: health-check delta named in scope |
| F9 | MAJOR | Build guard checks only `VITE_OIDC_AUTHORITY`; missing `VITE_OIDC_CLIENT_ID` (provider throws) and `VITE_API_BASE_URL` (same-origin default → no API on CloudFront); `APP_ORIGIN` CORS env unnamed | Folded: guard widened to the full env set; `APP_ORIGIN` named in backend env surface |
| F10 | MAJOR | Cognito callback URLs / sign-out URLs not contracted; logout unverified | Folded: registration named in Cognito scope; hosted-UI logout added to smoke |
| F11 | MAJOR | First-deploy preconditions incomplete (cdk bootstrap incl. us-east-1, app secret name+keys, fonts uploaded, operator-created user) | Folded: preconditions checklist added to deploy-docs scope |
| F12 | MAJOR | 10-run capacity claim not evidenced by any acceptance check | Folded proportionately: 3-concurrent-run smoke + documented headroom arithmetic; full 10-run soak deliberately excluded (cost) — noted for owner |
| F13 | MAJOR | Deploy-invariant check was happy-path (idle redeploy) | Folded: second deploy now happens over an executing walk; kill order + migration-between + sweep disposition verified |
| F14 | MINOR | SSE idle/heartbeat vs ALB idle timeout untested; busy streams mask it | Folded: ALB idle timeout explicitly encoded vs 15 s heartbeat; ≥2 min parked-stream observation added to smoke |
| F15 | MINOR | Keeping Cloud Map contradicts no-unused-infra discipline (only consumers deleted) | Folded: Cloud Map cut from NetworkStack port |

Reviewer verdict was "not ready for planning"; adjudication concurs — the amendments
above are folded, and the contract returns to the owner for re-approval on F1 (the one
change to a promise the owner had relied on). F12's proportionate scoping (3-run smoke,
not 10) is also surfaced for the owner alongside F1 rather than silently decided.
