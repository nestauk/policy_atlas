import type { ReactNode } from "react";

import { Figures } from "../../../lib/figures";
import { useNow } from "../../../lib/freshness";
import { COPY } from "../../../lib/vocabulary";
import { scrub } from "../../../lib/scrub";
import { cn } from "../../../ui/brand/cn";
import { LiveMark } from "../../../ui/brand/Card";
import { FoldMarkIcon } from "../../../ui/brand/FoldMarkIcon";
import { Tooltip, TooltipProvider } from "../../../ui/radix/Tooltip";
import { elapsedSeconds, formatMinutes } from "../runProgress";
import { ChatIcon, PanelIcon, PlusIcon } from "./icons";

const RAIL_BUTTON =
  "pressable flex h-8 w-8 shrink-0 items-center justify-center text-grey hover:bg-blue-tint-2 hover:text-navy focus-visible:outline-2 focus-visible:outline-blue disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent";

/** The Task Agent's mark in the rail, still or turning. */
const RAIL_MARK_SIZE = 11;

/** How many recent chats the rail marks. */
export const RAIL_RECENT = 4;

/** Icon buttons name themselves on hover this fast (owner, 2026-09-05: the
 *  browser's own `title` delay is too slow to be useful). */
export const RAIL_TOOLTIP_DELAY_MS = 150;

/** Rail and overlay tooltips originate from the left edge, so they carry the
 *  system's 2px blue leading rule; tooltips in running text do not. */
export const RAIL_TOOLTIP_CLASS = "border-l-2 border-l-blue";

/** The run's elapsed time under the turning mark, to the minute, in grey
 *  tabular figures (task 058, owner round 6). Caption size: Meta's "12 min"
 *  nearly fills the 48 px rail and "1 h 4 min" does not fit, so the figure is
 *  set a step smaller and an hour-long run wraps after its hours ("1 h" over
 *  "4 min"); each number keeps its unit. Ticks every 15 s, enough for a
 *  minute figure. */
function RailElapsed({ startedAt }: { startedAt: string }) {
  const nowMs = useNow(true, 15_000);
  const text = formatMinutes(elapsedSeconds(startedAt, undefined, nowMs)).replace(/(\d) /g, "$1\u00A0");
  return (
    // Tabular digits only: the tabular feature widens the space too.
    <span data-testid="rail-elapsed" className="-mt-0.5 block w-full px-0.5 text-center text-caption leading-tight text-grey">
      <Figures text={text} />
    </span>
  );
}

/** One recent chat on the rail. */
export type RailChat = { id: string; title: string };

/** An icon-only rail button: the label is its accessible name and its quick
 *  tooltip. Disabled buttons still explain themselves (the tooltip wraps a
 *  span so the pointer reaches it). */
function RailButton({
  label,
  tip = label,
  disabled = false,
  current = false,
  onClick,
  children,
  ...aria
}: {
  label: string;
  /** The tooltip, when it should say more than the name (a disabled reason);
   *  `null` for none (the toggle's icon is self-evident — owner). */
  tip?: string | null;
  disabled?: boolean;
  current?: boolean;
  onClick: () => void;
  children: ReactNode;
  "aria-expanded"?: boolean;
}) {
  const button = (
    <button
      type="button"
      aria-label={label}
      aria-current={current ? "true" : undefined}
      disabled={disabled}
      onClick={onClick}
      className={cn(
        RAIL_BUTTON,
        current && "bg-blue-tint text-navy hover:bg-blue-tint",
      )}
      {...aria}
    >
      {children}
    </button>
  );
  if (tip === null) return button;
  return (
    <Tooltip content={tip} side="right" className={RAIL_TOOLTIP_CLASS}>
      {disabled ? <span className="inline-flex">{button}</span> : button}
    </Tooltip>
  );
}

/** The slim conversation rail: one object on every task tab (owner request,
 *  2026-09-05). On the Agent tab it is the sidebar shut; on the other tabs
 *  it is the Agent overlay shut — the toggle expands into whichever the tab
 *  has. It carries the toggle, New chat, the Task Agent and the most recent
 *  chats (one bubble each, the title as tooltip).
 *
 * Args:
 *   props: `toggleLabel` names what the toggle opens ("Show chats" on the
 *     Agent tab, "Open the Agent" elsewhere); `expanded` is the toggle's
 *     `aria-expanded`; `toggleDisabled` holds it until the data it needs has
 *     resolved; `onTaskAgent` marks the Task Agent as current; `recent` and
 *     `currentId` are the chat marks and the one on show; `className` sets
 *     the rail's geometry (a column, or a bar that becomes a column at `lg`);
 *     `runLive` turns the Task Agent's mark while a run is live (task 058,
 *     owner 2026-11-05: the fold mark, at the rail's own size so nothing
 *     jumps); `runWords` and `runStartedAt` give the mark its hover words
 *     and the elapsed figure under it, and `besideTaskAgent` sits at the
 *     mark's height (the step note; owner, round 6).
 */
export function ConversationRail({
  toggleLabel,
  expanded,
  toggleDisabled = false,
  onToggle,
  onNewChat,
  chatsEnabled,
  onTaskAgent,
  onSelectTaskAgent,
  recent = [],
  currentId = null,
  onSelectChat,
  className,
  runLive = false,
  runWords,
  runStartedAt,
  besideTaskAgent,
}: {
  toggleLabel: string;
  expanded: boolean;
  toggleDisabled?: boolean;
  onToggle: () => void;
  onNewChat: () => void;
  chatsEnabled: boolean;
  onTaskAgent: boolean;
  onSelectTaskAgent: () => void;
  recent?: readonly RailChat[];
  currentId?: string | null;
  onSelectChat?: (conversationId: string) => void;
  className?: string;
  runLive?: boolean;
  /** While a run is live: the trace header's words, which the mark's
   *  tooltip and accessible name carry ("Searching and screening · 184 found
   *  so far"). */
  runWords?: string;
  /** While a run is live: when it started, for the elapsed figure under the mark. */
  runStartedAt?: string;
  /** Rendered beside the Task Agent mark, at its height (the step note). */
  besideTaskAgent?: ReactNode;
}) {
  const live = runLive && runWords !== undefined && runWords !== "";
  const taskAgentName = live ? `${COPY.taskAgent} · ${runWords}` : COPY.taskAgent;
  const elapsedFrom = runLive && runStartedAt !== undefined && runStartedAt !== "" ? runStartedAt : null;
  const showElapsed = elapsedFrom !== null;
  return (
    <TooltipProvider delayDuration={RAIL_TOOLTIP_DELAY_MS}>
      <aside
        aria-label="Chats"
        className={cn("flex shrink-0 items-center gap-1 border-line bg-paper-2", className)}
      >
        <RailButton label={toggleLabel} tip="Open sidebar" aria-expanded={expanded} disabled={toggleDisabled} onClick={onToggle}>
          <PanelIcon size={16} />
        </RailButton>
        <RailButton
          label={COPY.newChat}
          tip={chatsEnabled ? COPY.newChat : COPY.newChatUnavailable}
          disabled={!chatsEnabled}
          onClick={onNewChat}
        >
          <PlusIcon size={16} />
        </RailButton>
        {/* The Task Agent mark, and while a run is live the run's elapsed
            time under it (owner, round 6): a glance at the rail from any tab
            says the run is moving and for how long. */}
        {/* With the figure the column spans the rail, so the figure wraps
            inside the rail's 48 px instead of widening it. */}
        <div className={cn("relative flex flex-col items-center", showElapsed && "w-full")}>
          <RailButton label={taskAgentName} current={onTaskAgent} onClick={onSelectTaskAgent}>
            {runLive ? <LiveMark size={RAIL_MARK_SIZE} /> : <FoldMarkIcon size={RAIL_MARK_SIZE} />}
          </RailButton>
          {elapsedFrom !== null && <RailElapsed startedAt={elapsedFrom} />}
          {besideTaskAgent}
        </div>
        {recent.map((chat) => (
          <RailButton
            key={chat.id}
            label={scrub(chat.title)}
            current={chat.id === currentId}
            onClick={() => onSelectChat?.(chat.id)}
          >
            <ChatIcon size={15} />
          </RailButton>
        ))}
      </aside>
    </TooltipProvider>
  );
}
