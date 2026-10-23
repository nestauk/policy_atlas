---
type: Capability spec
title: Theory of change (ToC)
description: The declarative theory-of-change spec. The third v3.0 capability; it drafts a Magenta Book causal chain on a canvas, grades the evidence for each box, link and assumption with the Evidence search machinery and the web, consolidates the pathways, and lets the user stress-test the result.
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
  supporting-activities band (research § 1).
- 🟡 **Outcome.** The user describes a change they want, an intervention, or both, or brings a
  theory of change they already have. They get a **theory-of-change canvas**: success and failure
  pathways through the four Magenta Book layers, the assumptions on each link, the context, and a
  reason for each pathway kept or set aside. Each box, link and assumption shows how strong its
  evidence is, and the evidence for and against it. The canvas is a first version to work from
  (approach § 1, § 7).
- 🟡 **The theory is the reasoning and the evidence; the canvas shows it.** The stored object is
  the graph with its assumptions and evidence. The canvas, the list view and every export are
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
  The header shows counts by grade instead.
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
| **Assumption** | A condition that must hold for one specific link to work. It always belongs to a link (Mayne 2015: "only when we add the assumptions to the causal links … do we get a theory of change"). |
| **Assumption type** | Set by code from the layers the link joins, with the Magenta Book's three types: *take-up* (outputs to outcomes), *behaviour change* (outcomes to outcomes), *benefits and unintended effects* (outcomes to impact). An inputs-to-outputs link has the type *delivery*. |
| **Load-bearing assumption** | The assumption whose failure would break the most of the theory. Shown as "Test this first". |
| **Context** | External factors and other policies (Magenta Book band "Contextual factors and external influencers"). |
| **Supporting activities** | Work the chain needs but beneficiaries do not receive: training, referrals, marketing, setup (Magenta Book band "Supporting activities…"). |
| **Pathway** | One route through the layers, from an input to an impact. |
| **Success pathway** | A route by which the intervention brings the intended change. |
| **Failure pathway** | A route by which a step fails or the intervention causes harm: the Magenta Book's "negative programme theory" (p.47). Ends in a failure outcome. |
| **Set-aside pathway** | A pathway considered and not kept, with its reason. The user can restore it. |
| **Evidence grade** | *Strong*, *medium*, *weak* or *no evidence found*, for a box, a link or an assumption (§ Trust rules). |
| **Case study** | A named programme or place where a box's result was seen, from a document, with a quote. |
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
plan ══approve══▶ draft or import ─▶ evidence check (background) ─▶ discover ─▶ consolidate ─▶ summarise
                         │                  ▲                                          │
                         └─ user edits on the canvas at any time ──────────────────────┘─▶ re-check changed items
                                              stress test · discuss: chats, any time after the draft
```

1. 🟡 **Plan.** The Task Agent conversation fills the plan (§ Plan slots); the user approves it.
2. 🟡 **Draft** (R1 step 1). One model call writes **candidate pathways from reasoning**: up to 6
   success and 3 failure pathways through the four layers, with links, mechanisms, assumptions,
   context, supporting activities, the result criteria for each box (with a suggested indicator
   for each output, outcome and impact) and the load-bearing assumption. In the existing-theory
   entry point, an **import** call reads the user's text, image or PDF instead and only adds what
   is missing, labelled. The canvas shows the result at once.
3. 🟡 **Evidence check, in the background.** One search per **link**, per **assumption** and per
   **output, outcome and impact box** (owner, S3: "boxes could still have searches"), across
   OpenAlex, Overton and the web; the Evidence search spine on the pooled documents; then a
   judgement per item and document ([components.md](components.md)). Progress shows in the Task
   Agent thread through the existing run events.
4. 🟡 **Discover** (R1 step 2). One pass over the screened documents finds mechanisms, outcomes and
   failure modes the draft does not have. Each becomes a candidate pathway, labelled *found in the
   evidence*, with the documents and quotes that suggested it. Its new links are judged against the
   documents already found, with no new search.
5. 🟡 **Consolidate** (R1 step 3; owner, S5). Two stages:
   - **Aggregate by *distinct* and *relevant*.** Pathways that share a mechanism merge into one.
     Pathways that do not reach the intended change for the plan's population and place are set
     aside.
   - **Choose by *promising* and *evidence*.** If more than 6 success or 3 failure pathways
     remain, the ones kept are those most plausible within what the intervention can influence
     and with the stronger evidence grades on their links, read as counts, never a score.

   Every kept and set-aside pathway gets a one-line reason naming the criterion. Code checks the
   limits and flags every change to something the user made or edited (§ Editing during the
   check). Mayne's limit applies to
   each pathway view: about 13 boxes before a theory "may be a mess".
6. 🟡 **Summarise.** A short summary of the theory and its evidence, and **evaluation questions**
   made from the weak links and the untested assumptions (approach § 4.2 step 6).

### Editing during the check

✅ The user can edit from the moment the draft appears (R5). 🟡 Rules:

- Each evidence row stores a hash of the text it judged. If the text changed, the row shows as
  *out of date* and never counts toward the grade.
- An item the user adds or edits during the check is queued. When the main check ends, one
  follow-up check runs on every queued item. After that, an edit marks the item *out of date*, and
  the user presses "Check again" (one item, or all changed items).
- A deleted box, link or assumption loses its pending results.
- Discover and consolidate run on the graph as it is when the check ends. ✅ They **may** merge,
  reword or set aside items the user made or edited, but every such change is **flagged** (owner,
  2026-10-23: "still allow Policy Atlas to consolidate or edit the ToCs that users touched, just
  it should be flagged"). 🟡 A flagged item shows a *changed by Policy Atlas* mark with the reason;
  its panel shows the user's version beside the new one, with **Keep mine**. A set-aside pathway
  that held user work is marked *includes your edits* in "Considered and set aside".
- When consolidate finishes, the Task Agent thread says what changed ("2 pathways added from the
  evidence, 3 set aside, 2 of your edits changed"), with one **Undo** for the whole step. Every
  change is an event in History.
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

✅ The canvas is the default view of the Result tab (approach § 7).

- **Header.** "Intervention → intended change", the population, the check state ("Evidence check
  running: 12 of 31 items" or "Checked 23 Oct 2026 · 2 items out of date"), and the counts by
  grade ("31 items: 4 strong, 9 medium, 7 weak, 11 no evidence found; 3 with evidence against").
- **Test this first.** The load-bearing assumption, why, and its grade.
- **Canvas** (Magenta Book Figure 2.2 layout):
  - The **context band** across the top.
  - Four **layer columns**: Inputs · Outputs · Outcomes · Impact.
  - The **assumptions band** under the chain (R1: "visualise the assumptions better than in the
    prototype"). It has one slot per layer change, so each assumption card sits under the link it
    belongs to. Each link shows a small numbered marker ("A3"), and the card carries the same
    number. Hover or select either one, and the other lights up with a dotted line between them.
    Each card shows its type, its grade as a coloured edge and word, its flags, and a star if it is
    load-bearing. This combines three patterns from the guidance: the Magenta Book band, labelled
    arrows (Vogel 2012) and typed assumptions (Mayne 2015) (research § 1).
  - The **supporting-activities band** along the bottom.
  - **Failure pathways** in their own colour, ending in failure outcomes below the success chain.
  - A **pathway selector**: the full theory, one pathway at a time, success only, failure only.
  - Links are coloured and styled by grade, with a small mark for *evidence against*. A box shows
    its grade as a thin bar along its edge. An item still being checked shows a faint animation.
  - A **key** that is always visible: the layers and their meanings, the grades and the rule behind
    each, the flags, the line styles, the assumption markers and types.
  - Short on-canvas help: "Click a box, an arrow or an assumption for its evidence."
- **Detail panel** (on click):
  - A **box**: layer, text, origin, result criteria, its grade, the **case studies** found (each
    with programme, place, source type and quote, typed by source as in Options scoping), the
    **indicators** the documents used, and its incoming and outgoing links.
  - A **link**: if / for / then / because / unless, its assumptions, its grade with the rule that
    gave it, its flags, and the evidence in three groups: *supports* · *supports under conditions*
    · *challenges*. Each item has its title, year, source type (academic, policy document, web),
    appraisal tier, a quote, and a link to the source.
  - An **assumption**: its type, the link it belongs to, its grade, the same evidence groups.
- **Pathways list.** The kept success and failure pathways as cards, each with its reason. Then
  **"Considered and set aside"** (R1), each with its reason and a **Restore** button.
- **Summary and evaluation questions.** Written after the check, from it.
- **Your original.** For an imported theory, the uploaded image or PDF beside the canvas.
- **Sources tab.** The existing tab: every document read, by source, with what was searched and
  what was not.
- **History tab.** The existing event log: plan, draft, imports, every edit, every check.

## Trust rules

ToC follows the Options scoping principle: **generation is free, interpretation is labelled,
assessment is grounded** ([../options-scoping/trust.md](../options-scoping/trust.md)).

- 🟡 **Origin label** on every box, link, assumption and pathway: *drafted by Policy Atlas* · *found
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
  | Holds under conditions | Some support is only for some groups, places or conditions. The conditions are listed. |

  | Status | When |
  |---|---|
  | Checking | The check is running on this wording. |
  | Out of date | The text changed after the last check. |

  Supporting documents include those that support under conditions. Web pages show and count toward
  the flags and toward *weak*, but never toward *medium* or *strong* (Options scoping trust rule:
  "a web case study never raises an evidence-strength rating"). The rule is a banding, which
  Options scoping does not allow in v1 without its own eval; ToC adopts it deliberately, records it
  in the task ADR, and tunes it with evals E2, E2b and E7 (owner, S6).
- 🟡 **Every evidence item carries a quote**, checked by the existing quote verifier against the
  abstract or the frozen web page text. An item without a verified quote is dropped.
- 🟡 **Boxes get searches as well as result criteria** (owner, S3). Inputs boxes get no search:
  they describe what the intervention does. For an output, outcome or impact box, the search asks
  whether comparable interventions achieved that result and how it was measured. Its documents
  give the box its grade, its **case studies** and its **indicators**. Case studies are typed by
  source; a web case study never raises the grade.
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
  run is available", with a button that re-links and re-checks (owner, S11).
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
  encrypted S3 bucket, are readable only through the task's own access rules, and are deleted with
  the task. History records the name, size and a hash. A new bucket is an infrastructure change,
  recorded in the ADR.
- ✅ **Stress test: conversation only** (R11). A button opens a new chat of kind `stress_test`. Four
  short questions, one at a time, each tied to one box, link or assumption that the canvas
  highlights: mechanism, load-bearing assumption false, scope and population, failure. Replies are
  two to four sentences and use only the theory and its evidence.
- 🟡 **Discuss.** The existing chat, with the graph and its evidence as context, through the
  existing grounded-answer path. It does not edit the graph.
- 🟡 **Canvas editing.** Add, edit, delete and connect boxes; add, edit, delete and move
  assumptions; mark the load-bearing assumption; restore a set-aside pathway. Each edit writes an
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
| E1 | Structure checks | Every draft is well-formed: layers in order, no orphan boxes, every assumption on a link, at least one failure pathway, every evidence item on a real document | The tool's own drafts on about 30 descriptions | Pass rate per check; runs in CI |
| E2 | Judge on public data | Stance accuracy given an abstract | SciFact, Check-COVID, PubMedQA, Evidence Inference, mapped to our stances; plus an ablation arm (abstract removed, expect "not about this item") | Macro-F1; how often a challenge is called support |
| E2b | Grades against outside references | Whether our grade and flags agree with other evidence tools on the same claims | **Consensus** (its Consensus Meter: support, mixed, contradict) and **System** (a graph of statistical relationships from published studies, mostly health; public graph in closed beta until autumn 2026) | Agreement by claim; cases where we say *strong* and they say *contradict* |
| E3 | Image import on rendered diagrams | Reading a diagram with known answers | Our own graphs rendered in several layouts; FlowVQA as an outside check | Box F1 with fuzzy text match; link F1; direction; layer accuracy; assumption recall |
| E4 | Image import on real figures | The same, on published diagrams | 30–50 figures from GOV.UK plans, Campbell reviews, Youth Endowment Fund reports, labelled by hand | As E3 |
| E5 | Judge on our own data | Stance accuracy on real item and document pairs, including Overton and web | 150–200 pairs from real runs, two labellers with a written guide for "under conditions" | Agreement between labellers; judge against the agreed label |
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
· S2 no overall score for now · S3 boxes get searches too, with case studies · S4 strong, medium and
weak for link strength · S5 consolidate by distinct and relevant, choose by promising and evidence
· S6 strength rule: try it, then test against evals · S7 web search with OpenAI's own tool · S8 keep
uploads on S3 · S9 canvas library and exports agreed; start with E1, E2 and E6, and look at
Consensus and System · S10 light connections: one "Design a theory of change" button on the option
page · S11 a newer source run is flagged; several theories per option allowed.

## Open questions

No open questions remain from the owner rounds. Checks for the contract: the Bedrock key and
identity must be valid for us-east-1 as well as London (a short-term Bedrock key may be tied to the
region it was made in); the Google Slides import of PowerPoint connectors; System API access.
