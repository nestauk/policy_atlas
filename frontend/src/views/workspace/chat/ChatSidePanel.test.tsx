import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ChatSidePanel } from "./ChatSidePanel";

const CHAT_ROW = { id: "c1", kind: "chat", status: "active", closed_at: null, title: "Cost barriers", created_at: new Date().toISOString(), entry_artefact_id: null, latest_turn_preview: null };
const PLAN_ROW = { id: "plan-1", kind: "planning", status: "active", closed_at: null, title: "Planning", created_at: new Date().toISOString(), entry_artefact_id: null, latest_turn_preview: null };

const state = vi.hoisted(() => ({
  activeConversationId: null as string | null,
  setActiveConversation: vi.fn(),
  addOpenChatTab: vi.fn(),
  create: vi.fn(async () => ({ id: "c-new" })),
  navigate: vi.fn(),
  chatsResolved: true,
  rows: [] as unknown[],
}));

vi.mock("react-router", () => ({ useNavigate: () => state.navigate }));
vi.mock("../../../api/queries", () => ({
  useConversations: () => ({
    data: { data: state.rows },
    isSuccess: state.chatsResolved,
  }),
  useArtefact: () => ({ data: { sections: [{ title: "Key findings" }] } }),
}));
vi.mock("./conversationState", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./conversationState")>();
  return {
    ...actual,
    addOpenChatTab: state.addOpenChatTab,
    openChatTabs: () => ["c1"],
    removeOpenChatTab: vi.fn(),
    useActiveConversation: () => ({
      activeConversationId: state.activeConversationId,
      setActiveConversation: state.setActiveConversation,
    }),
    useConversationMutations: () => ({ create: state.create, archive: vi.fn() }),
  };
});
vi.mock("./ChatPane", () => ({
  ChatPane: ({ conversationId }: { conversationId: string }) => <div data-testid="chat-pane">{conversationId}</div>,
}));
vi.mock("../PlanningPane", () => ({
  // Task 033 phase 10c (contract § 11 / rubric 37): echoes the prop back so
  // the "ChatSidePanel duplicate" the rubric names can be checked for
  // threading `isOwner` through to the planning surface without re-testing
  // PlanningPane's own read-only rendering here (that's PlanningPane.test.tsx).
  PlanningPane: ({ isOwner }: { isOwner: boolean }) => (
    <div data-testid="planning-pane" data-is-owner={String(isOwner)} />
  ),
}));
vi.mock("./ChatsLibrary", () => ({
  ChatsLibrary: ({ open }: { open: boolean }) => (open ? <div data-testid="library" /> : null),
}));

describe("ChatSidePanel", () => {
  beforeEach(() => {
    state.chatsResolved = true;
    state.rows = [CHAT_ROW];
    state.setActiveConversation.mockClear();
    state.addOpenChatTab.mockClear();
    state.create.mockClear();
  });

  it("renders the edge toggle when closed and opens the latest chat", async () => {
    state.activeConversationId = null;
    const user = userEvent.setup();
    render(<ChatSidePanel taskId="p1" isOwner />);
    expect(screen.queryByTestId("chat-pane")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Open the Agent" }));
    expect(state.addOpenChatTab).toHaveBeenCalledWith("p1", "c1");
    expect(state.setActiveConversation).toHaveBeenCalledWith("c1");
  });

  it("disables the launcher until the chats query resolves, so a fast click can't POST a blank chat", async () => {
    state.activeConversationId = null;
    state.chatsResolved = false;
    const user = userEvent.setup();
    render(<ChatSidePanel taskId="p1" isOwner />);
    const launcher = screen.getByRole("button", { name: "Open the Agent" });
    expect(launcher).toBeDisabled();
    await user.click(launcher);
    expect(state.create).not.toHaveBeenCalled();
    expect(state.setActiveConversation).not.toHaveBeenCalled();
  });

  it("ignores a newer planning conversation when picking the latest chat to open — the launcher opens a follow-up chat", async () => {
    state.activeConversationId = null;
    state.rows = [PLAN_ROW, CHAT_ROW];
    const user = userEvent.setup();
    render(<ChatSidePanel taskId="p1" isOwner />);
    await user.click(screen.getByRole("button", { name: "Open the Agent" }));
    expect(state.addOpenChatTab).toHaveBeenCalledWith("p1", "c1");
    expect(state.setActiveConversation).toHaveBeenCalledWith("c1");
  });

  it("creates a follow-up chat when the launcher opens and none exist yet", async () => {
    state.activeConversationId = null;
    state.rows = [PLAN_ROW];
    const user = userEvent.setup();
    render(<ChatSidePanel taskId="p1" isOwner />);
    await user.click(screen.getByRole("button", { name: "Open the Agent" }));
    expect(state.create).toHaveBeenCalledWith(null);
    expect(state.addOpenChatTab).toHaveBeenCalledWith("p1", "c-new");
    expect(state.setActiveConversation).toHaveBeenCalledWith("c-new");
  });

  it("renders the open panel with the conversation strip when the URL names a chat", async () => {
    state.activeConversationId = "c1";
    const user = userEvent.setup();
    render(<ChatSidePanel taskId="p1" isOwner />);
    expect(screen.getByRole("complementary", { name: "Agent" })).toBeInTheDocument();
    expect(screen.getByTestId("chat-pane")).toHaveTextContent("c1");
    expect(screen.getByRole("button", { name: "Task Agent" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Chats" }));
    expect(screen.getByTestId("library")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Close chat panel" }));
    expect(state.setActiveConversation).toHaveBeenCalledWith(null);
  });

  it("shows the planning thread when the strip's Task Agent tab is selected", () => {
    state.activeConversationId = "plan-1";
    state.rows = [PLAN_ROW, CHAT_ROW];
    render(<ChatSidePanel taskId="p1" isOwner />);
    expect(screen.getByTestId("planning-pane")).toBeInTheDocument();
    expect(screen.queryByTestId("chat-pane")).not.toBeInTheDocument();
  });

  it("threads isOwner=false into the planning duplicate (task 033 phase 10c, contract § 11 / rubric 37)", () => {
    state.activeConversationId = "plan-1";
    state.rows = [PLAN_ROW, CHAT_ROW];
    render(<ChatSidePanel taskId="p1" isOwner={false} />);
    expect(screen.getByTestId("planning-pane")).toHaveAttribute("data-is-owner", "false");
  });
});
