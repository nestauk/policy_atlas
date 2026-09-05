import { COPY } from "../../../lib/vocabulary";
import { scrub } from "../../../lib/scrub";
import { cn } from "../../../ui/brand/cn";
import { FoldMarkIcon } from "../../../ui/brand/FoldMarkIcon";
import { ChatsIcon } from "./ChatsIcon";
import { PanelIcon, PlusIcon } from "./icons";

const RAIL_BUTTON =
  "pressable flex h-8 w-8 shrink-0 items-center justify-center text-grey hover:bg-blue-tint-2 hover:text-navy focus-visible:outline-2 focus-visible:outline-blue disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent";

/** How many recent chats the rail marks. */
export const RAIL_RECENT = 4;

/** One recent chat on the rail. */
export type RailChat = { id: string; title: string; unread: boolean };

/** The slim conversation rail: one object on every task tab (owner request,
 *  2026-09-05). On the Agent tab it is the sidebar shut; on the other tabs
 *  it is the Agent overlay shut — the toggle expands into whichever the tab
 *  has. It carries the toggle, New chat, the Task Agent and the most recent
 *  chats (their initial, the title as tooltip, a dot for a reply the reader
 *  has not seen).
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
    <aside
      aria-label="Chats"
      className={cn("flex shrink-0 items-center gap-1 border-line bg-paper-2", className)}
    >
      <button
        type="button"
        aria-label={toggleLabel}
        aria-expanded={expanded}
        title={toggleLabel}
        disabled={toggleDisabled}
        onClick={onToggle}
        className={RAIL_BUTTON}
      >
        <PanelIcon size={16} />
      </button>
      <button
        type="button"
        aria-label={COPY.newChat}
        title={chatsEnabled ? COPY.newChat : COPY.newChatUnavailable}
        disabled={!chatsEnabled}
        onClick={onNewChat}
        className={RAIL_BUTTON}
      >
        <PlusIcon size={16} />
      </button>
      <button
        type="button"
        aria-label={COPY.taskAgent}
        title={COPY.taskAgent}
        aria-current={onTaskAgent ? "true" : undefined}
        onClick={onSelectTaskAgent}
        className={cn(
          "pressable flex h-8 w-8 shrink-0 items-center justify-center focus-visible:outline-2 focus-visible:outline-blue",
          onTaskAgent ? "bg-blue-tint" : "hover:bg-blue-tint-2",
        )}
      >
        <FoldMarkIcon size={11} />
      </button>
      {recent.map((chat) => {
        const title = scrub(chat.title);
        const current = chat.id === currentId;
        return (
          <button
            key={chat.id}
            type="button"
            aria-label={chat.unread ? `${title} — new reply` : title}
            title={title}
            aria-current={current ? "true" : undefined}
            onClick={() => onSelectChat?.(chat.id)}
            className={cn(
              "pressable relative flex h-8 w-8 shrink-0 items-center justify-center focus-visible:outline-2 focus-visible:outline-blue",
              current ? "bg-blue-tint text-navy" : "text-grey hover:bg-blue-tint-2 hover:text-navy",
            )}
          >
            <ChatsIcon size={15} />
            {chat.unread && (
              <span aria-hidden="true" className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-blue" />
            )}
          </button>
        );
      })}
    </aside>
  );
}
