# Design inputs: 034-synthesis-report

Three sources, different jobs. The prototype binds layout; the good sample
binds the language direction; the current sample is the anti-target. None of
them is a contract — [contract.md](contract.md) is.

## 1. The prototype (layout reference)

The owner's clickable prototype, frozen at
[docs/specs/sources/synthesis-report-ux/](../../specs/sources/synthesis-report-ux/README.md)
(2026-08-26). Its Results tab shows the intended page shape: an executive
front matter (answer callout → metadata strip → key findings → case studies →
most relevant sources) ahead of collapsed body sections, References and
Method at the foot.

Owner notes supplied with it (2026-08-26):

- The prototype **still does not have a satisfying heading hierarchy** — its
  headings are visually flat. 034 must go past it on heading levels.
- Note the **bold lead** on key-findings bullets (`**Lead phrase:** warrant`).
- The good sample below is the language direction; **do not over-index on the
  one example** — encode fundamental principles.

Owner fork rulings (2026-08-26, design conversation):

| Fork | Ruling |
|---|---|
| Answer-callout label | **Softer label**, not "The answer" — the spec's citation-free-navigation rule stands, no spec flow-back |
| Sources metadata line | **Keep 031's included-based wording** ("M cited out of K included"); restyle only |
| Gap bullet in key findings | **In** — gap-typed bullets carrying their coverage base; a succinct overview of the evidence base's gaps |
| Authors line | Out — the backend has no author for an artefact |
| Confidence rating | Out |
| "Why this source matters" prose | Out — Most relevant sources is a restyle/move only, ranking unchanged |
| Case studies | **In, as a new synthesis pass** — discharge the 032 parked seam; grain = programmes, not papers |

## 2. The "good" language sample (target)

Owner-supplied, 2026-08-26, verbatim. Invented content on the childhood
obesity question — the *facts, section list and reference format are not
requirements*; the register is. Note: it carries an "Executive summary" /
"Themes" / "International comparisons" header set and author-formatted
references that 034 does **not** copy (the contract's structure rules win).

> **What works to reduce childhood obesity in the UK?**
>
> *Executive summary.* Measures that change the food environment — above all
> the Soft Drinks Industry Levy — carry the strongest UK evidence.
> School-only programmes shift behaviour but have not shifted weight.
> Confidence is moderate: several strong studies agree on what households
> buy, but only one UK study has measured an effect on children's weight.
>
> - The levy worked on sugar. Sugar bought in soft drinks fell 29.5 g per
>   household per week — driven by reformulation, not by households buying
>   less.[1,2]
> - One signal on actual weight. Obesity prevalence among year-6 girls in
>   the most deprived areas fell 1.6 percentage points. No effect detected
>   in boys.[3]
> - School programmes move behaviour, not BMI. The two largest UK
>   cluster-randomised trials found no BMI difference at 24 months, despite
>   measurable activity gains.[4,5,6]
> - Whole-systems local action looks promising. Participating local
>   authorities recorded a small relative fall in year-6 prevalence against
>   matched comparators — but evaluations are young.[8]
> - Main evidence gap. No study yet links promotion-placement restrictions
>   to weight outcomes — purchasing data only.
>
> *Theme: Fiscal and food-environment measures.* The strongest and most
> consistent UK evidence concerns fiscal measures, and specifically the Soft
> Drinks Industry Levy. … The levy is associated with a substantial fall in
> the sugar content of soft drinks purchased by households, driven largely
> by reformulation rather than reduced purchasing.[1,2] Evidence linking the
> levy directly to weight outcomes is thinner but emerging: one
> quasi-experimental analysis reports lower obesity prevalence among year-6
> girls, concentrated in the most deprived areas, with no equivalent effect
> detected in boys.[3] … Gap. No study yet links promotion-placement
> restrictions to weight outcomes; purchasing data only.
>
> *Theme: School-based programmes.* School-based evidence is mixed, and the
> contrast between outcome types matters more than the contrast between
> programmes. … Reviewers consistently read this as school-only
> interventions being too weak a dose against an obesogenic wider
> environment — consistent with the stronger fiscal results above. Gap.
> Little UK evidence covers secondary schools; the trial base is
> concentrated in primary settings.
>
> *Case study: United Kingdom — Soft Drinks Industry Levy, since 2018.* A
> tiered levy charged to manufacturers rather than consumers, set with a
> sugar threshold that producers could reformulate below. Sugar in eligible
> drinks fell 43.7% between 2015 and 2020, and sugar purchased per household
> fell without any fall in soft-drink volume — the signature of
> reformulation rather than reduced buying.[1,2] *Strong evidence ·
> controlled interrupted time series.*
>
> *Case study: Mexico — Sugary drinks excise tax, since 2014.* A flat
> one-peso-per-litre tax on sugar-sweetened beverages, passed through to
> shelf prices rather than absorbed by producers. Purchases of taxed drinks
> fell around 7.6% over two years, with the largest reductions in the
> lowest-income households.[9] Where reformulation is not available as a
> lever, price does the work — but the burden falls on shoppers, not
> manufacturers. *Strong evidence · household panel data.*
>
> *Conclusions.* Overall, the evidence points more strongly to
> population-level food-environment measures than to school-only
> programmes.[1,4] Three things follow for a policy reader. The mechanism is
> settled; the outcome is not. The best-supported measures reliably reduce
> the sugar supplied or purchased. Only one UK study reaches children's
> weight, and its effect is confined to year-6 girls in the most deprived
> areas. Design matters more than instrument. The levy worked because the
> threshold gave manufacturers a reason to reformulate; Mexico's tax worked
> through price, and Chile's package worked because labels and marketing
> restrictions pulled in the same direction. A measure that leaves the
> counter-pressure intact performs worse. Schools are not a substitute for
> the wider environment. The two largest UK trials are well-powered nulls on
> BMI. That reads as insufficient dose against an obesogenic environment
> rather than as evidence that schools are irrelevant.

## 3. The "current" language sample (anti-target)

Excerpts from the live 2026-07-30 childhood-obesity artefact (same question
family; the full artefact is in the dev DB). Each excerpt names the pattern
the language principles ban.

**Corpus-touring instead of naming the world** (banned by P2):

> "A high-level reading of the documents shows that childhood obesity
> interventions have been evaluated across schools, families, early life,
> local services, digital delivery, population policy, implementation and
> equity-focused adaptation."

> "Across the documents, implementation evidence is a strand in its own
> right: process evaluations and syntheses describe resources, training,
> fidelity, parental involvement, cultural tailoring and sustainability as
> recurrent delivery issues."

> "Inference: within the appraised text read here, school meals appear as
> part of broader healthy-diet or school-environment packages rather than as
> a clearly separable body of evaluated school-meal-only interventions."

**Stacked sentences — three findings in one** (banned by P3):

> "School-based programmes are the most developed strand: prior reviews
> found most evaluated prevention studies in primary schools, and
> meta-analyses report statistically significant but small BMI and BMI
> z-score reductions, with Cochrane evidence mixed by intervention type and
> certainty.[5,1,3]"

**Warrant-first, claim buried** (banned by P1):

> "The Cochrane review gives a more qualified picture, reporting
> moderate-certainty evidence of little or no effect on zBMI for some
> comparisons, low-certainty evidence that combined diet-and-activity
> interventions reduced zBMI, and high-certainty evidence that diet
> interventions had little impact on zBMI.[3]"

**Verbose question-restating section title** (banned by P9):

> "What the evidence shows about effectiveness for preventing or reducing
> childhood obesity"

## 4. What the prototype invents that the backend does not have

Recorded so the contract can rule on each (032 precedent):

| Prototype output | Backend today | 034 ruling |
|---|---|---|
| Authors line | No author on an artefact | Out (owner) |
| "Moderate confidence:" line | No confidence rating exists | Out (owner) |
| "N found · M cited" | 031 pinned "M cited out of K included" | Keep 031 wording (owner) |
| Case-study cards | Parked 032 seam | In — new synthesis pass (owner) |
| "Why this study matters" sentences | Facts-only rule (032) | Out — restyle only (owner) |
| "Published 2016–2026" | Cited-years range in the strip | Keep, relabel at contract |
| Author-formatted references | `title (year) · venue` | Out — format unchanged |
