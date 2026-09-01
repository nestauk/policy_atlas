import { useStartRun } from "../../api/mutations";
import { useCoverage, useFunnel, useGroups, useLandscape, usePlan } from "../../api/queries";
import type { RunStreamState } from "../../store/types";
import { Button } from "../../ui/brand/Button";
import { Divider, PaneHeading } from "../../ui/brand/Card";
import { InterruptedRunCard, ReconnectingBanner } from "../../ui/feedback";
import { JourneyPane } from "./journey/JourneyPane";

/**
 * The workspace run pane composes the journey's durable read models around
 * the authoritative SSE stream. Check-ins retain their precise chain
 * position; artefact streaming deliberately remains owned by the artefact
 * view (027 E.3).
 *
 * `isOwner` (task 033 phase 10c, contract § 11 / rubric 37): starting a run
 * — including a fresh run after an interruption or failure — is an
 * owner-only mutation, hidden here the same way `VisibilityControl`
 * established rather than left clickable to a 403.
 */
export function RunPane({
  projectId,
  stream,
  isOwner,
}: {
  projectId: string;
  stream: RunStreamState;
  isOwner: boolean;
}) {
  const startRun = useStartRun(projectId);
  const plan = usePlan(projectId);
  const funnel = useFunnel(projectId);
  const coverage = useCoverage(projectId);
  const groups = useGroups(projectId);
  const landscape = useLandscape(projectId);
  const runStatus = stream.run?.status;

  return (
    <section aria-label="Analysis progress" className="flex h-full flex-col">
      <PaneHeading>Analysis</PaneHeading>
      <Divider />
      <ReconnectingBanner connectionStatus={stream.connectionStatus} />
      {runStatus === undefined ? (
        <div className="flex flex-1 items-center justify-center px-6">
          <p role="status" className="max-w-xs text-center text-body text-grey">
            Nothing has run yet. Approve a plan on the left, then start the analysis.
          </p>
        </div>
      ) : (
        <div className="flex-1 overflow-hidden">
          <JourneyPane
            projectId={projectId}
            stream={stream}
            plan={stream.plan?.plan ?? plan.data?.plan ?? null}
            funnel={funnel.data}
            coverage={coverage.data ?? undefined}
            groups={groups.data}
            landscape={landscape.data}
            terminal={
              <>
                {runStatus === "interrupted" && isOwner && (
                  <InterruptedRunCard onStartFreshRun={() => startRun.mutate()} />
                )}
                {runStatus === "failed" && (
                  <div role="alert" className="border-l-2 border-l-red bg-paper p-4 shadow-[0_1px_3px_rgba(15,41,74,0.05)]">
                    <p className="text-body font-bold text-navy">The analysis failed.</p>
                    <p className="mt-1 text-body text-grey">Whatever completed is kept and readable.{isOwner ? " You can start a fresh run." : ""}</p>
                    {isOwner && (
                      <Button className="mt-3" size="sm" disabled={startRun.isPending} onClick={() => startRun.mutate()}>Start a fresh run</Button>
                    )}
                  </div>
                )}
              </>
            }
          />
        </div>
      )}
    </section>
  );
}
