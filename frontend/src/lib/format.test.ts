import { describe, expect, it } from "vitest";

import { formatCount } from "./format";
import { countOf } from "./vocabulary";

describe("formatCount", () => {
  it("groups thousands with a comma, en-GB", () => {
    expect(formatCount(0)).toBe("0");
    expect(formatCount(312)).toBe("312");
    expect(formatCount(1234)).toBe("1,234");
    expect(formatCount(1_234_567)).toBe("1,234,567");
  });
});

describe("countOf", () => {
  it("names the noun for one and for many, the count grouped", () => {
    expect(countOf(1, "option", "options")).toBe("1 option");
    expect(countOf(2, "option", "options")).toBe("2 options");
    expect(countOf(1200, "source", "sources")).toBe("1,200 sources");
  });
});
