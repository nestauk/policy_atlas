import { describe, expect, it } from "vitest";

import { displayUrl, referenceAuthorName, referenceAuthorsShort, referenceCitation, withFullStop } from "./reference";

describe("reference form (task 058, round 10, C5)", () => {
  it("names a person by surname and initials, and keeps an organisation as written", () => {
    expect(referenceAuthorName("Alex Sampleton")).toBe("Sampleton A");
    expect(referenceAuthorName("Alex J. Sampleton")).toBe("Sampleton AJ");
    expect(referenceAuthorName("Sampleton, Alex")).toBe("Sampleton A");
    expect(referenceAuthorName("Jan van der Berg")).toBe("van der Berg J");
    expect(referenceAuthorName("Jean-Paul Mockford")).toBe("Mockford JP");
    expect(referenceAuthorName("Example Policy Institute")).toBe("Example Policy Institute");
    expect(referenceAuthorName("Department for Education")).toBe("Department for Education");
    expect(referenceAuthorName("OECD")).toBe("OECD");
  });

  it("lists up to three authors, then et al., and nothing when there are none", () => {
    const names = (...list: string[]) => list.map((name) => ({ name }));
    expect(referenceAuthorsShort(names("Alex Sampleton", "Casey Mockford"))).toBe("Sampleton A, Mockford C");
    expect(referenceAuthorsShort(names("A One", "B Two", "C Three", "D Four"))).toBe("One A, Two B, Three C et al.");
    expect(referenceAuthorsShort([])).toBeNull();
  });

  it("shows an address without its scheme and ends a phrase with one full stop", () => {
    expect(displayUrl("https://doi.org/10.1000/x")).toBe("doi.org/10.1000/x");
    expect(displayUrl("http://example.org/report/")).toBe("example.org/report");
    expect(withFullStop("BMJ Open")).toBe("BMJ Open.");
    expect(withFullStop("Does it work?")).toBe("Does it work?");
  });
});

describe("referenceCitation (round 10, C5)", () => {
  it("starts at the title with no authors, carrying the year after it, and adds no second stop", () => {
    expect(referenceCitation({ title: "Uploaded note", year: 2023, venue: null })).toBe("Uploaded note (2023).");
    expect(referenceCitation({ title: "Does it work?", year: null, venue: "Health & Place" })).toBe(
      "Does it work? Health & Place.",
    );
    expect(
      referenceCitation({ title: "A study", year: null, authorships: [{ name: "Alex One" }], url: "ftp://x" }),
    ).toBe("One A. A study.");
  });
});
