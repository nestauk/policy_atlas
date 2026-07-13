// In-browser mock: fixture read-models plus a scripted analysis journey.
// Fixture data is invented (clearly plausible, never real evidence) — it exists
// so the demo UI can be rehearsed end-to-end with zero live runs.

import type {
  Artefact, ArtefactSection, Block, ChunkContext, Claim, DemoApi, DemoEvent, DecisionEntry,
  EvidenceRow, Finding, Funnel, Groups, Landscape, Plan, PlanStep, Project, SourceDossier,
} from './types'

const QUESTION = 'What works to reduce childhood obesity in the UK?'
const TITLE = 'Childhood obesity — what works'

// ---------- plan ----------
// Real 017 OrchestrationPlan shape — drafted field-by-field as the chat converges.

const STEPS: PlanStep[] = [
  { label: 'Searching sources', stage: 'acquire', blurb: 'Queries out to academic and policy databases, deep-search rounds included.' },
  { label: 'Screening for relevance', stage: 'screen_abstract', blurb: 'Every title and abstract, read against your question.' },
  { label: 'Sorting by evidence type', stage: 'classify', blurb: 'Trial, review, evaluation — each source labelled.' },
  { label: 'Appraising quality', stage: 'appraise', blurb: 'How much weight each source can bear.' },
  { label: 'Reading in full', stage: 'ingest_full_text', blurb: 'Fetching the documents; paywalls noted, not hidden.' },
  { label: 'Screening the full text', stage: 'screen_full', blurb: 'A second, closer relevance pass now the full text is in.' },
  { label: 'Mapping the landscape', stage: 'characterise', blurb: "What the evidence covers, and where it's thin." },
  { label: 'Shortlisting', stage: 'select', blurb: 'The strongest, most varied set chosen for close reading.' },
  { label: 'Extracting findings', stage: 'extract', blurb: 'Each claim pulled out with its exact quote.' },
  { label: 'Grouping findings', stage: 'group', blurb: 'Findings that answer the same question, together.' },
  { label: 'Writing the evidence base', stage: 'synthesise', blurb: 'Cited, checked, ready to challenge.' },
]

const emptyPlan: Plan = { steps: [], ready: false }

const draftPlan1: Plan = {
  title: TITLE,
  question: QUESTION,
  steps: [],
  ready: false,
}

const draftPlan2: Plan = {
  title: TITLE,
  question: QUESTION,
  scoping_notes: ['UK evidence prioritised', 'All intervention types', 'Schools flagged as a particular interest'],
  screening_criteria: ['Excludes pharmaceutical interventions'],
  backend_scope: 'both',
  scope_constraints: { published_after: '2015-01-01' },
  steps: [],
  ready: false,
}

const readyPlan: Plan = {
  title: TITLE,
  question: QUESTION,
  scoping_notes: draftPlan2.scoping_notes,
  screening_criteria: draftPlan2.screening_criteria,
  backend_scope: 'both',
  scope_constraints: { published_after: '2015-01-01' },
  search_effort: 'deep',
  analysis_depth: 'deep',
  components: ['screen_full', 'characterise', 'select', 'extract', 'group'],
  component_rationale: {
    select: 'Focuses close reading on the strongest, most varied sources within budget.',
  },
  steering_mode: 'moderate',
  assumptions: [
    'UK evidence is prioritised where both UK and international evidence exist',
    'Grey literature includes national and local government publications',
  ],
  expected_artefact_shape: 'A cited evidence base grouped by intervention type, with a coverage snapshot and flagged gaps.',
  time_band: '~30-45 min',
  steps: STEPS,
  ready: true,
}

const chatTurns: { reply: string; plan: Plan; suggestions?: string[] }[] = [
  {
    reply:
      'I can build that evidence base. One scoping question first — should I look at all intervention types (schools, fiscal measures, food environment, family programmes), or a particular area? And should UK evidence lead, with international brought in where it’s stronger?',
    plan: draftPlan1,
    suggestions: ['All intervention types, UK-led', 'Focus on schools only'],
  },
  {
    reply:
      'Noted — UK evidence leads, all intervention types, schools flagged as your priority. How thorough should I be? Standard gives a full write-up in around fifteen minutes; deep is a systematic-style sweep, closer to forty-five — you’ll see everything I keep and everything I set aside, with reasons.',
    plan: draftPlan2,
  },
  {
    reply:
      'Deep it is. The plan is on the right — search, screen, quality-check, read the strongest in full, then write it up with every claim traced to its source. I’ll check in when something needs your judgement. Start when you’re ready.',
    plan: readyPlan,
  },
]

// ---------- artefact (claims are verbatim spans of the prose) ----------

function block(id: string, prose: string, claimSpecs: [string, Partial<Claim>][]): Block {
  const claims: Claim[] = claimSpecs.map(([text, extra], i) => {
    const start = prose.indexOf(text)
    if (start < 0) throw new Error(`mock claim not in prose: ${text.slice(0, 40)}`)
    return {
      claim_id: `${id}-c${i}`, claim_type: 'citation', text,
      span: { start, end: start + text.length }, citations: [], ...extra,
    }
  })
  return { block_id: id, prose, claims }
}

const cite = (n: number, source_title: string, quote: string, tier = 'tier_1'): Claim['citations'][0] => ({
  n, source_title, quote, verified: tier === 'tier_1', grounding_tier: tier,
  appraisal_label: n <= 2 ? 'Strong' : 'Moderate', chunk_id: `chunk-${n}`,
})

const b1 = block(
  'b1',
  'The strongest and most consistent UK evidence concerns fiscal measures. The Soft Drinks Industry Levy is associated with a substantial fall in the sugar content of soft drinks purchased by households, driven largely by reformulation rather than reduced purchasing. Evidence linking the levy directly to weight outcomes is thinner but emerging: one quasi-experimental analysis reports lower obesity prevalence among year-6 girls, concentrated in the most deprived areas, with no equivalent effect detected in boys.\n\nEvaluations of in-store promotion restrictions are more recent and show early reductions in sugar purchased, though displacement to untargeted products remains under-studied. No study yet links promotion-placement restrictions to weight outcomes; purchasing data only.',
  [
    ['The Soft Drinks Industry Levy is associated with a substantial fall in the sugar content of soft drinks purchased by households, driven largely by reformulation rather than reduced purchasing.', {
      citations: [
        cite(1, 'Household purchasing of soft drinks after the UK Soft Drinks Industry Levy: controlled interrupted time series', 'The volume of sugar purchased in soft drinks fell by 29.5 g per household per week relative to the counterfactual, while total soft-drink volume was unchanged, consistent with reformulation as the dominant mechanism.'),
        cite(2, 'Sugar reduction programme: industry progress 2015–2020 (national evaluation)', 'Average sugar content of levy-eligible drinks fell by 43.7% between 2015 and 2020.'),
      ],
    }],
    ['one quasi-experimental analysis reports lower obesity prevalence among year-6 girls, concentrated in the most deprived areas, with no equivalent effect detected in boys', {
      citations: [cite(3, 'Changes in obesity prevalence among 10–11-year-olds after the soft drinks levy: interrupted time series by deprivation quintile', 'We estimate a 1.6 percentage-point reduction in obesity prevalence among year-6 girls in the most deprived quintile, with no measurable change among boys.')],
    }],
    ['No study yet links promotion-placement restrictions to weight outcomes; purchasing data only.', { claim_type: 'gap', citations: [] }],
  ],
)

const b2 = block(
  'b2',
  'School-based evidence is mixed, and the contrast between outcome types matters. Programmes combining curriculum change with family engagement report improvements in dietary intake and activity, but the two largest UK cluster-randomised trials found no significant effect on BMI at 24 months. Review-level evidence supports behavioural benefits of school programmes while weight effects are small and often fade.\n\nReviewers consistently note that school-only interventions may be too weak a dose against an obesogenic wider environment — a reading consistent with the stronger fiscal-measure results above. Little UK evidence covers secondary-school interventions; the trial base is concentrated in primary settings.',
  [
    ['the two largest UK cluster-randomised trials found no significant effect on BMI at 24 months', {
      citations: [
        cite(4, 'The WAVES cluster-randomised controlled trial of a multi-component school intervention', 'No statistically significant difference in BMI z-score was observed between intervention and control arms at 24 months (−0.02, 95% CI −0.09 to 0.05).'),
        cite(5, 'Active-mile initiatives in English primary schools: pragmatic evaluation', 'We found no detectable effect on weight status at follow-up, despite improvements in measured activity.'),
      ],
    }],
    ['Review-level evidence supports behavioural benefits of school programmes while weight effects are small and often fade.', {
      citations: [cite(6, 'School-based interventions to prevent childhood obesity: umbrella review of systematic reviews 2010–2023', 'Across 24 reviews, effects on dietary and activity behaviours were consistent; effects on adiposity were small, heterogeneous, and attenuated at longer follow-up.', 'tier_2')],
    }],
    ['Little UK evidence covers secondary-school interventions; the trial base is concentrated in primary settings.', { claim_type: 'gap', citations: [] }],
  ],
)

const b3 = block(
  'b3',
  'Family-based weight-management programmes show modest short-term effects on BMI when families complete them, but attrition is high and reach into the most affected communities is poor. Whole-systems community approaches — where local authorities coordinate action across food, planning and schools — report promising early signals on prevalence in a small number of evaluated sites, though evaluations are young and rely on routine measurement data.\n\nThe early-years evidence base is the thinnest of the four themes: UK-specific studies are few, and the strongest signals come from international trials of infant-feeding support whose transferability to UK settings is untested.',
  [
    ['Family-based weight-management programmes show modest short-term effects on BMI when families complete them, but attrition is high', {
      citations: [cite(7, 'Family-based weight management referrals in three English regions: service evaluation', 'Among completers, mean BMI z-score fell by 0.13 at six months; 46% of referred families did not complete the programme.')],
    }],
    ['Whole-systems community approaches — where local authorities coordinate action across food, planning and schools — report promising early signals on prevalence in a small number of evaluated sites', {
      citations: [cite(8, 'Whole-systems obesity programmes in English local authorities: three-year outcome evaluation', 'Participating authorities recorded a small relative reduction in year-6 obesity prevalence against matched comparators over three years.', 'tier_2')],
    }],
    ['The early-years evidence base is the thinnest of the four themes: UK-specific studies are few, and the strongest signals come from international trials of infant-feeding support whose transferability to UK settings is untested.', { claim_type: 'gap', citations: [] }],
  ],
)

const keyFindings = block(
  'kf1',
  'The clearest evidence favours measures that change the food environment, especially the Soft Drinks Industry Levy and early promotion restrictions. School programmes improve some behaviours but have not shown reliable BMI effects in the largest UK trials. The main gap is still direct weight-outcome evidence for newer food-environment restrictions and early-years approaches.',
  [
    ['The clearest evidence favours measures that change the food environment, especially the Soft Drinks Industry Levy and early promotion restrictions.', {
      citations: [
        cite(1, 'Household purchasing of soft drinks after the UK Soft Drinks Industry Levy: controlled interrupted time series', 'The volume of sugar purchased in soft drinks fell by 29.5 g per household per week relative to the counterfactual, while total soft-drink volume was unchanged, consistent with reformulation as the dominant mechanism.'),
        cite(2, 'Sugar reduction programme: industry progress 2015–2020 (national evaluation)', 'Average sugar content of levy-eligible drinks fell by 43.7% between 2015 and 2020.'),
      ],
    }],
    ['School programmes improve some behaviours but have not shown reliable BMI effects in the largest UK trials.', {
      citations: [
        cite(4, 'The WAVES cluster-randomised controlled trial of a multi-component school intervention', 'No statistically significant difference in BMI z-score was observed between intervention and control arms at 24 months (−0.02, 95% CI −0.09 to 0.05).'),
        cite(6, 'School-based interventions to prevent childhood obesity: umbrella review of systematic reviews 2010–2023', 'Across 24 reviews, effects on dietary and activity behaviours were consistent; effects on adiposity were small, heterogeneous, and attenuated at longer follow-up.', 'tier_2'),
      ],
    }],
    ['The main gap is still direct weight-outcome evidence for newer food-environment restrictions and early-years approaches.', { claim_type: 'gap', citations: [] }],
  ],
)

const conclusion = block(
  'conclusion',
  'Overall, the evidence points more strongly to population-level food-environment measures than to school-only programmes for reducing childhood obesity in the UK. The best-supported measures reduce sugar purchased or supplied, while evidence on actual weight outcomes is narrower and uneven. For a policy reader, that means the base is useful for choosing where to look harder, but it does not yet support a simple ranking of every intervention type.',
  [
    ['the evidence points more strongly to population-level food-environment measures than to school-only programmes for reducing childhood obesity in the UK', {
      citations: [
        cite(1, 'Household purchasing of soft drinks after the UK Soft Drinks Industry Levy: controlled interrupted time series', 'The volume of sugar purchased in soft drinks fell by 29.5 g per household per week relative to the counterfactual, while total soft-drink volume was unchanged, consistent with reformulation as the dominant mechanism.'),
        cite(4, 'The WAVES cluster-randomised controlled trial of a multi-component school intervention', 'No statistically significant difference in BMI z-score was observed between intervention and control arms at 24 months (−0.02, 95% CI −0.09 to 0.05).'),
      ],
    }],
    ['it does not yet support a simple ranking of every intervention type', { claim_type: 'reasoning', citations: [] }],
  ],
)

const mockArtefact: Artefact = {
  title: 'Evidence base: reducing childhood obesity in the UK',
  question: QUESTION,
  coverage_snapshot: {
    source_count: 214,
    study_types: { 'Policy guidance': 23, 'Expert opinion': 20, 'Systematic reviews': 9, Trials: 14, Other: 1 },
    year_range: { min: 2015, max: 2025 },
    included: 67,
    screened_out: 147,
  },
  key_findings: { title: 'Key findings', role: 'key_findings', blocks: [keyFindings] },
  sections: [
    { title: 'Fiscal and food-environment measures', blocks: [b1] },
    { title: 'School-based programmes', blocks: [b2] },
    { title: 'Family, community and early-years approaches', blocks: [b3] },
  ],
  conclusion: { title: 'Conclusions', role: 'conclusions', blocks: [conclusion] },
  references: [
    { n: 1, title: 'Household purchasing of soft drinks after the UK Soft Drinks Industry Levy: controlled interrupted time series', year: 2021, venue: 'BMJ Public Health', url: 'https://doi.org/10.0000/example1' },
    { n: 2, title: 'Sugar reduction programme: industry progress 2015–2020 (national evaluation)', year: 2022, venue: 'Office for Health Improvement', url: null },
    { n: 3, title: 'Changes in obesity prevalence among 10–11-year-olds after the soft drinks levy: interrupted time series by deprivation quintile', year: 2023, venue: 'PLOS Medicine', url: 'https://doi.org/10.0000/example3' },
    { n: 4, title: 'The WAVES cluster-randomised controlled trial of a multi-component school intervention', year: 2018, venue: 'BMJ', url: null },
    { n: 5, title: 'Active-mile initiatives in English primary schools: pragmatic evaluation', year: 2020, venue: 'International Journal of Behavioral Nutrition', url: null },
    { n: 6, title: 'School-based interventions to prevent childhood obesity: umbrella review of systematic reviews 2010–2023', year: 2024, venue: 'Obesity Reviews', url: null },
    { n: 7, title: 'Family-based weight management referrals in three English regions: service evaluation', year: 2022, venue: 'Journal of Public Health', url: null },
    { n: 8, title: 'Whole-systems obesity programmes in English local authorities: three-year outcome evaluation', year: 2024, venue: 'The Lancet Public Health', url: null },
  ],
}

const artefactSections = (): ArtefactSection[] =>
  [mockArtefact.key_findings, ...mockArtefact.sections, mockArtefact.conclusion]
    .filter((section): section is ArtefactSection => section != null)

// ---------- evidence table ----------

const included: [string, number, string, boolean][] = mockArtefact.references.map(
  (r) => [r.title, r.year ?? 2021, r.venue, true] as [string, number, string, boolean],
)

const PAD_TOPICS = [
  'Sugar-sweetened beverage consumption', 'After-school activity provision', 'Food marketing exposure',
  'Active travel to school', 'Breakfast club provision', 'Takeaway outlet density', 'Screen time and snacking',
  'Family cooking skills', 'Vending machine policies', 'Playground redesign', 'Supermarket layout interventions',
  'Calorie labelling in cafés', 'Sleep duration and weight', 'Sports club participation',
]
const PAD_KINDS: [string, string, string][] = [
  ['cohort evidence from a UK birth study', 'International Journal of Obesity', 'Cohort study'],
  ['cross-sectional analysis of national survey data', 'BMJ Open', 'Survey'],
  ['qualitative study with parents and teachers', 'Sociology of Health & Illness', 'Qualitative'],
  ['systematic scoping review', 'Obesity Reviews', 'Review'],
  ['local authority evaluation report', 'Local Government Association', 'Evaluation'],
]

function padRows(count: number, status: EvidenceRow['status'], reason: string, base: number): EvidenceRow[] {
  return Array.from({ length: count }, (_, i) => {
    const topic = PAD_TOPICS[i % PAD_TOPICS.length]
    const [kind, venue, type] = PAD_KINDS[i % PAD_KINDS.length]
    return {
      source_id: `pad-${status}-${i}`,
      title: `${topic} and childhood obesity: ${kind}`,
      year: 2015 + (i % 10), venue,
      origin: i % 4 === 3 ? 'Overton' : 'OpenAlex',
      status, status_reason: reason, evidence_type: type,
      appraisal_tier: status === 'screened_out' ? null : String(2 + (i % 2)),
      appraisal_label: status === 'screened_out' ? null : i % 2 ? 'Moderate' : 'Limited',
      cited: false, url: null,
      screen_confidence: 0.55 + ((i * 7) % 40) / 100,
      screen_basis: 'title_abstract', screen_stage: base === 2 ? 2 : 1,
    }
  })
}

const citedRows: EvidenceRow[] = included.map(([title, year, venue], i) => ({
  source_id: `src-${i + 1}`, title, year, venue,
  origin: venue.includes('Office') || venue.includes('Government') ? 'Overton' : 'OpenAlex',
  status: 'cited', status_reason: null,
  evidence_type: i < 3 ? 'Quasi-experimental' : i < 6 ? 'RCT / review' : 'Evaluation',
  appraisal_tier: i < 4 ? '4' : '3',
  appraisal_label: i < 4 ? 'Strong' : 'Moderate',
  cited: true, url: mockArtefact.references[i].url,
  screen_confidence: 0.9 + (i % 8) / 100, screen_basis: 'title_abstract', screen_stage: 2,
}))

const unavailableRows = padRows(3, 'unavailable', 'paywall', 1)
const mockEvidence: EvidenceRow[] = [
  ...citedRows,
  ...padRows(16, 'findings_extracted', 'Findings extracted from full text', 2),
  ...unavailableRows,
  ...padRows(40, 'not_selected', 'Relevant but not shortlisted under the plan’s depth budget', 1),
  ...padRows(147, 'screened_out', 'Not directly relevant to the question on closer reading', 1),
]

// ---------- findings ----------

const g = (i: string, o: string) => ({ intervention: i, outcome: o })
const F = (
  id: number, intervention: string, outcome: string, direction: Finding['direction'],
  design: string, stats: Record<string, unknown>, quote: string, srcIdx: number,
  groups: Record<string, string>,
): Finding => ({
  finding_id: `f-${id}`, source_id: `src-${srcIdx}`, intervention, outcome, direction,
  population: 'Children 4–11, England', comparator: null, study_design: design,
  estimate_level: design.includes('review') ? 'pooled' : 'study',
  causality: design.includes('randomised') ? 'attributable' : design.includes('quasi') ? 'plausibly_causal' : 'associational',
  // 020 extraction schema v2 fields (effect_basis vocabulary: observed | modelled)
  effect_basis: design.includes('model') ? 'modelled' : 'observed',
  study_geography: 'United Kingdom',
  is_primary: id % 3 === 0, statistics: stats, stratum_qualifiers: id % 4 === 0 ? [{ type: 'sex', value: 'girls' }] : [],
  quote, quote_verified: id % 7 !== 0, source_title: mockArtefact.references[srcIdx - 1].title,
  groups,
})

const mockFindings: Finding[] = [
  F(1, 'Soft Drinks Industry Levy', 'Sugar purchased from soft drinks', 'decrease', 'quasi-experimental (interrupted time series)',
    { effect_size: '−29.5 g/household/week', ci: '−45.1 to −13.9', p_value: '<0.001', n: 22183 },
    'The volume of sugar purchased in soft drinks fell by 29.5 g per household per week relative to the counterfactual.', 1,
    g('Sugar levy / fiscal', 'Purchasing behaviour')),
  F(2, 'Soft Drinks Industry Levy', 'Obesity prevalence (year-6 girls)', 'decrease', 'quasi-experimental (interrupted time series)',
    { effect_size: '−1.6 pp', ci: '−2.8 to −0.4', p_value: '0.009' },
    'We estimate a 1.6 percentage-point reduction in obesity prevalence among year-6 girls in the most deprived quintile.', 3,
    g('Sugar levy / fiscal', 'BMI / weight status')),
  F(3, 'Multi-component school programme (WAVES)', 'BMI z-score at 24 months', 'no_effect', 'cluster-randomised controlled trial',
    { effect_size: '−0.02 z', ci: '−0.09 to 0.05', n: 1467 },
    'No statistically significant difference in BMI z-score was observed between intervention and control arms at 24 months.', 4,
    g('School programmes', 'BMI / weight status')),
  F(4, 'Active-mile initiative', 'Physical activity (MVPA minutes)', 'increase', 'pragmatic evaluation',
    { effect_size: '+5.1 min/day', p_value: '0.03', n: 3218 },
    'Daily moderate-to-vigorous activity increased by just over five minutes on average.', 5,
    g('School programmes', 'Physical activity')),
  F(5, 'Active-mile initiative', 'Weight status', 'no_effect', 'pragmatic evaluation',
    {}, 'We found no detectable effect on weight status at follow-up.', 5,
    g('School programmes', 'BMI / weight status')),
  F(6, 'School-based interventions (pooled)', 'Dietary and activity behaviours', 'increase', 'umbrella review of systematic reviews',
    { k: 24, i2: '61%' },
    'Across 24 reviews, effects on dietary and activity behaviours were consistent.', 6,
    g('School programmes', 'Dietary intake')),
  F(7, 'School-based interventions (pooled)', 'Adiposity at longer follow-up', 'mixed', 'umbrella review of systematic reviews',
    { k: 24 }, 'Effects on adiposity were small, heterogeneous, and attenuated at longer follow-up.', 6,
    g('School programmes', 'BMI / weight status')),
  F(8, 'Family weight-management referral programme', 'BMI z-score (completers)', 'decrease', 'service evaluation',
    { effect_size: '−0.13 z', n: 4102 },
    'Among completers, mean BMI z-score fell by 0.13 at six months.', 7,
    g('Family programmes', 'BMI / weight status')),
  F(9, 'Family weight-management referral programme', 'Programme completion', 'decrease', 'service evaluation',
    { effect_size: '46% attrition' }, '46% of referred families did not complete the programme.', 7,
    g('Family programmes', 'Reach & completion')),
  F(10, 'Whole-systems local authority programme', 'Year-6 obesity prevalence', 'decrease', 'matched-comparator evaluation',
    { effect_size: '−0.9 pp', ci: '−1.7 to −0.1' },
    'Participating authorities recorded a small relative reduction in year-6 obesity prevalence against matched comparators.', 8,
    g('Whole-systems approaches', 'BMI / weight status')),
  F(11, 'In-store promotion restrictions (HFSS placement)', 'Sugar purchased', 'decrease', 'quasi-experimental',
    { effect_size: '−2.1%', p_value: '0.04' },
    'Purchases of targeted products fell modestly in the first year of the placement restrictions.', 2,
    g('Marketing restrictions', 'Purchasing behaviour')),
  F(12, 'Sugar reduction programme (voluntary reformulation)', 'Average sugar content of drinks', 'decrease', 'national evaluation',
    { effect_size: '−43.7%' }, 'Average sugar content of levy-eligible drinks fell by 43.7% between 2015 and 2020.', 2,
    g('Sugar levy / fiscal', 'Dietary intake')),
  F(13, 'Breakfast club provision', 'Dietary quality', 'increase', 'cohort evidence',
    {}, 'Attendance was associated with modestly better dietary quality scores.', 6,
    g('School programmes', 'Dietary intake')),
  F(14, 'Infant-feeding support (international trials)', 'Weight gain trajectory', 'unclear', 'pooled analysis of trials',
    { k: 6 }, 'Pooled effects were imprecise and inconsistent across settings.', 6,
    g('Early years', 'BMI / weight status')),
]

// ---------- landscape / groups / coverage / decisions ----------

const mockLandscape: Landscape = {
  evidence_types: {
    'Systematic reviews': 9, Trials: 14, 'Quasi-experimental': 11,
    'Cohort study': 12, 'Policy evaluation': 13, 'Guidance / expert': 8,
  },
  years: Object.fromEntries(
    Array.from({ length: 11 }, (_, i) => [String(2015 + i), [3, 4, 5, 6, 7, 8, 9, 9, 7, 6, 3][i]]),
  ),
  themes: [
    { name: 'School-based programmes', size: 18, description: 'Curriculum, active-mile and school-food interventions in primary settings.' },
    { name: 'Fiscal & food environment', size: 18, description: 'The soft drinks levy, promotion restrictions and reformulation programmes.' },
    { name: 'Family & community', size: 13, description: 'Family weight-management referrals and whole-systems community approaches.' },
    { name: 'Early years', size: 8, description: 'Interventions before age five: infant feeding, nursery food standards.' },
  ],
  publication_countries: {
    'United Kingdom': 38, 'United States': 9, 'International bodies': 7,
    Netherlands: 4, Australia: 3, Sweden: 2, Ireland: 2, Canada: 2,
  },
}

const mockGroups: Groups = {
  facets: [
    {
      facet: 'intervention',
      groups: [
        { label: 'School programmes', description: 'Curriculum, activity and school-food interventions', size: 9 },
        { label: 'Sugar levy / fiscal', description: 'Price-based measures on sugary products', size: 8 },
        { label: 'Family programmes', description: 'Referral programmes involving the family', size: 6 },
        { label: 'Marketing restrictions', description: 'Limits on advertising and placement', size: 5 },
        { label: 'Whole-systems approaches', description: 'Local multi-agency programmes', size: 5 },
        { label: 'Reformulation', description: 'Voluntary or mandated recipe change', size: 4 },
        { label: 'Early years', description: 'Interventions before age five', size: 3 },
        { label: 'Breakfast provision', description: 'School breakfast clubs', size: 3 },
        { label: 'Active travel', description: 'Walking and cycling to school', size: 2 },
        { label: 'Calorie labelling', description: 'Menu and shelf labelling', size: 2 },
      ],
      ungrouped: 3,
    },
    {
      facet: 'outcome',
      groups: [
        { label: 'BMI / weight status', description: 'Direct anthropometric outcomes', size: 21 },
        { label: 'Dietary intake', description: 'Sugar, calorie or nutrient consumption', size: 14 },
        { label: 'Physical activity', description: 'Activity levels and fitness', size: 9 },
        { label: 'Purchasing behaviour', description: 'Sales and household purchase data', size: 8 },
        { label: 'Reach & completion', description: 'Programme uptake and attrition', size: 4 },
      ],
      ungrouped: 6,
    },
  ],
}

const finalFunnel: Funnel = {
  found: 214, relevant: 67, screened_out: 147, quality_checked: 67,
  read_in_full: 41, selected: 24, findings: 58, cited: 8,
}

const mockCoverage = {
  backends: ['openalex', 'overton'],
  stop_condition: 'target_reached',
  summary: 'Searching stopped because it found enough confidently relevant sources. Coverage judged adequate.',
  adequacy: 'adequate' as const,
}

const T0 = Date.parse('2026-07-08T09:12:00Z')
const at = (m: number) => new Date(T0 + m * 60_000).toISOString()
const mockDecisions: DecisionEntry[] = [
  { at: at(0), kind: 'component.completed', text: 'Search completed — 214 found', detail: { 'New sources found': 214, 'Results returned by the databases': 246, 'Queries run · OpenAlex': 12, 'Queries run · Overton': 4, 'How the search ended': 'Stopped: found enough confidently relevant sources' } },
  { at: at(1), kind: 'searches', text: 'Search terms used (16 queries)', detail: { 'Query 1': 'Openalex: childhood obesity intervention United Kingdom', 'Query 2': 'Openalex: school-based obesity prevention randomised trial', 'Query 3': 'Openalex: sugar tax soft drinks levy child weight', 'Query 4': 'Overton: policies to reduce childhood obesity UK', 'Query 5': 'Overton: whole systems approach obesity local authority' } },
  { at: at(2), kind: 'component.completed', text: 'Screening completed — 67 relevant · 147 screened out', detail: { 'Judged relevant': 67, 'Screened out': 147, 'Could not be screened': 0 } },
  { at: at(3), kind: 'checkin', text: 'Paused to check in: The base looks strong on fiscal measures and school programmes, thin on early-years interventions — 8 sources so far.', detail: {} },
  { at: at(4), kind: 'component.completed', text: 'Evidence types assigned — 67 labelled', detail: { 'Sources labelled by evidence type': 67 } },
  { at: at(5), kind: 'component.completed', text: 'Quality appraisal completed', detail: { 'Sources quality-appraised': 67 } },
  { at: at(7), kind: 'component.completed', text: 'Full documents read — 41 read · 3 unavailable', detail: { 'Read in full': 41, 'Could not be fetched': 3 } },
  { at: at(8), kind: 'component.completed', text: 'Landscape mapped — 4 themes', detail: { 'Themes identified': 4 } },
  { at: at(9), kind: 'component.completed', text: 'Close-reading shortlist chosen — 24 selected', detail: { 'Shortlisted for close reading': 24 } },
  { at: at(11), kind: 'component.completed', text: 'Findings extracted — 58 findings', detail: { 'Findings extracted': 58, 'Documents with findings': 20, 'Quotes that could not be verified': 4 } },
  { at: at(12), kind: 'component.completed', text: 'Findings grouped — 15 groups', detail: { 'Groups formed': 15 } },
  { at: at(13), kind: 'component.completed', text: 'Evidence base written — 3 sections · 8 cited sources', detail: { 'Sections written': 3 } },
]

// ---------- dossiers + chunk context ----------

function dossier(row: EvidenceRow): SourceDossier {
  const academic = row.origin === 'OpenAlex'
  return {
    ...row,
    abstract:
      'We evaluated the intervention using routinely collected data across participating settings, comparing outcomes before and after implementation against a matched counterfactual. Effects were concentrated where exposure was highest; we discuss mechanisms and transferability.',
    doi: row.url, language: 'en',
    publisher_org: academic ? row.venue : 'UK public body',
    record_type: academic ? 'journal-article' : 'policy document',
    cited_by_count: academic ? 120 + (row.title.length % 90) : null,
    fwci: academic ? 1.8 : null,
    tags: [
      { tag: 'Childhood obesity', tag_type: 'topic_theme', asserted_by: academic ? 'openalex' : 'overton' },
      { tag: 'Fiscal policy', tag_type: 'topic_theme', asserted_by: 'characterise' },
      { tag: row.evidence_type ?? 'evaluation', tag_type: 'methodological_structural', asserted_by: 'classify' },
      { tag: 'school-based', tag_type: 'methodological_structural', asserted_by: 'classify' },
    ],
    cited_claims: row.cited
      ? artefactSections()
          .flatMap((s) => s.blocks.flatMap((b) => b.claims.map((c) => ({ c, s }))))
          .filter(({ c }) => c.citations.some((ci) => ci.source_title === row.title))
          .map(({ c, s }) => ({
            claim: c.text,
            quote: c.citations.find((ci) => ci.source_title === row.title)?.quote ?? '',
            verified: true, section: s.title,
          }))
      : [],
  }
}

function chunkContext(chunkId: string): ChunkContext | null {
  const quote = artefactSections()
    .flatMap((s) => s.blocks.flatMap((b) => b.claims.flatMap((c) => c.citations)))
    .find((c) => c.chunk_id === chunkId)
  if (!quote) return null
  const ref = mockArtefact.references.find((r) => r.title === quote.source_title)
  return {
    previous:
      'Data were drawn from a nationally representative panel covering the periods before and after the measure came into force. Models adjusted for pre-existing trends, seasonality and wider shifts in the market.',
    content: `Turning to the primary outcome, ${quote.quote} The pattern held across income groups, though the absolute change was larger in households with children.`,
    next: 'Sensitivity analyses using alternative counterfactuals produced consistent estimates. We discuss limitations, including the reliance on purchase rather than consumption data.',
    source_title: ref?.title ?? quote.source_title,
    year: ref?.year ?? null, venue: ref?.venue ?? '',
  }
}

// ---------- scripted journey ----------

interface Step { delay: number; event?: DemoEvent; funnel?: Partial<Funnel>; waitForCheckin?: string }

const p = (stage: string, kind: string, rest: Record<string, unknown>): DemoEvent =>
  ({ type: 'stage.progress', data: { stage, kind, ...rest } }) as DemoEvent
const started = (stage: string, label: string, blurb: string): DemoEvent =>
  ({ type: 'stage.started', data: { stage, stage_label: label, stage_blurb: blurb } })
const completed = (stage: string, label: string, summary: Record<string, number>): DemoEvent =>
  ({ type: 'stage.completed', data: { stage, stage_label: label, summary } })
const say = (text: string): DemoEvent => ({ type: 'narration', data: { text } })

const CHECKIN_ID = 'checkin-deepen-selection'

function script(): Step[] {
  return [
    { delay: 400, event: { type: 'analysis.started', data: {} } },
    { delay: 500, event: say('Searching. Queries are out to OpenAlex for the academic literature and Overton for policy documents.') },
    { delay: 600, event: started('acquire', 'Searching sources', 'Queries out to academic and policy databases') },
    { delay: 800, event: p('acquire', 'search_query', { backend: 'openalex', query: 'childhood obesity intervention United Kingdom' }) },
    { delay: 900, event: p('acquire', 'search_query', { backend: 'overton', query: 'policies to reduce childhood obesity UK' }) },
    { delay: 800, event: p('acquire', 'results', { backend: 'openalex', count: 88 }) },
    { delay: 900, event: p('acquire', 'search_query', { backend: 'openalex', query: 'sugar tax soft drinks levy child weight' }) },
    { delay: 700, event: p('acquire', 'results', { backend: 'overton', count: 41 }) },
    { delay: 800, event: p('acquire', 'search_query', { backend: 'overton', query: 'whole systems approach obesity local authority' }) },
    { delay: 700, event: p('acquire', 'results', { backend: 'openalex', count: 52 }) },
    { delay: 800, event: p('acquire', 'results', { backend: 'overton', count: 33 }) },
    { delay: 600, event: completed('acquire', 'Searching sources', { found: 214, seconds: 34 }), funnel: { found: 214 } },
    { delay: 700, event: say('214 sources back — 140 academic papers, 74 policy documents. Screening now: every title and abstract read against your question.') },
    { delay: 700, event: started('screen_abstract', 'Screening for relevance', 'Every title and abstract, against your question') },
    ...[40, 87, 139, 188, 214].map((_n, i) => ({
      delay: 1300,
      event: p('screen_abstract', 'tick', { note: 'Screening sources against your question' }),
      funnel: { relevant: [12, 25, 38, 51, 58][i] } as Partial<Funnel>,
    })),
    { delay: 900, event: p('screen_abstract', 'round', { round: 2, new_relevant: 9, total_relevant: 67 }) },
    { delay: 700, event: say('First pass kept 58. I reformulated my queries using what those taught me and followed their citation trails — 9 more, 67 in all. 147 screened out, each with a reason you can inspect.') },
    { delay: 800, event: completed('screen_abstract', 'Screening for relevance', { relevant: 67, screened_out: 147, seconds: 41 }), funnel: { relevant: 67, screened_out: 147 } },
    { delay: 600, event: started('classify', 'Sorting by evidence type', 'Trial, review, evaluation — each source labelled') },
    { delay: 2400, event: completed('classify', 'Sorting by evidence type', { classified: 67, seconds: 22 }), funnel: { quality_checked: 67 } },
    { delay: 500, event: started('appraise', 'Appraising quality', 'How much weight each source can bear') },
    { delay: 1600, event: completed('appraise', 'Appraising quality', { appraised: 67, seconds: 9 }) },
    { delay: 500, event: started('ingest_full_text', 'Reading in full', 'Fetching the documents; paywalls noted, not hidden') },
    { delay: 900, event: p('ingest_full_text', 'tick', { note: 'Read a document in full' }) },
    { delay: 900, event: p('ingest_full_text', 'tick', { note: 'Read a document in full' }) },
    { delay: 700, event: p('ingest_full_text', 'tick', { note: "A document couldn't be fetched — recorded" }) },
    { delay: 900, event: p('ingest_full_text', 'tick', { note: 'Read a document in full' }) },
    { delay: 700, event: say('Full documents in for 41 of the 67 — three paywalled or dead links, each noted in the sources table, not glossed over.') },
    { delay: 600, event: completed('ingest_full_text', 'Reading in full', { ingested: 41, failed: 3, seconds: 75 }), funnel: { read_in_full: 41 } },
    { delay: 600, event: started('screen_full', 'Screening the full text', 'A second, closer relevance pass now the full text is in') },
    { delay: 1400, event: completed('screen_full', 'Screening the full text', { relevant: 67, seconds: 14 }) },
    { delay: 600, event: started('characterise', 'Mapping the landscape', "What the evidence covers, and where it's thin") },
    { delay: 2600, event: completed('characterise', 'Mapping the landscape', { themes: 4, seconds: 27 }) },
    { delay: 600, event: say('The landscape is mapped: strongest around fiscal measures, school programmes well covered, early-years thin as flagged. Now shortlisting for close reading.') },
    { delay: 600, event: started('select', 'Shortlisting', 'The strongest, most varied set for close reading') },
    { delay: 1400, event: completed('select', 'Shortlisting', { selected: 24, seconds: 19 }), funnel: { selected: 24 } },
    {
      delay: 1000,
      event: {
        type: 'checkin',
        data: {
          checkin_id: CHECKIN_ID,
          kind: 'steer_point',
          text: 'The shortlist left out a fairly large cluster of sources on food-environment interventions. I can deepen on that cluster, widen toward the strongest evidence or the most relevant matches, adjust the shortlist budget, or continue as planned.',
          render: 'select: succeeded | wall_clock=36.9s | counts: selected=10',
          options: [
            { id: 'continue', label: 'Continue as planned', description: 'Keep the current shortlist and carry on.', requires_user_input: false },
            { id: 'deepen_clusters', label: 'Deepen specific clusters', description: 'Re-run the shortlist including more from clusters or documents you name.', requires_user_input: true },
            { id: 'strongest_evidence', label: 'Deepen on the strongest evidence', description: 'Widen the shortlist toward the highest-appraised sources.', requires_user_input: false },
            { id: 'most_relevant', label: 'Deepen on the most relevant', description: 'Widen the shortlist toward the most relevant matches.', requires_user_input: false },
            { id: 'adjust_budget', label: 'Adjust the shortlist budget', description: 'Change how many sources go forward for close reading.', requires_user_input: true },
            { id: 'abort', label: 'Stop here', description: 'End the run now; keep everything completed so far.', requires_user_input: false },
          ],
          triggers: [{ trigger: 'excluded_large_stratum', detail: { facet: 'intervention', group: 'food environment', excluded: 14 } }],
        },
      },
    },
    { delay: 0, waitForCheckin: CHECKIN_ID },
    { delay: 600, event: say('Recorded. Carrying on with the shortlist as it stands.') },
    { delay: 500, event: started('extract', 'Extracting findings', 'Each claim pulled out with its exact quote') },
    { delay: 1600, event: p('extract', 'tick', { note: 'Reading closely and pulling out findings' }) },
    { delay: 1600, event: p('extract', 'tick', { note: 'Reading closely and pulling out findings' }) },
    { delay: 1400, event: completed('extract', 'Extracting findings', { total: 58, seconds: 46 }), funnel: { findings: 58 } },
    { delay: 500, event: started('group', 'Grouping findings', 'Findings that answer the same question, together') },
    { delay: 1800, event: completed('group', 'Grouping findings', { groups: 15, seconds: 24 }) },
    { delay: 500, event: started('synthesise', 'Writing the evidence base', 'Cited, checked, ready to challenge') },
    { delay: 3000, event: p('synthesise', 'tick', { note: 'Drafting the next section' }) },
    { delay: 2600, event: completed('synthesise', 'Writing the evidence base', { section_count: 3, seconds: 39 }), funnel: { cited: 8 } },
    { delay: 700, event: say('Done. 67 sources included, 8 cited in the write-up. The evidence base is ready to read — and to challenge: every claim opens to its source.') },
    {
      delay: 400,
      event: {
        type: 'analysis.completed',
        data: {
          status: 'succeeded',
          collation: 'Flagged event collation\nfailures: none\nretries: none\nskips: none\nauto-resolutions: none',
        },
      },
    },
  ]
}

// completed projects replay the full story: planning turns, then the whole run
function completeBacklog(): DemoEvent[] {
  const events: DemoEvent[] = []
  const userTurns = [
    'What works to reduce childhood obesity?',
    'All intervention types, UK evidence should lead, schools are a particular interest.',
    'Deep, please.',
  ]
  userTurns.forEach((text, i) => {
    events.push({ type: 'user.message', data: { text } })
    events.push({ type: 'narration', data: { text: chatTurns[i].reply, suggestions: chatTurns[i].suggestions } })
  })
  events.push({ type: 'plan.updated', data: { plan: readyPlan } })
  for (const step of script()) {
    if (!step.event) continue
    events.push(step.event)
    if (step.event.type === 'checkin') {
      events.push({ type: 'checkin.resolved', data: { checkin_id: CHECKIN_ID, reply: 'continue' } })
    }
  }
  return events
}

// ---------- mock state + api ----------

interface MockState {
  project: Project
  plan: Plan
  turn: number
  funnel: Funnel
  backlog: DemoEvent[]
  listeners: ((e: DemoEvent) => void)[]
  running: boolean
  complete: boolean
  resume: (() => void) | null
}

const emptyFunnel: Funnel = {
  found: null, relevant: null, screened_out: null, quality_checked: null,
  read_in_full: null, selected: null, findings: null, cited: null,
}

const projects: Project[] = [
  { project_id: 'demo-complete', name: TITLE, question: QUESTION, status: 'complete', created_at: '2026-07-07T09:12:00Z', updated_at: '2026-07-07T10:02:00Z', source_count: 214 },
  { project_id: 'demo-new', name: 'A healthy life for all', question: null, status: 'new', created_at: '2026-07-09T08:00:00Z', updated_at: '2026-07-09T08:00:00Z', source_count: 0 },
]

const states = new Map<string, MockState>()

function state(id: string): MockState {
  let s = states.get(id)
  if (!s) {
    const known = projects.find((x) => x.project_id === id)
    const complete = known?.status === 'complete'
    s = {
      project: known ?? { project_id: id, name: 'Untitled project', question: null, status: 'new', created_at: new Date().toISOString(), updated_at: new Date().toISOString(), source_count: 0 },
      plan: complete ? readyPlan : { ...emptyPlan },
      turn: 0,
      funnel: complete ? { ...finalFunnel } : { ...emptyFunnel },
      backlog: complete ? completeBacklog() : [],
      listeners: [], running: false, complete: !!complete, resume: null,
    }
    states.set(id, s)
  }
  return s
}

function emit(s: MockState, e: DemoEvent) {
  s.backlog.push(e)
  for (const fn of s.listeners) fn(e)
}

function run(s: MockState) {
  const steps = script()
  let i = 0
  const next = () => {
    if (i >= steps.length) {
      s.complete = true
      s.project.status = 'complete'
      s.project.source_count = 214
      return
    }
    const step = steps[i++]
    if (step.waitForCheckin) {
      s.resume = next
      return
    }
    setTimeout(() => {
      if (step.funnel) s.funnel = { ...s.funnel, ...step.funnel }
      if (step.event) emit(s, step.event)
      next()
    }, step.delay)
  }
  next()
}

const delay = (ms = 180) => new Promise((r) => setTimeout(r, ms))

export const mockApi: DemoApi = {
  async listProjects() {
    await delay()
    return [...states.values()].map((s) => s.project).concat(
      projects.filter((x) => !states.has(x.project_id)),
    ).filter((x, i, arr) => arr.findIndex((y) => y.project_id === x.project_id) === i)
  },
  async createProject(name) {
    await delay()
    const id = `mock-${Math.random().toString(36).slice(2, 8)}`
    const s = state(id)
    s.project.name = name
    return { project_id: id }
  },
  async chat(id, message) {
    const s = state(id)
    emit(s, { type: 'user.message', data: { text: message } })
    emit(s, { type: 'stage.progress', data: { stage: null, kind: 'tick', note: 'Planning the analysis' } })
    await delay(700)
    const turn = chatTurns[Math.min(s.turn, chatTurns.length - 1)]
    s.turn += 1
    s.plan = turn.plan
    if (turn.plan.title) s.project.name = turn.plan.title
    s.project.question = turn.plan.question ?? null
    s.project.status = 'planning'
    const suggestions = turn.suggestions ?? []
    emit(s, { type: 'narration', data: { text: turn.reply, suggestions } })
    emit(s, { type: 'plan.updated', data: { plan: turn.plan } })
    return { reply: turn.reply, plan: turn.plan, suggestions }
  },
  async start(projectId) {
    const s = state(projectId)
    if (!s.running) {
      s.running = true
      s.project.status = 'running'
      run(s)
    }
  },
  async answerCheckin(id, checkinId, reply, _params) {
    const s = state(id)
    emit(s, { type: 'checkin.resolved', data: { checkin_id: checkinId, reply } })
    const resume = s.resume
    s.resume = null
    resume?.()
  },
  openEvents(id, onEvent) {
    const s = state(id)
    let open = true
    // async backlog replay mirrors the live SSE connect
    setTimeout(() => {
      if (!open) return
      for (const e of s.backlog) onEvent(e)
      s.listeners.push(onEvent)
    }, 40)
    return {
      close() {
        open = false
        s.listeners = s.listeners.filter((f) => f !== onEvent)
      },
    }
  },
  async getPlan(id) { await delay(); return state(id).plan },
  async getFunnel(id) { await delay(); return state(id).funnel },
  async getLandscape(id) {
    await delay()
    const s = state(id)
    return s.complete || (s.funnel.quality_checked ?? 0) > 0 ? mockLandscape : null
  },
  async getGroups(id) {
    await delay()
    const s = state(id)
    return s.complete || (s.funnel.findings ?? 0) > 0 ? mockGroups : null
  },
  async getEvidence(id) {
    await delay()
    return (state(id).funnel.found ?? 0) > 0 ? mockEvidence : []
  },
  async getArtefact(id) { await delay(); return state(id).complete ? mockArtefact : null },
  async getFindings(id) {
    await delay()
    return (state(id).funnel.findings ?? 0) > 0 ? mockFindings : []
  },
  async getDecisions(id) {
    await delay()
    return (state(id).funnel.found ?? 0) > 0 ? mockDecisions : []
  },
  async getCoverage(id) {
    await delay()
    return (state(id).funnel.screened_out ?? 0) > 0 ? mockCoverage : null
  },
  async getSource(_id, sourceId) {
    await delay()
    const row = mockEvidence.find((r) => r.source_id === sourceId)
    return row ? dossier(row) : null
  },
  async getChunkContext(_id, chunkId) { await delay(); return chunkContext(chunkId) },
}
