# Rubric: 046-search-baselines

The task is **done only if every box holds**. Otherwise it is in progress, not done.
Problems P1–P4, decisions D1–D8 and the arms are defined in [contract.md](contract.md).

1. [ ] Implementation satisfies [contract.md](contract.md): all six deliverables land;
       D1–D8 hold as written.
2. [ ] `make verify` passes. `test_metrics.py` passes with every new self-check listed in
       the contract's § Acceptance checks.
3. [ ] **P1.** All four arms ran at caps 50, 100, 200 and 1,000 over all four reviews. Each
       run is in Langfuse with exactly the seven scores in D6 and the metadata keys in D6,
       and appears as a row in `history.py` output.
4. [ ] **P2.** `--suggest-keys` ran on the 34 references with no key. The report says how
       many were `EXACT`, `AMBIGUOUS`, `NONE` and `LOOKUP FAILED`, and which the human
       accepted. The script wrote no key itself (D5). The dataset was re-uploaded and the
       pipeline's rapid depth re-run on it (D8).
5. [ ] **P3 / P4.** Every baseline trace carries `api_cost_usd`. `history.md` shows the
       per-run cost sum for baseline runs (`api`) and pipeline runs (`llm`), and the README
       says what each figure leaves out (D4).
6. [ ] **Fairness.** Every arm used the same intent text, the same cutoff (with the
       Consensus month rounding noted), the same scoring key function and the same recall
       formula. Recall is reported for the scholarly and grey spaces separately (D3). The
       history notes name each difference that favours an arm (D1, D2) and state that the
       raw-versus-pipeline comparison is a sign, not a controlled test.
7. [ ] Nothing under `backend/src` changed (D7). No dependency added. No key or CSV
       committed.
8. [ ] No generated files or secrets edited by hand.
9. [ ] No tests deleted, skipped or weakened without written justification.
10. [ ] Verification evidence recorded in [verification.md](verification.md), including
        the Consensus preflight and spend and any failed requests.
11. [ ] Known gaps listed: references still without a key after D5, standard and deep
        depths not re-run, the "swap" slice deferred → [docs/deferred.md](../../deferred.md).
12. [ ] Review stack for Tier 2 ran. The adversarial reviews of contract and plan the owner
        asked for ran at design time; their findings and outcomes are in the contract's
        status line and in [verification.md](verification.md).
