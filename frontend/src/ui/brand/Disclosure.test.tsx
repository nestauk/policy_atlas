import { act, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { DisclosureWord, useExpandForPrint } from "./Disclosure";

describe("DisclosureWord", () => {
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
