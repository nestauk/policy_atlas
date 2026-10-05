import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as queries from "../api/queries";
import { AUTH_RETURN_TO_KEY } from "../auth/OidcAuthProvider";
import { PublicTaskShell } from "./PublicTaskShell";

vi.mock("../api/queries", () => ({ useTask: vi.fn() }));

vi.mock("../auth", () => ({
  useAuth: () => ({
    user: null,
    status: "unauthenticated",
    signIn: vi.fn(),
    signOut: vi.fn(),
    onUnauthenticated: vi.fn(),
    getAccessToken: async () => null,
  }),
}));

// The shell mounts RunStreamProvider with connect={false}; stub the SSE
// client so an accidental connect would still never open a real stream —
// and assert below that it is never called at all.
const sseState = vi.hoisted(() => ({ connect: vi.fn(() => ({ close: vi.fn() })) }));
vi.mock("../api/sse", () => ({
  connectEventStream: sseState.connect,
}));

const TASK_ID = "11111111-1111-1111-1111-111111111111";

function mockTask(
  data: Record<string, unknown> | undefined,
  { pending = false } = {},
) {
  vi.mocked(queries.useTask).mockReturnValue({
    isPending: pending,
    data,
  } as unknown as ReturnType<typeof queries.useTask>);
}

const PUBLIC_TASK = {
  task_id: TASK_ID,
  name: "Shared evidence review",
  access: "public",
  is_public: true,
  is_owner: false,
  owner_display: null,
  project_ids: [],
  latest_run: null,
};

function renderShell(path: string) {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/" element={<div>splash probe</div>} />
          <Route path="/tasks/:taskId" element={<PublicTaskShell />}>
            <Route path="result" element={<div>results probe</div>} />
            <Route path="sources" element={<div>sources probe</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  sessionStorage.clear();
  sseState.connect.mockClear();
});

describe("PublicTaskShell — the public task view (task 037)", () => {
  it("shows a loading state while the tokenless task read is pending", () => {
    mockTask(undefined, { pending: true });
    renderShell(`/tasks/${TASK_ID}/result`);
    expect(screen.getByRole("status")).toHaveTextContent("Loading…");
  });

  it("keeps stash-and-splash for a Task that is not public — same as before the slice", () => {
    mockTask(undefined);
    renderShell(`/tasks/${TASK_ID}/result`);
    expect(screen.getByText("splash probe")).toBeInTheDocument();
    expect(sessionStorage.getItem(AUTH_RETURN_TO_KEY)).toBe(`/tasks/${TASK_ID}/result`);
  });

  it("renders the two-tab shell around a public Task's Results", () => {
    mockTask(PUBLIC_TASK);
    renderShell(`/tasks/${TASK_ID}/result`);
    expect(screen.getByText("Shared evidence review")).toBeInTheDocument();
    expect(screen.getByText("results probe")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
    const taskNav = screen.getByRole("navigation", { name: "Task" });
    const links = Array.from(taskNav.querySelectorAll("a")).map((a) => a.textContent);
    expect(links).toEqual(["Result", "Sources"]);
  });

  it("never opens the run event stream — the events route is not public", () => {
    mockTask(PUBLIC_TASK);
    renderShell(`/tasks/${TASK_ID}/result`);
    expect(sseState.connect).not.toHaveBeenCalled();
  });
});
