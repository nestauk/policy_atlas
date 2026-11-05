import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "./AppShell";
import { SITE_DISCLAIMER } from "./AppFooter";
import { PrivacyView } from "./legal/PrivacyView";
import { TermsView } from "./legal/TermsView";
import { useDocumentTitle } from "../lib/title";
import { TASK } from "../lib/vocabulary";
import type { SseFrame } from "../api/sseFrame";
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
const taskState = vi.hoisted(() => ({
  isOwner: true,
  access: "full",
  pending: false,
  capability: "evidence_search" as string | undefined,
  // Task 045 (S15): what exists and what is active.
  latestRun: null as { status: string } | null,
  activeRun: null as { status: string } | null,
  hasLonglist: false,
}));

// Both mocked as spies (task 037 review fix) so a describe block below can
// assert neither is invoked while the task query is pending — a real
// conversations fetch or a real SSE connect would mean access was assumed
// before it was known.
const useConversationsState = vi.hoisted(() => ({ mock: vi.fn(() => ({ data: { data: [] } })) }));
type StreamHandlers = {
  onConnected?: () => void;
  onDisconnected?: () => void;
  onFrame?: (frame: SseFrame) => void;
};
const sseState = vi.hoisted(() => ({
  handlers: null as StreamHandlers | null,
  connect: vi.fn((options: StreamHandlers) => {
    sseState.handlers = options;
    return { close: vi.fn() };
  }),
}));

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
          capability: taskState.capability,
          latest_run: taskState.latestRun,
          active_run: taskState.activeRun,
          has_longlist: taskState.hasLonglist,
        }
      : undefined,
  }),
  useCheckIns: () => ({ data: { data: [{ check_in_id: "pending-1" }] } }),
  // The chat side panel (029 rev 3.4) mounts on non-workspace task routes.
  useConversations: useConversationsState.mock,
  useArtefact: () => ({ data: undefined }),
  // The header's task-settings popover (028 F.5) wires the rename/archive
  // mutations, which resolve their API client through this hook — a bare
  // object is enough since these tests never open the popover.
  useApiClient: () => ({}),
}));

// The plan document reads its own queries; here only its opening matters.
vi.mock("./workspace/PlanDocument", () => ({
  PlanDocument: ({ onClose, readOnly }: { onClose: () => void; readOnly?: boolean }) => (
    <aside aria-label="Search plan" data-readonly={String(readOnly)}>
      <button type="button" onClick={onClose}>
        Close the search plan
      </button>
    </aside>
  ),
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

/** A task page that sets its title the way every task view does. */
function TitledTask() {
  useDocumentTitle("Acme task", "Sources");
  return <div>task</div>;
}

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
            <Route path="/tasks/:taskId/*" element={<TitledTask />} />
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
    taskState.capability = "evidence_search";
  });

  it("shows the Workspace nav badge when a check-in is pending outside the workspace", () => {
    renderShell(`/tasks/${TASK_ID}/sources`);
    // Two placements since 040 D2: the task NavBar (md+) and the bottom bar.
    expect(screen.getAllByText("Check-in pending")).toHaveLength(2);
  });

  it("hides the badge while already on the Agent tab", () => {
    renderShell(`/tasks/${TASK_ID}`);
    expect(screen.queryByText("Check-in pending")).not.toBeInTheDocument();
  });
});

describe("AppShell — mobile bottom tab bar (040 D2)", () => {
  it("renders all five lifecycle tabs in the bottom bar on a task route", () => {
    renderShell(`/tasks/${TASK_ID}/sources`);
    const bottomBar = screen.getByRole("navigation", { name: "Task stages" });
    for (const label of ["Agent", "Result", "Sources", "Share", "History"]) {
      expect(within(bottomBar).getByText(label)).toBeInTheDocument();
    }
  });

  it("renders no bottom bar on list pages", () => {
    renderShell("/");
    expect(screen.queryByRole("navigation", { name: "Task stages" })).not.toBeInTheDocument();
  });
});

const RUN_ID = "22222222-2222-2222-2222-222222222222";
let sequence = 0;
const now = () => new Date().toISOString();
const runStatus = (status: "running" | "paused" | "succeeded"): SseFrame =>
  ({ type: "run.status", capability_run_id: RUN_ID, status, occurred_at: now(), sequence: ++sequence }) as SseFrame;
const stageFrame = (type: "stage.started" | "stage.completed", stage: string, label: string): SseFrame =>
  ({
    type,
    capability_run_id: RUN_ID,
    stage,
    label,
    blurb: "",
    summary: {},
    seconds: 4,
    occurred_at: now(),
    sequence: ++sequence,
  }) as SseFrame;
const tickFrame = (stage: string, activity: string): SseFrame =>
  ({
    type: "tick",
    stage,
    activity,
    done: null,
    total: null,
    unit: null,
    section: null,
    heartbeat: false,
    dropped: 0,
    ephemeral: true,
    occurred_at: now(),
  }) as SseFrame;

/** Feed frames to the shell's one stream, as the server would. */
function feed(...frames: SseFrame[]) {
  act(() => {
    for (const frame of frames) sseState.handlers?.onFrame?.(frame);
  });
}

function connect() {
  act(() => {
    sseState.handlers?.onConnected?.();
  });
}

/** Let the replay window pass, so what lands next is news. */
function settle() {
  act(() => {
    vi.advanceTimersByTime(3_000);
  });
}

describe("AppShell — the live layer without a status bar (task 058; owner 2026-11-05, the run trace)", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    taskState.isOwner = true;
    taskState.access = "full";
    taskState.latestRun = { status: "running" };
    sseState.handlers = null;
  });
  afterEach(() => {
    vi.useRealTimers();
    taskState.latestRun = null;
  });

  it("shows the run status bar at the top of the page's column on Sources: the step and what it is doing, as the way to the Task Agent", () => {
    renderShell(`/tasks/${TASK_ID}/sources`);
    connect();
    feed(runStatus("running"), stageFrame("stage.started", "acquire", "Searching"), tickFrame("acquire", "searching · 184 found so far"));
    const statusBar = screen.getByTestId("run-status-bar");
    expect(statusBar).toHaveAttribute("data-open", "true");
    expect(statusBar).toHaveTextContent(/Searching.*184 found so far/);
    // Owner, round 9: after the time, the running step's view, while the
    // reader is elsewhere (here the Themes subtab, Sources' index).
    expect(within(statusBar).getByRole("link", { name: "Sources →" })).toHaveAttribute(
      "href",
      `/tasks/${TASK_ID}/sources/all`,
    );
    // Owner, round 8: the status bar opens the Task Agent (it starts after the
    // rail, in the column the routed view scrolls in).
    expect(within(statusBar).getByRole("button", { name: /^Open the Task Agent: Searching/ })).toBeInTheDocument();
    expect(statusBar.parentElement?.querySelector(":scope > [data-testid='task-scroll-pane']")).not.toBeNull();
  });

  it("shows the paused status bar and no paused banner while a check-in waits", () => {
    renderShell(`/tasks/${TASK_ID}/sources`);
    connect();
    feed(runStatus("running"), runStatus("paused"));
    const statusBar = screen.getByTestId("run-status-bar");
    expect(statusBar).toHaveAttribute("data-open", "true");
    expect(statusBar.querySelector("[data-tone='paused']")).not.toBeNull();
    expect(statusBar).toHaveTextContent(/^Paused/);
    expect(screen.queryByText(/Go to the check-in/)).toBeNull();
  });

  it("never tells a colleague a check-in is waiting on them", () => {
    taskState.isOwner = false;
    renderShell(`/tasks/${TASK_ID}/sources`);
    connect();
    feed(runStatus("running"), stageFrame("stage.completed", "acquire", "Searching and screening"), runStatus("paused"));
    expect(screen.queryByText("Check-in pending")).not.toBeInTheDocument();
    expect(screen.queryByText(/a check-in is waiting on you/)).not.toBeInTheDocument();
  });

  it("says the run finished in the title, with no link under the tabs", () => {
    renderShell(`/tasks/${TASK_ID}/sources`);
    connect();
    feed(runStatus("running"));
    settle();
    feed(runStatus("succeeded"));
    expect(screen.queryByRole("link", { name: "Read it →" })).toBeNull();
    expect(document.title).toBe("● Report ready · Acme task · Policy Atlas");
  });

  it("does not announce an old finish replayed when the page opens", () => {
    renderShell(`/tasks/${TASK_ID}/sources`);
    connect();
    feed(runStatus("running"), runStatus("succeeded"));
    settle();
    expect(screen.queryByRole("link", { name: "Read it →" })).toBeNull();
    expect(document.title).not.toContain("Report ready");
  });

  it("mounts the reconnecting banner while the live connection is lapsed", () => {
    renderShell(`/tasks/${TASK_ID}/sources`);
    connect();
    act(() => {
      sseState.handlers?.onDisconnected?.();
    });
    expect(screen.getByText(/Reconnecting to live updates/)).toBeInTheDocument();
  });

  it("is not in the public task view", () => {
    taskState.access = "public";
    renderShell(`/tasks/${TASK_ID}/sources`);
    expect(sseState.handlers).toBeNull();
    expect(screen.queryByRole("button", { name: "Plan" })).toBeNull();
  });
});

describe("AppShell — new content marks its tab (task 058, N14)", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    taskState.isOwner = true;
    taskState.access = "full";
    taskState.latestRun = { status: "running" };
    sseState.handlers = null;
  });
  afterEach(() => {
    vi.useRealTimers();
    taskState.latestRun = null;
  });

  it("dots Result when a section lands while the user is on Sources, and not Sources itself", () => {
    renderShell(`/tasks/${TASK_ID}/sources`);
    connect();
    feed(runStatus("running"));
    settle();
    feed(
      stageFrame("stage.completed", "acquire", "Searching and screening"),
      { type: "artefact.skeleton", sections: [{ index: 0, title: "Why take-up matters", focus: "" }], occurred_at: now(), sequence: ++sequence } as SseFrame,
      { type: "artefact.section_completed", index: 0, prose: "Take-up is lowest among the families it was designed for.", occurred_at: now(), sequence: ++sequence } as SseFrame,
    );
    const taskNav = screen.getByRole("navigation", { name: TASK.one });
    expect(within(taskNav).getByRole("link", { name: /Result/ })).toHaveTextContent("New content");
    expect(within(taskNav).getByRole("link", { name: /Sources/ })).not.toHaveTextContent("New content");
    // One mark shape in the app: a 6 px navy square, no radius.
    const mark = within(within(taskNav).getByRole("link", { name: /Result/ })).getByTestId("new-content-mark");
    expect(mark).toHaveClass("size-1.5", "bg-navy");
    expect(mark.className).not.toMatch(/rounded/);
  });

  it("never dots Sources, whatever lands (owner, round 8: the mark was not useful)", () => {
    renderShell(`/tasks/${TASK_ID}/history`);
    connect();
    feed(runStatus("running"));
    settle();
    feed(stageFrame("stage.completed", "screen", "Screening"));
    const taskNav = screen.getByRole("navigation", { name: TASK.one });
    expect(within(taskNav).getByRole("link", { name: /Sources/ })).not.toHaveTextContent("New content");
  });
});

describe("AppShell — the Sources tab opens on the step that has landed (owner, 2026-11-05)", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    taskState.isOwner = true;
    taskState.access = "full";
    taskState.latestRun = { status: "running" };
    sseState.handlers = null;
  });
  afterEach(() => {
    vi.useRealTimers();
    taskState.latestRun = null;
  });

  const sourcesLink = () =>
    within(screen.getByRole("navigation", { name: TASK.one })).getByRole("link", { name: /Sources/ });

  it("opens All sources, then Landscape once classified, then Themes once mapped", () => {
    renderShell(`/tasks/${TASK_ID}/history`);
    connect();
    feed(runStatus("running"), stageFrame("stage.started", "acquire", "Searching and screening"));
    expect(sourcesLink()).toHaveAttribute("href", `/tasks/${TASK_ID}/sources/all`);
    feed(
      stageFrame("stage.completed", "acquire", "Searching and screening"),
      stageFrame("stage.completed", "screen", "Searching and screening"),
      stageFrame("stage.started", "classify", "Classifying"),
    );
    expect(sourcesLink()).toHaveAttribute("href", `/tasks/${TASK_ID}/sources/all`);
    feed(stageFrame("stage.completed", "classify", "Classifying"));
    expect(sourcesLink()).toHaveAttribute("href", `/tasks/${TASK_ID}/sources/landscape`);
    feed(stageFrame("stage.started", "characterise", "Mapping"), stageFrame("stage.completed", "characterise", "Mapping"));
    expect(sourcesLink()).toHaveAttribute("href", `/tasks/${TASK_ID}/sources`);
  });

  it("opens Themes once the run has ended", () => {
    renderShell(`/tasks/${TASK_ID}/history`);
    connect();
    feed(runStatus("running"), stageFrame("stage.started", "acquire", "Searching and screening"));
    feed(runStatus("succeeded"));
    expect(sourcesLink()).toHaveAttribute("href", `/tasks/${TASK_ID}/sources`);
  });

  it("stays the current tab on every Sources view", () => {
    renderShell(`/tasks/${TASK_ID}/sources`);
    connect();
    feed(runStatus("running"), stageFrame("stage.started", "acquire", "Searching and screening"));
    // The link opens All sources, and the reader is on Themes: still Sources.
    expect(sourcesLink()).toHaveAttribute("href", `/tasks/${TASK_ID}/sources/all`);
    expect(sourcesLink()).toHaveAttribute("aria-current", "page");
    expect(sourcesLink()).toHaveClass("after:scale-x-100");
  });
});

describe("AppShell — the rail's Task Agent holds still (owner, round 8)", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    taskState.isOwner = true;
    taskState.access = "full";
    taskState.latestRun = { status: "running" };
    sseState.handlers = null;
  });
  afterEach(() => {
    vi.useRealTimers();
    taskState.latestRun = null;
  });

  // Owner, round 8: the rail's mark is the still fold mark, its name "Task
  // Agent", with no hover status and no timer, whatever the run is doing.
  it("keeps the still mark and the plain name on Sources and Result while a run is live", () => {
    const sources = renderShell(`/tasks/${TASK_ID}/sources`);
    connect();
    feed(runStatus("running"), stageFrame("stage.started", "acquire", "Searching"));
    const mark = screen.getByRole("button", { name: "Task Agent" });
    expect(mark.querySelector("[data-live-mark]")).toBeNull();
    expect(screen.queryByTestId("rail-elapsed")).toBeNull();
    sources.unmount();
    sseState.handlers = null;
    renderShell(`/tasks/${TASK_ID}/result`);
    connect();
    feed(runStatus("running"));
    expect(screen.getByRole("button", { name: "Task Agent" }).querySelector("[data-live-mark]")).toBeNull();
  });
});

describe("AppShell — the plan's links (task 058; owner, polish round 2)", () => {
  it("puts no Plan control in the task nav: the card and the Result tab carry the plan's links", async () => {
    renderShell(`/tasks/${TASK_ID}/sources`);
    await screen.findByRole("navigation", {}, { timeout: 3000 }).catch(() => undefined);
    expect(screen.queryByRole("button", { name: "Plan" })).toBeNull();
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
    expect(screen.queryByRole("menuitem", { name: "Sign out" })).not.toBeInTheDocument();
  });

  it("explains the BETA chip on hover", async () => {
    const user = userEvent.setup();
    renderShell("/new");
    await user.hover(screen.getByText("BETA"));
    expect(await screen.findByText(BETA_CHIP_HINT)).toBeInTheDocument();
  });

  it("underlines the active global nav item", () => {
    renderShell("/projects");
    expect(screen.getByRole("link", { name: "Projects" })).toHaveClass("after:scale-x-100");
    expect(screen.getByRole("link", { name: "New" })).not.toHaveClass("after:scale-x-100");
    expect(screen.getByRole("link", { name: TASK.many })).not.toHaveClass("after:scale-x-100");
  });

  it("opens Sign out from the account icon", async () => {
    const user = userEvent.setup();
    renderShell("/");
    await user.click(screen.getByRole("button", { name: "Account" }));
    await user.click(screen.getByRole("menuitem", { name: "Sign out" }));
    expect(authState.signOut).toHaveBeenCalledOnce();
  });

  it("opens the account menu with focus on its first item and the trigger pressed", async () => {
    const user = userEvent.setup();
    renderShell("/");
    const trigger = screen.getByRole("button", { name: "Account" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(trigger).toHaveAttribute("aria-haspopup", "menu");
    await user.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(trigger).toHaveAttribute("data-state", "open");
    expect(trigger).toHaveClass("data-[state=open]:bg-blue-tint-2");
    const menu = screen.getByRole("menu", { name: "Account" });
    const signOut = screen.getByRole("menuitem", { name: "Sign out" });
    expect(menu).toContainElement(signOut);
    expect(signOut).toHaveFocus();
    expect(signOut).toHaveClass("h-10", "text-meta", "hover:bg-blue-tint-2");
  });

  it("moves between items with the arrow keys and Home and End", async () => {
    const user = userEvent.setup();
    renderShell("/");
    await user.click(screen.getByRole("button", { name: "Account" }));
    const signOut = screen.getByRole("menuitem", { name: "Sign out" });
    await user.keyboard("{ArrowDown}");
    expect(signOut).toHaveFocus();
    await user.keyboard("{ArrowUp}{End}{Home}");
    expect(signOut).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(authState.signOut).toHaveBeenCalledOnce();
  });

  it("closes on Escape and on an outside press, giving focus back to the button", async () => {
    const user = userEvent.setup();
    renderShell("/");
    const trigger = screen.getByRole("button", { name: "Account" });
    await user.click(trigger);
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("menu")).not.toBeInTheDocument());
    expect(trigger).toHaveFocus();
    expect(trigger).toHaveAttribute("aria-expanded", "false");

    await user.click(trigger);
    expect(screen.getByRole("menu")).toBeInTheDocument();
    await user.click(document.body);
    await waitFor(() => expect(screen.queryByRole("menu")).not.toBeInTheDocument());
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

  it("shows the task's capability word in the header (task 044, X12)", () => {
    renderShell(`/tasks/${TASK_ID}/sources`);
    const taskNav = screen.getByRole("navigation", { name: "Task" });
    expect(taskNav).toHaveTextContent("Evidence search");
  });

  it("shows Options scoping for a scoping task", () => {
    taskState.capability = "options_scoping";
    renderShell(`/tasks/${TASK_ID}/sources`);
    const taskNav = screen.getByRole("navigation", { name: "Task" });
    expect(taskNav).toHaveTextContent("Options scoping");
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
    // TaskAgentPane's transcript scroll, not as a shell chrome status bar.
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

// Task 045 (S15): a scoping task's tabs stay on its `latest_run` and the
// longlist's existence, so a running child walk never opens or locks one.
// Task 058 (owner, 2026-11-05): the nav wordmark holds still during a run;
// the run's own live mark is the one turning logo on the screen.
describe("AppShell — the scoping readers (task 045)", () => {
  afterEach(() => {
    taskState.capability = "evidence_search";
    taskState.latestRun = null;
    taskState.activeRun = null;
    taskState.hasLonglist = false;
  });

  function logoAnimates() {
    const nav = screen.getByRole("navigation", { name: "App" });
    return nav.querySelector("svg g[transform]") !== null;
  }

  function tabLocks() {
    const bar = screen.getAllByRole("navigation", { name: TASK.one })[0];
    return ["Result", "Sources", "History"].map(
      (label) => within(bar).queryAllByRole("link", { name: label }).length > 0,
    );
  }

  it("a running child opens and locks no tab, and the nav logo holds still", () => {
    taskState.capability = "options_scoping";
    taskState.latestRun = { status: "succeeded" };
    taskState.hasLonglist = true;
    const first = renderShell(`/tasks/${TASK_ID}/sources`);
    expect(logoAnimates()).toBe(false);
    const before = tabLocks();
    expect(before).toEqual([true, true, true]);
    first.unmount();

    taskState.activeRun = { status: "running" };
    renderShell(`/tasks/${TASK_ID}/sources`);
    expect(logoAnimates()).toBe(false);
    expect(tabLocks()).toEqual(before);
  });

  it("holds the nav logo still while an Evidence search runs, inside the task and outside it", () => {
    taskState.latestRun = { status: "running" };
    const inside = renderShell(`/tasks/${TASK_ID}/sources`);
    expect(logoAnimates()).toBe(false);
    inside.unmount();
    renderShell("/");
    expect(logoAnimates()).toBe(false);
  });
});
