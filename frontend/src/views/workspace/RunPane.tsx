import { useStartRun } from "../../api/mutations";
import { scrub } from "../../lib/scrub";
import type { RunStreamState, StageEntry } from "../../store/types";
import { Button } from "../../ui/brand/Button";
import { Card, Divider, PaneHeading, StatusDot } from "../../ui/brand/Card";
import { Chip } from "../../ui/brand/Chip";
import { InterruptedRunCard, ReconnectingBanner } from "../../ui/feedback";
import { CheckInCard } from "./CheckInCard";

function stageDot(status: StageEntry["status"]): "running" | "complete" | "failed" | "idle" {
  switch (status) {
    case "started":
      return "running";
    case "completed":
      return "complete";
    case "failed":
      return "failed";
    case "skipped":
      return "idle";
  }
}

function summarySentence(entry: StageEntry): string | null {
  if (entry.status === "failed" || entry.status === "skipped") {
    const reason = entry.summary?.reason;
    if (typeof reason === "string" && reason.length > 0) return reason;
    return entry.status === "skipped"
      ? "Skipped — its prerequisite didn't complete."
      : "This stage failed. The analysis carries on from what succeeded.";
  }
  if (entry.summary === undefined) return null;
  const counts = Object.entries(entry.summary)
    .filter(([key, value]) => key !== "reason" && (typeof value === "number" || typeof value === "string"))
    .slice(0, 4)
    .map(([key, value]) => `${key.replaceAll("_", " ")}: ${String(value)}`);
  return counts.length > 0 ? counts.join(" · ") : null;
}

/**
 * The workspace run pane: execution-order stage timeline (one card per
 * stage, outcome-first), the live activity feed (ephemeral ticks — never
 * state-bearing), the pending check-in at its chain position, and honest
 * terminal states (interrupted runs are not resumable — a fresh run is).
 */
export function RunPane({
  projectId,
  stream,
}: {
  projectId: string;
  stream: RunStreamState;
}) {
  const startRun = useStartRun(projectId);
  const runStatus = stream.run?.status;
  const liveNotes = Object.entries(stream.liveness).slice(-4);

  return (
    <section aria-label="Analysis progress" className="flex h-full flex-col">
      <PaneHeading>Analysis</PaneHeading>
      <Divider />
      <ReconnectingBanner connectionStatus={stream.connectionStatus} />
      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {runStatus === undefined && (
          <p role="status" className="text-[12.5px] text-grey">
            Nothing has run yet. Approve a plan on the left, then start the analysis.
          </p>
        )}

        {runStatus === "paused" && stream.pendingCheckIn === null && (
          <Chip tone="yellow">
            <StatusDot tone="paused" /> Paused — loading the check-in…
          </Chip>
        )}

        <ol aria-label="Stage timeline" className="space-y-2">
          {stream.stages.map((entry, index) => (
            <li key={`${entry.stage}-${index}`}>
              <Card className="px-3.5 py-2.5">
                <div className="flex items-center gap-2.5">
                  <StatusDot tone={stageDot(entry.status)} />
                  <span className="text-[13px] font-bold text-navy">{entry.label}</span>
                  {entry.status === "skipped" && <Chip tone="soft">Skipped</Chip>}
                  {entry.status === "failed" && <Chip tone="red">Failed</Chip>}
                  {typeof entry.seconds === "number" && entry.status === "completed" && (
                    <span className="ml-auto text-[11px] text-grey">
                      {Math.round(entry.seconds)}s
                    </span>
                  )}
                </div>
                {entry.status === "started" &&
                  entry.blurb !== undefined &&
                  entry.blurb.length > 0 && (
                    <p className="mt-1 pl-[18px] text-[12px] text-grey">{entry.blurb}</p>
                  )}
                {summarySentence(entry) !== null && (
                  <p className="mt-1 pl-[18px] text-[12px] text-grey">
                    {scrub(summarySentence(entry) ?? "")}
                  </p>
                )}
              </Card>
            </li>
          ))}
        </ol>

        {stream.pendingCheckIn !== null && (
          <CheckInCard projectId={projectId} checkIn={stream.pendingCheckIn} />
        )}

        {runStatus === "running" && liveNotes.length > 0 && (
          <div aria-live="polite" aria-label="Live activity" className="space-y-1 pl-1">
            {liveNotes.map(([stage, note]) => (
              <p key={stage} className="text-[11.5px] text-grey">
                <span aria-hidden="true" className="text-line-2">
                  ·
                </span>{" "}
                {scrub(note.note)}
              </p>
            ))}
          </div>
        )}

        {runStatus === "interrupted" && (
          <InterruptedRunCard onStartFreshRun={() => startRun.mutate()} />
        )}

        {(runStatus === "succeeded" || runStatus === "degraded") && (
          <Card role="status" className="border-l-2 border-l-green p-4">
            <p className="text-[13px] font-bold text-navy">
              {runStatus === "succeeded"
                ? "The analysis is complete."
                : "The analysis completed with gaps."}
            </p>
            <p className="mt-1 text-[12.5px] text-grey">
              The evidence base is ready to read — open it from the navigation above.
            </p>
          </Card>
        )}

        {runStatus === "failed" && (
          <Card role="alert" className="border-l-2 border-l-red p-4">
            <p className="text-[13px] font-bold text-navy">The analysis failed.</p>
            <p className="mt-1 text-[12.5px] text-grey">
              Whatever completed is kept and readable. You can start a fresh run.
            </p>
            <Button
              className="mt-3"
              size="sm"
              disabled={startRun.isPending}
              onClick={() => startRun.mutate()}
            >
              Start a fresh run
            </Button>
          </Card>
        )}
      </div>
    </section>
  );
}
