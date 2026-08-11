import { useState } from "react";
import { useNavigate } from "react-router";

import { useArtefact, useConversations } from "../../../api/queries";
import { scrub } from "../../../lib/scrub";
import { ChatPane } from "./ChatPane";
import { ChatsLibrary } from "./ChatsLibrary";
import { addOpenChatTab, useActiveConversation, useConversationMutations } from "./conversationState";

/** Side-by-side chat on project views outside the workspace (rev 3.4).
 *
 * The panel is URL-addressable: it is open exactly when the route carries
 * `?chat=<cid>` — the same deep-link grammar the workspace tabs use, so a
 * chat opened beside the evidence base survives refresh and sharing.
 * Planning stays a workspace surface; the panel only hosts chats.
 *
 * Args:
 *   props: The owning project id.
 *
 * Returns:
 *   The open panel beside the view, or a compact edge toggle when closed.
 */
export function ChatSidePanel({ projectId }: { projectId: string }) {
  const { activeConversationId, setActiveConversation } = useActiveConversation();
  const [libraryOpen, setLibraryOpen] = useState(false);
  const navigate = useNavigate();
  const chats = useConversations(projectId, { kind: "chat", status: "active" });
  const artefact = useArtefact(projectId);
  const { create } = useConversationMutations(projectId);

  const openChat = (conversationId: string) => {
    addOpenChatTab(projectId, conversationId);
    setActiveConversation(conversationId);
  };

  const openLatestOrNew = async () => {
    const rows = chats.data?.data ?? [];
    if (rows.length > 0) return openChat(rows[0].id);
    openChat((await create(null)).id);
  };

  const newChat = async () => {
    const blank = (chats.data?.data ?? []).find(
      (chat) => chat.title === "New chat" && chat.entry_artefact_id === null,
    );
    openChat(blank !== undefined ? blank.id : (await create(null)).id);
  };

  if (activeConversationId === null) {
    return (
      <button
        type="button"
        onClick={() => void openLatestOrNew()}
        className="fixed right-0 top-1/2 z-10 -translate-y-1/2 border border-r-0 border-line bg-paper px-1.5 py-3 text-caption font-bold uppercase tracking-wider text-grey [writing-mode:vertical-rl] hover:text-blue"
      >
        Chat
      </button>
    );
  }

  const title = (chats.data?.data ?? []).find((chat) => chat.id === activeConversationId)?.title;
  return (
    <aside
      aria-label="Project chat"
      className="relative flex w-[26rem] shrink-0 flex-col border-l border-line bg-paper lg:h-[calc(100svh-58px)] lg:overflow-hidden"
    >
      <div className="flex items-center gap-2 border-b border-line px-3 py-1.5">
        <span className="min-w-0 flex-1 truncate text-meta font-semibold text-navy">
          {title === undefined ? "Chat" : scrub(title)}
        </span>
        <button
          type="button"
          aria-label="New chat"
          title="New chat"
          onClick={() => void newChat()}
          className="text-grey hover:text-blue"
        >
          <svg aria-hidden="true" width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M8 3v10M3 8h10" /></svg>
        </button>
        <button
          type="button"
          onClick={() => setLibraryOpen(true)}
          className="text-caption font-bold uppercase tracking-wider text-grey hover:text-blue"
        >
          Chats
        </button>
        <button
          type="button"
          aria-label="Close chat panel"
          title="Close"
          onClick={() => setActiveConversation(null)}
          className="text-grey hover:text-navy"
        >
          ×
        </button>
      </div>
      <div className="min-h-0 flex-1">
        <ChatPane
          projectId={projectId}
          conversationId={activeConversationId}
          sectionTitles={(artefact.data?.sections ?? []).map((section) => section.title)}
          onOpenPlanning={() => void navigate(`/projects/${projectId}`)}
        />
      </div>
      <ChatsLibrary projectId={projectId} open={libraryOpen} onClose={() => setLibraryOpen(false)} />
    </aside>
  );
}
