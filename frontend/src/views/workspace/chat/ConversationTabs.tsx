import { useState } from "react";

import { useConversations } from "../../../api/queries";
import { scrub } from "../../../lib/scrub";
import { ChatsIcon } from "./ChatsIcon";
import {
  addOpenChatTab,
  isPlanningConversation,
  openChatTabs,
  planningConversationId,
  removeOpenChatTab,
  useActiveConversation,
  useConversationMutations,
} from "./conversationState";

/** Conversation switcher for the project chat overlay.
 *
 * Args:
 *   props: Project, planning lifecycle, library-open callback, and an
 *     optional close control used when the strip sits in the side panel.
 *
 * Returns:
 *   A planning tab, session-local chat tabs, and library / new-chat actions.
 */
export function ConversationTabs({
  projectId,
  entryArtefactId = null,
  planningClosed,
  onOpenLibrary,
  onClose,
}: {
  projectId: string;
  entryArtefactId?: string | null;
  planningClosed: boolean;
  onOpenLibrary: () => void;
  onClose?: () => void;
}) {
  const conversations = useConversations(projectId, { status: "active" });
  const { activeConversationId, setActiveConversation } = useActiveConversation();
  const { create, archive } = useConversationMutations(projectId);
  const [tabIds, setTabIds] = useState(() => openChatTabs(projectId));
  // Derive-state-during-render on a project switch (no effect roundtrip).
  const [tabsProjectId, setTabsProjectId] = useState(projectId);
  if (tabsProjectId !== projectId) {
    setTabsProjectId(projectId);
    setTabIds(openChatTabs(projectId));
  }

  const rows = conversations.data?.data ?? [];
  const planningId = planningConversationId(rows);
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
    addOpenChatTab(projectId, activeConversationId);
    setTabIds(openChatTabs(projectId));
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
    addOpenChatTab(projectId, id);
    setTabIds(openChatTabs(projectId));
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
    removeOpenChatTab(projectId, id);
    setTabIds(openChatTabs(projectId));
    if (activeConversationId === id) {
      setActiveConversation(tabs[index + 1]?.id ?? tabs[index - 1]?.id ?? planningId);
    }
  };

  return (
    <nav aria-label="Conversations" className="flex min-w-0 items-stretch border-b border-line">
      <button
        type="button"
        onClick={() => setActiveConversation(planningId)}
        className={`flex min-w-0 items-center gap-2 px-3 py-2 text-meta font-semibold ${planningActive ? "border-b-2 border-blue text-navy" : "text-grey hover:bg-ground"}`}
      >
        <span aria-hidden="true" className={`h-2 w-2 rounded-full ${planningClosed ? "bg-line-2" : "bg-blue"}`} />
        <span className="truncate">Planning</span>
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
