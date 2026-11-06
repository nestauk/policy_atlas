import { useState, useSyncExternalStore } from "react";
import { Link, useLocation, useNavigate } from "react-router";

import { useConversations } from "../api/queries";
import { Figures } from "../lib/figures";
import { useNow } from "../lib/freshness";
import { createInitialRunStreamState } from "../store";
import { LiveMark, StatusMark } from "../ui/brand/Card";
import { cn } from "../ui/brand/cn";
import { useMountedTraces, useTaskLive } from "./taskLive";
import {
  isTaskAgentConversation,
  taskAgentConversationId,
  useActiveConversation,
} from "./workspace/chat/conversationState";
import { cardRows, currentRow, elapsedSeconds, formatElapsed, rowLink, walkKind } from "./workspace/runProgress";
import { useRunWords } from "./workspace/runWords";

/** A stream with no run, for the shell before the live layer is enabled. */
const NO_STREAM = createInitialRunStreamState();

/** The separator between items. A no-break space binds each "·" to the word
 *  before it, so a separator never starts a line (lead, 2026-11-05). */
const SEP = " · ";

/** The sidebar shows from `md` up (`ChatSidePanel` is `max-md:hidden`);
 *  below it the Agent tab is the way to the agent. */
const SIDEBAR_QUERY = "(min-width: 48rem)";

function sidebarAvailable(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.(SIDEBAR_QUERY).matches === true;
}

function subscribeSidebar(onChange: () => void): () => void {
  const query = typeof window === "undefined" ? undefined : window.matchMedia?.(SIDEBAR_QUERY);
  query?.addEventListener?.("change", onChange);
  return () => query?.removeEventListener?.("change", onChange);
}

/** Whether the screen is wide enough for the sidebar, kept current. */
function useSidebarAvailable(): boolean {
  return useSyncExternalStore(subscribeSidebar, sidebarAvailable, () => false);
}

type Shown = {
  head: string;
  rest: string;
  words: string;
  paused: boolean;
  elapsed: string;
  key: string;
  link: { href: string; label: string } | null;
};

/** Whether the reader is already on the view a link opens: the themes are
 *  the Sources tab's index, so only its own path counts; any other view
 *  counts with whatever sits under it. A link that names a Result view
 *  (`?view=baseline`, round 10) counts only on that view, or on the Result
 *  tab with no view named: a baseline walk runs only while the task has no
 *  longlist (the plan offers no rebuild after one), so the Result tab is
 *  showing the baseline then. */
export function onLinkedView(pathname: string, href: string, search = ""): boolean {
  const path = pathname.replace(/\/+$/, "");
  const [hrefPath, hrefQuery = ""] = href.split("?");
  const onPath = hrefPath.endsWith("/sources")
    ? path === hrefPath
    : path === hrefPath || path.startsWith(`${hrefPath}/`);
  const wanted = new URLSearchParams(hrefQuery).get("view");
  if (!onPath || wanted === null) return onPath;
  const shown = new URLSearchParams(search).get("view");
  return shown === null || shown === wanted;
}

/** What changed since the last render, so a tab switch can set the status bar at
 *  a cut while a run starting or ending, or the sidebar taking the Task
 *  Agent, still eases it (the animation sweep's entry 9). */
type Cause = { open: boolean; ticking: boolean; agentInSidebar: boolean; instant: boolean };

/**
 * The run status bar (task 058, owner rounds 7 and 8): under the lifecycle tabs
 * on every tab but Agent, while a run is live or paused, and nowhere else.
 * It starts after the rail, so it belongs to the page beside the sidebar
 * (the shell places it at the top of the page's column). One line on paper
 * over a hairline: the turning fold mark (the orange square while a
 * check-in waits) on the first line, the step's label in navy semibold and
 * what it is doing in grey, and the run's elapsed time at the right in grey
 * tabular figures.
 *
 * The status bar is a bar of two controls (owner, round 9). Its words are the way
 * to the agent (owner, round 8, reversing contract D8's "status only"): they
 * open the Task Agent in the sidebar, or the Agent tab below `md`, where the
 * sidebar does not show. After the time, the step in progress's view
 * ("Sources →", "Landscape →", "Themes →", "Report →") while the reader is
 * not on it.
 *
 * It opens and closes over 200 ms on the strong ease-out when the run starts
 * or ends or the sidebar takes the Task Agent, so the page eases rather than
 * jumps; on a tab switch it is set at a cut. Its words rise in when the step
 * changes. Both hold still under reduced motion. Its live region is quiet while a run trace is
 * mounted (the sidebar's), so one change is announced once.
 */
export function RunStatusBar() {
  const live = useTaskLive();
  const stream = live?.stream ?? NO_STREAM;
  const run = stream.run;
  const ticking = run?.status === "running" || run?.status === "paused";
  const taskId = live?.taskId ?? "";
  const conversations = useConversations(taskId, { status: "active" });
  const { activeConversationId, setActiveConversation } = useActiveConversation();
  const wide = useSidebarAvailable();
  // While the Task Agent is open in the sidebar its trace says the same
  // words, so the status bar steps aside; it returns when the sidebar shuts or
  // shows another conversation (lead, round 8).
  const agentInSidebar = wide && isTaskAgentConversation(activeConversationId, conversations.data?.data ?? []);
  const open = live !== null && live.tab !== null && live.tab !== "agent" && ticking && !agentInSidebar;
  const nowMs = useNow(open);
  const { words, row, paused } = useRunWords(stream, live?.isOwner ?? false);
  const traces = useMountedTraces();
  const navigate = useNavigate();
  const { pathname, search } = useLocation();

  // A tab switch is navigation, seen tens of times a day: the status bar opens or
  // closes at a cut then. It eases when the run starts or ends or the
  // sidebar takes the Task Agent (sweep entry 9).
  const [cause, setCause] = useState<Cause>({ open, ticking, agentInSidebar, instant: true });
  if (cause.open !== open) {
    setCause({
      open,
      ticking,
      agentInSidebar,
      instant: cause.ticking === ticking && cause.agentInSidebar === agentInSidebar,
    });
  } else if (cause.ticking !== ticking || cause.agentInSidebar !== agentInSidebar) {
    setCause({ ...cause, ticking, agentInSidebar });
  }

  // The step in progress's own view (owner, round 9): "Sources →",
  // "Landscape →", "Themes →", "Report →" at the status bar's right end, the same
  // link the trace's running row carries, hidden while the reader is there.
  const rows = cardRows(stream.stages, stream.plan?.plan, run?.status);
  const progress = currentRow(rows);
  const target =
    progress !== null && progress.state === "progress" && !paused
      ? rowLink(progress, rows, taskId, walkKind(live?.capability, stream.stages), false)
      : null;
  const here =
    target !== null &&
    (onLinkedView(pathname, target.href, search) || (target.href.endsWith("/result") && live?.tab === "result"));
  const link = target !== null && !here ? target : null;

  const [head = "", ...restParts] = words.split(" · ");
  const now: Shown | null =
    open && run !== null
      ? {
          head,
          rest: restParts.join(" · "),
          words,
          paused,
          elapsed: formatElapsed(elapsedSeconds(run.startedAt, undefined, nowMs)),
          key: paused ? "paused" : (row?.key ?? "start"),
          link,
        }
      : null;
  // Kept as the status bar closes, so it folds away with its last words.
  const [last, setLast] = useState<Shown | null>(now);
  if (
    now !== null &&
    (last === null ||
      now.words !== last.words ||
      now.elapsed !== last.elapsed ||
      now.key !== last.key ||
      now.link?.href !== last.link?.href)
  ) {
    setLast(now);
  }
  const shown = now ?? last;

  const openTaskAgent = () => {
    if (sidebarAvailable()) {
      setActiveConversation(taskAgentConversationId(conversations.data?.data ?? []));
    } else {
      void navigate(`/tasks/${taskId}`);
    }
  };

  return (
    <>
      <div
        data-testid="run-status-bar"
        data-open={open}
        aria-hidden={open ? undefined : true}
        className={cn(
          "grid shrink-0 transition-[grid-template-rows,opacity] duration-200 ease-[var(--ease-out-strong)] motion-reduce:transition-none",
          open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0",
          cause.instant && "transition-none",
        )}
      >
        <div className="min-h-0 overflow-hidden">
          {shown !== null && (
            // Two controls on one bar (owner, round 9): the words open the
            // Task Agent; the link after the time opens the step's view.
            <div className="flex items-stretch border-b border-line bg-paper text-meta leading-[1.55rem]">
            <button
              type="button"
              tabIndex={open ? undefined : -1}
              aria-label={`Open the Task Agent: ${shown.words}`}
              onClick={openTaskAgent}
              className={cn(
                "flex min-w-0 flex-1 cursor-pointer items-start gap-2 py-2.5 pl-6 text-left transition-colors duration-150 hover:bg-paper-2 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-blue max-md:pl-4",
                shown.link === null ? "pr-6 max-md:pr-4" : "pr-3",
              )}
            >
              {/* The mark sits on the first line of the words. */}
              <span aria-hidden="true" className="flex h-[1lh] w-3.5 shrink-0 items-center justify-center">
                {shown.paused ? <StatusMark tone="paused" /> : <LiveMark />}
              </span>
              <span key={shown.key} className="anim-rise min-w-0 flex-1 truncate">
                <span className="font-semibold text-navy">
                  <Figures text={shown.head} />
                </span>
                {shown.rest !== "" && (
                  <span className="text-grey">
                    {SEP}
                    <Figures text={shown.rest.replaceAll(" · ", SEP)} />
                  </span>
                )}
              </span>
              <span className="shrink-0 whitespace-nowrap text-right text-grey">
                <Figures text={shown.elapsed} />
              </span>
            </button>
            {shown.link !== null && (
              <Link
                to={shown.link.href}
                tabIndex={open ? undefined : -1}
                className="flex shrink-0 items-start whitespace-nowrap py-2.5 pr-6 pl-3 font-semibold text-blue no-underline transition-colors duration-150 hover:bg-paper-2 hover:underline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-blue max-md:pr-4"
              >
                {shown.link.label} →
              </Link>
            )}
            </div>
          )}
        </div>
      </div>
      {/* The words for a screen reader, without the ticking clock; quiet
          while a run trace (the sidebar's) announces the same words. */}
      {traces === 0 && (
        <p role="status" aria-live="polite" className="sr-only">
          {open ? words : ""}
        </p>
      )}
    </>
  );
}
