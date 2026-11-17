import { useState } from "react";
import { Link } from "react-router";

import { Button } from "../../ui/brand/Button";
import { Chip } from "../../ui/brand/Chip";
import { Figures } from "../../lib/figures";
import { cn } from "../../ui/brand/cn";
import { LINK_CLASS } from "../../ui/brand/inlineActions";
import { PageHeader } from "../../ui/brand/PageHeader";
import { OpsApiError, unwrap, useOpsAction, useOrganisations, useRequests, type AccessRequest } from "../api";
import { ago, facts, orgInRefusal } from "../format";
import {
  Dialog,
  FailedLine,
  Field,
  Loading,
  OrganisationSelect,
  SearchField,
  TABLE_CLASS,
  TABLE_WRAP_CLASS,
  TD_CLASS,
  TH_CLASS,
  useRecordedToast,
} from "../ui";

/** A row turned to Check by a refused approval, before the list says so. */
type Refusal = { org: string; message: string };

/**
 * A request's status, the word beside its colour: green Invited, yellow
 * Waiting, orange Check. The chip set has no orange tone, so Check is the
 * default chip led by an orange 6 px status mark.
 */
function StatusChip({ request, refusal }: { request: AccessRequest; refusal: Refusal | undefined }) {
  if (refusal !== undefined || request.status === "check") {
    return (
      <Chip className="max-w-full">
        <span aria-hidden="true" className="size-1.5 shrink-0 bg-orange" />
        <span className="truncate">Check: already in {refusal?.org ?? request.note}</span>
      </Chip>
    );
  }
  if (request.status === "invited") {
    return <Chip tone="green">Invited {request.account_created_at != null ? ago(request.account_created_at) : ""}</Chip>;
  }
  return <Chip tone="yellow">Waiting</Chip>;
}

/** Access requests (ops-pages-copy.md § Requests). */
export function RequestsView() {
  const requests = useRequests();
  const organisations = useOrganisations();
  const toast = useRecordedToast();
  const [query, setQuery] = useState("");
  const [approving, setApproving] = useState<AccessRequest | null>(null);
  const [orgId, setOrgId] = useState("");
  const [refusals, setRefusals] = useState<Record<string, Refusal>>({});
  const [retry, setRetry] = useState<(() => void) | null>(null);
  const approve = useOpsAction((client, { entryId, org }: { entryId: string; org: string }) =>
    unwrap(
      client.POST("/api/v1/ops/requests/{entry_id}/approve", {
        params: { path: { entry_id: entryId } },
        body: { org_id: org },
      }),
    ),
  );

  const send = (request: AccessRequest, org: string) => {
    setRetry(null);
    approve.mutate(
      { entryId: request.entry_id, org },
      {
        onSuccess: () => {
          setApproving(null);
          toast(`${request.name} approved`);
        },
        onError: (error) => {
          setApproving(null);
          if (error instanceof OpsApiError && error.code === "enrolled_elsewhere") {
            setRefusals((current) => ({
              ...current,
              [request.entry_id]: { org: orgInRefusal(error.message) ?? "another organisation", message: error.message },
            }));
          } else {
            setRetry(() => () => send(request, org));
          }
        },
      },
    );
  };

  if (requests.isPending) return <Loading />;
  const signup = requests.data?.self_signup;
  const q = query.trim().toLowerCase();
  const rows = (requests.data?.items ?? []).filter(
    (item) => q === "" || item.name.toLowerCase().includes(q) || item.email.toLowerCase().includes(q),
  );

  return (
    <>
      <PageHeader
        title="Access requests"
        actions={null}
        filters={<SearchField placeholder="Find by name or email" value={query} onChange={setQuery} />}
      />
      {signup !== undefined && (
        <p className="mt-6 text-body text-ink">
          {signup.enabled
            ? facts(
                `Self-signup on for ${signup.domains.join(", ")}`,
                `${signup.sent_this_hour} of ${signup.max_per_hour} invitations sent this hour`,
              )
            : "Self-signup off"}
        </p>
      )}
      <div className="mt-4">
        {requests.isError ? (
          <FailedLine onRetry={() => void requests.refetch()} />
        ) : (
          <div className={TABLE_WRAP_CLASS}>
            <table className={TABLE_CLASS}>
              <thead>
                <tr>
                  <th className={cn(TH_CLASS, "pl-4")}>Name</th>
                  <th className={TH_CLASS}>Email</th>
                  <th className={TH_CLASS}>Requested</th>
                  <th className={TH_CLASS}>Status</th>
                  <th className={TH_CLASS}>
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((request) => {
                  const refusal = refusals[request.entry_id];
                  const check = refusal !== undefined || request.status === "check";
                  return (
                    <tr key={request.entry_id}>
                      <td className={cn(TD_CLASS, "pl-4")}>
                        <span className="font-semibold text-navy">{request.name}</span>
                        {refusal !== undefined && <span className="block text-meta text-grey">{refusal.message}</span>}
                      </td>
                      <td className={TD_CLASS}>{request.email}</td>
                      <td className={cn(TD_CLASS, "whitespace-nowrap")}>
                        <Figures text={ago(request.created_at)} />
                      </td>
                      <td className={cn(TD_CLASS, "py-2.5")}>
                        <StatusChip request={request} refusal={refusal} />
                      </td>
                      <td className={cn(TD_CLASS, "whitespace-nowrap py-2 pr-4 text-right")}>
                        {check ? (
                          <Link
                            to={`/people?q=${encodeURIComponent(request.email)}`}
                            className={cn(LINK_CLASS, "inline-flex h-8 items-center text-meta")}
                          >
                            Open person
                          </Link>
                        ) : request.status === "waiting" ? (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              setOrgId("");
                              setApproving(request);
                            }}
                          >
                            Approve into…
                          </Button>
                        ) : null}
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

      {approving !== null && (
        <Dialog
          open
          onOpenChange={(open) => !open && setApproving(null)}
          title={`Approve ${approving.name}`}
          footer={
            <>
              <Button variant="ghost" onClick={() => setApproving(null)}>
                Cancel
              </Button>
              <Button disabled={orgId === "" || approve.isPending} onClick={() => send(approving, orgId)}>
                Approve
              </Button>
            </>
          }
        >
          <Field
            id="approve-org"
            label="Organisation"
            help="Cognito emails them a temporary password. If the address already has an account, it is enrolled without an email."
          >
            <OrganisationSelect
              id="approve-org"
              label="Organisation"
              organisations={organisations.data ?? []}
              value={orgId}
              onChange={setOrgId}
            />
          </Field>
        </Dialog>
      )}
    </>
  );
}
