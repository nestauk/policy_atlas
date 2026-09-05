import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ConversationRail } from "./ConversationRail";

describe("ConversationRail", () => {
  it("marks the recent chats by title, names the one on show, and opens on click", async () => {
    const onSelectChat = vi.fn();
    render(
      <ConversationRail
        toggleLabel="Show chats"
        expanded={false}
        onToggle={() => undefined}
        onNewChat={() => undefined}
        chatsEnabled={false}
        onTaskAgent={false}
        onSelectTaskAgent={() => undefined}
        recent={[
          { id: "c-1", title: "Budget options" },
          { id: "c-2", title: "Active travel" },
        ]}
        currentId="c-1"
        onSelectChat={onSelectChat}
      />,
    );
    expect(screen.getByRole("button", { name: "Budget options" })).toHaveAttribute("aria-current", "true");
    const other = screen.getByRole("button", { name: "Active travel" });
    expect(other).not.toHaveAttribute("aria-current");
    await userEvent.setup().click(other);
    expect(onSelectChat).toHaveBeenCalledWith("c-2");
    // New chat keeps its name while disabled; the reason is the tooltip's.
    expect(screen.getByRole("button", { name: "New chat" })).toBeDisabled();
  });
});
