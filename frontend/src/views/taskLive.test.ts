import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { NO_MARKS, landingOf, nextMarks, visitMarks, withTabMarks, type Landing } from "./taskLive";
import { createInitialRunStreamState, type StageEntry } from "../store";

const landing = (overrides: Partial<Landing> = {}): Landing => ({
  runId: "r1",
  sections: 0,
  finished: false,
  ...overrides,
});

describe("tab marks (task 058, N14; owner round 8: the Result tab's only)", () => {
  it("marks the Result tab only when a section lands while the user is elsewhere", () => {
    expect(nextMarks(NO_MARKS, landing(), landing({ sections: 1 }), "sources", true)).toEqual({
      result: true,
      ready: false,
    });
    expect(nextMarks(NO_MARKS, landing(), landing({ sections: 1 }), "result", true).result).toBe(false);
  });

  it("gives the Sources tab no mark, whatever lands (owner, round 8)", () => {
    const stream = {
      ...createInitialRunStreamState(),
      run: { id: "r1", status: "running" as const, startedAt: "2026-11-05T10:00:00Z" },
      stages: [
        { stage: "acquire", label: "Searching", status: "completed", startedAt: "2026-11-05T10:00:00Z", counts: [] },
        { stage: "screen", label: "Screening", status: "completed", startedAt: "2026-11-05T10:01:00Z", counts: [] },
      ] satisfies StageEntry[],
    };
    expect(landingOf(stream)).toEqual({ runId: "r1", sections: 0, finished: false });
    expect(NO_MARKS).not.toHaveProperty("sources");
    const items = withTabMarks<{ tab: string; marker?: ReactNode }>(
      [{ tab: "result" }, { tab: "sources" }],
      { result: true, ready: false },
    );
    expect(items[0].marker).toBeDefined();
    expect(items[1].marker).toBeUndefined();
  });

  it("marks Result and the unseen finish when the run finishes, unless the Result tab is in front of the user", () => {
    expect(nextMarks(NO_MARKS, landing(), landing({ finished: true }), "agent", true)).toEqual({
      result: true,
      ready: true,
    });
    expect(nextMarks(NO_MARKS, landing(), landing({ finished: true }), "result", true).ready).toBe(false);
    // On the Result tab in a background browser tab, the title still tells.
    expect(nextMarks(NO_MARKS, landing(), landing({ finished: true }), "result", false).ready).toBe(true);
  });

  it("clears the Result tab's dot on visiting it, and the finish once the Result tab is seen", () => {
    const marked = { result: true, ready: true };
    expect(visitMarks(marked, "sources", true)).toBe(marked);
    expect(visitMarks(marked, "result", false)).toEqual({ result: false, ready: true });
    expect(visitMarks(marked, "result", true)).toEqual({ result: false, ready: false });
    expect(visitMarks(NO_MARKS, "result", true)).toBe(NO_MARKS);
  });

  it("forgets an old finish when a new run starts", () => {
    const marks = { ...NO_MARKS, ready: true };
    expect(nextMarks(marks, landing({ finished: true }), landing({ runId: "r2" }), "agent", true).ready).toBe(false);
  });
});
