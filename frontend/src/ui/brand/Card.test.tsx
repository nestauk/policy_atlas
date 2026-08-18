import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it } from "vitest";

import { Card, Divider, PaneHeading, StatusDot } from "./Card";
import { NavBar, NavItem, NavLogo } from "./Nav";

describe("Card family", () => {
  it("renders surface, heading, divider and status dot with a text label", () => {
    render(
      <Card>
        <PaneHeading>Sources</PaneHeading>
        <Divider />
        <p>
          <StatusDot tone="paused" /> Paused — waiting on your input
        </p>
      </Card>,
    );
    expect(screen.getByText("Sources")).toBeInTheDocument();
    expect(screen.getByText(/Paused — waiting on your input/)).toBeInTheDocument();
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
