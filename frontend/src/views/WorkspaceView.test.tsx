import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WorkspaceView } from "./WorkspaceView";

/**
 * Two things are proved here.
 *
 * The URL leg (task 033 phase 10c, contract § 11 / rubric 37): the Agent
 * route (`/tasks/:taskId`) is never wrapped in `LifecycleRoute` — it's open
 * at every run state — so `is_owner` reaching its children is the ONLY
 * defence against a non-owner reaching a mutation surface by address.
 *
 * The two-column shape (038 V8, owner ruling 2026-09-05): the sidebar lists
 * the Task's conversations with one Task Agent pinned first, and the main
 * column shows whichever the `?chat=` param names.
 *
 * `PlanningPane`, `PlanDocument` and `ChatPane` are mocked to prop echoes —
 * each is covered thoroughly in its own file — so this proves the wiring:
 * which pane is mounted, and what ownership it is handed.
 */
const taskState = vi.hoisted(() => ({ isOwner: true }));
const state = vi.hoisted(() => ({
  create: vi.fn(async () => ({ id: "c-new" })),
  archive: vi.fn(),
  unarchive: vi.fn(async () => undefined),
  update: vi.fn(async () => undefined),
}));

const iso = (minutesAgo: number) => new Date(Date.now() - minutesAgo * 60_000).toISOString();
// One open planning lineage, one closed, one chat — the shape invariant I8
// needs: exactly one Task Agent, the older lineage an "Earlier plan".
const activeRows = [
  { id: "c1", kind: "chat", status: "active", closed_at: null, title: "Cost barriers", created_at: iso(1), entry_artefact_id: null, latest_turn_preview: null },
  { id: "p1", kind: "planning", status: "active", closed_at: null, title: "Plan for Task Alpha", created_at: iso(2), entry_artefact_id: null, latest_turn_preview: null },
  { id: "p0", kind: "planning", status: "active", closed_at: iso(3), title: "Plan round 1", created_at: iso(3), entry_artefact_id: null, latest_turn_preview: null },
];

vi.mock("../api/queries", () => ({
  useTask: () => ({
    data: {
      task_id: "11111111-1111-1111-1111-111111111111",
      name: "Acme task",
      is_owner: taskState.isOwner,
      latest_run: null,
    },
    isError: false,
    error: null,
  }),
  useConversations: (_taskId: string, query: { status: string }) => ({
    data: { data: query.status === "active" ? activeRows : [] },
  }),
  useArtefact: () => ({ data: { sections: [{ title: "Key findings" }] } }),
}));
vi.mock("../store", () => ({
  useRunStream: () => ({ run: null, stages: [], pendingCheckIn: null, decisions: [], plan: null }),
}));
vi.mock("./workspace/chat/conversationState", async (importOriginal) => ({
  // The selection rule and the URL param are the subject — only the
  // mutations are stubbed.
  ...(await importOriginal<typeof import("./workspace/chat/conversationState")>()),
  useConversationMutations: () => state,
}));
vi.mock("./workspace/PlanningPane", () => ({
  PlanningPane: ({ isOwner, onReviewPlan }: { isOwner: boolean; onReviewPlan?: () => void }) => (
    <div>
      <span data-testid="planning-pane-is-owner">{String(isOwner)}</span>
      <button type="button" onClick={onReviewPlan}>
        Open plan (test)
      </button>
    </div>
  ),
}));
vi.mock("./workspace/PlanDocument", () => ({
  PlanDocument: ({ readOnly }: { readOnly?: boolean }) => (
    <div data-testid="plan-document-read-only">{String(readOnly ?? false)}</div>
  ),
}));
vi.mock("./workspace/chat/ChatPane", () => ({
  ChatPane: ({ conversationId }: { conversationId: string }) => (
    <div data-testid="chat-pane">{conversationId}</div>
  ),
}));

function SearchProbe() {
  return <span data-testid="search">{useLocation().search}</span>;
}

function renderAtAgentTab(search = "") {
  return render(
    <MemoryRouter initialEntries={[`/tasks/11111111-1111-1111-1111-111111111111${search}`]}>
      <Routes>
        <Route
          path="/tasks/:taskId"
          element={
            <>
              <WorkspaceView />
              <SearchProbe />
            </>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

const sidebar = () => screen.getByRole("complementary", { name: "Chats" });

describe("WorkspaceView — the URL leg (task 033 phase 10c, contract § 11 / rubric 37)", () => {
  beforeEach(() => {
    taskState.isOwner = true;
    sessionStorage.clear();
    state.create.mockClear();
  });

  it("owner: reaches the Agent route with the mutation surface live, no redirect", () => {
    taskState.isOwner = true;
    renderAtAgentTab();
    expect(screen.getByTestId("planning-pane-is-owner")).toHaveTextContent("true");
  });

  it("non-owner: reaches the SAME route by address (not redirected) with the read-only variant", async () => {
    taskState.isOwner = false;
    const user = userEvent.setup();
    renderAtAgentTab();
    // Reachable, not bounced to an error page or elsewhere — `LifecycleRoute`
    // never wraps this route, so a redirect here would have to come from
    // WorkspaceView itself, and it doesn't.
    expect(screen.getByTestId("planning-pane-is-owner")).toHaveTextContent("false");

    // The plan document opened from here (PlanCard's "Review the plan",
    // read action) must render its already-tested read-only variant too.
    await user.click(screen.getByRole("button", { name: "Open plan (test)" }));
    expect(screen.getByTestId("plan-document-read-only")).toHaveTextContent("true");
  });
});

describe("WorkspaceView — the Agent tab is two columns (038 V8, owner ruling 2026-09-05)", () => {
  beforeEach(() => {
    taskState.isOwner = true;
    sessionStorage.clear();
    state.create.mockClear();
  });

  it("lists the Task's conversations in an always-visible sidebar, the Task Agent pinned first", () => {
    renderAtAgentTab();
    const names = ["Task Agent", "Cost barriers", "Earlier plan"];
    const rendered = within(sidebar())
      .getAllByRole("button")
      .map((button) => button.textContent)
      .filter((text): text is string => text !== null && names.includes(text));
    expect(rendered).toEqual(["Task Agent", "Cost barriers", "Earlier plan"]);
    // Exactly one row is the Task Agent (I8 / A10); the older closed
    // lineage is an earlier plan and no chat is called "Planning".
    expect(within(sidebar()).getAllByText("Task Agent")).toHaveLength(2); // name + chip
    expect(within(sidebar()).getAllByText("Earlier plan")).toHaveLength(2);
    expect(within(sidebar()).queryByText("Planning")).toBeNull();
  });

  it("shows the planning pane in the main column by default — no ?chat= is the Task Agent", () => {
    renderAtAgentTab();
    expect(screen.getByTestId("planning-pane-is-owner")).toBeInTheDocument();
    expect(screen.queryByTestId("chat-pane")).not.toBeInTheDocument();
  });

  it("swaps the main column to a chat when one is chosen, and shuts the plan rail", async () => {
    const user = userEvent.setup();
    renderAtAgentTab();
    await user.click(screen.getByRole("button", { name: "Open plan (test)" }));
    expect(screen.getByTestId("plan-document-read-only")).toBeInTheDocument();

    await user.click(within(sidebar()).getByRole("button", { name: "Cost barriers" }));
    expect(screen.getByTestId("chat-pane")).toHaveTextContent("c1");
    expect(screen.queryByTestId("planning-pane-is-owner")).not.toBeInTheDocument();
    // The rail belongs to the plan, not to a chat.
    expect(screen.queryByTestId("plan-document-read-only")).not.toBeInTheDocument();
    expect(screen.getByTestId("search")).toHaveTextContent("?chat=c1");
  });

  it("opens the chat a ?chat= deep link names, the same param the other tabs' overlay uses", () => {
    renderAtAgentTab("?chat=c1");
    expect(screen.getByTestId("chat-pane")).toHaveTextContent("c1");
    expect(screen.queryByTestId("planning-pane-is-owner")).not.toBeInTheDocument();
  });

  it("restores the planning pane and clears ?chat= when the Task Agent is chosen", async () => {
    const user = userEvent.setup();
    renderAtAgentTab("?chat=c1");
    await user.click(within(sidebar()).getByRole("button", { name: "Task Agent" }));
    expect(screen.getByTestId("planning-pane-is-owner")).toBeInTheDocument();
    expect(screen.queryByTestId("chat-pane")).not.toBeInTheDocument();
    expect(screen.getByTestId("search")).toHaveTextContent("");
    expect(screen.getByTestId("search").textContent).not.toContain("chat=");
  });

  it("reads a planning id in the param as the Task Agent, never as a second thread", () => {
    renderAtAgentTab("?chat=p0");
    expect(screen.getByTestId("planning-pane-is-owner")).toBeInTheDocument();
    expect(screen.queryByTestId("chat-pane")).not.toBeInTheDocument();
  });

  it("creates and opens a chat from the sidebar's New chat action", async () => {
    const user = userEvent.setup();
    renderAtAgentTab();
    await user.click(within(sidebar()).getByRole("button", { name: "New chat" }));
    expect(state.create).toHaveBeenCalledWith(null);
    expect(screen.getByTestId("search")).toHaveTextContent("?chat=c-new");
  });

  it("a non-owner sees the same rows under the same labels, with the surface still read-only (A9)", async () => {
    taskState.isOwner = false;
    const user = userEvent.setup();
    renderAtAgentTab();
    // Nothing in this view filters the listing — it renders what the
    // owner-relative API returned, labels and all.
    const names = ["Task Agent", "Cost barriers", "Earlier plan"];
    const rendered = within(sidebar())
      .getAllByRole("button")
      .map((button) => button.textContent)
      .filter((text): text is string => text !== null && names.includes(text));
    expect(rendered).toEqual(["Task Agent", "Cost barriers", "Earlier plan"]);
    expect(screen.getByTestId("planning-pane-is-owner")).toHaveTextContent("false");
    await user.click(screen.getByRole("button", { name: "Open plan (test)" }));
    expect(screen.getByTestId("plan-document-read-only")).toHaveTextContent("true");
  });
});
