import { createContext, Fragment, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router";

import { UPLOAD_MESSAGE, uploadMessage, useTocUpload, useTocUploading } from "../../api/mutations";
import { useCheckIns, useDecisions, useFunnel, usePlan, useRuns, useTask, useToc, useTocUploadFile, useTocUploads } from "../../api/queries";
import { useComposerSeed } from "../../lib/composerSeed";
import { scrub } from "../../lib/scrub";
import { COPY, TASK } from "../../lib/vocabulary";
import {
  composeTaskAgentThread,
  taskAgentAnswerRow,
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
import { ReauthRedirect, ReconnectingBanner } from "../../ui/feedback";
import { Arrival, ArrivalProvider, useFirstPaintDone } from "../../ui/motion/arrivals";
import { prefersReducedMotion } from "../../ui/motion/motion";
import { useEasedHeight } from "../streamPacing";
import { LIFECYCLE_PAGE_CLASS } from "../listPageChrome";
import { hasLonglist, isScoping } from "../scopingActivity";
import { ChatAnswer } from "./chat/ChatMessages";
import { JumpToEnd } from "./chat/JumpToEnd";
import { useFooterReveal } from "./chat/useFooterReveal";
import { usePinToBottom } from "./chat/usePinToBottom";
import { AnsweredCheckIn } from "./AnsweredCheckIn";
import { CheckInCard, SettledGateCard } from "./CheckInCard";
import { BASELINE_GATE_KIND } from "./checkInPresentation";
import type { components } from "../../api/gen/types";
import { PartCard, type PartState, type PlanStep, confirmTarget, derivePartStates, planSteps, settledSummary } from "./PartCard";
import { ActionLine } from "./ActionLine";
import { GrowBox } from "./GrowBox";
import { PlanCard } from "./PlanCard";
import type { PlanOverlay } from "./planOverlay";
import { PastRunLine, RunTrace } from "./RunTrace";
import { isFinished, threadRunStages } from "./runProgress";
import { usePacedText, PacedReply } from "./PacedReply";
import { joinTocWalks, pendingLead, waitsForCheck } from "./tocWalks";
import { useNow } from "../../lib/freshness";
import { TocCodeText } from "../toc/codeLinks";
import { CitationMarker } from "../toc/Documents";
import { AttachFileButton, UploadPreview } from "../toc/uploads";

/** The server page-size cap; one task_agent conversation fits comfortably. */
const TRANSCRIPT_PAGE_SIZE = 200;

/** The kinds a walk itself writes, so an untagged one inside its window is
 *  its own. Any other event with no walk (round 15: `shortlist.note_updated`,
 *  a shortlist or longlist action, a task's lifecycle) is housekeeping that
 *  stays in History, never placed in a walk's block by its time. */
const WALK_KIND_PREFIXES = ["component.", "search.", "run.", "steering.", "checkin."] as const;

function placedByTime(kind: string): boolean {
  return WALK_KIND_PREFIXES.some((prefix) => kind.startsWith(prefix));
}

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
  /** Theory of change (round 5): a child walk's lines go to its parent's block, for the trace. */
  foldChildren = false,
): { boundaries: RunThreadBoundary[]; runDecisions: RunThreadDecision[] } {
  // Task 045 (S12): a child walk (a longlist walk's option search) gets no
  // block of its own; the decisions that name it go nowhere.
  const childIds = new Set(
    runs.filter((run) => run.parent_capability_run_id != null).map((run) => run.capability_run_id),
  );
  const boundaries = runs.filter((run) => !childIds.has(run.capability_run_id)).map((run) => {
    const before = turns.filter((turn) => turn.created_at <= run.started_at);
    return {
      run,
      afterTurnIndex: before.length > 0 ? Math.max(...before.map((turn) => turn.turn_index)) : null,
    };
  });
  // Task 045 (F11): a decision whose event carries a run names its walk
  // (`capability_run_id`, from the event's run) and goes to that walk — or
  // nowhere, when the walk is a child or not one of these runs. A lifecycle
  // event's `detail.capability_run_id` names its run the same way. Only a
  // decision with neither is placed by time, and only among the parentless
  // walks — a child window sits inside its parent's, so it must not swallow
  // the parent's own lines.
  const runIds = new Set(runs.map((run) => run.capability_run_id));
  const orderedRuns = runs
    .filter((run) => !childIds.has(run.capability_run_id))
    .sort((left, right) => left.started_at.localeCompare(right.started_at));
  const parentOf = new Map(
    runs.flatMap((run) => (run.parent_capability_run_id != null ? [[run.capability_run_id, run.parent_capability_run_id] as const] : [])),
  );
  const runDecisions: RunThreadDecision[] = [];
  for (const decision of decisions) {
    const own = decision.capability_run_id;
    const walkId = foldChildren && own != null ? (parentOf.get(own) ?? own) : own;
    const tagged = decision.detail?.["capability_run_id"];
    const ownerId =
      walkId != null
        ? runIds.has(walkId)
          ? walkId
          : undefined
        : typeof tagged === "string" && runIds.has(tagged)
          ? tagged
          : placedByTime(decision.kind)
            ? orderedRuns.findLast(
              (run) =>
                run.started_at <= decision.occurred_at &&
                (run.ended_at === null || run.ended_at === undefined || decision.occurred_at <= run.ended_at),
            )?.capability_run_id
            : undefined;
    if (ownerId !== undefined && !childIds.has(ownerId)) {
      runDecisions.push({ decision, capabilityRunId: ownerId });
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
  const label = (checkIn.options ?? []).find((option) => option.id === optionId)?.label ?? null;
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
  hasLonglist = false,
  isToc = false,
): string {
  if (!isOwner) {
    return `Steering is limited to the ${TASK.lower} owner.`;
  }
  // Task 044 Phase 5.5: the scoping walk's one gate keeps the thread open —
  // a question about the baseline is exactly what this pause is for, so the
  // composer invites one instead of fencing it off.
  if (atScopingGate) {
    return "Question the baseline…";
  }
  if (runStatus === "running" || runStatus === "paused") {
    return "Replanning unlocks when this run finishes.";
  }
  // Task 045: with a longlist and nothing running, the thread takes the
  // longlist verbs as well as questions.
  if (hasLonglist) {
    return "Ask about the longlist, or add, exclude or include an option.";
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
  // A theory of change asks about the change, not a question for evidence (task 054).
  return isToc ? "Describe the change you want, or ask about your theory." : "Describe the policy question you need evidence for.";
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
  onAttach,
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
  /** A theory of change before its draft (task 054, increment 5): attach the user's own diagram. */
  onAttach?: (file: File) => void;
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
          className="max-h-60 min-h-14 flex-1 resize-y overflow-y-auto border border-line-2 bg-paper px-3 py-2.5 text-lead [field-sizing:content] disabled:bg-ground disabled:text-grey"
        />
        {onAttach !== undefined && (
          <AttachFileButton
            onFile={onAttach}
            disabled={disabled}
            title="Upload your own theory of change (PNG, JPEG or PDF)"
            className={cn(
              "inline-flex h-10 w-10 shrink-0 items-center justify-center border border-line-2 text-navy",
              disabled ? "cursor-default text-line-2" : "cursor-pointer hover:border-navy focus-within:outline-2 focus-within:outline-blue",
            )}
            iconClassName="h-5 w-5"
          >
            <span className="sr-only">Upload your own theory of change</span>
          </AttachFileButton>
        )}
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

/** A theory of change the user brought from the new-task page, uploaded once the task opens. */
export interface TocUploadHandOff {
  tocFile: File;
  note: string;
}

/** The task's uploaded diagrams, for the bubbles that sent them: the one still uploading, and those read. */
const UploadFiles = createContext<{ taskId: string; picked: File | null; uploads: { upload_id: string; file_name: string }[] } | null>(null);

/** The diagram an upload bubble names: "I've uploaded my own theory of change (name)." */
function UploadThumb({ text }: { text: string }) {
  const files = useContext(UploadFiles);
  const name = text.slice(UPLOAD_MESSAGE.length).match(/^ \((.+?)\)\./)?.[1] ?? null;
  const picked = files?.picked != null && files.picked.name === name ? files.picked : null;
  const uploadId = picked === null ? files?.uploads.findLast((upload) => upload.file_name === name)?.upload_id : undefined;
  const stored = useTocUploadFile(files?.taskId ?? "", uploadId);
  const blob = picked ?? stored.data ?? null;
  if (blob === null || name === null) return null;
  return (
    <UploadPreview
      blob={blob}
      className="mb-2 block w-fit"
      imageClassName="max-h-40 max-w-[16rem] border border-line bg-paper object-contain"
      pdf={(url) => (
        <a href={url} target="_blank" rel="noreferrer" className="mb-2 inline-flex items-center gap-2 border border-line bg-paper px-2.5 py-1.5 text-meta font-semibold text-navy hover:border-navy">
          <span aria-hidden="true">📄</span>
          {name}
        </a>
      )}
    />
  );
}

/** The user's message. It rises only when it arrives after the thread's
 *  first paint; the stored row that replaces a streamed one shares its id
 *  (the client turn id), so it appears in place and nothing animates twice. */
function UserBubble({ text, turnId }: { text: string; turnId: string }) {
  // A code-authored Task Agent line (task 054, J3) has no user message.
  if (text === "") return null;
  return (
    <Arrival arrivalId={`user:${turnId}`} className="ml-8 border border-blue-tint bg-blue-tint-2 px-3.5 py-2.5">
      {text.startsWith(UPLOAD_MESSAGE) && <UploadThumb text={text} />}
      <p className="max-w-prose-measure whitespace-pre-wrap text-lead text-ink">{scrub(text)}</p>
    </Arrival>
  );
}

type CitedSource = components["schemas"]["CitedSourceOut"];

/** "[1]" or "[1,2]" in a reply that cites its sources (task 054: the sense check). */
const SOURCE_MARKER = /\[(\d+(?:,\d+)*)\]/g;

/** TaskAgent replies are plain text — no box (binding record: task_agent-stage
 *  `.task_agent`); only part cards and the plan card are bordered. The reply
 *  rises in as it arrives and its words come at a steady pace (round 9).
 *
 *  It grows smoothly (owner, round 12: "Drafting the plan" was jittery): its
 *  own box eases to each new line's height, so what is under it (the action
 *  line while it streams, the part card once it is stored) glides down
 *  rather than jumping a line and being clipped by the thread's ease. A
 *  streamed turn mounts the box before its first words (`text` empty) and
 *  keeps the gap to the action line inside it (`gapBelow`), so the first
 *  line opens the same way. A cut under reduced motion.
 *
 *  A theory of change's stored reply links its box and connection codes, and
 *  a reply that cites its sources lists them under it (task 054). */
function TaskAgentBubble({
  text,
  turnId,
  streamed,
  gapBelow = false,
  taskId,
  tocCodes,
  sources = [],
}: {
  text: string;
  turnId: string;
  streamed: boolean;
  gapBelow?: boolean;
  taskId?: string;
  tocCodes?: ReadonlySet<string>;
  sources?: CitedSource[];
}) {
  const [box, content] = useEasedHeight(!prefersReducedMotion());
  const cited = sources.length > 0 && taskId !== undefined;
  const linked = tocCodes !== undefined && taskId !== undefined;
  return (
    <Arrival arrivalId={`reply:${turnId}`} className="mr-8">
      <div ref={box}>
        <div ref={content}>
          {text !== "" && (
            <p className={cn("max-w-prose-measure whitespace-pre-wrap text-lead text-ink", gapBelow && "pb-6")}>
              {cited || linked ? (
                <LinkedReply turnId={turnId} text={text} streamed={streamed} taskId={taskId} tocCodes={tocCodes} sources={sources} />
              ) : (
                <PacedReply turnId={turnId} text={text} streamed={streamed} />
              )}
            </p>
          )}
          {cited && (
            <ol className="mt-3 max-w-prose-measure space-y-1 text-body text-ink-2">
              {sources.map((source) => (
                <li key={source.n}>
                  <span className="mr-1 text-grey">[{source.n}]</span>
                  {source.url ? (
                    <a href={source.url} target="_blank" rel="noreferrer" className="text-blue hover:underline">
                      {scrub(source.title)}
                    </a>
                  ) : (
                    scrub(source.title)
                  )}
                  {source.year && <span className="text-grey"> ({source.year})</span>}
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </Arrival>
  );
}

/** A reply with its theory-of-change codes linked and its "[n]" markers as
 *  citation buttons, revealed at the same pace as a plain reply. */
function LinkedReply({
  turnId,
  text,
  streamed,
  taskId,
  tocCodes,
  sources,
}: {
  turnId: string;
  text: string;
  streamed: boolean;
  taskId: string;
  tocCodes?: ReadonlySet<string>;
  sources: CitedSource[];
}) {
  const revealed = usePacedText(turnId, text, streamed).text;
  const plain = (piece: string) =>
    tocCodes !== undefined ? <TocCodeText text={piece} taskId={taskId} codes={tocCodes} /> : scrub(piece);
  return sources.length > 0 ? <CitedText text={revealed} taskId={taskId} sources={sources} plain={plain} /> : <>{plain(revealed)}</>;
}

/** The reply with each "[n]" marker as a button that opens the citation sidebar. */
function CitedText({
  text,
  taskId,
  sources,
  plain,
}: {
  text: string;
  taskId: string;
  sources: CitedSource[];
  plain: (piece: string) => ReactNode;
}) {
  const byNumber = new Map(sources.map((source) => [source.n, source]));
  const pieces: ReactNode[] = [];
  let last = 0;
  for (const match of text.matchAll(SOURCE_MARKER)) {
    const index = match.index ?? 0;
    const sentenceStart = Math.max(text.lastIndexOf(". ", index) + 2, text.lastIndexOf("\n", index) + 1, 0);
    const citations = match[1]
      .split(",")
      .map((n) => byNumber.get(Number(n)))
      .filter((source): source is CitedSource => source !== undefined)
      .map((source) => ({ n: source.n, evidenceId: null, title: source.title, url: source.url ?? null, quote: source.quote, fallbackQuote: source.quote }));
    pieces.push(<Fragment key={`t${last}`}>{plain(text.slice(last, index))}</Fragment>);
    pieces.push(<CitationMarker key={`c${index}`} taskId={taskId} claim={text.slice(sentenceStart, index).trim() || null} citations={citations} />);
    last = index + match[0].length;
  }
  pieces.push(<Fragment key={`t${last}`}>{plain(text.slice(last))}</Fragment>);
  return <>{pieces}</>;
}

/** The action line under a streaming planner reply: the shared one. */
function PlannerActionLine({ label, live, turnId }: { label: string; live: boolean; turnId: string }) {
  return <ActionLine label={label} live={live} arrivalId={`action:${turnId}`} />;
}

/** Whether a turn on its way shows the planner's action line. */
function actionShown(turn: OptimisticTaskAgentTurn): boolean {
  return turn.status !== "failed" && turn.progressLabel !== undefined;
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
        <span className="font-semibold">{scrub(label)}</span> · recorded
        {planVersion !== null && ` · plan version ${planVersion}`}
      </p>
    </div>
  );
}

/** The recorded line for an applied longlist verb: the verb, then the
 *  option's name (task 045). An unknown verb shows the name alone. */
export function actionLine(action: { verb: string; label: string }): string {
  switch (action.verb) {
    case "add":
      return `Added ${action.label}`;
    case "exclude":
      return `Excluded ${action.label}`;
    case "include_again":
      return `Included ${action.label} again`;
    default:
      return action.label;
  }
}

/** A durable turn: user bubble, then the task_agent reply — or an honest
 *  incomplete row (pending spinner copy / failed with retry).
 *
 *  Task 044 Phase 5.5: a turn is one of three things (`kind`). A `reply`
 *  renders as it always has. An `answer` renders its grounded prose through
 *  the CHAT's own citation renderer (`ChatAnswer`) — one renderer, two
 *  surfaces. A `decision` renders the gate decision it recorded, and an
 *  `action` (task 045) the longlist verb it applied. `kind` is absent on
 *  every pre-044 turn, which reads as `reply`. */
function DurableTurn({
  taskId,
  turn,
  isLatest,
  onRetry,
  retryDisabled,
  partState,
  steps,
  plan,
  scopingPlan,
  onSend,
  tocCodes,
}: {
  taskId: string;
  turn: TaskAgentThreadTurn;
  /** A theory of change's box and connection codes, linked in the reply. */
  tocCodes?: ReadonlySet<string>;
  isLatest: boolean;
  onRetry: (input: { message: string; clientTurnId: string }) => void;
  retryDisabled: boolean;
  partState: PartState | undefined;
  /** The plan's steps, for the stepper above the active part card. */
  steps: PlanStep[];
  /** The task's current plans, so a settled part names its outcome. */
  plan?: components["schemas"]["PlanDraft"] | null;
  scopingPlan?: components["schemas"]["ScopingPlanDraft"] | null;
  onSend: (message: string) => void;
}) {
  // A button-confirm turn's record is its settled part card — the canned
  // marker bubble would only duplicate it (binding record: task_agent-stage).
  const isConfirmTurn = confirmTarget(turn.user_message) !== null;
  // A turn stored before task 044 carries no kind: it is a reply.
  const kind = turn.kind ?? "reply";
  // A part's body renders inside its card, under its title (annex scene 11).
  const taskAgentText = turn.reply ?? "";
  if (kind === "answer") {
    return (
      <div className="space-y-6">
        <UserBubble text={turn.user_message} turnId={turn.client_turn_id} />
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
  // A gate decision is said once, in the settled part card's language
  // (round 10, finding 8): no user bubble beside it, no "recorded" line.
  if (kind === "decision" && turn.decision != null) {
    return (
      <Arrival arrivalId={`decision:${turn.client_turn_id}`}>
        <SettledGateCard label={turn.decision.label} />
      </Arrival>
    );
  }
  // Task 045: a confirmed longlist verb (add · exclude · include again) is
  // the user's recorded action — the same quiet line as a gate decision,
  // under the reply that confirmed it.
  if (kind === "action" && turn.action != null) {
    return (
      <div className="space-y-6">
        <UserBubble text={turn.user_message} turnId={turn.client_turn_id} />
        {turn.status === "completed" && taskAgentText !== "" && (
          <TaskAgentBubble text={taskAgentText} turnId={turn.client_turn_id} streamed={false} taskId={taskId} tocCodes={tocCodes} sources={turn.sources} />
        )}
        <Arrival arrivalId={`decision:${turn.client_turn_id}`}>
          <DecisionLine label={actionLine(turn.action)} planVersion={null} />
        </Arrival>
      </div>
    );
  }
  return (
    <div className="space-y-6">
      {!isConfirmTurn && <UserBubble text={turn.user_message} turnId={turn.client_turn_id} />}
      {turn.status === "completed" && taskAgentText !== "" && (
        <TaskAgentBubble text={taskAgentText} turnId={turn.client_turn_id} streamed={false} taskId={taskId} tocCodes={tocCodes} sources={turn.sources} />
      )}
      {turn.part != null && partState !== undefined && (
        <PartCard
          arrivalId={`part:${turn.client_turn_id}`}
          part={turn.part}
          partName={steps.find((step) => step.id === turn.part?.id)?.name}
          state={partState}
          disabled={retryDisabled}
          steps={steps}
          summary={settledSummary(turn.part, partState, plan, scopingPlan)}
          onSend={onSend}
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

/** A turn on its way: the user's words (a confirm turn shows none; its
 *  settled card is the record), the reply as it streams with the action
 *  line under it, or the failure with its Retry. */
function InFlightTurn({
  turn,
  composerDisabled,
  onDiscard,
  onRetry,
}: {
  turn: OptimisticTaskAgentTurn;
  composerDisabled: boolean;
  onDiscard: () => void;
  onRetry: () => void;
}) {
  return (
    <div className="space-y-6">
      {/* Button-confirm turns never show a bubble — durable turns hide
          them too; the settled part card is the record. */}
      {confirmTarget(turn.userMessage) === null && <UserBubble text={turn.userMessage} turnId={turn.clientTurnId} />}
      {/* The reply and the action line under it are one block, so the
          reply's box can open the gap between them as its first line
          lands (round 12). */}
      {((turn.reply !== undefined && turn.reply !== "") || actionShown(turn)) && (
        <div>
          <TaskAgentBubble
            text={turn.reply ?? ""}
            turnId={turn.clientTurnId}
            streamed
            gapBelow={actionShown(turn)}
          />
          {actionShown(turn) && (
            <PlannerActionLine label={turn.progressLabel ?? ""} live={turn.status === "pending"} turnId={turn.clientTurnId} />
          )}
        </div>
      )}
      {turn.status === "failed" && (
        <Arrival arrivalId={`failed:${turn.clientTurnId}`} className="mr-8 border border-line bg-paper px-3.5 py-2.5">
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
              onClick={onDiscard}
            >
              Refresh conversation
            </Button>
          ) : (
            <Button
              size="sm"
              variant="secondary"
              className="mt-2"
              disabled={composerDisabled}
              onClick={onRetry}
            >
              Retry
            </Button>
          )}
        </Arrival>
      )}
    </div>
  );
}

function AnsweredCheckIns({
  answered,
  checkIns,
  stages,
}: {
  answered: ResolvedDecision[];
  checkIns: ReturnType<typeof useCheckIns>["data"];
  stages: StageEntry[];
}) {
  return answered.map((decision) => (
    <AnsweredCheckIn
      key={decision.checkInId}
      decision={decision}
      checkIn={checkIns?.data.find((checkIn) => checkIn.check_in_id === decision.checkInId)}
      stages={stages}
    />
  ));
}

/** A past run in the thread: the ended card (its finish, wall time and
 *  link, its steps folded when the read carries them; round 11) and the
 *  check-ins it answered. The event-log echoes ("Executed a search
 *  query × 55", "Recorded a steering decision") that used to sit here are
 *  audit rows for the History tab, not conversation (owner, 2026-11-05). */
function RunBlock({
  taskId,
  run,
  stages,
  answered,
  checkIns,
  capability,
  hasFindings,
}: {
  taskId: string;
  run: TaskAgentThreadRun;
  stages: StageEntry[];
  capability?: string | null;
  hasFindings: boolean;
  answered: ResolvedDecision[];
  checkIns: ReturnType<typeof useCheckIns>["data"];
}) {
  return (
    <div className="space-y-6">
      {/* Its words follow its own run's kind (task 045, A8), never the live stream's. */}
      <Arrival arrivalId={`run:${run.capability_run_id}`}>
        <PastRunLine run={run} taskId={taskId} capability={capability} hasFindings={hasFindings} />
      </Arrival>
      <AnsweredCheckIns answered={answered} checkIns={checkIns} stages={stages} />
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
  compact = false,
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
  /** The sidebar's pane: the same thread and run trace, with the check-in
   *  card at the sidebar's reduced width. */
  compact?: boolean;
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
  const taskQuery = useTask(taskId);
  // `PlanOut.plan` is null on a scoping task (task 044) — `scoping` carries
  // its own `ready` flag instead. Only one of the two is ever non-null for a
  // given task, so reading both costs nothing on the branch that doesn't apply.
  const planReady =
    planQuery.data?.status === "approved" &&
    (planQuery.data.plan?.ready === true || planQuery.data.scoping?.ready === true);
  // A new task has no plan until its first turn: the task itself says what kind it is.
  const isToc = (planQuery.data?.capability ?? taskQuery.data?.capability) === "theory_of_change";
  // A theory-of-change walk shows its steps as they happen (rounds 5, 6). Whether one runs
  // comes from the theory itself, not the live stream, so the chat sidebar on any tab
  // (which has no stream) shows the same as the Agent tab.
  const tocGraph = useToc(isToc ? taskId : "");
  const upload = useTocUpload(taskId);
  // An upload still running for this task, even one started before a tab switch.
  const uploading = useTocUploading(taskId);
  const picked = uploading?.file ?? null;
  const pickedNote = uploading?.note ?? "";
  const uploads = useTocUploads(taskId, isToc);
  const uploadFiles = useMemo(() => ({ taskId, picked, uploads: uploads.data ?? [] }), [taskId, picked, uploads.data]);
  const tocLive = isToc && (tocGraph.data?.check_status === "drafting" || tocGraph.data?.check_status === "checking");
  const tocReviewing = isToc && tocGraph.data?.reviewing === true;
  const tocCodes = useMemo(
    () =>
      tocGraph.data == null
        ? undefined
        : new Set([...tocGraph.data.boxes, ...tocGraph.data.links].flatMap((item) => (item.code != null ? [item.code] : []))),
    [tocGraph.data],
  );
  const decisionsQuery = useDecisions(taskId, { page_size: TRANSCRIPT_PAGE_SIZE }, tocLive ? 3000 : undefined);
  const runsQuery = useRuns(taskId, { page_size: TRANSCRIPT_PAGE_SIZE }, tocLive ? 3000 : undefined);
  // When a walk ends, fetch its last steps and the Task Agent's message about it at once.
  const wasLive = useRef(false);
  const { refetch: refetchDecisions } = decisionsQuery;
  const { refetch: refetchRuns } = runsQuery;
  const { refetch: refetchTranscript } = transcript;
  useEffect(() => {
    // A review ending posts the Task Agent's message too.
    const busy = tocLive || tocReviewing;
    if (wasLive.current && !busy) {
      void refetchDecisions();
      void refetchRuns();
      void refetchTranscript();
    }
    wasLive.current = busy;
  }, [tocLive, tocReviewing, refetchDecisions, refetchRuns, refetchTranscript]);
  const checkInsQuery = useCheckIns(taskId, "all");
  const funnel = useFunnel(taskId);
  const [message, setMessage] = useState("");
  useComposerSeed(setMessage);

  // A turn still streaming (or re-read after a dropped connection) shows as
  // its local row until it lands, so its durable row is held back meanwhile.
  const inFlightIds = new Set(transcript.optimisticTurns.map((turn) => turn.clientTurnId));
  const durableTurns = ((transcript.data?.data ?? []) as TaskAgentThreadTurn[]).filter(
    (turn) => !inFlightIds.has(turn.client_turn_id),
  );
  const { boundaries, runDecisions } = threadInputs(
    durableTurns,
    runsQuery.data?.data ?? [],
    decisionsQuery.data?.data ?? [],
    isToc,
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
  // A part card settles the moment the user answers it (owner, 2026-11-05):
  // the user's turns still on their way count as its answer until the
  // durable turns catch up. A failed one does not: its choice was not
  // recorded, so the card opens again beside the failure's Retry.
  const partStates = derivePartStates(
    durableTurns,
    transcript.optimisticTurns.filter((turn) => turn.status !== "failed").map((turn) => turn.userMessage),
  );
  const steps = planSteps(
    planQuery.data?.capability ?? durableTurns.at(-1)?.capability,
    durableTurns,
    partStates,
  );
  const streaming = transcript.isSubmitting;

  const runActive = runStatus === "running" || runStatus === "paused";
  // Task 044 Phase 5.5: a scoping walk parked on the baseline gate keeps the
  // thread open — the turn route accepts a question or a decision at exactly
  // this pause. The fence stays for every Evidence search check-in and for a
  // scoping walk that is still running.
  const atScopingGate =
    isScoping(planQuery.data) &&
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
  // The thread makes room for what arrives (task 058, round 9; the animation
  // sweep's entry 1): its box eases to the content's new height over 300 ms
  // on the strong ease-out, growth only (a settling card eases its own
  // shrink), and the pin follows the eased box, so the thread glides up as a
  // new block is revealed rather than jumping by its height. Not on the
  // first paint or a task switch; a cut under reduced motion.
  const firstPaintDone = useFirstPaintDone(transcript.data !== undefined, taskId);
  const [roomRef, contentRef] = useEasedHeight(firstPaintDone && !prefersReducedMotion(), true);
  // The site footer lives in `WorkspaceView`, under both columns (038 V8),
  // and opens only on a deliberate nudge past the transcript's end.
  const footer = useFooterReveal(onAtBottomChange);
  // The transcript opens at its end and stays there while new turns land
  // (shared with the chat pane).
  const pin = usePinToBottom(scrollRef, roomRef, taskId);

  // The plan card sits at its chronological position: right after the last
  // task_agent turn (approval always comes from a turn; turns are 409-fenced
  // during runs), so a started run's block renders BELOW it, not above.
  const lastTurnAt = thread.findLastIndex((item) => item.type === "task_agent_turn");
  // A theory of change pins its plan card where the plan was agreed: just before its first walk (round 7).
  const firstRunAt = isToc ? thread.findIndex((item) => item.type === "run_block") : -1;
  const planCardAt = firstRunAt > 0 ? firstRunAt : lastTurnAt === -1 ? thread.length : lastTurnAt + 1;
  // A theory of change has started once its theory exists or a walk runs: after a failed
  // draft the plan card offers "Draft the theory" again (owner, 2026-11-04).
  const planStarted = isToc
    ? tocGraph.data === undefined
      ? thread.some((item) => item.type === "run_block")
      : (tocGraph.data?.check_status ?? "none") !== "none"
    : thread.slice(planCardAt).some((item) => item.type === "run_block");
  const liveRunId = stream.run?.id;
  // Task 045 (A7): the live walk's own purpose, once the walk list has it —
  // an added option's search is not the baseline.
  const liveRunPurpose =
    (runsQuery.data?.data ?? []).find((run) => run.capability_run_id === liveRunId)?.purpose ?? null;
  const threadHasLiveRun = thread.some(
    (item) => item.type === "run_block" && item.run.capability_run_id === liveRunId,
  );
  const hasFindings = typeof funnel.data?.findings === "number" && funnel.data.findings > 0;

  // A theory of change's automatic chain is one card (task 054, decision 5,
  // S10): a check the server started after a draft draws the draft's rows
  // first and runs one timer from the draft's start; the draft gets no card
  // of its own. Between the two walks the card stays "Running".
  const threadRuns = runsQuery.data?.data ?? [];
  const tocChain = joinTocWalks(isToc ? threadRuns : []);
  const liveRead = threadRuns.find((run) => run.capability_run_id === liveRunId);
  const liveLead = isToc
    ? liveRunId !== undefined
      ? (tocChain.leadOf.get(liveRunId) ?? pendingLead(threadRuns, stream.run, tocChain))
      : null
    : null;
  const nowMs = useNow(isToc && stream.run !== null && isFinished(stream.run.status));
  const holding =
    isToc &&
    waitsForCheck(stream.run, stream.stages, liveRead?.toc_walk, liveRunId !== undefined && tocChain.joined.has(liveRunId), nowMs);

  // The run trace (task 058, owner 2026-11-05): the one place the live run
  // shows, in the Agent tab and the sidebar alike.
  const liveTrace =
    stream.run === null ? null : (
      <RunTrace
        taskId={taskId}
        status={holding ? "running" : stream.run.status}
        stages={liveLead !== null ? [...threadRunStages(liveLead), ...stream.stages] : stream.stages}
        liveness={stream.liveness}
        plan={stream.plan?.plan}
        startedAt={liveLead?.started_at ?? stream.run.startedAt}
        endedAt={holding ? undefined : stream.run.endedAt}
        hasFindings={hasFindings}
        capability={planQuery.data?.capability}
        purpose={liveRunPurpose}
        tocWalk={liveRead?.toc_walk ?? (liveLead !== null ? "check" : null)}
        isOwner={isOwner}
        ownerName={taskQuery.data?.owner_display ?? null}
        checkInWaiting={stream.pendingCheckIn !== null}
        onSeePlan={onReviewPlan}
        streamOpen={stream.connectionStatus === "connected"}
      />
    );
  // The thread's block the live card stands in: its own walk's, or, for a
  // check the runs read has not caught up with, the draft's it follows.
  const liveBlockId = liveLead !== null && !threadHasLiveRun ? liveLead.capability_run_id : liveRunId;

  const send = (input: { message: string; clientTurnId: string }) => {
    const trimmed = input.message.trim();
    if (trimmed.length === 0 || composerDisabled) return;
    setMessage("");
    // A failure stays on its own row with a retry; nothing to do here.
    void transcript.send({ message: trimmed, clientTurnId: input.clientTurnId }).catch(() => undefined);
  };

  // The opening turn (task 058, N9): the New Task screen navigates here at
  // once with the question, and this tab streams the planner's first reply.
  // The turn id was minted there, so the server's idempotency covers a
  // repeated mount; the navigation state is cleared once it is sent.
  const location = useLocation();
  const navigate = useNavigate();
  const opening = (location.state as { openingTurn?: { message: string; clientTurnId: string } } | null)
    ?.openingTurn;
  const openingSent = useRef<string | null>(null);
  const transcriptLoaded = transcript.data !== undefined;
  const { send: sendTurn } = transcript;
  useEffect(() => {
    if (opening === undefined || !transcriptLoaded || !isOwner) return;
    if (openingSent.current === opening.clientTurnId) return;
    openingSent.current = opening.clientTurnId;
    void navigate(`${location.pathname}${location.search}`, { replace: true, state: null });
    void sendTurn(opening).catch(() => undefined);
  }, [opening, transcriptLoaded, isOwner, sendTurn, navigate, location.pathname, location.search]);

  // An uploaded diagram: its bubble and "Reading…" show in the chat while it is read, then
  // the message it sends becomes the plan's starting point (task 054, increment 5).
  // The upload sends its own message once read, so it completes even if this chat closes.
  const attach = (file: File, note = "") => upload.mutate({ file, note });
  // A file picked on the new-task page arrives in the route state instead of an
  // opening turn (the upload's note is its opening); upload it once.
  const handOff = (location.state as Partial<TocUploadHandOff> | null)?.tocFile instanceof File ? (location.state as TocUploadHandOff) : null;
  const handedOff = useRef(false);
  useEffect(() => {
    if (handOff === null || handedOff.current || !isToc || !transcriptLoaded) return;
    handedOff.current = true;
    void navigate(`${location.pathname}${location.search}`, { replace: true, state: null });
    attach(handOff.tocFile, handOff.note);
  });

  // The planner's clarifying question and its quick replies come from the
  // stored turn (N10), so they survive a reload. They belong to the latest
  // turn only, and a turn that carries a part card answers through the card.
  const lastItem = thread.at(-1);
  const askingTurn =
    lastItem?.type === "task_agent_turn" && lastItem.turn.status === "completed" && lastItem.turn.part == null
      ? lastItem.turn
      : null;
  const suggestions = askingTurn?.suggestions ?? [];
  const question = askingTurn?.question ?? null;

  // The landing (no conversation yet) is a bare centred prompt — no pane
  // heading, no helper copy (Claude design concept; owner, 2026-08-05).
  const landing =
    transcript.data !== undefined &&
    thread.length === 0 &&
    transcript.optimisticTurns.length === 0 &&
    opening === undefined &&
    picked === null &&
    handOff === null;

  return (
    <UploadFiles.Provider value={uploadFiles}>
    <section aria-label="Task Agent conversation" className="flex h-full min-h-0 flex-col">
      {/* A lapsed stream on the Agent tab (owner, round 11): the run status
          bar's reconnecting line, at the top of this column so it starts
          after the rail. In the sidebar the page's own bar carries it. */}
      {!compact && <ReconnectingBanner connectionStatus={stream.connectionStatus} />}
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
        className="flex min-h-0 flex-1 flex-col overflow-y-auto py-4 [overflow-anchor:none] [scrollbar-gutter:stable]"
      >
        {/* Bottom-anchor: pushes a short thread to the composer end; the
            landing prompt sits in the top third (1:2 spacer split). */}
        <div aria-hidden="true" className={landing ? "flex-[1]" : "mt-auto"} />
        <ArrivalProvider settled={firstPaintDone} scopeKey={taskId}>
        <div ref={roomRef}>
        <div ref={contentRef} className={cn("space-y-6", LIFECYCLE_PAGE_CLASS)}>
        {transcript.isPending && (
          <div role="status" className="anim-breathe text-body text-grey">
            Loading your conversation…
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
            {isToc ? "What change do you want to explain?" : "What do you need evidence on?"}
          </h2>
        )}

        {(() => {
          // One list (round 14): a turn on its way and the stored turn that
          // replaces it share their key and their GrowBox, so the swap eases
          // in place; the plan card stays after both, never jumping between.
          const durable = thread.flatMap((item, index) => {
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
              <Arrival key={`gate-decision-${item.decision.checkInId}`} arrivalId={`gate-decision:${item.decision.checkInId}`}>
                <SettledGateCard label={item.decision.label} />
              </Arrival>
            ) : item.type === "task_agent_turn" ? (
              <GrowBox key={`turn-${item.turn.client_turn_id}`} arrivalId={`turn:${item.turn.client_turn_id}`}>
              <DurableTurn
                taskId={taskId}
                turn={item.turn}
                isLatest={item.turn.turn_index === latestTurnIndex}
                onRetry={send}
                retryDisabled={composerDisabled}
                partState={partStates.get(item.turn.turn_index)}
                steps={steps}
                plan={planQuery.data?.plan}
                scopingPlan={planQuery.data?.scoping}
                onSend={(text) => send({ message: text, clientTurnId: crypto.randomUUID() })}
                tocCodes={tocCodes}
              />
              </GrowBox>
            ) : isToc && tocChain.joined.has(item.run.capability_run_id) ? null : isToc &&
              item.run.capability_run_id === liveBlockId &&
              liveTrace !== null ? (
              // One key for the chain (the draft's id), so the draft's card
              // carries on as the check's when the check arrives (S10).
              <GrowBox key={`run-${liveLead?.capability_run_id ?? liveRunId}`} arrivalId={`run:${liveLead?.capability_run_id ?? liveRunId}`}>
                <Arrival arrivalId={`run:${liveLead?.capability_run_id ?? liveRunId}`}>{liveTrace}</Arrival>
              </GrowBox>
            ) : isToc ? (
              <GrowBox
                key={`run-${tocChain.leadOf.get(item.run.capability_run_id)?.capability_run_id ?? item.run.capability_run_id}`}
                arrivalId={`run:${tocChain.leadOf.get(item.run.capability_run_id)?.capability_run_id ?? item.run.capability_run_id}`}
              >
                <Arrival arrivalId={`run:${tocChain.leadOf.get(item.run.capability_run_id)?.capability_run_id ?? item.run.capability_run_id}`}>
                  <PastRunLine
                    run={item.run}
                    leadRun={tocChain.leadOf.get(item.run.capability_run_id) ?? null}
                    taskId={taskId}
                    capability={planQuery.data?.capability}
                  />
                </Arrival>
              </GrowBox>
            ) : item.run.capability_run_id === liveRunId && liveTrace !== null ? (
              <GrowBox key="live-run-block" arrivalId={`run:${liveRunId}`}>
              <div className="space-y-6">
                <Arrival arrivalId={`run:${liveRunId}`}>{liveTrace}</Arrival>
                <AnsweredCheckIns answered={streamDecisions} checkIns={checkInsQuery.data} stages={stream.stages} />
              </div>
              </GrowBox>
            ) : (
              <RunBlock
                key={`run-${item.run.capability_run_id}`}
                taskId={taskId}
                hasFindings={hasFindings}
                run={item.run}
                capability={planQuery.data?.capability}
                stages={stream.stages}
                answered={
                  item.run.capability_run_id === stream.run?.id ? streamDecisions : []
                }
                checkIns={checkInsQuery.data}
              />
            );
          return rendered === null ? [] : [{ rendered, index }];
          });
          const planCard = (
            <PlanCard key="plan-card" taskId={taskId} runActive={runActive} streaming={streaming} started={planStarted} isOwner={isOwner} onReviewPlan={onReviewPlan} overlay={planOverlay} onOverlayApplied={onOverlayApplied} onDiscardOverlay={onDiscardOverlay} />
          );
          const inFlight = transcript.optimisticTurns.map((turn: OptimisticTaskAgentTurn) => (
            <GrowBox key={`turn-${turn.clientTurnId}`} arrivalId={`turn:${turn.clientTurnId}`}>
              <InFlightTurn
                turn={turn}
                composerDisabled={composerDisabled}
                onDiscard={() => transcript.discard(turn.clientTurnId)}
                onRetry={() => void transcript.retry(turn.clientTurnId)}
              />
            </GrowBox>
          ));
          // The plan card follows the last turn; with turns on their way and
          // nothing after the stored ones, it follows those too.
          const planAfterInFlight = inFlight.length > 0 && planCardAt >= thread.length;
          return [
            ...durable.flatMap(({ rendered, index }) =>
              index === planCardAt - 1 && !planAfterInFlight ? [rendered, planCard] : [rendered],
            ),
            ...inFlight,
            ...(planAfterInFlight && planCardAt > 0 ? [planCard] : []),
          ];
        })()}

        {picked !== null && (
          <>
            <UserBubble text={uploadMessage(picked.name, pickedNote)} turnId={`upload:${picked.name}`} />
            <div role="status" className="anim-breathe mr-8 flex items-center gap-2 px-3.5 text-body text-grey">
              <span aria-hidden="true" className="h-2 w-2 bg-blue" />
              Reading your diagram… this takes about half a minute.
            </div>
          </>
        )}
        {upload.isError && (
          <p role="alert" className="mr-8 text-lead text-red">
            {(upload.error as Error | null)?.message ?? "The file couldn't be read. Try again."}
          </p>
        )}

        {/* The planner's question, then its quick replies (N10). The chips
            send a task_agent turn (task 033 phase 10c, contract § 11 / rubric
            37) — owner-only, hidden for a colleague rather than left
            clickable to a 403. */}
        {isOwner && suggestions.length > 0 && !streaming && !composerFenced && (
          <Arrival arrivalId={`suggestions:${askingTurn?.client_turn_id ?? ""}`} className="mr-8 space-y-2">
            {question !== null && question !== "" && (
              <p className="max-w-prose-measure text-body font-semibold text-navy">{scrub(question)}</p>
            )}
            <div className="flex flex-wrap gap-1.5">
            {suggestions.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                onClick={() => send({ message: suggestion, clientTurnId: crypto.randomUUID() })}
                className="cursor-pointer border border-blue-tint bg-blue-tint px-2.5 py-1 text-caption font-semibold text-blue hover:bg-blue-tint-2"
              >
                {scrub(suggestion)}
              </button>
            ))}
            </div>
          </Arrival>
        )}

        {liveTrace !== null && !threadHasLiveRun && !(isToc && liveLead !== null) && (
          <GrowBox key="live-run-fallback" arrivalId={`run:${liveRunId}`}>
          <div className="space-y-6">
            <Arrival arrivalId={`run:${liveRunId}`}>{liveTrace}</Arrival>
            <AnsweredCheckIns answered={streamDecisions} checkIns={checkInsQuery.data} stages={stream.stages} />
          </div>
          </GrowBox>
        )}
        {/* A waiting check-in sits under the run's trace. */}
        {stream.pendingCheckIn !== null && stream.pendingCheckIn.kind !== BASELINE_GATE_KIND && (
          <CheckInCard
            key={stream.pendingCheckIn.check_in_id}
            taskId={taskId}
            checkIn={stream.pendingCheckIn}
            stages={stream.stages}
            isOwner={isOwner}
            compact={compact}
          />
        )}
        {/* A review of the theory runs in the background (C45): the shared
            working line, its mark turning, until its message lands. */}
        {tocReviewing && <ActionLine label="Reviewing the theory" live arrivalId={`toc-review:${taskId}`} />}
        </div>
        </div>
        </ArrivalProvider>
        {landing && <div aria-hidden="true" className="flex-[2]" />}
      </div>
      <JumpToEnd visible={!pin.atEnd} onClick={pin.jumpToEnd} />
      </div>

      <div className="shrink-0 border-t border-line">
        <div className={cn("py-3", LIFECYCLE_PAGE_CLASS)}>
        <Composer
          value={message}
          onChange={setMessage}
          onSubmit={() => send({ message, clientTurnId: crypto.randomUUID() })}
          placeholder={taskAgentComposerPlaceholder(runStatus, planReady || planQuery.data?.toc?.ready === true, isOwner, atScopingGate, hasLonglist(taskQuery.data), isToc)}
          disabled={composerFenced || !isOwner || upload.isPending}
          sendDisabled={composerDisabled || upload.isPending}
          onAttach={
            // Before the draft the user's own diagram becomes the plan; after it, what it adds waits as suggestions.
            isToc && isOwner && !tocLive ? (file) => attach(file) : undefined
          }
        />
        </div>
      </div>
      </div>
    </section>
    </UploadFiles.Provider>
  );
}
