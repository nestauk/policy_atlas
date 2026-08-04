import { useParams } from "react-router";

import { useProject } from "../api/queries";
import { useDocumentTitle } from "../lib/title";
import { useRunStream } from "../store";
import { NotFoundView } from "../ui/feedback/NotFoundView";
import { PlanningPane } from "./workspace/PlanningPane";
import { RailToggle, useRail } from "./workspace/rail";
import { RunPane } from "./workspace/RunPane";

/**
 * The workspace. While planning (no run yet) the conversation IS the surface:
 * a centred single-column chat — parts, scope chips and the ready plan card
 * all live inline, and no right pane competes for attention (028 strand 3;
 * the interviews' split-attention finding). Once an analysis exists the
 * two-pane layout returns: chat left, journey right, defaulting to an even
 * 50/50 split (028 strand 4) with the 027 collapsible/resizable rail.
 */
export function WorkspaceView() {
  const { projectId = "" } = useParams();
  const project = useProject(projectId);
  const stream = useRunStream(projectId);
  const hasRun = stream.run !== null;
  const rail = useRail("50%");
  useDocumentTitle(project.data?.name, "Workspace");

  // Query errors are the raw envelope body ({error: {code}}), thrown as-is.
  const errorCode = (project.error as { error?: { code?: string } } | null)?.error?.code;
  if (project.isError && errorCode === "not_found") {
    return <NotFoundView />;
  }

  if (!hasRun) {
    return (
      <main className="mx-auto min-h-[calc(100svh-58px)] max-w-[760px] bg-paper lg:border-x lg:border-line">
        <PlanningPane projectId={projectId} runStatus={stream.run?.status} stream={stream} />
      </main>
    );
  }

  // minmax(0, …) on both grid tracks: a bare 1fr sizes to max-content and
  // lets long unwrappable content (the plan header row) blow the grid past
  // the viewport — truncation can never engage (owner feedback, 2026-07-29:
  // "the workspace expands too wide").
  return (
    <main
      className="mx-auto grid min-h-[calc(100svh-58px)] max-w-[1440px] grid-cols-1 lg:grid-cols-[minmax(0,var(--chat))_minmax(0,1fr)]"
      style={{ "--chat": rail.width } as React.CSSProperties}
    >
      <div className="relative min-w-0 border-r border-line bg-paper">
        <div className="flex justify-end border-b border-line p-1">
          <RailToggle collapsed={rail.collapsed} toggleProps={rail.toggleProps} />
        </div>
        <div id={rail.regionId} hidden={rail.collapsed}>
          <PlanningPane projectId={projectId} runStatus={stream.run?.status} stream={stream} />
        </div>
        {!rail.collapsed && (
          <div
            {...rail.separatorProps}
            className="absolute inset-y-0 -right-1 z-10 hidden w-2 cursor-col-resize hover:bg-blue-tint focus-visible:bg-blue-tint focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue lg:block"
          />
        )}
      </div>
      <div className="min-w-0 bg-ground">
        <RunPane projectId={projectId} stream={stream} />
      </div>
    </main>
  );
}
