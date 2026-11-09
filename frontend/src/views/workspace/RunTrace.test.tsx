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
      step("ingest", "Collecting the full texts", "ingest"),
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

/** The card's top line, and once the run has ended the "Show steps" control
 *  under it; live or paused the rows are open under it. */
const header = () => screen.getByTestId("trace-header");
const headerButton = () => within(header()).getByRole("button");
const time = () => screen.getByTestId("trace-time");
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
  it("is the running card: the Card frame, the turning mark, 'Running' in the label style and the time at the right", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    render(trace());
    expect(within(header()).queryByRole("button")).toBeNull();
    // The step's words live on its row (lead, round 6). No step count and
    // no "hide steps": the rows are open under it.
    expect(flat(header().textContent)).toBe("Running6 min 12 s");
    // Live, the mark is the fold mark at 14 px, not the square (owner, 2026-11-05).
    expect(liveMark()).toHaveStyle({ width: "14px" });
    expect(mark()).toBeNull();
    // The card we first designed (owner, round 7): frame, label, no Minimise.
    expect(within(header()).getByText("Running")).toHaveClass("uppercase", "font-extrabold", "tracking-label", "text-grey");
    expect(time()).toHaveClass("whitespace-nowrap", "text-grey");
    expect(time()).toHaveTextContent(/^6 min 12 s$/);
    // The rule under the top line belongs to the rows, so it folds with them.
    expect(screen.getByRole("list", { name: "Run steps" }).closest("[id]")).toHaveClass("border-t", "border-line");
    expect(screen.queryByRole("button", { name: "Minimise" })).toBeNull();
    expect(screen.getByRole("region", { name: "Analysis run" })).toHaveClass("border", "border-line-2", "bg-paper");
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
      "Searching and screening, done312 found · 118 relevant · 1 min 4 s ·Sources →",
      "Classifying, in progress1 min 15 s ·Landscape →40 of 118 classified",
      "Collecting the full texts, to come",
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
    expect(now.querySelector("[data-tone]")).toHaveClass("bg-blue", "size-1.5", "anim-breathe-mark");
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
    expect(within(done).getByText("Searching and screening")).toHaveClass("text-navy", "text-body");
    expect(done).toHaveClass("text-body");
    const upcoming = rowOf("Shortlisting");
    expect(upcoming.textContent).toBe("Shortlisting, to come");
    expect(within(upcoming).getByText("Shortlisting")).toHaveClass("text-grey", "text-meta");
    expect(within(upcoming).queryByRole("link")).toBeNull();
  });

  // Owner, round 8: the card reads as a table. Each line's counts and time
  // sit right-aligned in one column and its link in the last, on the same
  // template as the top line; narrow, the right group follows the label.
  it("lays the top line and every row on one table template, the counts and links right-aligned", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    render(trace());
    const template = "@lg:grid-cols-[minmax(0,1fr)_auto_5.75rem]";
    const done = rowOf("Searching and screening");
    const rowGrid = within(done).getByText("Searching and screening").parentElement as HTMLElement;
    const topGrid = within(header()).getByText("Running").closest("p")?.parentElement as HTMLElement;
    expect(rowGrid.className).toContain(template);
    expect(topGrid.className).toContain(template);
    const counts = [...done.querySelectorAll("span.text-grey")].find((el) => el.textContent?.startsWith("312 found"));
    expect(counts).toHaveClass("text-right");
    const linkCell = within(done).getByRole("link", { name: "Sources →" }).parentElement as HTMLElement;
    expect(linkCell).toHaveClass("text-right");
    // Narrow (the sidebar, a phone), the counts and the link sit on the row's
    // right edge as the wide table's do, the link wrapping to its own line
    // there (owner, round 14), not inline after the words.
    expect(linkCell.parentElement).toHaveClass("flex-1", "flex-wrap", "justify-end", "@lg:contents");
    // Narrow, a finished row's counts take the line under its label.
    expect(within(done).getByText("Searching and screening")).toHaveClass("basis-full", "@lg:basis-auto");
    // Every line shares one line box, so the rows stand equal.
    for (const item of within(screen.getByRole("list", { name: "Run steps" })).getAllByRole("listitem")) {
      expect(item).toHaveClass("leading-[1.55rem]");
    }
  });

  // Owner, round 8: the link to the step's page shows while the step runs.
  it.each([
    ["acquire", "Searching and screening", "Sources →", "/sources/all"],
    ["screen", "Searching and screening", "Sources →", "/sources/all"],
    ["classify", "Classifying", "Landscape →", "/sources/landscape"],
    ["characterise", "Mapping", "Themes →", "/sources"],
    ["synthesise", "Writing", "Report →", "/result"],
  ] as const)("links the step in progress (%s) to its page", (stage, label, name, path) => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    render(trace({ stages: [entry({ stage, label, status: "started", startedAt: ago(30) })], liveness: {} }));
    expect(within(rowOf(label)).getByRole("link", { name })).toHaveAttribute("href", `/tasks/${TASK_ID}${path}`);
  });

  it("gives Collecting the full texts and Shortlisting no link while they run", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    render(trace({ stages: [...SEARCHED, entry({ stage: "ingest", label: "Collecting the full texts", status: "started" })], liveness: {} }));
    expect(within(rowOf("Collecting the full texts")).queryByRole("link")).toBeNull();
  });

  // Round 9: acquisition carries done/total on its tick; the row shows the
  // server's line once, with no second count and no stray "of".
  it("renders the acquisition line as sent, without a second count", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    render(
      trace({
        stages: [entry({ stage: "acquire", label: "Searching", status: "started", startedAt: ago(30) })],
        liveness: {
          acquire: {
            activity: "keeping 312 of 1,234 candidates",
            done: 312,
            total: 1234,
            unit: "candidates",
            heartbeat: false,
            dropped: 0,
            occurredAt: ago(0),
          },
        },
      }),
    );
    const row = rowOf("Searching");
    expect(flat(within(row).getByTestId("row-activity").textContent)).toBe("keeping 312 of 1,234 candidates");
    expect(flat(row.textContent).match(/312/g)).toHaveLength(1);
    expect(flat(row.textContent).match(/\bof\b/g)).toHaveLength(1);
  });

  // Owner, round 8: the step in progress's activity line breathes with its
  // square, the label still; nothing breathes once updates stop.
  it("breathes the activity line with the square while updates arrive, and holds the label still", () => {
    vi.useFakeTimers({ now: NOW });
    render(trace());
    const activity = within(rowOf("Classifying")).getByTestId("row-activity");
    expect(activity).toHaveClass("anim-breathe-soft");
    expect(within(rowOf("Classifying")).getByText("Classifying")).not.toHaveClass("anim-breathe-soft");
    act(() => {
      vi.advanceTimersByTime(2_000);
    });
    expect(within(rowOf("Classifying")).getByTestId("row-activity")).not.toHaveClass("anim-breathe-soft");
    expect(rowOf("Classifying").querySelector("[data-tone]")).not.toHaveClass("anim-breathe-mark");
  });

  it("holds the activity line still while paused", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    render(trace({ status: "paused" }));
    expect(within(rowOf("Classifying")).getByTestId("row-activity")).not.toHaveClass("anim-breathe-soft");
  });

  // Owner, round 8: searching and screening are two rows once the server
  // splits them, each with its own counts, activity and link to Sources.
  it("shows Searching and Screening as two rows, each linking to Sources", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    const step = (stage: string, label: string, row: string) => ({ stage, label, row, blurb: "" }) as never;
    const split = {
      steps: [step("acquire", "Searching", "search"), step("screen", "Screening", "screen"), step("classify", "Classifying", "categorise")],
    } as unknown as PlanDraft;
    render(
      trace({
        plan: split,
        stages: [
          entry({ stage: "acquire", label: "Searching", status: "completed", startedAt: ago(600), seconds: 40, summary: { acquired: 312 } }),
          entry({ stage: "screen", label: "Screening", status: "started", startedAt: ago(60) }),
        ],
        liveness: { screen: { activity: "screening 87 new abstracts · 104 relevant so far", heartbeat: false, dropped: 0, occurredAt: ago(0) } },
      }),
    );
    expect(flat(rowOf("Searching").textContent)).toBe("Searching, done312 found · 40 s ·Sources →");
    expect(within(rowOf("Screening")).getByRole("link", { name: "Sources →" })).toHaveAttribute("href", `/tasks/${TASK_ID}/sources/all`);
    expect(flat(within(rowOf("Screening")).getByTestId("row-activity").textContent)).toBe(
      "screening 87 new abstracts · 104 relevant so far",
    );
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
      "Writing, in progress",
      "Section 3 of 7 · Costs and funding",
      "Looking for: childcare cost as a barrier to take-up",
    ]);
    expect(flat(rowOf("Writing").textContent)).toContain("30 s ·Report →");
  });

  it("re-mounts the header's words as the run pauses, so they rise in", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    const { rerender } = render(trace());
    expect(header().querySelector(".anim-rise")).toBeNull();
    rerender(trace({ status: "paused" }));
    expect(header().querySelector(".anim-rise")).toHaveTextContent("Paused · waiting on you");
  });

  // Lead, round 9: a row that lands keeps its place (it shrinks as it lands,
  // so a rise read as a jump); its counts and time fade in and its square
  // eases from blue to green.
  it("fades a landing row's counts in once, in place, and holds rows that were done before still", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    const running = SEARCHED.map((e) => ({ ...e, status: e.stage === "screen" ? ("started" as const) : e.status }));
    const { rerender } = render(trace({ stages: running, liveness: {} }));
    const counts = () => rowOf("Searching and screening").querySelector(".text-grey.text-right");
    expect(counts()).not.toHaveClass("anim-swap-in");
    rerender(trace());
    expect(rowOf("Searching and screening")).not.toHaveClass("anim-rise");
    expect(rowOf("Searching and screening")).toHaveAttribute("data-landed", "true");
    expect(counts()).toHaveClass("anim-swap-in");
    expect(rowOf("Searching and screening").querySelector("[data-tone]")).toHaveClass("transition-colors", "duration-150");
    // A trace that mounts with the step already done does not replay it.
    render(trace(), { container: document.body.appendChild(document.createElement("div")) });
    const lists = screen.getAllByRole("list", { name: "Run steps" });
    const fresh = within(lists[1]).getAllByRole("listitem")[0];
    expect(fresh).not.toHaveAttribute("data-landed");
    expect(fresh.querySelector(".anim-swap-in")).toBeNull();
  });

  it("keeps the elapsed time at the right of the top line, so it stays in view on a phone and in the sidebar", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    render(trace({ status: "paused" }));
    const words = header().querySelector(".anim-rise") as HTMLElement;
    expect(time()).toHaveTextContent(/^6 min 12 s$/);
    expect(time()).toHaveClass("whitespace-nowrap");
    expect(time().parentElement).toHaveClass("shrink-0");
    expect(words).toHaveClass("min-w-0", "flex-1");
  });

  it("sets the state word as a label and what waits in grey; the rows read at Body", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    render(trace({ status: "paused", isOwner: false, ownerName: "Grace Hopper" }));
    const words = header().querySelector(".anim-rise") as HTMLElement;
    expect(within(words).getByText("Paused")).toHaveClass("uppercase", "font-extrabold");
    expect(within(words).getByText("Paused").nextElementSibling).toHaveClass("text-grey");
    expect(within(words).getByText("Paused").nextElementSibling).not.toHaveClass("uppercase");
    expect(rowOf("Classifying")).toHaveClass("text-body");
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
    expect(flat(header().textContent)).toBe("Running6 min 12 s");
    expect(within(screen.getByRole("list", { name: "Run steps" })).getAllByRole("listitem")).toHaveLength(6);
  });
});

describe("RunTrace — paused", () => {
  it("turns the mark orange and tells the owner the run waits on them, with the rows under it, and never stalls", () => {
    vi.useFakeTimers({ now: NOW });
    render(trace({ status: "paused" }));
    expect(mark()).toHaveClass("bg-orange", "size-1.5");
    expect(mark()).not.toHaveClass("anim-breathe-mark");
    expect(liveMark()).toBeNull();
    expect(flat(header().textContent)).toMatch(/^Paused · waiting on you6 min 12 s$/);
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

  it("tells a colleague whom the run waits on instead, by first name", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    render(trace({ status: "paused", isOwner: false, ownerName: "Grace Hopper" }));
    expect(flat(header().textContent)).toMatch(/^Paused · waiting on Grace6 min 12 s/);
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

  // Owner, round 8: the ended state is the same card. Its top line is the
  // finish (the green square, the finish words in the label style, the wall
  // time, "Read it →"); the rows fold behind "Show steps".
  it("stays the card, its top line the finish and its one destination, the steps folded behind Show steps", async () => {
    render(trace({ status: "succeeded", stages: WRITTEN, liveness: {}, endedAt: ago(0) }));
    const region = screen.getByRole("region", { name: "Analysis run" });
    expect(region).toHaveClass("border", "border-line-2", "bg-paper");
    // The screen reader's status line, then the top line, then the control.
    expect(flat(region.textContent)).toBe("Report readyReport ready6 min ·Read it →Show steps");
    expect(headerButton().querySelector("svg")).not.toBeNull();
    expect(within(header()).getByText("Report ready")).toHaveClass("uppercase", "font-extrabold", "tracking-label", "text-grey");
    expect(mark()).toHaveClass("bg-green", "size-1.5");
    expect(liveMark()).toBeNull();
    expect(time()).toHaveTextContent(/^6 min/);
    expect(within(region).getByRole("link", { name: "Read it →" })).toHaveAttribute("href", `/tasks/${TASK_ID}/result`);
    expect(within(region).getByRole("link", { name: "Read it →" })).toHaveClass("text-blue", "font-semibold");
    expect(headerButton()).toHaveAccessibleName("Show steps");
    expect(headerButton()).toHaveAttribute("aria-expanded", "false");
    expect(headerButton()).toHaveClass("text-meta", "text-grey", "underline");
    expect(screen.queryByRole("list", { name: "Run steps" })).toBeNull();
    expect(header()).not.toHaveClass("border-b");
    // No green one-liner: the words are not green, and nothing repeats a row.
    expect(region.querySelector(".text-\\[\\#0c6b5a\\]")).toBeNull();
    expect(region).not.toHaveTextContent("312 found");
    await userEvent.click(headerButton());
    expect(headerButton()).toHaveAccessibleName("Hide steps");
    expect(headerButton()).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("list", { name: "Run steps" }).closest("[id]")).toHaveClass("border-t", "border-line");
    expect(within(rowOf("Writing")).getByRole("link", { name: "Report →" })).toHaveAttribute("href", `/tasks/${TASK_ID}/result`);
    expect(flat(rowOf("Writing").textContent)).toBe("Writing, done7 sections · 5 min ·Report →");
    await userEvent.click(headerButton());
    expect(screen.queryByRole("list", { name: "Run steps" })).toBeNull();
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
  ] as const)("reads a %s run as '%s' with the red mark and no link, the same card", (status, words) => {
    render(trace({ status, stages: SEARCHED, liveness: {}, endedAt: ago(0) }));
    expect(flat(header().textContent)).toBe(`${words}6 minShow steps`);
    expect(within(header()).getByText(words)).toHaveClass("uppercase", "font-extrabold");
    expect(mark()).toHaveClass("bg-red");
    expect(screen.queryByRole("link", { name: "Read it →" })).toBeNull();
    expect(screen.getByRole("region", { name: "Analysis run" })).toHaveClass("border", "bg-paper");
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
    // A sentence keeps its case: only a state word takes the label style.
    const sentence = within(header()).getByText("Policy Atlas could not propose a shortlist. Your places are unchanged.");
    expect(sentence).not.toHaveClass("uppercase");
    expect(sentence).toHaveClass("text-navy");
    expect(time()).toHaveTextContent(/^6 min$/);
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

  const past = (props: Partial<ComponentProps<typeof PastRunLine>> & { run: TaskAgentThreadRun }) =>
    render(
      <MemoryRouter>
        <PastRunLine taskId={TASK_ID} {...props} />
      </MemoryRouter>,
    );
  const withStages = (overrides: Partial<TaskAgentThreadRun>) =>
    run({
      ...overrides,
      // The read's steps (owner, round 11): what stage.started and
      // stage.completed carried, from the event log.
      stages: [
        { stage: "acquire", label: "Searching", status: "completed", started_at: "2026-11-04T10:00:00Z", ended_at: "2026-11-04T10:01:00Z", summary: { acquired: 312 }, counts: [{ value: 312, noun: "found" }] },
        { stage: "screen", label: "Screening", status: "completed", started_at: "2026-11-04T10:01:00Z", ended_at: "2026-11-04T10:02:30Z", summary: { relevant: 118 }, counts: [] },
        { stage: "synthesise", label: "Writing", status: "completed", started_at: "2026-11-04T10:05:00Z", ended_at: "2026-11-04T10:14:00Z", summary: {} },
      ],
    } as Partial<TaskAgentThreadRun>);

  // Owner, round 8: a past run is the same folded card; round 11: with the
  // link its walk ended with, so the thread keeps a way to what it made.
  it("is the ended card: its finish words, its wall time and Read it, not a landmark", () => {
    const { container } = past({ run: run({}) });
    expect(container).toHaveTextContent(/^Report ready14 min\s·Read it →$/);
    expect(screen.getByTestId("past-run")).toHaveClass("border", "border-line-2", "bg-paper");
    expect(screen.queryByRole("region", { name: "Analysis run" })).toBeNull();
    expect(container.querySelector('[role="status"]')).toBeNull();
    expect(screen.getByText("Report ready")).toHaveClass("uppercase", "font-extrabold", "text-grey");
    expect(screen.getByRole("link", { name: "Read it →" })).toHaveAttribute("href", `/tasks/${TASK_ID}/result`);
    expect(container.querySelector("[data-tone]")).toHaveClass("bg-green");
  });

  it("has no Show steps when the read carries no steps", () => {
    const { container } = past({ run: run({}) });
    expect(container.querySelector("button")).toBeNull();
  });

  it("words its finish from its own walk and links to what that walk made", () => {
    const { container } = past({ run: run({ purpose: "longlist" }), capability: "options_scoping" });
    expect(container).toHaveTextContent(/^The longlist is ready14 min\s·Read it →$/);
    expect(screen.getByRole("link", { name: "Read it →" })).toHaveAttribute("href", `/tasks/${TASK_ID}/result?view=longlist`);
  });

  it("links a past baseline walk to the baseline, so the thread keeps a way to it after the longlist starts", () => {
    past({ run: run({ purpose: "baseline" }), capability: "options_scoping" });
    expect(screen.getByText("The baseline is ready")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Read it →" })).toHaveAttribute("href", `/tasks/${TASK_ID}/result?view=baseline`);
  });

  it("folds its steps behind Show steps, as the ended card does, with their counts, times and links", async () => {
    const user = userEvent.setup();
    past({ run: withStages({ purpose: "baseline" }), capability: "options_scoping" });
    const toggle = screen.getByRole("button", { name: "Show steps" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await user.click(toggle);
    expect(screen.getByRole("button", { name: "Hide steps" })).toHaveAttribute("aria-expanded", "true");
    const steps = within(screen.getByRole("list", { name: "Run steps" })).getAllByRole("listitem");
    expect(steps.map((step) => step.getAttribute("data-state"))).toEqual(["done", "done", "done"]);
    expect(steps[0]).toHaveTextContent("Searching");
    expect(steps[0]).toHaveTextContent("312 found · 1 min");
    expect(within(steps[0]).getByRole("link", { name: "Sources →" })).toHaveAttribute("href", `/tasks/${TASK_ID}/sources/all`);
    expect(steps[1]).toHaveTextContent("1 min 30 s");
    expect(within(steps[2]).getByRole("link", { name: "Baseline →" })).toHaveAttribute(
      "href",
      `/tasks/${TASK_ID}/result?view=baseline`,
    );
  });

  it("reads a bad ending with the red mark and no link", () => {
    const { container } = past({ run: run({ status: "failed" }) });
    expect(container).toHaveTextContent(/^Failed14 min$/);
    expect(container.querySelector("[data-tone]")).toHaveClass("bg-red");
    expect(container.querySelector("a")).toBeNull();
  });

  it("keeps a listed run that has not ended to its status word, with no link", () => {
    const { container } = past({ run: run({ status: "paused", ended_at: null }) });
    expect(container.querySelector("a")).toBeNull();
    expect(container.querySelector("button")).toBeNull();
    expect(container.querySelector("[data-tone]")).toHaveClass("bg-orange");
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

  it("holds the breathing activity line still under reduced motion (owner, round 8)", () => {
    expect(utility("anim-breathe-soft")).toMatch(/animation: breathe-soft 1\.6s/);
    expect(utility("anim-breathe-soft")).toMatch(/prefers-reduced-motion: reduce\)\s*\{\s*animation: none;/);
    expect(css).toMatch(/@keyframes breathe-soft \{[^}]*\}\s*50% \{\s*opacity: 0\.6;/);
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
