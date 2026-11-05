import { STAGE_COUNTS } from "../../mock/fixtures";
import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { PlanDraft, RunStatus, StageEntry, StageLiveness } from "../../store";
import { RunningCard } from "./RunningCard";

const TASK_ID = "11111111-1111-1111-1111-111111111111";
const NOW = Date.parse("2026-11-05T10:10:00Z");
const ago = (seconds: number) => new Date(NOW - seconds * 1000).toISOString();

function entry(overrides: Partial<StageEntry> & Pick<StageEntry, "stage" | "status">): StageEntry {
  // The server puts the done row's counts on the frame (task 058, N17); the
  // test derives them from the summary with the mock's copy of that table.
  const counts = STAGE_COUNTS[overrides.stage].flatMap(([key, noun]) => {
    const value = overrides.summary?.[key];
    return typeof value === "number" ? [{ value, noun }] : [];
  });
  return { label: "Searching and screening", startedAt: ago(600), counts, ...overrides };
}

function standardPlan(): PlanDraft {
  const step = (stage: string, label: string, row: string) => ({ stage, label, row, blurb: "" }) as never;
  return {
    steps: [
      step("acquire", "Searching and screening", "search_screen"),
      step("screen", "Searching and screening", "search_screen"),
      step("classify", "Classifying", "categorise"),
      step("appraise", "Classifying", "categorise"),
      step("ingest", "Reading the full texts", "ingest"),
      step("characterise", "Mapping", "characterise"),
      step("select", "Shortlisting", "select"),
      step("synthesise", "Writing", "synthesise"),
    ],
  } as unknown as PlanDraft;
}

const SEARCHED: StageEntry[] = [
  entry({ stage: "acquire", status: "completed", startedAt: ago(600), seconds: 40, summary: { acquired: 312 } }),
  entry({ stage: "screen", status: "completed", startedAt: ago(560), seconds: 24, summary: { relevant: 118 } }),
];

function renderCard({
  status = "running",
  stages = SEARCHED,
  liveness,
  minimised = false,
  onMinimisedChange = () => undefined,
}: {
  status?: RunStatus;
  stages?: StageEntry[];
  liveness?: Record<string, StageLiveness>;
  minimised?: boolean;
  onMinimisedChange?: (next: boolean) => void;
} = {}) {
  return render(
    <MemoryRouter>
      <RunningCard
        taskId={TASK_ID}
        status={status}
        stages={stages}
        liveness={liveness}
        plan={standardPlan()}
        startedAt={ago(372)}
        endedAt={status === "succeeded" ? ago(0) : undefined}
        hasFindings={false}
        minimised={minimised}
        onMinimisedChange={onMinimisedChange}
      />
    </MemoryRouter>,
  );
}

function rowOf(label: string): HTMLElement {
  const item = within(screen.getByRole("list", { name: "Stage timeline" }))
    .getAllByRole("listitem")
    .find((li) => li.textContent?.startsWith(label));
  if (item === undefined) throw new Error(`no row ${label}`);
  return item;
}

afterEach(() => {
  vi.useRealTimers();
});

describe("RunningCard — direction C (task 058, D5, N5)", () => {
  it("has one top line: the state word, the elapsed time and Minimise; no title, no 'In progress'", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    renderCard();
    const card = screen.getByRole("region", { name: "Analysis run" });
    expect(within(card).getByText("RUNNING")).toBeInTheDocument();
    expect(card).toHaveTextContent("RUNNING6 min 12 sMinimise");
    expect(within(card).getByRole("button", { name: "Minimise" })).toBeInTheDocument();
    expect(within(card).queryByRole("heading")).toBeNull();
    expect(card).not.toHaveTextContent("In progress");
    expect(card).not.toHaveTextContent(/Round \d/);
  });

  it("shows a done row as label, counts, wall time and link; upcoming rows as names only", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    renderCard();
    const done = rowOf("Searching and screening");
    expect(done).toHaveTextContent("312 found · 118 relevant · 1 min 4 s");
    expect(within(done).getByRole("link", { name: "Sources →" })).toHaveAttribute("href", `/tasks/${TASK_ID}/sources/all`);
    const upcoming = rowOf("Shortlisting");
    expect(upcoming.textContent).toBe("Shortlisting, to come");
    expect(within(upcoming).queryByRole("link")).toBeNull();
    expect(screen.queryByRole("link", { name: /Shortlist/ })).toBeNull();
  });

  it("shows the step in progress with its activity line, its own elapsed time and a breathing mark", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    const { container } = renderCard({
      stages: [...SEARCHED, entry({ stage: "classify", label: "Classifying", status: "started", startedAt: ago(75) })],
      liveness: { classify: { activity: "40 of 118 classified", done: 40, total: 118, heartbeat: false, dropped: 0, occurredAt: ago(0) } },
    });
    const row = rowOf("Classifying");
    expect(row).toHaveTextContent("40 of 118 classified");
    expect(row).toHaveTextContent("1 min 15 s");
    expect(row.querySelector(".anim-breathe")).not.toBeNull();
    expect(container.querySelectorAll(".anim-breathe")).toHaveLength(1);
  });

  it("shows Writing's section line above its activity line", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    renderCard({
      stages: [...SEARCHED, entry({ stage: "synthesise", label: "Writing", status: "started", startedAt: ago(30) })],
      liveness: {
        synthesise: {
          activity: "Looking for: childcare cost as a barrier to take-up",
          section: "Section 3 of 7 · Costs and funding",
          heartbeat: false,
          dropped: 0,
          occurredAt: ago(0),
        },
      },
    });
    const lines = rowOf("Writing").querySelectorAll("p");
    expect([...lines].map((line) => line.textContent)).toEqual([
      "Section 3 of 7 · Costs and funding",
      "Looking for: childcare cost as a barrier to take-up",
    ]);
  });

  it("stops breathing 1.5 s after the last tick", () => {
    vi.useFakeTimers({ now: NOW });
    renderCard({
      stages: [...SEARCHED, entry({ stage: "ingest", label: "Reading the full texts", status: "started", startedAt: ago(10) })],
      liveness: { ingest: { activity: "14 of 38 read", heartbeat: false, dropped: 0, occurredAt: ago(0) } },
    });
    expect(rowOf("Reading the full texts").querySelector(".anim-breathe")).not.toBeNull();
    act(() => {
      vi.advanceTimersByTime(1_600);
    });
    expect(rowOf("Reading the full texts").querySelector(".anim-breathe")).toBeNull();
    expect(rowOf("Reading the full texts")).toHaveTextContent("14 of 38 read");
  });

  it("reads 'Still working on this step' after two minutes with no tick, with no counter", () => {
    vi.useFakeTimers({ now: NOW });
    renderCard({
      stages: [...SEARCHED, entry({ stage: "ingest", label: "Reading the full texts", status: "started", startedAt: ago(30) })],
      liveness: { ingest: { activity: "21 of 38 read", heartbeat: false, dropped: 0, occurredAt: ago(0) } },
    });
    act(() => {
      vi.advanceTimersByTime(119_000);
    });
    expect(rowOf("Reading the full texts")).toHaveTextContent("21 of 38 read");
    act(() => {
      vi.advanceTimersByTime(2_000);
    });
    const row = rowOf("Reading the full texts");
    expect(row).toHaveTextContent("Still working on this step");
    expect(row).not.toHaveTextContent("21 of 38 read");
  });

  it("reads PAUSED with the orange dot while the run waits on a check-in, and never stalls", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    renderCard({ status: "paused" });
    const card = screen.getByRole("region", { name: "Analysis run" });
    const word = within(card).getByText("PAUSED");
    expect(word.querySelector(".bg-orange")).not.toBeNull();
    expect(card.querySelector(".bg-yellow")).toBeNull();
  });

  it("offers Read the report once the run has finished, and the Report link on Writing", () => {
    renderCard({
      status: "succeeded",
      stages: [...SEARCHED, entry({ stage: "synthesise", label: "Writing", status: "completed", seconds: 300, summary: { section_count: 7 } })],
    });
    expect(screen.getByText("DONE")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Read the report" })).toHaveAttribute("href", `/tasks/${TASK_ID}/result`);
    const writing = rowOf("Writing");
    expect(writing).toHaveTextContent("7 sections · 5 min");
    expect(within(writing).getByRole("link", { name: "Report →" })).toHaveAttribute("href", `/tasks/${TASK_ID}/result`);
    expect(screen.queryByRole("button", { name: "See plan" })).toBeNull();
  });

  it("minimises to one line naming the current row", async () => {
    const onMinimisedChange = vi.fn();
    const user = userEvent.setup();
    const { rerender } = renderCard({ onMinimisedChange });
    await user.click(screen.getByRole("button", { name: "Minimise" }));
    expect(onMinimisedChange).toHaveBeenCalledWith(true);
    rerender(
      <MemoryRouter>
        <RunningCard
          taskId={TASK_ID}
          status="running"
          stages={SEARCHED}
          plan={standardPlan()}
          startedAt={ago(372)}
          hasFindings={false}
          minimised
          onMinimisedChange={onMinimisedChange}
        />
      </MemoryRouter>,
    );
    expect(screen.queryByRole("list", { name: "Stage timeline" })).toBeNull();
    expect(screen.getByRole("region", { name: "Analysis run" })).toHaveTextContent(/^RUNNING · Searching and screening · /);
    expect(screen.getByRole("button", { name: "Expand" })).toBeInTheDocument();
  });
});

describe("RunningCard — the plan's link (owner, polish round 2)", () => {
  it("shows See plan on the top line when the pane gives it a handler", async () => {
    const onSeePlan = vi.fn();
    render(
      <MemoryRouter>
        <RunningCard
          taskId="t"
          status="running"
          stages={SEARCHED}
          liveness={{}}
          plan={standardPlan()}
          startedAt={ago(600)}
          hasFindings={false}
          minimised={false}
          onMinimisedChange={() => undefined}
          onSeePlan={onSeePlan}
        />
      </MemoryRouter>,
    );
    await userEvent.click(screen.getByRole("button", { name: "See plan" }));
    expect(onSeePlan).toHaveBeenCalledTimes(1);
  });
});

