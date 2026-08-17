import { useLayoutEffect, useRef, useState } from "react";
import { Link } from "react-router";

import { useCheckIns, useDecisions, useRuns } from "../../api/queries";
import { useComposerSeed } from "../../lib/composerSeed";
import { scrub } from "../../lib/scrub";
import { composePlanningThread, usePlanningTranscript } from "../../store";
import type {
  OptimisticPlanningTurn,
  PlanningThreadDecision,
  PlanningThreadItem,
  PlanningThreadRun,
  PlanningThreadTurn,
  ResolvedDecision,
  RunStatus,
  RunStreamState,
  RunThreadBoundary,
  RunThreadDecision,
  StageEntry,
} from "../../store";
import { Button } from "../../ui/brand/Button";
import { Divider, PaneHeading } from "../../ui/brand/Card";
import { conflictSentences, errorCode, isConflictCode } from "../../lib/errors";
import { ReauthRedirect } from "../../ui/feedback";
import { groupSearchDecisions } from "../decisionsPresentation";
import { AnsweredCheckIn } from "./AnsweredCheckIn";
import { CheckInCard } from "./CheckInCard";
import { PartCard, type PartState, confirmTarget, derivePartStates } from "./PartCard";
import { PlanCard } from "./PlanCard";
import { COMPONENT_LABEL, RUN_BLOCK_STATUS } from "./planVocabulary";

/** The server page-size cap; one planning conversation fits comfortably. */
const TRANSCRIPT_PAGE_SIZE = 200;

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

/**
 * The message composer: a bounded auto-growing textarea (Enter sends,
 * Shift+Enter inserts a newline) plus its keybinding hint. Split out from
 * `PlanningPane` so the Enter/Shift+Enter/disabled behaviour is unit-testable
 * without the transcript/run/decision store wiring.
 */
export function Composer({
  value,
  onChange,
  onSubmit,
  placeholder,
  disabled,
  sendDisabled,
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  placeholder: string;
  /** Textarea's own disabled state (027: honest-copy placeholder swap). */
  disabled: boolean;
  /** Send button's disabled state (027: also covers in-flight submission). */
  sendDisabled: boolean;
}) {
  return (
    <div>
      <form
        className="flex items-center gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
      >
        <label className="sr-only" htmlFor="planning-message">
          Message the planner
        </label>
        <textarea
          id="planning-message"
          rows={2}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key !== "Enter" || event.shiftKey) return;
            event.preventDefault();
            onSubmit();
          }}
          placeholder={placeholder}
          disabled={disabled}
          className="max-h-60 min-h-14 flex-1 resize-y overflow-y-auto border border-line-2 bg-paper px-3 py-2.5 text-body [field-sizing:content] focus-visible:outline-2 focus-visible:outline-blue disabled:bg-ground disabled:text-grey"
        />
        <Button
          type="submit"
          aria-label="Send"
          className="cutout-2 h-10 w-12 justify-center p-0"
          disabled={sendDisabled || value.trim().length === 0}
        >
          <svg
            aria-hidden="true"
            viewBox="0 0 24 24"
            className="h-5 w-5"
            fill="none"
            stroke="currentColor"
            strokeWidth={2.5}
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 19V5" />
            <path d="m5 12 7-7 7 7" />
          </svg>
        </Button>
      </form>
      <p className="mt-1 text-caption text-grey">Enter to send · Shift+Enter for a new line</p>
    </div>
  );
}

function UserBubble({ text }: { text: string }) {
  return (
    <div className="anim-rise ml-8 border border-blue-tint bg-blue-tint-2 px-3.5 py-2.5">
      <p className="max-w-prose-measure whitespace-pre-wrap text-body text-ink">{scrub(text)}</p>
    </div>
  );
}

/** Planner replies are plain text — no box (binding record: planning-stage
 *  `.planner`); only part cards and the plan card are bordered. */
function PlannerBubble({ text }: { text: string }) {
  return (
    <div className="anim-rise mr-8">
      <p className="max-w-prose-measure whitespace-pre-wrap text-body text-ink">{scrub(text)}</p>
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
  partState,
  onSend,
  onPrefill,
}: {
  turn: PlanningThreadTurn;
  isLatest: boolean;
  onRetry: (input: { message: string; clientTurnId: string }) => void;
  retryDisabled: boolean;
  partState: PartState | undefined;
  onSend: (message: string) => void;
  onPrefill: (message: string) => void;
}) {
  // A button-confirm turn's record is the ✓ on its part card — the canned
  // marker bubble would only duplicate it (binding record: planning-stage).
  const isConfirmTurn = confirmTarget(turn.user_message) !== null;
  return (
    <div className="space-y-3">
      {!isConfirmTurn && <UserBubble text={turn.user_message} />}
      {turn.status === "completed" && turn.reply !== null && turn.reply !== "" && (
        <PlannerBubble text={turn.reply} />
      )}
      {turn.part != null && partState !== undefined && (
        <PartCard
          part={turn.part}
          state={partState}
          disabled={retryDisabled}
          onSend={onSend}
          onPrefill={onPrefill}
        />
      )}
      {turn.status === "pending" && (
        <p role="status" className="mr-8 px-3.5 text-body text-grey">
          This turn didn't finish — it will retry or expire shortly.
        </p>
      )}
      {turn.status === "failed" && (
        <div className="mr-8 border border-red-tint bg-red-tint/40 px-3.5 py-2.5">
          <p className="text-body text-ink">This turn didn't complete.</p>
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
interface PresentedRunDecision {
  sequence: number;
  summary: string;
  count: number;
}

/** Convert the decision-log feed into quiet, user-facing thread echoes.
 * Search grouping delegates to the shared decision presentation helper; the
 * remaining adjacent duplicate collapse is limited to this compact rail. */
export function presentRunDecisions(
  decisions: PlanningThreadDecision[],
  stages: StageEntry[],
): PresentedRunDecision[] {
  const labelled = decisions.flatMap((decision) => {
    if (decision.kind !== "component.completed") return [decision];
    const detail = decision.detail;
    const component =
      detail !== null && typeof detail === "object" && !Array.isArray(detail)
        ? [detail.component, detail.stage, detail.registry_component].find(
            (value): value is string => typeof value === "string",
          )
        : undefined;
    const stageLabel =
      (component === undefined ? undefined : [...stages].reverse().find((stage) => stage.stage === component)?.label)
      ?? (component === undefined ? undefined : COMPONENT_LABEL[component]);
    return stageLabel === undefined ? [] : [{ ...decision, summary: `Completed: ${stageLabel}` }];
  });

  const searchGrouped: PresentedRunDecision[] = [];
  for (let index = 0; index < labelled.length; index += 1) {
    const entry = labelled[index];
    if (entry.kind !== "search.executed" || labelled[index - 1]?.kind === "search.executed") continue;
    const consecutive: PlanningThreadDecision[] = [];
    for (let cursor = index; labelled[cursor]?.kind === "search.executed"; cursor += 1) {
      consecutive.push(labelled[cursor]);
    }
    const grouped = groupSearchDecisions(consecutive)[0];
    if (grouped !== undefined) {
      searchGrouped.push({
        sequence: grouped.sequence,
        summary: entry.summary.replace(/\.$/, ""),
        count: consecutive.length,
      });
    }
  }
  const nonSearch = labelled
    .filter((entry) => entry.kind !== "search.executed")
    .map((entry) => ({ sequence: entry.sequence, summary: entry.summary, count: 1 }));
  const ordered = [...searchGrouped, ...nonSearch].sort((left, right) => left.sequence - right.sequence);

  return ordered.reduce<PresentedRunDecision[]>((entries, entry) => {
    const previous = entries.at(-1);
    if (previous !== undefined && previous.summary === entry.summary) {
      previous.count += entry.count;
      return entries;
    }
    entries.push(entry);
    return entries;
  }, []);
}

function RunBlock({
  projectId,
  run,
  decisions,
  stages,
  answered,
  checkIns,
}: {
  projectId: string;
  run: PlanningThreadRun;
  decisions: PlanningThreadDecision[];
  stages: StageEntry[];
  answered: ResolvedDecision[];
  checkIns: ReturnType<typeof useCheckIns>["data"];
}) {
  const status = RUN_BLOCK_STATUS[run.status] ?? null;
  const presentedDecisions = presentRunDecisions(decisions, stages);
  const complete = run.status === "succeeded" || run.status === "degraded";
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-caption text-grey">
        <span aria-hidden="true" className="h-px flex-1 bg-line" />
        <span>Analysis run{status !== null ? ` — ${status}` : ""}</span>
        <span aria-hidden="true" className="h-px flex-1 bg-line" />
      </div>
      {presentedDecisions.map((decision) => (
        <div
          key={decision.sequence}
          className="mx-4 border-l-2 border-l-yellow bg-yellow-tint/50 px-3 py-2"
        >
          <p className="text-body text-ink">
            {scrub(decision.summary)}{decision.count > 1 ? ` × ${decision.count}` : ""}
          </p>
        </div>
      ))}
      {answered.map((decision) => (
        <AnsweredCheckIn
          key={decision.checkInId}
          decision={decision}
          checkIn={checkIns?.data.find((checkIn) => checkIn.check_in_id === decision.checkInId)}
        />
      ))}
      {/* The chat's own destination once the run lands (owner, 2026-08-05):
          a completed run's last word shouldn't be a quiet stage echo. */}
      {complete && (
        <div className="anim-rise mr-8 border border-green-tint bg-green-tint/40 px-4 py-3">
          <p className="text-body font-semibold text-navy">The evidence base is ready.</p>
          <Link
            to={`/projects/${projectId}/results`}
            className="cutout mt-2 inline-block bg-blue px-3 py-2 text-meta font-bold text-white"
          >
            Read the evidence base
          </Link>
        </div>
      )}
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
  stream,
}: {
  projectId: string;
  runStatus: RunStatus | undefined;
  stream: RunStreamState;
}) {
  const transcript = usePlanningTranscript(projectId, { page_size: TRANSCRIPT_PAGE_SIZE });
  const runsQuery = useRuns(projectId, { page_size: TRANSCRIPT_PAGE_SIZE });
  const decisionsQuery = useDecisions(projectId, { page_size: TRANSCRIPT_PAGE_SIZE });
  const checkInsQuery = useCheckIns(projectId, "all");
  const [message, setMessage] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  // The plan document's "Change this" seeds this composer rather than writing
  // to the plan — editing a plan stays conversational.
  useComposerSeed(setMessage);

  const durableTurns = (transcript.data?.data ?? []) as PlanningThreadTurn[];
  const { boundaries, runDecisions } = threadInputs(
    durableTurns,
    runsQuery.data?.data ?? [],
    decisionsQuery.data?.data ?? [],
  );
  const thread: PlanningThreadItem[] = composePlanningThread(durableTurns, boundaries, runDecisions);
  const latestTurnIndex =
    durableTurns.length > 0 ? Math.max(...durableTurns.map((turn) => turn.turn_index)) : null;
  const partStates = derivePartStates(durableTurns);

  const runActive = runStatus === "running" || runStatus === "paused";
  const composerDisabled = runActive || transcript.isSubmitting;

  // Chat scroll: pinned to the bottom (newest messages) unless the user has
  // scrolled up to read history; new content re-pins only when near-bottom.
  // A ResizeObserver on the thread content catches growth the pane itself
  // never renders for (child-owned queries like the plan card, disclosure
  // toggles, font loads).
  const scrollRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const pinnedToBottom = useRef(true);
  useLayoutEffect(() => {
    const el = scrollRef.current;
    const content = contentRef.current;
    if (el === null || content === null) return;
    const pin = () => {
      if (pinnedToBottom.current) el.scrollTop = el.scrollHeight;
    };
    pin();
    const observer = new ResizeObserver(pin);
    observer.observe(content);
    return () => observer.disconnect();
  }, []);

  // The plan card sits at its chronological position: right after the last
  // planning turn (approval always comes from a turn; turns are 409-fenced
  // during runs), so a started run's block renders BELOW it, not above.
  const lastTurnAt = thread.findLastIndex((item) => item.type === "planning_turn");
  const planCardAt = lastTurnAt === -1 ? thread.length : lastTurnAt + 1;
  const planStarted = thread.slice(planCardAt).some((item) => item.type === "run_block");

  const send = (input: { message: string; clientTurnId: string }) => {
    const trimmed = input.message.trim();
    if (trimmed.length === 0 || composerDisabled) return;
    setMessage("");
    void transcript
      .send({ message: trimmed, clientTurnId: input.clientTurnId })
      .then((result) => setSuggestions(result?.suggestions ?? []))
      .catch(() => setSuggestions([]));
  };

  // The landing (no conversation yet) is a bare centred prompt — no pane
  // heading, no helper copy (Claude design concept; owner, 2026-08-05).
  const landing =
    transcript.data !== undefined && thread.length === 0 && transcript.optimisticTurns.length === 0;

  return (
    <section aria-label="Planning conversation" className="flex h-full flex-col">
      {!landing && (
        <>
          <PaneHeading>Plan the analysis</PaneHeading>
          <Divider />
        </>
      )}
      <div
        ref={scrollRef}
        onScroll={(event) => {
          const el = event.currentTarget;
          pinnedToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
        }}
        className="flex flex-1 flex-col overflow-y-auto px-4 py-4"
      >
        {/* Bottom-anchor: pushes a short thread to the composer end; the
            landing prompt sits in the top third (1:2 spacer split). */}
        <div aria-hidden="true" className={landing ? "flex-[1]" : "mt-auto"} />
        <div ref={contentRef} className="space-y-3">
        {transcript.isPending && (
          <div role="status" className="anim-breathe text-body text-grey">
            Loading your planning conversation…
          </div>
        )}
        {transcript.isError &&
          (errorCode(transcript.error) === "unauthenticated" ? (
            <ReauthRedirect />
          ) : (
            <div role="status" className="text-body text-grey">
              <p>Your planning conversation couldn't be loaded.</p>
              <Button
                size="sm"
                variant="secondary"
                className="mt-2"
                onClick={() => void transcript.refetch()}
              >
                Try again
              </Button>
            </div>
          ))}
        {landing && (
          <h2 className="text-center font-display text-title font-bold text-navy">
            What do you need evidence on?
          </h2>
        )}

        {thread.flatMap((item, index) => {
          const rendered =
            item.type === "planning_turn" ? (
              <DurableTurn
                key={`turn-${item.turn.turn_index}`}
                turn={item.turn}
                isLatest={item.turn.turn_index === latestTurnIndex}
                onRetry={send}
                retryDisabled={composerDisabled}
                partState={partStates.get(item.turn.turn_index)}
                onSend={(text) => send({ message: text, clientTurnId: crypto.randomUUID() })}
                onPrefill={setMessage}
              />
            ) : (
              <RunBlock
                key={`run-${item.run.capability_run_id}`}
                projectId={projectId}
                run={item.run}
                decisions={item.decisions}
                stages={stream.stages}
                answered={
                  item.run.capability_run_id === stream.run?.id ? stream.decisions : []
                }
                checkIns={checkInsQuery.data}
              />
            );
          return index === planCardAt - 1
            ? [rendered, <PlanCard key="plan-card" projectId={projectId} runActive={runActive} started={planStarted} />]
            : [rendered];
        })}

        {transcript.optimisticTurns.map((turn: OptimisticPlanningTurn) => (
          <div key={turn.clientTurnId} className="space-y-3">
            {/* Button-confirm turns never show a bubble — durable turns hide
                them too; the ✓ on the part card is the record. */}
            {confirmTarget(turn.userMessage) === null && <UserBubble text={turn.userMessage} />}
            {turn.status === "failed" && (
              <div className="mr-8 border border-line bg-paper px-3.5 py-2.5">
                <p className="text-body text-ink">
                  {isConflictCode(turn.errorCode)
                    ? conflictSentences[turn.errorCode]
                    : "That turn couldn't be processed. Your draft so far is unchanged."}
                </p>
                {turn.errorCode === "stale_turn" ? (
                  // Retrying the same client_turn_id can never clear a
                  // stale_turn conflict — offer the refresh instead.
                  <Button
                    size="sm"
                    variant="secondary"
                    className="mt-2"
                    onClick={() => transcript.discard(turn.clientTurnId)}
                  >
                    Refresh conversation
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    variant="secondary"
                    className="mt-2"
                    disabled={composerDisabled}
                    onClick={() => void transcript.retry(turn.clientTurnId)}
                  >
                    Retry
                  </Button>
                )}
              </div>
            )}
          </div>
        ))}

        {transcript.isSubmitting && (
          <div role="status" className="anim-breathe mr-8 flex items-center gap-2 px-3.5 text-body text-grey">
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
                className="anim-rise cursor-pointer border border-blue-tint bg-blue-tint px-2.5 py-1 text-caption font-semibold text-blue hover:bg-blue-tint-2 focus-visible:outline-2 focus-visible:outline-blue"
              >
                {scrub(suggestion)}
              </button>
            ))}
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
        </div>
        {landing && <div aria-hidden="true" className="flex-[2]" />}
      </div>

      <div className="border-t border-line px-4 py-3">
        {runActive && (
          <p role="status" className="mb-2 text-body leading-relaxed text-grey">
            {runStatus === "paused"
              ? "The analysis is paused at a check-in above. Replanning unlocks when the run finishes."
              : "The analysis is running — steer it from its check-ins. Replanning unlocks when it finishes."}
          </p>
        )}
        <Composer
          value={message}
          onChange={setMessage}
          onSubmit={() => send({ message, clientTurnId: crypto.randomUUID() })}
          placeholder={
            runActive
              ? "Replanning is available after the run"
              : "Describe the policy question you need evidence for."
          }
          disabled={runActive}
          sendDisabled={composerDisabled}
        />
      </div>
    </section>
  );
}
