# Agentic evidence search per link: design and evaluation (draft)

> **Status:** draft, 2026-10-27 · lead. **Owner, 2026-10-27:** "the plan is very good"; add the web
> for directed searches (e.g. Evaluation Task Force evaluations), add System's findings graph as a
> tool, and at most **2 rounds** for now. Offline evaluation under way. For the owner's review before any build. Background
> research folded in (§ What others do; full notes in
> [agentic-search-research.md](agentic-search-research.md)). Not yet a contract decision.

## The problem, from one real link

Link: *"Lower excess dietary energy leads to a lower proportion of children living with obesity"*
(task `07e278fe`, link `2018a1e8`). Graded **weak**: its supports were two commentaries and a
policy overview (scores 2, 1, 1). A rebuild of its search (scratchpad `rank-test/`) showed why:

1. **The searches asked about the topic, not for the study that would test the step.** They ran
   five topic queries, each with systematic-review and trial filters. They never asked for
   trials that *cut intake and measured weight*, or for *validated energy-balance models*. The
   decisive studies (a 2004 school trial cutting fizzy drinks; a 2006 trial cutting sugary
   drinks; a 2013 validated growth model) ranked 29th, 281st, or not at all.
2. **A cap of 20 records**, filled by a mix of relevant, most-cited and recent papers, leaves
   about 7 places for the most relevant.
3. **Screening against the whole theory**, not the link: 13 of 20 were dropped as "not advertising
   restrictions", including reviews.

With the trials found, the judge says *supports* and the grade becomes medium (one trial) or
strong (both). The evidence exists; one fixed search round did not reach it.

## The idea

For each link, reason first about **what kind of evidence would test it, and where that evidence
lives**; run several small targeted searches; follow citations from the first good hit; judge; and
search again only where the result is still thin, with a stated reason to stop. The research
supports this shape: the measured gains come from asking for the right study type, chasing
citations from good hits and building the next query from what was found, not from running many
agents (§ What others do).

## Design

One loop per link, inside the existing check walk. Every piece except the planner and a small
filter table reuses what exists: the search backends, citation chasing, screen, classify,
appraise, the judge and the grade.

1. **Plan (one small call per link, new prompt `toc_search_plan_v1`).** Reads the link (sentence,
   if/then/because, conditions) and the plan's place and population. Returns:
   - the **link type**: a mechanism or biological step; a behaviour change; delivery or
     implementation; how firms or markets respond; a population outcome;
   - for each question, **1 to 3 target evidence types**, strongest first. *Worked elsewhere*:
     trials that change the source and measure the target, reviews of those, natural or
     quasi-experiments; for a mechanism, also dose-response studies and validated models.
     *Holds here*: evidence that the link's conditions are present in the place (surveys,
     monitoring, UK evaluations, regulator and policy documents). Many links are tested by
     descriptive facts, not impact studies (White 2009), and the planner says so when it applies;
   - **one small query per target type**: the link's cause and effect terms, combined in code with
     that type's terms from a fixed **study-design filter table** (adapted from the Cochrane,
     McMaster and ISSG filters), sent to the source that fits the type:
     - **OpenAlex** for trials, reviews and models;
     - **System** (system.com findings graph) for mechanisms and health outcomes: cause and
       effect concepts, the relationship between them, and the studies behind it (DOIs, then
       OpenAlex). System says about 20% of its extracted findings are inaccurate; it is used only
       to find studies, which the judge then reads;
     - **Overton** for regulation, implementation and local context;
     - the **web** for directed searches of official evaluations and monitoring (the UK Evaluation
       Task Force's evaluations, gov.uk research, Ofcom, the Advertising Standards Authority,
       What Works Centres), with site: restrictions. Web pages never raise a grade above weak.
     About 10 results per query; a query that returns nothing is reported.
2. **Search** each planned query; pool and de-duplicate per link.
3. **Screen against the link's own question**, not the whole theory. 🟡 Later step: score each hit
   0 to 10 with a one-line summary against the link, as PaperQA2 does, instead of a plain yes/no.
4. **Judge** the best documents (rerank to *K*, as now).
5. **Chase from the first good hit.** From any document the judge marks *supports* or *challenges*
   that is a trial, a review or a robust model, follow its references and citing works in OpenAlex
   (already in the search loop), and take terms from its title and abstract for the next query.
6. **Decide, in code, whether to go on**, per question:
   - **stop: decisive** when a study of a target type (scored 4 or 5, or a robust model) is judged
     to support or challenge the link;
   - **stop: saturated** when a round adds no new relevant records;
   - **stop: budget** at 2 rounds (owner) or the per-link cap;
   - otherwise the planner gets what was found ("only commentaries support; no trial yet"; "no
     England evidence for holds here") and plans the second and last round for the missing evidence type.
   The stop reason is recorded per link and shown in the Sources tab.
7. **Absence is unknown, not evidence.** Nothing found in Overton reads as "not found", never as
   "nothing exists": its coverage is uneven by country, language and topic.

**Cost control.** Only links not stopped as decisive after round 1 go on, to one more round at most. Per-link caps on
queries, records and judge calls. The planner is one small call per round; the judge stays the
main cost. Expected: about one extra call per link plus a second round for weak links.

## How we validate it

Offline and small, on real links, before any build. The rank-test harness already reproduces a
link's search exactly and runs the real judge, so the arms below run without a full walk.

**Known-key-studies set (lead-built; eval criteria are lead-only).** 10 links, chosen to cover the
link types: the energy-to-obesity link above; ads shown to ads seen; ads to children's choices;
requests to household purchases; firms' reformulation; brands moving spend (a failure link); two
*holds here*-heavy links; one link where the evidence should **challenge** the step; one where
little evidence should exist. For each: 2 to 4 **decisive studies** found by a careful manual
search (with how they were found), and an **expected grade band** per question. Where a
systematic review on the step exists, its included studies seed the set. The set is built before
any arm runs, so no arm's retrieval shapes it.

**Arms.**

| Arm | What it is |
|---|---|
| A | As run today (cap 20, screen against the theory) |
| B | Cheap fixes: cap 40, screen against the link |
| C | Agentic: plan by evidence type, filter table, OpenAlex, System, Overton and directed web, chase from good hits, at most 2 rounds |

**Measures, per link and in total.**
- **Recall of the decisive studies at a fixed cut-off**: how many reach the judge's top *K* (8),
  and how many are in the first 20 records. Recall depends on the cut-off, so both are reported.
- **Grade against the expected band**, both questions. The grade comes from the rule over the
  lead's set, not from the judge marking its own retrieval.
- **Strong-design supports** (scored 4 or 5).
- **False supports**: "supports" on a document that does not test the step, spot-checked by the
  lead (LLM screening and judging run inclusive).
- **Stop reasons** (arm C) and **cost**: calls, tokens, money, wall time.

**Decision rule.** Adopt C if it beats B on decisive-study recall or grade band on at least 6 of 10
links, at no more than 3 times B's cost. If B gets most of the gain, ship B and use C only for
links B leaves weak. Budget for the whole eval: about $5.

**First test: the energy-to-obesity link.** Success means the planner names intake-reduction
trials and validated growth models as the target types without being told, round 1 or the citation
chase from the first good hit reaches the 2004 and 2006 trials, *worked elsewhere* reaches medium or
strong, and the stop reason is "decisive".

## What others do

Full notes, sources and numbers: [agentic-search-research.md](agentic-search-research.md).

- **PaperQA2** (FutureHouse, 2024): an LLM scoring each retrieved passage 0 to 10 with a summary
  against the question gave the largest accuracy gain; citation chasing from hits scored 8 or more
  raised recall of the key papers. About 1.3 searches per question: the number of searches was
  not what made it work.
- **Seed studies:** giving an LLM one or two known relevant studies roughly doubled the recall of
  the queries it wrote (0.29 to 0.64; Wang et al., 2025). **Terms from known studies** gave 97%
  sensitivity against 75% for concept-only queries (IQWiG method). This is why step 5 mines terms
  from the first good hit.
- **Study-design filters:** the Cochrane randomised-trial filter has 0.96 sensitivity and 0.14
  precision (Glanville 2020); the McMaster broad filters exceed 90% sensitivity. Tested on medical
  databases; untested on OpenAlex keyword search, so the eval checks it.
- **Vendor recall claims are unreliable:** Elicit claims 95% recall across Cochrane reviews; an
  independent study found 39.5% against 94.5% for the reviews' own searches (Lau and Golder,
  2025).
- **Stopping:** systematic-review screening uses recall targets and "knee" rules (stop when new
  finds level off); newer tools estimate saturation from how often the same papers recur. Google's
  "sufficient context" work asks whether the evidence is enough to answer, not whether it is
  relevant. Step 6 combines "decisive" and "saturated".
- **Evaluation:** gold sets from systematic reviews' included studies (CLEF TAR, CSMeD); recall at
  a fixed cut-off; do not let an LLM judge grade its own retrieval (Clarke and Dietz, 2024).
- **Left for later:** many parallel agents and reinforcement-learned query writers: real gains,
  but 4 to 15 times the tokens, or training data we do not have.

## Open questions for the owner

1. The grade rule: should one challenging observational systematic review (score 5) outweigh two
   supporting randomised trials (score 4)? Today it does.
2. Whether Arm B's cheap fixes ship now regardless of the agentic outcome.
3. Where web search sits: in the planner's source menu from increment 3, or earlier.
4. The 0-to-10 relevance score with a summary in the screen (PaperQA2's biggest gain): try it in
   the eval as a fourth arm, or after C is settled.
