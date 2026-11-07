import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Checkbox } from "./Checkbox";

describe("Checkbox", () => {
  it("is a checkbox named by its label, and reports the next state when pressed", async () => {
    const onChange = vi.fn();
    render(<Checkbox checked={false} label="Housing supply" onChange={onChange} />);
    const box = screen.getByRole("checkbox", { name: "Housing supply" });
    expect(box).toHaveAttribute("aria-checked", "false");
    await userEvent.setup().click(box);
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("draws the tick on Navy when checked, and the empty box at 40 % Navy", () => {
    const { rerender } = render(<Checkbox checked={false} label="A" onChange={vi.fn()} />);
    const mark = () => screen.getByRole("checkbox").querySelector("span[aria-hidden]");
    expect(mark()).toHaveClass("border-navy/40");
    expect(mark()?.querySelector("svg")).toBeNull();
    rerender(<Checkbox checked label="A" onChange={vi.fn()} />);
    expect(screen.getByRole("checkbox")).toHaveAttribute("aria-checked", "true");
    expect(mark()).toHaveClass("bg-navy", "border-navy");
    expect(mark()?.querySelector("svg")).not.toBeNull();
  });

  it("cannot be ticked when disabled", async () => {
    const onChange = vi.fn();
    render(<Checkbox checked={false} disabled label="A" onChange={onChange} />);
    const box = screen.getByRole("checkbox");
    expect(box).toBeDisabled();
    await userEvent.setup().click(box);
    expect(onChange).not.toHaveBeenCalled();
  });
});
