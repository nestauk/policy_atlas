import type { SseFrame } from "../api/sseFrame";
import type { AuthApi } from "../auth/types";
import type { components } from "../api/gen/types";
import { PROJECT, TASK } from "../lib/vocabulary";
import type { EvidenceSortField } from "../views/sourcesPresentation";
import {
  mockArtefact,
  mockArtefactSectionProse,
  mockBaselineGateCheckIn,
  mockScopingAnswerTurn,
  mockScopingDecisionTurn,
  MOCK_BASELINE_CHECK_IN_ID,
  mockArtefactSkeleton,
  mockArtefactSectionRepairedProse,
  mockCaseStudiesProse,
  mockCaseStudyCards,
  mockSectionCitations,
  MOCK_CASE_STUDIES_INDEX,
  MOCK_FULL_REPORT_INTRO,
  MOCK_INTRO_INDEX,
  mockKeyFindingsClaim,
  mockSourceNotes,
  mockSearchQueries,
  mockLiveThemes,
  MOCK_STREAMED_SECTION_INDEX,
  mockSectionOneRevisingSpan,
  mockSectionOneClaims,
  mockSectionOneSources,
  mockCheckIn,
  mockPlannerTurn,
  STAGE_COUNTS,
  STAGE_PRESENTATION,
  MOCK_OPTION_COUNT,
  foldMockOptionRows,
  mockChildRunId,
  mockOptionFound,
  seedMockOptionRows,
  mockCoverage,
  mockDecisions,
  mockEvidence,
  mockEvidenceThemeIds,
  mockOtherTasks,
  mockFindings,
  mockFunnel,
  mockGroups,
  mockLandscape,
  mockMeUnenrolled,
  mockPlanReady,
  mockProject,
  mockScopingPlanReady,
  mockTask,
  mockSourceDossiers,
  seedTaskAgentTurns,
  MOCK_CHAT_ANSWER_DELTAS,
  MOCK_CHAT_CITATION_CHUNK_ID,
  MOCK_CHAT_CITATION_QUOTE,
  MOCK_CHAT_CLAIM_ID,
  MOCK_CHAT_CLAIM_TEXT,
  MOCK_CHAT_PROGRESS_LABEL,
  MOCK_CHECK_IN_ID,
  MOCK_LINK_ID,
  MOCK_LINK_SOURCE_RUN_ID,
  MOCK_PLAN_ID,
  MOCK_TASK_AGENT_CONVERSATION_ID,
  MOCK_TASK_ID,
  MOCK_RUN_ID,
  mockAuthorships,
  mockBaselineArtefact,
  buildMockAddedOption,
  mockLonglist,
  mockLonglistExtraOptionIds,
  mockLonglistOptionCards,
  mockWalkLonglist,
  mockWalkOptionCards,
  toLonglistOptionSummary,
  type MockWalkLonglistStage,
  mockShortlistState,
  MOCK_SHORTLIST_PLACES_TARGET,
  resetMockShortlist,
} from "./fixtures";

type MeOut = components["schemas"]["MeOut"];
type ProjectOut = components["schemas"]["ProjectOut"];

type RunOut = components["schemas"]["RunOut"];
type TaskOut = components["schemas"]["TaskOut"];
type TaskAgentTranscriptTurnOut = components["schemas"]["TaskAgentTranscriptTurnOut"];
type EvidenceItemOut = components["schemas"]["EvidenceItemOut"];
type ConversationOut = components["schemas"]["ConversationOut"];
type ConversationListItemOut = components["schemas"]["ConversationListItemOut"];
type ChatTurnOut = components["schemas"]["ChatTurnOut"];
type StageKey = components["schemas"]["StageStartedFrame"]["stage"];
type TaskAgentTurnOut = components["schemas"]["TaskAgentTurnOut"];

/** The planner's progress line, the server's `STEP_VERBS["task_agent_turn"]`. */
const STEP_DRAFTING_THE_PLAN = "Drafting the plan";

const EVIDENCE_STATUS_SORT_RANK: Record<EvidenceItemOut["status"], number> = {
  found: 0,
  screened_out: 1,
  relevant: 2,
  not_selected: 3,
  selected: 4,
  read_in_full: 5,
  findings_extracted: 6,
  cited: 7,
  unavailable: 8,
};

// Mock fixtures carry an appraisal *label*, not the backend's underlying
// quality score — this rank mirrors the same three tiers the fixtures use
// (`sourceDossier` details) well enough for an honest relative order.
const APPRAISAL_TIER_SORT_RANK: Record<string, number> = {
  "Low confidence": 0,
  "Moderate confidence": 1,
  "High confidence": 2,
};

/** The label of an appraisal with no score (task 056). Like the server, it
 *  sorts after every scored row in both directions, before an unappraised one. */
const UNRATED_TIER = "Unrated";

/** Mirrors `repository._relevance_rank`: the p(relevant) spectrum. */
function mockRelevanceRank(item: EvidenceItemOut): number | null {
  if (item.screen_status === "relevant") return item.screen_confidence ?? 0.5;
  if (item.screen_status === "not_relevant") return 1 - (item.screen_confidence ?? 0.5);
  if (item.screen_status === "excluded_retracted") return -1;
  return null;
}

/** Mirrors `repository._compare_evidence_sort`: nulls always sort last,
 *  regardless of `direction`. */
function compareMockEvidenceSort(
  left: EvidenceItemOut,
  right: EvidenceItemOut,
  sort: EvidenceSortField,
  direction: "asc" | "desc",
): number {
  let leftValue: string | number | null;
  let rightValue: string | number | null;
  if (sort === "strength" && left.appraisal_tier === UNRATED_TIER && right.appraisal_tier !== UNRATED_TIER) {
    return right.appraisal_tier == null || !(right.appraisal_tier in APPRAISAL_TIER_SORT_RANK) ? -1 : 1;
  }
  if (sort === "strength" && right.appraisal_tier === UNRATED_TIER && left.appraisal_tier !== UNRATED_TIER) {
    return left.appraisal_tier == null || !(left.appraisal_tier in APPRAISAL_TIER_SORT_RANK) ? 1 : -1;
  }
  if (sort === "title") {
    leftValue = left.title.toLowerCase();
    rightValue = right.title.toLowerCase();
  } else if (sort === "year") {
    leftValue = left.year ?? null;
    rightValue = right.year ?? null;
  } else if (sort === "type") {
    leftValue = left.evidence_type ?? null;
    rightValue = right.evidence_type ?? null;
  } else if (sort === "strength") {
    leftValue = left.appraisal_tier !== null && left.appraisal_tier !== undefined
      ? APPRAISAL_TIER_SORT_RANK[left.appraisal_tier] ?? null
      : null;
    rightValue = right.appraisal_tier !== null && right.appraisal_tier !== undefined
      ? APPRAISAL_TIER_SORT_RANK[right.appraisal_tier] ?? null
      : null;
  } else if (sort === "relevance") {
    leftValue = mockRelevanceRank(left);
    rightValue = mockRelevanceRank(right);
  } else {
    leftValue = EVIDENCE_STATUS_SORT_RANK[left.status];
    rightValue = EVIDENCE_STATUS_SORT_RANK[right.status];
  }
  if (leftValue === null) return rightValue === null ? 0 : 1;
  if (rightValue === null) return -1;
  if (leftValue === rightValue) return 0;
  const result = leftValue < rightValue ? -1 : 1;
  return direction === "asc" ? result : -result;
}

/**
 * Scripted event-stream variants (contract strand 13 fixture requirement):
 * `"default"` is the full skeleton -> writing -> filled -> succeeded flow the
 * main journey drives (round 9: the search first says it is writing its
 * queries, then sends five topic queries and one citations pass as
 * `search.query` frames, each out then back with its count; the characterise
 * stage sends its four themes as `characterise.themes` before its batches); `"paused"` holds indefinitely at a mid-synthesis
 * "writing" state (a demo/screenshot fixture — the run never resolves);
 * `"failed-partial"` streams both sections then ends the run `failed`, the
 * terminal-partial banner fixture the contract names. `"reload-mid-section"`
 * is what a reconnect sees mid-write (task 058, N26): the durable replay up to
 * `artefact.section_started` for the streamed section (display index 1), one
 * `replace` delta carrying the first half of the prose, then appends for the
 * rest. The key findings (index 0) stream as deltas with one claim mark before
 * they complete (round 8). The case-studies slot (index 2): its two cards
 * stream as `artefact.section_card` frames, then the checked cards land
 * (task 058, round 7). Then two source notes arrive as `artefact.source_note`
 * frames, and the introduction streams into its slot (index 3, role `intro`)
 * and completes (round 8). `"paused-strip"` runs
 * to the check-in after searching and screening and holds there for good,
 * for the run status bar's paused state. Selected via a
 * `?mockScenario=` query param on the `/events` request itself — a direct
 * mock-layer fixture switch (see `mock/api.test.ts`), not something the real
 * SSE client currently forwards from the page URL.
 */
type MockScenario = "default" | "paused" | "failed-partial" | "reload-mid-section" | "paused-strip";

const MOCK_SCENARIOS: readonly MockScenario[] = ["paused", "failed-partial", "reload-mid-section", "paused-strip"];

/** All frames in the scripted stream share this display timestamp — a mock
 *  fixture's `occurred_at` is presentation metadata only, never load-bearing. */
const FRAME_TIME = "2026-07-21T09:30:00Z";

interface Deferred {
  promise: Promise<void>;
  resolve: () => void;
}

/** How often the scripted walks emit an activity tick. */
export const MOCK_TICK_MS = 400;
/** Scales every scripted wait of the walks and streams below; tests set it near
 *  zero so a whole walk plays in milliseconds. */
let mockPace = 1;

/** Test helper: scale the scripted waits (1 is real time, 0.01 is fast). */
export function setMockPace(scale: number) {
  mockPace = scale;
}

function pace(ms: number): Promise<void> {
  return sleep(Math.round(ms * mockPace));
}

/** True once a fresh task has started the planner's scripted conversation
 *  (question, scope, thoroughness); the seeded transcript stays as it is. */
let plannerScripted = false;

let checkInAnswer = createDeferred();
let checkInAnswered = false;
// Task 044 Phase 5.5: the options-scoping baseline gate, held separately
// from the Evidence search check-in above so the two scripts cannot collide.
let baselineGateAnswer = createDeferred();
let baselineGateDecision: { optionId: string; label: string } | null = null;
/** When the gate's card opened in this session (its `created_at`). */
let baselineGateOpenedAt: string | null = null;
let runStarted = createDeferred();
let currentRun: RunOut | null = null;
let taskAgentTurns: TaskAgentTranscriptTurnOut[] = seedTaskAgentTurns();
let nextTurnIndex = 4; // the seed transcript occupies turn_index 1-3

// --- Chat conversations + turns (task 029 phase G3 mock) -----------------
// Follow-up chats are created on demand. The task_agent conversation is
// pre-seeded so the chats overlay (G14) has a task_agent row in mock mode,
// matching a real task that already has a plan lineage.
function seedConversations(): ConversationOut[] {
  return [
    {
      id: MOCK_TASK_AGENT_CONVERSATION_ID,
      task_id: MOCK_TASK_ID,
      kind: "task_agent",
      title: "Planning",
      status: "active",
      entry_artefact_id: null,
      created_at: "2026-07-18T09:00:00Z",
      closed_at: null,
      archived_at: null,
    },
  ];
}

let chatConversations: ConversationOut[] = seedConversations();
let chatTurnsByConversation = new Map<string, ChatTurnOut[]>();
// Counts reads of a still-`pending` turn's enrichment: the first read is the
// `completed` event's own `invalidateTurns()` refetch (still pending, the
// honest "unchecked" state); the second is the store's enrichment poll,
// which this flips to `enriched` — the scripted async-judge fixture.
let chatTurnEnrichmentReads = new Map<string, number>();
let currentPlan: components["schemas"]["PlanDraft"] = { ...mockPlanReady };
// Task 044: the mock's scoping-plan counterpart to `currentPlan`, read only
// while `mockTask.capability === "options_scoping"`.
let currentScopingPlan: components["schemas"]["ScopingPlanDraft"] = { ...mockScopingPlanReady };

/** A scoping task's `PlanOut` at a version. */
function scopingPlanOut(version: number) {
  return { capability: "options_scoping", plan: null, scoping: currentScopingPlan, version, status: "approved" } as const;
}

// --- Identity + projects (task 033 phase 10a) --------------------------
// `currentMe` defaults to the unenrolled fixture — dark launch: every
// pre-033 mock journey sees `organisation: null` and stays unchanged. Tests
// that need the enrolled/org-scoped journeys call `setMockMe(mockMeEnrolled)`.
let currentMe: MeOut = { ...mockMeUnenrolled };
let mockProjects: ProjectOut[] = [{ ...mockProject }];
const mockWaitlistEmails = new Set<string>();

/** Test helper: switch the mock's `/me` identity (e.g. to `mockMeEnrolled`). */
export function setMockMe(me: MeOut) {
  currentMe = { ...me };
}

/** Reset every scripted scenario; useful for isolated mock tests. */
export function resetMockScenario() {
  checkInAnswer = createDeferred();
  checkInAnswered = false;
  baselineGateAnswer = createDeferred();
  baselineGateDecision = null;
  baselineGateOpenedAt = null;
  runStarted = createDeferred();
  currentRun = null;
  mockTask.latest_run = null;
  taskAgentTurns = seedTaskAgentTurns();
  nextTurnIndex = 4;
  plannerScripted = false;
  mockTask.active_run = null;
  chatConversations = seedConversations();
  chatTurnsByConversation = new Map();
  chatTurnEnrichmentReads = new Map();
  currentPlan = { ...mockPlanReady };
  currentScopingPlan = { ...mockScopingPlanReady };
  currentMe = { ...mockMeUnenrolled };
  mockProjects = [{ ...mockProject }];
  mockTask.is_owner = true;
  mockTask.is_public = false;
  // Options added by hand belong to one scenario, not the next.
  for (const optionId of mockLonglistExtraOptionIds.splice(0)) delete mockLonglistOptionCards[optionId];
  resetMockLonglistWalks();
  resetMockShortlist();
}

function currentMockScenario(requestUrl: URL): MockScenario {
  const value = requestUrl.searchParams.get("mockScenario");
  return MOCK_SCENARIOS.find((scenario) => scenario === value) ?? "default";
}

/** Fetch implementation for the generated openapi-fetch client in mock mode. */
export async function mockFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const request = input instanceof Request ? input : undefined;
  const url = new URL(request?.url ?? input.toString(), globalThis.location?.origin ?? "http://localhost");
  const method = init?.method ?? request?.method ?? "GET";
  const path = url.pathname;

  if (method === "POST" && path.endsWith("/api/v1/waitlist")) {
    const body = await requestBody(request, init);
    if (!isRecord(body) || typeof body.email !== "string" || typeof body.name !== "string") {
      return json({ error: { code: "validation_error", message: "Invalid waitlist body" } }, 422);
    }
    const email = String(body.email).trim().toLowerCase();
    if (mockWaitlistEmails.has(email)) {
      return json(
        { error: { code: "already_registered", message: "This email is already on the waitlist." } },
        409,
      );
    }
    mockWaitlistEmails.add(email);
    return json(
      {
        entry_id: crypto.randomUUID(),
        email,
        created_at: new Date().toISOString(),
      },
      201,
    );
  }

  if (method === "GET" && path.endsWith(`/api/v1/tasks/${MOCK_TASK_ID}/events`)) {
    return new Response(createMockEventStream(currentMockScenario(url)), {
      headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" },
    });
  }
  // Task 044 Phase 5.5: the baseline gate. Both options end the walk — one
  // through to the longlist, one back to an editable plan — and each leaves a
  // `decision` turn in the Task Agent thread, exactly as the turn route does.
  if (method === "POST" && path.endsWith(`/api/v1/tasks/${MOCK_TASK_ID}/check-ins/${MOCK_BASELINE_CHECK_IN_ID}/response`)) {
    const body = await requestBody(request, init);
    if (baselineGateDecision !== null) {
      return json({ error: { code: "already_answered", message: "This check-in has already been answered." } }, 409);
    }
    const optionId = isRecord(body) && typeof body.option_id === "string" ? body.option_id : "confirm_plan";
    const option = (mockBaselineGateCheckIn.options ?? []).find((entry) => entry.id === optionId);
    baselineGateDecision = { optionId, label: option?.label ?? optionId };
    const decidedAt = new Date().toISOString();
    taskAgentTurns.push(
      mockScopingDecisionTurn(optionId, baselineGateDecision.label, nextTurnIndex, decidedAt),
    );
    nextTurnIndex += 1;
    // The walk ends in the same request the decision lands in, so the runs
    // read is already terminal when the answer's invalidation refetches it.
    finishRun(optionId === "change_plan" ? "aborted" : "succeeded");
    // Task 045 (6.3): the gate's Confirm opens the longlist walk, as the
    // turn route and the card do.
    if (optionId !== "change_plan") requestMockLonglistWalk(mockScopingPlanVersion);
    baselineGateAnswer.resolve();
    return json({ accepted: true });
  }
  if (method === "POST" && path.endsWith(`/api/v1/tasks/${MOCK_TASK_ID}/check-ins/${MOCK_CHECK_IN_ID}/response`)) {
    const body = await requestBody(request, init);
    checkInAnswer.resolve();
    checkInAnswered = true;
    if (isRecord(body) && body.kind === "free_text") {
      return json({
        render: "Use the free-text steer to foreground Tower Hamlets family support and keep the active-travel evidence gap explicit.",
        confirm_token: "mock-confirm-balanced-synthesis",
      }, 202);
    }
    return json({ accepted: true });
  }

  // Task 044 (C10): create is ONE request carrying the kind of work, the
  // projects and the tasks it starts from. The mock stores the capability so
  // the New task screen's two paths are exercisable without a backend; it
  // does not simulate the Link rules, which are server-side invariants with
  // their own backend tests.
  if (method === "POST" && path.endsWith("/api/v1/tasks")) {
    const body = await requestBody(request, init);
    const capability =
      isRecord(body) && body.capability === "options_scoping"
        ? "options_scoping"
        : "evidence_search";
    const fromTaskIds =
      isRecord(body) && Array.isArray(body.from_task_ids)
        ? body.from_task_ids.filter((value): value is string => typeof value === "string")
        : [];
    // Task 044 (C10, C11): the mock's single-task world only ever offers the
    // current task as a "Starts from" candidate — its name is captured here,
    // before the same object below is overwritten to become the new task.
    const sourceTaskName = mockTask.name;
    if (capability === "options_scoping") {
      baselineGateAnswer = createDeferred();
      baselineGateDecision = null;
    }
    const created = new Date().toISOString();
    const task: TaskOut = {
      ...mockTask,
      task_id: MOCK_TASK_ID,
      name: isRecord(body) && typeof body.name === "string" ? body.name : mockTask.name,
      question:
        isRecord(body) && typeof body.question === "string" ? body.question : null,
      capability,
      status: "active",
      created_at: created,
      updated_at: created,
      archived_at: null,
      latest_run: null,
      project_ids:
        isRecord(body) && Array.isArray(body.project_ids)
          ? body.project_ids.filter((value): value is string => typeof value === "string")
          : [],
      links:
        fromTaskIds.length > 0
          ? [
              {
                link_id: MOCK_LINK_ID,
                source_task_id: fromTaskIds[0],
                source_task_name: sourceTaskName,
                source_capability_run_id: MOCK_LINK_SOURCE_RUN_ID,
                flagged: false,
              },
            ]
          : [],
    };
    Object.assign(mockTask, task);
    // A fresh task starts a fresh session in the mock's single-task world —
    // the previous task's transcript, run and chats must not bleed into it.
    // The task_agent transcript is then re-seeded to a pre-scripted ready
    // plan for the chosen capability (like `currentPlan` above) so the New
    // task journey can show a finished plan document without scripting
    // every intermediate turn.
    taskAgentTurns = [];
    nextTurnIndex = 1;
    plannerScripted = true;
    currentRun = null;
    resetMockLonglistWalks();
    chatConversations = seedConversations();
    chatTurnsByConversation = new Map();
    chatTurnEnrichmentReads = new Map();
    currentPlan = { ...mockPlanReady };
    currentScopingPlan =
      capability === "options_scoping"
        ? { ...mockScopingPlanReady, linked_task_ids: fromTaskIds }
        : { ...mockScopingPlanReady };
    return json(task, 201);
  }

  // --- Project lifecycle (landing rename/archive, contract strand 8) ------
  if (method === "PATCH" && path.endsWith(`/api/v1/tasks/${MOCK_TASK_ID}`)) {
    const body = await requestBody(request, init);
    // Task 033 phase 10b: i.5 — a Task's own visibility can't be set while
    // it's in a Project (project membership). The mock mirrors the real
    // 409 `visibility_conflict` so the control's error line is exercisable
    // in mock mode too, not just against a live backend. Checked before any
    // field is assigned, matching the real API's all-or-nothing conflict —
    // a 409 must leave every field (including a same-body rename) untouched.
    if (
      isRecord(body) &&
      (body.visibility === "org" || body.visibility === "private") &&
      (mockTask.project_ids?.length ?? 0) > 0
    ) {
      return json({ error: { code: "visibility_conflict", message: `${TASK.one} is in a ${PROJECT.one}.` } }, 409);
    }
    // Task 058, round 10: PATCH is owner-only; a colleague's project change
    // gets the server's 403 and its plain message (flip `mockTask.is_owner`
    // to walk the colleague's Share page).
    if (isRecord(body) && "project_ids" in body && mockTask.is_owner === false) {
      return json({ error: { code: "forbidden", message: PROJECTS_OWNER_ONLY } }, 403);
    }
    if (isRecord(body) && typeof body.name === "string") mockTask.name = body.name;
    if (isRecord(body) && typeof body.question === "string") mockTask.question = body.question;
    if (isRecord(body) && typeof body.is_public === "boolean") mockTask.is_public = body.is_public;
    if (isRecord(body) && (body.visibility === "org" || body.visibility === "private")) {
      mockTask.visibility = body.visibility;
    }
    if (isRecord(body) && Array.isArray(body.project_ids)) {
      mockTask.project_ids = body.project_ids.filter(
        (value): value is string => typeof value === "string",
      );
    }
    mockTask.updated_at = new Date().toISOString();
    return json(mockTask);
  }
  if (method === "POST" && path.endsWith(`/api/v1/tasks/${MOCK_TASK_ID}/archive`)) {
    mockTask.status = "archived";
    mockTask.archived_at = new Date().toISOString();
    return json(mockTask);
  }

  // --- Durable task_agent transcript (contract strand 12) -------------------
  if (method === "GET" && path.endsWith(`/api/v1/tasks/${MOCK_TASK_ID}/task-agent-turns`)) {
    return json(page(taskAgentTurns));
  }
  if (method === "POST" && path.endsWith(`/api/v1/tasks/${MOCK_TASK_ID}/task-agent-turns`)) {
    const body = await requestBody(request, init);
    const clientTurnId = isRecord(body) && typeof body.client_turn_id === "string" ? body.client_turn_id : crypto.randomUUID();
    const message = isRecord(body) && typeof body.message === "string" ? body.message : "";
    // The route streams (task 058, N9): a `progress` line, the reply in
    // `delta` pieces, then one `completed` carrying the stored turn. The
    // transcript changes when the stream finishes, never before.
    // Task 044 Phase 5.5: while the scoping walk is parked on the baseline
    // gate the turn route answers FROM the baseline — an `answer` turn with
    // citations, not a planning reply.
    // The mock's REST run row stays `running` while the stream parks (the
    // pause is a stream state), so the gate is "open" from the walk's start
    // until its decision lands.
    const atGate =
      mockTask.capability === "options_scoping" &&
      currentRun !== null &&
      currentRun.status === "running" &&
      baselineGateDecision === null;
    if (atGate && taskAgentTurns.every((turn) => turn.client_turn_id !== clientTurnId)) {
      const answerReply = mockScopingAnswerTurn(clientTurnId, message, nextTurnIndex, new Date().toISOString()).reply ?? "";
      return ndjsonResponse(createMockTaskAgentStream(answerReply, () => {
        const answerTurn = mockScopingAnswerTurn(clientTurnId, message, nextTurnIndex, new Date().toISOString());
        taskAgentTurns.push(answerTurn);
        nextTurnIndex += 1;
        return {
          reply: answerTurn.reply ?? "",
          suggestions: [],
          capability: "options_scoping",
          kind: "answer",
          answer: answerTurn.answer,
          scoping_plan: currentScopingPlan,
        };
      }));
    }
    const existing = taskAgentTurns.find((turn) => turn.client_turn_id === clientTurnId);
    const scripted =
      plannerScripted && mockTask.capability !== "options_scoping"
        ? mockPlannerTurn(existing?.turn_index ?? nextTurnIndex)
        : { reply: "Noted — I'll keep that in mind for the analysis.", question: null, suggestions: [], part: null };
    return ndjsonResponse(createMockTaskAgentStream(scripted.reply, () => {
      const now = new Date().toISOString();
      if (existing !== undefined) {
        // Retry-in-place (finding 6): the same client_turn_id re-runs, never a
        // fresh turn_index.
        existing.status = "completed";
        existing.reply = scripted.reply;
        existing.question = scripted.question;
        existing.suggestions = scripted.suggestions;
        existing.part = scripted.part;
        existing.completed_at = now;
      } else {
        taskAgentTurns.push({
          client_turn_id: clientTurnId,
          turn_index: nextTurnIndex,
          user_message: message,
          reply: scripted.reply,
          question: scripted.question,
          suggestions: scripted.suggestions,
          part: scripted.part,
          status: "completed",
          created_at: now,
          completed_at: now,
        });
        nextTurnIndex += 1;
      }
      // Task 044: a scoping task's turn carries `scoping_plan`, never `plan`
      // (`PlanOut`'s own capability-keyed shape, mirrored here).
      if (mockTask.capability === "options_scoping") {
        return { scoping_plan: currentScopingPlan, reply: scripted.reply, suggestions: [], capability: "options_scoping" };
      }
      return {
        plan: currentPlan,
        reply: scripted.reply,
        question: scripted.question,
        suggestions: scripted.suggestions,
        part: scripted.part,
        capability: "evidence_search",
      };
    }));
  }

  // --- Plan (a resumed session: the transcript above already reached
  // `ready` — see mockPlanReady / mockScopingPlanReady) -------------------
  if (method === "GET" && path.endsWith(`/api/v1/tasks/${MOCK_TASK_ID}/plan`)) {
    if (mockTask.capability === "options_scoping") {
      // Task 045 (6.3): the version moves with each edit and confirm, so
      // the plan document can tell a longlist built from an older version.
      return json(scopingPlanOut(mockScopingPlanVersion));
    }
    return json({ capability: "evidence_search", plan: currentPlan, version: 1, status: "approved" });
  }
  if (method === "POST" && path.endsWith(`/api/v1/tasks/${MOCK_TASK_ID}/plan/confirm-baseline`)) {
    const body = await requestBody(request, init);
    const planVersion = isRecord(body) && typeof body.plan_version === "number" ? body.plan_version : 1;
    const artefactId = isRecord(body) && typeof body.artefact_id === "string" ? body.artefact_id : "";
    // Mirrors the API: the record is minted as a NEW approved version and
    // names that version, so "the record names the current version" holds
    // until the next plan edit mints a version without it.
    const minted = planVersion + 1;
    currentScopingPlan = {
      ...currentScopingPlan,
      baseline_confirmed: { artefact_id: artefactId, plan_version: minted },
    };
    // Task 045 (6.3): the confirm opens the longlist walk on the version it
    // minted (a rebuild when a longlist already exists — D14, P12).
    mockScopingPlanVersion = minted;
    const openedRun = requestMockLonglistWalk(minted);
    return json({ ...scopingPlanOut(minted), opened_run: openedRun });
  }
  if (method === "PATCH" && path.endsWith(`/api/v1/tasks/${MOCK_TASK_ID}/plan`)) {
    const body = await requestBody(request, init);
    // Task 045: a scoping plan's direct edits — the constraint list (removing
    // the default transferability preference) and the options by their words
    // (unchanged words keep their design; the mock proposes none for new ones).
    if (mockTask.capability === "options_scoping" && isRecord(body) && isRecord(body.scoping)) {
      const edits = body.scoping;
      if (typeof edits.risk_appetite === "string") {
        // The appetite alone: a new plan version, a stale proposal, and no
        // change to what the longlist reads (task 055, A6).
        currentScopingPlan = {
          ...currentScopingPlan,
          risk_appetite: edits.risk_appetite as NonNullable<typeof currentScopingPlan.risk_appetite>,
        };
        mockShortlistState.stale = true;
      }
      if (Array.isArray(edits.constraints) || Array.isArray(edits.your_options)) {
        mockShortlistState.inputsChanged = true;
      }
      if (Array.isArray(edits.constraints)) {
        currentScopingPlan = {
          ...currentScopingPlan,
          constraints: edits.constraints as NonNullable<typeof currentScopingPlan.constraints>,
        };
      }
      if (Array.isArray(edits.your_options)) {
        const previous = currentScopingPlan.your_options ?? [];
        currentScopingPlan = {
          ...currentScopingPlan,
          your_options: edits.your_options.filter(isRecord).map((option) => {
            const text = typeof option.text === "string" ? option.text : "";
            return previous.find((kept) => kept.text === text) ?? { text, design: null, turn_index: null };
          }),
        };
      }
      mockScopingPlanVersion += 1;
      return json(scopingPlanOut(mockScopingPlanVersion));
    }
    if (isRecord(body)) {
      if (typeof body.question === "string") currentPlan = { ...currentPlan, question: body.question };
      if (typeof body.backend_scope === "string") {
        currentPlan = { ...currentPlan, backend_scope: body.backend_scope as typeof currentPlan.backend_scope };
      }
      if (typeof body.search_effort === "string") {
        currentPlan = { ...currentPlan, search_effort: body.search_effort as typeof currentPlan.search_effort };
      }
      if (typeof body.analysis_depth === "string") {
        currentPlan = { ...currentPlan, analysis_depth: body.analysis_depth as typeof currentPlan.analysis_depth };
      }
      if (typeof body.steering_mode === "string") {
        currentPlan = { ...currentPlan, steering_mode: body.steering_mode as typeof currentPlan.steering_mode };
      }
      if (Array.isArray(body.screening_criteria)) {
        currentPlan = { ...currentPlan, screening_criteria: body.screening_criteria as string[] };
      }
    }
    return json({ plan: currentPlan, version: 2, status: "approved" });
  }

  if (method === "GET" && path.endsWith(`/api/v1/tasks/${MOCK_TASK_ID}/groups`)) {
    return json(mockGroups);
  }

  // --- Runs: gate the event stream behind an actual start (the plan pane's
  // "Start the analysis" CTA), rather than a run appearing pre-started. ----
  if (method === "POST" && path.endsWith(`/api/v1/tasks/${MOCK_TASK_ID}/runs`)) {
    if (currentRun !== null && (currentRun.status === "running" || currentRun.status === "paused")) {
      return json({ error: { code: "run_active", message: "An analysis is already running." } }, 409);
    }
    const now = new Date().toISOString();
    currentRun = {
      capability_run_id: MOCK_RUN_ID,
      task_id: MOCK_TASK_ID,
      plan_id: MOCK_PLAN_ID,
      plan_version: 1,
      status: "running",
      started_at: now,
      ended_at: null,
      artefact_id: null,
    };
    mockTask.latest_run = latestRunOf(currentRun);
    mockTask.active_run = latestRunOf(currentRun);
    runStarted.resolve();
    return json(currentRun, 201);
  }
  if (method === "GET" && path.endsWith(`/api/v1/tasks/${MOCK_TASK_ID}/runs`)) {
    // Newest first, as the API lists them: the longlist walks (task 045)
    // were all opened after the baseline walk.
    const walks = [...mockLonglistWalks, ...(currentRun ? [currentRun] : [])];
    // `parentless` (A13): the task's own walks only, never an option search.
    const parentless = url.searchParams.get("parentless") === "true";
    return json(
      page(
        parentless
          ? walks.filter((walk) => walk.parent_capability_run_id == null && walk.purpose !== "targeted")
          : walks,
      ),
    );
  }

  if (method === "GET" && path.endsWith(`/api/v1/tasks/${MOCK_TASK_ID}/check-ins`)) {
    const status = url.searchParams.get("status");
    if (mockTask.capability === "options_scoping") {
      const decided = baselineGateDecision !== null;
      if (currentRun === null) return json(page([]));
      if (status === "pending" && decided) return json(page([]));
      return json(page([{
        ...mockBaselineGateCheckIn,
        created_at: baselineGateOpenedAt ?? mockBaselineGateCheckIn.created_at,
        status: decided ? "decided" : "pending",
      }]));
    }
    const rows = status === "pending" && checkInAnswered ? [] : [mockCheckIn];
    return json(page(rows));
  }

  // --- Identity + projects (task 033 phase 10a) -------------------------
  if (method === "GET" && path.endsWith("/api/v1/me")) return json(currentMe);
  if (method === "GET" && path.endsWith("/api/v1/projects")) return json(page(mockProjects));
  const projectDetailMatch = /\/api\/v1\/projects\/([^/]+)$/.exec(path);
  if (method === "GET" && projectDetailMatch) {
    const found = mockProjects.find((project) => project.project_id === projectDetailMatch[1]);
    return found !== undefined ? json(found) : json({ detail: "resource not found" }, 404);
  }
  // Task 033 phase 10b: the visibility control's cascade (i.4) — the mock's
  // one task is the project's only member, so "every member follows"
  // is a single assignment, but the shape (mutate both rows, return the
  // updated `task_count`) matches what the visibility-outcome copy reads.
  if (method === "PATCH" && projectDetailMatch) {
    const found = mockProjects.find((project) => project.project_id === projectDetailMatch[1]);
    if (found === undefined) return json({ detail: "resource not found" }, 404);
    const body = await requestBody(request, init);
    if (isRecord(body) && typeof body.name === "string") found.name = body.name;
    if (isRecord(body) && typeof body.description === "string") found.description = body.description;
    if (isRecord(body) && (body.visibility === "org" || body.visibility === "private")) {
      found.visibility = body.visibility;
      if (mockTask.project_ids?.includes(found.project_id) === true) {
        mockTask.visibility = body.visibility;
      }
    }
    return json(found);
  }

  // `project_id` narrows to one project's members, server-side — mirrors
  // the real list's filter (contract task 033 phase 10a: `ProjectDetailView`
  // no longer filters the global page client-side).
  // Task 058, round 10: the list pages like the server (50 a page by
  // default, newest first, `has_more`), honours `status` and `scope=mine`,
  // and holds more than one page so "Show more" is walkable.
  if (method === "GET" && path.endsWith("/api/v1/tasks")) {
    const projectId = url.searchParams.get("project_id");
    const status = url.searchParams.get("status") ?? "active";
    const scope = url.searchParams.get("scope") ?? "all";
    const rows = [mockTask, ...mockOtherTasks]
      .filter((task) => projectId === null || task.project_ids?.includes(projectId) === true)
      .filter((task) => status === "all" || task.status === status)
      .filter((task) => scope !== "mine" || task.is_owner)
      .sort((left, right) => right.updated_at.localeCompare(left.updated_at));
    return json(pageOf(rows, url));
  }
  if (method === "GET" && path.endsWith(`/api/v1/tasks/${MOCK_TASK_ID}`)) return json(mockTask);
  const otherTaskMatch = path.match(/\/api\/v1\/tasks\/([^/]+)$/);
  const otherTask =
    method === "GET" && otherTaskMatch !== null
      ? mockOtherTasks.find((task) => task.task_id === otherTaskMatch[1])
      : undefined;
  if (otherTask !== undefined) return json(otherTask);
  if (method === "GET" && path.endsWith(`/api/v1/tasks/${MOCK_TASK_ID}/funnel`)) return json(mockFunnel);
  if (method === "GET" && path.endsWith(`/api/v1/tasks/${MOCK_TASK_ID}/landscape`)) return json(mockLandscape);
  if (method === "GET" && path.endsWith(`/api/v1/tasks/${MOCK_TASK_ID}/evidence`)) {
    const statuses = url.searchParams.getAll("status");
    const cited = url.searchParams.get("cited");
    const theme = url.searchParams.get("theme");
    const origin = url.searchParams.get("origin");
    const evidenceType = url.searchParams.get("evidence_type");
    const strength = url.searchParams.get("strength");
    const country = url.searchParams.get("country");
    const sort = url.searchParams.get("sort") as EvidenceSortField | null;
    const order = url.searchParams.get("order") as "asc" | "desc" | null;
    let rows = mockEvidence.filter((item) => {
      const included = ["relevant", "not_selected", "selected", "read_in_full", "findings_extracted", "cited", "unavailable"];
      const statusMatches = statuses.length === 0 || statuses.some((status) => status === item.status || (status === "Included" && included.includes(item.status)));
      const themeMatches = theme === null || (mockEvidenceThemeIds[item.source_id] ?? []).includes(theme);
      const yearFrom = url.searchParams.get("year_from");
      const yearTo = url.searchParams.get("year_to");
      const yearMatches =
        (yearFrom === null && yearTo === null)
        || (item.year !== null && item.year !== undefined
          && (yearFrom === null || item.year >= Number(yearFrom))
          && (yearTo === null || item.year <= Number(yearTo)));
      return statusMatches && (cited !== "true" || item.cited) && themeMatches
        && (origin === null || item.origin === origin)
        && (evidenceType === null || item.evidence_type === evidenceType)
        && (strength === null || item.appraisal_tier === strength)
        && (country === null || mockCountryMatches(item.country ?? null, country))
        && yearMatches;
    });
    // Server-side-equivalent sort (collection-true, matches
    // `repository._compare_evidence_sort`): `order` defaults to the
    // column's own natural direction (desc for year, asc otherwise) and
    // nulls always sort last regardless of direction.
    if (sort !== null) {
      const direction = order ?? (sort === "year" || sort === "relevance" ? "desc" : "asc");
      rows = [...rows].sort((left, right) => compareMockEvidenceSort(left, right, sort, direction));
    }
    return json(page(rows));
  }
  // Task 046, amendment 3 (R67): the dossier's records on a scoping task,
  // derived from the option cards' documents (one per option holding it).
  const sourceRecordsMatch = path.match(new RegExp(`/api/v1/tasks/${MOCK_TASK_ID}/sources/([^/]+)/records$`));
  if (method === "GET" && sourceRecordsMatch) {
    const sourceId = sourceRecordsMatch[1];
    const optionId = url.searchParams.get("option_id");
    const records = Object.values(mockLonglistOptionCards)
      .filter((card) => optionId === null || card.option_id === optionId)
      .flatMap((card) =>
        (card.documents ?? [])
          .filter((document) => document.task_source_snapshot_id === sourceId)
          .map((document) => ({
            option_id: card.option_id,
            option_name: card.name,
            record_id: `${card.option_id}-${sourceId}`,
            intervention: card.name,
            setting: card.profile?.settings?.[0] ?? null,
            unit: card.documents?.[0]?.tried_on_kind ?? null,
            outcome: card.outcomes_served?.[0] ?? null,
            study_geography: document.place ?? null,
            role: document.role,
          })),
      );
    return json({ task_source_snapshot_id: sourceId, records });
  }
  if (method === "GET" && path.includes(`/api/v1/tasks/${MOCK_TASK_ID}/sources/`)) {
    const sourceId = path.split("/").at(-1) ?? "";
    const source = mockSourceDossiers[sourceId];
    return source ? json(source) : json({ detail: "resource not found" }, 404);
  }
  if (method === "GET" && path.includes(`/api/v1/tasks/${MOCK_TASK_ID}/chunks/`) && path.endsWith("/context")) {
    // Chat citations carry a durable chunk id (never the artefact citation
    // table's id) — its own read path, sharing the same clamped-context
    // fixture text as the artefact citation above since both cite the same
    // breakfast-provision passage.
    const context = "Recruitment spanned two academic years across ten primary schools. Breakfast participation increased when provision was universal, particularly where uptake carried no separate sign-up. Effects attenuated modestly by the second term but remained significant.";
    return json({
      clamped: false,
      context,
      previous: "Recruitment spanned two academic years across ten primary schools.",
      next: "Effects attenuated modestly by the second term but remained significant.",
      span_start: 0,
      span_end: context.length,
      year: 2022,
      venue: "BMJ Open",
      authorships: mockAuthorships,
    });
  }
  if (method === "GET" && path.includes(`/api/v1/tasks/${MOCK_TASK_ID}/citations/`) && path.endsWith("/context")) {
    // One clamped chunk-context fixture (strand 5): its text literally
    // contains the citation quote used in `mockArtefact`, so the exact-match
    // highlight rung renders rather than the honest degrade.
    const context = "Recruitment spanned two academic years across ten primary schools. Breakfast participation increased when provision was universal, particularly where uptake carried no separate sign-up. Effects attenuated modestly by the second term but remained significant.";
    return json({
      clamped: false,
      context,
      previous: "Recruitment spanned two academic years across ten primary schools.",
      next: "Effects attenuated modestly by the second term but remained significant.",
      span_start: 0,
      span_end: context.length,
      year: 2022,
      venue: "BMJ Open",
      authorships: mockAuthorships,
    });
  }
  if (method === "GET" && path.endsWith(`/api/v1/tasks/${MOCK_TASK_ID}/findings`)) {
    const sourceId = url.searchParams.get("source_id");
    const profile = url.searchParams.get("profile");
    const facet = url.searchParams.get("facet");
    const group = url.searchParams.get("group");
    const rows = mockFindings.filter((finding) => {
      if (sourceId !== null && finding.source_id !== sourceId) return false;
      if (profile !== null && finding.profile !== profile) return false;
      if (facet !== null && group !== null && finding.groups?.[facet] !== group) return false;
      return true;
    });
    return json(page(rows));
  }
  if (method === "GET" && path.endsWith(`/api/v1/tasks/${MOCK_TASK_ID}/decisions`)) return json(pageOf(mockDecisions, url));
  // Task 044 (deliverable 9): a scoping task's Result is its baseline, not an
  // Evidence search report.
  if (method === "GET" && path.endsWith(`/api/v1/tasks/${MOCK_TASK_ID}/artefact`)) {
    return json(mockTask.capability === "options_scoping" ? mockBaselineArtefact : mockArtefact);
  }
  if (method === "GET" && path.endsWith(`/api/v1/tasks/${MOCK_TASK_ID}/coverage`)) return json(mockCoverage);

  // --- Conversations + chat turns (task 029 phase G3 mock) ---------------
  if (method === "GET" && path.endsWith(`/api/v1/tasks/${MOCK_TASK_ID}/conversations`)) {
    const kind = url.searchParams.get("kind");
    const status = url.searchParams.get("status");
    const rows = chatConversations
      .filter((conversation) => (kind === null || conversation.kind === kind) && (status === null || conversation.status === status))
      .map(conversationListItem)
      .sort((a, b) => b.created_at.localeCompare(a.created_at));
    return json(page(rows));
  }
  if (method === "POST" && path.endsWith(`/api/v1/tasks/${MOCK_TASK_ID}/conversations`)) {
    const body = await requestBody(request, init);
    const entryArtefactId = isRecord(body) && typeof body.entry_artefact_id === "string" ? body.entry_artefact_id : null;
    const now = new Date().toISOString();
    const conversation: ConversationOut = {
      id: crypto.randomUUID(),
      task_id: MOCK_TASK_ID,
      kind: "chat",
      title: "New chat",
      status: "active",
      entry_artefact_id: entryArtefactId,
      created_at: now,
      closed_at: null,
      archived_at: null,
    };
    chatConversations.push(conversation);
    return json(conversation, 201);
  }

  const chatTurnCancelMatch = /\/api\/v1\/conversations\/([^/]+)\/turns\/([^/]+)\/cancel$/.exec(path);
  if (method === "POST" && chatTurnCancelMatch) {
    const [, conversationId, turnId] = chatTurnCancelMatch;
    const turn = (chatTurnsByConversation.get(conversationId) ?? []).find((candidate) => candidate.id === turnId);
    return json({ status: turn?.status ?? "cancelled" });
  }
  const chatTurnsMatch = /\/api\/v1\/conversations\/([^/]+)\/turns$/.exec(path);
  if (chatTurnsMatch) {
    const conversationId = chatTurnsMatch[1];
    if (method === "GET") return json(page(readChatTurns(conversationId)));
    if (method === "POST") {
      const body = await requestBody(request, init);
      const message = isRecord(body) && typeof body.message === "string" ? body.message : "";
      const clientTurnId = isRecord(body) && typeof body.client_turn_id === "string" ? body.client_turn_id : crypto.randomUUID();
      return new Response(createMockChatTurnStream(conversationId, clientTurnId, message), {
        headers: { "Content-Type": "application/x-ndjson" },
      });
    }
  }
  const chatConversationArchiveMatch = /\/api\/v1\/conversations\/([^/]+)\/archive$/.exec(path);
  if (method === "POST" && chatConversationArchiveMatch) {
    const conversation = chatConversations.find((candidate) => candidate.id === chatConversationArchiveMatch[1]);
    if (conversation === undefined) return json({ detail: "resource not found" }, 404);
    conversation.status = "archived";
    conversation.archived_at = new Date().toISOString();
    return json(conversation);
  }
  const chatConversationUnarchiveMatch = /\/api\/v1\/conversations\/([^/]+)\/unarchive$/.exec(path);
  if (method === "POST" && chatConversationUnarchiveMatch) {
    const conversation = chatConversations.find((candidate) => candidate.id === chatConversationUnarchiveMatch[1]);
    if (conversation === undefined) return json({ detail: "resource not found" }, 404);
    conversation.status = "active";
    conversation.archived_at = null;
    return json(conversation);
  }
  const chatConversationMatch = /\/api\/v1\/conversations\/([^/]+)$/.exec(path);
  if (chatConversationMatch) {
    const conversation = chatConversations.find((candidate) => candidate.id === chatConversationMatch[1]);
    if (conversation === undefined) return json({ detail: "resource not found" }, 404);
    if (method === "GET") return json(conversation);
    if (method === "PATCH") {
      const body = await requestBody(request, init);
      if (isRecord(body)) {
        if (typeof body.title === "string") conversation.title = body.title;
        if ("entry_artefact_id" in body) conversation.entry_artefact_id = (body.entry_artefact_id as string | null) ?? null;
      }
      return json(conversation);
    }
  }

  // task 045 (6.2) — the longlist's three surfaces: list view, reduced
  // grid and option card. The two GETs and the three POSTs `pnpm e2e`
  // drives them through; the POSTs mutate `mockLonglistOptionCards` in
  // place (the same fixture `GET /longlist`'s summaries project from) so a
  // refetch after a mutation shows the flipped state.
  if (method === "GET" && path.endsWith(`/api/v1/tasks/${MOCK_TASK_ID}/longlist`)) {
    // The longlist does not exist until the walk's longlist stage completes.
    if (mockLonglistBuilding) return json({ detail: "resource not found" }, 404);
    // While a walk runs the read grows stage by stage over the options read's rows.
    if (mockLonglistWalkStage !== null) return json(mockWalkLonglist(mockOptionRows, mockLonglistWalkStage));
    if (mockFinishedWalk !== null) return json(mockFinishedWalkLonglist());
    return json(mockLonglist());
  }
  // Task 058, N22: the options read, served from the end of the suggest stage.
  if (method === "GET" && path.endsWith(`/api/v1/tasks/${MOCK_TASK_ID}/options`)) {
    return json({ options: mockOptionRows });
  }
  // task 055 — the shortlist: the two option verbs and Suggest more, over
  // the same in-memory cards. The 409s are the API's: `run_active` while a
  // walk runs, `not_included` for an excluded option, `nothing_to_propose`
  // when every included option holds a place or was set aside.
  const shortlistVerbMatch = new RegExp(`^/api/v1/tasks/${MOCK_TASK_ID}/options/([^/]+)/(shortlist|unshortlist)$`).exec(path);
  if (method === "POST" && shortlistVerbMatch) {
    const option = mockLonglistOptionCards[shortlistVerbMatch[1]];
    if (option === undefined) return json({ detail: "resource not found" }, 404);
    if (mockTask.active_run != null) return mockConflict("run_active", "A walk is already running.");
    if (shortlistVerbMatch[2] === "shortlist") {
      if (option.state !== "included") return mockConflict("not_included", "Only an included option can be shortlisted.");
      option.shortlist = { state: "added_by_you", reason: null };
    } else if (option.shortlist?.state === "proposed") {
      option.shortlist = { state: "set_aside", reason: null };
    } else if (option.shortlist?.state === "added_by_you") {
      option.shortlist = null;
    }
    return json(option);
  }
  if (method === "POST" && path.endsWith(`/api/v1/tasks/${MOCK_TASK_ID}/shortlist/suggest`)) {
    if (mockTask.active_run != null) return mockConflict("run_active", "A walk is already running.");
    // The proposal takes a moment on the server; a short wait lets the
    // button's pending state show (task 058, round 10).
    await pace(800);
    const current = currentMockOptionIds()
      .map((optionId) => mockLonglistOptionCards[optionId])
      .filter((option) => option !== undefined);
    const open = current.filter(
      (option) => option.state === "included" && option.shortlist == null,
    );
    if (open.length === 0 && !mockShortlistState.stale) {
      return mockConflict("nothing_to_propose", "Nothing is left to propose.");
    }
    const held = current.filter(
      (option) => option.shortlist?.state === "proposed" || option.shortlist?.state === "added_by_you",
    ).length;
    // Up to the target; past it, Suggest more still adds one place.
    for (const option of open.slice(0, Math.max(1, MOCK_SHORTLIST_PLACES_TARGET - held))) {
      option.shortlist = { state: "proposed", reason: "Mock reason: names a fact on the card." };
    }
    mockShortlistState.note = "Mock note: nothing here tackles the wider labour market.";
    mockShortlistState.stale = false;
    const startedAt = new Date().toISOString();
    const walk: RunOut = {
      capability_run_id: crypto.randomUUID(),
      task_id: MOCK_TASK_ID,
      plan_id: MOCK_PLAN_ID,
      plan_version: mockScopingPlanVersion,
      status: "succeeded",
      started_at: startedAt,
      ended_at: startedAt,
      artefact_id: null,
      parent_capability_run_id: null,
      purpose: "shortlist",
    };
    mockLonglistWalks = [walk, ...mockLonglistWalks];
    mockTask.latest_run = latestRunOf(walk);
    return json(latestRunOf(walk), 202);
  }
  const optionVerbMatch = new RegExp(`^/api/v1/tasks/${MOCK_TASK_ID}/options/([^/]+)/(exclude|include)$`).exec(path);
  if (method === "POST" && optionVerbMatch) {
    const option = mockLonglistOptionCards[optionVerbMatch[1]];
    if (option === undefined) return json({ detail: "resource not found" }, 404);
    if (optionVerbMatch[2] === "include") {
      option.state = "included";
      option.exclusion = null;
      return json(option);
    }
    const body = await requestBody(request, init);
    const reason = isRecord(body) && typeof body.reason === "string" ? body.reason : "";
    option.state = "excluded";
    option.exclusion = { by: "user", constraint: "your decision", reason };
    // An excluded option loses its place; a set-aside mark stays.
    if (option.shortlist?.state === "proposed" || option.shortlist?.state === "added_by_you") option.shortlist = null;
    return json(option);
  }
  if (method === "POST" && path.endsWith(`/api/v1/tasks/${MOCK_TASK_ID}/options`)) {
    const body = await requestBody(request, init);
    const text = isRecord(body) && typeof body.text === "string" ? body.text : "";
    const option = buildMockAddedOption(text);
    mockLonglistOptionCards[option.option_id] = option;
    mockLonglistExtraOptionIds.push(option.option_id);
    return json(
      {
        option,
        opened_run: {
          capability_run_id: crypto.randomUUID(),
          started_at: new Date().toISOString(),
          ended_at: null,
          status: "running",
        },
      },
      201,
    );
  }
  const optionCardMatch = new RegExp(`^/api/v1/tasks/${MOCK_TASK_ID}/options/([^/]+)$`).exec(path);
  if (method === "GET" && optionCardMatch) {
    const option = mockLonglistOptionCards[optionCardMatch[1]];
    if (option === undefined) return json({ detail: "resource not found" }, 404);
    return json(option);
  }

  return json({ detail: "Mock endpoint not found" }, 404);
}

/** Project one conversation into its library row shape, deriving the
 *  preview from its own latest chat turn — mirrors the real read model's
 *  cross-kind preview join closely enough for the mock library surface. */
function conversationListItem(conversation: ConversationOut): ConversationListItemOut {
  const latestChat = (chatTurnsByConversation.get(conversation.id) ?? []).at(-1);
  const latestTaskAgent = conversation.kind === "task_agent" ? taskAgentTurns.at(-1) : undefined;
  const latestTurnPreview =
    latestChat !== undefined
      ? {
          user_message: latestChat.user_message,
          reply_snippet: latestChat.status === "completed" ? latestChat.answer : null,
          at: latestChat.completed_at,
        }
      : latestTaskAgent !== undefined
        ? {
            user_message: latestTaskAgent.user_message,
            reply_snippet: latestTaskAgent.status === "completed" ? latestTaskAgent.reply : null,
            at: latestTaskAgent.completed_at,
          }
        : null;
  return {
    id: conversation.id,
    task_id: conversation.task_id,
    kind: conversation.kind,
    title: conversation.title,
    status: conversation.status,
    entry_artefact_id: conversation.entry_artefact_id,
    created_at: conversation.created_at,
    closed_at: conversation.closed_at,
    archived_at: conversation.archived_at,
    latest_turn_preview: latestTurnPreview,
  };
}

/** Advance a conversation's pending enrichment on its second read (task 029
 *  phase G3 fixture): the first read is the `completed` event's own
 *  `invalidateTurns()` refetch — still honestly "unchecked" — and the
 *  second is the client's async-judge poll, which this flips to `enriched`
 *  with a tier verdict on the one scripted citation. Mutates the stored
 *  turns in place, matching this module's other scripted-state handlers. */
function readChatTurns(conversationId: string): ChatTurnOut[] {
  const turns = chatTurnsByConversation.get(conversationId) ?? [];
  for (const turn of turns) {
    if (turn.enrichment === null || turn.enrichment === undefined || turn.enrichment.status !== "pending") continue;
    const reads = (chatTurnEnrichmentReads.get(turn.id) ?? 0) + 1;
    chatTurnEnrichmentReads.set(turn.id, reads);
    if (reads < 2) continue;
    turn.enrichment = { status: "enriched" };
    turn.citations = (turn.citations ?? []).map((citation, index) =>
      index === 0 ? { ...citation, state: "verdict:tier_2" } : citation);
  }
  return turns;
}

/** Split text into word groups of 2 to 6 words, keeping every space, so the
 *  groups joined are exactly the text. */
function chunkWords(text: string): string[] {
  const words = text.match(/\S+\s*/g) ?? [];
  const sizes = [3, 2, 5, 4, 6, 2];
  const chunks: string[] = [];
  let at = 0;
  for (let step = 0; at < words.length; step += 1) {
    const size = sizes[step % sizes.length];
    chunks.push(words.slice(at, at + size).join(""));
    at += size;
  }
  return chunks;
}

function ndjsonResponse(stream: ReadableStream<Uint8Array>): Response {
  return new Response(stream, { headers: { "Content-Type": "application/x-ndjson" } });
}

/**
 * One planner turn as NDJSON (task 058, N9): one `progress` line ("Drafting
 * the plan"), the reply as `delta` pieces of 2 to 6 words every 80 ms, then
 * one `completed` with the whole turn. `finish` runs once the reply has
 * streamed: it stores the turn and returns the `TaskAgentTurnOut` to send.
 */
function createMockTaskAgentStream(reply: string, finish: () => TaskAgentTurnOut): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    async start(controller) {
      const emit = (event: unknown) => controller.enqueue(encoder.encode(`${JSON.stringify(event)}\n`));
      emit({ type: "progress", label: STEP_DRAFTING_THE_PLAN });
      await pace(200);
      for (const text of chunkWords(reply)) {
        emit({ type: "delta", text });
        await pace(80);
      }
      emit({ type: "completed", turn: finish() });
      controller.close();
    },
  });
}

/** Reserve and stream one chat turn's scripted NDJSON lifecycle: one
 *  `progress` label, two `delta` chunks that concatenate into the answer,
 *  then a `completed` terminal event carrying one citation with its
 *  enrichment left honestly "pending" (task 029 phase G3 fixture). Each
 *  emit is separated by a brief real delay — matching this module's own
 *  `sleep(500)` before the artefact stream's section fill — so the
 *  progress/streaming states are reliably Playwright-observable rather than
 *  flashing and settling within one microtask tick. */
function createMockChatTurnStream(conversationId: string, clientTurnId: string, message: string): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    async start(controller) {
      const emit = (event: unknown) => controller.enqueue(encoder.encode(`${JSON.stringify(event)}\n`));
      emit({ type: "progress", label: MOCK_CHAT_PROGRESS_LABEL });
      await sleep(200);
      for (const part of MOCK_CHAT_ANSWER_DELTAS) {
        emit({ type: "delta", text: part });
        await sleep(50);
      }
      const now = new Date().toISOString();
      const existing = chatTurnsByConversation.get(conversationId) ?? [];
      const answer = MOCK_CHAT_ANSWER_DELTAS.join("");
      // Server-shape faithful (chat_floor.apply_citation_floor): the floor
      // computes a claim's span as `prose.find(text)`, never a hand-picked
      // offset — mirrored here so this fixture can't silently drift from
      // MOCK_CHAT_ANSWER_DELTAS above.
      const claimStart = answer.indexOf(MOCK_CHAT_CLAIM_TEXT);
      const turn: ChatTurnOut = {
        id: crypto.randomUUID(),
        conversation_id: conversationId,
        client_turn_id: clientTurnId,
        turn_index: existing.length,
        user_message: message,
        answer,
        status: "completed",
        created_at: now,
        completed_at: now,
        claims:
          claimStart >= 0
            ? [
                {
                  claim_id: MOCK_CHAT_CLAIM_ID,
                  text: MOCK_CHAT_CLAIM_TEXT,
                  span: [claimStart, claimStart + MOCK_CHAT_CLAIM_TEXT.length],
                  citation_ns: [1],
                },
              ]
            : [],
        // appraisal_label/evidence_type (030 fold): server-shape faithful —
        // the same "moderate" label + `mockEvidence[2].evidence_type` the
        // artefact fixture's own citation onto this source carries (see
        // `mockArtefact`'s claims[0].citations[0] in fixtures.ts).
        citations: [{ id: MOCK_CHAT_CITATION_CHUNK_ID, n: 1, quote: MOCK_CHAT_CITATION_QUOTE, source_title: mockEvidence[2].title, appraisal_label: "moderate", evidence_type: mockEvidence[2].evidence_type }],
        enrichment: { status: "pending" },
        warning_not_evidence_checked: false,
        handoff: null,
        stopped_before_evidence_check: false,
      };
      chatTurnsByConversation.set(conversationId, [...existing, turn]);
      emit({ type: "completed", turn });
      controller.close();
    },
  });
}

/** Install the client-level fetch interceptor only after VITE_MOCK is selected. */
export function installMockApi() {
  const realFetch = globalThis.fetch.bind(globalThis);
  const mockAuth: AuthApi = {
    getAccessToken: async () => "mock-access-token",
    signIn: () => undefined,
    signOut: () => undefined,
    onUnauthenticated: () => undefined,
    user: { sub: "mock-policy-lead" },
    status: "authenticated",
  };
  (globalThis as typeof globalThis & { __policyAtlasMockAuth?: AuthApi }).__policyAtlasMockAuth = mockAuth;
  globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(input instanceof Request ? input.url : input.toString(), globalThis.location?.origin ?? "http://localhost");
    return url.pathname.includes("/api/v1/") ? mockFetch(input, init) : realFetch(input, init);
  }) as typeof fetch;
}

/**
 * The scripted SSE narrative (task 025 I.1; extended 027 F.2 with the
 * `artefact.*` events, strand 13). Held open behind `runStarted` so the
 * stream carries no frames until a real `POST .../runs` succeeds — the plan
 * pane's "Start the analysis" CTA is a genuine gate, not cosmetic.
 */
function createMockEventStream(scenario: MockScenario): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let sequence = 0;
  const nextSequence = () => {
    sequence += 1;
    return sequence;
  };

  return new ReadableStream<Uint8Array>({
    async start(controller) {
      await runStarted.promise;
      const emit = (frame: SseFrame) => controller.enqueue(encoder.encode(toSse(frame)));

      if (mockTask.capability === "options_scoping") {
        await scopingBaselineWalk(emit, nextSequence);
        // Task 045 (6.3): the stream stays open for the longlist walks the
        // gate and the plan document's confirm open.
        await mockLonglistWalkLoop(emit, nextSequence);
        return;
      }

      const replay = scenario === "reload-mid-section";
      // A reconnect replays the durable frames at once; a live walk paces them.
      const wait = (ms: number) => (replay ? Promise.resolve() : pace(ms));
      // Ticks are ephemeral, so a replay carries none.
      const emitTick = (frame: SseFrame) => {
        if (!replay) emit(frame);
      };

      emit(runStatus("running", nextSequence()));
      // The approved plan's steps give the card its rows to come (task 058, N5).
      emit({ type: "plan.updated", plan: currentPlan, scoping: null, version: 1, occurred_at: frameTime(), sequence: nextSequence() });
      // The search (round 9): the queries are written, then each goes out
      // and comes back with its count, the line naming the query out; then
      // one citations pass, described in words.
      emit(stageStarted("acquire", nextSequence()));
      setLiveStage("acquire");
      emitTick(tick("acquire", "Writing search queries"));
      // The hub repeats the line while the query-writing call is open.
      emitTick(tick("acquire", "Writing search queries", { heartbeat: true }));
      await wait(MOCK_TICK_MS);
      let found = 0;
      for (const entry of mockSearchQueries) {
        const pass = entry.kind === "citations" || entry.kind === "lookup";
        const query = (results: number | null): SseFrame => ({
          type: "search.query",
          ephemeral: true,
          backend: entry.backend,
          query: entry.query,
          kind: entry.kind,
          results,
          occurred_at: frameTime(),
        });
        emitTick(query(null));
        emitTick(
          tick("acquire", pass ? `following citations · ${withCommas(found)} found` : `searching · ${withCommas(found)} found · ${entry.query}`, {
            done: found,
            unit: "documents",
          }),
        );
        await wait(MOCK_TICK_MS);
        found = entry.found;
        emitTick(query(entry.results));
        emitTick(tick("acquire", `searching · ${withCommas(found)} found`, { done: found, unit: "documents" }));
      }
      emit(stageCompleted("acquire", { acquired: found }, nextSequence()));
      await walkStage(emit, emitTick, nextSequence, "screen", wait, [
        { activity: "screening 87 abstracts · 104 relevant" },
        { activity: "screening 61 abstracts · 107 relevant" },
        { activity: "screening 23 abstracts · 112 relevant" },
      ], { relevant: 118, screened_out: 317 });
      // The run genuinely parks at this boundary (028 pause salience: paused
      // must read distinct from executing on every tab) — an explicit
      // `run.status` frame, not just the pending check-in itself.
      emit(runStatus("paused", nextSequence()));
      emit({ type: "checkin.pending", check_in: mockCheckIn, occurred_at: FRAME_TIME, sequence: nextSequence() });

      if (scenario === "paused-strip") {
        // Holds at the check-in for good: the run status bar's paused state.
        await new Promise<void>(() => {});
        return;
      }
      if (!replay) await checkInAnswer.promise;

      emit(runStatus("running", nextSequence()));
      emit({
        type: "checkin.resolved",
        check_in_id: MOCK_CHECK_IN_ID,
        response: { kind: "option", option_id: "continue", params: null },
        decided_by: "user",
        occurred_at: FRAME_TIME,
        sequence: nextSequence(),
      });

      await walkStage(emit, emitTick, nextSequence, "classify", wait, [
        { activity: "40 of 118 classified", done: 40, total: 118, unit: "documents" },
        { activity: "80 of 118 classified", done: 80, total: 118, unit: "documents" },
        { activity: "118 of 118 classified", done: 118, total: 118, unit: "documents" },
      ], { classified: 118 });
      await walkStage(emit, emitTick, nextSequence, "appraise", wait, [
        { activity: "Classifying" },
      ], { quality_checked: 118 });
      // The themes show once found, while the sources are assigned (round 9).
      emit(stageStarted("characterise", nextSequence()));
      setLiveStage("characterise");
      emitTick(tick("characterise", "Finding themes"));
      emitTick(tick("characterise", "Finding themes", { heartbeat: true }));
      await wait(MOCK_TICK_MS);
      emitTick({ type: "characterise.themes", ephemeral: true, themes: mockLiveThemes, occurred_at: frameTime() });
      for (const done of [1, 2, 3]) {
        emitTick(tick("characterise", `Assigning themes · batch ${done} of 3`, { done, total: 3, unit: "batches" }));
        await wait(MOCK_TICK_MS);
      }
      emit(stageCompleted("characterise", { theme_count: mockLiveThemes.length }, nextSequence()));
      emit(stageStarted("synthesise", nextSequence()));
      setLiveStage("synthesise");

      // Live artefact streaming (strand 13): skeleton, then each section
      // started -> completed, whole-section grain for the first, streamed for
      // the second.
      emit({ type: "artefact.skeleton", sections: mockArtefactSkeleton, occurred_at: FRAME_TIME, sequence: nextSequence() });
      emit({ type: "artefact.section_started", index: 0, occurred_at: FRAME_TIME, sequence: nextSequence() });
      if (!replay) {
        // The key findings stream as a body section does: deltas, then the
        // writer's citation as it closes (round 8).
        emitTick(tick("synthesise", "Writing the key findings", { section: "Key findings" }));
        for (const chunk of chunkWords(mockArtefactSectionProse[0])) {
          await pace(100);
          emit({ type: "artefact.section_delta", ephemeral: true, index: 0, mode: "append", text: chunk, occurred_at: frameTime() });
        }
        emit({ type: "artefact.section_claim", ephemeral: true, index: 0, ...mockKeyFindingsClaim, occurred_at: frameTime() });
        emitTick(tick("synthesise", "Checking claims", { section: "Key findings" }));
      }
      await wait(MOCK_TICK_MS);
      emit({
        type: "artefact.section_completed",
        index: 0,
        title: mockArtefactSkeleton[0].title,
        prose: mockArtefactSectionProse[0],
        citations: mockSectionCitations[0],
        occurred_at: FRAME_TIME,
        sequence: nextSequence(),
      });
      // The streamed section is the body section (display index 1).
      const streamed = MOCK_STREAMED_SECTION_INDEX;
      emit({ type: "artefact.section_started", index: streamed, occurred_at: FRAME_TIME, sequence: nextSequence() });
      const sectionOne = sectionLine(streamed);
      emitTick(tick("synthesise", "Looking for: evidence on subsidy uptake among low-income households", { section: sectionOne }));

      if (scenario === "paused") {
        // A demo/screenshot fixture: holds "writing" indefinitely rather
        // than a transient race a test would have to catch mid-flight.
        await new Promise<void>(() => {});
        return;
      }

      // Held briefly so the "writing" state is reliably observable before
      // the section fills — the demo journey's skeleton -> writing -> filled
      // check.
      await pace(500);

      if (scenario === "failed-partial") {
        emit({
          type: "artefact.section_completed",
          index: streamed,
          title: mockArtefactSkeleton[streamed].title,
          prose: mockArtefactSectionRepairedProse[1],
          citations: mockSectionCitations[streamed],
          occurred_at: FRAME_TIME,
          sequence: nextSequence(),
        });
        emit(stageFailed("synthesise", "The write-up run hit an unrecoverable error.", nextSequence()));
        finishRun("failed");
        emit(runStatus("failed", nextSequence()));
        controller.close();
        return;
      }

      // The writer's second section: its drafted prose streams in 2 to 6 word
      // appends; a reconnect starts with the first half in one `replace`.
      const draft = mockArtefactSectionProse[1];
      const delta = (text: string, mode: "append" | "replace"): SseFrame => ({
        type: "artefact.section_delta",
        ephemeral: true,
        index: streamed,
        mode,
        text,
        occurred_at: frameTime(),
      });
      // Each read names the sources it returned; the set only grows
      // (task 058, evidence shown live).
      const sources = (set: { source_id: string; title: string }[]): SseFrame => ({
        type: "artefact.section_sources",
        ephemeral: true,
        index: streamed,
        sources: set,
        occurred_at: frameTime(),
      });
      let rest = draft;
      if (replay) {
        const firstHalf = draft.slice(0, draft.lastIndexOf(" ", Math.floor(draft.length / 2)) + 1);
        emit(delta(firstHalf, "replace"));
        emit(sources(mockSectionOneSources[1]));
        rest = draft.slice(firstHalf.length);
      } else {
        emit(sources(mockSectionOneSources[0]));
        emitTick(tick("synthesise", "Reading findings", { section: sectionOne }));
        await pace(MOCK_TICK_MS);
        emit(sources(mockSectionOneSources[1]));
        emitTick(tick("synthesise", "Writing", { section: sectionOne }));
      }
      for (const chunk of chunkWords(rest)) {
        await pace(100);
        emit(delta(chunk, "append"));
      }
      // The writer's own citations close after the whole prose, in a wave.
      for (const claim of mockSectionOneClaims) {
        await pace(100);
        emit({ type: "artefact.section_claim", ephemeral: true, index: streamed, ...claim, occurred_at: frameTime() });
      }
      emitTick(tick("synthesise", "Checking claims", { section: sectionOne }));
      await pace(MOCK_TICK_MS);
      emit({
        type: "artefact.section_revising",
        ephemeral: true,
        index: streamed,
        spans: [mockSectionOneRevisingSpan],
        occurred_at: frameTime(),
      });
      emitTick(tick("synthesise", "Revising 1 claim", { section: sectionOne }));
      await pace(1500);
      emit({
        type: "artefact.section_completed",
        index: streamed,
        title: mockArtefactSkeleton[streamed].title,
        prose: mockArtefactSectionRepairedProse[1],
        citations: mockSectionCitations[streamed],
        occurred_at: FRAME_TIME,
        sequence: nextSequence(),
      });
      // The case studies come last: the slot starts, each card streams in as
      // it closes, then the checked cards land (task 058, round 7).
      emit({ type: "artefact.section_started", index: MOCK_CASE_STUDIES_INDEX, occurred_at: FRAME_TIME, sequence: nextSequence() });
      emitTick(tick("synthesise", "Writing the case studies", { section: "Case studies" }));
      for (const card of mockCaseStudyCards) {
        await pace(400);
        emit({
          type: "artefact.section_card",
          ephemeral: true,
          index: MOCK_CASE_STUDIES_INDEX,
          title: card.title,
          prose: card.prose,
          occurred_at: frameTime(),
        });
      }
      await pace(MOCK_TICK_MS);
      emit({
        type: "artefact.section_completed",
        index: MOCK_CASE_STUDIES_INDEX,
        title: mockArtefactSkeleton[MOCK_CASE_STUDIES_INDEX].title,
        prose: mockCaseStudiesProse,
        citations: mockSectionCitations[MOCK_CASE_STUDIES_INDEX],
        occurred_at: FRAME_TIME,
        sequence: nextSequence(),
      });
      // The source notes, each named on the line and sent as it is written
      // (round 8).
      for (const note of mockSourceNotes) {
        emitTick(tick("synthesise", `Writing a source note · ${note.short}`));
        await pace(400);
        emit({
          type: "artefact.source_note",
          ephemeral: true,
          source_id: note.sourceId,
          title: note.title,
          note: note.note,
          occurred_at: frameTime(),
        });
      }
      // The introduction streams into its own slot (round 8).
      emit({ type: "artefact.section_started", index: MOCK_INTRO_INDEX, occurred_at: FRAME_TIME, sequence: nextSequence() });
      emitTick(tick("synthesise", "Writing the introduction", { section: "Introduction" }));
      for (const chunk of chunkWords(MOCK_FULL_REPORT_INTRO)) {
        await pace(100);
        emit({ type: "artefact.section_delta", ephemeral: true, index: MOCK_INTRO_INDEX, mode: "append", text: chunk, occurred_at: frameTime() });
      }
      emit({
        type: "artefact.section_completed",
        index: MOCK_INTRO_INDEX,
        title: mockArtefactSkeleton[MOCK_INTRO_INDEX].title,
        prose: MOCK_FULL_REPORT_INTRO,
        citations: [],
        occurred_at: FRAME_TIME,
        sequence: nextSequence(),
      });
      emit(stageCompleted("synthesise", { section_count: 2 }, nextSequence()));
      setRunArtefact(mockArtefact.artefact_id);
      finishRun("succeeded");
      emit(runStatus("succeeded", nextSequence()));
      controller.close();
    },
  });
}

/** The writer's section line, as `tick.section` carries it: sections count
 *  without the case-studies and introduction slots, which have their own
 *  lines. */
function sectionLine(index: number): string {
  const written = mockArtefactSkeleton.filter(
    (slot) => slot.index !== MOCK_CASE_STUDIES_INDEX && slot.index !== MOCK_INTRO_INDEX,
  );
  const position = written.findIndex((slot) => slot.index === index);
  return `Section ${position + 1} of ${written.length} · ${mockArtefactSkeleton[index].title}`;
}

/** One activity tick (task 058, D2): never persisted, so no `sequence`. */
function tick(
  stage: StageKey,
  activity: string,
  extra: { done?: number; total?: number; unit?: string; section?: string; heartbeat?: boolean } = {},
): SseFrame {
  return {
    type: "tick",
    ephemeral: true,
    stage,
    activity,
    done: extra.done ?? null,
    total: extra.total ?? null,
    unit: extra.unit ?? null,
    section: extra.section ?? null,
    heartbeat: extra.heartbeat ?? false,
    dropped: 0,
    occurred_at: frameTime(),
  };
}

interface StageTick {
  activity: string;
  done?: number;
  total?: number;
  unit?: string;
}

/**
 * Walk one stage of the Evidence search: started, a tick every 400 ms with the
 * stage's activity line, one heartbeat (the hub repeating the current line
 * while a model call is in flight), completed with its summary.
 */
async function walkStage(
  emit: (frame: SseFrame) => void,
  emitTick: (frame: SseFrame) => void,
  nextSequence: () => number,
  stage: StageKey,
  wait: (ms: number) => Promise<void>,
  ticks: StageTick[],
  summary: Record<string, number>,
) {
  emit(stageStarted(stage, nextSequence()));
  setLiveStage(stage);
  for (const [index, entry] of ticks.entries()) {
    emitTick(tick(stage, entry.activity, entry));
    if (index === 0) emitTick(tick(stage, entry.activity, { ...entry, heartbeat: true }));
    await wait(MOCK_TICK_MS);
  }
  emit(stageCompleted(stage, summary, nextSequence()));
}

/**
 * The options-scoping baseline walk (task 044, Phase 5.5): three components,
 * then a genuine park on the baseline gate. The walk holds there until the
 * gate is answered — by the card or by a Task Agent decision turn — and ends
 * the way that decision says: `succeeded` through to the longlist, or
 * `aborted` back to an editable plan.
 *
 * Args:
 *   emit: Frame sink for the open stream.
 *   nextSequence: The stream's sequence counter.
 */
async function scopingBaselineWalk(emit: (frame: SseFrame) => void, nextSequence: () => number) {
  emit(runStatus("running", nextSequence()));
  const steps: Array<[StageKey, Record<string, number>]> = [
    ["acquire", { acquired: 74 }],
    ["screen", { relevant: 28, screened_out: 46 }],
    ["synthesise", { section_count: 4 }],
  ];
  for (const [stage, summary] of steps) {
    emit(stageStarted(stage, nextSequence()));
    setLiveStage(stage);
    emit(stageCompleted(stage, summary, nextSequence()));
  }
  setRunArtefact(mockBaselineArtefact.artefact_id);
  emit(runStatus("paused", nextSequence()));
  // The card is placed by its own time: it opens now, after the question
  // that started the task, never at the fixture's fixed time above it.
  baselineGateOpenedAt = frameTime();
  const gateSequence = nextSequence();
  emit({
    type: "checkin.pending",
    check_in: { ...mockBaselineGateCheckIn, created_at: baselineGateOpenedAt, sequence: gateSequence },
    occurred_at: baselineGateOpenedAt,
    sequence: gateSequence,
  });

  await baselineGateAnswer.promise;
  const decision = baselineGateDecision ?? { optionId: "confirm_plan", label: "Confirm plan and build longlist" };
  emit({
    type: "checkin.resolved",
    check_in_id: MOCK_BASELINE_CHECK_IN_ID,
    response: { kind: "option", option_id: decision.optionId, params: null },
    decided_by: "user",
    occurred_at: frameTime(),
    sequence: nextSequence(),
  });
  emit(runStatus(decision.optionId === "change_plan" ? "aborted" : "succeeded", nextSequence()));
}

/** Records the artefact this walk wrote, once synthesise completes — before
 *  the walk necessarily reaches a terminal status (the baseline gate pauses
 *  it first; task 044 review, C6). */
function setRunArtefact(artefactId: string) {
  if (currentRun === null) return;
  currentRun = { ...currentRun, artefact_id: artefactId };
}

/** Keep the REST-visible run/task state in step with the stream's
 *  terminal frame, so the landing card and nav badge stop claiming
 *  "Analysing…" once the scripted run has actually finished. */
function finishRun(status: "succeeded" | "failed" | "aborted") {
  if (currentRun === null) return;
  const endedAt = new Date().toISOString();
  currentRun = { ...currentRun, status, ended_at: endedAt };
  mockTask.latest_run = latestRunOf(currentRun);
  mockTask.active_run = null;
}

/** Stamp the live run with the stage it last started and the server's label
 *  for it, as `TaskOut.active_run` and `latest_run` carry them while a walk
 *  runs (task 058, N15). */
function setLiveStage(stage: StageKey) {
  const label = STAGE_PRESENTATION[stage][0];
  for (const run of [mockTask.latest_run, mockTask.active_run]) {
    if (run != null) {
      run.stage = stage;
      run.stage_label = label;
    }
  }
}

function frameTime(): string {
  return new Date().toISOString();
}

function runStatus(status: "running" | "paused" | "succeeded" | "failed" | "aborted", sequence: number, runId: string = MOCK_RUN_ID): SseFrame {
  return { type: "run.status", capability_run_id: runId, status, occurred_at: frameTime(), sequence };
}

function stageStarted(stage: StageKey, sequence: number, runId: string = MOCK_RUN_ID): SseFrame {
  const [label, blurb] = STAGE_PRESENTATION[stage];
  return { type: "stage.started", capability_run_id: runId, stage, label, blurb, occurred_at: frameTime(), sequence };
}

function stageCompleted(stage: StageKey, summary: Record<string, number>, sequence: number, runId: string = MOCK_RUN_ID): SseFrame {
  const counts = STAGE_COUNTS[stage].flatMap(([key, noun]) => (typeof summary[key] === "number" ? [{ value: summary[key], noun }] : []));
  return { type: "stage.completed", capability_run_id: runId, stage, label: STAGE_PRESENTATION[stage][0], summary, seconds: 4, counts, occurred_at: frameTime(), sequence };
}

function stageFailed(stage: StageKey, reason: string, sequence: number): SseFrame {
  return { type: "stage.failed", capability_run_id: MOCK_RUN_ID, stage, label: STAGE_PRESENTATION[stage][0], reason, skipped: false, occurred_at: frameTime(), sequence };
}

function toSse(frame: SseFrame): string {
  // Ephemeral frames (ticks, section deltas) are never persisted: no `id:`.
  const id = "sequence" in frame ? `id:${frame.sequence}\n` : "";
  return `${id}event:${frame.type}\ndata:${JSON.stringify(frame)}\n\n`;
}

function page<T>(data: T[]) {
  return { data, pagination: { page: 1, page_size: data.length, total_items: data.length, has_more: false } };
}

/** One server-shaped page of `rows`, read from `page` and `page_size`. */
function pageOf<T>(rows: T[], url: URL) {
  const pageNumber = Math.max(1, Number(url.searchParams.get("page") ?? "1") || 1);
  const pageSize = Math.max(1, Number(url.searchParams.get("page_size") ?? "50") || 50);
  const start = (pageNumber - 1) * pageSize;
  return {
    data: rows.slice(start, start + pageSize),
    pagination: {
      page: pageNumber,
      page_size: pageSize,
      total_items: rows.length,
      has_more: start + pageSize < rows.length,
    },
  };
}

/** The server's 403 message for a colleague's project change (task 058, round 10). */
export const PROJECTS_OWNER_ONLY = "Only the task's owner can change its projects.";

/** The spellings the server folds into one country name (`country_name`). */
const MOCK_COUNTRY_ALIASES: Record<string, string> = {
  gb: "united kingdom",
  uk: "united kingdom",
  us: "united states",
  usa: "united states",
};

/** Mirror of the server's `country` filter: any spelling; "Not reported" is none. */
function mockCountryMatches(itemCountry: string | null, wanted: string): boolean {
  if (wanted.trim() === "Not reported") return itemCountry === null;
  const key = wanted.trim().toLowerCase();
  return itemCountry !== null && itemCountry.toLowerCase() === (MOCK_COUNTRY_ALIASES[key] ?? key);
}

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}

async function requestBody(request: Request | undefined, init: RequestInit | undefined): Promise<unknown> {
  if (typeof init?.body === "string") return parseJson(init.body);
  if (request) return request.clone().json().catch(() => null);
  return null;
}

function parseJson(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

function createDeferred(): Deferred {
  let resolve: (() => void) | undefined;
  const promise = new Promise<void>((complete) => { resolve = complete; });
  return { promise, resolve: () => resolve?.() };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// --- task 045 (6.3): the longlist walk, what exists and what is active ---

/** True from the moment a longlist walk opens until its longlist stage
 *  completes: `GET /longlist` answers 404 meanwhile. */
let mockLonglistBuilding = false;
/** The options read while the walk builds: empty until suggest completes. */
let mockOptionRows: components["schemas"]["OptionProgressOut"][] = [];
/** The last stage the longlist read has caught up with while a walk runs;
 *  `null` outside a walk (the finished longlist is then served). */
let mockLonglistWalkStage: MockWalkLonglistStage | null = null;

/** The longlist a finished mock walk built (task 058, round 10): its option
 *  ids (cards in `mockLonglistOptionCards`) and its themes. `null` until a
 *  walk finishes; the fixture's four-option longlist is served meanwhile. */
let mockFinishedWalk: {
  optionIds: string[];
  themes: components["schemas"]["LonglistOut"]["themes"];
} | null = null;

/** The option search the mock fails, so the build shows a failed row: the
 *  last seed, "Conditionality reform for under-25s". */
const MOCK_FAILED_SEARCH_INDEX = 11;

/** The options the longlist currently holds: the finished walk's, else the
 *  fixture's four; either way plus any added by hand since. */
function currentMockOptionIds(): string[] {
  const base = mockFinishedWalk?.optionIds ?? (mockLonglist().options ?? []).map((option) => option.option_id);
  return [...new Set([...base, ...mockLonglistExtraOptionIds])];
}

/** `GET /longlist` after a walk: the build's options, themed, read off their
 *  cards so the verbs' changes show. */
function mockFinishedWalkLonglist(): components["schemas"]["LonglistOut"] {
  const finished = mockFinishedWalk!;
  const base = mockLonglist();
  const options = currentMockOptionIds()
    .map((optionId) => mockLonglistOptionCards[optionId])
    .filter((card) => card !== undefined)
    .map(toLonglistOptionSummary);
  const themed = new Set(finished.themes?.flatMap((theme) => theme.option_ids ?? []) ?? []);
  return {
    ...base,
    counts: {
      options: options.length,
      themes: finished.themes?.length ?? 0,
      included: options.filter((option) => option.state === "included").length,
      excluded: options.filter((option) => option.state === "excluded").length,
      no_in_scope: options.filter((option) => option.no_in_scope_evidence).length,
      none_fits: options.filter((option) => option.primary_lever_type == null).length,
    },
    themes: finished.themes,
    unthemed_option_ids: options.map((option) => option.option_id).filter((optionId) => !themed.has(optionId)),
    options,
  };
}

/** The scoping plan's current version; edits and confirms move it. */
let mockScopingPlanVersion = 1;
/** The longlist walks opened so far, newest first. */
let mockLonglistWalks: RunOut[] = [];
/** Walks opened but not yet streamed. */
let mockLonglistPending: string[] = [];
let mockLonglistWake = createDeferred();

function resetMockLonglistWalks() {
  mockScopingPlanVersion = 1;
  mockLonglistWalks = [];
  mockLonglistPending = [];
  mockLonglistWake = createDeferred();
  mockLonglistBuilding = false;
  mockLonglistWalkStage = null;
  mockOptionRows = [];
  mockTask.active_run = null;
  mockTask.has_longlist = false;
  for (const optionId of mockFinishedWalk?.optionIds ?? []) delete mockLonglistOptionCards[optionId];
  mockFinishedWalk = null;
}

/** A 409 in the API's error envelope. */
function mockConflict(code: string, message: string): Response {
  return json({ error: { code, message } }, 409);
}

function latestRunOf(run: RunOut): components["schemas"]["LatestRun"] {
  return {
    capability_run_id: run.capability_run_id,
    status: run.status,
    started_at: run.started_at,
    ended_at: run.ended_at,
  };
}

/**
 * Open a longlist walk the way the API does: at once, in the read models
 * (`active_run`, the walk list, `latest_run` — a longlist walk is parentless
 * and untargeted), with its frames following on the open stream.
 *
 * Returns:
 *   The opened walk, as the confirm route's `opened_run`.
 */
function requestMockLonglistWalk(planVersion: number): components["schemas"]["LatestRun"] {
  const walk: RunOut = {
    capability_run_id: crypto.randomUUID(),
    task_id: MOCK_TASK_ID,
    plan_id: MOCK_PLAN_ID,
    plan_version: planVersion,
    status: "running",
    started_at: new Date().toISOString(),
    ended_at: null,
    artefact_id: null,
    parent_capability_run_id: null,
    purpose: "longlist",
  };
  mockLonglistWalks = [walk, ...mockLonglistWalks];
  mockShortlistState.inputsChanged = false;
  mockLonglistBuilding = true;
  mockOptionRows = [];
  mockTask.active_run = latestRunOf(walk);
  mockTask.latest_run = latestRunOf(walk);
  mockLonglistPending.push(walk.capability_run_id);
  mockLonglistWake.resolve();
  return latestRunOf(walk);
}

/** Stream every longlist walk as it is opened, for as long as the stream
 *  stays connected. */
async function mockLonglistWalkLoop(emit: (frame: SseFrame) => void, nextSequence: () => number) {
  for (;;) {
    await mockLonglistWake.promise;
    mockLonglistWake = createDeferred();
    while (mockLonglistPending.length > 0) {
      const walkId = mockLonglistPending.shift();
      if (walkId !== undefined) await mockLonglistWalk(walkId, emit, nextSequence);
    }
  }
}

/** `1180` as `1,180`, the way the server's activity lines write counts. */
function withCommas(value: number): string {
  return String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/**
 * One longlist walk's frames (task 058, N21, N22): the stages in the order the
 * walk runs them, each with the server's label and an activity tick. The
 * options read follows the walk: rows from the end of `suggest`, a child
 * search per row (ten at once, then two) while `option_searches` runs, and
 * one fold plus two new rows when `longlist` completes, which is also when
 * `GET /longlist` stops answering 404. Held briefly at the start so "Building
 * the longlist" is observable.
 */
async function mockLonglistWalk(
  walkId: string,
  emit: (frame: SseFrame) => void,
  nextSequence: () => number,
) {
  const counts = mockWalkLonglist(foldMockOptionRows(seedMockOptionRows()), "shortlist").counts;
  const planVersion = mockLonglistWalks.find((walk) => walk.capability_run_id === walkId)?.plan_version ?? 1;
  const begin = (stage: StageKey) => {
    emit(stageStarted(stage, nextSequence(), walkId));
    setLiveStage(stage);
  };
  const finish = (stage: StageKey, summary: Record<string, number>) =>
    emit(stageCompleted(stage, summary, nextSequence(), walkId));
  /** A stage that only ticks: one tick per line, then the stage completes. */
  const runStage = async (stage: StageKey, lines: StageTick[], summary: Record<string, number>, onDone?: () => void) => {
    begin(stage);
    for (const line of lines) {
      emit(tick(stage, line.activity, line));
      await pace(MOCK_TICK_MS);
    }
    onDone?.();
    finish(stage, summary);
  };

  emit(runStatus("running", nextSequence(), walkId));
  await pace(1200);
  await runStage("inherit", [{ activity: "Reading the linked search" }], { documents: 42, links: 1 });
  await runStage("suggest", [{ activity: "Suggesting options" }], { suggested: MOCK_OPTION_COUNT, from_report: 2 }, () => {
    mockOptionRows = seedMockOptionRows();
  });

  // The option searches: one child walk per option, run through a pool of ten.
  begin("option_searches");
  const patchRow = (index: number, patch: Partial<components["schemas"]["OptionProgressOut"]>) => {
    mockOptionRows = mockOptionRows.map((row, at) => (at === index ? { ...row, ...patch } : row));
  };
  let nextOption = 0;
  let finished = 0;
  let failed = 0;
  let sources = 0;
  const searchOption = async (index: number) => {
    const childId = mockChildRunId(index);
    const startedAt = new Date().toISOString();
    mockLonglistWalks = [
      {
        capability_run_id: childId,
        task_id: MOCK_TASK_ID,
        plan_id: MOCK_PLAN_ID,
        plan_version: planVersion,
        status: "running",
        started_at: startedAt,
        ended_at: null,
        artefact_id: null,
        parent_capability_run_id: walkId,
        purpose: "targeted",
      },
      ...mockLonglistWalks,
    ];
    emit(runStatus("running", nextSequence(), childId));
    patchRow(index, { search_status: "searching" });
    emit(stageStarted("acquire", nextSequence(), childId));
    await pace(500 + ((index * 7) % 5) * 220);
    if (index === MOCK_FAILED_SEARCH_INDEX) {
      // One search fails, as one can on the server: the row says so, the
      // join counts it failed, not finished.
      emit({
        type: "stage.failed",
        capability_run_id: childId,
        stage: "acquire",
        label: STAGE_PRESENTATION.acquire[0],
        reason: "The search service did not respond.",
        skipped: false,
        occurred_at: frameTime(),
        sequence: nextSequence(),
      });
      patchRow(index, { search_status: "failed", found: null });
      emit(runStatus("failed", nextSequence(), childId));
      const failedAt = new Date().toISOString();
      mockLonglistWalks = mockLonglistWalks.map((walk) =>
        walk.capability_run_id === childId ? { ...walk, status: "failed", ended_at: failedAt } : walk,
      );
      failed += 1;
      emit(tick("option_searches", `${finished} of ${MOCK_OPTION_COUNT} searches done · ${withCommas(sources)} sources so far`, {
        done: finished,
        total: MOCK_OPTION_COUNT,
        unit: "searches",
      }));
      return;
    }
    const found = mockOptionFound(index);
    emit(stageCompleted("acquire", { acquired: found }, nextSequence(), childId));
    patchRow(index, { search_status: "searched", found });
    emit(runStatus("succeeded", nextSequence(), childId));
    const endedAt = new Date().toISOString();
    mockLonglistWalks = mockLonglistWalks.map((walk) =>
      walk.capability_run_id === childId ? { ...walk, status: "succeeded", ended_at: endedAt } : walk,
    );
    finished += 1;
    sources += found;
    emit(tick("option_searches", `${finished} of ${MOCK_OPTION_COUNT} searches done · ${withCommas(sources)} sources so far`, {
      done: finished,
      total: MOCK_OPTION_COUNT,
      unit: "searches",
    }));
  };
  const worker = async () => {
    while (nextOption < MOCK_OPTION_COUNT) {
      const index = nextOption;
      nextOption += 1;
      await searchOption(index);
    }
  };
  await Promise.all(Array.from({ length: 10 }, worker));
  finish("option_searches", { total: MOCK_OPTION_COUNT, finished, failed, sources });

  await runStage("extract_interventions", [
    { activity: "900 of 2,410 abstracts read", done: 900, total: 2410, unit: "documents" },
    { activity: "1,800 of 2,410 abstracts read", done: 1800, total: 2410, unit: "documents" },
    { activity: "2,410 of 2,410 abstracts read", done: 2410, total: 2410, unit: "documents" },
  ], { documents: 2410, records: 64 });
  await runStage("longlist", [
    { activity: "Assigning sources to options · batch 1 of 2", done: 1, total: 2, unit: "batches" },
    { activity: "Assigning sources to options · batch 2 of 2", done: 2, total: 2, unit: "batches" },
  ], { options: counts.options, themes: counts.themes, unclustered: 5, not_an_option: 2 }, () => {
    mockOptionRows = foldMockOptionRows(mockOptionRows);
    mockLonglistWalkStage = "longlist";
    mockLonglistBuilding = false;
  });
  await runStage("option_profile", [
    { activity: "Typing options · batch 1 of 1", done: 1, total: 1, unit: "batches" },
    { activity: `Writing place sentences · ${counts.options} of ${counts.options} options`, done: counts.options, total: counts.options, unit: "options" },
  ], { profiled: counts.options }, () => {
    mockLonglistWalkStage = "option_profile";
  });
  await runStage("constrain", [
    { activity: "Checking constraints · batch 1 of 1", done: 1, total: 1, unit: "batches" },
  ], { excluded: counts.excluded, no_in_scope: counts.no_in_scope }, () => {
    mockLonglistWalkStage = "constrain";
  });
  await runStage("theme", [
    { activity: "Assigning options to themes · batch 1 of 1", done: 1, total: 1, unit: "batches" },
  ], { themes: counts.themes }, () => {
    mockLonglistWalkStage = "theme";
  });
  // Hold the themed build a moment, so it can be seen before the shortlist.
  await pace(1500);
  const placed = Object.values(mockLonglistOptionCards).filter(
    (option) => option.shortlist?.state === "proposed" || option.shortlist?.state === "added_by_you",
  ).length;
  await runStage("shortlist", [{ activity: "Choosing the shortlist" }], { kept: placed }, () => {
    mockLonglistWalkStage = "shortlist";
  });
  // The walk is over: the finished longlist takes over, the same options the
  // build showed, themed, each with a working card.
  const built = mockWalkLonglist(mockOptionRows, "shortlist");
  for (const optionId of mockFinishedWalk?.optionIds ?? []) delete mockLonglistOptionCards[optionId];
  const cards = mockWalkOptionCards(built);
  for (const card of cards) mockLonglistOptionCards[card.option_id] = card;
  mockFinishedWalk = { optionIds: cards.map((card) => card.option_id), themes: built.themes };
  mockLonglistWalkStage = null;

  const endedAt = new Date().toISOString();
  mockLonglistWalks = mockLonglistWalks.map((walk) =>
    walk.capability_run_id === walkId ? { ...walk, status: "succeeded", ended_at: endedAt } : walk,
  );
  const finishedWalk = mockLonglistWalks.find((walk) => walk.capability_run_id === walkId);
  if (finishedWalk !== undefined) mockTask.latest_run = latestRunOf(finishedWalk);
  mockTask.active_run = null;
  mockTask.has_longlist = true;
  emit(runStatus("succeeded", nextSequence(), walkId));
}
