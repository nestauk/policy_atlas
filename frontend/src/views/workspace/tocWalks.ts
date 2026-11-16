import { useState } from "react";

import type { RunStreamState, StageEntry, TaskAgentThreadRun } from "../../store";
import { isFinished, walkKind } from "./runProgress";

type RunRef = NonNullable<RunStreamState["run"]>;

/*
 * A theory of change's automatic chain as one card (task 054's 058
 * alignment, decision 5, S3 and S10). The server runs a draft, then starts
 * the evidence check by itself and marks it as the draft's follow-on
 * (`RunOut.follows_capability_run_id`). The Task Agent thread draws the two
 * walks as one run card: the draft's rows first, one timer from the draft's
 * start, the check's finish words. A walk the reader starts keeps its own
 * card.
 */

/** How long a finished draft's card keeps reading "Running" while its check
 *  has not started: the check is minted as soon as the draft ends, so a
 *  longer gap means it was refused (the cost guard) and the card ends with
 *  the draft's own words. */
export const BETWEEN_WALKS_MS = 30_000;

/** The draft walks drawn inside their check's card, and each check's draft. */
export interface TocChain {
  /** Draft walk ids whose check is in the list: they get no card of their own. */
  joined: ReadonlySet<string>;
  /** The draft a check followed, by the check's id. */
  leadOf: ReadonlyMap<string, TaskAgentThreadRun>;
}

/**
 * Pair each check the server started by itself with the draft it followed.
 *
 * Args:
 *   runs: The task's walks from the runs read.
 *
 * Returns:
 *   The drafts to leave out of the thread and each check's draft.
 */
export function joinTocWalks(runs: readonly TaskAgentThreadRun[]): TocChain {
  const byId = new Map(runs.map((run) => [run.capability_run_id, run]));
  const joined = new Set<string>();
  const leadOf = new Map<string, TaskAgentThreadRun>();
  for (const run of runs) {
    const draftId = run.follows_capability_run_id;
    if (draftId == null) continue;
    const draft = byId.get(draftId);
    if (draft === undefined) continue;
    joined.add(draftId);
    leadOf.set(run.capability_run_id, draft);
  }
  return { joined, leadOf };
}

function endedMs(at: string | null | undefined): number | null {
  if (at == null || at === "") return null;
  const ms = Date.parse(at);
  return Number.isNaN(ms) ? null : ms;
}

/**
 * Whether a draft that has just finished still reads "Running": its check
 * is about to start (S10). A draft whose check is in the list, an upload's
 * read (the reader starts its check), a draft that ended badly and a gap
 * longer than `BETWEEN_WALKS_MS` (a refused check) do not.
 *
 * Args:
 *   run: The followed walk, as the stream has it.
 *   stages: Its steps.
 *   tocWalk: Its kind from the runs read, when the read has it.
 *   followed: A check that follows it is in the runs read.
 *   nowMs: The clock.
 *
 * Returns:
 *   True while the card should stay "Running" with the draft row done.
 */
export function waitsForCheck(
  run: Pick<RunRef, "status" | "endedAt"> | null,
  stages: StageEntry[],
  tocWalk: string | null | undefined,
  followed: boolean,
  nowMs: number,
): boolean {
  if (run === null || followed || !isFinished(run.status)) return false;
  if (walkKind("theory_of_change", stages, null, tocWalk) !== "toc_draft") return false;
  const ended = endedMs(run.endedAt);
  return ended !== null && nowMs - ended < BETWEEN_WALKS_MS;
}

/**
 * The draft a live check follows before the runs read has caught up with
 * the check: the newest walk in the read, when it is a draft that finished
 * well, has no check after it, and ended just before the live walk started.
 *
 * Args:
 *   runs: The task's walks from the runs read.
 *   live: The walk the stream follows.
 *   chain: The pairs already in the read.
 *
 * Returns:
 *   The draft, or null.
 */
export function pendingLead(
  runs: readonly TaskAgentThreadRun[],
  live: Pick<RunRef, "id" | "startedAt"> | null,
  chain: TocChain,
): TaskAgentThreadRun | null {
  if (live === null || runs.some((run) => run.capability_run_id === live.id)) return null;
  const newest = [...runs]
    .filter((run) => run.parent_capability_run_id == null)
    .sort((left, right) => left.started_at.localeCompare(right.started_at))
    .at(-1);
  if (newest === undefined || chain.joined.has(newest.capability_run_id)) return null;
  if (newest.toc_walk !== "draft" || !isFinished(newest.status as RunRef["status"])) return null;
  const ended = endedMs(newest.ended_at);
  const started = endedMs(live.startedAt);
  if (ended === null || started === null) return null;
  return started - ended < BETWEEN_WALKS_MS ? newest : null;
}

/**
 * When the run the stream follows started, counting a check from the draft
 * it followed (S10), for a surface with the stream and no runs read (the
 * run status bar). It remembers a draft that finished while this view was
 * mounted; a check that started within `BETWEEN_WALKS_MS` of its end takes
 * the draft's start. Without that memory (a page opened mid-check) it is the
 * check's own start.
 *
 * Args:
 *   run: The walk the stream follows, or null (not a theory of change).
 *   stages: Its steps.
 *
 * Returns:
 *   The start to time from, or undefined with no run.
 */
export function useChainStart(run: RunRef | null, stages: StageEntry[]): string | undefined {
  const [draft, setDraft] = useState<{ id: string; startedAt: string; endedAt: string } | null>(null);
  if (
    run !== null &&
    run.endedAt !== undefined &&
    draft?.id !== run.id &&
    isFinished(run.status) &&
    walkKind("theory_of_change", stages) === "toc_draft"
  ) {
    setDraft({ id: run.id, startedAt: run.startedAt, endedAt: run.endedAt });
  }
  if (run === null) return undefined;
  if (draft !== null && draft.id !== run.id) {
    const ended = endedMs(draft.endedAt);
    const started = endedMs(run.startedAt);
    if (ended !== null && started !== null && started - ended < BETWEEN_WALKS_MS) return draft.startedAt;
  }
  return run.startedAt;
}
