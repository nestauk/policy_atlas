import { useCallback, useRef, useState } from "react";
import { useNavigate } from "react-router";

import { useArtefact, useConversations } from "../../../api/queries";
import { COPY } from "../../../lib/vocabulary";
import { createInitialRunStreamState } from "../../../store";
import { PlanningPane } from "../PlanningPane";
import { ChatPane } from "./ChatPane";
import { ChatsLibrary } from "./ChatsLibrary";
import { ConversationTabs } from "./ConversationTabs";
import { addOpenChatTab, isPlanningConversation, planningConversationId, useActiveConversation, useConversationMutations } from "./conversationState";

/** Resize bounds (px) — the workspace rail's own clamp. */
const PANEL_MIN = 280;
const PANEL_MAX = 640;
const PANEL_DEFAULT = 416;
const KEY_STEP = 24;

/** Drag/keyboard width for the left-hand panel (handle on its RIGHT edge —
 *  the workspace rail's own geometry, so the delta math matches it). */
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
      setPx(clamp(from.width + (move.clientX - from.x)));
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
    setPx((current) => clamp(current + (event.key === "ArrowRight" ? KEY_STEP : -KEY_STEP)));
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

/** Side-by-side chat on task views outside Plan (rev 3.4).
 *
 * The panel is URL-addressable: it is open exactly when the route carries
 * `?chat=<cid>` — the same deep-link grammar the conversation strip uses.
 * The edge launcher opens the latest follow-up chat. The strip lists
 * planning plus those chats; selecting planning renders that thread here.
 *
 * Args:
 *   props: The owning task id, and `isOwner` for the planning duplicate's
 *     read-only gate (task 033 phase 10c, contract § 11 / rubric 37) — this
 *     is the `ChatSidePanel` duplicate the rubric names alongside the
 *     workspace's own `PlanningPane`.
 *
 * Returns:
 *   The open panel beside the view, or a compact edge toggle when closed.
 */
export function ChatSidePanel({ taskId, isOwner }: { taskId: string; isOwner: boolean }) {
  const { activeConversationId, setActiveConversation } = useActiveConversation();
  const [libraryOpen, setLibraryOpen] = useState(false);
  const panel = usePanelWidth();
  const navigate = useNavigate();
  const conversations = useConversations(taskId, { status: "active" });
  const rows = conversations.data?.data ?? [];
  const chatRows = rows.filter((row) => row.kind === "chat");
  const planningId = planningConversationId(rows);
  const planningOpen = isPlanningConversation(activeConversationId, rows);
  const artefact = useArtefact(taskId);
  const { create } = useConversationMutations(taskId);

  const openChat = (conversationId: string) => {
    addOpenChatTab(taskId, conversationId);
    setActiveConversation(conversationId);
  };

  const openLatestOrNew = async () => {
    // The launcher's create-vs-open decision needs the chats list resolved
    // first — firing before then reads "no chats" off `undefined` data and
    // POSTs a spurious blank chat on a fast first click.
    if (!conversations.isSuccess) return;
    if (chatRows.length > 0) return openChat(chatRows[0].id);
    openChat((await create(null)).id);
  };

  if (activeConversationId === null) {
    return (
      <button
        type="button"
        aria-label="Open chat"
        title="Chat"
        disabled={!conversations.isSuccess}
        onClick={() => void openLatestOrNew()}
        className="fixed bottom-5 left-5 z-10 flex h-11 w-11 items-center justify-center rounded-full border border-line bg-paper text-grey shadow-lg hover:text-blue focus-visible:outline-2 focus-visible:outline-blue disabled:cursor-not-allowed disabled:opacity-50"
      >
        <svg aria-hidden="true" width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round">
          <path d="M3 4.5h14v9H8l-3.5 3v-3H3v-9Z" />
        </svg>
      </button>
    );
  }

  const planningClosed = rows.some((row) => row.kind === "planning" && row.closed_at !== null)
    && !rows.some((row) => row.kind === "planning" && row.closed_at === null);

  return (
    <aside
      aria-label={COPY.projectChatAriaLabel}
      style={{ width: panel.width }}
      className="relative flex h-full min-h-0 shrink-0 flex-col overflow-hidden border-r border-line bg-paper"
    >
      <div
        {...panel.separatorProps}
        className="absolute inset-y-0 -right-1 z-10 hidden w-2 cursor-col-resize hover:bg-blue-tint focus-visible:bg-blue-tint focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue lg:block"
      />
      <ConversationTabs
        taskId={taskId}
        planningClosed={planningClosed}
        onOpenLibrary={() => setLibraryOpen(true)}
        onClose={() => setActiveConversation(null)}
      />
      <div className="min-h-0 flex-1">
        {planningOpen ? (
          <PlanningPane
            taskId={taskId}
            runStatus={undefined}
            stream={createInitialRunStreamState()}
            isOwner={isOwner}
            onReviewPlan={() => void navigate(`/tasks/${taskId}`)}
          />
        ) : (
          <ChatPane
            taskId={taskId}
            conversationId={activeConversationId}
            sectionTitles={(artefact.data?.sections ?? []).map((section) => section.title)}
            onOpenPlanning={() => setActiveConversation(planningId)}
          />
        )}
      </div>
      <ChatsLibrary taskId={taskId} open={libraryOpen} onClose={() => setLibraryOpen(false)} />
    </aside>
  );
}
