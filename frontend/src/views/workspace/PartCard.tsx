import { useState } from "react";

import type { components } from "../../api/gen/types";
import { scrub } from "../../lib/scrub";
import { Button } from "../../ui/brand/Button";
import { cn } from "../../ui/brand/cn";
import { LABEL_CLASS } from "../../ui/brand/label";
import {
  PLAN_PARTS,
  RISK_APPETITE_LABELS,
  SCOPING_DEPTH_LABEL,
  researchApproachId,
  researchApproachLabel,
} from "./planVocabulary";

type PartProposal = components["schemas"]["PartProposalOut"];
type PartChip = components["schemas"]["PartChipOut"];
type PartOption = components["schemas"]["PartOptionOut"];
export type TaskAgentTurn = components["schemas"]["TaskAgentTranscriptTurnOut"];

/** The canned confirm marker a part button appends as the message's final
 *  line. The backend treats it as an ordinary turn; the thread derives ✓
 *  state and hides these bubbles from it. */
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
}

/**
 * Derive each part-bearing turn's card state from the turn sequence alone
 * (F34 rehydration rules): the latest proposal per part id is live; a confirm
 * marker binds to the newest proposal of its part id at the time it was sent;
 * a confirm referencing a superseded proposal never mis-binds.
 */
export function derivePartStates(turns: TaskAgentTurn[]): Map<number, PartState> {
  const ordered = [...turns].sort((a, b) => a.turn_index - b.turn_index);
  const newestProposal = new Map<string, number>();
  for (const turn of ordered) {
    if (turn.part != null) newestProposal.set(turn.part.id, turn.turn_index);
  }
  // Walk forward, tracking the current proposal per part id, binding confirms.
  const currentProposal = new Map<string, number>();
  const confirmed = new Map<number, string>();
  for (const turn of ordered) {
    const target = confirmTarget(turn.user_message);
    if (target !== null) {
      const proposalIndex = currentProposal.get(target.partId);
      if (proposalIndex !== undefined) confirmed.set(proposalIndex, target.optionId);
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
    states.set(turn.turn_index, {
      live: newestProposal.get(turn.part.id) === turn.turn_index,
      answered: turn.turn_index < lastIndex,
      answer: next === undefined ? null : confirmTarget(next.user_message) !== null ? null : next.user_message.trim(),
      confirmedOptionId: confirmed.get(turn.turn_index) ?? null,
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
 *   The line after the part's name, or null when nothing can be named.
 */
export function settledSummary(
  part: PartProposal,
  state: PartState,
  plan: PlanDraft | null | undefined,
  scoping: ScopingPlanDraft | null | undefined,
): string | null {
  const confirmed =
    state.confirmedOptionId === null ? null : (part.options.find((option) => option.id === state.confirmedOptionId)?.label ?? null);
  if (confirmed !== null) return confirmed;
  const fallback = state.answer !== null && state.answer !== "" ? state.answer : null;
  switch (part.id) {
    case "question":
      return plan?.question ?? scoping?.question ?? fallback;
    case "scope": {
      const chips = (part.chips ?? []).map((chip) => chip.label);
      return chips.length > 0 ? chips.join(" · ") : fallback;
    }
    case "thoroughness": {
      if (plan?.search_effort == null || plan.analysis_depth == null) return fallback;
      const preset = researchApproachId(plan.search_effort, plan.analysis_depth);
      const option = preset === null ? undefined : part.options.find((candidate) => candidate.id === THOROUGHNESS_OPTION_BY_PRESET[preset]);
      const label = option?.label ?? researchApproachLabel(plan.search_effort, plan.analysis_depth);
      if (label === null) return fallback;
      return plan.time_band ? `${label} · ${plan.time_band}` : label;
    }
    case "depth":
      return scoping?.depth != null ? (SCOPING_DEPTH_LABEL[scoping.depth] ?? fallback) : fallback;
    case "appetite":
      return scoping?.risk_appetite != null ? (RISK_APPETITE_LABELS[scoping.risk_appetite] ?? fallback) : fallback;
    default:
      return fallback;
  }
}

/** Chip edit staged on the scope card, batched into one task_agent turn. */
interface ChipEdit {
  kind: "change" | "remove" | "add";
  label: string;
  detail?: string;
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
  if (chip.label.startsWith(prefix)) return chip.label;
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
  const displayLabel = chipDisplayLabel(chip);

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
            aria-label={`Edit ${displayLabel}`}
            className="cursor-pointer px-0.5 hover:text-navy"
            onClick={() => setEditing(true)}
          >
            ✎
          </button>
          <button
            type="button"
            aria-label={`Remove ${displayLabel}`}
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
 * i_have_some). Choosing one opens a short input inside the card with its own
 * Send; every other option is a choice and sends at once.
 */
const WORDS_OPTION_IDS = new Set(["refine", "change", "i_have_some"]);

/** Whether choosing this option asks the user for words rather than sending. */
export function optionNeedsWords(option: PartOption): boolean {
  return !option.primary && WORDS_OPTION_IDS.has(option.id);
}

/** The planner's primary option first, the rest in the order it gave them
 *  (annex block H: one shape for a choice). */
export function orderedOptions(options: PartOption[]): PartOption[] {
  return [...options.filter((option) => option.primary), ...options.filter((option) => !option.primary)];
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
 * grey, then "Plan · step n of M · <part>" (annex scene 11).
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
        Plan · step {index + 1} of {steps.length} · {steps[index].name}
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
      className="-mx-2 flex w-[calc(100%+1rem)] cursor-pointer items-start gap-3 px-2 py-2 text-left transition-colors duration-150 hover:bg-paper-2 focus-visible:outline-2 focus-visible:outline-blue disabled:cursor-default disabled:hover:bg-transparent"
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
        className="min-w-0 flex-1 border border-line-2 bg-paper px-3 py-2 text-body text-ink focus-visible:outline-2 focus-visible:outline-blue disabled:bg-ground"
      />
      <Button
        type="submit"
        size="sm"
        variant="secondary"
        className="border border-line-2"
        disabled={disabled || text.trim() === ""}
      >
        {sendLabel}
      </Button>
    </form>
  );
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
  summary?: string | null;
  /** Send a message as an ordinary task_agent turn. */
  onSend: (message: string) => void;
}) {
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

  if (confirmedOption === null && (state.answered || !state.live)) {
    // Answered in the user's own words: one settled line carrying what they
    // wrote, nothing to change here (owner, polish round 2).
    return (
      <div data-testid="part-settled" className="mr-8">
        <p className="max-w-prose-measure text-lead text-grey">
          <span className="font-semibold text-navy">{scrub(name)}</span>
          {(() => {
            const words = summary ?? state.answer;
            return words !== null && words !== undefined && words !== "" ? ` · ${scrub(words)}` : " · answered";
          })()}
        </p>
      </div>
    );
  }

  if (confirmedOption !== null) {
    return (
      <div data-testid="part-settled" className="mr-8">
        <p className="max-w-prose-measure text-lead text-grey">
          <span className="font-semibold text-navy">{scrub(name)}</span> · {scrub(confirmedOption.label)}
          {state.live && (
            <>
              {" · "}
              <button
                type="button"
                aria-expanded={changing}
                className="cursor-pointer font-semibold text-grey underline underline-offset-[3px] hover:text-navy focus-visible:outline-2 focus-visible:outline-blue disabled:cursor-default disabled:no-underline"
                disabled={disabled}
                onClick={() => setChanging((open) => !open)}
              >
                Change
              </button>
            </>
          )}
        </p>
        {changing && state.live && (
          <WordsInput
            label={`Change ${name}`}
            disabled={disabled}
            onSend={(text) => {
              onSend(`Change this part: ${text}`);
              setChanging(false);
            }}
          />
        )}
      </div>
    );
  }

  const chips = part.chips ?? [];
  return (
    <div className="anim-rise mr-8 space-y-2">
      {steps !== undefined && interactive && <PlanStepper steps={steps} activeId={part.id} />}
      <div data-testid="part-card" className="border border-line-2 bg-paper px-5 py-4">
        <h3 className="max-w-prose-measure text-lead font-bold text-navy">{scrub(part.title)}</h3>
        {part.body != null && part.body !== "" && (
          <p className="mt-1 max-w-prose-measure text-body text-ink">{scrub(part.body)}</p>
        )}

        {chips.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            {chips.map((chip) => (
              <EditableChip
                key={chip.label}
                chip={chip}
                disabled={!interactive}
                onStage={(edit) => setStaged((edits) => [...edits, edit])}
              />
            ))}
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
              <Button
                size="sm"
                disabled={disabled}
                onClick={() => {
                  onSend(chipEditMessage(staged));
                  setStaged([]);
                }}
              >
                Apply changes
              </Button>
              <Button size="sm" variant="secondary" onClick={() => setStaged([])}>
                Discard
              </Button>
            </div>
          </div>
        )}

        <div role="radiogroup" aria-label={part.title} className="mt-3 flex max-w-prose-measure flex-col gap-1">
          {orderedOptions(part.options).map((option) => {
            const selected = pickedId === option.id;
            const words = optionNeedsWords(option);
            return (
              <div key={option.id}>
                <ChoiceRow
                  label={option.label}
                  sentences={[option.sub, option.primary ? option.reason : null]}
                  selected={selected}
                  disabled={!interactive}
                  data-option-id={option.id}
                  data-part-option={option.primary ? "primary" : "secondary"}
                  onChoose={() => {
                    setPickedId(option.id);
                    if (!words) onSend(confirmMessage(part, option));
                  }}
                />
                {words && selected && interactive && (
                  <div className="pl-7 max-sm:pl-0">
                    <WordsInput
                      label={option.label}
                      disabled={disabled}
                      onSend={(text) => {
                        onSend(`${option.label}: ${text}`);
                        setPickedId(null);
                      }}
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>
        {!state.live && (
          <p className="mt-2 text-body text-grey">Updated below — this version is kept for the record.</p>
        )}
      </div>
    </div>
  );
}
