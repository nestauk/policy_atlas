import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";

import { useCheckIns, useDecisions, useFunnel, usePlan, useRuns } from "../../api/queries";
import { useComposerSeed } from "../../lib/composerSeed";
import { scrub } from "../../lib/scrub";
import { COPY, TASK } from "../../lib/vocabulary";
import {
  composeTaskAgentThread,
  taskAgentAnswerRow,
  taskAgentTurnKind,
  useTaskAgentTranscript,
} from "../../store";
import type {
  GateThreadInput,
  OptimisticTaskAgentTurn,
  TaskAgentThreadCheckIn,
  TaskAgentThreadDecision,
  TaskAgentThreadItem,
  TaskAgentThreadRun,
  TaskAgentThreadTurn,
  ResolvedDecision,
  RunStatus,
  RunStreamState,
  RunThreadBoundary,
  RunThreadDecision,
  StageEntry,
} from "../../store";
import { Button } from "../../ui/brand/Button";
import { cn } from "../../ui/brand/cn";
import { conflictSentences, errorCode, isConflictCode } from "../../lib/errors";
import { ReauthRedirect } from "../../ui/feedback";
import { groupSearchDecisions } from "../decisionsPresentation";
import { LIFECYCLE_PAGE_CLASS } from "../listPageChrome";
import { ChatAnswer } from "./chat/ChatMessages";
import { JumpToEnd } from "./chat/JumpToEnd";
import { useFooterReveal } from "./chat/useFooterReveal";
import { usePinToBottom } from "./chat/usePinToBottom";
import { sessionAnsweredCheckIn } from "../../store/thread";
import { AnsweredCheckIn } from "./AnsweredCheckIn";
import { CheckInCard } from "./CheckInCard";
import { BASELINE_GATE_KIND } from "./checkInPresentation";
import { PartCard, type PartState, confirmTarget, derivePartStates } from "./PartCard";
import { PlanCard } from "./PlanCard";
import type { PlanOverlay } from "./planOverlay";
import { COMPONENT_LABEL, RUN_BLOCK_STATUS } from "./planVocabulary";
import { RunningCard, RunningCardDock } from "./RunningCard";
import {
  completedSignposts,
  elapsedSeconds,
  formatElapsed,
  runFinishedSignpost,
} from "./runProgress";

/** The server page-size cap; one task_agent conversation fits comfortably. */
const TRANSCRIPT_PAGE_SIZE = 200;

/** The composer's invitation while a scoping walk is parked on the baseline
 *  gate (task 044 Phase 5.5, the Baseline board). */
const SCOPING_GATE_PLACEHOLDER = "Question the baseline…";

/** A decision turn's one line: the option as it was labelled, that it is on
 *  the record, and the plan version it was taken against. */
const DECISION_RECORDED = "recorded";

/** The prefix before a decision's plan version. */
const DECISION_PLAN_VERSION = "plan version";

/**
 * Assign each run its turn boundary and each decision its run block. TaskAgent
 * turns are 409-fenced while a run executes or parks, so a turn's receipt
 * time genuinely falls outside every run window — comparing it to run starts
 * only ANCHORS blocks; ordering within lists stays `turn_index` (turns) and
 * event-log `sequence` (decisions), never timestamps.
 */
export function threadInputs(
  turns: TaskAgentThreadTurn[],
  runs: TaskAgentThreadRun[],
  decisions: TaskAgentThreadDecision[],
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
 * The baseline gate's thread input: its card and any decision the CARD
 * endpoint recorded (task 044 Phase 5.5, D12).
 *
 * The live stream is preferred for the pending card — it arrives with the
 * pause — and the check-ins read supplies it after a reload. The decision is
 * read off `checkin.resolved` and labelled from the check-in's own options,
 * so the line shows the option exactly as it was offered; the client never
 * invents an option or a label.
 *
 * Args:
 *   stream: The run stream's current state.
 *   checkIns: The task's check-ins, pending and decided.
 *   planVersion: The plan's current version, shown on a card-endpoint
 *     decision (a `decision` TURN carries its own).
 *
 * Returns:
 *   The gate input, or null when this task has no baseline gate.
 */
export function baselineGateInput(
  stream: RunStreamState,
  checkIns: TaskAgentThreadCheckIn[],
  planVersion: number | null,
): GateThreadInput | null {
  const pending =
    stream.pendingCheckIn?.kind === BASELINE_GATE_KIND ? stream.pendingCheckIn : null;
  const checkIn = pending ?? checkIns.find((row) => row.kind === BASELINE_GATE_KIND) ?? null;
  if (checkIn === null) return null;
  const resolved = stream.decisions.find((entry) => entry.checkInId === checkIn.check_in_id) ?? null;
  if (resolved === null) return { checkIn, decision: null };
  const optionId = resolved.response["option_id"];
  const label =
    (checkIn.options ?? []).find((option) => option.id === optionId)?.label ??
    sessionAnsweredCheckIn(checkIn.check_in_id)?.chosenOptionLabel ??
    null;
  return {
    // A resolved decision is definitive: the read model may still be showing
    // the pre-decision row until its refetch lands.
    checkIn: { ...checkIn, status: "decided" },
    decision:
      label === null
        ? null
        : {
            checkInId: checkIn.check_in_id,
            label,
            planVersion,
            occurredAt: resolved.occurredAt,
          },
  };
}

/** Placeholder for the task_agent composer — task_agent/replanning, not follow-up Q&A.
 *
 * Args:
 *   runStatus: The task's current run status, or undefined before any run.
 *   planReady: True once the approved plan is ready to review and start.
 *   isOwner: Steering is owner-only (task 033 phase 10c, contract § 11 /
 *     rubric 37) — a non-owner always sees the same honest line, regardless
 *     of run state, the same idiom the run-state copy already uses rather
 *     than a "you cannot edit this" banner.
 *
 * Returns:
 *   Copy that matches the run and plan state.
 */
export function taskAgentComposerPlaceholder(
  runStatus: RunStatus | undefined,
  planReady = false,
  isOwner = true,
  atScopingGate = false,
): string {
  if (!isOwner) {
    return `Steering is limited to the ${TASK.lower} owner.`;
  }
  // Task 044 Phase 5.5: the scoping walk's one gate keeps the thread open —
  // a question about the baseline is exactly what this pause is for, so the
  // composer invites one instead of fencing it off.
  if (atScopingGate) {
    return SCOPING_GATE_PLACEHOLDER;
  }
  if (runStatus === "running" || runStatus === "paused") {
    return "Replanning unlocks when this run finishes.";
  }
  if (runStatus === "succeeded" || runStatus === "degraded") {
    return "Describe a change to the plan to run again.";
  }
  if (runStatus === "failed" || runStatus === "aborted" || runStatus === "interrupted") {
    return "Describe what to change, then start again.";
  }
  if (planReady) {
    return "Suggest changes here, or edit directly in the plan.";
  }
  return "Describe the policy question you need evidence for.";
}

/**
 * The message composer: a bounded auto-growing textarea (Enter sends,
 * Shift+Enter inserts a newline) plus its keybinding hint. Split out from
 * `TaskAgentPane` so the Enter/Shift+Enter/disabled behaviour is unit-testable
 * without the transcript/run/decision store wiring.
 */
export function Composer({
  value,
  onChange,
  onSubmit,
  placeholder,
  disabled,
  sendDisabled,
  id = "task_agent-message",
  label = COPY.messageTaskAgent,
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  placeholder: string;
  /** Textarea's own disabled state (027: honest-copy placeholder swap). */
  disabled: boolean;
  /** Send button's disabled state (027: also covers in-flight submission). */
  sendDisabled: boolean;
  /** DOM id and label, defaulting to the Task Agent's own composer. A chat
   *  passes its own (038 V8): with the Agent overlay beside the Task Agent's
   *  pane, one shared id would be two elements, and `getElementById` — the
   *  seed hand-off and the overlay's focus hand-off both use it — would take
   *  whichever came first in the document. */
  id?: string;
  label?: string;
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
        <label className="sr-only" htmlFor={id}>
          {label}
        </label>
        <textarea
          id={id}
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
          className="max-h-60 min-h-14 flex-1 resize-y overflow-y-auto border border-line-2 bg-paper px-3 py-2.5 text-lead [field-sizing:content] focus-visible:outline-2 focus-visible:outline-blue disabled:bg-ground disabled:text-grey"
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
      <p className="mt-1 text-meta text-grey">Enter to send · Shift+Enter for a new line</p>
    </div>
  );
}

function UserBubble({ text }: { text: string }) {
  return (
    <div className="anim-rise ml-8 border border-blue-tint bg-blue-tint-2 px-3.5 py-2.5">
      <p className="max-w-prose-measure whitespace-pre-wrap text-lead text-ink">{scrub(text)}</p>
    </div>
  );
}

/** TaskAgent replies are plain text — no box (binding record: task_agent-stage
 *  `.task_agent`); only part cards and the plan card are bordered. */
function TaskAgentBubble({ text }: { text: string }) {
  return (
    <div className="anim-rise mr-8">
      <p className="max-w-prose-measure whitespace-pre-wrap text-lead text-ink">{scrub(text)}</p>
    </div>
  );
}

/** One recorded gate decision, as a quiet line rather than a card: the
 *  option's own label, that it is on the record, and the plan version it was
 *  taken against. Shared by a `decision` turn and by a decision the card
 *  endpoint recorded, so the two can never word the same fact differently. */
export function DecisionLine({
  label,
  planVersion,
}: {
  label: string;
  planVersion: number | null;
}) {
  return (
    <div className="mr-8 border-l-2 border-l-green bg-paper-2 px-3 py-2">
      <p className="text-body text-ink">
        <span className="font-semibold">{scrub(label)}</span> · {DECISION_RECORDED}
        {planVersion !== null && ` · ${DECISION_PLAN_VERSION} ${planVersion}`}
      </p>
    </div>
  );
}

/** A durable turn: user bubble, then the task_agent reply — or an honest
 *  incomplete row (pending spinner copy / failed with retry).
 *
 *  Task 044 Phase 5.5: a turn is one of three things (`kind`). A `reply`
 *  renders as it always has. An `answer` renders its grounded prose through
 *  the CHAT's own citation renderer (`ChatAnswer`) — one renderer, two
 *  surfaces. A `decision` renders the gate decision it recorded. `kind` is
 *  absent on every pre-044 turn, which reads as `reply`. */
function DurableTurn({
  taskId,
  turn,
  isLatest,
  onRetry,
  retryDisabled,
  partState,
  onSend,
  onPrefill,
}: {
  taskId: string;
  turn: TaskAgentThreadTurn;
  isLatest: boolean;
  onRetry: (input: { message: string; clientTurnId: string }) => void;
  retryDisabled: boolean;
  partState: PartState | undefined;
  onSend: (message: string) => void;
  onPrefill: (message: string) => void;
}) {
  // A button-confirm turn's record is the ✓ on its part card — the canned
  // marker bubble would only duplicate it (binding record: task_agent-stage).
  const isConfirmTurn = confirmTarget(turn.user_message) !== null;
  const kind = taskAgentTurnKind(turn);
  const taskAgentText = [turn.reply, turn.part?.body]
    .filter((piece): piece is string => piece != null && piece !== "")
    .join("\n\n");
  if (kind === "answer") {
    return (
      <div className="space-y-6">
        <UserBubble text={turn.user_message} />
        <ChatAnswer
          taskId={taskId}
          turn={taskAgentAnswerRow(turn)}
          // The reader is already in the Task Agent: the chat's "open the
          // Task Agent" hand-off has nowhere to go from here.
          onOpenTaskAgent={() => {}}
          onRetry={() => onRetry({ message: turn.user_message, clientTurnId: turn.client_turn_id })}
        />
      </div>
    );
  }
  if (kind === "decision" && turn.decision != null) {
    return (
      <div className="space-y-6">
        {!isConfirmTurn && <UserBubble text={turn.user_message} />}
        <DecisionLine label={turn.decision.label} planVersion={turn.decision.plan_version} />
      </div>
    );
  }
  return (
    <div className="space-y-6">
      {!isConfirmTurn && <UserBubble text={turn.user_message} />}
      {turn.status === "completed" && taskAgentText !== "" && <TaskAgentBubble text={taskAgentText} />}
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
  decisions: TaskAgentThreadDecision[],
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
    const consecutive: TaskAgentThreadDecision[] = [];
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

function AnsweredCheckIns({
  answered,
  checkIns,
}: {
  answered: ResolvedDecision[];
  checkIns: ReturnType<typeof useCheckIns>["data"];
}) {
  return answered.map((decision) => (
    <AnsweredCheckIn
      key={decision.checkInId}
      decision={decision}
      checkIn={checkIns?.data.find((checkIn) => checkIn.check_in_id === decision.checkInId)}
    />
  ));
}

function RunFinishedNotice({
  taskId,
  status,
}: {
  taskId: string;
  status: RunStatus | undefined;
}) {
  const notice = runFinishedSignpost(taskId, status);
  if (notice === null) return null;
  return (
    <div className="anim-rise mr-8 border-2 border-[#17A88D] bg-[#DDF2EE] px-4 py-3">
      <p className="max-w-prose-measure text-lead text-navy">
        Evidence search is finished. You can read the report in the{" "}
        <Link to={notice.href} className="font-semibold text-blue underline">
          {notice.label}
        </Link>{" "}
        tab.
      </p>
    </div>
  );
}

function RunBlock({
  taskId,
  run,
  decisions,
  stages,
  answered,
  checkIns,
}: {
  taskId: string;
  run: TaskAgentThreadRun;
  decisions: TaskAgentThreadDecision[];
  stages: StageEntry[];
  answered: ResolvedDecision[];
  checkIns: ReturnType<typeof useCheckIns>["data"];
}) {
  const status = RUN_BLOCK_STATUS[run.status] ?? null;
  const presentedDecisions = presentRunDecisions(decisions, stages);
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
      <AnsweredCheckIns answered={answered} checkIns={checkIns} />
      {/* The chat's own destination once the run lands (owner, 2026-08-05):
          a completed run's last word shouldn't be a quiet stage echo. */}
      <RunFinishedNotice taskId={taskId} status={run.status} />
    </div>
  );
}

/**
 * The task_agent conversation, rendered from the durable transcript (strand 12):
 * it survives navigation and restarts. Message bubbles, the thinking row,
 * tappable suggestion chips, run blocks with their steering-decision echoes,
 * and the composer — which disables honestly while a run executes or parks
 * (task_agent turns 409 then; check-ins are the sanctioned steering channel).
 */
export function TaskAgentPane({
  taskId,
  runStatus,
  stream,
  isOwner,
  onReviewPlan,
  planOverlay,
  onOverlayApplied,
  onDiscardOverlay,
  onAtBottomChange,
}: {
  taskId: string;
  runStatus: RunStatus | undefined;
  stream: RunStreamState;
  /** Steering is owner-only (task 033 phase 10c, contract § 11 / rubric 37):
   *  gates the composer, retry controls, suggestion chips, the plan-ready
   *  card's Start action and the check-in card. Required, not defaulted —
   *  a forgotten prop must fail closed to read-only, never silently grant
   *  every colleague the owner's mutation surface. */
  isOwner: boolean;
  onReviewPlan?: () => void;
  planOverlay?: PlanOverlay;
  onOverlayApplied?: () => void;
  /** Clears the same overlay state as `onOverlayApplied` — wired to the
   *  plan-ready card's Discard edits and start action. */
  onDiscardOverlay?: () => void;
  /** Reports when the reader asks for the site footer (a deliberate scroll
   *  past the transcript's end) and when they scroll back up (038 V8); the
   *  Agent tab reveals the footer under both columns accordingly. */
  onAtBottomChange?: (atBottom: boolean) => void;
}) {
  const transcript = useTaskAgentTranscript(taskId, { page_size: TRANSCRIPT_PAGE_SIZE });
  const planQuery = usePlan(taskId);
  // `PlanOut.plan` is null on a scoping task (task 044) — `scoping` carries
  // its own `ready` flag instead. Only one of the two is ever non-null for a
  // given task, so reading both costs nothing on the branch that doesn't apply.
  const planReady =
    planQuery.data?.status === "approved" &&
    (planQuery.data.plan?.ready === true || planQuery.data.scoping?.ready === true);
  const runsQuery = useRuns(taskId, { page_size: TRANSCRIPT_PAGE_SIZE });
  const decisionsQuery = useDecisions(taskId, { page_size: TRANSCRIPT_PAGE_SIZE });
  const checkInsQuery = useCheckIns(taskId, "all");
  const funnel = useFunnel(taskId);
  const [message, setMessage] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [runMinimised, setRunMinimised] = useState(false);
  const [cardOffscreen, setCardOffscreen] = useState(false);
  const [nowMs, setNowMs] = useState(() => Date.now());
  useComposerSeed(setMessage);

  const durableTurns = (transcript.data?.data ?? []) as TaskAgentThreadTurn[];
  const { boundaries, runDecisions } = threadInputs(
    durableTurns,
    runsQuery.data?.data ?? [],
    decisionsQuery.data?.data ?? [],
  );
  // Task 044 Phase 5.5: the options-scoping baseline gate is the one check-in
  // that sits INSIDE the thread, in chronological order with the turns it
  // paused for. Every Evidence search check-in keeps its placement at the
  // thread's end, below, exactly as before.
  const gate = baselineGateInput(stream, checkInsQuery.data?.data ?? [], planQuery.data?.version ?? null);
  const thread: TaskAgentThreadItem[] = composeTaskAgentThread(
    durableTurns,
    boundaries,
    runDecisions,
    gate,
  );
  // The gate's own decision renders once, as a thread item; the run block's
  // answered-check-in echoes must not repeat it.
  const streamDecisions = stream.decisions.filter(
    (decision) => decision.checkInId !== gate?.checkIn.check_in_id,
  );
  const latestTurnIndex =
    durableTurns.length > 0 ? Math.max(...durableTurns.map((turn) => turn.turn_index)) : null;
  const partStates = derivePartStates(durableTurns);

  const runActive = runStatus === "running" || runStatus === "paused";
  // Task 044 Phase 5.5: a scoping walk parked on the baseline gate keeps the
  // thread open — the turn route accepts a question or a decision at exactly
  // this pause. The fence stays for every Evidence search check-in and for a
  // scoping walk that is still running.
  const atScopingGate =
    planQuery.data?.capability === "options_scoping" &&
    runStatus === "paused" &&
    stream.pendingCheckIn?.kind === BASELINE_GATE_KIND;
  const composerFenced = runActive && !atScopingGate;
  // `!isOwner` folds into the same `composerDisabled` flag that already
  // disables the composer, DurableTurn's retry button and PartCard's options
  // during an active run (task 033 phase 10c, contract § 11 / rubric 37) —
  // one mechanism, not a second parallel disabled path.
  const composerDisabled = composerFenced || transcript.isSubmitting || !isOwner;

  // Chat scroll: pinned to the bottom (newest messages) unless the user has
  // scrolled up to read history; new content re-pins only when near-bottom.
  // A ResizeObserver on the thread content catches growth the pane itself
  // never renders for (child-owned queries like the plan card, disclosure
  // toggles, font loads).
  const scrollRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  // The site footer lives in `WorkspaceView`, under both columns (038 V8),
  // and opens only on a deliberate nudge past the transcript's end.
  const footer = useFooterReveal(onAtBottomChange);
  // The transcript opens at its end and stays there while new turns land
  // (shared with the chat pane).
  const pin = usePinToBottom(scrollRef, contentRef, taskId);

  // The plan card sits at its chronological position: right after the last
  // task_agent turn (approval always comes from a turn; turns are 409-fenced
  // during runs), so a started run's block renders BELOW it, not above.
  const lastTurnAt = thread.findLastIndex((item) => item.type === "task_agent_turn");
  const planCardAt = lastTurnAt === -1 ? thread.length : lastTurnAt + 1;
  const planStarted = thread.slice(planCardAt).some((item) => item.type === "run_block");
  const liveRunId = stream.run?.id;
  const threadHasLiveRun = thread.some(
    (item) => item.type === "run_block" && item.run.capability_run_id === liveRunId,
  );
  const hasFindings = typeof funnel.data?.findings === "number" && funnel.data.findings > 0;
  const runTicking = runStatus === "running" || runStatus === "paused";
  const liveElapsed = formatElapsed(
    elapsedSeconds(stream.run?.startedAt, stream.run?.endedAt, nowMs),
  );

  useEffect(() => {
    if (!runTicking || !cardOffscreen) return undefined;
    const id = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [runTicking, cardOffscreen]);

  useEffect(() => {
    const card = cardRef.current;
    const root = scrollRef.current;
    if (card === null || root === null || typeof IntersectionObserver === "undefined") {
      setCardOffscreen(false);
      return undefined;
    }
    const observer = new IntersectionObserver(
      ([entry]) => setCardOffscreen(entry !== undefined && !entry.isIntersecting),
      { root, threshold: 0 },
    );
    observer.observe(card);
    return () => observer.disconnect();
  }, [liveRunId, threadHasLiveRun]);

  const liveCard =
    stream.run === null ? null : (
      <div key="live-run" ref={cardRef}>
        <RunningCard
          taskId={taskId}
          status={stream.run.status}
          stages={stream.stages}
          plan={stream.plan?.plan}
          startedAt={stream.run.startedAt}
          endedAt={stream.run.endedAt}
          hasFindings={hasFindings}
          minimised={runMinimised}
          onMinimisedChange={setRunMinimised}
          onSeePlan={onReviewPlan}
        />
      </div>
    );
  const signpostBubbles = completedSignposts(stream.stages, taskId, hasFindings).map(
    (signpost) => (
      <div key={signpost.href} className="anim-rise mr-8">
        <p className="max-w-prose-measure text-lead text-ink">
          {signpost.message}{" "}
          <Link to={signpost.href} className="font-semibold text-blue hover:underline">
            {signpost.label} →
          </Link>
        </p>
      </div>
    ),
  );

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
    <section aria-label="Task Agent conversation" className="flex h-full min-h-0 flex-col">
      {/* The scroll region spans the whole pane so its scrollbar sits at the
          pane's edge like every other tab's; the reading column is inside. */}
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      {/* `relative` for the jump-to-end pill, which floats over the region's bottom edge. */}
      <div className="relative flex min-h-0 flex-1 flex-col">
      <div
        ref={scrollRef}
        onScroll={(event) => {
          pin.onScroll(event);
          footer.onScroll(event);
        }}
        onWheel={footer.onWheel}
        onTouchStart={footer.onTouchStart}
        onTouchMove={footer.onTouchMove}
        className="flex min-h-0 flex-1 flex-col overflow-y-auto py-4 [scrollbar-gutter:stable]"
      >
        {/* Bottom-anchor: pushes a short thread to the composer end; the
            landing prompt sits in the top third (1:2 spacer split). */}
        <div aria-hidden="true" className={landing ? "flex-[1]" : "mt-auto"} />
        <div ref={contentRef} className={cn("space-y-6", LIFECYCLE_PAGE_CLASS)}>
        {transcript.isPending && (
          <div role="status" className="anim-breathe text-body text-grey">
            Loading your task_agent conversation…
          </div>
        )}
        {transcript.isError &&
          (errorCode(transcript.error) === "unauthenticated" ? (
            <ReauthRedirect />
          ) : (
            <div role="status" className="text-body text-grey">
              <p>Your Task Agent conversation couldn't be loaded.</p>
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
            item.type === "gate_check_in" ? (
              <CheckInCard
                key={`gate-${item.checkIn.check_in_id}`}
                taskId={taskId}
                checkIn={item.checkIn}
                stages={stream.stages}
                isOwner={isOwner}
              />
            ) : item.type === "gate_decision" ? (
              <DecisionLine
                key={`gate-decision-${item.decision.checkInId}`}
                label={item.decision.label}
                planVersion={item.decision.planVersion}
              />
            ) : item.type === "task_agent_turn" ? (
              <DurableTurn
                key={`turn-${item.turn.turn_index}`}
                taskId={taskId}
                turn={item.turn}
                isLatest={item.turn.turn_index === latestTurnIndex}
                onRetry={send}
                retryDisabled={composerDisabled}
                partState={partStates.get(item.turn.turn_index)}
                onSend={(text) => send({ message: text, clientTurnId: crypto.randomUUID() })}
                onPrefill={setMessage}
              />
            ) : item.run.capability_run_id === liveRunId && liveCard !== null ? (
              <div key="live-run-block" className="space-y-6">
                {liveCard}
                <AnsweredCheckIns answered={streamDecisions} checkIns={checkInsQuery.data} />
                {signpostBubbles}
                <RunFinishedNotice taskId={taskId} status={stream.run?.status} />
              </div>
            ) : (
              <RunBlock
                key={`run-${item.run.capability_run_id}`}
                taskId={taskId}
                run={item.run}
                decisions={item.decisions}
                stages={stream.stages}
                answered={
                  item.run.capability_run_id === stream.run?.id ? streamDecisions : []
                }
                checkIns={checkInsQuery.data}
              />
            );
          return index === planCardAt - 1
            ? [rendered, <PlanCard key="plan-card" taskId={taskId} runActive={runActive} started={planStarted} isOwner={isOwner} onReviewPlan={onReviewPlan} overlay={planOverlay} onOverlayApplied={onOverlayApplied} onDiscardOverlay={onDiscardOverlay} />]
            : [rendered];
        })}

        {transcript.optimisticTurns.map((turn: OptimisticTaskAgentTurn) => (
          <div key={turn.clientTurnId} className="space-y-6">
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
                {turn.errorCode === "stale_turn" || turn.errorCode === "already_answered" ? (
                  // Retrying the same client_turn_id can never clear a
                  // stale_turn conflict, and an already-answered check-in
                  // will not un-answer itself — offer the refresh instead.
                  // Both render inline, right where the message was typed;
                  // neither becomes a toast.
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
            TaskAgent…
          </div>
        )}

        {/* Suggestion chips send a task_agent turn (task 033 phase 10c,
            contract § 11 / rubric 37) — owner-only, hidden for a colleague
            rather than left clickable to a 403. */}
        {isOwner && suggestions.length > 0 && !transcript.isSubmitting && !composerFenced && (
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

        {stream.pendingCheckIn !== null && stream.pendingCheckIn.kind !== BASELINE_GATE_KIND && (
          <CheckInCard
            key={stream.pendingCheckIn.check_in_id}
            taskId={taskId}
            checkIn={stream.pendingCheckIn}
            stages={stream.stages}
            isOwner={isOwner}
          />
        )}
        {liveCard !== null && !threadHasLiveRun && (
          <div key="live-run-fallback" className="space-y-6">
            {liveCard}
            <AnsweredCheckIns answered={streamDecisions} checkIns={checkInsQuery.data} />
            {signpostBubbles}
            <RunFinishedNotice taskId={taskId} status={stream.run?.status} />
          </div>
        )}
        </div>
        {landing && <div aria-hidden="true" className="flex-[2]" />}
      </div>
      <JumpToEnd visible={!pin.atEnd} onClick={pin.jumpToEnd} />
      </div>

      <div className="shrink-0 border-t border-line">
        {stream.run !== null && cardOffscreen && (
          <RunningCardDock
            status={stream.run.status}
            stages={stream.stages}
            plan={stream.plan?.plan}
            elapsedLabel={liveElapsed}
            onOpen={() => {
              setRunMinimised(false);
              cardRef.current?.scrollIntoView({ block: "nearest" });
            }}
          />
        )}
        <div className={cn("py-3", LIFECYCLE_PAGE_CLASS)}>
        <Composer
          value={message}
          onChange={setMessage}
          onSubmit={() => send({ message, clientTurnId: crypto.randomUUID() })}
          placeholder={taskAgentComposerPlaceholder(runStatus, planReady, isOwner, atScopingGate)}
          disabled={composerFenced || !isOwner}
          sendDisabled={composerDisabled}
        />
        </div>
      </div>
      </div>
    </section>
  );
}
