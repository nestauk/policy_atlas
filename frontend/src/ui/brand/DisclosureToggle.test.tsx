import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DisclosureToggle } from "./DisclosureToggle";

describe("DisclosureToggle", () => {
  it("is the chevron and the quiet words, named by its words, expanded as it is open", async () => {
    const onToggle = vi.fn();
    const { rerender } = render(
      <DisclosureToggle open={false} onToggle={onToggle}>
        Show all 6 connections
      </DisclosureToggle>,
    );
    const button = screen.getByRole("button", { name: "Show all 6 connections" });
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(button.querySelector("svg")).not.toBeNull();
    expect(button).toHaveClass("text-grey", "font-semibold");
    await userEvent.setup().click(button);
    expect(onToggle).toHaveBeenCalledOnce();
    rerender(
      <DisclosureToggle open onToggle={onToggle}>
        Hide
      </DisclosureToggle>,
    );
    expect(screen.getByRole("button", { name: "Hide" })).toHaveAttribute("aria-expanded", "true");
  });
});
