import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ChatSidePanel } from "./ChatSidePanel";

const state = vi.hoisted(() => ({
  activeConversationId: null as string | null,
  setActiveConversation: vi.fn(),
  addOpenChatTab: vi.fn(),
  create: vi.fn(async () => ({ id: "c-new" })),
  navigate: vi.fn(),
}));

vi.mock("react-router", () => ({ useNavigate: () => state.navigate }));
vi.mock("../../../api/queries", () => ({
  useConversations: () => ({
    data: { data: [{ id: "c1", title: "Cost barriers", created_at: new Date().toISOString(), entry_artefact_id: null, latest_turn_preview: null }] },
  }),
  useArtefact: () => ({ data: { sections: [{ title: "Key findings" }] } }),
}));
vi.mock("./conversationState", () => ({
  addOpenChatTab: state.addOpenChatTab,
  useActiveConversation: () => ({
    activeConversationId: state.activeConversationId,
    setActiveConversation: state.setActiveConversation,
  }),
  useConversationMutations: () => ({ create: state.create }),
}));
vi.mock("./ChatPane", () => ({
  ChatPane: ({ conversationId }: { conversationId: string }) => <div data-testid="chat-pane">{conversationId}</div>,
}));
vi.mock("./ChatsLibrary", () => ({
  ChatsLibrary: ({ open }: { open: boolean }) => (open ? <div data-testid="library" /> : null),
}));

describe("ChatSidePanel", () => {
  it("renders the edge toggle when closed and opens the latest chat", async () => {
    state.activeConversationId = null;
    const user = userEvent.setup();
    render(<ChatSidePanel projectId="p1" />);
    expect(screen.queryByTestId("chat-pane")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Open chat" }));
    expect(state.addOpenChatTab).toHaveBeenCalledWith("p1", "c1");
    expect(state.setActiveConversation).toHaveBeenCalledWith("c1");
  });

  it("renders the open panel with header actions when the URL names a chat", async () => {
    state.activeConversationId = "c1";
    const user = userEvent.setup();
    render(<ChatSidePanel projectId="p1" />);
    expect(screen.getByRole("complementary", { name: "Project chat" })).toBeInTheDocument();
    expect(screen.getByTestId("chat-pane")).toHaveTextContent("c1");
    expect(screen.getByText("Cost barriers")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Chats" }));
    expect(screen.getByTestId("library")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Close chat panel" }));
    expect(state.setActiveConversation).toHaveBeenCalledWith(null);
  });

  it("creates a blank chat from the new-chat action when none is reusable", async () => {
    state.activeConversationId = "c1";
    const user = userEvent.setup();
    render(<ChatSidePanel projectId="p1" />);
    await user.click(screen.getByRole("button", { name: "New chat" }));
    expect(state.create).toHaveBeenCalledWith(null);
  });
});
