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

describe("VITE_THEORY_OF_CHANGE", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("offers Theory of change only when the flag is 1", async () => {
    vi.stubEnv("VITE_THEORY_OF_CHANGE", "1");
    vi.resetModules();
    const on = await import("./capabilities");
    expect(on.isSelectableCapability("theory_of_change")).toBe(true);

    vi.stubEnv("VITE_THEORY_OF_CHANGE", "");
    vi.resetModules();
    const off = await import("./capabilities");
    expect(off.isSelectableCapability("theory_of_change")).toBe(false);
    expect(off.capabilityLabel("theory_of_change")).toBe("Theory of change");
  });
});

describe("useCapabilities", () => {
  afterEach(() => {
    vi.doUnmock("posthog-js/react");
    vi.resetModules();
  });

  /** Load the module with PostHog answering each flag from `flags`. */
  async function capabilitiesWith(flags: Record<string, boolean | undefined>) {
    vi.resetModules();
    vi.doMock("posthog-js/react", () => ({
      useFeatureFlagEnabled: (key: string) => flags[key],
    }));
    const [{ renderHook }, { useCapabilities }] = await Promise.all([
      import("@testing-library/react"),
      import("./capabilities"),
    ]);
    const { result } = renderHook(() => useCapabilities());
    return Object.fromEntries(result.current.map((c) => [c.key, c.available]));
  }

  it("lets a PostHog flag turn a capability off and on over the build default", async () => {
    // vite.config.ts sets VITE_OPTIONS_SCOPING=1 for tests and leaves
    // VITE_THEORY_OF_CHANGE unset, so each flag here goes against its default.
    const available = await capabilitiesWith({ options_scoping: false, theory_of_change: true });
    expect(available.options_scoping).toBe(false);
    expect(available.theory_of_change).toBe(true);
  });

  it("keeps the build default when PostHog gives no answer", async () => {
    const available = await capabilitiesWith({});
    expect(available.options_scoping).toBe(true);
    expect(available.theory_of_change).toBe(false);
    expect(available.evidence_search).toBe(true);
    expect(available.map_stakeholders).toBe(false);
  });
});
