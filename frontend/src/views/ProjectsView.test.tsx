import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as mutations from "../api/mutations";
import * as queries from "../api/queries";
import { ToastProvider } from "../ui/radix/Toast";
import { ProjectDetailView, ProjectsView } from "./ProjectsView";

vi.mock("../api/queries", () => ({
  useMe: vi.fn(),
  useProject: vi.fn(),
  useProjects: vi.fn(),
  useTasks: vi.fn(),
}));

vi.mock("../api/mutations", () => ({
  useCreateProject: vi.fn(),
  useUpdateProject: vi.fn(),
}));

const PROJECT_ID = "project-1";

function renderDetail(projectId = PROJECT_ID) {
  return render(
    <ToastProvider>
      <MemoryRouter initialEntries={[`/projects/${projectId}`]}>
        <Routes>
          <Route path="/projects/:projectId" element={<ProjectDetailView />} />
        </Routes>
      </MemoryRouter>
    </ToastProvider>,
  );
}

function renderList() {
  return render(
    <ToastProvider>
      <MemoryRouter>
        <ProjectsView />
      </MemoryRouter>
    </ToastProvider>,
  );
}

beforeEach(() => {
  // Unenrolled default (task 033 phase 10b dark launch) — every pre-033 test
  // in this file keeps seeing no switcher and no owner column unless a test
  // below opts into an organisation explicitly.
  vi.mocked(queries.useMe).mockReturnValue(
    { data: { user_id: "u1", display_name: "Ada Lovelace", organisation: null, is_admin: false } } as unknown as ReturnType<
      typeof queries.useMe
    >,
  );
  vi.mocked(queries.useProject).mockReturnValue(
    {
      data: {
        project_id: PROJECT_ID,
        name: "Housing",
        description: null,
        visibility: "org",
        is_owner: true,
        owner_display: "Ada Lovelace",
        task_count: 0,
      },
      isPending: false,
      isError: false,
    } as unknown as ReturnType<typeof queries.useProject>,
  );
  vi.mocked(queries.useTasks).mockReturnValue(
    { data: { data: [] }, isPending: false, isError: false } as unknown as ReturnType<
      typeof queries.useTasks
    >,
  );
  vi.mocked(queries.useProjects).mockReturnValue(
    { data: { data: [] }, isPending: false } as unknown as ReturnType<typeof queries.useProjects>,
  );
  vi.mocked(mutations.useUpdateProject).mockReturnValue(
    { mutate: vi.fn(), isPending: false } as unknown as ReturnType<typeof mutations.useUpdateProject>,
  );
});

describe("ProjectDetailView — the project_id filter (task 033 phase 10a)", () => {
  it("requests its member tasks with the project_id filter and the 200-row page size, not the unfiltered global page or the 50-row default", () => {
    renderDetail();
    expect(queries.useTasks).toHaveBeenCalledWith({
      project_id: PROJECT_ID,
      page_size: 200,
    });
    // Never called with no filter — that would be the pre-10a client-side
    // filter over the global 50-row page, the exact bug this phase fixes.
    expect(queries.useTasks).not.toHaveBeenCalledWith();
    expect(queries.useTasks).not.toHaveBeenCalledWith({});
    // Never called with the filter alone, either — that would fall back to
    // the server's 50-row default and silently truncate a 51+-task project.
    expect(queries.useTasks).not.toHaveBeenCalledWith({ project_id: PROJECT_ID });
  });
});

describe("ProjectsView — the tasks-overview page size (task 033 phase 10a)", () => {
  it("raises the global tasks page beyond the 50-row default, since ProjectOut carries no last-task-updated field to use instead", () => {
    renderList();
    expect(queries.useTasks).toHaveBeenCalledWith({ page_size: 200 });
  });
});

describe("ProjectsView — the Organisation/Mine switcher (task 033 phase 10b)", () => {
  it("rubric 14 dark launch: hides the switcher when /me has no organisation", () => {
    renderList();
    expect(screen.queryByRole("tablist", { name: "Scope" })).not.toBeInTheDocument();
    // The 200-row page size is a deliberate fix shared by every caller,
    // enrolled or not — it is not part of the dark-launch invariant. What
    // rubric 14 actually pins is that an unenrolled caller's call carries no
    // org affordance at all: no `scope` param, enrolled or not.
    expect(queries.useTasks).toHaveBeenCalledWith({ page_size: 200 });
    expect(queries.useTasks).not.toHaveBeenCalledWith(
      expect.objectContaining({ scope: expect.anything() }),
    );
  });

  it("shows the switcher when enrolled, defaulting to Organisation, and drives scope", async () => {
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
    renderList();
    expect(queries.useProjects).toHaveBeenCalledWith({ scope: "all" });
    expect(queries.useTasks).toHaveBeenCalledWith({ page_size: 200, scope: "all" });

    await user.click(screen.getByRole("tab", { name: "Mine" }));
    expect(queries.useProjects).toHaveBeenCalledWith({ scope: "mine" });
    expect(queries.useTasks).toHaveBeenCalledWith({ page_size: 200, scope: "mine" });
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
    renderList();
    expect(screen.getByText("Showing every organisation.")).toBeInTheDocument();
  });

  it("does not show the admin notice for a non-admin, even with the switcher visible", () => {
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
    renderList();
    expect(screen.queryByText("Showing every organisation.")).not.toBeInTheDocument();
  });

  it("renders a null owner_display as 'No organisation' on the admin wide list", () => {
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
        data: {
          data: [
            {
              project_id: "orphan-1",
              name: "Orphan task",
              description: null,
              created_at: "2026-01-01T00:00:00Z",
              task_count: 0,
              visibility: "org",
              is_owner: false,
              owner_display: null,
            },
          ],
        },
        isPending: false,
      } as unknown as ReturnType<typeof queries.useProjects>,
    );
    renderList();
    expect(screen.getByText("No organisation")).toBeInTheDocument();
  });
});

describe("ProjectDetailView — the visibility-outcome copy (task 033 phase 10b)", () => {
  it("renders the singular cascade line when exactly one Task follows", async () => {
    const mutate = vi.fn((_body, options: { onSuccess: (data: unknown) => void }) => {
      options.onSuccess({ task_count: 1 });
    });
    vi.mocked(mutations.useUpdateProject).mockReturnValue(
      { mutate, isPending: false } as unknown as ReturnType<typeof mutations.useUpdateProject>,
    );
    const user = userEvent.setup();
    renderDetail();
    await user.click(screen.getByRole("button", { name: "Make private" }));
    expect(await screen.findByText("Now private. 1 Task follows.")).toBeInTheDocument();
  });

  it("renders the plural cascade line when more than one Task follows", async () => {
    const mutate = vi.fn((_body, options: { onSuccess: (data: unknown) => void }) => {
      options.onSuccess({ task_count: 3 });
    });
    vi.mocked(mutations.useUpdateProject).mockReturnValue(
      { mutate, isPending: false } as unknown as ReturnType<typeof mutations.useUpdateProject>,
    );
    const user = userEvent.setup();
    renderDetail();
    await user.click(screen.getByRole("button", { name: "Make private" }));
    expect(await screen.findByText("Now private. 3 Tasks follow.")).toBeInTheDocument();
  });

  it("hides the visibility control for a non-owner", () => {
    vi.mocked(queries.useProject).mockReturnValue(
      {
        data: {
          project_id: PROJECT_ID,
          name: "Housing",
          description: null,
          visibility: "org",
          is_owner: false,
          owner_display: "A Colleague",
          task_count: 0,
        },
        isPending: false,
        isError: false,
      } as unknown as ReturnType<typeof queries.useProject>,
    );
    renderDetail();
    expect(screen.queryByRole("button", { name: "Make private" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Share with organisation" })).not.toBeInTheDocument();
  });
});
