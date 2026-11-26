---
okf_version: "0.2"
---

# Knowledge index

Verified facts about how Policy Atlas is built and how it behaves, grouped by part of the system.
Before you change a part, read the lines in its group and open the concepts that apply.

`docs/specs/` holds design intent. This bundle holds what is built and checked. If a test, hook or
command enforces a fact, the fact does not belong here. Add or correct a concept in the pull
request that changes the code, and run `make okf-validate`.

## API and auth (`backend/src/policy_atlas/api`)

* [Widening an auth boundary needs sweeps for both anonymous and signed-in outsiders](auth-boundary-widening-needs-both-caller-sweeps.md) - when a route becomes public or conditionally public.
* [A read on the anonymous public leg carries no person's name](public-leg-reads-carry-no-names.md) - when you add a read model served without sign-in.
* [PyJWT verifies `aud` by default whenever the claim is present](pyjwt-aud-verified-by-default.md) - when you change token verification.
* [A request size limit in an ASGI middleware: order, disconnect, what tests prove](asgi-body-limit-middleware.md) - when you change the body limit or add a middleware that writes its own reply.
* [An attacker-chosen cache key cannot bound outbound fetches](bound-the-fetch-not-the-key.md) - when you cache lookups keyed on token content (JWKS).
* [Cross-process turn correctness lives in the database row](db-row-is-the-single-flight-authority.md) - when you add a guard against two concurrent turns or walks.
* [A mutation that commits and then waits returns what it made](mutation-never-fails-after-its-commit.md) - when a route commits and then waits for async work.
* [A read model pins the referencing row's foreign key, never latest-by-date](read-model-refs-pin-by-fk.md) - when a read model resolves another table's payload.
* [A displayed count comes from the producing component's summary](read-the-producing-components-summary.md) - when you show a count from a run.
* [Every run-status change needs a matching run event](run-status-transitions-emit-run-events.md) - when you write `run.status` anywhere.
* [Quote-in-context reads come in two keyings](chunk-context-two-keyings.md) - when you add a citation or quote surface.
* [A Task Agent line posted without a model call](agent-line-without-a-model-call.md) - when code posts into the Task Agent transcript.
* [A route that runs a model step wraps it in the task's trace session](model-step-routes-carry-the-task-session.md) - when a route calls a model step.
* [A tenancy predicate lives in its compiled SQL](tenancy-predicates-in-sql.md) - when you write organisation or ownership filters.
* [FastAPI yield dependencies tear down in reverse order](yield-dependency-order-sets-teardown-order.md) - when a dependency must act after the commit.
* [Trust forwarded headers from the VPC range only](forwarded-allow-ips-trust-the-vpc.md) - when you change uvicorn proxy settings.

## Runner, plans and Task Agent (`backend/src/policy_atlas/runtime`)

* [Every Evidence search run ends in synthesise](synthesise-is-run-terminus.md) - when you change plan composition.
* [The continuation reducer's plan choice is correct by fencing](plan-lineage-by-fencing-not-custody.md) - when you relax the Task Agent run fence.
* [A new plan field is carried from the previous version](plan-field-additions-carry-from-previous.md) - when you add a plan field.
* [Every directive key is plan-mappable or commit-layer](plan-mappable-vs-commit-layer-keys.md) - when you add a steering directive key.
* [A new ScopeConstraints field touches every projection surface](scope-constraint-fields-projection-surfaces.md) - when you add a scope field.
* [Compile-target parity is checked on the composed whole](compile-target-parity-covers-composed-wholes.md) - when you add a plan-to-config compile rule.
* [A confirm gate shows the compiled action](confirm-gate-renders-compiled-action.md) - when you build a human confirm step.
* [Retiring a UI affordance does not retire its grammar channel](retiring-ui-affordance-keeps-grammar-channel.md) - when you remove a steering option.
* [Harness scope lookups filter by owner as well as id](harness-scope-lookup-project-scoped.md) - when you add a harness lookup.
* [A run id from a success-only map is stale on failure](success-map-is-stale-on-the-failure-path.md) - when you build a steer-point bundle.
* [The executor's capacity counts running walks in the database](run-executor-capacity-counts-database-rows.md) - when you change walk capacity.
* [A task link grants no read](task-link-grants-no-read.md) - when you copy or read across linked tasks.
* [Live structured-output wire models: strict schemas and envelope variance](live-structured-output-wire-seam.md) - when you add a wire model.
* [gpt-5.6-terra rejects function tools unless reasoning effort is none](gpt-56-terra-tool-calls-reasoning-effort.md) - when you route a tool-calling step.
* [The agent CLI is the one check vehicle](orchestrate-stub-smoke.md) - when you need a stub smoke or a manual run.
* [Scoped live checks drive the real runner through the agent CLI](run-component-driver-for-scoped-live-checks.md) - before a dev-database live check.

## Database, events and migrations (`backend/src/policy_atlas/core`, `backend/alembic`)

* [Event-log sequence is assigned in app code under a retry](event-log-sequence.md) - when you append events from a new concurrent writer.
* [Run-less audit events carry no run id](run-id-fk-shapes-audit-carriers.md) - when you record audit state outside a run.
* [SQLAlchemy execution options belong on the statement](execution-options-statement-not-connection.md) - when you set execution options.
* [A Core INSERT's rowcount is not a did-it-insert signal](sqlalchemy-core-insert-rowcount-is-not-a-signal.md) - when you branch on an insert result.
* [`str(engine.url)` hides the password](sqlalchemy-url-str-hides-password.md) - when you hand a database URL to another process.
* [A BEFORE UPDATE trigger does not guard INSERT](before-update-trigger-does-not-guard-insert.md) - when you write a privilege trigger.
* [A constant column can lead a window partition and push a filter down](constant-column-in-partition-key-pushes-filter.md) - when you write a window query.
* [Postgres rejects NUL in TEXT and JSONB](model-output-nul-scrub.md) - when you store model output.
* [Removing a stored-shape tolerance sweeps every reader](removing-shape-tolerance-sweeps-every-reader.md) - when you tighten a stored shape.
* [An alembic revision freezes the SQL it runs](alembic-revision-freezes-the-sql-it-executes.md) - when you write a migration.
* [Every lossy downgrade refuses on its own data](lossy-downgrades-refuse-on-their-own-data.md) - when you write a lossy downgrade.
* [An identifier sweep must also rename stored JSON keys](stored-json-keys-are-vocabulary-too.md) - when you rename vocabulary.
* [A facet rename rewrites stored group-id prefixes](facet-key-rename-rewrites-stored-id-prefixes.md) - when you rename a grouping facet.

## Model calls, prompts and tracing (`core`, `model_routes.toml`)

* [Every model call site reads its own step from the route file](model-pin-per-surface.md) - when you add or re-pin a model call.
* [A model client's timeout is sized to the step's healthy tail](client-timeout-sized-to-healthy-tail.md) - when you set a timeout.
* [Retries inside a component the runner also retries multiply](retry-layers-multiply.md) - when you add a retry.
* [Omitted reasoning effort means medium; GPT-6 request shapes](reasoning-effort-omitted-is-medium-gpt6-shapes.md) - when you build a model request.
* [On reasoning models the output cap covers reasoning too](reasoning-model-output-cap.md) - when you set max tokens.
* [Bedrock from London: models, API and key variable](bedrock-route-facts.md) - when you use the Bedrock route.
* [Thread fan-outs carry context and return usage to the caller](executor-fanout-context-and-usage.md) - when you fan out model calls.
* [A wire-model field addition breaks every construction site](wire-field-additions-break-all-construction-sites.md) - when you add a wire field.
* [A max length on a wire field truncates mid-word](wire-max-length-truncates-not-fails.md) - when you limit structured output length.
* [Reject model output at the grain of the fault](validation-reject-at-fault-grain.md) - when you validate model output.
* [Cross-parameter validation runs on the defaulted values](validate-effective-defaults-not-explicit-args.md) - when you validate parameters.
* [Schema-valid output can still be empty](llm-schema-valid-empty-output.md) - when you consume structured output.
* [Untrusted text enters prompts only as encoded records](untrusted-prompt-fields-json-records.md) - when you put user or document text into a prompt.
* [A pydantic docstring in a tool schema is prompt text](pydantic-docstrings-in-tool-schemas-are-prompt-text.md) - when you edit a wire model's docstrings.
* [Structured-output prompts pin the key vocabulary](structured-output-prompts-pin-key-vocabulary.md) - when you write a structured-output prompt.
* [Short ids leak into a model's free text](short-ids-leak-into-free-text.md) - when a listwise call gets short ids.
* [A mini model's limits live in the schema or the code](mini-model-limits-live-in-the-schema-and-code.md) - when you tune a mini-model prompt.
* [An earlier honesty rule can defeat a new capability line](prompt-honesty-rules-route-around-new-capability.md) - when you add a prompt capability.
* [Langfuse usage buckets are exclusive](langfuse-usage-buckets-are-exclusive.md) - when you report usage to Langfuse.
* [structlog is the only logger](logging-structlog.md) - when you add logging.

## Evidence search: search and ingest (`evidence_search/sourcing`)

* [Bound search volume at acquisition, never with a clock](result-caps-need-distribution-rule.md) - when you change search caps or budgets.
* [A missing search-source key fails open](missing-source-key-fails-open.md) - before a live try.
* [OpenAlex semantic search rejects most filters](openalex-semantic-search-filter-support.md) - when you add an OpenAlex filter.
* [Overton country filters take display names](overton-filter-values-display-names.md) - when you filter Overton.
* [Overton returns date order unless sort is relevance](overton-relevance-order-needs-sort-parameter.md) - when you call Overton search.
* [Embedded values must exclude the wire's metacharacters](embedded-values-escape-wire-grammar.md) - when you build a provider query string.
* [Dispatch gated on a backend capability fails closed](capability-gated-dispatch-fails-closed.md) - when you dispatch on a backend feature.
* [Server-side request forgery IP pinning lives in the network backend](httpcore-origin-pooling-pinned-ip.md) - when you change live fetching.
* [A 403 from a document host is usually bot blocking](http-403-is-usually-bot-blocking.md) - when full-text fetches fail.
* [The HTTP library decodes whatever Content-Encoding a reply names](http-client-decodes-any-content-encoding.md) - when you cap the size of a fetch from an outside host.
* [Per-item isolation belts re-raise configuration errors](isolation-belts-reraise-config-errors.md) - when you add a per-item except.
* [Byte budgets reserve then shrink](reserve-then-shrink-byte-budgets.md) - when you change ingest budgets.
* [Full-text chunk hashes depend on a pymupdf4llm patch](fulltext-chunk-hash-determinism.md) - when you upgrade pymupdf4llm.

## Evidence search: screening, grouping and extraction (`assess`, `corpus`, `group`, `extract`)

* [Every screening consumer reads the effective row](effective-screen-row-read-rule.md) - when you read screening results.
* [The rubric's domain defines which types get a score](rubric-domain-defines-appraisability.md) - when you change evidence types or the rubric.
* [Content-keyed ids via uuid5](content-keyed-ids-uuid5.md) - when you mint a durable id from content.
* [The extraction fingerprint covers sub-backend knobs](fingerprint-covers-subcomponent-knobs.md) - when you add an extraction setting.
* [Two-stage clustering closes the partition capacity cliff](two-stage-clustering-closes-partition-cliff.md) - when you change grouping.
* [Facet partitioning has a value-list scale limit](facet-partition-value-list-scale-limit.md) - when you change facet grouping.

## Evidence search: synthesis and judges (`evidence_search/synthesis`)

* [A scoped pgvector search keeps its chunk list not materialised](scoped-sql-retrieval-planner-and-parity.md) - when you change retrieval SQL.
* [Vector maths runs in the database](sumprod-hot-path-vector-maths.md) - when you compute similarity.
* [Chunk-claim quotes verify against the whole document](synthesis-quote-whole-doc-basis.md) - when you read citation rows.
* [A citation row is written before a grounding error](citation-flag-dont-drop.md) - when you change grounding failure handling.
* [The shared scope row lock serialises synthesise runs](evidence-scope-row-lock-serialises-synthesise.md) - when you run synthesise concurrently.
* [Same-run re-execution fails loud before the first write](fail-loud-before-first-write.md) - when a re-run hits a database error.
* [Judge verdicts depend on the envelope](judge-envelope-defines-verdicts.md) - when you change what the judge sees.
* [A judge-effort decision needs a read of the verdicts](judge-effort-needs-a-content-read.md) - when you change judge reasoning effort.
* [Reuse an agent loop by generalising it in place](kernel-extraction-generalize-in-place.md) - when you share an agent loop.

## Options scoping and theory of change (`options_scoping`, `theory_of_change`)

* [A link's verdict is a weighted score; a pathway shows its lowest link](lower-grade-colours-the-canvas.md) - when a canvas looks empty.
* [Study geography from abstracts is mostly unknown](study-geography-from-abstracts-mostly-unknown.md) - when you show where an option was tried.

## Frontend (`frontend/src`)

* [The generated stream frame union forces reducer cases](generated-sse-union-reducer-cases.md) - when you add a stream frame.
* [Stream-fed state needs the same ownership gate](stream-fed-state-needs-ownership-gates.md) - when you show owner-only state.
* [String offsets from Python are code points](cross-language-string-offsets.md) - when you slice spans in the frontend.
* [A frontend label list is tested against the API's labels](frontend-label-lists-mirror-backend-vocabulary.md) - when you copy backend vocabulary.
* [Label maps live in one module; fixtures use raw keys](server-key-label-maps-one-home-raw-fixtures.md) - when you show a server key.
* [Report pages use the report's four text styles](report-typography.md) - when you style a report page.
* [Auth gating covers the cold path; sign-out needs a consumer](live-idp-cold-path-and-signout.md) - when you change frontend auth.
* [Mock-mode end-to-end tests check shape, not wiring](mock-fetch-blindness.md) - when you change transport or auth.
* [Vitest fake timers with userEvent need the clock to advance](fake-timers-with-user-event-need-should-advance-time.md) - when a test uses fake timers.
* [StrictMode poisons mount-flag refs](strictmode-mount-refs-reassert.md) - when you use a mount ref.
* [Replacing a native control loses its accessibility](native-control-replacement-rebuilds-free-a11y.md) - when you replace a native form control.
* [Additive mobile classes prove desktop is unchanged](additive-max-md-variants-prove-desktop-invariant.md) - when a change must leave desktop alone.
* [xyflow in this codebase](xyflow-in-this-codebase.md) - when you work on the canvas.
* [Vite 8 wires the React Compiler through a babel plugin](vite8-react-compiler-wiring.md) - when you change the Vite config.
* [The frontend's pnpm supply-chain settings](frontend-supply-chain-pnpm.md) - when you add a frontend dependency.

## Infrastructure and deployment (`infra/`, `scripts/deploy.sh`)

* [PowerUserAccess runs deploys but not bootstrap](cdk-poweruser-deploy-boundaries.md) - before a deploy.
* [CloudFormation re-asserts a value only on a changed deploy](noop-deploys-dont-reassert-template-pins.md) - when you pin a template value.
* [A CDK property typed Any takes a CloudFormation dict](cdk-any-typed-property-takes-cloudformation-dict.md) - when you set an untyped CDK property.
* [A CloudFront content security policy built from config](cloudfront-csp-from-config-pitfalls.md) - when you change security headers.
* [A WAF log keeps every header; inner rules show only in the log](waf-log-keeps-headers-and-hides-inner-rules.md) - when you change the web application firewall.
* [Cognito email templates render only with the SES sender](cognito-invitation-templates-need-ses-sender.md) - when you change Cognito emails.
* [Cognito MFA, managed login and custom domains](cognito-mfa-managed-login-custom-domain-facts.md) - when you change sign-in.
* [docker save layout depends on the image store](docker-save-layout-image-store.md) - when a script reads a saved image.
* [uv src-layout images sync in two layers](uv-src-layout-image-pattern.md) - when you change the Dockerfile.
* [Operator shell scripts target bash 3.2](operator-scripts-target-bash-3-2.md) - when you write an operator script.
* [macOS swap exhaustion looks like a Docker wedge](macos-swap-presents-as-docker-wedge.md) - when Docker hangs.

## Tests (`backend/tests`)

* [Tests run against a dedicated test database](testing-database.md) - when you run or write database tests.
* [Each parallel agent gets its own test database](parallel-agent-test-databases.md) - when agents run tests at the same time.
* [Committed test rows need unique subjects and cleanup](committed-test-rows-need-unique-subjects-and-cleanup.md) - when a test commits rows.
* [Migration round-trip tests pin explicit revisions](alembic-roundtrip-explicit-revisions.md) - when you write a migration test.
* [Stamping alembic back without a downgrade breaks later tests](alembic-stamp-back-without-downgrade-breaks-later-migration-tests.md) - when a test stamps a revision.
* [Column-churning migration tests need a scratch database](column-churn-migrations-need-scratch-db.md) - when a migration test changes columns.
* [Historical migration tests reflect old names below a rename](migration-tests-reflect-old-names-below-rename-revision.md) - when you test across a rename revision.
* [Postgres collation order is not Python's sorted](postgres-collation-order-is-not-python-sorted.md) - when a test checks ORDER BY.
* [JSONB reorders dictionary keys](jsonb-reorders-dict-keys.md) - when you compare stored JSON.
* [The suite sends nothing out; keys are scrubbed](tests-are-zero-egress-scrub-keys.md) - when you load settings in tests.
* [pytest-socket blocks only the current process](pytest-socket-process-local.md) - when a test spawns a process.
* [Assert on the written row, not the summary](assert-on-row-not-summary.md) - when you test a component.
* [Observe insert order at the write seam](observe-order-at-the-write-seam.md) - when you test ordering.
* [Assert timing on an injected clock](timing-asserts-injected-clock-logs-corroborate.md) - when you test timing.
* [A deadline from Process.start includes spawn time](process-start-deadlines-need-spawn-headroom.md) - when you test a subprocess deadline.
* [Some branches are reachable only live](live-only-reachability-coverage-class.md) - when you claim coverage of a live path.
* [A guard keyed on stored state is weakest on day zero](state-keyed-guards-day-zero.md) - when you test a state-based guard.
* [Before deleting a dead method, grep scripts and seeds](dead-surface-cuts-sweep-scripts-too.md) - when you delete code.

## Scripts, evaluations and live checks (`scripts/`, `scripts/evals`)

* [Live-check drives: environment and product facts](live-check-drive-runbook.md) - before a live check.
* [A readback script prints the task it read](evidence-readbacks-name-the-task-they-read.md) - when you read back live evidence.
* [Audit sanitized fixtures against the raw recording](sanitized-fixtures-audit-against-raw.md) - when you record fixtures.
* [The prompt hash guard hashes the whole module](prompt-hash-guard-hashes-whole-module.md) - when a prompt module moves.
* [Repository-root scripts are outside the typecheck gate](repo-root-scripts-not-typechecked.md) - when you edit scripts/.
* [Define the cost-per-run basis before a target](cost-per-run-basis-before-target.md) - when you measure cost.
* [An eval cost figure names its unit](eval-cost-figures-name-their-unit.md) - when you report a cost.
* [Langfuse cost by time window is a floor](langfuse-cost-by-time-window.md) - when you sum cost from Langfuse.
* [Reusing a Langfuse dataset run name appends](langfuse-dataset-run-name-reuse-appends.md) - when you rerun an experiment.
* [A prompt-cache measurement isolates every block](cache-measurement-needs-isolated-prefixes.md) - when you measure caching.
* [Consensus API paging and billing](consensus-api-paging-and-billing.md) - when you call Consensus.
* [Semantic Scholar has two search engines](semantic-scholar-two-search-engines.md) - when you call Semantic Scholar.
* [A rename manifest comes from the catalog](schema-manifest-from-catalog-not-metadata.md) - when you rename schema objects.
* [A code-word sweep can invert screen-sense text](rename-sweep-inverts-screen-sense-words.md) - when you run a rename sweep.
* [A two-step rename needs a ledger and anchored exemptions](two-step-rename-needs-ledger-and-anchored-exemptions.md) - when a rename's second step reuses the first's word.

## Build and dependencies (`Makefile`, `pyproject.toml`)

* [uv run re-syncs to the default groups](uv-run-resyncs-default-groups.md) - when you add a dependency group.
* [pip-audit's requirements mode crashes under uv Python on macOS](pip-audit-environment-mode-under-uv.md) - when you run a dependency audit.
* [Parallel mypy runs share one cache](parallel-mypy-runs-share-one-cache.md) - when mypy reports errors in untouched files.

## Agent workflow (delegation, gates, reviews)

* [Delegated-executor practices](delegated-executor-practices.md) - when you brief a delegated agent.
* [A parallel-agent brief forbids git stash](parallel-agent-briefs-forbid-git-stash.md) - when agents edit one checkout.
* [Gate an index snapshot in a second worktree](gate-snapshots-commit-from-tree-ids.md) - when you gate while agents build.
* [Measure a commit from a second worktree](measure-a-commit-from-a-second-worktree.md) - when you measure a commit.
* [Take-theirs drops unconflicted hunks](merge-take-theirs-drops-unconflicted-hunks.md) - when you resolve a merge conflict.
* [Binary verification evidence stays off the tree](binary-evidence-stays-off-the-tree.md) - when you record screenshots.
* [Tested in isolation is not wired](tested-in-isolation-is-not-wired.md) - when you claim an integration works.
* [Guard tests assert the real invariant](guard-tests-name-real-invariant.md) - when you write or review a guard test.
* [A test of one delay switches the other delays off](timing-test-removes-the-other-delay.md) - when you review a timing test.
* [A getattr-guarded SDK call no-ops silently; a stub shaped to it proves nothing](silent-sdk-guards-and-stub-shaped-tests.md) - when you upgrade an SDK or review a test double.
* [An interface change sweeps every fake and premise pin](interface-change-sweeps-fakes-and-premise-pins.md) - before a targeted test run.
* [A poll-deadline failure: re-run alone, find the race, then widen](poll-deadline-tests-under-parallel-load.md) - when a deadline test fails in the suite.
* [Recovery copy needs a route that recovers, tested end to end](recovery-copy-names-a-route-that-recovers.md) - when you review recovery copy.
* [The first-built variant hoards the generic names](unmarked-default-naming-smell.md) - when a second variant lands.
* [The refine-replay loop exits by reverting](refine-replay-revert-exit.md) - when you refine a prompt.
* [Replay-diff a guidance line](replay-diff-prophylactic-vs-corrective.md) - when you add a prompt guidance line.
* [On a mini model, a worked example beats a rule](mini-model-loops-examples-over-rules.md) - when you tune a mini-model prompt.
