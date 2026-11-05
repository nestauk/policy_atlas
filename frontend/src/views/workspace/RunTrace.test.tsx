import { STAGE_COUNTS } from "../../mock/fixtures";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps } from "react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { PlanDraft, StageEntry, StageLiveness, TaskAgentThreadRun } from "../../store";
import { PastRunLine, RunTrace } from "./RunTrace";

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

const CLASSIFYING: StageEntry[] = [
  ...SEARCHED,
  entry({ stage: "classify", label: "Classifying", status: "started", startedAt: ago(75) }),
];

const classifyTick = (occurredAt = ago(0)): Record<string, StageLiveness> => ({
  classify: { activity: "40 of 118 classified", done: 40, total: 118, heartbeat: false, dropped: 0, occurredAt },
});

type Props = Partial<ComponentProps<typeof RunTrace>>;

function trace(props: Props = {}) {
  return (
    <MemoryRouter>
      <RunTrace
        taskId={TASK_ID}
        status="running"
        stages={CLASSIFYING}
        liveness={classifyTick()}
        plan={standardPlan()}
        startedAt={ago(372)}
        hasFindings={false}
        isOwner
        {...props}
      />
    </MemoryRouter>
  );
}

const header = () => within(screen.getByRole("region", { name: "Analysis run" })).getAllByRole("button")[0];
const mark = () => screen.getByRole("region", { name: "Analysis run" }).querySelector("[data-tone]") as HTMLElement;

function rowOf(label: string): HTMLElement {
  const item = within(screen.getByRole("list", { name: "Run steps" }))
    .getAllByRole("listitem")
    .find((li) => li.textContent?.startsWith(label));
  if (item === undefined) throw new Error(`no row ${label}`);
  return item;
}

afterEach(() => {
  vi.useRealTimers();
});

describe("RunTrace — live, closed (annex § The run trace)", () => {
  it("is one header button: the blue mark, the step and what it is doing, the elapsed time, the step count", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    render(trace());
    const button = header();
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(button).toHaveTextContent("Classifying · 40 of 118 classified· 6 min 12 s · 6 steps");
    expect(mark()).toHaveClass("bg-blue", "size-1.5", "anim-breathe");
    expect(screen.queryByRole("list", { name: "Run steps" })).toBeNull();
    // No card frame, no state word in capitals, no Minimise.
    expect(screen.queryByText("RUNNING")).toBeNull();
    expect(screen.queryByRole("button", { name: "Minimise" })).toBeNull();
  });

  it("announces the header's words politely, without the ticking clock", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    render(trace());
    const status = within(screen.getByRole("region", { name: "Analysis run" })).getByRole("status");
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(status).toHaveTextContent(/^Classifying · 40 of 118 classified$/);
  });

  it("shows the last finished step's one line under the header, with its link", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    render(trace());
    const last = screen.getByText((_, el) => el?.tagName === "P" && el.textContent?.startsWith("Searching and screening") === true);
    expect(last).toHaveTextContent("Searching and screening · 312 found · 118 relevant · 1 min 4 s · Sources →");
    expect(last).toHaveClass("anim-rise", "border-l", "text-grey");
    expect(within(last).getByRole("link", { name: "Sources →" })).toHaveAttribute("href", `/tasks/${TASK_ID}/sources/all`);
  });

  it("reads Writing's section in the header", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    render(
      trace({
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
      }),
    );
    expect(header()).toHaveTextContent(/^Writing · Section 3 of 7 · Costs and funding/);
  });

  it("re-mounts the header's words when the step changes, so they rise in", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    const { rerender } = render(trace({ stages: SEARCHED.map((e) => ({ ...e, status: e.stage === "screen" ? "started" : e.status })), liveness: {} }));
    const before = header().querySelector(".anim-rise");
    expect(before).toHaveTextContent("Searching and screening");
    rerender(trace());
    const after = header().querySelector(".anim-rise");
    expect(after).toHaveTextContent("Classifying · 40 of 118 classified");
    expect(after).not.toBe(before);
  });

  it("keeps the elapsed time out of the words, so it stays in view on a phone and in the sidebar", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    render(trace());
    const words = header().querySelector(".anim-rise") as HTMLElement;
    // Narrow: up to two lines of words, then the line wraps; wide: one
    // truncated line. The trace's own width decides (a container query).
    expect(screen.getByRole("region", { name: "Analysis run" })).toHaveClass("@container");
    expect(words).toHaveClass("line-clamp-2", "@xl:truncate", "min-w-0");
    const clock = words.nextElementSibling as HTMLElement;
    expect(clock).toHaveTextContent("· 6 min 12 s · 6 steps");
    expect(clock).toHaveClass("shrink-0", "whitespace-nowrap");
    expect(words.parentElement).toHaveClass("flex-wrap", "@xl:flex-nowrap");
  });

  it("stops breathing 1.5 s after the last tick", () => {
    vi.useFakeTimers({ now: NOW });
    render(trace());
    expect(mark()).toHaveClass("anim-breathe");
    act(() => {
      vi.advanceTimersByTime(1_600);
    });
    expect(mark()).not.toHaveClass("anim-breathe");
    expect(mark()).toHaveClass("bg-blue");
    expect(header()).toHaveTextContent("40 of 118 classified");
  });

  it("reads 'Still working on this step' after two minutes with no tick, with no counter", () => {
    vi.useFakeTimers({ now: NOW });
    render(trace());
    act(() => {
      vi.advanceTimersByTime(119_000);
    });
    expect(header()).toHaveTextContent("Classifying · 40 of 118 classified");
    act(() => {
      vi.advanceTimersByTime(2_000);
    });
    expect(header()).toHaveTextContent("Classifying · Still working on this step");
    expect(header()).not.toHaveTextContent("40 of 118");
  });
});

describe("RunTrace — open", () => {
  it("lists every plan step under a hairline rule, and closes again", async () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    const user = userEvent.setup();
    render(trace());
    await user.click(header());
    expect(header()).toHaveAttribute("aria-expanded", "true");
    expect(header()).toHaveTextContent("· hide steps");
    const list = screen.getByRole("list", { name: "Run steps" });
    expect(list.parentElement).toHaveClass("border-l", "border-line");
    expect(header()).toHaveAttribute("aria-controls", list.parentElement?.id);
    expect(within(list).getAllByRole("listitem").map((li) => li.textContent)).toEqual([
      "Searching and screening · 312 found · 118 relevant · 1 min 4 s · Sources →, done",
      "Classifying, in progress · 1 min 15 s40 of 118 classified",
      "Reading the full texts, to come",
      "Mapping, to come",
      "Shortlisting, to come",
      "Writing, to come",
    ]);
    // The last finished line is in the list now, not under the header.
    const region = screen.getByRole("region", { name: "Analysis run" });
    expect(region.textContent?.match(/312 found/g)).toHaveLength(1);
    await user.click(header());
    expect(screen.queryByRole("list", { name: "Run steps" })).toBeNull();
  });

  it("shows a done row as label, counts, wall time and link; upcoming rows as names only", async () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    render(trace());
    await userEvent.click(header());
    const done = rowOf("Searching and screening");
    expect(within(done).getByRole("link", { name: "Sources →" })).toHaveAttribute("href", `/tasks/${TASK_ID}/sources/all`);
    const upcoming = rowOf("Shortlisting");
    expect(upcoming.textContent).toBe("Shortlisting, to come");
    expect(upcoming).toHaveClass("text-grey");
    expect(within(upcoming).queryByRole("link")).toBeNull();
  });

  it("shows Writing's section line above its activity line", async () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    render(
      trace({
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
      }),
    );
    await userEvent.click(header());
    const lines = [...rowOf("Writing").querySelectorAll("p")].map((line) => line.textContent);
    expect(lines).toEqual([
      "Writing, in progress · 30 s",
      "Section 3 of 7 · Costs and funding",
      "Looking for: childcare cost as a barrier to take-up",
    ]);
  });

  it("puts See plan at the foot of the list", async () => {
    const onSeePlan = vi.fn();
    render(trace({ onSeePlan }));
    expect(screen.queryByRole("button", { name: "See plan" })).toBeNull();
    await userEvent.click(header());
    await userEvent.click(screen.getByRole("button", { name: "See plan" }));
    expect(onSeePlan).toHaveBeenCalledTimes(1);
  });
});

describe("RunTrace — paused", () => {
  it("turns the mark orange and tells the owner a check-in waits, and never stalls", () => {
    vi.useFakeTimers({ now: NOW });
    render(trace({ status: "paused" }));
    expect(mark()).toHaveClass("bg-orange");
    expect(mark()).not.toHaveClass("anim-breathe");
    expect(header()).toHaveTextContent(/^Paused · a check-in is waiting on you· 6 min 12 s · 6 steps$/);
    act(() => {
      vi.advanceTimersByTime(180_000);
    });
    expect(header()).not.toHaveTextContent("Still working");
  });

  it("tells a colleague where the run stopped instead", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    render(trace({ status: "paused", isOwner: false }));
    expect(header()).toHaveTextContent(/^Paused · Classifying· 6 min 12 s/);
    expect(header()).not.toHaveTextContent(/waiting on you/);
  });

  it("reads paused as soon as the stream has the check-in", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    render(trace({ checkInWaiting: true }));
    expect(mark()).toHaveClass("bg-orange");
  });
});

describe("RunTrace — ended", () => {
  const WRITTEN = [
    ...SEARCHED,
    entry({ stage: "synthesise", label: "Writing", status: "completed", seconds: 300, summary: { section_count: 7 } }),
  ];

  it("folds to one green line, the run's one destination, with a chevron that opens the steps", async () => {
    render(trace({ status: "succeeded", stages: WRITTEN, liveness: {}, endedAt: ago(0) }));
    const region = screen.getByRole("region", { name: "Analysis run" });
    // The screen reader's status line, then the folded line itself.
    expect(region).toHaveTextContent(/^Report ready›Report ready· 6 min· Read it →$/);
    expect(mark()).toHaveClass("bg-green");
    expect(mark()).not.toHaveClass("anim-breathe");
    expect(within(region).getByRole("link", { name: "Read it →" })).toHaveAttribute("href", `/tasks/${TASK_ID}/result`);
    expect(header()).toHaveTextContent("›");
    expect(header()).toHaveAttribute("aria-expanded", "false");
    // No last-finished line and no step count on the folded line.
    expect(region).not.toHaveTextContent("312 found");
    expect(region).not.toHaveTextContent("steps");
    await userEvent.click(header());
    expect(within(rowOf("Writing")).getByRole("link", { name: "Report →" })).toHaveAttribute("href", `/tasks/${TASK_ID}/result`);
    expect(rowOf("Writing")).toHaveTextContent("Writing · 7 sections · 5 min");
  });

  it("opens a scoping walk's result on its own view", () => {
    render(
      trace({
        status: "succeeded",
        stages: [entry({ stage: "suggest", label: "Suggesting options", status: "completed", seconds: 20 })],
        plan: null,
        liveness: {},
        capability: "options_scoping",
        purpose: "longlist",
        endedAt: ago(0),
      }),
    );
    expect(screen.getByRole("link", { name: "Read it →" })).toHaveAttribute("href", `/tasks/${TASK_ID}/result?view=longlist`);
    expect(header()).toHaveTextContent("The longlist is ready");
  });

  it.each([
    ["failed", "Failed"],
    ["aborted", "Stopped"],
    ["interrupted", "Stopped"],
  ] as const)("reads a %s run as '%s' with the red mark and no link", (status, words) => {
    render(trace({ status, stages: SEARCHED, liveness: {}, endedAt: ago(0) }));
    expect(header()).toHaveTextContent(new RegExp(`^›${words}· 6 min$`));
    expect(mark()).toHaveClass("bg-red");
    expect(screen.queryByRole("link", { name: "Read it →" })).toBeNull();
  });
});

describe("RunTrace — a degraded shortlist walk (lead ruling, 2026-11-05)", () => {
  it("says it could not propose a shortlist, with the red mark, its wall time and no link", () => {
    render(
      trace({
        status: "degraded",
        stages: [entry({ stage: "shortlist", label: "Shortlisting", status: "failed", seconds: 20 })],
        plan: null,
        liveness: {},
        capability: "options_scoping",
        purpose: "shortlist",
        endedAt: ago(0),
      }),
    );
    expect(header()).toHaveTextContent(
      /^›Policy Atlas could not propose a shortlist\. Your places are unchanged\.· 6 min$/,
    );
    expect(mark()).toHaveClass("bg-red");
    expect(screen.queryByRole("link", { name: "Read it →" })).toBeNull();
  });
});

describe("PastRunLine — a run the stream is not following", () => {
  const run = (overrides: Partial<TaskAgentThreadRun>): TaskAgentThreadRun =>
    ({
      capability_run_id: "walk-1",
      status: "succeeded",
      started_at: "2026-11-04T10:00:00Z",
      ended_at: "2026-11-04T10:14:20Z",
      purpose: null,
      parent_capability_run_id: null,
      ...overrides,
    }) as TaskAgentThreadRun;

  it("folds to its status word and its wall time, with no chevron, no steps and no link", () => {
    const { container } = render(<PastRunLine run={run({})} />);
    expect(container).toHaveTextContent(/^Report ready · 14 min$/);
    expect(container.querySelector("button")).toBeNull();
    expect(container.querySelector("a")).toBeNull();
    expect(container.querySelector("[data-tone]")).toHaveClass("bg-green");
  });

  it("words its finish from its own walk", () => {
    const { container } = render(<PastRunLine run={run({ purpose: "longlist" })} capability="options_scoping" />);
    expect(container).toHaveTextContent(/^The longlist is ready · 14 min$/);
  });

  it("reads a bad ending with the red mark", () => {
    const { container } = render(<PastRunLine run={run({ status: "failed" })} />);
    expect(container).toHaveTextContent(/^Failed · 14 min$/);
    expect(container.querySelector("[data-tone]")).toHaveClass("bg-red");
  });
});

describe("RunTrace — reduced motion", () => {
  // The trace's motion is the breathing mark and the 300 ms rise; both are
  // utilities that go still under prefers-reduced-motion (index.css).
  const css = readFileSync(join(__dirname, "../../index.css"), "utf8");
  const utility = (name: string) => {
    const start = css.indexOf(`@utility ${name} {`);
    return css.slice(start, css.indexOf("\n}", start));
  };

  it("holds the mark still", () => {
    expect(utility("anim-breathe")).toMatch(/prefers-reduced-motion: reduce\)\s*\{\s*animation: none;/);
  });

  it("swaps the words and the last finished line in at once", () => {
    expect(utility("anim-rise")).toMatch(/prefers-reduced-motion: reduce\)\s*\{\s*animation-duration: 1ms;/);
  });
});
