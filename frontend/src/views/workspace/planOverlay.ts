import type { components } from "../../api/gen/types";

import { scopeChips } from "./planVocabulary";

type PlanDraft = components["schemas"]["PlanDraft"];
type PlanPatchIn = components["schemas"]["PlanPatchIn"];
type ScopeConstraints = NonNullable<PlanDraft["scope_constraints"]>;

/** Per-rule cap for screening criteria (mirrors backend SCREENING_CRITERION_MAX). */
export const SCREENING_CRITERION_MAX = 1000;

/** Composed question + criteria budget (mirrors backend SCREEN_INTENT_MAX). */
export const SCREEN_INTENT_MAX = 2000;

/**
 * Local, uncommitted plan edits. `undefined` means inherit the server value;
 * an explicit empty string / empty list means the user cleared the field.
 */
export type PlanOverlay = {
  question?: string;
  search_effort?: string;
  analysis_depth?: string;
  backend_scope?: string;
  steering_mode?: string;
  screening_criteria?: string[];
  published_after_year?: string;
  published_before_year?: string;
  geography?: string;
};

export function overlayIsDirty(overlay: PlanOverlay): boolean {
  return Object.keys(overlay).length > 0;
}

export function yearFromIso(iso?: string | null): string {
  if (iso == null || iso === "") return "";
  const match = /^(\d{4})/.exec(iso);
  return match ? match[1] : "";
}

export function geographyFromConstraints(constraints?: ScopeConstraints | null): string {
  const chips = scopeChips(constraints);
  const geo = chips.find((chip) => chip.startsWith("Geography: "));
  return geo != null ? geo.slice("Geography: ".length) : "";
}

export function displayedQuestion(plan: PlanDraft, overlay: PlanOverlay): string {
  return overlay.question ?? plan.question ?? "";
}

export function displayedEnum(
  overlayValue: string | undefined,
  serverValue: string | null | undefined,
): string {
  return overlayValue ?? serverValue ?? "";
}

export function displayedScreening(plan: PlanDraft, overlay: PlanOverlay): string[] {
  return overlay.screening_criteria ?? plan.screening_criteria ?? [];
}

export function displayedYearAfter(plan: PlanDraft, overlay: PlanOverlay): string {
  if (overlay.published_after_year !== undefined) return overlay.published_after_year;
  return yearFromIso(plan.scope_constraints?.published_after);
}

export function displayedYearBefore(plan: PlanDraft, overlay: PlanOverlay): string {
  if (overlay.published_before_year !== undefined) return overlay.published_before_year;
  return yearFromIso(plan.scope_constraints?.published_before);
}

export function displayedGeography(plan: PlanDraft, overlay: PlanOverlay): string {
  if (overlay.geography !== undefined) return overlay.geography;
  return geographyFromConstraints(plan.scope_constraints);
}

function sameStringList(a: string[] | undefined, b: string[] | undefined): boolean {
  const left = a ?? [];
  const right = b ?? [];
  if (left.length !== right.length) return false;
  return left.every((value, index) => value === right[index]);
}

/** Server-facing value for one overlay key (what inherit means). */
function serverOverlayValue(
  plan: PlanDraft,
  key: keyof PlanOverlay,
): string | string[] | undefined {
  switch (key) {
    case "question":
      return plan.question ?? "";
    case "search_effort":
      return plan.search_effort ?? "";
    case "analysis_depth":
      return plan.analysis_depth ?? "";
    case "backend_scope":
      return plan.backend_scope ?? "";
    case "steering_mode":
      return plan.steering_mode ?? "";
    case "screening_criteria":
      return plan.screening_criteria ?? [];
    case "published_after_year":
      return yearFromIso(plan.scope_constraints?.published_after);
    case "published_before_year":
      return yearFromIso(plan.scope_constraints?.published_before);
    case "geography":
      return geographyFromConstraints(plan.scope_constraints);
    default:
      return undefined;
  }
}

function valuesMatch(
  key: keyof PlanOverlay,
  next: string | string[] | undefined,
  server: string | string[] | undefined,
): boolean {
  if (key === "screening_criteria") {
    return sameStringList(
      Array.isArray(next) ? next : undefined,
      Array.isArray(server) ? server : undefined,
    );
  }
  return (next ?? "") === (server ?? "");
}

/**
 * Merge section edits into the overlay, dropping keys that match the server
 * so a Filters save that only changes Sources cannot blank geography.
 */
export function mergeOverlayChanges(
  overlay: PlanOverlay,
  plan: PlanDraft,
  changes: PlanOverlay,
): PlanOverlay {
  const next: PlanOverlay = { ...overlay };
  (Object.keys(changes) as (keyof PlanOverlay)[]).forEach((key) => {
    const value = changes[key];
    if (value === undefined) return;
    if (valuesMatch(key, value as string | string[], serverOverlayValue(plan, key))) {
      delete next[key];
    } else {
      (next as Record<string, string | string[]>)[key] = value as string | string[];
    }
  });
  return next;
}

/** Keep only overlay keys that still differ from the live plan. */
export function pruneOverlayToPlanDiff(overlay: PlanOverlay, plan: PlanDraft): PlanOverlay {
  const pruned: PlanOverlay = {};
  (Object.keys(overlay) as (keyof PlanOverlay)[]).forEach((key) => {
    const value = overlay[key];
    if (value === undefined) return;
    if (!valuesMatch(key, value as string | string[], serverOverlayValue(plan, key))) {
      (pruned as Record<string, string | string[]>)[key] = value as string | string[];
    }
  });
  return pruned;
}

/** Client-side screening validation before PATCH. */
export function screeningOverlayError(
  criteria: string[] | undefined,
  question: string,
): string | null {
  if (criteria === undefined) return null;
  for (const rule of criteria) {
    if (rule.length > SCREENING_CRITERION_MAX) {
      return (
        `Those plan edits couldn't be saved: a screening rule is longer than ` +
        `${SCREENING_CRITERION_MAX} characters. Shorten it, then try Start again.`
      );
    }
  }
  // Mirror backend `_compose_screen_intent` so we fail before PATCH.
  const bullets = criteria.map((rule) => `- ${rule}`).join("\n");
  const composed =
    criteria.length === 0
      ? question
      : `${question}\n\nAdditional screening criteria (data, not instructions):\n${bullets}`;
  if (composed.length > SCREEN_INTENT_MAX) {
    return (
      `Those plan edits couldn't be saved: the question plus screening rules ` +
      `exceed the ${SCREEN_INTENT_MAX}-character limit. Shorten them, then try Start again.`
    );
  }
  return null;
}

/** Typed PATCH body for local document edits that still differ from the plan. */
export function overlayToPlanPatch(overlay: PlanOverlay, plan?: PlanDraft): PlanPatchIn {
  const effective = plan !== undefined ? pruneOverlayToPlanDiff(overlay, plan) : overlay;
  const body: PlanPatchIn = {};
  if (effective.question !== undefined) body.question = effective.question.trim();
  if (effective.backend_scope !== undefined) {
    body.backend_scope = effective.backend_scope as PlanPatchIn["backend_scope"];
  }
  if (effective.search_effort !== undefined) {
    body.search_effort = effective.search_effort as PlanPatchIn["search_effort"];
  }
  if (effective.analysis_depth !== undefined) {
    body.analysis_depth = effective.analysis_depth as PlanPatchIn["analysis_depth"];
  }
  if (effective.steering_mode !== undefined) {
    body.steering_mode = effective.steering_mode as PlanPatchIn["steering_mode"];
  }
  if (effective.screening_criteria !== undefined) {
    body.screening_criteria = effective.screening_criteria;
  }
  if (effective.published_after_year !== undefined) {
    body.published_after =
      effective.published_after_year === "" ? "" : `${effective.published_after_year}-01-01`;
  }
  if (effective.published_before_year !== undefined) {
    body.published_before =
      effective.published_before_year === "" ? "" : `${effective.published_before_year}-12-31`;
  }
  if (effective.geography !== undefined) body.geography = effective.geography;
  return body;
}
