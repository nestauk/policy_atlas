import { describe, expect, it } from "vitest";

import {
  formatListDate,
  newestTaskUpdateByProject,
  rowAccessibleName,
  showOwnerColumn,
  newTaskHref,
  projectLastUpdated,
  sortProjectsByLastUpdated,
} from "./listPageChrome";

describe("listPageChrome — project last updated", () => {
  it("uses the newest task update when tasks exist", () => {
    const map = newestTaskUpdateByProject([
      { project_ids: ["p1"], updated_at: "2026-03-01T00:00:00Z" },
      { project_ids: ["p1"], updated_at: "2026-06-01T00:00:00Z" },
    ]);
    expect(
      projectLastUpdated(
        { project_id: "p1", created_at: "2026-01-01T00:00:00Z" },
        map,
      ),
    ).toBe("2026-06-01T00:00:00Z");
  });

  it("falls back to created_at when a project has no tasks", () => {
    expect(
      projectLastUpdated(
        { project_id: "p2", created_at: "2026-02-01T00:00:00Z" },
        new Map(),
      ),
    ).toBe("2026-02-01T00:00:00Z");
  });

  it("sorts projects by last updated, newest first", () => {
    const map = newestTaskUpdateByProject([
      { project_ids: ["older"], updated_at: "2026-01-01T00:00:00Z" },
      { project_ids: ["newer"], updated_at: "2026-08-01T00:00:00Z" },
    ]);
    const sorted = sortProjectsByLastUpdated(
      [
        { project_id: "older", created_at: "2025-01-01T00:00:00Z", name: "Older" },
        { project_id: "empty", created_at: "2026-07-01T00:00:00Z", name: "Empty" },
        { project_id: "newer", created_at: "2025-01-01T00:00:00Z", name: "Newer" },
      ],
      map,
    );
    expect(sorted.map((row) => row.project_id)).toEqual(["newer", "empty", "older"]);
  });
});

describe("newTaskHref", () => {
  it("opens the capability picker, with an optional task preset", () => {
    expect(newTaskHref()).toBe("/new");
    expect(newTaskHref("p-1")).toBe("/new?project=p-1");
  });
});

// Round 10, lead ruling P7: one date form for every reader.
describe("formatListDate", () => {
  const now = new Date(2026, 10, 6, 12);

  it("drops the year within the current year", () => {
    expect(formatListDate(new Date(2026, 10, 5, 9).toISOString(), now)).toBe("5 Nov");
    expect(formatListDate(new Date(2026, 0, 1, 0, 30).toISOString(), now)).toBe("1 Jan");
  });

  it("keeps the year before it, and never says Sept", () => {
    expect(formatListDate(new Date(2025, 9, 12, 9).toISOString(), now)).toBe("12 Oct 2025");
    expect(formatListDate(new Date(2025, 8, 3, 9).toISOString(), now)).toBe("3 Sep 2025");
  });

  it("is empty for a value it cannot read", () => {
    expect(formatListDate("not a date", now)).toBe("");
  });
});

describe("rowAccessibleName", () => {
  it("joins what the row shows with one separator", () => {
    expect(rowAccessibleName(["Bus fare caps", "Paused", null, "", undefined, "5 Nov"])).toBe(
      "Bus fare caps · Paused · 5 Nov",
    );
  });
});

// Round 10, lead ruling P6: the owner column is off on Mine and Archived.
describe("showOwnerColumn", () => {
  it("is off on the reader's own views and on for Organisation", () => {
    expect(showOwnerColumn(true, [{ is_owner: true }], "mine")).toBe(false);
    expect(showOwnerColumn(true, [{ is_owner: true }], "archived")).toBe(false);
    expect(showOwnerColumn(true, [{ is_owner: true }], "all")).toBe(true);
    expect(showOwnerColumn(true, [{ is_owner: true }])).toBe(true);
    expect(showOwnerColumn(false, [{ is_owner: true }])).toBe(false);
  });
});
