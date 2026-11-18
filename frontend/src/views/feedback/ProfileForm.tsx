/**
 * The onboarding profile form (in-app feedback, element F).
 *
 * Three questions. The first two are required: where the user works
 * (department and team type) and the main use of Policy Atlas. The same form
 * edits a completed profile from the account menu.
 */
import { useId, useState, type FormEvent } from "react";

import { useSaveProfile, type UserProfile } from "../../api/feedback";
import {
  DEPARTMENTS,
  JOB_LABELS,
  OTHER_DEPARTMENT,
  TEAM_TYPE_LABELS,
  departmentForEmail,
  type ProfileJob,
  type TeamType,
} from "../../lib/onboardingOptions";
import { Button } from "../../ui/brand/Button";
import { Select } from "../../ui/brand/Select";
import { ChoiceChip } from "../../ui/feedback/ChoiceChip";

const TEAM_TYPES = Object.keys(TEAM_TYPE_LABELS) as TeamType[];
const JOBS = Object.keys(JOB_LABELS) as ProfileJob[];

const QUESTION_CLASS = "text-body font-bold text-navy";
const FIELD_CLASS =
  "min-h-11 w-full border border-line-2 bg-paper px-3 text-body text-navy outline-none focus:border-blue";
const ERROR_CLASS = "mt-2 text-meta text-red";

/**
 * The profile form.
 *
 * Args:
 *   profile: The stored profile, to fill the form for an edit. Undefined or
 *     not completed: the form starts empty, with the department prefilled.
 *   email: The user's email address, for the department prefill.
 *   submitLabel: The words on the submit button.
 *   onSkip: "Skip for now". Omitted: the form offers no skip.
 *   skipping: True while the skip is being recorded.
 *   onSaved: Called after the answers are stored.
 */
export function ProfileForm({
  profile,
  email,
  submitLabel,
  onSkip,
  skipping = false,
  onSaved,
}: {
  profile?: UserProfile;
  email?: string | null;
  submitLabel: string;
  onSkip?: () => void;
  skipping?: boolean;
  onSaved?: () => void;
}) {
  const save = useSaveProfile();
  const uid = useId();
  const [department, setDepartment] = useState(profile?.department ?? departmentForEmail(email));
  const [departmentOther, setDepartmentOther] = useState(profile?.department_other ?? "");
  const [teamType, setTeamType] = useState<TeamType | null>(profile?.team_type ?? null);
  const [primaryJob, setPrimaryJob] = useState<ProfileJob | null>(profile?.primary_job ?? null);
  const [secondaryJob, setSecondaryJob] = useState<ProfileJob | "">(profile?.secondary_job ?? "");
  const [secondOpen, setSecondOpen] = useState(profile?.secondary_job != null);
  const [panelOptIn, setPanelOptIn] = useState<boolean | null>(profile?.panel_opt_in ?? null);
  const [attempted, setAttempted] = useState(false);

  const workMissing = department === "" || teamType === null;
  const jobMissing = primaryJob === null;
  const busy = save.isPending || skipping;

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    setAttempted(true);
    if (workMissing || jobMissing) return;
    save.mutate(
      {
        department,
        department_other:
          department === OTHER_DEPARTMENT && departmentOther.trim() !== ""
            ? departmentOther.trim()
            : null,
        team_type: teamType,
        primary_job: primaryJob,
        secondary_job: secondOpen && secondaryJob !== "" ? secondaryJob : null,
        panel_opt_in: panelOptIn,
      },
      { onSuccess: onSaved },
    );
  };

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-8">
      <fieldset className="flex flex-col gap-3">
        <legend className={QUESTION_CLASS}>Where do you work?</legend>
        <Select
          label="Department"
          value={department}
          options={DEPARTMENTS}
          onChange={setDepartment}
          placeholder="Choose your department"
          className="mt-3 min-h-11 w-full"
        />
        {department === OTHER_DEPARTMENT && (
          <div>
            <label htmlFor={`${uid}-other`} className="text-meta font-semibold text-navy">
              Department or organisation <span className="font-normal text-grey">(optional)</span>
            </label>
            <input
              id={`${uid}-other`}
              type="text"
              value={departmentOther}
              maxLength={200}
              onChange={(event) => setDepartmentOther(event.target.value)}
              className={`mt-1.5 ${FIELD_CLASS}`}
            />
          </div>
        )}
        <div role="group" aria-label="Team type" className="flex flex-wrap gap-2">
          {TEAM_TYPES.map((value) => (
            <ChoiceChip
              key={value}
              selected={teamType === value}
              onClick={() => setTeamType(value)}
            >
              {TEAM_TYPE_LABELS[value]}
            </ChoiceChip>
          ))}
        </div>
        {attempted && workMissing && (
          <p role="alert" className={ERROR_CLASS}>
            Choose your department and your team type.
          </p>
        )}
      </fieldset>

      <fieldset>
        <legend className={QUESTION_CLASS}>
          What will you mainly use Policy Atlas for? (pick one)
        </legend>
        <div className="mt-3 flex flex-col">
          {JOBS.map((value) => (
            <label
              key={value}
              className="flex min-h-11 cursor-pointer items-center gap-3 text-body text-navy"
            >
              <input
                type="radio"
                name={`${uid}-primary-job`}
                checked={primaryJob === value}
                onChange={() => {
                  setPrimaryJob(value);
                  if (secondaryJob === value) setSecondaryJob("");
                }}
                className="size-4 shrink-0 accent-navy"
              />
              {JOB_LABELS[value]}
            </label>
          ))}
        </div>
        {attempted && jobMissing && (
          <p role="alert" className={ERROR_CLASS}>
            Choose your main use.
          </p>
        )}
        {secondOpen ? (
          <Select
            label="Second use"
            value={secondaryJob}
            options={JOBS.filter((value) => value !== primaryJob).map((value) => ({
              value,
              label: JOB_LABELS[value],
            }))}
            onChange={setSecondaryJob}
            placeholder="Choose a second use"
            className="mt-3 min-h-11 w-full"
          />
        ) : (
          <Button
            variant="secondary"
            size="sm"
            className="mt-2 min-h-11"
            onClick={() => setSecondOpen(true)}
          >
            + add a second use
          </Button>
        )}
      </fieldset>

      <fieldset>
        <legend className={QUESTION_CLASS}>
          Would you take part in a 45-minute hands-on session with the team?{" "}
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
