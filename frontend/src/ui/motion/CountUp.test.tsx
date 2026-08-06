import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CountUp } from "./CountUp";

function mockMatchMedia(reduced: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockImplementation((query: string) => ({
      matches: reduced && query.includes("prefers-reduced-motion"),
      media: query,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    })),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("CountUp", () => {
  it("renders the initial value without animating on mount", () => {
    mockMatchMedia(false);
    render(<CountUp value={42} />);
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("snaps to the new value in a single frame under prefers-reduced-motion", () => {
    mockMatchMedia(true);
    const frames: FrameRequestCallback[] = [];
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
      frames.push(cb);
      return frames.length;
    });
    vi.stubGlobal("cancelAnimationFrame", () => undefined);
    const { rerender } = render(<CountUp value={0} />);
    rerender(<CountUp value={250} />);
    expect(frames).toHaveLength(1);
    act(() => frames[0](performance.now()));
    expect(screen.getByText("250")).toBeInTheDocument();
  });

  it("sweeps to the new value via requestAnimationFrame otherwise", async () => {
    mockMatchMedia(false);
    let now = 0;
    const frames: FrameRequestCallback[] = [];
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
      frames.push(cb);
      return frames.length;
    });
    vi.stubGlobal("cancelAnimationFrame", () => undefined);
    vi.spyOn(performance, "now").mockImplementation(() => now);

    const { rerender } = render(<CountUp value={0} />);
    rerender(<CountUp value={100} />);
    // Drive frames past the sweep duration; the shown value must land exactly.
    for (let i = 0; i < 20 && frames.length > i; i++) {
      now += 100;
      act(() => frames[i](now));
    }
    expect(screen.getByText("100")).toBeInTheDocument();
  });
});
