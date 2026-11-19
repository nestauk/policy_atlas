/**
 * The onboarding profile form (in-app feedback, element F).
 *
 * Four questions. The first three are required: where the user works, the
 * user's role, and the uses of Policy Atlas (one or more). The same form
 * edits a completed profile from the account menu.
 */
import { useId, useState, type FormEvent } from "react";

import { useSaveProfile, type UserProfile } from "../../api/feedback";
import { JOB_LABELS, type ProfileJob } from "../../lib/onboardingOptions";
import { Button } from "../../ui/brand/Button";
import { ChoiceChip } from "../../ui/feedback/ChoiceChip";

const JOBS = Object.keys(JOB_LABELS) as ProfileJob[];
/** The API's limit for a typed answer (`PROFILE_TEXT_MAX` in the contract). */
const TEXT_MAX = 200;

const QUESTION_CLASS = "text-body font-bold text-navy";
const FIELD_CLASS =
  "min-h-11 w-full border border-line-2 bg-paper px-3 text-body text-navy outline-none focus:border-blue";
const ERROR_CLASS = "mt-2 text-meta text-red";

/**
 * One required question with a typed answer.
 *
 * Args:
 *   question: The question, which is also the label of the input.
 *   value: The typed answer.
 *   onChange: Called with the new answer.
 *   autoComplete: The browser's autofill hint for the input.
 *   error: The message to show when the answer is missing. Undefined: none.
 */
function TextQuestion({
  question,
  value,
  onChange,
  autoComplete,
  error,
}: {
  question: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete: string;
  error?: string;
}) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className={`block ${QUESTION_CLASS}`}>
        {question}
      </label>
      <input
        id={id}
        type="text"
        value={value}
        maxLength={TEXT_MAX}
        autoComplete={autoComplete}
        aria-invalid={error !== undefined}
        onChange={(event) => onChange(event.target.value)}
        className={`mt-3 ${FIELD_CLASS}`}
      />
      {error !== undefined && (
        <p role="alert" className={ERROR_CLASS}>
          {error}
        </p>
      )}
    </div>
  );
}

/**
 * The profile form.
 *
 * Args:
 *   profile: The stored profile, to fill the form for an edit. Undefined or
 *     not completed: the form starts empty.
 *   submitLabel: The words on the submit button.
 *   onSkip: "Skip for now". Omitted: the form offers no skip.
 *   skipping: True while the skip is being recorded.
 *   onSaved: Called after the answers are stored.
 */
export function ProfileForm({
  profile,
  submitLabel,
  onSkip,
  skipping = false,
  onSaved,
}: {
  profile?: UserProfile;
  submitLabel: string;
  onSkip?: () => void;
  skipping?: boolean;
  onSaved?: () => void;
}) {
  const save = useSaveProfile();
  const [department, setDepartment] = useState(profile?.department ?? "");
  const [role, setRole] = useState(profile?.role ?? "");
  const [jobs, setJobs] = useState<ProfileJob[]>(profile?.jobs ?? []);
  const [panelOptIn, setPanelOptIn] = useState<boolean | null>(profile?.panel_opt_in ?? null);
  const [attempted, setAttempted] = useState(false);

  const departmentMissing = department.trim() === "";
  const roleMissing = role.trim() === "";
  const jobsMissing = jobs.length === 0;
  const busy = save.isPending || skipping;

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    setAttempted(true);
    if (departmentMissing || roleMissing || jobsMissing) return;
    save.mutate(
      { department: department.trim(), role: role.trim(), jobs, panel_opt_in: panelOptIn },
      { onSuccess: onSaved },
    );
  };

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-8">
      <TextQuestion
        question="Where do you work?"
        value={department}
        onChange={setDepartment}
        autoComplete="organization"
        error={attempted && departmentMissing ? "Enter where you work." : undefined}
      />

      <TextQuestion
        question="What is your role?"
        value={role}
        onChange={setRole}
        autoComplete="organization-title"
        error={attempted && roleMissing ? "Enter your role." : undefined}
      />

      <fieldset>
        <legend className={QUESTION_CLASS}>
          What will you mainly use Policy Atlas for? (pick all that apply)
        </legend>
        <div className="mt-3 flex flex-col">
          {JOBS.map((value) => (
            <label
              key={value}
              className="flex min-h-11 cursor-pointer items-center gap-3 text-body text-navy"
            >
              <input
                type="checkbox"
                checked={jobs.includes(value)}
                onChange={() =>
                  setJobs((picked) =>
                    picked.includes(value)
                      ? picked.filter((job) => job !== value)
                      : [...picked, value],
                  )
                }
                className="size-4 shrink-0 accent-navy"
              />
              {JOB_LABELS[value]}
            </label>
          ))}
        </div>
        {attempted && jobsMissing && (
          <p role="alert" className={ERROR_CLASS}>
            Choose one use or more.
          </p>
        )}
      </fieldset>

      <fieldset>
        <legend className={QUESTION_CLASS}>
          Can we contact you to take part in a 30 minute user research session?{" "}
          <span className="font-normal text-grey">(optional)</span>
        </legend>
        <div className="mt-3 flex flex-wrap gap-2">
          <ChoiceChip selected={panelOptIn === true} onClick={() => setPanelOptIn(true)}>
            Yes, contact me
          </ChoiceChip>
          <ChoiceChip selected={panelOptIn === false} onClick={() => setPanelOptIn(false)}>
            Not now
          </ChoiceChip>
        </div>
      </fieldset>

      {save.isError && (
        <p role="alert" className={ERROR_CLASS}>
          We could not save your answers. Try again.
        </p>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={busy} className="min-h-11">
          {submitLabel}
        </Button>
        {onSkip !== undefined && (
          <Button variant="ghost" disabled={busy} className="min-h-11" onClick={onSkip}>
            Skip for now
          </Button>
        )}
      </div>
    </form>
  );
}
