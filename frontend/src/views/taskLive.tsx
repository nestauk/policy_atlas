import { createContext, useCallback, useContext, useEffect, useMemo, useState, useSyncExternalStore, type ReactNode } from "react";
import { useLocation } from "react-router";

import { TitleMarkerProvider } from "../lib/title";
import { useRunStream, type RunStreamState } from "../store";
import { tabOfPath, type LifecycleTab } from "./lifecycle";
import { READY_WORDS, isFinished, walkKind } from "./workspace/runProgress";

/** A connection's replay arrives in a burst after it opens; nothing that lands
 *  in this window marks a tab, so an old run never reads as new. */
export const REPLAY_SETTLE_MS = 2_500;

/** What has landed on the stream so far, for the tab that can be marked. */
export interface Landing {
  runId: string | null;
  /** Report sections written. */
  sections: number;
  /** True once the run finished with something to read. */
  finished: boolean;
}

/** Marks the shell shows: the Result tab's dot (a section or the report is
 *  ready), and the unseen finish. The Sources tab has no mark (owner, round
 *  8: it was not useful). */
export interface Marks {
  result: boolean;
  /** The run finished and the user has not looked at the Result tab since. */
  ready: boolean;
}

export const NO_MARKS: Marks = { result: false, ready: false };

/** Read what has landed from the stream. */
export function landingOf(stream: Pick<RunStreamState, "run" | "stages" | "liveSections">): Landing {
  return {
    runId: stream.run?.id ?? null,
    sections: Object.values(stream.liveSections).filter((section) => section.state === "filled").length,
    finished: isFinished(stream.run?.status),
  };
}

export function sameLanding(a: Landing, b: Landing): boolean {
  return a.runId === b.runId && a.sections === b.sections && a.finished === b.finished;
}

/**
 * The marks after something new lands (task 058, N14): the Result tab gets a
 * dot when a section or the report lands while the user is on another tab;
 * the finish is unseen unless the user is looking at the Result tab. A new
 * run clears the finish.
 *
 * Args:
 *   marks: The marks before.
 *   before: What had landed before.
 *   after: What has landed now.
 *   tab: The tab the user is on.
 *   looking: Whether the page is visible.
 *
 * Returns:
 *   The new marks.
 */
export function nextMarks(marks: Marks, before: Landing, after: Landing, tab: LifecycleTab | null, looking: boolean): Marks {
  const next = after.runId !== before.runId ? { ...marks, ready: false } : { ...marks };
  const justFinished = after.finished && !before.finished;
  if (tab !== "result" && (after.sections > before.sections || justFinished)) next.result = true;
  if (justFinished && !(tab === "result" && looking)) next.ready = true;
  return next;
}

/** The marks once the user is on `tab`: visiting the Result tab clears its
 *  dot, and seeing it clears the unseen finish. */
export function visitMarks(marks: Marks, tab: LifecycleTab | null, looking: boolean): Marks {
  if (tab === "result" && (marks.result || (marks.ready && looking))) {
    return { ...marks, result: false, ready: looking ? false : marks.ready };
  }
  return marks;
}

function subscribeVisibility(onChange: () => void): () => void {
  document.addEventListener("visibilitychange", onChange);
  return () => document.removeEventListener("visibilitychange", onChange);
}

/** Whether the page is in front of the user (not a background browser tab). */
function usePageVisible(): boolean {
  return useSyncExternalStore(
    subscribeVisibility,
    () => document.visibilityState !== "hidden",
    () => true,
  );
}

interface TaskLive {
  taskId: string;
  tab: LifecycleTab | null;
  stream: RunStreamState;
  marks: Marks;
  capability: string | null | undefined;
  isOwner: boolean;
}

const TaskLiveContext = createContext<TaskLive | null>(null);

/** Registers a mounted run trace; returns the unregister. */
type RegisterTrace = () => () => void;
const RegisterTraceContext = createContext<RegisterTrace | null>(null);
const MountedTracesContext = createContext(0);

/** Called by every run trace while it is mounted, so the run status bar can keep
 *  its own live region quiet then: one change is announced once (task 058,
 *  owner round 7). A no-op outside the signed-in task shell. */
export function useRegisterTrace(): void {
  const register = useContext(RegisterTraceContext);
  useEffect(() => (register === null ? undefined : register()), [register]);
}

/** How many run traces are mounted (the Agent tab's, the sidebar's). */
export function useMountedTraces(): number {
  return useContext(MountedTracesContext);
}

/** The task shell's live layer, or `null` outside a signed-in task. */
export function useTaskLive(): TaskLive | null {
  return useContext(TaskLiveContext);
}

/**
 * The live layer of the signed-in task shell (task 058, N12, N14): reads the
 * one run stream and works out the tab dots and the unseen finish, which the
 * lifecycle tabs and the browser title read. Mounted inside
 * `RunStreamProvider`; the public task shell has no stream and no live layer.
 */
export function TaskLiveProvider({
  taskId,
  enabled,
  capability,
  isOwner,
  children,
}: {
  taskId: string;
  /** False for a reader with no stream (the public leg, or before the task
   *  resolves): the layer then provides nothing. Kept mounted either way so
   *  the shell's subtree never remounts when access resolves. */
  enabled: boolean;
  capability: string | null | undefined;
  isOwner: boolean;
  children: ReactNode;
}) {
  const stream = useRunStream(taskId);
  const { pathname } = useLocation();
  const tab = tabOfPath(pathname, `/tasks/${taskId}`);
  const looking = usePageVisible();

  const [settled, setSettled] = useState(false);
  useEffect(() => {
    if (settled || stream.connectionStatus !== "connected") return undefined;
    const id = window.setTimeout(() => setSettled(true), REPLAY_SETTLE_MS);
    return () => window.clearTimeout(id);
  }, [settled, stream.connectionStatus]);

  const landing = landingOf(stream);
  const [seen, setSeen] = useState(landing);
  const [marks, setMarks] = useState<Marks>(NO_MARKS);
  // Derived from the stream during render (state from the previous render):
  // before the replay settles, what has landed is the baseline, not news.
  let next = marks;
  if (!sameLanding(seen, landing)) {
    setSeen(landing);
    if (settled) next = nextMarks(next, seen, landing, tab, looking);
  }
  next = visitMarks(next, tab, looking);
  if (next !== marks) setMarks(next);

  const [traces, setTraces] = useState(0);
  const registerTrace = useCallback(() => {
    setTraces((count) => count + 1);
    return () => setTraces((count) => count - 1);
  }, []);

  const kind = walkKind(capability, stream.stages);
  const value = useMemo(
    () => (enabled ? { taskId, tab, stream, marks, capability, isOwner } : null),
    [enabled, taskId, tab, stream, marks, capability, isOwner],
  );
  return (
    <TaskLiveContext.Provider value={value}>
      <RegisterTraceContext.Provider value={registerTrace}>
        <MountedTracesContext.Provider value={traces}>
          <TitleMarkerProvider ready={enabled && marks.ready ? READY_WORDS[kind] : null}>{children}</TitleMarkerProvider>
        </MountedTracesContext.Provider>
      </RegisterTraceContext.Provider>
    </TaskLiveContext.Provider>
  );
}

/** The small navy mark a lifecycle tab carries when it has something new:
 *  the same 6 px square as the status mark, so the app has one mark shape. */
export function NewContentDot() {
  return (
    <>
      <span aria-hidden="true" data-testid="new-content-mark" className="inline-block size-1.5 flex-none bg-navy" />
      <span className="sr-only">New content</span>
    </>
  );
}

/** The Result tab's dot for the live layer's marks, merged into the tab items. */
export function withTabMarks<T extends { tab: string; marker?: ReactNode }>(items: T[], marks: Marks | null): T[] {
  if (marks === null) return items;
  return items.map((item) =>
    item.marker === undefined && item.tab === "result" && marks.result
      ? { ...item, marker: <NewContentDot /> }
      : item,
  );
}
