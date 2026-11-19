import { readFileSync } from "node:fs";
import { join } from "node:path";

import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Card, Divider, LiveMark, PaneHeading, StatusMark, type StatusTone } from "./Card";
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

describe("StatusMark", () => {
  const TONES: StatusTone[] = ["running", "complete", "paused", "failed", "idle"];

  it.each(TONES)("is hidden from screen readers in every state: %s", (tone) => {
    const { container } = render(<StatusMark tone={tone} />);
    expect(container.firstElementChild).toHaveAttribute("aria-hidden", "true");
  });

  it("holds the breathing mark still under reduced motion", () => {
    const css = readFileSync(join(__dirname, "../../index.css"), "utf8");
    const head = "@utility anim-breathe-mark {";
    const utility = css.slice(css.indexOf(head), css.indexOf("\n}", css.indexOf(head)));
    expect(utility).toContain("prefers-reduced-motion: reduce");
  });
});

describe("LiveMark", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  function stubReducedMotion(reduce: boolean) {
    vi.stubGlobal("matchMedia", (query: string) => ({
      matches: reduce && query.includes("reduce"),
      media: query,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    }));
  }

  it("is the fold mark, 14 px in a line of text and 17 px in the rail, hidden from screen readers", () => {
    const { container, rerender } = render(<LiveMark />);
    const mark = container.firstElementChild as HTMLElement;
    expect(mark).toHaveAttribute("aria-hidden", "true");
    expect(mark.querySelector("svg")).toHaveAttribute("width", "14");
    rerender(<LiveMark size={17} />);
    expect(mark.querySelector("svg")).toHaveAttribute("width", "17");
    // Not the square: no tone, no fill class.
    expect(mark).not.toHaveAttribute("data-tone");
  });

  it("turns, and holds still under reduced motion", () => {
    const frames = vi.spyOn(window, "requestAnimationFrame");
    stubReducedMotion(false);
    const moving = render(<LiveMark />);
    expect(frames).toHaveBeenCalled();
    moving.unmount();
    frames.mockClear();
    stubReducedMotion(true);
    const { container } = render(<LiveMark />);
    expect(frames).not.toHaveBeenCalled();
    expect(container.querySelector("svg path")).not.toBeNull();
  });
});

describe("Nav", () => {
  it("holds the wordmark's mark still: one turning logo per screen, the run's own (owner, 2026-11-05)", () => {
    const frames = vi.spyOn(window, "requestAnimationFrame");
    const { container } = render(<NavLogo />);
    expect(container.querySelector("svg g[transform]")).toBeNull();
    expect(frames).not.toHaveBeenCalled();
    frames.mockRestore();
  });

  it("marks the active route as the current page", () => {
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
    expect(active).toHaveAttribute("aria-current", "page");
    expect(inactive).not.toHaveAttribute("aria-current");
  });
});
