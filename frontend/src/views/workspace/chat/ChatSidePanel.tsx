import { useEffect, useState } from "react";
import { Link } from "react-router";

import { useArtefact, useConversations, useTask } from "../../../api/queries";
import { COPY } from "../../../lib/vocabulary";
import { useRunStream } from "../../../store";
import { cn } from "../../../ui/brand/cn";
import { FoldMarkIcon } from "../../../ui/brand/FoldMarkIcon";
import { isToc } from "../../scopingActivity";
import { usePlanPanel } from "../../planPanel";
import { useChatsEnabled } from "../../taskResult";
import { TaskAgentPane } from "../TaskAgentPane";
import { usePanelWidth } from "../usePanelWidth";
import { ChatPane } from "./ChatPane";
import { ChangingText } from "../ChangingText";
import { Tooltip, TooltipProvider } from "../../../ui/radix/Tooltip";
import { ConversationList, type ConversationRow } from "./ConversationList";
import { ConversationRail, RAIL_TOOLTIP_CLASS, RAIL_TOOLTIP_DELAY_MS } from "./ConversationRail";
import { readStored, writeStored } from "./ConversationSidebar";
import {
  DRAFT_CHAT_ID,
  isTaskAgentConversation,
  recentChats,
  taskAgentConversationId,
  useActiveConversation,
} from "./conversationState";
import { DraftChatPane } from "./DraftChatPane";
import { ChatsIcon, ExpandIcon, PanelCloseIcon, PlusIcon, iconButtonClass } from "../../../ui/brand/icons";

/** Whether the user closed the sidebar: a theory of change opens it on the Task Agent until they do. */
const CLOSED_KEY = "pa.chatSidebarClosed";

const HEADER_BUTTON = iconButtonClass("chrome");

/** The Agent overlay: side-by-side chat on every task view but the Agent tab
 *  (038 V8).
 *
 * The panel is URL-addressable: it is open exactly when the route carries
 * `?chat=<cid>`. It is the Agent tab's sidebar folded into one column: the
 * header names the conversation on show and toggles the same conversation
 * list the Agent tab keeps open beside its main view; the body is that
 * conversation — the Task Agent's task_agent thread, a chat, or a draft chat
 * that persists nothing until its first message. Shut, it is the same slim
 * rail the Agent tab's sidebar shuts to; the rail's toggle opens the latest
 * chat, or the Task Agent when there is none.
 *
 * The Task Agent here is the same agent as the Agent tab (task 058, N13): it
 * reads the task's one run stream and shows the same thread, with the run's
 * trace at its place (owner, 2026-11-05: the trace is the sidebar's run
 * view; no separate run line). While a check-in waits, the rail's toggle
 * opens the Task Agent, whose thread opens at its end, on the check-in.
 *
 * Args:
 *   props: The owning task id, and `isOwner` for the task_agent duplicate's
 *     read-only gate (task 033 phase 10c, contract § 11 / rubric 37) — this
 *     is the `ChatSidePanel` duplicate the rubric names alongside the
 *     workspace's own `TaskAgentPane`. `onOpenPlan` overrides how "Review the
 *     plan" and "See plan" open the plan document (the shell's plan panel by
 *     default).
 *
 * Returns:
 *   The open panel beside the view, or a compact edge toggle when closed.
 */
export function ChatSidePanel({
  taskId,
  isOwner,
  onOpenPlan,
}: {
  taskId: string;
  isOwner: boolean;
  onOpenPlan?: () => void;
}) {
  const { activeConversationId, draftEntryArtefactId, setActiveConversation, openDraftChat } = useActiveConversation();
  const [listOpen, setListOpen] = useState(false);
  const panel = usePanelWidth({ label: "Resize the chat panel", initial: 416 });
  const conversations = useConversations(taskId, { status: "active" });
  const rows = conversations.data?.data ?? [];
  const chatRows = rows.filter((row) => row.kind === "chat");
  const taskAgentId = taskAgentConversationId(rows);
  // The Task Agent's conversations, closed ones included (round 12): a walk
  // that ends closes the open one (answering the baseline check-in ends the
  // baseline walk), so it leaves the active list while the sidebar is still
  // showing it. Read against the active list alone, the panel took it for a
  // chat and showed an empty one.
  const taskAgentRows = useConversations(taskId, { kind: "task_agent" }).data?.data ?? [];
  const taskAgentOpen = isTaskAgentConversation(activeConversationId, [...rows, ...taskAgentRows]);
  const draftOpen = activeConversationId === DRAFT_CHAT_ID;
  const artefact = useArtefact(taskId);
  const chatsEnabled = useChatsEnabled(taskId);
  const task = useTask(taskId);
  const tocTask = isToc(task.data);
  // On a theory of change, the sidebar stays as the user left it across tabs
  // (round 7): open on the Task Agent unless they closed it, and closed until
  // they open it again. The other kinds keep it closed until opened, as before.
  // ponytail: one flag for every task in this browser; per task if users ask.
  useEffect(() => {
    if (activeConversationId !== null) {
      writeStored(CLOSED_KEY, "0");
      return;
    }
    if (tocTask && conversations.isSuccess && readStored(CLOSED_KEY) !== "1") {
      setActiveConversation(taskAgentId, { replace: true });
    }
  }, [activeConversationId, conversations.isSuccess, taskAgentId, setActiveConversation, tocTask]);
  const stream = useRunStream(taskId);
  const checkInWaiting = stream.pendingCheckIn != null;
  const openLatestOrTaskAgent = () => {
    // The launcher's decision needs the chats list resolved first — before
    // then "no chats" is read off `undefined` data.
    if (!conversations.isSuccess) return;
    // A waiting check-in wins: opening the panel lands on it (task 058, N13).
    if (checkInWaiting) return setActiveConversation(taskAgentId);
    setActiveConversation(chatRows.length > 0 ? chatRows[0].id : taskAgentId);
  };
  // "Review the plan" and "See plan" open the shell's plan document (task
  // 058, N13, N15) without leaving the tab.
  const planPanel = usePlanPanel();
  const openPlan = onOpenPlan ?? planPanel.openPlan;

  if (activeConversationId === null) {
    // Shut, the overlay is the same rail the Agent tab's sidebar shuts to
    // (owner request 2026-09-05): one object on every task tab.
    // Below md the rail hides with no stand-in (task 040 amendment A6): the
    // bottom tab bar's Agent tab is the mobile way into the conversation.
    return (
      <ConversationRail
        toggleLabel={COPY.openAgent}
        expanded={false}
        toggleDisabled={!conversations.isSuccess}
        onToggle={openLatestOrTaskAgent}
        onNewChat={() => openDraftChat(null)}
        chatsEnabled={chatsEnabled}
        onTaskAgent={false}
        onSelectTaskAgent={() => setActiveConversation(taskAgentId)}
        recent={recentChats(rows)}
        onSelectChat={setActiveConversation}
        // The rail's Task Agent mark holds still and carries no run status
        // (owner, round 8): the run status bar beside it says what the run is
        // doing, and opens the Task Agent.
        className="h-full w-12 flex-col border-r py-2 max-md:hidden"
      />
    );
  }

  const openRow = (row: ConversationRow) => {
    setActiveConversation(row.kind === "task_agent" ? taskAgentId : row.id);
    setListOpen(false);
  };
  const currentTitle = taskAgentOpen
    ? COPY.taskAgent
    : draftOpen
      ? COPY.newChat
      : (rows.find((row) => row.id === activeConversationId)?.title ?? COPY.newChat);
  const sectionTitles = (artefact.data?.sections ?? []).map((section) => section.title);

  return (
    <aside
      aria-label={COPY.agentAriaLabel}
      style={{ width: panel.width }}
      className="relative flex h-full min-h-0 shrink-0 flex-col overflow-hidden border-r border-line bg-paper max-md:hidden"
    >
      <div
        {...panel.separatorProps}
        className="absolute inset-y-0 -right-1 z-10 hidden w-2 cursor-col-resize hover:bg-blue-tint focus-visible:bg-blue-tint lg:block"
      />
      {/* The Agent tab's sidebar header, folded: list toggle · the
          conversation on show · New chat · close. */}
      <TooltipProvider delayDuration={RAIL_TOOLTIP_DELAY_MS}>
      <div className="flex shrink-0 items-center gap-1 border-b border-line bg-paper-2 px-2 py-1.5">
        <Tooltip content="Chats" side="bottom" className={RAIL_TOOLTIP_CLASS}>
          <button
            type="button"
            aria-label="Chats"
            aria-pressed={listOpen}
            aria-controls="agent-overlay-list"
            onClick={() => setListOpen((open) => !open)}
            className={cn(HEADER_BUTTON, listOpen && "bg-blue-tint text-navy")}
          >
            <ChatsIcon />
          </button>
        </Tooltip>
        {/* The name is the way to the conversation's full-width home (owner,
            2026-09-05): the Agent tab with this conversation in the main
            column — an explicit hand-over of `?chat=`, which the tab bar
            itself never carries there. No fifth control in the header. */}
        <Tooltip content="View in Agent tab" side="bottom" className={RAIL_TOOLTIP_CLASS}>
          <Link
            to={taskAgentOpen ? `/tasks/${taskId}` : `/tasks/${taskId}?chat=${encodeURIComponent(activeConversationId)}`}
            aria-label={`View in Agent tab: ${currentTitle}`}
            className="group/name flex min-w-0 flex-1 items-center gap-2 px-1 text-meta font-semibold text-navy hover:underline"
          >
            {taskAgentOpen && <FoldMarkIcon size={10} />}
            {/* A chat's title as the backend names it (round 14), revealed;
                keyed by the chat, so opening another never reads as one. */}
            <ChangingText key={activeConversationId} text={currentTitle} testIdPrefix="chat-title" />
            <ExpandIcon
              size={13}
              className="shrink-0 text-grey opacity-0 transition-opacity duration-150 group-hover/name:opacity-100 group-focus-visible/name:opacity-100"
            />
          </Link>
        </Tooltip>
        <Tooltip content={chatsEnabled ? COPY.newChat : COPY.newChatUnavailable} side="bottom" className={RAIL_TOOLTIP_CLASS}>
          <span className="inline-flex">
            <button
              type="button"
              aria-label={COPY.newChat}
              disabled={!chatsEnabled}
              onClick={() => {
                openDraftChat(null);
                setListOpen(false);
              }}
              className={HEADER_BUTTON}
            >
              <PlusIcon />
            </button>
          </span>
        </Tooltip>
        <Tooltip content="Close sidebar" side="bottom" className={RAIL_TOOLTIP_CLASS}>
          <button
            type="button"
            aria-label="Close sidebar"
            onClick={() => {
              writeStored(CLOSED_KEY, "1");
              setActiveConversation(null);
            }}
            className={HEADER_BUTTON}
          >
            <PanelCloseIcon />
          </button>
        </Tooltip>
      </div>
      </TooltipProvider>
      {listOpen ? (
        <div id="agent-overlay-list" role="region" aria-label="Chats" className="min-h-0 flex-1 overflow-y-auto bg-paper-2 px-1.5 pb-3 pt-1">
          <ConversationList taskId={taskId} onOpen={openRow} selectedId={taskAgentOpen ? taskAgentId : activeConversationId} />
        </div>
      ) : (
        // `compact-pane`: Lead text reads at Body size in the sidebar (owner,
        // 2026-11-05), for the Task Agent and the chats alike.
        <div className="compact-pane min-h-0 flex-1">
          {taskAgentOpen ? (
            <TaskAgentPane
              taskId={taskId}
              runStatus={stream.run?.status}
              stream={stream}
              isOwner={isOwner}
              onReviewPlan={openPlan}
              compact
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
              onOpenTaskAgent={() => setActiveConversation(taskAgentId)}
            />
          )}
        </div>
      )}
    </aside>
  );
}
