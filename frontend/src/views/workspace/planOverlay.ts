import type { components } from "../../api/gen/types";

import { scopeChips } from "./planVocabulary";

type PlanDraft = components["schemas"]["PlanDraft"];
type PlanPatchIn = components["schemas"]["PlanPatchIn"];
type ScopeConstraints = NonNullable<PlanDraft["scope_constraints"]>;

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

function yearFromIso(iso?: string | null): string {
  if (iso == null || iso === "") return "";
  const match = /^(\d{4})/.exec(iso);
  return match ? match[1] : "";
}

function geographyFromConstraints(constraints?: ScopeConstraints | null): string {
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

/** Typed PATCH body for local document edits. */
export function overlayToPlanPatch(overlay: PlanOverlay): PlanPatchIn {
  const body: PlanPatchIn = {};
  if (overlay.question !== undefined) body.question = overlay.question.trim();
  if (overlay.backend_scope !== undefined) {
    body.backend_scope = overlay.backend_scope as PlanPatchIn["backend_scope"];
  }
  if (overlay.search_effort !== undefined) {
    body.search_effort = overlay.search_effort as PlanPatchIn["search_effort"];
  }
  if (overlay.analysis_depth !== undefined) {
    body.analysis_depth = overlay.analysis_depth as PlanPatchIn["analysis_depth"];
  }
  if (overlay.steering_mode !== undefined) {
    body.steering_mode = overlay.steering_mode as PlanPatchIn["steering_mode"];
  }
  if (overlay.screening_criteria !== undefined) body.screening_criteria = overlay.screening_criteria;
  if (overlay.published_after_year !== undefined) {
    body.published_after =
      overlay.published_after_year === "" ? "" : `${overlay.published_after_year}-01-01`;
  }
  if (overlay.published_before_year !== undefined) {
    body.published_before =
      overlay.published_before_year === "" ? "" : `${overlay.published_before_year}-12-31`;
  }
  if (overlay.geography !== undefined) body.geography = overlay.geography;
  return body;
}
