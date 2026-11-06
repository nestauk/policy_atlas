import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ShortlistToggle, type useOptionActions } from "./optionActions";

type Actions = ReturnType<typeof useOptionActions>;

function actions(patch: Partial<Actions> = {}): Actions {
  return {
    walkActive: false,
    excludingId: null,
    setExcludingId: vi.fn(),
    notice: null,
    setNotice: vi.fn(),
    exclude: vi.fn(),
    include: vi.fn(),
    shortlist: vi.fn(),
    unshortlist: vi.fn(),
    shortlistPending: false,
    unshortlistPending: false,
    excludePending: false,
    includePending: false,
    ...patch,
  };
}

/** The words a sighted reader sees: the layer that is not faded out. */
function shownWords(button: HTMLElement): string {
  const layers = Array.from(button.children) as HTMLElement[];
  return layers
    .filter((layer) => !layer.className.split(" ").includes("opacity-0"))
    .map((layer) => layer.textContent)
    .join("");
}

describe("ShortlistToggle (round 11)", () => {
  it("says Shortlisted with the check mark at rest and Remove from shortlist on hover", async () => {
    const user = userEvent.setup();
    render(<ShortlistToggle actions={actions()} optionId="o1" shortlistState="proposed" excluded={false} />);
    const toggle = screen.getByRole("button", { name: "Shortlisted" });
    expect(toggle).toHaveAttribute("aria-pressed", "true");
    expect(toggle.querySelector("svg")).not.toBeNull();
    expect(shownWords(toggle)).toBe("Shortlisted");

    await user.hover(toggle);
    expect(shownWords(toggle)).toBe("Remove from shortlist");
    // The swap is visual: the name and the pressed state hold.
    expect(screen.getByRole("button", { name: "Shortlisted" })).toHaveAttribute("aria-pressed", "true");

    await user.unhover(toggle);
    expect(shownWords(toggle)).toBe("Shortlisted");
  });

  it("swaps on keyboard focus and holds its width with every label in one cell", async () => {
    const user = userEvent.setup();
    render(<ShortlistToggle actions={actions()} optionId="o1" shortlistState="added_by_you" excluded={false} />);
    const toggle = screen.getByRole("button", { name: "Shortlisted" });
    await user.tab();
    expect(toggle).toHaveFocus();
    expect(shownWords(toggle)).toBe("Remove from shortlist");
    // Both labels stay in the cell, so the button keeps the longest's width.
    expect(toggle.children).toHaveLength(2);
    for (const layer of Array.from(toggle.children)) expect(layer.className).toContain("col-start-1 row-start-1");
    fireEvent.blur(toggle);
    expect(shownWords(toggle)).toBe("Shortlisted");
  });

  it("gives the place up on a press and does not show the swap to the pointer that pressed", async () => {
    const user = userEvent.setup();
    const unshortlist = vi.fn();
    render(<ShortlistToggle actions={actions({ unshortlist })} optionId="o1" shortlistState="proposed" excluded={false} />);
    const toggle = screen.getByRole("button", { name: "Shortlisted" });
    await user.click(toggle);
    expect(unshortlist).toHaveBeenCalledWith("o1");
    expect(shownWords(toggle)).toBe("Shortlisted");
  });

  it("says Add to shortlist, unpressed, and never Remove from shortlist on an option without a place", async () => {
    const user = userEvent.setup();
    const shortlist = vi.fn();
    render(<ShortlistToggle actions={actions({ shortlist })} optionId="o2" shortlistState="set_aside" excluded={false} />);
    const toggle = screen.getByRole("button", { name: "Add to shortlist" });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    await user.hover(toggle);
    expect(shownWords(toggle)).toBe("Add to shortlist");
    await user.click(toggle);
    expect(shortlist).toHaveBeenCalledWith("o2");
  });

  it("does not swap on touch, where there is no hover", () => {
    render(<ShortlistToggle actions={actions()} optionId="o1" shortlistState="proposed" excluded={false} />);
    const toggle = screen.getByRole("button", { name: "Shortlisted" });
    fireEvent.pointerEnter(toggle, { pointerType: "touch" });
    expect(shownWords(toggle)).toBe("Shortlisted");
  });

  it("does not swap while a walk runs", async () => {
    const user = userEvent.setup();
    render(
      <ShortlistToggle actions={actions({ walkActive: true })} optionId="o1" shortlistState="proposed" excluded={false} />,
    );
    const toggle = screen.getByRole("button", { name: "Shortlisted" });
    expect(toggle).toBeDisabled();
    fireEvent.pointerEnter(toggle);
    await user.unhover(toggle);
    expect(shownWords(toggle)).toBe("Shortlisted");
  });
});
