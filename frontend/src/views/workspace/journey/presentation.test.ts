import { describe, expect, it } from "vitest";

import type { StageEntry } from "../../../store/types";
import { completionCopy, funnelBarWidth, screenedOutFooter, timelineSummary } from "./presentation";

describe("journey presentation rules", () => {
  it("uses bounded bar widths and keeps the screened-out footer data separate", () => {
    expect(funnelBarWidth(25, 100)).toBe(25);
    expect(funnelBarWidth(140, 100)).toBe(100);
    expect(funnelBarWidth(4, 0)).toBe(0);
    expect(screenedOutFooter(7)).toBe("7 screened out — kept in the sources table with reasons.");
  });

  it("maps only approved timeline summary keys", () => {
    const stage: StageEntry = {
      stage: "acquire",
      label: "Searching",
      status: "completed",
      summary: { found: 12, quality_checked: 4, internal_counter: 99, reason: "not a count" },
    };
    expect(timelineSummary(stage)).toEqual(["12 found", "4 quality-checked"]);
  });

  it("selects outcome-first completion copy", () => {
    expect(completionCopy("succeeded")?.heading).toBe("The evidence base is ready");
    expect(completionCopy("degraded")?.heading).toBe("The evidence base is ready with gaps");
    expect(completionCopy("failed")).toBeNull();
  });
});
