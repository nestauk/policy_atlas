import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SourcesLayout } from "./SourcesLayout";
import * as queries from "../api/queries";

vi.mock("../api/queries", () => ({
  useFunnel: vi.fn(),
}));

vi.mock("../store", () => ({
  useRunStream: () => ({ run: null, stages: [] }),
}));

const PROJECT_ID = "11111111-1111-1111-1111-111111111111";

function renderLayout(path = `/projects/${PROJECT_ID}/sources`) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/projects/:projectId/sources" element={<SourcesLayout />}>
          <Route index element={<div>themes child</div>} />
          <Route path="landscape" element={<div>landscape child</div>} />
          <Route path="all" element={<div>all child</div>} />
          <Route path="findings" element={<div>findings child</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

function mockFunnel(findings: number | null | undefined) {
  vi.mocked(queries.useFunnel).mockReturnValue(
    { data: { findings } } as unknown as ReturnType<typeof queries.useFunnel>,
  );
}

describe("SourcesLayout — the four Sources subview tabs", () => {
  beforeEach(() => {
    vi.mocked(queries.useFunnel).mockReset();
  });

  it("always renders Themes, Landscape and All sources", () => {
    mockFunnel(34);
    renderLayout();
    expect(screen.getByRole("link", { name: "Themes" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Landscape" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "All sources" })).toBeInTheDocument();
  });

  it("shows the Findings tab when the funnel reports a nonzero findings count", () => {
    mockFunnel(34);
    renderLayout();
    expect(screen.getByRole("link", { name: "Findings" })).toBeInTheDocument();
  });

  it("omits the Findings tab entirely — not disabled, not empty — when findings is zero", () => {
    mockFunnel(0);
    renderLayout();
    expect(screen.queryByRole("link", { name: /Findings/ })).toBeNull();
  });

  it("omits the Findings tab when findings is null", () => {
    mockFunnel(null);
    renderLayout();
    expect(screen.queryByRole("link", { name: /Findings/ })).toBeNull();
  });

  it("omits the Findings tab when findings is undefined (funnel not yet loaded)", () => {
    mockFunnel(undefined);
    renderLayout();
    expect(screen.queryByRole("link", { name: /Findings/ })).toBeNull();
  });

  it("renders the index route's Themes view under the tab strip", () => {
    mockFunnel(34);
    renderLayout();
    expect(screen.getByText("themes child")).toBeInTheDocument();
  });

  it("does not show the funnel summary — that belongs on All sources", () => {
    vi.mocked(queries.useFunnel).mockReturnValue(
      {
        data: { findings: 34, found: 128, relevant: 46, cited: 12 },
      } as unknown as ReturnType<typeof queries.useFunnel>,
    );
    renderLayout();
    expect(screen.queryByText(/Showing \d+ of \d+ sources/)).toBeNull();
  });

  it("spans the subview tabs across the content column", () => {
    mockFunnel(34);
    renderLayout();
    const nav = screen.getByRole("navigation", { name: "Sources" });
    expect(nav).toHaveClass("flex");
    expect(nav).not.toHaveClass("justify-end");
    expect(screen.getByRole("link", { name: "Themes" })).toHaveClass("flex-1");
    expect(screen.getByRole("link", { name: "Landscape" })).toHaveClass("flex-1");
  });

  it("uses the wide column for every Sources subview, including Themes", () => {
    mockFunnel(34);
    renderLayout();
    expect(screen.getByRole("navigation", { name: "Sources" }).closest(".mx-auto")).toHaveClass(
      "max-w-[1180px]",
    );
  });
});
