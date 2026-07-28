import type { components } from "../api/gen/types";

export const MOCK_PROJECT_ID = "0d91c2e7-9b9b-4f4d-bd20-1f6819fb3425";
export const MOCK_RUN_ID = "7b40cc12-c3a7-4457-92fc-23d15a26d433";
export const MOCK_CHECK_IN_ID = "4c1acbe7-c4a1-4e0b-8d5a-bb25ea2ef634";
export const MOCK_PLAN_ID = "80000000-0000-4000-8000-000000000001";

const now = "2026-07-21T09:30:00Z";

// The mock project starts with NO run (`latest_run: null`): the 027 journey
// begins at the plan pane, not mid-analysis. `mock/api.ts` mutates
// `latest_run` in place once a run actually starts, so every read of this
// object stays consistent with the scripted run state.
export const mockProject: components["schemas"]["ProjectOut"] = {
  project_id: MOCK_PROJECT_ID,
  name: "Healthier childhoods in Tower Hamlets",
  question: "Which local policy approaches reduce childhood obesity for primary-school children, and under what conditions?",
  status: "active",
  created_at: "2026-07-18T09:00:00Z",
  updated_at: now,
  archived_at: null,
  latest_run: null,
};

export const mockFunnel: components["schemas"]["FunnelOut"] = {
  found: 128,
  screened_out: 82,
  relevant: 46,
  quality_checked: 31,
  read_in_full: 29,
  selected: 18,
  findings: 34,
  cited: 12,
};

/** Every landscape distribution totals 46: the screened-in, not found, count. */
export const mockLandscape: components["schemas"]["LandscapeOut"] = {
  evidence_types: { "Systematic review": 20, "Local evaluation": 14, "Policy analysis": 12 },
  years: { "2019": 6, "2020": 7, "2021": 9, "2022": 10, "2023": 8, "2024": 6 },
  themes: [
    { name: "School food environments", size: 19, description: "Meal standards, free breakfast, and food access." },
    { name: "Active travel", size: 15, description: "Safer walking and cycling for the school journey." },
    { name: "Family support", size: 12, description: "Affordable cooking and community referral support." },
  ],
  geographies: { "Tower Hamlets": 22, "London": 14, "Comparable UK cities": 10 },
};

export const mockEvidence: components["schemas"]["EvidenceItemOut"][] = [
  { source_id: "10000000-0000-4000-8000-000000000001", title: "Childhood obesity prevention in urban primary schools", year: 2024, venue: "Public Health Nutrition", origin: "OpenAlex", status: "found", cited: false },
  { source_id: "10000000-0000-4000-8000-000000000002", title: "Borough food strategy consultation", year: 2023, venue: "Tower Hamlets Council", origin: "Overton", status: "screened_out", screen_status: "excluded_retracted", screen_confidence: 1, status_reason: "The record was retracted", cited: false },
  { source_id: "10000000-0000-4000-8000-000000000003", title: "Universal breakfast clubs and diet quality", year: 2022, venue: "BMJ Open", origin: "OpenAlex", status: "relevant", evidence_type: "Cohort study", appraisal_tier: "Moderate confidence", screen_confidence: 0.91, screen_basis: "title_abstract", screen_stage: 2, url: "https://example.org/universal-breakfast", cited: false },
  { source_id: "10000000-0000-4000-8000-000000000004", title: "Healthy High Streets programme review", year: 2023, venue: "London Assembly", origin: "Overton", status: "not_selected", status_reason: "Lower transferability", cited: false },
  { source_id: "10000000-0000-4000-8000-000000000005", title: "School meals and child weight outcomes", year: 2021, venue: "The Lancet Child & Adolescent Health", origin: "OpenAlex", status: "selected", evidence_type: "Systematic review", cited: false },
  { source_id: "10000000-0000-4000-8000-000000000006", title: "Neighbourhood food access and family choices", year: 2020, venue: "Health & Place", origin: "OpenAlex", status: "read_in_full", evidence_type: "Qualitative study", cited: false },
  { source_id: "10000000-0000-4000-8000-000000000007", title: "Active travel incentives: implementation findings", year: 2024, venue: "Local Government Studies", origin: "OpenAlex", status: "findings_extracted", evidence_type: "Mixed methods", cited: false },
  { source_id: "10000000-0000-4000-8000-000000000008", title: "Making healthy choices easier near schools", year: 2023, venue: "Nesta", origin: "Uploaded", status: "cited", evidence_type: "Policy analysis", cited: true },
  { source_id: "10000000-0000-4000-8000-000000000009", title: "Children's food environment survey", year: null, venue: null, origin: "Uploaded", status: "unavailable", status_reason: "Full text could not be obtained", cited: false },
];

export const mockSourceDossiers: Record<string, components["schemas"]["SourceDossierOut"]> = {
  [mockEvidence[2].source_id]: {
    ...mockEvidence[2],
    abstract: "A cohort study of universal breakfast provision and regular breakfast consumption.",
    abstract_source: "provider",
    publisher: "BMJ",
    record_type: "Journal article",
    language: "English",
    doi: "10.0000/example.breakfast",
    cited_by_count: 14,
    fwci: 1.2,
    tags: [
      { tag: "School food", tag_type: "topic", asserted_by: "OpenAlex" },
      { tag: "Cohort study", tag_type: "method", asserted_by: "OpenAlex" },
      { tag: "School food", tag_type: "topic", asserted_by: "Analyst" },
    ],
    cited_in: [{ claim: "Universal breakfast provision can support consistent breakfast consumption.", quote: "Breakfast participation increased when provision was universal.", section_title: "What appears to help" }],
  },
  // A second dossier exercising an LLM-produced abstract (never presented as
  // document prose) and tags asserted by more than two distinct parties —
  // the "grouped by asserter, never merged" rendering (contract strand 7).
  [mockEvidence[7].source_id]: {
    ...mockEvidence[7],
    abstract: "An AI-generated summary: measures near the school gate that make the healthy choice the easy choice.",
    abstract_source: "llm_description",
    publisher: null,
    record_type: "Policy brief",
    language: "English",
    doi: null,
    cited_by_count: null,
    fwci: null,
    tags: [
      { tag: "Food environment", tag_type: "topic", asserted_by: "Analyst" },
      { tag: "School gate", tag_type: "topic", asserted_by: "Analyst" },
      { tag: "Policy analysis", tag_type: "method", asserted_by: "Nesta" },
    ],
    cited_in: [{ claim: "Pair school food action with safer active-travel routes and practical family support, while monitoring local reach.", quote: "Making the healthy choice the easy choice near the school gate.", section_title: "Implications for local action" }],
  },
};

export const mockFindings: components["schemas"]["FindingOut"][] = [
  {
    finding_id: "20000000-0000-4000-8000-000000000001",
    statement: "Universal breakfast provision was associated with more consistent breakfast consumption where schools paired it with non-stigmatising access.",
    source_id: mockEvidence[2].source_id,
    source_title: mockEvidence[2].title,
    profile: "iof",
    relevance: "priority",
    intervention: "Universal breakfast provision",
    outcome: "Breakfast consumption",
    effect_direction: "increase",
    statistics: {
      effect_size: 0.34,
      effect_size_type: "Cohen's d",
      ci_lower: 0.12,
      ci_upper: 0.56,
      standard_error: 0.11,
      p_value: 0.01,
      n: 412,
      k: 3,
      i_squared: 22.5,
      tau2: 0.02,
    },
    comparator: "No universal provision (opt-in only)",
    estimate_level: "pooled",
    causality_by_design: "plausibly_causal",
    effect_basis: "observed",
    study_geography: "United Kingdom",
    population: "Primary-school children, ages 5-11",
    setting: "State primary schools",
    study_design: "Cohort study",
    is_primary: true,
    stratum_qualifiers: [{ "Age band": "5-7" }, { Deprivation: "IMD quintile 1-2" }],
    quote: "Breakfast participation increased when provision was universal, particularly where uptake carried no separate sign-up.",
    quote_verified: true,
    groups: { "Intervention type": "Universal breakfast provision" },
  },
  {
    finding_id: "20000000-0000-4000-8000-000000000002",
    statement: "Active-travel offers were more durable when routes felt safe to families and schools coordinated arrival routines.",
    source_id: mockEvidence[6].source_id,
    source_title: mockEvidence[6].title,
    profile: "icf",
    relevance: "normal",
    context_type: "implementation_condition",
    claim: "Active-travel offers were more durable when routes felt safe to families and schools coordinated arrival routines.",
    intervention: "Active-travel offers",
    context_label: "Perceived route safety and school-coordinated arrival",
    level: "provider",
    claim_level: "study",
    claim_basis: "studied",
    population: "Primary-school families",
    setting: "Urban local authority",
    study_geography: "London, United Kingdom",
    study_design: "Mixed methods",
    resource_requirements: "Crossing patrols and signed routes",
    workforce_requirements: "School travel coordinator time",
    quote: "Where routes felt safe and arrival was coordinated with the school day, participation held up over the term.",
    quote_verified: false,
    groups: { "Intervention type": "Active-travel offers" },
  },
];

export const mockGroups: components["schemas"]["GroupsOut"] = {
  facets: [
    {
      facet: "Intervention type",
      ungrouped: 2,
      groups: [
        { label: "Universal breakfast provision", description: "School-based universal breakfast schemes.", size: 9 },
        { label: "Active-travel offers", description: "Safer walking and cycling initiatives for the school journey.", size: 6 },
        { label: "Family support programmes", description: "Affordable cooking and referral support for families.", size: 4 },
      ],
    },
  ],
};

export const mockDecisions: components["schemas"]["DecisionOut"][] = [
  { sequence: 5, occurred_at: "2026-07-21T09:31:10Z", kind: "search.executed", summary: "Searched OpenAlex for school-food intervention studies.", decided_by: null, detail: { openalex: 12 } },
  { sequence: 6, occurred_at: "2026-07-21T09:31:40Z", kind: "search.executed", summary: "Searched Overton for local policy documents.", decided_by: null, detail: { overton: 8 } },
  { sequence: 17, occurred_at: "2026-07-21T09:34:00Z", kind: "scope", summary: "Kept the focus on primary-school children and local policy levers.", decided_by: "user", detail: null },
  { sequence: 20, occurred_at: "2026-07-21T09:36:00Z", kind: "component.completed", summary: "Appraisal completed.", decided_by: null, detail: { appraised: 31 } },
  { sequence: 24, occurred_at: "2026-07-21T09:38:00Z", kind: "component.skipped", summary: "Landscape mapping was skipped — no themes requested for this run.", decided_by: null, detail: null },
  { sequence: 31, occurred_at: "2026-07-21T09:41:00Z", kind: "steering", summary: "Accepted the suggested evidence balance for the synthesis.", decided_by: "user", detail: { option_id: "suggested-balanced" } },
];

export const mockCheckIn: components["schemas"]["CheckInOut"] = {
  check_in_id: MOCK_CHECK_IN_ID,
  kind: "evidence_balance",
  boundary: "before_component",
  component: "synthesise",
  stage: "synthesise",
  render: "The screened-in set has strong school-food coverage but fewer local active-travel evaluations. Choose how the synthesis should handle that balance, or add your own free-text steer.",
  options: [
    { id: "add-local-context", label: "Add local context", description: "Tell us which local programme or neighbourhood context to prioritise.", requires_user_input: true, suggested: false },
    { id: "suggested-balanced", label: "Use the balanced synthesis", description: "Lead with the strongest evidence and name the local evidence gap.", requires_user_input: false, suggested: true },
  ],
  triggers: [{ trigger: "thin_local_evidence", detail: { local_sources: 5, screened_in: 46 } }],
  segment_reentry_allowed: true,
  rerun_component: "acquire",
  status: "pending",
  created_at: "2026-07-21T09:42:00Z",
  sequence: 42,
};

export const mockArtefact: components["schemas"]["ArtefactOut"] = {
  title: "Policy options for healthier childhoods",
  question: mockProject.question ?? "",
  coverage_snapshot: { source_count: 46, included: 46, screened_out: 82, study_types: { review: 20, evaluation: 14, analysis: 12 }, year_range: [2019, 2024] },
  sections: [
    {
      title: "What appears to help",
      role: "key_findings",
      blocks: [{
        block_id: "30000000-0000-4000-8000-000000000001",
        prose: "Universal breakfast provision can support more consistent breakfast consumption when access is non-stigmatising.",
        claims: [{ claim_id: "40000000-0000-4000-8000-000000000001", claim_type: "citation", text: "support more consistent breakfast consumption", span: [27, 71], citations: [{ citation_id: "50000000-0000-4000-8000-000000000001", n: 1, source_title: mockEvidence[2].title, quote: "Breakfast participation increased when provision was universal.", grounding_tier: "grounded", appraisal_label: "moderate" }] }],
        gaps: ["Few evaluations report outcomes for recently arrived families."],
      }],
    },
    {
      title: "Implications for local action",
      role: "conclusions",
      blocks: [{
        block_id: "30000000-0000-4000-8000-000000000002",
        prose: "Pair school food action with safer active-travel routes and practical family support, while monitoring local reach.",
        claims: [{ claim_id: "40000000-0000-4000-8000-000000000002", claim_type: "pattern", text: "Pair school food action with safer active-travel routes", span: [0, 56] }],
      }],
    },
  ],
  references: [{ n: 1, title: mockEvidence[2].title, year: 2022, venue: "BMJ Open", url: null }],
};

/** The live-artefact skeleton (contract strand 13), display-index ordered —
 *  same titles/prose as `mockArtefact` so the streamed and committed pages
 *  read as one continuous document. */
export const mockArtefactSkeleton: Array<{ index: number; title: string; focus: string }> = [
  { index: 0, title: "What appears to help", focus: "What the evidence shows helps, headline first." },
  { index: 1, title: "Implications for local action", focus: "What this means for local decisions." },
];

export const mockArtefactSectionProse: Record<number, string> = {
  0: "Universal breakfast provision can support more consistent breakfast consumption when access is non-stigmatising.",
  1: "Pair school food action with safer active-travel routes and practical family support, while monitoring local reach.",
};

export const mockCoverage: components["schemas"]["CoverageOut"] = {
  sentence: "Coverage is adequate for school-food and family-support approaches (46 screened-in sources, 2019-2024), while local active-travel evaluation evidence remains thin.",
  base: { screened_in: 46, years: [2019, 2024] },
  backends: ["openalex", "overton"],
  backends_detail: [
    {
      backend: "openalex",
      results: 86,
      relevant: 30,
      queries: [
        { query: "childhood obesity school intervention UK", results: 34 },
        { query: "primary school food environment obesity", results: 28 },
        { query: "active travel school children obesity", results: 24 },
      ],
    },
    {
      backend: "overton",
      results: 42,
      relevant: 16,
      queries: [
        { query: "Tower Hamlets school food policy", results: 19 },
        { query: "UK childhood obesity local strategy", results: 23 },
      ],
    },
  ],
};

/**
 * A ready plan draft (contract 027 F.2 fixture item 1b): the mock project
 * represents a resumed session — the planning conversation already
 * happened, and its transcript persisted (`seedPlanningTurns`), so the
 * plan pane renders ready immediately. Demonstrates `time_band`,
 * `scope_constraints.country_group` and labelled `steps`.
 */
export const mockPlanReady: components["schemas"]["PlanDraft"] = {
  title: "Healthier childhoods in Tower Hamlets",
  question: mockProject.question ?? null,
  scoping_notes: ["Primary-school children", "Local policy levers"],
  screening_criteria: ["UK or comparable-context studies", "Published 2019 or later"],
  backend_scope: "both",
  scope_constraints: {
    published_after: "2019-01-01",
    published_before: null,
    publisher_country: null,
    author_affiliation_countries: null,
    country_group: { label: "United Kingdom", countries: ["GB"], authorship: "planner-proposed" },
  },
  search_effort: "rapid",
  analysis_depth: "standard",
  components: ["screen_full", "select", "extract", "group"],
  component_rationale: { screen_full: "Needed to reach a shortlist worth reading in full." },
  grouping_facets: ["intervention"],
  extract_profiles: ["iof", "icf"],
  steering_mode: "moderate",
  assumptions: ["Comparable UK cities count as transferable context."],
  expected_artefact_shape: "standard",
  time_band: "10-15 minutes",
  steps: [
    { stage: "acquire", label: "Searching sources", blurb: "Queries out to academic and policy databases." },
    { stage: "screen", label: "Screening sources", blurb: "Checking relevance to primary-school children." },
    { stage: "classify", label: "Classifying evidence", blurb: "Labelling evidence types and settings." },
    { stage: "appraise", label: "Appraising quality", blurb: "Reviewing the strength of selected evidence." },
    { stage: "characterise", label: "Characterising findings", blurb: "Extracting implementation conditions." },
    { stage: "synthesise", label: "Synthesising the evidence", blurb: "Preparing a decision-ready evidence base." },
  ],
  ready: true,
};

export const MOCK_PLANNING_TURN_IDS = {
  first: "60000000-0000-4000-8000-000000000001",
  second: "60000000-0000-4000-8000-000000000002",
  failed: "60000000-0000-4000-8000-000000000003",
} as const;

/**
 * The durable planning transcript (contract 027 F.2 fixture item 1a): two
 * completed turns that formed the ready plan above, plus one FAILED row —
 * the honest incomplete-turn render — deliberately the latest turn so it
 * carries a Retry control. Returns a fresh array each call so
 * `resetMockScenario` can restore pristine seed state.
 */
export function seedPlanningTurns(): components["schemas"]["PlanningTranscriptTurnOut"][] {
  return [
    {
      client_turn_id: MOCK_PLANNING_TURN_IDS.first,
      turn_index: 1,
      user_message: "Which local policy approaches reduce childhood obesity for primary-school children?",
      reply: "I can look at school-food, active-travel and family-support levers for Tower Hamlets. Want me to keep it UK-focused?",
      suggestions: ["Keep it UK-focused", "Widen to comparable cities"],
      status: "completed",
      created_at: "2026-07-18T09:02:00Z",
      completed_at: "2026-07-18T09:02:04Z",
    },
    {
      client_turn_id: MOCK_PLANNING_TURN_IDS.second,
      turn_index: 2,
      user_message: "Keep it UK-focused, rapid pass, and check both academic and policy sources.",
      reply: "Plan's ready: a rapid search across academic and policy sources, a standard write-up, and a check-in whenever something needs your judgement.",
      suggestions: [],
      status: "completed",
      created_at: "2026-07-18T09:03:10Z",
      completed_at: "2026-07-18T09:03:16Z",
    },
    {
      client_turn_id: MOCK_PLANNING_TURN_IDS.failed,
      turn_index: 3,
      user_message: "Also fold in whether family-support programmes should be a separate lever.",
      reply: null,
      suggestions: [],
      status: "failed",
      created_at: "2026-07-21T08:58:00Z",
      completed_at: "2026-07-21T08:58:03Z",
    },
  ];
}
