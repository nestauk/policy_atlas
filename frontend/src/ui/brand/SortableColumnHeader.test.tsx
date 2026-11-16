import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { TooltipProvider } from "../radix/Tooltip";
import { SortableColumnHeader } from "./SortableColumnHeader";

function renderHeader(props: Partial<Parameters<typeof SortableColumnHeader<"year">>[0]> = {}) {
  const onSort = vi.fn();
  render(
    <TooltipProvider>
      <table>
        <thead>
          <tr>
            <SortableColumnHeader column={{ key: "year", label: "Year" }} activeSort={null} activeOrder={null} onSort={onSort} {...props} />
          </tr>
        </thead>
      </table>
    </TooltipProvider>,
  );
  return onSort;
}

describe("SortableColumnHeader", () => {
  it("is a named button in a header that says its sort, the arrow's slot always kept", async () => {
    const onSort = renderHeader({ className: "my-cell" });
    const th = screen.getByRole("columnheader");
    expect(th).toHaveClass("my-cell");
    expect(th).toHaveAttribute("aria-sort", "none");
    const button = screen.getByRole("button", { name: "Sort by year" });
    expect(button).toHaveClass("whitespace-nowrap", "text-caption", "uppercase", "min-h-6");
    expect(button.querySelector("[data-testid='sort-arrow']")).not.toBeNull();
    await userEvent.setup().click(button);
    expect(onSort).toHaveBeenCalledWith("year");
  });

  it("points the arrow the way the column sorts", () => {
    renderHeader({ activeSort: "year", activeOrder: "asc" });
    expect(screen.getByRole("columnheader")).toHaveAttribute("aria-sort", "ascending");
    expect(screen.getByTestId("sort-arrow").getAttribute("class")).toContain("rotate-180");
  });
});
