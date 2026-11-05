import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createInitialRunStreamState } from "../store";
import type { PlanDraft, RunStatus, RunStreamState, StageEntry } from "../store";
import { onLinkedView, RunStatusBar } from "./RunStatusBar";
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

/** Where the status bar took the reader: the path and the open conversation. */
function Where() {
  const location = useLocation();
  return <p data-testid="where">{`${location.pathname}${location.search}`}</p>;
}

function renderStrip(ui: ReactElement = <RunStatusBar />) {
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

const statusBar = () => screen.getByTestId("run-status-bar");
const flat = (text: string | null | undefined) => (text ?? "").replace(/\u00A0/g, " ");

describe("RunStatusBar (task 058, owner rounds 7 and 8: the status bar returns, as the way to the Task Agent)", () => {
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
    expect(statusBar()).toHaveAttribute("data-open", "true");
    expect(statusBar()).not.toHaveAttribute("aria-hidden");
  });

  it("is not shown on the Agent tab", () => {
    live("agent", stream("running"));
    renderStrip();
    expect(statusBar()).toHaveAttribute("data-open", "false");
    expect(statusBar()).toHaveAttribute("aria-hidden", "true");
    expect(statusBar()).toHaveTextContent("");
  });

  it.each([null, "succeeded", "failed"] as const)("is not shown with no live run (%s)", (status) => {
    live("sources", stream(status));
    renderStrip();
    expect(statusBar()).toHaveAttribute("data-open", "false");
    expect(screen.getByRole("status")).toHaveTextContent(/^$/);
  });

  it("reads the step in navy semibold, what it does in grey, the turning mark on the first line and the time at the right", () => {
    live("result", stream("running"));
    renderStrip();
    const line = within(statusBar()).getByRole("button");
    // The bar holds the words' button and, when there is one, the link.
    expect(line.parentElement).toHaveClass("text-meta", "bg-paper", "border-b", "border-line");
    expect(line).toHaveClass("py-2.5");
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

  // Owner, round 8 (reversing contract D8's "status only"): the whole statusBar
  // opens the Task Agent, in the sidebar from md up and on the Agent tab
  // below it.
  it("is one button named for what it opens, with hover and focus states", () => {
    live("result", stream("running"));
    renderStrip();
    const button = screen.getByRole("button", {
      name: "Open the Task Agent: Writing · Section 3 of 7 · Costs and funding",
    });
    expect(button).toHaveClass("flex-1", "cursor-pointer", "hover:bg-paper-2", "focus-visible:outline-blue");
  });

  // Owner, round 9: the bar's second control, after the time, is the running
  // step's view while the reader is not on it.
  it("links to the running step's view after the time, words first in the tab order", () => {
    live("sources", stream("running"));
    renderStrip();
    const link = within(statusBar()).getByRole("link", { name: "Report →" });
    expect(link).toHaveAttribute("href", "/tasks/t1/result");
    expect(link).toHaveClass("text-blue", "font-semibold", "shrink-0", "whitespace-nowrap");
    const button = within(statusBar()).getByRole("button");
    expect(button.compareDocumentPosition(link) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(button.lastElementChild).toHaveTextContent(/^6 min 12 s$/);
  });

  it("hides the link on the step's own view and while paused", () => {
    live("result", stream("running"));
    const first = renderStrip();
    expect(within(statusBar()).queryByRole("link")).toBeNull();
    first.unmount();
    live("sources", stream("paused"));
    renderStrip();
    expect(within(statusBar()).queryByRole("link")).toBeNull();
  });

  it("knows which view a link opens", () => {
    expect(onLinkedView("/tasks/t1/sources", "/tasks/t1/sources")).toBe(true);
    expect(onLinkedView("/tasks/t1/sources/all", "/tasks/t1/sources")).toBe(false);
    expect(onLinkedView("/tasks/t1/sources/all", "/tasks/t1/sources/all")).toBe(true);
    expect(onLinkedView("/tasks/t1/result/", "/tasks/t1/result")).toBe(true);
    expect(onLinkedView("/tasks/t1/sources/landscape", "/tasks/t1/sources/all")).toBe(false);
  });

  it("opens the Task Agent in the sidebar from md up", async () => {
    stubWide(true);
    live("sources", stream("running"));
    renderStrip();
    await userEvent.setup({ advanceTimers: () => undefined }).click(within(statusBar()).getByRole("button"));
    expect(screen.getByTestId("where")).toHaveTextContent("/tasks/t1/sources?chat=ta-1");
  });

  it("goes to the Agent tab below md, where the sidebar does not show", async () => {
    stubWide(false);
    live("sources", stream("running"));
    renderStrip();
    await userEvent.setup({ advanceTimers: () => undefined }).click(within(statusBar()).getByRole("button"));
    expect(screen.getByTestId("where")).toHaveTextContent(/^\/tasks\/t1$/);
  });

  // Lead, round 8: while the Task Agent is open in the sidebar its trace
  // says the same words, so the status bar steps aside; it returns when the
  // sidebar shuts or shows another chat. Below md the sidebar does not show,
  // so the status bar stays.
  it("steps aside while the Task Agent is open in the sidebar, and returns when it shuts", () => {
    stubWide(true);
    live("sources", stream("running"));
    const at = (search: string) =>
      render(
        <MemoryRouter initialEntries={[`/tasks/t1/sources${search}`]}>
          <RunStatusBar />
        </MemoryRouter>,
      );
    const open = at("?chat=ta-1");
    expect(statusBar()).toHaveAttribute("data-open", "false");
    open.unmount();
    const other = at("?chat=c-9");
    expect(statusBar()).toHaveAttribute("data-open", "true");
    other.unmount();
    at("");
    expect(statusBar()).toHaveAttribute("data-open", "true");
  });

  it("steps aside once it has opened the Task Agent in the sidebar", async () => {
    stubWide(true);
    live("sources", stream("running"));
    renderStrip();
    await userEvent.setup().click(within(statusBar()).getByRole("button"));
    expect(screen.getByTestId("where")).toHaveTextContent("?chat=ta-1");
    expect(statusBar()).toHaveAttribute("data-open", "false");
  });

  it("stays below md, where the sidebar does not show", () => {
    stubWide(false);
    live("sources", stream("running"));
    render(
      <MemoryRouter initialEntries={["/tasks/t1/sources?chat=ta-1"]}>
        <RunStatusBar />
      </MemoryRouter>,
    );
    expect(statusBar()).toHaveAttribute("data-open", "true");
  });

  it("is out of the tab order while closed", () => {
    live("agent", stream("running"));
    renderStrip();
    expect(statusBar().querySelector("button")).toBeNull();
  });

  it("truncates long words on one line and keeps the time in view", () => {
    live("result", stream("running"));
    renderStrip();
    const words = statusBar().querySelector(".anim-rise") as HTMLElement;
    expect(words).toHaveClass("truncate", "min-w-0", "flex-1");
  });

  it("says a check-in waits, with the orange square, to the owner; where it stopped to a colleague", () => {
    live("sources", stream("paused"));
    const { unmount } = renderStrip();
    expect(statusBar().querySelector("[data-tone='paused']")).not.toBeNull();
    expect(statusBar().querySelector("[data-live-mark]")).toBeNull();
    expect(flat(statusBar().querySelector(".anim-rise")?.textContent)).toBe("Paused · a check-in is waiting on you");
    unmount();
    live("sources", stream("paused"), false);
    renderStrip();
    expect(flat(statusBar().querySelector(".anim-rise")?.textContent)).toBe("Paused · Writing");
  });

  it("holds still under reduced motion, and mounts open without a transition", () => {
    live("sources", stream("running"));
    renderStrip();
    expect(statusBar()).toHaveClass("duration-200", "motion-reduce:transition-none", "transition-none");
  });

  // The animation sweep's entry 9: a tab switch is navigation, so the status bar
  // is set at a cut; the run starting eases it open.
  it("eases open when the run starts, and is a cut on a tab switch", () => {
    live("sources", stream(null));
    const view = renderStrip();
    live("sources", stream("running"));
    view.rerender(
      <MemoryRouter initialEntries={["/tasks/t1/sources"]}>
        <Routes>
          <Route path="*" element={<RunStatusBar />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(statusBar()).toHaveAttribute("data-open", "true");
    expect(statusBar()).toHaveClass("transition-[grid-template-rows,opacity]", "duration-200");
    expect(statusBar()).not.toHaveClass("transition-none");
    live("agent", stream("running"));
    view.rerender(
      <MemoryRouter initialEntries={["/tasks/t1/sources"]}>
        <Routes>
          <Route path="*" element={<RunStatusBar />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(statusBar()).toHaveAttribute("data-open", "false");
    expect(statusBar()).toHaveClass("transition-none");
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
