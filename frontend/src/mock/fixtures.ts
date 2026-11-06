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

type StageKey = components["schemas"]["StageStartedFrame"]["stage"];

/**
 * The server's stage copy, copied from `api/stage_vocabulary.py`
 * (`STAGE_PRESENTATION`, `STAGE_ROW`). There is no runtime import across the
 * boundary, so a change there is made here by hand (task 058, N26).
 */
export const STAGE_PRESENTATION: Record<StageKey, readonly [label: string, blurb: string]> = {
  acquire: ["Searching", "Querying the databases and collecting candidates."],
  screen: ["Screening", "Reading each abstract against the question."],
  classify: ["Classifying", "Labelling each source by its evidence type."],
  appraise: ["Classifying", "Scoring how much weight each source can bear."],
  ingest: ["Collecting the full texts", "Fetching each full text and making it searchable."],
  characterise: ["Mapping", "What the evidence covers, and where it is thin."],
  select: ["Shortlisting", "The strongest, most varied set for close reading."],
  extract: ["Extracting findings", "Each finding is pulled out with its exact quote."],
  group: ["Grouping findings", "Findings that answer the same question, together."],
  synthesise: ["Writing", "A cited report, checked claim by claim."],
  inherit: ["Reading the linked search", "Its documents and report join this task."],
  suggest: ["Suggesting options", "From your plan, the baseline and any linked report."],
  option_searches: ["Searching for each option", "One search per option."],
  extract_interventions: ["Reading the abstracts", "Which interventions each source covers."],
  longlist: ["Clustering into options", "Sources grouped into options. Options may be combined or added."],
  option_profile: ["Estimating what each option would take", "Cost, time, workforce and who decides, for each option."],
  constrain: ["Applying your constraints", "Each option checked against the plan's limits."],
  theme: ["Grouping into themes", "Included options grouped into themes."],
  shortlist: ["Shortlisting", "Proposing options for close reading."],
};

/** The server's `STAGE_COUNTS` (task 058, N17): the done row's counts, each
 *  with its noun, copied here so the mock's frames carry what the server's do. */
export const STAGE_COUNTS: Record<StageKey, ReadonlyArray<readonly [string, string]>> = {
  acquire: [["acquired", "found"]],
  screen: [["relevant", "relevant"]],
  classify: [["classified", "classified"]],
  appraise: [],
  ingest: [["ingested", "collected"]],
  characterise: [["theme_count", "themes"]],
  select: [["selected_count", "selected"]],
  extract: [["finding_count", "findings"]],
  group: [["group_count", "groups"]],
  synthesise: [["section_count", "sections"]],
  inherit: [["documents", "documents"]],
  suggest: [["suggested", "suggested"]],
  option_searches: [["total", "searches"], ["sources", "sources"]],
  extract_interventions: [["documents", "abstracts"]],
  longlist: [["options", "options"]],
  option_profile: [["profiled", "profiled"]],
  constrain: [["excluded", "excluded"]],
  theme: [["themes", "themes"]],
  shortlist: [["shortlisted", "shortlisted"]],
};

/** The card row each stage belongs to: classify and appraise share one row;
 *  search and screen are two rows (owner round 8, 2026-11-05). */
export const STAGE_ROW: Record<StageKey, string> = {
  acquire: "search",
  screen: "screen",
  classify: "categorise",
  appraise: "categorise",
  ingest: "ingest",
  characterise: "characterise",
  select: "select",
  extract: "extract",
  group: "group",
  synthesise: "synthesise",
  inherit: "inherit",
  suggest: "suggest",
  option_searches: "option_searches",
  extract_interventions: "extract_interventions",
  longlist: "longlist",
  option_profile: "option_profile",
  constrain: "constrain",
  theme: "theme",
  shortlist: "shortlist",
};

/** One plan step in the server's words: its label, blurb and row. */
function planStep(stage: StageKey): components["schemas"]["PlanStep"] {
  const [label, blurb] = STAGE_PRESENTATION[stage];
  return { stage, label, blurb, row: STAGE_ROW[stage] };
}

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
  links: [],
  // Task 045: what exists and what is active. No walk, no longlist yet.
  active_run: null,
  has_longlist: false,
};

/**
 * Task 058, round 10: the rest of the mock's task list, so the Tasks page has
 * more than one page (50 a page) and "Show more" shows. Fifty-five are the
 * signed-in owner's, six a colleague's (Organisation only), three archived
 * (the archived filter). All older than `mockTask`, which stays first. Only
 * their rows are served: opening one reads its row and nothing else.
 */
const OTHER_TASK_TOPICS = [
  "School streets and air quality",
  "Free school meals auto-enrolment",
  "Holiday activities and food",
  "Sugar levy reinvestment",
  "Healthy start voucher uptake",
  "Takeaway planning restrictions",
  "Family hubs and early years",
  "Active travel to secondary school",
];
export const mockOtherTasks: components["schemas"]["TaskOut"][] = Array.from({ length: 64 }, (_, index) => {
  const colleague = index >= 55 && index < 61;
  const archived = index >= 61;
  const day = new Date(Date.UTC(2026, 6, 17) - index * 86_400_000).toISOString();
  return {
    task_id: `20000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`,
    name: `${OTHER_TASK_TOPICS[index % OTHER_TASK_TOPICS.length]} ${Math.floor(index / OTHER_TASK_TOPICS.length) + 1}`,
    question: null,
    status: archived ? "archived" : "active",
    created_at: day,
    updated_at: day,
    archived_at: archived ? day : null,
    latest_run: null,
    visibility: "org",
    is_owner: !colleague,
    owner_display: colleague ? "Grace Hopper" : "Ada Lovelace",
    is_public: false,
    access: "full",
    project_ids: [],
    capability: "evidence_search",
    links: [],
    active_run: null,
    has_longlist: false,
  };
});

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
  archived_at: null,
  // Its newest member's update, or its own creation (round 12).
  last_activity_at: "2026-07-15T09:00:00Z",
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
export const MOCK_THEME_ID_HIGH_STREETS = "30000000-0000-4000-8000-000000000003";

/** Every landscape distribution totals 46: the screened-in, not found, count.
 *  "Family support" carries no `theme_id` on purpose — a legacy
 *  characterisation predating 028 strand 8, which the sources theme filter
 *  must omit rather than offer a selection that can never round-trip. */
export const mockLandscape: components["schemas"]["LandscapeOut"] = {
  evidence_types: {
    "Systematic Review and Meta-Analysis": 20,
    "Observational Research Studies": 14,
    "Policy Syntheses & Guidance Documents": 12,
  },
  years: { "2019": 6, "2020": 7, "2021": 9, "2022": 10, "2023": 8, "2024": 6 },
  themes: [
    { name: "School food environments", size: 19, description: "Meal standards, free breakfast, and food access.", theme_id: MOCK_THEME_ID_SCHOOL_FOOD },
    { name: "Active travel", size: 15, description: "Safer walking and cycling for the school journey.", theme_id: MOCK_THEME_ID_ACTIVE_TRAVEL },
    { name: "Family support", size: 6, description: "Affordable cooking and community referral support." },
    // Round 9 (lead ruling): the four themes the live `characterise.themes`
    // frame names, in its order, so the handover neither reorders nor drops one.
    { name: "Healthy high streets", size: 6, description: "Food outlets and advertising around schools.", theme_id: MOCK_THEME_ID_HIGH_STREETS },
  ],
  // Publisher countries by the one name the server gives them (task 058,
  // round 10): each row links to All sources filtered by that value, and the
  // mock sources carry the same countries.
  geographies: { "United Kingdom": 30, "United States": 8, Netherlands: 3, "Not reported": 5 },
};

export const mockEvidence: components["schemas"]["EvidenceItemOut"][] = [
  { source_id: "10000000-0000-4000-8000-000000000001", title: "Childhood obesity prevention in urban primary schools", year: 2024, venue: "Public Health Nutrition", origin: "OpenAlex", status: "found", cited: false, read_in_full: false, abstract: "A cluster trial of classroom activity and school-meal changes in urban primary schools, measuring BMI z-score over two years.", abstract_source: "provider", country: "United States" },
  { source_id: "10000000-0000-4000-8000-000000000002", title: "Borough food strategy consultation", year: 2023, venue: "Tower Hamlets Council", origin: "Overton", status: "screened_out", screen_status: "excluded_retracted", screen_confidence: 1, status_reason: "The record was retracted", cited: false, read_in_full: false, abstract: "The council's consultation on a borough food strategy, covering school food, takeaways near schools and community growing.", abstract_source: "provider", country: "United Kingdom" },
  { source_id: "10000000-0000-4000-8000-000000000003", title: "Universal breakfast clubs and diet quality", year: 2022, venue: "BMJ Open", origin: "OpenAlex", status: "relevant", evidence_type: "Cohort study", appraisal_tier: "Moderate confidence", screen_status: "relevant", screen_confidence: 0.91, screen_basis: "title_abstract", screen_stage: 2, screen_reason: "Universal breakfast provision is a primary-school food-environment exposure in scope.", classification_reason: "Prospective cohort following ten schools over two academic years.", url: "https://example.org/universal-breakfast", cited: false, read_in_full: false, abstract: "A cohort study of universal breakfast provision and regular breakfast consumption.", abstract_source: "provider", country: "United Kingdom" },
  { source_id: "10000000-0000-4000-8000-000000000004", title: "Healthy High Streets programme review", year: 2023, venue: "London Assembly", origin: "Overton", status: "not_selected", status_reason: "Lower transferability", evidence_type: "Unknown / Insufficient information", appraisal_tier: "Unrated", screen_status: "relevant", screen_confidence: 0.72, screen_reason: "Covers food-environment levers around schools, though at borough rather than school level.", cited: false, read_in_full: false, abstract: "A review of the Healthy High Streets programme: food outlets near schools, signage and local planning levers.", abstract_source: "provider", country: "United Kingdom" },
  { source_id: "10000000-0000-4000-8000-000000000005", title: "School meals and child weight outcomes", year: 2021, venue: "The Lancet Child & Adolescent Health", origin: "OpenAlex", status: "selected", evidence_type: "Systematic review", screen_status: "relevant", screen_confidence: 0.88, screen_reason: "Directly evaluates school-meal policies against child weight outcomes.", classification_reason: "Explicit systematic search and synthesis across 42 trials.", cited: false, read_in_full: false, abstract: "A systematic review of 42 trials of school-meal standards and their effect on child weight.", abstract_source: "provider", country: "United Kingdom" },
  { source_id: "10000000-0000-4000-8000-000000000006", title: "Neighbourhood food access and family choices", year: 2020, venue: "Health & Place", origin: "OpenAlex", status: "read_in_full", evidence_type: "Qualitative study", screen_status: "relevant", screen_confidence: 0.81, screen_reason: "Family food-choice mechanisms around primary schools are in scope.", cited: false, read_in_full: true, full_text_url: "https://example.org/neighbourhood-food-access.pdf", abstract: "Interviews with families on how food outlets near primary schools shape everyday food choices.", abstract_source: "provider", country: "Netherlands" },
  { source_id: "10000000-0000-4000-8000-000000000007", title: "Active travel incentives: implementation findings", year: 2024, venue: "Local Government Studies", origin: "OpenAlex", status: "findings_extracted", evidence_type: "Mixed methods", screen_status: "relevant", screen_confidence: 0.86, screen_reason: "Implementation evidence for an in-scope active-travel lever.", cited: false, read_in_full: true, full_text_url: "https://europepmc.org/article/PMC/PMC1234567", abstract: "A mixed-methods study of how councils implemented active-travel incentives for school journeys.", abstract_source: "provider", country: "United Kingdom" },
  { source_id: "10000000-0000-4000-8000-000000000008", title: "Making healthy choices easier near schools", year: 2023, venue: "Nesta", origin: "Uploaded", status: "cited", evidence_type: "Policy analysis", appraisal_tier: "Moderate", screen_status: "relevant", screen_confidence: 0.95, screen_reason: "Uploaded by the task owner; directly addresses the question.", classification_reason: "Argument-led policy analysis rather than primary data collection.", cited: true, read_in_full: true, abstract: "An AI-generated summary: measures near the school gate that make the healthy choice the easy choice.", abstract_source: "llm_description", country: "United Kingdom" },
  { source_id: "10000000-0000-4000-8000-000000000009", title: "Children's food environment survey", year: null, venue: null, origin: "Uploaded", status: "unavailable", status_reason: "Full text could not be obtained", screen_status: "relevant", screen_confidence: 0.79, screen_reason: "Survey coverage of children's food environments matches the scope.", cited: false, read_in_full: false, country: null },
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
  [mockEvidence[3].source_id]: [MOCK_THEME_ID_HIGH_STREETS],
};

/** What each coverage row's search returned, by its `query_id` (round 12):
 *  the mock's `GET /evidence?query=` keeps these rows. A key not listed
 *  stands for a search from before the ids were kept: an empty page. */
export const mockEvidenceByQuery: Record<number, string[]> = {
  101: [mockEvidence[0].source_id, mockEvidence[4].source_id],
  102: [mockEvidence[2].source_id, mockEvidence[5].source_id],
  103: [mockEvidence[6].source_id],
  104: [mockEvidence[1].source_id],
  105: [mockEvidence[3].source_id],
  110: [mockEvidence[2].source_id, mockEvidence[4].source_id, mockEvidence[6].source_id],
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
    unit: "Primary-school children, ages 5-11",
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
    unit: "Primary-school families",
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

/**
 * The History read model as the server writes it (task 058, round 10): each
 * line says what happened, to what, and who did it. The mock signs in as the
 * owner, so the owner's acts read "You"; Policy Atlas's acts name it; a
 * step's line needs no subject. A run's searches are one row whose detail
 * lists every query. Newest first, as the server pages it.
 */
const ADA = { actor_display: "Ada Lovelace", actor_is_viewer: true } as const;
const SYSTEM_ACT = { actor_display: null, actor_is_viewer: null } as const;
const mockSearchTerms = [
  "school food environment childhood obesity",
  "universal free school meals BMI",
  "breakfast clubs diet quality primary school",
  "active travel primary school children",
  "healthy high streets fast food outlets schools",
  "sugar-sweetened beverages school policy",
  "family cooking skills programme obesity",
  "local authority planning hot food takeaways",
  "school food standards evaluation",
  "whole-systems approach childhood obesity",
  "after-school physical activity provision",
  "children's food advertising restrictions",
];
export const mockDecisions: components["schemas"]["DecisionOut"][] = [
  { sequence: 31, occurred_at: "2026-07-21T10:12:00Z", kind: "task.renamed", summary: "You renamed the task to \u201cHealthier childhoods in Tower Hamlets\u201d.", decided_by: "user", detail: { actor: "mock-policy-lead", name_from: "Childhood obesity", name_to: "Healthier childhoods in Tower Hamlets" }, ...ADA },
  { sequence: 30, occurred_at: "2026-07-21T10:06:00Z", kind: "run.finished", summary: "Policy Atlas finished the run.", decided_by: null, detail: { status: "succeeded" }, capability_run_id: MOCK_RUN_ID, ...SYSTEM_ACT },
  { sequence: 29, occurred_at: "2026-07-21T10:05:30Z", kind: "component.completed", summary: "Writing finished: 7 sections.", decided_by: null, detail: { component: "synthesise", section_count: 7 }, capability_run_id: MOCK_RUN_ID, ...SYSTEM_ACT },
  { sequence: 27, occurred_at: "2026-07-21T09:58:00Z", kind: "component.skipped", summary: "Grouping findings skipped.", decided_by: null, detail: { component: "group" }, capability_run_id: MOCK_RUN_ID, ...SYSTEM_ACT },
  { sequence: 25, occurred_at: "2026-07-21T09:52:00Z", kind: "component.completed", summary: "Mapping finished: 7 themes.", decided_by: null, detail: { component: "characterise", theme_count: 7 }, capability_run_id: MOCK_RUN_ID, ...SYSTEM_ACT },
  { sequence: 23, occurred_at: "2026-07-21T09:47:00Z", kind: "component.completed", summary: "Collecting the full texts finished: 38 collected, 5 failed.", decided_by: null, detail: { component: "ingest_full_text", ingested: 38, fetch_failed: 4, parse_failed: 1 }, capability_run_id: MOCK_RUN_ID, ...SYSTEM_ACT },
  { sequence: 21, occurred_at: "2026-07-21T09:41:00Z", kind: "component.completed", summary: "Classifying finished: 118 sources.", decided_by: null, detail: { component: "classify", classified: 118 }, capability_run_id: MOCK_RUN_ID, ...SYSTEM_ACT },
  { sequence: 20, occurred_at: "2026-07-21T09:36:00Z", kind: "steering.decision", summary: "You chose \u201cLooks right, assess these\u201d at the check-in.", decided_by: "user", detail: { option_id: "continue", response: "continue" }, capability_run_id: MOCK_RUN_ID, ...ADA },
  { sequence: 19, occurred_at: "2026-07-21T09:34:10Z", kind: "run.parked", summary: "Policy Atlas paused for a check-in.", decided_by: null, detail: {}, capability_run_id: MOCK_RUN_ID, ...SYSTEM_ACT },
  { sequence: 18, occurred_at: "2026-07-21T09:34:00Z", kind: "component.completed", summary: "Screening finished: 118 of 312 relevant.", decided_by: null, detail: { component: "screen", screened: 312, relevant: 118, not_relevant: 194 }, capability_run_id: MOCK_RUN_ID, ...SYSTEM_ACT },
  { sequence: 17, occurred_at: "2026-07-21T09:32:30Z", kind: "component.completed", summary: "Searching finished: 312 sources found.", decided_by: null, detail: { component: "acquire", acquired: 312 }, capability_run_id: MOCK_RUN_ID, ...SYSTEM_ACT },
  {
    sequence: 5,
    occurred_at: "2026-07-21T09:31:10Z",
    kind: "search.executed",
    summary: `Searched with ${mockSearchTerms.length} queries: ${mockSearchTerms.slice(0, 5).map((term) => `\u201c${term}\u201d`).join(", ")} and ${mockSearchTerms.length - 5} more.`,
    decided_by: null,
    detail: { queries: mockSearchTerms },
    capability_run_id: MOCK_RUN_ID,
    ...SYSTEM_ACT,
  },
  { sequence: 2, occurred_at: "2026-07-21T09:30:05Z", kind: "run.opened", summary: "Policy Atlas started the run.", decided_by: null, detail: {}, capability_run_id: MOCK_RUN_ID, ...SYSTEM_ACT },
  { sequence: 1, occurred_at: "2026-07-21T09:30:00Z", kind: "plan.approved", summary: "You approved the plan.", decided_by: "user", detail: { version: 1 }, ...ADA },
];

/**
 * The Evidence search check-in after searching and screening: the real
 * `search_review` steer point (the runner pauses after `acquire` and writes
 * kind `steer_point`). Its options are the server's five, in the server's ids,
 * with the suggested one first and its reason in `why`. No floor trigger
 * fired, so `triggers` is empty, as it is on a pause the mode always takes
 * (task 058, N26; annex scene 12).
 */
export const mockCheckIn: components["schemas"]["CheckInOut"] = {
  check_in_id: MOCK_CHECK_IN_ID,
  kind: "steer_point",
  boundary: "after_component",
  component: "acquire",
  stage: "acquire",
  render: "Does this look right before I assess the sources?\n312 sources · 118 relevant · 2 rounds",
  options: [
    { id: "continue", label: "Looks right, assess these", description: "Screening starts on what came back.", requires_user_input: false, suggested: true, why: "Coverage matches the plan and the second round added little.", endorsement: null },
    { id: "deepen_search", label: "Search deeper", description: "One more round on the thin themes.", requires_user_input: false, suggested: false, why: null, endorsement: null },
    { id: "rescope_filters", label: "Change the search scope", description: "Opens a line to say what to change.", requires_user_input: true, suggested: false, why: null, endorsement: null },
    { id: "guide_queries", label: "Guide the queries", description: "Tell me what to search for.", requires_user_input: true, suggested: false, why: null, endorsement: null },
    { id: "abort", label: "Stop the run", description: "Abort the remaining walk; prior component work is preserved.", requires_user_input: false, suggested: false, why: null, endorsement: null },
  ],
  triggers: [],
  bundle: {
    backends: ["openalex", "overton"],
    queries: ["free childcare take-up low-income families", "childcare entitlement outreach evaluation"],
    sample_titles: [mockEvidence[0].title, mockEvidence[1].title],
  },
  segment_reentry_allowed: true,
  rerun_component: "acquire",
  status: "pending",
  created_at: "2026-07-21T09:42:00Z",
  sequence: 42,
};

/** The sentence the judge fails in section 1, and its repaired wording: one
 *  number differs (task 058, N26). */
const MOCK_SECTION_ONE_LEAD =
  "Pair school food action with safer active-travel routes and practical family support, while monitoring local reach.";
const MOCK_SECTION_ONE_FAILED = "Schools that added a walking bus saw 8 more children arrive on foot in every 100.";
const MOCK_SECTION_ONE_REPAIRED = "Schools that added a walking bus saw 6 more children arrive on foot in every 100.";

/** What the writer streams: section 1 as drafted, before the check. */
export const mockArtefactSectionProse: Record<number, string> = {
  0: "Universal breakfast provision can support more consistent breakfast consumption when access is non-stigmatising.",
  1: `${MOCK_SECTION_ONE_LEAD} ${MOCK_SECTION_ONE_FAILED}`,
};

/** Section 1 as stored once the repair lands: the same text with the failed
 *  sentence's number changed. */
export const mockArtefactSectionRepairedProse: Record<number, string> = {
  ...mockArtefactSectionProse,
  1: `${MOCK_SECTION_ONE_LEAD} ${MOCK_SECTION_ONE_REPAIRED}`,
};

/** The code-point span `[start, end)` of the failed sentence in the drafted
 *  section 1, as `artefact.section_revising` carries it. */
export const mockSectionOneRevisingSpan: { start: number; end: number } = (() => {
  const start = mockArtefactSectionProse[1].indexOf(MOCK_SECTION_ONE_FAILED);
  return { start, end: start + MOCK_SECTION_ONE_FAILED.length };
})();

/** The sources the writer reads for section 1, as `artefact.section_sources`
 *  carries them (task 058, evidence shown live): the first read returns two,
 *  the second adds three more. Short names where the source has an author or
 *  publisher and a year; one long title the page cuts. */
export const mockSectionOneSources: { source_id: string; title: string }[][] = [
  [
    { source_id: "00000000-0000-4000-8000-0000000051a1", title: "Smith 2023" },
    { source_id: "00000000-0000-4000-8000-0000000051a2", title: "DfE 2022" },
  ],
  [
    { source_id: "00000000-0000-4000-8000-0000000051a1", title: "Smith 2023" },
    { source_id: "00000000-0000-4000-8000-0000000051a2", title: "DfE 2022" },
    { source_id: "00000000-0000-4000-8000-0000000051a3", title: "Nesta 2021" },
    {
      source_id: "00000000-0000-4000-8000-0000000051a4",
      title: "Walking school buses and active travel to school: a mixed-methods evaluation",
    },
    { source_id: "00000000-0000-4000-8000-0000000051a5", title: "Sustrans 2020" },
  ],
];

/** The writer's own citations in the drafted section 1, as
 *  `artefact.section_claim` carries them: the lead sentence and the sentence
 *  the judge later fails, each with the sources it cites. */
export const mockSectionOneClaims: { start: number; end: number; sources: { source_id: string; title: string }[] }[] = [
  {
    start: 0,
    end: MOCK_SECTION_ONE_LEAD.length,
    sources: [
      { source_id: "00000000-0000-4000-8000-0000000051a1", title: "Smith 2023" },
      { source_id: "00000000-0000-4000-8000-0000000051a2", title: "DfE 2022" },
    ],
  },
  {
    ...mockSectionOneRevisingSpan,
    sources: [{ source_id: "00000000-0000-4000-8000-0000000051a5", title: "Sustrans 2020" }],
  },
];

/** The case-study cards the writer streams (task 058, round 7), as
 *  `artefact.section_card` carries them, and as the committed report keeps
 *  them. */
export const mockCaseStudyCards: { title: string; prose: string }[] = [
  {
    title: "Leeds — Breakfast in every primary",
    prose: "Leeds offered a free breakfast in all primary schools from 2019. More pupils ate breakfast at school in the first year.",
  },
  {
    title: "Bristol — Walking bus pilots",
    prose: "Bristol ran walking buses at twelve schools for two terms. Parents reported calmer mornings and more children arriving on foot.",
  },
];

/** The case-studies block's prose as `artefact.section_completed` carries it:
 *  each card as its bold title line and text, cards a blank line apart. */
export const mockCaseStudiesProse = mockCaseStudyCards
  .map((card) => `**${card.title}**\n${card.prose}`)
  .join("\n\n");

/** One citation claim of the mock report, with the span and reference number
 *  the live page shows before the swap (task 058, round 7). */
interface MockCitedClaim {
  claimId: string;
  text: string;
  span: [number, number];
  cites: { citationId: string; n: number; source: components["schemas"]["EvidenceItemOut"]; quote: string }[];
}

function mockSpan(prose: string, text: string): [number, number] {
  const start = prose.indexOf(text);
  if (start < 0) throw new Error(`mock span not found: ${text}`);
  return [start, start + text.length];
}

/** The streamed body section's citations: the end of the lead sentence cites
 *  reference 2; the repaired sentence cites references 2 and 3. */
const MOCK_BODY_CITED: MockCitedClaim[] = [
  {
    claimId: "40000000-0000-4000-8000-000000000003",
    text: "while monitoring local reach",
    span: mockSpan(mockArtefactSectionRepairedProse[1], "while monitoring local reach"),
    cites: [{ citationId: "50000000-0000-4000-8000-000000000002", n: 2, source: mockEvidence[4], quote: "Effects depended on how many eligible children took the meal up." }],
  },
  {
    claimId: "40000000-0000-4000-8000-000000000004",
    text: MOCK_SECTION_ONE_REPAIRED,
    span: mockSpan(mockArtefactSectionRepairedProse[1], MOCK_SECTION_ONE_REPAIRED),
    cites: [
      { citationId: "50000000-0000-4000-8000-000000000003", n: 2, source: mockEvidence[4], quote: "Walking-bus schools reported six more pupils in every hundred arriving on foot." },
      { citationId: "50000000-0000-4000-8000-000000000004", n: 3, source: mockEvidence[3], quote: "Safer routes raised the share of children walking to school." },
    ],
  },
];

/** The case studies' one citation: the first card's result cites reference 2. */
const MOCK_CASE_STUDY_RESULT = "More pupils ate breakfast at school in the first year.";
const MOCK_CASE_STUDIES_CITED: MockCitedClaim = {
  claimId: "40000000-0000-4000-8000-000000000005",
  text: MOCK_CASE_STUDY_RESULT,
  span: mockSpan(mockCaseStudiesProse, MOCK_CASE_STUDY_RESULT),
  cites: [{ citationId: "50000000-0000-4000-8000-000000000005", n: 2, source: mockEvidence[4], quote: "Breakfast uptake rose in the first year of universal provision." }],
};

function mockClaimOut(claim: MockCitedClaim, span: [number, number] = claim.span): components["schemas"]["ClaimOut"] {
  return {
    claim_id: claim.claimId,
    claim_type: "citation",
    text: claim.text,
    span,
    citations: claim.cites.map((cite) => ({
      citation_id: cite.citationId,
      n: cite.n,
      source_id: cite.source.source_id,
      source_title: cite.source.title,
      quote: cite.quote,
      grounding_tier: "tier_2",
    })),
  };
}

function mockLiveCitations(claims: MockCitedClaim[]): components["schemas"]["SectionCitation"][] {
  return claims.flatMap((claim) =>
    claim.cites.map((cite) => ({
      start: claim.span[0],
      end: claim.span[1],
      n: cite.n,
      source_id: cite.source.source_id,
      title: cite.source.title,
      tier: "tier_2",
      // Round 8: the committed report's ids (the mock answers the chunk
      // context for any citation id) and the checked quote.
      citation_id: cite.citationId,
      claim_id: claim.claimId,
      quote: cite.quote,
    })),
  );
}

/** The full report's introduction as the writer streams it into the `intro`
 *  slot and as the committed report keeps it (task 058, round 8). */
export const MOCK_FULL_REPORT_INTRO =
  "The report first sets out what local action the evidence supports, then turns to the programmes that show it working in practice.";

/** The search's queries as `search.query` carries them (task 058, round 9):
 *  the five topic queries the coverage record lists after the stage, each
 *  sent then back with its count, then one citations pass described in
 *  words. `found` is the activity line's running count once each is back. */
export const mockSearchQueries: {
  backend: "openalex" | "overton";
  query: string;
  kind: "topic" | "semantic" | "citations" | "lookup";
  results: number;
  found: number;
}[] = [
  { backend: "openalex", query: "childhood obesity school intervention UK", kind: "topic", results: 34, found: 34 },
  { backend: "openalex", query: "primary school food environment obesity", kind: "topic", results: 28, found: 62 },
  { backend: "overton", query: "Tower Hamlets school food policy", kind: "topic", results: 19, found: 81 },
  { backend: "openalex", query: "active travel school children obesity", kind: "topic", results: 24, found: 105 },
  { backend: "overton", query: "UK childhood obesity local strategy", kind: "topic", results: 23, found: 128 },
  { backend: "openalex", query: "Following citations from 50 sources", kind: "citations", results: 184, found: 312 },
];

/** The themes as `characterise.themes` carries them once found, before the
 *  sources are assigned (task 058, round 9): the saved landscape's four, in
 *  its order and with its words, so the handover to the saved themes (with
 *  their counts) neither reorders nor drops one. */
export const mockLiveThemes: { label: string; description: string | null }[] = (mockLandscape.themes ?? []).map(
  (theme) => ({ label: theme.name, description: theme.description ?? null }),
);

/** The most-relevant-source notes as `artefact.source_note` carries them, in
 *  the order written, and as the committed report keeps them (round 8). Each
 *  `short` is the source's name on the activity line. */
export const mockSourceNotes: { sourceId: string; title: string; short: string; note: string }[] = [
  {
    sourceId: mockEvidence[4].source_id,
    title: mockEvidence[4].title,
    short: "Lancet 2021",
    note: "A systematic review of 42 trials linking school-meal policies to child weight outcomes.",
  },
  {
    sourceId: mockEvidence[3].source_id,
    title: mockEvidence[3].title,
    short: "London Assembly 2023",
    note: "A borough-level review of food-environment levers around schools, including safer routes.",
  },
];

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
      title: "Case studies",
      role: "case_studies",
      blocks: [{
        block_id: "30000000-0000-4000-8000-000000000003",
        prose: mockCaseStudiesProse,
        claims: [mockClaimOut(MOCK_CASE_STUDIES_CITED)],
      }],
      cards: mockCaseStudyCards.map((card, position) => ({
        card_id: `60000000-0000-4000-8000-00000000000${position + 1}`,
        title: card.title,
        prose: card.prose,
        claims:
          position === 0
            ? [mockClaimOut(MOCK_CASE_STUDIES_CITED, mockSpan(card.prose, MOCK_CASE_STUDY_RESULT))]
            : [],
        result_claim_id: position === 0 ? MOCK_CASE_STUDIES_CITED.claimId : null,
      })),
    },
    {
      title: "Implications for local action",
      role: "conclusions",
      blocks: [{
        block_id: "30000000-0000-4000-8000-000000000002",
        prose: mockArtefactSectionRepairedProse[1],
        claims: [{ claim_id: "40000000-0000-4000-8000-000000000002", claim_type: "pattern", text: "Pair school food action with safer active-travel routes", span: [0, 56], theme: { source: "grouping", base: "Co-occurrence across the screened-in corpus", items: [{ name: "Active-travel offers", description: "Route-safety and arrival-routine measures that families adopt alongside food provision.", size: 5, facet: "Intervention type", sources: [{ source_id: mockEvidence[0].source_id, title: mockEvidence[0].title }, { source_id: mockEvidence[1].source_id, title: mockEvidence[1].title }] }] } }, ...MOCK_BODY_CITED.map((claim) => mockClaimOut(claim))],
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
  }, {
    n: 2,
    title: mockEvidence[4].title,
    year: mockEvidence[4].year,
    venue: mockEvidence[4].venue,
    url: null,
  }, {
    n: 3,
    title: mockEvidence[3].title,
    year: mockEvidence[3].year,
    venue: mockEvidence[3].venue,
    url: null,
  }],
  full_report_intro: MOCK_FULL_REPORT_INTRO,
  most_relevant_notes: mockSourceNotes.map(({ sourceId, note }) => ({ source_id: sourceId, note })),
};

/** The live-artefact skeleton (contract strand 13), display-index ordered —
 *  same titles/prose as `mockArtefact` so the streamed and committed pages
 *  read as one continuous document. Each slot names its role; the
 *  case-studies slot follows the body sections and the introduction's slot
 *  comes last, as the server numbers them (task 058, rounds 7 and 8). The
 *  page shows the introduction by its role, before the body sections. */
export const mockArtefactSkeleton: components["schemas"]["ArtefactSectionSkeleton"][] = [
  { index: 0, title: "What appears to help", focus: "What the evidence shows helps, headline first.", role: "key_findings" },
  { index: 1, title: "Implications for local action", focus: "What this means for local decisions.", role: "body" },
  { index: 2, title: "Case studies", focus: "Relevant examples from the cited evidence.", role: "case_studies" },
  { index: 3, title: "Full report", focus: "", role: "intro" },
];

/** The case-studies slot's display index in the mock skeleton. */
export const MOCK_CASE_STUDIES_INDEX = 2;
/** The introduction slot's display index in the mock skeleton (round 8). */
export const MOCK_INTRO_INDEX = 3;
/** The key findings' writer's citation as `artefact.section_claim` carries it
 *  while the block streams (round 8): the span the judge later keeps. */
export const mockKeyFindingsClaim = {
  start: 34,
  end: 79,
  sources: [{ source_id: mockEvidence[2].source_id, title: "BMJ Open 2022" }],
};
/** The display index of the section the mock writer streams (its prose is
 *  `mockArtefactSectionProse[1]`). */
export const MOCK_STREAMED_SECTION_INDEX = 1;

/** Each completed section's checked citations, as `artefact.section_completed`
 *  carries them (task 058, round 7), keyed by display index. The numbers and
 *  spans match `mockArtefact`: the key findings cite reference 1; the
 *  implications cite 2, then 2 and 3; the case studies cite 2. */
export const mockSectionCitations: Record<number, components["schemas"]["SectionCitation"][]> = {
  0: [
    {
      start: 34,
      end: 79,
      n: 1,
      source_id: mockEvidence[2].source_id,
      title: mockEvidence[2].title,
      tier: "tier_2",
      citation_id: "50000000-0000-4000-8000-000000000001",
      claim_id: "40000000-0000-4000-8000-000000000001",
      quote: "Breakfast participation increased when provision was universal.",
    },
  ],
  [MOCK_STREAMED_SECTION_INDEX]: mockLiveCitations(MOCK_BODY_CITED),
  [MOCK_CASE_STUDIES_INDEX]: mockLiveCitations([MOCK_CASE_STUDIES_CITED]),
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
 * (`api/read_models/repository.py`). The section ORDER is what puts Sources
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
      results: 270,
      relevant: 30,
      // `query_id` (round 12): the key `GET /evidence?query=` takes.
      queries: [
        { query: "childhood obesity school intervention UK", results: 34, query_id: 101 },
        { query: "primary school food environment obesity", results: 28, query_id: 102 },
        { query: "active travel school children obesity", results: 24, query_id: 103 },
      ],
      // The live search's citations pass, worded for a finished search
      // (round 11): the saved coverage names its passes in the order run.
      passes: [{ pass: "citations", query: "Followed citations from 50 sources", results: 184, query_id: 110 }],
    },
    {
      backend: "Overton",
      results: 42,
      relevant: 16,
      queries: [
        { query: "Tower Hamlets school food policy", results: 19, query_id: 104 },
        { query: "UK childhood obesity local strategy", results: 23, query_id: 105 },
      ],
      passes: [],
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
  steps: (["acquire", "screen", "classify", "appraise", "characterise", "synthesise"] as const).map(planStep),
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
      kind: "boundary",
      origin: "your_call",
      checked_at: "longlist",
      country_group: null,
      published_after: null,
      published_before: null,
      languages: null,
      setting: false,
      default: null,
      aspect: null,
      hard: false,
    },
    {
      text: "Prefer options with a lower cost per participant",
      kind: "consideration",
      origin: "your_call",
      checked_at: "assessment",
      country_group: null,
      published_after: null,
      published_before: null,
      languages: null,
      setting: false,
      default: null,
      aspect: "cost",
      hard: false,
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
      aspect: null,
      hard: false,
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
      aspect: null,
      hard: false,
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
      row: "baseline",
      label: "Baseline",
      blurb:
        "What is in place, the trend, who is affected and what is contested, from Overton and OpenAlex. The run pauses for you to question it and confirm the plan.",
    },
    {
      stage: "acquire",
      row: "longlist",
      label: "Longlist",
      blurb:
        "Suggest options, search widely, read every abstract for the interventions it covers, cluster them into options, apply your constraints.",
    },
    {
      stage: "shortlist",
      row: "shortlist",
      label: "Shortlist",
      blurb:
        "Policy Atlas proposes about five places for close reading, one reason each, mixed to your risk appetite. Add, remove, ask for more. Assessment of the shortlisted options is not in this release.",
    },
  ],
  time_band: "10-15 minutes",
  baseline_confirmed: null,
  risk_appetite: "mostly_tried",
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
      question: "Is the question as you want it, or do you want to narrow it?",
      suggestions: ["That's my question", "Narrow it"],
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
      question: null,
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
      question: null,
      suggestions: [],
      part: null,
      status: "failed",
      created_at: "2026-07-21T08:58:00Z",
      completed_at: "2026-07-21T08:58:03Z",
    },
  ];
}

// --- The planner's scripted conversation (task 058, N10; annex scene 11) ---

/** One scripted planner turn: the reply the stream types out, plus the
 *  structured part, question and quick replies the finished turn carries. */
export interface MockPlannerTurn {
  reply: string;
  question: string | null;
  suggestions: string[];
  part: components["schemas"]["PartProposalOut"] | null;
}

/**
 * The planner's reply for the nth turn of a fresh Evidence search task:
 * the question, then the scope, then the thoroughness. Any later turn is a
 * plain reply with no part. The time bands are the plan document's own.
 */
export function mockPlannerTurn(turnIndex: number): MockPlannerTurn {
  if (turnIndex <= 1) {
    const reply = "I can search for this. First, is the question as you want it, or do you want to narrow it?";
    return {
      reply,
      question: "Is the question as you want it, or do you want to narrow it?",
      suggestions: ["That's my question", "Narrow it"],
      part: {
        id: "question",
        step_label: "Plan · step 1 of 3 · Question",
        title: "Your question",
        body: mockTask.question ?? null,
        chips: null,
        options: [
          { id: "confirm", label: "That's my question", sub: null, primary: true, reason: "It names the outcome, the group and the setting." },
          { id: "refine", label: "Narrow it", sub: "Tell me what to add or leave out.", primary: false, reason: null },
        ],
      },
    };
  }
  if (turnIndex === 2) {
    return {
      reply: "Here is the scope I would use. Change any chip, or add one.",
      question: null,
      suggestions: [],
      part: {
        id: "scope",
        step_label: "Plan · step 2 of 3 · Scope",
        title: "Scope",
        body: null,
        chips: [
          { label: "Since 2016", kind: "date_range", value: '{"after": "2016-01-01", "before": null}' },
          { label: "UK", kind: "country_list", value: '["GB"]' },
          { label: "Low-income families", kind: "text", value: "Low-income families" },
        ],
        options: [
          { id: "confirm", label: "Looks right", sub: null, primary: true, reason: "These match your question and the usual evidence base." },
          { id: "change", label: "Add or change a constraint", sub: "Opens a line to type the change.", primary: false, reason: null },
        ],
      },
    };
  }
  if (turnIndex === 3) {
    return {
      reply: "How thorough should the search be?",
      question: null,
      suggestions: [],
      part: {
        id: "thoroughness",
        step_label: "Plan · step 3 of 3 · Thoroughness",
        title: "Thoroughness",
        body: null,
        chips: null,
        options: [
          { id: "rapid", label: "Rapid overview", sub: "Up to 150 documents. A short report of 3 sections. · ~5-10 min", primary: false, reason: null },
          { id: "standard", label: "Standard report", sub: "Up to 300 documents, about 15 read in full. A report of up to 8 sections. · ~10-20 min", primary: true, reason: null },
          { id: "detailed", label: "Detailed report", sub: "Up to 600 documents, about 25 read in full with their findings extracted. A report of up to 8 sections. · ~20-30 min", primary: false, reason: null },
        ],
      },
    };
  }
  return { reply: "Noted — I'll keep that in mind for the analysis.", question: null, suggestions: [], part: null };
}

// --- The options read while the longlist builds (task 058, N22; scene 15) ---

type OptionProgress = components["schemas"]["OptionProgressOut"];

/** The twelve suggested options, in scene 15's order. `foldedInto` names the
 *  option (by index) the clustering stage folds this one into. */
const MOCK_OPTION_SEEDS: ReadonlyArray<{
  name: string;
  description: string;
  origin: OptionProgress["origin"];
  foldedInto?: number;
}> = [
  { name: "Youth guarantee with a job or training offer within four months", description: "Every young person out of work for four months is offered a job, training or education.", origin: "from_evidence_search" },
  { name: "Wage subsidies for employers hiring under-25s", description: "Employers are paid towards the wages of a young person they take on.", origin: "from_evidence_search" },
  { name: "Expanded apprenticeship incentives", description: "Payments that make it cheaper for employers to offer apprenticeships.", origin: "suggested" },
  { name: "Careers advice in every secondary school", description: "A named careers adviser in each school, from year 9.", origin: "suggested" },
  { name: "Sector-based work academies", description: "Short training tied to a guaranteed interview in one sector.", origin: "suggested" },
  { name: "Mental health support in job centres", description: "A trained worker on site for young people who are out of work.", origin: "suggested" },
  { name: "Transport subsidies for young job seekers", description: "Free or cheaper travel to interviews and the first weeks of work.", origin: "suggested", foldedInto: 9 },
  { name: "Intermediate labour market programmes", description: "Paid, time-limited jobs with support, run by the local authority.", origin: "suggested" },
  { name: "Digital skills bootcamps", description: "Short, intensive courses in the digital skills employers ask for.", origin: "suggested" },
  { name: "Youth hubs co-located with Jobcentre Plus", description: "One local place for advice, training and work coaching.", origin: "suggested" },
  { name: "Enterprise allowance for young founders", description: "A weekly allowance while a young person starts a business.", origin: "added_by_you" },
  { name: "Conditionality reform for under-25s", description: "Changes to what young people on benefits must do to keep them.", origin: "added_by_you" },
];

/** The two options the clustering stage adds, found in the evidence. */
const MOCK_OPTION_ADDED: ReadonlyArray<{ name: string; description: string }> = [
  { name: "Employer-led pre-apprenticeship traineeships", description: "Employers run short placements that lead to an apprenticeship offer." },
  { name: "Benefit run-ons when a young person starts work", description: "Benefits keep being paid for a few weeks after a job starts." },
];

/** How many sources each option's search finds (140 to 410). */
const MOCK_OPTION_FOUND = [312, 240, 186, 405, 148, 270, 332, 160, 215, 380, 140, 296];

export function mockOptionId(index: number): string {
  return `b0000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`;
}

/** Child search run ids, distinct from the parent walk and from each other. */
export function mockChildRunId(index: number): string {
  return `b1000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`;
}

export const MOCK_OPTION_COUNT = MOCK_OPTION_SEEDS.length;

export function mockOptionFound(index: number): number {
  return MOCK_OPTION_FOUND[index];
}

/** Fresh rows as suggest writes them: all queued, none folded. */
export function seedMockOptionRows(): OptionProgress[] {
  return MOCK_OPTION_SEEDS.map((seed, index) => ({
    option_id: mockOptionId(index),
    name: seed.name,
    description: seed.description,
    origin: seed.origin,
    state: "included",
    merged_into_option_id: null,
    search_status: "queued",
    found: null,
  }));
}

/** The clustering stage's one change: a suggestion folds into a wider option,
 *  and two options found in the evidence join the end of the list. */
export function foldMockOptionRows(rows: OptionProgress[]): OptionProgress[] {
  const folded = rows.map((row, index) => {
    const into = MOCK_OPTION_SEEDS[index]?.foldedInto;
    return into === undefined ? row : { ...row, merged_into_option_id: mockOptionId(into) };
  });
  const added = MOCK_OPTION_ADDED.map((entry, offset): OptionProgress => ({
    option_id: mockOptionId(MOCK_OPTION_SEEDS.length + offset),
    name: entry.name,
    description: entry.description,
    origin: "clustered",
    state: "included",
    merged_into_option_id: null,
    search_status: "searched",
    found: null,
  }));
  return [...folded, ...added];
}

/** The stages after which the longlist read gains something, in order. */
export const MOCK_WALK_LONGLIST_STAGES = ["longlist", "option_profile", "constrain", "theme", "shortlist"] as const;
export type MockWalkLonglistStage = (typeof MOCK_WALK_LONGLIST_STAGES)[number];

/** Lever types handed to the walk's options in turn once they are profiled. */
const MOCK_WALK_LEVERS = ["provide a service", "subsidise", "regulate", "inform", "convene", "invest in infrastructure"];
/** Positions (among the live rows) of the two options the constrain stage excludes. */
const MOCK_WALK_EXCLUDED_AT = [5, 7];
/** Positions of the options the shortlist stage picks. */
const MOCK_WALK_SHORTLIST_AT = [0, 1, 3];

/**
 * `GET /longlist` while the walk builds: the same option ids as the options
 * read (folded rows left out, as the API leaves them), growing stage by stage.
 * `stage` is the last stage that completed. After `longlist` each row has its
 * document count only; `option_profile` adds the lever lines; `constrain`
 * excludes two options with a one-line reason; `theme` groups the included
 * options; `shortlist` marks the picks.
 */
export function mockWalkLonglist(
  rows: readonly OptionProgress[],
  stage: MockWalkLonglistStage,
): components["schemas"]["LonglistOut"] {
  const reached = (target: MockWalkLonglistStage) =>
    MOCK_WALK_LONGLIST_STAGES.indexOf(stage) >= MOCK_WALK_LONGLIST_STAGES.indexOf(target);
  const live = rows.filter((row) => row.merged_into_option_id == null);
  const options = live.map((row, position): OptionSummaryOutFixture => {
    const excluded = reached("constrain") && MOCK_WALK_EXCLUDED_AT.includes(position);
    const picked = reached("shortlist") && !excluded && MOCK_WALK_SHORTLIST_AT.includes(position);
    const profiled = reached("option_profile");
    return {
      option_id: row.option_id,
      name: row.name,
      description: row.description,
      outcomes_served: [],
      origin: row.origin,
      state: excluded ? "excluded" : "included",
      exclusion: excluded
        ? { by: "constrain", constraint: MOCK_LONGLIST_FUNDING_CONSTRAINT, reason: "A local authority cannot fund this directly." }
        : null,
      no_in_scope_evidence: false,
      primary_lever_type: profiled ? MOCK_WALK_LEVERS[position % MOCK_WALK_LEVERS.length] : null,
      lever_none_fits_reason: null,
      lever_reason: null,
      secondary_lever_types: [],
      ambition: profiled && position % 4 === 1 ? "more" : null,
      ambition_reason: profiled ? "Builds on what local teams already run rather than adding a new body." : null,
      profile: null,
      authority: null,
      taxonomy_version: "lever-types-v1",
      document_count: row.found ?? 0,
      evaluated_count: 0,
      relations: [],
      search_pending: false,
      evaluated_countries: [],
      outcomes_evaluated: 0,
      outcomes_total: 2,
      shortlist: picked ? { state: "proposed", reason: "Mock reason: names a fact on the card." } : null,
      maturity: null,
    };
  });
  const included = options.filter((option) => option.state === "included");
  const half = Math.ceil(included.length / 2);
  const themes = reached("theme")
    ? [
        {
          theme_id: MOCK_LONGLIST_THEME_ID_CONDITIONALITY,
          name: "Conditionality and support",
          description: "Options that attach an obligation or targeted help to the existing offer.",
          option_ids: included.slice(0, half).map((option) => option.option_id),
        },
        {
          theme_id: MOCK_LONGLIST_THEME_ID_UNIVERSAL_OFFER,
          name: "A universal offer",
          description: "A single, non-conditional offer replacing today's patchwork.",
          option_ids: included.slice(half).map((option) => option.option_id),
        },
      ]
    : [];
  const base = mockLonglist();
  return {
    ...base,
    counts: {
      options: options.length,
      themes: themes.length,
      included: included.length,
      excluded: options.length - included.length,
      no_in_scope: 0,
      none_fits: 0,
    },
    themes,
    unthemed_option_ids: reached("theme") ? [] : options.map((option) => option.option_id),
    options,
  };
}

/**
 * The finished longlist after a mock walk (task 058, round 10): the same
 * options the build showed, themed, as working cards (a card per option, so
 * the verbs and Suggest more act on them). Built from the build's last read.
 */
export function mockWalkOptionCards(
  built: components["schemas"]["LonglistOut"],
): components["schemas"]["OptionOut"][] {
  return (built.options ?? []).map((summary) => ({
    ...buildMockAddedOption(summary.name),
    ...summary,
    design: {
      name: summary.name,
      description: summary.description,
      design_features: [summary.name],
      outcomes_served: [],
      assumed: [],
      version: 1,
    },
    design_features: [summary.name],
    shortlist: summary.shortlist ?? null,
    maturity: summary.maturity ?? null,
  }));
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
    "Does the plan still look right now you have the baseline?",
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
      // The label the user sees, as the server sends it (N19); the mock
      // plan's appetite is `mostly_tried`.
      risk_appetite: "Balanced: mostly evaluated, plus one or two not yet evaluated",
    },
  },
  segment_reentry_allowed: false,
  rerun_component: "synthesise",
  status: "pending",
  created_at: "2026-07-21T09:44:00Z",
  sequence: 44,
};

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

const MOCK_LONGLIST_RESTRICTION_TEXT = "Evidence from the UK and other high-income countries only";
const MOCK_LONGLIST_FUNDING_CONSTRAINT = "Only include options a local authority can fund directly";
const MOCK_LONGLIST_COST_PREFERENCE = "Prefer options with a lower cost per participant";

type ProfileFixture = NonNullable<OptionOutFixture["profile"]>;

/** One nine-line profile for a longlist fixture: a sentence per line and a
 *  mark where the option stands out (`who_decides` and `dependencies` never
 *  carry one). */
function mockProfile(
  marks: Partial<Record<"cost" | "time_to_set_up" | "time_to_effect" | "workforce" | "coordination" | "delivery_complexity" | "potential_impact", "less" | "more">>,
  settings: string[],
  actsOn: string[] = [],
): ProfileFixture {
  const line = (key: ProfileFixture["lines"][number]["key"], sentence: string) => ({
    key,
    sentence,
    mark: key === "who_decides" || key === "dependencies" ? null : (marks[key] ?? null),
  });
  return {
    lines: [
      line("cost", "Costs are mostly staff time; no capital spend is reported."),
      line("time_to_set_up", "Local teams could start within a year using existing contracts."),
      line("time_to_effect", "Effects on the NEET rate show after about two years."),
      line("workforce", "Needs trained advisers in every area, drawn from current staff."),
      line("who_decides", "The local authority decides, with the Department for Work and Pensions consulted."),
      line("dependencies", "Depends on shared data between schools and Jobcentre Plus."),
      line("coordination", "Schools, Jobcentres and councils must agree who refers whom."),
      line("delivery_complexity", "One referral route; few moving parts once the data is shared."),
      line("potential_impact", "Moderate if it works: it targets late referral, a main driver of the baseline; would apply to 16 to 24 year olds, tried on 18 to 24 year olds; the records describe proposals only."),
    ],
    settings,
    // Whom it acts on directly, the setting call's words (round 12).
    acts_on: actsOn,
  };
}

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
    outcomes_served: ["NEET rate at 6 months"],
    origin: "clustered",
    state: "excluded",
    exclusion: {
      by: "constrain",
      constraint: MOCK_LONGLIST_FUNDING_CONSTRAINT,
      reason: "A local authority cannot withdraw a national benefit directly.",
    },
    no_in_scope_evidence: false,
    primary_lever_type: "enforce existing powers",
    lever_none_fits_reason: null,
    lever_reason: "The council withholds a benefit payment when a young person refuses an offer.",
    secondary_lever_types: ["regulate"],
    ambition: "more",
    ambition_reason: "Changes who is entitled to a national benefit, not just how it is delivered.",
    profile: mockProfile({ cost: "less", time_to_effect: "more", coordination: "more", potential_impact: "more" }, ["Jobcentre", "Secondary school"], ["young jobseekers", "work coaches", "councils"]),
    authority: {
      label: "needs_action_by",
      body: "the Department for Work and Pensions",
      reason: "The benefit is set nationally, so a council cannot change it alone.",
    },
    taxonomy_version: "lever-types-v1",
    document_count: 6,
    evaluated_count: 3,
    relations: [{ kind: "part_of", other_option_id: MOCK_OPTION_ID_PACKAGE, other_name: "Universal youth offer bundle" }],
    search_pending: false,
    run_id: MOCK_LONGLIST_RUN_ID,
    capability_run_id: MOCK_LONGLIST_WALK_ID,
    plan_version: 1,
    evaluated_countries: [{ country: "United Kingdom", documents: 2 }],
    outcomes_evaluated: 1,
    outcomes_total: 2,
    place_sentences: [
      { place: "United Kingdom", sentence: "One moderate local evaluation of the Benefit sanctions pilot in England measured the NEET rate at 6 months in 18-24 year-olds.", generated: true, where: true },
      { place: "Several countries", sentence: "1 strong systematic review with 18-24 year-olds, measuring NEET rate at 6 months.", generated: false, where: false },
    ],
    evidence: {
      outcome_counts: {
        evaluating_documents: 3,
        by_outcome: [{ outcome: "NEET rate at 6 months", documents: 3, evaluated: 3 }],
      },
    },
    judgements: [
      { constraint_id: "relevant", constraint_text: "Relevant to the stated outcomes", verdict: "passes", reason: "Targets the NEET rate directly." },
      { constraint_id: "distinct", constraint_text: "Distinct from the other options", verdict: "passes", reason: "No other option on the list withdraws benefits." },
      { constraint_id: "in_scope", constraint_text: "Within scope", verdict: "passes", reason: "Its evidence is drawn from the plan's country group." },
      { constraint_id: "req-1", constraint_text: MOCK_LONGLIST_FUNDING_CONSTRAINT, verdict: "breaks", reason: "A local authority cannot withdraw a national benefit directly." },
    ],
    guesses: [
      { constraint_id: "pref-1", constraint_text: MOCK_LONGLIST_COST_PREFERENCE, guess: "likely a low cost per participant", leaning: "likely_meets" },
    ],
    in_scope: null,
    documents: [
      { task_source_snapshot_id: "mock-doc-a1", title: "Conditionality and NEET outcomes: a local authority review", role: "evaluated", evidence_type: "Local evaluation", tier: "Moderate", year: 2022, authors: ["R. Hollis", "M. Okafor"], venue: "Local Government Studies", place: "United Kingdom", programme_name: "Benefit sanctions pilot", tried_on_kind: "18-24 year-olds", measured: "NEET rate at 6 months", place_detail: "England", records_count: 1 },
      { task_source_snapshot_id: "mock-doc-a2", title: "Benefit sanctions for young jobseekers: a systematic review", role: "evaluated", evidence_type: "Systematic review", tier: "Strong", year: 2020, authors: ["J. Fenwick", "L. Garcia", "P. Shah"], venue: "Campbell Systematic Reviews", place: "multiple countries", programme_name: null, tried_on_kind: "18-24 year-olds", measured: "NEET rate at 6 months", place_detail: null, records_count: 2 },
      { task_source_snapshot_id: null, title: "National activation policy briefing", role: "mentioned", evidence_type: "Policy analysis", tier: null, year: 2023, authors: ["Department for Work and Pensions"], venue: null, place: "United Kingdom", programme_name: null, tried_on_kind: null, measured: null, place_detail: null, records_count: 0 },
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
    outcomes_served: ["NEET rate at 6 months"],
    origin: "suggested",
    state: "included",
    exclusion: null,
    no_in_scope_evidence: true,
    primary_lever_type: "provide a service",
    lever_none_fits_reason: null,
    secondary_lever_types: [],
    ambition: null,
    ambition_reason: "Adds support alongside the existing offer rather than changing who runs it.",
    profile: mockProfile({ workforce: "more", time_to_set_up: "less" }, ["Secondary school"], ["pupils", "mentors"]),
    authority: {
      label: "within_your_power",
      body: null,
      reason: "A council can commission mentors through its existing school contracts.",
    },
    taxonomy_version: "lever-types-v1",
    document_count: 4,
    evaluated_count: 2,
    evaluated_countries: [
      { country: "Australia", documents: 1 },
      { country: "Canada", documents: 1 },
    ],
    place_sentences: [
      { place: "Australia", sentence: "1 limited local evaluation with secondary school pupils in Victoria, measuring school engagement.", generated: false, where: false },
      { place: "Canada", sentence: "One moderate local evaluation in Ontario measured the NEET rate at 6 months in pupils at risk of becoming NEET.", generated: true, where: false },
    ],
    outcomes_evaluated: 1,
    outcomes_total: 2,
    relations: [],
    search_pending: false,
    run_id: MOCK_LONGLIST_RUN_ID,
    capability_run_id: MOCK_LONGLIST_WALK_ID,
    plan_version: 1,
    evidence: {
    },
    judgements: [
      { constraint_id: "relevant", constraint_text: "Relevant to the stated outcomes", verdict: "passes", reason: "Targets pupils at risk of the NEET outcome." },
      { constraint_id: "distinct", constraint_text: "Distinct from the other options", verdict: "passes", reason: "No other option delivers one-to-one mentoring." },
      { constraint_id: "in_scope", constraint_text: "Within scope", verdict: "cannot_check", reason: "None of its documents pass the plan's evidence restriction." },
      { constraint_id: "req-1", constraint_text: MOCK_LONGLIST_FUNDING_CONSTRAINT, verdict: "passes", reason: "Delivered through the school's existing budget." },
    ],
    guesses: [
      { constraint_id: "pref-1", constraint_text: MOCK_LONGLIST_COST_PREFERENCE, guess: "likely a low cost per participant", leaning: "likely_meets" },
    ],
    in_scope: { restriction: MOCK_LONGLIST_RESTRICTION_TEXT, in_scope_documents: 0, documents: 4 },
    documents: [
      { task_source_snapshot_id: "mock-doc-b1", title: "Peer mentoring for at-risk pupils in Ontario schools", role: "evaluated", evidence_type: "Local evaluation", tier: "Moderate", year: 2019, authors: ["K. Tremblay"], venue: "Canadian Journal of Education", place: "Canada", programme_name: null, tried_on_kind: "pupils at risk of becoming NEET", measured: "NEET rate at 6 months", place_detail: "Ontario", records_count: 1 },
      { task_source_snapshot_id: "mock-doc-b2", title: "School mentoring and NEET risk: an Australian cohort study", role: "evaluated", evidence_type: "Local evaluation", tier: "Limited", year: 2021, authors: ["S. Nguyen", "D. Walsh"], venue: "Journal of Adolescence", place: "Australia", programme_name: null, tried_on_kind: "secondary school pupils", measured: "school engagement", place_detail: "Victoria", records_count: 1 },
      { task_source_snapshot_id: "mock-doc-b3", title: "Mentoring programmes for disengaged youth: a scoping review", role: "described", evidence_type: "Policy analysis", tier: null, year: 2018, authors: ["H. Price"], venue: "Youth Studies Review", place: "other", programme_name: null, tried_on_kind: "young people", measured: null, place_detail: "English-speaking countries", records_count: 1 },
      { task_source_snapshot_id: "mock-doc-b4", title: "Youth mentoring outcomes: unclear geography", role: "recommended", evidence_type: "Local evaluation", tier: "Moderate", year: null, authors: [], venue: null, place: "not stated", programme_name: null, tried_on_kind: "young people", measured: null, place_detail: null, records_count: 1 },
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
    outcomes_served: ["NEET rate at 6 months"],
    origin: "added_by_you",
    state: "included",
    exclusion: null,
    no_in_scope_evidence: false,
    primary_lever_type: null,
    lever_none_fits_reason: "The design bundles an offer, an obligation and a delivery channel — no single instrument fits yet.",
    secondary_lever_types: [],
    ambition: null,
    ambition_reason: null,
    profile: null,
    authority: null,
    taxonomy_version: "lever-types-v1",
    document_count: 0,
    evaluated_count: 0,
    evaluated_countries: [],
    outcomes_evaluated: 0,
    outcomes_total: 2,
    relations: [],
    search_pending: false,
    run_id: MOCK_LONGLIST_RUN_ID,
    capability_run_id: MOCK_LONGLIST_WALK_ID,
    plan_version: 1,
    evidence: {
    },
    judgements: [],
    guesses: [],
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
    outcomes_served: ["NEET rate at 6 months", "Sustained employment or training at 12 months"],
    origin: "suggested",
    state: "included",
    exclusion: null,
    no_in_scope_evidence: false,
    primary_lever_type: "regulate",
    lever_none_fits_reason: null,
    secondary_lever_types: ["provide a service"],
    ambition: "less",
    ambition_reason: "Reorganises the existing offer into one application rather than adding anything new.",
    profile: mockProfile({ cost: "less", delivery_complexity: "more", time_to_set_up: "less", potential_impact: "less" }, ["Jobcentre", "Community centre"], ["young people", "employers", "councils"]),
    authority: { label: "unclear", body: null, reason: "The sources do not say who could merge the application routes." },
    taxonomy_version: "lever-types-v1",
    document_count: 9,
    evaluated_count: 5,
    evaluated_countries: [{ country: "United Kingdom", documents: 3 }],
    place_sentences: [
      { place: "United Kingdom", sentence: "One very strong systematic review of the Youth Guarantee in England measured the NEET rate at 6 months in 18-24 year-olds.", generated: true, where: true },
      { place: "Place not stated", sentence: "One strong local evaluation measured sustained employment or training at 12 months in 16-24 year-olds.", generated: true, where: false },
    ],
    outcomes_evaluated: 2,
    outcomes_total: 2,
    relations: [{ kind: "has_part", other_option_id: MOCK_OPTION_ID_EXCLUDED, other_name: "National sanctions regime" }],
    search_pending: false,
    run_id: MOCK_LONGLIST_RUN_ID,
    capability_run_id: MOCK_LONGLIST_WALK_ID,
    plan_version: 1,
    evidence: {
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
    in_scope: null,
    documents: [
      { task_source_snapshot_id: "mock-doc-d1", title: "Single-application youth guarantees: a systematic review", role: "evaluated", evidence_type: "Systematic review", tier: "Very strong", year: 2024, authors: ["A. Brennan", "T. Iqbal"], venue: "Campbell Systematic Reviews", place: "United Kingdom", programme_name: "Youth Guarantee", tried_on_kind: "18-24 year-olds", measured: "NEET rate at 6 months", place_detail: "England", records_count: 1 },
      { task_source_snapshot_id: "mock-doc-d2", title: "Combining careers advice and apprenticeships: a local evaluation", role: "evaluated", evidence_type: "Local evaluation", tier: "Strong", year: 2021, authors: ["C. Morgan"], venue: "Learning and Work Institute", place: "multiple countries", programme_name: null, tried_on_kind: "16-24 year-olds", measured: "Sustained employment or training at 12 months", place_detail: null, records_count: 2 },
      { task_source_snapshot_id: "mock-doc-d3", title: "One-stop youth offers outside the UK: a policy analysis", role: "described", evidence_type: "Policy analysis", tier: "Moderate", year: 2017, authors: ["F. Becker", "U. Klein"], venue: null, place: "Germany", programme_name: "Jugendberufsagentur", tried_on_kind: "young people", measured: "apprenticeship starts", place_detail: "Hamburg", records_count: 1 },
    ],
  },
};

/** Project one option card down to the list/grid's summary shape (the same
 *  fields `GET /longlist` returns for each option). */
export function toLonglistOptionSummary(option: OptionOutFixture): OptionSummaryOutFixture {
  return {
    option_id: option.option_id,
    name: option.name,
    description: option.description,
    outcomes_served: option.outcomes_served,
    origin: option.origin,
    state: option.state,
    exclusion: option.exclusion,
    no_in_scope_evidence: option.no_in_scope_evidence,
    primary_lever_type: option.primary_lever_type,
    lever_none_fits_reason: option.lever_none_fits_reason,
    lever_reason: option.lever_reason,
    secondary_lever_types: option.secondary_lever_types,
    ambition: option.ambition,
    ambition_reason: option.ambition_reason,
    profile: option.profile,
    authority: option.authority,
    taxonomy_version: option.taxonomy_version,
    document_count: option.document_count,
    evaluated_count: option.evaluated_count,
    relations: option.relations,
    search_pending: option.search_pending,
    evaluated_countries: option.evaluated_countries,
    outcomes_evaluated: option.outcomes_evaluated,
    outcomes_total: option.outcomes_total,
    shortlist: option.shortlist ?? null,
    maturity: option.maturity ?? null,
  };
}

/** The shortlist's in-memory state (task 055, A17): the note, whether the
 *  proposal is stale against the plan's appetite, and the appetite the
 *  mock's plan holds. The shortlist routes in `api.ts` change it. */
export const mockShortlistState: { note: string | null; stale: boolean; inputsChanged: boolean } = {
  note: null,
  stale: false,
  inputsChanged: false,
};

/** Places the shortlist fills up to. */
export const MOCK_SHORTLIST_PLACES_TARGET = 5;

/** Put the shortlist fixtures back to where they start: one pick with a
 *  reason (the bundle), one place added by you, one pick set aside, a
 *  maturity rung on every option and a note. Runs at load and on
 *  `resetMockScenario`. */
export function resetMockShortlist() {
  const cards = mockLonglistOptionCards;
  cards[MOCK_OPTION_ID_PACKAGE].shortlist = { state: "proposed", reason: "Mock reason: names a fact on the card." };
  cards[MOCK_OPTION_ID_ADDED_BY_YOU].shortlist = { state: "added_by_you", reason: null };
  cards[MOCK_OPTION_ID_NO_IN_SCOPE].shortlist = { state: "set_aside", reason: null };
  cards[MOCK_OPTION_ID_EXCLUDED].shortlist = null;
  cards[MOCK_OPTION_ID_EXCLUDED].maturity = {
    rung: "evaluated",
    design_mix: "1 RCT, 2 observational",
    none_in_your_setting: false,
    latest_evaluation_year: 2021,
    stale: false,
  };
  cards[MOCK_OPTION_ID_NO_IN_SCOPE].maturity = {
    rung: "evaluated",
    design_mix: "2 observational",
    none_in_your_setting: true,
    latest_evaluation_year: 2016,
    stale: true,
  };
  cards[MOCK_OPTION_ID_ADDED_BY_YOU].maturity = {
    rung: "proposal_only",
    design_mix: "",
    none_in_your_setting: false,
    latest_evaluation_year: null,
    stale: false,
  };
  cards[MOCK_OPTION_ID_PACKAGE].maturity = {
    rung: "reviewed",
    design_mix: "1 systematic review, 4 observational",
    none_in_your_setting: false,
    latest_evaluation_year: 2023,
    stale: false,
  };
  for (const id of mockLonglistExtraOptionIds) mockLonglistOptionCards[id].shortlist = null;
  mockShortlistState.note = "Mock note: nothing here tackles the wider labour market.";
  mockShortlistState.stale = false;
  mockShortlistState.inputsChanged = false;
}

/** Option ids added by hand or by chat verb since the walk built the four
 *  fixture options above (`POST /options`, `mockFetch`) — always unthemed,
 *  like a real rebuild's new entrants. */
export const mockLonglistExtraOptionIds: string[] = [];
resetMockShortlist();

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
    outcomes_served: [],
    origin: "added_by_you",
    state: "included",
    exclusion: null,
    no_in_scope_evidence: false,
    primary_lever_type: null,
    lever_none_fits_reason: "Not yet typed — its option search hasn't returned.",
    secondary_lever_types: [],
    ambition: null,
    ambition_reason: null,
    profile: null,
    authority: null,
    taxonomy_version: "lever-types-v1",
    document_count: 0,
    evaluated_count: 0,
    evaluated_countries: [],
    outcomes_evaluated: 0,
    outcomes_total: 2,
    relations: [],
    search_pending: false,
    run_id: MOCK_LONGLIST_RUN_ID,
    capability_run_id: MOCK_LONGLIST_WALK_ID,
    plan_version: 1,
    evidence: {
    },
    judgements: [],
    guesses: [],
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
    counts: {
      options: options.length,
      themes: 2,
      included: options.filter((option) => option.state === "included").length,
      excluded: options.filter((option) => option.state === "excluded").length,
      no_in_scope: options.filter((option) => option.no_in_scope_evidence).length,
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
    // Mirrors backend lever_types.py (LEVER_TYPES, AMBITION_DEFINITIONS);
    // update alongside it.
    lever_type_definitions: [
      { key: "regulate", definition: "set or change rules, standards, bans, licensing or planning requirements" },
      { key: "provide a service", definition: "deliver or fund a service or programme directly to people" },
    ],
    // Every taxonomy version (task 046): mirrors backend lever_types.py's
    // LEVER_TYPES (v2, current) and LEVER_TYPES_V1 — update alongside it.
    lever_type_definitions_by_version: {
      lever_types_v2: [
        { key: "regulate", definition: "set or change rules, standards, bans, licensing or planning requirements" },
        {
          key: "subsidise",
          definition:
            "pay for, grant-fund, discount or otherwise lower the price of something for people, or fund a provider to deliver it",
        },
        { key: "tax or charge", definition: "raise the price of something through a tax, levy, fee or charge" },
        { key: "inform", definition: "give information, advice, campaigns, labelling or guidance to change behaviour" },
        {
          key: "provide a service",
          definition:
            "deliver a service or programme to people directly, by the state's own bodies and staff (a public service, a facility, a scheme run by a public body)",
        },
        { key: "enforce existing powers", definition: "apply, inspect or enforce rules and duties that already exist" },
        {
          key: "devolve",
          definition: "move a decision, budget or power to a lower tier of government or a local body",
        },
        {
          key: "change who runs the system",
          definition: "reorganise institutions, commissioning, ownership or accountability for a service",
        },
        {
          key: "build or change infrastructure",
          definition: "create or alter physical environments, routes, facilities or estates",
        },
        {
          key: "procure or commission",
          definition:
            "buy a service or goods from a provider, or use public purchasing or commissioning rules to change what is bought or from whom",
        },
      ],
      lever_types_v1: [
        { key: "regulate", definition: "set or change rules, standards, bans, licensing or planning requirements" },
        {
          key: "subsidise",
          definition:
            "pay for, grant-fund, discount or otherwise lower the price of something for people or providers",
        },
        { key: "tax or charge", definition: "raise the price of something through a tax, levy, fee or charge" },
        { key: "inform", definition: "give information, advice, campaigns, labelling or guidance to change behaviour" },
        {
          key: "provide a service",
          definition: "deliver or fund a service or programme directly to people (a scheme, a programme, a facility)",
        },
        { key: "enforce existing powers", definition: "apply, inspect or enforce rules and duties that already exist" },
        {
          key: "devolve",
          definition: "move a decision, budget or power to a lower tier of government or a local body",
        },
        {
          key: "change who runs the system",
          definition: "reorganise institutions, commissioning, ownership or accountability for a service",
        },
        {
          key: "build or change infrastructure",
          definition: "create or alter physical environments, routes, facilities or estates",
        },
        {
          key: "procure or commission",
          definition: "use public purchasing or commissioning rules to change what is bought or from whom",
        },
      ],
    },
    taxonomy_version: "lever-types-v1",
    depth_label: "scoping pass",
    shortlist: {
      note: mockShortlistState.note,
      provenance: {},
      places_target: MOCK_SHORTLIST_PLACES_TARGET,
      stale: mockShortlistState.stale,
    },
    plan_inputs_changed: mockShortlistState.inputsChanged,
  };
}
