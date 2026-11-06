/** List-page column width (Tasks, Projects, Sources) — not the in-task tabs.
 *  The list pages' own column and header live in `ui/brand/PageHeader`. */
const PAGE_COLUMN_MAX_W = "max-w-[1180px]";

/** Reading measure: the report paper, and the content column on Plan,
 *  History and Share. Sources (Themes, Landscape, All sources, Findings)
 *  uses the list-page column — see `WIDE_PAGE_CLASS`. */
export const READING_COLUMN_MAX_W = "max-w-[780px]";

/** Centered lifecycle content: same width as the report paper. 24 px gutters
 *  from md up, 16 px below, as on the list pages and the report. Every task
 *  tab pads its page `py-8` (32 px, the report sheet's margin). */
export const LIFECYCLE_PAGE_CLASS = `mx-auto w-full px-6 max-md:px-4 ${READING_COLUMN_MAX_W}`;

/** Centered list-page column, reused by Sources. */
export const WIDE_PAGE_CLASS = `mx-auto w-full px-6 max-md:px-4 ${PAGE_COLUMN_MAX_W}`;

/*
 * One row recipe for the task list and the project list (task 058, lists
 * polish and round 10), so the two lists read as one family and every
 * column lines up page to page.
 *
 * md and up: one 56 px line (14 px padding around a 28 px line box). The
 * task's name takes every pixel the other columns leave (round 12). The task
 * list's columns are one grid on the list, not on each row: every row is a
 * subgrid of it (`taskListGridClass` on the `ul`, `taskListItemClass` on the
 * `li`, the row's own `md:grid-cols-subgrid`), so the capability, status and
 * owner tracks are `auto` and size to the widest value the list holds, not
 * to the widest value any list could hold. The status cell carries 8 px of
 * its own on the column gap, so its widest word stands 24 px from the owner
 * (or the count); the owner's name starts there, left-aligned, capped at
 * 8rem and ellipsed beyond it. The count and date tail stays fixed (5.5rem,
 * 5.5rem), so a project row's task count and date end exactly under a task
 * row's source count and date.
 *
 * Round 12's cause (owner: the gap between status and owner "is making the
 * task names cramped"): the status column was a fixed 11.5rem, sized for
 * "Paused · waiting on <first name>", and the owner a fixed 8rem with its
 * name right-aligned, so a "Complete" row by "You" left ~230 px of white
 * between the two words while the name was cut short.
 * The project rows below keep their own fixed grid (one row per grid); their
 * owner cell takes the same `rowOwnerCellClass`.
 *
 * Below md: two fixed lines, 84 px every row. Line 1 is the name alone
 * (24 px, truncated, never wrapped); line 2 (28 px) leads with the status
 * word and its live step, then the project, with the date at the right.
 * The capability, the owner and the source count drop on phones (lead
 * rulings P3, round 10); they stay on the task's own pages. The list is not
 * a grid there; each row is its own two-track grid.
 *
 * Press: the row deepens to Blue Tint the instant it is pressed and eases
 * back over the hover's 150 ms when released (round 10).
 *
 * The row's menu (round 12): every row keeps 48 px of right padding, where
 * its owner's 40 px menu control sits as a sibling of the link
 * (`ListRowMenu`), so every row's columns line up whether or not it has the
 * control. The hover wash is the item's (`group` on the `li`), so pointing
 * at the control keeps the row lit.
 */
const ROW_BASE =
  "grid min-h-14 items-center gap-x-4 pl-4 pr-12 py-3.5 no-underline group-hover:bg-blue-tint-2 " +
  "transition-colors duration-150 ease-[ease] active:bg-blue-tint active:duration-0 " +
  "focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-blue " +
  "max-md:gap-x-3 max-md:gap-y-1";

/** The task list's `ul`: from md up, the one grid every row is a subgrid
 *  of; its tracks are name, kind, status, sources, date. The date track is
 *  8.5rem because a subgrid's padding sits in its edge tracks: the row's
 *  48 px right padding (the room for the row's menu control, round 12)
 *  plus the date's 5.5rem. (Literal class strings:
 *  Tailwind finds classes by scanning the source.) */
export const taskListGridClass =
  "md:grid md:grid-cols-[minmax(0,1fr)_auto_auto_5.5rem_8.5rem] md:gap-x-4";

/** The same grid with the owner (task 033 phase 10b) before the count. */
export const taskListGridClassWithOwner =
  "md:grid md:grid-cols-[minmax(0,1fr)_auto_auto_auto_5.5rem_8.5rem] md:gap-x-4";

/** A task list's `li`: spans the list's grid and passes its tracks on. */
export const taskListItemClass = "md:col-span-full md:grid md:grid-cols-subgrid";

/** A task row: the list's tracks from md up (it must sit in the list's
 *  grid), its own two tracks below md. */
export const taskListRowGridClass = `${ROW_BASE} md:col-span-full md:grid-cols-subgrid max-md:grid-cols-[minmax(0,1fr)_auto]`;

/** A task row's status cell from md up: at most the old fixed width, and
 *  8 px on the 16 px gap, so 24 px to the next column. */
export const rowStatusCellClass = "md:max-w-[11.5rem] md:box-content md:pr-2";

/** A task row's owner cell: a name, so left-aligned, 24 px after the
 *  widest status word on every row; capped at 8rem (the Projects page's
 *  owner width) and ellipsed beyond it. */
export const rowOwnerCellClass = "max-w-[8rem] truncate text-left text-meta leading-7 text-grey";

/** Project rows: name, task count, date — on the task rows' tail. */
export const projectListRowGridClass = `${ROW_BASE} grid-cols-[minmax(0,1fr)_5.5rem_5.5rem] max-md:grid-cols-[minmax(0,1fr)_auto]`;

/** Project rows with the owner column, on the task rows' owner column. */
export const projectListRowGridClassWithOwner = `${ROW_BASE} grid-cols-[minmax(0,1fr)_8rem_5.5rem_5.5rem] max-md:grid-cols-[minmax(0,1fr)_auto]`;

/** A row's name cell: the whole first line below md (`max-md:col-span-2`). */
export const rowNameCellClass = "min-w-0 truncate text-body leading-7 max-md:leading-6";

/** A right-aligned cell (owner, count, date) on the 28 px line, at Meta.
 *  Set its digits with `Figures`, not `tabular-nums` on the cell: Averta's
 *  tabular feature widens the space too ("46  sources", "Ada  Lovelace"). */
export const rowFigureCellClass = "truncate text-right text-meta leading-7 text-grey";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/**
 * A list row's date: "5 Nov" within the current year, "12 Oct 2025" before
 * it (lead ruling P7, round 10). One fixed form for every reader rather than
 * the browser's locale ("11/5/2026" and "05/11/2026" are different days to
 * two colleagues), and never relative ("2 days ago" goes stale under an open
 * tab and in a pasted screenshot). The month names are fixed here so no
 * locale can turn "Sep" into "Sept".
 *
 * Args:
 *   iso: An ISO 8601 timestamp.
 *   now: The current time, for the year comparison; a parameter so tests
 *     need no clock.
 *
 * Returns:
 *   The date in the reader's local time zone, or "" for an unreadable value.
 */
export function formatListDate(iso: string, now: Date = new Date()): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const dayMonth = `${date.getDate()} ${MONTHS[date.getMonth()]}`;
  return date.getFullYear() === now.getFullYear() ? dayMonth : `${dayMonth} ${date.getFullYear()}`;
}

/**
 * A row's accessible name: its visible strings in reading order, joined by
 * " · " (lead ruling 1, round 10), skipping any the row does not show.
 *
 * Args:
 *   parts: The strings, title first; null, undefined and "" are dropped.
 *
 * Returns:
 *   The joined name.
 */
export function rowAccessibleName(parts: readonly (string | null | undefined)[]): string {
  return parts.filter((part): part is string => part != null && part.trim() !== "").join(" · ");
}

/** The list frame: hairline paper, rows divided by Line hairlines. */
export const listFrameClass = "border border-line-2 bg-paper";

/**
 * Whether a list page shows the `owner_display` column (task 033 phase
 * 10b, contract § 11 / rubric 41; round 10).
 *
 * The dark-launch invariant (rubric 14) is the anchor: an unenrolled caller
 * never has the switcher, and can never be handed a row they don't own (no
 * organisation means no colleague's row is reachable), so `hasSwitcher`
 * false and `rows.some(is_owner === false)` false always travel together for
 * that caller — the column stays off, byte-identical to today.
 *
 * On Mine, active or archived, the column is off (lead ruling P6, round
 * 10): it would say the reader's own name on every row. It shows on
 * Organisation, active or archived (round 11), and on a Project, where every
 * row renders it (the reader's own rows read "You") — a column that appears
 * on some rows and not others reads as broken alignment, not as a
 * considered omission.
 */
export function showOwnerColumn(
  hasSwitcher: boolean,
  rows: readonly { is_owner?: boolean }[],
  scope?: "mine" | "all",
): boolean {
  if (scope === "mine") return false;
  return hasSwitcher || rows.some((row) => row.is_owner === false);
}

/** New-task URL, optionally scoped to a task. Capability is chosen on that page. */
export function newTaskHref(projectId?: string | null): string {
  if (projectId == null || projectId === "") return "/new";
  return `/new?${new URLSearchParams({ project: projectId }).toString()}`;
}
