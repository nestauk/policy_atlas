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
  mockPlanReady,
  mockProject,
  mockSourceDossiers,
  seedPlanningTurns,
  MOCK_CHECK_IN_ID,
  MOCK_PLAN_ID,
  MOCK_PROJECT_ID,
  MOCK_RUN_ID,
} from "./fixtures";

type RunOut = components["schemas"]["RunOut"];
type PlanningTranscriptTurnOut = components["schemas"]["PlanningTranscriptTurnOut"];
type EvidenceItemOut = components["schemas"]["EvidenceItemOut"];

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

/** Reset every scripted scenario; useful for isolated mock tests. */
export function resetMockScenario() {
  checkInAnswer = createDeferred();
  checkInAnswered = false;
  runStarted = createDeferred();
  currentRun = null;
  mockProject.latest_run = null;
  planningTurns = seedPlanningTurns();
  nextTurnIndex = 4;
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
    if (isRecord(body) && typeof body.name === "string") mockProject.name = body.name;
    if (isRecord(body) && typeof body.question === "string") mockProject.question = body.question;
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
    return json({ plan: mockPlanReady, reply, suggestions: [] });
  }

  // --- Plan (a resumed session: the transcript above already reached
  // `ready` — see mockPlanReady) ------------------------------------------
  if (method === "GET" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/plan`)) {
    return json({ plan: mockPlanReady, version: 1, status: "approved" });
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

  if (method === "GET" && path.endsWith("/api/v1/projects")) return json(page([mockProject]));
  if (method === "GET" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}`)) return json(mockProject);
  if (method === "GET" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/funnel`)) return json(mockFunnel);
  if (method === "GET" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/landscape`)) return json(mockLandscape);
  if (method === "GET" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/evidence`)) {
    const statuses = url.searchParams.getAll("status");
    const cited = url.searchParams.get("cited");
    const theme = url.searchParams.get("theme");
    const sort = url.searchParams.get("sort") as EvidenceSortField | null;
    const order = url.searchParams.get("order") as "asc" | "desc" | null;
    let rows = mockEvidence.filter((item) => {
      const included = ["relevant", "not_selected", "selected", "read_in_full", "findings_extracted", "cited", "unavailable"];
      const statusMatches = statuses.length === 0 || statuses.some((status) => status === item.status || (status === "Included" && included.includes(item.status)));
      const themeMatches = theme === null || (mockEvidenceThemeIds[item.source_id] ?? []).includes(theme);
      return statusMatches && (cited !== "true" || item.cited) && themeMatches;
    });
    // Server-side-equivalent sort (collection-true, matches
    // `repository._compare_evidence_sort`): `order` defaults to the
    // column's own natural direction (desc for year, asc otherwise) and
    // nulls always sort last regardless of direction.
    if (sort !== null) {
      const direction = order ?? (sort === "year" ? "desc" : "asc");
      rows = [...rows].sort((left, right) => compareMockEvidenceSort(left, right, sort, direction));
    }
    return json(page(rows));
  }
  if (method === "GET" && path.includes(`/api/v1/projects/${MOCK_PROJECT_ID}/sources/`)) {
    const sourceId = path.split("/").at(-1) ?? "";
    const source = mockSourceDossiers[sourceId];
    return source ? json(source) : json({ detail: "resource not found" }, 404);
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
  return json({ detail: "Mock endpoint not found" }, 404);
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

function runStatus(status: "running" | "paused" | "succeeded" | "failed", sequence: number): SseFrame {
  return { type: "run.status", capability_run_id: MOCK_RUN_ID, status, occurred_at: FRAME_TIME, sequence };
}

function stageStarted(stage: "acquire" | "screen" | "classify" | "appraise" | "characterise" | "synthesise", label: string, blurb: string, sequence: number): SseFrame {
  return { type: "stage.started", stage, label, blurb, occurred_at: FRAME_TIME, sequence };
}

function stageCompleted(stage: "acquire" | "screen" | "classify" | "appraise" | "characterise" | "synthesise", label: string, summary: Record<string, number>, sequence: number): SseFrame {
  return { type: "stage.completed", stage, label, summary, seconds: 4, occurred_at: FRAME_TIME, sequence };
}

function stageFailed(stage: "synthesise", label: string, reason: string, sequence: number): SseFrame {
  return { type: "stage.failed", stage, label, reason, skipped: false, occurred_at: FRAME_TIME, sequence };
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
