import { useState } from "react";

import { useConversations } from "../../../api/queries";
import { scrub } from "../../../lib/scrub";
import { COPY } from "../../../lib/vocabulary";
import { ChatsIcon } from "./ChatsIcon";
import {
  addOpenChatTab,
  isPlanningConversation,
  openChatTabs,
  removeOpenChatTab,
  taskAgentConversationId,
  useActiveConversation,
  useConversationMutations,
} from "./conversationState";

/** Conversation switcher for the task's Agent overlay.
 *
 * Args:
 *   props: Task, planning lifecycle, library-open callback, an optional
 *     close control used when the strip sits in the side panel, and
 *     `onSelectTaskAgent` — supplied on the Agent tab, where the Task Agent
 *     already owns the main column and must not be opened here as well.
 *
 * Returns:
 *   The pinned Task Agent tab, session-local chat tabs, and library /
 *   new-chat actions.
 */
export function ConversationTabs({
  taskId,
  entryArtefactId = null,
  planningClosed,
  onOpenLibrary,
  onClose,
  onSelectTaskAgent,
}: {
  taskId: string;
  entryArtefactId?: string | null;
  planningClosed: boolean;
  onOpenLibrary: () => void;
  onClose?: () => void;
  onSelectTaskAgent?: () => void;
}) {
  const conversations = useConversations(taskId, { status: "active" });
  const { activeConversationId, setActiveConversation } = useActiveConversation();
  const { create, archive } = useConversationMutations(taskId);
  const [tabIds, setTabIds] = useState(() => openChatTabs(taskId));
  // Derive-state-during-render on a task switch (no effect roundtrip).
  const [tabsTaskId, setTabsTaskId] = useState(taskId);
  if (tabsTaskId !== taskId) {
    setTabsTaskId(taskId);
    setTabIds(openChatTabs(taskId));
  }

  const rows = conversations.data?.data ?? [];
  const taskAgentId = taskAgentConversationId(rows);
  const planningActive = isPlanningConversation(activeConversationId, rows);
  const activeChats = rows.filter((row) => row.kind === "chat");
  // A chat opened from the launcher or "+" can land in the URL before this
  // strip's local tabIds catch up — fold it in during render so the tab
  // exists on the first paint rather than after an effect.
  if (
    activeConversationId !== null &&
    !planningActive &&
    !tabIds.includes(activeConversationId)
  ) {
    addOpenChatTab(taskId, activeConversationId);
    setTabIds(openChatTabs(taskId));
  }
  const tabs = tabIds.flatMap((id) => {
    const chat = activeChats.find((candidate) => candidate.id === id);
    if (chat !== undefined) return [chat];
    if (id === activeConversationId && !planningActive) {
      return [{ id, title: "New chat" }];
    }
    return [];
  });

  // On the Agent tab the Task Agent is the main column, so selecting it here
  // hands off to that pane instead of binding `?chat=` to a second copy.
  const selectTaskAgent = onSelectTaskAgent ?? (() => setActiveConversation(taskAgentId));
  const select = (id: string) => {
    addOpenChatTab(taskId, id);
    setTabIds(openChatTabs(taskId));
    setActiveConversation(id);
  };
  const newChat = async () => {
    const blank = activeChats.find((chat) => chat.title === "New chat" && tabIds.includes(chat.id));
    if (blank !== undefined) return select(blank.id);
    const created = await create(entryArtefactId);
    select(created.id);
  };
  const close = async (id: string) => {
    const index = tabs.findIndex((chat) => chat.id === id);
    await archive(id);
    removeOpenChatTab(taskId, id);
    setTabIds(openChatTabs(taskId));
    if (activeConversationId === id) {
      const next = tabs[index + 1]?.id ?? tabs[index - 1]?.id;
      if (next === undefined) selectTaskAgent();
      else setActiveConversation(next);
    }
  };

  return (
    <nav aria-label="Conversations" className="flex min-w-0 items-stretch border-b border-line">
      {/* The Task Agent is pinned first — its label is the only marker it
          carries (contract § V8, fork F4). */}
      <button
        type="button"
        onClick={() => selectTaskAgent()}
        className={`flex min-w-0 items-center gap-2 px-3 py-2 text-meta font-semibold ${planningActive ? "border-b-2 border-blue text-navy" : "text-grey hover:bg-ground"}`}
      >
        <span aria-hidden="true" className={`h-2 w-2 rounded-full ${planningClosed ? "bg-line-2" : "bg-blue"}`} />
        <span className="truncate">{COPY.taskAgent}</span>
      </button>
      {tabs.map((chat) => (
        <div key={chat.id} className={`group flex min-w-0 items-center ${activeConversationId === chat.id ? "border-b-2 border-blue" : ""}`}>
          <button type="button" onClick={() => select(chat.id)} className="min-w-0 px-3 py-2 text-meta font-semibold text-navy hover:bg-ground">
            <span className="block max-w-32 truncate">{scrub(chat.title)}</span>
          </button>
          <button type="button" aria-label={`Archive ${chat.title}`} onClick={() => void close(chat.id)} className="mr-1 hidden px-1 text-grey hover:text-navy group-hover:block focus:block">×</button>
        </div>
      ))}
      <button type="button" aria-label="New chat" onClick={() => void newChat()} className="px-3 text-meta font-bold text-blue hover:bg-blue-tint">+</button>
      <button type="button" aria-label="Chats" title="Chats" onClick={onOpenLibrary} className="ml-auto px-2.5 text-blue hover:bg-blue-tint">
        <ChatsIcon size={15} />
      </button>
      {onClose !== undefined && (
        <button
          type="button"
          aria-label="Close chat panel"
          title="Close"
          onClick={onClose}
          className="px-2.5 text-grey hover:text-navy"
        >
          ×
        </button>
      )}
    </nav>
  );
}
