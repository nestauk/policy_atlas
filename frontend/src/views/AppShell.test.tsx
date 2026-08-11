import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "./AppShell";

const PROJECT_ID = "11111111-1111-1111-1111-111111111111";

vi.mock("../api/queries", () => ({
  useProject: () => ({ data: { project_id: PROJECT_ID, name: "Acme project" } }),
  useCheckIns: () => ({ data: { data: [{ check_in_id: "pending-1" }] } }),
  // The header's project-settings popover (028 F.5) wires the rename/archive
  // mutations, which resolve their API client through this hook — a bare
  // object is enough since these tests never open the popover.
  useApiClient: () => ({}),
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

function renderShell(initialPath: string) {
  // The header's project-settings popover (028 F.5) wires rename/archive
  // mutations, which resolve useQueryClient — a real QueryClient is needed
  // even though these tests never trigger a mutation.
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/projects/:projectId/*" element={<AppShell />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("AppShell — pending check-in nav badge (027 strand 14)", () => {
  it("shows the Workspace nav badge when a check-in is pending outside the workspace", () => {
    renderShell(`/projects/${PROJECT_ID}/sources`);
    expect(screen.getByText("Check-in pending")).toBeInTheDocument();
  });

  it("hides the badge while already on the workspace view", () => {
    renderShell(`/projects/${PROJECT_ID}`);
    expect(screen.queryByText("Check-in pending")).not.toBeInTheDocument();
  });

  it("shows the signed-in identity beside sign-out", () => {
    renderShell(`/projects/${PROJECT_ID}/sources`);
    expect(screen.getByText("policy-lead")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  });
});
