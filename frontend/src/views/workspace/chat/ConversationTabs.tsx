import { useState } from "react";

import { useConversations } from "../../../api/queries";
import { scrub } from "../../../lib/scrub";
import { ChatsIcon } from "./ChatsIcon";
import {
  addOpenChatTab,
  openChatTabs,
  removeOpenChatTab,
  useActiveConversation,
  useConversationMutations,
} from "./conversationState";

/** Conversation switcher for the workspace rail.
 *
 * Args:
 *   props: Project, planning lifecycle, and library-open callback.
 *
 * Returns:
 *   A planning tab and session-local chat tabs.
 */
export function ConversationTabs({
  projectId,
  entryArtefactId = null,
  planningClosed,
  onOpenLibrary,
}: {
  projectId: string;
  entryArtefactId?: string | null;
  planningClosed: boolean;
  onOpenLibrary: () => void;
}) {
  const chats = useConversations(projectId, { kind: "chat", status: "active" });
  const { activeConversationId, setActiveConversation } = useActiveConversation();
  const { create, archive } = useConversationMutations(projectId);
  const [tabIds, setTabIds] = useState(() => openChatTabs(projectId));
  // Derive-state-during-render on a project switch (no effect roundtrip).
  const [tabsProjectId, setTabsProjectId] = useState(projectId);
  if (tabsProjectId !== projectId) {
    setTabsProjectId(projectId);
    setTabIds(openChatTabs(projectId));
  }

  const activeChats = chats.data?.data ?? [];
  const tabs = tabIds.flatMap((id) => {
    const chat = activeChats.find((candidate) => candidate.id === id);
    return chat === undefined ? [] : [chat];
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
    if (activeConversationId === id) setActiveConversation(tabs[index + 1]?.id ?? tabs[index - 1]?.id ?? null);
  };

  return (
    <nav aria-label="Conversations" className="flex min-w-0 items-stretch border-b border-line">
      <button
        type="button"
        onClick={() => setActiveConversation(null)}
        className={`flex min-w-0 items-center gap-2 px-3 py-2 text-meta font-semibold ${activeConversationId === null ? "border-b-2 border-blue text-navy" : "text-grey hover:bg-ground"}`}
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
    </nav>
  );
}
