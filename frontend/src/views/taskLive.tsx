import { createContext, useContext, useEffect, useState, useSyncExternalStore, type ReactNode } from "react";
import { Link, useLocation } from "react-router";

import { Figures } from "../lib/figures";
import { useFreshness, useNow } from "../lib/freshness";
import { scrub } from "../lib/scrub";
import { TitleMarkerProvider } from "../lib/title";
import { useRunStream, type RunStreamState } from "../store";
import { StatusDot } from "../ui/brand/Card";
import { cn } from "../ui/brand/cn";
import { tabOfPath, type LifecycleTab } from "./lifecycle";
import {
  READY_WORDS,
  cardRows,
  currentRow,
  elapsedSeconds,
  formatMinutes,
  isFinished,
  resultHref,
  rowDetail,
  rowLiveness,
  walkKind,
} from "./workspace/runProgress";

/** The stage frames whose landing gives the Sources tab something new:
 *  sources, the landscape, findings (task 058, N14). */
const SOURCES_STAGES = new Set(["acquire", "screen", "characterise", "extract", "group"]);

/** A connection's replay arrives in a burst after it opens; nothing that lands
 *  in this window marks a tab, so an old run never reads as new. */
export const REPLAY_SETTLE_MS = 2_500;

/** What has landed on the stream so far, per tab that can be marked. */
export interface Landing {
  runId: string | null;
  /** Report sections written. */
  sections: number;
  /** Completed stages that feed the Sources tab. */
  sources: number;
  /** True once the run finished with something to read. */
  finished: boolean;
}

/** Marks the shell shows: a dot per tab, and the unseen finish. */
export interface Marks {
  result: boolean;
  sources: boolean;
  /** The run finished and the user has not looked at the Result tab since. */
  ready: boolean;
}

export const NO_MARKS: Marks = { result: false, sources: false, ready: false };

/** Read what has landed from the stream. */
export function landingOf(stream: Pick<RunStreamState, "run" | "stages" | "liveSections">): Landing {
  return {
    runId: stream.run?.id ?? null,
    sections: Object.values(stream.liveSections).filter((section) => section.state === "filled").length,
    sources: stream.stages.filter((entry) => entry.status === "completed" && SOURCES_STAGES.has(entry.stage)).length,
    finished: isFinished(stream.run?.status),
  };
}

export function sameLanding(a: Landing, b: Landing): boolean {
  return a.runId === b.runId && a.sections === b.sections && a.sources === b.sources && a.finished === b.finished;
}

/**
 * The marks after something new lands (task 058, N14): a tab gets a dot when
 * its content lands while the user is on another tab; the finish is unseen
 * unless the user is looking at the Result tab. A new run clears the finish.
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
  if (tab !== "sources" && after.sources > before.sources) next.sources = true;
  if (justFinished && !(tab === "result" && looking)) next.ready = true;
  return next;
}

/** The marks once the user is on `tab`: visiting a tab clears its dot, and
 *  seeing the Result tab clears the unseen finish. */
export function visitMarks(marks: Marks, tab: LifecycleTab | null, looking: boolean): Marks {
  if (tab === "sources" && marks.sources) return { ...marks, sources: false };
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

/** The task shell's live layer, or `null` outside a signed-in task. */
export function useTaskLive(): TaskLive | null {
  return useContext(TaskLiveContext);
}

/**
 * The live layer of the signed-in task shell (task 058, N12, N14): reads the
 * one run stream and works out the tab dots and the unseen finish, which the
 * run strip, the lifecycle tabs and the browser title read. Mounted inside
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

  const kind = walkKind(capability, stream.stages);
  return (
    <TaskLiveContext.Provider value={enabled ? { taskId, tab, stream, marks, capability, isOwner } : null}>
      <TitleMarkerProvider ready={enabled && marks.ready ? READY_WORDS[kind] : null}>{children}</TitleMarkerProvider>
    </TaskLiveContext.Provider>
  );
}

/** The small navy dot a lifecycle tab carries when it has something new. */
export function NewContentDot() {
  return (
    <>
      <span aria-hidden="true" className="inline-block size-1.5 flex-none rounded-full bg-navy" />
      <span className="sr-only">New content</span>
    </>
  );
}

/** The tab dots for the live layer's marks, merged into the tab items. */
export function withTabMarks<T extends { tab: string; marker?: ReactNode }>(items: T[], marks: Marks | null): T[] {
  if (marks === null) return items;
  return items.map((item) =>
    item.marker === undefined && ((item.tab === "result" && marks.result) || (item.tab === "sources" && marks.sources))
      ? { ...item, marker: <NewContentDot /> }
      : item,
  );
}

const STRIP_CLASS = "flex min-h-9 shrink-0 items-center gap-2 border-b border-line bg-paper px-6 py-2 text-meta max-md:px-4";

/**
 * The run strip (task 058, N12, D8): under the lifecycle tabs on every tab
 * but Agent, the run's status in one line — the current row, what it is
 * doing, the elapsed time. Status only: no link and no mark, except the
 * finish ("Report ready · Read it →"), the one link it ever carries. While a
 * check-in waits it turns orange.
 */
export function RunStrip() {
  const live = useTaskLive();
  const stream = live?.stream;
  const run = stream?.run ?? null;
  const status = run?.status;
  const ticking = status === "running" || status === "paused";
  const nowMs = useNow(ticking);
  const rows = cardRows(stream?.stages ?? [], stream?.plan?.plan, status);
  const row = currentRow(rows);
  const tick = row !== null && row.state === "progress" ? rowLiveness(row, stream?.liveness) : undefined;
  const fresh = useFreshness(tick?.occurredAt);

  if (live === null || stream === undefined || run === null || live.tab === "agent" || live.tab === null) return null;
  const kind = walkKind(live.capability, stream.stages);
  const elapsed = formatMinutes(elapsedSeconds(run.startedAt, ticking ? undefined : run.endedAt, nowMs));

  if (isFinished(status)) {
    if (!live.marks.ready) return null;
    return (
      <p className={cn(STRIP_CLASS, "text-[#0c6b5a]")}>
        <StatusDot tone="complete" />
        <span className="min-w-0 truncate">
          {READY_WORDS[kind]} ·{" "}
          <Link to={resultHref(live.taskId, kind)} className="font-semibold text-[#0c6b5a] underline-offset-[3px] hover:underline">
            Read it →
          </Link>
        </span>
      </p>
    );
  }
  if (!ticking) return null;

  if (status === "paused" || stream.pendingCheckIn !== null) {
    const words =
      live.isOwner
        ? "Paused · a check-in is waiting on you"
        : ["Paused", row?.label, elapsed].filter((part): part is string => Boolean(part)).join(" · ");
    return (
      <p className={cn(STRIP_CLASS, "text-navy")}>
        <StatusDot tone="paused" />
        <span className="min-w-0 truncate">
          <Figures text={scrub(words)} />
        </span>
      </p>
    );
  }

  const parts = [row?.label, rowDetail(tick, { short: true })].filter((part): part is string => Boolean(part));
  return (
    <p className={cn(STRIP_CLASS, "text-navy")}>
      <StatusDot tone="running" className={cn(fresh && "anim-breathe")} />
      {/* A long line truncates its words; the elapsed time stays in view. */}
      <span className="flex min-w-0 whitespace-pre">
        <span className="min-w-0 truncate">
          <Figures text={scrub(parts.join(" · "))} />
        </span>
        {elapsed !== "" && (
          <span className="shrink-0">
            {parts.length > 0 ? " · " : ""}
            <Figures text={elapsed} />
          </span>
        )}
      </span>
    </p>
  );
}
