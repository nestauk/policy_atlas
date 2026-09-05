import { useState } from "react";
import { useParams } from "react-router";

import { useTask } from "../api/queries";
import { useDocumentTitle } from "../lib/title";
import { useRunStream } from "../store";
import { NotFoundView } from "../ui/feedback/NotFoundView";
import { PlanDocument } from "./workspace/PlanDocument";
import { PlanningPane } from "./workspace/PlanningPane";
import type { PlanOverlay } from "./workspace/planOverlay";

/**
 * The Plan tab. The planning conversation is the only thread here — follow-up
 * chats live in the task chat overlay on every other tab.
 */
export function WorkspaceView() {
  const { taskId = "" } = useParams();
  const task = useTask(taskId);
  const stream = useRunStream(taskId);
  const hasRun = stream.run !== null;
  const [planOpen, setPlanOpen] = useState(false);
  const [planPlacement, setPlanPlacement] = useState<"center" | "side">("center");
  const [planOverlay, setPlanOverlay] = useState<PlanOverlay>({});
  useDocumentTitle(task.data?.name, "Plan");

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

  return (
    <main className="relative flex h-full min-h-0 overflow-hidden bg-paper">
      <div
        className="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden"
        inert={planOpen && planPlacement === "center" ? true : undefined}
      >
        <PlanningPane
          taskId={taskId}
          runStatus={stream.run?.status}
          stream={stream}
          isOwner={isOwner}
          onReviewPlan={openPlan}
          planOverlay={planOverlay}
          onOverlayApplied={() => setPlanOverlay({})}
        />
      </div>
      {planOpen && planPlacement === "side" && planDocument}
      {planOpen && planPlacement === "center" && (
        <div className="absolute inset-0 z-20 overflow-hidden">{planDocument}</div>
      )}
    </main>
  );
}
