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
  both: "Academic + policy (OpenAlex, Overton)",
};

export const SEARCH_EFFORT_LABEL: Record<string, string> = {
  rapid: "Rapid — top sources, fast pass",
  standard: "Standard — a balanced sweep",
  deep: "Deep — systematic-style sweep",
};

export const ANALYSIS_DEPTH_LABEL: Record<string, string> = {
  landscape: "Landscape — mapping the terrain",
  standard: "Standard — full write-up, every claim cited",
  deep: "Deep — the closest reading",
};

export const STEERING_MODE_LABEL: Record<string, string> = {
  frequent: "At every step",
  moderate: "When something needs your judgement",
  minimal: "Only if it can't proceed",
  unattended: "None — ask if you want them",
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
