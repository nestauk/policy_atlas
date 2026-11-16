import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as mutations from "../api/mutations";
import * as queries from "../api/queries";
import { ToastProvider } from "../ui/radix/Toast";
import { ProjectDetailView, ProjectsView } from "./ProjectsView";

vi.mock("../api/queries", async (importOriginal) => ({
  queryKeys: (await importOriginal<typeof import("../api/queries")>()).queryKeys,
  useMe: vi.fn(),
  useProject: vi.fn(),
  useProjects: vi.fn(),
  // The Projects list is paged (round 12).
  useProjectsPaged: vi.fn(),
  useTasks: vi.fn(),
  // A project's own list is paged (round 10).
  useTasksPaged: vi.fn(),
}));

/** One page as the infinite query's result. */
function pagedResult(rows: unknown[], extra: Record<string, unknown> = {}) {
  return {
    data: { pages: [{ data: rows, pagination: { page: 1, page_size: 200, total_items: rows.length, has_more: false } }] },
    isPending: false,
    isError: false,
    isFetchNextPageError: false,
    hasNextPage: false,
    isFetchingNextPage: false,
    fetchNextPage: vi.fn(),
    refetch: vi.fn(),
    ...extra,
  } as unknown as ReturnType<typeof queries.useTasksPaged>;
}

/** The Projects list's pages as the infinite query's result (round 12). */
function projectPages(rows: unknown[], extra: Record<string, unknown> = {}) {
  return pagedResult(rows, extra) as unknown as ReturnType<typeof queries.useProjectsPaged>;
}

vi.mock("../api/mutations", () => ({
  useCreateProject: vi.fn(),
  useUpdateProject: vi.fn(),
  // The project page's title menu (round 11, the workspace builder's).
  useArchiveProject: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  // A project's task rows carry their own menu (round 12).
  useUpdateTask: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useArchiveTask: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
}));

const PROJECT_ID = "project-1";

function renderDetail(projectId = PROJECT_ID, client = new QueryClient()) {
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/projects/${projectId}`]}>
          <Routes>
            <Route path="/projects/:projectId" element={<ProjectDetailView />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
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
  vi.mocked(queries.useTasksPaged).mockReturnValue(pagedResult([]));
  vi.mocked(queries.useProjects).mockReturnValue(
    { data: { data: [] }, isPending: false } as unknown as ReturnType<typeof queries.useProjects>,
  );
  vi.mocked(queries.useProjectsPaged).mockReturnValue(projectPages([]));
  vi.mocked(mutations.useUpdateProject).mockReturnValue(
    { mutate: vi.fn(), isPending: false } as unknown as ReturnType<typeof mutations.useUpdateProject>,
  );
});

describe("ProjectDetailView — the project_id filter (task 033 phase 10a)", () => {
  it("requests its member tasks with the project_id filter and the 200-row page size, not the unfiltered global page or the 50-row default", () => {
    renderDetail();
    expect(queries.useTasksPaged).toHaveBeenCalledWith({
      project_id: PROJECT_ID,
      page_size: 200,
    });
    // Never called with no filter — that would be the pre-10a client-side
    // filter over the global 50-row page, the exact bug this phase fixes.
    expect(queries.useTasksPaged).not.toHaveBeenCalledWith();
    expect(queries.useTasksPaged).not.toHaveBeenCalledWith({});
    // Never called with the filter alone, either — that would fall back to
    // the server's 50-row default and silently truncate a 51+-task project.
    expect(queries.useTasksPaged).not.toHaveBeenCalledWith({ project_id: PROJECT_ID });
  });
});

// Round 12: the server orders the projects by `last_activity_at` and sends it
// on every row, so the page asks for no task list of its own, keeps the
// server's order (a "Show more" page lands below) and dates each row by it.
describe("ProjectsView — the server's last activity (round 12)", () => {
  it("asks for no task list, keeps the server's order and dates rows by last_activity_at", () => {
    vi.mocked(queries.useProjectsPaged).mockReturnValue(
      projectPages([
        { ...PROJECT_ROW, project_id: "p-a", name: "Older by creation", created_at: "2025-01-01T00:00:00Z", last_activity_at: "2026-03-04T10:00:00Z" },
        { ...PROJECT_ROW, project_id: "p-b", name: "Newer by creation", created_at: "2026-02-01T00:00:00Z", last_activity_at: "2026-02-01T00:00:00Z" },
      ]),
    );
    renderList();
    expect(queries.useTasks).not.toHaveBeenCalled();
    const links = screen.getAllByRole("link");
    expect(links.map((link) => link.textContent)).toEqual([
      expect.stringContaining("Older by creation"),
      expect.stringContaining("Newer by creation"),
    ]);
    expect(links[0].querySelector("time")).toHaveAttribute("dateTime", "2026-03-04T10:00:00Z");
  });
});

describe("ProjectsView — the Organisation/Mine switcher (task 033 phase 10b)", () => {
  it("rubric 14 dark launch: hides the switcher when /me has no organisation", () => {
    renderList();
    expect(screen.queryByRole("tablist", { name: "Scope" })).not.toBeInTheDocument();
    // Rubric 14: an unenrolled caller's list carries no org affordance at
    // all, so no `scope` param.
    expect(queries.useProjectsPaged).toHaveBeenCalledWith(undefined);
  });

  it("shows the switcher when enrolled, defaulting to Mine, and drives scope", async () => {
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
    expect(queries.useProjectsPaged).toHaveBeenCalledWith({ scope: "mine" });
    expect(screen.getByRole("tab", { name: "Mine" })).toHaveAttribute("aria-selected", "true");

    await user.click(screen.getByRole("tab", { name: "Organisation" }));
    expect(queries.useProjectsPaged).toHaveBeenCalledWith({ scope: "all" });
  });

  it("shows the admin wider-list notice only for admin + Organisation scope", async () => {
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
    const user = userEvent.setup();
    renderList();
    // Mine is the default now; the wide list is behind the Organisation tab.
    await user.click(screen.getByRole("tab", { name: "Organisation" }));
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

  it("renders a null owner_display as 'No organisation' on the admin wide list", async () => {
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
    vi.mocked(queries.useProjectsPaged).mockReturnValue(
      projectPages([
            {
              project_id: "orphan-1",
              name: "Orphan task",
              description: null,
              created_at: "2026-01-01T00:00:00Z",
              last_activity_at: "2026-01-01T00:00:00Z",
              task_count: 0,
              visibility: "org",
              is_owner: false,
              owner_display: null,
            },
      ]),
    );
    const user = userEvent.setup();
    renderList();
    // Mine is the default now; the wide list is behind the Organisation tab.
    await user.click(screen.getByRole("tab", { name: "Organisation" }));
    expect(screen.getByText("No organisation")).toBeInTheDocument();
  });
});

// Round 11 (owner): projects can be archived; the Projects page takes the
// Tasks page's Archived toggle, listing the archived projects of the open
// scope through the list's `status` parameter.
describe("ProjectsView — the Archived toggle", () => {
  const ENROLLED_ME = {
    data: {
      user_id: "u1",
      display_name: "Ada Lovelace",
      organisation: { org_id: "org-1", name: "Dept" },
      is_admin: false,
    },
  } as unknown as ReturnType<typeof queries.useMe>;
  const toggle = () => screen.getByRole("button", { name: /^(Show|Hide) archived$/ });

  it("sits at the list's foot, off by default, with the queries as before", () => {
    vi.mocked(queries.useMe).mockReturnValue(ENROLLED_ME);
    const { container } = renderList();
    const filters = container.querySelector('[data-slot="filters"]') as HTMLElement;
    expect(filters).not.toContainElement(toggle());
    expect(toggle()).toHaveClass("text-caption");
    expect(screen.queryByRole("heading", { name: "Archived" })).not.toBeInTheDocument();
    expect(toggle()).toHaveAccessibleName("Show archived");
    expect(queries.useProjectsPaged).toHaveBeenCalledWith({ scope: "mine" });
    expect(queries.useProjectsPaged).not.toHaveBeenCalledWith(expect.objectContaining({ status: expect.anything() }));
  });

  it("asks for the archived projects of the open scope, and keeps the toggle across scopes", async () => {
    vi.mocked(queries.useMe).mockReturnValue(ENROLLED_ME);
    const user = userEvent.setup();
    renderList();
    await user.click(toggle());
    expect(toggle()).toHaveAccessibleName("Hide archived");
    expect(toggle()).toHaveAccessibleName("Hide archived");
    expect(screen.getByRole("heading", { level: 2, name: "Archived" })).toBeInTheDocument();
    expect(queries.useProjectsPaged).toHaveBeenCalledWith({ scope: "mine", status: "archived" });
    await user.click(screen.getByRole("tab", { name: "Organisation" }));
    expect(toggle()).toHaveAccessibleName("Hide archived");
    expect(queries.useProjectsPaged).toHaveBeenCalledWith({ scope: "all", status: "archived" });
    await user.click(toggle());
    expect(queries.useProjectsPaged).toHaveBeenLastCalledWith({ scope: "all" });
  });

  it("says 'No archived projects' when the open scope has none", async () => {
    const user = userEvent.setup();
    renderList();
    await user.click(toggle());
    expect(screen.getByRole("status")).toHaveTextContent(/^No archived projects$/);
  });

  it("gives a reader with no organisation the toggle without a scope", async () => {
    vi.mocked(queries.useProjectsPaged).mockClear();
    const user = userEvent.setup();
    renderList();
    expect(queries.useProjectsPaged).toHaveBeenCalledWith(undefined);
    await user.click(toggle());
    expect(queries.useProjectsPaged).toHaveBeenCalledWith({ status: "archived" });
    expect(queries.useProjectsPaged).not.toHaveBeenCalledWith(expect.objectContaining({ scope: expect.anything() }));
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

const PROJECT_ROW = {
  project_id: "p-1",
  name: "Child health, Tower Hamlets",
  description: null,
  created_at: "2026-01-01T00:00:00Z",
  last_activity_at: "2026-01-01T00:00:00Z",
  task_count: 3,
  visibility: "org",
  is_owner: true,
  owner_display: "Ada Lovelace",
};

// Task 058, lists polish: the shared header, the list's own frame for
// loading and empty, and one row recipe with the Tasks page.
describe("ProjectsView — the page header and list (lists polish)", () => {
  it("keeps New project in its slot, disabled, while the form is open", async () => {
    vi.mocked(mutations.useCreateProject).mockReturnValue(
      { mutate: vi.fn(), isPending: false, isError: false } as unknown as ReturnType<
        typeof mutations.useCreateProject
      >,
    );
    const user = userEvent.setup();
    const { container } = renderList();
    const primary = screen.getByRole("button", { name: "New project" });
    expect(primary).toHaveClass("h-13", "min-w-36");
    await user.click(primary);
    expect(screen.getByRole("button", { name: "New project" })).toBeDisabled();
    expect(container.querySelector('[data-slot="actions"]')).toContainElement(
      screen.getByRole("button", { name: "New project" }),
    );
    expect(screen.getByLabelText("Project name")).toBeInTheDocument();
  });

  // Round 13: the form is the shared name field with Create and Cancel.
  it("makes the project from the shared name field on Create or Enter, and closes the form", async () => {
    const mutate = vi.fn(
      (_body: unknown, options: { onSuccess: (project: { project_id: string; name: string }) => void }) =>
        options.onSuccess({ project_id: "p-new", name: "Coastal towns" }),
    );
    vi.mocked(mutations.useCreateProject).mockReturnValue(
      { mutate, isPending: false } as unknown as ReturnType<typeof mutations.useCreateProject>,
    );
    const user = userEvent.setup();
    renderList();
    await user.click(screen.getByRole("button", { name: "New project" }));
    const field = screen.getByRole("textbox", { name: "Project name" });
    expect(field).toHaveFocus();
    expect(screen.getByRole("button", { name: "Create" })).toBeDisabled();
    await user.type(field, "Coastal towns{Enter}");
    expect(mutate).toHaveBeenCalledWith({ name: "Coastal towns" }, expect.anything());
    expect(screen.queryByRole("textbox", { name: "Project name" })).not.toBeInTheDocument();
  });

  it("keeps the name and says so when the project cannot be made; Cancel closes the form", async () => {
    const mutate = vi.fn((_body: unknown, options: { onError: () => void }) => options.onError());
    vi.mocked(mutations.useCreateProject).mockReturnValue(
      { mutate, isPending: false } as unknown as ReturnType<typeof mutations.useCreateProject>,
    );
    const user = userEvent.setup();
    renderList();
    await user.click(screen.getByRole("button", { name: "New project" }));
    await user.type(screen.getByRole("textbox", { name: "Project name" }), "Coastal towns");
    await user.click(screen.getByRole("button", { name: "Create" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/^The project couldn't be created\. Try again\.$/);
    expect(screen.getByRole("textbox", { name: "Project name" })).toHaveValue("Coastal towns");
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("textbox", { name: "Project name" })).not.toBeInTheDocument();
  });

  // Round 11 (owner): the header keeps only the primary; Find a project is
  // the magnifier at the right of the filters row, before the archived toggle.
  it("keeps only New project in the header and puts the Find a project magnifier in the filters row", () => {
    const { container } = renderList();
    const actions = container.querySelector('[data-slot="actions"]') as HTMLElement;
    const filters = container.querySelector('[data-slot="filters"]') as HTMLElement;
    const find = screen.getByRole("button", { name: "Find a project" });
    expect(actions.children).toHaveLength(1);
    expect(actions.firstElementChild).toBe(screen.getByRole("button", { name: "New project" }));
    expect(filters).toContainElement(find);
    expect(find).toHaveClass("size-10", "text-grey", "hover:text-navy");
    expect(find.querySelector("svg")).not.toBeNull();
    expect(filters).not.toContainElement(screen.getByRole("button", { name: "Show archived" }));
  });

  it("shows an empty list in the list's frame, left-aligned, without the card shadow", () => {
    renderList();
    const empty = screen.getByRole("status");
    expect(empty).toHaveTextContent("No projects yet");
    expect(empty).toHaveTextContent("A project groups related tasks under one name.");
    expect(empty).toHaveClass("border", "border-line-2", "bg-paper");
    expect(empty.className).not.toMatch(/shadow|mx-auto|text-center/);
  });

  it("loads into the list's own frame", () => {
    vi.mocked(queries.useProjectsPaged).mockReturnValue(projectPages([], { data: undefined, isPending: true }));
    renderList();
    const skeleton = screen.getByRole("list", { name: "Loading projects" });
    expect(skeleton.querySelectorAll("li")).toHaveLength(5);
  });

  it("lays project rows on the task rows' tail: owner, count, date in fixed columns", async () => {
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
    vi.mocked(queries.useProjectsPaged).mockReturnValue(projectPages([PROJECT_ROW]));
    const user = userEvent.setup();
    renderList();
    // Mine: the reader's own list, no owner column (round 10, P6).
    expect(screen.getByRole("link", { name: /Child health, Tower Hamlets/ })).toHaveClass(
      "grid",
      "min-h-14",
      "grid-cols-[minmax(0,1fr)_5.5rem_5.5rem]",
    );
    expect(screen.queryByText("You")).not.toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Organisation" }));
    const row = screen.getByRole("link", { name: /Child health, Tower Hamlets/ });
    expect(row).toHaveClass("grid", "min-h-14", "grid-cols-[minmax(0,1fr)_8rem_5.5rem_5.5rem]");
    // Its content in order, one separator (round 10, ruling 1).
    expect(row).toHaveAccessibleName(/^Child health, Tower Hamlets · You · 3 tasks · 1 Jan( 2026)?$/);
    // Two fixed lines on phones: the name truncates on line 1, never wraps.
    expect(screen.getByText("Child health, Tower Hamlets")).toHaveClass("truncate", "max-md:col-span-2");
    // The owner drops on phones (lead ruling P3); the reader's own row says You.
    expect(screen.getByText("You")).toHaveClass("max-md:hidden");
    // Digits in tabular figures, the words and spaces at their normal width.
    expect(screen.getByText("3").parentElement).toHaveTextContent("3 tasks");
    expect(screen.getByText("3").parentElement).toHaveClass("text-right", "text-meta");
    expect(screen.getByText("3")).toHaveClass("tabular-nums");
    // The date at Meta, in the one list form.
    expect(row.querySelector("time")).toHaveClass("text-meta");
    expect(row.querySelector("time")).not.toHaveClass("text-caption");
  });
});

describe("ProjectDetailView — the page header and list (lists polish)", () => {
  it("shows an empty project's list as the list's frame with a label and one sentence (lead ruling P1)", () => {
    renderDetail();
    const empty = screen.getByRole("status");
    expect(empty).toHaveTextContent("No tasks yet");
    expect(empty).toHaveTextContent("Tasks you start here join this project.");
  });

  it("keeps the title's line box and the header's slots while the project loads", () => {
    vi.mocked(queries.useProject).mockReturnValue(
      { data: undefined, isPending: true, isError: false } as unknown as ReturnType<typeof queries.useProject>,
    );
    const { container } = renderDetail();
    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toBeEmptyDOMElement();
    expect(heading).toHaveClass("min-h-[1lh]");
    // The primary is already in its slot before the project lands.
    expect(container.querySelector('[data-slot="actions"]')).toContainElement(
      screen.getByRole("link", { name: "New task" }),
    );
    expect(screen.getByRole("list", { name: "Loading tasks" })).toBeInTheDocument();
  });

  it("keeps only New task in a project's header, the Find a task magnifier in its filters row", () => {
    const { container } = renderDetail();
    const actions = container.querySelector('[data-slot="actions"]') as HTMLElement;
    expect(actions.children).toHaveLength(1);
    expect(actions.firstElementChild).toBe(screen.getByRole("link", { name: "New task" }));
    expect(container.querySelector('[data-slot="filters"]')).toContainElement(
      screen.getByRole("button", { name: "Find a task" }),
    );
  });

  it("puts the way back in the context row, and Make private in the filters row at 40 px", () => {
    const { container } = renderDetail();
    const back = screen.getByRole("link", { name: "← Projects" });
    expect(container.querySelector('[data-slot="context"]')).toContainElement(back);
    const makePrivate = screen.getByRole("button", { name: "Make private" });
    expect(container.querySelector('[data-slot="filters"]')).toContainElement(makePrivate);
    expect(makePrivate).toHaveClass("h-10", "text-body");
  });

  it("shows the description in the filters row", () => {
    vi.mocked(queries.useProject).mockReturnValue(
      {
        data: {
          project_id: PROJECT_ID,
          name: "Housing",
          description: "Supply and affordability.",
          visibility: "org",
          is_owner: true,
          owner_display: "Ada Lovelace",
          task_count: 0,
        },
        isPending: false,
        isError: false,
      } as unknown as ReturnType<typeof queries.useProject>,
    );
    const { container } = renderDetail();
    expect(container.querySelector('[data-slot="filters"]')).toHaveTextContent("Supply and affordability.");
  });
});

describe("ProjectDetailView — arriving from the Projects list (lists polish)", () => {
  it("draws the whole header from the list's cached row while the project's own request is on its way", () => {
    vi.mocked(queries.useProject).mockReturnValue(
      { data: undefined, isPending: true, isError: false } as unknown as ReturnType<typeof queries.useProject>,
    );
    const client = new QueryClient();
    client.setQueryData(["projects", "list", { scope: "mine" }], {
      data: [
        {
          project_id: PROJECT_ID,
          name: "Housing",
          description: "Supply and affordability.",
          created_at: "2026-01-01T00:00:00Z",
          last_activity_at: "2026-01-01T00:00:00Z",
          task_count: 2,
          visibility: "org",
          is_owner: true,
          owner_display: "Ada Lovelace",
        },
      ],
    });
    renderDetail(PROJECT_ID, client);
    expect(screen.getByRole("heading", { level: 1, name: "Housing" })).toBeInTheDocument();
    expect(screen.getByText("Supply and affordability.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Make private" })).toBeInTheDocument();
  });

  it("ignores a cached row for another project", () => {
    vi.mocked(queries.useProject).mockReturnValue(
      { data: undefined, isPending: true, isError: false } as unknown as ReturnType<typeof queries.useProject>,
    );
    const client = new QueryClient();
    client.setQueryData(["projects", "list", undefined], {
      data: [{ project_id: "other", name: "Elsewhere", description: null, visibility: "org", is_owner: true }],
    });
    renderDetail(PROJECT_ID, client);
    expect(screen.getByRole("heading", { level: 1 })).toBeEmptyDOMElement();
  });
});

describe("ProjectsView — a list that failed to load (lead ruling, 2026-11-05)", () => {
  it("says so in the list's frame with a 40 px ghost Try again that refetches", async () => {
    const refetch = vi.fn();
    vi.mocked(queries.useProjectsPaged).mockReturnValue(
      projectPages([], { data: undefined, isPending: false, isError: true, refetch }),
    );
    const user = userEvent.setup();
    renderList();
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Couldn't load your projects.");
    expect(alert).toHaveClass("border", "border-line-2", "bg-paper");
    const again = screen.getByRole("button", { name: "Try again" });
    expect(again).toHaveClass("h-10", "text-meta");
    await user.click(again);
    expect(refetch).toHaveBeenCalled();
  });
});

// Round 10 (lead ruling): a project past the 200-row page gets the same
// "Show more" as the Tasks page, asking for the next page of its members.
describe("ProjectDetailView — Show more", () => {
  it("asks for the next page of the project's tasks", async () => {
    const member = (index: number) => ({
      task_id: `task-${index}`,
      name: `Member task ${index}`,
      updated_at: "2026-07-21T09:00:00Z",
      latest_run: null,
      project_ids: [PROJECT_ID],
      is_owner: true,
      owner_display: "Ada Lovelace",
    });
    const fetchNextPage = vi.fn();
    vi.mocked(queries.useTasksPaged).mockReturnValue(
      pagedResult(
        Array.from({ length: 200 }, (_, index) => member(index)),
        { hasNextPage: true, fetchNextPage },
      ),
    );
    const user = userEvent.setup();
    renderDetail();
    expect(screen.getAllByRole("listitem")).toHaveLength(200);
    await user.click(screen.getByRole("button", { name: "Show more" }));
    expect(fetchNextPage).toHaveBeenCalledTimes(1);
  });
});

// Round 12 (lead): the Projects list pages at 20 like the Tasks list, with
// the same "Show more" at the foot's left and the archived toggle at its right.
describe("ProjectsView — Show more", () => {
  const project = (index: number) => ({
    ...PROJECT_ROW,
    project_id: `p-${index}`,
    name: `Project ${index}`,
  });

  it("asks for the next page of the open list, beside the archived toggle", async () => {
    const fetchNextPage = vi.fn();
    vi.mocked(queries.useProjectsPaged).mockReturnValue(
      projectPages(Array.from({ length: 20 }, (_, index) => project(index)), { hasNextPage: true, fetchNextPage }),
    );
    const user = userEvent.setup();
    renderList();
    expect(screen.getAllByRole("listitem")).toHaveLength(20);
    const showMore = screen.getByRole("button", { name: "Show more" });
    // One foot row: Show more first, then the toggle.
    expect(showMore.parentElement).toContainElement(screen.getByRole("button", { name: "Show archived" }));
    await user.click(showMore);
    expect(fetchNextPage).toHaveBeenCalledTimes(1);
  });

  it("has no Show more when the server holds nothing more, and keeps the toggle", () => {
    vi.mocked(queries.useProjectsPaged).mockReturnValue(projectPages([project(1)]));
    renderList();
    expect(screen.queryByRole("button", { name: "Show more" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Show archived" })).toBeInTheDocument();
  });

  it("holds Show more disabled while the next page is on its way", () => {
    vi.mocked(queries.useProjectsPaged).mockReturnValue(
      projectPages([project(1)], { hasNextPage: true, isFetchingNextPage: true }),
    );
    renderList();
    expect(screen.getByRole("button", { name: "Show more" })).toBeDisabled();
  });

  it("drops a project listed twice across two pages", () => {
    vi.mocked(queries.useProjectsPaged).mockReturnValue({
      ...projectPages([]),
      data: {
        pages: [
          { data: [project(1), project(2)], pagination: { page: 1, page_size: 2, total_items: 3, has_more: true } },
          { data: [project(2), project(3)], pagination: { page: 2, page_size: 2, total_items: 3, has_more: false } },
        ],
      },
    } as unknown as ReturnType<typeof queries.useProjectsPaged>);
    renderList();
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
  });

  it("keeps the rows and offers Retry under them when a later page fails", async () => {
    const fetchNextPage = vi.fn();
    vi.mocked(queries.useProjectsPaged).mockReturnValue(
      projectPages([project(1)], {
        isError: true,
        isFetchNextPageError: true,
        hasNextPage: true,
        fetchNextPage,
      }),
    );
    const user = userEvent.setup();
    renderList();
    expect(screen.getByRole("link", { name: /Project 1/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Show more" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(fetchNextPage).toHaveBeenCalledTimes(1);
  });
});

// Round 12: a project opened from the paged list has its name on the first
// frame, read from the list's pages in the cache.
describe("ProjectDetailView — the name from the paged list", () => {
  it("reads the project from the Projects list's pages while its own request runs", () => {
    vi.mocked(queries.useProject).mockReturnValue(
      { data: undefined, isPending: true, isError: false } as unknown as ReturnType<typeof queries.useProject>,
    );
    const client = new QueryClient();
    client.setQueryData(queries.queryKeys.projectsPaged({ scope: "mine" }), {
      pages: [{ data: [{ ...PROJECT_ROW, project_id: PROJECT_ID, name: "Housing from the list" }] }],
      pageParams: [1],
    });
    renderDetail(PROJECT_ID, client);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Housing from the list");
  });
});

// Owner, round 12: rename and archive from the Projects list. Each owner's
// row has the project page's menu beside its link.
describe("ProjectsView — the row's menu (round 12)", () => {
  const COLLEAGUE = { ...PROJECT_ROW, project_id: "p-2", name: "Grace's project", is_owner: false, owner_display: "Grace Hopper" };
  const settings = () => screen.getByRole("button", { name: "Project settings: Child health, Tower Hamlets" });

  it("gives only the owner's rows the control, beside the link and never inside it", () => {
    vi.mocked(queries.useProjectsPaged).mockReturnValue(projectPages([PROJECT_ROW, COLLEAGUE]));
    renderList();
    expect(settings().closest("a")).toBeNull();
    expect(settings().closest("li")).toContainElement(screen.getByRole("link", { name: /^Child health, Tower Hamlets/ }));
    expect(screen.queryByRole("button", { name: "Project settings: Grace's project" })).not.toBeInTheDocument();
  });

  it("renames on the row with Save name and Cancel", async () => {
    const mutate = vi.fn((_body: unknown, options: { onSuccess: () => void }) => options.onSuccess());
    vi.mocked(mutations.useUpdateProject).mockReturnValue(
      { mutate, isPending: false } as unknown as ReturnType<typeof mutations.useUpdateProject>,
    );
    vi.mocked(queries.useProjectsPaged).mockReturnValue(projectPages([PROJECT_ROW]));
    const user = userEvent.setup();
    renderList();
    await user.click(settings());
    await user.click(screen.getByRole("menuitem", { name: "Rename" }));
    const field = screen.getByRole("textbox", { name: "Project name" });
    expect(field).toHaveValue("Child health, Tower Hamlets");
    expect(screen.queryByRole("link", { name: /^Child health, Tower Hamlets/ })).not.toBeInTheDocument();
    await user.clear(field);
    await user.type(field, "Child health, Hackney{Enter}");
    expect(mutate).toHaveBeenCalledWith({ name: "Child health, Hackney" }, expect.anything());
    await waitFor(() => expect(settings()).toHaveFocus());
  });

  it("archives after the confirm in words, and the row folds out of the list", async () => {
    const mutate = vi.fn((_body: unknown, options: { onSuccess: () => void }) => options.onSuccess());
    vi.mocked(mutations.useArchiveProject).mockReturnValue(
      { mutate, isPending: false } as unknown as ReturnType<typeof mutations.useArchiveProject>,
    );
    vi.mocked(queries.useProjectsPaged).mockReturnValue(projectPages([{ ...PROJECT_ROW, solo_task_count: 1 }]));
    const user = userEvent.setup();
    renderList();
    await user.click(settings());
    await user.click(screen.getByRole("menuitem", { name: "Archive" }));
    // Round 14: the row's count of tasks in no other project.
    expect(
      screen.getByText(
        "Archiving removes this project from your active projects and archives its 1 task that is in no other project.",
      ),
    ).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "Archive" }));
    expect(mutate).toHaveBeenCalledTimes(1);
    const fold = screen.getByRole("link", { name: /^Child health, Tower Hamlets/ }).closest("[data-leaving]");
    expect(fold).toHaveClass("grid-rows-[0fr]", "opacity-0");
    await waitFor(() =>
      expect(screen.queryByRole("link", { name: /^Child health, Tower Hamlets/ })).not.toBeInTheDocument(),
    );
  });

  it("says so in the menu when the archive fails, and keeps the row", async () => {
    const mutate = vi.fn((_body: unknown, options: { onError: () => void }) => options.onError());
    vi.mocked(mutations.useArchiveProject).mockReturnValue(
      { mutate, isPending: false } as unknown as ReturnType<typeof mutations.useArchiveProject>,
    );
    vi.mocked(queries.useProjectsPaged).mockReturnValue(projectPages([PROJECT_ROW]));
    const user = userEvent.setup();
    renderList();
    await user.click(settings());
    await user.click(screen.getByRole("menuitem", { name: "Archive" }));
    await user.click(screen.getByRole("button", { name: "Archive" }));
    expect(screen.getByRole("alert")).toHaveTextContent("The project couldn't be archived. Try again.");
    expect(screen.getByRole("link", { name: /^Child health, Tower Hamlets/ })).toBeInTheDocument();
  });

  it("draws the three dots, and offers no Add to project on a project row", async () => {
    vi.mocked(queries.useProjectsPaged).mockReturnValue(projectPages([PROJECT_ROW]));
    const user = userEvent.setup();
    renderList();
    expect(settings().querySelector("svg path")?.getAttribute("d")).toBe("M3.5 8h0M8 8h0M12.5 8h0");
    await user.click(settings());
    expect(screen.getByRole("menuitem", { name: "Rename" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: /Add to project/ })).not.toBeInTheDocument();
  });

  it("offers Rename only on an archived project", async () => {
    vi.mocked(queries.useProjectsPaged).mockReturnValue(
      projectPages([{ ...PROJECT_ROW, archived_at: "2026-11-01T00:00:00Z" }]),
    );
    const user = userEvent.setup();
    renderList();
    await user.click(settings());
    expect(screen.getByRole("menuitem", { name: "Rename" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Archive" })).not.toBeInTheDocument();
  });
});

// Round 12: "Add to project" is a task's; the project page's own menu has
// Rename and Archive only.
describe("ProjectDetailView — the title's menu (round 12)", () => {
  it("offers no Add to project", async () => {
    const user = userEvent.setup();
    renderDetail();
    await user.click(screen.getByRole("button", { name: "Project settings" }));
    expect(screen.getByRole("menuitem", { name: "Rename" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: /Add to project/ })).not.toBeInTheDocument();
  });
});
