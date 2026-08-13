# Knowledge update log

## 2026-08-13 (task 031 step 8)
* **Creation**: Added
  [success-map-is-stale-on-the-failure-path](success-map-is-stale-on-the-failure-path.md)
  — `successful_runs` is written only on the success path, but the runner still presents
  the component's steer point when it fails, so P1 rendered round 1's counts and queries
  under round 2's label. Found by the adversarial lane after the contract verifier had
  certified the success path; both were right about different paths.
* **Creation**: Added
  [read-the-producing-components-summary](read-the-producing-components-summary.md) — the
  read model displays the number the producing component already persisted rather than
  recounting the same population, so the check-in chip and its per-backend line cannot
  disagree. Carries the shared-read-helper corollary (`_executed_queries` right for P2,
  wrong for P1).
* **Creation**: Added
  [residual-counted-after-narrowing](residual-counted-after-narrowing.md) — counting
  "Not reported" inside the loop over already-scoped rows makes the add-up invariant true
  at every scope for free; the payload adding up is not the drawn chart adding up.
* **Update**: [guard-tests-name-real-invariant](guard-tests-name-real-invariant.md) — a
  guard can die by evaluating to nothing, not only by being routed around: `0 == sum(())`
  and a scope test whose fixture never entered the narrowed scope both passed
  unconditionally. Ask what value would make it fail; mutation-check when unsure. Plus
  the stub-search fixture trap (a plain walk acquires 0 new sources).

## 2026-08-06 (task 030)
* **Update**: [result-caps-need-distribution-rule](result-caps-need-distribution-rule.md) — caps
  owner-set at rapid 50 / standard 100 / deep 200 per backend per round; the wall clock is gone at
  every depth (the runner's round gate + record caps replaced it), and the multi-round loop the
  caps were sized for is now actually wired (runner-orchestrated rounds, task 030).

## 2026-08-05 (task 028 step 9 — owner live review)
* **Creation**: Added
  [custom-text-tokens-need-tailwind-merge-registration](custom-text-tokens-need-tailwind-merge-registration.md)
  — every brand primary shipped ink-on-blue with all gates green (twMerge classified the
  028 type-scale tokens as colours and stripped text-white); owner-caught on the live app.

## 2026-08-05 (task 028 step 8)
* **Creation**: Added
  [retiring-ui-affordance-keeps-grammar-channel](retiring-ui-affordance-keeps-grammar-channel.md),
  [content-keyed-ids-uuid5](content-keyed-ids-uuid5.md),
  [server-key-label-maps-one-home-raw-fixtures](server-key-label-maps-one-home-raw-fixtures.md)
  — task 028 (UX refinement): authored from BOTH the build's knowledge candidates and the
  review stack's findings (014 retro rule).
* **Update**: [column-churn-migrations-need-scratch-db](column-churn-migrations-need-scratch-db.md)
  — the predicted exhaustion happened (TooManyColumns mid-roundtrip → 627-failure cascade,
  recognition signature + remedy recorded); [tested-in-isolation-is-not-wired](tested-in-isolation-is-not-wired.md)
  — every offered floor option needs a test that ANSWERS a pause with it (028 M1, dead FG
  regroup); [delegated-executor-practices](delegated-executor-practices.md) — Codex-authored
  tests confirmed the dominant delegated-defect surface a third time; shared-file concurrent
  edits merge but mid-flight typecheck cross-fires;
  [wire-field-additions-break-all-construction-sites](wire-field-additions-break-all-construction-sites.md)
  — transport-twin corollary + schema-requires-what-the-prompt-forbids (endorsements,
  watch_authoring_v2); [guard-tests-name-real-invariant](guard-tests-name-real-invariant.md)
  — the guard's selector is part of its invariant (prompt-guard filename glob);
  [live-check-drive-runbook](live-check-drive-runbook.md) — Playwright exact:true vs brand
  copy, mock/live serialisation, LIVE_ALLOW_API_TAKEOVER.
* **Declined with reasons**: dev-DB-migrate gotcha (already in the runbook, 027 entry);
  Codex-no-Docker (already a delegated-practices rule, 027); nulls-first staging
  (already the wire-additions concept's core); a standalone "review-economy" concept
  (process, lives in the task-cycle skill + memory, not product knowledge).
## 2026-08-04 (task 029)
* **Update**: [result-caps-need-distribution-rule](result-caps-need-distribution-rule.md) — the
  total-volume bound named in the rule now exists (`record_cap_per_backend`, applied in
  `acquire_sources` after a rank-interleaved merge and after dedup), and a third instance of the
  same defect family is recorded: a *time* budget over an ordered fan-out truncates a specific set
  of queries and providers, not a random sample. Standard/deep wall clocks removed for that reason;
  rapid keeps its clock because latency is the requirement there, not a proxy for cost.

## 2026-07-28
* **Creation**: Added [cdk-poweruser-deploy-boundaries](cdk-poweruser-deploy-boundaries.md),
  [noop-deploys-dont-reassert-template-pins](noop-deploys-dont-reassert-template-pins.md),
  [live-idp-cold-path-and-signout](live-idp-cold-path-and-signout.md),
  [docker-save-layout-image-store](docker-save-layout-image-store.md),
  [cdk-synth-tests-lookups-and-hidden-lambdas](cdk-synth-tests-lookups-and-hidden-lambdas.md),
  [pyjwt-aud-verified-by-default](pyjwt-aud-verified-by-default.md),
  [uv-src-layout-image-pattern](uv-src-layout-image-pattern.md) — task 026 (infra deployment):
  build knowledge candidates + review-stack findings, authored from both sources (014 retro rule).
* **Update**: [testing-database](testing-database.md) — persisting harnesses need a disposable
  per-harness DB (026 smoke); [synthesise-is-run-terminus](synthesise-is-run-terminus.md) — UI/spec
  assertions target the acquire stage, never characterise (026 smoke spec bite);
  [macos-swap-presents-as-docker-wedge](macos-swap-presents-as-docker-wedge.md) — second wedge
  family: VM network path, full process kill required (026 E).

## 2026-07-15 (task 023 step-9 riders)
* **Retirement**: [citation-flag-dont-drop](citation-flag-dont-drop.md) marked RETIRED — its mechanism (`produce_grounded_block`'s pre-raise citation/annotation writes) was deleted when the owner directed dissolving `grounding.py` at the step-9 gate (`content_hash` → `core/hashing.py`; the production-dead grounded-block leg + tests removed). The flag-don't-drop principle stays spec-level and lives in the extract-side verification chain.

## 2026-07-14 (task 023 step 8)
* **Creation**: Added [sumprod-hot-path-vector-maths](sumprod-hot-path-vector-maths.md) — math.sumprod + construction-time norm precompute as the stdlib answer to hot-path vector maths; extended-precision near-tie reordering makes it observable-change class (023 WP10c, verified by two review lanes).
* **Creation**: Added [unmarked-default-naming-smell](unmarked-default-naming-smell.md) — the first-built variant hoarding generic names as a repeatable review lens; the IOF/ICF rename set was the instance (owner-caught at the 023 review).
* **Update**: [testing-database](testing-database.md) — parallel-lane fences include the shared test DB (023 contamination recurrence, twice: concurrent lane done-checks + the ad-hoc smoke's committed rows); index hook also corrected — it still described the pre-flip task-001 convention.
* **Declined**: gate-reading discipline (exit codes direct, `| tail` eats them, no `&&`-chained commits, done-checks = the gate's exact commands) → process lesson, recorded as a 2026-07-14 entry in `docs/agentic-ops/failure-log.md`; zero-egress-smoke-in-suite reframing → already authored at build step 6 as [orchestrate-stub-smoke](orchestrate-stub-smoke.md) (the review stack verified the reframing against the as-built test).

## 2026-07-14 (task 023 build, step 6)
* **Creation**: Added [orchestrate-stub-smoke](orchestrate-stub-smoke.md) — orchestrate as the one check vehicle after skeleton's retirement. Amended same day (owner correction at step-6 close): the automated gate smoke is the suite's own `test_full_stub_end_to_end_mints_artefact` (self-cleaning); the manual no-key command is the ad-hoc/live vehicle only, with the commits-rows caveat scoped to ad-hoc runs. Authored in-build per the approved 023 plan (Phase H); remaining 023 knowledge candidates land at step 8 from verification.md § Review handoff.
* **Update**: [reasoning-model-output-cap](reasoning-model-output-cap.md) — living-doc sweep: `extract_prompt.py` citation repointed to `evidence_base/extract/iof_prompt.py` (023 regroup).

## 2026-07-14 (task 022 step 8)
* **Creation**: Added [two-stage-clustering-closes-partition-cliff](two-stage-clustering-closes-partition-cliff.md) — the ~184-value duplicate-id cliff was the exhaustive-partition response format, not model capacity (0/9 arms fabricated ids); same framing change removed over-fragmentation; component sentinels forbidden in discovery (022 replays + review stack).
* **Creation**: Added [live-only-reachability-coverage-class](live-only-reachability-coverage-class.md) — three live-only bugs behind a green 1300-test suite: judge echo, enriched-record strict re-validation, tracing-enabled-only branch (022 live checks).
* **Creation**: Added [langfuse-cost-by-time-window](langfuse-cost-by-time-window.md) — per-run $ by summing trace totalCost over the run's window; serialize arms; same-source before/after honesty (022 cost protocol).
* **Update**: [judge-envelope-defines-verdicts](judge-envelope-defines-verdicts.md) — rules 4+5: identical-envelope variance baseline applied to EVERY reported metric (the 17(i) unspanned over-read the review stack corrected), and visible envelope data invites echo — validators anticipate verdicts for ids never asked about (022 live bug 1 + re-judge replay).
* **Update**: [facet-partition-value-list-scale-limit](facet-partition-value-list-scale-limit.md) — Status: CLOSED addendum pointing to the two-stage concept; group_facet_v1 deleted at the 022 review stack.
* **Declined**: nullable-wire-field ripples into few-shot examples → already covered by [wire-field-additions-break-all-construction-sites](wire-field-additions-break-all-construction-sites.md) (icf_v2 re-verified it, third confirmation — no new content); seeded-then-patched selection rows need the characterisation chain → test-helper locality, carried by the fixed helper + its test, not durable system knowledge; Codex parallel-write disjoint-file safety + Codex-authored tests as the dominant defect surface → delegation process lessons, recorded in `docs/agentic-ops/harness.md` (022 step 8).

## 2026-07-13 (task 021 step 8)
* **Creation**: Added [removing-shape-tolerance-sweeps-every-reader](removing-shape-tolerance-sweeps-every-reader.md) — dropping old-shape tolerance is only done when every reader fails closed; the 021 amendment's missed twin fallback in synthesise, caught by the review stack.
* **Creation**: Added [validate-effective-defaults-not-explicit-args](validate-effective-defaults-not-explicit-args.md) — query_findings' kind/filter guard skipped the omitted-kinds default path; validate resolved values, test the default path (021 Codex adversarial).
* **Creation**: Added [facet-partition-value-list-scale-limit](facet-partition-value-list-scale-limit.md) — duplicate value ids at ~184 distinct values, 4/4 live attempts, reasons persisted; REQUIRED Slice-C facet-redesign input (021 live check).
* **Creation**: Added [refine-replay-revert-exit](refine-replay-revert-exit.md) — round 3 regressed vs round 2 on extract_icf_v1; the loop's revert exit is the mechanism, not ceremony (021 phase C).
* **Declined**: wire-model few-shot carriage cost → already fully covered by [wire-field-additions-break-all-construction-sites](wire-field-additions-break-all-construction-sites.md) (021's `setting` rider re-verified it); shared-projection keys lesson → superseded same slice by the owner's tolerance removal; pdftotext probe qv artefact → probe-harness quirk recorded in verification.md (the live pipeline chunks from the ingest parser); specification-vs-finding frontier → lives in deferred.md's `intervention_specification` candidate, the eval slice owns its measurement; Codex clean-tree discipline → process lesson, recorded as a 2026-07-13 entry in `docs/agentic-ops/failure-log.md`.

## 2026-07-12 (task 020 step 8)
* **Creation**: Added [fingerprint-covers-subcomponent-knobs](fingerprint-covers-subcomponent-knobs.md) — the vetter's model/effort are fingerprint components; the 018-latent gap the 020 review stack's Codex adversarial lane caught and fixed, per-knob test-pinned.
* **Creation**: Added [wire-field-additions-break-all-construction-sites](wire-field-additions-break-all-construction-sites.md) — all-fields-required wire models + import-time few-shot pre-flight; nulls-first staging across schema/prompt phases (020 A/B).
* **Creation**: Added [replay-diff-prophylactic-vs-corrective](replay-diff-prophylactic-vs-corrective.md) — 0-flip pre/post replay reads as "pins behaviour", not "fixed a failure"; record which honestly (020 vetter v3).
* **Creation**: Added [run-component-driver-for-scoped-live-checks](run-component-driver-for-scoped-live-checks.md) — skeleton._run_component as the sanctioned dev-DB live-check driver; substrate discipline (reuse screened selection, never re-search) (020 live check).
* **Update**: [run-id-fk-shapes-audit-carriers](run-id-fk-shapes-audit-carriers.md) — annotation's transitive run reach (block → artefact) + the newest-first + `payload ? 'cited_finding_ids'` query shape (020 live check).
* **Declined**: codex mid-turn-death partial-diff salvage + duplicate-constant wart grep, mypy stale-cache false attr-defined, and the accidental node_modules commit (no node ignores existed) → process lessons, recorded as 2026-07-12 entries in `docs/agentic-ops/failure-log.md`; finding-grain geography's empirical validation (11 distinct geographies in one realist review) and submission-site provenance semantics → carried by ADR 0016 + verification.md, not re-recorded; "Visit a Heat Pump" geography over-fill → eval-slice ground-truth input, recorded in verification.md § Review findings.

## 2026-07-12 (task 019 step 8)
* **Creation**: Added [executor-fanout-context-and-usage](executor-fanout-context-and-usage.md) — copy_context at submit carries Langfuse span context + structlog contextvars in one mechanism; workers return usage, the submitting thread accumulates (019 items 4/7a/11, D1-trace-verified).
* **Creation**: Added [prompt-honesty-rules-route-around-new-capability](prompt-honesty-rules-route-around-new-capability.md) — an earlier honesty rule silently defeats a new capability line until the prompt states which reading selects which surface; only replay catches it (019 planner replay; first entry in a new Prompting index section).
* **Creation**: Added [coverage-base-project-pool-wide](coverage-base-project-pool-wide.md) — pool-wide per-question screening; scope-isolation tests assert `unscreened`, not absence (019 deviation 3).
* **Creation**: Added [pytest-socket-process-local](pytest-socket-process-local.md) — process-local deny, multiprocessing guards stay; `SocketConnectBlockedError` is not a `SocketBlockedError` subclass (019 A3).
* **Creation**: Added [scope-surface-compiles-within-backend-scope](scope-surface-compiles-within-backend-scope.md) — plan-time validation and compile must agree on backend scope or approved plans die at acquire (019 review stack, adversarial MAJOR + fix).
* **Creation**: Added [capability-gated-dispatch-fails-closed](capability-gated-dispatch-fails-closed.md) — hasattr dispatch never selects between enforcing and not enforcing (019 review stack, convergent Claude+Codex finding + fix).
* **Update**: [overton-filter-values-display-names](overton-filter-values-display-names.md) — no enumeration endpoint (allowlists only by per-candidate probing; 265 pp=1 calls); Overton short-name idiom + "IGO"; `source_country` single-valued with silent multi-value failure (019 plan probes + build).
* **Update**: stale step names in [structured-output-prompts-pin-key-vocabulary](structured-output-prompts-pin-key-vocabulary.md) and [compile-target-parity-covers-composed-wholes](compile-target-parity-covers-composed-wholes.md) — `screen_stage2` → `screen_full` (019 rename, living-doc sweep).
* **Declined**: wall-clock-breach plumbing shape (task-specific; carried by the acquire code, its tests, and 019 verification.md); dev-DB migration smoke + trace-attribution-by-project_id + codex-sandbox DB-test lessons → process lessons, recorded as two 2026-07-12 entries in `docs/agentic-ops/failure-log.md` (the codex-sandbox one also closes 018's dangling "recorded in failure-log" pointer — the entry never existed; reconcile miss now fixed).

## 2026-07-11 (task 018 step 8)
* **Creation**: Added [span-anchoring-text-not-offsets](span-anchoring-text-not-offsets.md) — model-facing wires carry verbatim text, never offsets; splice repair rebuilds offsets one-pass by construction; persist-time round-trip assertion (018 B3, B smoke re-proof).
* **Creation**: Added [judge-envelope-defines-verdicts](judge-envelope-defines-verdicts.md) — tier distributions incomparable across envelope versions; verification-grade A/B protocol; inspect flags before recalibrating an asymmetric judge rule (018 B3/B4).
* **Creation**: Added [overton-filter-values-display-names](overton-filter-values-display-names.md) — provider-side silent zero on wrong filter-value vocabulary; live-probe values, not just keys (018 B2).
* **Update**: [reasoning-model-output-cap](reasoning-model-output-cap.md) — effort × cap validated together per surface with a live A/B; xhigh non-monotonicity confirmed in-house (classify keep-high verdict, on quality); direct-backend A/B drivers keep pinned substrates uncontaminated (018 B4).
* **Promoted to spec**: the prompting doctrine (research rules + loop method + agent-loop conventions) → [docs/specs/system/prompting.md](../specs/system/prompting.md) — owner-seeded step-8 item; carries the loop-method lessons (under-damped rule pairs → flag-not-drop judge escape hatch; cache-discounted cost curves; compile-your-probes; prompt capability lines are registry readers).
* **Declined**: contract-pin replayability check, concurrent-suite test-DB contention, codex-sandbox DB limits, reviewer-agents-must-not-run-the-suite → process lessons, recorded in `docs/agentic-ops/failure-log.md`, not product knowledge. `run:` trace attach guard (C-loop eye note, not yet load-bearing); future-target rule dropping BAU projections (eval-slice watch item, recorded in 018 verification.md); codex-exhaustion fallback (already durable in agentic-ops routing docs).

## 2026-07-10 (task 017 step 8)
* **Creation**: Added [alembic-roundtrip-explicit-revisions](alembic-roundtrip-explicit-revisions.md) — explicit downgrade targets; uncommitted seeds across DDL on a second connection hang silently behind FK-dependent DROPs (017 build, 14-minute hang).
* **Creation**: Added [process-start-deadlines-need-spawn-headroom](process-start-deadlines-need-spawn-headroom.md) — a Process.start() deadline clock asserts spawn+import<deadline and inverts under host load (017 build).
* **Creation**: Added [macos-swap-presents-as-docker-wedge](macos-swap-presents-as-docker-wedge.md) — first Runbook entry; swap exhaustion presents as a Docker Desktop wedge, check `sysctl vm.swapusage` first (017 build incident).
* **Creation**: Added [structured-output-prompts-pin-key-vocabulary](structured-output-prompts-pin-key-vocabulary.md) — pin exact dict keys and state cross-field constraints as hard prompt rules; the fail-closed loop is the recovery surface (017 live check).
* **Creation**: Added [run-id-fk-shapes-audit-carriers](run-id-fk-shapes-audit-carriers.md) — no run, no event: the carrier decision (table-first / outcome-object / re-run provenance) recurred three times in 017.
* **Creation**: Added [two-phase-run-lifecycle-evented-vs-escaped](two-phase-run-lifecycle-evented-vs-escaped.md) — evented failure vs escaped exception; identity-first commit makes the failure backstop's FK trivial (017, decision 8).
* **Creation**: Added [compile-target-parity-covers-composed-wholes](compile-target-parity-covers-composed-wholes.md) — parity checks compose with the real composer against the real bound; containment for canonicalising round-trips; registries for runtime-consumed names (017 review stack, three instances of one class).
* **Update**: [model-output-nul-scrub](model-output-nul-scrub.md) — the planner became `_scrub_nul`'s second consumer; the scrub must be recursive over the whole record (017 review stack).
* **Declined**: weight_emphasis multiplier semantics (already carried by `steering.py`'s constants comment + rank-shift tests); planner ~20–30 s/turn latency (an 018 surface input, carried in 017's review handoff, not durable knowledge).

## 2026-07-10 (task 016 step 8)
* **Creation**: Added [execution-options-statement-not-connection](execution-options-statement-not-connection.md) — Connection-level `execution_options` is sticky and wrapped subsequent INSERTs in server-side cursors, red-lining three stage-2 tests at the phase-3 gate (task 016).
* **Creation**: Added [reserve-then-shrink-byte-budgets](reserve-then-shrink-byte-budgets.md) — reserve the per-item cap up front and shrink on completion, or in-flight holders on a shared budget can deadlock; found by lead review of the composed pipeline, not any component's tests (task 016).
* **Creation**: Added [pip-audit-environment-mode-under-uv](pip-audit-environment-mode-under-uv.md) — `pip-audit -r` SIGABRTs under uv-managed CPython on macOS; environment-mode audit over the synced lockfile is the CI-parity fix (task 016 deviation 1).
* **Creation**: Added [httpcore-origin-pooling-pinned-ip](httpcore-origin-pooling-pinned-ip.md) — SSRF-safe IP pinning must live in a custom `NetworkBackend.connect_tcp`, not a rewritten URL, or pooling and SNI break (task 016 plan-stage review blocker #3).
* **Creation**: Added [timing-asserts-injected-clock-logs-corroborate](timing-asserts-injected-clock-logs-corroborate.md) — politeness timing is asserted on an injected clock; live log timestamps only corroborate and can show jittered sub-interval gaps (016 live check).
* **Creation**: Added [http-403-is-usually-bot-blocking](http-403-is-usually-bot-blocking.md) — 403s from document hosts are bot-blocking unless corroborated as a paywall; 5 of 7 016 live-check failures were bot-blocks, zero corroborated paywalls.
* **Creation**: Added [isolation-belts-reraise-config-errors](isolation-belts-reraise-config-errors.md) — a per-item isolation belt swallowed a missing-fixture-corpus `FileNotFoundError` into per-doc `fetch_error` rows, exiting green over a systemic misconfiguration (016 review stack).
* **Creation**: Added [ip-refusal-allowlist-not-denylist](ip-refusal-allowlist-not-denylist.md) — IP refusal is allowlist-shaped (`not ip.is_global`); Python's `is_private` misses RFC 6598 CGNAT space, found by the 016 security lane's bypass-family testing.

## 2026-07-09 (task 015 step 8)
* **Creation**: Added
  [result-caps-need-distribution-rule](result-caps-need-distribution-rule.md) — a total
  cap needs a per-call distribution rule or the fan-out silently collapses to one
  load-bearing query (015 live-check finding, fixed in-slice as `_distribute_quota`).
  **Superseded 2026-08-04** — `_distribute_quota` became the next bug (dividing a
  shared cap across a widened fan-out gave 5 results per query). The concept is
  rewritten: caps belong per call, sized against the provider page; total volume is
  a separate bound.
* **Creation**: Added
  [guard-tests-name-real-invariant](guard-tests-name-real-invariant.md) — the 007
  zero-egress guard's importlib dodge (015 build); guards name their invariant, evasion
  is a defect even on green CI.
* **Creation**: Added
  [embedded-values-escape-wire-grammar](embedded-values-escape-wire-grammar.md) — the
  comma-borne OpenAlex filter injection (015 review stack, convergent across both
  heterogeneous lanes); sanitizers must be wire-grammar-aware.
* **Update**: [synthesise-is-run-terminus](synthesise-is-run-terminus.md) gained the
  substrate corollary — synthesise refuses envelope-only corpora
  (`no_groundable_substrate`), so no acquire-only chain can mint until 016; hit live at
  the 015 chain smoke (contract rev 3.14's wording corrected via components flow-back).
* **Adjudicated, not authored** (015 build candidates): "deep search's judge is free" —
  recorded in ADR 0012 decision 3 + verification evidence, no separate concept;
  429-burst behaviour → the cache-before-throttle seam note (deferred.md, task-015
  section); characterise live-corpus wobbles → deferred.md robustness entry (a work
  item, not durable learning); Overton tag-layer richness → a scale note on the
  filter-vocabulary seam entry.

## 2026-07-09
* **Creation**: Added
  [synthesise-is-run-terminus](synthesise-is-run-terminus.md) — every run ends in
  synthesise (the artefact-minting terminus); characterise and the composition generally
  are plan choices. Captured at the 015 contract gate after the mistake (chains described
  as ending in characterise) recurred across slices; the 015 smoke chain was corrected
  under it (contract rev 3.9). Verified against components.md §9 and the merged 013
  skeleton — not new-slice code, so it lands ahead of 015's PR by exception to the
  in-implementing-PR rule.

## 2026-07-08
* **Creation**: Added
  [effective-screen-row-read-rule](effective-screen-row-read-rule.md) — multiple screening
  rows per doc (stages + failed retries) make the effective-row helper the only legal read;
  the rule binds write paths too — the appraise write-path gap was the 014 review stack's
  unique-to-adversarial-lane find.
* **Creation**: Added
  [untrusted-prompt-fields-json-records](untrusted-prompt-fields-json-records.md) — untrusted
  fields enter prompts only inside `json.dumps` records; the sanitizer preserves newlines, so
  raw interpolation is the breach shape (014 review stack, security lane's stage-2 title
  finding).

## 2026-07-07
* **Creation**: Added
  [facet-grouping-exhaustive-partition](facet-grouping-exhaustive-partition.md) — the
  grouped set is exactly the referenced run's finding set, residuals counted never
  dropped, sum identities enforced at write (task 012).
* **Creation**: Added
  [assert-on-row-not-summary](assert-on-row-not-summary.md) — contract-required keys must
  be asserted on the persisted row, not the completed-event summary; the two drift (task
  012 review stack, the unique-to-adversarial-lane finding).
* **Creation**: Added
  [grounding-location-from-verification](grounding-location-from-verification.md) — a
  model-emitted location is a claim by untrusted output; dereferenceable location fields
  derive from verified spans (task 011 review stack, the convergent security + adversarial
  finding).
* **Creation**: Added
  [reasoning-model-output-cap](reasoning-model-output-cap.md) — `max_completion_tokens`
  covers reasoning + output on gpt-5-class models; an output-sized cap truncates real
  answers (task 011 live evidence, deviation 2).
* **Creation**: Added
  [model-output-nul-scrub](model-output-nul-scrub.md) — Postgres rejects U+0000 in
  TEXT/JSONB; model output is scrubbed once at the backend boundary (task 011 live
  evidence, deviation 3).
* **Creation**: Added
  [directive-parse-malformed-vs-unknown](directive-parse-malformed-vs-unknown.md) — untrusted
  execution-bearing JSONB inputs parse fail-closed on structural malformation (bounded
  strings/collections, static messages) but flag unknown column/tag references non-fatally;
  the split both 010 review families converged on (task 010).

## 2026-07-06
* **Creation**: Added
  [llm-schema-valid-empty-output](llm-schema-valid-empty-output.md) — structured outputs
  guarantee shape, never completeness; validate counts against the input set in code
  (gpt-5-nano returned `{"assignments":[]}` schema-perfectly on realistic batches; task 009
  live evidence). First entry in a new "Integration quirks" index section.
* **Creation**: Added
  [langfuse-host-must-be-explicit](langfuse-host-must-be-explicit.md) — the Langfuse SDK
  defaults its endpoint to the SaaS cloud when no host is set; with full-I/O traces
  `get_langfuse()` requires an explicit host and raises on partial config (task 009 review
  stack, convergent security + adversarial finding).

## 2026-07-05
* **Creation**: Added
  [fulltext-chunk-hash-determinism](fulltext-chunk-hash-determinism.md) — same bytes must hash
  the same in every process; pymupdf4llm 0.3.4's id()-keyed cache breaks it, source-patched at
  import with the fan-out determinism test as backstop (task 008).
* **Creation**: Added
  [sanitized-fixtures-audit-against-raw](sanitized-fixtures-audit-against-raw.md) — verify
  recorder sanitization by substring-auditing raw vs committed fixture (list items inherit the
  list's key; rare fields like grant IDs slip key lists; use a neutral fake lexicon) (task 007).

## 2026-07-03
* **Creation**: Added
  [rubric-domain-defines-appraisability](rubric-domain-defines-appraisability.md) — a scoring
  mapping's domain defines eligibility (absence = skip-and-count); counting buckets have two
  lifetimes (inserted-this-call vs recomputed-from-state); int dict keys become strings in
  JSONB payloads (task 006).

## 2026-07-01
* **Creation**: Added [per-doc-fanout-idempotent](per-doc-fanout-idempotent.md) — the
  `WHERE NOT EXISTS` guard that makes per-document fan-out functions safe to re-run (task 005).
* **Creation**: Added
  [per-doc-fanout-isolates-decision-call](per-doc-fanout-isolates-decision-call.md) — wrap only
  the per-document decision call, never the insert, so one bad document can't abort the batch or
  poison the transaction (task 005).
* **Creation**: Added
  [harness-scope-lookup-project-scoped](harness-scope-lookup-project-scoped.md) — a harness scope
  lookup must filter by `project_id`, not just the scope ID, or cross-project scope use is
  silently accepted (task 005).

## 2026-06-29
* **Creation**: Added [upload-no-dedup](upload-no-dedup.md) — the no-content-hash-dedup invariant for uploaded sources (task 003).
* **Creation**: Added [citation-flag-dont-drop](citation-flag-dont-drop.md) — citation row written before GroundingError; fail evidence survives committed transactions via the harness (task 003).

## 2026-06-24
* **Initialization**: Created the bundle — index + four verified concepts from task 001
  ([structlog-only](logging-structlog.md), [test DB](testing-database.md),
  [event-log sequence](event-log-sequence.md), [block content_hash](block-content-hash.md)).
* **Update**: Added the [plan→config compile fails-closed](plan-compile-fails-closed.md) invariant —
  also verified by task 001, missed in the initial seed.
