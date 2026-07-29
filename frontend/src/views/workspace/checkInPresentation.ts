import type { ResolvedDecision, StageEntry } from "../../store";

/** Locked labels for deterministic component-completion count fields. Unknown
 * keys are deliberately omitted rather than converted from implementation
 * vocabulary. */
export const CHECK_IN_COUNT_LABELS: Record<string, string> = {
  acquired: "Sources found",
  results: "Results returned",
  relevant: "Relevant sources",
  not_relevant: "Screened out",
  classified: "Sources classified",
  appraised: "Sources quality-appraised",
  selected: "Sources shortlisted",
  extracted: "Findings extracted",
  skipped: "Skipped",
  failed: "Failed",
};

/** Public fallback labels for renders received before a stage frame. */
const STAGE_LABELS: Record<string, string> = {
  acquire: "Searching sources",
  screen: "Screening sources",
  classify: "Classifying evidence",
  appraise: "Appraising quality",
  characterise: "Mapping the landscape",
  synthesise: "Synthesising the evidence",
};

export interface PresentedCheckInRender {
  stageLabel: string;
  status: "completed";
  seconds: string;
  counts: Array<{ label: string; value: string }>;
}

/**
 * Present the deterministic component-completion render without surfacing its
 * backend keys. A non-matching render remains prose, so no guessed structure
 * replaces the durable content of record.
 */
export function presentCheckInRender(
  render: string,
  stage: string | null,
  stages: StageEntry[],
): PresentedCheckInRender | null {
  const match = /^\s*([^:|]+):\s*([^|]+?)\s*\|\s*wall_clock=([0-9]+(?:\.[0-9]+)?)s\s*\|\s*counts:\s*(.*?)\s*$/.exec(render);
  if (match === null) return null;
  const [, component, rawStatus, seconds, rawCounts] = match;
  if (rawStatus.trim() !== "succeeded") return null;
  const stageKey = stage ?? component.trim();
  const stageLabel =
    [...stages].reverse().find((entry) => entry.stage === stageKey)?.label ?? STAGE_LABELS[stageKey];
  if (stageLabel === undefined) return null;
  const counts = rawCounts.split(",").flatMap((part) => {
    const count = /^\s*([a-z_]+)\s*=\s*(-?[0-9]+(?:\.[0-9]+)?)\s*$/.exec(part);
    if (count === null) return [];
    const label = CHECK_IN_COUNT_LABELS[count[1]];
    return label === undefined ? [] : [{ label, value: count[2] }];
  });
  return { stageLabel, status: "completed", seconds, counts };
}

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
