import type { ResolvedDecision, StageEntry } from "../../store";
import { SCOPING_DEPTH_LABEL, vocabLabel } from "./planVocabulary";

/** Locked backend display names, keyed by the durable backend key the stream
 *  and check-in bundles carry. Shared by the journey pane's coverage card
 *  and the check-in bundle's P1 search-review card — both render raw
 *  backend keys without it. */
const BACKEND_LABELS: Record<string, string> = {
  openalex: "OpenAlex · academic research",
  overton: "Overton · policy documents",
};

/** Look a backend key up in the locked map. Unknown key → null (the caller
 *  omits). Case-insensitive: the coverage read model serves public names
 *  ("OpenAlex"), the stream serves durable keys ("openalex") — the label-map
 *  mismatch left a completed task's "Where I looked" card nearly empty
 *  (owner finding, 2026-08-05) and, separately, left the P1 search-review
 *  card rendering raw keys outright. */
export function backendLabel(backend: string): string | null {
  return BACKEND_LABELS[backend.toLowerCase()] ?? null;
}

/** Locked heading copy for the CheckInBundle P1–P4 blocks. Pure copy, moved
 *  out of the component so the headings share the module's other locked
 *  vocabulary rather than living as inline JSX literals. */
export const CHECK_IN_SEARCH_HEADING = "What the search collected";

export function checkInThemesHeading(count: number): string {
  return `Themes in the evidence · ${count}`;
}

export function checkInReadingListHeading(count: number): string {
  return `The reading list · ${count}`;
}

export function checkInGroupsHeading(count: number): string {
  return `Finding groups · ${count}, largest first`;
}

export const CHECK_IN_SECTIONS_HEADING = "Proposed sections · edit any row, keep the rest";

/** Locked labels for deterministic component-completion count fields. Unknown
 * keys are deliberately omitted rather than converted from implementation
 * vocabulary. */
const CHECK_IN_COUNT_LABELS: Record<string, string> = {
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
  synthesise: "Writing the report",
};

interface PresentedCheckInRender {
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
const TRIGGER_COPY: Record<string, string> = {
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
  agent: "The Agent decided",
  standing_default: "Your standing rule decided",
};

/** The typed prose of a free-text steer, when the recorded response carries
 *  one. Anything non-string is presentation-mapped elsewhere, never dumped. */
export function decisionProse(decision: ResolvedDecision): string | null {
  const text = decision.response["text"] ?? decision.response["free_text"];
  return typeof text === "string" && text.trim() !== "" ? text : null;
}

/** The options-scoping baseline gate's check-in kind (task 044, D12). The one
 *  steer point on the scoping lattice; every other check-in kind keeps the
 *  Evidence search's card. */
export const BASELINE_GATE_KIND = "baseline_confirm";

/** The gate card's heading — the same words the backend's deterministic
 *  render leads with (`runtime/baseline_gate.GATE_HEADING`), so the card and
 *  the durable content of record cannot say different things. */
export const BASELINE_GATE_HEADING = "Confirm the plan against the baseline";

/** The label over the quoted baseline prose. */
export const BASELINE_KEY_ASSUMPTION_LABEL = "Key assumption";

/** An honest absence: a stub or degraded baseline carries no key-assumption
 *  section, and the card says so rather than quoting nothing. */
export const BASELINE_KEY_ASSUMPTION_ABSENT = "The baseline records no key assumption.";

/** The heading over the plan settings the walk actually ran from. */
export const BASELINE_SETTINGS_HEADING = "Settings";

/** The gate's own display copy, read off the check-in bundle. */
export interface BaselineGateCard {
  keyAssumption: string | null;
  settings: Array<{ label: string; value: string }>;
}

/** The plan settings the gate shows, in the plan document's own order and
 *  words (`PlanDocument`'s Settings section) so the card and the plan read
 *  identically. Keys the bundle does not carry are omitted, never guessed. */
const BASELINE_SETTING_LABELS: Array<[string, string]> = [
  ["target_unit", "Who or what should change"],
  ["where", "Where"],
  ["outcomes", "Outcomes"],
  ["depth", "Depth"],
];

/**
 * Read the baseline gate's card content off its check-in bundle.
 *
 * Args:
 *   bundle: The check-in's projected bundle, or null when it carries none.
 *
 * Returns:
 *   The quoted key assumption (null when the baseline had none) and the
 *   settings lines. `depth` renders through the plan's own depth vocabulary;
 *   an unknown depth key is omitted rather than shown raw.
 */
export function baselineGateCard(bundle: Record<string, unknown> | null): BaselineGateCard {
  const keyAssumption = bundle?.["key_assumption"];
  const raw = bundle?.["settings"];
  const settings =
    raw !== null && typeof raw === "object" && !Array.isArray(raw)
      ? (raw as Record<string, unknown>)
      : {};
  return {
    keyAssumption:
      typeof keyAssumption === "string" && keyAssumption.trim() !== "" ? keyAssumption.trim() : null,
    settings: BASELINE_SETTING_LABELS.flatMap(([key, label]) => {
      const value = settings[key];
      if (key === "depth") {
        const depth = typeof value === "string" ? vocabLabel(SCOPING_DEPTH_LABEL, value) : null;
        return depth === null ? [] : [{ label, value: depth }];
      }
      if (Array.isArray(value)) {
        const items = value.filter((item): item is string => typeof item === "string" && item !== "");
        return items.length > 0 ? [{ label, value: items.join(" · ") }] : [];
      }
      return typeof value === "string" && value !== "" ? [{ label, value }] : [];
    }),
  };
}
