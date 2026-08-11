import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { RailToggle, useRail } from "./rail";

/** Minimal consumer mirroring the WorkspaceView wiring. */
function Probe() {
  const rail = useRail("55%");
  return (
    <div style={{ width: rail.width }} data-testid="grid">
      <div style={{ width: 400 }}>
        <RailToggle collapsed={rail.collapsed} toggleProps={rail.toggleProps} />
        <div id={rail.regionId} hidden={rail.collapsed}>
          pane content
        </div>
        {!rail.collapsed && <div {...rail.separatorProps} data-testid="separator" />}
      </div>
    </div>
  );
}

describe("useRail", () => {
  it("collapse is a keyboard-operable button that hides the region and renames itself", async () => {
    render(<Probe />);
    const toggle = screen.getByRole("button", { name: "Collapse the planning rail" });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("pane content")).toBeVisible();

    await userEvent.tab();
    expect(toggle).toHaveFocus();
    await userEvent.keyboard("{Enter}");

    const expand = screen.getByRole("button", { name: "Expand the planning rail" });
    expect(expand).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByText("pane content")).not.toBeVisible();
    expect(screen.getByTestId("grid").style.width).toBe("48px");

    await userEvent.keyboard("{Enter}");
    expect(screen.getByText("pane content")).toBeVisible();
    expect(screen.getByTestId("grid").style.width).toBe("55%");
  });

  it("arrow keys resize within the clamped bounds", () => {
    render(<Probe />);
    const separator = screen.getByTestId("separator");
    expect(separator).toHaveAttribute("aria-orientation", "vertical");

    // jsdom reports zero layout width, so the first step starts from the
    // clamp floor — repeated presses must never leave the [280, 640] range.
    fireEvent.keyDown(separator, { key: "ArrowLeft" });
    expect(screen.getByTestId("grid").style.width).toBe("280px");
    for (let i = 0; i < 40; i++) {
      fireEvent.keyDown(separator, { key: "ArrowRight" });
    }
    const width = parseInt(screen.getByTestId("grid").style.width, 10);
    expect(width).toBeLessThanOrEqual(640);
    expect(width).toBeGreaterThanOrEqual(280);
  });
});
