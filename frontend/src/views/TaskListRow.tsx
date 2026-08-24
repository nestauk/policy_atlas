import { Link } from "react-router";

import type { components } from "../api/gen/types";
import { capabilityLabel } from "../lib/capabilities";
import { scrub } from "../lib/scrub";
import { StatusDot } from "../ui/brand/Card";
import { Chip } from "../ui/brand/Chip";
import { taskStatus } from "./landingPresentation";
import { taskListRowGridClass } from "./listPageChrome";

type LatestRun = components["schemas"]["ProjectOut"]["latest_run"];

type TaskListRowProps = {
  to: string;
  name: string;
  capabilityKey?: string | null;
  portfolioName?: string | null;
  showProjectPrefix?: boolean;
  sourceCount?: number | null;
  updatedAt?: string | null;
  latestRun?: LatestRun;
};

/** One task row: name (optional project prefix), capability, aligned status, sources, date. */
export function TaskListRow({
  to,
  name,
  capabilityKey,
  portfolioName,
  showProjectPrefix = false,
  sourceCount,
  updatedAt,
  latestRun,
}: TaskListRowProps) {
  const status = taskStatus(latestRun);
  const safeName = scrub(name);
  const safePortfolio = portfolioName != null ? scrub(portfolioName) : null;
  const ariaLabel =
    showProjectPrefix && safePortfolio != null ? `${safePortfolio}, ${safeName}` : safeName;

  return (
    <Link
      to={to}
      aria-label={ariaLabel}
      className={`${taskListRowGridClass} px-4 py-3.5 no-underline hover:bg-blue-tint-2`}
    >
      <span className="min-w-0 truncate text-body">
        {showProjectPrefix && safePortfolio != null && (
          <>
            <span className="font-normal text-grey">{safePortfolio}</span>
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
