import { describe, expect, it } from "vitest";

import {
  ANALYSIS_DEPTH_LABEL,
  COMPONENT_LABEL,
  SEARCH_EFFORT_LABEL,
  SOURCES_LABEL,
  STEERING_MODE_LABEL,
  scopeChips,
  vocabLabel,
} from "./planVocabulary";

describe("vocabLabel", () => {
  it("maps every locked key and omits unknown keys (never leaks raw enums)", () => {
    expect(vocabLabel(SEARCH_EFFORT_LABEL, "rapid")).toBe("Rapid — top sources, fast pass");
    expect(vocabLabel(ANALYSIS_DEPTH_LABEL, "landscape")).toBe("Landscape — mapping the terrain");
    expect(vocabLabel(SOURCES_LABEL, "both")).toBe("Academic + policy (OpenAlex, Overton)");
    expect(vocabLabel(STEERING_MODE_LABEL, "unattended")).toBe("Unattended (no pauses)");
    expect(vocabLabel(COMPONENT_LABEL, "screen_full")).toBe("Screening for relevance");
    // The contract's ban: an unknown key must OMIT, not render key.replace(…).
    expect(vocabLabel(SEARCH_EFFORT_LABEL, "warp_speed")).toBeNull();
    expect(vocabLabel(SEARCH_EFFORT_LABEL, null)).toBeNull();
    expect(vocabLabel(SEARCH_EFFORT_LABEL, undefined)).toBeNull();
  });
});

describe("scopeChips", () => {
  it("collapses geography to the named group when present", () => {
    expect(
      scopeChips({
        published_after: "2015-01-01",
        published_before: null,
        publisher_country: "GB",
        author_affiliation_countries: ["GB", "IE"],
        country_group: { label: "UK & Ireland", countries: ["GB", "IE"], authorship: null },
      }),
    ).toEqual(["Published after 2015", "Geography: UK & Ireland (GB, IE)"]);
  });

  it("falls back to the union of backend-specific country filters", () => {
    expect(
      scopeChips({
        published_after: null,
        published_before: "2024-06-30",
        publisher_country: "GB",
        author_affiliation_countries: ["GB", "SE"],
        country_group: null,
      }),
    ).toEqual(["Published before 2024", "Geography: GB, SE"]);
  });

  it("returns nothing for absent constraints", () => {
    expect(scopeChips(null)).toEqual([]);
    expect(scopeChips(undefined)).toEqual([]);
  });
});
