import { useState } from "react";
import { useParams } from "react-router";

import { useArtefact, useProject } from "../api/queries";
import { useDocumentTitle } from "../lib/title";
import { useRunStream } from "../store";
import { Button } from "../ui/brand/Button";
import { NotFoundView } from "../ui/feedback/NotFoundView";
import { PlanDocument } from "./workspace/PlanDocument";
import { PlanningPane } from "./workspace/PlanningPane";
import { ChatPane } from "./workspace/chat/ChatPane";
import { ChatsLibrary } from "./workspace/chat/ChatsLibrary";
import { ConversationTabs } from "./workspace/chat/ConversationTabs";
import { useActiveConversation } from "./workspace/chat/conversationState";
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
  const artefact = useArtefact(projectId);
  const stream = useRunStream(projectId);
  const hasRun = stream.run !== null;
  const rail = useRail("50%");
  const { activeConversationId, setActiveConversation } = useActiveConversation();
  const [libraryOpen, setLibraryOpen] = useState(false);
  // The plan opens on request rather than sitting open: progressive
  // disclosure, and the thread stays the surface a person works in.
  const [planOpen, setPlanOpen] = useState(false);
  useDocumentTitle(project.data?.name, "Plan");

  // Query errors are the raw envelope body ({error: {code}}), thrown as-is.
  const errorCode = (project.error as { error?: { code?: string } } | null)?.error?.code;
  if (project.isError && errorCode === "not_found") {
    return <NotFoundView />;
  }

  if (!hasRun) {
    // Full-bleed white page (no grey gutters, no column borders — owner,
    // 2026-08-05); the readable measure lives on the inner column.
    return (
      <main className="relative h-[calc(100svh-58px)] bg-paper">
        <div className="mx-auto h-full max-w-[760px]">
          <PlanningPane projectId={projectId} runStatus={stream.run?.status} stream={stream} />
        </div>
        <OpenPlanButton onOpen={() => setPlanOpen(true)} />
        {planOpen && <PlanDocument projectId={projectId} onClose={() => setPlanOpen(false)} />}
      </main>
    );
  }

  // minmax(0, …) on both grid tracks: a bare 1fr sizes to max-content and
  // lets long unwrappable content (the plan header row) blow the grid past
  // the viewport — truncation can never engage (owner feedback, 2026-07-29:
  // "the workspace expands too wide").
  return (
    <main
      className="relative mx-auto grid min-h-[calc(100svh-58px)] max-w-[1440px] grid-cols-1 lg:h-[calc(100svh-58px)] lg:grid-cols-[minmax(0,var(--chat))_minmax(0,1fr)]"
      style={{ "--chat": rail.width } as React.CSSProperties}
    >
      {/* lg: fixed viewport height so chat and journey scroll independently;
          below lg the stacked panes keep the page scroll. */}
      <div className="relative flex min-w-0 flex-col border-r border-line bg-paper lg:overflow-hidden">
        <div className="flex justify-end border-b border-line p-1">
          <RailToggle collapsed={rail.collapsed} toggleProps={rail.toggleProps} />
        </div>
        <div id={rail.regionId} hidden={rail.collapsed} className="min-h-0 flex-1">
          <div className="relative flex h-full min-h-0 flex-col">
            <ConversationTabs
              projectId={projectId}
              entryArtefactId={null}
              planningClosed={stream.run !== null && stream.run.status !== "running" && stream.run.status !== "paused"}
              onOpenLibrary={() => setLibraryOpen(true)}
            />
            <div className="min-h-0 flex-1">
              {activeConversationId === null ? <PlanningPane projectId={projectId} runStatus={stream.run?.status} stream={stream} /> : <ChatPane projectId={projectId} conversationId={activeConversationId} sectionTitles={(artefact.data?.sections ?? []).map((section) => section.title)} onOpenPlanning={() => setActiveConversation(null)} />}
            </div>
            <ChatsLibrary projectId={projectId} open={libraryOpen} onClose={() => setLibraryOpen(false)} />
          </div>
        </div>
        {!rail.collapsed && (
          <div
            {...rail.separatorProps}
            className="absolute inset-y-0 -right-1 z-10 hidden w-2 cursor-col-resize hover:bg-blue-tint focus-visible:bg-blue-tint focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue lg:block"
          />
        )}
      </div>
      <div className="min-w-0 bg-ground lg:overflow-hidden">
        <RunPane projectId={projectId} stream={stream} />
      </div>
      <OpenPlanButton onOpen={() => setPlanOpen(true)} />
      {planOpen && <PlanDocument projectId={projectId} onClose={() => setPlanOpen(false)} />}
    </main>
  );
}

/** The one affordance that opens the plan as a document. */
function OpenPlanButton({ onOpen }: { onOpen: () => void }) {
  return (
    <div className="absolute top-2 right-4 z-10">
      <Button variant="ghost" size="sm" onClick={onOpen}>
        Open the plan
      </Button>
    </div>
  );
}
