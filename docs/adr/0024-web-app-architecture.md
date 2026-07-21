# ADR 0024 — Web-app foundation: schema-first API, durable transport, Cognito-shaped auth, monorepo hoist

**Status:** Proposed — accepted at the 025 plan gate (owner sign-off date
recorded there). Contract: `docs/tasks/025-web-app-foundation/contract.md`
(approved + adversarially adjudicated 2026-07-21).

## Context

The `demo-live-run` branch proved the product surface but was built to avoid
backend changes: registry-sidecar project lifecycle, an in-memory SSE bus,
no auth, hand-diverging mock/live contracts (the demo's #1 bug class). 025
replaces it with the production web application. The org has pinned AWS
Cognito for auth (owner, 2026-07-20), landing only when CDK `infra/` exists.

## Decisions

1. **One schema, two ends.** Pydantic models in `policy_atlas/api/contract/`
   are the single contract: OpenAPI is exported from them; the TypeScript
   client is generated (`openapi-typescript` types + `openapi-fetch` runtime);
   CI fails on drift. Hand-written parallel types are banned. SSE events and
   check-in kinds are discriminated unions registered as named components.
2. **The durable record is the only read substrate.** All read models,
   pending check-ins, and decision history serve from Postgres
   (`event_log`, `steering_history`, result tables). SSE is transport, not
   truth: backlog replay to a snapshotted sequence + live tail from
   sequence+1 (atomic cutoff), our own reconnect cursor, ephemeral ticks
   marked and never persisted. Pending-vs-history: a pause without its
   decision is pending (at most one per active run); replayed decided pauses
   render as history, never as arrivals.
3. **Auth is a Cognito-shaped OIDC seam, not a Cognito integration.**
   Backend: JWT bearer verification (alg pinned, iss/aud/exp/JWKS) proven by
   a provider-conformance suite against two asymmetric issuers with key
   rotation; a visibly-non-production dev issuer locally. Frontend: a
   generic OIDC adapter owns login/refresh/logout. Cognito cutover = config.
   Identity = verified claims (`sub`); no users table (026+ seam).
   Cross-owner access returns **404 indistinguishable from absent** (BOLA);
   403 is reserved for future role failures. SSE authenticates via
   fetch-stream bearer headers; tokens never in query strings; no cookies →
   no CSRF machinery, by construction.
4. **Project lifecycle is real backend semantics.** `project` gains
   name/question/lifecycle columns; `status ∈ active | archived` only (run
   state lives on `capability_run`, presentation derived, never cached);
   delete = idempotent archive (audit/FOI: rows retained; hard purge
   deferred); rename/archive emit transactional audit events; migration
   backfills existing rows, NULL-owner rows intentionally API-inaccessible
   with documented DB recovery.
5. **Monorepo hoist now.** Python → `backend/`, new `frontend/`, `infra/`
   reserved (deferred.md pin, amended spelling 2026-07-20). Import-neutral;
   tooling paths only; revert-clean.
6. **Deployment posture: one API instance, one worker process.** Runs execute
   off the event loop in bounded executors (a blocking walk must never starve
   the loop). Pause-unblocking and live tail are process-local; the
   cross-instance mechanism (Postgres LISTEN/NOTIFY first candidate) is a
   named deferred seam for the infra slice. Broker-backed workers
   (Celery/RQ) are out: boundary durability is Postgres's job; the
   continuation-dispatch seam preserves the later move.
7. **Serialization primitive:** per-project row lock (`SELECT … FOR UPDATE`)
   guards run dispatch (one active run per project), check-in answers
   (double-answer → one decision + one 409), and continuation claims.
8. **Frontend stack:** React (19 + compiler pending the pinned compat spike,
   else 18), Vite, TS strict, Tailwind themed from the Nesta brand tokens,
   TanStack Query over the generated client + an event-sourced SSE reducer,
   URL-addressable dossier/filters, npm. Component primitives: visual-identity
   components hand-built; behaviour-bearing components shadcn-style copied-in
   over Radix. No component-library or design-system dependency (Astryx,
   MUI, Chakra, Mantine, daisyUI considered and rejected — contract rev
   history). Licensed fonts load locally untracked, never committed (CI
   guard); deployed delivery is an infra-slice seam.

## Consequences

- The API is a public interface: additive-only evolution under `/api/v1`;
  error envelope + status mapping are contract; pagination capped.
- The demo branch becomes historical evidence only.
- 026 (co-pilot Q&A + transcript store) builds on this auth/user identity and
  the `capability_run.session_id` anchor.
- Deferred with named triggers: cross-instance scale-out (infra slice),
  hard purge, users/profile table (026), designed component-progress
  protocol, broker workers (scale), cursor pagination (cross-project lists).
