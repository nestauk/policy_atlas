import { describe, expect, it } from "vitest";

import type { components } from "../../api/gen/types";

import {
  displayedGeography,
  displayedYearAfter,
  mergeOverlayChanges,
  overlayIsDirty,
  overlayToPlanPatch,
  screeningOverlayError,
  SCREENING_CRITERIA_LIST_MAX,
  SCREENING_CRITERION_MAX,
  SCREEN_INTENT_MAX,
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
      publisher_source: null,
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
            publisher_source: null,
          },
        }),
        {},
      ),
    ).toBe("GB");
  });

  it("reads APO from publisher_source with an empty overlay", () => {
    expect(
      displayedGeography(
        plan({
          scope_constraints: {
            author_affiliation_countries: null,
            country_group: null,
            published_after: null,
            published_before: null,
            publisher_country: null,
            publisher_source: "apo",
          },
        }),
        {},
      ),
    ).toBe("APO");
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

describe("mergeOverlayChanges", () => {
  function apoPlan(): PlanDraft {
    return plan({
      backend_scope: "grey_lit_only",
      scope_constraints: {
        author_affiliation_countries: null,
        country_group: null,
        published_after: null,
        published_before: null,
        publisher_country: null,
        publisher_source: "apo",
      },
    });
  }

  it("cannot blank APO geography when only Sources is saved (bug 2/3)", () => {
    // A Search-filters save that only touches `backend_scope` still carries
    // the unedited geography box value through `changes` (the section spreads
    // its whole draft) — it must be dropped rather than overwrite the
    // overlay with an empty `geography`, or a later Start would PATCH a
    // blank geography over the server's APO constraint.
    const result = mergeOverlayChanges({}, apoPlan(), {
      backend_scope: "grey_lit_only",
      geography: "APO",
    });
    expect(result).toEqual({});
  });

  it("deletes an overlay key once its edit matches the server value again", () => {
    const result = mergeOverlayChanges({ question: "Old edit" }, plan({ question: "What works?" }), {
      question: "What works?",
    });
    expect(result).toEqual({});
  });

  it("keeps a key that genuinely differs from the server value", () => {
    const result = mergeOverlayChanges({}, plan({ question: "What works?" }), {
      question: "Something new",
    });
    expect(result).toEqual({ question: "Something new" });
  });

  it("passes through overlay keys absent from changes", () => {
    const result = mergeOverlayChanges({ geography: "UK" }, plan(), { question: "New Q" });
    expect(result).toEqual({ geography: "UK", question: "New Q" });
  });

  it("treats an unchanged screening list as clean (array equality, not reference)", () => {
    const result = mergeOverlayChanges(
      {},
      plan({ screening_criteria: ["Peer-reviewed"] }),
      { screening_criteria: ["Peer-reviewed"] },
    );
    expect(result).toEqual({});
  });
});

describe("overlayToPlanPatch prunes no-ops against a live plan", () => {
  it("omits a field that already matches the plan's displayed value", () => {
    const patch = overlayToPlanPatch(
      { question: "What works?", backend_scope: "academic_only" },
      plan({ question: "What works?", backend_scope: "both" }),
    );
    expect(patch).toEqual({ backend_scope: "academic_only" });
  });

  it("emits every set key when no plan is given (prior behaviour)", () => {
    const patch = overlayToPlanPatch({ question: "What works?" });
    expect(patch).toEqual({ question: "What works?" });
  });

  it("re-sends the displayed geography whenever the patch changes backend_scope", () => {
    const patch = overlayToPlanPatch(
      { backend_scope: "grey_lit_only" },
      plan({
        backend_scope: "academic_only",
        scope_constraints: {
          author_affiliation_countries: ["GB"],
          country_group: null,
          published_after: null,
          published_before: null,
          publisher_country: null,
          publisher_source: null,
        },
      }),
    );
    // Without the geography field the backend would null the incompatible
    // constraint instead of recompiling "GB" under the new scope.
    expect(patch).toEqual({ backend_scope: "grey_lit_only", geography: "GB" });
  });

  it("adds no geography to a scope change when the plan has none", () => {
    const patch = overlayToPlanPatch({ backend_scope: "academic_only" }, plan());
    expect(patch).toEqual({ backend_scope: "academic_only" });
  });
});

describe("screeningOverlayError", () => {
  it("allows criteria and a question within both caps", () => {
    expect(screeningOverlayError(["Peer-reviewed only"], "What works?")).toBeNull();
  });

  it("rejects a single criterion over SCREENING_CRITERION_MAX", () => {
    const error = screeningOverlayError(["x".repeat(SCREENING_CRITERION_MAX + 1)], "What works?");
    expect(error).toMatch(String(SCREENING_CRITERION_MAX));
  });

  it("accepts a criterion exactly at SCREENING_CRITERION_MAX", () => {
    expect(screeningOverlayError(["x".repeat(SCREENING_CRITERION_MAX)], "What works?")).toBeNull();
  });

  it("rejects when the composed question+criteria exceeds SCREEN_INTENT_MAX", () => {
    const question = "q".repeat(1_990);
    const error = screeningOverlayError(["Exclude opinion pieces."], question);
    expect(error).toMatch(String(SCREEN_INTENT_MAX));
  });

  it("counts code points the way the backend's len() does, not UTF-16 units", () => {
    // 600 pill emoji: 1200 UTF-16 units, 600 backend characters — valid.
    expect(screeningOverlayError(["💊".repeat(600)], "What works?")).toBeNull();
    expect(screeningOverlayError(["💊".repeat(SCREENING_CRITERION_MAX + 1)], "What works?")).toMatch(
      String(SCREENING_CRITERION_MAX),
    );
  });

  it("mirrors the backend's 50-rule list cap", () => {
    const fifty = Array.from({ length: SCREENING_CRITERIA_LIST_MAX }, (_, i) => `Rule ${i}`);
    expect(screeningOverlayError(fifty, "What works?")).toBeNull();
    expect(screeningOverlayError([...fifty, "one too many"], "What works?")).toMatch(
      String(SCREENING_CRITERIA_LIST_MAX),
    );
  });
});
