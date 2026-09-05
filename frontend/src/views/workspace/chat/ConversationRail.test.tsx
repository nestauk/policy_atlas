import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ConversationRail } from "./ConversationRail";

describe("ConversationRail", () => {
  it("marks the recent chats, names the one on show, dots a new reply, and opens on click", async () => {
    const onSelectChat = vi.fn();
    render(
      <ConversationRail
        toggleLabel="Show chats"
        expanded={false}
        onToggle={() => undefined}
        onNewChat={() => undefined}
        chatsEnabled
        onTaskAgent={false}
        onSelectTaskAgent={() => undefined}
        recent={[
          { id: "c-1", title: "Budget options", unread: false },
          { id: "c-2", title: "Active travel", unread: true },
        ]}
        currentId="c-1"
        onSelectChat={onSelectChat}
      />,
    );
    const current = screen.getByRole("button", { name: "Budget options" });
    expect(current).toHaveAttribute("aria-current", "true");
    const unread = screen.getByRole("button", { name: "Active travel — new reply" });
    expect(unread).not.toHaveAttribute("aria-current");
    await userEvent.setup().click(unread);
    expect(onSelectChat).toHaveBeenCalledWith("c-2");
  });
});
