/** List-page column width (Tasks, Projects, Sources) — not the in-task tabs.
 *  The list pages' own column and header live in `ui/brand/PageHeader`. */
const PAGE_COLUMN_MAX_W = "max-w-[1180px]";

/** Reading measure: the report paper, and the content column on Plan,
 *  History and Share. Sources (Themes, Landscape, All sources, Findings)
 *  uses the list-page column — see `WIDE_PAGE_CLASS`. */
export const READING_COLUMN_MAX_W = "max-w-[780px]";

/** Centered lifecycle content: same width as the report paper. */
export const LIFECYCLE_PAGE_CLASS = `mx-auto w-full px-6 ${READING_COLUMN_MAX_W}`;

/** Centered list-page column, reused by Sources. */
export const WIDE_PAGE_CLASS = `mx-auto w-full px-6 ${PAGE_COLUMN_MAX_W}`;

/*
 * One row recipe for the task list and the project list (task 058, lists
 * polish), so the two lists read as one family and every column lines up
 * page to page.
 *
 * md and up: one 56 px line (14 px padding around a 28 px line box); the
 * owner, count and date columns share one tail (8rem, 5.5rem, 7rem), so a
 * project row's owner, task count and date sit exactly under a task row's
 * owner, source count and date.
 *
 * Below md: two fixed lines, 84 px every row. Line 1 is the name alone
 * (24 px, truncated, never wrapped); line 2 (28 px) is the metadata. The
 * owner and the source count drop on phones (lead ruling P3); they stay on
 * the task's own pages.
 */
const ROW_BASE =
  "grid min-h-14 items-center gap-x-4 px-4 py-3.5 no-underline hover:bg-blue-tint-2 " +
  "transition-colors duration-150 ease-[ease] " +
  "focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-blue " +
  "max-md:gap-x-3 max-md:gap-y-1";

/** Task rows: name, kind, status, sources, date. */
export const taskListRowGridClass = `${ROW_BASE} grid-cols-[minmax(0,1fr)_auto_15rem_5.5rem_7rem] max-md:grid-cols-[auto_minmax(0,1fr)_auto]`;

/** Same grid, with an owner column before the source count (task 033 phase
 *  10b) — only used where the caller has decided to show `owner_display`. */
export const taskListRowGridClassWithOwner = `${ROW_BASE} grid-cols-[minmax(0,1fr)_auto_15rem_8rem_5.5rem_7rem] max-md:grid-cols-[auto_minmax(0,1fr)_auto]`;

/** Project rows: name, task count, date — on the task rows' tail. */
export const projectListRowGridClass = `${ROW_BASE} grid-cols-[minmax(0,1fr)_5.5rem_7rem] max-md:grid-cols-[minmax(0,1fr)_auto]`;

/** Project rows with the owner column, on the task rows' owner column. */
export const projectListRowGridClassWithOwner = `${ROW_BASE} grid-cols-[minmax(0,1fr)_8rem_5.5rem_7rem] max-md:grid-cols-[minmax(0,1fr)_auto]`;

/** A row's name cell: the whole first line below md. Pair with the row's
 *  column count there (`max-md:col-span-3` for tasks, `-2` for projects). */
export const rowNameCellClass = "min-w-0 truncate text-body leading-7 max-md:leading-6";

/** A right-aligned cell (owner, count, date) on the 28 px line. Set its
 *  digits with `Figures`, not `tabular-nums` on the cell: Averta's tabular
 *  feature widens the space too ("46  sources", "Ada  Lovelace"). */
export const rowFigureCellClass = "truncate text-right leading-7 text-grey";

/** The list frame: hairline paper, rows divided by Line hairlines. */
export const listFrameClass = "border border-line-2 bg-paper";

/**
 * Whether a list page shows the `owner_display` column (task 033 phase
 * 10b, contract § 11 / rubric 41).
 *
 * The dark-launch invariant (rubric 14) is the anchor: an unenrolled caller
 * never has the switcher, and can never be handed a row they don't own (no
 * organisation means no colleague's row is reachable), so `hasSwitcher`
 * false and `rows.some(is_owner === false)` false always travel together for
 * that caller — the column stays off, byte-identical to today.
 *
 * When it's on, every row in the list renders the column (including the
 * caller's own rows, where `owner_display` is just their own name) — a
 * column that appears on some rows and not others reads as broken
 * alignment, not as a considered omission.
 */
export function showOwnerColumn(
  hasSwitcher: boolean,
  rows: readonly { is_owner?: boolean }[],
): boolean {
  return hasSwitcher || rows.some((row) => row.is_owner === false);
}

/** New-task URL, optionally scoped to a task. Capability is chosen on that page. */
export function newTaskHref(projectId?: string | null): string {
  if (projectId == null || projectId === "") return "/new";
  return `/new?${new URLSearchParams({ project: projectId }).toString()}`;
}

/**
 * When a project has tasks, its last activity is the newest task `updated_at`;
 * otherwise fall back to when the project row was created.
 */
export function projectLastUpdated(
  project: { project_id: string; created_at: string },
  taskUpdatedAt: ReadonlyMap<string, string>,
): string {
  return taskUpdatedAt.get(project.project_id) ?? project.created_at;
}

/** Newest activity first — the sort order for the tasks list. */
export function sortProjectsByLastUpdated<
  T extends { project_id: string; created_at: string },
>(rows: readonly T[], taskUpdatedAt: ReadonlyMap<string, string>): T[] {
  return [...rows].sort((left, right) =>
    projectLastUpdated(right, taskUpdatedAt).localeCompare(
      projectLastUpdated(left, taskUpdatedAt),
    ),
  );
}

/** Build a map of project id → newest assigned task `updated_at`. */
export function newestTaskUpdateByProject(
  tasks: ReadonlyArray<{ project_ids?: readonly string[] | null; updated_at: string }>,
): Map<string, string> {
  const map = new Map<string, string>();
  for (const task of tasks) {
    for (const projectId of task.project_ids ?? []) {
      const existing = map.get(projectId);
      if (existing === undefined || task.updated_at > existing) {
        map.set(projectId, task.updated_at);
      }
    }
  }
  return map;
}
