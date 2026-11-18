/**
 * "Would you use this report in your work?" (in-app feedback, element C).
 *
 * An inline card under the Key findings section, not a modal. The answer is
 * saved on the first click. "Yes, with edits" and "No" open an optional
 * follow-up in place. After the answer the card is one line with a "change"
 * link. `lib/useIntent.ts` holds the show-once rules.
 */
import { useEffect, useId, useState } from "react";

import { useFeedback, useSubmitFeedback, type FeedbackBody } from "../../api/feedback";
import { useAuth } from "../../auth";
import { firstShownAt, markShown, intentCardState } from "../../lib/useIntent";
import { Button } from "../../ui/brand/Button";
import { Card } from "../../ui/brand/Card";
import { LINK_CLASS } from "../../ui/brand/inlineActions";
import { ChoiceChip } from "../../ui/feedback/ChoiceChip";

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

/**
 * The use-intent card of one report.
 *
 * Args:
 *   taskId: The task.
 *   artefactId: The report.
 */
export function UseIntentCard({ taskId, artefactId }: { taskId: string; artefactId: string }) {
  const uid = useId();
  const userId = useAuth().user?.sub ?? "";
  const records = useFeedback(taskId, "use_intent");
  const submit = useSubmitFeedback(taskId);
  // Read once for this open: a question shown now stays for this visit.
  const [shownBefore] = useState(() => firstShownAt(userId, artefactId) !== null);
  const [editing, setEditing] = useState(false);
  const [followUp, setFollowUp] = useState<Answer | null>(null);
  const [reasons, setReasons] = useState<ChangeReason[]>([]);
  const [note, setNote] = useState("");

  const payload = records.data?.find((record) => record.target_id === artefactId)?.payload as
    | { use_intent: UseIntent; change_reasons?: ChangeReason[] }
    | undefined;
  // Hidden until the stored answer is read: asking a user who answered is
  // the one mistake to avoid.
  const state =
    records.data === undefined ? "hidden" : intentCardState(payload?.use_intent, shownBefore);
  // The first show is remembered at once, so a question that the user
  // leaves unanswered does not come back on a later open.
  useEffect(() => {
    if (state === "ask") markShown(userId, artefactId, new Date());
  }, [state, userId, artefactId]);
  if (state === "hidden") return null;

  const send = (body: Pick<UseIntentBody, "use_intent" | "change_reasons" | "note">) =>
    submit.mutate({
      kind: "use_intent",
      surface: "report_key_findings",
      task_id: taskId,
      artefact_id: artefactId,
      shown_at: markShown(userId, artefactId, new Date()),
      ...body,
    });
  const choose = (answer: Answer) => {
    send({ use_intent: answer });
    setEditing(false);
    setReasons([]);
    setNote("");
    setFollowUp(WITH_FOLLOW_UP.has(answer) ? answer : null);
  };
  const error = submit.isError && (
    <p role="alert" className="mt-2 text-meta text-red">
      We could not save your answer. Try again.
    </p>
  );

  if (followUp !== null) {
    return (
      <Card className="my-6 p-5 print:hidden">
        <p className="text-body font-bold text-navy">
          What would need to change? <span className="font-normal text-grey">(optional)</span>
        </p>
        <div role="group" aria-label="What would need to change?" className="mt-3 flex flex-wrap gap-2">
          {CHANGE_REASONS.map((value) => (
            <ChoiceChip
              key={value}
              selected={reasons.includes(value)}
              onClick={() =>
                setReasons((chosen) =>
                  chosen.includes(value) ? chosen.filter((one) => one !== value) : [...chosen, value],
                )
              }
            >
              {CHANGE_REASON_LABELS[value]}
            </ChoiceChip>
          ))}
        </div>
        <label htmlFor={`${uid}-note`} className="mt-3 block text-meta font-semibold text-navy">
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
              send({ use_intent: followUp, change_reasons: reasons, note: note.trim() || null });
              setFollowUp(null);
            }}
          >
            Send
          </Button>
          <Button variant="ghost" className="min-h-11" onClick={() => setFollowUp(null)}>
            Skip
          </Button>
        </div>
      </Card>
    );
  }

  if (state === "answered" && !editing && payload !== undefined) {
    const recorded = [
      ANSWER_LABELS[payload.use_intent as Answer],
      ...(payload.change_reasons ?? []).map((value) => CHANGE_REASON_LABELS[value]),
    ].join(" · ");
    return (
      <p role="status" className="my-6 text-meta text-grey print:hidden">
        Thanks — recorded as “{recorded}”.{" "}
        <button type="button" className={LINK_CLASS} onClick={() => setEditing(true)}>
          change
        </button>
      </p>
    );
  }

  return (
    <Card className="my-6 p-5 print:hidden">
      <p id={`${uid}-question`} className="text-body font-bold text-navy">
        Would you use this report in your work?
      </p>
      <div role="group" aria-labelledby={`${uid}-question`} className="mt-3 flex flex-col gap-2">
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
      {/* "Not now" is for the first ask only: an answer under edit is kept. */}
      {!editing && (
        <button
          type="button"
          className={`mt-3 min-h-11 ${LINK_CLASS}`}
          disabled={submit.isPending}
          onClick={() => send({ use_intent: "dismissed" })}
        >
          Not now
        </button>
      )}
    </Card>
  );
}
