import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as queries from "../api/queries";
import { TasksListView } from "./TasksListView";

vi.mock("../api/queries", () => ({
  useMe: vi.fn(),
  useProjects: vi.fn(),
  usePortfolios: vi.fn(),
}));

const ROW = {
  project_id: "task-1",
  name: "Healthier childhoods",
  updated_at: "2026-07-21T09:00:00Z",
  latest_run: null,
  portfolio_id: null,
  source_count: 4,
  is_owner: true,
  owner_display: "Ada Lovelace",
};

function renderView() {
  return render(
    <MemoryRouter>
      <TasksListView />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.mocked(queries.usePortfolios).mockReturnValue(
    { data: { data: [] } } as unknown as ReturnType<typeof queries.usePortfolios>,
  );
  vi.mocked(queries.useProjects).mockReturnValue(
    {
      data: { data: [ROW] },
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof queries.useProjects>,
  );
});

describe("TasksListView — the Organisation/Mine switcher (task 033 phase 10b, rubric 14 dark launch)", () => {
  it("hides the switcher, and calls useProjects with no scope, when /me has no organisation", () => {
    vi.mocked(queries.useMe).mockReturnValue(
      { data: { user_id: "u1", display_name: "Ada Lovelace", organisation: null, is_admin: false } } as unknown as ReturnType<
        typeof queries.useMe
      >,
    );
    renderView();
    expect(screen.queryByRole("tablist", { name: "Scope" })).not.toBeInTheDocument();
    expect(queries.useProjects).toHaveBeenCalledWith(undefined);
    // Byte-identical to today: no owner column either, even though the
    // row carries `owner_display` now.
    expect(screen.queryByText("Ada Lovelace")).not.toBeInTheDocument();
  });

  it("shows the switcher when enrolled, defaults to Organisation, and drives scope on click", async () => {
    vi.mocked(queries.useMe).mockReturnValue(
      {
        data: {
          user_id: "u1",
          display_name: "Ada Lovelace",
          organisation: { org_id: "org-1", name: "Dept" },
          is_admin: false,
        },
      } as unknown as ReturnType<typeof queries.useMe>,
    );
    const user = userEvent.setup();
    renderView();
    expect(queries.useProjects).toHaveBeenCalledWith({ scope: "all" });
    expect(screen.getByRole("tab", { name: "Organisation" })).toHaveAttribute("aria-selected", "true");

    await user.click(screen.getByRole("tab", { name: "Mine" }));
    expect(queries.useProjects).toHaveBeenCalledWith({ scope: "mine" });
  });

  it("shows the owner column once enrolled, even on the caller's own row", () => {
    vi.mocked(queries.useMe).mockReturnValue(
      {
        data: {
          user_id: "u1",
          display_name: "Ada Lovelace",
          organisation: { org_id: "org-1", name: "Dept" },
          is_admin: false,
        },
      } as unknown as ReturnType<typeof queries.useMe>,
    );
    renderView();
    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
  });

  it("shows the admin wider-list notice only for admin + Organisation scope", () => {
    vi.mocked(queries.useMe).mockReturnValue(
      {
        data: {
          user_id: "admin-1",
          display_name: "Admin",
          organisation: { org_id: "org-1", name: "Dept" },
          is_admin: true,
        },
      } as unknown as ReturnType<typeof queries.useMe>,
    );
    renderView();
    expect(screen.getByText("Showing every organisation.")).toBeInTheDocument();
  });

  it("does not show the admin notice for a non-admin", () => {
    vi.mocked(queries.useMe).mockReturnValue(
      {
        data: {
          user_id: "u1",
          display_name: "Ada Lovelace",
          organisation: { org_id: "org-1", name: "Dept" },
          is_admin: false,
        },
      } as unknown as ReturnType<typeof queries.useMe>,
    );
    renderView();
    expect(screen.queryByText("Showing every organisation.")).not.toBeInTheDocument();
  });

  it("renders a null owner_display as 'No organisation' for the admin wide list", () => {
    vi.mocked(queries.useMe).mockReturnValue(
      {
        data: {
          user_id: "admin-1",
          display_name: "Admin",
          organisation: { org_id: "org-1", name: "Dept" },
          is_admin: true,
        },
      } as unknown as ReturnType<typeof queries.useMe>,
    );
    vi.mocked(queries.useProjects).mockReturnValue(
      {
        data: { data: [{ ...ROW, project_id: "orphan-1", is_owner: false, owner_display: null }] },
        isPending: false,
        isError: false,
        refetch: vi.fn(),
      } as unknown as ReturnType<typeof queries.useProjects>,
    );
    renderView();
    expect(screen.getByText("No organisation")).toBeInTheDocument();
  });
});
