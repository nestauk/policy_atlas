---
type: Capability spec
title: Theory of change (ToC)
description: The declarative theory-of-change spec. The third v3.0 capability; it drafts a Magenta Book causal chain on a canvas, grades the evidence for each causal link, both where it was tried and for the user's own setting, with the Evidence search machinery and the web, consolidates the pathways, and lets the user stress-test the result.
tags: [capability, theory-of-change, compile-target, draft]
timestamp: 2026-10-23
---

# Capability spec — Theory of change (ToC)

**Status: draft (task 054).** The owner ruled on two rounds of questions on 2026-10-23. "R1" to
"R16" are the first round; "S1" to "S11" are the second (§ Rulings). Every 🟡 is still a
proposal; every ❓ is still open.

**Origin.**

- [theory_of_change_approach.md](../../../tasks/054-toc-integration/theory_of_change_approach.md):
  the Magenta Book, Nesta/TSIP guidance and the ToC user research ("approach § N"). Product intent.
- [research-notes.md](../../../tasks/054-toc-integration/research-notes.md): what the Magenta Book
  2026, Mayne and Vogel say; eval datasets; import and export feasibility ("research § N").
- The ToC prototype in the `stakeholder_atlas` repo ("prototype"). A reference for behaviour and
  screens, **not** for code or schema.
- The capabilities in this repo. ToC is an **instance** of the capability framework, like
  [Options scoping](../options-scoping/capability.md). It reuses the Evidence search components
  and the runtime, and adds a component only when nothing in the repo does the job.
  [components.md](components.md) gives the reason for each new one.

System contracts: [../../system/data-model.md](../../system/data-model.md) ·
[../../system/provenance-grounding.md](../../system/provenance-grounding.md) ·
[../../system/execution-orchestration.md](../../system/execution-orchestration.md) ·
[../../system/plan-as-object.md](../../system/plan-as-object.md) ·
[../../system/prompting.md](../../system/prompting.md).

Status legend: ✅ settled · 🟡 leaning · ❓ open · ⏸ deferred.

## Artefact & scope

- ✅ **The Magenta Book is followed fully** (owner, R1, S1). Its Figure 2.2 (p.46, based on Mayne
  2017) sets the layers, the assumptions under the chain, the context band and the
  supporting-activities band (research § 1). ✅ Its assumptions are held as each link's
  **conditions**, not as separate objects (owner, 2026-10-26: "the evidence for each connection is
  in fact the Assumption").
- 🟡 **Outcome.** The user describes a change they want, an intervention, or both, or brings a
  theory of change they already have. They get a **theory-of-change canvas**: success and failure
  pathways through the four Magenta Book layers, the conditions on each link, the context, and a
  reason for each pathway kept or set aside. Each link shows how strong its evidence is that it
  worked elsewhere and that it will hold here, and the evidence for and against it. The canvas is a first version to work from
  (approach § 1, § 7).
- 🟡 **The theory is the reasoning and the evidence; the canvas shows it.** The stored object is
  the graph with its links, their conditions and evidence. The canvas, Detailed information and every export are
  views of it (Magenta Book p.46).
- 🟡 **Users and jobs** (approach § 2): design and stress-test an intervention; communicate how it
  creates impact; plan an evaluation (weak links become evaluation questions); align a team.
- ✅ **Three entry points, one pipeline** (approach § 4.1; owner, R9, R10):
  - **Outcome-first.** The draft works backwards from the impact, in one pass. The user then
    changes it on the canvas or through the Task Agent.
  - **Intervention-first.** The draft works forwards, as a test of the logic.
  - **Existing theory.** The user pastes text, or uploads an **image or PDF** of their diagram.
    Policy Atlas reads it into the graph, keeps their words, labels what it adds, and checks it.
- ✅ **One light connection to other tasks** (owner, S10): "Design a theory of change" on the
  Options scoping option page. § Connections to other tasks.

**Scope boundaries.**

- ✅ **Lead with simplicity** (approach § 5). Linear, Magenta Book style theories first. ⏸ Feedback
  loops, mediators, system maps and realist context–mechanism–outcome statements.
- ✅ **No real-time co-editing** (approach § 7). Export comes before collaboration.
- ✅ **No overall score for the theory** (owner, S2: "not sure if it makes sense … at the moment").
  The header shows two short paragraphs instead (owner, 2026-10-26).
- 🟡 **Cross-capability triage stays out**: the user chooses "Theory of change" on the new-task page.
- ✅ **Out of this task:** full-text reading of evidence (R6); stress-test answers written back to
  the graph (R11); a Miro API integration (R13; the draw.io file covers Miro, research § 3);
  real-time collaboration; links to Evidence search tasks and any connection beyond the option
  button (S10).

## Vocabulary

✅ The Magenta Book's four layers and words (owner, S1: "fully follow Magenta"):

| Layer | Magenta Book meaning (Figure 2.2) | In a ToC task |
|---|---|---|
| **Inputs** | "The resources committed and activities undertaken" | What the intervention does for or with its beneficiaries, with its **dosage** (how much each beneficiary gets) and the resources it needs. |
| **Outputs** | "What is delivered or produced" | What is delivered and can be counted directly. |
| **Outcomes** | "The early or medium term results" | Changes in the beneficiaries: skills, behaviour, wellbeing. |
| **Impact** | "The long term results" | The furthest change the user can credibly measure and claim. |

| Word | Meaning |
|---|---|
| **Box** | One element in a layer. |
| **Link** | A causal step from one box to the next. It carries the **mechanism**: why the step happens. |
| **Conditions** | What must hold for a link to work in the user's setting: the link's *unless* text, one or more short statements. This is where the Magenta Book's assumptions live (Mayne 2015: "only when we add the assumptions to the causal links … do we get a theory of change"). There is no separate assumption object (owner, 2026-10-26). |
| **Worked elsewhere · Holds here** | The two evidence questions on every link: did it work where it was tried, and will it work here (Cartwright and Hardie 2012, *Evidence-Based Policy*). The second is about transferability: whether the link's conditions hold for this population, in this place, now. |
| **Critical connection** | The link whose failure here would break the most of the theory. Shown as "Critical connection · test this first". |
| **Context** | External factors and other policies (Magenta Book band "Contextual factors and external influencers"). |
| **Supporting activities** | Work the chain needs but beneficiaries do not receive: training, referrals, marketing, setup (Magenta Book band "Supporting activities…"). |
| **Pathway** | One route through the layers, from an input to an impact. |
| **Success pathway** | A route by which the intervention brings the intended change. |
| **Failure pathway** | A route by which a step fails or the intervention causes harm: the Magenta Book's "negative programme theory" (p.47). Ends in a failure outcome. |
| **Set-aside pathway** | A pathway considered and not kept, with its reason. The user can restore it. |
| **Evidence grade** | *Strong*, *medium*, *weak* or *no evidence found*. Each link has two: *worked elsewhere* and *holds here* (§ Trust rules). Boxes are not graded. |
| **Case study** | A named programme or place where a box's result was seen, or an input was delivered, from a document, with a quote. |
| **Result criteria** | Mayne's checks on each box: well-defined, measurable (with a suggested indicator), plausible timing. |

- ✅ "Mechanism" is never a layer label (approach § 3). It is the "because" text on a link.
- 🟡 Each link keeps the prototype's if / for / then / because / unless fields: the two ends, the
  population, the mechanism and the main way the link fails.

## Depths and modes

- ✅ **Abstract-level check only in this task** (R6). Each evidence item is labelled *abstract
  only* or *web page*.
- ⏸ **Check a link in depth**: full text for one link's best documents and a light extraction,
  like Options scoping's ⟨assess⟩.
- ⏸ **Full evidence search on a link**: a child Evidence search task, like ⟨full run⟩.
- ✅ **No pause between the draft and the evidence check** (R5). § Editing during the check.

## Pipeline

```
plan ══approve══▶ draft or import ─▶ search and screen (background) ─▶ discover ─▶ merge ─▶ judge ─▶ choose ─▶ summarise
                         │                  ▲                                          │
                         └─ user edits at any time: links flagged *check pending*; the user keeps the evidence or checks again
                                              stress test · discuss: chats, any time after the draft
```

1. 🟡 **Plan.** The Task Agent conversation fills the plan (§ Plan slots); the user approves it.
2. 🟡 **Draft** (R1 step 1). One model call writes **candidate pathways from reasoning**: up to 6
   success and 3 failure pathways through the four layers, with links, mechanisms, each link's conditions,
   context, supporting activities, the result criteria for each box (with a suggested indicator
   for each output, outcome and impact) and the critical connection. In the existing-theory
   entry point, an **import** call reads the user's text, image or PDF instead and only adds what
   is missing, labelled. The canvas shows the result at once.
3. 🟡 **Evidence check, in the background.** One search per **link** (owner,
   2026-10-26: the causal chain is what needs checking; boxes get no search of their own; a link's
   conditions are part of it), asking both whether it worked where it was tried and whether its
   conditions hold in the plan's place, across
   OpenAlex, Overton and the web; then the Evidence search spine on the pooled documents
   ([components.md](components.md)). Judging waits until discover and merge have run (owner,
   2026-10-26: "first elucidate missing pathways, consolidate them and then judge them all
   together"). Progress shows in the Task
   Agent thread through the existing run events.
4. 🟡 **Discover** (R1 step 2). One pass over the screened documents finds mechanisms, outcomes and
   failure modes the draft does not have. Each becomes a candidate pathway, labelled *found in the
   evidence*, with the documents and quotes that suggested it. Its new links get no search of their
   own; they are judged with the rest against the documents already found.
5. 🟡 **Consolidate** (R1 step 3; owner, S5) is two steps, merge and choose, with the judge between
   them:
   - **Merge, by *distinct* and *relevant*,** before judging. Pathways that share a mechanism,
     drafted or discovered, merge into one. Pathways that do not reach the intended change for the
     plan's population and place are set aside. This needs no evidence, so nothing is judged twice.
   - **Judge** every remaining link in one pass (§ Trust rules), then grade.
   - **Choose, by *promising* and *evidence*,** after grading. If more than 6 success or 3 failure
     pathways remain, the ones kept are those most plausible within what the intervention can
     influence and with the stronger evidence grades on their links, read as counts, never a
     score. Conditions that supports recorded and a link does not yet name are added to it.

   Every kept and set-aside pathway gets a one-line reason naming the criterion. Code checks the
   limits and flags every change to something the user made or edited (§ Editing during the
   check). Mayne's limit applies to
   each pathway view: about 13 boxes before a theory "may be a mess".
6. 🟡 **Summarise.** A short summary of the theory and its evidence, and **evaluation questions**
   made from the links whose *holds here* evidence is weak or missing (approach § 4.2 step 6). ✅ It
   also writes two **evidence sentences** per link, one for *worked elsewhere* and one for *holds
   here* (owner, 2026-10-26). The sentence follows
   the grade and names the key sources with their year, for example "Exposure fell by about half
   under Chile's rules (2020) and almost to none on London transport (2022)". It is shown in the
   detail panel and in Detailed information, with a control that opens the full document list.
   ✅ Each **box** gets a short **description**: two sentences of plain prose, the first saying what
   the step is and how you would know it happened, the second where it has been seen, citing its
   case studies (owner, 2026-10-26: "more into a narrative - still short"). Each link's sentence
   and its evidence sentence read as one paragraph.

### Editing during the check

✅ The user can edit from the moment the draft appears (R5). 🟡 Rules:

- ✅ **An edit flags; the user decides** (owner, 2026-10-26: "Policy Atlas should simply flag
  that there has been a user edit and that a check is pending or whether the user has accepted
  the evidence"). Each evidence row stores a hash of the wording it judged. When the user changes
  a link's wording, or a box at either end of it, the link keeps its evidence and grades,
  labelled *for the previous wording*, and is marked *Edited · check pending*. Nothing reruns on
  its own. The user chooses, per link or for all pending links:
  - **Keep the evidence**: the evidence counts for the new wording, marked *kept by you after an
    edit* in the panel and in History.
  - **Check again**, which changes as little as possible (owner: "if it's just a wording change,
    then right outcome would be no change"):
    1. One small call compares the old and new wording (claim, population, conditions). If the
       claim is the same, nothing is judged again; the link reads *Checked: no change*.
    2. If the claim changed, only the documents already judged for that link are judged again, reranked
       against the new wording, with no new search. The Task Agent says what changed: documents
       that no longer apply and stances that flipped. Grades are recomputed.
    3. If fewer than two documents still speak to the link, the user is offered **Search for
       more**, a new item search.
- A link edited before the check reaches it is simply judged on its new wording. There is no
  automatic follow-up pass. When the check ends with links pending, the Task Agent says how many,
  with *Check all* and *Keep all*.
- A deleted box or link loses its evidence.
- Discover, merge and choose run on the graph as it is when each starts. ✅ They **may** merge,
  reword or set aside items the user made or edited, but every such change is **flagged** (owner,
  2026-10-23: "still allow Policy Atlas to consolidate or edit the ToCs that users touched, just
  it should be flagged"). 🟡 A flagged item shows a *changed by Policy Atlas* mark with the reason;
  its panel shows the user's version beside the new one, with **Accept** (the change stands and
  the mark clears) and **Keep mine** (the user's version returns, the mark clears, and the link
  is marked *check pending*). Undo in the Task Agent thread also clears it. A set-aside pathway
  that held user work is marked *includes your edits* in "Considered and set aside".
- When the check finishes, the user gets the existing run notification. The Task Agent thread
  then lists **each change** discover, merge and choose made (pathways added from the evidence, merged, set aside,
  and every change to the user's work), each with its own **Undo**, plus **Undo all** (owner,
  2026-10-26). The blue dots on the canvas mark the same changes. Every change is an event in
  History. The Task Agent then **always suggests a stress test** (owner, 2026-10-26).
- A change the user asks for through the Task Agent is an edit like any other.

## Plan slots

🟡 Required slots are marked *.

| Slot | Notes |
|---|---|
| Entry point * | outcome-first · intervention-first · existing theory. Inferred from the first message where possible. |
| Intended change * | The impact, in measurable words. |
| Target population * | Who the change is for (approach § 8). |
| Intervention | Required for intervention-first. Includes the dosage. |
| Existing theory | Required for the existing-theory entry point: pasted text, an image (PNG, JPG) or a PDF. |
| Where | The place the theory is for. It steers the search and is shown; it never excludes. |
| Time horizon | When the impact is expected. |
| Context | What the user knows about the setting. |
| Evidence restriction | Optional country group, years and language, applied at retrieval, as in Options scoping. |
| Source option | Set when the task starts from an option (§ Connections to other tasks). |

## Output structure

✅ The canvas is the default view of the Result tab (approach § 7). ✅ The layout follows the owner's
wireframe review of 2026-10-26 (`docs/tasks/054-toc-integration/wireframes.html`, version 20).
Visual rules: one font, the app's own, in the app's sizes; colour means evidence grade and nothing
else; blue means actions and things to review; no counts, badges or captions on the canvas; detail
appears on hover, on click, and in Detailed information.

- **Header.** The title "Intervention → intended change". Then two short paragraphs: *About this
  theory* (population, place, time horizon, context, where it came from) and *What the evidence
  says* (the strongest and weakest steps, and a link to the critical connection). While the check
  runs, one paragraph says it is running and that editing is allowed. After the check, the header
  keeps both paragraphs; what Policy Atlas changed is listed in the Task Agent thread and marked
  by blue dots, not in the header (owner, 2026-10-26).
- **Toolbar.** A pathway menu (all pathways, each pathway on its own); *How to read this*, which
  opens a short guide above the canvas (layers, grade colours and line styles, the two questions,
  the critical connection, supporting activities); Edit; Your original; Stress test; Download.
- **Canvas** (Magenta Book layers):
  - Four **layer columns**: Inputs · Outputs · Outcomes · Impact. **Failure pathways** sit below a
    line labelled *If it goes wrong*.
  - **Boxes are neutral** (owner, 2026-10-26): rounded, with a grey outline. They carry no grade.
  - **Connections** are smooth curves coloured by the **lower** of their two grades, so the
    colour answers "how sure can we be this step works here"; weak and *no evidence found* are
    dashed. Hover shows both grades.
  - The **critical connection** carries one small navy dot at its middle.
  - An item still being checked is grey and pulses. An edited box, a link marked *Edited · check
    pending*, and an item changed by Policy Atlas each carry a blue dot; hover says which.
  - Context and supporting activities are in the header paragraph and the reading guide, not on
    the canvas.
- **Detail panel** (on click):
  - A **box**: its layer and text, its result criteria (definition, indicator, timing), its
    **case studies** (programme, place, source type, quote, typed by source as in Options scoping;
    for an input, delivery notes such as time, cost and enforcement), and the **indicators** the
    documents used.
  - A **connection**: its sentence; if / for / then / because; its **conditions**; then *Worked
    elsewhere* with its grade, sentence and documents in two groups, *supports* and *challenges*;
    then *Holds here* in the same form. Each document shows title, year, source type, appraisal
    tier, quote and link.
  - **A pending link** (W17) opens with a block above everything else: *Edited · check pending*,
    the old and new wording side by side, **Check again** and **Keep the evidence**, and the two
    grades marked *for the previous wording*. After Keep, the block becomes one line, *Evidence
    kept by you after an edit*, with **Check again**. After a no-change check: *Checked: no
    change*.
  - Folded away: how the grade was given, and where the item came from.
- **Detailed information**, under the canvas, in the report's expand and collapse sections, with
  *Download as PDF* on the right. One section per pathway (pathway 1 open), then *Considered and set
  aside* (each with its reason and **Restore**, R1) and *Questions for an evaluation*. In a pathway:
  each box (layer label, title, a two-sentence description citing its case studies), then each
  connection in **three paragraphs**: its sentence naming both boxes and the mechanism; *worked
  elsewhere*, with its grade and evidence sentence; *holds here*, with its grade and evidence
  sentence, naming the conditions. The critical one is labelled *Critical connection · test this
  first*. When the same documents answer both questions, the evidence is not repeated
  (§ Trust rules). A small **+** after a sentence opens its documents. This section is the PDF
  report. A pending link shows *Edited · check pending* above its paragraphs, with
  **Check again** and **Keep the evidence**, and its grades read *for the previous wording*.
- **Task Agent thread.** When a check ends with links pending, and whenever the user returns to a
  task with pending links, the thread says how many, with **Check all** and **Keep all**. After a
  Check again it reports what changed, or "no change".
- **Your original.** For an imported theory, the uploaded image or PDF, inside the plan under
  *Starting point*, and from the toolbar.
- **Sources tab.** The existing tab: every document read, what it was used for, by source type and
  country, with what was searched and what was not.
- **History tab.** The existing event log: plan, draft, imports, every edit, every check.

## Trust rules

ToC follows the Options scoping principle: **generation is free, interpretation is labelled,
assessment is grounded** ([../options-scoping/trust.md](../options-scoping/trust.md)).

- 🟡 **Origin label** on every box, link and pathway: *drafted by Policy Atlas* · *found
  in the evidence* · *from your theory* · *added by you* · *from your options scoping*. A drafted
  mechanism is a reasoning claim (tier 4, "reasoning, not evidence") until evidence is found.
- ✅ **Evidence grades: strong, medium, weak** (owner, S4; Mayne 2017: "classified as strong,
  medium, or weak"). The Magenta Book defines no scale (research § 1). User research asked to tell
  "no evidence" from "evidence against" (approach § 6), so a grade comes with flags, and *no
  evidence found* is its own label, not a low grade. 🟡 The v1 rule, computed by code and shown in
  the key (owner, S6: "try initially and then test against evals"):

  | Grade | Rule |
  |---|---|
  | Strong | Two or more supporting documents at appraisal score 4 or 5 (systematic review, meta-analysis, randomised trial, quasi-experiment), and no challenging document at 4 or 5. |
  | Medium | Not strong; at least one supporting document at score 3 or above; no challenging document scored higher than the best supporting one. |
  | Weak | Some documents speak to the item, but neither rule above is met: only low-scored support, only challenge, or challenge that outweighs the support. |
  | No evidence found | The search ran, and no screened document speaks to the item. |

  | Flag | When |
  |---|---|
  | Evidence against (N) | Any document challenges the item. "Weak · evidence against" and "No evidence found" never look alike. |

  | Status | When |
  |---|---|
  | Checking | The check is running on this wording. |
  | Edited · check pending | The wording changed after its evidence was judged; the evidence shown is for the previous wording. |
  | Evidence kept by you | The user kept the evidence after an edit, without a new check. |
  | Checked: no change | Check again found the claim unchanged, so the evidence stands. |

  ✅ There is no *supports under conditions* stance and no *holds under conditions* flag (owner,
  2026-10-26: "under conditions is implied, and should be covered by Assumptions"). A supporting
  document that holds only for some groups, places or settings records that condition, which shows
  in its evidence line. 🟡 A condition the link does not yet name goes to choose, which adds it
  to the link's conditions, labelled *found in the evidence*.

  ✅ **Robust modelling can reach medium** (owner, 2026-10-26). The shared appraisal scores every
  "Modelling & Simulation" study 2 by type, so a model alone could never pass *weak*. For a
  modelling study only, the judge also says whether the abstract shows it is **robust**: built on
  or calibrated against real outcome data (trials, reviews or cohorts), with sensitivity or
  uncertainty analysis, or validated against observed results. The grade rule then treats a robust
  model as a score-3 document: it can support *medium*, never *strong*. The shared appraisal is
  unchanged. Abstracts often omit how a model was built, so most models will stay at 2 until the
  full-text depth (⏸) exists.

  Web pages show and count toward
  the flags and toward *weak*, but never toward *medium* or *strong* (Options scoping trust rule:
  "a web case study never raises an evidence-strength rating"). The rule is a banding, which
  Options scoping does not allow in v1 without its own eval; ToC adopts it deliberately, records it
  in the task ADR, and tunes it with evals E2, E2b and E7 (owner, S6).
- 🟡 **Every evidence item carries a quote**, checked by the existing quote verifier against the
  abstract or the frozen web page text. An item without a verified quote is dropped.
- ✅ **An evidence sentence or box description cites only its own item's evidence** (owner,
  2026-10-26); for a box, its case studies. Every source
  it cites must be one of that item's judged documents with a verified quote; code checks each
  citation and drops a sentence that fails. It never states a grade of its own: the grade comes
  from the grade rule and is shown before the sentence. An item with no evidence gets a fixed
  sentence, not a generated one.
- ✅ **Only links are graded; boxes describe** (owner, 2026-10-26, replacing S3's
  box searches). Theory-based evaluation tests the links of the causal chain and the assumptions
  under them, which here are each link's conditions (White 2009; Mayne 2015, 2017); a box is a result with *result criteria* (Mayne 2015)
  or *success criteria and indicators* (Funnell and Rogers 2011), and "did the result happen" is a
  question for monitoring after delivery. A box search also repeated the evidence of the links
  into it. So boxes get no search and no grade. Each box shows its result criteria and its **case
  studies** and **indicators**, which the judge pulls out of the documents it reads for the box's
  links: for an output, outcome or impact, where that result was seen and how it was measured; for
  an input (owner, 2026-10-26: "Inputs also can get evidence/case study notes"), where it was put in
  place and what it took. Case studies are typed by source and cite only verified quotes.
- ✅ **Web search is in** (R7), as **OpenAI's own web search tool** (owner, S7). 🟡 On the OpenAI
  route it works as is. On the Bedrock route, global routing does **not** make it available
  (checked 2026-10-23 against the AWS model card for GPT-5.6 Sol and OpenAI's Bedrock guide):
  - The `bedrock-runtime` endpoint, which our Bedrock route and its global profiles use, lists
    "server-side tool use" as **not supported**.
  - Only the `bedrock-mantle` endpoint offers hosted web search, and only in-region in
    **us-east-1 and us-east-2**, with no geographic or global profile.

  ✅ So on the Bedrock route, **only the web search calls go to Bedrock's US endpoint**
  (`bedrock-mantle` in us-east-1) (owner, 2026-10-23: "this would be ok for now"). Every other
  call stays on the London endpoint. Web results are untrusted data either
  way: each cited page is fetched and stored as frozen text, screened like any document, and
  enters prompts only as quoted data. There is no "cite the live web" path. This opens the
  open-web seam that the execution contract defers, so it needs an ADR.
- 🟡 **Skew is shown.** The Sources tab splits documents by source type and by country where known
  (approach § 6).
- 🟡 **Evidence binds to the wording** of its item (§ Editing during the check).
- ✅ **Every link answers two questions** (owner, 2026-10-26: "the evidence for each connection is
  in fact the Assumption … make the distinctions between it worked elsewhere and it worked here").
  This replaces separate assumption objects.
  - *Worked elsewhere*: where this step was tried, did the change follow? Evidence about the effect
    and its mechanism. Shown as "<grade> evidence it worked elsewhere".
  - *Holds here*: will it work for this population, in this place, now? Evidence from the plan's
    place, or evidence that the link's conditions hold or fail in comparable settings (Cartwright
    and Hardie 2012: "it worked there" is not "it will work here"). Shown as "<grade> evidence it
    holds here". Evidence from the plan's place is preferred, never required.
  - One judge call per link and document returns a stance for each question, each with its own
    quote. Each grade counts only its own stances.
  - The canvas colours a link by the lower of the two grades; the panel and Detailed information
    show both. A link that worked elsewhere but has weak *holds here* evidence is the *critical
    connection · test this first* case. The draft proposes it; after choose, code re-picks it:
    among links on kept success pathways whose *worked elsewhere* grade is medium or strong and
    whose *holds here* grade is weak or none, the one on the most kept pathways (ties: the earlier
    one in pathway 1). If none qualifies, the link with the lowest *holds here* grade on the most
    kept pathways. A critical connection the user marked is kept.
  - ✅ **Evidence is not repeated** (owner, 2026-10-26). A document appears once in a link's list,
    tagged *elsewhere*, *here* or both. The *holds here* sentence never restates a finding the
    *worked elsewhere* sentence already gave; it names that study and says why it also counts
    here (for example, "The London study was in England, so it counts here too"). When every
    document answers both questions the same way, the two paragraphs merge into one ("Strong
    evidence, including in England").

## Connections to other tasks

✅ Light for now (owner, S10): "because we only have longlist for now, let's just test an
integration where a user in the option report view can click a button at the end that says,
Design a theory of change".

- ✅ The **option page** of an Options scoping task gets **"Design a theory of change"** at the end.
  The Options scoping spec listed this as a deferred consumer (OS capability.md § Artefact &
  scope); this spec brings that one action in.
- 🟡 It opens a new ToC task in the same project, linked to the scoping task through a `task_link`
  row that names the option. The entry point is **intervention-first**, and the Task Agent starts
  with these slots filled, each labelled *from your options scoping*:

  | ToC slot | Taken from |
  |---|---|
  | Intervention | The option's name, description and specified design |
  | Intended change | The scoping plan's outcomes |
  | Target population | The scoping plan's target unit |
  | Where | The scoping plan's Where |
  | Context | The scoping plan's considerations and the user's stated context |
  | Evidence restriction | The scoping plan's evidence restriction |

  An option names a kind of action, not a programme. The Task Agent asks for what a ToC needs and
  the option lacks, mainly the dosage and the delivery details.
- ✅ **The option's documents are shared, not copied** (owner, 2026-10-23: "option's documents
  should be shared across tasks … but don't duplicate"). This is how `inherit` already works: a
  document is stored once, and the ToC task gets only its own membership row pointing at it, plus
  its own screening row, because the ToC plan asks a different question. Classification and
  appraisal are read from the scoping run, never copied.
- 🟡 **Order matters.** `inherit` runs before the item searches. The duplicate check in `acquire`
  then sees the inherited documents, so when a ToC search finds one of them again, it is not
  stored twice.
- 🟡 **A known gap, not fixed here.** That duplicate check looks only inside one task. A document
  that a ToC search finds, which some *unlinked* task also found, is stored a second time. This
  is how all capabilities work today; a shared document store across tasks is a separate change
  (the meta-analysis seam in `docs/deferred.md`).
- ✅ **Several theories from one option** are allowed (owner, S11), for example one per population.
  The option page lists them all.
- ✅ **When the scoping task runs again**, the ToC keeps reading the pinned run and shows "a newer
  run is available" (owner, S11). To use the newer run, the user starts a new theory from the
  option page; a task never re-links after creation (task 054 contract C13).
- 🟡 Any option that is not merged can start a ToC. An excluded option passes its exclusion reason
  to the Task Agent as context.
- ⏸ **Later:** links to Evidence search tasks (their documents and extracted findings), linking
  after creation, a full Evidence search on a weak link, Value for money reading a ToC.

## Product surface

- 🟡 **New task page.** "Theory of change" becomes available behind a build flag
  (`VITE_THEORY_OF_CHANGE`).
- 🟡 **Agent tab.** The Task Agent leads the plan conversation. It takes the pasted text or the
  uploaded file there. After the draft, the same thread takes change requests and shows progress.
- ✅ **Uploaded files are kept** (owner, S8: "keep them on S3? why not?"). 🟡 They go to a private,
  encrypted S3 bucket and are readable only through the task's own access rules. Tasks are archived,
  never deleted, so a file stays while its task row exists; only the operator script that
  hard-deletes tasks removes it (task 054 contract C8). History records the name, size and a hash. A new bucket is an infrastructure change,
  recorded in the ADR.
- ✅ **Stress test: conversation only** (R11). A button opens a new chat of kind `stress_test`. Four
  short questions, one at a time, each tied to one box or link that the canvas
  highlights: the critical connection failing here, mechanism, scope and population, failure. Replies are
  two to four sentences and use only the theory and its evidence.
- 🟡 **Discuss.** The existing chat, with the graph and its evidence as context, through the
  existing grounded-answer path. It does not edit the graph.
- 🟡 **Canvas editing.** Add, edit, delete and connect boxes; edit a link's sentence and
  conditions; mark the critical connection; restore a set-aside pathway. Each edit writes an
  event to History.
- ✅ **Export** (R13; owner, S9), in this order: the canvas as PNG and SVG; the reference list as
  CSV; the graph as JSON; a **draw.io file**, which Miro, Lucidchart and diagrams.net can import; a
  **PowerPoint file** with native boxes and connected arrows. 🟡 Google Slides opens the PowerPoint
  file; whether it keeps the connected arrows must be tested before the screen promises it.

## Evaluation

✅ No public dataset of real theories of change exists, so we build small reference sets from
published reports (research § 2). ✅ **Start with E1, E2 (with E2b) and E6** (owner, S9). 🟡 The
ladder:

| # | Eval | Measures | Data | Metric |
|---|---|---|---|---|
| E1 | Structure checks | Every draft is well-formed: layers in order, no orphan boxes, every link with at least one condition, at least one failure pathway, every pathway a connected route, every evidence item on a stored document | The tool's own drafts on about 30 descriptions | Pass rate per check; runs in CI |
| E2 | Judge on public data | Stance accuracy given an abstract | SciFact, Check-COVID, PubMedQA, Evidence Inference, mapped to our stances; plus an ablation arm (abstract removed, expect "not about this item") | Macro-F1; how often a challenge is called support |
| E2b | Grades against outside references | Whether our grade and flags agree with other evidence tools on the same claims | **Consensus** (its Consensus Meter: support, mixed, contradict) and **System** (a graph of statistical relationships from published studies, mostly health; public graph in closed beta until autumn 2026) | Agreement by claim; cases where we say *strong* and they say *contradict* |
| E3 | Image import on rendered diagrams | Reading a diagram with known answers | Our own graphs rendered in several layouts; FlowVQA as an outside check | Box F1 with fuzzy text match; link F1; direction; layer accuracy; condition recall |
| E4 | Image import on real figures | The same, on published diagrams | 30–50 figures from GOV.UK plans, Campbell reviews, Youth Endowment Fund reports, labelled by hand | As E3 |
| E5 | Judge on our own data | Stance accuracy on real item and document pairs, including Overton and web | 150–200 pairs from real runs, two labellers with a written guide for recording conditions; includes documents labelled for both questions on one link, with different stances, and supports that record a condition | Agreement between labellers; judge against the agreed label |
| E6 | Rebuild a published theory | Draft quality against a human theory | 20–40 reports with separate intervention text and theory figure, preferably 2025–26 | Recall of the human impacts and outcomes; soft link F1 and direction; rubric judge on Mayne's criteria; stability over 5 runs |
| E7 | Back-test against reviews | Whether the check finds challenge evidence where reviews found no effect | EEF Toolkit strands, null EEF trials, Campbell reviews with null or harmful findings, effective ones as controls; the review itself and later papers excluded | Separation between the two groups |
| E8 | Expert panel | Usefulness against current practice | 5–8 evaluators, about 10 interventions, tool against published theory against a plain chatbot, labels hidden | Win rate; rubric means; "would you use this as a first draft?" |

- 🟡 **E2b costs and access.** The Consensus API is billed on every call (about $0.05) on a beta
  account, so each E2b run needs the owner's approval and a fixed claim set with cached results.
  System's access and coverage outside health must be checked first.
- The draft rubric for E6 and E8 is the approach § 8 checklist plus Mayne 2017's criteria. Writing
  it is lead-only prompt work ([../../system/prompting.md](../../system/prompting.md)).

## Rulings

**First round (2026-10-23):** R1 Magenta Book; pathways drafted, checked against evidence,
consolidated, set-aside ones shown · R2 four layers · R3 guidance wording · R5 check in the
background while the user edits · R6 abstracts only · R7 web search in · R9 image upload in · R10
backward draft in one pass · R11 stress test is conversation only · R12 new dependencies fine · R13
export slides, Miro if easy · R15 evals · R16 see R1.

**Third round (2026-10-23):** source option column agreed · option documents shared, not
duplicated · on the Bedrock route, web search calls go to Bedrock's US endpoint.

**Second round (2026-10-23):** S1 follow the Magenta Book fully: Inputs, Outputs, Outcomes, Impact
· S2 no overall score for now · S3 boxes get searches too, with case studies (replaced 2026-10-26: boxes are not searched or graded; case studies come from link evidence) · S4 strong, medium and
weak for link strength · S5 consolidate by distinct and relevant, choose by promising and evidence
· S6 strength rule: try it, then test against evals · S7 web search with OpenAI's own tool · S8 keep
uploads on S3 · S9 canvas library and exports agreed; start with E1, E2 and E6, and look at
Consensus and System · S10 light connections: one "Design a theory of change" button on the option
page · S11 a newer source run is flagged; several theories per option allowed.

**Wireframe and journey review (2026-10-26):** the visual and evidence rulings are in § Output
structure and § Trust rules, and in the task 054 contract as W1–W17. Journey: J1 starting from an
option reuses everything the option answers; only the intended change is confirmed. Connecting to
Options scoping is preferred, but the capability may ship standalone first if the link would
disturb Options scoping · J2 the Task Agent asks at most two questions before drafting (the
measurable change; whether a theory exists), more only if its latency is low · J3 the draft shows
on the canvas at once, and the Task Agent posts a message in the sidebar · J4 the existing run
notification when the check ends · J5 the Task Agent lists each change with its own Undo, beside
the blue dots · J6 the canvas and Detailed information are equal ways to read; neither is primary ·
J7 the Task Agent always suggests a stress test after the check · J8 the PDF report and the
PowerPoint both matter · J9 how an older theory signals it may be out of date is postponed. ·
Later the same day: assumptions are not separate objects; every link answers *worked elsewhere*
and *holds here*, and its conditions hold the Magenta Book's assumptions.

## Open questions

No open questions remain from the owner rounds. Checks for the contract: the Bedrock key and
identity must be valid for us-east-1 as well as London (a short-term Bedrock key may be tied to the
region it was made in); the Google Slides import of PowerPoint connectors; System API access.
