import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Button } from "./Button";
import { Chip } from "./Chip";

describe("Button", () => {
  it("renders the primary cutout variant and activates via keyboard", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Start the analysis</Button>);
    const button = screen.getByRole("button", { name: "Start the analysis" });
    expect(button.className).toContain("cutout");
    await userEvent.tab();
    expect(button).toHaveFocus();
    await userEvent.keyboard("{Enter}");
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("secondary and ghost variants drop the cutout", () => {
    render(
      <>
        <Button variant="secondary">Cancel</Button>
        <Button variant="ghost">Back to top</Button>
      </>,
    );
    expect(screen.getByRole("button", { name: "Cancel" }).className).not.toContain("cutout");
    expect(screen.getByRole("button", { name: "Back to top" }).className).not.toContain(
      "cutout",
    );
  });

  it("disabled is present but inert", async () => {
    const onClick = vi.fn();
    render(
      <Button disabled onClick={onClick}>
        Start the analysis
      </Button>,
    );
    const button = screen.getByRole("button", { name: "Start the analysis" });
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("defaults to type=button so it never submits forms accidentally", () => {
    render(<Button>Save changes</Button>);
    expect(screen.getByRole("button", { name: "Save changes" })).toHaveAttribute(
      "type",
      "button",
    );
  });
});

describe("Chip", () => {
  it("renders tones with their text labels", () => {
    render(
      <>
        <Chip tone="green">Complete</Chip>
        <Chip tone="yellow">Running</Chip>
        <Chip>Paused</Chip>
      </>,
    );
    expect(screen.getByText("Complete")).toBeInTheDocument();
    expect(screen.getByText("Running")).toBeInTheDocument();
    expect(screen.getByText("Paused")).toBeInTheDocument();
  });
});
