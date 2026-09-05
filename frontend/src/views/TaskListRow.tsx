import { Link } from "react-router";

import type { components } from "../api/gen/types";
import { capabilityLabel } from "../lib/capabilities";
import { scrub } from "../lib/scrub";
import { StatusDot } from "../ui/brand/Card";
import { Chip } from "../ui/brand/Chip";
import { taskStatus } from "./landingPresentation";
import { taskListRowGridClass, taskListRowGridClassWithOwner } from "./listPageChrome";

type LatestRun = components["schemas"]["TaskOut"]["latest_run"];

type TaskListRowProps = {
  to: string;
  name: string;
  capabilityKey?: string | null;
  projectName?: string | null;
  showProjectPrefix?: boolean;
  sourceCount?: number | null;
  updatedAt?: string | null;
  latestRun?: LatestRun;
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
  ownerDisplay,
  ownerlessLabel = "—",
}: TaskListRowProps) {
  const status = taskStatus(latestRun);
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
      <span className="min-w-0 truncate text-body">
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
        <StatusDot tone={status.dot} />
        <span className="truncate">{status.label}</span>
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
