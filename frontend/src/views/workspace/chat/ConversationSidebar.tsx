import { useState } from "react";

import { COPY } from "../../../lib/vocabulary";
import { ConversationList, type ConversationRow } from "./ConversationList";
import { ConversationRail } from "./ConversationRail";
import { useConversations } from "../../../api/queries";
import { recentChats, taskAgentConversationId } from "./conversationState";
import { PanelIcon, PlusIcon } from "./icons";

const STORAGE_KEY = "policy-atlas:chats-sidebar";

/** The reader's last choice, per browser; shut until they open it. */
function readInitialOpen(): boolean {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "open") return true;
    if (stored === "shut") return false;
  } catch {
    // Storage blocked: fall through to the viewport default.
  }
  // Shut by default (owner, 2026-09-05): the conversation gets the screen
  // until the reader asks for the list.
  return false;
}

function storeOpen(open: boolean) {
  try {
    localStorage.setItem(STORAGE_KEY, open ? "open" : "shut");
  } catch {
    // Best effort only.
  }
}

/** The Agent tab's left column: every conversation in the Task (038 V8,
 *  owner ruling 2026-09-05), collapsible to a slim rail.
 *
 * Selection is the route's own `?chat=` param, which the other tabs' overlay
 * shares — so a chat opened here is the chat that opens there. The Task
 * Agent carries no id in the URL: choosing it clears the param.
 *
 * Args:
 *   props: The owning task, the id the main view is showing (the Task Agent
 *     when the param is clear), and `onSelect`, called with the conversation
 *     to show — `null` for the Task Agent.
 *
 * Returns:
 *   Open: the toggle and New chat above the shared conversation list. Shut: a
 *   rail carrying the toggle, New chat and the Task Agent.
 */
export function ConversationSidebar({
  taskId,
  selectedId,
  onSelect,
  onNewChat,
  chatsEnabled,
}: {
  taskId: string;
  selectedId: string | null;
  onSelect: (conversationId: string | null) => void;
  /** Opens a draft chat (nothing is persisted until its first message). */
  onNewChat: () => void;
  /** False until the task has a result — there is no evidence to ask about
   *  before then, so New chat is offered but disabled, with the reason. */
  chatsEnabled: boolean;
}) {
  const conversations = useConversations(taskId, { status: "active" });
  const rows = conversations.data?.data ?? [];
  // The main view marks the Task Agent by its planning id; the rail has no
  // rows to compare against, so it resolves the same id here.
  const onTaskAgent = selectedId === null || selectedId === taskAgentConversationId(rows);
  const [open, setOpen] = useState(readInitialOpen);
  const toggle = () => {
    setOpen((current) => {
      storeOpen(!current);
      return !current;
    });
  };

  const openRow = (row: ConversationRow) => {
    // Any planning row resolves to the Task Agent: the pane renders the
    // Task's planning thread, never one lineage in isolation, so an id in
    // the URL would claim more than the view delivers.
    if (row.kind === "planning") return onSelect(null);
    onSelect(row.id);
  };
  const newChatTitle = chatsEnabled ? COPY.newChat : COPY.newChatUnavailable;

  const toggleButton = (
    <button
      type="button"
      aria-label={open ? "Hide chats" : "Show chats"}
      aria-expanded={open}
      aria-controls="chats-sidebar-list"
      title={open ? "Hide chats" : "Show chats"}
      onClick={toggle}
      className="pressable flex h-8 w-8 shrink-0 items-center justify-center text-grey hover:bg-blue-tint-2 hover:text-navy focus-visible:outline-2 focus-visible:outline-blue"
    >
      <PanelIcon size={16} />
    </button>
  );

  if (!open) {
    return (
      <ConversationRail
        toggleLabel="Show chats"
        expanded={false}
        onToggle={toggle}
        onNewChat={onNewChat}
        chatsEnabled={chatsEnabled}
        onTaskAgent={onTaskAgent}
        onSelectTaskAgent={() => onSelect(null)}
        recent={recentChats(rows)}
        currentId={selectedId}
        onSelectChat={onSelect}
        className="border-b px-2 py-1.5 lg:h-full lg:w-12 lg:flex-col lg:border-b-0 lg:border-r lg:px-0 lg:py-2"
      />
    );
  }

  return (
    <aside
      aria-label="Chats"
      className="flex w-full shrink-0 flex-col overflow-hidden border-b border-line bg-paper-2 lg:h-full lg:w-72 lg:border-b-0 lg:border-r"
    >
      <div className="flex shrink-0 items-center justify-between px-2 pt-2 pb-1">
        {toggleButton}
        <button
          type="button"
          title={newChatTitle}
          disabled={!chatsEnabled}
          onClick={onNewChat}
          className="pressable flex h-8 items-center gap-1.5 px-2.5 text-meta font-semibold text-navy hover:bg-blue-tint-2 focus-visible:outline-2 focus-visible:outline-blue disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent"
        >
          <PlusIcon size={14} />
          {COPY.newChat}
        </button>
      </div>
      {/* Narrow viewports stack the list above the conversation and cap its
          height; from `lg` it is the full-height column. */}
      <div id="chats-sidebar-list" className="max-h-72 min-h-0 flex-1 overflow-y-auto px-1.5 pb-3 lg:max-h-none">
        <ConversationList taskId={taskId} onOpen={openRow} selectedId={selectedId} />
      </div>
    </aside>
  );
}
