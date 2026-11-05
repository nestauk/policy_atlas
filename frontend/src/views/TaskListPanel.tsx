import type { ReactNode } from "react";

import type { components } from "../api/gen/types";
import { COPY, TASK } from "../lib/vocabulary";
import { Button } from "../ui/brand/Button";
import { PagePrimary } from "../ui/brand/PageHeader";
import { FindPopover, type FindItem } from "./FindPopover";
import { taskDestination } from "./lifecycle";
import { listFrameClass } from "./listPageChrome";
import { TaskListRow } from "./TaskListRow";
import { hasLonglist, statusRun } from "./scopingActivity";

type LatestRun = components["schemas"]["TaskOut"]["latest_run"];

type TaskListItem = {
  task_id: string;
  name: string;
  /** The kind of work (task 044). Optional so a caller assembling rows by
   *  hand need not invent one; the row's label falls back. */
  capability?: string | null;
  updated_at: string;
  latest_run?: LatestRun;
  /** Task 045 (S15): any running or paused walk, option searches included. */
  active_run?: LatestRun;
  /** Task 045: whether a scoping task has a longlist. */
  has_longlist?: boolean;
  project_ids?: string[];
  source_count?: number | null;
  is_owner?: boolean;
  owner_display?: string | null;
};

/** Where a row lands: the Result once there is one to read (a finished run,
 *  or a scoping task's longlist — task 045), else the Agent tab. */
function rowDestination(row: TaskListItem): string {
  return taskDestination(row.task_id, row.latest_run?.status, { hasLonglist: hasLonglist(row) });
}

/** The names of a task's projects, in order, skipping any not in the map. */
function projectNameList(
  ids: readonly string[] | null | undefined,
  names?: ReadonlyMap<string, string>,
): string[] {
  if (ids == null || ids.length === 0) return [];
  return ids.map((id) => names?.get(id) ?? "").filter((name) => name !== "");
}

function projectPrefix(
  ids: readonly string[] | null | undefined,
  names?: ReadonlyMap<string, string>,
): string {
  return projectNameList(ids, names).join(" · ");
}

/** Find-a-task and New-task controls shared by the Tasks and Project page
 *  headers: drop them straight into `PageHeader`'s actions slot. */
export function TaskListActions({
  rows,
  projectNames,
  showProjectPrefix = false,
  newTaskHref,
}: {
  rows: readonly TaskListItem[];
  projectNames?: ReadonlyMap<string, string>;
  showProjectPrefix?: boolean;
  newTaskHref: string;
}) {
  const items: FindItem[] = rows.map((row) => {
    const projectName = showProjectPrefix ? projectPrefix(row.project_ids, projectNames) : "";
    return {
      id: row.task_id,
      label: projectName !== "" ? `${projectName} / ${row.name}` : row.name,
      href: rowDestination(row),
      updatedAt: row.updated_at,
    };
  });

  return (
    <>
      <FindPopover items={items} copy={{ label: COPY.findTask, noun: TASK.lowerMany }} />
      <PagePrimary to={newTaskHref}>{COPY.newTask}</PagePrimary>
    </>
  );
}

type TaskListPanelProps = {
  rows: readonly TaskListItem[];
  projectNames?: ReadonlyMap<string, string>;
  showProjectPrefix?: boolean;
  isPending?: boolean;
  isError?: boolean;
  onRetry?: () => void;
  loaded?: boolean;
  /** Task 033 phase 10b: render the `owner_display` column, and what a null
   *  value renders as (see `ownerLabelRule` — the em dash by default, or
   *  the admin-wide-list's "No organisation" when the caller passes it). */
  showOwner?: boolean;
  ownerlessLabel?: string;
  /** What an empty list shows, in the list's frame; nothing when absent. */
  empty?: ReactNode;
};

/**
 * The list loading: the list's own frame and row shape (lead ruling), so
 * the rows arrive into it rather than replacing a different page. Five rows
 * of the real row's height, 56 px (84 px below md, two lines), each with
 * the system's placeholder bar where the name will sit. The bars breathe,
 * and hold still under reduced motion.
 */
export function ListSkeleton({ label }: { label: string }) {
  return (
    <ul role="list" aria-busy="true" aria-label={label} className={listFrameClass}>
      {Array.from({ length: 5 }).map((_, index) => (
        <li
          key={index}
          aria-hidden="true"
          className="flex h-14 flex-col justify-center gap-y-1 border-b border-line px-4 last:border-b-0 max-md:h-21"
        >
          <span className="flex h-7 items-center max-md:h-6">
            <span className="placeholder-bar h-2.5 w-2/5" />
          </span>
          <span className="hidden h-7 items-center max-md:flex">
            <span className="placeholder-bar h-2.5 w-1/4" />
          </span>
        </li>
      ))}
    </ul>
  );
}

/**
 * An empty list: the list's frame with nothing in it, left-aligned at the
 * list's edge, hairline only (no card shadow). A label, then one plain
 * sentence when there is one. The page's primary stays the way forward.
 */
export function ListEmpty({ label, children }: { label: string; children?: ReactNode }) {
  return (
    <div role="status" className={`${listFrameClass} px-4 py-6`}>
      <p className="text-body font-semibold text-navy">{label}</p>
      {children != null && <p className="mt-1 text-body text-grey">{children}</p>}
    </div>
  );
}

/** A control inside the list's frame: the 40 px ghost at the ghost's own
 *  Meta size (the header's controls are Body; this one is not in the header). */
const LIST_CONTROL_CLASS = "h-10 whitespace-nowrap px-3 py-0 text-meta";

/**
 * A list that failed to load: the list's frame, the sentence, and a 40 px
 * ghost that asks again (lead ruling, 2026-11-05).
 */
export function ListError({
  children,
  actionLabel,
  onRetry,
}: {
  children: ReactNode;
  actionLabel: string;
  onRetry: () => void;
}) {
  return (
    <div
      role="alert"
      className={`${listFrameClass} flex flex-wrap items-center justify-between gap-x-4 gap-y-2 py-4 pl-4 pr-1`}
    >
      <p className="text-body text-navy">{children}</p>
      <Button variant="ghost" className={LIST_CONTROL_CLASS} onClick={onRetry}>
        {actionLabel}
      </Button>
    </div>
  );
}

/** Shared task list body: loading, empty, and rows. */
export function TaskListPanel({
  rows,
  projectNames,
  showProjectPrefix = false,
  isPending = false,
  isError = false,
  onRetry,
  loaded = true,
  showOwner = false,
  ownerlessLabel,
  empty,
}: TaskListPanelProps) {
  if (isPending) {
    return <ListSkeleton label={`Loading ${TASK.lowerMany}`} />;
  }

  if (isError) {
    return (
      <ListError actionLabel="Retry" onRetry={() => onRetry?.()}>
        Your {TASK.lowerMany} couldn't be loaded.
      </ListError>
    );
  }

  if (rows.length === 0) return loaded ? (empty ?? null) : null;

  return (
    <ul role="list" className={listFrameClass}>
      {rows.map((row) => (
        <li key={row.task_id} className="border-b border-line last:border-b-0">
          <TaskListRow
            to={rowDestination(row)}
            name={row.name}
            capabilityKey={row.capability}
            projectNames={
              showProjectPrefix ? projectNameList(row.project_ids, projectNames) : null
            }
            showProjectPrefix={showProjectPrefix}
            sourceCount={row.source_count}
            updatedAt={row.updated_at}
            latestRun={statusRun(row)}
            activeRun={row.active_run}
            ownerDisplay={showOwner ? (row.owner_display ?? null) : undefined}
            ownerlessLabel={ownerlessLabel}
          />
        </li>
      ))}
    </ul>
  );
}
