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
// kind before rendering would still pass a kind-grouped fixture.
const activeRows = [
  { id: "c1", kind: "chat", status: "active", closed_at: null, title: "Cost barriers", created_at: iso(1), entry_artefact_id: "a1", latest_turn_preview: { reply_snippet: "A short answer", user_message: "What changed?", at: iso(1) } },
  { id: "p1", kind: "planning", status: "active", closed_at: null, title: "Plan for Task Alpha", created_at: iso(2), entry_artefact_id: null, latest_turn_preview: null },
  { id: "p2", kind: "planning", status: "active", closed_at: iso(3), title: "Plan round 1", created_at: iso(3), entry_artefact_id: null, latest_turn_preview: null },
  { id: "p3", kind: "planning", status: "active", closed_at: iso(4), title: "Plan round 2", created_at: iso(4), entry_artefact_id: null, latest_turn_preview: null },
];
const archivedRows = [
  { id: "c2", kind: "chat", status: "archived", closed_at: null, title: "Old thread", created_at: iso(5), entry_artefact_id: null, latest_turn_preview: null },
];

vi.mock("react-router", () => ({ useNavigate: () => state.navigate }));
vi.mock("../../../api/queries", () => ({
  useConversations: (_id: string, query: { status: string }) => ({
    data: { data: query.status === "active" ? activeRows : archivedRows },
  }),
}));
vi.mock("./conversationState", () => ({ addOpenChatTab: state.addOpenChatTab, useActiveConversation: () => ({ setActiveConversation: state.setActiveConversation }), useConversationMutations: () => ({ archive: state.archive, unarchive: state.unarchive, update: state.update }) }));

describe("ChatsLibrary", () => {
  beforeEach(() => {
    state.update.mockClear();
    state.archive.mockClear();
    state.unarchive.mockClear();
    state.setActiveConversation.mockClear();
    state.addOpenChatTab.mockClear();
    state.navigate.mockClear();
  });

  it("shows previews, the report chip, and supports inline rename and archive on a chat row", async () => {
    const user = userEvent.setup();
    render(<ChatsLibrary taskId="p1" open onClose={vi.fn()} />);
    expect(screen.getByText("A short answer")).toBeInTheDocument();
    expect(screen.getByText("Report")).toBeInTheDocument();
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
    expect(screen.getByRole("heading", { name: "Archived" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Old thread" }));
    expect(state.unarchive).toHaveBeenCalledWith("c2");
    expect(state.addOpenChatTab).toHaveBeenCalledWith("p1", "c2");
    expect(state.setActiveConversation).toHaveBeenCalledWith("c2");
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("lists both conversation kinds, newest first, preserving the API's own order", () => {
    render(<ChatsLibrary taskId="p1" open onClose={vi.fn()} />);
    const titles = ["Cost barriers", "Plan for Task Alpha", "Plan round 1", "Plan round 2"];
    const rendered = screen.getAllByRole("button")
      .map((button) => button.textContent)
      .filter((text): text is string => text !== null && titles.includes(text));
    expect(rendered).toEqual(titles);
  });

  it("badges a planning row as planning, showing Open or Closed from closed_at", () => {
    render(<ChatsLibrary taskId="p1" open onClose={vi.fn()} />);
    expect(screen.getAllByText("Planning")).toHaveLength(3);
    expect(screen.getByText("Open")).toBeInTheDocument();
    // Several closed planning rows on one task is the expected state
    // (rubric 44) — both render, neither is deduped or dropped.
    expect(screen.getAllByText("Closed")).toHaveLength(2);
  });

  it("offers neither a rename nor an archive control on a planning row", () => {
    render(<ChatsLibrary taskId="p1" open onClose={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "Rename Plan for Task Alpha" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Archive Plan for Task Alpha" })).toBeNull();
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
    await user.click(screen.getByRole("button", { name: "Plan for Task Alpha" }));
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
