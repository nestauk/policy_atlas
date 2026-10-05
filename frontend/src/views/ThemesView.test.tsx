import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { mockLandscape } from "../mock/fixtures";
import { ThemesView } from "./ThemesView";
import * as queries from "../api/queries";

vi.mock("../api/queries", () => ({
  useTask: vi.fn(),
  useLandscape: vi.fn(),
}));

const TASK_ID = "11111111-1111-1111-1111-111111111111";

function renderThemes() {
  return render(
    <MemoryRouter initialEntries={[`/tasks/${TASK_ID}/sources`]}>
      <Routes>
        <Route path="/tasks/:taskId/sources" element={<ThemesView />} />
        <Route path="/tasks/:taskId/sources/all" element={<div>all sources</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.mocked(queries.useTask).mockReturnValue(
    { data: { name: "Tower Hamlets task" } } as unknown as ReturnType<typeof queries.useTask>,
  );
});

describe("ThemesView — landscape themes only", () => {
  it("renders a landscape theme's name, size and existing prose description", () => {
    vi.mocked(queries.useLandscape).mockReturnValue(
      { data: mockLandscape, isPending: false, isError: false } as unknown as ReturnType<typeof queries.useLandscape>,
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
    renderThemes();
    const schoolFood = mockLandscape.themes?.find((theme) => theme.name === "School food environments");
    expect(screen.getByRole("link", { name: /School food environments/ })).toHaveAttribute(
      "href",
      `/tasks/${TASK_ID}/sources/all?theme=${schoolFood?.theme_id}`,
    );
    expect(screen.queryByRole("link", { name: /Family support/ })).toBeNull();
  });

  it("shows an empty state when there are no landscape themes", () => {
    vi.mocked(queries.useLandscape).mockReturnValue(
      { data: { evidence_types: {}, years: {}, themes: [] }, isPending: false, isError: false } as unknown as ReturnType<typeof queries.useLandscape>,
    );
    renderThemes();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Themes appear once the Mapping step has finished.",
    );
  });
});
