# Verification: 026-infra-deployment

> **Status: phases 0/A/B/C/D complete and verified; Phase E (live deploy + evidence)
> BLOCKED on three operator preconditions** — see § Known unverified items. Everything
> below the E sections is final evidence; E sections are pre-structured and empty.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (build-open baseline @ f5deb02) | pass | full gate, before any change |
| `make verify` (step-6 tree @ c5e552f) | pass | includes the new `make -C infra test` (28 tests) |
| `make verify-fast` (A.2, C-phase gates) | pass | 1924 backend tests + mypy + ruff |
| `make -C infra test` | pass | 28 passed — synth assertions, no AWS/Docker needed |
| `make fe-api-smoke` | pass | 3/3 Playwright specs against the real local API |
| `make deploy-build-guard-test` | pass | refusal proven per missing VITE_* var |
| `bash scripts/image_layer_scan.sh` | pass | image builds; 9 layers scanned clean |
| `bash -n scripts/deploy.sh` | pass | shellcheck not installed locally (noted) |

## Checks beyond the build

- **Infra unit suite** (`infra/tests/unit/`, 28 tests): table-driven namespacing over the
  port-map pin-2 table; v2-prefix absence; Supabase/Cloud Map/autoscaling absence; exactly
  one deploy Lambda (`load_secret`; CDK's Trigger-provider Lambda exempted); deploy
  invariants (`DesiredCount=0`, min/max healthy 0/100, `StopTimeout=10`, TG `/readyz`);
  Aurora SG ingress = exactly {API SG, migration SG, fck-nat SG} on 5432; fck-nat role has
  `AmazonSSMManagedInstanceCore`; Aurora `DeletionPolicy: Snapshot`; Cognito pool RETAIN +
  self-signup off + secretless PKCE client + exact callback/logout URLs; CloudFront OAC +
  SPA fallback + apex alias; buckets fully private; **lookup-filter test** reads the cloud
  assembly `manifest.json` missing-context queries and fails if any `vpc-provider` query
  loses the `tag:Name: policy-atlas-v3-vpc-staging` filter (negative-proven by removing
  the filter → `KeyError: 'tag:Name'`).
- **Auth conformance** (`backend/tests/api/test_auth_conformance.py`): Cognito-shaped
  accepted · `aud`-only rejected · wrong `client_id` rejected · `token_use: "id"`
  rejected · bogus `aud` alongside correct Cognito claims accepted (proves
  `verify_aud: False` doesn't resurrect the generic path).
- **Pool sizing** (`backend/tests/api/test_settings.py`): defaults/overrides/rejections;
  lifespan passes `pool_size`/`max_overflow` to `create_engine` (spied).
- **Image hygiene** (`infra/tests/unit/test_image_hygiene.py`): every gitignore pattern
  reachable in the backend build context is dockerignored; Dockerfile has non-root USER +
  factory CMD. Layer scan proves no `.env*`/`.dev-issuer/`/private-key material in ANY
  layer (public CA trust stores exempted). Image sanity: `import policy_atlas.api.app;
  import alembic` OK in-container; `alembic --help` OK.
- **FE↔real-API smoke** (browser, real HTTP): authenticated project-list GET renders ·
  project-create POST navigates to the project · stub run started and **"Searching
  sources" rendered from the real authenticated SSE tail** (fetch-streaming transport,
  not EventSource — the client attaches the bearer header).

## End-to-end command

```bash
make fe-api-smoke   # builds SPA w/ dev-issuer token, boots real API (stub mode,
                    # isolated policy_atlas_smoke DB), drives Chromium over real HTTP
```

Live-deploy end-to-end (Phase E): `bash scripts/deploy.sh bootstrap` — **not yet run**
(§ Known unverified items).

## Diff summary

v2's CDK app ported copy-first into `infra/` ([port-map.md](port-map.md) has the
per-file disposition table and the pinned v2 commit `db3027a`): three stacks namespaced
`PaV3*` with every fixed name resolved through the pin-2 table, Supabase apparatus
(Studio, postgres-meta, PostgREST+nginx, JWT Lambda + vendored PyJWT) deleted wholesale,
Cloud Map cut, autoscaling deleted. Deploy posture is template-encoded: `desired_count=0`
pinned so every `cdk deploy` stops the service; script (`scripts/deploy.sh`) owns
migrate→scale→publish ordering with fail-loud waits. New surfaces: Cognito
(`cognito_auth.py`), `PaV3CertStack` (us-east-1) + CloudFront OAC/SPA-fallback, private
font + SPA buckets, one-shot Alembic ECS task, SSM deploy/auth exports. Backend: the two
contracted edits only — auth congruence (`auth.py`, `dev_issuer.py`, settings rename
`OIDC_AUDIENCE`→`OIDC_CLIENT_ID`) and engine pool sizing. Backend Dockerfile + strict
`.dockerignore` authored (A.4). CI: `make -C infra test` joined `make verify`;
new `fe-api-smoke` job.

**Flagged deviations / build findings (minor, resolved in-slice):**
1. **Smoke DB isolation** — the FE↔API smoke initially reused `policy_atlas_test`; its
   persisted rows broke 4 migration round-trip tests in full verify (they downgrade with
   existing data). Fix: smoke owns disposable `policy_atlas_smoke`, recreated per run,
   dropped at teardown; `policy_atlas_test` reset. Root-caused, not guessed.
2. **Layer-scan layout** — `docker save` under Docker Desktop's containerd store emits
   OCI layout (`blobs/sha256/*`), not legacy `*/layer.tar`; the scan script now handles
   both and exempts OS public CA trust stores (certificates, not key material).
3. **Smoke SSE assertion** — original spec asserted "Mapping the landscape"
   (= `characterise`, an orchestrator-discretionary stage — known project pitfall);
   corrected to the always-present acquire stage "Searching sources", which persists in
   the timeline (no race against stub-speed execution).
4. **A.3 "exactly one Lambda"** — CDK's `triggers.Trigger` synthesizes a framework
   provider Lambda; the assertion counts application Lambdas and exempts the provider.
5. Local-only environment incident (not a repo change): Docker Desktop's VM network was
   wedged (pulls hung indefinitely, gvisor tx errors); full process kill + relaunch
   fixed it. Cost ~1.5h wall clock.

## Review findings

(To be added by the review stack — step 7, fresh conversation.)

## Rubric status

(To be added after the review stack; rubric items tied to live evidence are blocked with
Phase E.)

## Intent & assumptions

- Gate consolidation as landed: phases A–D completed together in one build session; one
  FULL `make verify` at the final tree (c5e552f) covers the A.4/C.3/D.3 full gates, with
  verify-fast + infra-suite runs green at each intermediate checkpoint. The plan's gate
  map anticipated consolidation across consecutive gates.
- `LOG_LEVEL=INFO` is wired in the task env though no backend reader consumes it yet
  (v2 carry; harmless).
- `LANGFUSE_BASE_URL` chosen over the `LANGFUSE_HOST` alias (tracing.py accepts both).

## Known unverified items

**Phase E (live deploy + evidence) is blocked on three operator preconditions**
(checked live 2026-07-21 ~21:30):

1. **NS delegation not live** — `dig NS v3.policyatlas.uk +short` returns nothing;
   parent `policyatlas.uk` still GoDaddy-only. Devops ETA was ~2026-07-22. Gates both
   DNS-validated ACM certs (first deploy hangs without it).
2. **No credentials for the target AWS account** — this machine's sole AWS profile is a
   different account (under-privileged user; cannot even `DescribeStacks`). The
   v2/v3 target account has no profile here. Operator must provide access
   (SSO/profile) before any `cdk` command.
3. **App secret not provisioned** — `policy_atlas_v3/app` must be created manually in
   Secrets Manager with the exact keys listed in [env-secret-map.md](env-secret-map.md)
   (gate A checks this and fails loud).

Ready-to-run once cleared: `scripts/deploy.sh bootstrap` (gates A/B verify the above
mechanically), then E.2 smoke (login → project → run → SSE → artefact → hosted-UI
logout; parked SSE ≥ 2 min; 3 concurrent runs + pin-14 measurements) and E.3
deploy-invariant check over an executing walk. Fonts for gate B are present locally at
`docs/specs/sources/evidence-base-ux/fonts/` (gitignored, as required).

Also unverified until E: real Cognito hosted-UI flow (the conformance suite covers token
semantics; the live smoke covers the interactive flow), CloudFront behaviour, migration
task against real Aurora.

## Public safety

No secrets, tokens, account ids, or IP allowlists in any committed file or in this
document (the misconfigured-account discovery above names no usable identifiers; config
JSONs carry no `aws_account_id` — decision 4). Deploy transcripts in Phase E must be
account-ID-scrubbed before landing here.

## Review handoff (step-7/8 inputs)

- **Executor provenance (family flip):** codex implemented A.3/A.4/B.2/B.3/C.2/D.1/D.3;
  fast-worker A.2/C.3/D.2; lead authored A.1/B.1/C.1 designs + review-time fixes
  (layer-scan OCI fix, smoke DB isolation, SSE assertion fix). Claude anchors review.
- **Diff-scoping:** exclude from review diffs: `docs/tasks/*` artefacts, the
  verbatim-copied portions of `infra/` (port-map.md gives the verbatim/edited split —
  review the deltas against v2 @ `db3027a`).
- **Adjudication items:** the 5 flagged deviations above; the auth diff
  (`9f40d32`) is the security lane's primary surface (contract hard gate).
- **Knowledge candidates** (014 retro — raw list for step 8):
  - Shared test DBs are a trap for migration round-trip tests: any harness that persists
    real rows (smoke, manual poking) breaks downgrade-with-data tests later and looks
    like a schema bug. Disposable per-harness DBs, always.
  - `docker save` layout depends on the daemon's image store: containerd store → OCI
    `blobs/sha256/*`; legacy store → `*/layer.tar`. Layer-scanning tools must handle both.
  - Docker Desktop VM network can wedge (API alive, all pulls hang, gvisor tx errors);
    app-level quit doesn't recycle the VM — full process kill + relaunch does.
  - Never assert orchestrator-discretionary stages (`characterise`) in UI tests — assert
    the acquire stage; recurring project pitfall, now bitten in a spec once.
  - CDK `triggers.Trigger` adds a hidden framework Lambda to the template — "exactly N
    Lambdas" assertions must exempt the provider.
  - The CDK lookup-filter can only be asserted via the cloud assembly's missing-context
    queries (`manifest.json`), never via template assertions — and CDK falls back to
    dummy context values silently, so a test that synthesizes "successfully" proves
    nothing about lookups.
  - PyJWT verifies `aud` by default when the claim is present even with no `audience=`
    argument — removing an audience check requires explicit `verify_aud: False` plus
    hand-rolled claim checks (plan-adv F9 held in practice).
  - uv src-layout images: `uv sync --no-dev --no-install-project --frozen` (deps layer)
    then post-COPY `uv sync --no-dev --frozen` (project) gives cacheable layers and a
    working `import policy_atlas` with no PYTHONPATH hacks.

## Deferred work

Closed by this slice (pending review-stack confirmation at step 8): licensed font
delivery (bucket + deploy-time injection) · deploy-invariant enforcement
(template-pinned `desired_count=0` + script ordering) · FE↔real-API smoke (adv-M6) ·
the widened `VITE_*` production build guard. **Stays open:** cross-instance
steering/live-tail seam (this slice enforces single-instance posture; scale-out remains
forbidden). `docs/deferred.md` edits land at E.4/step 8 against the final merged state.
