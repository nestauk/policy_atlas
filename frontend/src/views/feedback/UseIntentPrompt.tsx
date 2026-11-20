/**
 * "Would you use this report in your work?" (in-app feedback, element C).
 *
 * A centred dialog in front of the report. It opens by itself when the user
 * scrolls down as far as the conclusions and there is no stored answer. The
 * answer is saved on the first click. "Yes, with edits" and "No" open an
 * optional follow-up in place. "Not now" (or Escape) is saved as `dismissed`.
 * After that, and after an answer, a small button stays in the bottom-right
 * corner and opens the dialog again.
 */
import * as Dialog from "@radix-ui/react-dialog";
import { useEffect, useId, useState } from "react";
import { createPortal } from "react-dom";

import { useFeedback, useSubmitFeedback, type FeedbackBody } from "../../api/feedback";
import { useAuth } from "../../auth";
import { markShown } from "../../lib/useIntent";
import { Button } from "../../ui/brand/Button";
import { LINK_CLASS } from "../../ui/brand/inlineActions";
import { ChoiceChip } from "../../ui/feedback/ChoiceChip";
import { portalContainer } from "../../ui/radix/portal";
import { SHEET_SCRIM_CLASS } from "../../ui/radix/Sheet";

type UseIntentBody = Extract<FeedbackBody, { kind: "use_intent" }>;
type UseIntent = UseIntentBody["use_intent"];
type Answer = Exclude<UseIntent, "dismissed">;
type ChangeReason = NonNullable<UseIntentBody["change_reasons"]>[number];

/** The three answers, in display order. */
const ANSWER_LABELS: Readonly<Record<Answer, string>> = {
  as_is: "Yes, as it is",
  with_edits: "Yes, with edits",
  no: "No",
};
const ANSWERS = Object.keys(ANSWER_LABELS) as Answer[];

/** "What would need to change?", in display order. */
const CHANGE_REASON_LABELS: Readonly<Record<ChangeReason, string>> = {
  missing_evidence: "Missing evidence",
  wrong_emphasis: "Wrong emphasis",
  accuracy_concern: "Accuracy concern",
  length: "Length",
  tone_or_format: "Tone or format",
  other: "Other",
};
const CHANGE_REASONS = Object.keys(CHANGE_REASON_LABELS) as ChangeReason[];

/** The answers that open the follow-up. */
const WITH_FOLLOW_UP: ReadonlySet<Answer> = new Set(["with_edits", "no"]);

type Sent = Pick<UseIntentBody, "use_intent" | "change_reasons">;

/**
 * The use-intent question of one report: the dialog and its corner button.
 *
 * Args:
 *   taskId: The task.
 *   artefactId: The report.
 *   triggerId: The `id` of the report section that opens the dialog when it
 *     comes into view (the conclusions).
 */
export function UseIntentPrompt({
  taskId,
  artefactId,
  triggerId,
}: {
  taskId: string;
  artefactId: string;
  triggerId: string;
}) {
  const uid = useId();
  const userId = useAuth().user?.sub ?? "";
  const records = useFeedback(taskId, "use_intent");
  const submit = useSubmitFeedback(taskId);
  const [open, setOpen] = useState(false);
  // What this visit sent last. It stands in for the stored record until the
  // record is read again, so that a fast "close" cannot overwrite an answer.
  const [sent, setSent] = useState<Sent | null>(null);
  const [followUp, setFollowUp] = useState<Answer | null>(null);
  const [reasons, setReasons] = useState<ChangeReason[]>([]);
  const [note, setNote] = useState("");

  const stored = records.data?.find((record) => record.target_id === artefactId)?.payload as
    | Sent
    | undefined;
  const current = sent ?? stored;
  // Nothing is asked until the stored answer is read: asking a user who
  // answered is the one mistake to avoid.
  const unasked = records.data !== undefined && current === undefined;

  // The dialog opens by itself when the trigger section comes into view. A
  // browser with no `IntersectionObserver` never opens it.
  useEffect(() => {
    const target = document.getElementById(triggerId);
    if (!unasked || target === null || typeof IntersectionObserver === "undefined") {
      return undefined;
    }
    const observer = new IntersectionObserver((entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return;
      observer.disconnect();
      markShown(userId, artefactId, new Date());
      setOpen(true);
    });
    observer.observe(target);
    return () => observer.disconnect();
  }, [unasked, triggerId, userId, artefactId]);

  const send = (body: Pick<UseIntentBody, "use_intent" | "change_reasons" | "note">) => {
    submit.mutate({
      kind: "use_intent",
      surface: "report_key_findings",
      task_id: taskId,
      artefact_id: artefactId,
      shown_at: markShown(userId, artefactId, new Date()),
      ...body,
    });
    setSent({ use_intent: body.use_intent, change_reasons: body.change_reasons });
  };
  const close = () => {
    setOpen(false);
    setFollowUp(null);
  };
  // "Not now", Escape or a click outside. Only the first one is new to record.
  const dismiss = () => {
    if (current === undefined) send({ use_intent: "dismissed" });
    close();
  };
  const choose = (answer: Answer) => {
    send({ use_intent: answer });
    setReasons([]);
    setNote("");
    if (WITH_FOLLOW_UP.has(answer)) setFollowUp(answer);
    else close();
  };

  const answered = current !== undefined && current.use_intent !== "dismissed";
  const recorded = answered
    ? [
        ANSWER_LABELS[current.use_intent as Answer],
        ...(current.change_reasons ?? []).map((value) => CHANGE_REASON_LABELS[value]),
      ].join(" · ")
    : null;
  const error = submit.isError && (
    <p role="alert" className="mt-2 text-meta text-red">
      We could not save your answer. Try again.
    </p>
  );

  return (
    <>
      {/* In a portal: an ancestor of the report with a transform would
          otherwise hold the fixed button inside the report column. */}
      {!open &&
        current !== undefined &&
        createPortal(
          <Button
            variant="outline"
            className="fixed bottom-4 right-4 z-30 min-h-11 shadow-overlay print:hidden"
            onClick={() => setOpen(true)}
          >
            Would you use this report?
          </Button>,
          portalContainer() ?? document.body,
        )}
      <Dialog.Root open={open} onOpenChange={(next) => (next ? setOpen(true) : dismiss())}>
        <Dialog.Portal container={portalContainer()}>
          <Dialog.Overlay className={SHEET_SCRIM_CLASS} />
          <Dialog.Content
            aria-describedby={undefined}
            className="fixed left-1/2 top-1/2 z-50 max-h-[90svh] w-[min(30rem,92vw)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto border border-line-2 bg-paper p-6 shadow-overlay"
          >
            <Dialog.Title className="font-display text-lead font-bold text-navy">
              Would you use this report in your work?
            </Dialog.Title>
            {followUp !== null ? (
              <>
                <p id={`${uid}-change`} className="mt-4 text-body font-bold text-navy">
                  What would need to change?{" "}
                  <span className="font-normal text-grey">(optional)</span>
                </p>
                <div
                  role="group"
                  aria-labelledby={`${uid}-change`}
                  className="mt-3 flex flex-wrap gap-2"
                >
                  {CHANGE_REASONS.map((value) => (
                    <ChoiceChip
                      key={value}
                      selected={reasons.includes(value)}
                      onClick={() =>
                        setReasons((chosen) =>
                          chosen.includes(value)
                            ? chosen.filter((one) => one !== value)
                            : [...chosen, value],
                        )
                      }
                    >
                      {CHANGE_REASON_LABELS[value]}
                    </ChoiceChip>
                  ))}
                </div>
                <label
                  htmlFor={`${uid}-note`}
                  className="mt-3 block text-meta font-semibold text-navy"
                >
                  Anything else? <span className="font-normal text-grey">(optional)</span>
                </label>
                <textarea
                  id={`${uid}-note`}
                  rows={2}
                  value={note}
                  maxLength={2000}
                  onChange={(event) => setNote(event.target.value)}
                  className="mt-1.5 w-full border border-line-2 bg-paper px-3 py-2.5 text-body text-navy outline-none focus:border-blue"
                />
                {error}
                <div className="mt-3 flex gap-2">
                  <Button
                    variant="outline"
                    className="min-h-11"
                    disabled={submit.isPending}
                    onClick={() => {
                      send({
                        use_intent: followUp,
                        change_reasons: reasons,
                        note: note.trim() || null,
                      });
                      close();
                    }}
                  >
                    Send
                  </Button>
                  <Button variant="ghost" className="min-h-11" onClick={close}>
                    Skip
                  </Button>
                </div>
              </>
            ) : (
              <>
                {recorded !== null && (
                  <p role="status" className="mt-2 text-meta text-grey">
                    Recorded as “{recorded}”. You can change your answer.
                  </p>
                )}
                <div className="mt-4 flex flex-col gap-2">
                  {ANSWERS.map((answer) => (
                    <Button
                      key={answer}
                      variant="outline"
                      className="min-h-11 w-full justify-center"
                      disabled={submit.isPending}
                      onClick={() => choose(answer)}
                    >
                      {ANSWER_LABELS[answer]}
                    </Button>
                  ))}
                </div>
                {error}
                <button type="button" className={`mt-3 min-h-11 ${LINK_CLASS}`} onClick={dismiss}>
                  {answered ? "Close" : "Not now"}
                </button>
              </>
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  );
}
