import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";

import { formatDate } from "../../lib/dates";
import { Figures } from "../../lib/figures";
import { Button } from "../../ui/brand/Button";
import { InfoHint } from "../../ui/brand/InfoHint";
import { cn } from "../../ui/brand/cn";
import { PageHeader, PagePrimary } from "../../ui/brand/PageHeader";
import {
  inferDefaults,
  OpsApiError,
  unwrap,
  useOpsAction,
  useOrganisations,
  usePeople,
} from "../api";
import { facts, limitWord } from "../format";
import {
  ACTIONS_TD_CLASS,
  ACTIONS_TH_CLASS,
  Dialog,
  EmptyRows,
  FailedLine,
  Field,
  FIGURE_CLASS,
  INPUT_CLASS,
  Loading,
  RowMenu,
  SearchField,
  TABLE_CLASS,
  TABLE_WRAP_CLASS,
  TD_CLASS,
  TH_CLASS,
  useRecordedToast,
} from "../ui";

/** An override, or "default · <value>" in grey (just "default" when the value is unknown). */
function Override({ value, fallback }: { value: number | null | undefined; fallback: number | null | undefined }) {
  if (value != null) return <Figures text={limitWord(value)} />;
  return (
    <span className="text-grey">
      <Figures text={fallback === undefined ? "default" : facts("default", limitWord(fallback))} />
    </span>
  );
}

const TASKS_NOTE =
  "The number of tasks each person in this organisation can create in a year. It is per person, not shared by the organisation.";
const RUNS_NOTE =
  "The number of tasks each person in this organisation can run at the same time. It is per person, not shared by the organisation.";
const DOMAIN_NOTE =
  "People who request access with an email at this domain get an account in this organisation without approval. An administrator adds or removes a domain from the command line.";

/** A column header with its info hint beside the words. */
function HeaderHint({ label, note, align }: { label: string; note: string; align?: "end" }) {
  return (
    <span className={cn("-my-1 inline-flex items-center gap-1", align === "end" && "justify-end")}>
      {label}
      <InfoHint label={`About ${label.toLowerCase()}`} note={note} />
    </span>
  );
}

/** Organisations (ops-pages-copy.md § Organisations). */
export function OrganisationsView() {
  const navigate = useNavigate();
  const toast = useRecordedToast();
  const organisations = useOrganisations();
  const people = usePeople();
  const [query, setQuery] = useState("");
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [nameError, setNameError] = useState<string | null>(null);
  const create = useOpsAction((client, body: { name: string }) =>
    unwrap(client.POST("/api/v1/ops/organisations", { body })),
  );

  if (organisations.isPending) return <Loading />;
  const all = organisations.data ?? [];
  const q = query.trim().toLowerCase();
  const rows = all.filter((org) => q === "" || org.name.toLowerCase().includes(q));
  const defaults = inferDefaults(people.data ?? [], all);

  const submitCreate = (event: FormEvent) => {
    event.preventDefault();
    setNameError(null);
    create.mutate(
      { name: name.trim() },
      {
        onSuccess: (org) => {
          setAdding(false);
          toast(`Created ${org.name}`);
        },
        onError: (error) =>
          setNameError(
            error instanceof OpsApiError && error.status === 409
              ? "An organisation with that name already exists."
              : "Could not create the organisation. Try again.",
          ),
      },
    );
  };

  return (
    <>
      <PageHeader
        title="Organisations"
        actions={
          <PagePrimary
            onClick={() => {
              setName("");
              setNameError(null);
              setAdding(true);
            }}
          >
            Add organisation
          </PagePrimary>
        }
        filters={<SearchField placeholder="Find an organisation" value={query} onChange={setQuery} />}
      />
      <div className="mt-6">
        {organisations.isError ? (
          <FailedLine message="Could not load the organisations." onRetry={() => void organisations.refetch()} />
        ) : (
          <div className={TABLE_WRAP_CLASS}>
            <table className={TABLE_CLASS}>
              <thead>
                <tr>
                  <th className={cn(TH_CLASS, "pl-4")}>Name</th>
                  <th className={cn(TH_CLASS, "w-24 text-right")}>People</th>
                  <th className={cn(TH_CLASS, "w-40 text-right")}>
                    <HeaderHint label="Tasks per year" note={TASKS_NOTE} align="end" />
                  </th>
                  <th className={cn(TH_CLASS, "w-56 text-right")}>
                    <HeaderHint label="Simultaneous tasks" note={RUNS_NOTE} align="end" />
                  </th>
                  <th className={cn(TH_CLASS, "w-56")}>
                    <HeaderHint label="Self-signup domain" note={DOMAIN_NOTE} />
                  </th>
                  <th className={cn(TH_CLASS, "w-28")}>Created</th>
                  <th className={cn(TH_CLASS, ACTIONS_TH_CLASS)}>
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((org) => (
                  <tr key={org.org_id} className="bg-paper">
                    <td className={cn(TD_CLASS, "truncate pl-4 font-semibold text-navy")} title={org.name}>
                      {org.name}
                    </td>
                    <td className={cn(TD_CLASS, FIGURE_CLASS, "tabular-nums")}>{org.people}</td>
                    <td className={cn(TD_CLASS, FIGURE_CLASS)}>
                      <Override value={org.task_quota_per_year} fallback={defaults.tasks} />
                    </td>
                    <td className={cn(TD_CLASS, FIGURE_CLASS)}>
                      <Override value={org.runs_per_user} fallback={defaults.runs} />
                    </td>
                    <td className={cn(TD_CLASS, "break-words")}>{org.domains.length > 0 ? org.domains.join(", ") : "—"}</td>
                    <td className={cn(TD_CLASS, "whitespace-nowrap")}>
                      <Figures text={formatDate(org.created_at, "short")} />
                    </td>
                    <td className={cn(TD_CLASS, ACTIONS_TD_CLASS, "py-2 pr-2")}>
                      <RowMenu
                        label={`Actions for ${org.name}`}
                        items={[
                          { label: "Set quota defaults…", onSelect: () => navigate(`/organisations/${org.org_id}/quota`) },
                        ]}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {rows.length === 0 && <EmptyRows label="No organisations match." />}
          </div>
        )}
      </div>

      <Dialog
        open={adding}
        onOpenChange={setAdding}
        title="Add organisation"
        footer={
          <>
            <Button variant="ghost" onClick={() => setAdding(false)}>
              Cancel
            </Button>
            <Button type="submit" form="add-organisation" disabled={name.trim() === "" || create.isPending}>
              Create
            </Button>
          </>
        }
      >
        <form id="add-organisation" onSubmit={submitCreate}>
          <Field id="org-name" label="Name" error={nameError}>
            {(describedBy) => (
              <input
                id="org-name"
                required
                autoComplete="off"
                value={name}
                aria-invalid={nameError !== null}
                aria-describedby={describedBy}
                onChange={(event) => setName(event.target.value)}
                className={INPUT_CLASS}
              />
            )}
          </Field>
        </form>
      </Dialog>
    </>
  );
}
