import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SourcesLayout } from "./SourcesLayout";
import * as queries from "../api/queries";

vi.mock("../api/queries", () => ({
  useFunnel: vi.fn(),
}));

const PROJECT_ID = "11111111-1111-1111-1111-111111111111";

function renderLayout() {
  return render(
    <MemoryRouter initialEntries={[`/projects/${PROJECT_ID}/sources`]}>
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
});
