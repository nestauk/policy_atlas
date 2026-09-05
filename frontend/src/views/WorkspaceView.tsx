import { useState } from "react";
import { useParams } from "react-router";

import { useArtefact, useConversations, useTask } from "../api/queries";
import { useDocumentTitle } from "../lib/title";
import { LIFECYCLE_LABELS } from "../lib/vocabulary";
import { useRunStream } from "../store";
import { cn } from "../ui/brand/cn";
import { NotFoundView } from "../ui/feedback/NotFoundView";
import { LIFECYCLE_PAGE_CLASS } from "./listPageChrome";
import { AppFooter } from "./AppFooter";
import { ChatPane } from "./workspace/chat/ChatPane";
import { ConversationSidebar } from "./workspace/chat/ConversationSidebar";
import { isPlanningConversation, taskAgentConversationId, useActiveConversation } from "./workspace/chat/conversationState";
import { PlanDocument } from "./workspace/PlanDocument";
import { PlanningPane } from "./workspace/PlanningPane";
import type { PlanOverlay } from "./workspace/planOverlay";

/**
 * The Agent tab: the Task's conversations in a sidebar, the selected one in
 * the main column (owner ruling 2026-09-05, contract 038 § V8).
 *
 * The Task Agent is the default and carries no `?chat=`; it keeps this tab's
 * original layout, the planning pane with its plan-document rail. Any other
 * chat takes the main column instead, and the rail — which belongs to the
 * plan, not to a chat — stays shut. The overlay (`ChatSidePanel`) is not
 * mounted here: this sidebar is what it would have been.
 */
export function WorkspaceView() {
  const { taskId = "" } = useParams();
  const task = useTask(taskId);
  const stream = useRunStream(taskId);
  const { activeConversationId, setActiveConversation } = useActiveConversation();
  const conversations = useConversations(taskId, { status: "active" });
  const rows = conversations.data?.data ?? [];
  const artefact = useArtefact(taskId);
  // A planning id in the URL (a deep link, or the overlay's own selection
  // carried over) reads as the Task Agent: the pane renders the Task's
  // planning thread, never one lineage on its own.
  const onTaskAgent = activeConversationId === null || isPlanningConversation(activeConversationId, rows);
  const chatId = onTaskAgent ? null : activeConversationId;
  const hasRun = stream.run !== null;
  const [planOpen, setPlanOpen] = useState(false);
  const [planPlacement, setPlanPlacement] = useState<"center" | "side">("center");
  const [planOverlay, setPlanOverlay] = useState<PlanOverlay>({});
  useDocumentTitle(task.data?.name, LIFECYCLE_LABELS.agent);

  const runActive = stream.run?.status === "running" || stream.run?.status === "paused";
  // Task 033 phase 10c (contract § 11 / rubric 37) — the Plan route (this
  // view) hosts every owner-only mutation surface and is never gated by
  // `LifecycleRoute` (it's open at every run state), so `is_owner` is the
  // only line of defence against a non-owner reaching them by address.
  // Undefined while `task` is still loading reads as "not the owner" —
  // fail closed, never grant the mutation surface before ownership is known.
  const isOwner = task.data?.is_owner === true;
  const openPlan = () => {
    setPlanPlacement("center");
    setPlanOpen(true);
  };
  const planDocument = (
    <PlanDocument
      taskId={taskId}
      placement={planPlacement}
      runActive={runActive}
      // The plan-start card (contract § 11 / rubric 37): folds `!isOwner`
      // into the same `readOnly` prop that already hides Edit/Start once a
      // run has consumed the plan — one mechanism, not a second gate.
      readOnly={hasRun || !isOwner}
      onClose={() => setPlanOpen(false)}
      onDock={() => setPlanPlacement("side")}
      onStarted={() => {
        setPlanOverlay({});
        setPlanOpen(false);
      }}
      overlay={planOverlay}
      onOverlayChange={setPlanOverlay}
    />
  );

  // useTask (task 037 review fix) now throws a plain Error carrying
  // `status`, not the API's `{error:{code}}` envelope — read the status
  // directly rather than a `code` field that no longer exists.
  const taskErrorStatus = (task.error as { status?: number } | null)?.status;
  if (task.isError && taskErrorStatus === 404) {
    return <NotFoundView />;
  }

  // The rail belongs to the plan; a chat in the main column never carries it.
  const railOpen = chatId === null && planOpen;

  return (
    <main className="flex h-full min-h-0 flex-col overflow-hidden bg-paper">
      {/* Sidebar and conversation share the row; the site footer runs under
          both, so neither column ever appears to overhang it. */}
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <ConversationSidebar
          taskId={taskId}
          selectedId={onTaskAgent ? taskAgentConversationId(rows) : activeConversationId}
          onSelect={setActiveConversation}
        />
        {/* The plan document's centred placement covers the conversation, not
            the sidebar — so `relative` sits on this column, not on <main>. */}
        <div className="relative flex min-h-0 min-w-0 flex-1 overflow-hidden">
          <div
            className="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden"
            inert={railOpen && planPlacement === "center" ? true : undefined}
          >
            {chatId === null ? (
              <PlanningPane
                taskId={taskId}
                runStatus={stream.run?.status}
                stream={stream}
                isOwner={isOwner}
                onReviewPlan={openPlan}
                planOverlay={planOverlay}
                onOverlayApplied={() => setPlanOverlay({})}
              />
            ) : (
              // The same reading column the planning pane sets for itself —
              // this main view is wide, and `ChatPane` was drawn for the
              // 416px overlay.
              <div className={cn("flex min-h-0 flex-1 flex-col overflow-hidden", LIFECYCLE_PAGE_CLASS)}>
                <ChatPane
                  taskId={taskId}
                  conversationId={chatId}
                  sectionTitles={(artefact.data?.sections ?? []).map((section) => section.title)}
                  onOpenPlanning={() => setActiveConversation(null)}
                />
              </div>
            )}
          </div>
          {railOpen && planPlacement === "side" && planDocument}
          {railOpen && planPlacement === "center" && (
            <div className="absolute inset-0 z-20 overflow-hidden">{planDocument}</div>
          )}
        </div>
      </div>
      <AppFooter className="mt-0" />
    </main>
  );
}
