import { act, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { DisclosureChevron, DisclosureWord, useExpandForPrint } from "./Disclosure";

describe("DisclosureChevron", () => {
  it("points right when shut and turns down when open, Grey turning Navy with its control, still under reduced motion", () => {
    const { container, rerender } = render(<DisclosureChevron open={false} className="self-center" />);
    const glyph = container.querySelector("svg") as SVGElement;
    expect(glyph).toHaveAttribute("aria-hidden", "true");
    expect(glyph).toHaveAttribute("width", "12");
    expect(glyph).not.toHaveClass("rotate-90");
    expect(glyph).toHaveClass("text-grey", "group-hover:text-navy", "duration-200", "motion-reduce:transition-none", "self-center");
    rerender(<DisclosureChevron open />);
    expect(container.querySelector("svg")).toHaveClass("rotate-90");
  });
});

describe("DisclosureWord", () => {
  it("draws the one chevron before its word", () => {
    const { container } = render(<DisclosureWord open />);
    expect(container.querySelector("svg")).toHaveClass("rotate-90", "group-hover:text-navy");
  });

  it("reads Show when shut and Hide when open, hidden from assistive technology unless it names its button", () => {
    const { container, rerender } = render(<DisclosureWord open={false} />);
    expect(screen.getByText("Show")).toBeInTheDocument();
    expect(container.firstElementChild).toHaveAttribute("aria-hidden", "true");
    rerender(<DisclosureWord open named />);
    expect(screen.getByText("Hide")).toBeInTheDocument();
    expect(container.firstElementChild).not.toHaveAttribute("aria-hidden");
  });
});

describe("useExpandForPrint", () => {
  function Folded() {
    const [open, setOpen] = useState(false);
    useExpandForPrint(setOpen);
    return <p>{open ? "open" : "shut"}</p>;
  }

  it("opens a disclosure when the browser is about to print", () => {
    render(<Folded />);
    expect(screen.getByText("shut")).toBeInTheDocument();
    act(() => {
      window.dispatchEvent(new Event("beforeprint"));
    });
    expect(screen.getByText("open")).toBeInTheDocument();
  });
});
