import { describe, expect, it } from "vitest";

import { forgetSkipped, markSkipped, profileGate, skippedThisSession } from "./profileGate";

const NEW = { completed_at: null, skipped_once_at: null };
const SKIPPED = { completed_at: null, skipped_once_at: "2026-11-18T09:00:00Z" };
const COMPLETED = { completed_at: "2026-11-18T09:05:00Z", skipped_once_at: null };

describe("profileGate", () => {
  it("asks at first access, with one skip on offer", () => {
    expect(profileGate(NEW, false)).toBe("ask");
  });

  it("lets the user through for the rest of the login in which they skipped", () => {
    expect(profileGate(SKIPPED, true)).toBe("pass");
  });

  it("asks again at the next login, and offers no second skip", () => {
    expect(profileGate(SKIPPED, false)).toBe("ask_required");
  });

  it("never asks after the profile is completed", () => {
    expect(profileGate(COMPLETED, false)).toBe("pass");
    expect(profileGate({ ...SKIPPED, ...COMPLETED }, false)).toBe("pass");
  });

  it("does not block the app while the profile is unknown", () => {
    expect(profileGate(undefined, false)).toBe("pass");
  });
});

describe("the skip of this login", () => {
  it("is remembered for the user who skipped, and forgotten at sign-out", () => {
    expect(skippedThisSession("ada")).toBe(false);

    markSkipped("ada");
    expect(skippedThisSession("ada")).toBe(true);
    expect(skippedThisSession("grace")).toBe(false);

    forgetSkipped();
    expect(skippedThisSession("ada")).toBe(false);
  });
});
