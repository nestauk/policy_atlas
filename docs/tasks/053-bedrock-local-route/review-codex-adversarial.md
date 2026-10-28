# Step 7, Codex adversarial lane: raw findings (unadjudicated)

Reviewer: Codex (`codex-rescue`, read-only brief), 2026-10-14, started from the build
conversation so the slow lane could run early. **Not adjudicated.** Adjudication belongs
to the fresh review conversation (task-cycle-review § Step 7), which must also note the
reviewer's own caveat at the end: targets 2, 6, 7 and 10 of the brief (import-order,
security boundary, scope, simplification) are **not covered** by this run and need a
lane of their own or a second Codex pass.

Brief given: the diff `git diff dev...HEAD -- . ':!backend/uv.lock' ':!docs/tasks/**'
':!docs/adr/**'`; provenance map with Codex anchoring the Claude-written surfaces
(route file and loader, constant sweep, knobs, base_url change, Claude prompt, conftest,
image-hygiene guard, `.env.example`, deferred log) and reading the Codex-written ones
(Cohere backend, traced wrapper, Claude backend, Stubber tests) with lower weight.

## Findings, verbatim

1. **Major, Claude surface:** `backend/src/policy_atlas/core/model_routes.py:179`,
   `backend/src/policy_atlas/runtime/agent.py:817`. An unknown `search_queries.backend`
   is silently treated as OpenAI: the loader accepts any string, while the builder
   selects Claude only for the exact value `"claude"` and otherwise constructs
   `OpenAISearchGenerationBackend`. A typo in a committed route or evaluation overlay
   therefore changes provider behaviour rather than failing before egress, contrary to
   the slice's fail-loud posture. Validate this field in `load_route()` against
   `{"openai", "claude"}`, and make the selection branch explicitly raise for any
   unsupported value; add a loader and composition test.

2. **Minor, Claude surface:** `backend/src/policy_atlas/core/model_routes.py:155`. The
   loader only converts TOML syntax errors to the promised `RuntimeError`; valid TOML
   with the wrong shape can leak `ValueError`, `AttributeError`, or similar
   implementation exceptions. For example, an overlay whose `routes` value is an array
   reaches `routes.update(...)` at line 163 rather than producing an error that names
   the overlay and bad key. Add mapping/string type checks for `[steps]`, `[routes]`,
   route tables and nested sections, wrapping shape errors as `RuntimeError` with the
   file and key; cover malformed-but-parseable overlays in tests.

3. **Minor, Claude surface:** `backend/tests/core/test_model_routes.py:40`. The
   default-route test validates the loader's 23 step resolutions and embedding fields,
   but it does not import and assert the 25 actual module-level constants required by
   rubric item 10. That leaves the mechanical sweep unpinned: a future wrong step name or
   an unrelated constant not wired to `route()` could pass this test while the
   application uses the wrong model. Add an explicit inventory of all 25 imported
   constants, preferably in a clean subprocess, and compare it to the pre-053 literals.

4. **Minor, Claude surface:** `backend/tests/core/test_image_hygiene.py:58`. The
   repointed guard is not vacuous. `ops/` still directly imports Cognito type stubs, so
   its second assertion has a real witness. But it scans only `api/` and `core/`. The
   API's request path also imports `runtime/` and `evidence_search/`; a runtime
   `mypy_boto3_*` import there would fail in the production image yet evade the guard.
   Expand the forbidden-stub scan to all production packages (or all of `policy_atlas`
   excluding `ops`) while retaining the `ops` witness assertion.

## Reviewer's confirmations, verbatim

I found no issue with the four documented build-time deviations. The `fast` tier
preserves the task-051 defaults, agent triage is correctly independent of screen, the
six pinned modules are accounted for, and ADR 0041 matches the branch history. The
Claude prompt is a genuine fresh, minimal prompt. It keeps the data-not-instructions
posture and does not bake provider-specific knobs into the text. The Stubber tests do
inspect complete effective request bodies, and the subprocess route test removes both
route-related environment variables.

## Reviewer's verdict, verbatim

The slice is mergeable after fixes 1 and 2. Fixes 3 and 4 should also be made if the
rubric is to be met rather than approximated. Rubric items 1, 10 and 26 are currently
unmet or at risk because of the fail-loud gaps. Item 5 is at risk because the
replacement image guard does not cover the full request path.

## Reviewer's caveat, verbatim

This review came from one Codex run. The run's log shows it reading the task docs,
`model_routes.py`, `embeddings.py`, `search_generation.py`, `chat_backend_openai.py`,
`search_prompts.py` and the `git diff`. Its output gives no sign that it covered the
import-order, security-boundary, scope or simplification targets (2, 6, 7, 10) in
depth. Treat those as not reviewed rather than clean.

## For the adjudicating conversation

- All four findings are on Claude-written surfaces, which is what the family flip is
  for. None touches the Codex-written backends; those still need the Claude half of the
  pair (`/code-review medium`) and the security lane.
- The author's one note, offered as context and not as adjudication: finding 1 is
  real and small (one `if` in the loader, one `else: raise` in the builder, two tests);
  finding 3's intent is already partly served by the existing module tests that assert
  constants under the default route, but no single test covers all 25.
- Still open from the build: the owner's decision on one re-run of live check 3.
