# Rubric: 056-cost-latency

Core completion criteria. The task is **done only if every box holds**, otherwise it is in
progress. Item numbers point at [contract.md](contract.md) (revision 2): N1 to N10, D1 to
D11, O1 to O5, S1 to S8, X1 to X8.

Core
1. [ ] Implementation satisfies [contract.md](contract.md) for every phase the owner kept (D5).
2. [ ] `make verify` passes at the build-open baseline, after P1, after P3 and at the step-6
       exit; `make prompt-guard` passes at every commit.
3. [ ] No approval-gated change beyond those the contract approves: the model set (D2), the
       D7 migration (nullable score plus `unrated` flag, 1 to 5 check kept for scored rows), the
       S5 stage key and payload, the one appraisal label, and the Europe PMC host once the plan
       gate records its approval. No production config, auth or CI change; a dependency only if
       approved at the plan gate.
4. [ ] No generated files or secrets edited by hand; the generated frontend types regenerated,
       not hand-edited.
5. [ ] No tests deleted, skipped or weakened without written justification (the v6 test and the
       rename-script tests are deleted by the owner's tidy-up decision, recorded).
6. [ ] Verification evidence recorded ([verification.md](verification.md)) as the contract's
       § Verification evidence lists, read from saved results.
7. [ ] Known gaps and deferred seams listed; the close-out entries in § Research and deferred-log
       coverage made in [docs/deferred.md](../../deferred.md).
8. [ ] Required Tier 3 review stack ran (contract verifier · code and security review ·
       adversarial pass at plan stage · simplification) or skipped with written justification.

Instrument and tidy (P0)
9. [ ] N1: every generation carries `input_cache_write_tokens` and `output_reasoning_tokens` as
       exclusive buckets; one live generation shows a non-zero cache-write price in Langfuse;
       `scripts/cost_per_run.py` reproduces the contract's baseline table for the sessions named
       in § Goal.
10. [ ] D11: the section writer's prompt text lives in `synthesis/section_prompt.py` and is
        pinned; `finding_vetter.py` is pinned; the v6 module, switch, test and hash entry are gone.
11. [ ] The tidy-up moves, renames and deletions are done with no behaviour change (`make verify`
        green, imports updated, the knowledge-note path fixed).
12. [ ] D2a: Bedrock London quotas for the three GPT-6 ids recorded.

Switch and prompts (P1)
13. [ ] D2: both routes name gpt-6-luna, gpt-6.1-terra and gpt-6.1-sol with the stated knobs; the
        two scoping judgment steps are `standard` step exceptions; no step uses `frontier`.
14. [ ] D9 and D4: every model call site has its own route step; the inventory records today's
        model and effort per step including "not sent"; a test pins the resolved model and effort
        for every step on the committed routes to today's values; the four effort constants are
        deleted; `traced_parse` and `parse_structured` carry the effort argument.
15. [ ] Fixed questions run after the model-only switch and again after the prompt loop, whole-run
        cost recorded with session ids, owner's read recorded for both; one question also run on
        `openai-direct`.
16. [ ] O3 and N6: the judge and two summariser prompts refined together; zero corrupted summaries
        pass on the 90-item set; the 20 adjudicated items re-run; first-attempt summary pass rate on
        the fixed questions not lower; retries carry the judge's reason (X2); re-pins recorded.
17. [ ] X1: grounding judge replay on gpt-6-luna with flipped verdicts hand-read; prompt refined
        only if the read asks. X4: the 046 tuning set replayed on gpt-6-luna, result recorded.

Caching (P2)
18. [ ] The 96-call breakpoint test re-run on gpt-6.1-terra and gpt-6-luna on both routes before
        any caching code, output saved; if it does not reproduce the GPT-5.6 behaviour the slice
        stopped at this point and the owner decided.
19. [ ] D3: `openai_kwargs`, `parse_structured` and `traced_parse` carry the caching mode; a test
        lists every model call site with its mode; per site the mode was chosen by measurement
        (breakpoint vs off) and the measurement is recorded.
20. [ ] D8 and D10: the run message carries the breakpoint; section turns and the repair share one
        builder with a byte-identical prefix (test), the same five tools, `parallel_tool_calls`
        True everywhere including the forced turn with its single-tool check; cache read and write
        shares per call name recorded before and after; the owner's read recorded.
21. [ ] X3: the `lookup` tool offers only the kinds the run can serve; wasted
        `characterisation_summary` calls per scoping baseline recorded before and after.

Unrated (P3)
22. [ ] D7 and S1 to S3: untyped documents get an appraisal row with a null score and
        `unrated = true`; the 1 to 5 check is untouched and holds for scored rows; the consistency
        check holds; `steering_triggers.py` filters null scores (test); they are citable; the writer sees
        "Unrated" beside the evidence type; the reader sees "Unrated" wherever appraisal is shown;
        coverage counts carry Unrated as its own bucket; `select.py` and `steering_triggers.py`
        behaviour unchanged (test); `DEFAULT_RUBRIC_VERSION` bumped; the spec amendments applied as
        the owner accepted them; the owner's read recorded.

Repair guard and effort (P4, P5)
23. [ ] N5: chunks over the oversized threshold are sent as a window using the existing helper;
        repair input tokens per call recorded before and after; repair pass rate not lower.
24. [ ] N7: each step's effort set deliberately, with per-step tokens, reasoning tokens and latency
        before and after and outputs within noise; classify at `medium`.
25. [ ] X5 dropped (owner, 2026-11-01); nothing to check. The deferred-log entry for the ledger move
        is written at step 8.

Ingest, progress, XML (P6)
26. [ ] N8: any-free-slot draining and preloaded workers, and the batch hand-over fixed; output
        byte-identical on a committed fixture corpus (CI) and on the saved local corpus
        (verification line); the per-document timeout, large-payload safeguards and shared ingest semaphore
        kept (tests); parse wall time recorded locally and on staging.
27. [ ] N9 and S5: the "Reading the full texts" stage appears, its ticks carry typed `fetched`,
        `parsed` and `total` counts from the document store on a fixed-question run; the web-api spec amended as the owner
        accepted.
28. [ ] N10 and S7: PubMed Central ids present in fresh acquisitions (or the gap found and fixed)
        without changing the hashed envelope text; the Europe PMC egress approval (2026-11-01)
        recorded; billion-laughs and external-entity tests on the XML parser; XML parsed safely; the share of
        documents taking the XML route and their chunk quality recorded.

Target
29. [ ] O1: median cost per standard-depth run on the fixed questions at the end of the slice
        recorded against the $2 target, with the per-phase table showing where the change came
        from; any phase that raised cost or failed the owner's read reverted and recorded.
