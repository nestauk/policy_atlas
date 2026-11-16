import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Popover, PopoverContent, PopoverTrigger } from "./Popover";
import { Sheet, SheetContent } from "./Sheet";

// Owner, round 13: every sheet and popover closes on a press outside it,
// the way the plan document now does. The shared Sheet (the dossier, the
// citation sheet, the option dossier) and the Popover (the Find popover,
// the name and account menus) are Radix layers that dismiss on an outside
// press; these keep it that way.
describe("outside press closes the shared overlays (round 13)", () => {
  it("closes the Sheet on a press outside its panel", async () => {
    const onOpenChange = vi.fn();
    const user = userEvent.setup();
    render(
      <Sheet open onOpenChange={onOpenChange}>
        <SheetContent title="Evidence for this claim">
          <p>Inside the sheet</p>
        </SheetContent>
      </Sheet>,
    );
    await user.click(screen.getByText("Inside the sheet"));
    expect(onOpenChange).not.toHaveBeenCalled();
    // The modal sheet lays a scrim over the page: a press outside lands on it.
    const scrim = document.querySelector<HTMLElement>(".bg-navy\\/40");
    expect(scrim).not.toBeNull();
    await user.click(scrim as HTMLElement);
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  });

  it("closes the Popover on a press outside it", async () => {
    const onOpenChange = vi.fn();
    const user = userEvent.setup();
    render(
      <>
        <p>The page</p>
        <Popover open onOpenChange={onOpenChange}>
          <PopoverTrigger>Find a task</PopoverTrigger>
          <PopoverContent>
            <p>Inside the popover</p>
          </PopoverContent>
        </Popover>
      </>,
    );
    await user.click(screen.getByText("Inside the popover"));
    expect(onOpenChange).not.toHaveBeenCalled();
    await user.click(screen.getByText("The page"));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
