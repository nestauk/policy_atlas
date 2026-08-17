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
  findTask: `Find a ${TASK.lower}`,
  allTasks: `All ${TASK.lowerMany}`,
  noTasks: `No ${TASK.lowerMany} yet`,
  noProject: `No ${PROJECT.lower}`,
  comingSoon: "Coming soon",
  /** A locked tab explains itself rather than showing an empty page. */
  lockedHint: "Available once the analysis has run",
  notDecided: "Not decided yet",
  shareComingSoon: "Sharing is coming soon.",
} as const;
