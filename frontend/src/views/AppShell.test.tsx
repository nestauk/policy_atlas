import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "./AppShell";
import { SITE_DISCLAIMER } from "./AppFooter";
import { PrivacyView } from "./legal/PrivacyView";
import { TermsView } from "./legal/TermsView";
import { TASK } from "../lib/vocabulary";

const PROJECT_ID = "11111111-1111-1111-1111-111111111111";

const authState = vi.hoisted(() => ({ signOut: vi.fn() }));

vi.mock("../api/queries", () => ({
  useProject: (projectId: string) => ({
    data: projectId ? { project_id: PROJECT_ID, name: "Acme project" } : undefined,
  }),
  useCheckIns: () => ({ data: { data: [{ check_in_id: "pending-1" }] } }),
  // The chat side panel (029 rev 3.4) mounts on non-workspace project routes.
  useConversations: () => ({ data: { data: [] } }),
  useArtefact: () => ({ data: undefined }),
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
    signOut: authState.signOut,
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
          <Route element={<AppShell />}>
            <Route path="/" element={<div>tasks</div>} />
            <Route path="/new" element={<div>new</div>} />
            <Route path="/portfolios" element={<div>projects</div>} />
            <Route path="/privacy" element={<PrivacyView />} />
            <Route path="/terms" element={<TermsView />} />
            <Route path="/projects/:projectId/*" element={<div>task</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("AppShell — pending check-in nav badge (027 strand 14)", () => {
  beforeEach(() => {
    authState.signOut.mockClear();
  });

  it("shows the Workspace nav badge when a check-in is pending outside the workspace", () => {
    renderShell(`/projects/${PROJECT_ID}/sources`);
    expect(screen.getByText("Check-in pending")).toBeInTheDocument();
  });

  it("hides the badge while already on the workspace view", () => {
    renderShell(`/projects/${PROJECT_ID}`);
    expect(screen.queryByText("Check-in pending")).not.toBeInTheDocument();
  });
});

describe("AppShell — global chrome", () => {
  beforeEach(() => {
    authState.signOut.mockClear();
    sessionStorage.clear();
  });

  it("keeps New, Tasks, Projects and the account control on every view", () => {
    renderShell("/new");
    expect(screen.getByRole("link", { name: "New" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: TASK.many })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Projects" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Account" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Sign out" })).not.toBeInTheDocument();
  });

  it("underlines the active global nav item", () => {
    renderShell("/portfolios");
    expect(screen.getByRole("link", { name: "Projects" }).className).toContain("border-blue");
    expect(screen.getByRole("link", { name: "New" }).className).not.toContain("border-blue");
    expect(screen.getByRole("link", { name: TASK.many }).className).not.toContain("border-blue");
  });

  it("opens Sign out from the account icon", async () => {
    const user = userEvent.setup();
    renderShell("/");
    await user.click(screen.getByRole("button", { name: "Account" }));
    await user.click(screen.getByRole("button", { name: "Sign out" }));
    expect(authState.signOut).toHaveBeenCalledOnce();
  });

  it("puts the task name and lifecycle tabs on a second bar, not the global one", () => {
    renderShell(`/projects/${PROJECT_ID}/sources`);
    const appNav = screen.getByRole("navigation", { name: "App" });
    const taskNav = screen.getByRole("navigation", { name: "Task" });
    expect(appNav).toHaveTextContent("New");
    expect(appNav).toHaveTextContent(TASK.many);
    expect(appNav).toHaveTextContent("Projects");
    expect(appNav).not.toHaveTextContent("Plan");
    expect(taskNav).toHaveTextContent("Acme project");
    expect(taskNav).toHaveTextContent("Plan");
    expect(taskNav).toHaveTextContent("Results");
  });

  it("hides the task bar on workspace-level pages", () => {
    renderShell("/portfolios");
    expect(screen.queryByRole("navigation", { name: "Task" })).not.toBeInTheDocument();
    expect(screen.queryByText("Acme project")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Plan" })).not.toBeInTheDocument();
  });

  it("shows the site footer with privacy and terms links on workspace-level pages", () => {
    renderShell("/new");
    expect(screen.getByRole("contentinfo")).toHaveTextContent(SITE_DISCLAIMER);
    expect(screen.getByRole("link", { name: "Privacy policy" })).toHaveAttribute("href", "/privacy");
    expect(screen.getByRole("link", { name: "Terms of use" })).toHaveAttribute("href", "/terms");
  });

  it("shows the site footer inside a task", () => {
    renderShell(`/projects/${PROJECT_ID}`);
    expect(screen.getByRole("contentinfo")).toHaveTextContent(SITE_DISCLAIMER);
  });

  it("shows a dismissible sensitivity banner under the nav", async () => {
    const user = userEvent.setup();
    renderShell("/new");
    expect(
      screen.getByText("Do not enter sensitive or confidential information."),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Dismiss warning" }));
    expect(
      screen.queryByText("Do not enter sensitive or confidential information."),
    ).not.toBeInTheDocument();
  });

  it("opens the privacy notice and terms of use from the footer", async () => {
    const user = userEvent.setup();
    renderShell("/new");
    await user.click(screen.getByRole("link", { name: "Privacy policy" }));
    expect(screen.getByRole("heading", { name: "Privacy notice" })).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Terms of use" }));
    expect(screen.getByRole("heading", { name: "Terms of use" })).toBeInTheDocument();
  });
});
