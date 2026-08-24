import { describe, expect, it } from "vitest";

import { capabilityLabel } from "./capabilities";

describe("capabilityLabel", () => {
  it("defaults to Evidence search when the API sends no key yet", () => {
    expect(capabilityLabel()).toBe("Evidence search");
    expect(capabilityLabel(null)).toBe("Evidence search");
  });

  it("maps known keys to their list labels", () => {
    expect(capabilityLabel("evidence_base")).toBe("Evidence search");
    expect(capabilityLabel("map_stakeholders")).toBe("Mapping stakeholders");
  });
});
