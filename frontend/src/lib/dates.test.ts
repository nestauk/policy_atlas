import { describe, expect, it } from "vitest";

import { formatDate } from "./dates";

// Round 10, lead ruling P7: one date form for every reader (the lists).
describe("formatDate, short", () => {
  const now = new Date(2026, 10, 6, 12);

  it("drops the year within the current year", () => {
    expect(formatDate(new Date(2026, 10, 5, 9).toISOString(), "short", { now })).toBe("5 Nov");
    expect(formatDate(new Date(2026, 0, 1, 0, 30).toISOString(), "short", { now })).toBe("1 Jan");
  });

  it("keeps the year before it, and never says Sept", () => {
    expect(formatDate(new Date(2025, 9, 12, 9).toISOString(), "short", { now })).toBe("12 Oct 2025");
    expect(formatDate(new Date(2025, 8, 3, 9).toISOString(), "short", { now })).toBe("3 Sep 2025");
  });

  it("is empty for a value it cannot read", () => {
    expect(formatDate("not a date", "short", { now })).toBe("");
  });
});

// Round 10, C4: the report's date line carries its year, so a printed copy
// read out of its year still says when.
describe("formatDate, long", () => {
  it("always carries the year", () => {
    expect(formatDate(new Date(2026, 10, 5, 12).toISOString(), "long")).toBe("5 November 2026");
    expect(formatDate(new Date(2025, 10, 3, 15).toISOString(), "long")).toBe("3 November 2025");
  });

  it("can lead with the weekday (History's day headings)", () => {
    expect(formatDate(new Date(2026, 10, 3, 9, 2), "long", { weekday: true })).toBe("Tuesday 3 November 2026");
  });

  it("is empty for a value it cannot read", () => {
    expect(formatDate("not a date", "long")).toBe("");
  });
});

// H4: History's rows show absolute local 24-hour time.
describe("formatDate, time", () => {
  it("shows hours and minutes, zero-padded", () => {
    expect(formatDate(new Date(2026, 10, 3, 9, 2, 0).toISOString(), "time")).toBe("09:02");
    expect(formatDate(new Date(2026, 10, 3, 23, 45, 59).toISOString(), "time")).toBe("23:45");
  });
});
