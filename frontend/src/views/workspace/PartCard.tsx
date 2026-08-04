import { useState } from "react";

import type { components } from "../../api/gen/types";
import { scrub } from "../../lib/scrub";
import { Button } from "../../ui/brand/Button";

type PartProposal = components["schemas"]["PartProposalOut"];
type PartChip = components["schemas"]["PartChipOut"];
type PartOption = components["schemas"]["PartOptionOut"];
export type PlanningTurn = components["schemas"]["PlanningTranscriptTurnOut"];

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
  /** The option id a later (pre-supersession) confirm turn recorded, if any. */
  confirmedOptionId: string | null;
}

/**
 * Derive each part-bearing turn's card state from the turn sequence alone
 * (F34 rehydration rules): the latest proposal per part id is live; a confirm
 * marker binds to the newest proposal of its part id at the time it was sent;
 * a confirm referencing a superseded proposal never mis-binds.
 */
export function derivePartStates(turns: PlanningTurn[]): Map<number, PartState> {
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
  for (const turn of ordered) {
    if (turn.part == null) continue;
    states.set(turn.turn_index, {
      live: newestProposal.get(turn.part.id) === turn.turn_index,
      confirmedOptionId: confirmed.get(turn.turn_index) ?? null,
    });
  }
  return states;
}

/** Chip edit staged on the scope card, batched into one planning turn. */
interface ChipEdit {
  kind: "change" | "remove" | "add";
  label: string;
  detail?: string;
}

/** Compose the single batched planning-turn message for staged chip edits. */
export function chipEditMessage(edits: ChipEdit[]): string {
  const lines = edits.map((edit) => {
    if (edit.kind === "remove") return `- Remove "${edit.label}".`;
    if (edit.kind === "add") return `- Add: ${edit.detail ?? ""}.`;
    return `- Change "${edit.label}" to: ${edit.detail ?? ""}.`;
  });
  return `Update the scope:\n${lines.join("\n")}`;
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

  if (editing && !disabled) {
    return (
      <span className="inline-flex flex-wrap items-center gap-1 border border-blue-tint bg-paper px-2 py-1">
        <span className="text-caption font-semibold text-navy">{scrub(chip.label)}</span>
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
          Stage
        </Button>
        <Button size="sm" variant="secondary" onClick={() => setEditing(false)}>
          Cancel
        </Button>
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1 border border-blue-tint bg-blue-tint px-2 py-1 text-caption font-semibold text-blue">
      {scrub(chip.label)}
      {!disabled && (
        <>
          <button
            type="button"
            aria-label={`Edit ${chip.label}`}
            className="cursor-pointer px-0.5 hover:text-navy"
            onClick={() => setEditing(true)}
          >
            ✎
          </button>
          <button
            type="button"
            aria-label={`Remove ${chip.label}`}
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
 * One structured part proposal in the planning thread (028 fork A; binding
 * record: mockup/planning-stage.html). Renders ONLY what the reply carries —
 * server-supplied labels, never enum keys. Superseded proposals stay in the
 * history but render inert; the ✓ state derives from later confirm turns.
 */
export function PartCard({
  part,
  state,
  disabled,
  onSend,
  onPrefill,
}: {
  part: PartProposal;
  state: PartState;
  /** True while the composer is disabled (run active / turn in flight). */
  disabled: boolean;
  /** Send a canned message as an ordinary planning turn. */
  onSend: (message: string) => void;
  /** Put text in the composer for the user to finish. */
  onPrefill: (message: string) => void;
}) {
  const [staged, setStaged] = useState<ChipEdit[]>([]);
  const [adding, setAdding] = useState(false);
  const [addText, setAddText] = useState("");
  const interactive = state.live && state.confirmedOptionId === null && !disabled;
  const confirmedOption =
    state.confirmedOptionId === null
      ? null
      : part.options.find((option) => option.id === state.confirmedOptionId) ?? null;

  // Presets (options carrying a sub line) are concrete choices — they send.
  // A bare secondary option is an invitation to say more — it prefills.
  const sendsDirectly = (option: PartOption) => option.primary || option.sub != null;

  return (
    <div data-testid="part-card" className="anim-rise mr-8 border border-line-2 bg-paper px-4 py-3 shadow-sm">
      <p className="text-caption font-bold uppercase tracking-wide text-grey">
        {scrub(part.step_label)}
      </p>
      <h3 className="mt-1 max-w-prose-measure text-body font-bold text-navy">
        {scrub(part.title)}
      </h3>
      {part.body != null && part.body !== "" && (
        <p className="mt-1 max-w-prose-measure text-meta text-grey">{scrub(part.body)}</p>
      )}

      {(part.chips ?? []).length > 0 && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {(part.chips ?? []).map((chip) => (
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
              className="cursor-pointer border border-dashed border-line-2 bg-paper px-2 py-1 text-caption font-semibold text-grey hover:text-navy"
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
                Stage
              </Button>
            </span>
          )}
        </div>
      )}

      {staged.length > 0 && (
        <div className="mt-2 border border-yellow bg-yellow-tint/40 px-3 py-2">
          <p className="text-caption font-bold text-navy">Staged changes</p>
          <ul className="mt-1 space-y-0.5 text-caption text-ink">
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

      {confirmedOption !== null ? (
        <p className="mt-2 text-meta font-bold text-green-strong">
          ✓ Confirmed{confirmedOption.label !== "" ? ` — ${scrub(confirmedOption.label)}` : ""}
          {state.live && (
            <button
              type="button"
              className="ml-2 cursor-pointer text-caption font-semibold text-grey underline"
              disabled={disabled}
              onClick={() => onPrefill("Change this part: ")}
            >
              Change
            </button>
          )}
        </p>
      ) : (
        <div className="mt-3 flex flex-wrap gap-2">
          {part.options.map((option) => (
            <Button
              key={option.id}
              data-option-id={option.id}
              data-part-option={option.primary ? "primary" : "secondary"}
              variant={option.primary ? "primary" : "secondary"}
              disabled={!interactive}
              onClick={() =>
                sendsDirectly(option)
                  ? onSend(confirmMessage(part, option))
                  : onPrefill(`${option.label}: `)
              }
            >
              <span className="text-left">
                {scrub(option.label)}
                {option.sub != null && option.sub !== "" && (
                  <span className="block text-caption font-normal opacity-85">
                    {scrub(option.sub)}
                  </span>
                )}
              </span>
            </Button>
          ))}
        </div>
      )}
      {confirmedOption === null && part.options.some((option) => option.reason != null && option.reason !== "") && (
        <p className="mt-1.5 max-w-prose-measure text-caption text-grey">
          {part.options
            .filter((option) => option.reason != null && option.reason !== "")
            .map((option) => scrub(option.reason ?? ""))}
        </p>
      )}
      {!state.live && state.confirmedOptionId === null && (
        <p className="mt-2 text-caption text-grey">Updated below — this version is kept for the record.</p>
      )}
    </div>
  );
}
