import { readFileSync } from "node:fs";
import { join } from "node:path";

import { act, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LifecycleBar } from "../brand/LifecycleBar";
import { GROWING_RULE_CLASS, NavItem } from "../brand/Nav";
import { Arrival, ArrivalProvider, useFirstPaintDone } from "./arrivals";
import { Collapse } from "./Collapse";

const css = readFileSync(join(__dirname, "../../index.css"), "utf8");
const artefactCss = readFileSync(join(__dirname, "../../views/artefact.css"), "utf8");
const block = (source: string, head: string) => {
  const start = source.indexOf(head);
  return source.slice(start, source.indexOf("\n}", start));
};

/** A thread whose content loads (`ready`) and whose blocks are listed. */
function Thread({ ready, ids }: { ready: boolean; ids: string[] }) {
  const settled = useFirstPaintDone(ready, "task-1");
  return (
    <ArrivalProvider settled={settled} scopeKey="task-1">
      {ids.map((id) => (
        <Arrival key={id} arrivalId={id} data-testid={id}>
          {id}
        </Arrival>
      ))}
    </ArrivalProvider>
  );
}

describe("arrivals", () => {
  afterEach(() => vi.useRealTimers());

  it("holds the history still and rises only what arrives after the first paint", () => {
    vi.useFakeTimers();
    const view = render(<Thread ready={false} ids={[]} />);
    view.rerender(<Thread ready ids={["a", "b"]} />);
    act(() => {
      vi.runAllTimers();
    });
    expect(screen.getByTestId("a")).not.toHaveClass("anim-rise");
    expect(screen.getByTestId("b")).not.toHaveClass("anim-rise");
    view.rerender(<Thread ready ids={["a", "b", "c"]} />);
    expect(screen.getByTestId("c")).toHaveClass("anim-rise");
  });

  it("does not rise again for a block whose id has been on screen (a streamed turn becoming the stored one)", () => {
    vi.useFakeTimers();
    const view = render(<Thread ready ids={[]} />);
    act(() => {
      vi.runAllTimers();
    });
    view.rerender(<Thread ready ids={["reply:1"]} />);
    expect(screen.getByTestId("reply:1")).toHaveClass("anim-rise");
    view.rerender(<Thread ready ids={[]} />);
    view.rerender(<Thread ready ids={["reply:1"]} />);
    expect(screen.getByTestId("reply:1")).not.toHaveClass("anim-rise");
  });

  it("rises nothing outside a scope", () => {
    render(<Arrival arrivalId="x" data-testid="x">x</Arrival>);
    expect(screen.getByTestId("x")).not.toHaveClass("anim-rise");
  });

  it("cuts the rise under reduced motion", () => {
    const rise = block(css, "@utility anim-rise {");
    expect(rise).toMatch(/prefers-reduced-motion: reduce\)\s*\{\s*animation-duration: 1ms;/);
  });
});

describe("Collapse", () => {
  it("cuts where Web Animations are missing (jsdom), still under reduced motion", () => {
    const view = render(
      <Collapse show durationMs={200}>
        <p>Rows</p>
      </Collapse>,
    );
    const box = screen.getByText("Rows").parentElement?.parentElement as HTMLElement;
    expect(box).toHaveClass("motion-reduce:transition-none");
    view.rerender(
      <Collapse show={false} durationMs={200}>
        <p>Rows</p>
      </Collapse>,
    );
    expect(screen.queryByText("Rows")).toBeNull();
  });
});

describe("the growing underline", () => {
  it("holds the growing rule still under reduced motion", () => {
    expect(GROWING_RULE_CLASS).toContain("motion-reduce:after:transition-none");
  });

  it("marks the current nav item and leaves a locked stage disabled", () => {
    render(
      <MemoryRouter initialEntries={["/tasks"]}>
        <NavItem to="/tasks">Tasks</NavItem>
        <NavItem to="/projects">Projects</NavItem>
        <LifecycleBar
          hint="Locked"
          items={[
            { tab: "agent", label: "Agent", to: "/tasks/t1", locked: false },
            { tab: "share", label: "Share", to: "/tasks/t1/share", locked: true },
          ]}
        />
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "Tasks" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Projects" })).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("link", { name: "Agent" })).not.toHaveAttribute("aria-current");
    expect(screen.getByText("Share").closest("[aria-disabled]")).toHaveAttribute("aria-disabled", "true");
  });
});

describe("the chip wave while claims are checked", () => {
  it("stops the chip wave under reduced motion", () => {
    expect(artefactCss).toMatch(/prefers-reduced-motion: reduce\)\s*\{\s*\.draft-checking \.pending-mark \{\s*animation: none;/);
  });
});
