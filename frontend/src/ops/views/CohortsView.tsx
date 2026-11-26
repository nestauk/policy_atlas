import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";

import { formatDate } from "../../lib/dates";
import { Figures } from "../../lib/figures";
import { Button } from "../../ui/brand/Button";
import { cn } from "../../ui/brand/cn";
import { PageHeader, PagePrimary } from "../../ui/brand/PageHeader";
import { OpsApiError, useCohorts, useDeleteCohort, useSaveCohort, type Cohort } from "../api";
import { limitWord, plural, sentence } from "../format";
import {
  ACTIONS_TD_CLASS,
  ACTIONS_TH_CLASS,
  DANGER_CLASS,
  Dialog,
  EmptyRows,
  FailedLine,
  Field,
  FIGURE_CLASS,
  SortTh,
  INPUT_CLASS,
  Loading,
  RowMenu,
  SearchField,
  TABLE_CLASS,
  TABLE_WRAP_CLASS,
  TD_CLASS,
  TH_CLASS,
  useRecordedToast,
  useSort,
} from "../ui";

/** A cohort's date, "1 Dec 2026", always with its year; read as a local day, not a UTC instant. */
// Non-breaking spaces keep each date whole; the range wraps at the dash
// instead of running into the Links column.
const day = (value: string) => formatDate(`${value}T00:00:00`, "short", { now: new Date(0) }).replace(/ /g, "\u00a0");

/** "1 Dec 2026 – 31 Jan 2027", "from 1 Dec 2026", "until 31 Jan 2027", or "—". */
function dates(cohort: Cohort): string {
  const { starts_on: start, ends_on: end } = cohort;
  if (start != null && end != null) return `${day(start)} – ${day(end)}`;
  if (start != null) return `from ${day(start)}`;
  if (end != null) return `until ${day(end)}`;
  return "—";
}

const TASKS_NOTE =
  "The number of tasks each person in this cohort can create in a year. It is per person, not shared by the cohort.";
const RUNS_NOTE =
  "The number of tasks each person in this cohort can run at the same time. It is per person, not shared by the cohort.";

/** A cohort's override, or "—" in grey when it sets none (its members inherit). */
function Quota({ value }: { value: number | null | undefined }) {
  return value == null ? <span className="text-grey">—</span> : <Figures text={limitWord(value)} />;
}

/** A link's words in the table: its host and path, without the scheme. */
const linkWords = (link: string) => link.replace(/^https?:\/\//, "").replace(/\/$/, "");

/** Cohorts (ops-pages-copy.md § Cohorts): named groups of people for pilots and research. */
export function CohortsView() {
  const navigate = useNavigate();
  const toast = useRecordedToast();
  const cohorts = useCohorts();
  const remove = useDeleteCohort();
  const [query, setQuery] = useState("");
  // The form: null closed, "new", or the cohort being edited.
  const [editing, setEditing] = useState<Cohort | "new" | null>(null);
  const [deleting, setDeleting] = useState<Cohort | null>(null);

  const all = cohorts.data ?? [];
  const q = query.trim().toLowerCase();
  const { sorted: rows, sort, onSort } = useSort(
    all.filter(
      (cohort) => q === "" || [cohort.name, cohort.description ?? ""].some((value) => value.toLowerCase().includes(q)),
    ),
    {
      name: (cohort) => cohort.name,
      people: (cohort) => cohort.people,
      tasks: (cohort) => cohort.task_quota_per_year,
      runs: (cohort) => cohort.runs_per_user,
      dates: (cohort) => cohort.starts_on ?? cohort.ends_on,
      links: (cohort) => cohort.links[0],
    },
  );
  const th = { sort, onSort };

  if (cohorts.isPending) return <Loading />;

  return (
    <>
      <PageHeader
        title="Cohorts"
        actions={<PagePrimary onClick={() => setEditing("new")}>Add cohort</PagePrimary>}
        filters={
          <div className="flex flex-col gap-4">
            <p className="max-w-[44em] text-body text-grey">
              A cohort is a label for a group of people, such as a pilot or a user segment. A person can be in
              several cohorts. Add people to cohorts from the People tab.
            </p>
            <SearchField placeholder="Find a cohort" value={query} onChange={setQuery} />
          </div>
        }
      />
      <div className="mt-6">
        {cohorts.isError ? (
          <FailedLine message="Could not load the cohorts." onRetry={() => void cohorts.refetch()} />
        ) : (
          <div className={TABLE_WRAP_CLASS}>
            <table className={TABLE_CLASS} aria-label="Cohorts">
              <thead>
                <tr>
                  <SortTh {...th} sortKey="name" label="Name" className="w-52 pl-4" />
                  <SortTh {...th} sortKey="people" label="People" align="end" className="w-24" />
                  <SortTh {...th} sortKey="tasks" label="Tasks per year" note={TASKS_NOTE} align="end" className="w-44" />
                  <SortTh {...th} sortKey="runs" label="Simultaneous tasks" note={RUNS_NOTE} align="end" className="w-56" />
                  <SortTh {...th} sortKey="dates" label="Dates" className="w-44" />
                  <SortTh {...th} sortKey="links" label="Links" className="w-48" />
                  <th className={cn(TH_CLASS, ACTIONS_TH_CLASS)}>
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((cohort) => (
                  <tr key={cohort.cohort_id} className="bg-paper">
                    <td className={cn(TD_CLASS, "pl-4")}>
                      <Link
                        to={`/people?cohort=${cohort.cohort_id}`}
                        title={`Show the people in ${cohort.name}`}
                        className="block truncate font-semibold text-navy hover:text-blue hover:underline"
                      >
                        {cohort.name}
                      </Link>
                      {cohort.description != null && (
                        <span className="line-clamp-2 text-meta text-grey">{cohort.description}</span>
                      )}
                    </td>
                    <td className={cn(TD_CLASS, FIGURE_CLASS, "tabular-nums")}>{cohort.people}</td>
                    <td className={cn(TD_CLASS, FIGURE_CLASS)}>
                      <Quota value={cohort.task_quota_per_year} />
                    </td>
                    <td className={cn(TD_CLASS, FIGURE_CLASS)}>
                      <Quota value={cohort.runs_per_user} />
                    </td>
                    <td className={TD_CLASS}>
                      <Figures text={dates(cohort)} />
                    </td>
                    <td className={TD_CLASS}>
                      {cohort.links.length === 0 ? (
                        "—"
                      ) : (
                        <ul className="flex flex-col gap-0.5">
                          {cohort.links.map((link) => (
                            <li key={link} className="truncate">
                              <a href={link} target="_blank" rel="noreferrer noopener" className="text-blue hover:underline" title={link}>
                                {linkWords(link)}
                              </a>
                            </li>
                          ))}
                        </ul>
                      )}
                    </td>
                    <td className={cn(TD_CLASS, ACTIONS_TD_CLASS, "py-2 pr-2")}>
                      <RowMenu
                        label={`Actions for ${cohort.name}`}
                        items={[
                          { label: "Show people", onSelect: () => navigate(`/people?cohort=${cohort.cohort_id}`) },
                          { label: "Edit…", onSelect: () => setEditing(cohort) },
                          { label: "Set quota…", onSelect: () => navigate(`/cohorts/${cohort.cohort_id}/quota`) },
                          { label: "Delete…", onSelect: () => setDeleting(cohort) },
                        ]}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {rows.length === 0 && <EmptyRows label={all.length === 0 ? "No cohorts yet." : "No cohorts match."} />}
          </div>
        )}
      </div>

      {editing !== null && (
        <CohortDialog
          cohort={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={(saved, created) => {
            setEditing(null);
            toast(created ? `Created ${saved.name}` : `Saved ${saved.name}`);
          }}
        />
      )}
      {deleting !== null && (
        <Dialog
          open
          onOpenChange={(open) => !open && setDeleting(null)}
          title={`Delete ${deleting.name}?`}
          description={`This takes the label off ${plural(deleting.people, "person", "people")}. Their accounts, organisations and work do not change.`}
          footer={
            <>
              <Button variant="ghost" onClick={() => setDeleting(null)}>
                Cancel
              </Button>
              <Button
                className={DANGER_CLASS}
                disabled={remove.isPending}
                onClick={() =>
                  remove.mutate(deleting.cohort_id, {
                    onSuccess: () => {
                      toast(`Deleted ${deleting.name}`);
                      setDeleting(null);
                    },
                  })
                }
              >
                Delete
              </Button>
            </>
          }
        >
          {remove.isError && (
            <p role="alert" className="mt-3 text-body text-red">
              {remove.error?.message || "Could not delete the cohort. Try again."}
            </p>
          )}
        </Dialog>
      )}
    </>
  );
}

/** Add or edit a cohort: name, description, dates and links, one per line. */
function CohortDialog({
  cohort,
  onClose,
  onSaved,
}: {
  cohort: Cohort | null;
  onClose: () => void;
  onSaved: (saved: Cohort, created: boolean) => void;
}) {
  const save = useSaveCohort();
  const [name, setName] = useState(cohort?.name ?? "");
  const [description, setDescription] = useState(cohort?.description ?? "");
  const [startsOn, setStartsOn] = useState(cohort?.starts_on ?? "");
  const [endsOn, setEndsOn] = useState(cohort?.ends_on ?? "");
  const [links, setLinks] = useState((cohort?.links ?? []).join("\n"));
  const [error, setError] = useState<string | null>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    if (startsOn !== "" && endsOn !== "" && endsOn < startsOn) {
      setError("The end date is before the start date.");
      return;
    }
    const body = {
      name: name.trim(),
      description: description.trim() === "" ? null : description.trim(),
      starts_on: startsOn === "" ? null : startsOn,
      ends_on: endsOn === "" ? null : endsOn,
      links: links.split("\n").map((link) => link.trim()).filter((link) => link !== ""),
    };
    save.mutate(
      { cohortId: cohort?.cohort_id ?? null, body },
      {
        onSuccess: (saved) => onSaved(saved, cohort === null),
        onError: (failure) =>
          setError(
            failure instanceof OpsApiError && failure.status === 409 && failure.message !== ""
              ? sentence(failure.message)
              : failure instanceof OpsApiError && failure.status === 422
                ? "Check the links: at most 10, each a web address."
                : "Could not save the cohort. Try again.",
          ),
      },
    );
  };

  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={cohort === null ? "Add cohort" : `Edit ${cohort.name}`}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="cohort-form" disabled={name.trim() === "" || save.isPending}>
            {cohort === null ? "Create" : "Save"}
          </Button>
        </>
      }
    >
      <form id="cohort-form" onSubmit={submit} className="flex flex-col gap-5">
        <Field id="cohort-name" label="Name">
          <input
            id="cohort-name"
            required
            autoComplete="off"
            value={name}
            onChange={(event) => setName(event.target.value)}
            className={INPUT_CLASS}
          />
        </Field>
        <Field id="cohort-description" label="Description (optional)">
          <textarea
            id="cohort-description"
            rows={2}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            className={cn(INPUT_CLASS, "h-auto py-2")}
          />
        </Field>
        <div className="grid gap-5 sm:grid-cols-2">
          <Field id="cohort-start" label="Start date (optional)">
            <input
              id="cohort-start"
              type="date"
              value={startsOn}
              onChange={(event) => setStartsOn(event.target.value)}
              className={INPUT_CLASS}
            />
          </Field>
          <Field id="cohort-end" label="End date (optional)">
            <input
              id="cohort-end"
              type="date"
              value={endsOn}
              onChange={(event) => setEndsOn(event.target.value)}
              className={INPUT_CLASS}
            />
          </Field>
        </div>
        <Field id="cohort-links" label="Links (optional)" help="One web address per line, starting with https://">
          {(describedBy) => (
            <textarea
              id="cohort-links"
              rows={3}
              spellCheck={false}
              aria-describedby={describedBy}
              value={links}
              onChange={(event) => setLinks(event.target.value)}
              className={cn(INPUT_CLASS, "h-auto py-2 font-mono text-meta")}
            />
          )}
        </Field>
        {error !== null && (
          <p role="alert" className="text-body text-red">
            {error}
          </p>
        )}
      </form>
    </Dialog>
  );
}
