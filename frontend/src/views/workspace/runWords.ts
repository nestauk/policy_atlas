import { STALL_AFTER_MS, useFreshness } from "../../lib/freshness";
import { scrub } from "../../lib/scrub";
import type { RunStreamState } from "../../store";
import { cardRows, currentRow, rowDetail, rowLiveness, traceWords, type CardRow } from "./runProgress";

/**
 * What a run is doing now, in the trace header's words (task 058): the
 * current step and its activity ("Writing · Section 3 of 7 · Costs and
 * funding"), "Still working on this step" after two quiet minutes, and
 * "Paused · a check-in is waiting on you" (to a colleague, "Paused · <step>")
 * while a check-in waits. The rail's Task Agent mark and the run status bar read
 * these words; the trace in the thread works them out the same way.
 *
 * Args:
 *   stream: The task's run stream.
 *   isOwner: Only the owner is told a check-in waits on them.
 *
 * Returns:
 *   `words` (empty before the first stage frame), the current `row`, whether
 *   the run is `paused`, and the `fresh` flag (an update arrived in the last
 *   moment, for a breathing mark).
 */
export function useRunWords(stream: RunStreamState, isOwner: boolean) {
  const status = stream.run?.status;
  const rows = cardRows(stream.stages, stream.plan?.plan, status);
  const row: CardRow | null = currentRow(rows);
  const progress = row !== null && row.state === "progress" ? row : null;
  const tick = progress === null ? undefined : rowLiveness(progress, stream.liveness);
  const stamp = tick?.occurredAt ?? progress?.entries[0]?.startedAt;
  const quiet = !useFreshness(stamp, STALL_AFTER_MS);
  const fresh = useFreshness(tick?.occurredAt);
  const paused = status === "paused" || stream.pendingCheckIn != null;
  const stalled = progress !== null && stamp !== undefined && quiet && !paused;
  const words = scrub(traceWords(row, rowDetail(tick), paused ? "paused" : stalled ? "stalled" : "live", isOwner));
  return { words, row, paused, fresh };
}
