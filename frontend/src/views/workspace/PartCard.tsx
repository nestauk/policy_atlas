import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from "react";

import type { components } from "../../api/gen/types";
import { scrub } from "../../lib/scrub";
import { Button } from "../../ui/brand/Button";
import { cn } from "../../ui/brand/cn";
import { LABEL_CLASS } from "../../ui/brand/label";
import { useArrives } from "../../ui/motion/arrivals";
import {
  PLAN_PARTS,
  RISK_APPETITE_LABELS,
  SCOPING_DEPTH_LABEL,
  researchApproachId,
  researchApproachLabel,
} from "./planVocabulary";
import { QUIET_CONTROL_CLASS } from "../../ui/brand/inlineActions";

type PartProposal = components["schemas"]["PartProposalOut"];
type PartChip = components["schemas"]["PartChipOut"];
type PartOption = components["schemas"]["PartOptionOut"];
export type TaskAgentTurn = components["schemas"]["TaskAgentTranscriptTurnOut"];

/** The canned confirm marker a part button appends as the message's final
 *  line. The backend treats it as an ordinary turn; the thread derives the
 *  settled state and hides these bubbles from it. */
const CONFIRM_MARKER = /^\[confirm part=([a-z_]+) option=([a-z0-9_]+)\]$/;

/** Parse a user message's trailing confirm marker, if any. */
export function confirmTarget(message: string): { partId: string; optionId: string } | null {
  const lastLine = message.trimEnd().split("\n").at(-1) ?? "";
  const match = CONFIRM_MARKER.exec(lastLine.trim());
  return match === null ? null : { partId: match[1], optionId: match[2] };
}

/** Build the canned confirm message for an option press. */
export function confirmMessage(part: PartProposal, option: PartOption): string {
  return `${option.label}\n\n[confirm part=${part.id} option=${option.id}]`;
}

export interface PartState {
  /** Latest proposal per part id wins (F34): older proposals render inert. */
  live: boolean;
  /** A later turn exists, so the user answered this card (in words or by a
   *  choice); it renders settled even without a recorded option (owner,
   *  polish round 2: no open card on a finished conversation). */
  answered: boolean;
  /** What the user wrote in reply to this card (the next turn's message),
   *  shown on the settled line when no recorded choice names the answer. */
  answer: string | null;
  /** The option id a later (pre-supersession) confirm turn recorded, if any. */
  confirmedOptionId: string | null;
  /** The confirming message itself: the scope's "Looks right" carries any
   *  staged chip edits above its marker, and the settled lines apply them. */
  confirmedMessage: string | null;
  /** The answer is the user's turn still on its way (an optimistic turn):
   *  the card settles on the choice at once (owner, 2026-11-05) and names
   *  the user's words or choice until the durable turns catch up. */
  pending: boolean;
}

/** The fields part-state derivation reads from a turn. */
type PartTurn = Pick<TaskAgentTurn, "turn_index" | "user_message" | "part">;

/**
 * Derive each part-bearing turn's card state from the turn sequence alone
 * (F34 rehydration rules): the latest proposal per part id is live; a confirm
 * marker binds to the newest proposal of its part id at the time it was sent;
 * a confirm referencing a superseded proposal never mis-binds.
 *
 * Args:
 *   turns: The durable transcript.
 *   pendingMessages: The user's messages still on their way (the optimistic
 *     turns that have not failed), in order. They follow every durable turn,
 *     so the newest card settles on the choice the moment it is made.
 */
export function derivePartStates(turns: PartTurn[], pendingMessages: readonly string[] = []): Map<number, PartState> {
  const durable = [...turns].sort((a, b) => a.turn_index - b.turn_index);
  const lastDurable = durable.length === 0 ? -1 : durable[durable.length - 1].turn_index;
  const pendingFrom = lastDurable + 1;
  const ordered: PartTurn[] = [
    ...durable,
    ...pendingMessages.map((message, offset) => ({ turn_index: pendingFrom + offset, user_message: message, part: null })),
  ];
  const newestProposal = new Map<string, number>();
  for (const turn of ordered) {
    if (turn.part != null) newestProposal.set(turn.part.id, turn.turn_index);
  }
  // Walk forward, tracking the current proposal per part id, binding confirms.
  const currentProposal = new Map<string, number>();
  const confirmed = new Map<number, { optionId: string; message: string; pending: boolean }>();
  for (const turn of ordered) {
    const target = confirmTarget(turn.user_message);
    if (target !== null) {
      const proposalIndex = currentProposal.get(target.partId);
      if (proposalIndex !== undefined) {
        confirmed.set(proposalIndex, {
          optionId: target.optionId,
          message: turn.user_message,
          pending: turn.turn_index >= pendingFrom,
        });
      }
    }
    if (turn.part != null) {
      currentProposal.set(turn.part.id, turn.turn_index);
    }
  }
  const states = new Map<number, PartState>();
  const lastIndex = ordered.length === 0 ? -1 : ordered[ordered.length - 1].turn_index;
  for (const [position, turn] of ordered.entries()) {
    if (turn.part == null) continue;
    const next = ordered[position + 1];
    const confirm = confirmed.get(turn.turn_index);
    states.set(turn.turn_index, {
      live: newestProposal.get(turn.part.id) === turn.turn_index,
      answered: turn.turn_index < lastIndex,
      answer: next === undefined ? null : confirmTarget(next.user_message) !== null ? null : next.user_message.trim(),
      confirmedOptionId: confirm?.optionId ?? null,
      confirmedMessage: confirm?.message ?? null,
      pending: confirm?.pending ?? (next !== undefined && next.turn_index >= pendingFrom),
    });
  }
  return states;
}

type PlanDraft = components["schemas"]["PlanDraft"];
type ScopingPlanDraft = components["schemas"]["ScopingPlanDraft"];

/** The thoroughness part's option ids, by the plan's preset id. */
const THOROUGHNESS_OPTION_BY_PRESET: Record<string, string> = {
  rapid_overview: "quick_look",
  standard_review: "standard_review",
  detailed_review: "deep_analysis",
};

/**
 * What a settled part's line says (owner, polish round 2): the outcome the
 * plan settled on, not the user's words. A recorded choice names itself;
 * otherwise the question's text, the scope's chips, the thoroughness preset
 * and its band, the scoping depth and risk appetite labels; the user's reply
 * only where the plan has nothing to name.
 *
 * Args:
 *   part: The card's proposal.
 *   state: Its derived state.
 *   plan: The task's current Evidence search plan, if any.
 *   scoping: The task's current scoping plan, if any.
 *
 * Returns:
 *   The lines after the part's name (the scope gives one per chip group,
 *   each under its group's label), or null when nothing can be named.
 */
export function settledSummary(
  part: PartProposal,
  state: PartState,
  plan: PlanDraft | null | undefined,
  scoping: ScopingPlanDraft | null | undefined,
): SettledLine[] | null {
  const confirmedOption =
    state.confirmedOptionId === null ? undefined : part.options.find((option) => option.id === state.confirmedOptionId);
  const confirmed = confirmedOption?.label ?? null;
  const words = state.answer !== null && state.answer !== "" ? state.answer : null;
  // The outcome first (owner, polish round 3: "what looks right?"); the
  // recorded choice's label, then the user's words, only where the plan
  // names nothing.
  const fallbackText = confirmed ?? words;
  const fallback = fallbackText === null ? null : [{ label: null, text: fallbackText }];
  // While the answer is on its way the plan has not caught up with it: the
  // user's words, or a choice other than the planner's own, name the part
  // until the durable turns land (owner, 2026-11-05). Taking the planner's
  // primary option keeps the draft as it stands, so its outcome reads now.
  if (state.pending && (words !== null || (confirmedOption !== undefined && !confirmedOption.primary))) {
    return fallback;
  }
  const one = (text: string | null | undefined): SettledLine[] | null =>
    text == null || text === "" ? fallback : [{ label: null, text }];
  switch (part.id) {
    case "question":
      return one(plan?.question ?? scoping?.question);
    case "scope": {
      // One line per group under its label (owner, 2026-11-05: on one line
      // the criteria and the filters read as one jumble), with the chip
      // edits the "Looks right" carried already applied.
      const edited = applyChipEdits(part.chips ?? [], state.confirmedMessage);
      const groups = chipGroups(edited.chips);
      const lines = groups.map((group) => ({
        label: group.heading,
        text: group.chips.map((chip) => chipText(chipDisplayLabel(chip))).join(" · "),
      }));
      if (edited.added.length > 0) {
        // An added constraint names no group: it joins the unnamed line.
        const unnamed = lines.find((line) => line.label === null);
        const added = edited.added.join(" · ");
        if (unnamed !== undefined) unnamed.text = `${unnamed.text} · ${added}`;
        else lines.unshift({ label: null, text: added });
      }
      return lines.length === 0 ? fallback : lines;
    }
    case "thoroughness": {
      if (plan?.search_effort == null || plan.analysis_depth == null) return fallback;
      const preset = researchApproachId(plan.search_effort, plan.analysis_depth);
      const option = preset === null ? undefined : part.options.find((candidate) => candidate.id === THOROUGHNESS_OPTION_BY_PRESET[preset]);
      const label = option?.label ?? researchApproachLabel(plan.search_effort, plan.analysis_depth);
      if (label === null) return fallback;
      return one(plan.time_band ? `${label} · ${plan.time_band}` : label);
    }
    case "depth":
      return scoping?.depth != null ? one(SCOPING_DEPTH_LABEL[scoping.depth]) : fallback;
    case "appetite":
      return scoping?.risk_appetite != null ? one(RISK_APPETITE_LABELS[scoping.risk_appetite]) : fallback;
    default:
      return fallback;
  }
}

/** One line of a settled part: the words, under an optional group label. */
export interface SettledLine {
  label: string | null;
  text: string;
}

/** The planner prefixes a scope chip with what it constrains: "Screen: …"
 *  is a screening criterion, "Search: …" a source filter. */
const CHIP_PREFIXES: ReadonlyArray<readonly [RegExp, string]> = [
  [/^screen(?:ing)?\s*:\s*/i, "Screening criteria"],
  [/^search\s*:\s*/i, "Source filters"],
];

/** A chip's words without its "Screen:" / "Search:" prefix. */
export function chipText(label: string): string {
  for (const [prefix] of CHIP_PREFIXES) {
    if (prefix.test(label)) return label.replace(prefix, "").trim();
  }
  return label;
}

/**
 * The scope card's chips grouped by what they constrain (owner, 2026-11-05:
 * screening criteria and source filters were mixed in one row). Chips with
 * no recognised prefix form an unnamed group, first.
 */
export function chipGroups(chips: PartChip[]): Array<{ heading: string | null; chips: PartChip[] }> {
  const groups = new Map<string | null, PartChip[]>();
  for (const chip of chips) {
    // `chipDisplayLabel` normalises the prefix from the chip's kind.
    const match = CHIP_PREFIXES.find(([prefix]) => prefix.test(chipDisplayLabel(chip)));
    const heading = match === undefined ? null : match[1];
    groups.set(heading, [...(groups.get(heading) ?? []), chip]);
  }
  const order: Array<string | null> = [null, "Screening criteria", "Source filters"];
  return order.filter((heading) => groups.has(heading)).map((heading) => ({ heading, chips: groups.get(heading) ?? [] }));
}

/** Chip edit staged on the scope card, batched into one task_agent turn. */
interface ChipEdit {
  kind: "change" | "remove" | "add";
  label: string;
  detail?: string;
}

/** One line of `chipEditMessage`, read back. */
const CHIP_EDIT_LINE = /^- (?:Remove "(.*)"\.|Add: (.*)\.|Change "(.*)" to: (.*)\.)$/;

/**
 * The scope's chips with the edits a confirming message carried applied:
 * removed chips dropped, changed chips relabelled, added constraints listed
 * apart (they name no group).
 *
 * Args:
 *   chips: The proposal's chips.
 *   message: The confirming message (`chipEditMessage` lines above the
 *     confirm marker), or null.
 *
 * Returns:
 *   The chips as settled, and the added constraints' words.
 */
export function applyChipEdits(chips: PartChip[], message: string | null): { chips: PartChip[]; added: string[] } {
  if (message === null) return { chips, added: [] };
  const removed = new Set<string>();
  const changed = new Map<string, string>();
  const added: string[] = [];
  for (const line of message.split("\n")) {
    const match = CHIP_EDIT_LINE.exec(line.trim());
    if (match === null) continue;
    if (match[1] !== undefined) removed.add(match[1]);
    else if (match[2] !== undefined && match[2].trim() !== "") added.push(match[2].trim());
    else if (match[3] !== undefined && match[4] !== undefined) changed.set(match[3], match[4].trim());
  }
  return {
    chips: chips
      .filter((chip) => !removed.has(chip.label))
      .map((chip) => (changed.has(chip.label) ? { ...chip, label: changed.get(chip.label) ?? chip.label } : chip)),
    added,
  };
}

/** Compose the single batched task_agent-turn message for staged chip edits. */
export function chipEditMessage(edits: ChipEdit[]): string {
  const lines = edits.map((edit) => {
    if (edit.kind === "remove") return `- Remove "${edit.label}".`;
    if (edit.kind === "add") return `- Add: ${edit.detail ?? ""}.`;
    return `- Change "${edit.label}" to: ${edit.detail ?? ""}.`;
  });
  return `Update the scope:\n${lines.join("\n")}`;
}

const SEARCH_CHIP_PREFIX = "Search:";
const SCREEN_CHIP_PREFIX = "Screen:";

/** Visible chip label: Search: for date/country filters, Screen: for text rules.
 *
 * Args:
 *   chip: A scope chip; `kind` is the only search/screen signal on the wire.
 *
 * Returns:
 *   The label with a prefix unless it already starts with one.
 */
export function chipDisplayLabel(chip: Pick<PartChip, "kind" | "label">): string {
  const prefix =
    chip.kind === "date_range" || chip.kind === "country_list"
      ? SEARCH_CHIP_PREFIX
      : chip.kind === "text"
        ? SCREEN_CHIP_PREFIX
        : null;
  if (prefix === null) return chip.label;
  // A label that already says what it constrains keeps its own prefix.
  if (chip.label.startsWith(SCREEN_CHIP_PREFIX) || chip.label.startsWith(SEARCH_CHIP_PREFIX)) return chip.label;
  return `${prefix} ${chip.label}`;
}

/** Parse a date_range chip value ({"after": ..., "before": ...}) fail-soft. */
function parseDateRange(value: string): { after: string | null; before: string | null } | null {
  try {
    const decoded: unknown = JSON.parse(value);
    if (decoded === null || typeof decoded !== "object" || Array.isArray(decoded)) return null;
    const record = decoded as Record<string, unknown>;
    return {
      after: typeof record.after === "string" ? record.after : null,
      before: typeof record.before === "string" ? record.before : null,
    };
  } catch {
    return null;
  }
}

/** One editable scope chip: ✎ opens the inline editor, × stages a removal. */
function EditableChip({
  chip,
  disabled,
  onStage,
}: {
  chip: PartChip;
  disabled: boolean;
  onStage: (edit: ChipEdit) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState("");
  const range = chip.kind === "date_range" ? parseDateRange(chip.value) : null;
  const [after, setAfter] = useState(range?.after ?? "");
  const [before, setBefore] = useState(range?.before ?? "");
  const prefixed = chipDisplayLabel(chip);
  const displayLabel = chipText(prefixed);

  if (editing && !disabled) {
    return (
      <span className="inline-flex flex-wrap items-center gap-1 border border-blue-tint bg-paper px-2 py-1">
        <span className="text-caption font-semibold text-navy">{scrub(displayLabel)}</span>
        {chip.kind === "date_range" ? (
          <>
            <label className="text-caption text-grey">
              from{" "}
              <input
                type="date"
                value={after}
                onChange={(event) => setAfter(event.target.value)}
                className="border border-line-2 px-1 text-caption"
              />
            </label>
            <label className="text-caption text-grey">
              to{" "}
              <input
                type="date"
                value={before}
                onChange={(event) => setBefore(event.target.value)}
                className="border border-line-2 px-1 text-caption"
              />
            </label>
          </>
        ) : (
          <input
            type="text"
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="New value"
            aria-label={`New value for ${chip.label}`}
            className="border border-line-2 px-1.5 py-0.5 text-caption"
          />
        )}
        <Button
          size="sm"
          variant="secondary"
          onClick={() => {
            const detail =
              chip.kind === "date_range"
                ? `${after !== "" ? `from ${after}` : "no lower date bound"}${before !== "" ? ` to ${before}` : ", no upper date bound"}`
                : text;
            if (detail.trim() !== "") onStage({ kind: "change", label: chip.label, detail });
            setEditing(false);
          }}
        >
          Save
        </Button>
        <Button size="sm" variant="secondary" onClick={() => setEditing(false)}>
          Cancel
        </Button>
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1 border border-blue-tint bg-blue-tint px-2 py-1 text-caption font-semibold text-blue">
      {scrub(displayLabel)}
      {!disabled && (
        <>
          <button
            type="button"
            aria-label={`Edit ${prefixed}`}
            className="cursor-pointer px-0.5 hover:text-navy"
            onClick={() => setEditing(true)}
          >
            ✎
          </button>
          <button
            type="button"
            aria-label={`Remove ${prefixed}`}
            className="cursor-pointer px-0.5 hover:text-navy"
            onClick={() => onStage({ kind: "remove", label: chip.label })}
          >
            ×
          </button>
        </>
      )}
    </span>
  );
}

/**
 * Option ids the planners reserve for "let me say it in my own words"
 * (`task_agent_prompt.py`: refine, change; `task_agent_scoping_prompt.py`:
 * i_have_some, and my_own_words on the settings and constraints parts,
 * owner round 12). Choosing one opens a short input inside the card with its own
 * Send; every other option is a choice and sends at once.
 */
const WORDS_OPTION_IDS = new Set(["refine", "change", "i_have_some", "my_own_words"]);

/** Whether choosing this option asks the user for words rather than sending. */
export function optionNeedsWords(option: PartOption): boolean {
  return !option.primary && WORDS_OPTION_IDS.has(option.id);
}

/** The options in the order the planner gave them (owner, polish round 3:
 *  the thoroughness presets read fastest to slowest; the primary is not
 *  moved to the front). */
export function orderedOptions(options: PartOption[]): PartOption[] {
  return [...options];
}

/** One step of the plan, as the stepper names it. */
export interface PlanStep {
  id: string;
  name: string;
  settled: boolean;
}

/**
 * The plan's steps for the stepper (task 058, N18): the capability's parts
 * in the planner's order, computed on the client rather than read off the
 * model's `step_label`. An optional part counts only once the transcript
 * carries it; a step is settled when its newest proposal was confirmed.
 *
 * Args:
 *   capability: The task's capability; unknown or absent reads as Evidence search.
 *   turns: The durable transcript.
 *   states: `derivePartStates(turns)`.
 *
 * Returns:
 *   The steps in order.
 */
export function planSteps(
  capability: string | null | undefined,
  turns: TaskAgentTurn[],
  states: Map<number, PartState>,
): PlanStep[] {
  const parts = PLAN_PARTS[capability ?? "evidence_search"] ?? PLAN_PARTS.evidence_search;
  const newest = new Map<string, number>();
  for (const turn of turns) {
    if (turn.part != null) newest.set(turn.part.id, Math.max(turn.turn_index, newest.get(turn.part.id) ?? -1));
  }
  return parts
    .filter((part) => part.optional !== true || newest.has(part.id))
    .map((part) => {
      const index = newest.get(part.id);
      const partState = index === undefined ? undefined : states.get(index);
      const settled =
        partState !== undefined && ((partState.confirmedOptionId ?? null) !== null || partState.answered);
      return { id: part.id, name: part.name, settled };
    });
}

/**
 * The one small line above the active part card: the settled steps named in
 * grey, then "Plan · decision n of M · <part>" (annex scene 11; owner round 12:
 * the line counts decisions, M the parts the planner asks, the question
 * included, Who can act and Your options only once asked).
 *
 * Args:
 *   steps: `planSteps(...)`.
 *   activeId: The active card's part id.
 *
 * Returns:
 *   The line, or null when the part is not one of the capability's steps.
 */
export function PlanStepper({ steps, activeId }: { steps: PlanStep[]; activeId: string }) {
  const index = steps.findIndex((step) => step.id === activeId);
  if (index === -1) return null;
  const settled = steps.filter((step) => step.settled && step.id !== activeId);
  return (
    <p data-testid="plan-stepper" className={cn(LABEL_CLASS, "flex flex-wrap items-baseline gap-x-3 gap-y-1")}>
      {settled.map((step) => (
        <span key={step.id}>
          {step.name} <span aria-hidden="true">✓</span>
          <span className="sr-only">, done</span>
        </span>
      ))}
      <span className="text-navy">
        Plan · decision {index + 1} of {steps.length} · {steps[index].name}
      </span>
    </p>
  );
}

/**
 * One choice in a radio list (annex block H: one shape for a choice): the
 * label, then its plain sentences in grey. Nothing is pre-selected; the dot
 * fills only once the user has chosen.
 */
export function ChoiceRow({
  label,
  sentences,
  selected,
  disabled,
  onChoose,
  ...data
}: {
  label: string;
  /** The option's sentence, then its reason, when it has them. */
  sentences: Array<string | null | undefined>;
  selected: boolean;
  disabled: boolean;
  onChoose: () => void;
  [dataAttribute: `data-${string}`]: string;
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      disabled={disabled}
      className="-mx-2 flex w-[calc(100%+1rem)] cursor-pointer items-start gap-3 px-2 py-2 text-left transition-colors duration-150 hover:bg-paper-2 disabled:cursor-default disabled:hover:bg-transparent"
      onClick={onChoose}
      {...data}
    >
      <span
        aria-hidden="true"
        className={cn(
          "mt-1 flex size-4 shrink-0 items-center justify-center rounded-full border-2",
          selected ? "border-navy" : "border-navy/40",
        )}
      >
        {selected ? <span className="size-2 rounded-full bg-navy" /> : null}
      </span>
      <span className="min-w-0">
        <span className="block text-body font-semibold text-navy">{scrub(label)}</span>
        {sentences
          .filter((sentence): sentence is string => sentence != null && sentence !== "")
          .map((sentence) => (
            <span key={sentence} className="block text-body text-grey">
              {scrub(sentence)}
            </span>
          ))}
      </span>
    </button>
  );
}

/** The short input an option opens inside its card, with its own Send. */
export function WordsInput({
  label,
  disabled,
  onSend,
  sendLabel = "Send",
}: {
  label: string;
  disabled: boolean;
  onSend: (text: string) => void;
  sendLabel?: string;
}) {
  const [text, setText] = useState("");
  return (
    <form
      className="mt-2 flex items-center gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        const trimmed = text.trim();
        if (trimmed === "") return;
        onSend(trimmed);
        setText("");
      }}
    >
      <input
        // The input opens because the user just asked for it.
        autoFocus
        type="text"
        value={text}
        onChange={(event) => setText(event.target.value)}
        placeholder="What should change?"
        aria-label={label}
        disabled={disabled}
        className="min-w-0 flex-1 border border-line-2 bg-paper px-3 py-2 text-body text-ink disabled:bg-ground"
      />
      <Button
        type="submit"
        size="sm"
        variant="outline"
        disabled={disabled || text.trim() === ""}
      >
        {sendLabel}
      </Button>
    </form>
  );
}

/** How long what leaves a settling card takes to fade (owner, round 8). */
const SETTLE_FADE_MS = 150;
/** How long the card takes to ease to its settled height and place. */
const SETTLE_MS = 300;
/** The strong ease-out (`--ease-out-strong`), for the script-driven part. */
const EASE_OUT_STRONG = "cubic-bezier(0.23, 1, 0.32, 1)";

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
}

/**
 * The settle's motion (owner, round 8: "make the transition from the decision
 * card to the decided card smoother"). One card across the two states: when
 * it settles, the box eases from its open height to its settled height and
 * from the thread's side to the user's (the 32 px indent) over 300 ms on the
 * strong ease-out, while the open form fades out over it for 150 ms and the
 * settled words rise in. A card that mounts settled (the history) holds
 * still. Under reduced motion it is a cut.
 *
 * Args:
 *   settled: Whether the card shows its settled form.
 *
 * Returns:
 *   Refs for the outer shell and the box, `leaving` while the open form
 *   fades out over the settled one, `justSettled` when the settle happened
 *   in front of the reader, and `hadOpenForm` when the card was ever open
 *   here (so the stepper's line can fold away rather than vanish).
 */
function useSettleMotion(settled: boolean) {
  const shellRef = useRef<HTMLDivElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const lastHeight = useRef<number | null>(null);
  const [hadOpenForm] = useState(!settled);
  const [seen, setSeen] = useState(settled);
  const [leaving, setLeaving] = useState(false);
  const [justSettled, setJustSettled] = useState(false);
  const [flip, setFlip] = useState(0);
  // The box's open height, held through the settle's commit (round 14): the
  // open form leaves the flow in that commit, and anything that reads the
  // layout before the height animation starts (React giving focus back to
  // the pressed option) saw a shorter thread and clamped its scroll, so the
  // thread dropped for a frame. Released once the animation holds it.
  // Set by the press that settles the card (an event handler, so it lands in
  // the settle's own commit); a settle that comes from the data needs none,
  // since only a press makes React give focus back. The layout effect
  // clears the inline height once the animation holds the box.
  const [hold, setHold] = useState<number | null>(null);
  const holdForSettle = () => {
    const box = boxRef.current;
    if (box !== null && !prefersReducedMotion()) setHold(box.offsetHeight);
  };
  // Derived during render, so the fading form and the settled words land in
  // the same commit.
  if (seen !== settled) {
    setSeen(settled);
    if (settled && !prefersReducedMotion()) {
      setLeaving(true);
      setJustSettled(true);
      setFlip((count) => count + 1);
    }
  }

  useEffect(() => {
    if (!leaving) return undefined;
    const id = window.setTimeout(() => setLeaving(false), SETTLE_FADE_MS + 10);
    return () => window.clearTimeout(id);
  }, [leaving]);

  // After every commit, remember the box's height; on the settle's commit,
  // ease from the remembered open height to the settled one, and slide the
  // shell from the thread's side to the user's.
  const animated = useRef(0);
  useLayoutEffect(() => {
    const box = boxRef.current;
    if (box === null) return;
    const settling = flip !== animated.current;
    // While held, the settled height is the settled words' own (the one
    // child in the flow) plus the box's borders; never the held height.
    const inFlow = box.firstElementChild as HTMLElement | null;
    const height =
      settling && hold !== null && inFlow !== null
        ? inFlow.offsetHeight + (box.offsetHeight - box.clientHeight)
        : box.offsetHeight;
    const from = settling && hold !== null ? hold : lastHeight.current;
    lastHeight.current = height;
    if (settling) {
      animated.current = flip;
      if (typeof box.animate === "function") {
        const timing = { duration: SETTLE_MS, easing: EASE_OUT_STRONG };
        if (from !== null && from !== height) {
          box.animate([{ height: `${from}px` }, { height: `${height}px` }], timing);
        }
        shellRef.current?.animate([{ transform: "translateX(-2rem)" }, { transform: "translateX(0)" }], timing);
      }
    }
    // The hold is for one commit: the animation holds the box from here (and
    // a press that did not settle the card leaves it as it was).
    if (box.style.height !== "") box.style.height = "";
  });

  return { shellRef, boxRef, leaving, justSettled, hadOpenForm, hold, holdForSettle };
}

/**
 * One structured part proposal in the task_agent thread (task 058, N18;
 * annex scene 11). A radio list: each option's label, then its one plain
 * sentence; the planner's primary option first with its reason under it;
 * nothing pre-selected and no "Recommended" word. An option that needs words
 * opens a short input inside the card with its own Send. A confirmed part
 * collapses to one line, "<Part> · <choice> · Change". Renders ONLY what the
 * reply carries — server-supplied labels, never enum keys. Superseded
 * proposals stay in the history but render inert.
 */
export function PartCard({
  part,
  partName,
  state,
  disabled,
  steps,
  summary,
  onSend,
  arrivalId,
}: {
  part: PartProposal;
  /** The stepper's name for this part ("Scope"); falls back to the title. */
  partName?: string;
  state: PartState;
  /** True while the composer is disabled (run active / turn in flight). */
  disabled: boolean;
  /** The plan's steps; the stepper line renders above a live, open card. */
  steps?: PlanStep[];
  /** The settled line's words (`settledSummary`); falls back to the user's reply. */
  summary?: SettledLine[] | null;
  /** Send a message as an ordinary task_agent turn. */
  onSend: (message: string) => void;
  /** The card's id in the thread's arrivals (round 9): a card that arrives
   *  after the thread's first paint rises in and lays its rows out. */
  arrivalId?: string;
}) {
  const arrives = useArrives(arrivalId ?? `part:${part.id}`);
  const [staged, setStaged] = useState<ChipEdit[]>([]);
  const [adding, setAdding] = useState(false);
  const [addText, setAddText] = useState("");
  const [pickedId, setPickedId] = useState<string | null>(null);
  const [changing, setChanging] = useState(false);
  const interactive = state.live && state.confirmedOptionId === null && !disabled;
  const confirmedOption =
    state.confirmedOptionId === null
      ? null
      : part.options.find((option) => option.id === state.confirmedOptionId) ?? null;
  const name = partName ?? part.title;

  const settled = confirmedOption !== null || state.answered || !state.live;
  const { shellRef, boxRef, leaving, justSettled, hadOpenForm, hold, holdForSettle } = useSettleMotion(settled);
  // Every send settles the card: hold its height for the settle's commit.
  const send = (message: string) => {
    holdForSettle();
    onSend(message);
  };
  // An arriving open card lays itself out (the animation sweep's entry 5):
  // its chip groups and radio rows fade up 4 px in turn, 80 ms after the
  // card and 40 ms apart (capped at six), so the eye reads it top-down as it
  // lands. They stay clickable throughout. None under reduced motion.
  const cascade = (index: number): { className?: string; style?: CSSProperties } =>
    arrives && !settled ? { className: "anim-cascade", style: { "--i": index } as CSSProperties } : {};
  // The settled form (owner, 2026-11-05, rounds 6 and 8): the part's name
  // and a green line naming the outcome the plan settled on (`summary`), the
  // recorded choice or the user's words. It reads as the user's: the user
  // bubble's surface (Blue Wash fill, Blue Tint border, 32 px left indent),
  // text left-aligned, with the green rule on its right edge over the
  // bubble's own border, the deep green words and the part's name as a small
  // grey label. No tick: the rule and the green words say it.
  const lines: SettledLine[] = (() => {
    if (summary !== undefined && summary !== null && summary.length > 0) return summary;
    if (confirmedOption !== null) return [{ label: null, text: confirmedOption.label }];
    return [{ label: null, text: state.answer !== null && state.answer !== "" ? state.answer : "Answered" }];
  })();
  const settledBody = (
    <div key="settled" className={cn("px-3.5 py-2.5", justSettled && "anim-rise")}>
      <p className={cn(LABEL_CLASS, "text-grey")}>{scrub(name)}</p>
      {/* The scope's groups each take a line under a grey label, so the
          criteria and the filters do not read as one list (owner,
          2026-11-05). */}
      {lines.map((line, index) => (
        // A first line under its own group label stands a step below the
        // part's name.
        <div key={index} className={index > 0 || line.label !== null ? "mt-2" : "mt-0.5"}>
          {/* The group labels a step smaller than the part's name, so the
              name leads (lead, round 6). */}
          {line.label !== null && <p className={cn(LABEL_CLASS, "text-caption text-grey")}>{line.label}</p>}
          {/* The deep green of the green tint's text: it passes contrast at
              the sidebar's Body size too. */}
          <p className="max-w-prose-measure text-lead font-bold text-[#0c6b5a]">{scrub(line.text)}</p>
        </div>
      ))}
      {/* "Change" takes its own line under the green words, left-aligned,
          as a quiet control at Caption size (owner, round 8): never inline
          with the words it would change. */}
      {state.live && confirmedOption !== null && (
        <button
          type="button"
          aria-expanded={changing}
          className={cn(QUIET_CONTROL_CLASS, "mt-1.5 block text-caption")}
          disabled={disabled}
          onClick={() => setChanging((open) => !open)}
        >
          Change
        </button>
      )}
      {changing && state.live && (
        <WordsInput
          label={`Change ${name}`}
          disabled={disabled}
          onSend={(text) => {
            send(`Change this part: ${text}`);
            setChanging(false);
          }}
        />
      )}
    </div>
  );

  const chips = part.chips ?? [];
  // The scope changes through its chips alone (owner, 2026-11-05): the
  // planner's words option is not shown, and the card's one choice is a
  // "Looks right" button that records the planner's primary option and
  // carries any staged chip edits with it, in one turn.
  const primary = part.options.find((option) => option.primary);
  const scopeButton = part.id === "scope" && primary !== undefined;
  const looksRight = () => {
    if (primary === undefined) return;
    send(
      staged.length === 0
        ? confirmMessage(part, primary)
        : `${chipEditMessage(staged)}\n\n[confirm part=${part.id} option=${primary.id}]`,
    );
    setStaged([]);
  };
  const openBody = (
    <>
      <h3 className="max-w-prose-measure text-lead font-bold text-navy">{scrub(part.title)}</h3>
      {part.body != null && part.body !== "" && (
        <p className="mt-1 max-w-prose-measure text-body text-ink">{scrub(part.body)}</p>
      )}

      {chips.length > 0 && (
        <div className="mt-3 space-y-2">
          {chipGroups(chips).map((group, index) => (
            <div key={group.heading ?? "chips"} {...cascade(index)}>
              {group.heading !== null && <p className={cn(LABEL_CLASS, "mb-1 text-grey")}>{group.heading}</p>}
              <div className="flex flex-wrap items-center gap-1.5">
                {group.chips.map((chip) => (
                  <EditableChip
                    key={chip.label}
                    chip={chip}
                    disabled={!interactive}
                    onStage={(edit) => setStaged((edits) => [...edits, edit])}
                  />
                ))}
              </div>
            </div>
          ))}
          <div className="flex flex-wrap items-center gap-1.5">
          {interactive && !adding && (
            <button
              type="button"
              className="cursor-pointer border border-dashed border-line-2 bg-paper px-2 py-1 text-meta font-semibold text-grey hover:text-navy"
              onClick={() => setAdding(true)}
            >
              + add
            </button>
          )}
          {adding && (
            <span className="inline-flex items-center gap-1">
              <input
                type="text"
                value={addText}
                onChange={(event) => setAddText(event.target.value)}
                placeholder="New constraint"
                aria-label="New constraint"
                className="border border-line-2 px-1.5 py-0.5 text-caption"
              />
              <Button
                size="sm"
                variant="secondary"
                onClick={() => {
                  if (addText.trim() !== "") {
                    setStaged((edits) => [...edits, { kind: "add", label: addText, detail: addText }]);
                  }
                  setAddText("");
                  setAdding(false);
                }}
              >
                Save
              </Button>
            </span>
          )}
          </div>
        </div>
      )}

      {staged.length > 0 && (
        <div className="mt-3 border border-yellow bg-yellow-tint/40 px-3 py-2">
          <p className="text-caption font-bold text-navy">Staged changes</p>
          <ul className="mt-1 space-y-0.5 text-lead text-ink">
            {staged.map((edit, index) => (
              <li key={`${edit.kind}-${edit.label}-${index}`}>
                {edit.kind === "remove"
                  ? `Remove "${edit.label}"`
                  : edit.kind === "add"
                    ? `Add: ${edit.detail}`
                    : `Change "${edit.label}" to ${edit.detail}`}
              </li>
            ))}
          </ul>
          <div className="mt-2 flex gap-2">
            {/* On the scope card the staged edits go with "Looks right". */}
            {!scopeButton && (
              <Button
                size="sm"
                disabled={disabled}
                onClick={() => {
                  send(chipEditMessage(staged));
                  setStaged([]);
                }}
              >
                Apply changes
              </Button>
            )}
            <Button size="sm" variant="secondary" onClick={() => setStaged([])}>
              Discard
            </Button>
          </div>
        </div>
      )}

      {scopeButton ? (
        <Button
          variant="secondary"
          className={cn("mt-4 border border-line-2", cascade(chipGroups(chips).length).className)}
          style={cascade(chipGroups(chips).length).style}
          disabled={!interactive}
          data-part-option="primary"
          onClick={looksRight}
        >
          Looks right
        </Button>
      ) : (
        <div role="radiogroup" aria-label={part.title} className="mt-3 flex max-w-prose-measure flex-col gap-1">
          {orderedOptions(part.options).map((option, index) => {
            const selected = pickedId === option.id;
            const words = optionNeedsWords(option);
            return (
              <div key={option.id} {...cascade(index)}>
                <ChoiceRow
                  label={option.label}
                  sentences={[option.sub]}
                  selected={selected}
                  disabled={!interactive}
                  data-option-id={option.id}
                  data-part-option={option.primary ? "primary" : "secondary"}
                  onChoose={() => {
                    setPickedId(option.id);
                    if (!words) send(confirmMessage(part, option));
                  }}
                />
                {words && selected && interactive && (
                  <div className="pl-7 max-sm:pl-0">
                    <WordsInput
                      label={option.label}
                      disabled={disabled}
                      onSend={(text) => {
                        send(`${option.label}: ${text}`);
                        setPickedId(null);
                      }}
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
      {!state.live && (
        <p className="mt-2 text-body text-grey">Updated below — this version is kept for the record.</p>
      )}
    </>
  );

  // One container across the two states (owner, round 8: a fluid settle).
  // The card keeps its box: the surface and the rule ease to the settled
  // look, the box eases to its settled height and across to the user's side,
  // the options and controls fade out over it and the settled words rise in.
  // Under reduced motion it is a cut.
  return (
    <div ref={shellRef} className={cn(arrives && "anim-rise", settled ? "ml-8" : "mr-8")}>
      {steps !== undefined && hadOpenForm && (
        // The stepper line folds away with the settle rather than leaving a
        // gap above the card.
        <div
          className={cn(
            "grid transition-[grid-template-rows,opacity] duration-300 ease-[var(--ease-out-strong)]",
            interactive ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0",
          )}
        >
          <div className="min-h-0 overflow-hidden">
            <div className="pb-2">
              <PlanStepper steps={steps} activeId={part.id} />
            </div>
          </div>
        </div>
      )}
      <div
        ref={boxRef}
        style={hold !== null ? { height: hold } : undefined}
        data-testid={settled ? "part-settled" : "part-card"}
        className={cn(
          "relative overflow-hidden border transition-[background-color,border-color] duration-300 ease-[var(--ease-out-strong)]",
          settled ? "border-r-2 border-blue-tint border-r-green bg-blue-tint-2" : "border-line-2 bg-paper",
        )}
      >
        {settled && settledBody}
        {(!settled || leaving) && (
          <div
            key="open"
            aria-hidden={settled ? true : undefined}
            inert={settled}
            className={cn("px-5 py-4", settled && "pointer-events-none absolute inset-x-0 top-0 anim-fade-out")}
          >
            {openBody}
          </div>
        )}
      </div>
    </div>
  );
}
