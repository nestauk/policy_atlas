import { describe, expect, it } from "vitest";

import type { components } from "../api/gen/types";
import { isBaselineArtefact } from "./baselineBand";

type ArtefactOut = components["schemas"]["ArtefactOut"];

/** A partial `ArtefactOut` — only the fields each test cares about. */
function artefact(overrides: Partial<ArtefactOut>): ArtefactOut {
  return overrides as ArtefactOut;
}

describe("isBaselineArtefact", () => {
  it("reads the roll-up's template word, not the sections", () => {
    expect(isBaselineArtefact(artefact({ template: "baseline" }))).toBe(true);
    expect(isBaselineArtefact(artefact({ template: null }))).toBe(false);
    expect(isBaselineArtefact(artefact({}))).toBe(false);
    expect(isBaselineArtefact(null)).toBe(false);
    expect(isBaselineArtefact(undefined)).toBe(false);
  });
});
