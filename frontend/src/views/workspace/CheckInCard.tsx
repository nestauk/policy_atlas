import { useRef, useState } from "react";

import { useAnswerCheckIn } from "../../api/mutations";
import { conflictSentences, isConflictCode } from "../../lib/errors";
import { scrub } from "../../lib/scrub";
import { recordSessionAnsweredCheckIn } from "../../store/thread";
import type { CheckInOut, StageEntry } from "../../store/types";
import { Button } from "../../ui/brand/Button";
import { Card } from "../../ui/brand/Card";
import { Chip } from "../../ui/brand/Chip";
import { useToast } from "../../ui/radix/Toast";
import { CheckInBundle, type SectionRow, type ThemeRename } from "./CheckInBundle";
import { presentCheckInRender, triggerCopy } from "./checkInPresentation";
import { STEERING_MODE_LABEL, vocabLabel } from "./planVocabulary";

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
  const toast = useToast();
  const [freeText, setFreeText] = useState("");
  const [changeModeOpen, setChangeModeOpen] = useState(false);
  const [changeModeValue, setChangeModeValue] = useState<ChangeModeValue>("moderate");
  const [compiled, setCompiled] = useState<CompiledSteer | null>(null);
  const [steerWords, setSteerWords] = useState<string | null>(null);
  const [stagedRenames, setStagedRenames] = useState<ThemeRename[]>([]);
  const [editedSections, setEditedSections] = useState<SectionRow[] | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const freeTextRef = useRef<HTMLInputElement>(null);

  // Toast complements the inline `notice` below — it doesn't replace it: the
  // inline copy is load-bearing right where the user is looking, the toast
  // makes the failure visible even if they've scrolled away from the card.
  const conflictNotice = (error: unknown) => {
    const code = (error as { code?: string }).code;
    const message = isConflictCode(code)
      ? conflictSentences[code]
      : "That couldn't be applied. The check-in is still waiting.";
    setNotice(message);
    toast.toast({ title: "Check-in update failed", description: message, tone: "error" });
  };

  const sendOption = (optionId: string, params?: Record<string, unknown>) => {
    setNotice(null);
    const selected = (checkIn.options ?? []).find((option) => option.id === optionId);
    // Staged P2 theme renames ride the SINGLE response as validated params on
    // whichever option answers the card (028 strand 14 — no second response).
    const withRenames =
      stagedRenames.length > 0 ? { ...(params ?? {}), renames: stagedRenames } : params;
    answer.mutate(
      {
        checkInId: checkIn.check_in_id,
        body: { kind: "option", option_id: optionId, params: withRenames ?? null },
      },
      {
        onSuccess: () => {
          if (selected === undefined) return;
          recordSessionAnsweredCheckIn(
            checkIn.check_in_id,
            selected.label,
            (checkIn.options ?? [])
              .filter((option) => option.id !== optionId)
              .map((option) => option.label),
          );
        },
        onError: conflictNotice,
      },
    );
  };

  const stageLabel = findStageLabel(stages, checkIn.stage);
  const presentedRender = presentCheckInRender(checkIn.render, checkIn.stage, stages);

  if (compiled !== null) {
    return (
      <Card aria-live="polite" className="border-l-2 border-l-blue p-5">
        <div className="flex items-center gap-2">
          <Chip tone="blue">Confirm your steer</Chip>
        </div>
        {steerWords !== null && (
          <div className="mt-2 ml-8 border border-blue-tint bg-blue-tint-2 px-3 py-2">
            <p className="text-body text-ink">{scrub(steerWords)}</p>
          </div>
        )}
        <p className="mt-2 text-body font-semibold text-navy">
          Here's what that would change — apply it?
        </p>
        <pre className="mt-2 overflow-x-auto whitespace-pre-wrap border border-line bg-paper-2 p-3 font-sans text-body leading-relaxed text-ink">
          {scrub(compiled.render)}
        </pre>
        <p className="mt-1.5 text-body text-grey">
          If part of your steer can't be honoured, the changes above say which part and why —
          nothing applies until you confirm.
        </p>
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
            Discard — back to the options
          </Button>
        </div>
        {notice !== null && (
          <p role="alert" className="mt-3 text-body text-red">
            {notice}
          </p>
        )}
      </Card>
    );
  }

  const triggerLines = triggerCopy(checkIn.triggers);
  // Suggested options (authored from this run's results) get their own block;
  // the edit_sections channel renders as the bundle's inline row editing, not
  // a button (028 strand 14 — the retype-everything button retired).
  const allOptions = checkIn.options ?? [];
  const canonicalOptions = allOptions.filter(
    (option) => !option.suggested && option.id !== "edit_sections",
  );
  const suggestedOptions = allOptions.filter((option) => option.suggested);
  const editChannel = allOptions.find((option) => option.id === "edit_sections");
  const sectionsEdited = editedSections !== null && editChannel !== undefined;

  const bundleRecord =
    checkIn.bundle !== null && typeof checkIn.bundle === "object" && !Array.isArray(checkIn.bundle)
      ? (checkIn.bundle as Record<string, unknown>)
      : null;

  return (
    <Card aria-live="polite" className="anim-glow border-l-2 border-l-orange p-5">
      <div className="flex flex-wrap items-center gap-2">
        <Chip tone="yellow">Waiting on your input</Chip>
        {stageLabel !== null && <Chip tone="soft">{scrub(stageLabel)}</Chip>}
      </div>
      {triggerLines.length > 0 && (
        <p className="mt-2 max-w-prose-measure text-body leading-relaxed text-grey">{triggerLines.join(" ")}</p>
      )}
      {presentedRender === null ? (
        <pre className="mt-3 overflow-x-auto whitespace-pre-wrap border border-line bg-paper-2 p-3 font-sans text-body leading-relaxed text-ink">
          {scrub(checkIn.render)}
        </pre>
      ) : (
        <div className="mt-3 border border-line bg-paper-2 p-3">
          {/* No decimal completion time, no raw-render disclosure (owner,
              2026-08-05) — the stage label and counts carry the story. */}
          <p className="text-body font-semibold text-navy">{scrub(presentedRender.stageLabel)}</p>
          {presentedRender.counts.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {presentedRender.counts.map(({ label, value }) => (
                <Chip key={label} tone="soft">
                  {label}: {value}
                </Chip>
              ))}
            </div>
          )}
        </div>
      )}

      <CheckInBundle
        bundle={bundleRecord}
        stagedRenames={stagedRenames}
        onStageRename={(rename) =>
          setStagedRenames((staged) => [
            ...staged.filter((entry) => entry.theme_id !== rename.theme_id),
            rename,
          ])
        }
        editedSections={editedSections}
        onEditSections={setEditedSections}
      />

      {sectionsEdited && (
        <div className="mt-3 flex flex-col gap-1">
          <Button
            size="sm"
            disabled={answer.isPending}
            onClick={() =>
              sendOption("edit_sections", {
                delta: { synthesis: { sections: editedSections } },
              })
            }
          >
            Write the report with the edited sections
          </Button>
          <p className="text-body text-grey">
            Untouched rows carry over exactly as displayed.
          </p>
        </div>
      )}

      <div className="mt-4 flex flex-col gap-2">
        {canonicalOptions.map((option) => (
          <div key={option.id} className="flex flex-col gap-2">
            <div className="flex items-start gap-2.5">
              <Button
                variant={
                  (option.id === "continue" || option.id === "as_proposed") && !sectionsEdited
                    ? "primary"
                    : "secondary"
                }
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
            </div>
            {option.endorsement != null && option.endorsement !== "" && (
              // The run's reviewer endorsed this option: its reason renders
              // here, under the option — never a duplicate button.
              <p className="text-body leading-relaxed text-blue">
                {scrub(option.endorsement)}
              </p>
            )}
            {option.description.length > 0 && (
              <p className="text-body leading-relaxed text-grey">{scrub(option.description)}</p>
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
                  className="flex-1 border border-line-2 bg-paper px-2.5 py-1.5 text-meta focus-visible:outline-2 focus-visible:outline-blue"
                >
                  {CHANGE_MODE_VALUES.flatMap((value) => {
                    const label = vocabLabel(STEERING_MODE_LABEL, value);
                    return label === null
                      ? []
                      : [
                          <option key={value} value={value}>
                            {label}
                          </option>,
                        ];
                  })}
                </select>
                <Button type="submit" size="sm" disabled={answer.isPending}>
                  Send
                </Button>
              </form>
            )}
          </div>
        ))}
      </div>

      {suggestedOptions.length > 0 && (
        <div className="mt-4 border border-blue-tint bg-blue-tint/40 px-3 py-2.5">
          <p className="text-meta font-bold uppercase tracking-[0.06em] text-blue">
            Suggested from this run's results
          </p>
          <div className="mt-2 flex flex-col gap-2">
            {suggestedOptions.map((option) => (
              <div key={option.id} className="flex flex-col gap-1">
                <div>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={answer.isPending}
                    onClick={() => sendOption(option.id)}
                  >
                    {scrub(option.label)}
                  </Button>
                </div>
                {option.why != null && option.why !== "" && (
                  <p className="text-body leading-relaxed text-grey">{scrub(option.why)}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

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
                  setSteerWords(text);
                  setFreeText("");
                }
              },
              onError: conflictNotice,
            },
          );
        }}
      >
        <label className="text-body font-semibold text-navy" htmlFor="check-in-free-text">
          Or steer in your own words
        </label>
        <div className="mt-1.5 flex items-center gap-2">
          <input
            id="check-in-free-text"
            ref={freeTextRef}
            value={freeText}
            onChange={(event) => setFreeText(event.target.value)}
            placeholder="e.g. prioritise UK school-based studies"
            className="flex-1 border border-line-2 bg-paper px-3 py-2 text-body focus-visible:outline-2 focus-visible:outline-blue"
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
        <p className="mt-1.5 text-body text-grey">
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
              {
                onSuccess: () =>
                  recordSessionAnsweredCheckIn(
                    checkIn.check_in_id,
                    "Stop the analysis",
                    (checkIn.options ?? []).map((option) => option.label),
                  ),
                onError: conflictNotice,
              },
            );
          }}
        >
          Stop the analysis
        </Button>
      </div>

      {notice !== null && (
        <p role="alert" className="mt-3 text-caption text-red">
          {notice}
        </p>
      )}
    </Card>
  );
}
