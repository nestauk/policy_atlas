import type { components } from "../api/gen/types";

export const MOCK_PROJECT_ID = "0d91c2e7-9b9b-4f4d-bd20-1f6819fb3425";
export const MOCK_RUN_ID = "7b40cc12-c3a7-4457-92fc-23d15a26d433";
export const MOCK_CHECK_IN_ID = "4c1acbe7-c4a1-4e0b-8d5a-bb25ea2ef634";

const now = "2026-07-21T09:30:00Z";

export const mockProject: components["schemas"]["ProjectOut"] = {
  project_id: MOCK_PROJECT_ID,
  name: "Healthier childhoods in Tower Hamlets",
  question: "Which local policy approaches reduce childhood obesity for primary-school children, and under what conditions?",
  status: "active",
  created_at: "2026-07-18T09:00:00Z",
  updated_at: now,
  archived_at: null,
  latest_run: { capability_run_id: MOCK_RUN_ID, status: "running", started_at: now, ended_at: null },
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
  { source_id: "10000000-0000-4000-8000-000000000002", title: "Borough food strategy consultation", year: 2023, venue: "Tower Hamlets Council", origin: "Overton", status: "screened_out", status_reason: "Not an evaluative source", cited: false },
  { source_id: "10000000-0000-4000-8000-000000000003", title: "Universal breakfast clubs and diet quality", year: 2022, venue: "BMJ Open", origin: "OpenAlex", status: "relevant", evidence_type: "Cohort study", cited: false },
  { source_id: "10000000-0000-4000-8000-000000000004", title: "Healthy High Streets programme review", year: 2023, venue: "London Assembly", origin: "Overton", status: "not_selected", status_reason: "Lower transferability", cited: false },
  { source_id: "10000000-0000-4000-8000-000000000005", title: "School meals and child weight outcomes", year: 2021, venue: "The Lancet Child & Adolescent Health", origin: "OpenAlex", status: "selected", evidence_type: "Systematic review", cited: false },
  { source_id: "10000000-0000-4000-8000-000000000006", title: "Neighbourhood food access and family choices", year: 2020, venue: "Health & Place", origin: "OpenAlex", status: "read_in_full", evidence_type: "Qualitative study", cited: false },
  { source_id: "10000000-0000-4000-8000-000000000007", title: "Active travel incentives: implementation findings", year: 2024, venue: "Local Government Studies", origin: "OpenAlex", status: "findings_extracted", evidence_type: "Mixed methods", cited: false },
  { source_id: "10000000-0000-4000-8000-000000000008", title: "Making healthy choices easier near schools", year: 2023, venue: "Nesta", origin: "Uploaded", status: "cited", evidence_type: "Policy analysis", cited: true },
  { source_id: "10000000-0000-4000-8000-000000000009", title: "Children's food environment survey", year: null, venue: null, origin: "Uploaded", status: "unavailable", status_reason: "Full text could not be obtained", cited: false },
];

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
    statistics: {},
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
  },
];

export const mockDecisions: components["schemas"]["DecisionOut"][] = [
  { sequence: 17, occurred_at: "2026-07-21T09:34:00Z", kind: "scope", summary: "Kept the focus on primary-school children and local policy levers.", decided_by: "user", detail: null },
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

export const mockCoverage: components["schemas"]["CoverageOut"] = {
  sentence: "Coverage is adequate for school-food and family-support approaches (46 screened-in sources, 2019–2024), while local active-travel evaluation evidence remains thin.",
  base: { screened_in: 46, years: [2019, 2024] },
};
