import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { Select, type SelectOption } from "./Select";

const OPTIONS: SelectOption[] = [
  { value: "ambition", label: "Ambition" },
  { value: "cost", label: "Cost", sub: "What it would cost to run" },
  { value: "coordination", label: "Coordination requirements" },
  { value: "complexity", label: "Delivery complexity" },
];

function Harness({ onChange = vi.fn(), disabled = false }: { onChange?: (value: string) => void; disabled?: boolean }) {
  const [value, setValue] = useState("cost");
  return (
    <>
      <button type="button">Before</button>
      <Select
        label="Columns"
        value={value}
        options={OPTIONS}
        disabled={disabled}
        onChange={(next) => {
          setValue(next);
          onChange(next);
        }}
      />
    </>
  );
}

// Round 12 (owner): the app's one dropdown, no native <select>.
describe("Select", () => {
  it("is a select-only combobox showing the chosen words, never a native select", () => {
    const { container } = render(<Harness />);
    const trigger = screen.getByRole("combobox", { name: "Columns" });
    expect(trigger.tagName).toBe("BUTTON");
    expect(trigger).toHaveAttribute("aria-haspopup", "listbox");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(trigger).toHaveTextContent("Cost");
    expect(container.querySelector("select")).toBeNull();
  });

  it("opens on the chosen option, moves with the arrows, Home and End, and picks with Enter", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    await user.tab();
    await user.tab();
    expect(screen.getByRole("combobox", { name: "Columns" })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("listbox", { name: "Columns" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /^Cost/ })).toHaveFocus();
    expect(screen.getByRole("option", { name: /^Cost/ })).toHaveAttribute("aria-selected", "true");
    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("option", { name: "Coordination requirements" })).toHaveFocus();
    await user.keyboard("{End}");
    expect(screen.getByRole("option", { name: "Delivery complexity" })).toHaveFocus();
    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("option", { name: "Delivery complexity" })).toHaveFocus();
    await user.keyboard("{Home}");
    expect(screen.getByRole("option", { name: "Ambition" })).toHaveFocus();
    await user.keyboard("{ArrowUp}");
    expect(screen.getByRole("option", { name: "Ambition" })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(onChange).toHaveBeenCalledWith("ambition");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    const trigger = screen.getByRole("combobox", { name: "Columns" });
    expect(trigger).toHaveTextContent("Ambition");
    expect(trigger).toHaveFocus();
  });

  it("opens with the down arrow, jumps by first letter, and closes on Escape without a change", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    const trigger = screen.getByRole("combobox", { name: "Columns" });
    trigger.focus();
    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("option", { name: /^Cost/ })).toHaveFocus();
    await user.keyboard("c");
    expect(screen.getByRole("option", { name: "Coordination requirements" })).toHaveFocus();
    await user.keyboard("c");
    expect(screen.getByRole("option", { name: /^Cost/ })).toHaveFocus();
    await user.keyboard("d");
    expect(screen.getByRole("option", { name: "Delivery complexity" })).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
    expect(trigger).toHaveFocus();
  });

  it("shows an option's grey line under its words, and stays shut when disabled", async () => {
    const user = userEvent.setup();
    const { unmount } = render(<Harness />);
    await user.click(screen.getByRole("combobox", { name: "Columns" }));
    expect(screen.getByText("What it would cost to run")).toHaveClass("text-grey");
    unmount();
    render(<Harness disabled />);
    const trigger = screen.getByRole("combobox", { name: "Columns" });
    expect(trigger).toBeDisabled();
    await user.click(trigger);
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("shows the placeholder in grey when no option is chosen", () => {
    render(<Select label="Add to a project" value="" placeholder="Choose a project" options={OPTIONS} onChange={vi.fn()} />);
    const trigger = screen.getByRole("combobox", { name: "Add to a project" });
    expect(trigger).toHaveTextContent("Choose a project");
    expect(screen.getByText("Choose a project")).toHaveClass("text-grey");
  });

  it("takes the caller's trigger, giving it the open state and the chosen option (round 12)", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <Select
        label="Strength"
        value="b"
        options={[{ value: "a", label: "Alpha" }, { value: "b", label: "Beta" }]}
        onChange={onChange}
        renderTrigger={({ open, chosen }) => (
          <button type="button" data-open={String(open)}>
            {`Own trigger: ${chosen?.label ?? "none"}`}
          </button>
        )}
      />,
    );
    const trigger = screen.getByRole("button", { name: "Own trigger: Beta" });
    expect(screen.queryByRole("combobox")).toBeNull();
    await user.click(trigger);
    expect(trigger).toHaveAttribute("data-open", "true");
    await user.click(within(screen.getByRole("listbox", { name: "Strength" })).getByRole("option", { name: "Alpha" }));
    expect(onChange).toHaveBeenCalledWith("a");
  });
});
