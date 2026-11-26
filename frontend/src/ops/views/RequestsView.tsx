import { useRef, useState } from "react";
import { Link } from "react-router";

import { formatDate } from "../../lib/dates";
import { Figures } from "../../lib/figures";
import { Button } from "../../ui/brand/Button";
import { Checkbox } from "../../ui/brand/Checkbox";
import { cn } from "../../ui/brand/cn";
import { LINK_CLASS } from "../../ui/brand/inlineActions";
import { PageHeader } from "../../ui/brand/PageHeader";
import { OpsApiError, unwrap, unwrapEmpty, useOpsAction, useOrganisations, useRequests, type AccessRequest } from "../api";
import { ago, facts, orgInRefusal } from "../format";
import {
  ACTIONS_TD_CLASS,
  ACTIONS_TH_CLASS,
  DANGER_CLASS,
  Dialog,
  EmptyRows,
  FailedDialog,
  FailedLine,
  Field,
  Loading,
  NameList,
  CohortsField,
  OrganisationSelect,
  SearchField,
  SortTh,
  TABLE_CLASS,
  TABLE_WRAP_CLASS,
  TD_CLASS,
  TH_CLASS,
  useCohortNames,
  useRecordedToast,
  useSort,
  withCohorts,
} from "../ui";

type RequestInvite = NonNullable<AccessRequest["invite"]>;

/** The words after "Invite link: <label> — " for each reason a code has made no account yet. */
const INVITE_REASONS: Record<Exclude<RequestInvite["reason"], "unknown_code">, string> = {
  wrong_domain: "wrong email domain",
  expired: "expired",
  full: "full",
  revoked: "revoked",
  next_run: "waiting for the next run",
  retry_wait: "last try failed, next try in a few minutes",
};

/** Why a waiting request's invite code has made no account yet. */
function inviteLine(invite: RequestInvite): string {
  return invite.reason === "unknown_code"
    ? "Invite link: code not recognised"
    : `Invite link: ${invite.label ?? ""} — ${INVITE_REASONS[invite.reason]}`;
}

/** A row turned to Check by a refused approval, before the list says so. */
type Refusal = { org: string; message: string };

/**
 * A request's status in plain words: Waiting, Rejected, or Already in an
 * organisation (Check). An invited request is on People, never listed here.
 */
function Status({ request, refusal }: { request: AccessRequest; refusal: Refusal | undefined }) {
  // Plain words like the Requested column: no badges.
  if (refusal !== undefined || request.status === "check") {
    return <span className="block truncate">Already in {refusal?.org ?? request.note}</span>;
  }
  if (request.status === "rejected") {
    return <Figures text={request.rejected_at != null ? `Rejected ${ago(request.rejected_at)}` : "Rejected"} />;
  }
  return <>Waiting</>;
}

/** Access requests (ops-pages-copy.md § Requests). */
export function RequestsView() {
  const [showRejected, setShowRejected] = useState(false);
  const requests = useRequests(showRejected);
  const organisations = useOrganisations();
  const toast = useRecordedToast();
  const [query, setQuery] = useState("");
  const [approving, setApproving] = useState<AccessRequest | null>(null);
  // Several waiting requests approved into one organisation at once.
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
  const [approvingMany, setApprovingMany] = useState<AccessRequest[] | null>(null);
  const [bulkPending, setBulkPending] = useState(false);
  const [rejecting, setRejecting] = useState<AccessRequest[] | null>(null);
  const [deleting, setDeleting] = useState<AccessRequest | null>(null);
  const remove = useOpsAction((client, entryId: string) =>
    unwrapEmpty(client.DELETE("/api/v1/ops/requests/{entry_id}", { params: { path: { entry_id: entryId } } })),
  );
  const reject = useOpsAction((client, entryId: string) =>
    unwrapEmpty(client.POST("/api/v1/ops/requests/{entry_id}/reject", { params: { path: { entry_id: entryId } } })),
  );
  const [viewing, setViewing] = useState<AccessRequest | null>(null);
  const [orgId, setOrgId] = useState("");
  const [cohortIds, setCohortIds] = useState<string[]>([]);
  const cohortNames = useCohortNames();
  const [refusals, setRefusals] = useState<Record<string, Refusal>>({});
  const [retry, setRetry] = useState<(() => void) | null>(null);
  const tableRef = useRef<HTMLTableElement>(null);
  /** Whether the open dialog's approval came back: its row's button is then on its way out. */
  const answered = useRef(false);
  const approve = useOpsAction(
    (client, { entryId, org, cohorts }: { entryId: string; org: string; cohorts: string[] }) =>
      unwrap(
        client.POST("/api/v1/ops/requests/{entry_id}/approve", {
          params: { path: { entry_id: entryId } },
          body: { org_id: org, cohort_ids: cohorts },
        }),
      ),
  );

  const send = (request: AccessRequest, org: string, cohorts: string[]) => {
    setRetry(null);
    approve.mutate(
      { entryId: request.entry_id, org, cohorts },
      {
        onSuccess: () => {
          answered.current = true;
          setApproving(null);
          toast(withCohorts(`${request.name} approved`, cohortNames(cohorts)));
        },
        onError: (error) => {
          setApproving(null);
          if (error instanceof OpsApiError && error.code === "enrolled_elsewhere") {
            answered.current = true;
            setRefusals((current) => ({
              ...current,
              [request.entry_id]: { org: orgInRefusal(error.message) ?? "another organisation", message: error.message },
            }));
          } else {
            setRetry(() => () => send(request, org, cohorts));
          }
        },
      },
    );
  };

  /**
   * Approve each request in turn through the one-request route, so each keeps
   * its own audit row and its own outcome; a refusal marks its row Check.
   */
  const sendMany = async (many: AccessRequest[], org: string, cohorts: string[]) => {
    setBulkPending(true);
    setRetry(null);
    let approved = 0;
    const failed: AccessRequest[] = [];
    for (const request of many) {
      try {
        await approve.mutateAsync({ entryId: request.entry_id, org, cohorts });
        approved += 1;
      } catch (error) {
        if (error instanceof OpsApiError && error.code === "enrolled_elsewhere") {
          setRefusals((current) => ({
            ...current,
            [request.entry_id]: { org: orgInRefusal(error.message) ?? "another organisation", message: error.message },
          }));
        } else {
          failed.push(request);
        }
      }
    }
    setBulkPending(false);
    setApprovingMany(null);
    setSelected(new Set());
    const refused = many.length - approved - failed.length;
    toast(facts(`${approved} approved`, ...(refused > 0 ? [`${refused} already in another organisation`] : []), ...(failed.length > 0 ? [`${failed.length} failed`] : [])));
    if (failed.length > 0) setRetry(() => () => void sendMany(failed, org, cohorts));
  };

  /** Reject each request in turn: no email; each keeps its own audit row. */
  const rejectMany = async (many: AccessRequest[]) => {
    setBulkPending(true);
    setRetry(null);
    const failed: AccessRequest[] = [];
    let refusal = "";
    for (const request of many) {
      try {
        await reject.mutateAsync(request.entry_id);
      } catch (error) {
        failed.push(request);
        if (error instanceof OpsApiError) refusal = error.message;
      }
    }
    setBulkPending(false);
    setRejecting(null);
    setSelected(new Set());
    const done = many.length - failed.length;
    toast(
      many.length === 1 && failed.length === 0
        ? `${many[0].name} rejected`
        : many.length === 1 && refusal !== ""
          ? refusal
          : facts(`${done} rejected`, ...(failed.length > 0 ? [`${failed.length} failed`] : [])),
    );
    if (failed.length > 0) setRetry(() => () => void rejectMany(failed));
  };

  const signup = requests.data?.self_signup;
  const q = query.trim().toLowerCase();
  const { sorted: rows, sort, onSort } = useSort(
    (requests.data?.items ?? []).filter(
      (item) => q === "" || item.name.toLowerCase().includes(q) || item.email.toLowerCase().includes(q),
    ),
    {
      name: (item) => item.name,
      email: (item) => item.email,
      organisation: (item) => item.organisation,
      requested: (item) => item.created_at,
      // Waiting first, then those to check, then the rejected record.
      status: (item) => ({ waiting: 0, check: 1, invited: 2, rejected: 3 })[item.status],
    },
  );
  const th = { sort, onSort };
  if (requests.isPending) return <Loading />;
  // Only a waiting request can be approved, so only those can be ticked.
  const waiting = rows.filter((item) => item.status === "waiting" && refusals[item.entry_id] === undefined);
  const ticked = waiting.filter((item) => selected.has(item.entry_id));
  const allTicked = waiting.length > 0 && ticked.length === waiting.length;
  const toggle = (entryId: string, on: boolean) =>
    setSelected((current) => {
      const next = new Set(current);
      if (on) next.add(entryId);
      else next.delete(entryId);
      return next;
    });
  const selectAll = () => setSelected(new Set(waiting.map((item) => item.entry_id)));
  const clearChoice = () => {
    setOrgId("");
    setCohortIds([]);
  };
  const openMany = () => {
    clearChoice();
    setApprovingMany(ticked);
  };

  return (
    <>
      <PageHeader
        title="Waitlist"
        actions={null}
        filters={
          <div className="flex flex-col gap-4">
            {signup !== undefined && <SelfSignupLine signup={signup} />}
            <SearchField placeholder="Find by name or email" value={query} onChange={setQuery} />
          </div>
        }
      />
      <div className="mt-4 min-h-12">
        {ticked.length === 0 && (
          <div className="flex min-h-12 items-center gap-1">
            {waiting.length > 0 && (
              <Button variant="ghost" size="sm" onClick={selectAll}>
                Select all {waiting.length} waiting
              </Button>
            )}
            <Button variant="ghost" size="sm" aria-pressed={showRejected} onClick={() => setShowRejected((on) => !on)}>
              {showRejected ? "Hide rejected" : "Show rejected"}
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
            <Button variant="secondary" size="sm" onClick={openMany}>
              Approve
            </Button>
            <Button variant="secondary" size="sm" onClick={() => setRejecting(ticked)}>
              Reject
            </Button>
            {!allTicked && (
              <Button variant="ghost" size="sm" onClick={selectAll}>
                Select all {waiting.length} waiting
              </Button>
            )}
            <Button variant="ghost" size="sm" onClick={() => setSelected(new Set())}>
              Clear selection
            </Button>
          </div>
        )}
      </div>
      <div>
        {requests.isError ? (
          <FailedLine message="Could not load the waitlist." onRetry={() => void requests.refetch()} />
        ) : (
          <div className={TABLE_WRAP_CLASS}>
            <table ref={tableRef} tabIndex={-1} aria-label="Waitlist" className={TABLE_CLASS}>
              <thead>
                <tr>
                  <th className={cn(TH_CLASS, "w-12 overflow-visible pb-0 pl-4")}>
                    <Checkbox
                      checked={allTicked}
                      label={<span className="sr-only">Select every waiting request shown</span>}
                      onChange={(on) => (on ? selectAll() : setSelected(new Set()))}
                    />
                  </th>
                  <SortTh {...th} sortKey="name" label="Name" className="w-40" />
                  <SortTh {...th} sortKey="email" label="Email" className="w-52" />
                  <SortTh {...th} sortKey="organisation" label="Organisation" className="w-56" />
                  <SortTh {...th} sortKey="requested" label="Requested" className="w-32" />
                  <SortTh {...th} sortKey="status" label="Status" className="w-40" />
                  <th className={cn(TH_CLASS, ACTIONS_TH_CLASS, "w-48")}>
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((request) => {
                  const refusal = refusals[request.entry_id];
                  const check = refusal !== undefined || request.status === "check";
                  return (
                    <tr key={request.entry_id} className={selected.has(request.entry_id) ? "bg-blue-tint-2" : "bg-paper"}>
                      <td className={cn(TD_CLASS, "py-1 pl-4")}>
                        {request.status === "waiting" && refusal === undefined && (
                          <Checkbox
                            checked={selected.has(request.entry_id)}
                            label={<span className="sr-only">Select {request.name}</span>}
                            onChange={(on) => toggle(request.entry_id, on)}
                          />
                        )}
                      </td>
                      <td className={TD_CLASS}>
                        <button
                          type="button"
                          onClick={() => setViewing(request)}
                          className="block max-w-full cursor-pointer truncate text-left font-semibold text-navy hover:text-blue hover:underline"
                          title={request.name}
                        >
                          {request.name}
                        </button>
                        {refusal !== undefined && <span className="block text-meta text-grey">{refusal.message}</span>}
                      </td>
                      <td className={cn(TD_CLASS, "truncate")} title={request.email}>
                        {request.email}
                      </td>
                      <td className={TD_CLASS}>
                        <span className="block truncate" title={request.organisation ?? undefined}>
                          {request.organisation ?? <span className="text-grey">—</span>}
                        </span>
                        {request.invite != null && request.status === "waiting" && (
                          <span className="block text-meta text-grey">{inviteLine(request.invite)}</span>
                        )}
                      </td>
                      <td className={cn(TD_CLASS, "whitespace-nowrap")}>
                        <Figures text={ago(request.created_at)} />
                      </td>
                      <td className={TD_CLASS}>
                        <Status request={request} refusal={refusal} />
                      </td>
                      <td className={cn(TD_CLASS, ACTIONS_TD_CLASS, "whitespace-nowrap py-2 pr-4 text-right")}>
                        {check ? (
                          // The address rides in router state, not the URL, so it
                          // never reaches the server's access log.
                          <Link
                            to="/people"
                            state={{ q: request.email }}
                            className={cn(LINK_CLASS, "inline-flex h-8 items-center text-meta")}
                          >
                            Open person
                          </Link>
                        ) : request.status === "waiting" || request.status === "rejected" ? (
                          <span className="inline-flex items-center gap-2">
                            {request.status === "rejected" ? (
                              <Button variant="ghost" size="sm" className="text-red hover:text-red" onClick={() => setDeleting(request)}>
                                Delete
                              </Button>
                            ) : (
                              <Button variant="ghost" size="sm" onClick={() => setRejecting([request])}>
                                Reject
                              </Button>
                            )}
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => {
                                answered.current = false;
                                clearChoice();
                                setApproving(request);
                              }}
                            >
                              Approve
                            </Button>
                          </span>
                        ) : null}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {rows.length === 0 && <EmptyRows label="No requests yet." />}
          </div>
        )}
        {retry !== null && <FailedDialog message="Could not finish the action." onRetry={retry} onClose={() => setRetry(null)} />}
      </div>
      {viewing !== null && (
        <Dialog
          open
          onOpenChange={(open) => !open && setViewing(null)}
          title={viewing.name}
          footer={
            <>
              <Button variant="ghost" onClick={() => setViewing(null)}>
                Close
              </Button>
              {(viewing.status === "waiting" || viewing.status === "rejected") && refusals[viewing.entry_id] === undefined && (
                <Button
                  onClick={() => {
                    answered.current = false;
                    clearChoice();
                    setApproving(viewing);
                    setViewing(null);
                  }}
                >
                  Approve
                </Button>
              )}
            </>
          }
        >
          <dl className="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-6 gap-y-3 text-body">
            <dt className="font-semibold text-navy">Email</dt>
            <dd className="break-words">{viewing.email}</dd>
            <dt className="font-semibold text-navy">Organisation</dt>
            <dd>{viewing.organisation ?? <span className="text-grey">not given</span>}</dd>
            <dt className="font-semibold text-navy">Role or reason</dt>
            <dd className="whitespace-pre-line break-words">{viewing.role_or_reason}</dd>
            <dt className="font-semibold text-navy">Requested</dt>
            <dd>
              <Figures text={`${formatDate(viewing.created_at, "long")}, ${formatDate(viewing.created_at, "time")}`} />
            </dd>
            <dt className="font-semibold text-navy">Status</dt>
            <dd>
              <Status request={viewing} refusal={refusals[viewing.entry_id]} />
            </dd>
          </dl>
        </Dialog>
      )}

      {deleting !== null && (
        <Dialog
          open
          onOpenChange={(open) => !open && setDeleting(null)}
          title={`Delete ${deleting.name}'s request?`}
          description="This removes the request permanently. If they ask again, a new request appears here."
          footer={
            <>
              <Button variant="ghost" onClick={() => setDeleting(null)}>
                Cancel
              </Button>
              <Button
                className={DANGER_CLASS}
                disabled={remove.isPending}
                onClick={() =>
                  remove.mutate(deleting.entry_id, {
                    onSuccess: () => {
                      toast(`${deleting.name}'s request deleted`);
                      setDeleting(null);
                    },
                    onError: (error) => {
                      setDeleting(null);
                      setRetry(null);
                      toast(error.message || `Could not delete ${deleting.name}'s request`);
                    },
                  })
                }
              >
                Delete
              </Button>
            </>
          }
        />
      )}
      {rejecting !== null && (
        <Dialog
          open
          onOpenChange={(open) => !open && !bulkPending && setRejecting(null)}
          title={rejecting.length === 1 ? `Reject ${rejecting[0].name}?` : `Reject ${rejecting.length} requests?`}
          description="This will remove them from the waitlist. No account is created and no email is sent."
          footer={
            <>
              <Button variant="ghost" disabled={bulkPending} onClick={() => setRejecting(null)}>
                Cancel
              </Button>
              <Button className={DANGER_CLASS} disabled={bulkPending} onClick={() => void rejectMany(rejecting)}>
                {bulkPending ? "Rejecting…" : "Reject"}
              </Button>
            </>
          }
        >
          {rejecting.length > 1 && (
            <NameList
              people={rejecting.map((item) => ({ user_id: item.entry_id, display_name: item.name, email: item.email }))}
            />
          )}
        </Dialog>
      )}
      {approvingMany !== null && (
        <Dialog
          open
          onOpenChange={(open) => !open && !bulkPending && setApprovingMany(null)}
          title={`Approve ${approvingMany.length} requests`}
          footer={
            <>
              <Button variant="ghost" disabled={bulkPending} onClick={() => setApprovingMany(null)}>
                Cancel
              </Button>
              <Button disabled={orgId === "" || bulkPending} onClick={() => void sendMany(approvingMany, orgId, cohortIds)}>
                {bulkPending ? "Approving…" : "Approve"}
              </Button>
            </>
          }
        >
          <Field
            id="approve-many-org"
            label="Organisation"
            help="Each person gets an email with a temporary password. An address that already has an account is enrolled without an email."
          >
            {(describedBy) => (
              <OrganisationSelect
                id="approve-many-org"
                label="Organisation"
                organisations={organisations.data ?? []}
                value={orgId}
                onChange={setOrgId}
                describedBy={describedBy}
              />
            )}
          </Field>
          <div className="mt-5">
            <CohortsField id="approve-many-cohorts" values={cohortIds} onChange={setCohortIds} />
          </div>
          <NameList
            people={approvingMany.map((item) => ({ user_id: item.entry_id, display_name: item.name, email: item.email }))}
          />
        </Dialog>
      )}
      {approving !== null && (
        <Dialog
          open
          onOpenChange={(open) => !open && setApproving(null)}
          title={`Approve ${approving.name}`}
          describedBy="approve-org-help"
          // Approved or turned to Check, the row's button is gone: focus goes to the table.
          returnFocus={() => (answered.current ? tableRef.current : null)}
          footer={
            <>
              <Button variant="ghost" onClick={() => setApproving(null)}>
                Cancel
              </Button>
              <Button disabled={orgId === "" || approve.isPending} onClick={() => send(approving, orgId, cohortIds)}>
                Approve
              </Button>
            </>
          }
        >
          <Field
            id="approve-org"
            label="Organisation"
            help="Policy Atlas will email them a temporary password. If the address already has an account, it is enrolled without an email."
          >
            {(describedBy) => (
              <OrganisationSelect
                id="approve-org"
                label="Organisation"
                organisations={organisations.data ?? []}
                value={orgId}
                onChange={setOrgId}
                describedBy={describedBy}
              />
            )}
          </Field>
          <div className="mt-5">
            <CohortsField id="approve-cohorts" values={cohortIds} onChange={setCohortIds} />
          </div>
        </Dialog>
      )}
    </>
  );
}

/** What self-signup is doing, in a sentence or two under the title. */
function SelfSignupLine({ signup }: { signup: { enabled: boolean; domains: string[]; sent_this_hour: number; max_per_hour: number } }) {
  if (!signup.enabled || signup.domains.length === 0) {
    return (
      <p className="max-w-[44em] text-body text-grey">
        Self-signup is off. Every request waits here until someone approves or rejects it.
      </p>
    );
  }
  return (
    <p className="max-w-[44em] text-body text-grey">
      Self-signup is on for <span className="font-semibold text-ink">{signup.domains.join(", ")}</span>. Requests from
      these addresses get an account and an invitation automatically within a minute, up to {signup.max_per_hour} an
      hour (<Figures text={`${signup.sent_this_hour} sent this hour`} />). Other requests wait here until someone
      approves or rejects them.
    </p>
  );
}

