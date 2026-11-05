import { describe, expect, it } from "vitest";

import { NO_MARKS, nextMarks, visitMarks, type Landing } from "./taskLive";

const landing = (overrides: Partial<Landing> = {}): Landing => ({
  runId: "r1",
  sections: 0,
  sources: 0,
  finished: false,
  ...overrides,
});

describe("tab marks (task 058, N14)", () => {
  it("marks a tab only when its content lands while the user is elsewhere", () => {
    const onSources = nextMarks(NO_MARKS, landing(), landing({ sections: 1, sources: 1 }), "sources", true);
    expect(onSources).toMatchObject({ result: true, sources: false });
    const onResult = nextMarks(NO_MARKS, landing(), landing({ sections: 1, sources: 1 }), "result", true);
    expect(onResult).toMatchObject({ result: false, sources: true });
  });

  it("marks Result and the unseen finish when the run finishes, unless the Result tab is in front of the user", () => {
    expect(nextMarks(NO_MARKS, landing(), landing({ finished: true }), "agent", true)).toEqual({
      result: true,
      sources: false,
      ready: true,
    });
    expect(nextMarks(NO_MARKS, landing(), landing({ finished: true }), "result", true).ready).toBe(false);
    // On the Result tab in a background browser tab, the title still tells.
    expect(nextMarks(NO_MARKS, landing(), landing({ finished: true }), "result", false).ready).toBe(true);
  });

  it("clears a tab's dot on visiting it, and the finish once the Result tab is seen", () => {
    const marked = { result: true, sources: true, ready: true };
    expect(visitMarks(marked, "sources", true)).toEqual({ result: true, sources: false, ready: true });
    expect(visitMarks(marked, "result", false)).toEqual({ result: false, sources: true, ready: true });
    expect(visitMarks(marked, "result", true)).toEqual({ result: false, sources: true, ready: false });
    expect(visitMarks(NO_MARKS, "result", true)).toBe(NO_MARKS);
  });

  it("forgets an old finish when a new run starts", () => {
    const marks = { ...NO_MARKS, ready: true };
    expect(nextMarks(marks, landing({ finished: true }), landing({ runId: "r2" }), "agent", true).ready).toBe(false);
  });
});
