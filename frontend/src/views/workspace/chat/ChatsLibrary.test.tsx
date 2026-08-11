import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ChatsLibrary } from "./ChatsLibrary";

const state = vi.hoisted(() => ({ update: vi.fn(async () => undefined), archive: vi.fn(), unarchive: vi.fn(async () => undefined), setActiveConversation: vi.fn(), addOpenChatTab: vi.fn() }));
vi.mock("../../../api/queries", () => ({
  useConversations: (_id: string, query: { status: string }) => ({
    data: {
      data: query.status === "active"
        ? [{ id: "c1", title: "Cost barriers", created_at: new Date().toISOString(), entry_artefact_id: "a1", latest_turn_preview: { reply_snippet: "A short answer", user_message: "What changed?", at: new Date().toISOString() } }]
        : [{ id: "c2", title: "Old thread", created_at: new Date().toISOString(), entry_artefact_id: null, latest_turn_preview: null }],
    },
  }),
}));
vi.mock("./conversationState", () => ({ addOpenChatTab: state.addOpenChatTab, useActiveConversation: () => ({ setActiveConversation: state.setActiveConversation }), useConversationMutations: () => ({ archive: state.archive, unarchive: state.unarchive, update: state.update }) }));

describe("ChatsLibrary", () => {
  it("shows previews, the evidence-base chip, and supports inline rename and archive", async () => {
    const user = userEvent.setup();
    render(<ChatsLibrary projectId="p1" open onClose={vi.fn()} />);
    expect(screen.getByText("A short answer")).toBeInTheDocument();
    expect(screen.getByText("Evidence base")).toBeInTheDocument();
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
    render(<ChatsLibrary projectId="p1" open onClose={onClose} />);
    expect(screen.getByRole("heading", { name: "Archived" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Old thread" }));
    expect(state.unarchive).toHaveBeenCalledWith("c2");
    expect(state.addOpenChatTab).toHaveBeenCalledWith("p1", "c2");
    expect(state.setActiveConversation).toHaveBeenCalledWith("c2");
    expect(onClose).toHaveBeenCalledOnce();
  });
});
