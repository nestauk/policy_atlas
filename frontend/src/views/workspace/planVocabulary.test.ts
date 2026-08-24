import { describe, expect, it } from "vitest";

import {
  ANALYSIS_DEPTH_LABEL,
  ANALYSIS_QUESTION,
  ANALYSIS_SHORTLIST_CAP,
  ANALYSIS_TITLE,
  acquireSearchBlurb,
  axesForResearchApproach,
  COMPONENT_LABEL,
  RESEARCH_APPROACH_CUSTOM,
  researchApproachId,
  researchApproachLabel,
  SEARCH_EFFORT_LABEL,
  SEARCH_SCOPE_HINT,
  SEARCH_SCOPE_RECORD_CAP,
  SOURCES_LABEL,
  STEERING_MODE_LABEL,
  scopeChips,
  stepsForAnalysisDepth,
  timeBandFor,
  vocabLabel,
} from "./planVocabulary";

describe("vocabLabel", () => {
  it("maps every locked key and omits unknown keys (never leaks raw enums)", () => {
    expect(vocabLabel(SEARCH_EFFORT_LABEL, "rapid")).toBe("Focused");
    expect(vocabLabel(SEARCH_EFFORT_LABEL, "standard")).toBe("Broad");
    expect(vocabLabel(SEARCH_EFFORT_LABEL, "deep")).toBe("Broadest");
    expect(ANALYSIS_TITLE).toBe("Analysis level");
    expect(vocabLabel(ANALYSIS_DEPTH_LABEL, "landscape")).toBe("Evidence overview");
    expect(vocabLabel(ANALYSIS_DEPTH_LABEL, "standard")).toBe("Full-text synthesis");
    expect(vocabLabel(ANALYSIS_DEPTH_LABEL, "deep")).toBe("Findings synthesis");
    expect(vocabLabel(SOURCES_LABEL, "both")).toBe("Academic + Policy (OpenAlex, Overton)");
    expect(vocabLabel(STEERING_MODE_LABEL, "unattended")).toBe("None");
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

describe("plan-panel hints", () => {
  it("states the acquire caps on Search scope and the shortlist sizes on Analysis level", () => {
    expect(SEARCH_SCOPE_HINT).toContain(`Focused: up to ${SEARCH_SCOPE_RECORD_CAP.rapid} relevant results per database`);
    expect(SEARCH_SCOPE_HINT).toContain(`Broad: up to ${SEARCH_SCOPE_RECORD_CAP.standard} relevant results per database`);
    expect(SEARCH_SCOPE_HINT).toContain(`Broadest: up to ${SEARCH_SCOPE_RECORD_CAP.deep} relevant results per database`);
    expect(ANALYSIS_QUESTION).toContain("Overview: Themes, coverage and gaps across the screened evidence");
    expect(ANALYSIS_QUESTION).toContain(
      `Full-text synthesis: Synthesise about ${ANALYSIS_SHORTLIST_CAP.standard} shortlisted sources`,
    );
    expect(ANALYSIS_QUESTION).toContain(
      `Findings synthesis: Extract and synthesise findings from about ${ANALYSIS_SHORTLIST_CAP.deep} shortlisted sources`,
    );
  });
});

describe("researchApproach", () => {
  it("names the three diagonal presets and Custom off the diagonal", () => {
    expect(researchApproachId("rapid", "landscape")).toBe("rapid_overview");
    expect(researchApproachLabel("standard", "standard")).toBe("Standard report");
    expect(researchApproachLabel("deep", "deep")).toBe("Detailed report");
    expect(researchApproachId("rapid", "deep")).toBe("custom");
    expect(researchApproachLabel("rapid", "deep")).toBe(RESEARCH_APPROACH_CUSTOM);
    expect(researchApproachId("", "standard")).toBeNull();
    expect(researchApproachLabel("", "")).toBeNull();
  });

  it("compiles a preset back to both axes", () => {
    expect(axesForResearchApproach("rapid_overview")).toEqual({
      search_effort: "rapid",
      analysis_depth: "landscape",
    });
    expect(axesForResearchApproach("custom")).toBeNull();
  });
});

describe("timeBandFor", () => {
  it("returns the measured band for a search-effort × analysis-depth pair", () => {
    expect(timeBandFor("standard", "standard")).toBe("~10-20 min");
    expect(timeBandFor("rapid", "deep")).toBe("~75-90 min");
    expect(timeBandFor("unknown", "standard")).toBeNull();
  });
});

describe("stepsForAnalysisDepth", () => {
  it("adds shortlisting at standard and the findings chain at deep", () => {
    const landscape = stepsForAnalysisDepth("landscape").map((step) => step.stage);
    const standard = stepsForAnalysisDepth("standard").map((step) => step.stage);
    const deep = stepsForAnalysisDepth("deep").map((step) => step.stage);
    expect(landscape).toEqual(["acquire", "screen", "classify", "appraise", "characterise", "synthesise"]);
    expect(standard).toContain("select");
    expect(standard).not.toContain("extract");
    expect(deep).toEqual([
      "acquire",
      "screen",
      "classify",
      "appraise",
      "characterise",
      "select",
      "extract",
      "group",
      "synthesise",
    ]);
  });

  it("adapts the searching blurb to the selected source libraries", () => {
    expect(acquireSearchBlurb("academic_only")).toBe("Querying academic databases.");
    expect(acquireSearchBlurb("grey_lit_only")).toBe("Querying policy databases.");
    expect(acquireSearchBlurb("both")).toBe("Querying academic and policy databases.");
    expect(stepsForAnalysisDepth("landscape", "academic_only")[0]).toMatchObject({
      stage: "acquire",
      label: "Searching",
      blurb: "Querying academic databases.",
    });
  });
});
