import { useState } from "react";

import { useDecisions, useRuns } from "../../api/queries";
import { scrub } from "../../lib/scrub";
import { composePlanningThread, usePlanningTranscript } from "../../store";
import type {
  OptimisticPlanningTurn,
  PlanningThreadDecision,
  PlanningThreadItem,
  PlanningThreadRun,
  PlanningThreadTurn,
  RunStatus,
  RunThreadBoundary,
  RunThreadDecision,
} from "../../store";
import { Button } from "../../ui/brand/Button";
import { Divider, PaneHeading } from "../../ui/brand/Card";

/** The server page-size cap; one planning conversation fits comfortably. */
const TRANSCRIPT_PAGE_SIZE = 200;

const RUN_BLOCK_STATUS: Record<string, string> = {
  running: "running",
  paused: "paused",
  succeeded: "completed",
  degraded: "completed with gaps",
  failed: "failed",
  interrupted: "interrupted",
  aborted: "stopped",
};

/**
 * Assign each run its turn boundary and each decision its run block. Planning
 * turns are 409-fenced while a run executes or parks, so a turn's receipt
 * time genuinely falls outside every run window — comparing it to run starts
 * only ANCHORS blocks; ordering within lists stays `turn_index` (turns) and
 * event-log `sequence` (decisions), never timestamps.
 */
export function threadInputs(
  turns: PlanningThreadTurn[],
  runs: PlanningThreadRun[],
  decisions: PlanningThreadDecision[],
): { boundaries: RunThreadBoundary[]; runDecisions: RunThreadDecision[] } {
  const boundaries = runs.map((run) => {
    const before = turns.filter((turn) => turn.created_at <= run.started_at);
    return {
      run,
      afterTurnIndex: before.length > 0 ? Math.max(...before.map((turn) => turn.turn_index)) : null,
    };
  });
  const orderedRuns = [...runs].sort((left, right) => left.started_at.localeCompare(right.started_at));
  const runDecisions: RunThreadDecision[] = [];
  for (const decision of decisions) {
    const owner = orderedRuns.findLast(
      (run) =>
        run.started_at <= decision.occurred_at &&
        (run.ended_at === null || run.ended_at === undefined || decision.occurred_at <= run.ended_at),
    );
    if (owner !== undefined) {
      runDecisions.push({ decision, capabilityRunId: owner.capability_run_id });
    }
  }
  return { boundaries, runDecisions };
}

function UserBubble({ text }: { text: string }) {
  return (
    <div className="anim-rise ml-8 border border-blue-tint bg-blue-tint-2 px-3.5 py-2.5">
      <p className="whitespace-pre-wrap text-[12.5px] leading-relaxed text-ink">{scrub(text)}</p>
    </div>
  );
}

function PlannerBubble({ text }: { text: string }) {
  return (
    <div className="anim-rise mr-8 border border-line bg-paper px-3.5 py-2.5">
      <p className="whitespace-pre-wrap text-[12.5px] leading-relaxed text-ink">{scrub(text)}</p>
    </div>
  );
}

/** A durable turn: user bubble, then the planner reply — or an honest
 *  incomplete row (pending spinner copy / failed with retry). */
function DurableTurn({
  turn,
  isLatest,
  onRetry,
  retryDisabled,
}: {
  turn: PlanningThreadTurn;
  isLatest: boolean;
  onRetry: (input: { message: string; clientTurnId: string }) => void;
  retryDisabled: boolean;
}) {
  return (
    <div className="space-y-3">
      <UserBubble text={turn.user_message} />
      {turn.status === "completed" && turn.reply !== null && <PlannerBubble text={turn.reply} />}
      {turn.status === "pending" && (
        <p role="status" className="mr-8 px-3.5 text-[12.5px] text-grey">
          This turn didn't finish — it will retry or expire shortly.
        </p>
      )}
      {turn.status === "failed" && (
        <div className="mr-8 border border-red-tint bg-red-tint/40 px-3.5 py-2.5">
          <p className="text-[12.5px] text-ink">This turn didn't complete.</p>
          {isLatest && (
            <Button
              size="sm"
              variant="secondary"
              className="mt-2"
              disabled={retryDisabled}
              onClick={() => onRetry({ message: turn.user_message, clientTurnId: turn.client_turn_id })}
            >
              Retry
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

/** A run block in the thread: a quiet divider row naming the run and its
 *  outcome, with any steering decisions echoed inside it. */
function RunBlock({ run, decisions }: { run: PlanningThreadRun; decisions: PlanningThreadDecision[] }) {
  const status = RUN_BLOCK_STATUS[run.status] ?? null;
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-[11.5px] text-grey">
        <span aria-hidden="true" className="h-px flex-1 bg-line" />
        <span>Analysis run{status !== null ? ` — ${status}` : ""}</span>
        <span aria-hidden="true" className="h-px flex-1 bg-line" />
      </div>
      {decisions.map((decision) => (
        <div
          key={decision.sequence}
          className="mx-4 border-l-2 border-l-yellow bg-yellow-tint/50 px-3 py-2"
        >
          <p className="text-[12px] text-ink">{scrub(decision.summary)}</p>
        </div>
      ))}
    </div>
  );
}

/**
 * The planning conversation, rendered from the durable transcript (strand 12):
 * it survives navigation and restarts. Message bubbles, the thinking row,
 * tappable suggestion chips, run blocks with their steering-decision echoes,
 * and the composer — which disables honestly while a run executes or parks
 * (planning turns 409 then; check-ins are the sanctioned steering channel).
 */
export function PlanningPane({
  projectId,
  runStatus,
}: {
  projectId: string;
  runStatus: RunStatus | undefined;
}) {
  const transcript = usePlanningTranscript(projectId, { page_size: TRANSCRIPT_PAGE_SIZE });
  const runsQuery = useRuns(projectId, { page_size: TRANSCRIPT_PAGE_SIZE });
  const decisionsQuery = useDecisions(projectId, { page_size: TRANSCRIPT_PAGE_SIZE });
  const [message, setMessage] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>([]);

  const durableTurns = (transcript.data?.data ?? []) as PlanningThreadTurn[];
  const { boundaries, runDecisions } = threadInputs(
    durableTurns,
    runsQuery.data?.data ?? [],
    decisionsQuery.data?.data ?? [],
  );
  const thread: PlanningThreadItem[] = composePlanningThread(durableTurns, boundaries, runDecisions);
  const latestTurnIndex =
    durableTurns.length > 0 ? Math.max(...durableTurns.map((turn) => turn.turn_index)) : null;

  const runActive = runStatus === "running" || runStatus === "paused";
  const composerDisabled = runActive || transcript.isSubmitting;

  const send = (input: { message: string; clientTurnId: string }) => {
    const trimmed = input.message.trim();
    if (trimmed.length === 0 || composerDisabled) return;
    setMessage("");
    void transcript
      .send({ message: trimmed, clientTurnId: input.clientTurnId })
      .then((result) => setSuggestions(result?.suggestions ?? []))
      .catch(() => setSuggestions([]));
  };

  return (
    <section aria-label="Planning conversation" className="flex h-full flex-col">
      <PaneHeading>Plan the analysis</PaneHeading>
      <Divider />
      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {thread.length === 0 && transcript.optimisticTurns.length === 0 && (
          <div role="status" className="text-[12.5px] leading-relaxed text-grey">
            <p>
              Describe the policy question you need evidence for. The planner refines it with
              you into an analysis plan you approve before anything runs.
            </p>
            <p className="mt-2 text-[11.5px]">Your conversation is kept — it survives restarts.</p>
          </div>
        )}

        {thread.map((item) =>
          item.type === "planning_turn" ? (
            <DurableTurn
              key={`turn-${item.turn.turn_index}`}
              turn={item.turn}
              isLatest={item.turn.turn_index === latestTurnIndex}
              onRetry={send}
              retryDisabled={composerDisabled}
            />
          ) : (
            <RunBlock key={`run-${item.run.capability_run_id}`} run={item.run} decisions={item.decisions} />
          ),
        )}

        {transcript.optimisticTurns.map((turn: OptimisticPlanningTurn) => (
          <div key={turn.clientTurnId} className="space-y-3">
            <UserBubble text={turn.userMessage} />
            {turn.status === "failed" && (
              <div className="mr-8 border border-line bg-paper px-3.5 py-2.5">
                <p className="text-[12.5px] text-ink">
                  That turn couldn't be processed. Your draft so far is unchanged.
                </p>
                <Button
                  size="sm"
                  variant="secondary"
                  className="mt-2"
                  disabled={composerDisabled}
                  onClick={() => void transcript.retry(turn.clientTurnId)}
                >
                  Retry
                </Button>
              </div>
            )}
          </div>
        ))}

        {transcript.isSubmitting && (
          <div role="status" className="anim-breathe mr-8 flex items-center gap-2 px-3.5 text-[12.5px] text-grey">
            <span aria-hidden="true" className="h-2 w-2 bg-blue" />
            Planning…
          </div>
        )}

        {suggestions.length > 0 && !transcript.isSubmitting && !runActive && (
          <div className="flex flex-wrap gap-1.5">
            {suggestions.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                onClick={() => send({ message: suggestion, clientTurnId: crypto.randomUUID() })}
                className="anim-rise cursor-pointer border border-blue-tint bg-blue-tint px-2.5 py-1 text-[11.5px] font-semibold text-blue hover:bg-blue-tint-2 focus-visible:outline-2 focus-visible:outline-blue"
              >
                {scrub(suggestion)}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="border-t border-line px-4 py-3">
        {runActive && (
          <p role="status" className="mb-2 text-[11.5px] leading-relaxed text-grey">
            {runStatus === "paused"
              ? "The analysis is paused at a check-in — answer it in the Analysis pane. Replanning unlocks when the run finishes."
              : "The analysis is running — steer it from its check-ins. Replanning unlocks when it finishes."}
          </p>
        )}
        <form
          className="flex items-center gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            send({ message, clientTurnId: crypto.randomUUID() });
          }}
        >
          <label className="sr-only" htmlFor="planning-message">
            Message the planner
          </label>
          <input
            id="planning-message"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder={runActive ? "Replanning is available after the run" : "What do you need evidence on?"}
            disabled={runActive}
            className="flex-1 border border-line-2 bg-paper px-3 py-2.5 text-[13px] focus-visible:outline-2 focus-visible:outline-blue disabled:bg-ground disabled:text-grey"
          />
          <Button type="submit" variant="secondary" disabled={composerDisabled}>
            Send
          </Button>
        </form>
      </div>
    </section>
  );
}
