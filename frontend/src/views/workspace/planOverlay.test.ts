import { describe, expect, it } from "vitest";

import type { components } from "../../api/gen/types";

import {
  displayedGeography,
  displayedYearAfter,
  overlayIsDirty,
  overlayToPlanPatch,
} from "./planOverlay";

type PlanDraft = components["schemas"]["PlanDraft"];

function plan(overrides: Partial<PlanDraft> = {}): PlanDraft {
  return {
    analysis_depth: "standard",
    assumptions: null,
    backend_scope: "both",
    component_rationale: null,
    components: null,
    expected_artefact_shape: null,
    extract_profiles: null,
    grouping_facets: null,
    question: "What works?",
    ready: true,
    scope_constraints: {
      author_affiliation_countries: null,
      country_group: null,
      published_after: "2016-01-01",
      published_before: null,
      publisher_country: null,
    },
    scoping_notes: null,
    screening_criteria: ["Peer-reviewed"],
    search_effort: "standard",
    section_budget: null,
    steering_mode: "moderate",
    steps: [],
    time_band: "~10-20 min",
    title: null,
    ...overrides,
  };
}

describe("planOverlay", () => {
  it("treats an empty overlay as clean", () => {
    expect(overlayIsDirty({})).toBe(false);
    expect(overlayIsDirty({ question: "New Q" })).toBe(true);
  });

  it("reads the year bound from the server until locally overridden", () => {
    expect(displayedYearAfter(plan(), {})).toBe("2016");
    expect(displayedYearAfter(plan(), { published_after_year: "2020" })).toBe("2020");
    expect(displayedYearAfter(plan(), { published_after_year: "" })).toBe("");
  });

  it("reads geography from constraints", () => {
    expect(
      displayedGeography(
        plan({
          scope_constraints: {
            author_affiliation_countries: ["GB"],
            country_group: null,
            published_after: null,
            published_before: null,
            publisher_country: "GB",
          },
        }),
        {},
      ),
    ).toBe("GB");
  });

  it("compiles local edits into a typed patch", () => {
    expect(overlayToPlanPatch({ question: "New question", published_after_year: "2018" })).toEqual({
      question: "New question",
      published_after: "2018-01-01",
    });
    expect(overlayToPlanPatch({ backend_scope: "academic_only" })).toEqual({
      backend_scope: "academic_only",
    });
    expect(overlayToPlanPatch({ published_after_year: "", geography: "" })).toEqual({
      published_after: "",
      geography: "",
    });
  });
});
