import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { sourcesSubtabChoice, withSourcesLanding } from "./lifecycle";

// A storage of our own: the Node and jsdom storages behave differently
// locally and on CI (docs/knowledge), so the tests never lean on either.
function fakeStorage(): Storage {
  const values = new Map<string, string>();
  return {
    get length() {
      return values.size;
    },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    key: (index) => [...values.keys()][index] ?? null,
    removeItem: (key) => void values.delete(key),
    setItem: (key, value) => void values.set(key, String(value)),
  };
}

const sources = (taskId: string, landing: "" | "/all" | "/landscape") =>
  withSourcesLanding([{ tab: "sources", to: `/tasks/${taskId}/sources?chat=c1` }], landing)[0].to;

beforeEach(() => {
  vi.stubGlobal("localStorage", fakeStorage());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the Sources tab remembers the reader's subtab (owner, round 10)", () => {
  it("lands by stage on a first visit, before the reader has chosen", () => {
    expect(sources("t1", "/all")).toBe("/tasks/t1/sources/all?chat=c1");
    expect(sources("t1", "/landscape")).toBe("/tasks/t1/sources/landscape?chat=c1");
    expect(sources("t1", "")).toBe("/tasks/t1/sources?chat=c1");
  });

  it("returns to the chosen subtab, live or done, until another is chosen", () => {
    sourcesSubtabChoice.remember("t1", "/landscape");
    // Live, the stage would say All sources; done, Themes. The choice wins.
    expect(sources("t1", "/all")).toBe("/tasks/t1/sources/landscape?chat=c1");
    expect(sources("t1", "")).toBe("/tasks/t1/sources/landscape?chat=c1");
    sourcesSubtabChoice.remember("t1", "");
    expect(sources("t1", "/all")).toBe("/tasks/t1/sources?chat=c1");
    expect(sourcesSubtabChoice.read("t1")).toBe("");
  });

  it("keeps the choice per task", () => {
    sourcesSubtabChoice.remember("t1", "/findings");
    expect(sources("t1", "/all")).toBe("/tasks/t1/sources/findings?chat=c1");
    expect(sources("t2", "/all")).toBe("/tasks/t2/sources/all?chat=c1");
  });

  it("falls back to the landing rule when the storage fails or holds nonsense", () => {
    vi.stubGlobal("localStorage", {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
    });
    expect(() => sourcesSubtabChoice.remember("t1", "/all")).not.toThrow();
    expect(sourcesSubtabChoice.read("t1")).toBeNull();
    expect(sources("t1", "/landscape")).toBe("/tasks/t1/sources/landscape?chat=c1");
    const storage = fakeStorage();
    storage.setItem("policy-atlas:sources-subtab:t1", "/elsewhere");
    vi.stubGlobal("localStorage", storage);
    expect(sources("t1", "/all")).toBe("/tasks/t1/sources/all?chat=c1");
  });
});
