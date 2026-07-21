# FastAPI guidelines digest — for task 025-web-app-foundation

> Source: `docs/research-and-development/FAST_API.pdf` ("FastAPI for AI
> Engineers", AI Engineering Insider, 2026), all 89 pages read. Page
> citations are the printed page numbers (PDF p.9 = book "9").
> Audience: three future readers — the **lead** adjudicating section 1,
> the **plan author** (section 2), the **build agent** (section 3).
> The PDF is a general best-practices text; it does not know our contract.
> Where it conflicts with a contract pin, section 1 flags it honestly —
> the contract is not automatically wrong. **This digest never edits the
> contract.**

---

## 1. Contract-impacting findings

Few, by design. Each names the guideline + page, the contract pin it
touches, and a recommendation for the lead.

### 1.1 — `403 cross-user` contradicts the PDF's BOLA guidance (return `404`)

- **Guideline (p.51 §6.5, p.53 Q3, p.52 B2B scenario, p.58 Listing 7.3):**
  Broken Object-Level Authorization is OWASP API risk #1. The PDF is
  explicit and repeated: for a resource the caller does not own, **return
  `404`, not `403`** — a `403` confirms the object exists and leaks
  information ("cross-tenant access is a 404, not a 403, to avoid
  existence leaks", p.52; "Return 404 not 403 for unowned objects to
  avoid confirming existence", p.53). The auth test in Listing 7.3
  asserts `404` for one user reading another's task.
- **Contract pin touched:** § API design pins → *One error envelope*
  mapping: "**403 cross-user** · 404 unknown/archived"; and Deliverable
  tests "authz fail-closed (401/403 incl. cross-user)"; and Constraints
  "authz fail-closed (401/403)".
- **Recommendation:** flip object-ownership failures to **`404`** (treat
  another user's project/run as not-found). Reserve `403` for
  authenticated-but-forbidden *role/permission* cases within an owned
  scope (there are none in this slice yet). This also removes an internal
  inconsistency — the contract elsewhere pins strict per-owner scoping,
  whose whole point (p.53) is that unauthorized rows are never loaded and
  the response is indistinguishable from absent. Note the contract already
  lists `404` for "archived", so a soft-deleted-but-owned resource and a
  not-yours resource would then share `404` — that is the intended
  behaviour, not a bug.

### 1.2 — In-process long-running runs: event-loop execution mode is unpinned

- **Guideline (p.64 §8.1 + Table 8.1, p.64 "deadliest production bug",
  p.67 document-processing case study, p.68 Q1, p.73 Listing 9.1, p.77
  Q1):** The PDF's single most-emphasised rule is *never block the event
  loop*. An `async def` handler (or any coroutine) that runs CPU-bound or
  synchronous-blocking work freezes **every** endpoint in the process for
  its duration — including `/health`, SSE streams, and other projects'
  requests. The document-processing case study (p.67) is exactly our
  shape: an in-process synchronous job took down `/health` and triggered a
  restart cascade. The prescribed fix for >100 ms CPU work is offload:
  plain `def` (threadpool), `run_in_executor` / `anyio.to_thread.run_sync`
  (p.73 Listing 9.1 does this for inference), or a worker queue.
- **Contract pin touched:** Context summary — "long-running LLM runs
  executed **in-process** with blocking steering pauses"; strand 5 "runs
  execute in-process".
- **Assessment:** the contract has *deliberately* accepted
  non-durability (honest interruption, orphan sweep, no resume engine) —
  that reconciles with the PDF's "losing the task on restart is a bug →
  don't use BackgroundTasks / use a queue" point (p.66, p.69 Q3): our
  answer is "the walk is disposable, the durable record is the truth", not
  "the walk survives". **That is a coherent choice and section 1 does not
  reopen it.** What is *not* pinned is **how the in-process run executes
  relative to the event loop**: on the request coroutine (fatal), as an
  `asyncio` background task that only ever `await`s truly-async work, or
  offloaded to a thread. The chain does blocking LLM/IO and CPU work; if
  it lands on the loop, SSE + health + all other projects stall.
- **Recommendation:** the **plan must pin the execution model** — most
  likely a background `asyncio.Task` per run whose blocking/CPU steps are
  offloaded via `to_thread`/`run_in_executor`, plus a bound on concurrent
  in-flight runs per process. Add a loop-lag guard to the live-check
  acceptance (p.64 watchdog) so a blocking regression is caught.

### 1.3 — In-process runner vs. horizontal scaling / cross-instance steering delivery

- **Guideline (p.16 Q8 statelessness, p.11 Fig 1.1, p.81 §10.1 "one
  worker per pod … horizontal scaling by pod count", p.83 Fig 10.1):**
  The PDF's production model is *stateless* workers behind a load balancer
  — "any worker can serve any request", state lives in shared stores. It
  also notes long-lived connections pin clients to a pod and need a
  pub/sub backplane to fan out across pods (p.67 WebSocket note, p.69 Q5).
- **Contract pin touched:** strand 5 "runs execute in-process" + § API
  design pins "one active run per project enforced in Postgres at
  dispatch"; strand 4 steering answers "POST through the real steering
  seam". The infra/deploy shape is deferred to the `infra/` slice.
- **Assessment:** in-process runner state (the blocking pause, the live
  SSE tail, the ephemeral tick channel) is **pod-local**. Under >1
  API instance: (a) a steering answer POSTed to instance B cannot unblock
  a runner blocked on instance A without a cross-process mechanism; (b)
  the live tail / ephemeral ticks are only visible on the instance running
  the walk; (c) the startup orphan sweep (strand 5) runs once **per
  worker/pod** and must be idempotent and guarded (e.g. advisory lock, or
  only sweep runs this instance can prove are dead) so one worker doesn't
  mark another's live run `interrupted`. The durable-replay design already
  covers *reconstruction*, but not *live delivery* or *unblocking* across
  instances.
- **Recommendation:** the plan should either (i) **pin a single API
  instance for this slice** (document it; the infra slice revisits
  scale-out), or (ii) specify the cross-instance steering-delivery + live
  fan-out mechanism (DB poll / Postgres `LISTEN`/`NOTIFY` / pub-sub). And
  pin the orphan-sweep guard regardless. This is a plan-level decision the
  contract currently leaves implicit.

### 1.4 — Pagination: offset/page + `total_items` vs. the PDF's cursor default, and a missing `page_size` cap

- **Guideline (p.27 §3.4, p.28 Stripe case study + deep-pagination cost
  curve, p.29 Q2, p.31 Q10):** offset/page pagination "degrades on deep
  pages … can skip/duplicate items when rows are inserted mid-scan";
  cursor/keyset is the recommended default "for anything public,
  infinite-scroll, or large", offset only for "small admin UIs". Separately
  and emphatically (p.30 **Q6**): list `limit`/`page_size` **must have a
  server-enforced maximum** — an unbounded page size is a DoS vector and a
  capacity-planning impossibility.
- **Contract pin touched:** § API design pins → *Pagination from day one*:
  "one envelope `{data, pagination: {page, page_size, total_items}}`" for
  evidence (~200+), findings (~400+), projects, decisions.
- **Assessment:** two distinct points. (a) **`page_size` cap is a genuine
  gap** — the contract's envelope names `page_size` but pins no maximum;
  the PDF treats a server-max as mandatory. This is a missing decision,
  not a conflict. (b) **offset vs cursor** — the contract's page-number +
  `total_items` shape is offset pagination. At our scale (per-owner,
  per-project, hundreds of items) offset is defensible and `total_items`
  gives the UI its "X of Y" affordance that cursor cannot cheaply provide.
  But the *shape* bakes in page/total; if lists later grow (multi-question
  workspace-cluster, cross-project listings) migrating to cursor is a
  breaking change under the contract's own "additive-only" evolution rule.
- **Recommendation:** (a) **add a server-enforced `page_size` max**
  (`Query(le=...)`) — low-cost, clearly correct per p.30 Q6. (b) Confirm
  offset is accepted given bounded per-project scale, and record cursor as
  the migration path in `web-api.md` / deferred.md; or adopt an
  opaque-cursor-capable envelope now if any listed collection is expected
  to grow unbounded.

---

## 2. Plan-time guidance

Architecture/structure recommendations for the plan draft. All page-cited.

- **Project layout — router / service / repository (p.33–35, Fig 4.1
  p.34).** The PDF's production layout: per-resource `APIRouter` files;
  `main.py` shrinks to composition (app creation, router mounting,
  lifespan); a single **composition root** `api/deps.py` wiring
  `Depends()` (p.35, p.38 Q6). Layering rule: routers translate HTTP↔domain
  and map exceptions to status codes (no business logic); services hold
  rules + orchestrate transactions and raise **domain** exceptions (no HTTP,
  no SQL); repositories own all data access (p.34 §4.3). This maps cleanly
  onto the contract's routers (projects, planning-turns, runs, check-ins,
  read models, SSE) and lets the read-model rewrite live in a repository
  layer over the real schema. Dependencies point inward only.
- **Async vs sync for the LLM run (p.64 Table 8.1 — "the most important
  table in this book").** Rule: `async def` + `await` for async-capable
  I/O; plain `def` (threadpool) for blocking libraries; offload heavy CPU
  via `run_in_executor`/worker. See finding 1.2 — the LLM run's steps must
  be offloaded, not run on the loop. REST read endpoints that only touch
  the DB via a sync SQLAlchemy session can be plain `def` (threadpool) or
  async with an async driver — pick one and be consistent (avoid `async
  def` + a blocking sync session call, the deadliest bug, p.64/p.68 Q1).
- **Background execution — do NOT reach for Celery, and know why (p.65–66
  §8.3, p.69 Q3).** The PDF's decision rule: work that must survive a
  restart belongs in a broker-backed queue (Celery); `BackgroundTasks` is
  in-process and lost on crash. Our contract has *chosen* the lossy path on
  purpose (honest interruption). So the guidance to apply is the *shape* of
  the job pattern (p.66 Fig 8.1: accept fast → 202/created + id → report
  status), realised here as `POST …/runs` (create run row) + SSE progress,
  **not** the Celery infrastructure. Don't let the review push Celery in —
  it's the deferred 017 resume-engine seam.
- **SSE / streaming (p.66–67 §8.4, p.69 Q5, p.77 Q2).** SSE
  (`StreamingResponse`, `media_type="text/event-stream"`) is the right
  primitive for one-way server push (progress, run events) — "most 'we need
  WebSockets' requirements are SSE-shaped" (p.70). SSE gets automatic
  reconnection via the browser's `Last-Event-ID`; **use the `id:` field
  keyed to the `event_log` sequence** so reconnect resumes replay exactly —
  this directly serves the contract's "idempotent rebuild from replay".
  Wrap the generator in `try/finally` (p.74 Listing 9.2) so cleanup runs on
  the constant client disconnects. At the edge, disable proxy buffering
  (`X-Accel-Buffering: no`, p.77 Q2) or SSE stalls. Note OpenAPI does not
  describe a stream body — the discriminated-union event models must be
  registered as components some other way (see 3.4) for the generated TS
  client to see them.
- **SQLAlchemy session / connection management (p.40–41, p.46 Q6/Q7).**
  Session-per-request as a **yield dependency** with commit-on-success /
  rollback-on-error / close-in-`finally` (p.41 Listing 5.1) gives every
  endpoint atomic semantics for free. Engine is one-per-process (owns the
  pool); set `pool_pre_ping=True` and `pool_recycle` below any LB/NAT idle
  timeout for cloud (p.46 Q7). **Caveat for our long-running run:** the
  request-scoped session closes when the dispatch response is sent — the
  in-process run must open and manage **its own** session lifecycle, and
  must **not hold a pooled connection while blocked on a steering pause**
  (that would exhaust the pool, p.43 GitLab pool-exhaustion case study).
  Plan the run's DB access as short transactions around event writes, not
  one long-held session.
- **One-active-run guard (p.45 Q3, p.44 order scenario).** The PDF's
  concurrency-guard idiom is a DB-level atomic check (`SELECT … FOR UPDATE`
  or an atomic `UPDATE … WHERE` with rowcount) — structural, not
  app-memory. The contract's "partial unique index or advisory lock" is
  squarely in this spirit; a partial unique index (`UNIQUE(project_id)
  WHERE status='active'`) is the cleanest structural guard.
- **Event_log / transactional outbox (p.45 Q3, p.66).** Writing the
  domain state change and its `event_log` row **in the same transaction**
  is the transactional-outbox pattern — it guarantees the durable event
  stream never diverges from state. Worth stating explicitly in the plan
  since replay correctness is a review-focus item.
- **Migrations (p.42–43 §5.5, p.45 Q4).** Always hand-review autogenerated
  Alembic (it mis-sees renames as drop+add and misses server defaults);
  test the `downgrade` path (the contract already requires up/down). Run
  migrations in CI (not `create_all`) so the migration chain itself is
  tested (p.59). The `project` lifecycle columns are all additive/nullable
  → a safe single expand migration.
- **Testing strategy (p.56–59, p.61 Q2/Q3).** Two tiers: **SQLite
  in-memory** with `StaticPool` for the bulk (business logic, contracts,
  serialization — p.59), **real Postgres** (testcontainers/CI service) for
  Postgres-specific behaviour (partial unique index, `FOR UPDATE`, the
  migration chain). The architectural payoff: `app.dependency_overrides`
  swaps the DB/auth/LLM seam in one line — no monkeypatching (p.57 Listing
  7.1, p.61 Q1). Unit-test services with fake repositories; integration-test
  the contract (status codes, 422 shapes, response_model filtering, authz)
  through `TestClient`. **Use `with TestClient(app) as client`** so lifespan
  runs — required to exercise the startup orphan sweep (p.63 Q8).
- **OpenAPI generation workflow (p.13, p.16 Q10, p.21 multi-tenant
  scenario).** Contract-in-code → `/openapi.json` is a build output, not a
  maintained artifact. CI snapshots it and fails on uncommunicated breaking
  changes; the generated client is downstream. This is exactly the
  contract's drift-check; the PDF confirms the workflow and the "one tag
  per resource/router" convention (p.31 Q9) which shapes the generated
  client's namespaces.
- **Auth as a dependency, not middleware (p.38 Q5, p.33 §4.1.1).** Prefer a
  `get_current_user` dependency (participates in OpenAPI security → `/docs`
  lock icon; handlers receive the user; public routes are explicit) over
  middleware. Router-level dependencies scope enforcement to a subtree.
  This fits the contract's "every data route authenticated" cleanly.

---

## 3. Build-time reference

Concrete practices with page cites for the build agent to go deeper.

- **Three-model separation (p.18 Listing 2.1, p.21 case study, p.22 Q2).**
  Separate `…Create` (inbound) / `…Update` (all-optional, PATCH) / `…Out`
  (outbound) Pydantic models. `response_model` acts as a **whitelist** —
  only declared fields serialize, even if the handler returns an ORM object
  (p.18, p.20). Prevents both mass-assignment and field leakage. Add
  `extra="forbid"` on inbound models to reject unexpected fields (p.21).
  For our read models this is the structural guard that internal payload
  keys / module names never leak (contract "Hyrum hygiene").
- **PATCH semantics (p.23 Q6, p.27, p.29 Q3, p.31 Q8).** PATCH model =
  every field `Optional` with no semantic default; apply with
  `model_dump(exclude_unset=True)` so "field omitted" (leave unchanged) is
  distinct from "field null" (clear). Directly relevant to the contract's
  `PATCH` rename (only `name`) and idempotent archive.
- **Field constraints → OpenAPI (p.19 Listing 2.3, p.24 Q8).** Declarative
  `Field(gt=, le=, min_length=, max_length=, pattern=)` and enum `Literal`s
  export into the schema and thus the generated TS client; custom
  `@field_validator` logic is opaque to the schema — prefer declarative
  constraints, document validators in `description`. Query params:
  whitelist `sort` via `pattern=` to prevent column injection (p.26/p.27).
- **Discriminated unions for SSE/check-in variants (p.19 nested models;
  general typed-contract theme).** Pydantic tagged unions (a `Literal`
  discriminator field) export as OpenAPI `oneOf` with a discriminator, so
  the generated client narrows on `type`/`kind` — this is the contract's
  "typed variants" pin. **Build subtlety:** a `StreamingResponse` endpoint
  does not advertise its frame schema in OpenAPI, so the event-union models
  won't appear automatically. Register them explicitly (e.g. reference the
  union from a documented response model, or add them to the app's schema
  components) so `openapi-typescript` emits them and the drift check covers
  them.
- **Single error envelope + overriding the 422 handler (p.23 Q5, p.27
  §3.3, p.63 Q9).** The PDF endorses one custom envelope across services
  and overriding the default handler (p.23). FastAPI's default validation
  error is `{"detail": [{loc, type, msg}, …]}`; clients parse `loc`/`type`
  programmatically. To honour the contract's `{error: {code, message,
  details?}}` while keeping field-level mapping, install a
  `RequestValidationError` handler that wraps the default `detail` list into
  `details` (preserve `loc`/`type`; treat `msg` text as non-contract).
  Never return `200` with an error body (p.27). Tests should assert on
  `loc`/`type` (contract), not `msg` strings (p.63 Q9).
- **JWT verification — Cognito is RS256/JWKS, NOT the PDF's HS256 example
  (p.49 Listing 6.1/6.2, p.52 Q1, p.55 Q9).** Pin the algorithm explicitly
  (`algorithms=[…]`) — the `alg=none` / RS-as-HMAC attacks (p.52 Q1) come
  from trusting the token header. Validate `exp`, `iss`, `aud` (p.49).
  **Do not copy the PDF's HS256 shared-secret pattern** — Cognito signs with
  RS256 and publishes public keys at a JWKS endpoint; verify against the
  fetched+cached JWKS. The dev issuer likewise uses a keypair (asymmetric),
  per the contract. `user_id = sub`. Return `401` (with
  `WWW-Authenticate: Bearer`) for missing/invalid tokens; object-ownership
  → `404` (finding 1.1).
- **Secrets & logging hygiene (p.51, p.54–55 Q9, p.88 Q7).** Secrets from
  env / secrets manager via `pydantic-settings` (`SecretStr` fields);
  validated at boot (missing config crashes startup, not the first request
  — p.82). Structured logs must **never** contain tokens, `Authorization`
  headers, secrets, or raw model-authored text; log a content hash / token
  counts instead. Reinforces the contract's "no secrets in bundle/env",
  "dev keys are dev-only", and "model-authored display strings untrusted".
- **CORS (p.50, p.54 Q7).** `CORSMiddleware` with an explicit origin list;
  `allow_origins=["*"]` + credentials is spec-forbidden. CORS protects
  browsers only — it is not access control; auth must never assume CORS
  blocked anything. Matches the contract's "CORS locked to the app origin".
- **httpx client in lifespan (p.65 Listing 8.1, p.70 Q6).** Any shared
  outbound HTTP client (the existing chain's egress) belongs in the lifespan
  handler with explicit timeouts and connection limits — per-request clients
  pay TCP+TLS handshakes and leak connections. Same per-process-singleton
  rule applies to the DB engine.
- **Timeout / cancellation / disconnect (p.65, p.70 Q7, p.74 Listing 9.2,
  p.77 Q2).** Explicit timeouts on every external call ("wait forever" is an
  outage). For SSE, the `try/finally` around the generator is where you
  release resources and stop work when the client disconnects mid-stream —
  relevant to the ephemeral tick channel and live tail.
- **Health probes (p.83 Listing 10.3, p.86 Q1).** Liveness (`/health/live`)
  checks **process only** — no DB (else a DB blip restarts every pod, p.84
  readiness-cascade case study). Readiness (`/health/ready`) checks critical
  deps + warm state. Only these stay unauthenticated (contract:
  "nothing unauthenticated beyond liveness/health").
- **Observability (p.83 §10.4, p.88 Q7/Q8).** RED metrics per endpoint +
  resource gauges (pool checkout wait, loop lag); OpenTelemetry auto-instru-
  ments FastAPI/httpx/SQLAlchemy; propagate a request/trace id into every
  log line. Alert on SLO burn / user-facing symptoms, not CPU. Thin in the
  contract — cheap wins available if the plan wants them.
- **N+1 (p.42 Listing 5.3, p.44 Q1).** The read-model rewrite (evidence,
  findings, decisions) is the classic N+1 surface. Use `selectinload` for
  collections, `joinedload` for to-one; add a per-request query-count
  assertion in tests (`assert query_count <= N`).
- **Performance / OOM (p.84 §10.5, p.89 Q10).** Bound every buffer:
  `page_size`/limit caps (finding 1.4), stream large reads rather than
  buffering. Measure before scaling; N+1 and loop-blocking dominate real
  latency.

---

## 4. Explicitly NOT applicable (so future readers don't misapply)

The PDF is a broad text; large parts do not fit this slice's scope or
conflict with pinned architecture.

- **Password hashing, OAuth2 password flow, the `/token` login endpoint,
  refresh-token storage/rotation (p.48–50 §6.2/6.3, p.53 Q5, p.52 Q2).**
  Cognito owns identity. This API is a **resource server that only
  *verifies* bearer tokens** — it issues none, hashes no passwords, stores
  no refresh tokens. No `users` table this slice (contract: verified claims
  *are* the identity). Ignore all password/login-issuance material.
- **HS256 shared-secret JWT example (p.49 Listing 6.1).** Wrong for Cognito
  (RS256/JWKS) and the dev issuer (keypair). See 3.6.
- **API keys / `X-API-Key` (p.50, p.55 Q10).** No machine-to-machine
  callers in this slice.
- **Celery / RQ / broker-backed workers (p.65–66, p.69 Q3).** Deliberately
  out. *(Updated 2026-07-21 after the contract's parked-pauses revision —
  the original "contract chose the lossy path" framing is superseded.)*
  Boundary durability now comes from Postgres (parking + per-component
  commits), not from where the task runs; a broker wouldn't close the
  remaining mid-component gap (a crashed Celery task also restarts from the
  task's start — that's the deferred 017 resume seam either way); separate
  worker processes would immediately need the deferred cross-process
  live-tail/unblocking seam (LISTEN/NOTIFY); and the broker is new
  infra-dependency weight belonging to the infra/CDK slice. Continuation
  dispatch is the preserved seam — walk segments are queue-shaped, so
  broker workers slot in behind it later if scale demands. Apply the
  job-pattern *shape* (create → id → out-of-band progress), not the worker
  infrastructure (see 2).
- **WebSockets (p.67, p.69 Q5).** Run progress is one-way server push → SSE
  is correct; the PDF agrees most such needs are SSE-shaped. No bidirectional
  channel here.
- **File uploads / `UploadFile` / S3 presigned (p.66–68).** Upload UI is
  explicitly OUT (owner-settled). No file-handling surface this slice.
- **Embeddings, vector DBs, pgvector, RAG ingestion/query pipelines
  (p.74 §9.3, p.78 Q5).** The synthesis/evidence chain is upstream of this
  API; the slice adds no retrieval/embedding surface.
- **LLM guardrails, output-validation-retry, prompt-injection defenses,
  `model_version` echoing (p.74 §9.4, p.75 Listing 9.3, p.79 Q7).** These
  live in the existing chain; the contract adds **no new prompt-bearing
  surface**. The one carry-over principle that *does* apply — "treat model
  output as untrusted at the boundary" (p.78 Q4) — is already the contract's
  render-time scrub of model-authored display strings.
- **Redis caching / rate limiting / token buckets (p.50, p.54 Q8, p.84
  §10.5).** No Redis in scope; server-state caching is the frontend's
  TanStack Query + event-sourced store. Rate limiting is not pinned; the
  one-active-run guard already bounds the expensive run-dispatch route, and
  every route is authenticated (not a public signup surface). A light note
  only — not a slice requirement.
- **Multi-worker/Gunicorn tuning, K8s HPA, PgBouncer, pool-sizing
  arithmetic, Docker/Compose specifics (p.43–44, p.81–82 §10.1/10.2,
  p.88 Q6).** Deployment is the deferred `infra/` slice. **Exception:** the
  *concurrency model decision* in finding 1.3 cannot be fully deferred —
  the in-process runner forces a single-instance-vs-scale-out choice the
  plan must at least record.
- **HITL review-queue with multi-item pending + claim/lock semantics (p.75
  §9.5, p.80 Q10).** The PDF's human-in-the-loop review API (`GET
  /reviews/pending`, `POST /reviews/{id}/decision`, confidence-threshold
  routing) is an excellent *conceptual* mirror of our check-in resource and
  worth reading as design reference — **but do not import its multi-pending
  queue + claim/lock model**: our invariant (contract strand 4) is **at most
  one pending check-in per active run by construction** (the runner blocks).
  No reviewer-collision / claim semantics needed.
- **SQLModel (p.42 §5.3, p.46 Q5).** The PDF offers it as an option; the
  repo already uses plain SQLAlchemy + explicit schemas. The PDF itself
  recommends explicit separation for "multi-team or security-sensitive
  codebases" — stay with the existing pattern; do not introduce SQLModel.
