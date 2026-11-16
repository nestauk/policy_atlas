import { readFileSync } from "node:fs";
import { join } from "node:path";

import { act, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LifecycleBar } from "../brand/LifecycleBar";
import { GROWING_RULE_ACTIVE_CLASS, GROWING_RULE_CLASS, NavItem } from "../brand/Nav";
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

describe("arrivals (task 058, round 9; the animation sweep's entry 2)", () => {
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

  it("is one rise on the strong ease-out, a cut under reduced motion", () => {
    const rise = block(css, "@utility anim-rise {");
    expect(rise).toContain("animation: rise 300ms var(--ease-out-strong) both");
    expect(rise).toMatch(/prefers-reduced-motion: reduce\)\s*\{\s*animation-duration: 1ms;/);
  });
});

describe("Collapse", () => {
  it("cuts where Web Animations are missing (jsdom) and opens with its height on the strong ease-out", () => {
    const view = render(
      <Collapse show durationMs={200}>
        <p>Rows</p>
      </Collapse>,
    );
    const box = screen.getByText("Rows").parentElement?.parentElement as HTMLElement;
    expect(box).toHaveClass("grid", "grid-rows-[1fr]", "transition-[grid-template-rows,opacity]", "motion-reduce:transition-none");
    expect(box.style.transitionDuration).toBe("200ms");
    // At rest it does not clip, so focus rings and shadows inside show.
    expect(screen.getByText("Rows").parentElement).not.toHaveClass("overflow-hidden");
    view.rerender(
      <Collapse show={false} durationMs={200}>
        <p>Rows</p>
      </Collapse>,
    );
    expect(screen.queryByText("Rows")).toBeNull();
  });
});

describe("the growing underline (owner, round 9)", () => {
  it("grows a blue rule from the left edge to the centre on hover and focus, over 200 ms, still under reduced motion", () => {
    for (const name of [
      "after:scale-x-0",
      "after:origin-left",
      "after:bg-blue",
      "after:h-[3px]",
      "after:duration-200",
      "after:ease-[var(--ease-out-strong)]",
      "hover:after:scale-x-50",
      "focus-visible:after:scale-x-50",
      "motion-reduce:after:transition-none",
    ]) {
      expect(GROWING_RULE_CLASS).toContain(name);
    }
    expect(GROWING_RULE_CLASS).not.toContain("after:origin-center");
  });

  it("holds the active item's rule at full width, the same rule continuing past the centre", () => {
    for (const name of ["after:scale-x-100", "hover:after:scale-x-100", "focus-visible:after:scale-x-100"]) {
      expect(GROWING_RULE_ACTIVE_CLASS).toContain(name);
    }
  });

  it("is on the top nav's items and the lifecycle tabs, the active rule full and still", () => {
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
    // The active item's rule is the growing rule at full width (not a
    // border), so a click continues the hover's half rule.
    const tasks = screen.getByRole("link", { name: "Tasks" });
    expect(tasks).toHaveClass("border-transparent", "after:scale-x-100", "hover:after:scale-x-100");
    expect(tasks).not.toHaveClass("after:scale-x-0", "hover:after:scale-x-50");
    const projects = screen.getByRole("link", { name: "Projects" });
    expect(projects).toHaveClass("border-transparent", "after:scale-x-0", "hover:after:scale-x-50");
    const agent = screen.getByRole("link", { name: "Agent" });
    expect(agent).toHaveClass("after:scale-x-0", "hover:after:scale-x-50");
    // A locked stage has no rule to grow.
    expect(screen.getByText("Share").closest("[aria-disabled]")).not.toHaveClass("hover:after:scale-x-50");
  });
});

describe("the chip wave while claims are checked (owners, rounds 9 and 11)", () => {
  it("pulses each chip narrowly to the checked marker's blue look with a halo, every 2 s, 350 ms apart", () => {
    const keyframes = block(artefactCss, "@keyframes checking-pulse {");
    expect(keyframes).toContain("background-color: var(--color-blue-tint-2)");
    expect(keyframes).toContain("border-color: rgb(0 0 255 / 0.25)");
    expect(keyframes).toContain("color: rgb(0 0 255 / 0.8)");
    expect(keyframes).toContain("box-shadow: 0 0 0 1px rgb(0 0 255 / 0.35)");
    expect(keyframes).not.toContain("opacity");
    // A narrow pulse: muted to 25 %, in by 40 %, held to 50 %, out by 65 %
    // (300 ms each way on a 2 s cycle).
    expect(keyframes).toMatch(/0%,\s*25%,\s*65%,\s*100% \{/);
    expect(keyframes).toMatch(/40%,\s*50% \{/);
    const rule = block(artefactCss, ".draft-checking .pending-mark {");
    expect(rule).toContain("checking-pulse 2s ease-in-out infinite");
    expect(rule).toContain("calc(var(--mark-at, 0) * 350ms)");
    expect(artefactCss).toMatch(/prefers-reduced-motion: reduce\)\s*\{\s*\.draft-checking \.pending-mark \{\s*animation: none;/);
  });
});

describe("the check-in ring", () => {
  it("is the ring only, blooming 150 ms after the card arrives", () => {
    const glow = block(css, "@keyframes glow-in {");
    expect(glow).not.toContain("opacity");
    expect(block(css, "@utility anim-glow {")).toContain("glow-in 900ms ease-out 150ms both");
  });
});
