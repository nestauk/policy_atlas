import { useCallback, useRef, useState } from "react";
import { useNavigate } from "react-router";

import { useArtefact, useConversations } from "../../../api/queries";
import { scrub } from "../../../lib/scrub";
import { ChatPane } from "./ChatPane";
import { ChatsLibrary } from "./ChatsLibrary";
import { addOpenChatTab, useActiveConversation, useConversationMutations } from "./conversationState";

/** Resize bounds (px) — the workspace rail's own clamp. */
const PANEL_MIN = 280;
const PANEL_MAX = 640;
const PANEL_DEFAULT = 416;
const KEY_STEP = 24;

/** Drag/keyboard width for the right-hand panel (handle on its LEFT edge,
 *  so the drag delta inverts relative to the workspace rail). */
function usePanelWidth() {
  const [px, setPx] = useState(PANEL_DEFAULT);
  const dragFrom = useRef<{ x: number; width: number } | null>(null);
  const clamp = (value: number) => Math.min(Math.max(value, PANEL_MIN), PANEL_MAX);

  const onPointerDown = useCallback((event: React.PointerEvent<HTMLElement>) => {
    const panel = (event.currentTarget as HTMLElement).parentElement;
    if (panel === null) return;
    dragFrom.current = { x: event.clientX, width: panel.getBoundingClientRect().width };
    const handle = event.currentTarget as HTMLElement;
    handle.setPointerCapture(event.pointerId);
    const onMove = (move: PointerEvent) => {
      const from = dragFrom.current;
      if (from === null) return;
      setPx(clamp(from.width - (move.clientX - from.x)));
    };
    const onUp = () => {
      dragFrom.current = null;
      handle.removeEventListener("pointermove", onMove);
      handle.removeEventListener("pointerup", onUp);
    };
    handle.addEventListener("pointermove", onMove);
    handle.addEventListener("pointerup", onUp);
  }, []);

  const onKeyDown = useCallback((event: React.KeyboardEvent<HTMLElement>) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    setPx((current) => clamp(current + (event.key === "ArrowLeft" ? KEY_STEP : -KEY_STEP)));
  }, []);

  return {
    width: `${px}px`,
    separatorProps: {
      role: "separator" as const,
      "aria-orientation": "vertical" as const,
      "aria-label": "Resize the chat panel",
      "aria-valuemin": PANEL_MIN,
      "aria-valuemax": PANEL_MAX,
      "aria-valuenow": px,
      tabIndex: 0 as const,
      onPointerDown,
      onKeyDown,
    },
  };
}

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
  const panel = usePanelWidth();
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
        aria-label="Open chat"
        title="Chat"
        onClick={() => void openLatestOrNew()}
        className="fixed bottom-5 left-5 z-10 flex h-11 w-11 items-center justify-center rounded-full border border-line bg-paper text-grey shadow-lg hover:text-blue focus-visible:outline-2 focus-visible:outline-blue"
      >
        <svg aria-hidden="true" width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round">
          <path d="M3 4.5h14v9H8l-3.5 3v-3H3v-9Z" />
        </svg>
      </button>
    );
  }

  const title = (chats.data?.data ?? []).find((chat) => chat.id === activeConversationId)?.title;
  return (
    <aside
      aria-label="Project chat"
      style={{ width: panel.width }}
      className="relative flex shrink-0 flex-col border-l border-line bg-paper lg:h-[calc(100svh-58px)] lg:overflow-hidden"
    >
      <div
        {...panel.separatorProps}
        className="absolute inset-y-0 -left-1 z-10 hidden w-2 cursor-col-resize hover:bg-blue-tint focus-visible:bg-blue-tint focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue lg:block"
      />
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
