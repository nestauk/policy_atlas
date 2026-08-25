import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as queries from "../api/queries";
import { PortfolioDetailView, PortfoliosView } from "./PortfoliosView";

vi.mock("../api/queries", () => ({
  usePortfolio: vi.fn(),
  usePortfolios: vi.fn(),
  useProjects: vi.fn(),
}));

vi.mock("../api/mutations", () => ({
  useCreatePortfolio: vi.fn(),
}));

const PORTFOLIO_ID = "portfolio-1";

function renderDetail(portfolioId = PORTFOLIO_ID) {
  return render(
    <MemoryRouter initialEntries={[`/portfolios/${portfolioId}`]}>
      <Routes>
        <Route path="/portfolios/:portfolioId" element={<PortfolioDetailView />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.mocked(queries.usePortfolio).mockReturnValue(
    {
      data: { portfolio_id: PORTFOLIO_ID, name: "Housing", description: null },
      isPending: false,
      isError: false,
    } as unknown as ReturnType<typeof queries.usePortfolio>,
  );
  vi.mocked(queries.useProjects).mockReturnValue(
    { data: { data: [] }, isPending: false, isError: false } as unknown as ReturnType<
      typeof queries.useProjects
    >,
  );
  vi.mocked(queries.usePortfolios).mockReturnValue(
    { data: { data: [] }, isPending: false } as unknown as ReturnType<typeof queries.usePortfolios>,
  );
});

describe("PortfolioDetailView — the portfolio_id filter (task 033 phase 10a)", () => {
  it("requests its member tasks with the portfolio_id filter, not the unfiltered global page", () => {
    renderDetail();
    expect(queries.useProjects).toHaveBeenCalledWith({ portfolio_id: PORTFOLIO_ID });
    // Never called with no filter — that would be the pre-10a client-side
    // filter over the global 50-row page, the exact bug this phase fixes.
    expect(queries.useProjects).not.toHaveBeenCalledWith();
    expect(queries.useProjects).not.toHaveBeenCalledWith({});
  });
});

describe("PortfoliosView — the projects-overview page size (task 033 phase 10a)", () => {
  it("raises the global projects page beyond the 50-row default, since PortfolioOut carries no last-task-updated field to use instead", () => {
    render(
      <MemoryRouter>
        <PortfoliosView />
      </MemoryRouter>,
    );
    expect(queries.useProjects).toHaveBeenCalledWith({ page_size: 200 });
  });
});
