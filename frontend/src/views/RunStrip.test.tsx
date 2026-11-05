import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createInitialRunStreamState } from "../store";
import type { PlanDraft, RunStatus, RunStreamState, StageEntry } from "../store";
import { RunStrip } from "./RunStrip";
import * as taskLive from "./taskLive";
import type { LifecycleTab } from "./lifecycle";

vi.mock("./taskLive", async (importOriginal) => {
  const actual = await importOriginal<typeof taskLive>();
  return { ...actual, useTaskLive: vi.fn(), useMountedTraces: vi.fn(() => 0) };
});

const NOW = Date.parse("2026-11-05T10:10:00Z");
const ago = (seconds: number) => new Date(NOW - seconds * 1000).toISOString();

function plan(): PlanDraft {
  const step = (stage: string, label: string, row: string) => ({ stage, label, row, blurb: "" }) as never;
  return {
    steps: [
      step("acquire", "Searching and screening", "search_screen"),
      step("screen", "Searching and screening", "search_screen"),
      step("synthesise", "Writing", "synthesise"),
    ],
  } as unknown as PlanDraft;
}

const WRITING: StageEntry[] = [
  { stage: "acquire", label: "Searching and screening", status: "completed", startedAt: ago(600), seconds: 40, counts: [] },
  { stage: "screen", label: "Searching and screening", status: "completed", startedAt: ago(560), seconds: 24, counts: [] },
  { stage: "synthesise", label: "Writing", status: "started", startedAt: ago(100), counts: [] },
];

function stream(status: RunStatus | null, overrides: Partial<RunStreamState> = {}): RunStreamState {
  return {
    ...createInitialRunStreamState(),
    run: status === null ? null : { id: "r1", status, startedAt: ago(372) },
    stages: WRITING,
    plan: { plan: plan() } as never,
    liveness: {
      synthesise: {
        activity: "Looking for: childcare cost as a barrier to take-up",
        section: "Section 3 of 7 · Costs and funding",
        heartbeat: false,
        dropped: 0,
        occurredAt: ago(1),
      },
    },
    ...overrides,
  };
}

function live(tab: LifecycleTab | null, runStream: RunStreamState, isOwner = true) {
  vi.mocked(taskLive.useTaskLive).mockReturnValue({
    taskId: "t1",
    tab,
    stream: runStream,
    marks: taskLive.NO_MARKS,
    capability: "evidence_search",
    isOwner,
  });
}

const strip = () => screen.getByTestId("run-strip");
const flat = (text: string | null | undefined) => (text ?? "").replace(/\u00A0/g, " ");

describe("RunStrip (task 058, owner round 7: the strip returns)", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    vi.mocked(taskLive.useMountedTraces).mockReturnValue(0);
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it.each(["sources", "result", "history", "share"] as const)("shows on %s while a run is live", (tab) => {
    live(tab, stream("running"));
    render(<RunStrip />);
    expect(strip()).toHaveAttribute("data-open", "true");
    expect(strip()).not.toHaveAttribute("aria-hidden");
  });

  it("is not shown on the Agent tab", () => {
    live("agent", stream("running"));
    render(<RunStrip />);
    expect(strip()).toHaveAttribute("data-open", "false");
    expect(strip()).toHaveAttribute("aria-hidden", "true");
    expect(strip()).toHaveTextContent("");
  });

  it.each([null, "succeeded", "failed"] as const)("is not shown with no live run (%s)", (status) => {
    live("sources", stream(status));
    render(<RunStrip />);
    expect(strip()).toHaveAttribute("data-open", "false");
    expect(screen.getByRole("status")).toHaveTextContent(/^$/);
  });

  it("reads the trace header's words, the turning mark, and the elapsed time at the end; no link, no button", () => {
    live("result", stream("running"));
    render(<RunStrip />);
    const line = strip().querySelector(".border-b") as HTMLElement;
    expect(line).toHaveClass("text-meta", "text-grey", "bg-paper", "border-line");
    expect(line.querySelector("[data-live-mark]")).not.toBeNull();
    expect(flat(line.children[1].textContent)).toBe("Writing · Section 3 of 7 · Costs and funding");
    expect(line.lastElementChild).toHaveTextContent(/^6 min 12 s$/);
    expect(line.lastElementChild).toHaveClass("shrink-0", "whitespace-nowrap");
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("truncates long words on one line and keeps the time in view", () => {
    live("result", stream("running"));
    render(<RunStrip />);
    const words = strip().querySelector(".anim-rise") as HTMLElement;
    expect(words).toHaveClass("truncate", "min-w-0", "flex-1");
  });

  it("says a check-in waits, with the orange square, to the owner; where it stopped to a colleague", () => {
    live("sources", stream("paused"));
    const { unmount } = render(<RunStrip />);
    expect(strip().querySelector("[data-tone='paused']")).not.toBeNull();
    expect(strip().querySelector("[data-live-mark]")).toBeNull();
    expect(flat(strip().querySelector(".anim-rise")?.textContent)).toBe("Paused · a check-in is waiting on you");
    unmount();
    live("sources", stream("paused"), false);
    render(<RunStrip />);
    expect(flat(strip().querySelector(".anim-rise")?.textContent)).toBe("Paused · Writing");
  });

  it("opens and closes with a height transition that holds still under reduced motion", () => {
    live("sources", stream("running"));
    render(<RunStrip />);
    expect(strip()).toHaveClass("transition-[grid-template-rows]", "duration-200", "motion-reduce:transition-none");
  });

  it("announces through one live region, quiet while a run trace is mounted", () => {
    live("sources", stream("running"));
    const { unmount } = render(<RunStrip />);
    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(flat(status.textContent)).toBe("Writing · Section 3 of 7 · Costs and funding");
    unmount();
    vi.mocked(taskLive.useMountedTraces).mockReturnValue(1);
    render(<RunStrip />);
    expect(screen.queryByRole("status")).toBeNull();
  });
});
