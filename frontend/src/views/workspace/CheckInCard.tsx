import { useRef, useState } from "react";

import { useAnswerCheckIn } from "../../api/mutations";
import { conflictSentences, isConflictCode } from "../../lib/errors";
import { scrub } from "../../lib/scrub";
import type { CheckInOut, StageEntry } from "../../store/types";
import { Button } from "../../ui/brand/Button";
import { Card } from "../../ui/brand/Card";
import { Chip } from "../../ui/brand/Chip";

interface CompiledSteer {
  render: string;
  confirm_token: string;
}

const CHANGE_MODE_VALUES = ["frequent", "moderate", "minimal", "unattended"] as const;
type ChangeModeValue = (typeof CHANGE_MODE_VALUES)[number];

/** Look up the most recent stage-entry label for `stage` — the chip must
 *  show the server-supplied label, never the raw stage key, and must not
 *  render at all when no label is known for it. */
function findStageLabel(stages: StageEntry[], stage: string | null): string | null {
  if (stage === null) return null;
  for (let index = stages.length - 1; index >= 0; index--) {
    if (stages[index].stage === stage) return stages[index].label;
  }
  return null;
}

/**
 * The steering check-in card: the deterministic render is the content of
 * record; options are ALWAYS server-supplied (never invented client-side);
 * free text goes through the router confirm gate — the compiled deltas
 * render before anything applies (the 024 fidelity mitigation).
 */
export function CheckInCard({
  projectId,
  checkIn,
  stages,
}: {
  projectId: string;
  checkIn: CheckInOut;
  stages: StageEntry[];
}) {
  const answer = useAnswerCheckIn(projectId);
  const [freeText, setFreeText] = useState("");
  const [changeModeOpen, setChangeModeOpen] = useState(false);
  const [changeModeValue, setChangeModeValue] = useState<ChangeModeValue>("moderate");
  const [compiled, setCompiled] = useState<CompiledSteer | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const freeTextRef = useRef<HTMLInputElement>(null);

  const conflictNotice = (error: unknown) => {
    const code = (error as { code?: string }).code;
    setNotice(
      isConflictCode(code)
        ? conflictSentences[code]
        : "That couldn't be applied. The check-in is still waiting.",
    );
  };

  const sendOption = (optionId: string, params?: Record<string, unknown>) => {
    setNotice(null);
    answer.mutate(
      { checkInId: checkIn.check_in_id, body: { kind: "option", option_id: optionId, params: params ?? null } },
      { onError: conflictNotice },
    );
  };

  const stageLabel = findStageLabel(stages, checkIn.stage);

  if (compiled !== null) {
    return (
      <Card aria-live="polite" className="border-l-2 border-l-blue p-5">
        <div className="flex items-center gap-2">
          <Chip tone="blue">Confirm your steer</Chip>
        </div>
        <p className="mt-2 text-[12.5px] text-grey">
          Here's how your instruction compiled into plan changes. Nothing applies until
          you confirm.
        </p>
        <pre className="mt-3 overflow-x-auto whitespace-pre-wrap border border-line bg-paper-2 p-3 font-sans text-[12.5px] leading-relaxed text-ink">
          {scrub(compiled.render)}
        </pre>
        <div className="mt-4 flex items-center gap-2">
          <Button
            disabled={answer.isPending}
            onClick={() => {
              setNotice(null);
              answer.mutate(
                {
                  checkInId: checkIn.check_in_id,
                  body: {
                    kind: "free_text_confirm",
                    confirm_token: compiled.confirm_token,
                    apply: true,
                  },
                },
                { onSuccess: () => setCompiled(null), onError: conflictNotice },
              );
            }}
          >
            Apply these changes
          </Button>
          <Button
            variant="secondary"
            disabled={answer.isPending}
            onClick={() => {
              answer.mutate(
                {
                  checkInId: checkIn.check_in_id,
                  body: {
                    kind: "free_text_confirm",
                    confirm_token: compiled.confirm_token,
                    apply: false,
                  },
                },
                { onSettled: () => setCompiled(null) },
              );
            }}
          >
            Cancel
          </Button>
        </div>
        {notice !== null && (
          <p role="alert" className="mt-3 text-xs text-red">
            {notice}
          </p>
        )}
      </Card>
    );
  }

  return (
    <Card aria-live="polite" className="border-l-2 border-l-orange p-5">
      <div className="flex flex-wrap items-center gap-2">
        <Chip tone="yellow">Waiting on your input</Chip>
        {stageLabel !== null && <Chip tone="soft">{scrub(stageLabel)}</Chip>}
      </div>
      <pre className="mt-3 overflow-x-auto whitespace-pre-wrap border border-line bg-paper-2 p-3 font-sans text-[12.5px] leading-relaxed text-ink">
        {scrub(checkIn.render)}
      </pre>

      <div className="mt-4 flex flex-col gap-2">
        {(checkIn.options ?? []).map((option) => (
          <div key={option.id} className="flex flex-col gap-2">
            <div className="flex items-start gap-2.5">
              <Button
                variant={option.id === "continue" ? "primary" : "secondary"}
                size="sm"
                disabled={answer.isPending}
                onClick={() => {
                  if (option.id === "change_mode") {
                    setChangeModeOpen((open) => !open);
                    return;
                  }
                  if (option.requires_user_input) {
                    // Parameterised options beyond `change_mode` don't have
                    // a server-shaped params form — steer them honestly
                    // through the free-text compile→confirm path instead
                    // of sending a made-up `{ value }` params body.
                    setFreeText(`${option.label}: `);
                    freeTextRef.current?.focus();
                    return;
                  }
                  sendOption(option.id);
                }}
              >
                {scrub(option.label)}
              </Button>
              {option.suggested && <Chip tone="blue">Suggested</Chip>}
            </div>
            {option.description.length > 0 && (
              <p className="text-xs leading-relaxed text-grey">{scrub(option.description)}</p>
            )}
            {option.id === "change_mode" && changeModeOpen && (
              <form
                className="flex items-center gap-2"
                onSubmit={(event) => {
                  event.preventDefault();
                  sendOption("change_mode", { new_mode: changeModeValue });
                  setChangeModeOpen(false);
                }}
              >
                <label className="sr-only" htmlFor="change-mode-select">
                  New steering mode
                </label>
                <select
                  id="change-mode-select"
                  value={changeModeValue}
                  onChange={(event) => setChangeModeValue(event.target.value as ChangeModeValue)}
                  className="flex-1 border border-line-2 bg-paper px-2.5 py-1.5 text-xs focus-visible:outline-2 focus-visible:outline-blue"
                >
                  {CHANGE_MODE_VALUES.map((value) => (
                    <option key={value} value={value}>
                      {value[0].toUpperCase() + value.slice(1)}
                    </option>
                  ))}
                </select>
                <Button type="submit" size="sm" disabled={answer.isPending}>
                  Send
                </Button>
              </form>
            )}
          </div>
        ))}
      </div>

      <form
        className="mt-4 border-t border-line pt-4"
        onSubmit={(event) => {
          event.preventDefault();
          const text = freeText.trim();
          if (text.length === 0) return;
          setNotice(null);
          answer.mutate(
            { checkInId: checkIn.check_in_id, body: { kind: "free_text", text } },
            {
              onSuccess: (result) => {
                if (result.kind === "compiled") {
                  setCompiled(result.compiled);
                  setFreeText("");
                }
              },
              onError: conflictNotice,
            },
          );
        }}
      >
        <label className="text-xs font-semibold text-navy" htmlFor="check-in-free-text">
          Or steer in your own words
        </label>
        <div className="mt-1.5 flex items-center gap-2">
          <input
            id="check-in-free-text"
            ref={freeTextRef}
            value={freeText}
            onChange={(event) => setFreeText(event.target.value)}
            placeholder="e.g. prioritise UK school-based studies"
            className="flex-1 border border-line-2 bg-paper px-3 py-2 text-[12.5px] focus-visible:outline-2 focus-visible:outline-blue"
          />
          <Button
            type="submit"
            variant="secondary"
            size="sm"
            disabled={answer.isPending || freeText.trim().length === 0}
          >
            Compile
          </Button>
        </div>
        <p className="mt-1.5 text-[11px] text-grey">
          Your words compile into plan changes you confirm before they apply.
        </p>
      </form>

      <div className="mt-3 flex justify-end">
        <Button
          variant="ghost"
          size="sm"
          disabled={answer.isPending}
          onClick={() => {
            setNotice(null);
            answer.mutate(
              { checkInId: checkIn.check_in_id, body: { kind: "abort" } },
              { onError: conflictNotice },
            );
          }}
        >
          Stop the analysis
        </Button>
      </div>

      {notice !== null && (
        <p role="alert" className="mt-3 text-xs text-red">
          {notice}
        </p>
      )}
    </Card>
  );
}
