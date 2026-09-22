import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { mockLonglist } from "../../mock/fixtures";
import { LonglistGrid } from "./LonglistGrid";

const TASK_ID = "11111111-1111-1111-1111-111111111111";

function renderGrid() {
  const longlist = mockLonglist();
  return render(
    <MemoryRouter>
      <LonglistGrid taskId={TASK_ID} longlist={longlist} />
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

  it("places each option's tile at its lever/ambition intersection and shows an empty row's message", () => {
    renderGrid();
    const structuralCell = screen.getByRole("link", { name: "National sanctions regime" }).closest("td");
    expect(structuralCell).not.toBeNull();
    expect(within(structuralCell as HTMLElement).getByText("National sanctions regime")).toBeInTheDocument();
    expect(screen.getAllByText("no option of this type on the longlist").length).toBeGreaterThan(0);
  });

  it("carries the excluded state (struck through) and the no-in-scope-evidence tag on tiles", () => {
    renderGrid();
    const excludedLink = screen.getByRole("link", { name: "National sanctions regime" });
    expect(excludedLink.className).toContain("line-through");
    const excludedCell = excludedLink.closest("td") as HTMLElement;
    expect(within(excludedCell).getByText("excluded")).toBeInTheDocument();

    const noInScopeLink = screen.getByRole("link", { name: "School-based mentoring" });
    const noInScopeCell = noInScopeLink.closest("td") as HTMLElement;
    expect(within(noInScopeCell).getByText("no in-scope evidence")).toBeInTheDocument();
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
