import type { components } from "../../api/gen/types";

type PlanDraft = components["schemas"]["PlanDraft"];
type ScopeConstraints = NonNullable<PlanDraft["scope_constraints"]>;

/**
 * The locked plan vocabulary (RETRO §2; contract strand 2). Labels render
 * from these maps or from server-supplied strings — an unknown key OMITS its
 * surface, it never leaks a raw enum or a `replace(/_/g, " ")` fallback.
 */
export const SOURCES_LABEL: Record<string, string> = {
  academic_only: "Academic research (OpenAlex)",
  grey_lit_only: "Policy literature (Overton)",
  both: "Academic + Policy (OpenAlex, Overton)",
};

/**
 * Owner-set acquire caps (`record_cap_per_backend` in search_loop
 * DEPTH_CONSTANTS): documents kept per database per round.
 */
export const SEARCH_SCOPE_RECORD_CAP = {
  rapid: 50,
  standard: 100,
  deep: 200,
} as const;

/** Shortlist sizes from ``ANALYSIS_DEPTH_TABLE`` selection budgets. */
export const ANALYSIS_SHORTLIST_CAP = {
  standard: 15,
  deep: 25,
} as const;

/** Axis title for `search_effort` — how widely the databases are queried. */
export const SEARCH_SCOPE_TITLE = "Search scope";
export const SEARCH_SCOPE_HINT = [
  "How many relevant results each database may collect:",
  `Focused: up to ${SEARCH_SCOPE_RECORD_CAP.rapid} relevant results per database`,
  `Broad: up to ${SEARCH_SCOPE_RECORD_CAP.standard} relevant results per database`,
  `Broadest: up to ${SEARCH_SCOPE_RECORD_CAP.deep} relevant results per database`,
].join("\n");

export const SEARCH_EFFORT_LABEL: Record<string, string> = {
  rapid: "Focused",
  standard: "Broad",
  deep: "Broadest",
};

/** Axis title for `analysis_depth` — what happens after search. */
export const ANALYSIS_TITLE = "Analysis level";
export const ANALYSIS_QUESTION = [
  "Overview: Themes, coverage and gaps across the screened evidence",
  `Full-text synthesis: Synthesise about ${ANALYSIS_SHORTLIST_CAP.standard} shortlisted sources`,
  `Findings synthesis: Extract and synthesise findings from about ${ANALYSIS_SHORTLIST_CAP.deep} shortlisted sources`,
].join("\n");

export const ANALYSIS_DEPTH_LABEL: Record<string, string> = {
  landscape: "Evidence overview",
  standard: "Full-text synthesis",
  deep: "Findings synthesis",
};

/** Named diagonal pairings of search scope × analysis — the chat presets. */
export const RESEARCH_APPROACH_TITLE = "Thoroughness";
export const RESEARCH_APPROACH_HINT =
  "Standard combinations of Search scope and Analysis level. Choose one or make a custom combination using Search scope and Analysis level below.";
export const RESEARCH_APPROACH_CUSTOM = "Custom";

const RESEARCH_APPROACH_PRESETS: Record<
  string,
  { search_effort: string; analysis_depth: string; label: string }
> = {
  rapid_overview: { search_effort: "rapid", analysis_depth: "landscape", label: "Rapid overview" },
  standard_review: { search_effort: "standard", analysis_depth: "standard", label: "Standard report" },
  detailed_review: { search_effort: "deep", analysis_depth: "deep", label: "Detailed report" },
};

export const RESEARCH_APPROACH_PRESET_LABEL: Record<string, string> = Object.fromEntries(
  Object.entries(RESEARCH_APPROACH_PRESETS).map(([id, preset]) => [id, preset.label]),
);

/** Preset id for a search-scope × analysis pair, `custom` off-diagonal, or null if unset. */
export function researchApproachId(effort: string, depth: string): string | null {
  if (effort === "" || depth === "") return null;
  for (const [id, preset] of Object.entries(RESEARCH_APPROACH_PRESETS)) {
    if (preset.search_effort === effort && preset.analysis_depth === depth) return id;
  }
  return "custom";
}

/** Screen label for a search-scope × analysis pair. */
export function researchApproachLabel(effort: string, depth: string): string | null {
  const id = researchApproachId(effort, depth);
  if (id === null) return null;
  if (id === "custom") return RESEARCH_APPROACH_CUSTOM;
  return RESEARCH_APPROACH_PRESETS[id]?.label ?? null;
}

/** Axes compiled by a named research-approach preset. Unknown id → null. */
export function axesForResearchApproach(
  id: string,
): { search_effort: string; analysis_depth: string } | null {
  const preset = RESEARCH_APPROACH_PRESETS[id];
  if (preset === undefined) return null;
  return { search_effort: preset.search_effort, analysis_depth: preset.analysis_depth };
}

export const STEERING_MODE_LABEL: Record<string, string> = {
  frequent: "At every step",
  moderate: "When something needs your judgement",
  minimal: "Only if it can't proceed",
  unattended: "None",
};

/**
 * Display bands seeded from the runtime `TIME_BANDS` table — search effort
 * × analysis depth. Kept here so the plan panel can update the estimate
 * without a planner round-trip.
 */
const TIME_BANDS: Record<string, Record<string, string>> = {
  rapid: {
    landscape: "~10-15 min",
    standard: "~30-45 min",
    deep: "~75-90 min",
  },
  standard: {
    landscape: "~15-20 min",
    standard: "~10-20 min",
    deep: "~80-95 min",
  },
  deep: {
    landscape: "~20-25 min",
    standard: "~35-50 min",
    deep: "~90-100 min",
  },
};

export type PlanStepPreview = { stage: string; label: string; blurb: string };

const ALWAYS_STEPS: readonly PlanStepPreview[] = [
  { stage: "acquire", label: "Searching", blurb: "Querying academic and policy databases." },
  { stage: "screen", label: "Screening", blurb: "Checking title and abstract against your criteria." },
  { stage: "classify", label: "Sorting by evidence type", blurb: "Labelling each document by its evidence type." },
  { stage: "appraise", label: "Appraising", blurb: "Calculating evidence strength scores." },
];

const CHARACTERISE_STEP: PlanStepPreview = {
  stage: "characterise",
  label: "Mapping",
  blurb: "Assessing coverage and summarising themes.",
};
const SELECT_STEP: PlanStepPreview = {
  stage: "select",
  label: "Shortlisting",
  blurb: "Selecting the strongest and most varied set for close reading.",
};
const EXTRACT_STEP: PlanStepPreview = {
  stage: "extract",
  label: "Extracting findings",
  blurb: "Detailed extraction of interventions and outcomes.",
};
const GROUP_STEP: PlanStepPreview = {
  stage: "group",
  label: "Grouping findings",
  blurb: "Clustering findings into coherent groups.",
};
const SYNTHESISE_STEP: PlanStepPreview = {
  stage: "synthesise",
  label: "Writing",
  blurb: "Synthesising a report with citations.",
};

/** Searching-step blurb for the selected source libraries. */
export function acquireSearchBlurb(backendScope?: string | null): string {
  if (backendScope === "academic_only") return "Querying academic databases.";
  if (backendScope === "grey_lit_only") return "Querying policy databases.";
  return "Querying academic and policy databases.";
}

/** Public agreed-steps list for an analysis-depth rung — same collapse as the API. */
export function stepsForAnalysisDepth(
  depth: string,
  backendScope?: string | null,
): PlanStepPreview[] {
  const steps = ALWAYS_STEPS.map((step) =>
    step.stage === "acquire" ? { ...step, blurb: acquireSearchBlurb(backendScope) } : step,
  );
  if (depth === "landscape" || depth === "standard" || depth === "deep") {
    steps.push(CHARACTERISE_STEP);
  }
  if (depth === "standard" || depth === "deep") {
    steps.push(SELECT_STEP);
  }
  if (depth === "deep") {
    steps.push(EXTRACT_STEP, GROUP_STEP);
  }
  steps.push(SYNTHESISE_STEP);
  return steps;
}

/** Expected run-time band for a search-effort × analysis-depth pair. */
export function timeBandFor(effort: string, depth: string): string | null {
  return TIME_BANDS[effort]?.[depth] ?? null;
}

/** Run-block status labels for the planning thread's run divider ("Analysis
 *  run — running/paused/completed/…"). Unknown status → the caller omits. */
export const RUN_BLOCK_STATUS: Record<string, string> = {
  running: "running",
  paused: "paused",
  succeeded: "completed",
  degraded: "completed with gaps",
  failed: "failed",
  interrupted: "interrupted",
  aborted: "stopped",
};

/** Pre-ready component labels: the same public stage vocabulary the server's
 *  STAGE_PRESENTATION serves for approved-plan steps (D‑7b: the wire carries
 *  no steps before `ready`, so the pane lists the planned components). */
export const COMPONENT_LABEL: Record<string, string> = {
  characterise: "Mapping the landscape",
  screen_full: "Screening for relevance",
  select: "Shortlisting",
  extract: "Extracting findings",
  group: "Grouping findings",
};

/** Look a key up in a locked map. Unknown key → null (the caller omits). */
export function vocabLabel(map: Record<string, string>, key?: string | null): string | null {
  if (key === null || key === undefined) return null;
  return map[key] ?? null;
}

function yearOf(iso: string): string {
  const match = /^(\d{4})/.exec(iso);
  return match ? match[1] : iso;
}

/**
 * Constraint chips with the demo's geography-collapse rule: one user-facing
 * geography chip — the named country group when present (it covers both
 * search backends), otherwise the union of the backend-specific publisher
 * (Overton) and author-affiliation (OpenAlex) country filters.
 */
export function scopeChips(constraints?: ScopeConstraints | null): string[] {
  if (constraints === null || constraints === undefined) return [];
  const chips: string[] = [];
  if (constraints.published_after) chips.push(`Published after ${yearOf(constraints.published_after)}`);
  if (constraints.published_before) chips.push(`Published before ${yearOf(constraints.published_before)}`);
  const group = constraints.country_group;
  const geography = group
    ? group.label + (group.countries?.length ? ` (${group.countries.join(", ")})` : "")
    : [
        ...new Set(
          [constraints.publisher_country, ...(constraints.author_affiliation_countries ?? [])].filter(
            (value): value is string => typeof value === "string" && value.length > 0,
          ),
        ),
      ].join(", ");
  if (geography) chips.push(`Geography: ${geography}`);
  return chips;
}
