import { useState } from "react";
import { useParams } from "react-router";

import { useTask } from "../api/queries";
import { useDocumentTitle } from "../lib/title";
import { useRunStream } from "../store";
import { cn } from "../ui/brand/cn";
import { NotFoundView } from "../ui/feedback/NotFoundView";
import { LIFECYCLE_PAGE_CLASS } from "./listPageChrome";
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
  const openPlan = () => {
    setPlanPlacement("center");
    setPlanOpen(true);
  };
  const planDocument = (
    <PlanDocument
      taskId={taskId}
      placement={planPlacement}
      runActive={runActive}
      readOnly={hasRun}
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

  const errorCode = (task.error as { error?: { code?: string } } | null)?.error?.code;
  if (task.isError && errorCode === "not_found") {
    return <NotFoundView />;
  }

  return (
    <main className="relative flex h-full min-h-0 justify-center overflow-hidden bg-paper">
      <div
        className={cn(
          "flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden",
          LIFECYCLE_PAGE_CLASS,
        )}
        inert={planOpen && planPlacement === "center" ? true : undefined}
      >
        <PlanningPane
          taskId={taskId}
          runStatus={stream.run?.status}
          stream={stream}
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
