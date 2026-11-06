import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { InfoHint } from "./InfoHint";

const LINES = ["Theme: a group of options that work in a similar way.", "Lever: the kind of action government takes."];

// Round 12 (lead): one "i", two paths; a tap opens the words as a popover,
// hover and keyboard focus as the tooltip.
describe("InfoHint", () => {
  it("opens its words as a popover on a tap, and closes on a second tap", async () => {
    const user = userEvent.setup();
    render(<InfoHint label="What a theme and a lever are" note={LINES} />);
    const info = screen.getByRole("button", { name: "What a theme and a lever are" });
    await user.pointer({ keys: "[TouchA]", target: info });
    const popover = screen.getByRole("dialog", { name: "What a theme and a lever are" });
    expect(popover).toHaveTextContent(LINES.join(""));
    await user.pointer({ keys: "[TouchA]", target: info });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("opens no popover on a mouse click; keyboard focus shows the tooltip", async () => {
    const user = userEvent.setup();
    render(<InfoHint label="Policy Atlas's estimate" note="Policy Atlas's estimate from the sources." />);
    const info = screen.getByRole("button", { name: "Policy Atlas's estimate" });
    await user.click(info);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    act(() => info.blur());
    act(() => info.focus());
    expect((await screen.findAllByText("Policy Atlas's estimate from the sources.")).length).toBeGreaterThan(0);
  });
});
