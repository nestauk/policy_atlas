import { describe, expect, it } from "vitest";

import { firstShownAt, markShown } from "./useIntent";

describe("the time of the first show", () => {
  it("is kept for each user and report, and the first time wins", () => {
    expect(firstShownAt("ada", "report-1")).toBeNull();

    const first = markShown("ada", "report-1", new Date("2026-11-18T09:00:00Z"));
    const again = markShown("ada", "report-1", new Date("2026-11-19T09:00:00Z"));

    expect(first).toBe("2026-11-18T09:00:00.000Z");
    expect(again).toBe(first);
    expect(firstShownAt("ada", "report-1")).toBe(first);
    expect(firstShownAt("ada", "report-2")).toBeNull();
    expect(firstShownAt("grace", "report-1")).toBeNull();
  });
});
