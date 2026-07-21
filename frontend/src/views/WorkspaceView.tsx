import { useParams } from "react-router";

import { useProject } from "../api/queries";
import { useRunStream } from "../store";
import { NotFoundView } from "../ui/feedback/NotFoundView";
import { PlanningPane } from "./workspace/PlanningPane";
import { RunPane } from "./workspace/RunPane";

/**
 * The workspace: planning conversation left, analysis right. The chat pane
 * holds the room while planning (55/45) and shrinks once an analysis exists
 * (35/65) — the RETRO §2.3 split, driven by run presence, not a toggle.
 */
export function WorkspaceView() {
  const { projectId = "" } = useParams();
  const project = useProject(projectId);
  const stream = useRunStream(projectId);
  const hasRun = stream.run !== null;

  // Query errors are the raw envelope body ({error: {code}}), thrown as-is.
  const errorCode = (project.error as { error?: { code?: string } } | null)?.error?.code;
  if (project.isError && errorCode === "not_found") {
    return <NotFoundView />;
  }

  return (
    <main
      className="mx-auto grid min-h-[calc(100svh-58px)] max-w-[1440px] grid-cols-1 lg:grid-cols-[var(--chat)_1fr]"
      style={{ "--chat": hasRun ? "35%" : "55%" } as React.CSSProperties}
    >
      <div className="border-r border-line bg-paper">
        <PlanningPane projectId={projectId} />
      </div>
      <div className="bg-ground">
        <RunPane projectId={projectId} stream={stream} />
      </div>
    </main>
  );
}
