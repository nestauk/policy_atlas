import { useStartRun } from "../../api/mutations";
import { useCoverage, useFunnel, useGroups, useLandscape, usePlan } from "../../api/queries";
import type { RunStreamState } from "../../store/types";
import { Button } from "../../ui/brand/Button";
import { Chip } from "../../ui/brand/Chip";
import { Divider, PaneHeading, StatusDot } from "../../ui/brand/Card";
import { InterruptedRunCard, ReconnectingBanner } from "../../ui/feedback";
import { AnsweredCheckIn } from "./AnsweredCheckIn";
import { CheckInCard } from "./CheckInCard";
import { JourneyPane } from "./journey/JourneyPane";

/**
 * The workspace run pane composes the journey's durable read models around
 * the authoritative SSE stream. Check-ins retain their precise chain
 * position; artefact streaming deliberately remains owned by the artefact
 * view (027 E.3).
 */
export function RunPane({ projectId, stream }: { projectId: string; stream: RunStreamState }) {
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
          <p role="status" className="max-w-xs text-center text-[12.5px] text-grey">
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
            coverage={coverage.data}
            groups={groups.data}
            landscape={landscape.data}
            checkIn={
              <>
                {runStatus === "paused" && stream.pendingCheckIn === null && (
                  <div className="px-1 py-1">
                    <Chip tone="yellow">
                      <StatusDot tone="paused" /> Paused — loading the check-in…
                    </Chip>
                  </div>
                )}
                {stream.pendingCheckIn !== null && (
                  <CheckInCard
                    key={stream.pendingCheckIn.check_in_id}
                    projectId={projectId}
                    checkIn={stream.pendingCheckIn}
                    stages={stream.stages}
                  />
                )}
                {stream.decisions.map((decision) => (
                  <AnsweredCheckIn key={decision.checkInId} decision={decision} />
                ))}
              </>
            }
            terminal={
              <>
                {runStatus === "interrupted" && <InterruptedRunCard onStartFreshRun={() => startRun.mutate()} />}
                {runStatus === "failed" && (
                  <div role="alert" className="border-l-2 border-l-red bg-paper p-4 shadow-[0_1px_3px_rgba(15,41,74,0.05)]">
                    <p className="text-[13px] font-bold text-navy">The analysis failed.</p>
                    <p className="mt-1 text-[12.5px] text-grey">Whatever completed is kept and readable. You can start a fresh run.</p>
                    <Button className="mt-3" size="sm" disabled={startRun.isPending} onClick={() => startRun.mutate()}>Start a fresh run</Button>
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
