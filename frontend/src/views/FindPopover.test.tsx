import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FIND_DEBOUNCE_MS, FindPopover, findMatches, type FindItem } from "./FindPopover";

const ITEMS: FindItem[] = [
  { id: "a", label: "Childhood obesity in schools", href: "/tasks/a", updatedAt: "2026-11-01T10:00:00Z" },
  { id: "b", label: "Youth employment pathways", href: "/tasks/b", updatedAt: "2026-11-05T10:00:00Z" },
  { id: "c", label: "School meals and attainment", href: "/tasks/c", updatedAt: "2026-11-03T10:00:00Z" },
  { id: "d", label: "Active travel to school", href: "/tasks/d", updatedAt: "2026-10-20T10:00:00Z" },
  { id: "e", label: "Housing retrofit", href: "/tasks/e", updatedAt: "2026-10-01T10:00:00Z" },
  { id: "f", label: "Heat pumps uptake", href: "/tasks/f", updatedAt: "2026-09-01T10:00:00Z" },
];

function Where() {
  return <p data-testid="where">{useLocation().pathname}</p>;
}

function renderFind() {
  return render(
    <MemoryRouter initialEntries={["/tasks"]}>
      <FindPopover items={ITEMS} copy={{ label: "Find a task", noun: "tasks" }} />
      <Routes>
        <Route path="*" element={<Where />} />
      </Routes>
    </MemoryRouter>,
  );
}

/** Let the debounce settle. */
async function settle() {
  await act(async () => {
    vi.advanceTimersByTime(FIND_DEBOUNCE_MS + 10);
  });
}

describe("findMatches", () => {
  it("offers the five most recent when nothing is typed", () => {
    expect(findMatches(ITEMS, "  ").map((item) => item.id)).toEqual(["b", "c", "a", "d", "e"]);
  });

  it("keeps an item whose name holds every typed word, in any order and case", () => {
    expect(findMatches(ITEMS, "SCHOOL meals").map((item) => item.id)).toEqual(["c"]);
    expect(findMatches(ITEMS, "school").map((item) => item.id)).toEqual(["a", "c", "d"]);
  });
});

describe("FindPopover", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("opens with the field focused, its placeholder, the recent five and no result line", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderFind();
    await user.click(screen.getByRole("button", { name: "Find a task" }));
    const field = screen.getByRole("combobox", { name: "Find a task" });
    expect(field).toHaveFocus();
    expect(field).toHaveAttribute("placeholder", "Search your tasks by name");
    expect(screen.getAllByRole("option")).toHaveLength(5);
    expect(screen.queryByText(/match/)).toBeNull();
    expect(screen.queryByText(/Nothing matches/)).toBeNull();
  });

  it("filters as the user types, after the debounce, and says so only once there are words", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderFind();
    await user.click(screen.getByRole("button", { name: "Find a task" }));
    await user.type(screen.getByRole("combobox"), "school");
    await settle();
    expect(screen.getAllByRole("option").map((option) => option.textContent)).toEqual([
      "Childhood obesity in schools",
      "School meals and attainment",
      "Active travel to school",
    ]);
    // The matched words are not marked: rows are plain Navy text.
    expect(screen.getAllByRole("option")[0].querySelector("mark, .text-blue")).toBeNull();

    await user.type(screen.getByRole("combobox"), " zebra");
    await settle();
    expect(screen.getByRole("status")).toHaveTextContent("No tasks match “school zebra”");
    expect(screen.queryAllByRole("option")).toHaveLength(0);
  });

  it("moves the highlight with the arrow keys and opens the highlighted row on Enter", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderFind();
    await user.click(screen.getByRole("button", { name: "Find a task" }));
    const field = screen.getByRole("combobox");
    expect(screen.getAllByRole("option")[0]).toHaveAttribute("aria-selected", "true");
    await user.keyboard("{ArrowDown}{ArrowDown}");
    const options = screen.getAllByRole("option");
    expect(options[2]).toHaveAttribute("aria-selected", "true");
    expect(field).toHaveAttribute("aria-activedescendant", options[2].id);
    await user.keyboard("{ArrowUp}");
    expect(screen.getAllByRole("option")[1]).toHaveAttribute("aria-selected", "true");
    await user.keyboard("{Enter}");
    expect(screen.getByTestId("where")).toHaveTextContent("/tasks/c");
    expect(screen.queryByRole("combobox")).toBeNull();
  });

  it("closes on Escape and gives focus back to the trigger", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderFind();
    const trigger = screen.getByRole("button", { name: "Find a task" });
    await user.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("combobox")).toBeNull();
    expect(trigger).toHaveFocus();
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });
});
