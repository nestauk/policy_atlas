import { afterEach, describe, expect, it, vi } from "vitest";

import { capabilityLabel } from "./capabilities";

describe("capabilityLabel", () => {
  it("defaults to Evidence search when the API sends no key yet", () => {
    expect(capabilityLabel()).toBe("Evidence search");
    expect(capabilityLabel(null)).toBe("Evidence search");
  });

  it("maps known keys to their list labels", () => {
    expect(capabilityLabel("evidence_search")).toBe("Evidence search");
    expect(capabilityLabel("map_stakeholders")).toBe("Mapping stakeholders");
  });
});

describe("VITE_OPTIONS_SCOPING", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("offers Options scoping only when the flag is 1", async () => {
    vi.stubEnv("VITE_OPTIONS_SCOPING", "1");
    vi.resetModules();
    const on = await import("./capabilities");
    expect(on.isSelectableCapability("options_scoping")).toBe(true);

    vi.stubEnv("VITE_OPTIONS_SCOPING", "");
    vi.resetModules();
    const off = await import("./capabilities");
    expect(off.isSelectableCapability("options_scoping")).toBe(false);
    expect(off.isSelectableCapability("evidence_search")).toBe(true);
    expect(off.capabilityLabel("options_scoping")).toBe("Options scoping");
  });
});
