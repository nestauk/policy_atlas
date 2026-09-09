import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { mockFunnel, mockGroups, mockLandscape } from "../mock/fixtures";
import { LandscapeView } from "./LandscapeView";
import * as queries from "../api/queries";

vi.mock("../api/queries", () => ({
  useTask: vi.fn(),
  useLandscape: vi.fn(),
  useFunnel: vi.fn(),
  useGroups: vi.fn(),
}));

const TASK_ID = "11111111-1111-1111-1111-111111111111";

function renderLandscape() {
  return render(
    <MemoryRouter initialEntries={[`/tasks/${TASK_ID}/sources/landscape`]}>
      <Routes>
        <Route path="/tasks/:taskId/sources/landscape" element={<LandscapeView />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.mocked(queries.useTask).mockReturnValue(
    { data: { name: "Tower Hamlets task" } } as unknown as ReturnType<typeof queries.useTask>,
  );
});

describe("LandscapeView", () => {
  it("stacks one centred plot per row so classification labels are not squeezed", () => {
    vi.mocked(queries.useLandscape).mockReturnValue({
      data: mockLandscape,
      isPending: false,
      isError: false,
    } as unknown as ReturnType<typeof queries.useLandscape>);
    vi.mocked(queries.useFunnel).mockReturnValue({
      data: mockFunnel,
      isPending: false,
      isError: false,
    } as unknown as ReturnType<typeof queries.useFunnel>);
    vi.mocked(queries.useGroups).mockReturnValue({
      data: mockGroups,
      isPending: false,
      isError: false,
    } as unknown as ReturnType<typeof queries.useGroups>);

    const { container } = renderLandscape();

    expect(screen.getByText("Evidence types").parentElement?.className).toContain("max-w-3xl");
    expect(screen.getByText("Publication years").parentElement?.className).toContain("max-w-3xl");
    expect(screen.getByText("From search to citation").parentElement?.className).toContain("max-w-3xl");
    expect(container.querySelector(".lg\\:grid-cols-2")).toBeNull();
  });
});
