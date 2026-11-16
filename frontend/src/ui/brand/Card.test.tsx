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
    expect(container.firstElementChild).toHaveClass("anim-breathe-mark");
    rerender(<StatusMark tone="running" />);
    expect(container.firstElementChild).not.toHaveClass("anim-breathe-mark");
    rerender(<StatusMark tone="paused" breathing />);
    expect(container.firstElementChild).not.toHaveClass("anim-breathe-mark");
  });

  it("breathes deeper than before and shrinks as it breathes (owner, round 11)", () => {
    const css = readFileSync(join(__dirname, "../../index.css"), "utf8");
    const block = (head: string) => css.slice(css.indexOf(head), css.indexOf("\n}", css.indexOf(head)));
    // The shared rhythm's trough is 0.25, for skeletons and placeholder bars too.
    expect(block("@keyframes breathe {")).toContain("opacity: 0.25");
    // The mark alone adds the scale, on the same 1.6 s rhythm.
    const mark = block("@keyframes breathe-mark {");
    expect(mark).toContain("opacity: 0.25");
    expect(mark).toContain("transform: scale(0.8)");
    const utility = block("@utility anim-breathe-mark {");
    expect(utility).toContain("breathe-mark 1.6s ease-in-out infinite");
    expect(utility).toContain("prefers-reduced-motion: reduce");
  });
});

describe("LiveMark (task 058; owner 2026-11-05: the live mark is the fold mark)", () => {
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
    expect(mark).toHaveStyle({ width: "14px", height: "14px" });
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
    // The active rule is the growing rule held at full width.
    expect(active).toHaveClass("after:scale-x-100", "font-extrabold");
    expect(inactive).not.toHaveClass("after:scale-x-100");
    expect(inactive).toHaveClass("after:scale-x-0");
    expect(screen.getByRole("navigation").className).toContain("w-full");
    expect(screen.getByRole("navigation").innerHTML).not.toContain("max-w-[1180px]");
  });
});
