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

/** The header line: a button only once the run has ended (its chevron opens
 *  the rows); live or paused it is a line, with the rows open under it. */
const header = () => screen.getByTestId("trace-header");
const headerButton = () => within(header()).getByRole("button");
const mark = () => header().querySelector("[data-tone]") as HTMLElement;
/** Text with its no-break spaces read as spaces (the separators bind to the
 *  word before them). */
const flat = (text: string | null | undefined) => (text ?? "").replace(/\u00A0/g, " ");
const liveMark = () => header().querySelector("[data-live-mark]");

function rowOf(label: string): HTMLElement {
  const item = within(screen.getByRole("list", { name: "Run steps" }))
    .getAllByRole("listitem")
    .find((li) => li.textContent?.startsWith(label));
  if (item === undefined) throw new Error(`no row ${label}`);
  return item;
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

/** The system's reduced-motion setting, as `matchMedia` reports it. */
function stubReducedMotion(reduce: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: reduce && query.includes("reduce"),
    media: query,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  }));
}

describe("RunTrace — live (annex § The run trace; owner round 6: the card's body)", () => {
  it("has a header line, not a button: the turning mark and the run's elapsed time only", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    render(trace());
    expect(within(header()).queryByRole("button")).toBeNull();
    // The step's words live on its row (lead, round 6). No step count and
    // no "hide steps": the rows are open under it.
    expect(flat(header().textContent)).toBe("6 min 12 s");
    // Live, the mark is the fold mark at 14 px, not the square (owner, 2026-11-05).
    expect(liveMark()).toHaveStyle({ width: "14px" });
    expect(mark()).toBeNull();
    // No card frame, no state word in capitals, no Minimise.
    expect(screen.queryByText("RUNNING")).toBeNull();
    expect(screen.queryByRole("button", { name: "Minimise" })).toBeNull();
    expect(screen.getByRole("region", { name: "Analysis run" }).className).not.toMatch(/\bborder\b|shadow/);
  });

  it("announces the header's words politely, without the ticking clock", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    render(trace());
    const status = within(screen.getByRole("region", { name: "Analysis run" })).getByRole("status");
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(status).toHaveTextContent(/^Classifying · 40 of 118 classified$/);
  });

  it("lists every plan step under the header, in plan order, top to bottom, and keeps the list open", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    render(trace());
    const list = screen.getByRole("list", { name: "Run steps" });
    expect(within(list).getAllByRole("listitem").map((li) => flat(li.textContent))).toEqual([
      "Searching and screening · 312 found · 118 relevant · 1 min 4 s · Sources →, done",
      "Classifying, in progress · 1 min 15 s40 of 118 classified",
      "Reading the full texts, to come",
      "Mapping, to come",
      "Shortlisting, to come",
      "Writing, to come",
    ]);
    // The finished step shows once, in its place in the list: no line under
    // the header repeats it.
    const region = screen.getByRole("region", { name: "Analysis run" });
    expect(region.textContent?.match(/312 found/g)).toHaveLength(1);
    expect(screen.queryByText(/hide steps|6 steps/)).toBeNull();
  });

  it("marks each row on a spine: the square in its tone, the blue square breathing on the step in progress", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    render(trace());
    const done = rowOf("Searching and screening");
    expect(done.querySelector("[data-tone]")).toHaveClass("bg-green", "size-1.5");
    const now = rowOf("Classifying");
    // One mark turns per block, the header's (lead, round 6): the step in
    // progress takes the 6 px blue square, breathing while updates arrive.
    expect(now.querySelector("[data-live-mark]")).toBeNull();
    expect(now.querySelector("[data-tone]")).toHaveClass("bg-blue", "size-1.5", "anim-breathe");
    expect(screen.getByRole("region", { name: "Analysis run" }).querySelectorAll("[data-live-mark]")).toHaveLength(1);
    expect(rowOf("Writing").querySelector("[data-tone]")).toHaveClass("bg-line-2");
    // A hairline spine through the marks, and a hairline rule between rows.
    expect(done.querySelector("span.w-px.bg-line-2")).not.toBeNull();
    expect(done.lastElementChild?.className).not.toMatch(/border-t/);
    expect(now.lastElementChild).toHaveClass("border-t", "border-line");
  });

  it("shows a done row as label, counts, wall time and link; upcoming rows as names only, grey and smaller", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    render(trace());
    const done = rowOf("Searching and screening");
    expect(within(done).getByRole("link", { name: "Sources →" })).toHaveAttribute("href", `/tasks/${TASK_ID}/sources/all`);
    expect(within(done).getByText("Searching and screening")).toHaveClass("text-navy");
    expect(done).toHaveClass("text-body");
    const upcoming = rowOf("Shortlisting");
    expect(upcoming.textContent).toBe("Shortlisting, to come");
    expect(upcoming).toHaveClass("text-grey", "text-meta");
    expect(within(upcoming).queryByRole("link")).toBeNull();
  });

  it("reads Writing's section above the action line in its row, and in the screen reader's words", () => {
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
    expect(within(screen.getByRole("region", { name: "Analysis run" })).getByRole("status")).toHaveTextContent(
      /^Writing · Section 3 of 7 · Costs and funding$/,
    );
    expect(header()).not.toHaveTextContent("Writing");
    const lines = [...rowOf("Writing").querySelectorAll("p")].map((line) => flat(line.textContent));
    expect(lines).toEqual([
      "Writing, in progress · 30 s",
      "Section 3 of 7 · Costs and funding",
      "Looking for: childcare cost as a barrier to take-up",
    ]);
  });

  it("re-mounts the header's words as the run pauses, so they rise in", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    const { rerender } = render(trace());
    expect(header().querySelector(".anim-rise")).toBeNull();
    rerender(trace({ status: "paused" }));
    expect(header().querySelector(".anim-rise")).toHaveTextContent("Paused · a check-in is waiting on you");
  });

  it("rises a row in once as it lands, and holds rows that were done before still", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    const running = SEARCHED.map((e) => ({ ...e, status: e.stage === "screen" ? ("started" as const) : e.status }));
    const { rerender } = render(trace({ stages: running, liveness: {} }));
    expect(rowOf("Searching and screening")).not.toHaveClass("anim-rise");
    rerender(trace());
    expect(rowOf("Searching and screening")).toHaveClass("anim-rise");
    // A trace that mounts with the step already done does not replay it.
    render(trace(), { container: document.body.appendChild(document.createElement("div")) });
    const lists = screen.getAllByRole("list", { name: "Run steps" });
    const fresh = within(lists[1]).getAllByRole("listitem")[0];
    expect(fresh).not.toHaveClass("anim-rise");
  });

  it("keeps the elapsed time out of the words, so it stays in view on a phone and in the sidebar", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    render(trace({ status: "paused" }));
    const words = header().querySelector(".anim-rise") as HTMLElement;
    // Narrow: up to two lines of words, then the line wraps; wide: one
    // truncated line. The trace's own width decides (a container query).
    expect(screen.getByRole("region", { name: "Analysis run" })).toHaveClass("@container");
    expect(words).toHaveClass("line-clamp-2", "@xl:truncate", "min-w-0");
    const clock = words.nextElementSibling as HTMLElement;
    expect(clock).toHaveTextContent(/^6 min 12 s$/);
    expect(words.textContent?.endsWith("\u00A0·")).toBe(true);
    expect(clock).toHaveClass("shrink-0", "whitespace-nowrap");
    expect(words.parentElement).toHaveClass("flex-wrap", "@xl:flex-nowrap");
  });

  it("reads at the chat's size: the header's words Lead, the time grey, the rows Body", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    render(trace({ status: "paused", isOwner: false }));
    const words = header().querySelector(".anim-rise") as HTMLElement;
    expect(header()).toHaveClass("text-lead");
    expect(words).toHaveClass("text-navy");
    // The first word semibold, the rest regular (lead, 2026-11-05).
    expect(within(words).getByText("Paused")).toHaveClass("font-semibold");
    expect(words).not.toHaveClass("font-semibold");
    expect(words.nextElementSibling).toHaveClass("text-grey");
    expect(rowOf("Classifying")).toHaveClass("text-body");
    expect(screen.getByRole("region", { name: "Analysis run" }).className).not.toMatch(/text-meta/);
  });

  it("reads 'Still working on this step' after two minutes with no tick, with no counter", () => {
    vi.useFakeTimers({ now: NOW });
    render(trace());
    act(() => {
      vi.advanceTimersByTime(119_000);
    });
    expect(rowOf("Classifying")).toHaveTextContent("40 of 118 classified");
    act(() => {
      vi.advanceTimersByTime(2_000);
    });
    expect(rowOf("Classifying")).toHaveTextContent("Still working on this step");
    expect(rowOf("Classifying")).not.toHaveTextContent("40 of 118");
    expect(within(screen.getByRole("region", { name: "Analysis run" })).getByRole("status")).toHaveTextContent(
      "Classifying · Still working on this step",
    );
  });

  it("puts See plan at the foot of the list", async () => {
    const onSeePlan = vi.fn();
    render(trace({ onSeePlan }));
    await userEvent.click(screen.getByRole("button", { name: "See plan" }));
    expect(onSeePlan).toHaveBeenCalledTimes(1);
  });

  it("shows the mark and the time only before the first stage frame, with the plan's steps to come", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    render(trace({ stages: [], liveness: {} }));
    expect(flat(header().textContent)).toBe("6 min 12 s");
    expect(within(screen.getByRole("list", { name: "Run steps" })).getAllByRole("listitem")).toHaveLength(6);
  });
});

describe("RunTrace — paused", () => {
  it("turns the mark orange and tells the owner a check-in waits, with the rows under it, and never stalls", () => {
    vi.useFakeTimers({ now: NOW });
    render(trace({ status: "paused" }));
    expect(mark()).toHaveClass("bg-orange", "size-1.5");
    expect(mark()).not.toHaveClass("anim-breathe");
    expect(liveMark()).toBeNull();
    expect(flat(header().textContent)).toMatch(/^Paused · a check-in is waiting on you ·6 min 12 s$/);
    // Nothing turns while the run waits on a person: the step's mark is the
    // orange square too.
    expect(screen.getByRole("list", { name: "Run steps" })).toBeVisible();
    expect(rowOf("Classifying").querySelector("[data-tone]")).toHaveClass("bg-orange");
    expect(screen.getByRole("region", { name: "Analysis run" }).querySelector("[data-live-mark]")).toBeNull();
    act(() => {
      vi.advanceTimersByTime(180_000);
    });
    expect(header()).not.toHaveTextContent("Still working");
  });

  it("tells a colleague where the run stopped instead", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    render(trace({ status: "paused", isOwner: false }));
    expect(flat(header().textContent)).toMatch(/^Paused · Classifying ·6 min 12 s/);
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
    expect(region).toHaveTextContent(/^Report ready›Report ready ·6 min· Read it →$/);
    expect(mark()).toHaveClass("bg-green", "size-1.5");
    expect(liveMark()).toBeNull();
    expect(within(region).getByRole("link", { name: "Read it →" })).toHaveAttribute("href", `/tasks/${TASK_ID}/result`);
    expect(headerButton()).toHaveTextContent("›");
    expect(headerButton()).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("list", { name: "Run steps" })).toBeNull();
    // No last-finished line and no step count on the folded line.
    expect(region).not.toHaveTextContent("312 found");
    expect(region).not.toHaveTextContent("steps");
    await userEvent.click(headerButton());
    expect(headerButton()).toHaveAttribute("aria-expanded", "true");
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
    expect(headerButton()).toHaveTextContent("The longlist is ready");
  });

  it.each([
    ["failed", "Failed"],
    ["aborted", "Stopped"],
    ["interrupted", "Stopped"],
  ] as const)("reads a %s run as '%s' with the red mark and no link", (status, words) => {
    render(trace({ status, stages: SEARCHED, liveness: {}, endedAt: ago(0) }));
    expect(headerButton()).toHaveTextContent(new RegExp(`^›${words} ·6 min$`));
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
    expect(headerButton()).toHaveTextContent(
      /^›Policy Atlas could not propose a shortlist\. Your places are unchanged\. ·6 min$/,
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
  // The trace's motion is the turning fold mark and the 300 ms rise; the
  // mark holds still under prefers-reduced-motion, and the rise is a utility
  // that goes still there too (index.css).
  const css = readFileSync(join(__dirname, "../../index.css"), "utf8");
  const utility = (name: string) => {
    const start = css.indexOf(`@utility ${name} {`);
    return css.slice(start, css.indexOf("\n}", start));
  };

  it("turns the live mark, and holds it still under reduced motion", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    const frames = vi.spyOn(window, "requestAnimationFrame");
    stubReducedMotion(false);
    const { unmount } = render(trace());
    expect(liveMark()).not.toBeNull();
    expect(frames).toHaveBeenCalled();
    unmount();
    frames.mockClear();
    stubReducedMotion(true);
    render(trace());
    // Still the fold mark (the shut diamond), but no frame loop runs.
    expect(liveMark()?.querySelector("svg")).not.toBeNull();
    expect(frames).not.toHaveBeenCalled();
  });

  it("swaps the words and a landed row in at once", () => {
    expect(utility("anim-rise")).toMatch(/prefers-reduced-motion: reduce\)\s*\{\s*animation-duration: 1ms;/);
  });
});

describe("RunTrace — a separator never starts a line (lead, 2026-11-05)", () => {
  it("binds every · to the word before it, in the header and the step rows", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    render(trace());
    const visible = (el: Element) => (el.textContent ?? "").replace(/\s+$/, "");
    // Every visible separator is preceded by a no-break space, so a line can
    // break after it but never before it.
    const check = (el: Element) => expect(visible(el)).not.toMatch(/ ·/);
    check(header());
    for (const item of within(screen.getByRole("list", { name: "Run steps" })).getAllByRole("listitem")) check(item);
  });
});
