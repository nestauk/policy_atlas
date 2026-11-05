import { describe, expect, it } from "vitest";

import type { components } from "../../api/gen/types";
import { mockLonglist } from "../../mock/fixtures";
import {
  ORIGIN_WORDS,
  buildingLayout,
  isLonglistBuilding,
  searchStatusLine,
  stageLineText,
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

describe("origin words (task 058, scene 15)", () => {
  it("maps every origin literal to its word in one place", () => {
    expect(ORIGIN_WORDS).toEqual({
      from_evidence_search: "from your report",
      suggested: "suggested",
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

describe("stageLineText", () => {
  it("joins the server's label and activity, and gives clustering the fold note", () => {
    expect(stageLineText("Searching for each option", "4 of 12 searches done · 1,180 sources so far")).toBe(
      "Searching for each option · 4 of 12 searches done · 1,180 sources so far",
    );
    expect(stageLineText("Clustering into options", "options may be folded together or added")).toBe(
      "Clustering into options · options may be folded together or added",
    );
    expect(stageLineText("Clustering into options", "Assigning sources to options · batch 1 of 2")).toBe(
      "Clustering into options · Assigning sources to options · batch 1 of 2",
    );
    expect(stageLineText("Suggesting options", "Suggesting options")).toBe("Suggesting options");
    expect(stageLineText(null, null)).toBeNull();
  });
});

describe("searchStatusLine", () => {
  it("reads queued, searching, searched with its count, failed", () => {
    expect(searchStatusLine({ search_status: "queued", found: null }).text).toBe("Queued");
    expect(searchStatusLine({ search_status: "searching", found: null }).text).toBe("Searching");
    expect(searchStatusLine({ search_status: "searched", found: 1312 }).text).toBe("Searched · 1,312 found");
    expect(searchStatusLine({ search_status: "failed", found: null }).text).toBe("Search failed");
  });
});

describe("buildingLayout (N24, D9)", () => {
  it("gives one flat group of rows with their searches before the longlist exists", () => {
    const layout = buildingLayout([row(1, { search_status: "searched", found: 312 }), row(2, { search_status: "searching" }), row(3)], null);
    expect(layout.groups).toHaveLength(1);
    expect(layout.groups[0].title).toBeNull();
    expect(layout.groups[0].rows.map((r) => r.status.text)).toEqual(["Searched · 312 found", "Searching", "Queued"]);
    expect(layout.groups[0].rows.every((r) => r.lever === null && !r.shortlisted)).toBe(true);
  });

  it("folds a row under its parent and adds the clustered rows at the end, with document counts", () => {
    const rows = [row(1), row(2, { merged_into_option_id: id(3) }), row(3), row(4, { origin: "clustered" })];
    const layout = buildingLayout(rows, longlistOf([1, 3, 4], (o, n) => { if (n === 4) o.origin = "clustered"; }));
    const flat = layout.groups[0].rows;
    expect(flat.map((r) => r.id)).toEqual([id(1), id(3), id(4)]);
    expect(flat[1].folded).toEqual([{ id: id(2), name: "Option 2" }]);
    expect(flat[2].origin).toBe("found in the evidence");
    expect(flat.map((r) => r.status.text)).toEqual(["2 documents", "6 documents", "8 documents"]);
  });

  it("lands each wave from the longlist read: levers, exclusions, themes, shortlist marks", () => {
    const rows = [row(1), row(2), row(3)];
    const profiled = buildingLayout(rows, longlistOf([1, 2, 3], (o) => { o.primary_lever_type = "regulate"; }));
    expect(profiled.groups[0].rows.map((r) => r.lever)).toEqual(["Regulate", "Regulate", "Regulate"]);

    const constrained = buildingLayout(rows, longlistOf([1, 2, 3], (o, n) => {
      if (n === 2) { o.state = "excluded"; o.exclusion = { by: "constrain", constraint: "Youth only", reason: "Out of scope: not a youth measure" }; }
    }));
    expect(constrained.groups[0].rows.map((r) => r.id)).toEqual([id(1), id(3)]);
    expect(constrained.excluded.map((r) => r.reason)).toEqual(["Out of scope: not a youth measure"]);

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
});
