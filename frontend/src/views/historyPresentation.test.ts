import { describe, expect, it } from "vitest";

import { dayHeading, groupByDay, mergeHistory, type HistoryEntry, type HistoryRun } from "./historyPresentation";

const entry = (item: unknown) => item as HistoryEntry;
const run = (item: unknown) => item as HistoryRun;

describe("mergeHistory", () => {
  it("merges task_agent turns and decisions into one list ordered by time, question and plan first", () => {
    const turns = [
      { turn_index: 0, created_at: "2026-07-28T09:00:00Z", user_message: "What is the policy landscape?", status: "completed" as const },
      { turn_index: 1, created_at: "2026-07-28T09:05:00Z", user_message: "Focus on the UK only.", status: "completed" as const },
    ];
    const decisions = [
      { sequence: 1, occurred_at: "2026-07-28T09:10:00Z", kind: "plan.approved", summary: "Plan approved." },
      { sequence: 2, occurred_at: "2026-07-28T09:20:00Z", kind: "task.renamed", summary: "Renamed the task." },
    ];
    expect(mergeHistory(decisions, turns).map((r) => r.id)).toEqual([
      "turn-0",
      "turn-1",
      "decision-plan.approved-1",
      "decision-task.renamed-2",
    ]);
  });

  it("breaks ties on identical timestamps by turn index / decision sequence", () => {
    const turns = [
      { turn_index: 1, created_at: "2026-07-28T09:00:00Z", user_message: "second", status: "completed" as const },
      { turn_index: 0, created_at: "2026-07-28T09:00:00Z", user_message: "first", status: "completed" as const },
    ];
    const decisions = [
      { sequence: 2, occurred_at: "2026-07-28T10:00:00Z", kind: "plan.approved", summary: "later" },
      { sequence: 1, occurred_at: "2026-07-28T10:00:00Z", kind: "task.renamed", summary: "earlier" },
    ];
    expect(mergeHistory(decisions, turns).map((r) => r.id)).toEqual([
      "turn-0",
      "turn-1",
      "decision-task.renamed-1",
      "decision-plan.approved-2",
    ]);
  });

  it("says the opening turn was asked and later free text was written, with typographic quotes", () => {
    const turns = [
      { turn_index: 0, created_at: "2026-07-28T09:00:00Z", user_message: "What works?", status: "completed" as const },
      { turn_index: 1, created_at: "2026-07-28T09:05:00Z", user_message: "Focus on the UK.", status: "completed" as const },
    ];
    expect(mergeHistory([], turns).map((r) => r.sentence)).toEqual([
      "You asked: “What works?”",
      "You wrote: “Focus on the UK.”",
    ]);
  });

  it("reads a part card's machine marker as the choice, never printing the marker (H3)", () => {
    const turns = [
      {
        turn_index: 1,
        created_at: "2026-07-28T09:05:00Z",
        user_message: "That's my question\n\n[confirm part=question option=confirm]",
        status: "completed" as const,
      },
    ];
    const [row] = mergeHistory([], turns);
    expect(row.sentence).toBe("You chose “That's my question”.");
    expect(JSON.stringify(row)).not.toContain("[confirm");
  });

  it("reads a scope edit as its changes, one line each", () => {
    const turns = [
      {
        turn_index: 2,
        created_at: "2026-07-28T09:05:00Z",
        user_message:
          'Update the scope:\n- Remove "Search: Published 2016 or later".\n- Add: Include outreach by health visitors.\n\n[confirm part=scope option=looks_right]',
        status: "completed" as const,
      },
    ];
    const row = entry(mergeHistory([], turns)[0]);
    expect(row.sentence).toBe("You changed the scope:");
    expect(row.lines).toEqual(['Remove "Search: Published 2016 or later".', "Add: Include outreach by health visitors."]);
  });

  it("names the owner in a colleague's turns and says You only for the owner (H6)", () => {
    const turns = [{ turn_index: 0, created_at: "2026-07-28T09:00:00Z", user_message: "Q?", status: "completed" as const }];
    expect(mergeHistory([], turns, { isOwner: false, ownerName: "Ada Lovelace" })[0].sentence).toBe("Ada Lovelace asked: “Q?”");
    expect(mergeHistory([], turns, { isOwner: true, ownerName: "Ada Lovelace" })[0].sentence).toBe("You asked: “Q?”");
    expect(mergeHistory([], turns, { isOwner: false, ownerName: null })[0].sentence).toBe("Someone asked: “Q?”");
  });

  it("shows the server's sentence as given: it already names who acted for this reader", () => {
    const decisions = [
      {
        sequence: 1,
        occurred_at: "2026-07-28T09:10:00Z",
        kind: "task.shared_publicly",
        summary: "Ada Lovelace made the task public.",
        decided_by: "user",
        detail: { actor: "owner-1" },
      },
    ];
    expect(mergeHistory(decisions, [], { isOwner: false, ownerName: "Ada Lovelace" })[0].sentence).toBe(
      "Ada Lovelace made the task public.",
    );
  });

  it("marks a failed turn and says it didn't send (H5, P7)", () => {
    const turns = [{ turn_index: 1, created_at: "2026-07-28T09:05:00Z", user_message: "Refine", status: "failed" as const }];
    const [row] = mergeHistory([], turns);
    expect(row.failed).toBe(true);
    expect(row.sentence).toBe("You wrote: “Refine”. This didn't send.");
  });

  it("gives a turn with a reply a details entry, and one without none", () => {
    const turns = [
      { turn_index: 0, created_at: "2026-07-28T09:00:00Z", user_message: "Start", reply: "Here is the plan.", status: "completed" as const },
      { turn_index: 1, created_at: "2026-07-28T09:05:00Z", user_message: "Refine", status: "completed" as const },
    ];
    const result = mergeHistory([], turns).map(entry);
    expect(result[0].details).toEqual([{ label: "The Task Agent replied", value: "Here is the plan." }]);
    expect(result[1].details).toBeUndefined();
  });

  it("never lets a raw event kind reach the output", () => {
    const decisions = [
      { sequence: 1, occurred_at: "2026-07-28T09:00:00Z", kind: "component.weird_internal_name", summary: "Something happened." },
    ];
    const [row] = mergeHistory(decisions, []);
    for (const [key, value] of Object.entries(row)) {
      if (key === "id") continue;
      expect(String(JSON.stringify(value))).not.toContain("component.weird_internal_name");
    }
  });

  it("returns an empty array for empty inputs", () => {
    expect(mergeHistory([], [])).toEqual([]);
    expect(mergeHistory(undefined, undefined)).toEqual([]);
  });

  it("keeps the server's sentence for the user's longlist changes (task 045)", () => {
    const rows = mergeHistory(
      ["option.added", "option.excluded"].map((kind, index) => ({
        sequence: index + 1,
        occurred_at: `2026-09-22T10:0${index}:00Z`,
        kind,
        summary: `Changed option ${index + 1}.`,
      })),
      [],
    );
    expect(rows.map((row) => row.sentence)).toEqual(["Changed option 1.", "Changed option 2."]);
  });

  describe("runs (H7)", () => {
    const RUN = "run-1";
    const step = (sequence: number, at: string, kind: string, summary: string, detail: Record<string, unknown> = {}) => ({
      sequence,
      occurred_at: at,
      kind,
      summary,
      detail,
      capability_run_id: RUN,
    });

    it("folds a run's events into one line with its outcome and time; the check-in stays a row", () => {
      const decisions = [
        step(1, "2026-11-03T09:12:00Z", "run.opened", "Opened an evidence-search run."),
        step(2, "2026-11-03T09:19:00Z", "component.completed", "Completed screening: 118 of 312 relevant.", { relevant: 118 }),
        { ...step(3, "2026-11-03T09:26:30Z", "steering.decision", "You chose “Looks right, assess these” at the check-in."), decided_by: "user" },
        step(4, "2026-11-03T09:48:00Z", "run.finished", "Finished the run."),
      ];
      const rows = mergeHistory(decisions, [], { isOwner: true, ownerName: "Ada Lovelace", capability: "evidence_search" });
      expect(rows.map((row) => row.kind)).toEqual(["run", "entry"]);
      const folded = run(rows[0]);
      expect(folded.sentence).toBe("Ran the evidence search · 36 min");
      expect(folded.failed).toBe(false);
      expect(folded.steps.map((s) => s.sentence)).toEqual([
        "Opened an evidence-search run.",
        "Completed screening: 118 of 312 relevant.",
        "Finished the run.",
      ]);
      expect(folded.steps[1].details).toEqual([{ label: "Judged relevant", value: "118" }]);
      expect(rows[1].sentence).toBe("You chose “Looks right, assess these” at the check-in.");
    });

    it("marks a run that stopped or failed, and says so in words", () => {
      const stopped = mergeHistory(
        [step(1, "2026-11-03T09:00:00Z", "run.opened", "Opened."), step(2, "2026-11-03T09:12:00Z", "run.interrupted", "Interrupted the run.")],
        [],
      );
      expect(run(stopped[0])).toMatchObject({ sentence: "The evidence search stopped · 12 min", failed: true });
      const failed = mergeHistory(
        [step(1, "2026-11-03T09:00:00Z", "run.opened", "Opened."), step(2, "2026-11-03T09:05:00Z", "component.failed", "A step failed.")],
        [],
      );
      expect(run(failed[0])).toMatchObject({ sentence: "The evidence search didn't complete · 5 min", failed: true });
      expect(run(failed[0]).steps[1].failed).toBe(true);
      const aborted = mergeHistory(
        [step(1, "2026-11-03T09:00:00Z", "run.opened", "Opened."), step(2, "2026-11-03T09:03:00Z", "run.finished", "The run was stopped.", { status: "aborted" })],
        [],
      );
      expect(run(aborted[0])).toMatchObject({ sentence: "The evidence search stopped · 3 min", failed: true });
    });

    it("opens a run's search row to every term the server lists", () => {
      const rows = mergeHistory(
        [
          step(1, "2026-11-03T09:00:00Z", "run.opened", "Policy Atlas started the run."),
          step(2, "2026-11-03T09:01:00Z", "search.executed", "Searched with 2 queries: “childcare take-up” and “free early education”.", {
            queries: ["childcare take-up", "free early education"],
          }),
        ],
        [],
      );
      const search = run(rows[0]).steps[1];
      expect(search.sentence).toBe("Searched with 2 queries: “childcare take-up” and “free early education”.");
      expect(search.details).toEqual([{ label: "Search terms", value: "childcare take-up\nfree early education" }]);
    });
  });
});

describe("days and times (H4)", () => {
  it("heads a day Today, Yesterday, or with its long en-GB date", () => {
    const now = new Date(2026, 10, 5, 12, 0, 0);
    expect(dayHeading(new Date(2026, 10, 5, 8, 0).toISOString(), now)).toBe("Today");
    expect(dayHeading(new Date(2026, 10, 4, 23, 59).toISOString(), now)).toBe("Yesterday");
    expect(dayHeading(new Date(2026, 10, 3, 9, 2).toISOString(), now)).toBe("Tuesday 3 November 2026");
  });

  it("groups consecutive rows by their local day", () => {
    const now = new Date(2026, 10, 5, 12, 0, 0);
    const turns = [
      { turn_index: 0, created_at: new Date(2026, 10, 3, 9, 0).toISOString(), user_message: "a", status: "completed" as const },
      { turn_index: 1, created_at: new Date(2026, 10, 3, 9, 5).toISOString(), user_message: "b", status: "completed" as const },
      { turn_index: 2, created_at: new Date(2026, 10, 5, 9, 0).toISOString(), user_message: "c", status: "completed" as const },
    ];
    const days = groupByDay(mergeHistory([], turns), now);
    expect(days.map((day) => [day.heading, day.items.length])).toEqual([
      ["Tuesday 3 November 2026", 2],
      ["Today", 1],
    ]);
  });
});
