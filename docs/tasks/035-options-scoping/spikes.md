# Options scoping — spikes before any contract

Source: concept ruling 42 (`docs/specs/sources/options-scoping/options-scoping-concept.md`), which
adopted the third review pass's six spikes in its order. A spike order is an order for resolving
uncertainty, not a build order (ruling 28). Each section: the question, the smallest informative
method, who does it, what it depends on, and the result that would change the design.

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
- **Depends on.** Spike 6 for the field lists; the light and abstract extraction profiles drafted.
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
- **Depends on.** Spike 6; the abstract extraction profile.
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
- **Depends on.** A transferability prompt and the column-grounded block (from spike 3's profile
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
- **Depends on.** Spike 3; a working select strategy and light profile.
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
