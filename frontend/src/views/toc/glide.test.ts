import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { easeOutStrong, useGlide, type GlideTarget } from "./glide";

describe("the glide's curve", () => {
  it("is the strong ease-out: fast at first, settling at the end", () => {
    expect(easeOutStrong(0)).toBe(0);
    expect(easeOutStrong(1)).toBe(1);
    // cubic-bezier(0.23, 1, 0.32, 1) is most of the way there by half time.
    expect(easeOutStrong(0.5)).toBeGreaterThan(0.9);
    const samples = Array.from({ length: 11 }, (_, i) => easeOutStrong(i / 10));
    expect(samples.every((value, i) => i === 0 || value >= (samples[i - 1] ?? 0))).toBe(true);
  });
});

describe("useGlide", () => {
  const at = (x: number, y: number, key = "k"): GlideTarget => ({ x, y, key });

  it("puts items at their places at once when it is not live", () => {
    const { result, rerender } = renderHook(({ targets }) => useGlide(targets, false, false), {
      initialProps: { targets: new Map([["a", at(0, 0)]]) },
    });
    rerender({ targets: new Map([["a", at(100, 50)]]) });
    expect(result.current.get("a")).toEqual({ x: 100, y: 50 });
  });

  it("starts a moved item where it was while live, and a reduced-motion reader sees it land", () => {
    const live = renderHook(({ targets }) => useGlide(targets, true, false), { initialProps: { targets: new Map([["a", at(0, 0)]]) } });
    live.rerender({ targets: new Map([["a", at(100, 50)]]) });
    expect(live.result.current.get("a")).toEqual({ x: 0, y: 0 });
    const reduced = renderHook(({ targets }) => useGlide(targets, true, true), { initialProps: { targets: new Map([["a", at(0, 0)]]) } });
    reduced.rerender({ targets: new Map([["a", at(100, 50)]]) });
    expect(reduced.result.current.get("a")).toEqual({ x: 100, y: 50 });
  });

  it("starts a stored box where its sketch twin was (the same key)", () => {
    const { result, rerender } = renderHook(({ targets, live }) => useGlide(targets, live, false), {
      initialProps: { targets: new Map([["sketch:b1", at(10, 20, "box:input|Ban")]]), live: true },
    });
    rerender({ targets: new Map([["stored-1", at(40, 20, "box:input|Ban")]]), live: false });
    expect(result.current.get("stored-1")).toEqual({ x: 10, y: 20 });
  });
});
