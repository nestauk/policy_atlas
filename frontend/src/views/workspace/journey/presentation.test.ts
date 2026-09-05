import { describe, expect, it } from "vitest";

import type { StageEntry } from "../../../store/types";
import { timelineSummary } from "./presentation";

describe("journey presentation rules", () => {
  it("maps only approved timeline summary keys", () => {
    const stage: StageEntry = {
      stage: "acquire",
      label: "Searching",
      status: "completed",
      summary: { found: 12, quality_checked: 4, internal_counter: 99, reason: "not a count" },
    };
    expect(timelineSummary(stage)).toEqual(["12 found", "4 quality-checked"]);
  });
});
