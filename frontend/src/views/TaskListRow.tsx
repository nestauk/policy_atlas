import { Link } from "react-router";

import type { components } from "../api/gen/types";
import { capabilityLabel } from "../lib/capabilities";
import { Figures } from "../lib/figures";
import { useFreshness, useNow } from "../lib/freshness";
import { scrub } from "../lib/scrub";
import { StatusDot } from "../ui/brand/Card";
import { Chip } from "../ui/brand/Chip";
import { taskStatus } from "./landingPresentation";
import { taskListRowGridClass, taskListRowGridClassWithOwner } from "./listPageChrome";
import { elapsedSeconds, formatMinutes } from "./workspace/runProgress";

type LatestRun = components["schemas"]["TaskOut"]["latest_run"];

type TaskListRowProps = {
  to: string;
  name: string;
  /** The row's `TaskOut.capability` (task 044). Left undefined only by a
   *  caller with no task row to hand; `capabilityLabel` falls back. No depth
   *  is shown beside it (owner ruling, C17). */
  capabilityKey?: string | null;
  projectName?: string | null;
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

/** One task row: name (optional task prefix), capability, aligned status, [owner], sources, date. */
export function TaskListRow({
  to,
  name,
  capabilityKey,
  projectName,
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
  // The dot breathes for a moment when the polled stage changes, then rests.
  const fresh = useFreshness(running ? (activeRun?.stage_label ?? null) : null);
  const statusLabel = running
    ? `${activeRun?.stage_label} · ${formatMinutes(elapsedSeconds(activeRun?.started_at, undefined, nowMs))}`
    : status.label;
  const safeName = scrub(name);
  const safeProject = projectName != null ? scrub(projectName) : null;
  const ariaLabel =
    showProjectPrefix && safeProject != null ? `${safeProject}, ${safeName}` : safeName;
  const showOwner = ownerDisplay !== undefined;

  return (
    <Link
      to={to}
      aria-label={ariaLabel}
      className={`${showOwner ? taskListRowGridClassWithOwner : taskListRowGridClass} px-4 py-3.5 no-underline hover:bg-blue-tint-2`}
    >
      {/* Below md the row is a wrapping flex line: the name takes the whole
          first line, the metadata flows onto the line(s) below. */}
      <span className="min-w-0 truncate text-body max-md:w-full">
        {showProjectPrefix && safeProject != null && (
          <>
            <span className="font-normal text-grey">{safeProject}</span>
            <span aria-hidden="true" className="mx-1.5 font-normal text-line-2">
              /
            </span>
          </>
        )}
        <span className="font-semibold text-navy">{safeName}</span>
      </span>
      <Chip tone="blue" className="shrink-0">
        {capabilityLabel(capabilityKey)}
      </Chip>
      <span className="inline-flex min-w-0 items-center gap-1.5 text-meta text-grey">
        <StatusDot tone={running ? "running" : status.dot} className={running && fresh ? "anim-breathe" : undefined} />
        <span className="truncate" title={statusLabel}>
          <Figures text={scrub(statusLabel)} />
        </span>
      </span>
      {showOwner && (
        <span className="truncate text-right text-meta text-grey">
          {ownerDisplay !== null ? scrub(ownerDisplay) : ownerlessLabel}
        </span>
      )}
      <span className="text-right text-meta tabular-nums text-grey">
        {/* null and 0 differ: null means no run has asked yet. */}
        {sourceCount != null
          ? sourceCount === 1
            ? "1 source"
            : `${sourceCount} sources`
          : ""}
      </span>
      {updatedAt != null ? (
        <time dateTime={updatedAt} className="text-right text-caption tabular-nums text-grey">
          {new Date(updatedAt).toLocaleDateString()}
        </time>
      ) : (
        <span aria-hidden="true" />
      )}
    </Link>
  );
}
