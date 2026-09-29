# Spec changes proposed by task 046 (for the owner's decision)

> **Status:** proposed 2026-09-29 · lead. **Nothing in `docs/specs/` is
> changed by this file.** Each item below is applied only after the owner
> accepts its wording (contract § Spec changes; rubric box 20). Item 0 of the
> contract (`theme` as a component of its own) was applied on 2026-09-28 with
> the owner's accepted wording and is not repeated here.

How to answer: for each item, "accept", "accept with this change: …" or
"reject". The numbers are the contract's.

Each item gives the place, the words to remove or replace (short quotes from
the spec as it stands), and the proposed words.

---

## 1 — OS components § 6 longlist (R1, R2, R9, R14; items 1, 4, 7, 9)

**1a. Reader grain, target size and ceiling.** In the bullet "Suggest
first, then seeded clustering", replace

> are supplied to the clustering as options to assign against, and discovery
> adds new ones under the ceiling `clamp(ceil(N/4), 8, 40)` (D4, accepted).

with

> are supplied to the clustering as options to assign against. **An option
> is named at reader grain: one kind of action a government can take.** A
> named programme, a trial's version and a delivery form are **variants**,
> shown on the option's card with their document counts, never rows
> (task 046, R2). The longlist has a **target size of 20 and a hard ceiling
> of 25**, seeds included; discovery adds no option once the list holds 25,
> and the user's own options can take the list above it (task 046, R1, AM9;
> this replaces `clamp(ceil(N/4), 8, 40)`). Owner: "even 40 feels like a lot
> of options to expect the user to decide on".

**1b. The corpus digest and the baseline.** Add after 1a:

> Discovery reads the plan, the baseline, the seeds and a **corpus digest**
> (the distinct intervention names with their record counts by role), never
> the unit records. The baseline is the reference for discovery, typing and
> `constrain` (task 046, item 9).

**1c. The fold.** Add:

> Suggestions are named at reader grain too, and discovery may **fold** a
> suggested option into a wider one; the folded option shows as a variant
> and as *also found as*. An option the user named is never folded or
> renamed (task 046, R14; owner: "user options aren't folded").

**1d. The residual pass.** In the same bullet, after "shown as numbers", add:

> The unclustered records get **one residual pass** (one more discovery and
> assignment over them only), then they are counted (task 046, R9).

**1e. The flag's meaning.** Replace

> the document covers the intervention but its abstract does not state the
> feature that defines this option

with

> the document covers this kind of action but its abstract does not state
> one of the option's defining features; the full text may say

**1f. No packages from discovery.** In the bullet "The ES characterise
machines", replace

> a bundle becomes a package option with *part of* links to its constituents.

with

> a bundle is one option, and its components are variants on its card;
> discovery mints no package (task 046, item 4). *part of* stays for the
> user's actions and task 3.

**1g. Lever list v2.** In the bullet "Top-down", after the list of lever
types, add:

> Under `lever_types_v2` (task 046, item 7), *provide a service* is direct
> delivery by the state's own bodies; funding a provider is *subsidise*;
> buying from a provider is *procure or commission*. The typing reads the
> plan and the baseline, and ambition is judged against what the baseline
> says is in place. The runner-up lever is shown on the card.

**1h. Open question 4.** Replace "❓ Overlap/dedup and target longlist size
(open question 4)." with "✅ Target longlist size: 20, ceiling 25 (task 046,
R1; closes open question 4)."

## 2 — OS components § 10 extract and § 2–5 (R3, R17; items 13, 14, 15)

**2a.** In the component table row 10 (extract) and in § 2–5 "Out", after
"setting, study geography, population and outcome", add:

> and three **tags against the plan** — population (*on target · adjacent ·
> other*), outcome (a plan outcome, or *other*) and object (*the plan's
> object · option · neither*). The profile receives the plan's target unit,
> outcomes and intended change, with the place removed, as reference for the
> tags only; what it records from the abstract does not change. Tags sort;
> they never drop a record (task 046, R3).

**2b.** Add to § 2–5:

> **Setting** is the kind of place where the recipient meets the
> intervention (school, home, workplace, primary care); never a country, a
> region or a named body; empty for a system-level instrument. **A document
> with a title and no abstract is not profiled**; it stays in Sources and in
> the counts. Non-evidence documents are profiled (task 046, R17).

## 3 — OS components § 2–5 and ⟨longlist depth⟩ (R13, R15, R18, R19; items 18, 22, 23)

**3a. The screen input.** Replace the bullet's opening

> **The longlist intent is PICO-shaped, without Where** (…): the target unit
> (P), the intervention left open (I), the plan's outcomes (O), and the
> setting only when the user stated one as a requirement (S, optional — …);
> no comparison before assessment.

with

> **The longlist intent is PICO-shaped, without Where and without setting**
> (task 045 D20; task 046, R15, R19, which reopens D21): the target unit,
> **read wide** — the plan's population or a wider or adjacent one passes —
> (P), the intervention left open (I) and the plan's outcomes (O); no
> comparison before assessment. The screen's error cannot be seen or
> reversed, so it is wide; `constrain` judges the option, where an error is
> visible and reversible. Owner: "we shouldn't let that stop potentially
> transferable evidence not getting in at the screen step". A setting
> requirement is checked by `constrain`.

**3b. Ingest and the option search.** Replace

> full text is fetched and ingested for the whole screened-in set.

with

> at longlist depth no full text is fetched: the longlist is built from
> titles and abstracts, and task 3 fetches full text for shortlisted options
> (task 046, R13; owner: "remove ingest, full text fetched in task 3").

and replace, in the option-search passage,

> runs as a **child walk** under its own targeted intent record — acquire →
> screen → classify → appraise → ingest → intervention profile — its records
> joining the pool and its entrant a seed in the clustering.

with

> runs as a **child walk** under its own targeted intent record. In a
> longlist walk the child **only acquires**; its documents join the pool,
> and the longlist walk then screens, classifies, appraises and profiles the
> whole pool **once**, against the plan (task 046, R18). The entrant is a
> seed in the clustering. The option search that *Add an option* starts
> keeps the full chain, without ingest.

**3c. The composition row ⟨longlist depth⟩.** Replace its "Made of" cell with

> suggest → an **option search** per entrant (child walks, acquire only, in
> parallel) beside the broad acquire → *join* → screen → classify → appraise
> → extract(**intervention profile**) over every screened-in document →
> longlist → constrain → theme → shortlist (task 045, deliverable 3; task
> 046, R13, R18, R28)

**3d.** The note near the top of the file ("Full text is fetched and
ingested for the whole screened-in set, as in the ES, each source carrying
`text_basis`") gains: "at assessment depth; at longlist depth every source is
*abstract only* (task 046, R13)".

## 3a — OS components § 1 plan, and plan-as-object (R19, AM8)

Add to § 1:

> ✅ **Target unit, setting and place are kept apart** (task 046, R19). The
> target unit says who or what should change and holds no place and no
> setting; the place is Where; a setting is either a requirement or, when
> the user states it without requiring it, an entry in Your context. Owner:
> "We should separate the target unit (who/what the intervention is for),
> from the target intervention setting and geography. But they are still
> important context of what the user wants, and will feed into things like
> transferability assessment."

The same sentence, without the quote, in
`docs/specs/system/plan-as-object.md` where the scoping plan's slots are
listed.

## 4 — OS components § 7 constrain, and OS trust § Screening (R4, R21; items 5, 10, 11, 12; AM12)

**4a.** In § 7 "Out", replace "the three default screens (relevant to
outcomes · distinct · in scope) applied and cited like any other" with

> the three default screens (relevant to outcomes · distinct · in scope)
> applied and cited like any other; **the distinct screen reads the whole
> list in one judgement** (task 046, item 5)

**4b.** Replace "✅ Screens judge the **specified design**; a finding about
the parent's typical implementations is not a finding against a variant
(ruling 15)." with

> ✅ Screens judge the option as a **kind of action**, on its specified
> design (task 046, R21): silence about the target unit or the setting
> passes; *cannot check* is for a real unknown; a setting requirement
> excludes only a kind of action that cannot be delivered through the
> required setting, and evidence from another setting stays attached. A
> finding about the parent's typical implementations is not a finding
> against a variant (ruling 15).

**4c.** Add to § 7:

> ✅ **Place never reaches `constrain`** and is never the reason for an
> exclusion (task 045 D20; task 046, R4). A requirement in which the user
> names a place is judged on the kind of action. ✅ **A wider or adjacent
> population never excludes**: it is shown as *tried on*. ✅ The *relevant*
> screen also passes an outcome on a stated pathway to a plan outcome.

**4d.** OS trust § Screening and shortlisting: replace "Screens judge the
option's specified design" with "Screens judge the option as a kind of
action, on its specified design (task 046, R21)".

## 5 — OS capability § Output structure (Longlist) and § Open decisions (items 7, 23; R1)

**5a.** Beside the *where tried* line (capability.md ~383), add:

> and a **tried on** line — the populations an option's evidence from an
> adjacent population studied, with document counts; a facet on the list,
> never a filter and never an exclusion (task 046, item 23). The card shows
> the option's **variants** and, when the typing names one, the
> **runner-up lever**.

**5b.** § Open decisions: open question 4 is marked closed (target 20,
ceiling 25; task 046, R1).

**5c.** § Depths and modes and OS trust § Provenance labels (AM12): the
depth label *scoping pass* reads

> *scoping pass* (screened on titles and abstracts; at the longlist,
> abstracts only; full text read for the documents an assessment cites;
> document set not confirmed)

and § Depths and modes item 1 drops "full-text ingest" from the longlist
depth's plan-level chain.

## 6 — OS capability § Pipeline and gates (item 9, R13)

Add a recorded principle for task 3:

> ✅ **The baseline is the reference for every judgement** after it: the
> longlist, the shortlist and the assessment judge an option against what
> the baseline says is in place (task 046, item 9; owner: "using the
> baseline more to inform judgements at longlist, shortlist, and assessment
> stages is especially important"). 🟡 Task 3 fetches full text for the
> shortlisted options only; about half of the fetches failed in the seven
> pre-contract runs, and task 3 plans for that.

## 7 — `vocabulary.md`

Three new definitions:

| Word | Meaning |
|---|---|
| Reader grain | The grain of a longlist row: one kind of action a government can take. |
| Variant (of an option) | A design of an option that the evidence or a folded suggestion describes; shown on the option's card, never a row. Different from the *variant of* relation of a user's design edit. |
| Tried on | The populations an option's adjacent evidence studied; a card line and a facet, never a filter. |

## 8 — Decision sheet rows A9 and E4

Decision column updated: A9 "variants on the card, computed from members; no
instance-of relation (task 046, R2)"; E4 "target 20, ceiling 25 (task 046,
R1)".

## 9 — `docs/specs/log.md`

One line per accepted item, dated, with the owner's words.

---

## ADR 0039 (AM12)

ADR 0040 already records the amendments to ADR 0039 decisions 2, 3, 6, 8
and 10. ADR 0039's text is not rewritten (merged ADRs are never rewritten).

## Not proposed

No change to the Evidence search specs. No change to a frozen source under
`docs/specs/sources/`.
