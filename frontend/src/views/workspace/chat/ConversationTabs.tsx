import { useState } from "react";

import { useConversations } from "../../../api/queries";
import { scrub } from "../../../lib/scrub";
import { COPY } from "../../../lib/vocabulary";
import { FoldMarkIcon } from "../../../ui/brand/FoldMarkIcon";
import { ChatsIcon } from "./ChatsIcon";
import { CloseIcon, PlusIcon } from "./icons";
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
 *   props: Task, planning lifecycle, library-open callback, and an optional
 *     close control used when the strip sits in the side panel.
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
}: {
  taskId: string;
  entryArtefactId?: string | null;
  planningClosed: boolean;
  onOpenLibrary: () => void;
  onClose?: () => void;
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
      setActiveConversation(tabs[index + 1]?.id ?? tabs[index - 1]?.id ?? taskAgentId);
    }
  };

  return (
    <nav aria-label="Conversations" className="flex min-w-0 items-stretch border-b border-line bg-paper-2">
      {/* The Task Agent is pinned first — its label is the only marker it
          carries (contract § V8, fork F4); the brand mark echoes the Agent
          tab's sidebar row. */}
      <button
        type="button"
        onClick={() => setActiveConversation(taskAgentId)}
        className={`flex min-w-0 items-center gap-2 border-b-2 px-3 py-2 text-meta font-semibold ${planningActive ? "border-blue text-navy" : "border-transparent text-grey hover:bg-blue-tint-2 hover:text-navy"}`}
      >
        <FoldMarkIcon size={10} className={planningClosed ? "opacity-40" : undefined} />
        <span className="truncate">{COPY.taskAgent}</span>
      </button>
      {tabs.map((chat) => (
        <div key={chat.id} className={`group flex min-w-0 items-center border-b-2 ${activeConversationId === chat.id ? "border-blue" : "border-transparent"}`}>
          <button type="button" onClick={() => select(chat.id)} className={`min-w-0 px-3 py-2 text-meta font-semibold hover:bg-blue-tint-2 ${activeConversationId === chat.id ? "text-navy" : "text-grey hover:text-navy"}`}>
            <span className="block max-w-32 truncate">{scrub(chat.title)}</span>
          </button>
          <button type="button" aria-label={`Archive ${chat.title}`} title="Archive" onClick={() => void close(chat.id)} className="mr-1 hidden h-6 w-6 items-center justify-center text-grey hover:text-navy group-hover:flex focus-visible:flex">
            <CloseIcon size={12} />
          </button>
        </div>
      ))}
      <button type="button" aria-label={COPY.newChat} title={COPY.newChat} onClick={() => void newChat()} className="flex items-center px-2.5 text-grey hover:bg-blue-tint-2 hover:text-navy focus-visible:outline-2 focus-visible:outline-blue">
        <PlusIcon size={14} />
      </button>
      <button type="button" aria-label="Chats" title="Chats" onClick={onOpenLibrary} className="ml-auto flex items-center px-2.5 text-grey hover:bg-blue-tint-2 hover:text-navy focus-visible:outline-2 focus-visible:outline-blue">
        <ChatsIcon size={15} />
      </button>
      {onClose !== undefined && (
        <button
          type="button"
          aria-label="Close chat panel"
          title="Close"
          onClick={onClose}
          className="flex items-center px-2.5 text-grey hover:bg-blue-tint-2 hover:text-navy focus-visible:outline-2 focus-visible:outline-blue"
        >
          <CloseIcon size={14} />
        </button>
      )}
    </nav>
  );
}
