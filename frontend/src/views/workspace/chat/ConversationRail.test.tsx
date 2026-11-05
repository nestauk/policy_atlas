import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

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

  // Owner, round 6: from another tab, the shut rail says the run is moving
  // and for how long; the mark's hover and focus text say what it is doing.
  describe("while a run is live", () => {
    afterEach(() => vi.useRealTimers());
    const rail = (props: Partial<Parameters<typeof ConversationRail>[0]>) =>
      render(
        <ConversationRail
          toggleLabel="Open the Agent"
          expanded={false}
          onToggle={() => undefined}
          onNewChat={() => undefined}
          chatsEnabled
          onTaskAgent={false}
          onSelectTaskAgent={() => undefined}
          {...props}
        />,
      );

    it("puts the run's elapsed minutes under the turning mark, and the trace's words in its name", () => {
      vi.useFakeTimers({ toFake: ["Date"], now: Date.parse("2026-11-05T10:06:20Z") });
      rail({ runLive: true, runWords: "Searching and screening · 184 found so far", runStartedAt: "2026-11-05T10:00:00Z" });
      const mark = screen.getByRole("button", { name: "Task Agent · Searching and screening · 184 found so far" });
      expect(mark.querySelector("[data-live-mark]")).not.toBeNull();
      const elapsed = screen.getByTestId("rail-elapsed");
      expect(elapsed.textContent).toBe("6\u00A0min");
      expect(elapsed).toHaveClass("text-caption", "text-grey", "text-center");
      // Tabular digits, not a tabular space (Averta widens it).
      expect(elapsed.querySelector(".tabular-nums")).toHaveTextContent("6");
      // It sits under the mark, inside the rail's width.
      expect(elapsed.previousElementSibling).toBe(mark);
      expect(elapsed.parentElement).toHaveClass("w-full");
    });

    it("wraps an hour-long run after its hours, never between a number and its unit", () => {
      vi.useFakeTimers({ toFake: ["Date"], now: Date.parse("2026-11-05T11:04:00Z") });
      rail({ runLive: true, runWords: "Writing", runStartedAt: "2026-11-05T10:00:00Z" });
      expect(screen.getByTestId("rail-elapsed").textContent).toBe("1\u00A0h 4\u00A0min");
    });

    it("shows no figure and keeps the plain name when no run is live", () => {
      rail({ runLive: false, runWords: "Writing", runStartedAt: "2026-11-05T10:00:00Z" });
      expect(screen.getByRole("button", { name: "Task Agent" })).toBeInTheDocument();
      expect(screen.queryByTestId("rail-elapsed")).toBeNull();
    });
  });
});
