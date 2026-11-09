import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ReferenceUrl } from "./ReferenceUrl";

describe("ReferenceUrl", () => {
  it("shows the address without its scheme and opens it in a new tab", () => {
    render(<ReferenceUrl url="https://doi.org/10.1000/x/" />);
    const link = screen.getByRole("link", { name: "doi.org/10.1000/x" });
    expect(link).toHaveAttribute("href", "https://doi.org/10.1000/x/");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(link).toHaveClass("text-grey", "hover:text-navy");
    expect(link.querySelector(".print\\:inline")).toBeNull();
  });

  it("prints the full address when asked (the References)", () => {
    render(<ReferenceUrl url="https://doi.org/10.1000/x" printFull />);
    const link = screen.getByRole("link");
    expect(link.querySelector(".print\\:hidden")).toHaveTextContent("doi.org/10.1000/x");
    expect(link.querySelector(".print\\:inline")).toHaveTextContent("https://doi.org/10.1000/x");
  });

  it("draws nothing for an address that is not http or https", () => {
    const { container } = render(<ReferenceUrl url="javascript:alert(1)" />);
    expect(container).toBeEmptyDOMElement();
  });
});
