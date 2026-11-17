import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";

import { formatDate } from "../../lib/dates";
import { Figures } from "../../lib/figures";
import { Button } from "../../ui/brand/Button";
import { cn } from "../../ui/brand/cn";
import { PageHeader, PagePrimary } from "../../ui/brand/PageHeader";
import {
  errorStatus,
  inferDefaults,
  OpsApiError,
  unwrap,
  useOpsAction,
  useOrganisations,
  usePeople,
  type OpsClient,
} from "../api";
import { facts, limitWord, plural } from "../format";
import {
  Dialog,
  FailedLine,
  Field,
  FIGURE_CLASS,
  INPUT_CLASS,
  Loading,
  OrganisationSelect,
  Panel,
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

/**
 * The id from a pasted web address or a bare id. A bare id may be a task's or
 * a project's, so the move tries it as a task first.
 */
function parseRowId(text: string): { task_id?: string; project_id?: string; bare?: string } {
  const trimmed = text.trim();
  const project = /\/projects\/([0-9a-f-]{36})/i.exec(trimmed);
  if (project !== null) return { project_id: project[1] };
  const task = /\/tasks\/([0-9a-f-]{36})/i.exec(trimmed);
  if (task !== null) return { task_id: task[1] };
  return { bare: trimmed };
}

async function assign(client: OpsClient, { id, orgId }: { id: string; orgId: string }) {
  const parsed = parseRowId(id);
  const post = (body: { task_id?: string; project_id?: string }) =>
    unwrap(client.POST("/api/v1/ops/rows/assign", { body: { org_id: orgId, ...body } }));
  if (parsed.bare === undefined) return post(parsed);
  try {
    return await post({ task_id: parsed.bare });
  } catch (error) {
    // Not a task: nothing was written, so try the same id as a project.
    if (errorStatus(error) === 404) return post({ project_id: parsed.bare });
    throw error;
  }
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
  const [rowId, setRowId] = useState("");
  const [moveTo, setMoveTo] = useState("");
  const [moveMessage, setMoveMessage] = useState<string | null>(null);
  const [moveFailed, setMoveFailed] = useState(false);
  const create = useOpsAction((client, body: { name: string }) =>
    unwrap(client.POST("/api/v1/ops/organisations", { body })),
  );
  const move = useOpsAction(assign);

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
              : "Something went wrong. Try again.",
          ),
      },
    );
  };

  const sendMove = () => {
    setMoveMessage(null);
    setMoveFailed(false);
    move.mutate(
      { id: rowId, orgId: moveTo },
      {
        onSuccess: (moved) => {
          toast(
            `Moved ${plural(moved.projects_moved, "project")} and ${plural(moved.tasks_moved, "task")} into ${moved.org.name}`,
          );
          setMoveMessage(moved.message);
        },
        onError: (error) => {
          if (error instanceof OpsApiError && error.status > 0 && error.status < 500 && error.message !== "") {
            setMoveMessage(error.message);
          } else {
            setMoveFailed(true);
          }
        },
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
          <FailedLine onRetry={() => void organisations.refetch()} />
        ) : (
          <div className={TABLE_WRAP_CLASS}>
            <table className={TABLE_CLASS}>
              <thead>
                <tr>
                  <th className={cn(TH_CLASS, "pl-4")}>Name</th>
                  <th className={cn(TH_CLASS, "text-right")}>People</th>
                  <th className={cn(TH_CLASS, "text-right")}>Tasks per year</th>
                  <th className={cn(TH_CLASS, "text-right")}>Simultaneous tasks</th>
                  <th className={TH_CLASS}>Self-signup domain</th>
                  <th className={TH_CLASS}>Created</th>
                  <th className={cn(TH_CLASS, "w-10")}>
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((org) => (
                  <tr key={org.org_id}>
                    <td className={cn(TD_CLASS, "pl-4 font-semibold text-navy")}>{org.name}</td>
                    <td className={cn(TD_CLASS, FIGURE_CLASS, "tabular-nums")}>{org.people}</td>
                    <td className={cn(TD_CLASS, FIGURE_CLASS)}>
                      <Override value={org.task_quota_per_year} fallback={defaults.tasks} />
                    </td>
                    <td className={cn(TD_CLASS, FIGURE_CLASS)}>
                      <Override value={org.runs_per_user} fallback={defaults.runs} />
                    </td>
                    <td className={TD_CLASS}>{org.domains.length > 0 ? org.domains.join(", ") : "—"}</td>
                    <td className={cn(TD_CLASS, "whitespace-nowrap")}>
                      <Figures text={formatDate(org.created_at, "short")} />
                    </td>
                    <td className={cn(TD_CLASS, "py-2 pr-2")}>
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
          </div>
        )}
      </div>

      <Panel title="Move a task or project to another organisation" className="mt-10 max-w-[48rem]">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            sendMove();
          }}
          className="flex flex-col gap-5 pt-1">
          <div className="grid gap-5 md:grid-cols-2">
            <Field id="move-row" label="Task or project id" help="Paste the id from its web address">
              <input
                id="move-row"
                required
                autoComplete="off"
                spellCheck={false}
                value={rowId}
                onChange={(event) => setRowId(event.target.value)}
                className={cn(INPUT_CLASS, "font-mono text-meta")}
              />
            </Field>
            <Field id="move-to" label="Move to">
              <OrganisationSelect id="move-to" label="Move to" organisations={all} value={moveTo} onChange={setMoveTo} />
            </Field>
          </div>
          <div className="flex justify-end">
            <Button type="submit" variant="outline" disabled={rowId.trim() === "" || moveTo === "" || move.isPending}>
              Move
            </Button>
          </div>
          {moveMessage !== null && (
            <p role="status" className="text-body text-ink">
              {moveMessage}
            </p>
          )}
          {moveFailed && <FailedLine onRetry={sendMove} />}
        </form>
      </Panel>

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
            <input
              id="org-name"
              required
              autoComplete="off"
              value={name}
              aria-invalid={nameError !== null}
              onChange={(event) => setName(event.target.value)}
              className={INPUT_CLASS}
            />
          </Field>
        </form>
      </Dialog>
    </>
  );
}
