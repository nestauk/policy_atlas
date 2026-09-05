import { useCallback, useRef, useState } from "react";
import { useNavigate } from "react-router";

import { useArtefact, useConversations } from "../../../api/queries";
import { COPY } from "../../../lib/vocabulary";
import { createInitialRunStreamState, useRunStream } from "../../../store";
import { cn } from "../../../ui/brand/cn";
import { FoldMarkIcon } from "../../../ui/brand/FoldMarkIcon";
import { hasResult } from "../../lifecycle";
import { PlanningPane } from "../PlanningPane";
import { ChatPane } from "./ChatPane";
import { ChatsIcon } from "./ChatsIcon";
import { ConversationList, type ConversationRow } from "./ConversationList";
import {
  DRAFT_CHAT_ID,
  isPlanningConversation,
  taskAgentConversationId,
  useActiveConversation,
} from "./conversationState";
import { DraftChatPane } from "./DraftChatPane";
import { CloseIcon, PlusIcon } from "./icons";

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

const HEADER_BUTTON =
  "pressable flex h-8 w-8 shrink-0 items-center justify-center text-grey hover:bg-blue-tint-2 hover:text-navy focus-visible:outline-2 focus-visible:outline-blue disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent";

/** The Agent overlay: side-by-side chat on every task view but the Agent tab
 *  (038 V8).
 *
 * The panel is URL-addressable: it is open exactly when the route carries
 * `?chat=<cid>`. It is the Agent tab's sidebar folded into one column: the
 * header names the conversation on show and toggles the same conversation
 * list the Agent tab keeps open beside its main view; the body is that
 * conversation — the Task Agent's planning thread, a chat, or a draft chat
 * that persists nothing until its first message. The edge launcher opens the
 * latest chat, or the Task Agent when there is none.
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
  const { activeConversationId, draftEntryArtefactId, setActiveConversation, openDraftChat } = useActiveConversation();
  const [listOpen, setListOpen] = useState(false);
  const panel = usePanelWidth();
  const navigate = useNavigate();
  const conversations = useConversations(taskId, { status: "active" });
  const rows = conversations.data?.data ?? [];
  const chatRows = rows.filter((row) => row.kind === "chat");
  const taskAgentId = taskAgentConversationId(rows);
  const planningOpen = isPlanningConversation(activeConversationId, rows);
  const draftOpen = activeConversationId === DRAFT_CHAT_ID;
  const artefact = useArtefact(taskId);
  const stream = useRunStream(taskId);
  const chatsEnabled = hasResult(stream.run?.status);

  const openLatestOrTaskAgent = () => {
    // The launcher's decision needs the chats list resolved first — before
    // then "no chats" is read off `undefined` data.
    if (!conversations.isSuccess) return;
    setActiveConversation(chatRows.length > 0 ? chatRows[0].id : taskAgentId);
  };

  if (activeConversationId === null) {
    return (
      <button
        type="button"
        aria-label={COPY.openAgent}
        title={COPY.agent}
        disabled={!conversations.isSuccess}
        onClick={openLatestOrTaskAgent}
        className="pressable fixed bottom-5 left-5 z-10 flex h-11 w-11 items-center justify-center rounded-full border border-line bg-paper text-grey shadow-lg hover:text-blue focus-visible:outline-2 focus-visible:outline-blue disabled:cursor-not-allowed disabled:opacity-60"
      >
        <svg aria-hidden="true" width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round">
          <path d="M3 4.5h14v9H8l-3.5 3v-3H3v-9Z" />
        </svg>
      </button>
    );
  }

  const openRow = (row: ConversationRow) => {
    setActiveConversation(row.kind === "planning" ? taskAgentId : row.id);
    setListOpen(false);
  };
  const currentTitle = planningOpen
    ? COPY.taskAgent
    : draftOpen
      ? COPY.newChat
      : (rows.find((row) => row.id === activeConversationId)?.title ?? COPY.newChat);
  const sectionTitles = (artefact.data?.sections ?? []).map((section) => section.title);

  return (
    <aside
      aria-label={COPY.agentAriaLabel}
      style={{ width: panel.width }}
      className="relative flex h-full min-h-0 shrink-0 flex-col overflow-hidden border-r border-line bg-paper"
    >
      <div
        {...panel.separatorProps}
        className="absolute inset-y-0 -right-1 z-10 hidden w-2 cursor-col-resize hover:bg-blue-tint focus-visible:bg-blue-tint focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue lg:block"
      />
      {/* The Agent tab's sidebar header, folded: list toggle · the
          conversation on show · New chat · close. */}
      <div className="flex shrink-0 items-center gap-1 border-b border-line bg-paper-2 px-2 py-1.5">
        <button
          type="button"
          aria-label="Chats"
          aria-pressed={listOpen}
          aria-controls="agent-overlay-list"
          title="Chats"
          onClick={() => setListOpen((open) => !open)}
          className={cn(HEADER_BUTTON, listOpen && "bg-blue-tint text-navy")}
        >
          <ChatsIcon size={15} />
        </button>
        <div className="flex min-w-0 flex-1 items-center gap-2 px-1 text-meta font-semibold text-navy">
          {planningOpen && <FoldMarkIcon size={10} />}
          <span className="truncate">{currentTitle}</span>
        </div>
        <button
          type="button"
          aria-label={COPY.newChat}
          title={chatsEnabled ? COPY.newChat : COPY.newChatUnavailable}
          disabled={!chatsEnabled}
          onClick={() => {
            openDraftChat(null);
            setListOpen(false);
          }}
          className={HEADER_BUTTON}
        >
          <PlusIcon size={14} />
        </button>
        <button
          type="button"
          aria-label="Close chat panel"
          title="Close"
          onClick={() => setActiveConversation(null)}
          className={HEADER_BUTTON}
        >
          <CloseIcon size={14} />
        </button>
      </div>
      {listOpen ? (
        <div id="agent-overlay-list" role="region" aria-label="Chats" className="min-h-0 flex-1 overflow-y-auto bg-paper-2 px-1.5 pb-3 pt-1">
          <ConversationList taskId={taskId} onOpen={openRow} selectedId={planningOpen ? taskAgentId : activeConversationId} />
        </div>
      ) : (
        <div className="min-h-0 flex-1">
          {planningOpen ? (
            <PlanningPane
              taskId={taskId}
              runStatus={undefined}
              stream={createInitialRunStreamState()}
              isOwner={isOwner}
              onReviewPlan={() => void navigate(`/tasks/${taskId}`)}
            />
          ) : draftOpen ? (
            <DraftChatPane
              taskId={taskId}
              entryArtefactId={draftEntryArtefactId}
              sectionTitles={sectionTitles}
              onCreated={setActiveConversation}
            />
          ) : (
            <ChatPane
              taskId={taskId}
              conversationId={activeConversationId}
              sectionTitles={sectionTitles}
              onOpenPlanning={() => setActiveConversation(taskAgentId)}
            />
          )}
        </div>
      )}
    </aside>
  );
}
