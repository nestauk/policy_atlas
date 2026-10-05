import type { ReactNode } from "react";

import { COPY } from "../../../lib/vocabulary";
import { scrub } from "../../../lib/scrub";
import { cn } from "../../../ui/brand/cn";
import { FoldMarkIcon } from "../../../ui/brand/FoldMarkIcon";
import { Tooltip, TooltipProvider } from "../../../ui/radix/Tooltip";
import { ChatIcon, PanelIcon, PlusIcon } from "./icons";

const RAIL_BUTTON =
  "pressable flex h-8 w-8 shrink-0 items-center justify-center text-grey hover:bg-blue-tint-2 hover:text-navy focus-visible:outline-2 focus-visible:outline-blue disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent";

/** How many recent chats the rail marks. */
export const RAIL_RECENT = 4;

/** Icon buttons name themselves on hover this fast (owner, 2026-09-05: the
 *  browser's own `title` delay is too slow to be useful). */
export const RAIL_TOOLTIP_DELAY_MS = 150;

/** Rail and overlay tooltips originate from the left edge, so they carry the
 *  system's 2px blue leading rule; tooltips in running text do not. */
export const RAIL_TOOLTIP_CLASS = "border-l-2 border-l-blue";

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
 *     the rail's geometry (a column, or a bar that becomes a column at `lg`).
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
}) {
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
        <RailButton label={COPY.taskAgent} current={onTaskAgent} onClick={onSelectTaskAgent}>
          <FoldMarkIcon size={11} />
        </RailButton>
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
