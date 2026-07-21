import type { SseFrame } from "../api/sseFrame";
import type { AuthApi } from "../auth/types";
import {
  mockArtefact,
  mockCheckIn,
  mockCoverage,
  mockDecisions,
  mockEvidence,
  mockFindings,
  mockFunnel,
  mockLandscape,
  mockProject,
  MOCK_CHECK_IN_ID,
  MOCK_PROJECT_ID,
  MOCK_RUN_ID,
} from "./fixtures";

interface Deferred {
  promise: Promise<void>;
  resolve: () => void;
}

let checkInAnswer = createDeferred();

/** Reset the scripted pause; useful for isolated mock tests. */
export function resetMockScenario() {
  checkInAnswer = createDeferred();
}

/** Fetch implementation for the generated openapi-fetch client in mock mode. */
export async function mockFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const request = input instanceof Request ? input : undefined;
  const url = new URL(request?.url ?? input.toString(), globalThis.location?.origin ?? "http://localhost");
  const method = init?.method ?? request?.method ?? "GET";
  const path = url.pathname;

  if (method === "GET" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/events`)) {
    return new Response(createMockEventStream(), {
      headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" },
    });
  }
  if (method === "POST" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/check-ins/${MOCK_CHECK_IN_ID}/response`)) {
    const body = await requestBody(request, init);
    checkInAnswer.resolve();
    if (isRecord(body) && body.kind === "free_text") {
      return json({
        render: "Use the free-text steer to foreground Tower Hamlets family support and keep the active-travel evidence gap explicit.",
        confirm_token: "mock-confirm-balanced-synthesis",
      }, 202);
    }
    return json({ accepted: true });
  }

  if (method === "GET" && path.endsWith("/api/v1/projects")) return json(page([mockProject]));
  if (method === "GET" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}`)) return json(mockProject);
  if (method === "GET" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/funnel`)) return json(mockFunnel);
  if (method === "GET" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/landscape`)) return json(mockLandscape);
  if (method === "GET" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/evidence`)) return json(page(mockEvidence));
  if (method === "GET" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/findings`)) return json(page(mockFindings));
  if (method === "GET" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/decisions`)) return json(page(mockDecisions));
  if (method === "GET" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/artefact`)) return json(mockArtefact);
  if (method === "GET" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/coverage`)) return json(mockCoverage);
  if (method === "GET" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/check-ins`)) return json([mockCheckIn]);
  if (method === "GET" && path.endsWith(`/api/v1/projects/${MOCK_PROJECT_ID}/runs`)) {
    return json([{ capability_run_id: MOCK_RUN_ID, project_id: MOCK_PROJECT_ID, plan_id: "90000000-0000-4000-8000-000000000001", plan_version: 3, status: "running", started_at: "2026-07-21T09:30:00Z", ended_at: null }]);
  }
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

function createMockEventStream(): ReadableStream<Uint8Array> {
  const beforeAnswer: SseFrame[] = [
    runStatus("running", 1),
    stageStarted("acquire", "Finding relevant sources", "Searching policy and research evidence", 2),
    stageCompleted("acquire", "Finding relevant sources", { found: 128 }, 3),
    stageStarted("screen", "Screening sources", "Checking relevance to primary-school children", 4),
    stageCompleted("screen", "Screening sources", { relevant: 46, screened_out: 82 }, 5),
    stageStarted("classify", "Classifying evidence", "Labelling evidence types and settings", 6),
    stageCompleted("classify", "Classifying evidence", { classified: 46 }, 7),
    stageStarted("appraise", "Appraising quality", "Reviewing the strength of selected evidence", 8),
    stageCompleted("appraise", "Appraising quality", { quality_checked: 31 }, 9),
    stageStarted("characterise", "Characterising findings", "Extracting implementation conditions", 10),
    stageCompleted("characterise", "Characterising findings", { findings: 34 }, 11),
    stageStarted("synthesise", "Synthesising the evidence", "Preparing a decision-ready evidence base", 12),
    { type: "checkin.pending", check_in: mockCheckIn, occurred_at: "2026-07-21T09:42:00Z", sequence: 42 },
  ];
  const afterAnswer: SseFrame[] = [
    { type: "checkin.resolved", check_in_id: MOCK_CHECK_IN_ID, response: { kind: "option", option_id: "suggested-balanced", params: null }, decided_by: "user", occurred_at: "2026-07-21T09:43:00Z", sequence: 43 },
    stageCompleted("synthesise", "Synthesising the evidence", { cited: 12, sections: 2 }, 44),
    runStatus("succeeded", 45),
  ];
  const encoder = new TextEncoder();

  return new ReadableStream<Uint8Array>({
    async start(controller) {
      for (const frame of beforeAnswer) {
        controller.enqueue(encoder.encode(toSse(frame)));
        await Promise.resolve();
      }
      await checkInAnswer.promise;
      for (const frame of afterAnswer) {
        controller.enqueue(encoder.encode(toSse(frame)));
        await Promise.resolve();
      }
      controller.close();
    },
  });
}

function runStatus(status: "running" | "succeeded", sequence: number): SseFrame {
  return { type: "run.status", capability_run_id: MOCK_RUN_ID, status, occurred_at: "2026-07-21T09:30:00Z", sequence };
}

function stageStarted(stage: "acquire" | "screen" | "classify" | "appraise" | "characterise" | "synthesise", label: string, blurb: string, sequence: number): SseFrame {
  return { type: "stage.started", stage, label, blurb, occurred_at: "2026-07-21T09:30:00Z", sequence };
}

function stageCompleted(stage: "acquire" | "screen" | "classify" | "appraise" | "characterise" | "synthesise", label: string, summary: Record<string, number>, sequence: number): SseFrame {
  return { type: "stage.completed", stage, label, summary, seconds: 4, occurred_at: "2026-07-21T09:30:00Z", sequence };
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
