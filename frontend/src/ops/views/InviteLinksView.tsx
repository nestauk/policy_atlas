import { useEffect, useState, type FormEvent, type ReactNode } from "react";

import { formatDate } from "../../lib/dates";
import { Figures } from "../../lib/figures";
import { formatCount } from "../../lib/format";
import { Button } from "../../ui/brand/Button";
import { Chip } from "../../ui/brand/Chip";
import { cn } from "../../ui/brand/cn";
import { PageHeader, PagePrimary } from "../../ui/brand/PageHeader";
import { OpsApiError, unwrap, useInviteLinks, useOpsAction, useOrganisations, type InviteLink } from "../api";
import { sentence } from "../format";
import {
  ACTIONS_TD_CLASS,
  ACTIONS_TH_CLASS,
  CHOOSE_ORGANISATION,
  CohortsField,
  DANGER_CLASS,
  Dialog,
  EmptyRows,
  FailedLine,
  Field,
  FIGURE_CLASS,
  INPUT_CLASS,
  Loading,
  OrganisationSelect,
  RowMenu,
  TABLE_CLASS,
  TABLE_WRAP_CLASS,
  TD_CLASS,
  TH_CLASS,
  useRecordedToast,
} from "../ui";

const STATE_CHIP: Record<InviteLink["state"], { tone: "green" | "yellow" | "soft" | "red"; word: string }> = {
  active: { tone: "green", word: "ACTIVE" },
  full: { tone: "yellow", word: "FULL" },
  expired: { tone: "soft", word: "EXPIRED" },
  revoked: { tone: "red", word: "REVOKED" },
};

/** A local day, "2027-02-14", as a date field holds it. */
function localDay(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** The end of a local day with the operator's own zone, in RFC 3339: "2027-02-14T23:59:59+00:00". */
function endOfDay(day: string): string {
  const offset = -new Date(`${day}T23:59:59`).getTimezoneOffset();
  const pad = (n: number) => String(Math.floor(Math.abs(n))).padStart(2, "0");
  return `${day}T23:59:59${offset < 0 ? "-" : "+"}${pad(offset / 60)}:${pad(offset % 60)}`;
}

/** The page's primary and each row's menu button: where focus goes back to when a dialog closes. */
const CREATE_LINK_ID = "create-link";
const linkMenuId = (linkId: string) => `link-menu-${linkId}`;
const createButton = () => document.getElementById(CREATE_LINK_ID);
const COPY_LINK_ID = "copy-new-link";

/** The id of a dialog's refusal line, for the field it is about. */
const REFUSAL_ID = "link-refusal";

/** Whether a refusal is about the email domains: each of those words names them. */
const isDomainRefusal = (message: string | null) => message !== null && /domain/i.test(message);

/** "14 Feb 2027", always with its year. */
const expires = (iso: string) => formatDate(iso, "short", { now: new Date(0) });

/** The words of a refused or failed save. */
function failure(error: unknown): string {
  return error instanceof OpsApiError && error.status === 409 && error.message !== ""
    ? sentence(error.message)
    : "Could not save the link. Try again.";
}

/** Copy a link's address; the toast never carries the code. */
function useCopyLink() {
  const toast = useRecordedToast();
  return (link: InviteLink) =>
    navigator.clipboard.writeText(link.url).then(
      () => toast("Link copied"),
      () => toast("Could not copy the link."),
    );
}

/** Invite links: list, create, copy, edit and revoke. */
export function InviteLinksView() {
  const links = useInviteLinks();
  const copy = useCopyLink();
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<InviteLink | null>(null);
  const [revoking, setRevoking] = useState<InviteLink | null>(null);

  if (links.isPending) return <Loading />;
  const rows = links.data ?? [];

  return (
    <>
      <PageHeader
        title="Invite links"
        actions={
          <PagePrimary id={CREATE_LINK_ID} onClick={() => setCreating(true)}>
            Create link
          </PagePrimary>
        }
        filters={
          <p className="max-w-[44em] text-body text-grey">
            An invite link lets people from the email domains you choose request access and get an account without
            approval, until the link is full, expires or is revoked.
          </p>
        }
      />
      <div className="mt-6">
        {links.isError ? (
          <FailedLine message="Could not load the invite links." onRetry={() => void links.refetch()} />
        ) : (
          <div className={TABLE_WRAP_CLASS}>
            <table className={TABLE_CLASS} aria-label="Invite links">
              <thead>
                <tr>
                  <th className={cn(TH_CLASS, "w-48 pl-4")}>Label</th>
                  <th className={cn(TH_CLASS, "w-36")}>Organisation</th>
                  <th className={cn(TH_CLASS, "w-44")}>Cohorts</th>
                  <th className={cn(TH_CLASS, "w-48")}>Email domains</th>
                  <th className={cn(TH_CLASS, "w-28 text-right")}>Used</th>
                  <th className={cn(TH_CLASS, "w-32")}>Expires</th>
                  <th className={cn(TH_CLASS, "w-28")}>Status</th>
                  <th className={cn(TH_CLASS, ACTIONS_TH_CLASS)}>
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((link) => (
                  <tr key={link.invite_link_id} className="bg-paper">
                    <td className={cn(TD_CLASS, "truncate pl-4 font-semibold text-navy")} title={link.label}>
                      {link.label}
                    </td>
                    <td className={cn(TD_CLASS, "truncate")} title={link.organisation.name}>
                      {link.organisation.name}
                    </td>
                    <td className={TD_CLASS}>
                      {link.cohorts.length === 0 ? (
                        <span className="text-grey">None</span>
                      ) : (
                        link.cohorts.map((cohort) => (
                          <span key={cohort.cohort_id} className="block truncate">
                            {cohort.name}
                          </span>
                        ))
                      )}
                    </td>
                    <td className={TD_CLASS}>
                      {link.allowed_domains.map((domain) => (
                        <span key={domain} className="block truncate">
                          {domain}
                        </span>
                      ))}
                    </td>
                    <td className={cn(TD_CLASS, FIGURE_CLASS)}>
                      <Figures text={`${formatCount(link.uses)} of ${formatCount(link.max_uses)}`} />
                    </td>
                    <td className={cn(TD_CLASS, "whitespace-nowrap")}>
                      <Figures text={expires(link.expires_at)} />
                    </td>
                    <td className={cn(TD_CLASS, "py-2.5")}>
                      <Chip tone={STATE_CHIP[link.state].tone}>{STATE_CHIP[link.state].word}</Chip>
                    </td>
                    <td className={cn(TD_CLASS, ACTIONS_TD_CLASS, "py-2 pr-2")}>
                      <RowMenu
                        id={linkMenuId(link.invite_link_id)}
                        label={`Actions for ${link.label}`}
                        items={[
                          { label: "Copy link", onSelect: () => void copy(link) },
                          ...(link.state === "revoked"
                            ? []
                            : [
                                { label: "Edit…", onSelect: () => setEditing(link) },
                                { label: "Revoke…", onSelect: () => setRevoking(link) },
                              ]),
                        ]}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {rows.length === 0 && <EmptyRows label="No invite links yet." />}
          </div>
        )}
      </div>

      {creating && <CreateDialog onClose={() => setCreating(false)} />}
      {editing !== null && <EditDialog link={editing} onClose={() => setEditing(null)} />}
      {revoking !== null && <RevokeDialog link={revoking} onClose={() => setRevoking(null)} />}
    </>
  );
}

/** The fields a link keeps for life, shown in the created and edit dialogs. */
function Fixed({ link, extra }: { link: InviteLink; extra?: Array<[string, string]> }) {
  const pairs: Array<[string, string]> = [
    ["Organisation", link.organisation.name],
    ["Cohorts", link.cohorts.length === 0 ? "None" : link.cohorts.map((cohort) => cohort.name).join(", ")],
    ["Email domains", link.allowed_domains.join(", ")],
    ...(extra ?? []),
  ];
  return (
    <dl className="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-6 gap-y-2 text-body">
      {pairs.map(([term, value]) => (
        <div key={term} className="contents">
          <dt className="font-semibold text-navy">{term}</dt>
          <dd className="break-words">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Label, maximum uses and the last day: the fields both dialogs share; `between` goes after the label. */
function LimitFields({
  label,
  setLabel,
  maxUses,
  setMaxUses,
  day,
  setDay,
  between,
}: {
  label: string;
  setLabel: (value: string) => void;
  maxUses: string;
  setMaxUses: (value: string) => void;
  day: string;
  setDay: (value: string) => void;
  between?: ReactNode;
}) {
  return (
    <>
      <Field id="link-label" label="Label" help="Only operators see this name.">
        {(describedBy) => (
          <input
            id="link-label"
            required
            autoComplete="off"
            aria-describedby={describedBy}
            value={label}
            onChange={(event) => setLabel(event.target.value)}
            className={INPUT_CLASS}
          />
        )}
      </Field>
      {between}
      <div className="grid gap-5 sm:grid-cols-2">
        <Field id="link-max" label="Maximum uses" help="From 1 to 1,000.">
          {(describedBy) => (
            <input
              id="link-max"
              type="number"
              inputMode="numeric"
              required
              aria-describedby={describedBy}
              value={maxUses}
              onChange={(event) => setMaxUses(event.target.value)}
              className={cn(INPUT_CLASS, "tabular-nums")}
            />
          )}
        </Field>
        <Field id="link-expires" label="Expires on" help="The link works to the end of that day. At most 90 days from today.">
          {(describedBy) => (
            <input
              id="link-expires"
              type="date"
              required
              aria-describedby={describedBy}
              value={day}
              onChange={(event) => setDay(event.target.value)}
              className={cn(INPUT_CLASS, "tabular-nums")}
            />
          )}
        </Field>
      </div>
    </>
  );
}

/** A refused or failed save: full width in the dialog's footer, over its buttons, so it is never scrolled out of sight. */
function ErrorLine({ message }: { message: string | null }) {
  return message === null ? null : (
    <p id={REFUSAL_ID} role="alert" className="w-full text-body text-red">
      {message}
    </p>
  );
}

/** Create a link; once made, the dialog shows its address to copy. */
function CreateDialog({ onClose }: { onClose: () => void }) {
  const organisations = useOrganisations();
  const copy = useCopyLink();
  const [label, setLabel] = useState("");
  const [orgId, setOrgId] = useState("");
  const [orgMissing, setOrgMissing] = useState(false);
  const [cohortIds, setCohortIds] = useState<string[]>([]);
  const [domains, setDomains] = useState("");
  const [maxUses, setMaxUses] = useState("");
  const [day, setDay] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [made, setMade] = useState<InviteLink | null>(null);
  const create = useOpsAction((client, body: Parameters<typeof createBody>[0]) =>
    unwrap(client.POST("/api/v1/ops/invite-links", { body: createBody(body) })),
  );
  const domainRefused = isDomainRefusal(error);
  // Once made, focus starts on Copy link. An effect, not `autoFocus`: the
  // dialog takes focus back to itself when the submit button it held goes.
  useEffect(() => {
    if (made !== null) document.getElementById(COPY_LINK_ID)?.focus();
  }, [made]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (orgId === "") {
      setOrgMissing(true);
      document.getElementById("link-org")?.focus();
      return;
    }
    setError(null);
    create.mutate(
      { label, orgId, cohortIds, domains, maxUses, day },
      {
        onSuccess: setMade,
        onError: (failed) => {
          const message = failure(failed);
          setError(message);
          if (isDomainRefusal(message)) document.getElementById("link-domains")?.focus();
        },
      },
    );
  };

  // One dialog for both steps, so focus is not lost between them.
  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={made === null ? "Create invite link" : "Invite link created"}
      returnFocus={createButton}
      footer={
        made === null ? (
          <>
            <ErrorLine message={error} />
            <Button variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" form="link-form" disabled={create.isPending}>
              Create link
            </Button>
          </>
        ) : (
          <>
            <Button variant="ghost" onClick={onClose}>
              Done
            </Button>
            <Button id={COPY_LINK_ID} onClick={() => void copy(made)}>
              Copy link
            </Button>
          </>
        )
      }
    >
      {made !== null ? (
        <div className="flex flex-col gap-4">
          <LinkAddress url={made.url} />
          <Fixed
            link={made}
            extra={[
              ["Maximum uses", formatCount(made.max_uses)],
              ["Expires", `${expires(made.expires_at)}, end of day`],
            ]}
          />
          <p className="text-body text-ink">
            Anyone with this link and an address at one of these domains can get an account. Share it only with the
            group.
          </p>
          <p className="text-body text-grey">You can copy the link again later from the list.</p>
        </div>
      ) : (
        <form id="link-form" onSubmit={submit} className="flex flex-col gap-5">
          <LimitFields
            {...{ label, setLabel, maxUses, setMaxUses, day, setDay }}
            between={
              <>
                <Field id="link-org" label="Organisation" error={orgMissing && orgId === "" ? CHOOSE_ORGANISATION : null}>
                  {(describedBy) => (
                    <OrganisationSelect
                      id="link-org"
                      label="Organisation"
                      organisations={organisations.data ?? []}
                      value={orgId}
                      onChange={setOrgId}
                      describedBy={describedBy}
                      invalid={orgMissing && orgId === ""}
                    />
                  )}
                </Field>
                <CohortsField id="link-cohorts" values={cohortIds} onChange={setCohortIds} />
                <Field
                  id="link-domains"
                  label="Email domains"
                  help="Only addresses at these domains can use the link. One domain on each line, for example dhsc.gov.uk. At most 10."
                >
                  {(describedBy) => (
                    <textarea
                      id="link-domains"
                      rows={3}
                      required
                      spellCheck={false}
                      aria-invalid={domainRefused || undefined}
                      aria-describedby={domainRefused ? `${describedBy} ${REFUSAL_ID}` : describedBy}
                      value={domains}
                      onChange={(event) => setDomains(event.target.value)}
                      className={cn(INPUT_CLASS, "h-auto py-2")}
                    />
                  )}
                </Field>
              </>
            }
          />
        </form>
      )}
    </Dialog>
  );
}

/** A link's address, which may break before its code but never inside it. */
function LinkAddress({ url }: { url: string }) {
  const at = url.indexOf("#invite=") + "#invite=".length;
  return (
    <p className="border border-line bg-ground px-3 py-2.5 text-body font-semibold text-navy">
      <span className="break-all">{url.slice(0, at)}</span>
      <wbr />
      <span className="whitespace-nowrap">{url.slice(at)}</span>
    </p>
  );
}

/** The create route's body from the form's words. */
function createBody(form: { label: string; orgId: string; cohortIds: string[]; domains: string; maxUses: string; day: string }) {
  return {
    label: form.label.trim(),
    org_id: form.orgId,
    cohort_ids: form.cohortIds,
    // Only the blank lines at the ends go, so "Line n" in a refusal is the box's line n.
    allowed_domains: form.domains.trim() === "" ? [] : form.domains.trim().split("\n").map((line) => line.trim()),
    max_uses: Number(form.maxUses),
    expires_at: endOfDay(form.day),
  };
}

/** Change a link's label, maximum uses or last day. */
function EditDialog({ link, onClose }: { link: InviteLink; onClose: () => void }) {
  const toast = useRecordedToast();
  const [label, setLabel] = useState(link.label);
  const [maxUses, setMaxUses] = useState(String(link.max_uses));
  const shownDay = localDay(new Date(link.expires_at));
  const [day, setDay] = useState(shownDay);
  const [error, setError] = useState<string | null>(null);
  const save = useOpsAction((client, body: { label?: string; max_uses?: number; expires_at?: string }) =>
    unwrap(
      client.POST("/api/v1/ops/invite-links/{invite_link_id}", {
        params: { path: { invite_link_id: link.invite_link_id } },
        body,
      }),
    ),
  );

  const submit = (event: FormEvent) => {
    event.preventDefault();
    // Only what the operator changed: a value left out stays as stored, so a
    // colleague in another time zone does not move the end by saving a label.
    const body = {
      ...(label.trim() !== link.label && { label: label.trim() }),
      ...(Number(maxUses) !== link.max_uses && { max_uses: Number(maxUses) }),
      ...(day !== shownDay && { expires_at: endOfDay(day) }),
    };
    if (Object.keys(body).length === 0) {
      onClose();
      return;
    }
    setError(null);
    save.mutate(
      body,
      {
        onSuccess: (saved) => {
          toast(`Saved ${saved.label}`);
          onClose();
        },
        onError: (failed) => setError(failure(failed)),
      },
    );
  };

  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={`Edit ${link.label}`}
      clampTitle
      returnFocus={() => document.getElementById(linkMenuId(link.invite_link_id))}
      footer={
        <>
          <ErrorLine message={error} />
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="link-edit-form" disabled={save.isPending}>
            Save
          </Button>
        </>
      }
    >
      <form id="link-edit-form" onSubmit={submit} className="flex flex-col gap-5">
        <LimitFields {...{ label, setLabel, maxUses, setMaxUses, day, setDay }} />
        <div className="flex flex-col gap-2 border-t border-line pt-4">
          <Fixed link={link} />
          <p className="text-body text-grey">To change these, revoke this link and create a new one.</p>
        </div>
      </form>
    </Dialog>
  );
}

/** Revoke a link: the accounts it made stay. */
function RevokeDialog({ link, onClose }: { link: InviteLink; onClose: () => void }) {
  const toast = useRecordedToast();
  const [error, setError] = useState<string | null>(null);
  const revoke = useOpsAction((client, id: string) =>
    unwrap(client.POST("/api/v1/ops/invite-links/{invite_link_id}/revoke", { params: { path: { invite_link_id: id } } })),
  );
  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={`Revoke ${link.label}?`}
      returnFocus={() => document.getElementById(linkMenuId(link.invite_link_id))}
      description={
        "People who use the link after this get no account through it." +
        (link.uses === 1
          ? " The 1 account already made stays."
          : link.uses > 1
            ? ` The ${formatCount(link.uses)} accounts already made stay.`
            : "")
      }
      footer={
        <>
          <ErrorLine message={error} />
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            className={DANGER_CLASS}
            disabled={revoke.isPending}
            onClick={() =>
              revoke.mutate(link.invite_link_id, {
                onSuccess: () => {
                  toast(`Revoked ${link.label}`);
                  onClose();
                },
                onError: (failed) => setError(failure(failed)),
              })
            }
          >
            Revoke link
          </Button>
        </>
      }
    />
  );
}
