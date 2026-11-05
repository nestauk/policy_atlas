import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it } from "vitest";

import { Card, Divider, PaneHeading, StatusMark, type StatusTone } from "./Card";
import { NavBar, NavItem, NavLogo } from "./Nav";

describe("Card family", () => {
  it("renders surface, heading, divider and status mark with a text label", () => {
    render(
      <Card>
        <PaneHeading>Sources</PaneHeading>
        <Divider />
        <p>
          <StatusMark tone="paused" /> Paused — waiting on your input
        </p>
      </Card>,
    );
    expect(screen.getByText("Sources")).toBeInTheDocument();
    expect(screen.getByText(/Paused — waiting on your input/)).toBeInTheDocument();
  });
});

describe("StatusMark (task 058; DESIGN.md § Status mark)", () => {
  const COLOURS: [StatusTone, string][] = [
    ["running", "bg-blue"],
    ["complete", "bg-green"],
    ["paused", "bg-orange"],
    ["failed", "bg-red"],
    ["idle", "bg-line-2"],
  ];

  it.each(COLOURS)("is a 6 px square in one colour per state: %s is %s", (tone, colour) => {
    const { container } = render(<StatusMark tone={tone} />);
    const mark = container.firstElementChild as HTMLElement;
    expect(mark).toHaveClass("size-1.5", colour);
    expect(mark.className).not.toMatch(/rounded/);
    expect(mark).toHaveAttribute("aria-hidden", "true");
  });

  it("breathes only while live", () => {
    const { container, rerender } = render(<StatusMark tone="running" breathing />);
    expect(container.firstElementChild).toHaveClass("anim-breathe");
    rerender(<StatusMark tone="running" />);
    expect(container.firstElementChild).not.toHaveClass("anim-breathe");
    rerender(<StatusMark tone="paused" breathing />);
    expect(container.firstElementChild).not.toHaveClass("anim-breathe");
  });
});

describe("Nav", () => {
  it("marks the active route with the growing underline", () => {
    const router = createMemoryRouter(
      [
        {
          path: "/",
          element: (
            <NavBar>
              <NavLogo />
              <div>
                <NavItem to="/">Workspace</NavItem>
                <NavItem to="/sources">Sources</NavItem>
              </div>
            </NavBar>
          ),
        },
      ],
      { initialEntries: ["/"] },
    );
    render(<RouterProvider router={router} />);
    const active = screen.getByRole("link", { name: "Workspace" });
    const inactive = screen.getByRole("link", { name: "Sources" });
    expect(active.className).toContain("border-blue");
    expect(inactive.className).not.toContain("border-blue");
    expect(screen.getByRole("navigation").className).toContain("w-full");
    expect(screen.getByRole("navigation").innerHTML).not.toContain("max-w-[1180px]");
  });
});
