import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { TaskListRow } from "./TaskListRow";

function renderRow(props: Partial<Parameters<typeof TaskListRow>[0]> = {}) {
  return render(
    <MemoryRouter>
      <TaskListRow to="/tasks/t1" name="Youth employment" {...props} />
    </MemoryRouter>,
  );
}

// Task 044: the kind of work comes from `TaskOut.capability`, which the API
// did not carry before this slice — the row used to label every task
// "Evidence search" by fallback. No depth is shown beside it (owner ruling,
// dropping C17: there is no API field for it and there should not be one).
describe("TaskListRow — the capability label", () => {
  it("shows the kind named by the API field", () => {
    renderRow({ capabilityKey: "options_scoping" });
    expect(screen.getByText("Options scoping")).toBeInTheDocument();
  });

  it("shows Evidence search for a row with no capability at all", () => {
    renderRow({ capabilityKey: null });
    expect(screen.getByText("Evidence search")).toBeInTheDocument();
  });

  it("shows an unknown key rather than nothing", () => {
    renderRow({ capabilityKey: "something_later" });
    expect(screen.getByText("something_later")).toBeInTheDocument();
  });

  it("shows no depth beside the kind", () => {
    renderRow({ capabilityKey: "options_scoping" });
    for (const depth of ["Rapid", "Standard", "Deep", "rapid", "standard"]) {
      expect(screen.queryByText(depth)).not.toBeInTheDocument();
    }
  });
});

// Task 058 (N15): a running task's row says where its run is.
describe("TaskListRow — the running stage", () => {
  const startedAt = new Date(Date.now() - 14 * 60_000 - 5_000).toISOString();

  it("reads the active run's stage label and elapsed time", () => {
    renderRow({
      latestRun: { capability_run_id: "r1", status: "running", started_at: startedAt },
      activeRun: { capability_run_id: "r1", status: "running", started_at: startedAt, stage: "synthesise", stage_label: "Writing" },
    });
    expect(screen.getByTitle("Writing · 14 min")).toHaveTextContent("Writing · 14 min");
    expect(screen.queryByText("Analysing the evidence…")).toBeNull();
  });

  it("keeps the status word when no stage is known, and once the run has finished", () => {
    renderRow({ latestRun: { capability_run_id: "r1", status: "running", started_at: startedAt } });
    expect(screen.getByText("Analysing the evidence…")).toBeInTheDocument();
  });

  it("keeps the paused word while a check-in waits", () => {
    renderRow({
      latestRun: { capability_run_id: "r1", status: "paused", started_at: startedAt },
      activeRun: { capability_run_id: "r1", status: "paused", started_at: startedAt, stage: "screen", stage_label: "Searching and screening" },
    });
    expect(screen.getByText("Paused — waiting on your input")).toBeInTheDocument();
  });
});

// Task 058 (owner, 2026-11-05): the row's status is the 6 px square mark,
// blue while the run is live, orange while paused, green once done.
describe("TaskListRow — the status mark", () => {
  const startedAt = new Date(Date.now() - 60_000).toISOString();
  const markOf = (container: HTMLElement) => container.querySelector("[data-tone]") as HTMLElement;

  it("is blue while the run is live", () => {
    const { container } = renderRow({
      latestRun: { capability_run_id: "r1", status: "running", started_at: startedAt },
      activeRun: { capability_run_id: "r1", status: "running", started_at: startedAt, stage: "acquire", stage_label: "Searching and screening" },
    });
    expect(markOf(container)).toHaveClass("bg-blue", "size-1.5");
    expect(markOf(container).className).not.toMatch(/rounded|bg-yellow/);
  });

  it.each([
    ["paused", "bg-orange"],
    ["succeeded", "bg-green"],
    ["failed", "bg-red"],
  ] as const)("is %s → %s", (status, colour) => {
    const { container } = renderRow({ latestRun: { capability_run_id: "r1", status, started_at: startedAt } });
    expect(markOf(container)).toHaveClass(colour);
  });
});
