import { describe, expect, it } from "vitest";

import {
  newestTaskUpdateByPortfolio,
  newTaskHref,
  portfolioLastUpdated,
  sortPortfoliosByLastUpdated,
} from "./listPageChrome";

describe("listPageChrome — portfolio last updated", () => {
  it("uses the newest task update when tasks exist", () => {
    const map = newestTaskUpdateByPortfolio([
      { portfolio_ids: ["p1"], updated_at: "2026-03-01T00:00:00Z" },
      { portfolio_ids: ["p1"], updated_at: "2026-06-01T00:00:00Z" },
    ]);
    expect(
      portfolioLastUpdated(
        { portfolio_id: "p1", created_at: "2026-01-01T00:00:00Z" },
        map,
      ),
    ).toBe("2026-06-01T00:00:00Z");
  });

  it("falls back to created_at when a portfolio has no tasks", () => {
    expect(
      portfolioLastUpdated(
        { portfolio_id: "p2", created_at: "2026-02-01T00:00:00Z" },
        new Map(),
      ),
    ).toBe("2026-02-01T00:00:00Z");
  });

  it("sorts portfolios by last updated, newest first", () => {
    const map = newestTaskUpdateByPortfolio([
      { portfolio_ids: ["older"], updated_at: "2026-01-01T00:00:00Z" },
      { portfolio_ids: ["newer"], updated_at: "2026-08-01T00:00:00Z" },
    ]);
    const sorted = sortPortfoliosByLastUpdated(
      [
        { portfolio_id: "older", created_at: "2025-01-01T00:00:00Z", name: "Older" },
        { portfolio_id: "empty", created_at: "2026-07-01T00:00:00Z", name: "Empty" },
        { portfolio_id: "newer", created_at: "2025-01-01T00:00:00Z", name: "Newer" },
      ],
      map,
    );
    expect(sorted.map((row) => row.portfolio_id)).toEqual(["newer", "empty", "older"]);
  });
});

describe("newTaskHref", () => {
  it("opens the capability picker, with an optional project preset", () => {
    expect(newTaskHref()).toBe("/new");
    expect(newTaskHref("p-1")).toBe("/new?portfolio=p-1");
  });
});
