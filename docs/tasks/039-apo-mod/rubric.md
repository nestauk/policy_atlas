# Rubric: 039-apo-mod (re-apply)

Done only if every box holds.

1. [ ] S1: the full 038 rubric holds at the renamed paths
       (`old_contracts/038-apo-mod/rubric.md`), including the live Overton
       `source=apo` evidence and the exactly-one-key allowlist widenings.
2. [ ] S2: distinct case-study cards carry unique `claim_ids`; the read model
       recovers colliding-alias rollups and keeps the alias path when healthy.
3. [ ] S3: a Sources-only save leaves APO geography intact; Start failures
       show the API message; "Discard edits and start" works; screening rules
       are a +/− list with a 1000-char per-rule cap (1001 rejected; list max
       50 and composed 2000 unchanged; `DIRECTIVE_STRING_MAX` untouched).
4. [ ] S4: `planner_v11` pinned (hash re-pinned as deliberate work); prompt
       teaches APO and the 1000-char wording; geography-box tokens still work.
5. [ ] `make verify` green at exit; no hand edits to generated files.
6. [ ] No stale-vocabulary references introduced (`portfolio`, old `project`
       row semantics, `evidence_base`).
7. [ ] Verification evidence recorded; removal note + v11 note in
       `docs/deferred.md`.
8. [ ] Tier-3 review stack runs in a fresh conversation (step 7); no new
       design-stage adversarial pass (owner ruling recorded in the contract).
