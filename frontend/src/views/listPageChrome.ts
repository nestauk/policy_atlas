/** List-page column (Tasks, Projects, New task) — not the in-task tabs. */
export const PAGE_COLUMN_MAX_W = "max-w-[1180px]";

/** Reading measure: the report paper, and the content column on Plan,
 *  History and Share. Sources (Themes, Landscape, All sources, Findings)
 *  uses the list-page column — see `WIDE_PAGE_CLASS`. */
export const READING_COLUMN_MAX_W = "max-w-[780px]";

/** Centered lifecycle content: same width as the report paper. */
export const LIFECYCLE_PAGE_CLASS = `mx-auto w-full px-6 ${READING_COLUMN_MAX_W}`;

/** Centered list-page column, reused by Sources. */
export const WIDE_PAGE_CLASS = `mx-auto w-full px-6 ${PAGE_COLUMN_MAX_W}`;

/** Shared page title on Tasks, Projects and project-detail views. */
export const listPageTitleClass =
  "text-display font-extrabold tracking-[-0.5px] text-navy text-pretty";

/** Primary “new” action in a list-page header — matches the New-task entry weight. */
export const listNewButtonClass =
  "cutout inline-flex items-center bg-blue px-6 py-3.5 text-body font-bold text-white no-underline hover:bg-[#0000d6]";

/** Secondary header action (Find a task, back links). */
export const listSecondaryActionClass =
  "text-lead font-normal text-grey no-underline hover:text-navy";

/**
 * Fixed-column grid for task rows so status, source count and date stay aligned
 * even when labels differ in length.
 */
export const taskListRowGridClass =
  "grid grid-cols-[minmax(0,1fr)_auto_12rem_5.5rem_7rem] items-center gap-x-4";

/** Same grid, with an owner column before the source count (task 033 phase
 *  10b) — only used where the caller has decided to show `owner_display`. */
export const taskListRowGridClassWithOwner =
  "grid grid-cols-[minmax(0,1fr)_auto_12rem_8rem_5.5rem_7rem] items-center gap-x-4";

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

/** New-task URL, optionally scoped to a project. Capability is chosen on that page. */
export function newTaskHref(portfolioId?: string | null): string {
  if (portfolioId == null || portfolioId === "") return "/new";
  return `/new?${new URLSearchParams({ portfolio: portfolioId }).toString()}`;
}

/**
 * When a portfolio has tasks, its last activity is the newest task `updated_at`;
 * otherwise fall back to when the portfolio row was created.
 */
export function portfolioLastUpdated(
  portfolio: { portfolio_id: string; created_at: string },
  taskUpdatedAt: ReadonlyMap<string, string>,
): string {
  return taskUpdatedAt.get(portfolio.portfolio_id) ?? portfolio.created_at;
}

/** Newest activity first — the sort order for the projects list. */
export function sortPortfoliosByLastUpdated<
  T extends { portfolio_id: string; created_at: string },
>(rows: readonly T[], taskUpdatedAt: ReadonlyMap<string, string>): T[] {
  return [...rows].sort((left, right) =>
    portfolioLastUpdated(right, taskUpdatedAt).localeCompare(
      portfolioLastUpdated(left, taskUpdatedAt),
    ),
  );
}

/** Build a map of portfolio id → newest assigned task `updated_at`. */
export function newestTaskUpdateByPortfolio(
  tasks: ReadonlyArray<{ portfolio_ids?: readonly string[] | null; updated_at: string }>,
): Map<string, string> {
  const map = new Map<string, string>();
  for (const task of tasks) {
    for (const portfolioId of task.portfolio_ids ?? []) {
      const existing = map.get(portfolioId);
      if (existing === undefined || task.updated_at > existing) {
        map.set(portfolioId, task.updated_at);
      }
    }
  }
  return map;
}
