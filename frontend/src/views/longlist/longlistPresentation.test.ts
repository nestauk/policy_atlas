import { describe, expect, it } from "vitest";

import {
  AUTHORITY_LABELS,
  GRID_COLUMN_LINES,
  LEVEL_WORDS,
  LINE_NAMES,
  PROFILE_LINE_KEYS,
  authorityWords,
  servesOutcome,
  deliveredThroughLine,
  leverDefinitionFor,
  leverLabel,
  leverLine,
  triedOnFacet,
  triedOnSentence,
  exampleLine,
} from "./longlistPresentation";

// Task 046: the card's new lines and the lever definition by version.
describe("longlist presentation (task 046)", () => {
  const byVersion = {
    lever_types_v2: [{ key: "subsidise", definition: "pay for it, or fund a provider" }],
    lever_types_v1: [{ key: "subsidise", definition: "pay for it" }],
  };

  it("shows the definition of the version a group's options were typed under", () => {
    const typedV1 = [{ taxonomy_version: "lever_types_v1" }, { taxonomy_version: "lever_types_v1" }];
    expect(leverDefinitionFor("subsidise", typedV1, byVersion, "Current.")).toBe("Pay for it.");
  });

  it("falls back to the current definition for a mixed or unknown version", () => {
    const mixed = [{ taxonomy_version: "lever_types_v1" }, { taxonomy_version: "lever_types_v2" }];
    expect(leverDefinitionFor("subsidise", mixed, byVersion, "Current.")).toBe("Current.");
    expect(leverDefinitionFor("subsidise", [{ taxonomy_version: null }], byVersion, "Current.")).toBe("Current.");
    expect(leverDefinitionFor("subsidise", [], undefined, "Current.")).toBe("Current.");
  });

  it("says the unit of the tried-on counts once", () => {
    expect(
      triedOnSentence([
        { kind: "adolescents", documents: 2 },
        { kind: "preschool children", documents: 1 },
      ]),
    ).toBe("Tried on: adolescents (2 documents), preschool children (1).");
  });

  it("words an example with its documents and drops a zero count", () => {
    expect(exampleLine({ name: "HENRY", documents: 1 })).toBe("HENRY (1 document)");
    expect(exampleLine({ name: "Breakfast clubs", documents: 0 })).toBe("Breakfast clubs");
  });

  // Task 046, amendment 3 (§ 2.5): the lever line, the secondary types after "with".
  it("words the lever line with its secondary types joined by and", () => {
    expect(leverLine("subsidise", ["inform", "provide a service"])).toBe("Lever: Subsidise, with Inform and Provide a service.");
    expect(leverLine("subsidise", ["inform"])).toBe("Lever: Subsidise, with Inform.");
    expect(leverLine("subsidise", [])).toBe("Lever: Subsidise.");
    expect(leverLine("subsidise", undefined)).toBe("Lever: Subsidise.");
    expect(leverLine(null, [])).toBe("Lever: none fits.");
  });

  it("limits the Tried on facet and counts what it hides", () => {
    const options = [
      { tried_on: [{ kind: "adolescents" }, { kind: "families" }] },
      { tried_on: [{ kind: "adolescents" }, { kind: "parents" }] },
      { tried_on: null },
    ];
    expect(triedOnFacet(options, 2)).toEqual({
      shown: [
        ["adolescents", 2],
        ["families", 1],
      ],
      hidden: 1,
    });
  });
});

// Task 046, amendment 2 (R40, R41, R42, R43, R44): the words of the profile.
describe("longlist presentation (amendment 2 words)", () => {
  it("names the eight lines and ambition exactly", () => {
    expect(PROFILE_LINE_KEYS.map((key) => LINE_NAMES[key])).toEqual([
      "Cost",
      "Time to set up",
      "Time to effect",
      "Workforce requirements",
      "Who decides",
      "Dependencies",
      "Coordination requirements",
      "Delivery complexity",
    ]);
    expect(LINE_NAMES.ambition).toBe("Ambition");
  });

  it("gives each line exactly the table's level words", () => {
    const words = (key: keyof typeof LEVEL_WORDS) => [LEVEL_WORDS[key].less, LEVEL_WORDS[key].more];
    expect(words("cost")).toEqual(["Cheaper", "Costlier"]);
    expect(words("time_to_set_up")).toEqual(["Quicker", "Slower"]);
    expect(words("time_to_effect")).toEqual(["Quicker", "Slower"]);
    expect(words("workforce")).toEqual(["Lower", "Higher"]);
    expect(words("who_decides")).toEqual([null, null]);
    expect(words("dependencies")).toEqual([null, null]);
    expect(words("coordination")).toEqual(["Lower", "Higher"]);
    expect(words("delivery_complexity")).toEqual(["Simpler", "More complex"]);
    expect(words("ambition")).toEqual(["Smaller", "Bigger"]);
    const all = Object.values(LEVEL_WORDS).flatMap((pair) => [pair.less, pair.more]);
    expect(all.filter((word) => word !== null)).toHaveLength(14);
    expect(all).not.toContain("Middle");
  });

  it("offers the seven lines that carry a mark as grid columns, ambition first", () => {
    expect(GRID_COLUMN_LINES.map((key) => LINE_NAMES[key])).toEqual([
      "Ambition",
      "Cost",
      "Time to set up",
      "Time to effect",
      "Workforce requirements",
      "Coordination requirements",
      "Delivery complexity",
    ]);
  });

  it("words the authority labels, naming the body when there is one", () => {
    expect(AUTHORITY_LABELS).toEqual({
      within_your_power: "Within your power",
      needs_action_by: "Needs action by another body",
      unclear: "Unclear who can act",
    });
    expect(authorityWords({ label: "needs_action_by", body: "the Treasury", reason: "It sets the rate." })).toBe(
      "Needs action by the Treasury",
    );
    expect(authorityWords({ label: "needs_action_by", body: null, reason: null })).toBe("Needs action by another body");
    expect(authorityWords({ label: "unclear", reason: "Not stated." })).toBe("Unclear who can act");
  });

  it("matches a served outcome with case and spacing folded", () => {
    expect(servesOutcome(["NEET rate at 6 months"], " neet rate at 6 months ")).toBe(true);
    expect(servesOutcome(["Attendance"], "Wellbeing")).toBe(false);
    expect(servesOutcome(undefined, "Wellbeing")).toBe(false);
  });

  it("words the delivery setting", () => {
    expect(deliveredThroughLine(["Jobcentre", "School"])).toBe("Delivered through: Jobcentre · School");
    expect(deliveredThroughLine([])).toBe("");
  });

  it("labels a row with its lever only", () => {
    expect(leverLabel({ primary_lever_type: "provide a service", ambition: "more" } as never)).toBe("Provide a service");
    expect(leverLabel({ primary_lever_type: null, ambition: "less" } as never)).toBe("No lever fits");
  });
});
