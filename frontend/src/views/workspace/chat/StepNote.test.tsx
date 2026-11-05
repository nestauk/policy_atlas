import { STAGE_COUNTS } from "../../../mock/fixtures";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { act, render, renderHook, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createInitialRunStreamState, type PlanDraft, type RunStreamState, type StageEntry } from "../../../store";
import { cardRows } from "../runProgress";
import { STEP_NOTE_HOLD_MS, StepNote, useRailRun } from "./StepNote";

const TASK_ID = "11111111-1111-1111-1111-111111111111";
const NOW = Date.parse("2026-11-05T10:10:00Z");
const ago = (seconds: number) => new Date(NOW - seconds * 1000).toISOString();

function entry(overrides: Partial<StageEntry> & Pick<StageEntry, "stage" | "status">): StageEntry {
  const counts = STAGE_COUNTS[overrides.stage].flatMap(([key, noun]) => {
    const value = overrides.summary?.[key];
    return typeof value === "number" ? [{ value, noun }] : [];
  });
  return { label: "Searching and screening", startedAt: ago(70), counts, ...overrides };
}

const PLAN = {
  steps: [
    { stage: "acquire", label: "Searching and screening", row: "search_screen", blurb: "" },
    { stage: "screen", label: "Searching and screening", row: "search_screen", blurb: "" },
    { stage: "classify", label: "Classifying", row: "categorise", blurb: "" },
  ],
} as unknown as PlanDraft;

const SCREENING: StageEntry[] = [
  entry({ stage: "acquire", status: "completed", startedAt: ago(70), seconds: 40, summary: { acquired: 312 } }),
  entry({ stage: "screen", status: "started", startedAt: ago(30) }),
];
const SCREENED: StageEntry[] = [
  SCREENING[0],
  entry({ stage: "screen", status: "completed", startedAt: ago(30), seconds: 24, summary: { relevant: 118 } }),
];

function stream(stages: StageEntry[], liveness: RunStreamState["liveness"] = {}): RunStreamState {
  return {
    ...createInitialRunStreamState(),
    run: { id: "run-1", status: "running", startedAt: ago(372) },
    stages,
    liveness,
    plan: { plan: PLAN } as never,
  } as RunStreamState;
}

afterEach(() => {
  vi.useRealTimers();
});

describe("useRailRun (task 058, owner round 6)", () => {
  it("gives the rail the trace header's words", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    const { result } = renderHook(() =>
      useRailRun(TASK_ID, stream(SCREENING, { screen: { activity: "screening 61 new abstracts", heartbeat: false, dropped: 0, occurredAt: ago(0) } }), null, true, true),
    );
    expect(result.current.words).toBe("Searching and screening · screening 61 new abstracts");
  });

  it("notes a step that finishes while the rail is on show, and none already done when it mounts", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    const { result, rerender } = renderHook(({ s }) => useRailRun(TASK_ID, s, null, true, true), {
      initialProps: { s: stream(SCREENING) },
    });
    expect(result.current.note).toBeNull();
    rerender({ s: stream(SCREENED) });
    expect(result.current.note?.label).toBe("Searching and screening");
    const fresh = renderHook(() => useRailRun(TASK_ID, stream(SCREENED), null, true, true));
    expect(fresh.result.current.note).toBeNull();
  });

  it("gives no note while the sidebar is open, and none for a step that finished long ago (a replay)", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    const shut = renderHook(({ s }) => useRailRun(TASK_ID, s, null, true, false), { initialProps: { s: stream(SCREENING) } });
    shut.rerender({ s: stream(SCREENED) });
    expect(shut.result.current.note).toBeNull();
    const old = SCREENED.map((e) => ({ ...e, startedAt: ago(600) }));
    const replay = renderHook(({ s }) => useRailRun(TASK_ID, s, null, true, true), {
      initialProps: { s: stream([old[0], { ...old[1], status: "started" as const }]) },
    });
    replay.rerender({ s: stream(old) });
    expect(replay.result.current.note).toBeNull();
  });
});

describe("useRailRun — Writing's finish (lead, round 6)", () => {
  it("gives no note when Writing finishes: the title marker, the tab mark and the report say it", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    const plan = {
      steps: [...(PLAN.steps as unknown[]), { stage: "synthesise", label: "Writing", row: "synthesise", blurb: "" }],
    } as unknown as PlanDraft;
    const writing = (status: "started" | "completed") => ({
      ...stream([...SCREENED, entry({ stage: "synthesise", label: "Writing", status, startedAt: ago(10), seconds: status === "completed" ? 8 : undefined })]),
      plan: { plan } as never,
    });
    const { result, rerender } = renderHook(({ s }) => useRailRun(TASK_ID, s, null, true, true), {
      initialProps: { s: writing("started") },
    });
    rerender({ s: writing("completed") });
    expect(result.current.note).toBeNull();
  });
});

describe("StepNote", () => {
  const rows = cardRows(SCREENED, PLAN, "running");
  const context = { rows, taskId: TASK_ID, kind: "evidence_search" as const, hasFindings: false, nowMs: NOW };
  const note = (row = rows[0], onDone = vi.fn()) => (
    <MemoryRouter>
      <StepNote row={row} context={context} onDone={onDone} />
    </MemoryRouter>
  );

  it("reads the finished step's one line, link included, in a polite live region", () => {
    vi.useFakeTimers({ toFake: ["Date"], now: NOW });
    render(note());
    const region = screen.getByRole("status");
    expect(region).toHaveAttribute("aria-live", "polite");
    // Without the wall time (lead, round 6).
    expect(region).toHaveTextContent(/^Searching and screening · 312 found · 118 relevant · Sources →$/);
    expect(screen.getByRole("link", { name: "Sources →" })).toHaveAttribute("href", `/tasks/${TASK_ID}/sources/all`);
    // Paper, hairline, the overlay lift, square, Meta; no close control.
    expect(screen.getByTestId("step-note")).toHaveClass("step-note", "bg-paper", "border-line-2", "text-meta");
    expect(screen.getByTestId("step-note").className).toContain("shadow-[0_10px_30px_rgba(15,41,74,0.14)]");
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("holds about six seconds, then retracts; a pointer over it holds it", () => {
    vi.useFakeTimers();
    const onDone = vi.fn();
    render(note(rows[0], onDone));
    act(() => {
      vi.advanceTimersByTime(20);
    });
    const box = screen.getByTestId("step-note");
    expect(box).toHaveAttribute("data-shown", "true");
    act(() => {
      box.dispatchEvent(new PointerEvent("pointerover", { bubbles: true }));
    });
    act(() => {
      vi.advanceTimersByTime(STEP_NOTE_HOLD_MS * 2);
    });
    expect(box).toHaveAttribute("data-shown", "true");
    expect(onDone).not.toHaveBeenCalled();
    act(() => {
      box.dispatchEvent(new PointerEvent("pointerout", { bubbles: true }));
    });
    act(() => {
      vi.advanceTimersByTime(STEP_NOTE_HOLD_MS);
    });
    expect(box).toHaveAttribute("data-shown", "false");
    act(() => {
      vi.advanceTimersByTime(200);
    });
    expect(onDone).toHaveBeenCalledTimes(1);
  });

  it("slides on the strong ease-out and goes still under reduced motion", () => {
    const css = readFileSync(join(__dirname, "../../../index.css"), "utf8");
    const start = css.indexOf("@utility step-note {");
    const rule = css.slice(start, css.indexOf("\n}", start));
    expect(rule).toContain("var(--ease-out-strong)");
    expect(rule).toMatch(/prefers-reduced-motion: reduce\)\s*\{[\s\S]*clip-path: none;\s*transform: none;/);
    expect(rule).not.toMatch(/@keyframes|animation:/);
  });
});
