# Options scoping — feasibility checks before any contract

Source: concept ruling 42 (`docs/specs/sources/options-scoping/options-scoping-concept.md`), which
adopted the third review pass's six checks in its order. A check order is an order for resolving
uncertainty, not a build order (ruling 28). Each section: the question, the smallest informative
method, who does it, what it depends on, and the result that would change the design.

**Word.** Ruling 42 and the review pack call these *spikes*. The team's word is **feasibility check**: a
small, time-boxed investigation that tests one design claim before a contract is signed. Same thing.

## 6 — Contract trace (first: needs nothing)

- **Question.** Can the declared components compose without hidden changes to ownership, evidence
  eligibility, extraction profiles, context or output semantics?
- **Method.** On paper, trace one inherited question and one edited variant through every component
  in `components.md`: fields in, fields out, records written, what is missing or ambiguous.
- **Who.** An agent, in a fresh chat; the owner reads the result.
- **Depends on.** Nothing.
- **Changes the design if.** Substantial new I/O appears that the origin column did not admit → mark
  those components new and put shared invariants in the system contracts. If the child full search
  cannot carry the profile's verdict cells within the widened boundary (ruling 41), revisit 41.

## 2 — Evidence attribution and confidence

- **Question.** Can the system distinguish a mention from support, documents from independent
  evidence, and inherited availability from compatibility?
- **Method.** Hand-build a small set from the existing corpus: a systematic review plus overlapping
  primary papers; a multi-intervention paper; a package evaluation; a modelled estimate; an
  abstract-only source; a changed variant; an older, partial inherited extraction. Run the abstract
  and light profiles over it and trace every proposed row and confidence statement back to the exact
  finding and source set.
- **Who.** Agent assembles and runs; owner or an analyst checks the verdicts (about an hour).
- **Depends on.** Check 6 for the field lists; the light and abstract extraction profiles drafted.
- **Changes the design if.** Independence cannot be resolved → suppress study tallies, count
  documents. Source tiers do not sustain claim confidence → keep the source-quality profile and the
  assessed judgement as two separate things (already ruled 33; this tests it). Inheritance misses
  required fields → reuse partially, never skip a document (ruling 35).

## 3 — Option-grain construction and selection stability

- **Question.** Do mentions and findings produce meaningful options, packages and variants, and does
  relabelling a primary lever move shortlist places without changing policy substance?
- **Method.** Run the characterise machinery at option grain over two or three logged questions
  (`pass1/real-questions-all.csv`: one evidence-dense, two structural, e.g. NEET; industrial energy
  prices; regional disparities), from abstract mentions and from inherited findings; include bundles,
  reviews, thin metadata and no-document suggestions. Rephrase the same options; vary primary-lever
  labels; watch the proposal. Ask a domain expert whether the selected comparisons change for a
  substantive reason.
- **Who.** Agent against real corpora; expert judgement on meaningfulness.
- **Depends on.** Check 6; the abstract extraction profile.
- **Changes the design if.** Options cannot be recovered reliably from abstracts → targeted full-text
  reading of reviews before minting (ruling 31 anticipates this). Lever assignment drives unstable
  places → stop using one-primary-lever quotas as the selection instrument.

## 4 — Local-condition adjudication

- **Question.** Can the weakest-leg verdict distinguish an applicable universal fact, an aggregate
  geography fact, a present user report and a commitment?
- **Method.** Paired cases: national average vs a local resource condition; a generally applicable
  rule with and without a relevant exception; planned funding vs presently available capacity; an old
  vs a current observation. Run each through the transferability working and inspect whether the cap
  moves for the right reason.
- **Who.** Agent drafts the pairs and runs them; owner judges.
- **Depends on.** A transferability prompt and the column-grounded block (from check 3's profile
  work).
- **Changes the design if.** Verdicts strengthen on containment or assurances alone → keep conditions
  visible and the verdict Unknown / conditional. Even corrected conditions cannot be judged reliably →
  remove the verdict word and keep the argument (reopens ruling 29's rejection).

## 5 — Balanced reading within a real budget

- **Question.** What is the total time and cost to a useful, qualified result, and what is lost when
  the per-option document cap tightens?
- **Method.** Compare light extraction plus narrative reading with targeted reading alone and with
  compatible finding reuse. Include cold starts, inherited runs, poor metadata, failed fetches, a
  rapid one-option check and a standard comparison set. Time the whole path — baseline, synthesis,
  verification, waiting at gates — not extraction alone. Inspect omitted contrary evidence under
  tightening caps.
- **Who.** Agent, on a prototype of ⟨assess⟩.
- **Depends on.** Check 3; a working select strategy and light profile.
- **Changes the design if.** A smaller cap changes the conclusion or drops the counter-case → change
  the read-set strategy and the promised result. The spine dominates latency → shrinking extraction
  does not solve rapid. Performance works only on inherited evidence → define that narrower rapid
  proposition rather than claiming cold-start parity.

## 1 — Advice and commissioning (the one that can change the shape)

- **Question.** Does the ruled stage-and-report journey improve what officials actually write or
  commission, compared with a progressive account using the same evidence?
- **Method.** Two or three live asks with an authoring official and a senior or central-team reader,
  including a newcomer and an Evidence search continuation. Hold evidence constant. Show the stage
  journey and a progressive account as paper or mocked outputs (nothing is built). Follow what gets
  copied, challenged and commissioned; observe resumption. Instrument = ruling 27's four tests; the
  newcomer criterion is recognising an omission or an unsupported transfer, not participation.
- **Who.** The owner's team with pilot users. Not agent work.
- **Depends on.** Nothing technical; needs people and asks. Should land before any contract is
  signed.
- **Changes the design if.** The shortlist ceremony adds no useful judgement → make selection
  subordinate to the report (the hybrid of ruling 32 already leans this way). Similar-plus-challenger
  comparisons omit the question the senior needs → change the comparison principle. Recipients lose
  qualifications → change the handoff before expanding output detail.

## Order

6 → (2 ∥ 3) → 4 → 5, with 1 running whenever live asks are available and landing before contracts.

## After the feasibility checks — the intended task split (owner, 2026-09-08)

The concept and spec carry no build order (ruling 28); this is the working intention for the
contracts, recorded here because it is a task-planning decision, not a product one. Check results
can change it.

**Branching.** One feature branch, `feat/options-scoping`, until the capability is ready for users.
Each task has its own sub-branch, contract, rubric and full review stack, and a PR into the feature
branch (`verify.yml` runs on every pull request, whatever its base). `dev` is merged into the feature
branch after each task lands. The final merge into `dev` is a merge commit, not a squash, so the task
commits survive; that needs the ruleset's one-off break-glass. Task branches are not deleted with
`--delete-branch` while a later task is stacked on them. The capability picker stays off in production
until the last task.

**Five tasks, in order.** Task numbers are assigned at contract time (035 was reserved before the
split; 036–038 are taken).

1. **Task shell and baseline.** The options-scoping task kind; the plan with its slots and the three
   constraint kinds; the task tabs (Agent · Result · Sources · Share · History); `inherit` in the
   scoping direction for the plan and the document pool, with inherited-versus-added accounting; the
   ⟨baseline⟩ composition and template with "what is contested"; the pause-and-confirm gate; the
   Baseline view. No option entity yet: there are no options to store. Ends with a scoping task that
   has a confirmed plan and a baseline. Gated on check 6.
2. **Longlist.** The abstract extraction profile; `longlist`, which **mints the option entity** as
   declared in `data-model.md` (stable task-scoped id, versioned specified design, primary and
   secondary lever type, ambition tag, theme, variant-of and part-of relations, included and excluded
   states with the constraint record behind an exclusion, mention-grain membership, origin including
   "from your evidence search"); the part of `inherit` that turns a linked report's interventions into
   suggestions; `constrain`; the list view and the option card with its source-quality profile. The
   Result at this stage is the longlist (ruling 50). The first demoable milestone and the riskiest
   task. Gated on check 3 (and 2).
3. **Shortlist and assessment.** `shortlist` with its reasons and gap messages; the grid and
   shortlist views; add, remove and exclude from the view and the chat; the "Assess these N" gate;
   the scoping `select` strategy; the light extraction profile; the profile template; the
   transferability working block (new column-grounded block kind); the assessed report; the
   comparison view; post-assessment constraint checks. Extends the option entity with the shortlist
   membership record and the assessed cells. The largest task. Gated on checks 4 and 5.
4. **Sense-check, Sources and export.** The sense-check entry branch (short plan, light baseline
   still paused, neighbours at metadata depth, the named option alone through the gate, questions to
   put to the department; the standard variant with similar neighbours plus one challenger); depth as
   a setting in both branches; the Sources tab additions (statuses set aside / read in full / abstract
   only / not read under the cap, By option); export through Share. Placed before the full run because
   the sense-check is one of the two primary jobs (ruling 29).
5. **Full run (deferrable).** The child Evidence search task written with the profile template and
   computing the judgement cells (ruling 41); `inherit` in the Evidence search direction (ruling 48);
   one document in two homes (ruling 47); History. Extends the option entity with the child-task link.
   Kept separate because it is the only task that changes the live Evidence search (a prompt-bearing
   template and a declared boundary widening, which want their own ADR). It can wait for a later round
   if the live-ask check shows people stopping at the assessed report.

**Alongside.** The eval slice of ruling 27 (four behavioural tests on live asks; recall floor) runs
next to the tasks, not inside one.

