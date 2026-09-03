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
import { BETA_CHIP_HINT } from "../ui/brand/Nav";

const PROJECT_ID = "11111111-1111-1111-1111-111111111111";

const authState = vi.hoisted(() => ({ signOut: vi.fn() }));

// Task 033 phase 10b: mutable per-test so the owner-scoped check-in banner
// and the account-menu tests can each set their own `/me`/`is_owner` shape
// without a fresh `vi.mock` factory per test.
const meState = vi.hoisted(() => ({
  data: {
    user_id: "policy-lead",
    display_name: "Ada Lovelace",
    email: null as string | null,
    organisation: null as { org_id: string; name: string } | null,
    is_admin: false,
  },
}));
const projectState = vi.hoisted(() => ({ isOwner: true }));

vi.mock("../api/queries", () => ({
  useMe: () => ({ data: meState.data }),
  useProject: (projectId: string) => ({
    data: projectId
      ? {
          project_id: PROJECT_ID,
          name: "Acme project",
          visibility: "org",
          is_owner: projectState.isOwner,
        }
      : undefined,
  }),
  useCheckIns: () => ({ data: { data: [{ check_in_id: "pending-1" }] } }),
  // The nav logo checks all projects for an active run outside a task.
  useProjects: () => ({ data: { data: [] } }),
  // The chat side panel (029 rev 3.4) mounts on non-workspace project routes.
  useConversations: () => ({ data: { data: [] } }),
  useArtefact: () => ({ data: undefined }),
  // The header's project-settings popover (028 F.5) wires the rename/archive
  // mutations, which resolve their API client through this hook — a bare
  // object is enough since these tests never open the popover.
  useApiClient: () => ({}),
}));

vi.mock("../api/mutations", () => ({
  useUpdateProject: () => ({ mutate: vi.fn(), isPending: false }),
  useArchiveProject: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
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

// AppShell owns RunStreamProvider on task routes — stub the SSE client so
// tests never open a real fetch-stream.
vi.mock("../api/sse", () => ({
  connectEventStream: () => ({ close: vi.fn() }),
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
    projectState.isOwner = true;
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

describe("AppShell — the check-in banner is owner-scoped (task 033 phase 10b, rubric 38)", () => {
  beforeEach(() => {
    authState.signOut.mockClear();
  });

  it("shows the cross-tab pause banner for the Task's owner", () => {
    projectState.isOwner = true;
    renderShell(`/projects/${PROJECT_ID}/sources`);
    expect(
      screen.getByText(/a check-in is waiting on you/),
    ).toBeInTheDocument();
  });

  it("a colleague reading a non-owned Task is never told a check-in is waiting on them", () => {
    projectState.isOwner = false;
    renderShell(`/projects/${PROJECT_ID}/sources`);
    expect(screen.queryByText("Check-in pending")).not.toBeInTheDocument();
    expect(screen.queryByText(/a check-in is waiting on you/)).not.toBeInTheDocument();
  });
});

describe("AppShell — the project-settings popover (task 033 phase 10c, contract § 11 / rubric 37)", () => {
  beforeEach(() => {
    authState.signOut.mockClear();
  });

  async function openProjectSettings() {
    const user = userEvent.setup();
    renderShell(`/projects/${PROJECT_ID}`);
    await user.click(screen.getByRole("button", { name: "Project settings" }));
    return user;
  }

  it("owner: shows Rename and Archive", async () => {
    projectState.isOwner = true;
    await openProjectSettings();
    expect(screen.getByRole("button", { name: "Rename" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Archive" })).toBeInTheDocument();
  });

  it("non-owner: hides the settings gear itself, not just the items inside it — an empty popover is not a fix", () => {
    projectState.isOwner = false;
    renderShell(`/projects/${PROJECT_ID}`);
    expect(screen.queryByRole("button", { name: "Project settings" })).not.toBeInTheDocument();
    // With the trigger gone, Rename and Archive can never be reached either.
    expect(screen.queryByRole("button", { name: "Rename" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Archive" })).not.toBeInTheDocument();
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

  it("explains the BETA chip on hover", async () => {
    const user = userEvent.setup();
    renderShell("/new");
    await user.hover(screen.getByText("BETA"));
    expect(await screen.findByText(BETA_CHIP_HINT)).toBeInTheDocument();
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

  it("does not pin the site footer under the Plan tab (it scrolls with the chat)", () => {
    renderShell(`/projects/${PROJECT_ID}`);
    // AppShell stubs the Plan outlet — the real footer mounts inside
    // PlanningPane's transcript scroll, not as a shell chrome strip.
    expect(screen.queryByRole("contentinfo")).not.toBeInTheDocument();
  });

  it("puts the site footer at the bottom of task tab scroll content", () => {
    renderShell(`/projects/${PROJECT_ID}/sources`);
    const pane = screen.getByTestId("task-scroll-pane");
    const footer = screen.getByRole("contentinfo");
    expect(pane).toContainElement(footer);
    expect(footer).toHaveTextContent(SITE_DISCLAIMER);
  });
});

describe("AppShell — the account menu (task 033 phase 10b, contract § 11 / rubric 41)", () => {
  beforeEach(() => {
    authState.signOut.mockClear();
    meState.data = {
      user_id: "policy-lead",
      display_name: "Ada Lovelace",
      email: null,
      organisation: null,
      is_admin: false,
    };
  });

  async function openAccountMenu() {
    const user = userEvent.setup();
    renderShell("/");
    await user.click(screen.getByRole("button", { name: "Account" }));
    return user;
  }

  it("unenrolled: shows the display name, 'No organisation', and no email line", async () => {
    await openAccountMenu();
    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.getByText("No organisation")).toBeInTheDocument();
    expect(screen.queryByText("Administrator")).not.toBeInTheDocument();
  });

  it("enrolled: shows the email and the organisation name", async () => {
    meState.data = {
      user_id: "policy-lead",
      display_name: "Ada Lovelace",
      email: "ada.lovelace@example.gov.uk",
      organisation: { org_id: "org-1", name: "Department for Local Growth" },
      is_admin: false,
    };
    await openAccountMenu();
    expect(screen.getByText("ada.lovelace@example.gov.uk")).toBeInTheDocument();
    expect(screen.getByText("Department for Local Growth")).toBeInTheDocument();
    expect(screen.queryByText("Administrator")).not.toBeInTheDocument();
  });

  it("admin: shows the word Administrator", async () => {
    meState.data = {
      user_id: "admin-1",
      display_name: "Grace Hopper",
      email: "grace.hopper@example.gov.uk",
      organisation: { org_id: "org-1", name: "Department for Local Growth" },
      is_admin: true,
    };
    await openAccountMenu();
    expect(screen.getByText("Administrator")).toBeInTheDocument();
  });

  it("truncates a long email with CSS rather than breaking the popover layout", async () => {
    meState.data = {
      user_id: "policy-lead",
      display_name: "Ada Lovelace",
      email: "a.very.long.civil.service.email.address.indeed@example.gov.uk",
      organisation: null,
      is_admin: false,
    };
    await openAccountMenu();
    const emailNode = screen.getByText("a.very.long.civil.service.email.address.indeed@example.gov.uk");
    expect(emailNode.className).toContain("truncate");
  });
});

describe("AppShell — global chrome, continued", () => {
  beforeEach(() => {
    authState.signOut.mockClear();
    sessionStorage.clear();
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
