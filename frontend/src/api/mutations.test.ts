import { describe, expect, it } from "vitest";

import { taskNameFromQuestion } from "./mutations";

describe("taskNameFromQuestion", () => {
  it("drops a trailing question mark", () => {
    expect(taskNameFromQuestion("What works?")).toBe("What works");
  });

  it("collapses whitespace", () => {
    expect(taskNameFromQuestion("What   works   best?")).toBe("What works best");
  });

  it("returns short questions unchanged", () => {
    expect(taskNameFromQuestion("Short question")).toBe("Short question");
  });

  it("clips long questions on a word boundary with an ellipsis, never exceeding the max by more than the ellipsis", () => {
    const long = "word ".repeat(30).trim();
    const max = 80;
    const result = taskNameFromQuestion(long, max);
    expect(result.endsWith("…")).toBe(true);
    expect(result.length).toBeLessThanOrEqual(max + 1);
    expect(result.slice(0, -1)).not.toMatch(/\s$/);
  });
});
