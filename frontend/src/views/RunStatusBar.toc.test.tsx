import { render, screen } from "@testing-library/react";
import { act, useSyncExternalStore } from "react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createInitialRunStreamState, type RunStreamState, type StageEntry } from "../store";
import { RunStatusBar } from "./RunStatusBar";
import { TaskListRow } from "./TaskListRow";
import * as taskLive from "./taskLive";

/*
 * The run status bar and the task list row for a theory of change's walks
 * (task 054's 058 alignment, A10): the server's step label and activity, and
 * the automatic chain read as one run. The labels stand for the server's.
 */

const NOW = Date.parse("2026-11-09T10:10:00Z");
const ago = (seconds: number) => new Date(NOW - seconds * 1000).toISOString();

const reads = vi.hoisted(() => {
  const listeners = new Set<() => void>();
  return {
    live: null as unknown,
    subscribe: (listener: () => void) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    notify: () => listeners.forEach((listener) => listener()),
  };
});

vi.mock("../api/queries", () => ({
  useTask: () => ({ data: { task_id: "t1", latest_run: null } }),
  useConversations: () => ({ isSuccess: true, data: { data: [{ id: "ta-1", kind: "task_agent", title: "Task Agent", closed_at: null }] } }),
}));
vi.mock("./taskLive", async (importOriginal) => {
  const actual = await importOriginal<typeof taskLive>();
  return { ...actual, useTaskLive: () => useSyncExternalStore(reads.subscribe, () => reads.live), useMountedTraces: () => 0 };
});

function stream(run: RunStreamState["run"], stages: StageEntry[], liveness: RunStreamState["liveness"] = {}): RunStreamState {
  return { ...createInitialRunStreamState(), connectionStatus: "connected", run, stages, liveness };
}

function live(state: RunStreamState) {
  act(() => {
    reads.live = { taskId: "t1", tab: "sources", stream: state, marks: taskLive.NO_MARKS, capability: "theory_of_change", isOwner: true, ownerName: null };
    reads.notify();
  });
}

const draftDone: StageEntry = { stage: "toc_draft", label: "Drafting", status: "completed", startedAt: ago(600), seconds: 70 };
const judging: StageEntry = { stage: "toc_judge", label: "Judging", status: "started", startedAt: ago(30) };

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"], now: NOW });
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: query.includes("min-width"), media: query, addEventListener: () => undefined, removeEventListener: () => undefined }));
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function renderBar() {
  return render(
    <MemoryRouter initialEntries={["/tasks/t1/sources"]}>
      <RunStatusBar />
    </MemoryRouter>,
  );
}

describe("the run status bar on a theory of change (A10)", () => {
  it("reads the server's step and activity, and links to the step's view", () => {
    reads.live = null;
    renderBar();
    live(
      stream({ id: "check", status: "running", startedAt: ago(500) }, [judging], {
        toc_judge: { activity: "judging · 30 of 64 documents", heartbeat: false, dropped: 0, occurredAt: ago(1) },
      }),
    );
    const bar = screen.getByTestId("run-status-bar");
    expect(bar).toHaveAttribute("data-open", "true");
    expect(bar.textContent?.replace(/\u00A0/g, " ")).toContain("Judging · judging · 30 of 64 documents");
    expect(screen.getByRole("link", { name: "Theory →" })).toHaveAttribute("href", "/tasks/t1/result");
  });

  it("stays open between the draft and its check, and times the check from the draft's start (S10)", () => {
    reads.live = null;
    renderBar();
    live(stream({ id: "draft", status: "running", startedAt: ago(600) }, [{ ...draftDone, status: "started" }]));
    // The draft lands: the check has not started yet.
    live(stream({ id: "draft", status: "succeeded", startedAt: ago(600), endedAt: ago(2) }, [draftDone]));
    expect(screen.getByTestId("run-status-bar")).toHaveAttribute("data-open", "true");
    // The check starts: the timer runs on from the draft's start.
    live(stream({ id: "check", status: "running", startedAt: ago(1) }, [judging]));
    expect(screen.getByTestId("run-status-bar")).toHaveTextContent("10 min");
  });
});

describe("the task list row on a theory of change (A10)", () => {
  it("reads the walk's step and its timer", () => {
    render(
      <MemoryRouter>
        <TaskListRow
          to="/tasks/t1"
          name="Wage subsidies and NEETs"
          capabilityKey="theory_of_change"
          latestRun={{ capability_run_id: "check", status: "running", started_at: ago(840) }}
          activeRun={{ capability_run_id: "check", status: "running", started_at: ago(840), stage: "toc_judge", stage_label: "Judging" }}
        />
      </MemoryRouter>,
    );
    expect(screen.getByTitle("Judging · 14 min")).toBeInTheDocument();
  });
});
