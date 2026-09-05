import { describe, expect, it } from "vitest";

import { friendlyDecisionDetails, groupSearchDecisions } from "./decisionsPresentation";
import { cancelledRenameState } from "./landingPresentation";
import { abstractSourceLabel, screeningDetails, sourceStatusLabel } from "./sourcesPresentation";

describe("source presentation", () => {
  it("omits unknown status labels", () => {
    expect(sourceStatusLabel({ status: "unknown" as "found", screen_status: null })).toBeUndefined();
  });

  it("marks an LLM description as AI description", () => {
    expect(abstractSourceLabel("llm_description")).toBe("AI description");
    expect(abstractSourceLabel("provider")).toBeUndefined();
  });

  it("suppresses the confidence chip for retracted exclusions", () => {
    expect(screeningDetails({ screen_status: "excluded_retracted", screen_confidence: 1, screen_basis: null, screen_stage: null, status_reason: null })).not.toContainEqual(["Screening confidence", "100%"]);
  });
});

describe("decision presentation", () => {
  it("allows only friendly-labelled decision detail", () => {
    expect(friendlyDecisionDetails({ acquired: 8, internal_trace: "do not render", nested: { token: "do not render" } })).toEqual([
      { label: "New sources found", value: 8 },
    ]);
  });

  it("groups search entries into one search terms row", () => {
    const entries = [
      { sequence: 3, occurred_at: "2026-07-28T10:00:00Z", kind: "search.executed", summary: "Executed a search query.", detail: null },
      { sequence: 2, occurred_at: "2026-07-28T09:59:00Z", kind: "search.executed", summary: "Executed a search query.", detail: null },
    ];
    expect(groupSearchDecisions(entries)).toMatchObject([{ summary: "Search terms used (2 queries)", searchCount: 2 }]);
  });
});

describe("task rename", () => {
  it("cancel restores the original task name", () => {
    expect(cancelledRenameState("Original task")).toEqual({ editing: false, draftName: "Original task" });
  });
});
