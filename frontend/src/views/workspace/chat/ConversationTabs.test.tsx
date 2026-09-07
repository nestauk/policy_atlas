import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConversationTabs } from "./ConversationTabs";

const state = vi.hoisted(() => ({
  archive: vi.fn(),
  create: vi.fn(async () => ({ id: "c2" })),
  setActiveConversation: vi.fn(),
  activeConversationId: "c1" as string,
  tabIds: ["c1"] as string[],
}));

vi.mock("../../../api/queries", () => ({ useConversations: () => ({ data: { data: [
  { id: "p1", kind: "planning", title: "Planning", status: "active", closed_at: null },
  { id: "c1", kind: "chat", title: "Barriers", status: "active" },
] } }) }));
vi.mock("./conversationState", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./conversationState")>();
  return {
    ...actual,
    openChatTabs: () => state.tabIds,
    addOpenChatTab: (_taskId: string, id: string) => {
      state.tabIds = [...state.tabIds.filter((value) => value !== id), id];
    },
    removeOpenChatTab: vi.fn(),
    useActiveConversation: () => ({
      activeConversationId: state.activeConversationId,
      setActiveConversation: state.setActiveConversation,
    }),
    useConversationMutations: () => ({ create: state.create, archive: state.archive }),
  };
});

describe("ConversationTabs", () => {
  beforeEach(() => {
    state.activeConversationId = "c1";
    state.tabIds = ["c1"];
    state.create.mockClear();
    state.archive.mockClear();
    state.setActiveConversation.mockClear();
  });

  it("renders planning, reuses the open blank-chat path, and archives a tab", async () => {
    const user = userEvent.setup();
    render(<ConversationTabs taskId="p1" planningClosed={false} onOpenLibrary={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Planning" })).toBeInTheDocument();
    expect(screen.getByText("Barriers")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "New chat" }));
    expect(state.create).toHaveBeenCalledOnce();
    await user.click(screen.getByRole("button", { name: "Archive Barriers" }));
    expect(state.archive).toHaveBeenCalledWith("c1");
  });

  it("selects an open tab and opens the chats library", async () => {
    const onOpenLibrary = vi.fn();
    const user = userEvent.setup();
    render(<ConversationTabs taskId="p1" planningClosed={false} onOpenLibrary={onOpenLibrary} />);
    await user.click(screen.getByRole("button", { name: "Barriers" }));
    expect(state.setActiveConversation).toHaveBeenCalledWith("c1");
    await user.click(screen.getByRole("button", { name: "Chats" }));
    expect(onOpenLibrary).toHaveBeenCalledOnce();
  });

  it("selects the planning conversation when the Planning tab is clicked", async () => {
    const user = userEvent.setup();
    render(<ConversationTabs taskId="p1" planningClosed={false} onOpenLibrary={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Planning" }));
    expect(state.setActiveConversation).toHaveBeenCalledWith("p1");
  });

  it("shows a New chat tab for an active follow-up that is not yet in the list", () => {
    state.activeConversationId = "c-new";
    state.tabIds = [];
    render(<ConversationTabs taskId="p1" planningClosed={false} onOpenLibrary={vi.fn()} />);
    expect(screen.getByText("New chat")).toBeInTheDocument();
  });
});
