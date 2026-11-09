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

interface PresentedCheckInRender {
  stageLabel: string;
  status: "completed";
  seconds: string;
  counts: Array<{ label: string; value: string }>;
  /** The question the check-in asks (the render's first line), or null. */
  question: string | null;
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
  // The render's first line is the question the check-in asks (task 058,
  // N19) and its machine line follows; a render without a question is the
  // machine line alone.
  const lines = render.split("\n").map((line) => line.trim()).filter((line) => line !== "");
  const machine = lines.find((line) => /\|\s*wall_clock=/.test(line)) ?? render;
  const match = /^\s*([^:|]+):\s*([^|]+?)\s*\|\s*wall_clock=([0-9]+(?:\.[0-9]+)?)s\s*\|\s*counts:\s*(.*?)\s*$/.exec(machine);
  if (match === null) return null;
  const [, component, rawStatus, seconds, rawCounts] = match;
  const question = lines[0] !== undefined && lines[0] !== machine ? lines[0] : null;
  if (rawStatus.trim() !== "succeeded") return null;
  const stageKey = stage ?? component.trim();
  // The stage frame carries the server's label (task 058, N17); without one
  // the render stays prose rather than guessing a name.
  const stageLabel = [...stages].reverse().find((entry) => entry.stage === stageKey)?.label;
  if (stageLabel === undefined) return null;
  const counts = rawCounts.split(",").flatMap((part) => {
    const count = /^\s*([a-z_]+)\s*=\s*(-?[0-9]+(?:\.[0-9]+)?)\s*$/.exec(part);
    if (count === null) return [];
    const label = CHECK_IN_COUNT_LABELS[count[1]];
    return label === undefined ? [] : [{ label, value: count[2] }];
  });
  return { stageLabel, status: "completed", seconds, counts, question };
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

/** An honest absence: a stub or degraded baseline carries no key-assumption
 *  section, and the card says so rather than quoting nothing. */
export const BASELINE_KEY_ASSUMPTION_ABSENT = "The baseline records no key assumption.";

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
  // The server sends the label the user sees (`RISK_APPETITE_LABELS`, N19).
  ["risk_appetite", "Risk appetite"],
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

/** The check-in's question and its one line of facts (task 058, N19; annex
 *  scene 12). */
export interface CheckInHeadline {
  /** The question, shown as the card's title. */
  title: string;
  /** One line of facts, or null when the render carries none. */
  facts: string | null;
}

/**
 * Read the card's title and facts line off the check-in's deterministic
 * render, the content of record. A prose render leads with its question and
 * puts its facts on the next line; a component-completion render has no
 * question, so its stage label is the title and its counts are the facts.
 *
 * Args:
 *   render: The check-in's `render`.
 *   stage: The check-in's stage key.
 *   stages: The run's stage entries (they carry the server's labels).
 *
 * Returns:
 *   The title and the facts line.
 */
export function checkInHeadline(render: string, stage: string | null, stages: StageEntry[]): CheckInHeadline {
  const presented = presentCheckInRender(render, stage, stages);
  if (presented !== null) {
    const facts = presented.counts.map(({ label, value }) => `${label} ${value}`).join(" · ");
    // The server's question is the title; the stage label only when the
    // render carries none.
    return { title: presented.question ?? presented.stageLabel, facts: facts === "" ? null : facts };
  }
  const lines = render.split("\n").map((line) => line.trim()).filter((line) => line !== "");
  return { title: lines[0] ?? "", facts: lines.length > 1 ? lines.slice(1).join(" · ") : null };
}

/** The check-in's place in the run, in the stage's own words: "after
 *  searching and screening". Null when the stream has no label for it. */
export function checkInWhen(stage: string | null | undefined, stages: StageEntry[]): string | null {
  if (stage == null) return null;
  const label = [...stages].reverse().find((entry) => entry.stage === stage)?.label;
  return label === undefined ? null : `after ${label.toLowerCase()}`;
}

/** The words on the check-in's one stop link, and the line it leaves. */
export const STOP_THE_RUN = "Stop the run";

/**
 * The answered check-in's one line, "You chose: <label> · <when>", built from
 * the durable `checkin.resolved` frame (task 058, N19): the chosen option's
 * label off the check-in's own options, never a session-local echo.
 *
 * Args:
 *   decision: The resolved decision from the stream.
 *   checkIn: The check-in it answered, when the check-ins read has it.
 *   stages: The run's stage entries, for the "after …" place.
 *
 * Returns:
 *   The line, or null when the frame names nothing the card can word.
 */
export function chosenLine(
  decision: ResolvedDecision,
  checkIn: { options?: Array<{ id: string; label: string }>; stage: string | null; component: string | null } | undefined,
  stages: StageEntry[],
): string | null {
  const response = decision.response;
  const optionId = response["option_id"];
  const choice =
    response["kind"] === "abort"
      ? STOP_THE_RUN
      : typeof optionId === "string"
        ? (checkIn?.options ?? []).find((option) => option.id === optionId)?.label ?? null
        : decisionProse(decision);
  if (choice === null) return null;
  const who = decision.decidedBy === null || decision.decidedBy === "user" ? "You chose" : DECIDED_BY_LABEL[decision.decidedBy];
  const when = checkInWhen(checkIn?.stage ?? checkIn?.component, stages);
  return [`${who ?? "You chose"}: ${choice}`, when].filter((part): part is string => part !== null).join(" · ");
}
