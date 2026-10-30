# Spec update log

## 2026-10-30 (task 054, evidence fit)
* **Update**: [Theory of change components](capabilities/theory-of-change/components.md): after a
  fit review of run 9 (15 of 65 documents, 8 of 38 link figures, 9 of 18 box figures and 8 of 22
  case studies misfit), `toc_judge_v8` requires the step's source to happen (else not_about;
  "refutes" means the source happened and the target did not follow), caps evidence from
  another channel or a rule that removes nothing at weak support and relevance 1, and sees
  "Alongside" steps (other links into the same target or out of the same source); a case study
  must show the box itself, and is kept only from a document about the step. `toc_figures_v3`
  sees the link sentence, the judge's support and quote and the neighbouring steps, and keeps
  to the judge's finding. `toc_summary_v4` may leave "seen in" empty
  (`toc_summary_v5`, same day: a box with case studies normally gets one, including a case where
  the change failed, its mirror image, or a modelled estimate; empty only when every case study is
  about another product, channel or kind of rule). A box shows a level only
  from a document of relevance 2 or more.

## 2026-10-30 (task 054, verdict calibration and report navigation)
* **Update**: [Theory of change components](capabilities/theory-of-change/components.md) and
  ADR 0042's verdict rule: six verdicts, "Not sure" dropped. Not enough evidence (W < 4/9);
  Leaning supports / Leaning against (some evidence, or enough but not clear-cut, average
  support beyond ±0.5); Confident (W ≥ 1, S̄ ≥ 1, under 25% refuting, was 15%); Mixed;
  Not confident (S̄ ≤ −1, was −0.5). Calibrated over six runs (123 links). Keys
  `not_sure_mixed` and `not_sure_insufficient` keep their names. Prompts `toc_choose_v3` and
  `toc_report_v3` name the new verdicts. The Result page gains the Evidence search's contents
  sidebar (Canvas, then the report's sections); the report loses its "Detailed information"
  heading and "Sources" becomes "References"; a code clicked in the report centres the canvas
  on it; clicking an evidence-balance block opens its citation.

## 2026-10-29 (task 054, presentation round 4)
* **Update**: [Theory of change components](capabilities/theory-of-change/components.md): the
  label is "Critical connection" (no "test this first"); hovering it gives the rule: the weakest
  step on the kept pathways (lowest verdict), ties to the one most pathways pass through. The
  warning triangle sits at the middle of the route. Sidebar section labels are blue, part labels
  bold body ink; source lines and judgement lines are body ink, not grey. Hovering or focusing a
  block of the evidence balance shows its document as the document list does. In a connection's
  Evidence, the balance and its sentence come before Size of change. Tooltips, like sidebars,
  open inside full screen.

## 2026-10-29 (task 054, presentation round 3)
* **Update**: [Theory of change components](capabilities/theory-of-change/components.md): the
  critical connection carries a red warning triangle on its line instead of a thicker line (key,
  reading guide and panel header too). A box panel has one Evidence section: the "seen in" note,
  Size of change, then Case studies, each study one item (programme and place, note, source line
  with its title, quote). Sidebar labels and listed items are body size. Citation sidebars open
  inside full screen. The "Figures come from the documents' abstracts" line is removed.

## 2026-10-29 (task 054, presentation round 2)
* **Update**: [Theory of change components](capabilities/theory-of-change/components.md): a
  link's "How this works" is one sentence with **If**, **for**, **then** and **because** in bold;
  hovering a block of the evidence balance names its document; the "close to the threshold"
  sentence is gone; sidebar items (documents, figures, case studies) share one title, source-line
  and quote style. A chosen pathway also shows the inputs and outputs that feed it. The last
  report section is "Sources", listed as the Evidence search lists references (title, authors,
  year, venue); the method note is no longer shown. The canvas dividers follow the view instead
  of being very long nodes, which made panning slow.

## 2026-10-29 (task 054, presentation of information)
* **Update**: [Theory of change components](capabilities/theory-of-change/components.md): the
  Result page's title and summary come from the report; each link has a short title, and its
  panel reads title and verdict, how it works, then one Evidence section (size of change with a
  plain statement per figure, the balance, the cited sentence, the numbered documents); box panels
  show "How we'd know it happened" and a "seen in" note from case studies; citations open the
  Evidence search's source sidebar with the quote in context; the canvas dividers run edge to
  edge. The summary step no longer writes header paragraphs or evaluation questions.

## 2026-10-28 (task 054, narrative Detailed information)
* **Update**: [Theory of change components](capabilities/theory-of-change/components.md):
  Detailed information is now a short narrative report in five sections (Summary, How change
  happens, Assumptions and evidence, What to test and measure, Sources and method), written by one
  call on every check, with every code and source number checked by code and the source list and
  method note written by code. Codes in the text select their box or link on the canvas. It
  replaces the summary's header paragraphs and evaluation questions. Task 054 contract C38.

## 2026-10-28 (task 054, size of change)
* **Update**: [Theory of change components](capabilities/theory-of-change/components.md): a new
  step after the judge finds up to three figures per supporting or refuting document (how much the
  effect changed, or a baseline level), keeps only those whose quote and number are in the
  abstract, and shows them as "Size of change" in the link panel (a range across studies, never an
  average) and as "Figures" on a box. Task 054 contract C37.

## 2026-10-28 (task 054, one evidence verdict per link)
* **Update**: [Theory of change components](capabilities/theory-of-change/components.md): each
  link now has one evidence verdict (Confident, Not sure: mixed, Not sure: too little evidence,
  Not confident: evidence against) instead of two grades, computed from each document's support,
  quality and relevance to this population and place (a simplified BEAM). The judge, choose and
  summary steps follow; the canvas shows the verdict by line style, and the link panel shows the
  evidence balance. Task 054 contract C36; ADR 0042 amendment.

## 2026-10-28 (task 054, Magenta Book layers and short codes)
* **Update**: [Theory of change components](capabilities/theory-of-change/components.md): the
  outcome layer splits into short-term and long-term outcomes, with fixed allowed steps (only
  long-term outcomes lead to an impact); stored outcome boxes become short-term. Every box and link
  gets a short code (`S3`, `#5`) that is never reused, shown on the canvas and in the panels, and
  the canvas draws the accountability ceiling after the outputs. Task 054 contract C34 and C35.

## 2026-10-27 (task 054, searches for discovered links)
* **Update**: [Theory of change components](capabilities/theory-of-change/components.md): after
  merge, each kept link that discovery added gets its own light search and pick, as the first
  links do, instead of only borrowing the closest documents from the pool. Task 054 contract C32.

## 2026-10-27 (task 054, study-design search and classify after the judge)
* **Update**: [Theory of change components](capabilities/theory-of-change/components.md): each
  link search adds one generated keyword query, run with the systematic-review and trial clauses
  (5 search calls and 1 generation call per link, up to 60 documents). Each link's pick also sees
  the 10 documents from the other links' searches closest to it, so a study found for one step
  can serve another. Classify and appraise now run after the judge, only on documents it found
  on topic. Crossref lookups respect its limit of 3 at a time. Task 054 contract C31.

## 2026-10-27 (task 054, pick call, box folds, trusted publishers)
* **Update**: [Theory of change components](capabilities/theory-of-change/components.md): one
  small model call per link now picks the 10 documents the judge reads (6 of 38 key studies
  judged in the eval, against 3 for round-robin), with round-robin as the top-up and fallback.
  Merge also folds boxes that name the same change (same layer, never a user's box into a model
  one), re-pointing and de-duplicating links. Links only on set-aside pathways are not checked.
  Web pages from trusted publishers (gov.uk, ONS, NHS, Ofcom, ASA, What Works Centres and others,
  in one committed list) count by their appraisal score. Missing abstracts come from Crossref.
  Each walk's finish event carries its token totals and a dollar estimate. Task 054 contract C28
  to C30.

## 2026-10-27 (task 054, light link check)
* **Update**: [Theory of change components](capabilities/theory-of-change/components.md): each
  link's item search now searches the link sentence by meaning (two OpenAlex calls and one
  Overton call, no query generation, the Evidence search's new `link` depth) and keeps every
  distinct result. A code step, `toc_select`, replaces the model screen in the check walk: it
  picks 10 documents per link (in turn from the three result lists, documents with an abstract
  first) and screens out the rest; the rule is expected to change after a pick-rule experiment.
  The judge reads up to 10 documents per link with no rerank; a link added by discovery reads the
  10 closest by meaning. The last live run's rerank alone took about 65 minutes. Task 054
  contract C27, replacing C24's record cap and box-list screen.

## 2026-10-27 (task 054, discovery consolidates)
* **Update**: [Theory of change components](capabilities/theory-of-change/components.md): discover's
  batch proposals are joined by one `toc_consolidate_v1` call before anything is written: repeats
  merged, boxes reused, at most 3 new success and 2 new failure pathways. The second live run had
  written 53 boxes and 80 links because parallel batches could not see each other's boxes. The
  check screen lists the theory's boxes, not link sentences, to fit the screen's 1,000-character
  limit. Task 054 contract C24 to C26.

## 2026-10-27 (task 054, judge v4)
* **Update**: [Theory of change components](capabilities/theory-of-change/components.md): the
  judge prompt is `toc_judge_v4`. It names the step's source and target as "the test", counts a
  study that changes a close proxy of the source and measures the target, treats a document with
  no data of its own as not about the step, and decides first whether the step depends on place
  before it answers "holds here". In a 34-document labelled experiment (3 repeats) it was right on
  97 of 102 judgements against 92 for v3, and more consistent. Adding the whole theory and the
  policy to the call made results worse, so it is not sent. A local `openai-6x` model route
  (gpt-6-luna, gpt-6.1-terra, gpt-6.1-sol) is added; staging and prod are unchanged.

## 2026-10-27 (task 054, arm B)
* **Update**: [Theory of change components](capabilities/theory-of-change/components.md): each
  item search's record cap goes from 20 to 40, and the check walk's screen judges documents against
  the steps it covers (any setting, any intervention) instead of the whole theory, after the
  offline search eval's arm B won (owner approved). A live run had screened out 13 of 20 relevant
  documents, including the decisive trials for a mid-chain step. Task 054 contract C24.

## 2026-10-27 (task 054, web pages)
* **Update**: [Theory of change](capabilities/theory-of-change/capability.md) § Trust rules: web
  pages are classified and appraised like any document; a page from a trusted publisher (configured
  list) counts by its appraisal score, any other page keeps the cap at *weak* (owner: "If it comes
  from Eval Task Force, for example, it could be quite strong"). Task 054 contract C23; ADR 0042
  amended.

## 2026-10-27 (task 054, iteration loop 2)
* **Update**: [Theory of change](capabilities/theory-of-change/capability.md): conditions are 0 to 2
  per link, only those most likely to fail here, each once in the whole theory; E1 checks that
  rule instead of "at least one condition" (owner: "way too many assumptions … quite a few
  duplicates"). Task 054 contract C22 records the loop's other rulings (case studies capped at 5,
  the judge's neighbouring-step and place-independent condition rules, authors, quote in context,
  page and canvas fixes); plan 2.3 adds moving boxes with Reset layout for increment 2.

## 2026-10-26 (design close, task 054)
* **Update**: task 054 contract spec changes 2–5 applied at the plan gate (owner: "Approve!"),
  with [ADR 0042](../adr/0042-theory-of-change-task-kind.md):
  [ToC capability](capabilities/theory-of-change/capability.md) § Product surface gains the
  server setting, the empty lattice and the plan-change choice;
  [OS capability](capabilities/options-scoping/capability.md) "start a theory of change" moves
  from ⏸ to ✅; [execution-orchestration](system/execution-orchestration.md) opens the open-web
  backend for the ToC check walk only; [product.md](product.md) puts Theory of change in scope
  behind a build flag. Spec change 1 (components) was applied earlier the same day.

## 2026-10-26
* **Update**: [Theory of change](capabilities/theory-of-change/capability.md) § Trust rules: a
  link and its assumptions answer different questions, get their own judge question and grade, and
  never share judgements (owner: "add these changes you've listed"). Components § item_evidence
  and eval E5 updated to match. Found while reviewing the task 054 wireframes.
* **Update**: [Theory of change](capabilities/theory-of-change/capability.md): the *supports under
  conditions* stance and the *holds under conditions* flag are removed; a support may record a
  condition, and conditions no assumption covers go to consolidate as candidate assumptions
  (owner: "under conditions is implied, and should be covered by Assumptions"). The link panel
  lists its assumptions after its evidence. Task 054 contract § Terms amended to match; schema
  unchanged.
* **Update**: [Theory of change](capabilities/theory-of-change/capability.md): summarise writes one
  evidence sentence per box, link and assumption, citing only that item's judged documents, checked
  by code (owner: "yes, add them to spec"). Components § summarise updated to match.
* **Update**: [Theory of change](capabilities/theory-of-change/capability.md): inputs boxes are
  searched and graded too, with delivery case studies (owner: "Inputs also can get evidence/case
  study notes"). Components § Items gives the input item text. Task 054 contract § Terms amended.
* **Update**: [Theory of change](capabilities/theory-of-change/capability.md): only links and
  assumptions are searched and graded; boxes are neutral and show result criteria, case studies
  and indicators drawn from their links' documents (owner: "Let's go with neutral boxes. Rest of
  the suggestions sound good"; White 2009, Mayne 2015 and 2017, Funnell and Rogers 2011). This
  replaces S3's box searches and the same day's input searches. § Output structure rewritten to
  the reviewed wireframes. Components § Items, § item_evidence, § summarise and § Data updated.
  Task 054 contract § Wireframe review amendments W1–W10.
* **Update**: [Theory of change](capabilities/theory-of-change/capability.md) § Trust rules: a
  link's evidence answers "did it work elsewhere", an assumption's "will this condition hold here";
  an assumption never restates its link's mechanism; no shared quotes; E1 restatement check;
  components § Items assumption text names population and place (owner: "Yes let's apply it").
  Task 054 contract W11.
* **Update**: [Theory of change](capabilities/theory-of-change/capability.md): each box gets a
  two-sentence description citing its case studies; link sentences read as one paragraph (owner:
  "more into a narrative - still short"). Task 054 contract W7 extended.
* **Update**: [Theory of change](capabilities/theory-of-change/capability.md) § Rulings: journey
  rulings J1–J9 (option entry reuses the option; at most two questions; draft message; run
  notification; per-change Undo; canvas and Detailed information equal; stress test always
  suggested; PDF and PowerPoint both matter; staleness postponed). § Editing during the check
  updated for per-change Undo. Task 054 contract W12–W13.
* **Update**: [Theory of change](capabilities/theory-of-change/capability.md): no separate
  assumptions. Every link answers *worked elsewhere* and *holds here* (Cartwright and Hardie 2012),
  and its conditions hold the Magenta Book's assumptions; the canvas colours a link by the lower
  grade and marks one critical connection; Detailed information shows a link as three paragraphs
  without repeating evidence (owner: "the evidence for each connection is in fact the
  Assumption"). Vocabulary, Pipeline, Output structure, Trust rules, Product surface, Evaluation
  and components § Items, item_evidence, summarise and Data updated. Task 054 contract W14.
* **Update**: [Theory of change](capabilities/theory-of-change/capability.md) § Trust rules: a
  modelling study the judge marks robust counts as score 3 in the ToC grade rule, so it can
  support *medium*, never *strong*; the shared appraisal is unchanged (owner: "if modelling is
  robust, then it could be upgraded to Medium evidence"). Task 054 contract W15.
* **Update**: [Theory of change](capabilities/theory-of-change/capability.md) § Pipeline: the
  check order is discover → merge → judge → choose; consolidate splits around the judge (owner:
  "first elucidate missing pathways, consolidate them and then judge them all together").
  Components skeleton and task 054 contract C6, W16 and plan chain updated.
* **Update**: [Theory of change](capabilities/theory-of-change/capability.md) § Editing during
  the check: an edit flags the link *Edited · check pending* and keeps its evidence; the user
  chooses Keep the evidence or a minimal Check again (same-meaning call first, then re-judge only
  documents already found, then optionally Search for more); no automatic follow-up pass. Status
  table updated (owner: "Policy Atlas should simply flag that there has been a user edit").
  Task 054 contract W17.
* **Update**: [Theory of change](capabilities/theory-of-change/capability.md): Detailed
  information gains an **Assumptions** section listing every condition, grouped by the Magenta
  Book's types (computed from layers), with its *holds here* grade, so the PDF report keeps the
  purpose of the assumptions band (owner: "let's add that assumptions list"). Vocabulary gains
  *Assumption type*. Task 054 contract W18 (2026-10-26).

## 2026-10-23
* **Creation**: [Theory of change capability](capabilities/theory-of-change/capability.md) and
  [components](capabilities/theory-of-change/components.md), a draft for owner review (task 054).
  Sources: the task 054 approach note and the `stakeholder_atlas` ToC prototype. Every decision is
  🟡 or ❓ until the owner rules on the open questions.
* **Update**: owner rulings R1–R16 of the same day applied (Magenta Book layout, four layers,
  pathways drafted then checked then consolidated, background check while editing, web search,
  image import, exports, evals). Research behind them:
  `docs/tasks/054-toc-integration/research-notes.md`. Open: Q4, Q8, Q14, Q17–Q20.
* **Update**: second round of owner rulings S1–S11 (Magenta Book layers Inputs, Outputs,
  Outcomes, Impact; strong/medium/weak grades with flags; box searches with case studies; OpenAI web
  search; uploads kept in S3; one "Design a theory of change" button on the option page).
* **Update**: third round: `source_option_id` column; option documents shared, not duplicated;
  on the Bedrock route, web search calls go to Bedrock's US endpoint. No owner questions remain open.

## 2026-10-12
Task 046 (the longlist refinement), contract § Spec changes, applied at the step-7 review on the
owner's word ("Make the spec changes"; items 1–17 of `spec-changes-proposed.md` and the amendment 3
and 4 items of the contract). Items that amendments 3 and 4 superseded are applied in their final
form, so the specs describe the system as built. Contract:
`docs/tasks/046-longlist-refinement/contract.md`; decisions in ADR 0040.
* **Update** (item 1; R1, R2, R9, R14; owner: "even 40 feels like a lot of options to expect the
  user to decide on" · "user options aren't folded"): [OS components § 6](capabilities/options-scoping/components.md)
  and [OS capability § Longlist](capabilities/options-scoping/capability.md) — reader grain; target 20,
  ceiling 25 in place of the formula; the corpus digest; the fold and *also found as*; the residual
  pass; the flag's meaning; discovery mints no package; lever list v2; open question 4 closed.
* **Update** (item 2; R3, R17, R63, R72, R73, R87): [OS components § 2–5 and § 10](capabilities/options-scoping/components.md)
  — the record's fields (unit, outcome, programme name, study geography and study country) and the
  three tags against the plan; the setting and place rules; title-only documents are not profiled.
* **Update** (item 3; R13, R15, R18, R19; owner: "remove ingest, full text fetched in task 3" · "we
  shouldn't let that stop potentially transferable evidence not getting in at the screen step"):
  [OS components § 2–5 and ⟨longlist depth⟩](capabilities/options-scoping/components.md) and
  [OS capability § Depths and modes, § Plan](capabilities/options-scoping/capability.md) — no ingest at
  longlist depth; the option search only acquires in a longlist walk and the pool is screened once;
  the screen input is the wide target unit and the outcomes, no setting.
* **Update** (item 3a; R19; owner: "We should separate the target unit … from the target
  intervention setting and geography"): [OS components § 1](capabilities/options-scoping/components.md),
  [OS capability § Plan](capabilities/options-scoping/capability.md) and
  [plan-as-object § What a plan contains](system/plan-as-object.md) — target unit, setting and place
  kept apart.
* **Update** (item 4; R4, R21, item 5; R74, the strip deleted on the owner's ruling 2026-10-12):
  [OS components § 7](capabilities/options-scoping/components.md), [OS capability § Screening](capabilities/options-scoping/capability.md)
  and [OS trust § Screening](capabilities/options-scoping/trust.md) — the option judged as a kind of
  action; place never reaches `constrain`, by a rule in words; a wider population never excludes;
  the pathway rule; the distinct screen over the whole list.
* **Update** (items 5, 13 and the amendment 4 items 10–12; R42, R43, R60–R68, R76–R90; owner: "Let's
  move the estimates to above the evidence" · "Shall we just remove them?" · "Let's keep
  evaluated/evaluations for now"): [OS capability § Output structure (Longlist)](capabilities/options-scoping/capability.md)
  — the list header, no facets, the row's grey line and the evidence signal, the grid cell limit;
  the card: the callout, How it works, What it would take (Policy Atlas's estimate; seven cells with
  "Middle"), Evidence (the opener, Your outcomes, the place sentences, the Documents disclosure);
  thin and empty cards; the vocabulary rule. *Tried on* as a line and a facet, the where-tried
  groups, the examples block and the transferability line are gone.
* **Update** (item 6; item 9, R13; owner: "using the baseline more to inform judgements … is
  especially important"): [OS capability § Baseline](capabilities/options-scoping/capability.md) — the
  baseline is the reference for every judgement after it; task 3 fetches full text for shortlisted
  options.
* **Update** (items 7, 12, 16; R90): [vocabulary.md](vocabulary.md) — reader grain, boundary,
  consideration, preference, option profile, line, mark, authority label, setting, tried on and
  measures as folded kinds, evidence signal, place sentence, describing document, also found as;
  option search, intervention profile and where tried redefined.
* **Update** (item 8): [decision sheet rows A9 and E4](../tasks/035-options-scoping/checks/decision-sheet.md).
* **Update** (items 10–12, amendment 2; R34, R36–R38, R40, R43, R53, R58, R70; owner: "Yes these 5
  kinds feel right." · "I think it is its own step." · "Why don't we just run profile before
  constrain" · "Yes leave as is"): [OS components § 1, § 6, new § 6a, § 7 and the table](capabilities/options-scoping/components.md),
  [OS capability § Plan, § Four kinds of constraint](capabilities/options-scoping/capability.md) and
  [plan-as-object](system/plan-as-object.md) — the four kinds of statement; the aim and the
  who-can-act question; `option_profile` as a spine component; ambition relative to the list; the
  authority label.
* **Update** (item 14; R44; owner: "we don't need 'a guess, not evidence', it sounds too
  LLM-generated."): [OS trust § Reasoned guesses](capabilities/options-scoping/trust.md) — the label
  sits on the block heading.
* **Update** (item 15; R47; owner: "the guesses are useful for how the shortlist selects"):
  [OS capability § Shortlist](capabilities/options-scoping/capability.md) — the task 3 principle for
  the cut; rulings 12 and 19 reopened for the profile only.
* **Update** (amendment 3 items; R54–R59, R64, R66, R67; owner: "is population the right concept"
  · "that OECD rule feels weak" · "just because a document is published in one country, it doesn't
  necessarily mean that's where the option was tried"): [OS components § 2–5, § 6, § 6a](capabilities/options-scoping/components.md)
  and [vocabulary.md](vocabulary.md) — `unit` in place of population; the folding calls; where
  tried in two levels from `study_country`; the dossier's records slot.
* **Update** (AM12): [OS trust § Provenance labels](capabilities/options-scoping/trust.md) and
  [OS capability § Depths and modes](capabilities/options-scoping/capability.md) — the *scoping pass*
  label reads "at the longlist, abstracts only".

## 2026-09-28
* **Update**: [OS components](capabilities/options-scoping/components.md) and
  [OS capability](capabilities/options-scoping/capability.md) — `theme` is a component of its own
  after `constrain` (§ 7a): it groups the included options into themes; `longlist` no longer makes
  themes. Owner ruling R28, task 046 contract; ADR 0040 decision 5. Wording accepted by the owner
  2026-09-28 ("Looks good").

## 2026-09-24
Task 045 step-7 review (contract-verifier finding F1: D33 had removed the words from the card
while the trust rule still required them). Contract: `docs/tasks/045-scoping-longlist/contract.md`.
* **Update** (task 045, review F1; owner: "D33 wins, amend trust.md"):
  [OS trust § The principle](capabilities/options-scoping/trust.md) and
  [OS capability § Longlist](capabilities/options-scoping/capability.md) — the ambition tag stays a
  tier-4 reasoning claim; the option card no longer carries the words "as described, not measured".
* **Update** (task 045, review P1; owner: "If there are duplicate options, then shouldn't they be
  merged instead of one being excluded? …" and "Fold into the kept option"):
  [OS components § 7](capabilities/options-scoping/components.md) — a *distinct* breach merges the
  duplicate into the kept option instead of excluding it.
* **Update** (task 045, review deviation 46; owner: "Also allow empty reasons via the button"):
  [OS components § 7](capabilities/options-scoping/components.md) — the user's exclusion never
  requires a reason.

## 2026-09-23
Task 045 (the options-scoping longlist), contract § Spec changes, applied in its phase 8 with the
owner's words quoted (item 10, the decision sheet, landed at plan approval). Contract:
`docs/tasks/045-scoping-longlist/contract.md`.
* **Update** (task 045, item 1; D19 accepted, D22 "Should be a default preference"):
  [OS components § 1](capabilities/options-scoping/components.md) and
  [plan-as-object § What a plan contains](system/plan-as-object.md) — the optional plan slot
  *Options you already have in mind* (the user's words, a design proposed back, each an entrant with
  its option search) and the default preference "Transferable to *Where*" on every scoping plan.
* **Update** (task 045, item 2; D20, D21, D6, D25 — "Directly saying Z in the search scope may
  constrain the results too much"; "let's go with option search"):
  [OS components § 2–5](capabilities/options-scoping/components.md) and
  [OS capability § Pipeline and gates](capabilities/options-scoping/capability.md) (Plan) — the
  longlist intent is PICO-shaped without Where; Where enters nothing in retrieval and is shown as
  *where tried*; setting is the optional S; an entrant's own search is the **option search**, a
  child walk; "mini evidence search" stays the assessment-depth term.
* **Update** (task 045, item 3; D3 owner naming, D4, D7 "free with the checklist", A15, D8, D11):
  [OS components § 6](capabilities/options-scoping/components.md) (and the table, compositions,
  § 0, § 2–5, interface ruling 1) and [OS capability](capabilities/options-scoping/capability.md)
  — "abstract profile" → **intervention profile** and "intervention mention" →
  **`intervention_profile_record`** in the living specs (not the frozen sources); suggest first
  with the linked report as input; seeded assignment under `clamp(ceil(N/4), 8, 40)`; the
  assignment reason and `design_feature_not_stated` flag on membership; the taxonomy version and
  *none fits*; the 🟡 "unproven at option grain" closes on check 3; open question 5 closes.
* **Update** (task 045, item 4; D9 "the ruling stands, deterministic check", D22):
  [OS components § 7](capabilities/options-scoping/components.md),
  [OS capability § Three kinds of constraint](capabilities/options-scoping/capability.md) and
  [OS trust § Reasoned guesses](capabilities/options-scoping/trust.md) — "no in-scope evidence" is
  computed from publication metadata; the transferability preference carries no guess.
* **Update** (task 045, item 5; D12 "reduced grid in task 2", D15 "Assembled in task 2, on-demand
  summary as a seam", D20): [OS capability § Output structure](capabilities/options-scoping/capability.md)
  (Longlist) — the reduced grid before the proposal; the assembled option page and the on-demand
  summary seam; the where-tried line and facet.
* **Update** (task 045, item 6; A3 "origin stays the original source; inherited = created by the
  inherit step", D23): [OS components § 0](capabilities/options-scoping/components.md) and
  [data-model](system/data-model.md) § Corpus, § The findings layer, § The option entity, § Links
  between tasks — inherited rows keep their origin; classification and appraisal read across
  through one resolver; `intervention_profile_record`; the option tables; `task_link.option_id`
  (unique per pair, noted for task 5 — A21); `capability_run.parent_capability_run_id`.
* **Update** (task 045, item 7; D1, D13 "chat verbs in task 2, buttons as the second way", D14,
  A2, A23, P4, P16a "card route stays 204"): [web-api](system/web-api.md) § Tasks, § Task Agent
  turns, § Runs, § Check-ins, § Read models — the longlist routes, the longlist verbs, the two
  confirm surfaces opening the longlist walk, `active_run` and `has_longlist`, `your_options` and
  the default preference on the plan bodies, child walks on the run stream.
* **Update** (task 045, item 8; D2 "start there, measure, I'll set it after"; "cap at 15, run the
  live check at rapid"): [plan-as-object § Thoroughness](system/plan-as-object.md) — broad search
  50 · 25 per backend (standard · rapid), option search 10 per backend, at most 15 option searches
  per walk at width 4; the owner sets the final numbers after measurement.
* **Update** (task 045, item 9; owner naming 2026-09-22): [vocabulary.md](vocabulary.md) — entrant,
  option search, child walk, intervention profile, `intervention_profile_record`, where tried.
* **Update** (task 045, item 11; D3, D24 "Yes, selection-free, record it as an edit to those
  rows"): [ES components § 7](capabilities/evidence-search/components.md) — the third profile and
  the selection-free path; § 0's inherited "abstract profiles" renamed; § 1 acquire unchanged.

## 2026-09-17
* **Update** (task 044, phase 8; owner ruling "Go with options 2 and 5, targets 20 and 10"): the
  depth sets the baseline's acquisition target and proposed-section allowance —
  [OS capability](capabilities/options-scoping/capability.md) § Output structure,
  [OS components](capabilities/options-scoping/components.md) § 11 and
  [plan-as-object](system/plan-as-object.md) § Thoroughness. Rapid: the same eight required sections,
  no proposed sections, acquisition target 10 per search backend. Standard: eight plus up to two proposed, target 20
  per backend (was one target of 25 per backend; "per backend" made explicit on 2026-09-18 — owner:
  "Add per backend to the docs", after the 044 review stack found the four documents read as totals). A five-section rapid merge was built, measured (no shorter write: 168 s and
  189 s against 183 s for seven) and reverted the same day on the owner's ruling. Re-revises the
  2026-09-09 "one shape at every depth" line after the measured 4.3 to 7.5 minute baselines.

## 2026-09-09
* **Update** (task 044, deliverable 2): the abbreviation **EB → ES** across the
  living specs, `docs/tasks/_templates/`, `docs/agentic-ops/` and code comments
  (the four "EB handoff" citations of the frozen source keep their name; ADRs,
  merged task docs, frozen sources and this log's past entries untouched);
  the Task Agent code names in [web-api.md](system/web-api.md) and
  `docs/knowledge/` content (`planning` → `task_agent`, `/planning-turns` →
  `/task-agent-turns`, `planning_transcript` → `task_agent_transcript`).
* **Update** (task 044, contract § Spec changes 7; plan-review P9):
  [web-api.md](system/web-api.md) § Task Agent turns and § Check-ins — a
  sorted, non-approving Task Agent turn is admitted while an Options scoping
  walk is **paused** (question → the answer core; decision → the check-in
  response transaction); the approving branch and `PATCH /plan` stay 409
  `run_active` while a walk is running or paused. Owner ruling D9
  (2026-09-09): the gate is answered in the Task Agent chat; routing hangs on
  the turn, not the conversation kind. New: check-in kind `baseline_confirm`,
  `POST /tasks/{id}/plan/confirm-baseline`, `POST /tasks` with `capability`,
  `project_ids` and `from_task_ids` in one transaction.
* **Update** (task 044, owner ruling 2026-09-09 "option 2"):
  [prompting.md](system/prompting.md) / ES components § 9 — the synthesis
  section writer is **template-keyed**: one writer, a shared core plus a
  preamble per output kind (report · baseline; profile and scoping report
  arrive with tasks 3 and 5); the Evidence search assembly is byte-identical
  and pinned by a test.

## 2026-09-09
* **Update** (owner rulings at the task 044 contract interview; applied with the owner's words
  quoted): [OS capability § Output structure](capabilities/options-scoping/capability.md) and
  [OS components § 11](capabilities/options-scoping/components.md) — the baseline's eight sections are
  required and the writer may add up to two problem-specific sections; one shape at every depth.
  [plan-as-object § Thoroughness](system/plan-as-object.md) — the baseline is not graded by depth
  (revises decision-sheet row E12's baseline part); one measured compute target; the latency
  levers. [OS capability § Check-in points](capabilities/options-scoping/capability.md) and
  [OS components](capabilities/options-scoping/components.md) — the two structural gates pass on
  standing defaults in unattended mode, recorded and flagged; unattended is never the default.
  [vocabulary.md](vocabulary.md) — the Task Agent's code names (`task_agent`).
* **Update** (owner rulings at the task 044 contract re-approval, after the adversarial reviews):
  [plan-as-object § Plan vs config](system/plan-as-object.md) — plan ↔ turn provenance is at
  **version grain**, not field grain; [plan-as-object § Thoroughness](system/plan-as-object.md) —
  the baseline is written sequentially, with a development-time feasibility check against a
  parallel version; no parallel mode in the product without a revision of the durability contract.

## 2026-09-09
* **Update**: Owner rulings on the sixteen pre-task-1 rows of the options-scoping decision sheet
  (`docs/tasks/035-options-scoping/checks/decision-sheet.md`), decided one at a time and applied
  with the ruling quoted. [data-model](system/data-model.md): a generic task-to-task **`task_link`**
  (many-to-many, same project only, no purpose column; `inherit` reads across a link and copies
  nothing beyond the receiving task's own document rows and screening; archive-not-delete for linked
  tasks); inherited documents need no column (inherited = created by the inherit run); linked
  findings read across the link and reused piecemeal, memo unchanged; document identity across
  snapshots deferred to an Evidence search slice (`docs/deferred.md`); `setting` generalised to where
  the target unit experiences the intervention; a stub-page ingest defect noted (issue #74).
  [plan-as-object](system/plan-as-object.md): "face" retired ("where we search" / "what may be cited
  as support"); the **evidence restriction** of OS ruling 23 is the existing search directive's
  filters at retrieval; a **Your context** plan section (present fact / commitment, verbatim words,
  turn provenance, attribution by user id, an entry may be flagged "test this as a condition");
  **Where** defaults to the United Kingdom and setting is an optional scope-shaped constraint;
  several intent records per plan; time managed by design targets not run-time cut-offs (baseline
  ≈ 2 min rapid / 5 min standard), no small reading cap, compute and waiting time stated separately,
  no rapid number promised. [provenance-grounding](system/provenance-grounding.md): the retrieved
  cell reads existing source and finding fields (D3 folded into C3). [OS components](capabilities/options-scoping/components.md),
  [OS capability](capabilities/options-scoping/capability.md), [OS trust](capabilities/options-scoping/trust.md)
  and [EB components](capabilities/evidence-search/components.md) § 0 aligned. Frozen sources untouched.
## 2026-10-09
* **Update**: Evidence search [components.md](capabilities/evidence-search/components.md) §1 acquire
  and §2 screen describe the task 051 build ([ADR 0038](../adr/0038-single-pass-search-and-adaptive-screen.md)):
  one search pass at every scope (keyword + semantic seeds, backward and forward citation chasing,
  two specificity-ranked pools cut at a papers cap and a policy cap, Overton in relevance order with
  cited landmarks) replaces the task 015 acquire↔screen round loop, and the stage-1 screen's
  three-sample majority becomes an adaptive one-or-two-call vote on `screen_v4`.

## 2026-09-08
* **Update**: Options scoping board refinement — concept rulings 45–47 (the report stays linear with
  verdict strips, the comparison table is the shortlist view after assessment; the Sources tab is
  the Evidence search's Sources component plus read-depth and set-aside statuses; one document after
  a full run: the child task's report is the profile, shown in place, no mirror). Boards 6, 6b, 7b
  and 7c redrawn, board 6c added; [capability.md](capabilities/options-scoping/capability.md)
  (product surface, report sections, Sources tab, full evidence search) and
  [components.md](capabilities/options-scoping/components.md) (⟨full run⟩) amended;
  [source README](sources/options-scoping/README.md) updated.
* **Update**: `inherit` becomes a **shared component** (options-scoping concept ruling 48): the
  Evidence search adopts it for the reverse direction, so a task started from a scoping task (the
  child full run) inherits the option's specified design, the user context and evidence scope, the
  option's documents (re-screened) and the light findings (reused at finding grain) before acquire
  runs. [EB components](capabilities/evidence-search/components.md) gains § 0 inherit and a wiring
  row; [EB capability](capabilities/evidence-search/capability.md) dependencies and scope boundary
  amended; [OS components](capabilities/options-scoping/components.md) § 0 and ⟨full run⟩ amended;
  [execution-orchestration](system/execution-orchestration.md) names `inherit` as the first
  component both capabilities compose. Boards 7b, 7c, 7d updated.
* **Update**: Options scoping board refinement pass (concept ruling 49): an owner-approved ChatGPT
  review pack ported into the canonical boards in the ruled design language — Hide chat, the plan's
  constraints as a table, the baseline's target-population callout, five state boards (generating,
  direct edit with Undo, plan changed with refresh, refresh running, History), corrected counts, top
  lines leading with findings, Sources filters grouped with a "source quality" column. Restyle, chips,
  viewport clipping and the "Do nothing" rename not adopted. [Source README](sources/options-scoping/README.md).
* **Update**: Options scoping ruling 50 — **no report before assessment**: the report is written from
  the assessment and rewritten by a full run; before it the Result tab opens on the longlist. Board 3c
  withdrawn (24 boards). [capability.md](capabilities/options-scoping/capability.md) § Output
  structure and the report/export bullet, [components.md](capabilities/options-scoping/components.md)
  (synthesise, ⟨longlist depth⟩) amended; the on-demand longlist report recorded in
  [deferred.md](../deferred.md) § Product / output.

## 2026-09-07 (boards redrawn)
* **Update**: Options scoping wireframes redrawn to concept rulings 15–44 at the owner's direction
  ([source README](sources/options-scoping/README.md); readable boards under
  `sources/options-scoping/boards/`, bundled canvas page rebuilt). Every board now carries the
  task's tabs (Agent · Result · Sources · Share · History) with the plan in the Agent tab; the
  report is the Result, in a provisional form from the longlist stage (new board 3c) and an
  assessed form (board 6, the assessed table embedded); the longlist shows a variant option, the
  evidence-scope constraint's "no in-scope evidence" state and a source-quality profile per option;
  the grid's rows are primary lever types; the shortlist is a provisional allocation of reading
  effort; transferability works from three context sources with the weakest leg deciding; Sources
  states what was read at which depth; the sense-check is a rapid entry branch. Page 2's
  alternatives are marked superseded. The product-surface source note in
  [capability.md](capabilities/options-scoping/capability.md) updated to match. Rulings still win
  over boards where they differ.

## 2026-09-07 (later)
* **Update**: Options scoping, third review pass and its rulings (concept rulings 30–40): the
  component skeleton rebuilt on the Evidence search spine as is (classify and appraise at longlist
  depth), `longlist` replaces `mint`, the three depths become compositions; the Result is the
  **report** (provisional from the longlist, rewritten by assessment) with Baseline and Longlist as
  working views; source quality is not "how sure"; containing-geography context fills a local
  factor only by applicability; inherited findings reused at finding grain; identity rules for
  variants; the proposal is a provisional allocation of reading effort with one challenger in the
  standard sense-check; read-set discipline under the cap; editorial exceptions bounded; tabs are
  Agent · Result · Sources · Share · History. **System contracts amended:** components are shared
  across capabilities ([execution-orchestration](system/execution-orchestration.md) § vocabulary,
  withdrawing "a capability never runs another's component"); the depth "relative nudge" section of
  [plan-as-object](system/plan-as-object.md) carries an as-enacted note (rapid / standard / deep is
  user-chosen in the shipped product).
* **Update** (same day, closing the pass-3 ledger): OS concept rulings 41–42 — the child full
  evidence search's report carries the profile's judgement cells (a declared widening of the
  Evidence search's evidence-descriptive boundary, recorded in
  [evidence-search/capability.md](capabilities/evidence-search/capability.md) § Scope boundaries);
  six ordered spikes before any contract; eval refinements; an open-interfaces list in
  [options-scoping/components.md](capabilities/options-scoping/components.md). Seam notes added to
  [plan-as-object](system/plan-as-object.md) (evidence-scope constraint ≠ source policy),
  [data-model](system/data-model.md) (durable option identity) and
  [execution-orchestration](system/execution-orchestration.md) (reading budget / eligibility).
* **Update** (same day): OS concept ruling 43 — the six open interfaces ruled: mentions via a new
  `extract` abstract profile (screen unchanged); Unknown/Non-evidence as buckets, unresolved in
  scoping; the read set via `select` with a scoping strategy; claim kinds mapped onto pattern and
  reasoning claims plus one new **column-grounded block** declared in
  [provenance-grounding](system/provenance-grounding.md); baseline on Overton + OpenAlex only;
  uploads deferred. [evidence-search/components.md](capabilities/evidence-search/components.md) § 6
  notes the second `select` strategy.
* **Update** (same day): OS concept ruling 44 — the option entity declared in
  [data-model](system/data-model.md) (task-scoped stable id, versioned specified design, typed
  relations, state and membership records, child-task link; re-run matching open); the reading
  budget / eligibility and evidence-scope seams left open with their candidates recorded in the
  review pack.

## 2026-09-07
* **Update**: Options scoping review round. A two-pass adversarial product review of the concept
  and wireframes (blind proposal, then comparison) produced eleven findings; the owner ruled on
  all of them in one session (decision sheet in the gitignored review pack). Rulings 15–29 appended
  to the frozen concept as "Review-round rulings"; the three OS specs re-distilled
  ([capability](capabilities/options-scoping/capability.md) ·
  [components](capabilities/options-scoping/components.md) ·
  [trust](capabilities/options-scoping/trust.md)). Headlines: variants are linked options with
  their own assessment; claim depth follows reading depth; the do-nothing band is a starting
  point, not a comparison; transferability context is typed retrieved / stated / planned and the
  weakest leg decides; guesses never feed the shortlist proposal; coverage anchors on lever types;
  a scoping task may start from an Evidence search task; evidence-scope constraints never exclude
  options; sense-check is an entry branch and rapid/standard are depth settings; no build-order
  guidance in the spec. Two deferred seams added to `docs/deferred.md`.

## 2026-09-04
* **Creation**: Distilled the Options Scoping capability spec ([capability](capabilities/options-scoping/capability.md)
  · [components](capabilities/options-scoping/components.md) · [trust rules](capabilities/options-scoping/trust.md))
  from the owner-agreed concept and its wireframe-round rulings; froze the concept and the wireframe
  canvas as sources #8 and #9 under [sources/options-scoping/](sources/options-scoping/README.md);
  added the OS routing row to the [index](index.md). The concept moved here from the (uncontracted)
  task 035 folder; task contracts consume the spec.

## 2026-07-12
* **Update**: [system/data-model.md § The findings layer](system/data-model.md) — the
  `intervention_outcome_finding` base-field list gains `effect_basis` (`observed` |
  `modelled`, null if indeterminate — evidence basis is its own dimension from causal
  identification, deliberately not folded into `causality_by_design`) and
  `study_geography` (source-named, finding-grain — the same population/comparator
  treatment; null when unreported, never inferred). Existing v1 rows are not backfilled;
  they read as "not recorded under v1" via `field_coverage` key-absence, per the
  upgrades-never-invalidate rule. Task 020, ADR 0016.

* **Update**: [system/data-model.md § The findings layer](system/data-model.md) — the
  second reusable finding schema `implementation_context_finding` ships (mechanisms,
  barriers, implementation conditions — the "how/why/under what conditions"). Grain:
  one implementation-context claim about a named intervention, single source. The
  shared source-named reference vocabulary (`intervention` / `outcome` / `population` /
  `setting` / `study_geography` / `study_design`) is now defined once, with per-schema
  requiredness overrides (IOF `outcome` required, ICF `outcome` nullable); `setting`
  joins the stored vocabulary on BOTH schemas (ICF from day one, IOF via the bounded
  `iof_v3` rider — deliberate, pre-ground-truth, nothing else riding the bump). Storage
  stays parallel tables; the cross-kind UNION read view is a Slice C seam. ICF is its
  own fingerprint domain — its arrival never invalidates IOF memos. Task 021, ADR 0017.
* **Update**: [capabilities/evidence-search/components.md](capabilities/evidence-search/components.md)
  §7/§8/§9 — extract runs ICF as a second plan-visible profile alongside IOF through the
  same component (`profiles` directive, fail-closed compile, default both at deep,
  IOF-only expressible); `group`'s membership reach spans both finding kinds via the
  shared reference columns (facet shape untouched; `direction_spread` stays IOF-members-
  only; ICF-specific facets await Slice C's multi-facet redesign); synthesise's
  claim-type ladder gains ICF finding claims (id-cited, resolve-via-row) and the
  `icf_context_type_count` pattern claim (extraction-wide + group-scoped), with theme
  claims available over kind-spanning groups at their existing (softest, base-labelled)
  grade. The unified `query_findings` tool serves both schemas kind-segregated, never
  blended. Task 021, ADR 0017.
## 2026-07-11 (b)
* **Creation**: [system/prompting.md](system/prompting.md) — the prompting doctrine promoted
  out of the 018 task folder (owner decision, 2026-07-11; task-cycle step 8): the 12
  family-general rules + mini-tier adjustments from the 018 research sweep, the
  refine-replay loop method as validated by the 018 C-loop (two-stage baselines, cheap-probe
  classes, ≤3-rounds bound with the flag-not-drop-judge escape hatch, anti-overfit pins,
  compile-your-probes), agent-loop conventions (force-emit exhaustion, code-enforced read
  batching, adjacent envelopes, judge-envelope re-baselining, environment-context preamble),
  and the provider quarantine for the Bedrock swap. A hand-maintained prompt-surface registry
  was considered and declined (drifts; provenance already records surface versions).

## 2026-07-11
* **Update**: [EB capability § Output structure](capabilities/evidence-search/capability.md) and
  [provenance-grounding § Summaries](system/provenance-grounding.md) — the "what did it
  conclude" front door split into **two distinct grounded blocks, never merged** (owner
  refinement 2026-07-10; task 018, ADR 0015): the **key-findings block** (headline evidence
  claims at their appropriate grade, produced last / shown first, conditional-required —
  present iff headline claims are made) and a **conclusions block** at the report foot (what
  this evidence amounts to against the user's question, evidence-descriptive — no
  recommendations / decision-answer content; cited to sources, never to sibling blocks).
  provenance-grounding's compound "key-findings/conclusion block" phrase resolved into the
  two-block structure accordingly. Approved with the 018 contract (rev 4) per the
  spec-refinement flow.

## 2026-07-10
* **Update**: [execution-orchestration § Steering modes & the routing rule](system/execution-orchestration.md)
  — **Unattended mode** added (task 017, contract rev 2 decision 6b, user call; approved in
  principle at the 017 contract 🛑; ADR 0014): a fourth steering mode with zero mid-run
  interaction. Anticipated steer-points auto-resolve to **pre-declared visible default
  resolutions carried as plan content** (pre-declarable rules per steer-point class, never
  runtime-data-specific answers — rev 2.5 adversarial finding 6); every auto-resolution is
  flagged, collated into the end-of-run review and marked on the run record. The firm
  principle's wording assumed a live pause; its accountability purpose is preserved — the
  human substance decision moves from run-time to plan-time and is never *silent*, no longer
  always *live*. The routing-rule table gains the Unattended column; unanticipated substance
  residuals resolve proceed-and-flag as `unconfigured_default`, the loudest flag class.
  Approved with the 017 contract per the spec-refinement flow.
* **Update**: [EB components](capabilities/evidence-search/components.md) (opening chain
  statement + §9) and [EB capability](capabilities/evidence-search/capability.md) (component
  skeleton) — **the mandatory EB spine** (task 016, user call at the contract gate
  2026-07-09; ADR 0013): every EB run executes acquire(`search`) → screen → classify →
  appraise → ingest(fetch) → synthesise; characterise · select · extract · group · stage-2
  screen are orchestrator-discretionary per the depth gradation. Mandatory ingest is a
  mandatory **attempt** (reason-coded per document), never a substrate guarantee.
  Synthesise's substrate gate is untouched in character; its envelope-only refusal becomes
  unreachable-by-composition and `no_groundable_substrate` narrows to the genuinely empty
  corpus (no references AND screened-in count zero). Approved with the 016 contract
  (rev 2.2 + amendments, 2026-07-09) per the spec-refinement flow.
* **Update**: [EB components §4](capabilities/evidence-search/components.md) — as-enacted
  note on the flag-not-drop failure path (016 contract rev 2.5, user call): the
  unfetchable document's substrate IS its envelope abstract chunks (chunked + embedded at
  acquire), joining grounded retrieval as labelled substrate with `text_basis` carried on
  chunk records and citations; an all-fetch-failed corpus still synthesises, visibly
  abstract-labelled. Access-failure honesty recorded (401 → paywall; 403 → paywall only
  with corroboration, else `blocked_by_host`; bot-blocks never counted as paywalls). This
  enacts written §4 text the 008 fixture era never reached — no semantic change to the
  spec's intent.

## 2026-07-08
* **Update**: [EB components §2](capabilities/evidence-search/components.md) — screen refined
  to its v3.0 **two-stage realisation of the one component** (stage-parameterised via the
  plan directive; the thoroughness gradation selects): stage 1 metadata (fail-open,
  title-only exclusion needs consensus unanimity) always; stage 2 windowed full-text
  re-screen at depth, **demote-only**, text-availability-scoped, both stages persisting with
  stage provenance ("screened-in" = *effective* screened-in); `screen_basis` gains
  `full_text`; failures never block retry. Tiered content peek noted as largely superseded.
  Approved with the task 014 contract (rev 1.10, 2026-07-08) per the spec-refinement flow;
  ADR 0011.
* **Update**: [EB components §9](capabilities/evidence-search/components.md) — `search_chunks`
  described as its staged pipeline (task 013 contract rev 7.5): content-only hybrid
  relevance → arithmetic soft priors (selection prior + fail-closed directive boosts over
  columns/tags/appraisal tier, re-weight-never-exclude — the surface the future
  source/evidence policy compiles into, honouring plan-as-object's steerable-never-baked
  quality-prior ruling) → a cross-encoder reranker slot (pass-through until Bedrock Rerank
  lands, per the retrieval contract's inference-trust-boundary line) → caps.
* **Coherence pass** (task 013 gate, pre-adversarial-review; fresh-context audit, 18
  findings, no semantic changes): superseded same-gate wording reconciled to the amended
  state across [EB capability](capabilities/evidence-search/capability.md) and
  [EB components](capabilities/evidence-search/components.md) — "artefact needs at least
  characterise's content" → **≥ 1 groundable substrate** (all upstream references
  optional); the selected-set/corpus-wide chunk-grounding binary → **screened-in corpus
  with the selection as a soft prior**, only corpus-scale retrieval (beyond the in-memory
  ceiling, or unscreened content) retrieve-gated; the tool-wiring table row for synthesise
  → substrate-conditional (+ declares `search_chunks`); ADRs 0009/0010 subsequently
  **consolidated into cohesive, amendment-free records** (user direction: amendments are
  for shipped ADRs — within one unmerged branch, decisions and justifications belong in
  the main structure; ADR 0010 retitled "…and substrate-conditional grounding"; the
  round-by-round decision trail is retained in the task-013 contract's revision history);
  cross-references updated everywhere.
* **Update**: [EB components §9](capabilities/evidence-search/components.md) — the unified
  interpretive-shape claim type renamed **cluster claims → theme claims** (task 013 gate,
  user call: policy-maker-facing vocabulary, and the more spec-aligned word — the
  provenance ladder's soft grade is "thematic clustering", group's component is
  "facet-level theming"). Semantics unchanged (validated against the referenced
  clustering: characterise themes / facet groups; softest grade, base-labelled);
  `cluster` remains the internal tool-registry verb. Recorded in
  [ADR 0010](../adr/0010-intent-led-synthesis-sections.md) (2026-07-08 amendment),
  alongside the user's confirmation of the **consensus boundary** as the intended v3.0
  line (descriptive spread, never a weighted verdict, until the ⏸ consensus seam).

## 2026-07-07
* **Update**: [EB capability](capabilities/evidence-search/capability.md), [EB components
  §9](capabilities/evidence-search/components.md) — the **intent-led synthesis refinement**
  ([ADR 0010](../adr/0010-intent-led-synthesis-sections.md); task 013 contract gate, second
  round, after an independent deep-reasoner interrogation): deep synthesis is structured as
  **intent-led sections** (bounded section proposal over intent + group summaries; fail-closed
  scope-directive override; plan-compile sectioning = the seam), each section **mixing
  grounding modes** — finding claims (extract-verified anchors), **selected-set chunk claims**
  (windowed frozen text already in hand; no retrieval needed; select's discipline inherited),
  pattern claims (deterministically validated). **Groups demoted to input, not structure**
  (pure intent-led — no rendered backbone, user choice; uncovered groups counted). ADR 0009
  decision 5 amended: only **corpus-wide** chunk grounding stays retrieve-gated. Supersedes
  the group-per-block reading of §9's "per group produce a grounded block". **Third-round
  amendment (same day, ADR 0010 § Amendment):** "deep path" terminology retired (content
  modes by available references); the claim vocabulary completed to the spec's full set —
  **gap claims** (graded, coverage-base-carrying, fail-closed corpus-promotion via
  `search_coverage_record`) and **reasoning claims** (visibly-labelled Tier-4 authoring,
  judge strict-routing guard) join finding/chunk/pattern/theme; whole-document windowing
  replaced by **scoped retrieval** (anchor chunks + top-k embedding-relevant selected-set
  chunks — the 009 unit vectors' first reader; the `retrieve` seam's first increment).
  **Fourth-round amendment (same day, ADR 0010 § second Amendment):** modes renamed
  (**landscape synthesis** / **findings-grounded synthesis** — both intent-led; "findings" =
  the findings layer); theme claims generalised to **cluster claims** across both modes
  (validated against the referenced clustering; softest grade); depth clarified as the
  plan's thoroughness gradation, not a fork; the section writer realised as a **capped
  agent-loop over scoped read-only tools** (`search_chunks` hybrid + `query-findings`) —
  execution-orchestration's declared realisation, the repo's first agent loop, discharging
  the 012 `query-findings` deferral in full. **Fifth-round amendment (same day, ADR 0010
  § third Amendment):** the mode split itself dissolved into **one substrate-conditional
  flow** — claim types gated by what the referenced runs produced (chunk claims need only a
  **selection**, not extraction — non-intervention-shaped questions run
  characterise → select → synthesise; finding claims need an extraction; pattern/cluster/
  gap/reasoning per available substrate); the separate landscape prompt dies (**three**
  prompt surfaces); the loop gains **`lookup`** (the universal-core canonical-state read —
  appraisals, classifications, selection rationale, coverage records, clusterings); "writer
  agent" corrected to **the section loop** (component-internal realisation per the facade
  principle — no second agent; the capability sub-agent remains the capability-run seam).
  **Sixth/seventh-round amendment (same day, ADR 0010 § fourth Amendment):** **all
  references optional** — characterisation joins the substrate-conditional logic
  (requirement = ≥ 1 groundable substrate; a rapid acquire → screen → ingest → synthesise
  run is fully served); **select is a soft prior, never a reading boundary** — retrieval
  scope = the screened-in corpus always (the data-model's agents-are-never-penned-in
  scoping principle; select gates extraction cost), a referenced selection contributes a
  recorded look-here-first rank boost, every chunk citation records its origin
  (selected | unselected_screened); fail-closed in-memory retrieval ceiling
  (`RETRIEVAL_UNIT_CAP`), beyond which the index-backed `retrieve` slice is required;
  `lookup` explicitly covers the **tag layer** (per its universal-core definition);
  clarified on the record: verification is non-agentic — deterministic code legs + a
  separate single-call judge surface (maker ≠ checker at the surface level) — and the
  verify loop's rewrite step is explicit (judge rationales → one reword-down regeneration
  → one re-judge; `REPAIR_ROUND_CAP` = 1, plan-pinned).
* **Update**: [EB capability](capabilities/evidence-search/capability.md), [EB components
  §§5/6/9](capabilities/evidence-search/components.md),
  [execution-orchestration.md](system/execution-orchestration.md) — the **terminus
  refinement** (task 013 flow-back, user-decided at the contract gate): (1) the
  **capability-composes rule** — every capability sub-agent composes its own artefact at its
  run terminus; the orchestrator shapes sections at plan time and owns no runtime content
  machinery (supersedes the orchestrator-composes reading; characterise §5 note updated).
  (2) **Synthesise is EB's terminal component at every depth** — landscape rendering always
  (model prose, shape claims deterministically validated against the characterisation
  record), per-group grounded finding-blocks when the deep chain ran, artefact minting +
  block binding. (3) **Components are a registry the plan selects from**; data dependencies
  structural via explicit fail-closed run references; **breadth and depth independent** (a
  targeted question compiles to a narrow-and-deep run). (4) ⏸ **Direct chunk-grounded
  narrative synthesis sanctioned** for pre-findings targeted answers (full
  produce-grounded-block bar, visibly chunk-cited; lands with `retrieve`). ADR 0009.
* **Update**: [data-model.md](system/data-model.md) — findings-layer base-field list made
  explicit with three source-groundable sharpenings surfaced by the task-011 V2 extraction
  autopsy, all inside the spec's own "what the source reports" line: **stratum qualifiers**
  (timepoint/subgroup/setting as structured qualifiers; the outcome reference stays the base
  measure only — grain becomes *(intervention, outcome, effect, stratum)*), source-named
  nullable **comparator** (an effect direction is versus something), and the
  **estimate-level discriminator** (`study` | `pooled` | `claim`), with **τ²** joining the
  pooled stats (k, I²). Approved with the task 011 contract (rev 1.4 ⚑) per the
  spec-refinement flow.

## 2026-07-06
* **Update**: [EB components §6](capabilities/evidence-search/components.md) — select
  realisation refined: *procedure* → *procedure with an optional bounded generative rerank* of
  within-stratum ordering (stratification, breadth floor, budget arithmetic and must-includes
  stay code-side; schema-constrained per-doc scores + reasons; scores order, never exclude;
  per-doc fallback to the deterministic composite). `unclustered` named a first-class stratum
  (folding in what §5's counted-unclustered already implied). Approved with the task 010
  contract per the spec-refinement flow (rev 3).
* **Update**: [EB components §5](capabilities/evidence-search/components.md) — clarified
  content-vs-artefact: characterise produces the landscape *content* (run-scoped
  characterisation record + topic/theme tags); the single EB artefact is composed once at the
  run terminus by the orchestrator (artefact composition is a recorded seam). Approved with
  the task 009 contract per the spec-refinement flow (decision 7).
* **Update**: [EB components §5](capabilities/evidence-search/components.md) — thematic
  mechanism clarified to the bounded two-stage LLM grouping (discover over all
  titles+abstracts, batched assignment against the fixed theme list; code-enforced
  exhaustiveness; counted `unclustered`; run-local memberships; embedding-based clustering
  recorded as the very-large-corpus seam); and [EB components §4] — the embed seam opened in
  task 009 ahead of its first reader (approved exception), eager-and-uniform at
  embedding-unit grain over immutable canonical chunks. Approved with the task 009 contract
  (decisions 4, 2).
* **Update**: [data-model.md](system/data-model.md) — tag-layer clarification: "nothing hangs
  off a tag" governs the tag *label*; the assignment row carries assertion provenance
  (`asserted_by` + creating run); provider topical signals materialise as provenance-classed
  tags; provenance classes never mix. Approved with the task 009 contract (decision 10).

## 2026-07-05
* **Fidelity restoration** (full specs-vs-sources review; maintainer-approved): restored source
  content lost in the original distillation —
  [product.md](product.md): "counterfactuals" back in the human-substance authority list (briefing §1/§3);
  [data-model.md](system/data-model.md): inferred-`function` lane set restored to 🟡 illustrative /
  to-be-specced with the five example lanes (arch §3.3), removing the undocumented
  `project_context_directive` closed set;
  [provenance-grounding.md](system/provenance-grounding.md): content-scan pattern rung restored
  (ships soft and honestly labelled, never gated; arch §3.3) and the citation-scope rule added
  (citations point to sources, never to sibling blocks; arch §3.3/§4);
  [plan-as-object.md](system/plan-as-object.md): audit posture across the modes restored
  (per-commit approval in Frequent/Moderate; every commit recorded; Minimal's guarantee triple;
  arch §5), cross-referenced from
  [execution-orchestration.md](system/execution-orchestration.md).
* **Update**: [EB components §4](capabilities/evidence-search/components.md) — clarified v3.0
  Tier-0 ingestion scope: fetch → parse → segment; vectorisation deferred to the slice where
  vectors are first read, with the eager-and-uniform discipline restated (not weakened) for
  when the embed seam lands. Approved with the task 008 contract per the spec-refinement flow
  (decision 1).
* **Update**: [EB components §1](capabilities/evidence-search/components.md) — clarified v3.0
  acquire-time snapshotting: acquire snapshots the metadata envelope as text-in-hand
  (`text_basis="abstract_only"`); full-text fetch + Tier-0 ingestion remain post-screen.
  Approved with the task 007 contract per the spec-refinement flow.

## 2026-07-03
* **Update**: [EB components §4](capabilities/evidence-search/components.md) — clarified v3.0
  appraisal coverage: the light pass scores classified evidence types; Non-evidence and Unknown
  are skipped-and-counted (Unknown re-enters via the deferred full-text resolution seam).
  Approved with the task 006 contract per the spec-refinement flow.

## 2026-06-24
* **Update**: Adopted OKF — added frontmatter (type/title/description/tags) to the eight distilled
  specs and declared `okf_version: "0.1"` on the [index](index.md). Content and status markers
  unchanged; this is an *intent* bundle (status-tagged, not "verified").

## 2026-06-22
* **Creation**: Distilled the four system contracts and the Evidence Base capability spec from the
  canonical sources; ratified the conflict-resolution order in the [index](index.md).
