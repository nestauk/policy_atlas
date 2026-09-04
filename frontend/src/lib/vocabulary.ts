/**
 * Every user-visible word for the two entities, in one place.
 *
 * The screen and the code deliberately disagree, and the mapping is fixed
 * (task 032 § Terms):
 *
 * - a backend `project` row is a **Task** on screen — one research question
 *   with its own plan, run and report;
 * - a backend `portfolio` row is a **Project** on screen — a named body of
 *   related tasks, holding no plan, run or evidence of its own.
 *
 * No view hard-codes either word. A view that writes "Task" or "Project" as a
 * string literal has leaked the code word to the user, or the screen word into
 * the code — both are defects, and importing from here is what prevents them.
 */

/** The screen word for a backend `project` row. */
export const TASK = {
  one: "Task",
  many: "Tasks",
  lower: "task",
  lowerMany: "tasks",
} as const;

/** The screen word for a backend `portfolio` row. */
export const PROJECT = {
  one: "Project",
  many: "Projects",
  lower: "project",
  lowerMany: "projects",
} as const;

/** The five task-level lifecycle tabs, in their fixed order. */
export const LIFECYCLE_LABELS = {
  plan: "Plan",
  results: "Results",
  sources: "Sources",
  share: "Share",
  history: "History",
} as const;

/** The four Sources subviews. */
export const SOURCES_LABELS = {
  themes: "Themes",
  landscape: "Landscape",
  all: "All sources",
  findings: "Findings",
} as const;

/** Copy shared across the new-task entry and the lists. */
export const COPY = {
  newTask: `New ${TASK.lower}`,
  /** Global-nav label — shorter than the page heading. */
  navNew: "New",
  /** Capability-picker heading on /new. */
  newTaskPrompt: "What would you like to do?",
  findTask: `Find a ${TASK.lower}`,
  allTasks: `All ${TASK.lowerMany}`,
  noTasks: `No ${TASK.lowerMany} yet`,
  noProject: `No ${PROJECT.lower}`,
  comingSoon: "Coming soon",
  /** A locked tab explains itself rather than showing an empty page. */
  lockedHint: "Available once the analysis has run",
  notDecided: "Not decided yet",
} as const;

/**
 * Task 037 — the Share tab's public-link section (contract § R1, §
 * Public / private boundary). The warning states exactly what a public link
 * exposes, before the owner can turn it on.
 */
export const PUBLIC_SHARE = {
  heading: "Public link",
  statusOn: "Shared publicly — anyone with the link can view.",
  statusOff: "Not shared publicly.",
  warning:
    "Anyone on the internet with the link can see this Task's results and sources — including the source list and quoted excerpts from the underlying documents. They do not need to sign in.",
  turnOn: "Share publicly",
  turnOff: "Stop sharing publicly",
  copyLink: "Copy link",
  copied: "Link copied",
  toggleFailed: "Public sharing couldn't be changed. Try again.",
} as const;

/**
 * Task 033 phase 10b — organisation-tenancy chrome copy (contract § 11,
 * rubric 41). Lead-owned and binding: wired exactly, not rewritten.
 */
export const TENANCY_COPY = {
  /** Switcher options, in this order — the component itself carries no label. */
  scopeOrganisation: "Organisation",
  scopeMine: "Mine",
  /** Shown only when `is_admin` and the switcher's scope is Organisation. */
  adminWiderList: "Showing every organisation.",
  /** A null owning organisation on an admin-visible row. */
  noOrganisation: "No organisation",
  /** A null `owner_display` outside the admin-wide-list case. */
  ownerlessRow: "—",
  administrator: "Administrator",
} as const;
