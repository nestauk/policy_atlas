import { describe, expect, it } from "vitest";

import { newTaskHref, rowAccessibleName, showOwnerColumn } from "./listPageChrome";

describe("newTaskHref", () => {
  it("opens the capability picker, with an optional task preset", () => {
    expect(newTaskHref()).toBe("/new");
    expect(newTaskHref("p-1")).toBe("/new?project=p-1");
  });
});

describe("rowAccessibleName", () => {
  it("joins what the row shows with one separator", () => {
    expect(rowAccessibleName(["Bus fare caps", "Paused", null, "", undefined, "5 Nov"])).toBe(
      "Bus fare caps · Paused · 5 Nov",
    );
  });
});

// Round 10, lead ruling P6: the owner column is off on Mine, active or
// archived; on Organisation it shows, active or archived (round 11).
describe("showOwnerColumn", () => {
  it("is off on the reader's own views and on for Organisation", () => {
    expect(showOwnerColumn(true, [{ is_owner: true }], "mine")).toBe(false);
    expect(showOwnerColumn(true, [{ is_owner: true }], "all")).toBe(true);
    expect(showOwnerColumn(true, [{ is_owner: true }])).toBe(true);
    expect(showOwnerColumn(false, [{ is_owner: true }])).toBe(false);
  });
});
