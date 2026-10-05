import { describe, expect, it } from "vitest";

import {
  BLUE,
  FRAMES,
  STATIC_LOGO_FRAME,
  framePaths,
  pathsAt,
  splashPathsAt,
} from "./foldMark";

describe("foldMark", () => {
  it("frame 5 (index 4) is the solid blue diamond logo", () => {
    const [folded, deg, colour] = FRAMES[STATIC_LOGO_FRAME]!;
    expect(folded).toHaveLength(4);
    expect(deg).toBe(0);
    expect(colour).toBe(BLUE);

    const paths = framePaths(STATIC_LOGO_FRAME);
    expect(paths).toHaveLength(1);
    expect(paths[0]!.fill).toBe(BLUE);
    // Closed diamond at 0°: midpoints of the square edges.
    expect(paths[0]!.d).toBe("M-75 0L0 -75L75 0L0 75Z");
  });

  it("pathsAt is deterministic at a fixed clock", () => {
    expect(pathsAt(0)).toEqual(pathsAt(0));
    expect(pathsAt(1.25)).toEqual(pathsAt(1.25));
  });

  it("splashPathsAt returns paths and a rotation for SVG transform", () => {
    const result = splashPathsAt(0);
    expect(result.paths.length).toBeGreaterThan(0);
    expect(typeof result.degrees).toBe("number");
    expect(result.frameIndex).toBeGreaterThanOrEqual(0);
  });
});
