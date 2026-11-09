import { describe, expect, it } from "vitest";

import {
  rowAccessibleName,
  rowOwnerCellClass,
  rowStatusCellClass,
  showOwnerColumn,
  taskListGridClass,
  taskListGridClassWithOwner,
  taskListItemClass,
  taskListRowGridClass,
  newTaskHref,
} from "./listPageChrome";

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

/** The `md:grid-cols-[…]` tracks of a list grid class, split. */
function tracks(className: string): string[] {
  const match = /md:grid-cols-\[([^\]]+)\]/.exec(className);
  if (match === null) throw new Error(`no md tracks in ${className}`);
  return match[1].split("_");
}

// Round 12 (owner: the gap between the status and the owner "is making the
// task names cramped"). The status and owner columns were fixed widths sized
// for the widest word any list could hold; now the list is one grid whose
// rows are subgrids, so they size to what this list holds.
describe("the task list's column rule (round 12)", () => {
  it("gives the name every pixel the content-sized columns leave", () => {
    expect(tracks(taskListGridClassWithOwner)).toEqual([
      "minmax(0,1fr)", // name
      "auto", // kind
      "auto", // status
      "auto", // owner
      "5.5rem", // sources
      "8.5rem", // date, plus the row's 48 px right padding (the menu control)
    ]);
    expect(tracks(taskListGridClass)).toEqual(["minmax(0,1fr)", "auto", "auto", "5.5rem", "8.5rem"]);
    // Only the name track is flexible, so no slack lands anywhere else.
    for (const className of [taskListGridClass, taskListGridClassWithOwner]) {
      expect(tracks(className).filter((track) => track.includes("fr"))).toEqual(["minmax(0,1fr)"]);
    }
  });

  it("makes every row a subgrid of the list from md up and its own two tracks below", () => {
    expect(taskListItemClass.split(" ")).toEqual(
      expect.arrayContaining(["md:col-span-full", "md:grid", "md:grid-cols-subgrid"]),
    );
    expect(taskListRowGridClass.split(" ")).toEqual(
      expect.arrayContaining(["md:col-span-full", "md:grid-cols-subgrid", "max-md:grid-cols-[minmax(0,1fr)_auto]"]),
    );
  });

  it("puts 24 px between the widest status word and the owner", () => {
    // The 16 px column gap plus the status cell's own 8 px.
    expect(taskListGridClassWithOwner).toContain("md:gap-x-4");
    expect(rowStatusCellClass.split(" ")).toEqual(expect.arrayContaining(["md:pr-2", "md:box-content"]));
    // Never wider than the old fixed column.
    expect(rowStatusCellClass).toContain("md:max-w-[11.5rem]");
  });

  it("fits the owner to the longest name, capped and ellipsed", () => {
    expect(rowOwnerCellClass.split(" ")).toEqual(
      expect.arrayContaining(["max-w-[8rem]", "truncate", "text-left"]),
    );
  });
});
