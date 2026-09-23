import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { mockLonglist } from "../../mock/fixtures";
import { LonglistGrid } from "./LonglistGrid";

const TASK_ID = "11111111-1111-1111-1111-111111111111";

function renderGrid(showExcluded = false) {
  const longlist = mockLonglist();
  return render(
    <MemoryRouter>
      <LonglistGrid taskId={TASK_ID} longlist={longlist} showExcluded={showExcluded} />
    </MemoryRouter>,
  );
}

describe("LonglistGrid", () => {
  it("lays out rows by lever type (plus None fits) and columns by ambition band (plus Untagged)", () => {
    renderGrid();
    expect(screen.getByRole("row", { name: /Enforce existing powers/ })).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /None fits/ })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Do minimum" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Incremental" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Structural" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Untagged" })).toBeInTheDocument();
  });

  it("places each option's tile at its lever/ambition intersection and leaves an empty row empty", () => {
    renderGrid(true);
    const structuralCell = screen.getByRole("link", { name: "National sanctions regime" }).closest("td");
    expect(structuralCell).not.toBeNull();
    expect(within(structuralCell as HTMLElement).getByText("National sanctions regime")).toBeInTheDocument();
    expect(screen.queryByText("no option of this type on the longlist")).not.toBeInTheDocument();
    const emptyRow = screen.getByRole("row", { name: /Convene/ });
    expect(within(emptyRow).queryAllByRole("link")).toHaveLength(0);
  });

  it("hides excluded options until asked", () => {
    renderGrid();
    expect(screen.queryByRole("link", { name: "National sanctions regime" })).not.toBeInTheDocument();
  });

  it("carries the excluded state (struck through) and the no-in-scope-evidence tag on tiles", () => {
    renderGrid(true);
    const excludedLink = screen.getByRole("link", { name: "National sanctions regime" });
    expect(excludedLink.className).toContain("line-through");
    const excludedCell = excludedLink.closest("td") as HTMLElement;
    expect(within(excludedCell).getByText("excluded")).toBeInTheDocument();

    const noInScopeLink = screen.getByRole("link", { name: "School-based mentoring" });
    const noInScopeCell = noInScopeLink.closest("td") as HTMLElement;
    expect(within(noInScopeCell).getByText("no in-scope evidence")).toBeInTheDocument();
  });

  it("folds a crowded cell behind +N more", async () => {
    const user = userEvent.setup();
    const longlist = mockLonglist();
    const base = longlist.options![0];
    longlist.options = Array.from({ length: 9 }, (_, i) => ({
      ...base,
      option_id: `crowd-${i}`,
      name: `Crowd option ${i}`,
      state: "included" as const,
      primary_lever_type: "regulate",
      ambition: "incremental",
    }));
    render(
      <MemoryRouter>
        <LonglistGrid taskId={TASK_ID} longlist={longlist} />
      </MemoryRouter>,
    );
    expect(screen.getAllByRole("link", { name: /Crowd option/ })).toHaveLength(6);
    await user.click(screen.getByRole("button", { name: "+3 more" }));
    expect(screen.getAllByRole("link", { name: /Crowd option/ })).toHaveLength(9);
    await user.click(screen.getByRole("button", { name: "Show fewer −" }));
    expect(screen.getAllByRole("link", { name: /Crowd option/ })).toHaveLength(6);
  });

  it("has no shortlist action", () => {
    renderGrid();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("links a tile through to the option card", () => {
    renderGrid();
    const link = screen.getByRole("link", { name: "Youth guarantee" });
    expect(link).toHaveAttribute("href", expect.stringContaining("/options/"));
  });
});
