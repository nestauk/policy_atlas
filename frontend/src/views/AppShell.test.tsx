import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "./AppShell";
import { SITE_DISCLAIMER } from "./AppFooter";
import { PrivacyView } from "./legal/PrivacyView";
import { TermsView } from "./legal/TermsView";
import { TASK } from "../lib/vocabulary";
import { BETA_CHIP_HINT } from "../ui/brand/Nav";

const TASK_ID = "11111111-1111-1111-1111-111111111111";

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
const taskState = vi.hoisted(() => ({ isOwner: true, access: "full", pending: false }));

// Both mocked as spies (task 037 review fix) so a describe block below can
// assert neither is invoked while the task query is pending — a real
// conversations fetch or a real SSE connect would mean access was assumed
// before it was known.
const useConversationsState = vi.hoisted(() => ({ mock: vi.fn(() => ({ data: { data: [] } })) }));
const sseState = vi.hoisted(() => ({ connect: vi.fn(() => ({ close: vi.fn() })) }));

vi.mock("../api/queries", () => ({
  useMe: () => ({ data: meState.data }),
  useTask: (taskId: string) => ({
    data: taskId && !taskState.pending
      ? {
          task_id: TASK_ID,
          name: "Acme task",
          visibility: "org",
          is_owner: taskState.isOwner,
          access: taskState.access,
        }
      : undefined,
  }),
  useCheckIns: () => ({ data: { data: [{ check_in_id: "pending-1" }] } }),
  // The nav logo checks all tasks for an active run outside a task.
  useTasks: () => ({ data: { data: [] } }),
  // The chat side panel (029 rev 3.4) mounts on non-workspace task routes.
  useConversations: useConversationsState.mock,
  useArtefact: () => ({ data: undefined }),
  // The header's task-settings popover (028 F.5) wires the rename/archive
  // mutations, which resolve their API client through this hook — a bare
  // object is enough since these tests never open the popover.
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
    signOut: authState.signOut,
    onUnauthenticated: vi.fn(),
    getAccessToken: async () => "token",
  }),
}));

// AppShell owns RunStreamProvider on task routes — stub the SSE client so
// tests never open a real fetch-stream.
vi.mock("../api/sse", () => ({
  connectEventStream: sseState.connect,
}));

function renderShell(initialPath: string) {
  // The header's task-settings popover (028 F.5) wires rename/archive
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
            <Route path="/projects" element={<div>tasks</div>} />
            <Route path="/privacy" element={<PrivacyView />} />
            <Route path="/terms" element={<TermsView />} />
            <Route path="/tasks/:taskId/*" element={<div>task</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("AppShell — pending check-in nav badge (027 strand 14)", () => {
  beforeEach(() => {
    authState.signOut.mockClear();
    taskState.isOwner = true;
  });

  it("shows the Workspace nav badge when a check-in is pending outside the workspace", () => {
    renderShell(`/tasks/${TASK_ID}/sources`);
    expect(screen.getByText("Check-in pending")).toBeInTheDocument();
  });

  it("hides the badge while already on the Agent tab", () => {
    renderShell(`/tasks/${TASK_ID}`);
    expect(screen.queryByText("Check-in pending")).not.toBeInTheDocument();
  });
});

describe("AppShell — the check-in banner is owner-scoped (task 033 phase 10b, rubric 38)", () => {
  beforeEach(() => {
    authState.signOut.mockClear();
  });

  it("shows the cross-tab pause banner for the Task's owner", () => {
    taskState.isOwner = true;
    renderShell(`/tasks/${TASK_ID}/sources`);
    expect(
      screen.getByText(/a check-in is waiting on you/),
    ).toBeInTheDocument();
  });

  it("a colleague reading a non-owned Task is never told a check-in is waiting on them", () => {
    taskState.isOwner = false;
    renderShell(`/tasks/${TASK_ID}/sources`);
    expect(screen.queryByText("Check-in pending")).not.toBeInTheDocument();
    expect(screen.queryByText(/a check-in is waiting on you/)).not.toBeInTheDocument();
  });
});

describe("AppShell — the task-settings popover (task 033 phase 10c, contract § 11 / rubric 37)", () => {
  beforeEach(() => {
    authState.signOut.mockClear();
  });

  async function openTaskSettings() {
    const user = userEvent.setup();
    renderShell(`/tasks/${TASK_ID}`);
    await user.click(screen.getByRole("button", { name: "Task settings" }));
    return user;
  }

  it("owner: shows Rename and Archive", async () => {
    taskState.isOwner = true;
    await openTaskSettings();
    expect(screen.getByRole("button", { name: "Rename" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Archive" })).toBeInTheDocument();
  });

  it("non-owner: hides the settings gear itself, not just the items inside it — an empty popover is not a fix", () => {
    taskState.isOwner = false;
    renderShell(`/tasks/${TASK_ID}`);
    expect(screen.queryByRole("button", { name: "Task settings" })).not.toBeInTheDocument();
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
    renderShell("/projects");
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
    renderShell(`/tasks/${TASK_ID}/sources`);
    const appNav = screen.getByRole("navigation", { name: "App" });
    const taskNav = screen.getByRole("navigation", { name: "Task" });
    expect(appNav).toHaveTextContent("New");
    expect(appNav).toHaveTextContent(TASK.many);
    expect(appNav).toHaveTextContent("Projects");
    expect(appNav).not.toHaveTextContent("Agent");
    expect(taskNav).toHaveTextContent("Acme task");
    expect(taskNav).toHaveTextContent("Agent");
    expect(taskNav).toHaveTextContent("Result");
  });

  it("hides the task bar on workspace-level pages", () => {
    renderShell("/projects");
    expect(screen.queryByRole("navigation", { name: "Task" })).not.toBeInTheDocument();
    expect(screen.queryByText("Acme task")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Agent" })).not.toBeInTheDocument();
  });

  it("shows the site footer with privacy and terms links on workspace-level pages", () => {
    renderShell("/new");
    expect(screen.getByRole("contentinfo")).toHaveTextContent(SITE_DISCLAIMER);
    expect(screen.getByRole("link", { name: "Privacy policy" })).toHaveAttribute("href", "/privacy");
    expect(screen.getByRole("link", { name: "Terms of use" })).toHaveAttribute("href", "/terms");
  });

  it("does not pin the site footer under the Plan tab (it scrolls with the chat)", () => {
    renderShell(`/tasks/${TASK_ID}`);
    // AppShell stubs the Plan outlet — the real footer mounts inside
    // PlanningPane's transcript scroll, not as a shell chrome strip.
    expect(screen.queryByRole("contentinfo")).not.toBeInTheDocument();
  });

  it("puts the site footer at the bottom of task tab scroll content", () => {
    renderShell(`/tasks/${TASK_ID}/sources`);
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

describe("AppShell — the Agent overlay rides every task tab but Agent (038 V8)", () => {
  it("never mounts the overlay on the Agent tab — that tab has its own sidebar", () => {
    renderShell(`/tasks/${TASK_ID}`);
    expect(screen.queryByRole("button", { name: "Open the Agent" })).not.toBeInTheDocument();
  });

  it("mounts it on the other task tabs", () => {
    renderShell(`/tasks/${TASK_ID}/sources`);
    expect(screen.getByRole("button", { name: "Open the Agent" })).toBeInTheDocument();
  });

  it("never mounts it outside a task", () => {
    renderShell("/projects");
    expect(screen.queryByRole("button", { name: "Open the Agent" })).not.toBeInTheDocument();
  });
});

describe("AppShell — public-leg access renders the two-tab view (task 037)", () => {
  beforeEach(() => {
    taskState.isOwner = false;
    taskState.access = "public";
  });
  afterEach(() => {
    taskState.isOwner = true;
    taskState.access = "full";
  });

  it("shows only Results and Sources in the task nav for a public-leg reader", () => {
    renderShell(`/tasks/${TASK_ID}/result`);
    const taskNav = screen.getByRole("navigation", { name: "Task" });
    const links = Array.from(taskNav.querySelectorAll("a")).map((a) => a.textContent);
    expect(links).toEqual(["Result", "Sources"]);
  });

  it("does not mount the chat side panel on the public leg", () => {
    renderShell(`/tasks/${TASK_ID}/result`);
    expect(screen.queryByLabelText("Agent")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Open the Agent")).not.toBeInTheDocument();
  });

  it("keeps the five-tab shell for graded readers", () => {
    taskState.access = "full";
    taskState.isOwner = true;
    renderShell(`/tasks/${TASK_ID}/result`);
    const taskNav = screen.getByRole("navigation", { name: "Task" });
    const labels = Array.from(taskNav.querySelectorAll("a, [aria-disabled]")).map(
      (el) => el.textContent,
    );
    expect(labels).toHaveLength(5);
  });
});

describe("AppShell — gates the run stream and chat panel until access is known (task 037 review fix)", () => {
  beforeEach(() => {
    sseState.connect.mockClear();
    useConversationsState.mock.mockClear();
    taskState.pending = true;
  });
  afterEach(() => {
    taskState.pending = false;
  });

  it("does not connect the run stream while the task query is pending", () => {
    renderShell(`/tasks/${TASK_ID}/sources`);
    expect(sseState.connect).not.toHaveBeenCalled();
  });

  it("does not fetch conversations or show the chat panel while the task query is pending", () => {
    renderShell(`/tasks/${TASK_ID}/sources`);
    expect(useConversationsState.mock).not.toHaveBeenCalled();
    expect(screen.queryByLabelText("Agent")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Open the Agent")).not.toBeInTheDocument();
  });
});
