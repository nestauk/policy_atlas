import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { rememberedChoice, rememberedKey } from "./remembered";

// A storage of our own: the Node and jsdom storages behave differently
// locally and on CI (docs/knowledge), so the tests never lean on either.
function fakeStorage(): Storage & { values: Map<string, string> } {
  const values = new Map<string, string>();
  return {
    values,
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

const COLOURS = ["red", "green"] as const;
const colour = rememberedChoice<(typeof COLOURS)[number]>("colour", {
  write: (value) => value,
  read: (stored) => COLOURS.find((candidate) => candidate === stored) ?? null,
});

let storage: ReturnType<typeof fakeStorage>;

beforeEach(() => {
  storage = fakeStorage();
  vi.stubGlobal("localStorage", storage);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("remembered choices (round 12 consolidation)", () => {
  it("keys every choice policy-atlas:<name>:<taskId>", () => {
    expect(rememberedKey("sources-subtab", "t1")).toBe("policy-atlas:sources-subtab:t1");
    colour.remember("t1", "green");
    expect(storage.values.get("policy-atlas:colour:t1")).toBe("green");
  });

  it("reads back the choice per task, and nothing before one is made", () => {
    colour.remember("t1", "red");
    expect(colour.read("t1")).toBe("red");
    expect(colour.read("t2")).toBeNull();
  });

  it("reads a stored string that is no longer a value as nothing", () => {
    storage.setItem("policy-atlas:colour:t1", "blue");
    expect(colour.read("t1")).toBeNull();
  });

  it("never throws when the storage is blocked", () => {
    vi.stubGlobal("localStorage", {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
    });
    expect(() => colour.remember("t1", "red")).not.toThrow();
    expect(colour.read("t1")).toBeNull();
  });
});
