import { describe, expect, it } from "vitest";

import type { components } from "../../api/gen/types";
import { mockLonglist } from "../../mock/fixtures";
import {
  ORIGIN_WORDS,
  buildingLayout,
  isLonglistBuilding,
  layoutSignature,
  searchStatusLine,
} from "./longlistPresentation";

type Row = components["schemas"]["OptionProgressOut"];
type Longlist = components["schemas"]["LonglistOut"];

const id = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const row = (n: number, patch: Partial<Row> = {}): Row => ({
  option_id: id(n),
  name: `Option ${n}`,
  description: "",
  origin: "suggested",
  state: "included",
  merged_into_option_id: null,
  search_status: "queued",
  found: null,
  ...patch,
});

/** A longlist read over the given ids, built from the mock's first option. */
function longlistOf(ids: number[], patch: (option: Longlist["options"] extends (infer O)[] | undefined ? O : never, n: number) => void = () => {}): Longlist {
  const base = mockLonglist();
  const template = base.options![1];
  return {
    ...base,
    themes: [],
    options: ids.map((n) => {
      const option = { ...template, option_id: id(n), name: `Option ${n}`, origin: "suggested" as const, state: "included" as const, exclusion: null, profile: null, primary_lever_type: null, lever_none_fits_reason: null, shortlist: null, document_count: n * 2 };
      patch(option, n);
      return option;
    }),
  };
}

describe("origin words (task 058, scene 15; round 10, C1)", () => {
  it("maps every origin literal to its words in one place, one vocabulary for the build and the finished list", () => {
    expect(ORIGIN_WORDS).toEqual({
      from_evidence_search: "from your report",
      suggested: "suggested by Policy Atlas",
      added_by_you: "added by you",
      clustered: "found in the evidence",
    });
  });
});

describe("isLonglistBuilding (N24)", () => {
  const scoping = (stage: string | null) => ({ capability: "options_scoping", active_run: { stage } });
  it("is building while a longlist walk is live, from the stream or the task read", () => {
    expect(isLonglistBuilding(scoping(null), [{ stage: "suggest" }])).toBe(true);
    expect(isLonglistBuilding(scoping("option_searches"), [])).toBe(true);
    expect(isLonglistBuilding(scoping("shortlist"), [{ stage: "theme" }, { stage: "shortlist" }])).toBe(true);
  });
  it("is not building for the baseline walk, a standalone shortlist walk, no walk, or an Evidence search", () => {
    expect(isLonglistBuilding(scoping("acquire"), [{ stage: "acquire" }])).toBe(false);
    expect(isLonglistBuilding(scoping("shortlist"), [{ stage: "shortlist" }])).toBe(false);
    expect(isLonglistBuilding({ capability: "options_scoping", active_run: null }, [{ stage: "suggest" }])).toBe(false);
    expect(isLonglistBuilding({ capability: "evidence_search", active_run: { stage: "suggest" } }, [])).toBe(false);
  });
});

describe("searchStatusLine", () => {
  it("reads queued, searching, searched with its count, failed", () => {
    expect(searchStatusLine({ search_status: "queued", found: null })?.text).toBe("Queued");
    expect(searchStatusLine({ search_status: "searching", found: null })?.text).toBe("Searching");
    expect(searchStatusLine({ search_status: "searched", found: 1312 })?.text).toBe("Searched · 1,312 found");
    expect(searchStatusLine({ search_status: "failed", found: null })?.text).toBe("Search failed");
  });
});

describe("buildingLayout (N24, D9)", () => {
  it("gives one flat group of rows with their searches before the longlist exists", () => {
    const layout = buildingLayout([row(1, { search_status: "searched", found: 312 }), row(2, { search_status: "searching" }), row(3)], null);
    expect(layout.groups).toHaveLength(1);
    expect(layout.groups[0].title).toBeNull();
    expect(layout.groups[0].rows.map((r) => r.status?.text)).toEqual(["Searched · 312 found", "Searching", "Queued"]);
    expect(layout.groups[0].rows.every((r) => r.lever === null && !r.shortlisted)).toBe(true);
  });

  it("folds a row under its parent and adds the clustered rows at the end, its search line giving way to the summary", () => {
    const rows = [row(1), row(2, { merged_into_option_id: id(3) }), row(3), row(4, { origin: "clustered" })];
    const layout = buildingLayout(rows, longlistOf([1, 3, 4], (o, n) => { if (n === 4) o.origin = "clustered"; }));
    const flat = layout.groups[0].rows;
    expect(flat.map((r) => r.id)).toEqual([id(1), id(3), id(4)]);
    expect(flat[1].folded).toEqual([{ id: id(2), name: "Option 2" }]);
    expect(flat[2].origin).toBe("found in the evidence");
    // The count is said once, on the evidence line the summary brings (R85).
    expect(flat.map((r) => r.status)).toEqual([null, null, null]);
    expect(flat.map((r) => r.summary?.document_count)).toEqual([2, 6, 8]);
  });

  it("lays a finished list out from the longlist read alone, before the options read answers", () => {
    const longlist = longlistOf([1, 2]);
    const layout = buildingLayout([], longlist);
    expect(layout.groups[0].rows.map((r) => [r.id, r.status, r.summary?.option_id])).toEqual([
      [id(1), null, id(1)],
      [id(2), null, id(2)],
    ]);
  });

  it("lands each wave from the longlist read: levers, exclusions, themes, shortlist marks", () => {
    const rows = [row(1), row(2), row(3)];
    const profiled = buildingLayout(rows, longlistOf([1, 2, 3], (o) => { o.primary_lever_type = "regulate"; }));
    expect(profiled.groups[0].rows.map((r) => r.lever)).toEqual(["Regulate", "Regulate", "Regulate"]);

    const constrained = buildingLayout(rows, longlistOf([1, 2, 3], (o, n) => {
      if (n === 2) { o.state = "excluded"; o.exclusion = { by: "constrain", constraint: "Youth only", reason: "Out of scope: not a youth measure" }; }
    }));
    expect(constrained.groups[0].rows.map((r) => r.id)).toEqual([id(1), id(3)]);
    expect(constrained.excluded.map((r) => r.summary?.exclusion?.reason)).toEqual(["Out of scope: not a youth measure"]);

    const themed = longlistOf([1, 2, 3], (o, n) => { if (n === 3) o.shortlist = { state: "proposed", reason: "" }; });
    themed.themes = [
      { ...mockLonglist().themes![0], theme_id: "t1", name: "Staying in work", option_ids: [id(3)] },
      { ...mockLonglist().themes![0], theme_id: "t2", name: "Getting into work", option_ids: [id(1)] },
    ];
    const grouped = buildingLayout(rows, themed);
    expect(grouped.groups.map((g) => g.title)).toEqual(["Staying in work", "Getting into work", "No theme"]);
    expect(grouped.groups[0].rows[0].shortlisted).toBe(true);
    expect(grouped.groups[1].rows[0].shortlisted).toBe(false);
  });

  it("runs a theme's rows by lever then name, as the finished list sorts them", () => {
    const rows = [row(1), row(2), row(3)];
    const themed = longlistOf([1, 2, 3], (o, n) => {
      o.primary_lever_type = n === 1 ? "subsidise" : "regulate";
      o.name = n === 3 ? "A option" : `Option ${n}`;
    });
    themed.lever_types = ["regulate", "subsidise"];
    themed.themes = [{ ...mockLonglist().themes![0], theme_id: "t1", name: "All", option_ids: [id(1), id(2), id(3)] }];
    expect(buildingLayout(rows, themed).groups[0].rows.map((r) => r.id)).toEqual([id(3), id(2), id(1)]);
  });

  it("signs the grouping, not the values, so only a regrouping moves rows", () => {
    const rows = [row(1), row(2)];
    const before = layoutSignature(buildingLayout(rows, longlistOf([1, 2])));
    const valued = layoutSignature(buildingLayout(rows, longlistOf([1, 2], (o) => { o.primary_lever_type = "regulate"; })));
    expect(valued).toBe(before);
    const themed = longlistOf([1, 2]);
    themed.themes = [{ ...mockLonglist().themes![0], theme_id: "t1", name: "All", option_ids: [id(2)] }];
    expect(layoutSignature(buildingLayout(rows, themed))).not.toBe(before);
  });
});
