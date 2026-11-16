import { type ReactNode, useEffect, useRef, useState } from "react";

import type { components } from "../api/gen/types";
import { useArchiveTask, useUpdateTask } from "../api/mutations";
import type { useTasksPaged } from "../api/queries";
import { COPY, TASK } from "../lib/vocabulary";
import { FindPopover, type FindItem } from "./FindPopover";
import { RowFold, RowMenuControl, RowRenameField, useDepartingRows } from "./ListRowMenu";
import { useAddToProjectStep } from "./NameMenu";
import { taskDestination } from "./lifecycle";
import {
  taskListGridClass,
  taskListGridClassWithOwner,
  taskListItemClass,
} from "./listPageChrome";
import { TaskListRow } from "./TaskListRow";
import { hasLonglist, statusRun } from "./scopingActivity";
import { LIST_FRAME_CLASS, ListError, ListSkeleton } from "../ui/brand/list/ListStates";
import { ListFootRow, ShowMore } from "../ui/brand/list/ListFoot";

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
  /** `TaskOut.status`: an archived task's row reads "Archived". */
  status?: "active" | "archived";
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

/** "Find a task", shared by the Tasks and Project pages: the magnifier at
 *  the right of the filters row (round 11; the header keeps only the
 *  primary). */
export function FindTasks({
  rows,
  projectNames,
  showProjectPrefix = false,
  className,
}: {
  rows: readonly TaskListItem[];
  projectNames?: ReadonlyMap<string, string>;
  showProjectPrefix?: boolean;
  /** Placement only, passed to the magnifier. */
  className?: string;
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
    <FindPopover
      items={items}
      copy={{ label: COPY.findTask, noun: TASK.lowerMany }}
      className={className}
    />
  );
}

type PagedTasks = ReturnType<typeof useTasksPaged>;
type TaskRow = NonNullable<PagedTasks["data"]>["pages"][number]["data"][number];

/** What the list's foot needs to offer the next page (round 10). */
export type MoreTasks = {
  /** The server holds rows the list has not asked for yet. */
  hasMore: boolean;
  /** The page just asked for is on its way. */
  loading: boolean;
  /** The page just asked for failed. */
  error: boolean;
  onShowMore: () => void;
  onRetry: () => void;
};

/**
 * A paged task list's rows and its foot (round 10: "Show more").
 *
 * `useTasksPaged` holds the pages and asks for the next one only while the
 * server says `has_more`. The rows are the pages in order with any task
 * already listed dropped, since a task that changes between two requests
 * can move across a page boundary.
 *
 * Args:
 *   result: A `useTasksPaged` result.
 *
 * Returns:
 *   The loaded rows and the foot's state.
 */
export function pagedTasks(result: PagedTasks): { rows: TaskRow[]; more: MoreTasks } {
  const seen = new Set<string>();
  const rows: TaskRow[] = [];
  for (const page of result.data?.pages ?? []) {
    for (const row of page.data) {
      if (seen.has(row.task_id)) continue;
      seen.add(row.task_id);
      rows.push(row);
    }
  }
  const askForNext = () => void result.fetchNextPage();
  return {
    rows,
    more: {
      hasMore: result.hasNextPage,
      loading: result.isFetchingNextPage,
      error: result.isFetchNextPageError,
      onShowMore: askForNext,
      onRetry: askForNext,
    },
  };
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
  /** The list's foot: "Show more" while the server holds more rows. */
  more?: MoreTasks;
  /** The foot row's right end, shown in every state (the archived toggle). */
  footEnd?: ReactNode;
};

/**
 * One task row with its menu (owner, round 12): the row's link, and beside
 * it, for the task's owner only, the control that opens Rename and Archive.
 * Rename turns the row into the name's field; Archive, once confirmed,
 * folds the row away (`onArchived`). An archived task offers Rename only.
 */
function TaskRowWithMenu({
  row,
  projectNames,
  showProjectPrefix,
  showOwner,
  ownerlessLabel,
  onArchived,
}: {
  row: TaskListItem;
  projectNames?: ReadonlyMap<string, string>;
  showProjectPrefix: boolean;
  showOwner: boolean;
  ownerlessLabel?: string;
  onArchived: () => void;
}) {
  const update = useUpdateTask(row.task_id);
  const archive = useArchiveTask(row.task_id);
  const [editing, setEditing] = useState(false);
  const control = useRef<HTMLButtonElement>(null);
  const isOwner = row.is_owner ?? true;
  const archived = row.status === "archived";
  const pending = update.isPending || archive.isPending;
  // The header's "Add to project", shared (owner, round 12).
  const addToProject = useAddToProjectStep(row.task_id, row.project_ids);

  if (editing) {
    return (
      <RowRenameField
        name={row.name}
        label={COPY.taskSettings}
        fieldLabel={`${TASK.one} name`}
        rename={(next, done) => update.mutate({ name: next }, { onSuccess: done.onSuccess, onError: done.onError })}
        renameError={`The ${TASK.lower} couldn't be renamed. Try again.`}
        pending={pending}
        onClose={() => {
          setEditing(false);
          window.setTimeout(() => control.current?.focus(), 0);
        }}
      />
    );
  }

  return (
    <>
      <TaskListRow
        to={rowDestination(row)}
        name={row.name}
        capabilityKey={row.capability}
        projectNames={showProjectPrefix ? projectNameList(row.project_ids, projectNames) : null}
        showProjectPrefix={showProjectPrefix}
        sourceCount={row.source_count}
        updatedAt={row.updated_at}
        latestRun={statusRun(row)}
        activeRun={row.active_run}
        isOwner={isOwner}
        ownerName={row.owner_display ?? null}
        showOwner={showOwner}
        ownerlessLabel={ownerlessLabel}
        archived={archived}
      />
      {isOwner && (
        <RowMenuControl
          label={COPY.taskSettings}
          name={row.name}
          controlRef={control}
          pending={pending}
          onRename={() => setEditing(true)}
          archive={
            archived
              ? undefined
              : (_, done) =>
                  archive.mutate(undefined, {
                    onSuccess: () => {
                      done.onSuccess();
                      onArchived();
                    },
                    onError: done.onError,
                  })
          }
          archiveSentence={`Archiving removes this ${TASK.lower} from your active ${TASK.lowerMany}.`}
          archiveError={`The ${TASK.lower} couldn't be archived. Try again.`}
          steps={[addToProject]}
        />
      )}
    </>
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
  more,
  footEnd,
}: TaskListPanelProps) {
  // After "Show more", focus moves to the first row that arrived, so a
  // keyboard reader carries on reading where the list grew rather than at a
  // button that may now be gone.
  const listRef = useRef<HTMLUListElement>(null);
  const focusFrom = useRef<number | null>(null);
  useEffect(() => {
    const from = focusFrom.current;
    if (from === null || rows.length <= from) return;
    focusFrom.current = null;
    listRef.current?.querySelectorAll<HTMLAnchorElement>(":scope > li a[href]")[from]?.focus();
  }, [rows.length]);

  // An archived row folds away where it stood (owner, round 12).
  const { shown, depart } = useDepartingRows(rows, (row) => row.task_id);

  const foot = (start?: ReactNode) => <ListFootRow start={start} end={footEnd} />;

  if (isPending) {
    return (
      <>
        <ListSkeleton label={`Loading ${TASK.lowerMany}`} />
        {foot()}
      </>
    );
  }

  if (isError) {
    return (
      <>
        <ListError actionLabel="Retry" onRetry={() => onRetry?.()}>
          Your {TASK.lowerMany} couldn't be loaded.
        </ListError>
        {foot()}
      </>
    );
  }

  if (rows.length === 0) {
    return (
      <>
        {loaded ? (empty ?? null) : null}
        {foot()}
      </>
    );
  }

  return (
    <>
      <ul
        ref={listRef}
        role="list"
        className={`${LIST_FRAME_CLASS} ${showOwner ? taskListGridClassWithOwner : taskListGridClass}`}
      >
        {shown.map(({ row, leaving }) => (
          <li key={row.task_id} className={`${taskListItemClass} group border-b border-line last:border-b-0`}>
            <RowFold leaving={leaving} subgrid>
              <TaskRowWithMenu
                row={row}
                projectNames={projectNames}
                showProjectPrefix={showProjectPrefix}
                showOwner={showOwner}
                ownerlessLabel={ownerlessLabel}
                onArchived={() => depart(row.task_id)}
              />
            </RowFold>
          </li>
        ))}
      </ul>
      {/* A page after the first that fails offers Retry under the rows. */}
      {more?.error === true && (
        <div className="mt-4">
          <ListError actionLabel="Retry" onRetry={more.onRetry}>
            Your {TASK.lowerMany} couldn't be loaded.
          </ListError>
        </div>
      )}
      {foot(
        more !== undefined && !more.error && more.hasMore ? (
          <ShowMore
            loading={more.loading}
            onShowMore={() => {
              focusFrom.current = rows.length;
              more.onShowMore();
            }}
          />
        ) : null,
      )}
    </>
  );
}
