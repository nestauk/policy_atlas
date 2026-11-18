import { describe, expect, it } from "vitest";

import { firstShownAt, markShown, intentCardState } from "./useIntent";

describe("intentCardState (the show-once rules)", () => {
  it("asks on the first open of a report", () => {
    expect(intentCardState(undefined, false)).toBe("ask");
  });

  it("does not ask again on a later open when the question was not answered", () => {
    expect(intentCardState(undefined, true)).toBe("hidden");
  });

  it("never asks again after Not now", () => {
    expect(intentCardState("dismissed", false)).toBe("hidden");
    expect(intentCardState("dismissed", true)).toBe("hidden");
  });

  it.each(["as_is", "with_edits", "no"])(
    "shows the editable answer line after %s, on every open",
    (answer) => {
      expect(intentCardState(answer, false)).toBe("answered");
      expect(intentCardState(answer, true)).toBe("answered");
    },
  );
});

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
