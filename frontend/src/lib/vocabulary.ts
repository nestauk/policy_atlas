import { formatCount } from "./format";

/**
 * Every user-visible word for the two entities, in one place.
 *
 * Task 038 (ADR 0036) aligned the code word to the screen word: a `task`
 * row is a **Task** on screen — one research question with its own plan,
 * run and report; a `project` row is a **Project** on screen — a named
 * body of related tasks, holding no plan, run or evidence of its own.
 *
 * No view hard-codes either word even though the words now match. A view
 * that writes "Task" or "Project" as a string literal still bypasses the
 * one place this copy is maintained — that is what importing from here
 * prevents.
 */

/** The screen word for a `task` row. */
export const TASK = {
  one: "Task",
  many: "Tasks",
  lower: "task",
  lowerMany: "tasks",
} as const;

/** The screen word for a `project` row. */
export const PROJECT = {
  one: "Project",
  many: "Projects",
  lower: "project",
  lowerMany: "projects",
} as const;

/** A count with its noun: `countOf(1, "option", "options")` → "1 option". */
export function countOf(n: number, one: string, many: string): string {
  return `${formatCount(n)} ${n === 1 ? one : many}`;
}

/** The five task-level lifecycle tabs, in their fixed order. */
export const LIFECYCLE_LABELS = {
  agent: "Agent",
  result: "Result",
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
  findProject: `Find a ${PROJECT.lower}`,
  allTasks: `All ${TASK.lowerMany}`,
  noTasks: `No ${TASK.lowerMany} yet`,
  comingSoon: "Coming soon",
  /** `AppShell`'s header popover — the trigger's `aria-label` and `title`. */
  taskSettings: `${TASK.one} settings`,
  /** A locked tab explains itself rather than showing an empty page. */
  lockedHint: "Available once the analysis has run",
  notDecided: "Not decided yet",
  /** `ChatSidePanel`'s overlay region: the Agent, the one persona a user
   *  talks to (ADR 0036, contract § V4 / § V8). */
  agentAriaLabel: "Agent",
  /** The collapsed overlay's launcher — its `aria-label`, then its `title`. */
  openAgent: "Open the Agent",
  agent: "Agent",
  /** A Task's primary chat: the `kind = task_agent` conversation — the active
   *  one, else the most recently closed. Exactly one row ever carries this
   *  label (contract § V8, invariant I8 / fold A10). */
  taskAgent: `${TASK.one} Agent`,
  newChat: "New chat",
  newChatUnavailable: `New chat — available once the ${TASK.lower} has a result`,
  /** An older, closed task_agent lineage in the chats library — chipped, never
   *  pinned. */
  earlierPlan: "Earlier plan",
  /** `TaskAgentPane`'s composer label. */
  messageTaskAgent: `Message the ${TASK.one} Agent`,
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
