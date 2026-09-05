import { COPY } from "../../../lib/vocabulary";
import { cn } from "../../../ui/brand/cn";
import { FoldMarkIcon } from "../../../ui/brand/FoldMarkIcon";
import { PanelIcon, PlusIcon } from "./icons";

const RAIL_BUTTON =
  "pressable flex h-8 w-8 shrink-0 items-center justify-center text-grey hover:bg-blue-tint-2 hover:text-navy focus-visible:outline-2 focus-visible:outline-blue disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent";

/** The slim conversation rail: one object on every task tab (owner request,
 *  2026-09-05). On the Agent tab it is the sidebar shut; on the other tabs
 *  it is the Agent overlay shut — the toggle expands into whichever the tab
 *  has. It carries the toggle, New chat and the Task Agent.
 *
 * Args:
 *   props: `toggleLabel` names what the toggle opens ("Show chats" on the
 *     Agent tab, "Open the Agent" elsewhere); `expanded` is the toggle's
 *     `aria-expanded`; `toggleDisabled` holds it until the data it needs has
 *     resolved; `onTaskAgent` marks the Task Agent as current; `className`
 *     sets the rail's geometry (a column, or a bar that becomes a column at
 *     `lg`).
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
    </aside>
  );
}
