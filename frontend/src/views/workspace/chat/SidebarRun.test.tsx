import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createInitialRunStreamState } from "../../../store";
import type { RunStreamState } from "../../../store";
import type { CheckInOut } from "../../../store/types";
import { checkInPlace, SidebarRun } from "./SidebarRun";

// The check-in card is brief Q's surface with its own tests; here it is the
// thing that mounts (and glows once as it mounts) inside the sidebar.
vi.mock("../CheckInCard", () => ({
  CheckInCard: ({ checkIn, isOwner }: { checkIn: CheckInOut; isOwner: boolean }) =>
    isOwner ? (
      <div data-testid="check-in-card" className="anim-glow">
        {checkIn.check_in_id}
      </div>
    ) : null,
}));

const CHECK_IN = {
  check_in_id: "k1",
  kind: "steer_point",
  stage: "acquire",
  component: "acquire",
  status: "pending",
} as unknown as CheckInOut;

function searching(): RunStreamState {
  return {
    ...createInitialRunStreamState(),
    run: { id: "run-1", status: "running", startedAt: "2026-11-05T09:53:48Z" },
    stages: [
      { stage: "acquire", label: "Searching and screening", status: "completed", startedAt: "2026-11-05T09:54:00Z" },
      { stage: "screen", label: "Searching and screening", status: "started", startedAt: "2026-11-05T09:56:00Z" },
    ],
    liveness: {
      screen: {
        activity: "screening 61 new abstracts · 107 relevant so far",
        heartbeat: false,
        dropped: 0,
        occurredAt: "2026-11-05T09:59:59Z",
      },
    },
  };
}

function pausedAtCheckIn(): RunStreamState {
  const stream = searching();
  return {
    ...stream,
    run: { id: "run-1", status: "paused", startedAt: "2026-11-05T09:53:48Z" },
    stages: stream.stages.map((stage) => ({ ...stage, status: "completed" as const })),
    pendingCheckIn: CHECK_IN,
  };
}

describe("SidebarRun", () => {
  const scrollIntoView = vi.fn();
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-11-05T10:00:00Z"));
    scrollIntoView.mockClear();
    HTMLElement.prototype.scrollIntoView = scrollIntoView;
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows the compact run line and the card's current row with its activity", () => {
    render(<SidebarRun taskId="t1" stream={searching()} isOwner />);
    const line = screen.getByTestId("sidebar-run-line");
    expect(line).toHaveTextContent(/^Searching and screening · /);
    expect(screen.getByTestId("sidebar-run-dot")).toHaveClass("bg-yellow");
    const tail = screen.getByTestId("sidebar-thread-tail");
    // The run line already names the row; the tail is the activity only.
    expect(tail).not.toHaveTextContent("Searching and screening");
    expect(tail).toHaveTextContent("screening 61 new abstracts · 107 relevant so far");
    expect(screen.queryByTestId("check-in-card")).toBeNull();
  });

  it("locks the composer with the Agent tab's own placeholder", () => {
    render(<SidebarRun taskId="t1" stream={searching()} isOwner />);
    const composer = screen.getByRole("textbox");
    expect(composer).toBeDisabled();
    expect(composer).toHaveAttribute("placeholder", "Replanning unlocks when this run finishes.");
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  it("turns orange and paused while a check-in waits, and the check-in is answerable here", () => {
    render(<SidebarRun taskId="t1" stream={pausedAtCheckIn()} isOwner />);
    expect(screen.getByTestId("sidebar-run-line")).toHaveTextContent(
      "Paused · check-in after searching and screening",
    );
    expect(screen.getByTestId("sidebar-run-dot")).toHaveClass("bg-orange");
    expect(screen.getByTestId("check-in-card")).toHaveTextContent("k1");
    expect(screen.queryByTestId("sidebar-thread-tail")).toBeNull();
  });

  it("lands on the check-in when it opens with one waiting, and glows it once", () => {
    const { rerender } = render(<SidebarRun taskId="t1" stream={pausedAtCheckIn()} isOwner />);
    expect(scrollIntoView).toHaveBeenCalledTimes(1);
    const card = screen.getByTestId("check-in-card");
    expect(card).toHaveClass("anim-glow");
    // A later frame on the same check-in neither re-scrolls nor remounts it.
    rerender(<SidebarRun taskId="t1" stream={{ ...pausedAtCheckIn() }} isOwner />);
    expect(scrollIntoView).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("check-in-card")).toBe(card);
  });

  it("gives a colleague the paused line but no check-in to answer", () => {
    render(<SidebarRun taskId="t1" stream={pausedAtCheckIn()} isOwner={false} />);
    expect(screen.getByTestId("sidebar-run-line")).toHaveTextContent(/^Paused/);
    expect(screen.queryByTestId("check-in-card")).toBeNull();
    expect(screen.getByRole("textbox")).toHaveAttribute("placeholder", "Steering is limited to the task owner.");
  });
});

describe("checkInPlace", () => {
  it("names the stage in its own words, or nothing when the stream has no label", () => {
    expect(checkInPlace("acquire", searching().stages)).toBe("check-in after searching and screening");
    expect(checkInPlace("synthesise", searching().stages)).toBeNull();
    expect(checkInPlace(null, searching().stages)).toBeNull();
  });
});
