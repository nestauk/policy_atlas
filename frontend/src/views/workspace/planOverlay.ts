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

/** Per-criterion cap (mirrors backend `SCREENING_CRITERION_MAX`, screen.py). */
export const SCREENING_CRITERION_MAX = 1000;
/** Composed question+criteria cap (mirrors backend `SCREEN_INTENT_MAX`, screen_prompt.py). */
export const SCREEN_INTENT_MAX = 2000;
/** List cap (mirrors backend `CRITERIA_LIST_MAX`, screen.py). */
export const SCREENING_CRITERIA_LIST_MAX = 50;

/** Character count the way the backend's `len()` counts — Unicode code
 *  points, not UTF-16 units (`"💊".length` is 2; the backend counts 1). */
function charCount(text: string): number {
  return [...text].length;
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

function valuesEqual(a: string | string[] | undefined, b: string | string[] | undefined): boolean {
  if (Array.isArray(a)) {
    const bList = Array.isArray(b) ? b : [];
    return a.length === bList.length && a.every((item, index) => item === bList[index]);
  }
  if (Array.isArray(b)) return false;
  return (a ?? "") === (b ?? "");
}

/** The server's displayed value for `key`, ignoring any local overlay — the
 *  baseline a dirty-only overlay diffs against. Reuses the same
 *  `displayed*` helpers the read side already trusts (an empty overlay
 *  makes them read the plan alone). */
function serverDisplayedValue(key: keyof PlanOverlay, plan: PlanDraft): string | string[] {
  switch (key) {
    case "question":
      return displayedQuestion(plan, {});
    case "search_effort":
      return displayedEnum(undefined, plan.search_effort);
    case "analysis_depth":
      return displayedEnum(undefined, plan.analysis_depth);
    case "backend_scope":
      return displayedEnum(undefined, plan.backend_scope);
    case "steering_mode":
      return displayedEnum(undefined, plan.steering_mode);
    case "screening_criteria":
      return displayedScreening(plan, {});
    case "published_after_year":
      return displayedYearAfter(plan, {});
    case "published_before_year":
      return displayedYearBefore(plan, {});
    case "geography":
      return displayedGeography(plan, {});
  }
}

/**
 * Fold `changes` into `overlay`, dropping any key whose new value matches
 * the server plan's own displayed value (the plan feeds the read side, so a
 * clean-again field must vanish from the overlay rather than freeze at
 * whatever the server already has). Keys not present in `changes` pass
 * through unchanged.
 *
 * This is what stops a Sources-only save from writing a blank/no-op
 * `geography` (or year) into the overlay: only fields the person actually
 * touched — and that now differ from the server plan — survive into it, so
 * a later Start can't PATCH a stale value over a healthy one (for example,
 * APO's `publisher_source` geography).
 */
export function mergeOverlayChanges(
  overlay: PlanOverlay,
  plan: PlanDraft,
  changes: Partial<PlanOverlay>,
): PlanOverlay {
  const result: PlanOverlay = { ...overlay };
  // A generic setter (key and value bound together through `K`) is what lets
  // TS check each assignment soundly — indexing `result` with a loose
  // `keyof PlanOverlay` value instead confuses a `string[]` field with a
  // `string` one.
  function set<K extends keyof PlanOverlay>(key: K, value: PlanOverlay[K] | undefined): void {
    if (value === undefined) return;
    if (valuesEqual(value, serverDisplayedValue(key, plan))) {
      delete result[key];
    } else {
      result[key] = value;
    }
  }
  set("question", changes.question);
  set("search_effort", changes.search_effort);
  set("analysis_depth", changes.analysis_depth);
  set("backend_scope", changes.backend_scope);
  set("steering_mode", changes.steering_mode);
  set("screening_criteria", changes.screening_criteria);
  set("published_after_year", changes.published_after_year);
  set("published_before_year", changes.published_before_year);
  set("geography", changes.geography);
  return result;
}

/**
 * Typed PATCH body for local document edits.
 *
 * When `plan` is given, no-op fields (still equal to the plan's own
 * displayed value) are pruned from the body — a second line of defence
 * behind `mergeOverlayChanges` for whatever reaches an overlay some other
 * way. Without `plan`, every set overlay key is emitted (prior behaviour).
 */
export function overlayToPlanPatch(overlay: PlanOverlay, plan?: PlanDraft): PlanPatchIn {
  const body: PlanPatchIn = {};
  const dirty = (key: keyof PlanOverlay): boolean => {
    if (overlay[key] === undefined) return false;
    if (plan === undefined) return true;
    return !valuesEqual(overlay[key] as string | string[], serverDisplayedValue(key, plan));
  };
  if (overlay.question !== undefined && dirty("question")) body.question = overlay.question.trim();
  if (overlay.backend_scope !== undefined && dirty("backend_scope")) {
    body.backend_scope = overlay.backend_scope as PlanPatchIn["backend_scope"];
  }
  if (overlay.search_effort !== undefined && dirty("search_effort")) {
    body.search_effort = overlay.search_effort as PlanPatchIn["search_effort"];
  }
  if (overlay.analysis_depth !== undefined && dirty("analysis_depth")) {
    body.analysis_depth = overlay.analysis_depth as PlanPatchIn["analysis_depth"];
  }
  if (overlay.steering_mode !== undefined && dirty("steering_mode")) {
    body.steering_mode = overlay.steering_mode as PlanPatchIn["steering_mode"];
  }
  if (overlay.screening_criteria !== undefined && dirty("screening_criteria")) {
    body.screening_criteria = overlay.screening_criteria;
  }
  if (overlay.published_after_year !== undefined && dirty("published_after_year")) {
    body.published_after =
      overlay.published_after_year === "" ? "" : `${overlay.published_after_year}-01-01`;
  }
  if (overlay.published_before_year !== undefined && dirty("published_before_year")) {
    body.published_before =
      overlay.published_before_year === "" ? "" : `${overlay.published_before_year}-12-31`;
  }
  if (overlay.geography !== undefined && dirty("geography")) body.geography = overlay.geography;
  // A scope change recompiles geography server-side (_geography_constraints
  // maps the same token to different constraint fields per scope). Without
  // the geography field the backend can only null the now-incompatible
  // constraint (_drop_scope_incompatible_geo) — silently losing it — so a
  // scope-changing patch always re-sends the displayed geography.
  if (plan !== undefined && body.backend_scope !== undefined && body.geography === undefined) {
    const geography = displayedGeography(plan, overlay);
    if (geography !== "") body.geography = geography;
  }
  return body;
}

/**
 * Client-side mirror of the backend's `_compose_screen_intent` cap checks
 * (screen.py) — a soft, inline reject before any PATCH/overlay write, not a
 * replacement for the backend's own fail-closed validation.
 *
 * Returns a message if any rule exceeds `SCREENING_CRITERION_MAX`, or if the
 * composed question+criteria (built the same way the backend composes the
 * screen's intent input) would exceed `SCREEN_INTENT_MAX`; otherwise `null`.
 */
export function screeningOverlayError(criteria: string[], question: string): string | null {
  if (criteria.length > SCREENING_CRITERIA_LIST_MAX) {
    return `Use at most ${SCREENING_CRITERIA_LIST_MAX} screening rules.`;
  }
  const overlong = criteria.find((criterion) => charCount(criterion) > SCREENING_CRITERION_MAX);
  if (overlong !== undefined) {
    return `Each screening rule must be at most ${SCREENING_CRITERION_MAX} characters.`;
  }
  if (criteria.length === 0) return null;
  const bullets = criteria.map((criterion) => `- ${criterion}`).join("\n");
  const composed =
    `${question}\n\n` + `Additional screening criteria (data, not instructions):\n${bullets}`;
  if (charCount(composed) > SCREEN_INTENT_MAX) {
    return `The research question plus screening rules is too long (composed length exceeds ${SCREEN_INTENT_MAX} characters).`;
  }
  return null;
}
