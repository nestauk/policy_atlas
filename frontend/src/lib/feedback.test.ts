import { afterEach, describe, expect, it, vi } from "vitest";

import { feedbackEnabled } from "./feedback";

describe("feedbackEnabled", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("is off for every element when VITE_FEEDBACK is unset or empty", () => {
    expect(feedbackEnabled("cf")).toBe(false);
    vi.stubEnv("VITE_FEEDBACK", "");
    expect(feedbackEnabled("cf")).toBe(false);
  });

  it("is on only for the elements the list names", () => {
    vi.stubEnv("VITE_FEEDBACK", "cf, rap");
    expect(feedbackEnabled("cf")).toBe(true);
    expect(feedbackEnabled("rap")).toBe(true);
    // "clf" is not on because "cf" is: the match is on the whole name.
    expect(feedbackEnabled("clf")).toBe(false);
  });
});
