import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { StageEntry, TaskAgentThreadRun } from "../../store";
import { PastRunLine, RunTrace } from "./RunTrace";

/*
 * A theory of change's walks in the shared run card (task 054's 058
 * alignment, A6, A7, A23): the automatic chain is one card, the draft's
 * rows first and one timer from its start; between the walks it reads
 * "Running" with the draft row done. The labels stand for the server's.
 */

const TASK_ID = "11111111-1111-1111-1111-111111111111";
const NOW = Date.parse("2026-11-09T10:10:00Z");
const ago = (seconds: number) => new Date(NOW - seconds * 1000).toISOString();

const draftRow: StageEntry = {
  stage: "toc_draft",
  label: "Drafting",
  status: "completed",
  startedAt: ago(600),
  seconds: 70,
  counts: [
    { value: 17, noun: "boxes" },
    { value: 17, noun: "connections" },
  ],
};
const searchRow: StageEntry = {
  stage: "toc_item_searches",
  label: "Searching each",
  status: "completed",
  startedAt: ago(520),
  seconds: 90,
  counts: [{ value: 412, noun: "found" }],
};

function walk(id: string, overrides: Partial<TaskAgentThreadRun>): TaskAgentThreadRun {
  return {
    capability_run_id: id,
    task_id: TASK_ID,
    plan_id: "p1",
    plan_version: 1,
    status: "succeeded",
    started_at: ago(600),
    ended_at: ago(0),
    stages: [],
    ...overrides,
  } as TaskAgentThreadRun;
}

const step = (row: StageEntry) => ({
  stage: row.stage,
  label: row.label,
  status: row.status,
  started_at: row.startedAt,
  seconds: row.seconds ?? null,
  counts: row.counts ?? [],
});

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(NOW);
});
afterEach(() => vi.useRealTimers());

describe("the automatic chain as one card (A7)", () => {
  it("draws the draft's rows first, times the card from the draft's start, and ends with the check's words", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const draft = walk("draft", { toc_walk: "draft", started_at: ago(600), ended_at: ago(530), stages: [step(draftRow)] as never });
    const check = walk("check", { toc_walk: "check", follows_capability_run_id: "draft", started_at: ago(529), ended_at: ago(0), stages: [step(searchRow)] as never });
    render(
      <MemoryRouter>
        <PastRunLine run={check} leadRun={draft} taskId={TASK_ID} capability="theory_of_change" />
      </MemoryRouter>,
    );
    const header = screen.getByTestId("trace-header");
    expect(header).toHaveTextContent("Evidence checked");
    // Ten minutes from the draft's start, not the check's.
    expect(within(header).getByTestId("trace-time")).toHaveTextContent("10 min");
    expect(within(header).getByRole("link", { name: "Read it →" })).toHaveAttribute("href", `/tasks/${TASK_ID}/result`);
    await user.click(screen.getByRole("button", { name: "Show steps" }));
    const rows = within(screen.getByRole("list", { name: "Run steps" })).getAllByRole("listitem");
    expect(rows.map((row) => row.textContent?.split(",")[0])).toEqual(["Drafting", "Searching each"]);
    expect(rows[0]).toHaveTextContent("17 boxes · 17 connections");
    expect(within(rows[1] as HTMLElement).getByRole("link", { name: "Sources →" })).toBeInTheDocument();
  });

  it("gives a walk the reader started its own card", () => {
    const check = walk("check", { toc_walk: "check", started_at: ago(300), stages: [step(searchRow)] as never });
    render(
      <MemoryRouter>
        <PastRunLine run={check} taskId={TASK_ID} capability="theory_of_change" />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("trace-time")).toHaveTextContent("5 min");
  });

  it("ends an upload's read with Theory drafted", () => {
    const read = walk("read", { toc_walk: "read", stages: [step({ ...draftRow, stage: "toc_read", label: "Reading" })] as never });
    render(
      <MemoryRouter>
        <PastRunLine run={read} taskId={TASK_ID} capability="theory_of_change" />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("trace-header")).toHaveTextContent("Theory drafted");
    expect(screen.getByRole("link", { name: "Read it →" })).toBeInTheDocument();
  });
});

describe("between the walks (A23, S10)", () => {
  it("stays Running with the draft row done until the check's first frame", () => {
    render(
      <MemoryRouter>
        <RunTrace
          taskId={TASK_ID}
          status="running"
          stages={[draftRow]}
          plan={null}
          startedAt={ago(600)}
          hasFindings={false}
          capability="theory_of_change"
          tocWalk="draft"
          isOwner
        />
      </MemoryRouter>,
    );
    const header = screen.getByTestId("trace-header");
    expect(header).toHaveTextContent("Running");
    expect(header).not.toHaveTextContent("Theory drafted");
    const row = within(screen.getByRole("list", { name: "Run steps" })).getByRole("listitem");
    expect(row).toHaveAttribute("data-state", "done");
    expect(row).toHaveTextContent("17 boxes · 17 connections");
  });

  it("ends a draft whose check was refused with the draft's own words", () => {
    render(
      <MemoryRouter>
        <RunTrace
          taskId={TASK_ID}
          status="succeeded"
          stages={[draftRow]}
          plan={null}
          startedAt={ago(600)}
          endedAt={ago(530)}
          hasFindings={false}
          capability="theory_of_change"
          tocWalk="draft"
          isOwner
        />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("trace-header")).toHaveTextContent("Theory drafted");
  });
});
