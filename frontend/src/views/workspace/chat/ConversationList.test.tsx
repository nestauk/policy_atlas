import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConversationList } from "./ConversationList";
import { DRAFT_CHAT_ID, PLANNING_TAB_ID } from "./conversationState";

const state = vi.hoisted(() => ({
  update: vi.fn(async () => undefined),
  archive: vi.fn(),
  unarchive: vi.fn(async () => undefined),
  onOpen: vi.fn(),
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
  { id: "c1", kind: "chat", status: "active", closed_at: null, title: "Cost barriers", created_at: iso(1), entry_artefact_id: "a1", latest_turn_preview: { reply_snippet: "A short answer", user_message: "Why?", at: iso(1) } },
  { id: "p1", kind: "planning", status: "active", closed_at: null, title: "Plan for Task Alpha", created_at: iso(2), entry_artefact_id: null, latest_turn_preview: null },
  { id: "p2", kind: "planning", status: "active", closed_at: iso(3), title: "Plan round 1", created_at: iso(3), entry_artefact_id: null, latest_turn_preview: null },
  { id: "p3", kind: "planning", status: "active", closed_at: iso(4), title: "Plan round 2", created_at: iso(4), entry_artefact_id: null, latest_turn_preview: null },
];
const defaultArchivedRows = (): Row[] => [
  { id: "c2", kind: "chat", status: "archived", closed_at: null, title: "Old thread", created_at: iso(5), entry_artefact_id: null, latest_turn_preview: null },
];
let activeRows = defaultActiveRows();
let archivedRows = defaultArchivedRows();

vi.mock("../../../api/queries", () => ({
  useConversations: (_id: string, query: { status: string }) => ({
    data: { data: query.status === "active" ? activeRows : archivedRows },
  }),
}));
vi.mock("./conversationState", async (importOriginal) => ({
  // `taskAgentConversationId` is the real selection rule under test here —
  // only the mutation hook is stubbed.
  ...(await importOriginal<typeof import("./conversationState")>()),
  useConversationMutations: () => ({ archive: state.archive, unarchive: state.unarchive, update: state.update }),
}));

const renderList = (selectedId: string | null = null) =>
  render(<ConversationList taskId="p1" onOpen={state.onOpen} selectedId={selectedId} />);

const rowNames = () =>
  screen.getAllByRole("button")
    .map((button) => button.textContent)
    .filter((text): text is string => text !== null && ["Task Agent", "Cost barriers", "Earlier plan", "New chat"].includes(text));

describe("ConversationList", () => {
  beforeEach(() => {
    state.update.mockClear();
    state.archive.mockClear();
    state.unarchive.mockClear();
    state.onOpen.mockClear();
    activeRows = defaultActiveRows();
    archivedRows = defaultArchivedRows();
  });

  it("shows title-only rows (no preview, no chips) and supports inline rename and archive on a chat row", async () => {
    const user = userEvent.setup();
    renderList();
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

  it("lists archived chats behind a shut disclosure and restores one back into the active list", async () => {
    const user = userEvent.setup();
    renderList();
    const archived = screen.getByRole("heading", { name: "Archived" });
    expect(archived.closest("details")).not.toHaveAttribute("open");
    await user.click(archived);
    await user.click(screen.getByRole("button", { name: "Old thread" }));
    expect(state.unarchive).toHaveBeenCalledWith("c2");
    expect(state.onOpen).toHaveBeenCalledWith(expect.objectContaining({ id: "c2" }));
  });

  it("pins the Task Agent first, then keeps the API's own order for the rest", () => {
    renderList();
    // p1 (the open planning lineage) is pinned above the date groups; the
    // chat and the two older lineages keep the order the API sent.
    expect(rowNames()).toEqual(["Task Agent", "Cost barriers", "Earlier plan", "Earlier plan"]);
  });

  it("names exactly one row the Task Agent and every older lineage an earlier plan (I8/A10)", () => {
    renderList();
    // The label is the only marker (fork F4): one row, one label, no chip.
    expect(screen.getAllByText("Task Agent")).toHaveLength(1);
    // Several closed planning rows on one task is the expected state
    // (rubric 44) — both render, neither is deduped or dropped.
    expect(screen.getAllByText("Earlier plan")).toHaveLength(2);
    expect(screen.queryByText("Planning")).toBeNull();
    expect(screen.queryByText("Closed")).toBeNull();
  });

  it("falls back to the most recently closed lineage once the run has closed the open one", () => {
    activeRows = activeRows.filter((row) => row.id !== "p1");
    renderList();
    // p2 closed 3 minutes ago, p3 four — the newer closure is the Task Agent.
    expect(rowNames()).toEqual(["Task Agent", "Cost barriers", "Earlier plan"]);
    expect(screen.getAllByText("Task Agent")).toHaveLength(1);
  });

  it("still lists the Task Agent when the listing carries no planning row at all (a completed task)", async () => {
    // A run closes the planning lineage, and the active listing then has no
    // planning row — the Task Agent must still be there to select.
    const user = userEvent.setup();
    activeRows = activeRows.filter((row) => row.kind !== "planning");
    renderList(PLANNING_TAB_ID);
    const taskAgent = screen.getByRole("button", { name: "Task Agent" });
    expect(rowNames()[0]).toBe("Task Agent");
    expect(taskAgent).toHaveAttribute("aria-current", "true");
    await user.click(taskAgent);
    expect(state.onOpen).toHaveBeenCalledWith(expect.objectContaining({ id: PLANNING_TAB_ID, kind: "planning" }));
  });

  it("shows a selected New chat row while a draft chat is open, with no rename or archive on it", () => {
    renderList(DRAFT_CHAT_ID);
    expect(rowNames()).toEqual(["Task Agent", "New chat", "Cost barriers", "Earlier plan", "Earlier plan"]);
    expect(screen.getByRole("button", { name: "New chat" })).toHaveAttribute("aria-current", "true");
    expect(screen.queryByRole("button", { name: "Rename New chat" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Archive New chat" })).toBeNull();
  });

  it("a non-owner's list is exactly the rows the API returned plus the Task Agent, only the labels differ (A9)", () => {
    // The listing is owner-relative server-side: a colleague's page carries
    // their own chats and no planning row at all. Nothing here filters,
    // hides or invents a chat.
    activeRows = [
      { id: "c9", kind: "chat", status: "active", closed_at: null, title: "Colleague question", created_at: iso(1), entry_artefact_id: null, latest_turn_preview: null },
    ];
    archivedRows = [];
    renderList();
    expect(screen.getByRole("button", { name: "Colleague question" })).toBeInTheDocument();
    expect(screen.getAllByText("Task Agent")).toHaveLength(1);
    expect(screen.queryByText("Earlier plan")).toBeNull();
    expect(screen.queryByText("Planning")).toBeNull();
    expect(screen.queryByRole("heading", { name: "Archived" })).toBeNull();
  });

  it("offers neither a rename nor an archive control on a planning row", () => {
    renderList();
    expect(screen.queryByRole("button", { name: "Rename Plan for Task Alpha" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Archive Plan for Task Alpha" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Rename Task Agent" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Archive Task Agent" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Rename Plan round 1" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Archive Plan round 1" })).toBeNull();
  });

  it("still offers both a rename and an archive control on a chat row", () => {
    renderList();
    expect(screen.getByRole("button", { name: "Rename Cost barriers" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Archive Cost barriers" })).toBeInTheDocument();
  });

  it("hands the chosen row to the caller — a planning row as itself, a chat as itself", async () => {
    const user = userEvent.setup();
    renderList();
    await user.click(screen.getByRole("button", { name: "Task Agent" }));
    expect(state.onOpen).toHaveBeenLastCalledWith(expect.objectContaining({ id: "p1", kind: "planning" }));
    await user.click(screen.getByRole("button", { name: "Cost barriers" }));
    expect(state.onOpen).toHaveBeenLastCalledWith(expect.objectContaining({ id: "c1", kind: "chat" }));
  });
});
