import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ConversationTabs } from "./ConversationTabs";

const state = vi.hoisted(() => ({ archive: vi.fn(), create: vi.fn(async () => ({ id: "c2" })), setActiveConversation: vi.fn() }));

vi.mock("../../../api/queries", () => ({ useConversations: () => ({ data: { data: [{ id: "c1", title: "Barriers", status: "active" }] } }) }));
vi.mock("./conversationState", () => ({ openChatTabs: () => ["c1"], addOpenChatTab: vi.fn(), removeOpenChatTab: vi.fn(), useActiveConversation: () => ({ activeConversationId: "c1", setActiveConversation: state.setActiveConversation }), useConversationMutations: () => ({ create: state.create, archive: state.archive }) }));

describe("ConversationTabs", () => {
  it("renders planning, reuses the open blank-chat path, and archives a tab", async () => {
    const user = userEvent.setup();
    render(<ConversationTabs projectId="p1" planningClosed={false} onOpenLibrary={vi.fn()} />);
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
    render(<ConversationTabs projectId="p1" planningClosed={false} onOpenLibrary={onOpenLibrary} />);
    await user.click(screen.getByRole("button", { name: "Barriers" }));
    expect(state.setActiveConversation).toHaveBeenCalledWith("c1");
    await user.click(screen.getByRole("button", { name: "Chats" }));
    expect(onOpenLibrary).toHaveBeenCalledOnce();
  });
});
