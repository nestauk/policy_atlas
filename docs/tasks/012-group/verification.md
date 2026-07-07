# Verification: 012-group

Evidence for the group slice (EB component 8, facet-level theming). Public-safe.
Filled at verify (step 6); **Review findings** + **Rubric status** land after the
review stack (step 7, conversation C).

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (okf-validate · test · typecheck · lint · build) | pass | **526 passed**, 0 failed; okf 27 concepts, 0 violations; mypy 61 files clean; ruff clean; sdist+wheel built. Deterministic, zero egress — socket-deny: `test_socket_deny_group_round_trip` (plus the standing 008/009/010/011 socket-deny tests) green. |
| `make test` (inside verify) | pass | includes the 92 slice-added tests (see below) |
| `make typecheck` | pass | |
| `make lint` | pass | |
| `make build` | pass | |

Migration roundtrip (test DB, alembic): head → **24** tables → downgrade -1 → **23**
→ upgrade head → **24**. Six pre-existing `len(metadata.tables) == 23` assertions
bumped to 24 (acquire/appraise/classify/embeddings/screen/ingest_full_text).

## Checks beyond the build

**Deterministic tests — the slice's named-test list, all green:**

- **Finding-set resolution** (`tests/test_group.py`): grouped set == the referenced
  run's findings via `docs[].extraction_record_id`; memo-reused docs included;
  foreign-run findings never enter; integrity cross-check against
  `counts.findings.total` — mismatch → structural failure, no row.
- **Exhaustiveness invariants** (`test_group.py`, `test_facet_values.py`): every
  finding in exactly one of group/ungrouped/no_value; `Σ group sizes + ungrouped +
  no_value == findings_total`; direction-spread sums per group, per residual bucket
  and overall.
- **Validation + repair** (`test_facet_values.py`, `test_group_judgment.py`):
  missing value ids → one targeted repair; still-missing → counted `ungrouped`;
  unknown/duplicate ids, zero-member groups → response rejected → one full-re-ask
  repair; a rejected repair discards to an honest all-ungrouped row; a raising
  repair → `component.failed`, no row.
- **Label/description validation** (`test_facet_values.py`,
  `test_group_judgment.py`): empty/over-length/control-char/duplicate labels and
  descriptions and the exact seven-entry forbidden-generic set (parametrized, case
  variants) all reject the response; negative rules additionally asserted on the
  built prompt.
- **Scale cap** (`test_group.py`, `test_group_judgment.py`): > `FACET_VALUE_CAP`
  (150) distinct values → `GroupError` naming `value_cap_exceeded`, **zero backend
  calls** (counting double).
- **Null-facet handling** (`test_group.py`): population facet with NULL populations
  → counted `no_value`; all-null → `all_no_value` flag, no call.
- **Facet directive** (`test_facet_values.py`, `test_group.py`): default
  `intervention`/`default`; scope-context override recorded in provenance and
  summary; malformed/unknown-key/control-char/non-enum directives fail closed
  (`FacetDirectiveError`), no row, no call.
- **Mixed/unclear first-class** (`test_group.py`, `test_group_contract.py`):
  `mixed`/`unclear` fixture findings appear in group spreads and residual spreads;
  a mixed-status referenced run (extracted + no_findings + failed docs) contributes
  findings from extracted records only.
- **Edge scopes** (`test_group.py`): zero-findings run → `empty_findings` flag,
  zero-group row, no call; missing extraction row → structural failure; same-run
  re-execution loud (`uq_grr_scope_run` IntegrityError).
- **Backend failure** (`test_group.py`): stub fail sentinel → raises →
  `component.failed`, **no roll-up row, no partial state**.
- **Determinism** (`test_group.py`, `test_facet_grouping.py`): two stub runs over
  the same extraction → identical facet/groups/counts/flags payloads; value ids
  assigned in sorted-normalised order regardless of input order.
- **Injection posture** (`test_group_judgment.py`): an injection-shaped facet value
  enters the built prompt only inside the id-keyed JSON records (data position);
  the system prompt is byte-identical to the built `group_facet_v1`; **no scope
  intent in any built message** (canary-asserted); the run completes with the value
  as inert data.
- **Single prompt surface** (`test_facet_grouping.py`): the repair call's system
  prompt is byte-identical to the partition call's; one `PROMPT_VERSION`
  (`group_facet_v1`) recorded in provenance.
- **Provenance required keys** (`test_group.py`): prompt_version, model, mode,
  facet + source, value_cap, call/repair counts, distinct_value_count,
  extraction_run_id, and the inherited base — extraction fingerprint + profile,
  base-ladder counts, finding-set size + sha256 over sorted finding ids, facet
  coverage breakdown — asserted key-by-key.
- **No side effects** (`test_group_contract.py`): `source_tag` and
  `intervention_outcome_finding` rows byte-identical before/after; `grouping_result`
  the only new row; **no evaluative keys** (verdict/consensus/strength/…) anywhere
  in the row or summary, key-name-asserted.
- **Schema constraints** (`test_group_contract.py`): facet CHECK, both
  cross-project FK guards, the extraction-reference FK (no-row and wrong-scope),
  and the scope-run unique all reject.
- **Key hygiene** (`test_group_judgment.py`): an `OPENAI_API_KEY` canary never
  appears in the summary or the written row.
- **Wiring** (`test_compile.py`, `test_group_contract.py`, `test_harness.py`):
  `"group"` compile fails closed without `extraction_run_id`; harness runs group
  with the stub default (no backend arg); `component.failed` + `run.failed` on a
  missing extraction row; delete-order integrity via `delete_project_data`.

**Slice test tally:** 36 (`test_facet_values`) + 4 (`test_facet_grouping`) +
13 (`test_group`) + 25 (`test_group_judgment`) + 14 (`test_group_contract`) =
**92 added tests**; suite 430 → 526 (plus the six bumped table-count asserts and
the renamed characterise/harness suite green under the theme rename).

**AI evals:** none — deliberate. Grouping *quality* (coherent/useful partitions)
is the recorded facet-grouping-quality eval seam (docs/deferred.md); this slice's
bar is machinery correctness, exhaustiveness invariants, honest residuals and
provenance fidelity. The review stack should not mistake machinery tests for a
quality claim.

## End-to-end command

Stub end-to-end (deterministic, zero egress — driven, log captured):

```
DATABASE_URL="postgresql+psycopg://policy_atlas:policy_atlas@localhost:5432/policy_atlas_test" \
  uv run python -m policy_atlas.skeleton
```

Observed: full chain … extract → **group** (facet=`intervention`,
facet_source=`default`) → scope-context update → **group** again
(facet=`outcome`, facet_source=`scope_context` — the directive path, new run id,
same `extraction_run_id`); both `grouping_result` rows written and verified by
direct DB query; both summaries rendered (`grouping.facet/counts/flags/provenance`);
`grouping_row_present count=2`; `skeleton.done`. Both runs honestly flag
`empty_findings` — the stub extraction backend yields zero findings on the
skeleton fixture corpus (pre-existing 011 stub behaviour), so the roll-up records
the zero-group honest skip with the empty-set sha256; the non-empty partition path
is exercised by the 92 tests and the live run below.

### Live manual check (contract acceptance) — **run 2026-07-07, operator keys**

```
set -a; source .env; set +a; uv run python -m policy_atlas.skeleton
```

Executed by the operator in-session (keys env-only); full log captured. Results:

- **Run 1 — facet `intervention` (source `default`)**: the extract run produced
  **190 findings**; group resolved them exactly, extracted **94 distinct
  intervention values**, and one real `group_facet_v1` partition call returned a
  near-partition with missing ids — **the repair path fired for real** (one
  targeted repair; flags `['ungrouped_values', 'repair_path_taken']`). Result:
  **16 groups**, grouped 164, ungrouped 26 findings (5 values), no_value 0.
  Usage: partition 4,810 prompt + 6,779 completion tokens; repair 1,739 + 1,919.
- **Run 2 — facet `outcome` (source `scope_context`)**: the skeleton's directive
  update (`context["grouping"] = {"facet": "outcome"}`) ran group again as a
  **new run over the same `extraction_run_id`**: 123 distinct outcome values,
  one partition call (5,999 + 8,342 tokens), no repair → **20 groups**, grouped
  186, ungrouped 4, no_value 0.
- **Invariants verified on the written rows by direct DB query** (both runs):
  the union of group/ungrouped/no_value finding ids **equals exactly** the
  referenced run's finding set resolved via `docs[].extraction_record_id` (no
  duplicates); `Σ sizes + residuals == findings_total`; per-group spread sums ==
  sizes; the provenance `finding_set.sha256` **recomputes identically** from the
  stored ids; call/repair counts (1+1, 1+0); `mode=live`, `model=gpt-5-mini`,
  `prompt_version=group_facet_v1`.
- **Labels are corpus-grounded and descriptive, no catch-alls** — e.g. "Taxes on
  sugar-sweetened beverages (country examples)", "Menu labeling (regulated
  chains and local regulations)", "Front-of-package and negative warning
  labeling systems". Direction spreads are counts; `unclear` findings visible in
  group and residual spreads (overall run-1 spread: positive 80 · negative 69 ·
  no_effect 32 · unclear 9 · mixed 0 — zero mixed is honest, none was extracted).
- **Langfuse**: `traced=True` on the user-operated dev instance; per-call
  generation spans logged (`facet_grouping.partition.usage` /
  `facet_grouping.repair.usage` with token counts); run-level scores attached
  via `grouping_score_summary` (`partition_valid`, `ungrouped_share`,
  `no_value_share`, `group_count`).
- **Cost note (honest)**: the group surface used 3 calls totalling ≈ 12.5K
  prompt + 17.0K completion tokens on `gpt-5-mini` — ≈ $0.04 at list rates; the
  full live skeleton (screen/rank/extract included) is the dominant spend, not
  grouping.
- **Key hygiene**: zero `sk-`-pattern or key-name matches in the captured log.
- **Environment event (recorded, not a code defect)**: the first live attempt
  failed with `UndefinedTable: grouping_result` — the **dev** database had not
  had migration 12 applied (the test DB migrates via conftest). Fixed with
  `alembic upgrade head` on the dev DB; the rerun was clean. Secondary
  observation for the review stack: a server-side DB error mid-component leaves
  the transaction aborted, so `_run_scope_component`'s `component.failed` event
  append itself fails (`InFailedSqlTransaction`) — the run dies loudly but
  without its failure event. This is standing harness behaviour affecting every
  component (not introduced by 012); noted as review-stack input.

## Diff summary

Five commits on `task/012-group` (data files: none — no fixture changes ride this
slice):

- **e437570 (schema)** — `grouping_result` + migration 12 (tables 23 → 24); six
  table-count asserts bumped.
- **7ac6acd (clustering layer)** — `facet_grouping.py` (the `group_facet_v1`
  prompt — lead-authored, pre-flight-validated; wire models; protocol; OpenAI +
  stub backends) · `facet_values.py` (pure identity/validation/derivation
  functions) · the **theme symmetry rename** (`GroupingBackend` family → `Theme…`,
  `run_harness(grouping_backend)` → `theme_grouping_backend`) rippled whole across
  src/tests/living docs, grep-sweep clean, stored-data vocabulary untouched.
- **65f7fd6 (component)** — `group.py`: roll-up load → resolution + integrity
  cross-check → facet projection → cap (fail closed) → one partition + one repair
  → deterministic membership → invariants → row last → summary.
- **afb884f (wiring)** — registry entry (compile fails closed), harness node +
  `facet_grouping_backend` (stub default), skeleton chain + second directive run +
  `grouping_score_summary`, delete order.
- **f6341f0 (tests + seams)** — contract-bulk + judgment tests; deferred.md's
  seven 012 seams + the 009 inheritance discharge.

**Minor deviations (visible, not silent):**
- Judgment-test expectation aligned to group.py's provenance semantics:
  `call_count` counts partition calls, repairs counted separately (total = sum) —
  a test-side fix, no behaviour change.
- Delete-order test uses the suite's rollback-fixture shape (every existing
  delete-order test's precedent) rather than a literal COMMIT.
- Skeleton stub group runs show `empty_findings` (stub extraction yields zero
  findings on the fixture corpus — pre-existing 011 stub behaviour, not introduced
  here); the honest-skip path is what the deterministic demo exercises.

**Executor routing (plan table honoured):** lead — schema, prompt + protocol,
deferred.md, verification; Codex — `facet_values.py`, backends + rename ripple,
`group.py`, judgment tests; fast-worker — wiring, contract-bulk tests. All
delegated output lead-reviewed before landing.

## Review findings

Review stack run 2026-07-07 (conversation C, fresh adjudicator). Lanes: contract
verifier (fresh Opus subagent, read-only) · `/code-review medium` (8 finder
angles, per-angle diff scoping, Sonnet fast-workers) · security-auditor subagent
(Tier-3 lane) · Codex adversarial (read-only rescue brief). Budget honoured:
reasoning-class lanes ≈ 220K; fast-worker fan-out ≈ 560K (slightly over the 500K
proxy — 8 angles; verification of the 5 surviving candidates was done by the
lead inline instead of verifier agents to compensate). `/simplify` skipped with
justification: `/code-review` ran the reuse/simplification/efficiency/altitude
angles and their adoptions were applied — a separate same-family pass would
duplicate it.

- **Contract verifier:** all rubric items PASS (8 pending — this stack);
  independently re-ran the suite twice (526 green both times); traced rubric
  9–11 to code and tests; no "documented but not built" gaps in
  verification.md or ADR 0008. Forwarded the standing transaction-abort
  observation (below).
- **`/code-review medium`:** 0 correctness findings (line-by-line,
  removed-behaviour and cross-file angles all clean — the rename ripple was
  verified hunk-by-hunk with no weakened assertion). 5 cleanup candidates,
  lead-verified inline: **adopted** the altitude finding (`DIRECTIVE_STRING_MAX`
  borrowed from `select.py` → hoisted to `schema.py`, both importers updated);
  **deferred** the traced-call-shape triplication across OpenAI backends
  (deferred.md § 012 seams — factor when a fourth backend lands); **declined**
  the per-group full-list scans in `build_groups_payload` (the `values`-order
  iteration deliberately pins payload ordering to the sorted input, n ≤ 150),
  the duplicated 2-line try/except in `_partition_values` (a helper is more
  indirection than it saves), and a shared pydantic→TypedDict unwrap helper
  (speculative abstraction over two genuinely different shapes).
- **Security lane (security-auditor subagent):** 0 critical/high/medium; all
  six contracted posture points verified as holding (injection, untrusted
  labels, egress bounds, key hygiene, tenancy FKs, fail-closed directive).
  **Adopted** both findings: LOW — no per-string length cap on facet
  values/counterparts entering the live prompt → fail-closed
  `VALUE_SURFACE_MAX` (500) check before any call, mirroring the
  `FACET_VALUE_CAP` posture (+ named test); INFO — unknown directive keys
  echoed unbounded into the failure message → bounded/sanitised echo
  (repr-escaped, truncated, first 5).
- **Adversarial review (Codex, Tier 3):** no critical/high. **MEDIUM,
  CONFIRMED and adopted (unique to this lane):** the contracted *overall*
  direction spread was computed only into the `component.completed` summary,
  never persisted — a synthesise reader of `grouping_result` by
  `grouping_run_id` could not read it. Fixed: `build_groups_payload` now
  writes `overall_direction_spread` into the row payload,
  `assert_grouping_invariants` enforces its sum identity
  (`Σ overall == findings_total`), the summary reads the payload key instead
  of recomputing, and the happy-path + zero-findings tests assert it on the
  written row. **LOW, declined with reason:** the count-only integrity
  cross-check could in principle be bypassed by a *corrupted* roll-up whose
  `docs[].extraction_record_id` points at a same-project record with an equal
  finding count — resolution via the roll-up's own recorded ids is the
  contract's rev-1.3 blocker fix, the count cross-check is the contracted
  integrity bar, and a tampered first-party roll-up row is outside the trust
  model (the FK guard already pins the extraction row to the scope).
- **Convergence note:** the `build_groups_payload` scan candidate surfaced
  independently in two cleanup angles (simplification + efficiency) —
  convergent but declined on the ordering-semantics ground both missed. The
  row-payload overall-spread defect was unique to the Codex lane (the contract
  verifier graded rubric 9 partly on the summary's spread) — family diversity
  earned its keep.
- **Forwarded (not a 012 defect):** the standing harness behaviour where a
  server-side DB error mid-component aborts the transaction and the
  `component.failed` event append itself fails (`InFailedSqlTransaction`) —
  recorded repo-wide in deferred.md, fix belongs in the harness.

**Fixes applied in this phase** (fake-done check: no test deleted/weakened —
two exact-equality expectations *extended* with the new payload key, one test
added): `overall_direction_spread` persisted + invariant + tests ·
`VALUE_SURFACE_MAX` fail-closed cap + test · bounded directive-key echo ·
`DIRECTIVE_STRING_MAX` hoisted to `schema.py`. `make verify` re-run green after
fixes: **527 passed** (526 + 1 added test), okf/typecheck/lint/build clean.

## Rubric status

Checked after the review stack (step 7, 2026-07-07): **all 11 items hold.**
1–2 implementation + `make verify` green (527 after review fixes) + live check
evidenced above; 3 gated changes only (schema/interface/egress approved at
contract rev 1.2/1.3 — review confirmed nothing beyond them); 4–5 no generated
files/secrets touched, no tests deleted/weakened (contract verifier + removed-
behaviour angle both confirmed; review-phase fixes extended expectations, added
one test); 6 this document; 7 deferred.md updated (seven seams + two
review-phase entries); 8 the review stack above — four lanes run, adjudicated,
fixes applied, re-verified; 9–11 test-enforced and independently traced to code
by the contract verifier (rubric 9's overall-spread-in-row gap found by the
adversarial lane and closed this phase).

## Intent & assumptions

- Groups are run-local execution state (ADR 0008): one `grouping_result` row per
  run; memberships never promote to canonical state; synthesise (013) reads by
  `grouping_run_id`.
- The LLM's entire job is one schema-constrained partition of distinct facet
  values; membership derivation, residuals, spreads and writes are deterministic.
- `GroupContext.intent` is carried for wiring uniformity and **not consumed**
  (code comment states it; injection test asserts no intent reaches the prompt).

## Known unverified items

- Grouping quality on real reference sets — deliberately unverified (eval seam);
  the live labels *look* coherent but no quality bar is asserted.
- Langfuse trace contents verified via the logged generation-span usage lines
  and the score-summary call path; visual UI inspection of the trace is
  available on the dev instance but was not screenshotted into evidence.
- `FACET_VALUE_CAP = 150` calibration — plan-pinned, uncalibrated (eval seam).

## Public safety

- Suite + skeleton stub runs: zero egress (socket-deny green); everything above is
  synthetic-fixture derived — safe to publish.
- Live run (when executed): egress is the fixture corpus's distinct
  intervention/outcome/population reference strings + per-value counterpart names
  and counts to the OpenAI API — no quotes, no statistics, no document text, no
  scope intent; full-I/O traces to the user-operated dev Langfuse only. Group
  labels/descriptions are model output over openly-licensed fixture text —
  public-safe for this corpus; stored/rendered as data, validated at write.
- No keys in any committed artefact or captured output (canary-tested).

## Deferred work

Seven seams recorded in [docs/deferred.md](../../deferred.md) § Group /
facet-level theming (task 012 seams): the `query-findings` tool (an **explicit
deviation** from components §8's tool table — lands with synthesise's agent-loop)
· facet-grouping quality evals incl. cap calibration · the large-corpus grouping
algorithm · agent-authored grouping directive · cross-schema reference-mediated
linkage · re-grouping/steering UX · facet-theme promotion (the staged ladder).
Plus the 009 `group`-component inheritance entry discharged defect-by-defect.
