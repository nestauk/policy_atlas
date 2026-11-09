import { Link } from "react-router";

import type { components } from "../api/gen/types";
import { capabilityLabel } from "../lib/capabilities";
import { formatDate } from "../lib/dates";
import { Figures } from "../lib/figures";
import { useNow } from "../lib/freshness";
import { scrub } from "../lib/scrub";
import { StatusMark } from "../ui/brand/Card";
import { isStale, taskStatusTone, taskStatusWord } from "../ui/brand/taskStatus";
import {
  rowAccessibleName,
  rowFigureCellClass,
  rowNameCellClass,
  rowOwnerCellClass,
  rowStatusCellClass,
  taskListRowGridClass,
} from "./listPageChrome";
import { elapsedSeconds, formatElapsed } from "./workspace/runProgress";
import { formatCount } from "../lib/format";

type LatestRun = components["schemas"]["TaskOut"]["latest_run"];

type TaskListRowProps = {
  to: string;
  name: string;
  /** The row's `TaskOut.capability` (task 044). Left undefined only by a
   *  caller with no task row to hand; `capabilityLabel` falls back. No depth
   *  is shown beside it (owner ruling, C17). */
  capabilityKey?: string | null;
  /** The projects the task belongs to, in order. The row shows the first
   *  and a count of the rest ("Child health +1"); the full list is the
   *  prefix's hover text (lead ruling P2) and is in the accessible name. */
  projectNames?: readonly string[] | null;
  showProjectPrefix?: boolean;
  sourceCount?: number | null;
  updatedAt?: string | null;
  latestRun?: LatestRun;
  /** The walk running now (`TaskOut.active_run`): while it runs, the row
   *  reads its stage and elapsed time (task 058, N15). */
  activeRun?: LatestRun;
  /** `TaskOut.is_owner`: whose task it is, for the paused word ("waiting on
   *  you" or on the owner) and the owner column's "You". A caller with no
   *  organisation owns every row it can see, so undefined reads as true. */
  isOwner?: boolean;
  /** `TaskOut.owner_display`: the owner's name, or null for an ownerless row. */
  ownerName?: string | null;
  /** Task 033 phase 10b: render the owner column (off on Mine, round 10). */
  showOwner?: boolean;
  /** What the owner column shows for an ownerless row (`"—"`, or the
   *  admin-wide-list's "No organisation" — the caller decides). */
  ownerlessLabel?: string;
  /** `TaskOut.status === "archived"`: the status word is "Archived". */
  archived?: boolean;
};

/** One task row: name (optional project prefix), capability, aligned status, [owner], sources, date.
 *  From md up it is a subgrid of the list's grid (`taskListGridClass`), so
 *  it must sit in `TaskListPanel`'s list. */
export function TaskListRow({
  to,
  name,
  capabilityKey,
  projectNames,
  showProjectPrefix = false,
  sourceCount,
  updatedAt,
  latestRun,
  activeRun,
  isOwner = true,
  ownerName = null,
  showOwner = false,
  ownerlessLabel = "—",
  archived = false,
}: TaskListRowProps) {
  const safeOwner = ownerName != null ? scrub(ownerName) : null;
  // The words come from the one status vocabulary (round 10: who a paused
  // task waits on, one separator, "Archived").
  const statusWord = taskStatusWord(latestRun?.status, {
    isOwner,
    ownerName: safeOwner,
    archived,
    stale: isStale(latestRun),
  });
  const statusTone = taskStatusTone(latestRun?.status, archived);
  const running = !archived && activeRun?.status === "running" && Boolean(activeRun.stage_label);
  const nowMs = useNow(running);
  // A running row's step and its timer (round 14: a long step truncates,
  // the timer always shows).
  const liveStep = running ? scrub(activeRun?.stage_label ?? "") : null;
  const liveTimer = running ? formatElapsed(elapsedSeconds(activeRun?.started_at, undefined, nowMs), { withSeconds: false }) : null;
  const statusLabel = liveStep !== null ? `${liveStep} · ${liveTimer}` : scrub(statusWord);
  const safeName = scrub(name);
  const safeProjects = showProjectPrefix
    ? (projectNames ?? []).map(scrub).filter((project) => project !== "")
    : [];
  const firstProject = safeProjects[0];
  const moreProjects = safeProjects.length - 1;
  const ownerCell = isOwner ? "You" : (safeOwner ?? ownerlessLabel);
  const date = updatedAt != null ? formatDate(updatedAt, "short") : "";

  // The accessible name is the row's content in order (lead ruling 1, round
  // 10): the title, the status word with its live step, the project, the
  // owner where the column shows, the date. The capability and the source
  // count are not in the ruling's name; the owner's bare dash says nothing.
  const accessibleName = rowAccessibleName([
    safeName,
    statusLabel,
    safeProjects.length > 0 ? new Intl.ListFormat("en-GB").format(safeProjects) : null,
    showOwner && ownerCell !== "—" ? ownerCell : null,
    date,
  ]);

  // The first project and its count, Grey: before the name from md up, after
  // the status word on a phone's second line.
  const projectText =
    firstProject !== undefined ? (
      <>
        <span className="truncate">{firstProject}</span>
        {moreProjects > 0 && <span className="ml-1 shrink-0 tabular-nums">+{moreProjects}</span>}
      </>
    ) : null;

  return (
    <Link
      to={to}
      aria-label={accessibleName}
      className={taskListRowGridClass}
    >
      {/* The name cell: below md the whole first line, the name alone. From
          md up the project prefix and the name each truncate, the prefix at
          most 45% of the cell, so the task's own name always shows. */}
      <span className={`${rowNameCellClass} flex items-baseline max-md:col-span-2`}>
        {projectText !== null && (
          <span
            className="flex min-w-0 max-w-[45%] shrink items-baseline font-normal text-grey max-md:hidden"
            title={safeProjects.join(" · ")}
          >
            {projectText}
            <span aria-hidden="true" className="mx-1.5 shrink-0 text-line-2">
              /
            </span>
          </span>
        )}
        <span className="min-w-0 flex-1 truncate font-semibold text-navy">{safeName}</span>
      </span>
      {/* The kind of work in plain Grey, one column as wide as the widest
          kind listed, so the status words line up below each other (round
          10: not a chip). */}
      <span className="truncate text-meta leading-7 text-grey max-md:hidden">
        {capabilityLabel(capabilityKey)}
      </span>
      {/* The status column is as wide as the widest word listed, at most
          the old 11.5rem, and stands 24 px from the owner (round 12). */}
      <span className={`flex min-w-0 items-center gap-1.5 text-meta leading-7 text-grey ${rowStatusCellClass}`}>
        {/* Every row's mark is the 6 px square, so a running row's is the
            same size as a finished one's (owner, round 8): blue and
            breathing while the run is live. */}
        {running || statusTone === "running" ? (
          <StatusMark tone="running" breathing />
        ) : (
          <StatusMark tone={statusTone} />
        )}
        {/* The status word keeps its room; the phone's project after it is
            what gives way (the word never shrinks on a phone: a shrink
            weight, however small, cuts it by a subpixel into an ellipsis). */}
        {liveStep !== null ? (
          // Round 14 (owner): the step gives way, the timer never does; the
          // pair holds its place on a phone as the word does.
          <span className="flex min-w-0 items-baseline max-md:max-w-[calc(100%-12px)] max-md:shrink-0" title={statusLabel}>
            <span className="min-w-0 truncate">{liveStep}</span>
            <span className="shrink-0 whitespace-pre">
              <Figures text={` · ${liveTimer}`} />
            </span>
          </span>
        ) : (
          <span className="min-w-0 truncate max-md:max-w-[calc(100%-12px)] max-md:shrink-0" title={statusLabel}>
            <Figures text={statusLabel} />
          </span>
        )}
        {projectText !== null && (
          <span className="flex min-w-0 shrink-[1000] items-baseline md:hidden">
            <span aria-hidden="true" className="mx-1.5 shrink-0">
              ·
            </span>
            {projectText}
          </span>
        )}
      </span>
      {showOwner && (
        <span
          className={`${rowOwnerCellClass} max-md:hidden`}
          title={safeOwner !== null && !isOwner ? safeOwner : undefined}
        >
          {ownerCell}
        </span>
      )}
      <span className={`${rowFigureCellClass} max-md:hidden`}>
        {/* null and 0 differ: null means no run has asked yet. A failed
            run's count says nothing about the evidence, so it reads as the
            dash (lead ruling, round 10), archived or not (round 11). */}
        {latestRun?.status === "failed" ? (
          "—"
        ) : sourceCount != null ? (
          <Figures text={sourceCount === 1 ? "1 source" : `${formatCount(sourceCount)} sources`} />
        ) : (
          ""
        )}
      </span>
      {updatedAt != null ? (
        <time dateTime={updatedAt} className={rowFigureCellClass}>
          <Figures text={date} />
        </time>
      ) : (
        <span aria-hidden="true" />
      )}
    </Link>
  );
}
