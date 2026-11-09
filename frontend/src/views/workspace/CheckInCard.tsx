import { Fragment, useEffect, useRef, useState } from "react";
import { Link } from "react-router";

import { useAnswerCheckIn } from "../../api/mutations";
import { conflictSentences, isConflictCode } from "../../lib/errors";
import { scrub } from "../../lib/scrub";
import type { CheckInOut, StageEntry } from "../../store/types";
import { Button } from "../../ui/brand/Button";
import { Card } from "../../ui/brand/Card";
import { Select } from "../../ui/brand/Select";
import { cn } from "../../ui/brand/cn";
import { DisclosureChevron } from "../../ui/brand/Disclosure";
import { LABEL_CLASS } from "../../ui/brand/label";
import { useArrives } from "../../ui/motion/arrivals";
import { ARRIVE_MS, EASE_OUT_STRONG, prefersReducedMotion } from "../../ui/motion/motion";
import { useToast } from "../../ui/radix/Toast";
import { useEasedHeight } from "../streamPacing";
import { CheckInBundle, type SectionRow, type ThemeRename } from "./CheckInBundle";
import {
  BASELINE_GATE_KIND,
  STOP_THE_RUN,
  baselineGateCard,
  checkInHeadline,
  triggerCopy,
} from "./checkInPresentation";
import { ChoiceRow, WordsInput } from "./PartCard";
import { STEERING_MODE_LABEL, vocabLabel } from "./planVocabulary";
import { LINK_CLASS } from "../../ui/brand/inlineActions";

interface CompiledSteer {
  render: string;
  confirm_token: string;
}

const CHANGE_MODE_VALUES = ["frequent", "moderate", "minimal", "unattended"] as const;
type ChangeModeValue = (typeof CHANGE_MODE_VALUES)[number];

/** The stages whose check-in is about what the search found: its facts line
 *  links to the Sources tab (annex scene 12). */
const SOURCES_CHECK_IN_STAGES = new Set(["acquire", "screen"]);

/** The baseline gate's question, its card's title (round 10, C9: the gate
 *  reads as this week's check-ins do, the question as the title). The
 *  backend's render leads with the same words
 *  (`runtime/baseline_gate.GATE_HEADING`), so the card and the content of
 *  record say the same thing. */
export const BASELINE_GATE_QUESTION = "Does the plan still look right now you have the baseline?";

/** The settled gate's grey label, as a settled part card names its part. */
export const BASELINE_GATE_SETTLED_LABEL = "Baseline";

/**
 * The gate's one facts line (round 10, finding 8): the settings the walk ran
 * from, in the plan document's order, each value as the bundle gives it, the
 * outcomes as a count ("2 outcomes").
 */
export function baselineGateFacts(bundle: Record<string, unknown> | null): string[] {
  const settings = baselineGateCard(bundle).settings;
  const raw = bundle?.["settings"];
  const outcomes =
    raw !== null && typeof raw === "object" && !Array.isArray(raw)
      ? (raw as Record<string, unknown>)["outcomes"]
      : undefined;
  const outcomeCount = Array.isArray(outcomes)
    ? outcomes.filter((item) => typeof item === "string" && item !== "").length
    : 0;
  return settings.map(({ label, value }) =>
    label === "Outcomes" && outcomeCount > 0 ? (outcomeCount === 1 ? "1 outcome" : `${outcomeCount} outcomes`) : value,
  );
}

/**
 * The gate once decided, in the settled part card's language (round 10,
 * finding 8): the user's side of the thread (Blue Wash, a Blue Tint border,
 * the 32 px indent) with the 2 px Green rule on its right edge, the grey
 * label "Baseline" and the chosen option in deep green bold. The decision is
 * said once: this card replaces the user bubble and the "recorded · plan
 * version" line for the gate.
 *
 * Args:
 *   label: The chosen option's label, as the check-in offered it.
 */
export function SettledGateCard({ label }: { label: string }) {
  return (
    <div
      data-testid="settled-gate"
      className="ml-8 border border-r-2 border-blue-tint border-r-green bg-blue-tint-2 px-3.5 py-2.5"
    >
      <p className={cn(LABEL_CLASS, "text-grey")}>{BASELINE_GATE_SETTLED_LABEL}</p>
      <p className="mt-0.5 max-w-prose-measure text-lead font-bold text-green-deep">{scrub(label)}</p>
    </div>
  );
}

/** The waiting-on-you card: the one orange rule, and one 900 ms orange ring
 *  that blooms 150 ms after it arrives (task 058, D15; round 9; reduce
 *  motion honoured by `anim-glow`). */
const WAITING_CARD_CLASS = "anim-glow border-l-2 border-l-orange";

/**
 * The steering check-in card: the deterministic render is the content of
 * record; options are ALWAYS server-supplied (never invented client-side);
 * free text goes through the router confirm gate — the compiled deltas
 * render before anything applies (the 024 fidelity mitigation).
 *
 * `isOwner` (task 033 phase 10c, contract § 11 / rubric 37): steering is
 * owner-only (the same invariant Phase 10b gave the check-in banner), so a
 * non-owner never gets this card at all — hidden entirely, matching
 * `VisibilityControl`'s idiom, rather than a read-only render of a form
 * whose every control is a mutation.
 */
type CheckInCardProps = {
  taskId: string;
  checkIn: CheckInOut;
  stages: StageEntry[];
  isOwner: boolean;
  /** The sidebar's reduced-width card: no facts line (annex scene 13). */
  compact?: boolean;
};

/**
 * The check-in card's motion (task 058, round 9; the animation sweep's
 * entry 3 and the lead's ruling on it). It rises in when it arrives after
 * the thread's first paint, its ring blooming once it has landed. It settles
 * the moment the user chooses, as the part cards do: its contents fade out
 * over 150 ms while its box eases to nothing over 300 ms on the strong
 * ease-out, and the answered line rises in its place in the run block when
 * the run records the choice. If the answer fails the card comes back open
 * with its notice. The "Confirm your steer" step eases the card's height to
 * its new contents, which fade in over 150 ms. Under reduced motion every
 * step is a cut.
 */
export function CheckInCard(props: CheckInCardProps) {
  const arrives = useArrives(`checkin:${props.checkIn.check_in_id}`);
  const [leaving, setLeaving] = useState(false);
  const reduced = prefersReducedMotion();
  const [box, content] = useEasedHeight(!leaving && !reduced);
  const shell = useRef<HTMLDivElement>(null);

  // The shell eases to nothing while the contents fade; it holds there until
  // the stream clears the check-in (the card unmounts) or the answer fails.
  useEffect(() => {
    const outer = shell.current;
    if (!leaving || outer === null || reduced || typeof outer.animate !== "function") return undefined;
    outer.style.overflow = "clip";
    const animation = outer.animate([{ height: `${outer.offsetHeight}px` }, { height: "0px" }], {
      duration: ARRIVE_MS,
      easing: EASE_OUT_STRONG,
      fill: "forwards",
    });
    return () => {
      animation.cancel();
      outer.style.overflow = "";
    };
  }, [leaving, reduced]);

  if (!props.isOwner) return null;
  return (
    <div
      ref={shell}
      data-testid="check-in-shell"
      data-leaving={leaving || undefined}
      className={cn(arrives && "anim-rise", leaving && reduced && "hidden")}
    >
      <div ref={box}>
        <div ref={content} inert={leaving} className={cn(leaving && "anim-fade-out")}>
          <CheckInCardBody {...props} onChosen={() => setLeaving(true)} onFailed={() => setLeaving(false)} />
        </div>
      </div>
    </div>
  );
}

function CheckInCardBody({
  taskId,
  checkIn,
  stages,
  isOwner,
  compact = false,
  onChosen,
  onFailed,
}: CheckInCardProps & {
  /** The user chose: the card settles at once. */
  onChosen: () => void;
  /** The answer failed: the card comes back open. */
  onFailed: () => void;
}) {
  const answer = useAnswerCheckIn(taskId);
  const toast = useToast();
  const [freeText, setFreeText] = useState("");
  const [changeModeValue, setChangeModeValue] = useState<ChangeModeValue>("moderate");
  const [compiled, setCompiled] = useState<CompiledSteer | null>(null);
  const [steerWords, setSteerWords] = useState<string | null>(null);
  const [stagedRenames, setStagedRenames] = useState<ThemeRename[]>([]);
  const [editedSections, setEditedSections] = useState<SectionRow[] | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [pickedId, setPickedId] = useState<string | null>(null);

  if (!isOwner) return null;

  // Toast complements the inline `notice` below — it doesn't replace it: the
  // inline copy is load-bearing right where the user is looking, the toast
  // makes the failure visible even if they've scrolled away from the card.
  const conflictNotice = (error: unknown) => {
    const code = (error as { code?: string }).code;
    const message = isConflictCode(code)
      ? conflictSentences[code]
      : "That couldn't be applied. The check-in is still waiting.";
    setNotice(message);
    onFailed();
    toast.toast({ title: "Check-in update failed", description: message, tone: "error" });
  };

  const sendOption = (optionId: string, params?: Record<string, unknown>) => {
    setNotice(null);
    onChosen();
    // Staged P2 theme renames ride the SINGLE response as validated params on
    // whichever option answers the card (028 strand 14 — no second response).
    const withRenames =
      stagedRenames.length > 0 ? { ...(params ?? {}), renames: stagedRenames } : params;
    answer.mutate(
      {
        checkInId: checkIn.check_in_id,
        body: { kind: "option", option_id: optionId, params: withRenames ?? null },
      },
      { onError: conflictNotice },
    );
  };

  /** Free text goes through the router's compile → confirm gate: nothing
   *  applies until the user confirms the compiled change. */
  const compileSteer = (text: string) => {
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
  };

  if (compiled !== null) {
    return (
      <Card aria-live="polite" className="anim-swap-in-fast border-l-2 border-l-orange p-5">
        <h3 className="text-lead font-bold text-navy">Confirm your steer</h3>
        {steerWords !== null && (
          <div className="mt-2 ml-8 border border-blue-tint bg-blue-tint-2 px-3 py-2">
            <p className="text-body text-ink">{scrub(steerWords)}</p>
          </div>
        )}
        <p className="mt-2 text-body font-semibold text-navy">
          Here's what that would change — apply it?
        </p>
        <pre className="mt-2 overflow-x-auto whitespace-pre-wrap border border-line bg-paper-2 p-3 font-sans text-body text-ink">
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
              onChosen();
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


  const bundleRecord =
    checkIn.bundle !== null && typeof checkIn.bundle === "object" && !Array.isArray(checkIn.bundle)
      ? (checkIn.bundle as Record<string, unknown>)
      : null;
  const noticeLine =
    notice === null ? null : (
      <p role="alert" className="mt-3 text-body text-red">
        {notice}
      </p>
    );

  // The options-scoping baseline gate (task 044, D12) is a decision, not a
  // steer: two server-supplied options end the walk one way or the other,
  // neither carries a delta, and there is nothing here to compile free text
  // into. Its card is the gate's own read — the settings the walk ran from,
  // risk appetite included (N19) — over
  // the same `sendOption` path every other option uses. Questions about the
  // baseline go to the Task Agent composer, which stays open at this pause.
  // Since round 10 (finding 8) it reads as the other check-ins: the question
  // as the title, one facts line with the way to the baseline, no labels;
  // no key assumption (round 12, owner).
  if (checkIn.kind === BASELINE_GATE_KIND) {
    const facts = baselineGateFacts(bundleRecord);
    return (
      <Card aria-live="polite" data-testid="check-in-card" className={cn(WAITING_CARD_CLASS, compact ? "p-4" : "p-5")}>
        <h3 className="max-w-prose-measure text-lead font-bold text-navy">{BASELINE_GATE_QUESTION}</h3>
        {!compact && (
          <p data-testid="check-in-facts" className="mt-1 max-w-prose-measure text-meta text-grey">
            {facts.map((fact) => (
              <Fragment key={fact}>
                <span className="inline-block max-w-full">
                  {scrub(fact)}
                  <span aria-hidden="true">{" ·"}</span>
                  <span className="sr-only">,</span>
                </span>{" "}
              </Fragment>
            ))}
            <Link to={`/tasks/${taskId}/result?view=baseline`} className={LINK_CLASS}>
              Baseline →
            </Link>
          </p>
        )}
        <div role="radiogroup" aria-label={BASELINE_GATE_QUESTION} className="mt-3 flex max-w-prose-measure flex-col gap-1">
          {(checkIn.options ?? []).map((option) => (
            <ChoiceRow
              key={option.id}
              label={option.label}
              sentences={[option.description]}
              selected={pickedId === option.id}
              disabled={answer.isPending}
              data-option-id={option.id}
              onChoose={() => {
                setPickedId(option.id);
                sendOption(option.id);
              }}
            />
          ))}
        </div>
        {noticeLine}
      </Card>
    );
  }

  const headline = checkInHeadline(checkIn.render, checkIn.stage, stages);
  const triggerLines = triggerCopy(checkIn.triggers);
  // One radio list (annex scene 12): the steering's suggested option first
  // with its `why` under it, then the rest in the server's order. The stop
  // option is the card's one "Stop the run" link, and the edit_sections
  // channel is the bundle's own row editing, so neither is a choice here.
  const allOptions = checkIn.options ?? [];
  const choices = [
    ...allOptions.filter((option) => option.suggested),
    ...allOptions.filter((option) => !option.suggested),
  ].filter((option) => option.id !== "abort" && option.id !== "edit_sections");
  const editChannel = allOptions.find((option) => option.id === "edit_sections");
  const sectionsEdited = editedSections !== null && editChannel !== undefined;
  const linksToSources = checkIn.stage !== null && SOURCES_CHECK_IN_STAGES.has(checkIn.stage);

  return (
    <Card aria-live="polite" data-testid="check-in-card" className={cn(WAITING_CARD_CLASS, compact ? "p-4" : "p-5")}>
      <h3 className="max-w-prose-measure text-lead font-bold text-navy">{scrub(headline.title)}</h3>
      {!compact && headline.facts !== null && (
        <p data-testid="check-in-facts" className="mt-1 max-w-prose-measure text-body text-grey">
          {scrub(headline.facts)}
          {linksToSources && (
            <>
              {" · "}
              <Link
                to={`/tasks/${taskId}/sources`}
                className={LINK_CLASS}
              >
                Sources →
              </Link>
            </>
          )}
        </p>
      )}
      {triggerLines.length > 0 && (
        <p className="mt-2 max-w-prose-measure text-body text-grey">{triggerLines.join(" ")}</p>
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
          <p className="text-body text-grey">Untouched rows carry over exactly as displayed.</p>
        </div>
      )}

      <div role="radiogroup" aria-label={headline.title} className="mt-3 flex max-w-prose-measure flex-col gap-1">
        {choices.map((option) => {
          const selected = pickedId === option.id;
          // `change_mode` opens its own select; any other option that needs
          // words opens a line inside the card and compiles like free text.
          const opensForm = option.id === "change_mode" || option.requires_user_input;
          return (
            <div key={option.id}>
              <ChoiceRow
                label={option.label}
                sentences={[option.description, option.suggested ? option.why : null, option.endorsement]}
                selected={selected}
                disabled={answer.isPending}
                data-option-id={option.id}
                data-suggested={option.suggested ? "true" : "false"}
                onChoose={() => {
                  setPickedId(option.id);
                  if (!opensForm) sendOption(option.id);
                }}
              />
              {selected && option.id === "change_mode" && (
                <form
                  className="mt-2 flex items-center gap-2 pl-7"
                  onSubmit={(event) => {
                    event.preventDefault();
                    sendOption("change_mode", { new_mode: changeModeValue });
                  }}
                >
                  <Select
                    id={`change-mode-${checkIn.check_in_id}`}
                    label="New steering mode"
                    value={changeModeValue}
                    options={CHANGE_MODE_VALUES.flatMap((value) => {
                      const label = vocabLabel(STEERING_MODE_LABEL, value);
                      return label === null ? [] : [{ value, label }];
                    })}
                    onChange={setChangeModeValue}
                    className="flex-1"
                  />
                  <Button type="submit" size="sm" variant="outline" disabled={answer.isPending}>
                    Send
                  </Button>
                </form>
              )}
              {selected && option.id !== "change_mode" && option.requires_user_input && (
                <div className="pl-7 max-sm:pl-0">
                  <WordsInput
                    label={option.label}
                    disabled={answer.isPending}
                    onSend={(text) => compileSteer(`${option.label}: ${text}`)}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>

      <details className="group/steer mt-3 border-t border-line pt-3">
        <summary className="group flex cursor-pointer list-none items-center gap-1.5 text-body font-semibold text-grey hover:text-navy [&::-webkit-details-marker]:hidden">
          <DisclosureChevron className="group-open/steer:rotate-90" />
          Or steer in your own words
        </summary>
        <form
          className="mt-2"
          onSubmit={(event) => {
            event.preventDefault();
            const text = freeText.trim();
            if (text.length === 0) return;
            compileSteer(text);
          }}
        >
          <label className="sr-only" htmlFor={`check-in-free-text-${checkIn.check_in_id}`}>
            Or steer in your own words
          </label>
          <div className="flex items-center gap-2">
            <input
              id={`check-in-free-text-${checkIn.check_in_id}`}
              value={freeText}
              onChange={(event) => setFreeText(event.target.value)}
              placeholder="e.g. prioritise UK school-based studies"
              className="min-w-0 flex-1 border border-line-2 bg-paper px-3 py-2 text-body"
            />
            <Button
              type="submit"
              variant="outline"
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
      </details>

      <div className="mt-2 flex justify-end">
        <Button
          variant="ghost"
          size="sm"
          disabled={answer.isPending}
          onClick={() => {
            setNotice(null);
            onChosen();
            answer.mutate(
              { checkInId: checkIn.check_in_id, body: { kind: "abort" } },
              { onError: conflictNotice },
            );
          }}
        >
          {STOP_THE_RUN}
        </Button>
      </div>

      {noticeLine}
    </Card>
  );
}
