# Task contract: 048-coverage-prominence-eval

> **Status:** drafted. Tier 1 (isolated scripts and tests; no schema, dependency, CI, production
> or public-interface change); skips rubric/ADR per tier rules. Plan: the approved plan in the
> originating conversation, summarised in `scripts/evals/coverage/README.md`.

## Goal

An offline, review-referenced evaluator for the evidence report. Given a human-approved list
of expected findings taken from a published systematic review, and a saved report, an LLM
judge labels how each expected finding is represented in the whole report and (for the
designated subset) in the Key findings section. Code computes coverage and prominence rates
with full denominators, and compares judge labels with human labels.

## Deliverable

`scripts/evals/coverage/` with `cli.py` (draft-reference, approve, export, evaluate,
compare), `coverage_lib.py` (pure logic), two prompt files, a README, and a fully synthetic
example case that runs offline from a hand-written judge cache. Mocked tests in
`backend/tests/scripts/test_coverage_eval.py` (run by `make verify-fast`).

## Terms

| Term | Meaning |
|---|---|
| **reference** | `cases/<case_id>/reference.json`: the approved expected findings plus approval record and content hash. |
| **run package** | `cases/<case_id>/runs/<run_id>.json`: one report's markdown plus the character offsets of its Key findings section and how it was generated. |
| **pair** | One (finding, section) the judge must label; section is `full_report` or `key_findings`. |
| **prominence gap** | A finding required in Key findings that is `adequate` in the full report but `partial`, `absent` or `misrepresented` in Key findings. |
| **grounding judge** | The run-time judge in `evidence_search/synthesis/grounding_judge.py`. Out of scope; never called or modified here (a test proves it). |

## Read first

- `scripts/evals/report/README.md` (the sibling answer-relevance evaluator whose conventions this follows).
- `backend/src/policy_atlas/evidence_search/extract/quote_verify.py` (`qv_v1`, the reused quote normalisation).

## Scope / Out of scope

- **In:** the new folder, the test file, a `.gitignore` entry, this contract.
- **Out:** any change to synthesis, the grounding judge, search controls, the model client,
  dependencies, CI. No agent, search service, vector database or PDF/OCR subsystem. No
  Langfuse prompt push or dataset upload (deferred).

## Constraints & approval gates

No gated change. Model egress happens only when the user runs `draft-reference` or
`evaluate` with keys, through the existing OpenAI client. Langfuse tracing is optional and
offline without keys.

## Public / private boundary

Real cases (`cases/*` except the synthetic example) are gitignored: review text is
copyrighted. Results and the judge cache are gitignored. The synthetic example is public-safe
by construction (everything invented, labelled as such).

## Model route

Judge: OpenAI via `resolve_openai_client`, model and settings in the prompt file's front
matter (`gpt-5.4-mini`, `reasoning_effort: medium`). Prompt-bearing files:
`judges/align_findings.md`, `judges/draft_reference.md` (lead-written).

## Acceptance checks

- `uv run pytest tests/scripts/test_coverage_eval.py` green with the network blocked.
- `make verify-fast` green.
- The synthetic example evaluates and compares offline with the numbers in its README section.
- Deterministic checks are tests; judge behaviour is validated only by `compare` on real cases.

## Verification evidence expected

Test output, the offline example run, and the ruff/mypy results, in the PR.

## Risk tier & review focus

Tier 1. Focus: scoring correctness, gates that cannot be bypassed, no silent truncation or
silent absence, scope creep into fact-checking.
