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
    expect(screen.getByText("Paused · waiting on you")).toBeInTheDocument();
  });
});

// Task 058 (owner, round 8): every row's mark is the 6 px square, so a
// running row's mark is the same size as a finished one's: blue and
// breathing while the run is live, orange while paused, green once done.
describe("TaskListRow — the status mark", () => {
  const startedAt = new Date(Date.now() - 60_000).toISOString();
  const markOf = (container: HTMLElement) => container.querySelector("[data-tone]") as HTMLElement;
  const liveMarkOf = (container: HTMLElement) => container.querySelector("[data-live-mark]") as HTMLElement | null;

  it("is the breathing blue square while the run is live, with its stage known or not", () => {
    const { container, unmount } = renderRow({
      latestRun: { capability_run_id: "r1", status: "running", started_at: startedAt },
      activeRun: { capability_run_id: "r1", status: "running", started_at: startedAt, stage: "acquire", stage_label: "Searching" },
    });
    expect(markOf(container)).toHaveClass("bg-blue", "size-1.5", "anim-breathe");
    expect(liveMarkOf(container)).toBeNull();
    unmount();
    const before = renderRow({ latestRun: { capability_run_id: "r1", status: "running", started_at: startedAt } });
    expect(markOf(before.container)).toHaveClass("bg-blue", "size-1.5", "anim-breathe");
    expect(liveMarkOf(before.container)).toBeNull();
  });

  it.each([
    ["paused", "bg-orange"],
    ["succeeded", "bg-green"],
    ["failed", "bg-red"],
  ] as const)("is %s → %s", (status, colour) => {
    const { container } = renderRow({ latestRun: { capability_run_id: "r1", status, started_at: startedAt } });
    expect(markOf(container)).toHaveClass(colour, "size-1.5");
    expect(liveMarkOf(container)).toBeNull();
  });
});

// Task 058, lists polish: the project prefix never hides the task's own
// name, several projects read as the first and a count (lead ruling P2),
// and phone rows are two fixed lines without owner or sources (P3).
describe("TaskListRow — layout (lists polish)", () => {
  it("shows the first project and a count, with every project in the hover text", () => {
    renderRow({
      showProjectPrefix: true,
      projectNames: ["Child health, Tower Hamlets", "Net zero homes"],
    });
    // Twice in the DOM: before the name from md up, on line 2 below md.
    const [desktop, phone] = screen.getAllByText("Child health, Tower Hamlets");
    expect(desktop.parentElement).toHaveClass("max-md:hidden");
    expect(phone.parentElement).toHaveClass("md:hidden");
    expect(screen.getAllByText("+1")).toHaveLength(2);
    expect(screen.queryByText("Net zero homes")).not.toBeInTheDocument();
    expect(screen.getByTitle("Child health, Tower Hamlets · Net zero homes")).toBeInTheDocument();
  });

  it("shows no count for a task in one project", () => {
    renderRow({ showProjectPrefix: true, projectNames: ["Net zero homes"] });
    expect(screen.queryByText(/^\+\d/)).not.toBeInTheDocument();
  });

  it("caps the prefix so the task's own name always shows", () => {
    renderRow({ showProjectPrefix: true, projectNames: ["Child health, Tower Hamlets"] });
    expect(screen.getByTitle("Child health, Tower Hamlets")).toHaveClass("max-w-[45%]", "shrink", "min-w-0");
    expect(screen.getByText("Youth employment")).toHaveClass("min-w-0", "flex-1", "truncate");
  });

  it("is one 56 px line from md up and two fixed lines below, without owner and sources", () => {
    renderRow({
      sourceCount: 46,
      showOwner: true,
      isOwner: false,
      ownerName: "Ada Lovelace",
      updatedAt: "2026-07-21T09:00:00Z",
    });
    expect(screen.getByRole("link")).toHaveClass("min-h-14", "py-3.5");
    expect(screen.getByText("Youth employment").parentElement).toHaveClass("max-md:col-span-2", "leading-7", "max-md:leading-6");
    const sources = screen.getByText("46").parentElement as HTMLElement;
    expect(sources).toHaveTextContent("46 sources");
    expect(sources).toHaveClass("max-md:hidden", "text-meta");
    // Only the digits take tabular figures; the space keeps its width.
    expect(screen.getByText("46")).toHaveClass("tabular-nums");
    expect(sources).not.toHaveClass("tabular-nums");
    expect(screen.getByText("Ada Lovelace")).toHaveClass("max-md:hidden");
  });

  it("deepens to Blue Tint the instant it is pressed (round 10)", () => {
    renderRow();
    expect(screen.getByRole("link")).toHaveClass("active:bg-blue-tint", "active:duration-0", "hover:bg-blue-tint-2");
  });
});

// Round 10, lead ruling 1: the accessible name is the row's content in
// order, never a label that drops the status.
describe("TaskListRow — the accessible name", () => {
  const thisYear = new Date().getFullYear();

  it("reads title · status · projects · owner · date", () => {
    renderRow({
      name: "Bus fare caps",
      latestRun: { capability_run_id: "r1", status: "paused", started_at: "2026-01-01T00:00:00Z" },
      showProjectPrefix: true,
      projectNames: ["Net zero homes", "Transport and access"],
      showOwner: true,
      isOwner: false,
      ownerName: "Grace Hopper",
      sourceCount: 41,
      capabilityKey: "evidence_search",
      updatedAt: `${thisYear}-10-15T09:00:00`,
    });
    expect(
      screen.getByRole("link", {
        name: "Bus fare caps · Paused · waiting on Grace · Net zero homes and Transport and access · Grace Hopper · 15 Oct",
      }),
    ).toBeInTheDocument();
  });

  it("carries the live step of a running row, and leaves out what the row does not show", () => {
    const startedAt = new Date(Date.now() - 14 * 60_000 - 5_000).toISOString();
    renderRow({
      latestRun: { capability_run_id: "r1", status: "running", started_at: startedAt },
      activeRun: { capability_run_id: "r1", status: "running", started_at: startedAt, stage: "screen", stage_label: "Screening" },
      updatedAt: "2025-10-12T09:00:00",
    });
    expect(screen.getByRole("link", { name: "Youth employment · Screening · 14 min · 12 Oct 2025" })).toBeInTheDocument();
  });

  it("says You for the reader's own row where the owner column shows, and skips a bare dash", () => {
    const { unmount } = renderRow({ showOwner: true, isOwner: true, ownerName: "Ada Lovelace" });
    expect(screen.getByRole("link", { name: "Youth employment · Not started · You" })).toBeInTheDocument();
    expect(screen.getByText("You")).toBeInTheDocument();
    unmount();
    renderRow({ showOwner: true, isOwner: false, ownerName: null });
    expect(screen.getByRole("link", { name: "Youth employment · Not started" })).toBeInTheDocument();
  });
});

// Round 10, lead rulings 3 to 5 and 7: the status column's words, the
// phone's second line, the capability as plain text, one date form.
describe("TaskListRow — round 10 words and layout", () => {
  const paused = { capability_run_id: "r1", status: "paused" as const, started_at: "2026-01-01T00:00:00Z" };

  it.each([
    [{ isOwner: true }, "Paused · waiting on you"],
    [{ isOwner: false, ownerName: "Grace Hopper" }, "Paused · waiting on Grace"],
    [{ isOwner: false, ownerName: null }, "Paused"],
  ])("names who a paused task waits on: %o → %s", (who, word) => {
    renderRow({ latestRun: paused, ...who });
    expect(screen.getByTitle(word)).toHaveTextContent(word);
  });

  it("uses one separator in the status column", () => {
    renderRow({ latestRun: { capability_run_id: "r1", status: "degraded", started_at: "2026-01-01T00:00:00Z" } });
    expect(screen.getByTitle("Complete · with gaps")).toBeInTheDocument();
  });

  it("shows the dash, not 0 sources, on a failed row (lead ruling, round 10)", () => {
    renderRow({ sourceCount: 0, latestRun: { capability_run_id: "r1", status: "failed", started_at: "2026-01-01T00:00:00Z" } });
    expect(screen.queryByText("0")).not.toBeInTheDocument();
    expect(screen.getByText("—")).toHaveClass("max-md:hidden");
  });

  it("reads Archived for an archived task, whatever its last run", () => {
    renderRow({ archived: true, latestRun: { capability_run_id: "r1", status: "succeeded", started_at: "2026-01-01T00:00:00Z" } });
    expect(screen.getByTitle("Archived")).toBeInTheDocument();
    expect(screen.queryByText("Complete")).not.toBeInTheDocument();
  });

  it("puts the status word first on the phone's second line, then the project, which gives way first", () => {
    renderRow({ latestRun: paused, showProjectPrefix: true, projectNames: ["Net zero homes"] });
    const word = screen.getByTitle("Paused · waiting on you");
    const cell = word.parentElement as HTMLElement;
    expect(word).toHaveClass("min-w-0", "truncate", "max-md:shrink-0");
    const phoneProject = cell.lastElementChild as HTMLElement;
    expect(phoneProject).toHaveClass("md:hidden", "min-w-0", "shrink-[1000]");
    expect(phoneProject).toHaveTextContent(/^·\s*Net zero homes$/);
  });

  it("shows the capability as plain Grey text, hidden on phones", () => {
    renderRow({ capabilityKey: "options_scoping" });
    const kind = screen.getByText("Options scoping");
    expect(kind).toHaveClass("text-meta", "text-grey", "max-md:hidden");
    expect(kind).not.toHaveClass("bg-blue-tint");
  });

  it("dates the row at Meta in the one list form", () => {
    const { container } = renderRow({ updatedAt: "2025-10-12T09:00:00" });
    const time = container.querySelector("time") as HTMLElement;
    expect(time).toHaveTextContent("12 Oct 2025");
    expect(time).toHaveClass("text-meta");
    expect(time).not.toHaveClass("text-caption", "tabular-nums");
  });
});
