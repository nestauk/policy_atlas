import { Link, useNavigate } from "react-router";

import { useAuth } from "../../auth";
import { formatDate } from "../../lib/dates";
import { Figures } from "../../lib/figures";
import { formatCount } from "../../lib/format";
import { cn } from "../../ui/brand/cn";
import { PageHeader, PagePrimary } from "../../ui/brand/PageHeader";
import { useAnnouncements, usePeople, type AnnouncementSummary } from "../api";
import { facts } from "../format";
import { EmptyRows, FailedLine, Loading, TABLE_CLASS, TABLE_WRAP_CLASS, TD_CLASS, TH_CLASS } from "../ui";
import { KIND_WORDS, Marked } from "./announcementParts";

/** How long a `sending` row may still finish before it reads as left in the middle. */
export const LIVE_MS = 2 * 60 * 1000;

/** The list's Result cell: "N sent", "N sent · M failed", or "Sending: N of M" while rows wait. */
function result({ counts, created_at }: AnnouncementSummary) {
  const waiting = counts.pending > 0 || (counts.sending > 0 && Date.now() - Date.parse(created_at) < LIVE_MS);
  if (waiting) {
    const gets = counts.pending + counts.sending + counts.sent + counts.failed;
    return <Marked colour="yellow">{`Sending: ${formatCount(counts.sent)} of ${formatCount(gets)}`}</Marked>;
  }
  if (counts.failed > 0) {
    return <Marked colour="red">{facts(`${formatCount(counts.sent)} sent`, `${formatCount(counts.failed)} failed`)}</Marked>;
  }
  return <Marked colour="green">{`${formatCount(counts.sent)} sent`}</Marked>;
}

/** When, to the minute: "24 Nov, 10:12" ("24 Nov 2025, 10:12" before this year). */
export const when = (iso: string) => `${formatDate(iso, "short")}, ${formatDate(iso, "time")}`;

/** Announcements (design annex § Announcements list): every email sent, newest first. */
export function AnnouncementsView() {
  const navigate = useNavigate();
  const auth = useAuth();
  const people = usePeople();
  const announcements = useAnnouncements();
  const myName = people.data?.find((person) => person.user_id === auth.user?.sub)?.display_name;

  if (announcements.isPending) return <Loading />;
  const rows = announcements.data?.items ?? [];

  return (
    <>
      <PageHeader
        title="Announcements"
        actions={<PagePrimary to="/announcements/new">New announcement</PagePrimary>}
        filters={
          <p className="max-w-[44em] text-body text-grey">
            Email people who have an account. Every email you send is recorded here.
          </p>
        }
      />
      <div className="mt-6">
        {announcements.isError ? (
          <FailedLine message="Could not load the announcements." onRetry={() => void announcements.refetch()} />
        ) : (
          <div className={TABLE_WRAP_CLASS}>
            <table className={TABLE_CLASS} aria-label="Announcements">
              <thead>
                <tr>
                  <th className={cn(TH_CLASS, "w-80 pl-4")}>Subject</th>
                  <th className={cn(TH_CLASS, "w-36")}>Kind</th>
                  <th className={cn(TH_CLASS, "w-56")}>Who</th>
                  <th className={cn(TH_CLASS, "w-32")}>Sent by</th>
                  <th className={cn(TH_CLASS, "w-36")}>When</th>
                  <th className={cn(TH_CLASS, "w-48")}>Result</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr
                    key={row.announcement_id}
                    onClick={() => navigate(`/announcements/${row.announcement_id}`)}
                    className="cursor-pointer bg-paper transition-colors duration-150 hover:bg-blue-tint-2"
                  >
                    <td className={cn(TD_CLASS, "pl-4")}>
                      <Link
                        to={`/announcements/${row.announcement_id}`}
                        onClick={(event) => event.stopPropagation()}
                        className="block truncate font-semibold text-navy hover:text-blue hover:underline"
                        title={row.subject}
                      >
                        {row.subject}
                      </Link>
                    </td>
                    <td className={TD_CLASS}>{KIND_WORDS[row.kind]}</td>
                    <td className={cn(TD_CLASS, "truncate")} title={row.audience_summary}>
                      {row.audience_summary}
                    </td>
                    <td className={cn(TD_CLASS, "truncate")}>
                      {row.sent_by_name === null ? "—" : row.sent_by_name === myName ? "You" : row.sent_by_name}
                    </td>
                    <td className={cn(TD_CLASS, "whitespace-nowrap")}>
                      <Figures text={when(row.created_at)} />
                    </td>
                    <td className={cn(TD_CLASS, "whitespace-nowrap")}>{result(row)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {rows.length === 0 && <EmptyRows label="No announcements yet." />}
          </div>
        )}
      </div>
    </>
  );
}
