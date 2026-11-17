import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router";

import { Button } from "../../ui/brand/Button";
import { Checkbox } from "../../ui/brand/Checkbox";
import { Chip } from "../../ui/brand/Chip";
import { Figures } from "../../lib/figures";
import { cn } from "../../ui/brand/cn";
import { PageHeader, PagePrimary } from "../../ui/brand/PageHeader";
import {
  errorStatus,
  useBulk,
  useEnrol,
  useOrganisations,
  usePeople,
  usePeopleQuota,
  type ActionResult,
  type Organisation,
  type Person,
} from "../api";
import { ago, inCooldown, limitWord, resendHint } from "../format";
import {
  DANGER_CLASS,
  Dialog,
  FailedLine,
  Field,
  FIGURE_CLASS,
  INPUT_CLASS,
  Loading,
  NameList,
  OrganisationSelect,
  RowMenu,
  SearchField,
  TABLE_CLASS,
  TABLE_WRAP_CLASS,
  TD_CLASS,
  TH_CLASS,
  useRecordedToast,
} from "../ui";
import { QuotaFields, valuesOf, type QuotaDraft } from "./QuotaFields";

/** A line under a person's name after an action: a failure's message, or a cooldown. */
type Note = { text: string; failed: boolean };

type DialogState = { kind: "move" | "deenrol" | "offboard" | "quota"; ids: string[] } | null;

const COOLDOWN_NOTE = "Sent less than an hour ago";

function matches(person: Person, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (q === "") return true;
  return [person.display_name, person.email ?? "", person.organisation?.name ?? ""].some((value) =>
    value.toLowerCase().includes(q),
  );
}

/** "Tom Ellis" for one, "3 people" for several. */
function who(people: readonly Person[]): string {
  return people.length === 1 ? people[0].display_name : `${people.length} people`;
}

/** The People list (ops-pages-copy.md § People). */
export function PeopleView() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [query, setQuery] = useState(params.get("q") ?? "");
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
  const [dialog, setDialog] = useState<DialogState>(null);
  const [notes, setNotes] = useState<Record<string, Note>>({});
  const [retry, setRetry] = useState<(() => void) | null>(null);
  const people = usePeople();
  const organisations = useOrganisations();
  const toast = useRecordedToast();
  const enrol = useEnrol();
  const deEnrol = useBulk("/api/v1/ops/people/de-enrol");
  const offboard = useBulk("/api/v1/ops/people/offboard");
  const resend = useBulk("/api/v1/ops/people/resend");
  const quota = usePeopleQuota();

  if (people.isPending) return <Loading />;
  const all = people.data ?? [];
  const visible = all.filter((person) => matches(person, query));
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

  /**
   * Show what a bulk route did: the toast, and each failed or cooling row's
   * line under its name. One person who went through gets the action's own
   * summary; otherwise the counts.
   */
  const report = (results: readonly ActionResult[], summary: (person: Person) => string) => {
    setNotes((current) => {
      const next = { ...current };
      for (const result of results) {
        if (result.outcome === "failed") next[result.user_id] = { text: result.message, failed: true };
        else if (result.outcome === "too_soon") next[result.user_id] = { text: COOLDOWN_NOTE, failed: false };
        else delete next[result.user_id];
      }
      return next;
    });
    const done = results.filter((result) => result.outcome === "ok").length;
    const failed = results.filter((result) => result.outcome === "failed").length;
    const only = results.length === 1 && done === 1 ? byId.get(results[0].user_id) : undefined;
    if (only !== undefined) toast(summary(only));
    else if (done + failed > 0) toast(`${done} done, ${failed} failed`);
    if (failed === 0) setSelected(new Set());
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
        setDialog(null);
        report(data.results, summary);
      },
      onError: (error) => {
        setDialog(null);
        if (errorStatus(error) === 429) {
          report(ids.map((id) => ({ user_id: id, outcome: "too_soon", message: COOLDOWN_NOTE })), summary);
          return;
        }
        setRetry(() => again);
      },
    });
  };

  const sendInvitations = (ids: string[]) =>
    run(resend, ids, ids, (person) => `Invitation sent to ${person.email ?? person.display_name}`);

  const menuFor = (person: Person) => [
    { label: "Enrol or move to an organisation…", onSelect: () => setDialog({ kind: "move", ids: [person.user_id] }) },
    { label: "Set quota…", onSelect: () => navigate(`/people/${person.user_id}/quota`) },
    {
      label: "Resend invitation",
      onSelect: () => sendInvitations([person.user_id]),
      disabled: inCooldown(person.invited_at),
      hint: inCooldown(person.invited_at) && person.invited_at != null ? resendHint(person.invited_at) : undefined,
    },
    {
      label: "De-enrol",
      onSelect: () => setDialog({ kind: "deenrol", ids: [person.user_id] }),
      disabled: person.organisation == null && !person.is_admin && !person.is_ops,
    },
    { label: "Offboard…", onSelect: () => setDialog({ kind: "offboard", ids: [person.user_id] }) },
  ];

  const ticked = [...selected].filter((id) => byId.has(id));
  const bar =
    ticked.length > 0 ? (
      <div
        role="toolbar"
        aria-label="Selected people"
        className="flex min-h-12 flex-wrap items-center gap-x-1 gap-y-1 border-x border-t border-line bg-blue-tint-2 px-4 py-1.5"
      >
        <span className="mr-2 text-meta font-semibold text-navy">
          <Figures text={`${ticked.length} selected`} />
        </span>
        <Button variant="secondary" size="sm" onClick={() => setDialog({ kind: "quota", ids: ticked })}>
          Set quota…
        </Button>
        <Button variant="secondary" size="sm" onClick={() => setDialog({ kind: "move", ids: ticked })}>
          Move to…
        </Button>
        <Button variant="secondary" size="sm" onClick={() => sendInvitations(ticked)}>
          Resend invitation
        </Button>
        <Button variant="secondary" size="sm" onClick={() => setDialog({ kind: "deenrol", ids: ticked })}>
          De-enrol
        </Button>
        <Button variant="secondary" size="sm" onClick={() => setDialog({ kind: "offboard", ids: ticked })}>
          Offboard…
        </Button>
        <Button variant="ghost" size="sm" onClick={() => setSelected(new Set())}>
          Clear selection
        </Button>
      </div>
    ) : null;

  const chosen = dialog === null ? [] : subjects(dialog.ids);
  const close = (open: boolean) => {
    if (!open) setDialog(null);
  };

  return (
    <>
      <PageHeader
        title="People"
        actions={<PagePrimary to="/people/new">Add person</PagePrimary>}
        filters={<SearchField placeholder="Find by name, email or organisation" value={query} onChange={setQuery} />}
      />
      <div className="mt-6">
        {bar}
        {people.isError ? (
          <FailedLine onRetry={() => void people.refetch()} />
        ) : (
          <div className={TABLE_WRAP_CLASS}>
            <table className={TABLE_CLASS}>
              <thead>
                <tr>
                  <th className={cn(TH_CLASS, "w-10 pl-4")}>
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
                  <th className={TH_CLASS}>Name</th>
                  <th className={TH_CLASS}>Email</th>
                  <th className={TH_CLASS}>Organisation</th>
                  <th className={TH_CLASS}>Flags</th>
                  <th className={cn(TH_CLASS, "text-right")}>Tasks this year</th>
                  <th className={TH_CLASS}>Invited</th>
                  <th className={cn(TH_CLASS, "w-10")}>
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {visible.map((person) => {
                  const note = notes[person.user_id];
                  const quotaLimit = person.limits.task_quota_per_year;
                  return (
                    <tr key={person.user_id} className={cn(selected.has(person.user_id) && "bg-blue-tint-2")}>
                      <td className={cn(TD_CLASS, "py-1 pl-4")}>
                        <Checkbox
                          checked={selected.has(person.user_id)}
                          label={<span className="sr-only">Select {person.display_name}</span>}
                          onChange={(on) => toggle(person.user_id, on)}
                        />
                      </td>
                      <td className={TD_CLASS}>
                        <span className="whitespace-nowrap font-semibold text-navy">{person.display_name}</span>
                        {note !== undefined && (
                          <span className={cn("block text-meta", note.failed ? "text-red" : "text-grey")}>
                            {note.text}
                          </span>
                        )}
                      </td>
                      <td className={TD_CLASS}>{person.email ?? "—"}</td>
                      <td className={TD_CLASS}>
                        {person.organisation != null ? (
                          person.organisation.name
                        ) : (
                          <span className="text-grey">not enrolled</span>
                        )}
                      </td>
                      <td className={cn(TD_CLASS, "py-2.5")}>
                        <span className="flex gap-1.5">
                          {person.is_admin && <Chip>Admin</Chip>}
                          {person.is_ops && <Chip>Ops</Chip>}
                        </span>
                      </td>
                      <td className={cn(TD_CLASS, FIGURE_CLASS)}>
                        <Figures
                          text={quotaLimit == null ? "no limit" : `${person.tasks_this_year} of ${limitWord(quotaLimit)}`}
                        />
                      </td>
                      <td className={cn(TD_CLASS, "whitespace-nowrap")}>
                        <Figures text={person.invited_at != null ? ago(person.invited_at) : "—"} />
                      </td>
                      <td className={cn(TD_CLASS, "py-2 pr-2")}>
                        <RowMenu label={`Actions for ${person.display_name}`} items={menuFor(person)} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {retry !== null && <FailedLine onRetry={retry} />}
      </div>

      {dialog?.kind === "move" && (
        <MoveDialog
          people={chosen}
          organisations={organisations.data ?? []}
          pending={enrol.isPending}
          onOpenChange={close}
          onMove={(org) =>
            run(enrol, { user_ids: dialog.ids, org_id: org.org_id }, dialog.ids, (person) =>
              `Moved ${person.display_name} to ${org.name}`,
            )
          }
        />
      )}
      {dialog?.kind === "deenrol" && (
        <Dialog
          open
          onOpenChange={close}
          title={`De-enrol ${who(chosen)}?`}
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
          <p className="text-body text-ink">
            They stay signed in but leave their organisation. Their tasks and projects stay with them and leave the
            organisation too.
          </p>
          {chosen.length > 1 && <NameList people={chosen} />}
        </Dialog>
      )}
      {dialog?.kind === "offboard" && (
        <OffboardDialog
          people={chosen}
          pending={offboard.isPending}
          onOpenChange={close}
          onOffboard={() => run(offboard, dialog.ids, dialog.ids, (person) => `Offboarded ${person.display_name}`)}
        />
      )}
      {dialog?.kind === "quota" && (
        <BulkQuotaDialog
          people={chosen}
          pending={quota.isPending}
          onOpenChange={close}
          onSave={(draft) =>
            run(quota, { user_ids: dialog.ids, ...valuesOf(draft) }, dialog.ids, () => "Quota saved")
          }
        />
      )}
    </>
  );
}

function MoveDialog({
  people,
  organisations,
  pending,
  onOpenChange,
  onMove,
}: {
  people: readonly Person[];
  organisations: readonly Organisation[];
  pending: boolean;
  onOpenChange: (open: boolean) => void;
  onMove: (org: Organisation) => void;
}) {
  const [orgId, setOrgId] = useState("");
  const org = organisations.find((entry) => entry.org_id === orgId);
  return (
    <Dialog
      open
      onOpenChange={onOpenChange}
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
        <OrganisationSelect
          id="move-org"
          label="Organisation"
          organisations={organisations}
          value={orgId}
          onChange={setOrgId}
        />
      </Field>
      {people.length > 1 && <NameList people={people} />}
    </Dialog>
  );
}

/**
 * Offboard, the one red button. One person confirms by typing their address;
 * several (or one with no address) by typing how many, under the list of
 * every name and address (contract B6, revision 3.1).
 */
function OffboardDialog({
  people,
  pending,
  onOpenChange,
  onOffboard,
}: {
  people: readonly Person[];
  pending: boolean;
  onOpenChange: (open: boolean) => void;
  onOffboard: () => void;
}) {
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
      title={`Offboard ${who(people)}?`}
      footer={
        <>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Keep the account
          </Button>
          <Button className={DANGER_CLASS} disabled={!confirmed || pending} onClick={onOffboard}>
            Offboard
          </Button>
        </>
      }
    >
      <p className="text-body text-ink">
        This stops them signing in, signs them out everywhere, removes them from their organisation and takes down
        any public links to their tasks. Their tasks stay in the database. This cannot be undone from here.
      </p>
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

function BulkQuotaDialog({
  people,
  pending,
  onOpenChange,
  onSave,
}: {
  people: readonly Person[];
  pending: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (draft: QuotaDraft) => void;
}) {
  const [draft, setDraft] = useState<QuotaDraft>({ tasks: "", runs: "" });
  return (
    <Dialog
      open
      onOpenChange={onOpenChange}
      title={`Quota for ${who(people)}`}
      footer={
        <>
          <Button variant="ghost" disabled={pending} onClick={() => onSave({ tasks: "", runs: "" })}>
            Clear and inherit
          </Button>
          <Button disabled={pending} onClick={() => onSave(draft)}>
            Save quota
          </Button>
        </>
      }
    >
      <QuotaFields draft={draft} onChange={setDraft} />
      <NameList people={people} />
    </Dialog>
  );
}
