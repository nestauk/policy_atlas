import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthContext } from "../auth/AuthContext";
import type { AuthApi } from "../auth/types";
import { ArtefactView } from "./ArtefactView";
import { PublicViewProvider } from "./publicView";

// The public view (task 037) must never open the run stream (the events
// route is not on the public surface) — stub the SSE-backed store to its
// idle shape rather than requiring a real RunStreamProvider connection.
vi.mock("../store", () => ({
  useRunStream: () => ({ liveSections: {}, run: null, connectionStatus: "idle" }),
  hasTerminalPartialLiveArtefact: () => false,
}));

const TASK_ID = "11111111-1111-1111-1111-111111111111";

function auth(): AuthApi {
  return {
    getAccessToken: async () => null,
    signIn: vi.fn(),
    signOut: vi.fn(),
    onUnauthenticated: vi.fn(),
    user: null,
    status: "unauthenticated",
  };
}

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } });
}

const PROJECT = {
  task_id: TASK_ID,
  name: "Shared evidence review",
  access: "public",
  is_owner: false,
  latest_run: null,
};

const ARTEFACT = {
  artefact_id: "artefact-1",
  title: "Shared evidence review",
  sections: [],
  references: [],
  most_relevant_notes: [],
  coverage_snapshot: null,
  full_report_intro: null,
};

const LANDSCAPE = { evidence_types: {}, years: {}, geographies: {}, themes: [] };
const FUNNEL = { found: 0, relevant: 0, cited: 0 };

/** Render the real `ArtefactView` under `PublicViewProvider value={true}`
 *  with every actual request logged — the pin is on the requests made, not
 *  on a mocked query layer that could quietly diverge from the real hooks. */
function renderPublicArtefact() {
  const requestedPaths: string[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(
      input instanceof Request ? input.url : String(input),
      "http://localhost:3000",
    );
    requestedPaths.push(url.pathname);
    if (url.pathname === `/api/v1/tasks/${TASK_ID}`) return jsonResponse(PROJECT);
    if (url.pathname === `/api/v1/tasks/${TASK_ID}/artefact`) return jsonResponse(ARTEFACT);
    if (url.pathname === `/api/v1/tasks/${TASK_ID}/landscape`) return jsonResponse(LANDSCAPE);
    if (url.pathname === `/api/v1/tasks/${TASK_ID}/funnel`) return jsonResponse(FUNNEL);
    return jsonResponse({});
  });
  vi.stubGlobal("fetch", fetchMock);

  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <AuthContext.Provider value={auth()}>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[`/tasks/${TASK_ID}/result`]}>
          <Routes>
            <Route
              path="/tasks/:taskId/result"
              element={
                <PublicViewProvider value={true}>
                  <ArtefactView />
                </PublicViewProvider>
              }
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
  return { requestedPaths };
}

beforeEach(() => {
  // Node's fetch (undici) rejects relative URLs — an absolute base keeps
  // the stub intercepting (matches `src/api/queries.test.ts`).
  vi.stubEnv("VITE_API_BASE_URL", "http://localhost:3000");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("ArtefactView — public view issues only public-surface requests (task 037 acceptance pin)", () => {
  it("never fetches conversations and hides the chat affordance", async () => {
    const { requestedPaths } = renderPublicArtefact();

    await waitFor(() => expect(screen.getByText("Shared evidence review")).toBeInTheDocument());

    expect(requestedPaths.some((path) => path.includes("conversations"))).toBe(false);
    expect(screen.queryByText("Ask about this analysis")).not.toBeInTheDocument();
  });
});
