import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { mockGroups, mockLandscape } from "../mock/fixtures";
import { ThemesView } from "./ThemesView";
import * as queries from "../api/queries";

vi.mock("../api/queries", () => ({
  useProject: vi.fn(),
  useLandscape: vi.fn(),
  useGroups: vi.fn(),
}));

const PROJECT_ID = "11111111-1111-1111-1111-111111111111";

function renderThemes() {
  return render(
    <MemoryRouter initialEntries={[`/projects/${PROJECT_ID}/sources`]}>
      <Routes>
        <Route path="/projects/:projectId/sources" element={<ThemesView />} />
        <Route path="/projects/:projectId/sources/all" element={<div>all sources</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.mocked(queries.useProject).mockReturnValue(
    { data: { name: "Tower Hamlets project" } } as unknown as ReturnType<typeof queries.useProject>,
  );
});

describe("ThemesView — reader-facing themes and groups", () => {
  it("renders a landscape theme's name, size and existing prose description", () => {
    vi.mocked(queries.useLandscape).mockReturnValue(
      { data: mockLandscape, isPending: false, isError: false } as unknown as ReturnType<typeof queries.useLandscape>,
    );
    vi.mocked(queries.useGroups).mockReturnValue(
      { data: undefined, isPending: false, isError: false } as unknown as ReturnType<typeof queries.useGroups>,
    );
    renderThemes();
    expect(screen.getByText("School food environments")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Key themes" })).toBeNull();
    expect(screen.getByText("19 documents")).toBeInTheDocument();
    expect(
      screen.getByText("Meal standards, free breakfast, and food access."),
    ).toBeInTheDocument();
  });

  it("links a landscape theme with a theme_id through to All sources filtered on that theme", () => {
    vi.mocked(queries.useLandscape).mockReturnValue(
      { data: mockLandscape, isPending: false, isError: false } as unknown as ReturnType<typeof queries.useLandscape>,
    );
    vi.mocked(queries.useGroups).mockReturnValue(
      { data: undefined, isPending: false, isError: false } as unknown as ReturnType<typeof queries.useGroups>,
    );
    renderThemes();
    const schoolFood = mockLandscape.themes?.find((theme) => theme.name === "School food environments");
    expect(screen.getByRole("link", { name: /School food environments/ })).toHaveAttribute(
      "href",
      `/projects/${PROJECT_ID}/sources/all?theme=${schoolFood?.theme_id}`,
    );
    expect(screen.queryByRole("link", { name: /Family support/ })).toBeNull();
  });

  it("does not turn grouping-facet rows into source-filter links", () => {
    vi.mocked(queries.useLandscape).mockReturnValue(
      { data: mockLandscape, isPending: false, isError: false } as unknown as ReturnType<typeof queries.useLandscape>,
    );
    vi.mocked(queries.useGroups).mockReturnValue(
      { data: mockGroups, isPending: false, isError: false } as unknown as ReturnType<typeof queries.useGroups>,
    );
    renderThemes();
    expect(screen.getByText("Intervention type")).toBeInTheDocument();
    expect(screen.getByText("Universal breakfast provision")).toBeInTheDocument();
    expect(
      screen.getByText("School-based universal breakfast schemes."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Universal breakfast provision/ })).toBeNull();
  });

  it("shows an empty state when there are no themes and no facets", () => {
    vi.mocked(queries.useLandscape).mockReturnValue(
      { data: { evidence_types: {}, years: {}, themes: [] }, isPending: false, isError: false } as unknown as ReturnType<typeof queries.useLandscape>,
    );
    vi.mocked(queries.useGroups).mockReturnValue(
      { data: { facets: [] }, isPending: false, isError: false } as unknown as ReturnType<typeof queries.useGroups>,
    );
    renderThemes();
    expect(screen.getByRole("status")).toHaveTextContent("Themes appear once screening has run.");
  });
});
