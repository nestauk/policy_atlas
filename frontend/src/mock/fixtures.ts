import type { components } from "../api/gen/types";
import { TASK } from "../lib/vocabulary";

export const MOCK_TASK_ID = "0d91c2e7-9b9b-4f4d-bd20-1f6819fb3425";
export const MOCK_RUN_ID = "7b40cc12-c3a7-4457-92fc-23d15a26d433";
export const MOCK_CHECK_IN_ID = "4c1acbe7-c4a1-4e0b-8d5a-bb25ea2ef634";
export const MOCK_PLAN_ID = "80000000-0000-4000-8000-000000000001";
export const MOCK_TASK_AGENT_CONVERSATION_ID = "50000000-0000-4000-8000-000000000001";
export const MOCK_PROJECT_ID = "60000000-0000-4000-8000-000000000001";
const MOCK_ORGANISATION_ID = "90000000-0000-4000-8000-000000000001";

const now = "2026-07-21T09:30:00Z";

// The mock task starts with NO run (`latest_run: null`): the 027 journey
// begins at the plan pane, not mid-analysis. `mock/api.ts` mutates
// `latest_run` in place once a run actually starts, so every read of this
// object stays consistent with the scripted run state.
export const mockTask: components["schemas"]["TaskOut"] = {
  task_id: MOCK_TASK_ID,
  name: "Healthier childhoods in Tower Hamlets",
  question: "Which local policy approaches reduce childhood obesity for primary-school children, and under what conditions?",
  status: "active",
  created_at: "2026-07-18T09:00:00Z",
  updated_at: now,
  archived_at: null,
  latest_run: null,
  // Task 033 tenancy. The mock signs in as the row's owner, so `is_owner` is
  // true and every affordance stays live; the org journeys the switcher needs
  // arrive with the mock's `/me` and project routes.
  visibility: "org",
  is_owner: true,
  owner_display: "Ada Lovelace",
  // Task 037 public sharing: the mock's task starts unshared, read at the
  // full grade — mock mode signs in as the owner.
  is_public: false,
  access: "full",
  // Assigned to `mockProject` below so `GET /tasks?project_id=` has a
  // real member to return (task 033 phase 10a; membership is a list, ADR 0032).
  project_ids: [MOCK_PROJECT_ID],
  // Task 044: the kind of work. The mock's task is an Evidence search; a
  // scoping task is created through the mock's `POST /tasks`.
  capability: "evidence_search",
  from_task_ids: [],
  links: [],
  // Task 045: what exists and what is active. No walk, no longlist yet.
  active_run: null,
  has_longlist: false,
};

/** Task 033 phase 10a: the one project the mock serves. `task_count`
 *  mirrors the real read model's own derivation (never cached on the row) —
 *  it counts `mockTask`, the fixture's only member. */
export const mockProject: components["schemas"]["ProjectOut"] = {
  project_id: MOCK_PROJECT_ID,
  name: "Child health, Tower Hamlets",
  description: `${TASK.many} assessing childhood health policy levers for the borough.`,
  created_at: "2026-07-15T09:00:00Z",
  task_count: 1,
  visibility: "org",
  is_owner: true,
  owner_display: "Ada Lovelace",
};

/**
 * `GET /api/v1/me` fixtures (task 033 phase 10a). `mockMeUnenrolled` is the
 * mock's default identity — dark launch: an unenrolled caller (`organisation:
 * null`) so the switcher and every org-scoped affordance stay hidden and
 * every pre-033 mock journey is unchanged until a test opts into
 * `mockMeEnrolled` via `setMockMe` (`mock/api.ts`).
 */
export const mockMeUnenrolled: components["schemas"]["MeOut"] = {
  user_id: "mock-policy-lead",
  display_name: "Ada Lovelace",
  email: null,
  organisation: null,
  is_admin: false,
};

export const mockMeEnrolled: components["schemas"]["MeOut"] = {
  user_id: "mock-policy-lead",
  display_name: "Ada Lovelace",
  email: "ada.lovelace@example.gov.uk",
  organisation: { org_id: MOCK_ORGANISATION_ID, name: "Department for Local Growth" },
  is_admin: false,
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

export const MOCK_THEME_ID_SCHOOL_FOOD = "30000000-0000-4000-8000-000000000001";
export const MOCK_THEME_ID_ACTIVE_TRAVEL = "30000000-0000-4000-8000-000000000002";

/** Every landscape distribution totals 46: the screened-in, not found, count.
 *  "Family support" carries no `theme_id` on purpose — a legacy
 *  characterisation predating 028 strand 8, which the sources theme filter
 *  must omit rather than offer a selection that can never round-trip. */
export const mockLandscape: components["schemas"]["LandscapeOut"] = {
  evidence_types: { "Systematic review": 20, "Local evaluation": 14, "Policy analysis": 12 },
  years: { "2019": 6, "2020": 7, "2021": 9, "2022": 10, "2023": 8, "2024": 6 },
  themes: [
    { name: "School food environments", size: 19, description: "Meal standards, free breakfast, and food access.", theme_id: MOCK_THEME_ID_SCHOOL_FOOD },
    { name: "Active travel", size: 15, description: "Safer walking and cycling for the school journey.", theme_id: MOCK_THEME_ID_ACTIVE_TRAVEL },
    { name: "Family support", size: 12, description: "Affordable cooking and community referral support." },
  ],
  geographies: { "Tower Hamlets": 22, "London": 14, "Comparable UK cities": 10 },
};

export const mockEvidence: components["schemas"]["EvidenceItemOut"][] = [
  { source_id: "10000000-0000-4000-8000-000000000001", title: "Childhood obesity prevention in urban primary schools", year: 2024, venue: "Public Health Nutrition", origin: "OpenAlex", status: "found", cited: false, read_in_full: false },
  { source_id: "10000000-0000-4000-8000-000000000002", title: "Borough food strategy consultation", year: 2023, venue: "Tower Hamlets Council", origin: "Overton", status: "screened_out", screen_status: "excluded_retracted", screen_confidence: 1, status_reason: "The record was retracted", cited: false, read_in_full: false },
  { source_id: "10000000-0000-4000-8000-000000000003", title: "Universal breakfast clubs and diet quality", year: 2022, venue: "BMJ Open", origin: "OpenAlex", status: "relevant", evidence_type: "Cohort study", appraisal_tier: "Moderate confidence", screen_status: "relevant", screen_confidence: 0.91, screen_basis: "title_abstract", screen_stage: 2, screen_reason: "Universal breakfast provision is a primary-school food-environment exposure in scope.", classification_reason: "Prospective cohort following ten schools over two academic years.", url: "https://example.org/universal-breakfast", cited: false, read_in_full: false },
  { source_id: "10000000-0000-4000-8000-000000000004", title: "Healthy High Streets programme review", year: 2023, venue: "London Assembly", origin: "Overton", status: "not_selected", status_reason: "Lower transferability", screen_status: "relevant", screen_confidence: 0.72, screen_reason: "Covers food-environment levers around schools, though at borough rather than school level.", cited: false, read_in_full: false },
  { source_id: "10000000-0000-4000-8000-000000000005", title: "School meals and child weight outcomes", year: 2021, venue: "The Lancet Child & Adolescent Health", origin: "OpenAlex", status: "selected", evidence_type: "Systematic review", screen_status: "relevant", screen_confidence: 0.88, screen_reason: "Directly evaluates school-meal policies against child weight outcomes.", classification_reason: "Explicit systematic search and synthesis across 42 trials.", cited: false, read_in_full: false },
  { source_id: "10000000-0000-4000-8000-000000000006", title: "Neighbourhood food access and family choices", year: 2020, venue: "Health & Place", origin: "OpenAlex", status: "read_in_full", evidence_type: "Qualitative study", screen_status: "relevant", screen_confidence: 0.81, screen_reason: "Family food-choice mechanisms around primary schools are in scope.", cited: false, read_in_full: true },
  { source_id: "10000000-0000-4000-8000-000000000007", title: "Active travel incentives: implementation findings", year: 2024, venue: "Local Government Studies", origin: "OpenAlex", status: "findings_extracted", evidence_type: "Mixed methods", screen_status: "relevant", screen_confidence: 0.86, screen_reason: "Implementation evidence for an in-scope active-travel lever.", cited: false, read_in_full: true },
  { source_id: "10000000-0000-4000-8000-000000000008", title: "Making healthy choices easier near schools", year: 2023, venue: "Nesta", origin: "Uploaded", status: "cited", evidence_type: "Policy analysis", appraisal_tier: "Moderate", screen_status: "relevant", screen_confidence: 0.95, screen_reason: "Uploaded by the task owner; directly addresses the question.", classification_reason: "Argument-led policy analysis rather than primary data collection.", cited: true, read_in_full: true },
  { source_id: "10000000-0000-4000-8000-000000000009", title: "Children's food environment survey", year: null, venue: null, origin: "Uploaded", status: "unavailable", status_reason: "Full text could not be obtained", screen_status: "relevant", screen_confidence: 0.79, screen_reason: "Survey coverage of children's food environments matches the scope.", cited: false, read_in_full: false },
];

/** Theme membership for the mock evidence rows, keyed by theme id — the
 *  real `EvidenceItemOut` carries no theme field (the server joins against
 *  `source_tag` internally), so the sources-view theme filter has nothing
 *  to key off in mock mode without this. `mock/api.ts`'s evidence handler
 *  reads this to honour the `theme` query param honestly. */
export const mockEvidenceThemeIds: Record<string, string[]> = {
  [mockEvidence[2].source_id]: [MOCK_THEME_ID_SCHOOL_FOOD],
  [mockEvidence[4].source_id]: [MOCK_THEME_ID_SCHOOL_FOOD],
  [mockEvidence[7].source_id]: [MOCK_THEME_ID_SCHOOL_FOOD],
  [mockEvidence[6].source_id]: [MOCK_THEME_ID_ACTIVE_TRAVEL],
};

/** Shared + distinct institutions: markers 1, 1-2 — the D5 numbering path.
 *  One copy feeds the dossier, the reference list and both chunk-context
 *  handlers so the surfaces can never silently disagree. */
export const mockAuthorships: components["schemas"]["AuthorshipOut"][] = [
  { name: "Alex Sampleton", institutions: ["University of Exampleshire"] },
  { name: "Casey Mockford", institutions: ["University of Exampleshire", "Institute of Fictional Studies"] },
];

export const mockSourceDossiers: Record<string, components["schemas"]["SourceDossierOut"]> = {
  [mockEvidence[2].source_id]: {
    ...mockEvidence[2],
    authorships: mockAuthorships,
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
    // Corporate author (042 D2): one name, no institutions, no markers.
    authorships: [{ name: "Example Policy Institute" }],
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
    chunk_id: "70000000-0000-4000-8000-000000000001",
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
    chunk_id: null,
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
    { id: "add-local-context", label: "Add local context", description: "Tell us which local programme or neighbourhood context to prioritise.", requires_user_input: true, suggested: false, why: null, endorsement: null },
    { id: "suggested-balanced", label: "Use the balanced synthesis", description: "Lead with the strongest evidence and name the local evidence gap.", requires_user_input: false, suggested: true, why: null, endorsement: null },
  ],
  triggers: [{ trigger: "thin_local_evidence", detail: { local_sources: 5, screened_in: 46 } }],
  bundle: null,
  segment_reentry_allowed: true,
  rerun_component: "acquire",
  status: "pending",
  created_at: "2026-07-21T09:42:00Z",
  sequence: 42,
};

export const mockArtefact: components["schemas"]["ArtefactOut"] = {
  artefact_id: "00000000-0000-4000-8000-00000000a001",
  title: "Policy options for healthier childhoods",
  question: mockTask.question ?? "",
  coverage_snapshot: { source_count: 46, included: 46, screened_out: 82, study_types: { review: 20, evaluation: 14, analysis: 12 }, year_range: [2019, 2024] },
  sections: [
    {
      title: "What appears to help",
      role: "key_findings",
      blocks: [{
        block_id: "30000000-0000-4000-8000-000000000001",
        prose: "Universal breakfast provision can support more consistent breakfast consumption when access is non-stigmatising.",
        claims: [{ claim_id: "40000000-0000-4000-8000-000000000001", claim_type: "citation", text: "support more consistent breakfast consumption", span: [34, 79], citations: [{ citation_id: "50000000-0000-4000-8000-000000000001", n: 1, source_title: mockEvidence[2].title, quote: "Breakfast participation increased when provision was universal.", grounding_tier: "tier_2", appraisal_label: "moderate" }] }],
        gaps: ["Few evaluations report outcomes for recently arrived families."],
      }],
    },
    {
      title: "Implications for local action",
      role: "conclusions",
      blocks: [{
        block_id: "30000000-0000-4000-8000-000000000002",
        prose: "Pair school food action with safer active-travel routes and practical family support, while monitoring local reach.",
        claims: [{ claim_id: "40000000-0000-4000-8000-000000000002", claim_type: "pattern", text: "Pair school food action with safer active-travel routes", span: [0, 56], theme: { source: "grouping", base: "Co-occurrence across the screened-in corpus", items: [{ name: "Active-travel offers", description: "Route-safety and arrival-routine measures that families adopt alongside food provision.", size: 5, facet: "Intervention type", sources: [{ source_id: mockEvidence[0].source_id, title: mockEvidence[0].title }, { source_id: mockEvidence[1].source_id, title: mockEvidence[1].title }] }] } }],
      }],
    },
  ],
  references: [{
    n: 1,
    title: mockEvidence[2].title,
    year: 2022,
    venue: "BMJ Open",
    url: null,
    authorships: mockAuthorships,
  }],
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

/**
 * The options-scoping baseline (task 044, deliverable 9) the mock serves as
 * the scoping task's Result: the seven written sections in their fixed order,
 * one proposed section inserted after "What is contested", and the
 * code-rendered Sources section last. No key findings, no conclusions, no
 * case studies — a baseline mints none of them.
 *
 * `role` is `"standard"` throughout because that is what the read model
 * returns: the Sources block is written with role `"sources"` and coerced
 * (`api/readmodels/repository.py`). The section ORDER is what puts Sources
 * last, not its role.
 */
export const mockBaselineArtefact: components["schemas"]["ArtefactOut"] = {
  artefact_id: "00000000-0000-4000-8000-00000000b001",
  title: "Do nothing: current policy and trajectory",
  question:
    "How can we reduce the number of young people not in education, employment or training?",
  template: "baseline",
  depth_label: "scoping pass",
  coverage_snapshot: {
    source_count: 18,
    included: 18,
    screened_out: 24,
    study_types: { "policy report": 11, analysis: 5, evaluation: 2 },
    year_range: [2020, 2026],
  },
  sections: [
    {
      title: "What is in place",
      nav_label: "In place",
      role: "standard",
      blocks: [{
        block_id: "31000000-0000-4000-8000-000000000001",
        prose: "The borough runs a youth employment hub, a supported-internship offer through the further education college, and the national Youth Offer through Jobcentre Plus. Careers advice reaches school leavers through the schools themselves; there is no single referral route for young people who have already left.",
        claims: [],
      }],
    },
    {
      title: "Trend if nothing changes",
      nav_label: "Trend",
      role: "standard",
      blocks: [{
        block_id: "31000000-0000-4000-8000-000000000002",
        prose: "The NEET and not-known rate for 16-17 year-olds has moved little across the last four years, sitting a little above the London average. No source in the set projects the rate forward beyond the current academic year.",
        claims: [],
      }],
    },
    {
      title: "Who is affected",
      nav_label: "Who",
      role: "standard",
      blocks: [{
        block_id: "31000000-0000-4000-8000-000000000003",
        prose: "Young people with a recorded special educational need, those known to children's social care, and those who left school without a level 2 qualification are over-represented. The plan names 16-24 year-olds; the published figures measure 16-17 year-olds, so the older half of the group is not described by this data.",
        claims: [],
      }],
    },
    {
      title: "What is already changing",
      nav_label: "Changing",
      role: "standard",
      blocks: [{
        block_id: "31000000-0000-4000-8000-000000000004",
        prose: "A devolved adult-skills settlement takes effect from the next financial year, and the college's supported-internship places are due to expand. One employer-partnership programme closes at the end of the current cohort.",
        claims: [],
      }],
    },
    {
      title: "What is contested",
      nav_label: "Contested",
      role: "standard",
      blocks: [{
        block_id: "31000000-0000-4000-8000-000000000005",
        prose: "Sources disagree about whether the binding constraint is the supply of entry-level jobs or the transition support around them. They also disagree about the not-known cohort: one reading treats it as measurement error, another as unrecorded disengagement.",
        claims: [],
      }],
    },
    {
      title: "How the transition is tracked",
      nav_label: "Tracking",
      role: "standard",
      blocks: [{
        block_id: "31000000-0000-4000-8000-000000000006",
        prose: "Destination data is collected at two points in the year and reconciled against school records. Two sources describe the reconciliation as incomplete for young people who move borough.",
        claims: [],
      }],
    },
    {
      title: "Cost of inaction",
      nav_label: "Cost of inaction",
      role: "standard",
      blocks: [{
        block_id: "31000000-0000-4000-8000-000000000007",
        prose: "One national estimate puts the lifetime public-finance cost of a sustained NEET spell in the tens of thousands of pounds per person, at 2021 prices. No source in this set costs the status quo for this borough.",
        claims: [{
          claim_id: "41000000-0000-4000-8000-000000000001",
          claim_type: "gap",
          text: "No source in this set costs the status quo for this borough.",
          span: [138, 195],
          citations: [],
          gap: { grade: "corpus_absence", caveat: null },
        }],
      }],
    },
    {
      title: "Key assumption",
      nav_label: "Key assumption",
      role: "standard",
      blocks: [{
        block_id: "31000000-0000-4000-8000-000000000008",
        prose: "The assumption most worth checking is that the current offer does not reach the young people driving the trend, rather than reaching them and failing. This rests on the absence of a referral route for those who have already left, and on the incomplete destination reconciliation reported above.",
        claims: [],
      }],
    },
    {
      title: "Sources",
      nav_label: "Sources",
      role: "standard",
      blocks: [{
        block_id: "31000000-0000-4000-8000-000000000009",
        prose: "18 sources from Overton and OpenAlex, searched for the situation and trend this plan describes, limited to the United Kingdom and other high-income countries.\nLive official statistics and departmental pages were not searched; figures come from the documents above, as at their publication dates.\nSource mix: 13 grey literature (policy reports, official and organisational publications) and 5 academic articles. The profile leans on grey sources.\nA language restriction is recorded in the plan and not yet applied at retrieval.",
        claims: [],
      }],
    },
  ],
  references: [],
};

export const mockCoverage: components["schemas"]["CoverageOut"] = {
  sentence: "Coverage is adequate for school-food and family-support approaches (46 screened-in sources, 2019-2024), while local active-travel evaluation evidence remains thin.",
  base: { screened_in: 46, years: [2019, 2024] },
  backends: ["OpenAlex", "Overton"],
  backends_detail: [
    {
      // The real coverage read model serves PUBLIC backend names — the
      // fixture matches so the label mapping is exercised as shipped.
      backend: "OpenAlex",
      results: 86,
      relevant: 30,
      queries: [
        { query: "childhood obesity school intervention UK", results: 34 },
        { query: "primary school food environment obesity", results: 28 },
        { query: "active travel school children obesity", results: 24 },
      ],
    },
    {
      backend: "Overton",
      results: 42,
      relevant: 16,
      queries: [
        { query: "Tower Hamlets school food policy", results: 19 },
        { query: "UK childhood obesity local strategy", results: 23 },
      ],
    },
  ],
};

// --- Chat conversations (task 029 phase G3 mock) ------------------------
//
// The chat citation carries a durable chunk id (not the artefact citation
// table's id) — a distinct fixture id in the same 8-4-4-4-12 style, one
// prefix on from the task_agent-turn ids above.
export const MOCK_CHAT_CITATION_CHUNK_ID = "70000000-0000-4000-8000-000000000001";
export const MOCK_CHAT_CLAIM_ID = "70000000-0000-4000-8000-000000000002";

/** The quote a chat citation resolves to — the same breakfast-provision
 *  passage the artefact's own citation cites (`mockFindings[0].quote`),
 *  so `mock/api.ts`'s chunk-context handler can share one context window. */
export const MOCK_CHAT_CITATION_QUOTE = mockFindings[0].quote ?? "";

/** Two NDJSON `delta` chunks the mock chat stream emits in order; joined,
 *  they form the turn's persisted `answer` (with its `[1]` marker landing
 *  in the second chunk, so the marker itself only ever arrives whole). */
export const MOCK_CHAT_ANSWER_DELTAS = [
  "Universal breakfast provision supported more consistent uptake ",
  "when schools removed the separate sign-up step [1].",
] as const;

/** The claim-span text the mock chat turn carries over its own answer
 *  (030 fold e2e coverage): server-shape faithful to what
 *  `chat_floor.apply_citation_floor` actually persists on `claims[]` —
 *  `{text, span, citation_ns}`, with `span` the floor's own
 *  `prose.find(text)` result rather than a hand-picked offset that could
 *  silently drift from `MOCK_CHAT_ANSWER_DELTAS` above. Deliberately ends
 *  before the `[1]` marker (like a model's own claim text, which never
 *  includes the bracket) so the mock exercises the claim-span affordance and
 *  the literal-marker affordance as the two distinct, non-overlapping
 *  regions the fold's design specifies. */
export const MOCK_CHAT_CLAIM_TEXT = "Universal breakfast provision supported more consistent uptake";

export const MOCK_CHAT_PROGRESS_LABEL = "Searching the evidence…";

/**
 * A ready plan draft (contract 027 F.2 fixture item 1b): the mock task
 * represents a resumed session — the task_agent conversation already
 * happened, and its transcript persisted (`seedTaskAgentTurns`), so the
 * plan pane renders ready immediately. Demonstrates `time_band`,
 * `scope_constraints.country_group` and labelled `steps`.
 */
export const mockPlanReady: components["schemas"]["PlanDraft"] = {
  title: "Healthier childhoods in Tower Hamlets",
  question: mockTask.question ?? null,
  scoping_notes: ["Primary-school children", "Local policy levers"],
  screening_criteria: ["UK or comparable-context studies", "Published 2019 or later"],
  backend_scope: "both",
  scope_constraints: {
    published_after: "2019-01-01",
    published_before: null,
    publisher_country: null,
    publisher_source: null,
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
  section_budget: null,
  steps: [
    { stage: "acquire", label: "Searching sources", blurb: "Queries out to academic and policy databases." },
    { stage: "screen", label: "Screening sources", blurb: "Checking relevance to primary-school children." },
    { stage: "classify", label: "Classifying evidence", blurb: "Labelling evidence types and settings." },
    { stage: "appraise", label: "Appraising quality", blurb: "Reviewing the strength of selected evidence." },
    { stage: "characterise", label: "Characterising findings", blurb: "Extracting implementation conditions." },
    { stage: "synthesise", label: "Writing the report", blurb: "Preparing a decision-ready evidence base." },
  ],
  ready: true,
};

export const MOCK_LINK_ID = "70000000-0000-4000-8000-000000000001";
export const MOCK_LINK_SOURCE_RUN_ID = "70000000-0000-4000-8000-000000000002";

/**
 * A ready options-scoping plan (task 044, contract deliverable 5), one link
 * and one of each constraint kind so every plan-document section has
 * something to render. Mirrors `mockPlanReady`'s role for the ES fixture:
 * the mock's task_agent turn transcript is scripted as already having
 * reached this shape, so mock mode and the e2e journey can show the
 * finished plan document without scripting every intermediate turn.
 */
export const mockScopingPlanReady: components["schemas"]["ScopingPlanDraft"] = {
  title: "Cutting NEET numbers in Tower Hamlets",
  question: "How can we reduce the number of young people not in education, employment or training?",
  intended_change: {
    text: "Fewer 16-24 year-olds are NEET six months after leaving school.",
    origin: "from_your_question",
  },
  target_unit: { text: "16-24 year-olds at risk of becoming NEET", origin: "assumed" },
  where: { text: "United Kingdom", origin: "assumed" },
  outcomes: [
    { text: "NEET rate at 6 months", origin: "from_your_question" },
    { text: "Sustained employment or training at 12 months", origin: "assumed" },
  ],
  depth: "standard",
  constraints: [
    {
      text: "Only include options a local authority can fund directly",
      kind: "requirement",
      origin: "your_call",
      checked_at: "longlist",
      country_group: null,
      published_after: null,
      published_before: null,
      languages: null,
      setting: false,
      default: null,
    },
    {
      text: "Prefer options with a lower cost per participant",
      kind: "preference",
      origin: "your_call",
      checked_at: "assessment",
      country_group: null,
      published_after: null,
      published_before: null,
      languages: null,
      setting: false,
      default: null,
    },
    {
      text: "Evidence from the UK and other high-income countries only",
      kind: "evidence_restriction",
      origin: "assumed",
      checked_at: "retrieval",
      country_group: { label: "United Kingdom", countries: ["GB"], authorship: "planner-proposed" },
      published_after: null,
      published_before: null,
      languages: ["English"],
      setting: false,
      default: null,
    },
    {
      text: "Transferable to United Kingdom",
      kind: "preference",
      origin: "assumed",
      checked_at: "assessment",
      country_group: null,
      published_after: null,
      published_before: null,
      languages: null,
      setting: false,
      default: "transferability",
    },
  ],
  your_options: [
    {
      text: "A youth guarantee, like the one Finland runs",
      design: {
        name: "Youth guarantee",
        description: "Every young person out of work for four months is offered a job, training or education.",
        design_features: [
          "an offer within four months of leaving work or education",
          "a job, apprenticeship, training or education place",
          "delivered through Jobcentre Plus",
        ],
        outcomes_served: ["NEET rate at 6 months"],
        assumed: ["delivered through Jobcentre Plus"],
        version: 1,
      },
      turn_index: 2,
    },
  ],
  your_context: [
    {
      text: "We already run a careers-advice service in every secondary school.",
      type: "present_fact",
      turn_index: 1,
      test_as_condition: false,
    },
    {
      text: "We plan to expand apprenticeship places next year.",
      type: "commitment",
      turn_index: 2,
      test_as_condition: true,
    },
  ],
  entry_branch: "explore",
  linked_task_ids: [],
  steering_mode: "moderate",
  steer_point_defaults: [],
  assumptions: ["The United Kingdom is the right jurisdiction unless you say otherwise."],
  steps: [
    {
      stage: "synthesise",
      label: "Baseline",
      blurb:
        "What is in place, the trend, who is affected and what is contested, from Overton and OpenAlex. The run pauses for you to question it and confirm the plan.",
    },
    {
      stage: "acquire",
      label: "Longlist",
      blurb:
        "Suggest options, search widely, read every abstract for the interventions it covers, cluster them into options, apply your constraints.",
    },
    {
      stage: "select",
      label: "Shortlist and assessment",
      blurb: "Review the proposed reading set. Assessment runs only when you say so. Not in this release.",
    },
  ],
  time_band: "10-15 minutes",
  baseline_confirmed: null,
  ready: true,
};

const MOCK_TASK_AGENT_TURN_IDS = {
  first: "60000000-0000-4000-8000-000000000001",
  second: "60000000-0000-4000-8000-000000000002",
  failed: "60000000-0000-4000-8000-000000000003",
} as const;

/**
 * The durable task_agent transcript (contract 027 F.2 fixture item 1a): two
 * completed turns that formed the ready plan above, plus one FAILED row —
 * the honest incomplete-turn render — deliberately the latest turn so it
 * carries a Retry control. Returns a fresh array each call so
 * `resetMockScenario` can restore pristine seed state.
 */
export function seedTaskAgentTurns(): components["schemas"]["TaskAgentTranscriptTurnOut"][] {
  return [
    {
      client_turn_id: MOCK_TASK_AGENT_TURN_IDS.first,
      turn_index: 1,
      user_message: "Which local policy approaches reduce childhood obesity for primary-school children?",
      reply: "Here's how I've read your question.",
      suggestions: [],
      part: {
        id: "question",
        step_label: "Plan · 1 of 3 · the question",
        title: "Which local policy approaches reduce childhood obesity for primary-school children?",
        body: "Read as a policy and service-delivery question — I'll search academic and grey literature.",
        chips: null,
        options: [
          { id: "confirm", label: "That's my question", sub: null, primary: true, reason: null },
          { id: "refine", label: "Refine it", sub: null, primary: false, reason: null },
        ],
      },
      status: "completed",
      created_at: "2026-07-18T09:02:00Z",
      completed_at: "2026-07-18T09:02:04Z",
    },
    {
      client_turn_id: MOCK_TASK_AGENT_TURN_IDS.second,
      turn_index: 2,
      user_message: "That's my question\n\n[confirm part=question option=confirm]",
      reply: "What counts as in-scope? Edit any chip directly. I'll search from 2016 onward. UK as the primary setting is judged from each document.",
      suggestions: [],
      part: {
        id: "scope",
        step_label: "Plan · 2 of 3 · scope",
        title: "What counts as in-scope?",
        body: null,
        chips: [
          { label: "UK primary", kind: "text", value: "UK as the primary study setting" },
          { label: "Since 2016", kind: "date_range", value: '{"after": "2016-01-01", "before": null}' },
        ],
        options: [
          { id: "confirm", label: "Looks right", sub: null, primary: true, reason: null },
          { id: "change", label: "Add or change a constraint", sub: null, primary: false, reason: null },
        ],
      },
      status: "completed",
      created_at: "2026-07-18T09:03:10Z",
      completed_at: "2026-07-18T09:03:16Z",
    },
    {
      client_turn_id: MOCK_TASK_AGENT_TURN_IDS.failed,
      turn_index: 3,
      user_message: "Also fold in whether family-support programmes should be a separate lever.",
      reply: null,
      suggestions: [],
      part: null,
      status: "failed",
      created_at: "2026-07-21T08:58:00Z",
      completed_at: "2026-07-21T08:58:03Z",
    },
  ];
}

// --- The options-scoping baseline gate (task 044, Phase 5.5) -------------

export const MOCK_BASELINE_CHECK_IN_ID = "4c1acbe7-c4a1-4e0b-8d5a-bb25ea2ef635";

const MOCK_SCOPING_TURN_IDS = {
  plan: "60000000-0000-4000-8000-000000000011",
  answer: "60000000-0000-4000-8000-000000000012",
  decision: "60000000-0000-4000-8000-000000000013",
} as const;

/** The gate's key assumption, quoted by the card and by the seeded answer. */
const MOCK_KEY_ASSUMPTION =
  "Careers advice reaches the young people already in school, not the ones who have already dropped out.";

/**
 * The baseline gate's check-in (`baseline_confirm`) — the one steer point on
 * the scoping lattice. Its bundle carries what the card shows: the baseline's
 * key assumption and the four plan settings the walk ran from.
 */
export const mockBaselineGateCheckIn: components["schemas"]["CheckInOut"] = {
  check_in_id: MOCK_BASELINE_CHECK_IN_ID,
  kind: "baseline_confirm",
  boundary: "after_component",
  component: "synthesise",
  stage: "synthesise",
  render: [
    "Confirm the plan against the baseline",
    `Key assumption: ${MOCK_KEY_ASSUMPTION}`,
    "Settings",
    "Target unit: 16-24 year-olds at risk of becoming NEET",
    "Where: United Kingdom",
    "Outcomes: NEET rate at 6 months; Sustained employment or training at 12 months",
    "Depth: standard",
  ].join("\n"),
  options: [
    {
      id: "confirm_plan",
      label: "Confirm plan and build longlist",
      description: "Accept the plan as it stands and go on to the longlist.",
      requires_user_input: false,
      suggested: false,
      why: null,
      endorsement: null,
    },
    {
      id: "change_plan",
      label: "Change the plan",
      description: "Stop here and edit the plan; the baseline you have read is kept.",
      requires_user_input: false,
      suggested: false,
      why: null,
      endorsement: null,
    },
  ],
  triggers: [],
  bundle: {
    key_assumption: MOCK_KEY_ASSUMPTION,
    settings: {
      target_unit: "16-24 year-olds at risk of becoming NEET",
      where: "United Kingdom",
      outcomes: ["NEET rate at 6 months", "Sustained employment or training at 12 months"],
      depth: "standard",
    },
  },
  segment_reentry_allowed: false,
  rerun_component: "synthesise",
  status: "pending",
  created_at: "2026-07-21T09:44:00Z",
  sequence: 44,
};

/** The scoping task's own seed transcript: the one planning turn that made
 *  the ready scoping plan. The answer and decision turns are not seeded —
 *  the mock mints them from real requests at the gate (a question posted
 *  while paused comes back an `answer` turn; the card's decision appends a
 *  `decision` turn), so mock mode shows the projection the way the backend
 *  produces it rather than as pre-baked history. */
export function seedScopingTaskAgentTurns(): components["schemas"]["TaskAgentTranscriptTurnOut"][] {
  return [
    {
      client_turn_id: MOCK_SCOPING_TURN_IDS.plan,
      turn_index: 1,
      user_message: "How can we reduce the number of young people not in education, employment or training?",
      reply: "I've drafted a scoping plan. Review it, then build the baseline.",
      suggestions: [],
      part: null,
      capability: "options_scoping",
      kind: "reply",
      status: "completed",
      created_at: "2026-07-21T09:10:00Z",
      completed_at: "2026-07-21T09:10:06Z",
    },
  ];
}

/** A grounded answer to a question asked at the gate: one claim, one
 *  citation, rendered by the chat's own citation renderer. */
export function mockScopingAnswerTurn(
  clientTurnId: string,
  message: string,
  turnIndex: number,
  createdAt: string,
): components["schemas"]["TaskAgentTranscriptTurnOut"] {
  const answer =
    "The baseline holds one study of school-based careers advice; it does not cover young people who have already left education [1].";
  return {
    client_turn_id: clientTurnId,
    turn_index: turnIndex,
    user_message: message,
    reply: answer,
    suggestions: [],
    part: null,
    capability: "options_scoping",
    kind: "answer",
    answer: {
      citations: [
        {
          n: 1,
          id: MOCK_CHAT_CITATION_CHUNK_ID,
          chunk_id: MOCK_CHAT_CITATION_CHUNK_ID,
          source_id: mockEvidence[0].source_id,
          source_title: mockEvidence[0].title,
          quote: MOCK_CHAT_CITATION_QUOTE,
        },
      ],
      claims: [
        {
          claim_id: MOCK_CHAT_CLAIM_ID,
          text: "The baseline holds one study of school-based careers advice",
          span: [0, 57],
          citation_ns: [1],
        },
      ],
      enrichment: null,
      handoff: null,
      warning_not_evidence_checked: false,
      stopped_before_evidence_check: false,
    },
    status: "completed",
    created_at: createdAt,
    completed_at: createdAt,
  };
}

/** The decision turn the gate's card decision leaves in the thread. */
export function mockScopingDecisionTurn(
  optionId: string,
  label: string,
  turnIndex: number,
  createdAt: string,
): components["schemas"]["TaskAgentTranscriptTurnOut"] {
  return {
    client_turn_id: MOCK_SCOPING_TURN_IDS.decision,
    turn_index: turnIndex,
    user_message: label,
    reply: null,
    suggestions: [],
    part: null,
    capability: "options_scoping",
    kind: "decision",
    decision: {
      option_id: optionId,
      label,
      check_in_id: MOCK_BASELINE_CHECK_IN_ID,
      capability_run_id: MOCK_RUN_ID,
      plan_version: 1,
    },
    status: "completed",
    created_at: createdAt,
    completed_at: createdAt,
  };
}

// task 045 (6.2) -----------------------------------------------------------
// The longlist's three surfaces (list view, reduced grid, option card): a
// longlist walk on `mockScopingPlanReady`'s NEET/Tower Hamlets plan, two
// themes and four options exercising every state the views must render —
// one clustered and excluded (breaks the funding requirement, and part of
// the package below), one suggested with no in-scope evidence, one added by
// the user with zero documents (its own option search found nothing yet),
// and one package bundling the excluded option.

type OptionOutFixture = components["schemas"]["OptionOut"];
type OptionSummaryOutFixture = components["schemas"]["OptionSummaryOut"];

export const MOCK_LONGLIST_RUN_ID = "a0000000-0000-4000-8000-000000000001";
export const MOCK_LONGLIST_WALK_ID = "a0000000-0000-4000-8000-000000000002";
export const MOCK_LONGLIST_THEME_ID_CONDITIONALITY = "a0000000-0000-4000-8000-000000000020";
export const MOCK_LONGLIST_THEME_ID_UNIVERSAL_OFFER = "a0000000-0000-4000-8000-000000000021";
export const MOCK_OPTION_ID_EXCLUDED = "a0000000-0000-4000-8000-000000000010";
export const MOCK_OPTION_ID_NO_IN_SCOPE = "a0000000-0000-4000-8000-000000000011";
export const MOCK_OPTION_ID_ADDED_BY_YOU = "a0000000-0000-4000-8000-000000000012";
export const MOCK_OPTION_ID_PACKAGE = "a0000000-0000-4000-8000-000000000013";
const MOCK_LONGLIST_LINKED_TASK_ID = "a0000000-0000-4000-8000-000000000099";

export const MOCK_LONGLIST_WHERE_LABEL = "United Kingdom";
const MOCK_LONGLIST_RESTRICTION_TEXT = "Evidence from the UK and other high-income countries only";
const MOCK_LONGLIST_FUNDING_CONSTRAINT = "Only include options a local authority can fund directly";
const MOCK_LONGLIST_COST_PREFERENCE = "Prefer options with a lower cost per participant";

/** One full `OptionOut` (the card) per longlist option, keyed by id — the
 *  single source both `GET /options/{id}` and the two GETs' summaries
 *  project from, and the exclude/include/add handlers mutate in place. */
export const mockLonglistOptionCards: Record<string, OptionOutFixture> = {
  [MOCK_OPTION_ID_EXCLUDED]: {
    option_id: MOCK_OPTION_ID_EXCLUDED,
    name: "National sanctions regime",
    description: "A statutory duty on the local authority to withdraw benefits from NEET young people who refuse an offer.",
    design: {
      name: "National sanctions regime",
      description: "A statutory duty on the local authority to withdraw benefits from NEET young people who refuse an offer.",
      design_features: [
        "a duty to withdraw benefits on refusal of an offer",
        "administered by the local authority",
        "applies after one missed offer",
      ],
      outcomes_served: ["NEET rate at 6 months"],
      assumed: [],
      version: 1,
    },
    design_features: ["a duty to withdraw benefits on refusal of an offer", "administered by the local authority", "applies after one missed offer"],
    design_version: 1,
    outcomes_served: ["NEET rate at 6 months"],
    origin: "clustered",
    state: "excluded",
    exclusion: {
      by: "constrain",
      constraint: MOCK_LONGLIST_FUNDING_CONSTRAINT,
      reason: "A local authority cannot withdraw a national benefit directly.",
    },
    no_in_scope_evidence: false,
    restriction_text: null,
    primary_lever_type: "enforce existing powers",
    lever_none_fits_reason: null,
    secondary_lever_types: ["regulate"],
    ambition: "structural",
    ambition_reason: "Changes who is entitled to a national benefit, not just how it is delivered.",
    taxonomy_version: "lever-types-v1",
    document_count: 6,
    evaluated_count: 3,
    settings: ["Jobcentre", "Secondary school"],
    where_tried: { where: 4, comparable: 2, other: 0, unknown: 0 },
    relations: [{ kind: "part_of", other_option_id: MOCK_OPTION_ID_PACKAGE, other_name: "Universal youth offer bundle" }],
    abstract_only: false,
    is_entrant_with_no_documents: false,
    search_pending: false,
    run_id: MOCK_LONGLIST_RUN_ID,
    capability_run_id: MOCK_LONGLIST_WALK_ID,
    plan_version: 1,
    where_label: MOCK_LONGLIST_WHERE_LABEL,
    depth_label: "scoping pass",
    evidence: {
      documents: 6,
      by_evidence_type: { "Systematic review": 2, "Policy analysis": 3, "Local evaluation": 1 },
      by_role: { evaluated: 3, described: 2, recommended: 0, mentioned: 1 },
      by_tier: { Strong: 2, Moderate: 3, "not rated": 1 },
      where_tried: { where: 4, comparable: 2, other: 0, unknown: 0 },
      populations: ["16-24 year-olds"],
      settings: ["Jobcentre", "Secondary school"],
      outcomes: ["NEET rate at 6 months"],
      flagged_not_stated: 1,
      inherited_labels: 1,
      abstract_only: 2,
    },
    judgements: [
      { constraint_id: "relevant", constraint_text: "Relevant to the stated outcomes", verdict: "passes", reason: "Targets the NEET rate directly." },
      { constraint_id: "distinct", constraint_text: "Distinct from the other options", verdict: "passes", reason: "No other option on the list withdraws benefits." },
      { constraint_id: "in_scope", constraint_text: "Within scope", verdict: "passes", reason: "Its evidence is drawn from the plan's country group." },
      { constraint_id: "req-1", constraint_text: MOCK_LONGLIST_FUNDING_CONSTRAINT, verdict: "breaks", reason: "A local authority cannot withdraw a national benefit directly." },
    ],
    guesses: [
      { constraint_id: "pref-1", constraint_text: MOCK_LONGLIST_COST_PREFERENCE, guess: "likely a low cost per participant, a guess rather than evidence", leaning: "likely_meets" },
    ],
    transferability: "checked at assessment",
    in_scope: null,
    documents: [
      { task_source_snapshot_id: "mock-doc-a1", title: "Conditionality and NEET outcomes: a local authority review", role: "evaluated", evidence_type: "Local evaluation", tier: "Moderate", design_feature_not_stated: false, where_tried_group: "where", source_task_id: null },
      { task_source_snapshot_id: "mock-doc-a2", title: "Benefit sanctions for young jobseekers: a systematic review", role: "evaluated", evidence_type: "Systematic review", tier: "Strong", design_feature_not_stated: false, where_tried_group: "comparable", source_task_id: null },
      { task_source_snapshot_id: null, title: "National activation policy briefing", role: "mentioned", evidence_type: "Policy analysis", tier: null, design_feature_not_stated: true, where_tried_group: "where", source_task_id: MOCK_LONGLIST_LINKED_TASK_ID },
    ],
  },
  [MOCK_OPTION_ID_NO_IN_SCOPE]: {
    option_id: MOCK_OPTION_ID_NO_IN_SCOPE,
    name: "School-based mentoring",
    description: "Trained mentors work one-to-one with pupils identified as at risk of becoming NEET.",
    design: {
      name: "School-based mentoring",
      description: "Trained mentors work one-to-one with pupils identified as at risk of becoming NEET.",
      design_features: ["one-to-one mentoring", "delivered in the school", "targeted at pupils flagged as at risk"],
      outcomes_served: ["NEET rate at 6 months"],
      assumed: [],
      version: 1,
    },
    design_features: ["one-to-one mentoring", "delivered in the school", "targeted at pupils flagged as at risk"],
    design_version: 1,
    outcomes_served: ["NEET rate at 6 months"],
    origin: "suggested",
    state: "included",
    exclusion: null,
    no_in_scope_evidence: true,
    restriction_text: MOCK_LONGLIST_RESTRICTION_TEXT,
    primary_lever_type: "provide a service",
    lever_none_fits_reason: null,
    secondary_lever_types: [],
    ambition: "incremental",
    ambition_reason: "Adds support alongside the existing offer rather than changing who runs it.",
    taxonomy_version: "lever-types-v1",
    document_count: 4,
    evaluated_count: 2,
    settings: ["Secondary school", "Community centre"],
    where_tried: { where: 0, comparable: 0, other: 3, unknown: 1 },
    relations: [],
    abstract_only: true,
    is_entrant_with_no_documents: false,
    search_pending: false,
    run_id: MOCK_LONGLIST_RUN_ID,
    capability_run_id: MOCK_LONGLIST_WALK_ID,
    plan_version: 1,
    where_label: MOCK_LONGLIST_WHERE_LABEL,
    depth_label: "scoping pass",
    evidence: {
      documents: 4,
      by_evidence_type: { "Local evaluation": 3, "Policy analysis": 1 },
      by_role: { evaluated: 2, described: 1, recommended: 1, mentioned: 0 },
      by_tier: { Moderate: 2, Limited: 1, "not rated": 1 },
      where_tried: { where: 0, comparable: 0, other: 3, unknown: 1 },
      populations: ["Pupils at risk of becoming NEET"],
      settings: ["Secondary school", "Community centre"],
      outcomes: ["NEET rate at 6 months"],
      flagged_not_stated: 0,
      inherited_labels: 0,
      abstract_only: 4,
    },
    judgements: [
      { constraint_id: "relevant", constraint_text: "Relevant to the stated outcomes", verdict: "passes", reason: "Targets pupils at risk of the NEET outcome." },
      { constraint_id: "distinct", constraint_text: "Distinct from the other options", verdict: "passes", reason: "No other option delivers one-to-one mentoring." },
      { constraint_id: "in_scope", constraint_text: "Within scope", verdict: "cannot_check", reason: "None of its documents pass the plan's evidence restriction." },
      { constraint_id: "req-1", constraint_text: MOCK_LONGLIST_FUNDING_CONSTRAINT, verdict: "passes", reason: "Delivered through the school's existing budget." },
    ],
    guesses: [
      { constraint_id: "pref-1", constraint_text: MOCK_LONGLIST_COST_PREFERENCE, guess: "likely a low cost per participant, a guess rather than evidence", leaning: "likely_meets" },
    ],
    transferability: "checked at assessment",
    in_scope: { restriction: MOCK_LONGLIST_RESTRICTION_TEXT, in_scope_documents: 0, documents: 4 },
    documents: [
      { task_source_snapshot_id: "mock-doc-b1", title: "Peer mentoring for at-risk pupils in Ontario schools", role: "evaluated", evidence_type: "Local evaluation", tier: "Moderate", design_feature_not_stated: false, where_tried_group: "other", source_task_id: null },
      { task_source_snapshot_id: "mock-doc-b2", title: "School mentoring and NEET risk: an Australian cohort study", role: "evaluated", evidence_type: "Local evaluation", tier: "Limited", design_feature_not_stated: false, where_tried_group: "other", source_task_id: null },
      { task_source_snapshot_id: "mock-doc-b3", title: "Mentoring programmes for disengaged youth: a scoping review", role: "described", evidence_type: "Policy analysis", tier: null, design_feature_not_stated: false, where_tried_group: "other", source_task_id: null },
      { task_source_snapshot_id: "mock-doc-b4", title: "Youth mentoring outcomes: unclear geography", role: "recommended", evidence_type: "Local evaluation", tier: "Moderate", design_feature_not_stated: false, where_tried_group: "unknown", source_task_id: null },
    ],
  },
  [MOCK_OPTION_ID_ADDED_BY_YOU]: {
    option_id: MOCK_OPTION_ID_ADDED_BY_YOU,
    name: "Youth guarantee",
    description: "Every young person out of work for four months is offered a job, training or education.",
    design: {
      name: "Youth guarantee",
      description: "Every young person out of work for four months is offered a job, training or education.",
      design_features: [
        "an offer within four months of leaving work or education",
        "a job, apprenticeship, training or education place",
        "delivered through Jobcentre Plus",
      ],
      outcomes_served: ["NEET rate at 6 months"],
      assumed: ["delivered through Jobcentre Plus"],
      version: 1,
    },
    design_features: [
      "an offer within four months of leaving work or education",
      "a job, apprenticeship, training or education place",
      "delivered through Jobcentre Plus",
    ],
    design_version: 1,
    outcomes_served: ["NEET rate at 6 months"],
    origin: "added_by_you",
    state: "included",
    exclusion: null,
    no_in_scope_evidence: false,
    restriction_text: null,
    primary_lever_type: null,
    lever_none_fits_reason: "The design bundles an offer, an obligation and a delivery channel — no single instrument fits yet.",
    secondary_lever_types: [],
    ambition: null,
    ambition_reason: null,
    taxonomy_version: "lever-types-v1",
    document_count: 0,
    evaluated_count: 0,
    settings: [],
    where_tried: { where: 0, comparable: 0, other: 0, unknown: 0 },
    relations: [],
    abstract_only: false,
    is_entrant_with_no_documents: true,
    search_pending: false,
    run_id: MOCK_LONGLIST_RUN_ID,
    capability_run_id: MOCK_LONGLIST_WALK_ID,
    plan_version: 1,
    where_label: MOCK_LONGLIST_WHERE_LABEL,
    depth_label: "scoping pass",
    evidence: {
      documents: 0,
      by_evidence_type: {},
      by_role: {},
      by_tier: {},
      where_tried: { where: 0, comparable: 0, other: 0, unknown: 0 },
      populations: [],
      settings: [],
      outcomes: [],
      flagged_not_stated: 0,
      inherited_labels: 0,
      abstract_only: 0,
    },
    judgements: [],
    guesses: [],
    transferability: "checked at assessment",
    in_scope: null,
    documents: [],
  },
  [MOCK_OPTION_ID_PACKAGE]: {
    option_id: MOCK_OPTION_ID_PACKAGE,
    name: "Universal youth offer bundle",
    description: "A single application bringing together careers advice, apprenticeships and training places under one offer.",
    design: {
      name: "Universal youth offer bundle",
      description: "A single application bringing together careers advice, apprenticeships and training places under one offer.",
      design_features: ["one application", "careers advice, apprenticeships and training places", "delivered through Jobcentre Plus"],
      outcomes_served: ["NEET rate at 6 months", "Sustained employment or training at 12 months"],
      assumed: [],
      version: 1,
    },
    design_features: ["one application", "careers advice, apprenticeships and training places", "delivered through Jobcentre Plus"],
    design_version: 1,
    outcomes_served: ["NEET rate at 6 months", "Sustained employment or training at 12 months"],
    origin: "suggested",
    state: "included",
    exclusion: null,
    no_in_scope_evidence: false,
    restriction_text: null,
    primary_lever_type: "regulate",
    lever_none_fits_reason: null,
    secondary_lever_types: ["provide a service"],
    ambition: "do minimum",
    ambition_reason: "Reorganises the existing offer into one application rather than adding anything new.",
    taxonomy_version: "lever-types-v1",
    document_count: 9,
    evaluated_count: 5,
    settings: ["Jobcentre", "Secondary school", "Community centre"],
    where_tried: { where: 5, comparable: 3, other: 1, unknown: 0 },
    relations: [{ kind: "has_part", other_option_id: MOCK_OPTION_ID_EXCLUDED, other_name: "National sanctions regime" }],
    abstract_only: false,
    is_entrant_with_no_documents: false,
    search_pending: false,
    run_id: MOCK_LONGLIST_RUN_ID,
    capability_run_id: MOCK_LONGLIST_WALK_ID,
    plan_version: 1,
    where_label: MOCK_LONGLIST_WHERE_LABEL,
    depth_label: "scoping pass",
    evidence: {
      documents: 9,
      by_evidence_type: { "Systematic review": 4, "Local evaluation": 3, "Policy analysis": 2 },
      by_role: { evaluated: 5, described: 3, recommended: 1, mentioned: 0 },
      by_tier: { "Very strong": 2, Strong: 4, Moderate: 3 },
      where_tried: { where: 5, comparable: 3, other: 1, unknown: 0 },
      populations: ["16-24 year-olds"],
      settings: ["Jobcentre", "Secondary school", "Community centre"],
      outcomes: ["NEET rate at 6 months", "Sustained employment or training at 12 months"],
      flagged_not_stated: 0,
      inherited_labels: 0,
      abstract_only: 1,
    },
    judgements: [
      { constraint_id: "relevant", constraint_text: "Relevant to the stated outcomes", verdict: "passes", reason: "Serves both stated outcomes." },
      { constraint_id: "distinct", constraint_text: "Distinct from the other options", verdict: "passes", reason: "The only option combining the existing offer into one application." },
      { constraint_id: "in_scope", constraint_text: "Within scope", verdict: "passes", reason: "Its evidence is drawn from the plan's country group." },
      { constraint_id: "req-1", constraint_text: MOCK_LONGLIST_FUNDING_CONSTRAINT, verdict: "passes", reason: "Delivered through the local authority's existing Jobcentre Plus partnership." },
    ],
    guesses: [
      { constraint_id: "pref-1", constraint_text: MOCK_LONGLIST_COST_PREFERENCE, guess: "cannot say on cost from the design alone", leaning: "cannot_say" },
    ],
    transferability: "checked at assessment",
    in_scope: null,
    documents: [
      { task_source_snapshot_id: "mock-doc-d1", title: "Single-application youth guarantees: a systematic review", role: "evaluated", evidence_type: "Systematic review", tier: "Very strong", design_feature_not_stated: false, where_tried_group: "where", source_task_id: null },
      { task_source_snapshot_id: "mock-doc-d2", title: "Combining careers advice and apprenticeships: a local evaluation", role: "evaluated", evidence_type: "Local evaluation", tier: "Strong", design_feature_not_stated: false, where_tried_group: "comparable", source_task_id: null },
      { task_source_snapshot_id: "mock-doc-d3", title: "One-stop youth offers outside the UK: a policy analysis", role: "described", evidence_type: "Policy analysis", tier: "Moderate", design_feature_not_stated: false, where_tried_group: "other", source_task_id: null },
    ],
  },
};

/** Project one option card down to the list/grid's summary shape (the same
 *  fields `GET /longlist` returns for each option). */
function toLonglistOptionSummary(option: OptionOutFixture): OptionSummaryOutFixture {
  return {
    option_id: option.option_id,
    name: option.name,
    description: option.description,
    outcomes_served: option.outcomes_served,
    origin: option.origin,
    state: option.state,
    exclusion: option.exclusion,
    no_in_scope_evidence: option.no_in_scope_evidence,
    restriction_text: option.restriction_text,
    primary_lever_type: option.primary_lever_type,
    lever_none_fits_reason: option.lever_none_fits_reason,
    secondary_lever_types: option.secondary_lever_types,
    ambition: option.ambition,
    ambition_reason: option.ambition_reason,
    taxonomy_version: option.taxonomy_version,
    design_version: option.design_version,
    document_count: option.document_count,
    evaluated_count: option.evaluated_count,
    settings: option.settings,
    where_tried: option.where_tried,
    relations: option.relations,
    abstract_only: option.abstract_only,
    is_entrant_with_no_documents: option.is_entrant_with_no_documents,
    search_pending: option.search_pending,
  };
}

/** Option ids added by hand or by chat verb since the walk built the four
 *  fixture options above (`POST /options`, `mockFetch`) — always unthemed,
 *  like a real rebuild's new entrants. */
export const mockLonglistExtraOptionIds: string[] = [];

/** Build one `OptionOut` for `POST /options` (the button's and the chat
 *  verb's shared path, D13): minted *added by you*, zero documents, not yet
 *  typed — an option search would fill it in, which the mock does not run. */
export function buildMockAddedOption(text: string): OptionOutFixture {
  const name = text.trim().length > 0 ? text.trim() : "New option";
  return {
    option_id: crypto.randomUUID(),
    name,
    description: name,
    design: {
      name,
      description: name,
      design_features: [name],
      outcomes_served: [],
      assumed: [],
      version: 1,
    },
    design_features: [name],
    design_version: 1,
    outcomes_served: [],
    origin: "added_by_you",
    state: "included",
    exclusion: null,
    no_in_scope_evidence: false,
    restriction_text: null,
    primary_lever_type: null,
    lever_none_fits_reason: "Not yet typed — its option search hasn't returned.",
    secondary_lever_types: [],
    ambition: null,
    ambition_reason: null,
    taxonomy_version: "lever-types-v1",
    document_count: 0,
    evaluated_count: 0,
    settings: [],
    where_tried: { where: 0, comparable: 0, other: 0, unknown: 0 },
    relations: [],
    abstract_only: false,
    is_entrant_with_no_documents: true,
    search_pending: false,
    run_id: MOCK_LONGLIST_RUN_ID,
    capability_run_id: MOCK_LONGLIST_WALK_ID,
    plan_version: 1,
    where_label: MOCK_LONGLIST_WHERE_LABEL,
    depth_label: "scoping pass",
    evidence: {
      documents: 0,
      by_evidence_type: {},
      by_role: {},
      by_tier: {},
      where_tried: { where: 0, comparable: 0, other: 0, unknown: 0 },
      populations: [],
      settings: [],
      outcomes: [],
      flagged_not_stated: 0,
      inherited_labels: 0,
      abstract_only: 0,
    },
    judgements: [],
    guesses: [],
    transferability: "checked at assessment",
    in_scope: null,
    documents: [],
  };
}

/** `GET /tasks/{id}/longlist` — two themes, four options, in themed-first
 *  order (the package's theme before "No theme"'s single added-by-you
 *  option), built from `mockLonglistOptionCards` so the summary and the
 *  card never drift apart. Any option added since (`mockLonglistExtraOptionIds`)
 *  appends unthemed, like a real rebuild's new entrants. */
export function mockLonglist(): components["schemas"]["LonglistOut"] {
  const options = [
    MOCK_OPTION_ID_EXCLUDED,
    MOCK_OPTION_ID_NO_IN_SCOPE,
    MOCK_OPTION_ID_PACKAGE,
    MOCK_OPTION_ID_ADDED_BY_YOU,
    ...mockLonglistExtraOptionIds,
  ].map((optionId) => toLonglistOptionSummary(mockLonglistOptionCards[optionId]));
  return {
    run_id: MOCK_LONGLIST_RUN_ID,
    capability_run_id: MOCK_LONGLIST_WALK_ID,
    plan_version: 1,
    built_from_plan_version: 1,
    current_plan_version: 1,
    counts: {
      options: options.length,
      themes: 2,
      included: options.filter((option) => option.state === "included").length,
      excluded: options.filter((option) => option.state === "excluded").length,
      no_in_scope: options.filter((option) => option.no_in_scope_evidence).length,
      unclustered: 5,
      not_an_option: 2,
      none_fits: options.filter((option) => option.primary_lever_type == null).length,
    },
    themes: [
      {
        theme_id: MOCK_LONGLIST_THEME_ID_CONDITIONALITY,
        name: "Conditionality and support",
        description: "Options that attach an obligation or targeted help to the existing offer.",
        option_ids: [MOCK_OPTION_ID_EXCLUDED, MOCK_OPTION_ID_NO_IN_SCOPE],
      },
      {
        theme_id: MOCK_LONGLIST_THEME_ID_UNIVERSAL_OFFER,
        name: "A universal offer",
        description: "A single, non-conditional offer replacing today's patchwork.",
        option_ids: [MOCK_OPTION_ID_PACKAGE],
      },
    ],
    unthemed_option_ids: [MOCK_OPTION_ID_ADDED_BY_YOU, ...mockLonglistExtraOptionIds],
    options,
    where_label: MOCK_LONGLIST_WHERE_LABEL,
    lever_types: [
      "regulate",
      "subsidise",
      "tax or charge",
      "inform",
      "provide a service",
      "enforce existing powers",
      "devolve",
      "change who runs the system",
      "invest in infrastructure",
      "convene",
    ],
    ambition_bands: [
      { key: "do minimum", label: "Do minimum" },
      { key: "incremental", label: "Incremental" },
      { key: "structural", label: "Structural" },
    ],
    taxonomy_version: "lever-types-v1",
    depth_label: "scoping pass",
  };
}
