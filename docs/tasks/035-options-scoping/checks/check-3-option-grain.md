# Feasibility check 3 — option-grain construction and selection stability

Source: `../feasibility-checks.md` § 3. Question: do mentions and findings produce meaningful
options, packages and variants, and does relabelling a primary lever move shortlist places
without changing policy substance?

Method as run (2026-09-08): the Evidence search's shared two-stage clustering engine
(`clustering_engine.cluster_units`, ADR 0018) was run at option grain with a new discovery and
assignment prompt pair (`os_option_cluster_v0`) over three real corpora exported read-only from
staging, from abstract mentions (`os_abstract_v0`) and, for the deep search, from the 128
inherited IOF findings. Options were then typed against ruling 11's lever list
(`os_lever_typing_v0`), grouped into themes on the same engine, given deterministic coverage, and
run through a deterministic shortlist procedure (one place per primary lever type present;
reason = only option of its type, else widest implementation record). Two perturbations:
paraphrase every option's label and design and re-assign every mention; re-type levers with the
taxonomy shuffled three times and once with labels but no definitions. Runner: `oscheck.py`
(commands `options`, `stability`). Prompts: `os_profiles.py`. Raw results are held outside the repository (they carry staging document text): session scratchpad `staging/out/*.options.*.json`,
`staging/out/*.stability.json`; a zip is available from the owner on request.

The method named NEET, industrial energy prices and regional disparities. Staging holds none of
those corpora. Substitutes, all real user runs: **physical inactivity** (the evidence-dense case;
351 documents; the only deep run), **childhood obesity in the UK** (151), and **local
unemployment** (48; thin and structural; the closest to NEET, and it holds the European Youth
Guarantee). No-document suggestions were **not** injected in this run; that path is untested here.

## 1 — What the machinery produced

| corpus | units | from documents | options (ceiling) | residual | documents in 1 / 2 / 3+ options | themes | engine calls, time |
|---|---|---|---|---|---|---|---|
| inactivity, mentions | 827 | 295 | 29 (40) | 213 (26%) | 164 / 53 / 50 | 8 (+4 unthemed) | 22, 36 s |
| inactivity, deep findings | 128 | 17 | 22 (22) | 8 (6%) | — | — | 5, 11 s |
| obesity, mentions | 461 | 128 | 32 (40) | 130 (28%) | 63 / 16 / 39 | 8 | 13, 30 s |
| unemployment, mentions | 103 | 42 | 18 (18) | 22 (21%) | 25 / 6 / 7 | 5 | 4, 11 s |

Many-to-many is real and large: a third of the inactivity documents and half of the obesity
documents that carry mentions land in two or more options; one document lands in eight. A
document is not an option (ruling 31) is confirmed on the data.

**Grain.** The two paths produce options at different grains.

- From **mentions** the discovered options are mostly **classes**: "School-based physical
  activity programmes" (24 documents), "Primary care exercise referral and prescription" (13),
  "Free or subsidised access to activity facilities" (14), "Sugar and soft drinks fiscal
  measures" (15), "Food advertising and promotion restrictions" (21). Some are option-grade
  designs a minister could adopt; others read as themes ("Population-level physical activity
  promotion policy", 34 documents; "Targeted support for disadvantaged or inactive groups", 34;
  "Cross-sector governance and coordination", 32).
- From **deep findings** the options are **named programmes**: JU:MP, The Daily Mile, Creating
  Active Schools, Playing Out, Transform-Us!, Walk with Me, the Opening School Facilities Fund;
  each with one to three documents, because 64 of the 128 findings come from one synthesis.

Both are legitimate grains; neither alone is the longlist. The mention path gives coverage; the
finding path gives specified designs. The design must let a class option carry its named
implementations as children (*part of*, or a new *instance of* relation), or the option card
will show a class with 24 documents and no design to assess.

**Bundles, variants, reviews.** The discovery prompt kept bundles and components apart where
both were present: "JU:MP whole-system programme" beside "Creating Active Schools programmes"
(finding path); "Whole-systems obesity strategy" (29 documents) beside its ingredients.
Defining features did split options when the set held both sides: "Nursery obesity prevention
with parent home component" beside "Preschool community obesity prevention for parents";
"Teacher-delivered school obesity prevention" beside "School-based obesity prevention
programmes". Reviews entered as class-grain evaluated mentions ("Community-wide,
multi-strategic interventions") and clustered with the programmes they review. Comparator
mentions (51) were excluded before clustering.

**The residual.** A quarter of mentions in the two dense corpora fit no option. Reading the
213 inactivity residuals, three kinds:

1. **Not interventions** the profile should not have recorded: behaviour-change theories,
   "physical activity", "cluster randomised controlled trial", a conference, a declaration.
2. **Out-of-question interventions** from multi-topic policy documents: universal free school
   meals, scrapping the two-child limit, community food programmes.
3. **Genuine uncovered options**: Parkrun, high-intensity interval training, supervised
   gym-based classes, sedentary-behaviour interventions for adults, step-count monitoring.

Kinds 1 and 2 are profile and screen work (the mention needs a "could a government adopt this"
gate, and the residual needs the constrain step's relevance screen). Kind 3 is discovery
under-producing: the ceiling of 40 was not binding (29 found), so breadth, not the cap, lost
them. In the thin corpus the ceiling **was** binding (18 of 18): the ceiling formula (one option
per six units, floor five) is too tight for small corpora.

**Lever typing.** "Provide a service" took 17 of 29, 18 of 32 and 9 of 18 options. The typer
named a runner-up for 18 of 29 and 27 of 32 options in the dense corpora: the primary lever is
a close call for most options.

## 2 — Selection stability

**Baseline shortlists** (one place per primary lever type present):

| corpus | places | seated options (documents, evaluated) |
|---|---|---|
| inactivity | 6 | Built environment changes (19, 4) · Cross-sector governance (32, 1) · Mass media campaigns (19, 2) · Targeted support for disadvantaged groups (34, 6) · Population-level promotion policy (34, 2) · Incentives and financial support (16, 2) |
| obesity | 6 | Whole-systems strategy (29, 1) · Social marketing campaigns (6, 1) · School-based prevention (17, 6) · Advertising restrictions (21, 1) · Healthy food access (13, 0) · Sugar and soft-drink fiscal measures (15, 0) |
| unemployment | 5 | Labour-market partnership bodies (3, 1) · Vocational training (11, 3) · **Collective bargaining (1, 0)** · Place-based job creation (8, 1) · Employment tax credits (3, 0) |

**Perturbation (a) — paraphrase the options, re-assign every mention.**

| corpus | mentions that changed option | median membership overlap (Jaccard) | least stable options | shortlist places moved |
|---|---|---|---|---|
| inactivity | 147 of 827 (18%) | 0.67 | Community-wide multi-strategy 0.39 · Whole-system strategies 0.49 · Community partnerships 0.54 | 2 (the "provide a service" place swapped between two class options with near-equal records) |
| obesity | 75 of 461 (16%) | 0.77 | School PA promotion 0.17 · School nutrition education 0.44 · Commercial determinants 0.47 | 0 |
| unemployment | 8 of 103 (8%) | 1.00 | Place-based job creation 0.73 | 0 |

The fuzzier the option's grain, the less stable its membership. Class options lose or gain a
third of their members on rewording; named designs keep theirs. The shortlist moved only where
two class options had near-equal implementation records.

**Perturbation (b) — re-type levers with the taxonomy shuffled or stripped of definitions.**

| corpus | options whose primary lever changed, per run | lever set changed | shortlist places moved, per run |
|---|---|---|---|
| inactivity | 2 · 2 · 0 · 1 of 29 | never | 0 · 0 · 0 · 0 |
| obesity | 1 · 3 · 1 · 3 of 32 | once (a "devolve" place appeared) | 0 · 1 · 0 · 0 |
| unemployment | 1 · 1 · 3 · 1 of 18 | twice ("change who runs the system" came and went) | 0 · 0 · **4 of 5** · 1 |

What this shows. Relabelling a primary lever does move shortlist places without changing policy
substance, and the effect concentrates where the instrument is weakest: thin corpora, singleton
lever types, and options with a named runner-up. In the unemployment corpus one shuffle of the
taxonomy order moved four of five places, and the baseline seated "Collective bargaining" on
one document with no evaluation because it was the only "regulate" option. In the dense corpora
the places held under relabelling; they moved under paraphrase instead, at the class-grain
options.

## 3 — Questions for a domain expert

The check's method asks whether the selected comparisons change for a substantive reason. The
owner or an expert should answer these against the `*.options.mentions.json` results:

1. Inactivity: is "Targeted support for disadvantaged or inactive groups" an option or a theme?
   It took the "provide a service" place over "Community-based lifestyle and exercise
   programmes" on 18 versus 14 countries recorded; under paraphrase they swapped. Is either
   choice a substantive one?
2. Inactivity: "Cross-sector governance and coordination" (32 documents, 1 evaluated) holds the
   "change who runs the system" place. Would you assess it, or is it a theme that no department
   could adopt as one thing?
3. Obesity: the sugar levy and advertising restrictions hold places with 0 and 1 evaluated
   documents; the corpus is UK-descriptive rather than evaluative. Is a place on 21 mentions
   and 1 evaluation a reasonable allocation of reading effort?
4. Unemployment: "Collective bargaining" (1 document, unevaluated) took the only "regulate"
   place. Should a lever type with no evaluated option earn a gap message instead of a place?
5. Finding path: the named programmes (Daily Mile, Playing Out, JU:MP) are the options a
   minister would recognise; the mention path never produced them. Should the longlist show
   class options with named implementations beneath them?
6. Are the residual kind-3 options (Parkrun, HIIT, supervised gym classes) ones you would expect
   on a longlist for this question?

## Findings, ranked by whether they change the design

**Changes the design.**

- **C3-1 — Two grains, one longlist: class options must carry named implementations.** Mentions
  give class-grain options with coverage; findings give programme-grain options with specified
  designs. Proposal: the option entity's relations gain **instance of** beside *variant of* and
  *part of* (or *part of* is reused with a type), `longlist` discovers at class grain from mentions
  and at design grain from findings, and the option card shows the class with its named
  implementations beneath. Without this the assessable unit (a specified design, ruling 15) and
  the counted unit (a class with 24 documents) are different things. Affects task 2 and the
  data-model declaration of the option entity.
- **C3-2 — One place per primary lever type is not robust on its own.** Places moved without
  substance under lever relabelling (four of five in the thin corpus) and under paraphrase (two
  of six in the dense corpus), and a lever type represented only by an unevaluated singleton
  earned a place. This fires ruling 42's clause in a bounded form: not "stop using quotas", but
  **add two guards**: (i) a lever type whose options all have zero evaluated mentions earns a
  **gap message, not a place** ("Regulate: mentioned in 3 documents, none evaluates an option");
  (ii) a place is marked **contested** when the seated option's typer named a runner-up lever
  or when a paraphrase-level rival exists (implementation record within one country or one
  evaluated document), and the user is asked to confirm it. Both stay inside ruling 37 (a
  provisional allocation of reading effort). Affects task 3 (`shortlist`).
- **C3-3 — The abstract profile needs an adoptability gate, and the ceiling formula needs a
  floor for small corpora.** A quarter of mentions were residual; roughly half of those were
  not interventions or not for the question. Proposal: the mention record gains a boolean
  "a government could adopt this" (or the constrain step's relevance screen runs over residual
  mentions before they are counted as uncovered); the discovery ceiling becomes
  `clamp(ceil(N/4), 8, 40)` and the check's ceiling-binding case is re-run. Affects task 2.

**Clarifies the design.**

- **C3-4 — Lever typing is a close call for most options; record the runner-up.** 18 of 29 and
  27 of 32 options had a named runner-up. Proposal: the option entity stores primary, secondary
  and runner-up lever types with the one-sentence reason, so the grid and the gap messages can
  show where the typing is soft. The taxonomy itself needs no change from this run, though
  "provide a service" absorbing more than half of every corpus suggests it wants splitting
  (delivered programme versus facility or infrastructure access) before the grid is useful.
- **C3-5 — Membership stability is a property of grain.** Class options lost a third of their
  members on rewording; named designs kept theirs. A membership record should therefore carry
  the assignment's confidence or a re-assignment check under paraphrase, and the coverage
  denominators shown to the user ("12 of 12 evaluations read") should be computed over the
  stable core, not over one run's assignment. Affects task 2 (membership record) and ruling 39's
  denominator rule.
- **C3-6 — Themes work as declared.** Eight themes per dense corpus, problem-worded, mapped to
  lever types by their member options; four options unthemed. No change.

**Not tested here.** No-document suggestions (user, ministerial, taxonomy-prompted) were not
injected. The three named logged questions were substituted with staging corpora. The domain
expert's judgement of meaningfulness is the open half of this check (§ 3).

## Cost note for check 5

Abstract profile over 550 documents: about three minutes and roughly 1.6 million prompt tokens
on the mini model. Option clustering over 827 mentions: 22 calls, 36 seconds. Lever typing and
themes: 3 calls. The longlist stage is cheap; nothing here threatens the rapid budget.

## What this means for the contracts

- **Task 2 (longlist).** Mint options at two grains with an instance relation (C3-1); gate
  mentions on adoptability and widen the discovery ceiling (C3-3); store primary, secondary and
  runner-up lever types (C3-4); give the membership record a stability marker (C3-5).
- **Task 3 (shortlist and assessment).** Add the evaluated-floor gap rule and the contested-place
  flag to `shortlist` (C3-2). The assessment reads specified designs, so it assesses instance-grain
  options or a class option's named implementations, never a bare class.
- **Spec.** Ruling 20 stands (coverage over lever types) with C3-2's guards added; ruling 11's
  list stands, with the split of "provide a service" recorded as a candidate for the eval slice.
