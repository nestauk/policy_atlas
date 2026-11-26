/**
 * "Useful" / "Not relevant" on one document (in-app feedback, element A).
 *
 * Two icon buttons. The flag is saved on the first click. "Not relevant"
 * opens a panel under the row with optional reasons and a note, which refine
 * the saved flag. A second click on the pressed button retracts the flag.
 */
import { useId, useState } from "react";

import {
  useFeedback,
  useRetractFeedback,
  useSubmitFeedback,
  type FeedbackBody,
} from "../../api/feedback";
import { Button } from "../../ui/brand/Button";
import { cn } from "../../ui/brand/cn";
import { ChoiceChip } from "../../ui/feedback/ChoiceChip";

type CitationFlagBody = Extract<FeedbackBody, { kind: "citation_flag" }>;
type Action = CitationFlagBody["action"];
type Reason = NonNullable<CitationFlagBody["reason"]>;

/** The reasons for "Not relevant", in display order. */
const REASON_LABELS: Readonly<Record<Reason, string>> = {
  off_topic: "Off topic",
  wrong_population: "Wrong population or setting",
  not_evidence: "Not evidence (e.g. methods paper)",
  duplicate: "Duplicate",
  other: "Other",
};
const REASONS = Object.keys(REASON_LABELS) as Reason[];

/** The two thumb glyphs, as SVG path data on a 24 px grid. */
const THUMB_PATHS: Readonly<Record<Action, string[]>> = {
  useful: [
    "M7 10v12",
    "M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z",
  ],
  not_relevant: [
    "M17 14V2",
    "M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88Z",
  ],
};
const ACTION_LABELS: Readonly<Record<Action, string>> = {
  useful: "Useful",
  not_relevant: "Not relevant",
};

/** One thumb button: a toggle with a name and a 44 px target. */
function ThumbButton({
  action,
  pressed,
  title,
  disabled,
  onClick,
}: {
  action: Action;
  pressed: boolean;
  title: string;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      aria-label={`${ACTION_LABELS[action]}: ${title}`}
      title={ACTION_LABELS[action]}
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "flex size-11 cursor-pointer items-center justify-center transition-colors duration-150 disabled:cursor-default",
        pressed ? "bg-blue-tint-2 text-navy" : "text-grey hover:bg-hover-fill hover:text-navy",
      )}
    >
      <svg
        aria-hidden="true"
        viewBox="0 0 24 24"
        className="size-5"
        fill={pressed ? "currentColor" : "none"}
        fillOpacity={0.15}
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        {THUMB_PATHS[action].map((d) => (
          <path key={d} d={d} />
        ))}
      </svg>
    </button>
  );
}

/**
 * The two flag buttons of one document, with the "Not relevant" panel.
 *
 * Args:
 *   taskId: The task.
 *   artefactId: The report that the row is in. It names the run. Absent on
 *     the Sources tab.
 *   sourceId: The document's task source identity.
 *   title: The document's title, for the buttons' names.
 *   surface: Where the row is.
 *   className: Placement of the buttons.
 */
export function CitationFlag({
  taskId,
  artefactId,
  sourceId,
  title,
  surface,
  className,
}: {
  taskId: string;
  artefactId?: string;
  sourceId: string;
  title: string;
  surface: CitationFlagBody["surface"];
  className?: string;
}) {
  const uid = useId();
  const flags = useFeedback(taskId, "citation_flag");
  const submit = useSubmitFeedback(taskId);
  const retract = useRetractFeedback(taskId, "citation_flag");
  const flag = flags.data?.find((record) => record.target_id === sourceId);
  const action = flag?.payload.action as Action | undefined;

  const [panelOpen, setPanelOpen] = useState(false);
  const [reason, setReason] = useState<Reason | null>(null);
  const [note, setNote] = useState("");
  const busy = submit.isPending || retract.isPending;

  const send = (next: Pick<CitationFlagBody, "action" | "reason" | "note">) =>
    submit.mutate({
      kind: "citation_flag",
      surface,
      task_id: taskId,
      artefact_id: artefactId ?? null,
      source_id: sourceId,
      ...next,
    });
  const undo = () => {
    if (flag !== undefined) retract.mutate(flag.feedback_event_id);
    setPanelOpen(false);
  };
  const press = (pressed: Action) => {
    if (action === pressed) {
      undo();
      return;
    }
    send({ action: pressed });
    setReason(null);
    setNote("");
    setPanelOpen(pressed === "not_relevant");
  };

  return (
    <div className={cn("print:hidden", className)}>
      <div className="flex gap-1">
        <ThumbButton
          action="useful"
          pressed={action === "useful"}
          title={title}
          disabled={busy}
          onClick={() => press("useful")}
        />
        <ThumbButton
          action="not_relevant"
          pressed={action === "not_relevant"}
          title={title}
          disabled={busy}
          onClick={() => press("not_relevant")}
        />
      </div>
      {panelOpen && (
        <div className="mt-2 flex flex-col gap-3 border border-line-2 bg-paper p-3">
          <div role="group" aria-label="Why is it not relevant? (optional)" className="flex flex-wrap gap-2">
            {REASONS.map((value) => (
              <ChoiceChip
                key={value}
                selected={reason === value}
                onClick={() => setReason(reason === value ? null : value)}
              >
                {REASON_LABELS[value]}
              </ChoiceChip>
            ))}
          </div>
          <div>
            <label htmlFor={`${uid}-note`} className="text-meta font-semibold text-navy">
              Note <span className="font-normal text-grey">(optional)</span>
            </label>
            <input
              id={`${uid}-note`}
              type="text"
              value={note}
              maxLength={2000}
              onChange={(event) => setNote(event.target.value)}
              className="mt-1.5 min-h-11 w-full border border-line-2 bg-paper px-3 text-body text-navy outline-none focus:border-blue"
            />
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              className="min-h-11"
              disabled={busy}
              onClick={() => {
                send({ action: "not_relevant", reason, note: note.trim() || null });
                setPanelOpen(false);
              }}
            >
              Save
            </Button>
            <Button variant="ghost" size="sm" className="min-h-11" disabled={busy} onClick={undo}>
              Undo
            </Button>
          </div>
        </div>
      )}
      {(submit.isError || retract.isError) && (
        <p role="alert" className="mt-1 text-meta text-red">
          We could not save this. Try again.
        </p>
      )}
    </div>
  );
}
