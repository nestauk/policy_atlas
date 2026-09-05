import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ChatSidePanel } from "./ChatSidePanel";

const CHAT_ROW = { id: "c1", kind: "chat", status: "active", closed_at: null, title: "Cost barriers", created_at: new Date().toISOString(), entry_artefact_id: null, latest_turn_preview: null };
const PLAN_ROW = { id: "plan-1", kind: "planning", status: "active", closed_at: null, title: "Planning", created_at: new Date().toISOString(), entry_artefact_id: null, latest_turn_preview: null };

const state = vi.hoisted(() => ({
  activeConversationId: null as string | null,
  draftEntryArtefactId: null as string | null,
  setActiveConversation: vi.fn(),
  openDraftChat: vi.fn(),
  create: vi.fn(async () => ({ id: "c-new" })),
  navigate: vi.fn(),
  chatsResolved: true,
  rows: [] as unknown[],
  runStatus: undefined as string | undefined,
}));

vi.mock("react-router", () => ({ useNavigate: () => state.navigate }));
vi.mock("../../../api/queries", () => ({
  useConversations: () => ({
    data: { data: state.rows },
    isSuccess: state.chatsResolved,
  }),
  useArtefact: () => ({ data: { sections: [{ title: "Key findings" }] } }),
  // The result gate reads the task's latest run as well as the stream; the
  // stream mock carries the run state these tests vary.
  useTask: () => ({ data: undefined }),
}));
vi.mock("../../../store", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../../store")>()),
  useRunStream: () => ({ run: state.runStatus === undefined ? null : { status: state.runStatus }, stages: [] }),
}));
vi.mock("./conversationState", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./conversationState")>();
  return {
    ...actual,
    useActiveConversation: () => ({
      activeConversationId: state.activeConversationId,
      draftEntryArtefactId: state.draftEntryArtefactId,
      setActiveConversation: state.setActiveConversation,
      openDraftChat: state.openDraftChat,
    }),
    useConversationMutations: () => ({ create: state.create, archive: vi.fn() }),
  };
});
vi.mock("./ChatPane", () => ({
  ChatPane: ({ conversationId }: { conversationId: string }) => <div data-testid="chat-pane">{conversationId}</div>,
}));
vi.mock("./DraftChatPane", () => ({
  DraftChatPane: () => <div data-testid="draft-chat-pane" />,
}));
vi.mock("./ConversationList", () => ({
  ConversationList: ({ selectedId }: { selectedId: string | null }) => <div data-testid="conversation-list">{selectedId}</div>,
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

describe("ChatSidePanel", () => {
  beforeEach(() => {
    state.chatsResolved = true;
    state.rows = [CHAT_ROW];
    state.runStatus = "succeeded";
    state.draftEntryArtefactId = null;
    state.setActiveConversation.mockClear();
    state.openDraftChat.mockClear();
    state.create.mockClear();
  });

  it("renders the edge toggle when closed and opens the latest chat", async () => {
    state.activeConversationId = null;
    const user = userEvent.setup();
    render(<ChatSidePanel taskId="p1" isOwner />);
    expect(screen.queryByTestId("chat-pane")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Open the Agent" }));
    expect(state.setActiveConversation).toHaveBeenCalledWith("c1");
    expect(state.create).not.toHaveBeenCalled();
  });

  it("disables the launcher until the chats query resolves", async () => {
    state.activeConversationId = null;
    state.chatsResolved = false;
    const user = userEvent.setup();
    render(<ChatSidePanel taskId="p1" isOwner />);
    const launcher = screen.getByRole("button", { name: "Open the Agent" });
    expect(launcher).toBeDisabled();
    await user.click(launcher);
    expect(state.setActiveConversation).not.toHaveBeenCalled();
  });

  it("shut, it is the Agent tab's rail: New chat opens a draft and the mark opens the Task Agent", async () => {
    state.activeConversationId = null;
    state.rows = [PLAN_ROW, CHAT_ROW];
    const user = userEvent.setup();
    render(<ChatSidePanel taskId="p1" isOwner />);
    const rail = screen.getByRole("complementary", { name: "Chats" });
    await user.click(within(rail).getByRole("button", { name: "New chat" }));
    expect(state.openDraftChat).toHaveBeenCalledWith(null);
    await user.click(within(rail).getByRole("button", { name: "Task Agent" }));
    expect(state.setActiveConversation).toHaveBeenCalledWith("plan-1");
    expect(state.create).not.toHaveBeenCalled();
  });

  it("ignores a newer planning conversation when picking the latest chat to open", async () => {
    state.activeConversationId = null;
    state.rows = [PLAN_ROW, CHAT_ROW];
    const user = userEvent.setup();
    render(<ChatSidePanel taskId="p1" isOwner />);
    await user.click(screen.getByRole("button", { name: "Open the Agent" }));
    expect(state.setActiveConversation).toHaveBeenCalledWith("c1");
  });

  it("opens the Task Agent when no chat exists yet — never creates a chat on open (038 V8)", async () => {
    state.activeConversationId = null;
    state.rows = [PLAN_ROW];
    const user = userEvent.setup();
    render(<ChatSidePanel taskId="p1" isOwner />);
    await user.click(screen.getByRole("button", { name: "Open the Agent" }));
    expect(state.create).not.toHaveBeenCalled();
    expect(state.setActiveConversation).toHaveBeenCalledWith("plan-1");
  });

  it("renders the open panel with the header naming the chat, toggles the shared list, and closes", async () => {
    state.activeConversationId = "c1";
    const user = userEvent.setup();
    render(<ChatSidePanel taskId="p1" isOwner />);
    expect(screen.getByRole("complementary", { name: "Agent" })).toBeInTheDocument();
    expect(screen.getByTestId("chat-pane")).toHaveTextContent("c1");
    expect(screen.getByText("Cost barriers")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Chats" }));
    expect(screen.getByTestId("conversation-list")).toHaveTextContent("c1");
    expect(screen.queryByTestId("chat-pane")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Chats" }));
    expect(screen.getByTestId("chat-pane")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Close sidebar" }));
    expect(state.setActiveConversation).toHaveBeenCalledWith(null);
  });

  it("shows the planning thread, named Task Agent, when the URL names the planning conversation", () => {
    state.activeConversationId = "plan-1";
    state.rows = [PLAN_ROW, CHAT_ROW];
    render(<ChatSidePanel taskId="p1" isOwner />);
    expect(screen.getByTestId("planning-pane")).toBeInTheDocument();
    expect(screen.getByText("Task Agent")).toBeInTheDocument();
    expect(screen.queryByTestId("chat-pane")).not.toBeInTheDocument();
  });

  it("threads isOwner=false into the planning duplicate (task 033 phase 10c, contract § 11 / rubric 37)", () => {
    state.activeConversationId = "plan-1";
    state.rows = [PLAN_ROW, CHAT_ROW];
    render(<ChatSidePanel taskId="p1" isOwner={false} />);
    expect(screen.getByTestId("planning-pane")).toHaveAttribute("data-is-owner", "false");
  });

  it("New chat opens a draft — nothing is created — and is disabled until the task has a result", async () => {
    state.activeConversationId = "c1";
    const user = userEvent.setup();
    const { unmount } = render(<ChatSidePanel taskId="p1" isOwner />);
    await user.click(screen.getByRole("button", { name: "New chat" }));
    expect(state.openDraftChat).toHaveBeenCalledWith(null);
    expect(state.create).not.toHaveBeenCalled();
    unmount();

    state.runStatus = "running";
    render(<ChatSidePanel taskId="p1" isOwner />);
    const newChat = screen.getByRole("button", { name: "New chat" });
    expect(newChat).toBeDisabled();
    // The reason is the (quick) tooltip on the disabled button's wrapper.
    await user.hover(newChat.parentElement as HTMLElement);
    expect(await screen.findByRole("tooltip")).toHaveTextContent("available once the task has a result");
  });

  it("renders the draft pane while the URL names a draft chat", () => {
    state.activeConversationId = "new";
    render(<ChatSidePanel taskId="p1" isOwner />);
    expect(screen.getByTestId("draft-chat-pane")).toBeInTheDocument();
    expect(screen.getByText("New chat")).toBeInTheDocument();
    expect(screen.queryByTestId("chat-pane")).not.toBeInTheDocument();
  });
});
