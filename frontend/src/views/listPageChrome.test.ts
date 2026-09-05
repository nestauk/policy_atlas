import { describe, expect, it } from "vitest";

import {
  newestTaskUpdateByProject,
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
