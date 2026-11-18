import { useState, type FormEvent, type ReactNode } from "react";
import { Navigate, useParams } from "react-router";

import { Button } from "../../ui/brand/Button";
import { PageBackLink } from "../../ui/brand/PageHeader";
import {
  inferDefaults,
  OpsApiError,
  useCohortQuota,
  useCohorts,
  useOrganisationQuota,
  useOrganisations,
  usePeople,
  usePeopleQuota,
  type Person,
  type QuotaValues,
} from "../api";
import { facts, limitWord, plural } from "../format";
import { FailedLine, FormHeader, Loading, Panel, useRecordedToast } from "../ui";
import {
  draftErrors,
  draftIsValid,
  draftOf,
  QuotaFields,
  valuesOf,
  WARNING_WHO,
  type QuotaDraft,
  type QuotaErrors,
} from "./QuotaFields";

/** A placeholder naming where an empty field's value comes from. */
function inherits(from: string, value: number | null | undefined): string {
  return value === undefined ? `Inherits ${from}` : facts(`Inherits ${from}`, limitWord(value));
}

/**
 * The quota page's frame, for a person or an organisation: the way back,
 * the title, one line under it, the two fields, Save quota and Clear and
 * inherit, and an optional panel beside the form.
 */
function QuotaPage({
  back,
  title,
  line,
  initial,
  placeholders,
  save,
  aside,
  who,
}: {
  back: ReactNode;
  title: string;
  line: string;
  initial: QuotaDraft;
  placeholders: { tasks: string; runs: string };
  save: (values: QuotaValues, done: { onSaved: () => void; onRefused: (message: string) => void; onFailed: () => void }) => void;
  aside?: ReactNode;
  who?: string;
}) {
  const toast = useRecordedToast();
  const [draft, setDraft] = useState(initial);
  const [refused, setRefused] = useState<string | null>(null);
  const [failed, setFailed] = useState<(() => void) | null>(null);
  const [pending, setPending] = useState(false);

  const [errors, setErrors] = useState<QuotaErrors>({});

  const send = (next: QuotaDraft) => {
    // A value that is not a whole number is refused here: nothing is sent.
    setErrors(draftErrors(next));
    if (!draftIsValid(next)) return;
    setRefused(null);
    setFailed(null);
    setPending(true);
    save(valuesOf(next), {
      onSaved: () => {
        setPending(false);
        setDraft(next);
        toast("Quota saved");
      },
      onRefused: (message) => {
        setPending(false);
        setRefused(message);
      },
      onFailed: () => {
        setPending(false);
        setFailed(() => () => send(next));
      },
    });
  };

  return (
    <>
      <FormHeader back={back} title={title} line={line} />
      <div className="mt-6 grid gap-8 md:grid-cols-[minmax(0,34rem)_minmax(0,22rem)]">
        <form
          onSubmit={(event: FormEvent) => {
            event.preventDefault();
            send(draft);
          }}
          className="flex flex-col gap-6 border border-line-2 bg-paper p-6 shadow-paper max-md:p-4"
        >
          <QuotaFields
            draft={draft}
            onChange={setDraft}
            tasksPlaceholder={placeholders.tasks}
            runsPlaceholder={placeholders.runs}
            who={who}
            errors={errors}
          />
          {refused !== null && (
            <p role="alert" className="text-body text-red">
              {refused}
            </p>
          )}
          {failed !== null && <FailedLine message="Could not save the quota." onRetry={failed} />}
          <div className="flex flex-wrap items-center justify-end gap-3 pt-2">
            <Button variant="ghost" disabled={pending} onClick={() => send({ tasks: "", runs: "" })}>
              Clear and inherit
            </Button>
            <Button type="submit" disabled={pending}>
              Save quota
            </Button>
          </div>
        </form>
        {aside}
      </div>
    </>
  );
}

function LimitsPanel({ person }: { person: Person }) {
  const rows = [
    `Tasks per year: ${facts(
      limitWord(person.limits.task_quota_per_year),
      `from ${person.limits.task_quota_from}`,
    )}`,
    `Simultaneous tasks: ${facts(
      limitWord(person.limits.runs_per_user),
      `from ${person.limits.runs_from}`,
    )}`,
    `Admin exemption: ${person.is_admin ? "yes" : "no"}`,
  ];
  return (
    <Panel title="Currently applied limits" className="self-start">
      <ul className="flex flex-col">
        {rows.map((row) => (
          <li key={row} className="border-t border-line py-2.5 text-meta text-ink first:border-t-0 first:pt-0">
            {row}
          </li>
        ))}
      </ul>
    </Panel>
  );
}

/** A person's quota (`/people/:userId/quota`). */
export function PersonQuotaView() {
  const { userId = "" } = useParams();
  const people = usePeople();
  const organisations = useOrganisations();
  const quota = usePeopleQuota();
  if (people.isPending || organisations.isPending) return <Loading />;
  if (people.isError || organisations.isError) {
    return (
      <FailedLine
        message="Could not load this person’s quota."
        onRetry={() => {
          void people.refetch();
          void organisations.refetch();
        }}
      />
    );
  }
  const person = people.data.find((entry) => entry.user_id === userId);
  if (person === undefined) return <Navigate to="/people" replace />;
  const org = organisations.data.find((entry) => entry.org_id === person.organisation?.org_id);
  const defaults = inferDefaults(people.data);
  return (
    <QuotaPage
      key={person.user_id}
      back={<PageBackLink to="/people">People</PageBackLink>}
      title={`Quota for ${person.display_name}`}
      line={facts(
        person.organisation?.name ?? "not enrolled",
        `${plural(person.tasks_this_year, "task")} created in the last 365 days`,
      )}
      initial={draftOf(person)}
      placeholders={{
        // What applies without the person's own number: the server's source
        // when that is not the person; else the organisation's or the default
        // (a cohort's number is shown in the panel beside the form).
        tasks:
          person.task_quota_per_year == null
            ? inherits(person.limits.task_quota_from, person.limits.task_quota_per_year ?? 0)
            : org?.task_quota_per_year != null
              ? inherits(org.name, org.task_quota_per_year)
              : inherits("the default", defaults.tasks),
        runs:
          person.runs_per_user == null
            ? inherits(person.limits.runs_from, person.limits.runs_per_user ?? 0)
            : org?.runs_per_user != null
              ? inherits(org.name, org.runs_per_user)
              : inherits("the default", defaults.runs),
      }}
      save={(values, done) =>
        quota.mutate(
          { user_ids: [person.user_id], ...values },
          {
            onSuccess: ({ results }) =>
              results[0]?.outcome === "ok" ? done.onSaved() : done.onRefused(results[0]?.message ?? ""),
            onError: done.onFailed,
          },
        )
      }
      aside={<LimitsPanel person={person} />}
    />
  );
}

/** An organisation's quota defaults (`/organisations/:orgId/quota`). */
export function OrganisationQuotaView() {
  const { orgId = "" } = useParams();
  const people = usePeople();
  const organisations = useOrganisations();
  const quota = useOrganisationQuota(orgId);
  if (organisations.isPending) return <Loading />;
  if (organisations.isError) return <FailedLine message="Could not load this organisation’s quota." onRetry={() => void organisations.refetch()} />;
  const org = organisations.data.find((entry) => entry.org_id === orgId);
  if (org === undefined) return <Navigate to="/organisations" replace />;
  const defaults = inferDefaults(people.data ?? []);
  return (
    <QuotaPage
      key={org.org_id}
      back={<PageBackLink to="/organisations">Organisations</PageBackLink>}
      title={`Quota for ${org.name}`}
      line={`Applies to everyone in ${org.name} who doesn't have a personalised quota.`}
      initial={draftOf(org)}
      placeholders={{ tasks: inherits("the default", defaults.tasks), runs: inherits("the default", defaults.runs) }}
      who={WARNING_WHO.organisation(org.name)}
      save={(values, done) =>
        quota.mutate(values, {
          onSuccess: done.onSaved,
          onError: (error) =>
            error instanceof OpsApiError && error.code === "ops_refused" ? done.onRefused(error.message) : done.onFailed(),
        })
      }
    />
  );
}

/** A cohort's quota (`/cohorts/:cohortId/quota`), between a person's own and their organisation's. */
export function CohortQuotaView() {
  const { cohortId = "" } = useParams();
  const people = usePeople();
  const cohorts = useCohorts();
  const quota = useCohortQuota(cohortId);
  if (cohorts.isPending) return <Loading />;
  if (cohorts.isError) return <FailedLine message="Could not load this cohort’s quota." onRetry={() => void cohorts.refetch()} />;
  const cohort = cohorts.data.find((entry) => entry.cohort_id === cohortId);
  if (cohort === undefined) return <Navigate to="/cohorts" replace />;
  const defaults = inferDefaults(people.data ?? []);
  return (
    <QuotaPage
      key={cohort.cohort_id}
      back={<PageBackLink to="/cohorts">Cohorts</PageBackLink>}
      title={`Quota for ${cohort.name}`}
      line={`Applies to everyone in ${cohort.name} who doesn't have a personalised quota, before their organisation's. If someone is in several cohorts with a quota, the one they joined last applies.`}
      initial={draftOf(cohort)}
      placeholders={{ tasks: inherits("the organisation or default", defaults.tasks), runs: inherits("the organisation or default", defaults.runs) }}
      who={WARNING_WHO.organisation(cohort.name)}
      save={(values, done) =>
        quota.mutate(values, {
          onSuccess: done.onSaved,
          onError: (error) =>
            error instanceof OpsApiError && error.code === "ops_refused" ? done.onRefused(error.message) : done.onFailed(),
        })
      }
    />
  );
}

