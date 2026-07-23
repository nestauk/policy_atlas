// The capability + artifact model that sits IN FRONT of the single-project
// backend. The real orchestrator drives exactly one artifact (the evidence
// base); every other capability and any additional artifact is a light,
// clearly-invented frontend mock so the multi-artifact UX is demonstrable.

export type CapabilityId =
  | 'find_evidence'
  | 'value_for_money'
  | 'stakeholder_mapping'
  | 'theory_of_change'
  | 'meta_analysis'

export interface Capability {
  id: CapabilityId
  title: string
  blurb: string
  /** Noun for the thing this capability produces. */
  noun: string
}

export const CAPABILITIES: Capability[] = [
  {
    id: 'find_evidence',
    title: 'Evidence base',
    blurb: 'Search, screen and synthesise a cited evidence base — every claim traceable to its source.',
    noun: 'evidence base',
  },
  {
    id: 'value_for_money',
    title: 'Value for money analysis',
    blurb: 'Weigh costs against outcomes across the options on the table.',
    noun: 'value-for-money analysis',
  },
  {
    id: 'stakeholder_mapping',
    title: 'Stakeholder mapping',
    blurb: 'Map the actors, their interests and their influence over the issue.',
    noun: 'stakeholder map',
  },
  {
    id: 'theory_of_change',
    title: 'Theory of Change',
    blurb: 'Trace inputs through activities to outcomes — and the assumptions between them.',
    noun: 'theory of change',
  },
  {
    id: 'meta_analysis',
    title: 'Meta analysis',
    blurb: 'Pool comparable findings into a single combined estimate.',
    noun: 'meta-analysis',
  },
]

export const capabilityById = (id: CapabilityId): Capability =>
  CAPABILITIES.find((c) => c.id === id) ?? CAPABILITIES[0]

export type ArtifactStatus = 'draft' | 'running' | 'complete'

export interface OutputSection {
  heading: string
  body: string[]
}

export interface MockArtifact {
  id: string
  capability: CapabilityId
  title: string
  subtitle: string
  status: ArtifactStatus
  updatedAt: string
  output: OutputSection[]
  activity: { at: string; text: string }[]
}

/** A card the workspace can show — either the real evidence base or a mock. */
export interface ArtifactRef {
  id: string
  capability: CapabilityId
  title: string
  subtitle: string
  status: ArtifactStatus
  updatedAt: string
  kind: 'evidence' | 'mock'
  mock?: MockArtifact
}

/** Canned scripting for the mocked (non-evidence) capabilities. */
export const CANNED: Record<
  CapabilityId,
  { greeting: string; reply: string; subtitle: string; output: OutputSection[] }
> = {
  find_evidence: {
    greeting: '',
    reply: '',
    subtitle: '',
    output: [],
  },
  value_for_money: {
    greeting:
      'Happy to put a value-for-money analysis together. Which options should I compare, and over what time horizon and perspective (Exchequer, societal)?',
    reply:
      'Got it — I’ve costed the options against modelled health outcomes and drafted the analysis on the right. Every figure is illustrative for this demo.',
    subtitle: 'Costs against modelled outcomes for the structural options',
    output: [
      {
        heading: 'Summary',
        body: [
          'On a ten-year Exchequer view, the soft-drinks levy dominates the option set: it is broadly cost-saving once reformulation and averted treatment costs are counted, while school-based programmes carry the highest cost per QALY of the options considered.',
          'Whole-systems local programmes sit in between — plausibly cost-effective but with the widest uncertainty, driven by thin outcome data.',
        ],
      },
      {
        heading: 'Cost per outcome',
        body: [
          'Soft-drinks levy — net cost-saving (illustrative).',
          'Promotion-placement restrictions — ~£3,400 per QALY.',
          'Whole-systems community programmes — ~£11,000 per QALY (wide CI).',
          'School curriculum + family programmes — ~£28,000 per QALY.',
        ],
      },
      {
        heading: 'Caveats',
        body: [
          'Figures are demo placeholders, not a costed appraisal. Weight-outcome evidence for newer restrictions is thin, so cost-effectiveness for those options rests heavily on modelled assumptions.',
        ],
      },
    ],
  },
  stakeholder_mapping: {
    greeting:
      'I can map the stakeholders. Who’s the audience for this — a national policy team, a local authority, or a delivery partner? That shapes whose influence I weight.',
    reply:
      'Mapped it from a national-policy vantage point. The actors, their interests and an influence–interest read are on the right — illustrative for this demo.',
    subtitle: 'Actors, interests and influence across UK obesity policy',
    output: [
      {
        heading: 'Overview',
        body: [
          'The field splits into three blocs: central government and its arm’s-length bodies (high influence, mixed appetite), the food and drink industry (high influence, defensive interests), and public-health and civil-society actors (lower formal influence, high interest).',
        ],
      },
      {
        heading: 'Key actors',
        body: [
          'DHSC / OHID — policy owner; sets fiscal and regulatory levers.',
          'HM Treasury — controls the levy; frames measures as revenue vs health.',
          'Food & drink manufacturers / retailers — reformulation and pricing decisions.',
          'Local authorities — commission weight-management and whole-systems work.',
          'NHS England — delivery of diabetes-prevention and treatment pathways.',
          'Public-health charities & academia — evidence, advocacy, scrutiny.',
        ],
      },
      {
        heading: 'Influence–interest read',
        body: [
          'Manage closely: Treasury, DHSC/OHID, major manufacturers.',
          'Keep satisfied: retailers, NHSE.',
          'Keep informed: local authorities, charities, academia.',
        ],
      },
    ],
  },
  theory_of_change: {
    greeting:
      'Let’s build the theory of change. What’s the ultimate outcome you’re anchoring on — reduced obesity prevalence, or a narrower intermediate like reduced sugar intake?',
    reply:
      'Anchored on reduced childhood obesity prevalence and worked back through the causal chain. The full theory of change is on the right — illustrative for this demo.',
    subtitle: 'Inputs → activities → outcomes for structural interventions',
    output: [
      {
        heading: 'Goal',
        body: ['Reduced childhood obesity prevalence in the UK, with the gap between deprivation quintiles narrowing.'],
      },
      {
        heading: 'Causal chain',
        body: [
          'Inputs — fiscal levers, regulation, local commissioning budgets, evidence.',
          'Activities — levy on high-sugar drinks, promotion restrictions, whole-systems local action, family programmes.',
          'Outputs — reformulated products, reduced sugar purchasing, coordinated local delivery.',
          'Intermediate outcomes — lower dietary sugar intake, healthier food environments.',
          'Long-term outcome — reduced adiposity, narrowed inequalities.',
        ],
      },
      {
        heading: 'Key assumptions',
        body: [
          'Reformulation is not offset by displacement to untaxed products.',
          'Local capacity exists to sustain whole-systems action.',
          'Food-environment change is a large enough dose against the wider obesogenic environment.',
        ],
      },
    ],
  },
  meta_analysis: {
    greeting:
      'I can pool the comparable findings. Should I restrict to UK quasi-experimental designs, or include international RCTs where they’re comparable?',
    reply:
      'Pooled the comparable soft-drinks-levy findings into a combined estimate. The forest-plot read and heterogeneity are on the right — illustrative for this demo.',
    subtitle: 'Pooled estimate — soft-drinks levy on sugar purchased',
    output: [
      {
        heading: 'Pooled estimate',
        body: [
          'Across the comparable studies, the levy is associated with a mean reduction of ~30 g of sugar purchased per household per week (95% CI −38 to −22), consistent in direction across every included study.',
        ],
      },
      {
        heading: 'Heterogeneity',
        body: [
          'I² ≈ 46% — moderate heterogeneity, driven mainly by differences in the counterfactual period rather than effect direction.',
        ],
      },
      {
        heading: 'Caveats',
        body: [
          'Estimates are demo placeholders. Weight-outcome studies were too few and too design-heterogeneous to pool; only purchasing outcomes are combined here.',
        ],
      },
    ],
  },
}

/** Pre-existing mock artifacts so the gallery and multi-context chat are demonstrable. */
export const SEED_MOCK_ARTIFACTS: MockArtifact[] = [
  {
    id: 'mock-stakeholders',
    capability: 'stakeholder_mapping',
    title: 'Obesity policy — stakeholder map',
    subtitle: CANNED.stakeholder_mapping.subtitle,
    status: 'complete',
    updatedAt: 'yesterday',
    output: CANNED.stakeholder_mapping.output,
    activity: [
      { at: '11:02', text: 'Job started — Stakeholder mapping' },
      { at: '11:03', text: 'Scope confirmed — national-policy vantage point' },
      { at: '11:05', text: 'Actors identified — 6 primary, 9 secondary' },
      { at: '11:06', text: 'Influence–interest grid drafted' },
      { at: '11:07', text: 'Stakeholder map complete' },
    ],
  },
  {
    id: 'mock-meta',
    capability: 'meta_analysis',
    title: 'Soft-drinks levy — meta-analysis',
    subtitle: CANNED.meta_analysis.subtitle,
    status: 'complete',
    updatedAt: '3 days ago',
    output: CANNED.meta_analysis.output,
    activity: [
      { at: '09:14', text: 'Job started — Meta analysis' },
      { at: '09:15', text: 'Eligibility set — comparable purchasing-outcome studies' },
      { at: '09:18', text: 'Effect sizes extracted — 5 studies pooled' },
      { at: '09:19', text: 'Random-effects model fitted · I² ≈ 46%' },
      { at: '09:20', text: 'Meta-analysis complete' },
    ],
  },
]

/**
 * Which artifacts a source is cited in — mocked, deterministic from the source id.
 * A cited source always appears in the first evidence-type artifact and, for
 * roughly half of sources, a second one, so the column is visibly varied.
 */
export function citedInTitles(sourceId: string, cited: boolean, artifacts: ArtifactRef[]): string[] {
  if (!cited) return []
  const evidence = artifacts.filter(
    (a) => a.status === 'complete' && (a.capability === 'find_evidence' || a.capability === 'meta_analysis'),
  )
  if (evidence.length === 0) return []
  const sum = [...sourceId].reduce((n, ch) => n + ch.charCodeAt(0), 0)
  const titles = [evidence[0].title]
  if (evidence.length > 1 && sum % 2 === 0) titles.push(evidence[1].title)
  return titles
}

/** Past chats that start closed — reopenable from the Chats library. */
export interface SeedChat {
  id: string
  title: string
  updatedAt: string
  /** Relative sort key — higher = more recent. */
  sort: number
  contextIds: string[]
  messages: { role: 'user' | 'assistant'; text: string }[]
}

export const SEED_CHAT_HISTORY: SeedChat[] = [
  {
    id: 'hist-compare',
    title: 'Fiscal vs school options',
    updatedAt: 'Yesterday',
    sort: 20,
    contextIds: ['evidence', 'mock-meta'],
    messages: [
      { role: 'user', text: 'How do the soft-drinks levy findings sit alongside the school-programme evidence?' },
      {
        role: 'assistant',
        text: 'They answer different questions. The levy has the clearer purchasing and reformulation signal; school programmes improve behaviours but haven’t shown reliable BMI effects in the largest UK trials. If the goal is population-level adiposity, the levy is the stronger lever — school programmes are complementary, not substitutes.',
      },
    ],
  },
  {
    id: 'hist-stakeholders',
    title: 'Local-authority stakeholders',
    updatedAt: '3 days ago',
    sort: 10,
    contextIds: ['mock-stakeholders'],
    messages: [
      { role: 'user', text: 'Who should a local authority engage first on whole-systems obesity work?' },
      {
        role: 'assistant',
        text: 'Start with the public-health team and the cabinet member for health — they hold the commissioning budget — then bring in planning and education early. Manufacturers matter nationally more than locally; retailers and schools are the local delivery partners to keep informed.',
      },
    ],
  },
  {
    id: 'hist-scope',
    title: 'Narrowing the research question',
    updatedAt: 'Last week',
    sort: 5,
    contextIds: ['evidence'],
    messages: [
      { role: 'user', text: 'Should we drop family programmes from the scope?' },
      {
        role: 'assistant',
        text: 'You can — the evidence there is thinner and attrition-heavy. I’d keep them as a secondary theme rather than drop them entirely, so the gaps stay visible in the write-up.',
      },
    ],
  },
]

