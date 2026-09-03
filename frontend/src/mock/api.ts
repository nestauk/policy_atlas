import type { SseFrame } from "../api/sseFrame";
import type { AuthApi } from "../auth/types";
import type { components } from "../api/gen/types";
import type { EvidenceSortField } from "../views/sourcesPresentation";
import {
  mockArtefact,
  mockArtefactSectionProse,
  mockArtefactSkeleton,
  mockCheckIn,
  mockCoverage,
  mockDecisions,
  mockEvidence,
  mockEvidenceThemeIds,
  mockFindings,
  mockFunnel,
  mockGroups,
  mockLandscape,
  mockMeUnenrolled,
  mockPlanReady,
  mockPortfolio,
  mockProject,
  mockSourceDossiers,
  seedPlanningTurns,
  MOCK_CHAT_ANSWER_DELTAS,
  MOCK_CHAT_CITATION_CHUNK_ID,
  MOCK_CHAT_CITATION_QUOTE,
  MOCK_CHAT_CLAIM_ID,
  MOCK_CHAT_CLAIM_TEXT,
  MOCK_CHAT_PROGRESS_LABEL,
  MOCK_CHECK_IN_ID,
  MOCK_PLAN_ID,
  MOCK_PLANNING_CONVERSATION_ID,
  MOCK_PROJECT_ID,
  MOCK_RUN_ID,
} from "./fixtures";

type MeOut = components["schemas"]["MeOut"];
type PortfolioOut = components["schemas"]["PortfolioOut"];

type RunOut = components["schemas"]["RunOut"];
type PlanningTranscriptTurnOut = components["schemas"]["PlanningTranscriptTurnOut"];
type EvidenceItemOut = components["schemas"]["EvidenceItemOut"];
type ConversationOut = components["schemas"]["ConversationOut"];
type ConversationListItemOut = components["schemas"]["ConversationListItemOut"];
type ChatTurnOut = components["schemas"]["ChatTurnOut"];

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
 * main journey drives; `"paused"` holds indefinitely at a mid-synthesis
 * "writing" state (a demo/screenshot fixture — the run never resolves);
 * `"failed-partial"` streams both sections then ends the run `failed`, the
 * terminal-partial banner fixture the contract names. Selected via a
 * `?mockScenario=` query param on the `/events` request itself — a direct
 * mock-layer fixture switch (see `mock/api.test.ts`), not something the real
 * SSE client currently forwards from the page URL.
 */
type MockScenario = "default" | "paused" | "failed-partial";

/** All frames in the scripted stream share this display timestamp — a mock
 *  fixture's `occurred_at` is presentation metadata only, never load-bearing. */
const FRAME_TIME = "2026-07-21T09:30:00Z";

interface Deferred {
  promise: Promise<void>;
  resolve: () => void;
}

let checkInAnswer = createDeferred();
let checkInAnswered = false;
let runStarted = createDeferred();
let currentRun: RunOut | null = null;
let planningTurns: PlanningTranscriptTurnOut[] = seedPlanningTurns();
let nextTurnIndex = 4; // the seed transcript occupies turn_index 1-3

// --- Chat conversations + turns (task 029 phase G3 mock) -----------------
// Follow-up chats are created on demand. The planning conversation is
// pre-seeded so the chats overlay (G14) has a planning row in mock mode,
// matching a real project that already has a plan lineage.
function seedConversations(): ConversationOut[] {
  return [
    {
      id: MOCK_PLANNING_CONVERSATION_ID,
      project_id: MOCK_PROJECT_ID,
      kind: "planning",
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

// --- Identity + portfolios (task 033 phase 10a) --------------------------
// `currentMe` defaults to the unenrolled fixture — dark launch: every
// pre-033 mock journey sees `organisation: null` and stays unchanged. Tests
// that need the enrolled/org-scoped journeys call `setMockMe(mockMeEnrolled)`.
let currentMe: MeOut = { ...mockMeUnenrolled };
let mockPortfolios: PortfolioOut[] = [{ ...mockPortfolio }];
const mockWaitlistEmails = new Set<string>();

/** Test helper: switch the mock's `/me` identity (e.g. to `mockMeEnrolled`). */
export function setMockMe(me: MeOut) {
  currentMe = { ...me };
}

/** Reset every scripted scenario; useful for isolated mock tests. */
export function resetMockScenario() {
  checkInAnswer = createDeferred();
  checkInAnswered = false;
  runStarted = createDeferred();
  currentRun = null;
  mockProject.latest_run = null;
  planningTurns = seedPlanningTurns();
  nextTurnIndex = 4;
  chatConversations = seedConversations();
  chatTurnsByConversation = new Map();
  chatTurnEnrichmentReads = new Map();
  currentPlan = { ...mockPlanReady };
  currentMe = { ...mockMeUnenrolled };
  mockPortfolios = [{ ...mockPortfolio }];
}

function currentMockScenario(requestUrl: URL): MockScenario {
  const value = requestUrl.searchParams.get("mockScenario");
  return value === "paused" || value === "failed-partial" ? value : "default";
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

  if (method === "GET" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/events`)) {
    return new Response(createMockEventStream(currentMockScenario(url)), {
      headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" },
    });
  }
  if (method === "POST" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/check-ins/${MOCK_CHECK_IN_ID}/response`)) {
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

  // --- Project lifecycle (landing rename/archive, contract strand 8) ------
  if (method === "PATCH" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}`)) {
    const body = await requestBody(request, init);
    // Task 033 phase 10b: i.5 — a Task's own visibility can't be set while
    // it's in a Project (portfolio membership). The mock mirrors the real
    // 409 `visibility_conflict` so the control's error line is exercisable
    // in mock mode too, not just against a live backend. Checked before any
    // field is assigned, matching the real API's all-or-nothing conflict —
    // a 409 must leave every field (including a same-body rename) untouched.
    if (
      isRecord(body) &&
      (body.visibility === "org" || body.visibility === "private") &&
      (mockProject.portfolio_ids?.length ?? 0) > 0
    ) {
      return json({ error: { code: "visibility_conflict", message: "Task is in a Project." } }, 409);
    }
    if (isRecord(body) && typeof body.name === "string") mockProject.name = body.name;
    if (isRecord(body) && typeof body.question === "string") mockProject.question = body.question;
    if (isRecord(body) && (body.visibility === "org" || body.visibility === "private")) {
      mockProject.visibility = body.visibility;
    }
    if (isRecord(body) && Array.isArray(body.portfolio_ids)) {
      mockProject.portfolio_ids = body.portfolio_ids.filter(
        (value): value is string => typeof value === "string",
      );
    }
    mockProject.updated_at = new Date().toISOString();
    return json(mockProject);
  }
  if (method === "POST" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/archive`)) {
    mockProject.status = "archived";
    mockProject.archived_at = new Date().toISOString();
    return json(mockProject);
  }

  // --- Durable planning transcript (contract strand 12) -------------------
  if (method === "GET" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/planning-turns`)) {
    return json(page(planningTurns));
  }
  if (method === "POST" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/planning-turns`)) {
    const body = await requestBody(request, init);
    const clientTurnId = isRecord(body) && typeof body.client_turn_id === "string" ? body.client_turn_id : crypto.randomUUID();
    const message = isRecord(body) && typeof body.message === "string" ? body.message : "";
    const now = new Date().toISOString();
    const reply = "Noted — I'll keep that in mind for the analysis.";
    const existing = planningTurns.find((turn) => turn.client_turn_id === clientTurnId);
    if (existing !== undefined) {
      // Retry-in-place (finding 6): the same client_turn_id re-runs, never a
      // fresh turn_index.
      existing.status = "completed";
      existing.reply = reply;
      existing.suggestions = [];
      existing.completed_at = now;
    } else {
      planningTurns.push({
        client_turn_id: clientTurnId,
        turn_index: nextTurnIndex,
        user_message: message,
        reply,
        suggestions: [],
        part: null,
        status: "completed",
        created_at: now,
        completed_at: now,
      });
      nextTurnIndex += 1;
    }
    return json({ plan: currentPlan, reply, suggestions: [] });
  }

  // --- Plan (a resumed session: the transcript above already reached
  // `ready` — see mockPlanReady) ------------------------------------------
  if (method === "GET" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/plan`)) {
    return json({ plan: currentPlan, version: 1, status: "approved" });
  }
  if (method === "PATCH" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/plan`)) {
    const body = await requestBody(request, init);
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

  if (method === "GET" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/groups`)) {
    return json(mockGroups);
  }

  // --- Runs: gate the event stream behind an actual start (the plan pane's
  // "Start the analysis" CTA), rather than a run appearing pre-started. ----
  if (method === "POST" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/runs`)) {
    if (currentRun !== null && (currentRun.status === "running" || currentRun.status === "paused")) {
      return json({ error: { code: "run_active", message: "An analysis is already running." } }, 409);
    }
    const now = new Date().toISOString();
    currentRun = {
      capability_run_id: MOCK_RUN_ID,
      project_id: MOCK_PROJECT_ID,
      plan_id: MOCK_PLAN_ID,
      plan_version: 1,
      status: "running",
      started_at: now,
      ended_at: null,
    };
    mockProject.latest_run = {
      capability_run_id: currentRun.capability_run_id,
      status: currentRun.status,
      started_at: currentRun.started_at,
      ended_at: currentRun.ended_at,
    };
    runStarted.resolve();
    return json(currentRun, 201);
  }
  if (method === "GET" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/runs`)) {
    return json(page(currentRun ? [currentRun] : []));
  }

  if (method === "GET" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/check-ins`)) {
    const status = url.searchParams.get("status");
    const rows = status === "pending" && checkInAnswered ? [] : [mockCheckIn];
    return json(page(rows));
  }

  // --- Identity + portfolios (task 033 phase 10a) -------------------------
  if (method === "GET" && path.endsWith("/api/v1/me")) return json(currentMe);
  if (method === "GET" && path.endsWith("/api/v1/portfolios")) return json(page(mockPortfolios));
  const portfolioDetailMatch = /\/api\/v1\/portfolios\/([^/]+)$/.exec(path);
  if (method === "GET" && portfolioDetailMatch) {
    const found = mockPortfolios.find((portfolio) => portfolio.portfolio_id === portfolioDetailMatch[1]);
    return found !== undefined ? json(found) : json({ detail: "resource not found" }, 404);
  }
  // Task 033 phase 10b: the visibility control's cascade (i.4) — the mock's
  // one project is the portfolio's only member, so "every member follows"
  // is a single assignment, but the shape (mutate both rows, return the
  // updated `task_count`) matches what the visibility-outcome copy reads.
  if (method === "PATCH" && portfolioDetailMatch) {
    const found = mockPortfolios.find((portfolio) => portfolio.portfolio_id === portfolioDetailMatch[1]);
    if (found === undefined) return json({ detail: "resource not found" }, 404);
    const body = await requestBody(request, init);
    if (isRecord(body) && typeof body.name === "string") found.name = body.name;
    if (isRecord(body) && typeof body.description === "string") found.description = body.description;
    if (isRecord(body) && (body.visibility === "org" || body.visibility === "private")) {
      found.visibility = body.visibility;
      if (mockProject.portfolio_ids?.includes(found.portfolio_id) === true) {
        mockProject.visibility = body.visibility;
      }
    }
    return json(found);
  }

  // `portfolio_id` narrows to one portfolio's members, server-side — mirrors
  // the real list's filter (contract task 033 phase 10a: `PortfolioDetailView`
  // no longer filters the global page client-side).
  if (method === "GET" && path.endsWith("/api/v1/projects")) {
    const portfolioId = url.searchParams.get("portfolio_id");
    const rows =
      portfolioId === null || mockProject.portfolio_ids?.includes(portfolioId) === true
        ? [mockProject]
        : [];
    return json(page(rows));
  }
  if (method === "GET" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}`)) return json(mockProject);
  if (method === "GET" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/funnel`)) return json(mockFunnel);
  if (method === "GET" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/landscape`)) return json(mockLandscape);
  if (method === "GET" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/evidence`)) {
    const statuses = url.searchParams.getAll("status");
    const cited = url.searchParams.get("cited");
    const theme = url.searchParams.get("theme");
    const origin = url.searchParams.get("origin");
    const evidenceType = url.searchParams.get("evidence_type");
    const strength = url.searchParams.get("strength");
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
  if (method === "GET" && path.includes(`/api/v1/projects/${MOCK_PROJECT_ID}/sources/`)) {
    const sourceId = path.split("/").at(-1) ?? "";
    const source = mockSourceDossiers[sourceId];
    return source ? json(source) : json({ detail: "resource not found" }, 404);
  }
  if (method === "GET" && path.includes(`/api/v1/projects/${MOCK_PROJECT_ID}/chunks/`) && path.endsWith("/context")) {
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
    });
  }
  if (method === "GET" && path.includes(`/api/v1/projects/${MOCK_PROJECT_ID}/citations/`) && path.endsWith("/context")) {
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
    });
  }
  if (method === "GET" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/findings`)) {
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
  if (method === "GET" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/decisions`)) return json(page(mockDecisions));
  if (method === "GET" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/artefact`)) return json(mockArtefact);
  if (method === "GET" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/coverage`)) return json(mockCoverage);

  // --- Conversations + chat turns (task 029 phase G3 mock) ---------------
  if (method === "GET" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/conversations`)) {
    const kind = url.searchParams.get("kind");
    const status = url.searchParams.get("status");
    const rows = chatConversations
      .filter((conversation) => (kind === null || conversation.kind === kind) && (status === null || conversation.status === status))
      .map(conversationListItem)
      .sort((a, b) => b.created_at.localeCompare(a.created_at));
    return json(page(rows));
  }
  if (method === "POST" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/conversations`)) {
    const body = await requestBody(request, init);
    const entryArtefactId = isRecord(body) && typeof body.entry_artefact_id === "string" ? body.entry_artefact_id : null;
    const now = new Date().toISOString();
    const conversation: ConversationOut = {
      id: crypto.randomUUID(),
      project_id: MOCK_PROJECT_ID,
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

  return json({ detail: "Mock endpoint not found" }, 404);
}

/** Project one conversation into its library row shape, deriving the
 *  preview from its own latest chat turn — mirrors the real read model's
 *  cross-kind preview join closely enough for the mock library surface. */
function conversationListItem(conversation: ConversationOut): ConversationListItemOut {
  const latestChat = (chatTurnsByConversation.get(conversation.id) ?? []).at(-1);
  const latestPlanning = conversation.kind === "planning" ? planningTurns.at(-1) : undefined;
  const latestTurnPreview =
    latestChat !== undefined
      ? {
          user_message: latestChat.user_message,
          reply_snippet: latestChat.status === "completed" ? latestChat.answer : null,
          at: latestChat.completed_at,
        }
      : latestPlanning !== undefined
        ? {
            user_message: latestPlanning.user_message,
            reply_snippet: latestPlanning.status === "completed" ? latestPlanning.reply : null,
            at: latestPlanning.completed_at,
          }
        : null;
  return {
    id: conversation.id,
    project_id: conversation.project_id,
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

      emit(runStatus("running", nextSequence()));
      emit(stageStarted("acquire", "Finding relevant sources", "Searching policy and research evidence", nextSequence()));
      emit(stageCompleted("acquire", "Finding relevant sources", { found: 128 }, nextSequence()));
      emit(stageStarted("screen", "Screening sources", "Checking relevance to primary-school children", nextSequence()));
      emit(stageCompleted("screen", "Screening sources", { relevant: 46, screened_out: 82 }, nextSequence()));
      emit(stageStarted("classify", "Classifying evidence", "Labelling evidence types and settings", nextSequence()));
      emit(stageCompleted("classify", "Classifying evidence", { classified: 46 }, nextSequence()));
      emit(stageStarted("appraise", "Appraising quality", "Reviewing the strength of selected evidence", nextSequence()));
      emit(stageCompleted("appraise", "Appraising quality", { quality_checked: 31 }, nextSequence()));
      emit(stageStarted("characterise", "Characterising findings", "Extracting implementation conditions", nextSequence()));
      emit(stageCompleted("characterise", "Characterising findings", { findings: 34 }, nextSequence()));
      emit(stageStarted("synthesise", "Synthesising the evidence", "Preparing a decision-ready evidence base", nextSequence()));
      // The run genuinely parks at this boundary (028 pause salience: paused
      // must read distinct from executing on every tab) — an explicit
      // `run.status` frame, not just the pending check-in itself.
      emit(runStatus("paused", nextSequence()));
      emit({ type: "checkin.pending", check_in: mockCheckIn, occurred_at: FRAME_TIME, sequence: nextSequence() });

      await checkInAnswer.promise;

      emit(runStatus("running", nextSequence()));
      emit({
        type: "checkin.resolved",
        check_in_id: MOCK_CHECK_IN_ID,
        response: { kind: "option", option_id: "suggested-balanced", params: null },
        decided_by: "user",
        occurred_at: FRAME_TIME,
        sequence: nextSequence(),
      });

      // Live artefact streaming (strand 13): skeleton, then each section
      // started -> completed, whole-section grain.
      emit({ type: "artefact.skeleton", sections: mockArtefactSkeleton, occurred_at: FRAME_TIME, sequence: nextSequence() });
      emit({ type: "artefact.section_started", index: 0, occurred_at: FRAME_TIME, sequence: nextSequence() });
      emit({
        type: "artefact.section_completed",
        index: 0,
        title: mockArtefactSkeleton[0].title,
        prose: mockArtefactSectionProse[0],
        occurred_at: FRAME_TIME,
        sequence: nextSequence(),
      });
      emit({ type: "artefact.section_started", index: 1, occurred_at: FRAME_TIME, sequence: nextSequence() });

      if (scenario === "paused") {
        // A demo/screenshot fixture: holds "writing" indefinitely rather
        // than a transient race a test would have to catch mid-flight.
        await new Promise<void>(() => {});
        return;
      }

      // Held briefly so the "writing" state is reliably observable before
      // the section fills — the demo journey's skeleton -> writing -> filled
      // check.
      await sleep(500);

      if (scenario === "failed-partial") {
        emit({
          type: "artefact.section_completed",
          index: 1,
          title: mockArtefactSkeleton[1].title,
          prose: mockArtefactSectionProse[1],
          occurred_at: FRAME_TIME,
          sequence: nextSequence(),
        });
        emit(stageFailed("synthesise", "Synthesising the evidence", "The write-up run hit an unrecoverable error.", nextSequence()));
        finishRun("failed");
        emit(runStatus("failed", nextSequence()));
        controller.close();
        return;
      }

      emit({
        type: "artefact.section_completed",
        index: 1,
        title: mockArtefactSkeleton[1].title,
        prose: mockArtefactSectionProse[1],
        occurred_at: FRAME_TIME,
        sequence: nextSequence(),
      });
      emit(stageCompleted("synthesise", "Synthesising the evidence", { cited: 12, sections: 2 }, nextSequence()));
      finishRun("succeeded");
      emit(runStatus("succeeded", nextSequence()));
      controller.close();
    },
  });
}

/** Keep the REST-visible run/project state in step with the stream's
 *  terminal frame, so the landing card and nav badge stop claiming
 *  "Analysing…" once the scripted run has actually finished. */
function finishRun(status: "succeeded" | "failed") {
  if (currentRun === null) return;
  const endedAt = new Date().toISOString();
  currentRun = { ...currentRun, status, ended_at: endedAt };
  mockProject.latest_run = {
    capability_run_id: currentRun.capability_run_id,
    status: currentRun.status,
    started_at: currentRun.started_at,
    ended_at: currentRun.ended_at,
  };
}

function frameTime(): string {
  return new Date().toISOString();
}

function runStatus(status: "running" | "paused" | "succeeded" | "failed", sequence: number): SseFrame {
  return { type: "run.status", capability_run_id: MOCK_RUN_ID, status, occurred_at: frameTime(), sequence };
}

function stageStarted(stage: "acquire" | "screen" | "classify" | "appraise" | "characterise" | "synthesise", label: string, blurb: string, sequence: number): SseFrame {
  return { type: "stage.started", stage, label, blurb, occurred_at: frameTime(), sequence };
}

function stageCompleted(stage: "acquire" | "screen" | "classify" | "appraise" | "characterise" | "synthesise", label: string, summary: Record<string, number>, sequence: number): SseFrame {
  return { type: "stage.completed", stage, label, summary, seconds: 4, occurred_at: frameTime(), sequence };
}

function stageFailed(stage: "synthesise", label: string, reason: string, sequence: number): SseFrame {
  return { type: "stage.failed", stage, label, reason, skipped: false, occurred_at: frameTime(), sequence };
}

function toSse(frame: SseFrame): string {
  const id = frame.type === "tick" ? "" : `id:${frame.sequence}\n`;
  return `${id}event:${frame.type}\ndata:${JSON.stringify(frame)}\n\n`;
}

function page<T>(data: T[]) {
  return { data, pagination: { page: 1, page_size: data.length, total_items: data.length } };
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
