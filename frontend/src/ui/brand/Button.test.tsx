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

  it("primary keeps white text alongside the type-scale size token", () => {
    // tailwind-merge treated the unknown text-meta scale token as a text
    // COLOUR and stripped text-white — ink-on-blue buttons live (028).
    render(<Button>New project</Button>);
    const className = screen.getByRole("button", { name: "New project" }).className;
    expect(className).toContain("text-white");
    expect(className).toContain("text-meta");
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
