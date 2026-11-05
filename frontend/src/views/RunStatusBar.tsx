import { useState, useSyncExternalStore } from "react";
import { useNavigate } from "react-router";

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
import { elapsedSeconds, formatElapsed } from "./workspace/runProgress";
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

type Shown = { head: string; rest: string; words: string; paused: boolean; elapsed: string; key: string };

/**
 * The run strip (task 058, owner rounds 7 and 8): under the lifecycle tabs
 * on every tab but Agent, while a run is live or paused, and nowhere else.
 * It starts after the rail, so it belongs to the page beside the sidebar
 * (the shell places it at the top of the page's column). One line on paper
 * over a hairline: the turning fold mark (the orange square while a
 * check-in waits) on the first line, the step's label in navy semibold and
 * what it is doing in grey, and the run's elapsed time at the right in grey
 * tabular figures.
 *
 * The whole strip is the way to the agent (owner, round 8, reversing
 * contract D8's "status only"): it opens the Task Agent in the sidebar, or
 * the Agent tab below `md`, where the sidebar does not show.
 *
 * It opens and closes over 200 ms on the strong ease-out, so the page eases
 * rather than jumps, and its words rise in when the step changes; both hold
 * still under reduced motion. Its live region is quiet while a run trace is
 * mounted (the sidebar's), so one change is announced once.
 */
export function RunStrip() {
  const live = useTaskLive();
  const stream = live?.stream ?? NO_STREAM;
  const run = stream.run;
  const ticking = run?.status === "running" || run?.status === "paused";
  const taskId = live?.taskId ?? "";
  const conversations = useConversations(taskId, { status: "active" });
  const { activeConversationId, setActiveConversation } = useActiveConversation();
  const wide = useSidebarAvailable();
  // While the Task Agent is open in the sidebar its trace says the same
  // words, so the strip steps aside; it returns when the sidebar shuts or
  // shows another conversation (lead, round 8).
  const agentInSidebar = wide && isTaskAgentConversation(activeConversationId, conversations.data?.data ?? []);
  const open = live !== null && live.tab !== null && live.tab !== "agent" && ticking && !agentInSidebar;
  const nowMs = useNow(open);
  const { words, row, paused } = useRunWords(stream, live?.isOwner ?? false);
  const traces = useMountedTraces();
  const navigate = useNavigate();

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
        }
      : null;
  // Kept as the strip closes, so it folds away with its last words.
  const [last, setLast] = useState<Shown | null>(now);
  if (now !== null && (last === null || now.words !== last.words || now.elapsed !== last.elapsed || now.key !== last.key)) {
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
        data-testid="run-strip"
        data-open={open}
        aria-hidden={open ? undefined : true}
        className={cn(
          "grid shrink-0 transition-[grid-template-rows] duration-200 ease-[var(--ease-out-strong)] motion-reduce:transition-none",
          open ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
        )}
      >
        <div className="min-h-0 overflow-hidden">
          {shown !== null && (
            <button
              type="button"
              tabIndex={open ? undefined : -1}
              aria-label={`Open the Task Agent: ${shown.words}`}
              onClick={openTaskAgent}
              className="flex w-full cursor-pointer items-start gap-2 border-b border-line bg-paper px-6 py-2.5 text-left text-meta leading-[1.55rem] transition-colors duration-150 hover:bg-paper-2 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-blue max-md:px-4"
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
