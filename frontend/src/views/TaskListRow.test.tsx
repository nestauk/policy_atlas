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
