import { describe, expect, it } from "vitest";

import {
  leverDefinitionFor,
  runnerUpLine,
  triedOnSentence,
  variantLine,
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
        { population: "adolescents", documents: 2 },
        { population: "preschool children", documents: 1 },
      ]),
    ).toBe("Tried on: adolescents (2 documents), preschool children (1).");
  });

  it("names a folded suggestion's origin and drops a zero count", () => {
    expect(variantLine({ name: "HENRY", documents: 1, folded_seed: false })).toBe("HENRY · 1 document");
    expect(variantLine({ name: "Breakfast clubs", documents: 0, folded_seed: true })).toBe(
      "Breakfast clubs · suggested by Policy Atlas",
    );
  });

  it("words the runner-up like the lever line", () => {
    expect(runnerUpLine("regulate")).toBe("Runner-up lever type: Regulate.");
  });
});
