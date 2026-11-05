import { Link } from "react-router";

import type { components } from "../api/gen/types";
import { capabilityLabel } from "../lib/capabilities";
import { Figures } from "../lib/figures";
import { useNow } from "../lib/freshness";
import { scrub } from "../lib/scrub";
import { StatusMark } from "../ui/brand/Card";
import { Chip } from "../ui/brand/Chip";
import { taskStatus } from "./landingPresentation";
import {
  rowFigureCellClass,
  rowNameCellClass,
  taskListRowGridClass,
  taskListRowGridClassWithOwner,
} from "./listPageChrome";
import { elapsedSeconds, formatMinutes } from "./workspace/runProgress";

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
   *  prefix's hover text (lead ruling P2). */
  projectNames?: readonly string[] | null;
  showProjectPrefix?: boolean;
  sourceCount?: number | null;
  updatedAt?: string | null;
  latestRun?: LatestRun;
  /** The walk running now (`TaskOut.active_run`): while it runs, the row
   *  reads its stage and elapsed time (task 058, N15). */
  activeRun?: LatestRun;
  /** Task 033 phase 10b: render the owner column, and the string to show
   *  when `owner_display` is null (`"—"`, or the admin-wide-list's "No
   *  organisation" — the caller decides which, this row just renders it). */
  ownerDisplay?: string | null;
  ownerlessLabel?: string;
};

/** One task row: name (optional project prefix), capability, aligned status, [owner], sources, date. */
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
  ownerDisplay,
  ownerlessLabel = "—",
}: TaskListRowProps) {
  const status = taskStatus(latestRun);
  const running = activeRun?.status === "running" && Boolean(activeRun.stage_label);
  const nowMs = useNow(running);
  const statusLabel = running
    ? `${activeRun?.stage_label} · ${formatMinutes(elapsedSeconds(activeRun?.started_at, undefined, nowMs))}`
    : status.label;
  const safeName = scrub(name);
  const safeProjects = (projectNames ?? []).map(scrub).filter((project) => project !== "");
  const safeProject = safeProjects.length > 0 ? safeProjects.join(" · ") : null;
  const moreProjects = safeProjects.length - 1;
  const ariaLabel =
    showProjectPrefix && safeProject != null ? `${safeProject}, ${safeName}` : safeName;
  const showOwner = ownerDisplay !== undefined;

  return (
    <Link
      to={to}
      aria-label={ariaLabel}
      className={showOwner ? taskListRowGridClassWithOwner : taskListRowGridClass}
    >
      {/* The name cell: below md the whole first line. The project prefix
          and the name each truncate, the prefix at most 45% of the cell, so
          the task's own name always shows (the reader scans for it). */}
      <span className={`${rowNameCellClass} flex items-baseline max-md:col-span-3`}>
        {showProjectPrefix && safeProject != null && (
          <span className="flex min-w-0 max-w-[45%] shrink items-baseline" title={safeProject}>
            <span className="truncate font-normal text-grey">{safeProjects[0]}</span>
            {moreProjects > 0 && (
              <span className="ml-1 shrink-0 font-normal tabular-nums text-grey">+{moreProjects}</span>
            )}
            <span aria-hidden="true" className="mx-1.5 shrink-0 font-normal text-line-2">
              /
            </span>
          </span>
        )}
        <span className="min-w-0 flex-1 truncate font-semibold text-navy">{safeName}</span>
      </span>
      <Chip tone="blue" className="shrink-0 justify-self-start">
        {capabilityLabel(capabilityKey)}
      </Chip>
      <span className="inline-flex min-w-0 items-center gap-1.5 text-meta leading-7 text-grey">
        {/* Every row's mark is the 6 px square, so a running row's is the
            same size as a finished one's (owner, round 8): blue and
            breathing while the run is live. */}
        {running || status.dot === "running" ? <StatusMark tone="running" breathing /> : <StatusMark tone={status.dot} />}
        <span className="truncate" title={statusLabel}>
          <Figures text={scrub(statusLabel)} />
        </span>
      </span>
      {showOwner && (
        <span className={`${rowFigureCellClass} text-meta max-md:hidden`}>
          {ownerDisplay !== null ? scrub(ownerDisplay) : ownerlessLabel}
        </span>
      )}
      <span className={`${rowFigureCellClass} text-meta max-md:hidden`}>
        {/* null and 0 differ: null means no run has asked yet. */}
        {sourceCount != null ? (
          <Figures text={sourceCount === 1 ? "1 source" : `${sourceCount} sources`} />
        ) : (
          ""
        )}
      </span>
      {updatedAt != null ? (
        <time dateTime={updatedAt} className={`${rowFigureCellClass} text-caption tabular-nums`}>
          {new Date(updatedAt).toLocaleDateString()}
        </time>
      ) : (
        <span aria-hidden="true" />
      )}
    </Link>
  );
}
