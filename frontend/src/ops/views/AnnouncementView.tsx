import { useMemo, useState } from "react";
import { useParams } from "react-router";

import { useAuth } from "../../auth";
import { formatDate } from "../../lib/dates";
import { formatCount } from "../../lib/format";
import { Button } from "../../ui/brand/Button";
import { cn } from "../../ui/brand/cn";
import { QUIET_CONTROL_CLASS } from "../../ui/brand/inlineActions";
import { OutlineSwitch } from "../../ui/brand/OutlineSwitch";
import { PageBackLink } from "../../ui/brand/PageHeader";
import { useAnnouncement, usePeople, useRetryAnnouncement, type AnnouncementDetail } from "../api";
import { facts } from "../format";
import { Dialog, EmptyRows, FailedLine, FormHeader, Loading, TABLE_CLASS, TABLE_WRAP_CLASS, TD_CLASS, TH_CLASS } from "../ui";
import { EmailPreview, KIND_WORDS, LIVE_MS, Marked, resultRank, resultWords } from "./announcementParts";

/** How often the page reads again while rows wait. */
const REFRESH_MS = 3000;

const byName = new Intl.Collator().compare;

type Filter = "all" | "sent" | "failed" | "left_out";
const FILTERS: ReadonlyArray<{ key: Filter; label: string }> = [
  { key: "all", label: "All" },
  { key: "sent", label: "Sent" },
  { key: "failed", label: "Failed" },
  { key: "left_out", label: "Left out" },
];

/** The result page (design annex § Result page): one announcement and each person's result. */
export function AnnouncementView() {
  const { announcementId = "" } = useParams();
  const auth = useAuth();
  const people = usePeople();
  const retry = useRetryAnnouncement();
  // The moment this page last started a retry: with the send's own time, the newest change.
  const [retriedAt, setRetriedAt] = useState(0);
  const [filter, setFilter] = useState<Filter>("all");
  const [showMessage, setShowMessage] = useState(false);

  const live = (data: AnnouncementDetail) => Date.now() - Math.max(Date.parse(data.created_at), retriedAt) < LIVE_MS;
  const detail = useAnnouncement(announcementId, (data) =>
    data !== undefined && live(data) && data.recipients.some((row) => row.status === "pending" || row.status === "sending")
      ? REFRESH_MS
      : false,
  );
  const recipients = detail.data?.recipients;
  const isLive = detail.data !== undefined && live(detail.data);
  const rows = useMemo(
    () =>
      (recipients ?? [])
        .filter((row) => filter === "all" || row.status === filter)
        .sort((a, b) => resultRank(a, isLive) - resultRank(b, isLive) || byName(a.name, b.name)),
    [recipients, filter, isLive],
  );

  if (detail.isPending) return <Loading />;
  const back = <PageBackLink to="/announcements">Announcements</PageBackLink>;
  if (detail.isError) {
    return (
      <>
        <FormHeader back={back} title="Announcement" />
        <FailedLine message="Could not load the announcement." onRetry={() => void detail.refetch()} />
      </>
    );
  }

  const data = detail.data;
  const { counts } = data;
  const waiting = counts.pending + (isLive ? counts.sending : 0);
  const notConfirmed = isLive ? 0 : counts.sending;
  // A send the server stopped in the middle leaves rows waiting; the retry route continues it.
  const stuck = !isLive && counts.pending > 0;
  const myName = people.data?.find((person) => person.user_id === auth.user?.sub)?.display_name;
  const sentBy = data.sent_by_name === null ? null : data.sent_by_name === myName ? "Sent by you" : `Sent by ${data.sent_by_name}`;
  // The counts are the server's; the page does not count people itself.
  const total = counts.pending + counts.sending + counts.sent + counts.failed + counts.left_out;
  const filterCounts: Record<Filter, number> = {
    all: total,
    sent: counts.sent,
    failed: counts.failed,
    left_out: counts.left_out,
  };
  const filters = FILTERS.map(({ key, label }) => ({ key, label: `${label} ${filterCounts[key]}` }));

  return (
    <>
      <FormHeader
        back={back}
        title={data.subject}
        line={facts(
          KIND_WORDS[data.kind],
          ...(sentBy === null ? [] : [sentBy]),
          `${formatDate(data.created_at, "long")}, ${formatDate(data.created_at, "time")}`,
          `To ${data.audience_summary}`,
        )}
      />

      <section
        aria-label="Result"
        className="mt-6 flex flex-wrap items-center justify-between gap-4 border border-line-2 bg-paper px-6 py-5 shadow-paper max-md:px-4"
      >
        <div className="min-w-0">
          <p className="flex flex-wrap gap-x-5 gap-y-1 text-body font-bold text-navy">
            <Marked colour="green">{`${formatCount(counts.sent)} sent`}</Marked>
            {counts.failed > 0 && <Marked colour="red">{`${formatCount(counts.failed)} failed`}</Marked>}
            {counts.left_out > 0 && <Marked colour="grey">{`${formatCount(counts.left_out)} left out`}</Marked>}
            {waiting > 0 && <Marked colour="yellow">{`${formatCount(waiting)} waiting`}</Marked>}
            {notConfirmed > 0 && <Marked colour="grey">{`${formatCount(notConfirmed)} not confirmed`}</Marked>}
          </p>
          <p className="mt-1 text-body text-grey">
            “Sent” means the mail service accepted the email. We do not track who opens it.
          </p>
          {data.suppression_unreadable && <p className="mt-1 text-body text-grey">We could not check for bounces just now.</p>}
        </div>
        {(stuck || (counts.failed > 0 && waiting === 0)) && (
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            {stuck && <p className="text-body text-grey">The send stopped before it reached everyone.</p>}
            <Button
              variant="outline"
              disabled={retry.isPending}
              onClick={() => retry.mutate(data.announcement_id, { onSuccess: () => setRetriedAt(Date.now()) })}
            >
              {stuck ? `Send to the ${formatCount(counts.pending)} still waiting` : `Try the ${formatCount(counts.failed)} failed again`}
            </Button>
          </div>
        )}
        {retry.isError && (
          <p role="alert" className="w-full text-body text-red">
            {stuck ? "The emails were not sent. Try again." : "The failed emails were not sent again. Try again."}
          </p>
        )}
      </section>

      <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
        <OutlineSwitch label="Show" choices={filters} value={filter} onChange={setFilter} />
        <button type="button" onClick={() => setShowMessage(true)} className={cn(QUIET_CONTROL_CLASS, "text-body")}>
          Show the message that was sent
        </button>
      </div>

      <div className={cn(TABLE_WRAP_CLASS, "mt-3")}>
        <table className={TABLE_CLASS} aria-label="Recipients">
          <thead>
            <tr>
              <th className={cn(TH_CLASS, "w-56 pl-4")}>Name</th>
              <th className={cn(TH_CLASS, "w-72")}>Email</th>
              <th className={cn(TH_CLASS, "w-44")}>Organisation</th>
              <th className={cn(TH_CLASS, "w-80")}>Result</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const { colour, words } = resultWords(row, isLive);
              return (
                <tr key={row.user_id} className="bg-paper">
                  <td className={cn(TD_CLASS, "truncate pl-4 font-semibold text-navy")} title={row.name}>
                    {row.name}
                  </td>
                  <td className={cn(TD_CLASS, "truncate")} title={row.email ?? undefined}>
                    {row.email ?? "—"}
                  </td>
                  <td className={cn(TD_CLASS, "truncate")} title={row.organisation ?? undefined}>
                    {row.organisation ?? "—"}
                  </td>
                  <td className={TD_CLASS}>
                    <Marked colour={colour}>{words}</Marked>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {rows.length === 0 && <EmptyRows label="No one here." />}
      </div>

      {showMessage && (
        <Dialog
          open
          onOpenChange={setShowMessage}
          title="The message that was sent"
          footer={
            <Button variant="ghost" onClick={() => setShowMessage(false)}>
              Close
            </Button>
          }
        >
          <EmailPreview
            kind={data.kind}
            subject={data.subject}
            body={data.body}
            buttonLabel={data.button_label}
            picture={data.image_alt === null ? null : { src: null, alt: data.image_alt }}
          />
        </Dialog>
      )}
    </>
  );
}
