import type { QuotaValues } from "../api";
import { Field, INPUT_CLASS } from "../ui";

/**
 * A whole-number field. A text field with the numeric keyboard, not
 * `type="number"`: that one reports "" for "1e" or "abc", which would read as
 * "inherit" and clear the override; as text, every typed character reaches
 * the check below. It has no spin arrows either.
 */
const NUMBER_CLASS = `${INPUT_CLASS} max-w-80`;

/** The red line under a quota field whose value is not a whole number. */
export const WHOLE_NUMBER_ERROR = "Enter a whole number, or leave it empty.";

/** Which fields of a draft are not empty and not a whole number. */
export type QuotaErrors = { tasks?: string; runs?: string };

/** Who a raised "Simultaneous tasks" lets take more of the shared capacity. */
export const WARNING_WHO = {
  person: "this person",
  people: "these people",
  organisation: (org: string) => `each person in ${org}`,
};

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

const WHOLE = /^\d+$/;

/** The fields that would not save: anything but empty or a whole number. */
export function draftErrors(draft: QuotaDraft): QuotaErrors {
  const bad = (text: string) => text.trim() !== "" && !WHOLE.test(text.trim());
  return {
    ...(bad(draft.tasks) && { tasks: WHOLE_NUMBER_ERROR }),
    ...(bad(draft.runs) && { runs: WHOLE_NUMBER_ERROR }),
  };
}

/** Whether a draft can be sent. */
export function draftIsValid(draft: QuotaDraft): boolean {
  return Object.keys(draftErrors(draft)).length === 0;
}

/**
 * The draft as the route takes it: empty is null (inherit), 0 is no limit.
 * Call it only on a draft `draftIsValid` passed: a bad value must never
 * become null, which would clear the override.
 */
export function valuesOf(draft: QuotaDraft): QuotaValues {
  const value = (text: string) => (text.trim() === "" ? null : Number(text.trim()));
  return { task_quota_per_year: value(draft.tasks), runs_per_user: value(draft.runs) };
}

/**
 * The quota form's two fields: "Tasks per year" and
 * "Simultaneous tasks", each empty to inherit. The second carries the
 * warning band (Yellow Tint, the word "Warning:" beside the colour) and is
 * editable all the same.
 */
export function QuotaFields({
  draft,
  onChange,
  tasksPlaceholder,
  runsPlaceholder,
  who = WARNING_WHO.person,
  errors = {},
}: {
  draft: QuotaDraft;
  onChange: (draft: QuotaDraft) => void;
  tasksPlaceholder?: string;
  runsPlaceholder?: string;
  /** The warning's subject: "this person", "these people", "each person in <org>". */
  who?: string;
  /** Red lines under the fields that would not save. */
  errors?: QuotaErrors;
}) {
  return (
    <div className="flex flex-col gap-6">
      <Field
        id="quota-tasks"
        label="Tasks per year"
        help="Leave empty to inherit. Enter 0 for no limit."
        error={errors.tasks}
      >
        {(describedBy) => (
          <input
            id="quota-tasks"
            aria-describedby={describedBy}
            aria-invalid={errors.tasks !== undefined}
            inputMode="numeric"
            autoComplete="off"
            value={draft.tasks}
            placeholder={tasksPlaceholder}
            onChange={(event) => onChange({ ...draft, tasks: event.target.value })}
            className={NUMBER_CLASS}
          />
        )}
      </Field>
      <Field
        id="quota-runs"
        label="Simultaneous tasks"
        error={errors.runs}
        help={
          <p className="border-l-2 border-yellow bg-yellow-tint px-3 py-2 text-body text-ink">
            <strong className="font-bold text-yellow-deep">Warning:</strong> this limit protects the shared run
            capacity. A higher number lets {who} take more of it at the same time, which can slow other
            people&apos;s runs.
          </p>
        }
      >
        {(describedBy) => (
          <input
            id="quota-runs"
            aria-describedby={describedBy}
            aria-invalid={errors.runs !== undefined}
            inputMode="numeric"
            autoComplete="off"
            value={draft.runs}
            placeholder={runsPlaceholder}
            onChange={(event) => onChange({ ...draft, runs: event.target.value })}
            className={NUMBER_CLASS}
          />
        )}
      </Field>
    </div>
  );
}
