## What / why

Task: `docs/tasks/051-improve-production-search-screen/`

Production search found 5% of a review's reference list at Broad for $1.06 a review
(2026-10-05). This slice replaces the three-round search loop (task 015, ADR 0012) with
**one search pass at every scope**: generated queries on both databases, OpenAlex semantic
seeds, a backward citation snowball and a forward citation chase, ranked by specificity and
cut at two caps per scope (papers 100 / 200 / 400, policy documents 50 / 100 / 200); Overton
searched in relevance order, de-duplicated by title, with the 15 most-cited missing
documents fetched as landmarks. Stage-1 screening moves to `gpt-5.6-luna` with the
`screen_v4` prompt and an **adaptive two-call vote** (a second call only on a first
"not relevant"), replacing three calls and a majority. Query generation moves to Luna. The
two search legs run in parallel with concurrent OpenAlex calls behind a paced admission
lock. ADR 0038 records the design; the round loop's last working commit is tagged
`search-round-loop-last` with a restore recipe.

Measured on the 15-review mini set (search recall / screen recall / cost per review at
Langfuse's rate): Focused 12.9% / 12.5% / $0.17, Broad 17.8% / 17.3% / $0.33, Broadest
22.3% / 21.3% / $0.71. Search takes about 45 s a review at every scope (130 s before).
Against the 2026-10-05 loop at Broad: 17.8% for $0.33 where it gave 5.0% for $1.06.

## Proof it works

Evidence lives in `docs/tasks/051-improve-production-search-screen/verification.md`.

- **`make verify`:** pass (step-6 exit and again after the review fixes; backend 2,600+
  tests, frontend 617, typecheck, lint, build, eval-check, OKF).
- **Manual / end-to-end:** the live check
  `scripts/evals/search/checks/production_recall.py --dataset retrieval-ground-truth-mini --depths rapid standard deep`
  (three launches, labels `mini-051-2026-10-09`, `b`, `c`; history rows in
  `scripts/evals/search/results/history.md`); one app run at Focused on the obesity
  question through the real planning flow, completed, 13 landmarks in the Sources view.
- **Thresholds:** Focused and Broad met (by 0.4 and 0.5 points). **Broadest missed:
  22.3% against 24.6%**, recorded with the candidate causes for the owner's call.
- **Cost note:** Langfuse's price row for Luna is five times the list price; at list
  price the mini set cost about $4, not $20.64.

## Risk tier

Tier 3 — runtime egress changes (four new provider request shapes, parallel legs), model
id changes on two surfaces, a prompt transplant, and the deletion of the round loop.

| Tier | Review |
|---|---|
| 0–1 | tests + AI review or human skim |
| 2 | contract verifier + tests + human review |
| 3 | + security + adversarial review + human deep review |
| 4 | + human-approved plan + ADR + rollback plan |

## AI role

Claude (lead) designed, ran the experiments, built the search pass, the eval changes, the
records and the live check; Codex built the pool module, the transport verbs and the
adaptive vote and reviewed the plan and the parallel-search phase; a fast-worker did the
frontend text. The owner decided D13's amendment (local filters, no skipped semantic leg),
the parallel-search phase, the prompt and model pins, the spend ceiling, and the review
instruction (no new evals at review). The review stack (contract verifier, Claude code
review, security lane, Codex adversarial) ran as fresh agents; the lead adjudicated in the
build conversation at the owner's instruction.

## Review focus

- The single pass's local filtering of semantic and citation-found records (D13): the
  review fixed a dropped second country variant; is the union predicate right?
- The pool cut by position (D7, corrected at review): a repeat inside the cut is not
  refilled; confirm that is the behaviour wanted on a re-run of the same task.
- The Broadest threshold miss (rubric 10) and whether the measured 22.3% is accepted,
  re-run, or re-based.
- Egress: the 429 pause, the per-run concurrency, the budgets.

## Reviews run

Findings recorded in `verification.md` § Review findings.

- [x] Contract verifier
- [x] `/code-review` (fresh Claude agent, medium)
- [x] `/security-review` (fresh Claude agent)
- [x] Adversarial review (Codex, read-only)
- [x] `/simplify` (carried by the code-review lane's cleanup lenses; recorded)

## Known gaps & deferred seams

- Broadest 22.3% against the 24.6% threshold; full-set Broad run not made (owner: no new
  evals at review; the Langfuse price row to be corrected first).
- `docs/deferred.md` (task 051 section): relevance reserve (D6), similarity damping (D8),
  reformulation contingency (D11), seminal-decile score (D17), removed-title records and
  the `source_country` plan option (D18), partial backend failure and the coverage
  verdict, landmarks without wire filters, per-run pacing under concurrent runs.
- ADR 0038 is Proposed until the owner signs off.

## Public safety

- [x] No secrets, credentials, or real/acquired source text in the diff or evidence
  (fixtures hold ids, titles, dates and counts only; probe error excerpts key-redacted).
- [x] Logs / traces / screenshots are public-safe (Langfuse links are to the private
  project; the app screenshot shows public policy document titles).
- [x] No approval-gated change beyond those the contract names: the new egress shapes,
  the model ids and the prompt edits are the contract's D2, D8, D10, D12, D13; no
  schema, auth, dependency, CI or production-config change.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
