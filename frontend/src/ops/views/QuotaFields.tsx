import type { QuotaValues } from "../api";
import { Field, INPUT_CLASS } from "../ui";

/** A form's two number fields as typed: "" means inherit. */
export interface QuotaDraft {
  tasks: string;
  runs: string;
}

export function draftOf(values: { task_quota_per_year?: number | null; runs_per_user?: number | null }): QuotaDraft {
  return {
    tasks: values.task_quota_per_year == null ? "" : String(values.task_quota_per_year),
    runs: values.runs_per_user == null ? "" : String(values.runs_per_user),
  };
}

/** The draft as the route takes it: empty is null (inherit), 0 is no limit. */
export function valuesOf(draft: QuotaDraft): QuotaValues {
  const value = (text: string) => (text.trim() === "" ? null : Math.max(0, Math.floor(Number(text))));
  return { task_quota_per_year: value(draft.tasks), runs_per_user: value(draft.runs) };
}

/**
 * The quota form's two fields (contract B12): "Tasks per year" and
 * "Simultaneous tasks", each empty to inherit. The second carries the
 * warning band (Yellow Tint, the word "Warning:" beside the colour) and is
 * editable all the same.
 */
export function QuotaFields({
  draft,
  onChange,
  tasksPlaceholder,
  runsPlaceholder,
}: {
  draft: QuotaDraft;
  onChange: (draft: QuotaDraft) => void;
  tasksPlaceholder?: string;
  runsPlaceholder?: string;
}) {
  return (
    <div className="flex flex-col gap-6">
      <Field id="quota-tasks" label="Tasks per year" help="Leave empty to inherit. Enter 0 for no limit.">
        <input
          id="quota-tasks"
          type="number"
          min={0}
          step={1}
          inputMode="numeric"
          value={draft.tasks}
          placeholder={tasksPlaceholder}
          onChange={(event) => onChange({ ...draft, tasks: event.target.value })}
          className={`${INPUT_CLASS} max-w-80`}
        />
      </Field>
      <Field
        id="quota-runs"
        label="Simultaneous tasks"
        help={
          <p className="border-l-2 border-yellow bg-yellow-tint px-3 py-2 text-body text-ink">
            <strong className="font-bold text-yellow-deep">Warning:</strong> this limit protects the shared run
            capacity. A higher number lets this person take more of it at the same time, which can slow other
            people&apos;s runs.
          </p>
        }
      >
        <input
          id="quota-runs"
          type="number"
          min={0}
          step={1}
          inputMode="numeric"
          value={draft.runs}
          placeholder={runsPlaceholder}
          onChange={(event) => onChange({ ...draft, runs: event.target.value })}
          className={`${INPUT_CLASS} max-w-80`}
        />
      </Field>
    </div>
  );
}
