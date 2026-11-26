/**
 * "Report a problem" (in-app feedback, element E).
 *
 * A button in the app header on every signed-in page. It opens the one modal
 * of the feedback work. The report goes to the Policy Atlas team with the run,
 * the page and the browser attached.
 */
import { useId, useState, type FormEvent } from "react";
import { useLocation } from "react-router";

import { useSubmitFeedback, type FeedbackBody } from "../../api/feedback";
import type { components } from "../../api/gen/types";
import { Button } from "../../ui/brand/Button";
import { Checkbox } from "../../ui/brand/Checkbox";
import { Sheet, SheetContent } from "../../ui/radix/Sheet";

type ProblemBody = Extract<FeedbackBody, { kind: "problem_report" }>;
type ProblemKind = ProblemBody["problem_kind"];
type Task = components["schemas"]["TaskOut"];

/** "What kind of problem?", in display order. */
const PROBLEM_KIND_LABELS: Readonly<Record<ProblemKind, string>> = {
  error: "Something broke or errored",
  stalled: "Search stalled or took too long",
  unusable: "Output isn't usable",
  other: "Something else",
};
const PROBLEM_KINDS = Object.keys(PROBLEM_KIND_LABELS) as ProblemKind[];

/** How many characters of a run id the "Attached automatically" box shows. */
const SHORT_RUN_ID_CHARS = 8;

/**
 * What the report attaches with no input from the user.
 *
 * Args:
 *   task: The open task, or undefined on a page with no task.
 *   page: The page path.
 *   now: The browser's clock.
 *
 * Returns:
 *   The attached fields. `runId` and the step are null when there is no run.
 */
export function attachedContext(task: Task | undefined, page: string, now: Date) {
  const run = task?.active_run ?? task?.latest_run ?? null;
  return {
    runId: run?.capability_run_id ?? null,
    version: import.meta.env.VITE_PA_VERSION || "unknown",
    page,
    stepReached: run?.stage_label ?? run?.stage ?? null,
    stepStatus: run?.status ?? null,
    browser: navigator.userAgent,
    time: now,
  };
}

/**
 * The header button and its modal.
 *
 * Args:
 *   task: The open task, or undefined on a page with no task (the report is
 *     then stored with no run).
 */
export function ReportProblem({ task }: { task: Task | undefined }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="min-h-11 cursor-pointer text-meta font-semibold text-navy hover:text-blue"
      >
        Report a problem
      </button>
      {open && (
        <Sheet open onOpenChange={(next) => !next && setOpen(false)}>
          <SheetContent
            title="Report a problem"
            description="Goes to the Policy Atlas team"
            descriptionHidden
          >
            <ProblemForm task={task} onClose={() => setOpen(false)} />
          </SheetContent>
        </Sheet>
      )}
    </>
  );
}

/** The form in the modal. Mounted when the modal opens, so the time is the opening time. */
function ProblemForm({ task, onClose }: { task: Task | undefined; onClose: () => void }) {
  const uid = useId();
  const location = useLocation();
  const submit = useSubmitFeedback(task?.task_id);
  const [context] = useState(() => attachedContext(task, location.pathname, new Date()));
  const [problemKind, setProblemKind] = useState<ProblemKind | null>(null);
  const [description, setDescription] = useState("");
  const [includeQuestion, setIncludeQuestion] = useState(true);
  const question = task?.question ?? null;

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    submit.mutate({
      kind: "problem_report",
      surface: "app_header",
      task_id: task?.task_id ?? null,
      // No kind is required: a report with none goes with "Something else".
      problem_kind: problemKind ?? "other",
      description: description.trim(),
      page: context.page,
      step_reached: context.stepReached,
      step_status: context.stepStatus,
      query_text: includeQuestion ? question : null,
      client: { browser: context.browser, time: context.time.toISOString() },
    });
  };

  if (submit.isSuccess) {
    return (
      <div className="flex flex-col items-start gap-4">
        <p role="status" className="text-body text-navy">
          Thanks. Your report was sent to the Policy Atlas team.
        </p>
        <Button variant="outline" className="min-h-11" onClick={onClose}>
          Close
        </Button>
      </div>
    );
  }

  const attached: Array<[string, string]> = [
    ["Run", context.runId === null ? "No run" : context.runId.slice(0, SHORT_RUN_ID_CHARS)],
    ["Version", context.version],
    ["Page", context.page],
    [
      "Step reached",
      context.stepReached === null && context.stepStatus === null
        ? "None"
        : [context.stepReached, context.stepStatus].filter(Boolean).join(" · "),
    ],
    ["Browser", context.browser],
    ["Time", context.time.toLocaleString()],
  ];

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-6">
      <fieldset>
        <legend className="text-body font-bold text-navy">What kind of problem?</legend>
        <div className="mt-2 flex flex-col">
          {PROBLEM_KINDS.map((value) => (
            <label
              key={value}
              className="flex min-h-11 cursor-pointer items-center gap-3 text-body text-navy"
            >
              <input
                type="radio"
                name={`${uid}-kind`}
                checked={problemKind === value}
                onChange={() => setProblemKind(value)}
                className="size-4 shrink-0 accent-navy"
              />
              {PROBLEM_KIND_LABELS[value]}
            </label>
          ))}
        </div>
      </fieldset>

      <div>
        <label htmlFor={`${uid}-what`} className="text-body font-bold text-navy">
          What happened?
        </label>
        <textarea
          id={`${uid}-what`}
          rows={4}
          value={description}
          maxLength={5000}
          onChange={(event) => setDescription(event.target.value)}
          className="mt-2 w-full border border-line-2 bg-paper px-3 py-2.5 text-body text-navy outline-none focus:border-blue"
        />
      </div>

      <div className="border border-line bg-ground p-3">
        <p className="text-meta font-bold text-navy">Attached automatically</p>
        <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-meta text-grey">
          {attached.map(([name, value]) => (
            <div key={name} className="contents">
              <dt className="font-semibold">{name}</dt>
              <dd className="min-w-0 [overflow-wrap:anywhere]">{value}</dd>
            </div>
          ))}
        </dl>
      </div>

      {question !== null && (
        <Checkbox
          checked={includeQuestion}
          onChange={setIncludeQuestion}
          label={<span className="text-body text-navy">Include my research question text</span>}
        />
      )}

      {submit.isError && (
        <p role="alert" className="text-meta text-red">
          We could not send your report. Try again.
        </p>
      )}
      <div className="flex gap-3">
        <Button type="submit" disabled={submit.isPending} className="min-h-11">
          Send report
        </Button>
        <Button variant="ghost" className="min-h-11" onClick={onClose}>
          Cancel
        </Button>
      </div>
      <p className="text-meta text-grey">Goes to the Policy Atlas team</p>
    </form>
  );
}
