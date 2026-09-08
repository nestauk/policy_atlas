# Feasibility check 2 — evidence attribution and confidence

Source: `../feasibility-checks.md` § 2. Question: can the system distinguish a mention from
support, documents from independent evidence, and inherited availability from compatibility?

Method as run (2026-09-08): the abstract profile (`os_abstract_v0`) and the light full-text
profile (`os_light_v0`), drafted from check 6's field lists in `os_profiles.py`, were run over
real corpora exported read-only from staging: the "physical inactivity" deep Evidence search
(351 screened-in documents, 128 deep IOF findings over 17 documents) and the "local
unemployment" search (48 documents). A hand-built set of 21 documents was read in full by the
light profile. Six target designs in each domain, including two parent–variant pairs, were
used as fixed option lists; every mention, light finding and inherited deep finding was assigned
to a target or to none, and the resulting rows were traced back to their documents and quotes.
Runner: `oscheck.py` (commands `abstract`, `light`, `trace2`). Raw results are held outside the repository (they carry staging document text):
session scratchpad `staging/out/trace2.json` and `staging/out/light.json`; a zip is available from the owner on request.

**Version note (after the pass-4 review, 2026-09-08).** The numbers in this report come from the
first light run: 21 documents, 90 findings, 125 anchors (69 exact · 35 normalised · 21 failed).
The results bundle now holds a later run over 36 documents (136 findings, 196 anchors, 32 failed)
in which six documents were re-profiled to record timing for check 5; the two runs are not
identical, and `trace2.json` was computed from the first. The verdict table should be checked
against a pinned copy of the first run, not the later bundle.

The owner or an analyst should spend the hour on § The verdict table.

## The hand-built set

| ingredient (from the method) | documents used | note |
|---|---|---|
| a systematic review plus overlapping primary papers | Cochrane "Community wide interventions" (two copies, `2de6988a` full text, `262fd5bf` abstract only); equity review `6d71742d` naming free gym-and-swim access, and the free-leisure-access trial `70b93629` it includes | the same review appears twice in the corpus as two snapshots |
| a multi-intervention paper | "Inactive Nation" `b9590c39` (a policy synthesis; 64 of the 128 deep findings come from it; names JU:MP, Daily Mile, Creating Active Schools, Playing Out, and more) | |
| a package evaluation | JU:MP whole-system approach, four documents on one trial (`a3a7243b`, `d745c2c8`, `de29337d`, `d65ae6e0`); "Phase 1 evaluation of a systems-based approach" `66c22122` | |
| a modelled estimate | `e12285a6` cost-effectiveness of Transform-Us!; `576c1dea` healthcare costs of inactivity | |
| an abstract-only source | `70b93629`, `262fd5bf`, `47c7136a` | |
| a changed variant | T1 free leisure access **with** outreach vs T1v **without**; T2 **peer-led** walking programme vs T2v **professional-led**; Y youth guarantee **with** benefit sanction vs Yv **without** | the parent–variant pairs of rulings 15 and 36 |
| an older, partial inherited extraction | the 128 deep IOF records (`iof_v3`), treated as inherited into a scoping task | not older in version; partial in fields, as § 3 shows |

Corpus fact found on the way: five of the 21 read-set documents carry `text_basis = full_text`
with 284 to 796 characters of parsed text. Their "full text" is a failed parse. The runner fell
back to the abstract for them. See finding C2-7.

## 1 — Mention versus support

The abstract profile records a `role` per mention: evaluated · described · recommended ·
comparator · mentioned. Support is a light-profile finding read from text. The two never mix in
the trace.

| target | documents mentioning (any role) | of which *evaluated* | documents with light findings | distinct claims | independent own-data studies | reviews or syntheses among the support |
|---|---|---|---|---|---|---|
| T3 whole-system place-based approach | 37 (18 described · 10 recommended · 3 mentioned · 7 evaluated) | 7 | 4 (one, `e12285a6`, read from its abstract after a failed parse) | 15 | 2 (JU:MP; Transform-Us!) | 1 (Inactive Nation) |
| T4 community-wide multi-strategy programme | 22 | 11 | 2 | 6 | 1 (Antwerp community sport development) | 1 (the Cochrane review) |
| T1 free leisure access with outreach | 2 | 2 | 0 (not in the read set) | 0 | 0 | 0 |
| T2 peer-led walking programme | 1 | 1 | 1 | 5 (from 9 raw findings) | 1 (Walk with Me) | 0 |
| A job search assistance (unemployment) | 6 | 4 | 2 | 2 | 0 | 2 |
| B training programmes | 11 | 4 | 3 | 4 | 0 | 3 |
| C wage or hiring subsidies | 9 | 2 | 2 | 2 | 0 | 2 |
| D public employment programmes | 6 | 1 | 2 | 2 | 0 | 2 |

What this shows. The four counts 37 · 7 · 4 · 2 for the whole-system approach are exactly the
distinctions the source-quality profile must display and never collapse: 37 documents mention
it, most of them policy syntheses that describe or recommend it; seven evaluate it; four were
read; two are independent studies. They are **not one nested set**: three of the four read
documents (`b9590c39`, `d745c2c8`, `e12285a6`) entered the read set by other roles and are not
among the seven evaluated mentions, so the `role` field predicts support but does not bound it
*(clarified after the pass-4 review)*. The `role` field does most of the work before any full
text is read. Described and recommended mentions never became support. Comparator mentions (51 in
the inactivity corpus) are excluded from membership by construction.

## 2 — Documents versus independent evidence

The light profile records a document-level `study_identity` (registration id, programme or
trial name, protocol-only flag, reports-on-own-data flag). Independence is resolved by grouping
own-data documents on programme name first, registration id second.

| case | documents | resolved to | how |
|---|---|---|---|
| JU:MP whole-system trial | `a3a7243b` (ISRCTN14332797), `d745c2c8` ("JU:MP"), `b9590c39` Inactive Nation (cites JU:MP) | 1 study; the synthesis excluded | programme name matched across papers; the synthesis has `reports_on_own_data = false` |
| Walk with Me | `9973f940` (ISRCTN23051918) | 1 study | registration id and name both present |
| Cochrane community-wide review, two snapshots | `2de6988a`, `262fd5bf` | not resolved at this layer | both are reviews, so neither enters the study tally; but their inherited findings count twice (§ 3) |
| Active-labour-market support (A–D) | Card–Kluve–Weber meta-analysis `f03de147`, RCT meta-analysis `f565d93c`, European review `e4c1cd12` | 0 independent studies; 2–3 reviews per target | all support is review-mediated; the reviews pool overlapping primary studies and the abstract-level fields cannot see which |

What this shows. Independence is resolvable where own-data papers carry a programme name or
registration id, and the recogniser must key on name before id (JU:MP carried the id in one
paper and only the name in another). It is **not** resolvable for review-mediated support, which
is the whole of the support in the unemployment domain. The check's "changes the design if"
clause therefore fires in a bounded form: **count documents by default; report an independent-
study count only over own-data documents that carry identity; reviews are documents, never
studies, and are shown as such** ("3 reviews, 0 independent primary studies read").

## 3 — Inherited availability versus compatibility

Every inherited IOF record assigned to a target was tested against the light profile's fourteen
requirements at field grain (ruling 35), and for compatibility with the target's specified design.

| target | inherited records | fields every record lacked | fields most records lacked | compatible with the specified design | in the light read set |
|---|---|---|---|---|---|
| T1 free leisure access with outreach | 6 (from `6d71742d`, `70b93629`, both abstract-basis) | design_features, trial_or_registration_id | comparator (6/6), period (6/6), magnitude (1/6), setting (1/6) | yes, all six | none |
| T2 peer-led walking programme | 3 (`9973f940`) | design_features, registration id, **magnitude** | comparator, period, setting, geography (1/3) | yes; none attached to T2v | yes |
| T3 whole-system approach | 15 (mostly `b9590c39`) | design_features, registration id | comparator (15/15) | yes | yes |
| T4 community-wide programme | 5 (two copies of one review) | design_features, registration id, magnitude | comparator, period, setting | yes | one copy |
| T1v, T2v (variants) | 0 | | | correctly: no parent record leaked | |
| Yv youth guarantee without sanctions | 0 inherited; **1 mention wrongly attached** (`a2415bce`, "European Youth Guarantee scheme", no design features stated) | | | **no**: the sanction feature is unstated, so the mention belongs to neither variant | |

Across all 128 inherited records: `design_features` and `trial_or_registration_id` are absent by
schema; `comparator` is present in 43; `magnitude` (an effect size with its type) in fewer than
half. **No inherited record satisfies the light requirement set.** Where the read set overlapped
(Walk with Me), the light profile added what the inherited record lacked: the 10.64 minutes per
day difference in MVPA the IOF record had marked `unclear`.

What this shows. Ruling 35's "reuse partially, never skip a document" is not a nicety; it is the
only shape that works. Reuse must be at field grain within a schema, and both profiles must carry
the intervention *as implemented* with its design features, or compatibility cannot be judged.
Parent findings did not leak to the variants. But an **unstated** defining feature was resolved
to a variant rather than held back, which ruling 36 forbids.

## The verdict table (for the owner or an analyst, about an hour)

For each row, open the documents named (ids are the first eight characters of
`task_source_snapshot_id` in `trace2.json`, which carries quotes and anchors) and mark the
proposed verdict right or wrong.

| # | proposed statement the system would make | rests on | verdict |
|---|---|---|---|
| V1 | "Whole-system place-based approaches: 37 documents mention this; 7 evaluate it; 4 were read in full; evidence from 2 independent studies (JU:MP; Transform-Us!) and 1 synthesis." | § 1 row T3; identities in `study_identities` | |
| V2 | "JU:MP: +5 minutes of MVPA per day" (Inactive Nation, `b9590c39`) and the JU:MP trial papers report the same programme, so this is one study, not three. | `a3a7243b`, `d745c2c8`, `b9590c39` | |
| V3 | "Walk with Me (peer-led, 12 weeks): MVPA increased; difference in change between groups 10.64 minutes per day at 6 months; 1 study." The three inherited records for this document lacked the magnitude. | `9973f940` findings; anchors marked `normalised` | |
| V4 | "A professional-led walking programme: no evidence read; 1 document evaluates a related design (primary-care exercise programmes, `2efd08d3`)." Walk with Me's results do not appear here. | T2v row | |
| V5 | "Free access to leisure facilities without outreach: no evidence read; the free-access trial with outreach is related evidence for a different design." | T1v row | |
| V6 | "Community-wide multi-strategy programmes: the Cochrane review finds no consistent effect on population physical activity; the Antwerp community sport programme reports higher sport participation (61.3% vs 42.4%)." Two documents; 1 independent study; 1 review. | `2de6988a`, `08dde513` | |
| V7 | The Cochrane review's inherited findings appear under two document ids (`2de6988a`, `262fd5bf`). A count of "5 inherited findings" for T4 double-counts one review. | § 3 row T4 | |
| V8 | "Job search assistance: 2 reviews report positive effects (Card et al. pooled; European review); 0 independent primary studies read." Not "N studies". | § 2 row A–D | |
| V9 | "Public employment programmes: 2 reviews report negative or less positive impacts." Direction is per outcome family; the two reviews use different outcome words ("program impacts", "employment outcomes"). | D row | |
| V10 | The European Youth Guarantee document (`a2415bce`) states no sanction feature. It should attach to neither "with obligation" nor "without sanctions"; the system attached it to "without sanctions". | Yv row | wrong by construction; the fix is C2-3 |
| V11 | Findings with a failed anchor (21 of 125 anchors) would be dropped by the production vetter; none of V1–V9 rests only on a failed-anchor finding. | `light.json` `anchors_verified` | |

## Findings, ranked by whether they change the design

**Changes the design.**

- **C2-1 — Independence: count documents; tally studies only over own-data documents with
  identity.** Review-mediated support (all of it in the unemployment domain) cannot be resolved
  to independent studies at any profile depth short of reading each included study. Proposal:
  the "how sure" cell shows *documents read* and, separately, *independent studies* computed
  only from own-data documents whose `study_identity` carries a programme name or registration
  id; reviews are listed as reviews. The light profile's `study_identity` block (name first, id
  second) is the mechanism; it belongs in the light profile's field set (task 3). This is the
  bounded form of the check's "suppress study tallies, count documents".
- **C2-2 — Field-grain reuse is mandatory, and both profiles must carry the intervention as
  implemented.** No inherited IOF record satisfied the light requirement set; design features
  and study identity are absent by schema. Confirms check 6 F3 (cross-task, field-grain memo)
  and ruling 44.1's "intervention as implemented". Proposal: the light profile is an IOF subset
  plus `design_features`, `magnitude_as_reported`, `period` and `trial_or_registration_id`;
  reuse resolves per field through `field_coverage`; a reused record is labelled with what it
  lacked.
- **C2-3 — Unstated defining features must hold support back, not resolve it.** The assigner
  put a youth guarantee with no stated sanction feature under the "without sanctions" variant.
  Ruling 36 says support binds to a finding *and* a specified design. Proposal: the assignment
  step gains a third outcome beside *option* and *ungroupable*: **design feature not stated**,
  which attaches the mention or finding to the parent class only and leaves every variant "not
  yet assessed". Affects `longlist(assign)` in tasks 2 and 3.
- **C2-4 — Source tiers do not sustain claim confidence.** The whole-system approach has 37
  mentioning documents, many of them tier-5 policy syntheses, and 2 independent studies. The
  free-leisure-access option has a tier-5 review and a tier-4 trial mentioning it and no
  magnitude in any inherited record. Ruling 33 (source-quality profile is not "how sure") is
  confirmed by demonstration; nothing to add except that the profile should show the role
  funnel (mention → evaluated → read → independent) rather than tiers alone.

**Clarifies the design.**

- **C2-5 — Duplicate documents double-count inherited findings.** One Cochrane review is two
  snapshots (two backends, two locators). Inherited findings from both count twice. Proposal:
  document identity for counting purposes is DOI or normalised title plus year, resolved at
  `inherit` and at `longlist`, with the duplicate shown as such on Sources. Affects task 1
  (inherit) and task 2.
- **C2-6 — The light profile needs the vetter and a claim-key dedup.** 21 of 125 anchors failed
  verification (17 percent); repeated results across windows turned 5 distinct Walk with Me
  claims into 9 records. Both are solved machinery in the Evidence search (quote vetter,
  `dedup_records`, `claim_key`) and must be wired for the new profile. Affects task 3.
- **C2-7 — `text_basis = full_text` is not evidence of full text.** Five of 21 read-set
  documents carried under 800 characters of parsed text. Ruling 16 ("every claim carries the
  depth of what was read") needs the depth label derived from the parse result, not the fetch
  status. Proposal: a parse-size or parse-success rule sets `text_basis`, or a third value
  (`full_text_failed_parse`) is added. This is an Evidence search fix; affects the Sources tab's
  "read in full" status in task 4.
- **C2-8 — Separate the number from the words.** The light profile recorded "large positive
  effects" as a magnitude. Proposal: `magnitude_as_reported` holds a number with its unit only;
  the source's own characterisation ("a small but robust effect") is a separate field, which
  trust.md already wants for scannability.

**Confirmed as designed.** Comparator arms are mentions, never support. Parent findings did not
leak into either variant's row (rulings 15, 36). A modelled estimate (`e12285a6`) was recorded
with `effect_basis = modelled`. Abstract-only sources produced abstract-level findings only
(ruling 16). The role funnel gives the source-quality profile a truthful shape before any full
text is read (ruling 33).

## What this means for the contracts

- **Task 2 (longlist).** The abstract profile field set stands as drafted, with `role` kept and
  a "design feature not stated" outcome added to assignment (C2-3). Document identity for
  counting (C2-5) is declared with the mention record.
- **Task 3 (assessment).** The light profile is an IOF subset plus four fields (C2-2), with
  `study_identity` at document grain (C2-1), the existing vetter and dedup wired (C2-6), and a
  separate characterisation field (C2-8). "How sure" shows documents read and independent
  studies as two numbers, never one.
- **Evidence search.** Two fixes want their own slice or ADR: the `text_basis` label (C2-7) and
  the cross-task field-grain memo (check 6 F3, confirmed here).
