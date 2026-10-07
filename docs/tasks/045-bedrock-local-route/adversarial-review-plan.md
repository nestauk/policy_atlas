# Plan-stage adversarial review: 045-bedrock-local-route

Reviewer: Codex (`codex-rescue`, read-only brief), 2026-09-25, job
`task-muguw8re-77bfom`. Target: plan.md as drafted after the contract-stage remedies.
Adjudicated by the lead the same day. The plan was rewritten to carry every adopted
remedy; the contract and rubric received the small corrections noted below. None of the
changes alters the approved scope or the two approved gates.

| # | Severity | Finding, in plain words | Adjudication |
|---|---|---|---|
| F1 | Blocker | The plan still named the route file at the repo root in three places, after the contract moved it into the package. An implementer could create a file the image would not ship. | **Adopted.** Every reference now reads `backend/src/policy_atlas/model_routes.toml`. A test reads the file through the loader's own path, which is the path the wheel ships. |
| F2 | Blocker | The "no literal model name left" grep would never pass, because comments and docstrings mention model names and the contract forbids changing those lines in the pinned prompt modules. | **Adopted.** The check is a test, not a grep: it imports every constant in the inventory under the default route and asserts each equals its pre-045 value, and a narrowed grep looks only at assignment lines (`= "gpt-`), which comments do not match. |
| F3 | Blocker | The plan counted seven environment overrides; there are more, and the case-studies model today follows the synthesis model when only the synthesis override is set. Two steps with the same default tier would not preserve that. | **Adopted, then overtaken.** The code has nine overrides, not eight: the reviewer missed `POLICY_ATLAS_AGENT_TRIAGE_MODEL`, which follows the screen model the same way. The plan first listed all nine with precedence and "follows" rules. The owner then retired all nine (2026-09-25), so the loader ignores them with a warning and the follows rules disappear with them. The inventory correction stands. |
| F4 | Should fix | The step name `report_intro` does not match the existing tracing key `full_report_intro`. | **Adopted.** Step renamed `full_report_intro`. The steps table now has 23 entries. |
| F5 | Blocker | The Cohere brief left wire details to be invented: there is no `ThrottlingException` class, only a `ClientError` with a code; request argument and field names, response reading and the header location were not pinned. | **Adopted.** The plan pins the exact `invoke_model` call, JSON body, response reading, header name, error rule and the dummy credentials the `Stubber` client needs. Values come from the 2026-09-25 probe. |
| F6 | Blocker | The Claude brief never named the tool or pinned the Converse request nesting or the usage mapping. | **Adopted.** The plan pins the tool name and description, the `system`/`messages`/`toolConfig`/`toolChoice`/`inferenceConfig` shapes, how the existing two-message builder maps onto them, the response walk, and the `usage` to `TokenUsage` mapping. Values come from the probe. |
| F7 | Should fix | Ownership of `runtime/agent.py` between the two parallel jobs contradicted itself, and test-file ownership was not named. | **Adopted by removing the problem.** Phases B and C run one after the other, not in parallel (see F8, F13). Ownership questions disappear. |
| F8 | Should fix | Two jobs running verification at the same time would share one Postgres, which the repo's landmine list says breaks migration round-trips. | **Adopted.** Sequential phases; every gate runs alone. |
| F9 | Should fix | `make audit` is not part of `make verify`, yet the rubric requires it after the dependency move. | **Adopted.** `make audit` runs at the end of Phase A, right after the lock file changes, and again at the step-6 exit. |
| F10 | Should fix | A route frozen at import makes tests sensitive to import order; reloading one module does not refresh constants other modules already imported. | **Adopted.** The loader is a pure function `load_route(path, name, environ)` tested directly with fixture files. Import-time selection is tested by a small subprocess per route, the pattern `tests/ops/test_make_wrappers.py` already uses. The module-level cached route is never reloaded in tests. |
| F11 | Should fix | Several tasks marked fast-worker need judgment (override precedence, the case-studies rule, the knob change, the test fixture design), and some lead marks lacked a reason. | **Adopted.** Loader, its tests, the knob change and the two "follows" rules are lead. Fast-worker keeps only the exact constant replacements against the inventory table. Every lead mark now carries its reason. |
| F12 | Minor | Live checks named a time budget but not a command, route or success condition. | **Adopted.** Each live check names its command skeleton, route, expected evidence and stop condition. |
| F13 | Minor | Simpler alternatives: subprocess tests instead of module reloads; sequential B then C instead of parallel. | **Adopted both.** They are the remedies for F10 and F7/F8. |
| L1 | (lead) | While verifying F3 the lead found a 25th model constant, `AGENT_TRIAGE_MODEL` in `runtime/agent_backend.py`, defaulting to the screen model. It was missing from the inventory. | **Fixed.** Added as step `agent_triage`, default tier `mini`, following `screen`. Inventory: 25 constants, 23 steps, 16 modules. |

**Verdict handling.** The reviewer's "not yet" rested on the path contradiction, the
override semantics, the provider wire contracts, the import-time test method and the
parallel ownership. All five are resolved in the rewritten plan. The plan goes to the
owner's gate with these remedies in place.
