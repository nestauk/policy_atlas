import { useParams } from "react-router";

import { useProject } from "../api/queries";
import { useRunStream } from "../store";
import { NotFoundView } from "../ui/feedback/NotFoundView";
import { PlanningPane } from "./workspace/PlanningPane";
import { PlanPane } from "./workspace/PlanPane";
import { RailToggle, useRail } from "./workspace/rail";
import { RunPane } from "./workspace/RunPane";

/**
 * The workspace: planning conversation left, analysis right. The chat pane
 * holds the room while planning (55/45) and shrinks once an analysis exists
 * (35/65) — the RETRO §2.3 split, driven by run presence, not a toggle. The
 * left pane is a collapsible/resizable rail (027 strand 3); a user resize
 * pins the width for the session, collapse leaves a slim re-open strip.
 */
export function WorkspaceView() {
  const { projectId = "" } = useParams();
  const project = useProject(projectId);
  const stream = useRunStream(projectId);
  const hasRun = stream.run !== null;
  const rail = useRail(hasRun ? "35%" : "55%");

  // Query errors are the raw envelope body ({error: {code}}), thrown as-is.
  const errorCode = (project.error as { error?: { code?: string } } | null)?.error?.code;
  if (project.isError && errorCode === "not_found") {
    return <NotFoundView />;
  }

  return (
    <main
      className="mx-auto grid min-h-[calc(100svh-58px)] max-w-[1440px] grid-cols-1 lg:grid-cols-[var(--chat)_1fr]"
      style={{ "--chat": rail.width } as React.CSSProperties}
    >
      <div className="relative border-r border-line bg-paper">
        <div className="flex justify-end border-b border-line p-1">
          <RailToggle collapsed={rail.collapsed} toggleProps={rail.toggleProps} />
        </div>
        <div id={rail.regionId} hidden={rail.collapsed}>
          <PlanningPane projectId={projectId} runStatus={stream.run?.status} />
        </div>
        {!rail.collapsed && (
          <div
            {...rail.separatorProps}
            className="absolute inset-y-0 -right-1 z-10 hidden w-2 cursor-col-resize hover:bg-blue-tint focus-visible:bg-blue-tint focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue lg:block"
          />
        )}
      </div>
      <div className="bg-ground">
        {hasRun ? (
          <RunPane projectId={projectId} stream={stream} />
        ) : (
          <PlanPane projectId={projectId} />
        )}
      </div>
    </main>
  );
}
