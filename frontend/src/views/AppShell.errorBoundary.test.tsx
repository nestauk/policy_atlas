import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "./AppShell";

const TASK_ID = "11111111-1111-1111-1111-111111111111";

vi.mock("../api/queries", () => ({
  useMe: () => ({ data: { user_id: "policy-lead", display_name: "Ada Lovelace", organisation: null, is_admin: false } }),
  useTask: () => ({
    data: { task_id: TASK_ID, name: "Acme task", visibility: "org", is_owner: true },
  }),
  useCheckIns: () => ({ data: { data: [] } }),
  // The nav logo checks all tasks for an active run outside a task.
  useTasks: () => ({ data: { data: [] } }),
  // The header's task-settings popover wires rename/archive mutations,
  // which resolve their client through this hook.
  useApiClient: () => ({}),
}));

vi.mock("../api/mutations", () => ({
  useUpdateTask: () => ({ mutate: vi.fn(), isPending: false }),
  useArchiveTask: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
}));

vi.mock("../auth", () => ({
  useAuth: () => ({
    user: { sub: "policy-lead" },
    status: "authenticated",
    signIn: vi.fn(),
    signOut: vi.fn(),
    onUnauthenticated: vi.fn(),
    getAccessToken: async () => "token",
  }),
}));

vi.mock("../api/sse", () => ({
  connectEventStream: () => ({ close: vi.fn() }),
}));

// A render error inside the chat subtree (029 fix 6): the panel must not
// take the whole shell down with it — it sits in its own `ErrorBoundary`,
// separate from the routed view's.
vi.mock("./workspace/chat/ChatSidePanel", () => ({
  ChatSidePanel: () => {
    throw new Error("boom");
  },
}));

function renderShell(initialPath: string) {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/tasks/:taskId/*" element={<AppShell />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("AppShell — chat subtree error containment (029 fix 6)", () => {
  it("keeps the nav and routed view usable when the chat panel throws while rendering", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    renderShell(`/tasks/${TASK_ID}/sources`);

    // The chat's own boundary caught it — the last-resort fallback shows in
    // its place, not a full-page crash.
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    // Everything outside the chat subtree survives: global nav, account.
    expect(screen.getByRole("link", { name: "New" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Account" })).toBeInTheDocument();
  });
});
