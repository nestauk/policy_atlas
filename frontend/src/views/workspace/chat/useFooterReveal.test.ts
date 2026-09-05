import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { UIEvent, WheelEvent } from "react";

import { useFooterReveal } from "./useFooterReveal";

/** A scroll region of `clientHeight` 500 with `scrollHeight` 1500, positioned
 *  `fromEnd` px above its end. */
function region(fromEnd: number) {
  return { scrollHeight: 1500, clientHeight: 500, scrollTop: 1000 - fromEnd } as unknown as HTMLElement;
}
const scroll = (el: HTMLElement) => ({ currentTarget: el }) as unknown as UIEvent<HTMLElement>;
const wheel = (el: HTMLElement, deltaY: number) => ({ currentTarget: el, deltaY }) as unknown as WheelEvent<HTMLElement>;

describe("useFooterReveal — the footer opens on a deliberate nudge past the end, never on arrival", () => {
  it("arriving at the end does not open it; wheeling on past the end does", () => {
    const onChange = vi.fn();
    const { result } = renderHook(() => useFooterReveal(onChange));
    act(() => result.current.onScroll(scroll(region(0))));
    expect(onChange).not.toHaveBeenCalled();
    // A small nudge is not enough; the travel accumulates to the threshold.
    act(() => result.current.onWheel(wheel(region(0), 30)));
    expect(onChange).not.toHaveBeenCalled();
    act(() => result.current.onWheel(wheel(region(0), 60)));
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("wheeling down while not yet at the end does not count", () => {
    const onChange = vi.fn();
    const { result } = renderHook(() => useFooterReveal(onChange));
    act(() => result.current.onWheel(wheel(region(200), 500)));
    expect(onChange).not.toHaveBeenCalled();
  });

  it("any wheel up closes it and resets the nudge; scrolling well back up closes it too", () => {
    const onChange = vi.fn();
    const { result } = renderHook(() => useFooterReveal(onChange));
    act(() => result.current.onWheel(wheel(region(0), 100)));
    expect(onChange).toHaveBeenLastCalledWith(true);
    act(() => result.current.onWheel(wheel(region(0), -10)));
    expect(onChange).toHaveBeenLastCalledWith(false);
    // Reset: the next opening needs the full nudge again.
    act(() => result.current.onWheel(wheel(region(0), 40)));
    expect(onChange).toHaveBeenCalledTimes(2);
    act(() => result.current.onWheel(wheel(region(0), 40)));
    expect(onChange).toHaveBeenLastCalledWith(true);
    act(() => result.current.onScroll(scroll(region(200))));
    expect(onChange).toHaveBeenLastCalledWith(false);
  });
});
