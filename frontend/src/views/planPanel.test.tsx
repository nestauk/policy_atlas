import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PLAN_EXIT_MS, PlanPanelProvider, usePlanPanel } from "./planPanel";

function Panel() {
  const plan = usePlanPanel();
  return (
    <div>
      <button type="button" onClick={plan.openPlan}>
        Open
      </button>
      <button type="button" onClick={plan.closePlan}>
        Close
      </button>
      {plan.open && <p data-state={plan.closing ? "closed" : "open"}>the plan</p>}
    </div>
  );
}

describe("the plan panel leaves the way it came (owner, 2026-11-09)", () => {
  const restoreAnimate = HTMLElement.prototype.animate;
  afterEach(() => {
    HTMLElement.prototype.animate = restoreAnimate;
    vi.useRealTimers();
  });

  it("stays mounted, marked closed, for the exit, then closes", async () => {
    HTMLElement.prototype.animate = vi.fn() as unknown as typeof HTMLElement.prototype.animate;
    const user = userEvent.setup();
    render(
      <PlanPanelProvider>
        <Panel />
      </PlanPanelProvider>,
    );
    await user.click(screen.getByRole("button", { name: "Open" }));
    expect(screen.getByText("the plan")).toHaveAttribute("data-state", "open");
    vi.useFakeTimers();
    act(() => screen.getByRole("button", { name: "Close" }).click());
    expect(screen.getByText("the plan")).toHaveAttribute("data-state", "closed");
    act(() => vi.advanceTimersByTime(PLAN_EXIT_MS));
    expect(screen.queryByText("the plan")).toBeNull();
  });

  it("closes at once where no exit can run (jsdom, reduced motion)", async () => {
    const user = userEvent.setup();
    render(
      <PlanPanelProvider>
        <Panel />
      </PlanPanelProvider>,
    );
    await user.click(screen.getByRole("button", { name: "Open" }));
    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByText("the plan")).toBeNull();
  });

  it("an open during the exit keeps it open", async () => {
    HTMLElement.prototype.animate = vi.fn() as unknown as typeof HTMLElement.prototype.animate;
    const user = userEvent.setup();
    render(
      <PlanPanelProvider>
        <Panel />
      </PlanPanelProvider>,
    );
    await user.click(screen.getByRole("button", { name: "Open" }));
    vi.useFakeTimers();
    act(() => screen.getByRole("button", { name: "Close" }).click());
    act(() => screen.getByRole("button", { name: "Open" }).click());
    act(() => vi.advanceTimersByTime(PLAN_EXIT_MS * 2));
    expect(screen.getByText("the plan")).toHaveAttribute("data-state", "open");
  });
});
