import type { ResolvedDecision } from "../../store";

/** Friendly copy for the known steering-trigger keys
 *  (`runtime/steering_triggers.py`). Unknown trigger → omit (locked
 *  vocabulary; raw keys never render). */
export const TRIGGER_COPY: Record<string, string> = {
  coverage_inadequate: "Search coverage looked inadequate for the question.",
  coverage_stop_condition: "A coverage stop condition was hit.",
  screen_quorum_failure_spike: "Screening hit a spike of failed relevance checks.",
  classification_unknown_share: "Many sources couldn't be classified by evidence type.",
  classification_type_mix_collapse: "The evidence-type mix collapsed to one type.",
  appraisal_quality_collapse: "Appraisal found quality concentrated at the low end.",
  extraction_failure_spike: "Extraction hit a spike of failures.",
  extraction_vetting_failed_spike: "Extracted findings failed vetting unusually often.",
  grouping_facet_flagged: "A grouping facet looked unreliable.",
  downstream_capability_reduced: "An earlier step reduced what later steps can do.",
};

export function triggerCopy(triggers: Array<{ trigger: string }> | undefined): string[] {
  return (triggers ?? [])
    .map(({ trigger }) => TRIGGER_COPY[trigger])
    .filter((copy): copy is string => copy !== undefined);
}

export const DECIDED_BY_LABEL: Record<string, string> = {
  user: "You decided",
  orchestrator: "The orchestrator decided",
  standing_default: "Your standing rule decided",
};

/** The typed prose of a free-text steer, when the recorded response carries
 *  one. Anything non-string is presentation-mapped elsewhere, never dumped. */
export function decisionProse(decision: ResolvedDecision): string | null {
  const text = decision.response["text"] ?? decision.response["free_text"];
  return typeof text === "string" && text.trim() !== "" ? text : null;
}
