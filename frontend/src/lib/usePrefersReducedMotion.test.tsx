import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { usePrefersReducedMotion } from "./usePrefersReducedMotion";

function PreferenceHarness() {
  return <output>{usePrefersReducedMotion() ? "reduce" : "no-preference"}</output>;
}

describe("usePrefersReducedMotion", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("reads and subscribes to the media preference", () => {
    let matches = false;
    let listener: (() => void) | undefined;
    vi.stubGlobal("matchMedia", vi.fn(() => ({
      get matches() { return matches; },
      addEventListener: (_event: string, callback: () => void) => { listener = callback; },
      removeEventListener: vi.fn(),
    })));

    render(<PreferenceHarness />);
    expect(screen.getByText("no-preference")).toBeInTheDocument();
    matches = true;
    act(() => listener?.());
    expect(screen.getByText("reduce")).toBeInTheDocument();
  });
});
