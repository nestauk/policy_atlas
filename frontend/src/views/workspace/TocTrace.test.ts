import { describe, expect, it } from "vitest";

import type { TaskAgentThreadDecision } from "../../store";
import { tocTrace } from "./TocTrace";

const event = (sequence: number, kind: string, detail: Record<string, unknown>, run = "walk"): TaskAgentThreadDecision =>
  ({ sequence, kind, detail, capability_run_id: run, occurred_at: "2026-10-30T14:00:00Z", summary: "" }) as TaskAgentThreadDecision;

const check = [
  event(1, "search.executed", { query: "If restricted on-demand slots carry no adverts, then children see fewer" }, "child"),
  event(2, "search.executed", { query: "HFSS advertising on-demand" }, "child"),
  event(3, "component.completed", { component: "acquire", results_returned: 40, acquired: 8 }, "child"),
  event(4, "component.started", { component: "toc_select" }),
  event(5, "component.completed", { component: "toc_select", screened: 52, relevant: 10 }),
  event(6, "component.started", { component: "toc_judge" }),
];

describe("tocTrace", () => {
  it("says what each search found and each step's counts, and what runs now", () => {
    const view = tocTrace("walk", check, true);
    expect(view.lines).toEqual([
      "Searched 2 queries, e.g. “HFSS advertising on-demand”: 40 results, 8 new to this task.",
      "Read 52 titles and abstracts: 10 look on topic, 42 set aside.",
    ]);
    expect(view.now).toBe("Judging 10 documents against the steps");
    expect(view.title).toBe("Searching for evidence");
  });

  it("names a finished walk by what it did", () => {
    expect(tocTrace("walk", check, false)).toMatchObject({ title: "Searched for evidence", now: null });
    const draft = [event(1, "component.started", { component: "toc_draft" }), event(2, "component.completed", { component: "toc_draft" })];
    expect(tocTrace("walk", draft, false).title).toBe("Drafted the theory");
    expect(tocTrace("walk", draft.slice(0, 1), true).now).toBe("Drafting the theory");
  });

  it("does not call a check that has no steps yet a draft", () => {
    const started = [event(1, "run.started", {})];
    expect(tocTrace("walk", started, true).title).toBe("Searching for evidence");
    expect(tocTrace("walk", started, true, "check").now).toBe("Starting the evidence check");
  });
});

describe("a failed walk", () => {
  it("says it failed, not that it drafted or searched", () => {
    expect(tocTrace("w1", [], false, "draft", "failed").title).toBe("The draft failed");
    expect(tocTrace("w1", [], false, "check", "interrupted").title).toBe("The evidence check failed");
    expect(tocTrace("w1", [], false, "draft", "succeeded").title).toBe("Drafted the theory");
  });
});
