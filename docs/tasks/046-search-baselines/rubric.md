# Rubric: 046-search-baselines

The task is **done only if every box holds**. Otherwise it is in progress, not done.
Problems P1–P4, decisions D1–D9 and the arms are defined in [contract.md](contract.md).
P2 and D5 are deferred and have no item here.

1. [ ] Implementation satisfies [contract.md](contract.md): all five deliverables land;
       D1–D4 and D6–D9 hold as written.
2. [ ] `make verify` passes. `test_metrics.py` passes with every new self-check listed in
       the contract's § Acceptance checks.
3. [ ] **P1.** All four arms (the fourth added by owner amendment, 2026-09-25) were fetched once to 1,000 results over all four reviews and
       scored at caps 50, 100, 200 and 1,000 from the cache (D9). Each run is in Langfuse
       with exactly the seven scores in D6 and the metadata keys in D6, including
       `fetched_at`, and appears as a row in `history.py` output. A second run with no
       flags made zero service requests.
4. [ ] **P3 / P4.** Every baseline trace carries `api_cost_usd` as the computed price of
       that cap (D4). `history.md` shows the per-run cost sum for baseline runs (`api`) and
       pipeline runs (`llm`), and the README says what each figure leaves out and that the
       baseline figure is computed, not spent.
5. [ ] **Fairness.** Every arm used the same intent text (Semantic Scholar's hyphen rule
       noted), the same cutoff (Consensus month rounding noted), the same scoring key
       function, the same cap rule (first N in service order, then dedup) and the same
       recall formula. The history notes name each difference that favours an arm (D1,
       D2), state that the target is scholarly only (D3), name the pipeline commit the
       rows are compared with (D8), and state that the raw-versus-pipeline comparison is a
       sign, not a controlled test.
6. [ ] Nothing under `backend/src` changed (D7). The ground truth and
       `ground_truth_dataset.py` are unchanged (P2 deferred). No dependency added. No key
       and no cache file committed; the cache holds no key.
7. [ ] No generated files or secrets edited by hand.
8. [ ] No tests deleted, skipped or weakened without written justification.
9. [ ] Verification evidence recorded in [verification.md](verification.md), including
       the Consensus preflight, the calls the fetch used, and any failed requests.
10. [ ] Known gaps listed in [docs/deferred.md](../../deferred.md): P2 (grey-literature
        keys, with the raw Overton arm), to land with the owner's ground-truth expansion;
        the "swap" slice; uploading the cache to S3; a ranking-stability test (D9).
11. [ ] Review stack for Tier 2 ran. The adversarial reviews of contract and plan the owner
        asked for ran at design time; their findings and outcomes are in the contract's
        status line and in [verification.md](verification.md).
