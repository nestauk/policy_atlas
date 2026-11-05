import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createInitialRunStreamState } from "../store";
import type { PlanDraft, RunStatus, RunStreamState, StageEntry } from "../store";
import { RunStrip } from "./RunStrip";
import * as taskLive from "./taskLive";
import type { LifecycleTab } from "./lifecycle";

vi.mock("../api/queries", () => ({
  useConversations: () => ({
    isSuccess: true,
    data: { data: [{ id: "ta-1", kind: "task_agent", title: "Task Agent", closed_at: null }] },
  }),
}));

vi.mock("./taskLive", async (importOriginal) => {
  const actual = await importOriginal<typeof taskLive>();
  return { ...actual, useTaskLive: vi.fn(), useMountedTraces: vi.fn(() => 0) };
});

const NOW = Date.parse("2026-11-05T10:10:00Z");
const ago = (seconds: number) => new Date(NOW - seconds * 1000).toISOString();

function plan(): PlanDraft {
  const step = (stage: string, label: string, row: string) => ({ stage, label, row, blurb: "" }) as never;
  // Searching and screening are two rows (owner, round 8).
  return {
    steps: [
      step("acquire", "Searching", "search"),
      step("screen", "Screening", "screen"),
      step("synthesise", "Writing", "synthesise"),
    ],
  } as unknown as PlanDraft;
}

const WRITING: StageEntry[] = [
  { stage: "acquire", label: "Searching", status: "completed", startedAt: ago(600), seconds: 40, counts: [] },
  { stage: "screen", label: "Screening", status: "completed", startedAt: ago(560), seconds: 24, counts: [] },
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

/** Where the strip took the reader: the path and the open conversation. */
function Where() {
  const location = useLocation();
  return <p data-testid="where">{`${location.pathname}${location.search}`}</p>;
}

function renderStrip(ui: ReactElement = <RunStrip />) {
  return render(
    <MemoryRouter initialEntries={["/tasks/t1/sources"]}>
      <Routes>
        <Route path="*" element={<>{ui}<Where /></>} />
      </Routes>
    </MemoryRouter>,
  );
}

/** The sidebar shows from md up; below it the Agent tab is the way in. */
function stubWide(wide: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: wide && query.includes("min-width"),
    media: query,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  }));
}

const strip = () => screen.getByTestId("run-strip");
const flat = (text: string | null | undefined) => (text ?? "").replace(/\u00A0/g, " ");

describe("RunStrip (task 058, owner rounds 7 and 8: the strip returns, as the way to the Task Agent)", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    vi.mocked(taskLive.useMountedTraces).mockReturnValue(0);
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it.each(["sources", "result", "history", "share"] as const)("shows on %s while a run is live", (tab) => {
    live(tab, stream("running"));
    renderStrip();
    expect(strip()).toHaveAttribute("data-open", "true");
    expect(strip()).not.toHaveAttribute("aria-hidden");
  });

  it("is not shown on the Agent tab", () => {
    live("agent", stream("running"));
    renderStrip();
    expect(strip()).toHaveAttribute("data-open", "false");
    expect(strip()).toHaveAttribute("aria-hidden", "true");
    expect(strip()).toHaveTextContent("");
  });

  it.each([null, "succeeded", "failed"] as const)("is not shown with no live run (%s)", (status) => {
    live("sources", stream(status));
    renderStrip();
    expect(strip()).toHaveAttribute("data-open", "false");
    expect(screen.getByRole("status")).toHaveTextContent(/^$/);
  });

  it("reads the step in navy semibold, what it does in grey, the turning mark on the first line and the time at the right", () => {
    live("result", stream("running"));
    renderStrip();
    const line = within(strip()).getByRole("button");
    expect(line).toHaveClass("text-meta", "bg-paper", "border-b", "border-line", "py-2.5");
    // The mark sits on the first line of the words.
    expect(line.firstElementChild).toHaveClass("h-[1lh]");
    expect(line.firstElementChild?.querySelector("[data-live-mark]")).not.toBeNull();
    const words = line.children[1] as HTMLElement;
    expect(flat(words.textContent)).toBe("Writing · Section 3 of 7 · Costs and funding");
    expect(words.firstElementChild).toHaveClass("font-semibold", "text-navy");
    expect(words.lastElementChild).toHaveClass("text-grey");
    expect(line.lastElementChild).toHaveTextContent(/^6 min 12 s$/);
    expect(line.lastElementChild).toHaveClass("shrink-0", "whitespace-nowrap", "text-grey", "text-right");
    expect(line.lastElementChild?.querySelector(".tabular-nums")).not.toBeNull();
    expect(screen.queryByRole("link")).toBeNull();
  });

  // Owner, round 8 (reversing contract D8's "status only"): the whole strip
  // opens the Task Agent, in the sidebar from md up and on the Agent tab
  // below it.
  it("is one button named for what it opens, with hover and focus states", () => {
    live("result", stream("running"));
    renderStrip();
    const button = screen.getByRole("button", {
      name: "Open the Task Agent: Writing · Section 3 of 7 · Costs and funding",
    });
    expect(button).toHaveClass("w-full", "cursor-pointer", "hover:bg-paper-2", "focus-visible:outline-blue");
  });

  it("opens the Task Agent in the sidebar from md up", async () => {
    stubWide(true);
    live("sources", stream("running"));
    renderStrip();
    await userEvent.setup({ advanceTimers: () => undefined }).click(within(strip()).getByRole("button"));
    expect(screen.getByTestId("where")).toHaveTextContent("/tasks/t1/sources?chat=ta-1");
  });

  it("goes to the Agent tab below md, where the sidebar does not show", async () => {
    stubWide(false);
    live("sources", stream("running"));
    renderStrip();
    await userEvent.setup({ advanceTimers: () => undefined }).click(within(strip()).getByRole("button"));
    expect(screen.getByTestId("where")).toHaveTextContent(/^\/tasks\/t1$/);
  });

  // Lead, round 8: while the Task Agent is open in the sidebar its trace
  // says the same words, so the strip steps aside; it returns when the
  // sidebar shuts or shows another chat. Below md the sidebar does not show,
  // so the strip stays.
  it("steps aside while the Task Agent is open in the sidebar, and returns when it shuts", () => {
    stubWide(true);
    live("sources", stream("running"));
    const at = (search: string) =>
      render(
        <MemoryRouter initialEntries={[`/tasks/t1/sources${search}`]}>
          <RunStrip />
        </MemoryRouter>,
      );
    const open = at("?chat=ta-1");
    expect(strip()).toHaveAttribute("data-open", "false");
    open.unmount();
    const other = at("?chat=c-9");
    expect(strip()).toHaveAttribute("data-open", "true");
    other.unmount();
    at("");
    expect(strip()).toHaveAttribute("data-open", "true");
  });

  it("steps aside once it has opened the Task Agent in the sidebar", async () => {
    stubWide(true);
    live("sources", stream("running"));
    renderStrip();
    await userEvent.setup().click(within(strip()).getByRole("button"));
    expect(screen.getByTestId("where")).toHaveTextContent("?chat=ta-1");
    expect(strip()).toHaveAttribute("data-open", "false");
  });

  it("stays below md, where the sidebar does not show", () => {
    stubWide(false);
    live("sources", stream("running"));
    render(
      <MemoryRouter initialEntries={["/tasks/t1/sources?chat=ta-1"]}>
        <RunStrip />
      </MemoryRouter>,
    );
    expect(strip()).toHaveAttribute("data-open", "true");
  });

  it("is out of the tab order while closed", () => {
    live("agent", stream("running"));
    renderStrip();
    expect(strip().querySelector("button")).toBeNull();
  });

  it("truncates long words on one line and keeps the time in view", () => {
    live("result", stream("running"));
    renderStrip();
    const words = strip().querySelector(".anim-rise") as HTMLElement;
    expect(words).toHaveClass("truncate", "min-w-0", "flex-1");
  });

  it("says a check-in waits, with the orange square, to the owner; where it stopped to a colleague", () => {
    live("sources", stream("paused"));
    const { unmount } = renderStrip();
    expect(strip().querySelector("[data-tone='paused']")).not.toBeNull();
    expect(strip().querySelector("[data-live-mark]")).toBeNull();
    expect(flat(strip().querySelector(".anim-rise")?.textContent)).toBe("Paused · a check-in is waiting on you");
    unmount();
    live("sources", stream("paused"), false);
    renderStrip();
    expect(flat(strip().querySelector(".anim-rise")?.textContent)).toBe("Paused · Writing");
  });

  it("opens and closes with a height transition that holds still under reduced motion", () => {
    live("sources", stream("running"));
    renderStrip();
    expect(strip()).toHaveClass("transition-[grid-template-rows]", "duration-200", "motion-reduce:transition-none");
  });

  it("announces through one live region, quiet while a run trace is mounted", () => {
    live("sources", stream("running"));
    const { unmount } = renderStrip();
    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(flat(status.textContent)).toBe("Writing · Section 3 of 7 · Costs and funding");
    unmount();
    vi.mocked(taskLive.useMountedTraces).mockReturnValue(1);
    renderStrip();
    expect(screen.queryByRole("status")).toBeNull();
  });
});
