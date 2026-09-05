import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ChatsLibrary } from "./ChatsLibrary";

const state = vi.hoisted(() => ({
  update: vi.fn(async () => undefined),
  archive: vi.fn(),
  unarchive: vi.fn(async () => undefined),
  setActiveConversation: vi.fn(),
  addOpenChatTab: vi.fn(),
  navigate: vi.fn(),
}));

const now = Date.now();
const iso = (minutesAgo: number) => new Date(now - minutesAgo * 60_000).toISOString();

// Deliberately interleaved (not grouped by kind) — a bug that re-sorts by
// kind before rendering would still pass a kind-grouped fixture. Several
// planning lineages, one still open: the Task Agent selection rule and the
// "Earlier plan" label both need that shape (contract 038 § V8).
type Row = {
  id: string; kind: string; status: string; closed_at: string | null; title: string;
  created_at: string; entry_artefact_id: string | null;
  latest_turn_preview: { reply_snippet: string; user_message: string; at: string } | null;
};
const defaultActiveRows = (): Row[] => [
  { id: "c1", kind: "chat", status: "active", closed_at: null, title: "Cost barriers", created_at: iso(1), entry_artefact_id: "a1", latest_turn_preview: { reply_snippet: "A short answer", user_message: "What changed?", at: iso(1) } },
  { id: "p1", kind: "planning", status: "active", closed_at: null, title: "Plan for Task Alpha", created_at: iso(2), entry_artefact_id: null, latest_turn_preview: null },
  { id: "p2", kind: "planning", status: "active", closed_at: iso(3), title: "Plan round 1", created_at: iso(3), entry_artefact_id: null, latest_turn_preview: null },
  { id: "p3", kind: "planning", status: "active", closed_at: iso(4), title: "Plan round 2", created_at: iso(4), entry_artefact_id: null, latest_turn_preview: null },
];
const defaultArchivedRows = (): Row[] => [
  { id: "c2", kind: "chat", status: "archived", closed_at: null, title: "Old thread", created_at: iso(5), entry_artefact_id: null, latest_turn_preview: null },
];
let activeRows = defaultActiveRows();
let archivedRows = defaultArchivedRows();

vi.mock("react-router", () => ({ useNavigate: () => state.navigate }));
vi.mock("../../../api/queries", () => ({
  useConversations: (_id: string, query: { status: string }) => ({
    data: { data: query.status === "active" ? activeRows : archivedRows },
  }),
}));
vi.mock("./conversationState", async (importOriginal) => ({
  // `taskAgentConversationId` is the real selection rule under test here —
  // only the URL/mutation hooks are stubbed.
  ...(await importOriginal<typeof import("./conversationState")>()),
  addOpenChatTab: state.addOpenChatTab,
  useActiveConversation: () => ({ setActiveConversation: state.setActiveConversation }),
  useConversationMutations: () => ({ archive: state.archive, unarchive: state.unarchive, update: state.update }),
}));

describe("ChatsLibrary", () => {
  beforeEach(() => {
    state.update.mockClear();
    state.archive.mockClear();
    state.unarchive.mockClear();
    state.setActiveConversation.mockClear();
    state.addOpenChatTab.mockClear();
    state.navigate.mockClear();
    activeRows = defaultActiveRows();
    archivedRows = defaultArchivedRows();
  });

  it("shows title-only rows (no preview, no chips) and supports inline rename and archive on a chat row", async () => {
    const user = userEvent.setup();
    render(<ChatsLibrary taskId="p1" open onClose={vi.fn()} />);
    expect(screen.queryByText("A short answer")).toBeNull();
    expect(screen.queryByText("Report")).toBeNull();
    expect(screen.queryByText("Open")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Rename Cost barriers" }));
    await user.clear(screen.getByLabelText("Chat title"));
    await user.type(screen.getByLabelText("Chat title"), "Updated chat{Enter}");
    expect(state.update).toHaveBeenCalledWith("c1", { title: "Updated chat" });
    await user.click(screen.getByRole("button", { name: /^Archive / }));
    expect(state.archive).toHaveBeenCalledWith("c1");
  });

  it("lists archived chats under their own heading and restores one back into the active list", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<ChatsLibrary taskId="p1" open onClose={onClose} />);
    // Archived rows sit behind a disclosure that starts shut.
    const archived = screen.getByRole("heading", { name: "Archived" });
    expect(archived.closest("details")).not.toHaveAttribute("open");
    await user.click(archived);
    await user.click(screen.getByRole("button", { name: "Old thread" }));
    expect(state.unarchive).toHaveBeenCalledWith("c2");
    expect(state.addOpenChatTab).toHaveBeenCalledWith("p1", "c2");
    expect(state.setActiveConversation).toHaveBeenCalledWith("c2");
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("pins the Task Agent first, then keeps the API's own order for the rest", () => {
    render(<ChatsLibrary taskId="p1" open onClose={vi.fn()} />);
    const names = ["Cost barriers", "Task Agent", "Earlier plan"];
    const rendered = screen.getAllByRole("button")
      .map((button) => button.textContent)
      .filter((text): text is string => text !== null && names.includes(text));
    // p1 (the open planning lineage) is pinned above the date groups; the
    // chat and the two older lineages keep the order the API sent.
    expect(rendered).toEqual(["Task Agent", "Cost barriers", "Earlier plan", "Earlier plan"]);
  });

  it("names exactly one row the Task Agent and every older lineage an earlier plan (I8/A10)", () => {
    render(<ChatsLibrary taskId="p1" open onClose={vi.fn()} />);
    // The label is the only marker (fork F4): one row, one label, no chip.
    expect(screen.getAllByText("Task Agent")).toHaveLength(1);
    // Several closed planning rows on one task is the expected state
    // (rubric 44) — both render, neither is deduped or dropped.
    expect(screen.getAllByText("Earlier plan")).toHaveLength(2);
    expect(screen.queryByText("Planning")).toBeNull();
    expect(screen.queryByText("Open")).toBeNull();
    expect(screen.queryByText("Closed")).toBeNull();
  });

  it("falls back to the most recently closed lineage once the run has closed the open one", () => {
    activeRows = activeRows.filter((row) => row.id !== "p1");
    render(<ChatsLibrary taskId="p1" open onClose={vi.fn()} />);
    const rendered = screen.getAllByRole("button")
      .map((button) => button.textContent)
      .filter((text): text is string => text === "Task Agent" || text === "Earlier plan");
    // p2 closed 3 minutes ago, p3 four — the newer closure is the Task Agent.
    expect(rendered).toEqual(["Task Agent", "Earlier plan"]);
    expect(screen.getAllByText("Task Agent")).toHaveLength(1);
  });

  it("a non-owner's list is exactly the rows the API returned, only the labels differ (A9)", () => {
    // The listing is owner-relative server-side: a colleague's page carries
    // their own chats and no planning row at all. Nothing here filters,
    // hides or invents a row — and with no planning row, nothing is pinned.
    activeRows = [
      { id: "c9", kind: "chat", status: "active", closed_at: null, title: "Colleague question", created_at: iso(1), entry_artefact_id: null, latest_turn_preview: null },
    ];
    archivedRows = [];
    render(<ChatsLibrary taskId="p1" open onClose={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Colleague question" })).toBeInTheDocument();
    expect(screen.queryByText("Task Agent")).toBeNull();
    expect(screen.queryByText("Earlier plan")).toBeNull();
    expect(screen.queryByText("Planning")).toBeNull();
  });

  it("offers neither a rename nor an archive control on a planning row", () => {
    render(<ChatsLibrary taskId="p1" open onClose={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "Rename Plan for Task Alpha" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Archive Plan for Task Alpha" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Rename Task Agent" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Archive Task Agent" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Rename Plan round 1" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Archive Plan round 1" })).toBeNull();
  });

  it("still offers both a rename and an archive control on a chat row", () => {
    render(<ChatsLibrary taskId="p1" open onClose={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Rename Cost barriers" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Archive Cost barriers" })).toBeInTheDocument();
  });

  it("opens a planning row in the chat panel, not by navigating to Plan", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<ChatsLibrary taskId="proj-9" open onClose={onClose} />);
    await user.click(screen.getByRole("button", { name: "Task Agent" }));
    expect(state.setActiveConversation).toHaveBeenCalledWith("p1");
    expect(onClose).toHaveBeenCalledOnce();
    expect(state.addOpenChatTab).not.toHaveBeenCalled();
    expect(state.navigate).not.toHaveBeenCalled();
  });

  it("still opens a chat row in the panel when selected", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<ChatsLibrary taskId="p1" open onClose={onClose} />);
    await user.click(screen.getByRole("button", { name: "Cost barriers" }));
    expect(state.addOpenChatTab).toHaveBeenCalledWith("p1", "c1");
    expect(state.setActiveConversation).toHaveBeenCalledWith("c1");
    expect(state.navigate).not.toHaveBeenCalled();
    expect(onClose).toHaveBeenCalledOnce();
  });
});
