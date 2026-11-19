import { useRef, useState, type ReactNode } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router";

import { formatDate } from "../../lib/dates";
import { Figures } from "../../lib/figures";
import { Button } from "../../ui/brand/Button";
import { Checkbox } from "../../ui/brand/Checkbox";
import { Chip } from "../../ui/brand/Chip";
import { cn } from "../../ui/brand/cn";
import { PageHeader, PagePrimary } from "../../ui/brand/PageHeader";
import {
  errorStatus,
  useBulk,
  useCohortMembers,
  useCohorts,
  useEnrol,
  useOrganisations,
  usePeople,
  usePeopleQuota,
  type ActionResult,
  type Cohort,
  type Organisation,
  type Person,
  sourceLabel,
} from "../api";
import { ago, facts, inCooldown, limitWord, resendHint } from "../format";
import {
  ACTIONS_TD_CLASS,
  ACTIONS_TH_CLASS,
  DANGER_CLASS,
  Dialog,
  EmptyRows,
  FailedDialog,
  FailedLine,
  Field,
  FIGURE_CLASS,
  INPUT_CLASS,
  Loading,
  NameList,
  OrganisationSelect,
  RowMenu,
  SearchField,
  SearchSelect,
  SortTh,
  TABLE_CLASS,
  TABLE_WRAP_CLASS,
  TD_CLASS,
  TH_CLASS,
  useRecordedToast,
  useSort,
} from "../ui";
import { draftErrors, draftIsValid, QuotaFields, valuesOf, WARNING_WHO, type QuotaDraft, type QuotaErrors } from "./QuotaFields";

/** A line under a person's name after an action: a failure's message, or a cooldown. */
type Note = { text: string; failed: boolean };

type DialogKind = "move" | "deenrol" | "offboard" | "quota" | "cohortAdd" | "cohortRemove";

/** The open dialog: what it does, to whom, and whether a row's menu or the selection bar opened it. */
type DialogState = { kind: DialogKind; ids: string[]; from: "row" | "bar" } | null;

const COOLDOWN_NOTE = "Sent less than an hour ago";

/** The column filters' "no filter" value, and the organisation filter's "not enrolled". */
const ALL = "all";

/** An organisation or cohort name that filters the list to it: plain text until pointed at. */
const FILTER_LINK_CLASS = "text-ink hover:text-blue hover:underline";
const NO_ORG = "none";

const DE_ENROL_SENTENCE =
  "They stay signed in but leave their organisation. Their tasks and projects stay with them and leave the organisation too.";

const OFFBOARD_SENTENCE =
  "This stops them signing in, signs them out everywhere, removes them from their organisation and takes down any public links to their tasks. Their tasks stay in the database. This cannot be undone from here.";

function matches(person: Person, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (q === "") return true;
  return [
    person.display_name,
    person.email ?? "",
    person.organisation?.name ?? "",
    ...person.cohorts.map((cohort) => cohort.name),
  ].some((value) => value.toLowerCase().includes(q));
}

/** "Tom Ellis" for one, "3 people" for several. */
function who(people: readonly Person[]): string {
  return people.length === 1 ? people[0].display_name : `${people.length} people`;
}

/** The id of a person's row menu button, where focus returns after its dialog. */
const rowMenuId = (userId: string) => `row-menu-${userId}`;

/**
 * A bulk result's toast: "<n> done, <m> failed", with "<k> too soon" after
 * them when some invitations were inside the hour ("failed" then only when
 * something did fail).
 */
function counts(results: readonly ActionResult[]): string {
  const count = (outcome: ActionResult["outcome"]) => results.filter((result) => result.outcome === outcome).length;
  const [done, failed, tooSoon] = [count("ok"), count("failed"), count("too_soon")];
  const parts = [`${done} done`];
  if (failed > 0 || tooSoon === 0) parts.push(`${failed} failed`);
  if (tooSoon > 0) parts.push(`${tooSoon} too soon`);
  return parts.join(", ");
}

/** The People list (ops-pages-copy.md § People). */
export function PeopleView() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  // The two column filters live in the address (ids only), so "Show people"
  // on an organisation or cohort lands here filtered.
  const orgFilter = params.get("org") ?? ALL;
  const cohortFilter = params.get("cohort") ?? ALL;
  const location = useLocation();
  // "Open person" on Requests passes the address in router state, so it stays
  // out of the URL; a plain search word may still come as ?q=.
  const [query, setQuery] = useState(
    (location.state as { q?: string } | null)?.q ?? params.get("q") ?? "",
  );
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
  const [dialog, setDialog] = useState<DialogState>(null);
  const [viewing, setViewing] = useState<Person | null>(null);
  const [notes, setNotes] = useState<Record<string, Note>>({});
  const [retry, setRetry] = useState<(() => void) | null>(null);
  const tableRef = useRef<HTMLTableElement>(null);
  /** Whether the open dialog's action went through (an offboarded row is on its way out). */
  const acted = useRef(false);
  const people = usePeople();
  const organisations = useOrganisations();
  const toast = useRecordedToast();
  const enrol = useEnrol();
  const deEnrol = useBulk("/api/v1/ops/people/de-enrol");
  const offboard = useBulk("/api/v1/ops/people/offboard");
  const resend = useBulk("/api/v1/ops/people/resend");
  const quota = usePeopleQuota();
  const cohorts = useCohorts();
  const cohortAdd = useCohortMembers("/api/v1/ops/people/cohort-add");
  const cohortRemove = useCohortMembers("/api/v1/ops/people/cohort-remove");

  const all = people.data ?? [];
  const visible = all.filter(
    (person) =>
      matches(person, query) &&
      (orgFilter === ALL ||
        (orgFilter === NO_ORG ? person.organisation == null : person.organisation?.org_id === orgFilter)) &&
      (cohortFilter === ALL || person.cohorts.some((own) => own.cohort_id === cohortFilter)),
  );
  const { sorted: shown, sort, onSort } = useSort(visible, {
    name: (person) => person.display_name,
    email: (person) => person.email,
    organisation: (person) => person.organisation?.name,
    cohorts: (person) => person.cohorts[0]?.name,
    flags: (person) => (person.is_admin ? "a" : "") + (person.is_ops ? "o" : "") || null,
    tasks: (person) => person.tasks_this_year,
    // Invited people sort by when they were sent the invitation, everyone else by their latest task.
    last: (person) => (waitingForSignIn(person) ? person.invited_at : person.last_task_at),
  });
  const th = { sort, onSort };
  if (people.isPending) return <Loading />;
  const setFilter = (key: "org" | "cohort", value: string) => {
    const next = new URLSearchParams(params);
    if (value === ALL) next.delete(key);
    else next.set(key, value);
    setParams(next, { replace: true });
    setSelected(new Set());
  };
  const selectAllShown = () => setSelected(new Set(visible.map((person) => person.user_id)));
  const selectAllLabel =
    visible.length === all.length ? `Select all ${visible.length}` : `Select all ${visible.length} shown`;
  const byId = new Map(all.map((person) => [person.user_id, person]));
  const subjects = (ids: readonly string[]) => ids.flatMap((id) => byId.get(id) ?? []);
  const allVisibleTicked = visible.length > 0 && visible.every((person) => selected.has(person.user_id));

  const toggle = (userId: string, on: boolean) =>
    setSelected((current) => {
      const next = new Set(current);
      if (on) next.add(userId);
      else next.delete(userId);
      return next;
    });

  /** Each failed or cooling row's line under its name; a row that went through loses its line. */
  const noteResults = (results: readonly ActionResult[]) =>
    setNotes((current) => {
      const next = { ...current };
      for (const result of results) {
        if (result.outcome === "failed") next[result.user_id] = { text: result.message, failed: true };
        else if (result.outcome === "too_soon") next[result.user_id] = { text: COOLDOWN_NOTE, failed: false };
        else delete next[result.user_id];
      }
      return next;
    });

  /**
   * Show what a bulk route did: the lines under the names, and the toast.
   * One person who went through gets the action's own summary; otherwise
   * the counts.
   */
  const report = (results: readonly ActionResult[], summary: (person: Person) => string) => {
    noteResults(results);
    const only = results.length === 1 && results[0].outcome === "ok" ? byId.get(results[0].user_id) : undefined;
    toast(only !== undefined ? summary(only) : counts(results));
    if (results.every((result) => result.outcome !== "failed")) setSelected(new Set());
  };

  /** Run one write; a failed request leaves the line and a way to send it again. */
  const run = <V,>(
    action: { mutate: (variables: V, options: { onSuccess: (data: { results: ActionResult[] }) => void; onError: (error: Error) => void }) => void },
    variables: V,
    ids: string[],
    summary: (person: Person) => string,
  ) => {
    const again = () => run(action, variables, ids, summary);
    setRetry(null);
    action.mutate(variables, {
      onSuccess: (data) => {
        acted.current = true;
        setDialog(null);
        report(data.results, summary);
      },
      onError: (error) => {
        setDialog(null);
        if (errorStatus(error) === 429) {
          // Every invitation was inside the hour: nothing was sent or recorded.
          noteResults(ids.map((id) => ({ user_id: id, outcome: "too_soon", message: COOLDOWN_NOTE })));
          return;
        }
        setRetry(() => again);
      },
    });
  };

  const sendInvitations = (ids: string[]) =>
    run(resend, ids, ids, (person) => `Invitation sent to ${person.email ?? person.display_name}`);

  const menuFor = (person: Person) => {
    const open = (kind: DialogKind) => () => {
      acted.current = false;
      setDialog({ kind, ids: [person.user_id], from: "row" });
    };
    const cooling = inCooldown(person.invited_at);
    return [
      { label: "Enrol or move to an organisation…", onSelect: open("move") },
      { label: "Set quota…", onSelect: () => navigate(`/people/${person.user_id}/quota`) },
      { label: "Add to cohort…", onSelect: open("cohortAdd") },
      { label: "Remove from cohort…", onSelect: open("cohortRemove"), disabled: person.cohorts.length === 0 },
      // Only while the invitation is unused (owner, 2026-11-18).
      ...(waitingForSignIn(person)
        ? [
            {
              label: "Resend invitation",
              onSelect: () => sendInvitations([person.user_id]),
              disabled: cooling,
              hint: cooling && person.invited_at != null ? resendHint(person.invited_at) : undefined,
            },
          ]
        : []),
      {
        label: "De-enrol",
        onSelect: open("deenrol"),
        disabled: person.organisation == null && !person.is_admin && !person.is_ops,
      },
      { label: "Offboard…", onSelect: open("offboard") },
    ];
  };

  // A bulk action names only ticked rows the reader can see.
  const ticked = visible.filter((person) => selected.has(person.user_id)).map((person) => person.user_id);
  /** A new search starts a new selection, so nothing out of sight is acted on. */
  const search = (next: string) => {
    setQuery(next);
    setSelected(new Set());
  };
  const openBulk = (kind: DialogKind) => () => {
    acted.current = false;
    setDialog({ kind, ids: ticked, from: "bar" });
  };

  const chosen = dialog === null ? [] : subjects(dialog.ids);
  const close = (open: boolean) => {
    if (!open) setDialog(null);
  };
  /**
   * Where focus goes when a dialog closes: back to the row's menu button
   * (the menu item that opened it is gone), or to the table when the row is
   * leaving (offboarded) or the action cleared the selection bar. A
   * cancelled bar action returns to the bar's button, as Radix does by itself.
   */
  const returnFocus = () => {
    if (dialog?.from === "row") {
      if (dialog.kind === "offboard" && acted.current) return tableRef.current;
      return document.getElementById(rowMenuId(dialog.ids[0])) ?? tableRef.current;
    }
    return document.querySelector("[data-selection-bar] button") === null ? tableRef.current : null;
  };

  return (
    <>
      <PageHeader
        title="People"
        actions={<PagePrimary to="/people/new">Add person</PagePrimary>}
        filters={
          <div className="flex flex-wrap items-center gap-3">
            <SearchField placeholder="Find a person, organisation or cohort" value={query} onChange={search} />
            <div className="w-60">
              <SearchSelect
                label="Organisation filter"
                value={orgFilter}
                options={[
                  { value: ALL, label: "All organisations" },
                  { value: NO_ORG, label: "Not enrolled" },
                  ...(organisations.data ?? []).map((org) => ({ value: org.org_id, label: org.name })),
                ]}
                onChange={(value) => setFilter("org", value)}
                placeholder="All organisations"
                filterLabel="Find an organisation"
                empty="No organisations match."
              />
            </div>
            <div className="w-60">
              <SearchSelect
                label="Cohort filter"
                value={cohortFilter}
                options={[
                  { value: ALL, label: "All cohorts" },
                  ...(cohorts.data ?? []).map((cohort) => ({ value: cohort.cohort_id, label: cohort.name })),
                ]}
                onChange={(value) => setFilter("cohort", value)}
                placeholder="All cohorts"
                filterLabel="Find a cohort"
                empty="No cohorts match."
              />
            </div>
          </div>
        }
      />
      {/* The bar's room is kept while nothing is ticked, so ticking the first
          box does not push the table down. */}
      <div className="mt-6 min-h-12">
        {ticked.length === 0 && visible.length > 0 && (
          <div className="flex min-h-12 items-center">
            <Button variant="ghost" size="sm" onClick={selectAllShown}>
              {selectAllLabel}
            </Button>
          </div>
        )}
        {ticked.length > 0 && (
          <div
            data-selection-bar=""
            className="flex min-h-12 flex-wrap items-center gap-x-1 gap-y-1 border-x border-t border-line bg-blue-tint-2 px-4 py-1.5"
          >
            <span className="mr-2 text-meta font-semibold text-navy">
              <Figures text={`${ticked.length} selected`} />
            </span>
            <Button variant="secondary" size="sm" onClick={openBulk("quota")}>
              Set quota
            </Button>
            <Button variant="secondary" size="sm" onClick={openBulk("move")}>
              Move to
            </Button>
            <Button variant="secondary" size="sm" onClick={openBulk("cohortAdd")}>
              Add to cohort
            </Button>
            <Button variant="secondary" size="sm" onClick={openBulk("cohortRemove")}>
              Remove from cohort
            </Button>
            <Button variant="secondary" size="sm" onClick={() => sendInvitations(ticked)}>
              Resend invitation
            </Button>
            <Button variant="secondary" size="sm" onClick={openBulk("deenrol")}>
              De-enrol
            </Button>
            <Button variant="secondary" size="sm" onClick={openBulk("offboard")}>
              Offboard
            </Button>
            {!allVisibleTicked && (
              <Button variant="ghost" size="sm" onClick={selectAllShown}>
                {selectAllLabel}
              </Button>
            )}
            <Button variant="ghost" size="sm" onClick={() => setSelected(new Set())}>
              Clear selection
            </Button>
          </div>
        )}
      </div>
      {people.isError ? (
        <FailedLine message="Could not load the people list." onRetry={() => void people.refetch()} />
      ) : (
        <div className={TABLE_WRAP_CLASS}>
          <table ref={tableRef} tabIndex={-1} aria-label="People" className={TABLE_CLASS}>
            <thead>
              <tr>
                <th className={cn(TH_CLASS, "w-12 overflow-visible pb-0 pl-4")}>
                  <Checkbox
                    checked={allVisibleTicked}
                    label={<span className="sr-only">Select everyone shown</span>}
                    onChange={(on) =>
                      setSelected((current) => {
                        const next = new Set(current);
                        for (const person of visible) {
                          if (on) next.add(person.user_id);
                          else next.delete(person.user_id);
                        }
                        return next;
                      })
                    }
                  />
                </th>
                <SortTh {...th} sortKey="name" label="Name" className="w-36" />
                <SortTh {...th} sortKey="email" label="Email" className="w-44" />
                <SortTh {...th} sortKey="organisation" label="Organisation" className="w-36" />
                <SortTh {...th} sortKey="cohorts" label="Cohorts" className="w-32" />
                <SortTh {...th} sortKey="flags" label="Flags" className="w-24" />
                <SortTh {...th} sortKey="tasks" label="Tasks this year" align="end" className="w-40" />
                <SortTh {...th} sortKey="last" label="Last task" className="w-36" />
                <th className={cn(TH_CLASS, ACTIONS_TH_CLASS)}>
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {shown.map((person) => {
                const note = notes[person.user_id];
                const quotaLimit = person.limits.task_quota_per_year;
                const isTicked = selected.has(person.user_id);
                return (
                  <tr key={person.user_id} className={isTicked ? "bg-blue-tint-2" : "bg-paper"}>
                    <td className={cn(TD_CLASS, "py-1 pl-4")}>
                      <Checkbox
                        checked={isTicked}
                        label={<span className="sr-only">Select {person.display_name}</span>}
                        onChange={(on) => toggle(person.user_id, on)}
                      />
                    </td>
                    <td className={TD_CLASS}>
                      <button
                        type="button"
                        onClick={() => setViewing(person)}
                        className="block max-w-full cursor-pointer text-left text-navy hover:text-blue hover:underline"
                      >
                        <span className="block truncate font-semibold" title={person.display_name}>
                          {person.display_name}
                        </span>
                      </button>
                      {note !== undefined && (
                        <span className={cn("block text-meta", note.failed ? "text-red" : "text-grey")}>
                          {note.text}
                        </span>
                      )}
                    </td>
                    <td className={cn(TD_CLASS, "truncate")} title={person.email ?? undefined}>
                      {person.email ?? "—"}
                    </td>
                    <td className={cn(TD_CLASS, "truncate")}>
                      {person.organisation != null ? (
                        <Link
                          to={`/people?org=${person.organisation.org_id}`}
                          onClick={() => setSelected(new Set())}
                          className={FILTER_LINK_CLASS}
                          title={`Show everyone in ${person.organisation.name}`}
                        >
                          {person.organisation.name}
                        </Link>
                      ) : (
                        <span className="text-grey">not enrolled</span>
                      )}
                    </td>
                    <td className={TD_CLASS}>
                      {person.cohorts.length === 0 ? (
                        <span className="text-grey">—</span>
                      ) : (
                        <ul className="flex flex-col gap-0.5">
                          {person.cohorts.map((cohort) => (
                            <li key={cohort.cohort_id} className="truncate">
                              <Link
                                to={`/people?cohort=${cohort.cohort_id}`}
                                onClick={() => setSelected(new Set())}
                                className={FILTER_LINK_CLASS}
                                title={`Show everyone in ${cohort.name}`}
                              >
                                {cohort.name}
                              </Link>
                            </li>
                          ))}
                        </ul>
                      )}
                    </td>
                    <td className={cn(TD_CLASS, "py-2.5")}>
                      <span className="flex gap-1.5">
                        {person.is_admin && <Chip>ADMIN</Chip>}
                        {person.is_ops && <Chip>OPS</Chip>}
                      </span>
                    </td>
                    <td className={cn(TD_CLASS, FIGURE_CLASS)}>
                      <Figures
                        text={`${person.tasks_this_year} of ${quotaLimit ? limitWord(quotaLimit) : "∞"}`}
                      />
                    </td>
                    <td className={cn(TD_CLASS, "py-2.5")}>
                      <LastActivity person={person} />
                    </td>
                    <td className={cn(TD_CLASS, ACTIONS_TD_CLASS, "py-2 pr-2")}>
                      <RowMenu
                        id={rowMenuId(person.user_id)}
                        label={`Actions for ${person.display_name}`}
                        items={menuFor(person)}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {visible.length === 0 && <EmptyRows label="No people match." />}
        </div>
      )}
      {retry !== null && <FailedDialog message="Could not finish the action." onRetry={retry} onClose={() => setRetry(null)} />}

      {viewing !== null && (
        <PersonDialog
          person={byId.get(viewing.user_id) ?? viewing}
          onClose={() => setViewing(null)}
          onQuota={() => navigate(`/people/${viewing.user_id}/quota`)}
        />
      )}
      {dialog?.kind === "move" && (
        <MoveDialog
          people={chosen}
          organisations={organisations.data ?? []}
          pending={enrol.isPending}
          onOpenChange={close}
          returnFocus={returnFocus}
          onMove={(org) =>
            run(enrol, { user_ids: dialog.ids, org_id: org.org_id }, dialog.ids, (person) =>
              `Moved ${person.display_name} to ${org.name}`,
            )
          }
        />
      )}
      {(dialog?.kind === "cohortAdd" || dialog?.kind === "cohortRemove") && (
        <CohortDialog
          adding={dialog.kind === "cohortAdd"}
          people={chosen}
          cohorts={
            dialog.kind === "cohortAdd"
              ? (cohorts.data ?? [])
              : (cohorts.data ?? []).filter((cohort) =>
                  chosen.some((person) => person.cohorts.some((own) => own.cohort_id === cohort.cohort_id)),
                )
          }
          pending={cohortAdd.isPending || cohortRemove.isPending}
          onOpenChange={close}
          returnFocus={returnFocus}
          onSave={(cohort) =>
            run(
              dialog.kind === "cohortAdd" ? cohortAdd : cohortRemove,
              { user_ids: dialog.ids, cohort_id: cohort.cohort_id },
              dialog.ids,
              (person) =>
                dialog.kind === "cohortAdd"
                  ? `Added ${person.display_name} to ${cohort.name}`
                  : `Removed ${person.display_name} from ${cohort.name}`,
            )
          }
        />
      )}
      {dialog?.kind === "deenrol" && (
        <Dialog
          open
          onOpenChange={close}
          returnFocus={returnFocus}
          title={`De-enrol ${who(chosen)}?`}
          description={DE_ENROL_SENTENCE}
          footer={
            <>
              <Button variant="ghost" onClick={() => setDialog(null)}>
                Cancel
              </Button>
              <Button
                disabled={deEnrol.isPending}
                onClick={() => run(deEnrol, dialog.ids, dialog.ids, (person) => `De-enrolled ${person.display_name}`)}
              >
                De-enrol
              </Button>
            </>
          }
        >
          {chosen.length > 1 && <NameList people={chosen} />}
        </Dialog>
      )}
      {dialog?.kind === "offboard" && (
        <OffboardDialog
          people={chosen}
          pending={offboard.isPending}
          onOpenChange={close}
          returnFocus={returnFocus}
          onOffboard={() => run(offboard, dialog.ids, dialog.ids, (person) => `Offboarded ${person.display_name}`)}
        />
      )}
      {dialog?.kind === "quota" && (
        <BulkQuotaDialog
          people={chosen}
          pending={quota.isPending}
          onOpenChange={close}
          returnFocus={returnFocus}
          onSave={(draft) =>
            run(quota, { user_ids: dialog.ids, ...valuesOf(draft) }, dialog.ids, () => "Quota saved")
          }
        />
      )}
    </>
  );
}

type DialogProps = {
  people: readonly Person[];
  pending: boolean;
  onOpenChange: (open: boolean) => void;
  returnFocus: () => HTMLElement | null;
};

function MoveDialog({
  people,
  organisations,
  pending,
  onOpenChange,
  returnFocus,
  onMove,
}: DialogProps & { organisations: readonly Organisation[]; onMove: (org: Organisation) => void }) {
  const [orgId, setOrgId] = useState("");
  const org = organisations.find((entry) => entry.org_id === orgId);
  return (
    <Dialog
      open
      onOpenChange={onOpenChange}
      returnFocus={returnFocus}
      describedBy="move-org-help"
      title={`Move ${who(people)} to an organisation`}
      footer={
        <>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button disabled={org === undefined || pending} onClick={() => org !== undefined && onMove(org)}>
            Move
          </Button>
        </>
      }
    >
      <Field id="move-org" label="Organisation" help="Their tasks and projects move with them and become private.">
        {(describedBy) => (
          <OrganisationSelect
            id="move-org"
            label="Organisation"
            organisations={organisations}
            value={orgId}
            onChange={setOrgId}
            describedBy={describedBy}
          />
        )}
      </Field>
      {people.length > 1 && <NameList people={people} />}
    </Dialog>
  );
}

/**
 * Offboard, the one red button. One person confirms by typing their address;
 * several (or one with no address) by typing how many, under the list of
 * every name and address (contract B6, revision 3.1). The consequence
 * sentence is the dialog's description, read before the confirm field.
 */
function OffboardDialog({
  people,
  pending,
  onOpenChange,
  returnFocus,
  onOffboard,
}: DialogProps & { onOffboard: () => void }) {
  const [typed, setTyped] = useState("");
  const email = people.length === 1 ? people[0].email : null;
  const confirmed =
    email != null
      ? typed.trim().toLowerCase() === email.toLowerCase()
      : typed.trim() === String(people.length);
  return (
    <Dialog
      open
      onOpenChange={onOpenChange}
      returnFocus={returnFocus}
      title={`Offboard ${who(people)}?`}
      description={OFFBOARD_SENTENCE}
      footer={
        <>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            {people.length > 1 ? "Keep the accounts" : "Keep the account"}
          </Button>
          <Button className={DANGER_CLASS} disabled={!confirmed || pending} onClick={onOffboard}>
            Offboard
          </Button>
        </>
      }
    >
      {email == null && <NameList people={people} />}
      <div className="mt-5">
        <Field id="offboard-confirm" label={email != null ? "Type the email to confirm" : "Type the number of people to confirm"}>
          <input
            id="offboard-confirm"
            autoComplete="off"
            spellCheck={false}
            inputMode={email != null ? "email" : "numeric"}
            value={typed}
            placeholder={email ?? undefined}
            onChange={(event) => setTyped(event.target.value)}
            className={INPUT_CLASS}
          />
        </Field>
      </div>
    </Dialog>
  );
}

/** Several people's quota at once: Cancel where every dialog keeps it, then Clear and inherit beside Save quota. */
function BulkQuotaDialog({
  people,
  pending,
  onOpenChange,
  returnFocus,
  onSave,
}: DialogProps & { onSave: (draft: QuotaDraft) => void }) {
  const [draft, setDraft] = useState<QuotaDraft>({ tasks: "", runs: "" });
  const [errors, setErrors] = useState<QuotaErrors>({});
  const save = () => {
    setErrors(draftErrors(draft));
    if (draftIsValid(draft)) onSave(draft);
  };
  return (
    <Dialog
      open
      onOpenChange={onOpenChange}
      returnFocus={returnFocus}
      title={`Quota for ${who(people)}`}
      footer={
        <>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button variant="ghost" disabled={pending} onClick={() => onSave({ tasks: "", runs: "" })}>
            Clear and inherit
          </Button>
          <Button disabled={pending} onClick={save}>
            Save quota
          </Button>
        </>
      }
    >
      <QuotaFields
        draft={draft}
        onChange={setDraft}
        who={people.length > 1 ? WARNING_WHO.people : WARNING_WHO.person}
        errors={errors}
      />
      <NameList people={people} />
    </Dialog>
  );
}

/**
 * Add the people to one cohort, or take them out of one. Removing lists only
 * the cohorts at least one of them is in; adding with no cohorts yet points
 * at the Cohorts page.
 */
function CohortDialog({
  adding,
  people,
  cohorts,
  pending,
  onOpenChange,
  returnFocus,
  onSave,
}: DialogProps & { adding: boolean; cohorts: readonly Cohort[]; onSave: (cohort: Cohort) => void }) {
  const [cohortId, setCohortId] = useState("");
  const cohort = cohorts.find((entry) => entry.cohort_id === cohortId);
  return (
    <Dialog
      open
      onOpenChange={onOpenChange}
      returnFocus={returnFocus}
      title={adding ? `Add ${who(people)} to a cohort` : `Remove ${who(people)} from a cohort`}
      description={
        adding
          ? "A cohort is a label for research and pilots. It does not change what they can see."
          : "Only the label comes off. Their account and work do not change."
      }
      footer={
        <>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button disabled={cohort === undefined || pending} onClick={() => cohort !== undefined && onSave(cohort)}>
            {adding ? "Add" : "Remove"}
          </Button>
        </>
      }
    >
      <div className="mt-4">
        {cohorts.length === 0 ? (
          <p className="text-body text-grey">
            {adding ? "No cohorts yet. Create one on the Cohorts page first." : "They are in no cohorts."}
          </p>
        ) : (
          <Field id="cohort-pick" label="Cohort">
            <SearchSelect
              id="cohort-pick"
              label="Cohort"
              value={cohortId}
              placeholder="Choose a cohort."
              options={cohorts.map((entry) => ({ value: entry.cohort_id, label: entry.name }))}
              onChange={setCohortId}
              filterLabel="Find a cohort"
              empty="No cohorts match."
            />
          </Field>
        )}
      </div>
      {people.length > 1 && <NameList people={people} />}
    </Dialog>
  );
}

/** One person's full record: everything the table truncates or leaves out. */
function PersonDialog({ person, onClose, onQuota }: { person: Person; onClose: () => void; onQuota: () => void }) {
  const flags = [person.is_admin && "ADMIN", person.is_ops && "OPS"].filter(Boolean).join(", ");
  const limit = (value: number | null | undefined, from: string) => facts(limitWord(value), `from ${from}`);
  const rows: Array<[string, ReactNode]> = [
    ["Email", person.email ?? <span className="text-grey">none stored</span>],
    ["Organisation", person.organisation?.name ?? <span className="text-grey">not enrolled</span>],
    [
      "Cohorts",
      person.cohorts.length === 0 ? (
        <span className="text-grey">none</span>
      ) : (
        <ul>
          {person.cohorts.map((cohort) => (
            <li key={cohort.cohort_id}>{cohort.name}</li>
          ))}
        </ul>
      ),
    ],
    ["Flags", flags === "" ? <span className="text-grey">none</span> : flags],
    ["Tasks this year", `${person.tasks_this_year} in the last 365 days`],
    ["Tasks per year", limit(person.limits.task_quota_per_year, sourceLabel(person.limits.task_quota_from))],
    ["Simultaneous tasks", limit(person.limits.runs_per_user, sourceLabel(person.limits.runs_from))],
    [
      "Last task",
      waitingForSignIn(person)
        ? "Invited, not signed in yet"
        : person.last_task_at != null
          ? `${formatDate(person.last_task_at, "long")}, ${formatDate(person.last_task_at, "time")}`
          : "No tasks yet",
    ],
    ["Invited", person.invited_at != null ? `${formatDate(person.invited_at, "long")}, ${formatDate(person.invited_at, "time")}` : "—"],
    [
      "First signed in",
      person.first_signed_in_at != null
        ? `${formatDate(person.first_signed_in_at, "long")}, ${formatDate(person.first_signed_in_at, "time")}`
        : "—",
    ],
    ["Account created", `${formatDate(person.created_at, "long")}, ${formatDate(person.created_at, "time")}`],
  ];
  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={person.display_name}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
          <Button variant="outline" onClick={onQuota}>
            Set quota
          </Button>
        </>
      }
    >
      <dl className="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-6 gap-y-3 text-body">
        {rows.map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="font-semibold text-navy">{label}</dt>
            <dd className="break-words">
              {typeof value === "string" ? <Figures text={value} /> : value}
            </dd>
          </div>
        ))}
      </dl>
    </Dialog>
  );
}

/** Invited by the ops pages or the sweep, and has not opened the app since. */
function waitingForSignIn(person: Person): boolean {
  return person.invited_at != null && person.first_signed_in_at == null;
}

/**
 * When the person last worked: their latest task's age. Until an invited
 * person first opens the app, the yellow "Invited" and when it was sent
 * instead (owner, 2026-11-18); Resend is in the row menu.
 */
function LastActivity({ person }: { person: Person }) {
  if (waitingForSignIn(person)) {
    return (
      <div className="flex flex-col items-start gap-1">
        <Chip tone="yellow">Invited</Chip>
        <span className="text-meta text-grey">
          <Figures text={`sent ${ago(person.invited_at ?? "")}`} />
        </span>
      </div>
    );
  }
  if (person.last_task_at == null) return <span className="text-grey">No tasks yet</span>;
  return <Figures text={ago(person.last_task_at)} />;
}

