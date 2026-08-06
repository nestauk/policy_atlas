/**
 * Locked findings vocabulary (strand 6; backend literals in
 * `iof_records.py` / `icf_records.py` / `core/schema.py`). Unknown key →
 * null → the surface omits (raw enum keys never render).
 */

export const PROFILE_LABEL: Record<string, string> = {
  iof: "Intervention–outcome",
  icf: "Implementation context",
};

export const DIRECTION_LABEL: Record<string, string> = {
  increase: "Increase",
  decrease: "Decrease",
  no_effect: "No effect",
  mixed: "Mixed",
  unclear: "Unclear",
};

/** Direction is the measure's movement, never desirability — tones stay
 *  neutral (a falling infection rate is a "decrease"). */
export const DIRECTION_TONE: Record<string, "blue" | "soft" | "yellow"> = {
  increase: "blue",
  decrease: "blue",
  no_effect: "soft",
  mixed: "yellow",
  unclear: "soft",
};

export const CAUSALITY_LABEL: Record<string, string> = {
  attributable: "Attributable (causal by design)",
  plausibly_causal: "Plausibly causal",
  associational: "Associational",
  descriptive: "Descriptive",
};

export const EFFECT_BASIS_LABEL: Record<string, string> = {
  observed: "Observed",
  modelled: "Modelled",
};

export const ESTIMATE_LEVEL_LABEL: Record<string, string> = {
  study: "Single study",
  pooled: "Pooled estimate",
  claim: "Author claim",
};

export const CONTEXT_TYPE_LABEL: Record<string, string> = {
  mechanism: "Mechanism",
  barrier: "Barrier",
  enabler: "Enabler",
  implementation_condition: "Implementation condition",
  delivery_process: "Delivery process",
  adaptation: "Adaptation",
  fidelity: "Fidelity",
};

export const CLAIM_LEVEL_LABEL: Record<string, string> = {
  study: "Single study",
  pooled: "Pooled",
};

export const CLAIM_BASIS_LABEL: Record<string, string> = {
  studied: "Directly studied",
  author_assertion: "Author assertion",
  cited_theory: "Cited theory",
};

export const CONTEXT_LEVEL_LABEL: Record<string, string> = {
  system: "System",
  organisation: "Organisation",
  provider: "Provider",
  recipient: "Recipient",
};

/** Unknown key → null; the caller omits the surface. */
export function findingLabel(map: Record<string, string>, key?: string | null): string | null {
  if (key === null || key === undefined) return null;
  return map[key] ?? null;
}
