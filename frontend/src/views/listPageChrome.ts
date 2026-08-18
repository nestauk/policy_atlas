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
  tasks: ReadonlyArray<{ portfolio_id?: string | null; updated_at: string }>,
): Map<string, string> {
  const map = new Map<string, string>();
  for (const task of tasks) {
    if (task.portfolio_id == null) continue;
    const existing = map.get(task.portfolio_id);
    if (existing === undefined || task.updated_at > existing) {
      map.set(task.portfolio_id, task.updated_at);
    }
  }
  return map;
}
