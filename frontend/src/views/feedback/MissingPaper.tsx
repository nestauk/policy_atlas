/**
 * "A paper I expected is missing" and "Should have been kept"
 * (in-app feedback, element B).
 *
 * The form takes a DOI, a URL or a title. The server works out which paper it
 * is and at which pipeline stage it was lost; the user never chooses a stage.
 * The answer can take longer than the request, so the form polls while the
 * resolution is pending.
 */
import { useId, useState, type FormEvent } from "react";
import { Link } from "react-router";

import {
  useFeedback,
  useFeedbackRecord,
  useRetractFeedback,
  useSubmitFeedback,
  type FeedbackBody,
  type FeedbackRecord,
} from "../../api/feedback";
import { Button } from "../../ui/brand/Button";
import { Card } from "../../ui/brand/Card";
import { PROSE_LINK_CLASS } from "../../ui/brand/inlineActions";

type MissingPaperBody = Extract<FeedbackBody, { kind: "missing_paper" }>;
type FailureStage = NonNullable<NonNullable<FeedbackRecord["resolution"]>["failure_stage"]>;

const FIELD_CLASS =
  "w-full border border-line-2 bg-paper px-3 text-body text-navy outline-none focus:border-blue";

/** What the user reads for each stage. A stage with `found` links to the paper. */
const CONFIRMATIONS: Readonly<Record<FailureStage, { text: string; found: boolean }>> = {
  cited: { text: "This paper is in the report's references.", found: true },
  not_cited: {
    text: "The search found this paper, but the report does not cite it.",
    found: true,
  },
  not_selected: {
    text: "The search found this paper, but the report does not cite it.",
    found: true,
  },
  acquired_only: {
    text: "The search found this paper, but the report does not cite it.",
    found: true,
  },
  screened_out_s2: {
    text: "The search found this paper, but screening removed it. Recorded as a screening override.",
    found: false,
  },
  screened_out_s1: {
    text: "The search found this paper, but screening removed it. Recorded as a screening override.",
    found: false,
  },
  not_retrieved: {
    text: "The search did not find this paper. Added to the checks we run on every search update.",
    found: false,
  },
  unresolved: {
    text: "Thanks — we couldn't match this automatically; we'll review it.",
    found: false,
  },
};

/** The line under the form after a report: pending, then the stage's words. */
function Confirmation({ taskId, record }: { taskId: string; record: FeedbackRecord }) {
  // The first answer can be "pending"; this read polls until the stage is known.
  const latest = useFeedbackRecord(record.feedback_event_id, record).data ?? record;
  const stage = latest.resolution?.failure_stage ?? null;
  if (stage === null) {
    return (
      <p role="status" className="text-meta text-grey">
        Checking where this paper went…
      </p>
    );
  }
  const { text, found } = CONFIRMATIONS[stage];
  return (
    <p role="status" className="text-meta text-navy">
      {text}
      {found && latest.resolution?.resolved_id != null && (
        <>
          {" "}
          <Link
            to={`/tasks/${taskId}/sources/all?status=all&source=${latest.resolution.resolved_id}`}
            className={PROSE_LINK_CLASS}
          >
            Open it in All sources
          </Link>
        </>
      )}
    </p>
  );
}

/**
 * The missing-paper form.
 *
 * Args:
 *   taskId: The task.
 *   artefactId: The report that the form is under. It names the run. Absent
 *     on the Sources tab.
 *   surface: Where the form is.
 */
export function MissingPaperForm({
  taskId,
  artefactId,
  surface,
}: {
  taskId: string;
  artefactId?: string;
  surface: MissingPaperBody["surface"];
}) {
  const uid = useId();
  const submit = useSubmitFeedback(taskId);
  const [rawInput, setRawInput] = useState("");
  const [why, setWhy] = useState("");
  const reported = submit.data;

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (rawInput.trim() === "") return;
    submit.mutate({
      kind: "missing_paper",
      surface,
      task_id: taskId,
      artefact_id: artefactId ?? null,
      raw_input: rawInput.trim(),
      why: why.trim() || null,
    });
  };
  const addAnother = () => {
    submit.reset();
    setRawInput("");
    setWhy("");
  };

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3 print:hidden">
      <div>
        <label htmlFor={`${uid}-paper`} className="text-meta font-semibold text-navy">
          DOI, web address or title
        </label>
        <input
          id={`${uid}-paper`}
          type="text"
          value={rawInput}
          maxLength={500}
          disabled={reported !== undefined}
          onChange={(event) => setRawInput(event.target.value)}
          className={`mt-1.5 min-h-11 ${FIELD_CLASS}`}
        />
      </div>
      <div>
        <label htmlFor={`${uid}-why`} className="text-meta font-semibold text-navy">
          Why does it matter? <span className="font-normal text-grey">(optional)</span>
        </label>
        <textarea
          id={`${uid}-why`}
          rows={2}
          value={why}
          maxLength={2000}
          disabled={reported !== undefined}
          onChange={(event) => setWhy(event.target.value)}
          className={`mt-1.5 py-2.5 ${FIELD_CLASS}`}
        />
      </div>
      {submit.isError && (
        <p role="alert" className="text-meta text-red">
          We could not send this. Try again.
        </p>
      )}
      {reported !== undefined && <Confirmation taskId={taskId} record={reported} />}
      <div className="flex gap-2">
        {reported === undefined ? (
          <Button
            type="submit"
            variant="outline"
            className="min-h-11"
            disabled={submit.isPending || rawInput.trim() === ""}
          >
            Report missing paper
          </Button>
        ) : (
          <Button variant="outline" className="min-h-11" onClick={addAnother}>
            Add another
          </Button>
        )}
      </div>
    </form>
  );
}

/** The card at the foot of the References list (`surface = report_foot`). */
export function MissingPaperCard({ taskId, artefactId }: { taskId: string; artefactId: string }) {
  return (
    <Card className="mt-6 p-5 print:hidden">
      <h3 className="mb-3 text-body font-bold text-navy">A paper I expected is missing</h3>
      <MissingPaperForm taskId={taskId} artefactId={artefactId} surface="report_foot" />
    </Card>
  );
}

/**
 * "Should have been kept" on one screened-out row. A toggle with no free text:
 * a second click retracts it.
 *
 * Args:
 *   taskId: The task.
 *   sourceId: The document's task source identity.
 *   title: The document's title, for the button's name.
 *   className: Placement of the button.
 */
export function ScreeningOverrideButton({
  taskId,
  sourceId,
  title,
  className,
}: {
  taskId: string;
  sourceId: string;
  title: string;
  className?: string;
}) {
  const overrides = useFeedback(taskId, "screening_override");
  const submit = useSubmitFeedback(taskId);
  const retract = useRetractFeedback(taskId, "screening_override");
  const override = overrides.data?.find((record) => record.target_id === sourceId);
  return (
    <div className={className}>
      <Button
        variant="outline"
        size="sm"
        className="min-h-11 print:hidden"
        aria-pressed={override !== undefined}
        aria-label={`Should have been kept: ${title}`}
        disabled={submit.isPending || retract.isPending}
        onClick={() =>
          override !== undefined
            ? retract.mutate(override.feedback_event_id)
            : submit.mutate({
                kind: "screening_override",
                surface: "screened_out_row",
                task_id: taskId,
                source_id: sourceId,
              })
        }
      >
        {override !== undefined ? "Marked: should have been kept" : "Should have been kept"}
      </Button>
      {(submit.isError || retract.isError) && (
        <p role="alert" className="mt-1 text-meta text-red">
          We could not save this. Try again.
        </p>
      )}
    </div>
  );
}
