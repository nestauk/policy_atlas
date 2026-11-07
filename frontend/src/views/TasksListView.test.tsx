import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as queries from "../api/queries";
import { TasksListView } from "./TasksListView";

/*
 * The lists come from `useTasksPaged` (round 10). Each test sets one page per
 * query on `tasks` in the flat `{ data: { data, pagination } }` shape; the
 * mock hands it to the view as the infinite query's `{ pages: [page] }`, or
 * as several pages when the flat value carries `pages`.
 */
const { tasks } = vi.hoisted(() => ({ tasks: vi.fn() }));

type Flat = {
  data?: { data: unknown[]; pagination?: unknown };
  pages?: { data: unknown[]; pagination?: unknown }[];
  hasNextPage?: boolean;
  fetchNextPage?: () => void;
  isFetchingNextPage?: boolean;
  isFetchNextPageError?: boolean;
  [key: string]: unknown;
};

function asPaged(flat: Flat) {
  const pages = flat.pages ?? (flat.data !== undefined ? [flat.data] : undefined);
  return {
    ...flat,
    data: pages === undefined ? undefined : { pages },
    hasNextPage: flat.hasNextPage ?? false,
    fetchNextPage: flat.fetchNextPage ?? vi.fn(),
    isFetchingNextPage: flat.isFetchingNextPage ?? false,
    isFetchNextPageError: flat.isFetchNextPageError ?? false,
  };
}

// The rows' own menu (round 12) runs the task's rename and archive.
const taskMutations = vi.hoisted(() => ({ update: vi.fn(), archive: vi.fn(), createProject: vi.fn() }));
vi.mock("../api/mutations", () => ({
  useUpdateTask: vi.fn(() => ({ mutate: taskMutations.update, isPending: false })),
  useArchiveTask: vi.fn(() => ({ mutate: taskMutations.archive, isPending: false })),
  // The step's "New project…" (round 13).
  useCreateProject: vi.fn(() => ({ mutate: taskMutations.createProject, isPending: false })),
}));

vi.mock("../api/queries", () => ({
  useMe: vi.fn(),
  useProjects: vi.fn(),
  useTasksPaged: vi.fn((...args: unknown[]) => asPaged(tasks(...args) as Flat)),
}));

/** A fresh query cache per render, for the pages after the first. */
function withClient(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

const ROW = {
  task_id: "task-1",
  name: "Healthier childhoods",
  updated_at: "2026-07-21T09:00:00Z",
  latest_run: null,
  project_id: null,
  source_count: 4,
  is_owner: true,
  owner_display: "Ada Lovelace",
};

function renderView() {
  return render(
    withClient(
      <MemoryRouter>
        <TasksListView />
      </MemoryRouter>,
    ),
  );
}

beforeEach(() => {
  vi.mocked(queries.useProjects).mockReturnValue(
    { data: { data: [] } } as unknown as ReturnType<typeof queries.useProjects>,
  );
  tasks.mockReturnValue(
    {
      data: { data: [ROW] },
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as Flat,
  );
});

describe("TasksListView — the Organisation/Mine switcher (task 033 phase 10b, rubric 14 dark launch)", () => {
  it("hides the switcher, and asks for the list with no scope, when /me has no organisation", () => {
    vi.mocked(queries.useMe).mockReturnValue(
      { data: { user_id: "u1", display_name: "Ada Lovelace", organisation: null, is_admin: false } } as unknown as ReturnType<
        typeof queries.useMe
      >,
    );
    // Nothing archived; the Archived toggle is not a scope (round 11).
    tasks.mockImplementation(((query: Parameters<typeof queries.useTasksPaged>[0]) => ({
      data: { data: query?.status === "archived" ? [] : [ROW] },
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })) as unknown as (...args: unknown[]) => Flat);
    renderView();
    expect(screen.queryByRole("tablist", { name: "Scope" })).not.toBeInTheDocument();
    expect(queries.useTasksPaged).toHaveBeenCalledWith(undefined);
    // Byte-identical to today: no owner column either, even though the
    // row carries `owner_display` now.
    expect(screen.queryByText("Ada Lovelace")).not.toBeInTheDocument();
  });

  it("shows the switcher when enrolled, defaults to Mine, and drives scope on click", async () => {
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
    expect(queries.useTasksPaged).toHaveBeenCalledWith({ scope: "mine" });
    expect(screen.getByRole("tab", { name: "Mine" })).toHaveAttribute("aria-selected", "true");

    await user.click(screen.getByRole("tab", { name: "Organisation" }));
    expect(queries.useTasksPaged).toHaveBeenCalledWith({ scope: "all" }, { enabled: true });
    expect(screen.getByRole("tab", { name: "Organisation" })).toHaveAttribute("aria-selected", "true");
  });

  it("hides the owner column on Mine and shows it on Organisation, the reader's own rows as You (round 10, P6)", async () => {
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
    expect(screen.queryByText("Ada Lovelace")).not.toBeInTheDocument();
    expect(screen.queryByText("You")).not.toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Organisation" }));
    expect(screen.getByText("You")).toBeInTheDocument();
  });

  it("lays Organisation's rows on one grid with the owner track, Mine's without (round 12)", async () => {
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
    const list = () => screen.getByRole("list");
    expect(list()).toHaveClass("md:grid", "md:grid-cols-[minmax(0,1fr)_auto_auto_5.5rem_8.5rem]");
    await user.click(screen.getByRole("tab", { name: "Organisation" }));
    expect(list()).toHaveClass("md:grid", "md:grid-cols-[minmax(0,1fr)_auto_auto_auto_5.5rem_8.5rem]");
    const item = within(list()).getAllByRole("listitem")[0];
    expect(item).toHaveClass("md:grid-cols-subgrid", "md:col-span-full");
    expect(within(item).getByRole("link")).toHaveClass("md:grid-cols-subgrid", "md:col-span-full");
    // Capped and ellipsed; the reader's own "You" needs no hover text.
    expect(within(item).getByText("You")).toHaveClass("max-w-[8rem]", "truncate", "text-left");
    expect(within(item).getByText("You")).not.toHaveAttribute("title");
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
    renderView();
    // Mine is the default now; the wide list is behind the Organisation tab.
    await user.click(screen.getByRole("tab", { name: "Organisation" }));
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

  it("renders a null owner_display as 'No organisation' for the admin wide list", async () => {
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
    tasks.mockReturnValue(
      {
        data: { data: [{ ...ROW, task_id: "orphan-1", is_owner: false, owner_display: null }] },
        isPending: false,
        isError: false,
        refetch: vi.fn(),
      } as unknown as Flat,
    );
    const user = userEvent.setup();
    renderView();
    // Mine is the default now; the wide list is behind the Organisation tab.
    await user.click(screen.getByRole("tab", { name: "Organisation" }));
    expect(screen.getByText("No organisation")).toBeInTheDocument();
  });
});

const ENROLLED = {
  data: {
    user_id: "u1",
    display_name: "Ada Lovelace",
    organisation: { org_id: "org-1", name: "Dept" },
    is_admin: false,
  },
} as unknown as ReturnType<typeof queries.useMe>;
const SOLO = {
  data: { user_id: "u1", display_name: "Ada Lovelace", organisation: null, is_admin: false },
} as unknown as ReturnType<typeof queries.useMe>;

type TasksArg = Parameters<typeof queries.useTasksPaged>[0];

/** The lists answering per query: `own` for Mine (or unscoped), `org` for
 *  Organisation, `archived` and `orgArchived` for their archives. */
function tasksBy({
  own = [] as unknown[],
  archived = [] as unknown[],
  org = [] as unknown[],
  orgArchived = [] as unknown[],
}) {
  tasks.mockImplementation(((query: TasksArg) => {
    const rows =
      query?.status === "archived"
        ? query?.scope === "all"
          ? orgArchived
          : archived
        : query?.scope === "all"
          ? org
          : own;
    return { data: { data: rows }, isPending: false, isError: false, refetch: vi.fn() };
  }) as unknown as (...args: unknown[]) => Flat);
}

function renderRoutes() {
  return render(
    withClient(
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<TasksListView />} />
          <Route path="/new" element={<p>New task page</p>} />
        </Routes>
      </MemoryRouter>,
    ),
  );
}

// Task 058, lists polish (lead ruling): the first-run redirect to /new fires
// only when every list the caller can open is empty, not just Mine.
describe("TasksListView — the first-run redirect", () => {
  it("does not redirect an enrolled caller with no tasks of their own when Organisation has some", () => {
    vi.mocked(queries.useMe).mockReturnValue(ENROLLED);
    tasksBy({ org: [{ ...ROW, is_owner: false, owner_display: "Grace Hopper" }] });
    renderRoutes();
    expect(screen.queryByText("New task page")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Tasks" })).toBeInTheDocument();
    expect(queries.useTasksPaged).toHaveBeenCalledWith({ scope: "all" }, { enabled: true });
  });

  it("redirects an enrolled caller when Mine, their archive and Organisation are all empty", () => {
    vi.mocked(queries.useMe).mockReturnValue(ENROLLED);
    tasksBy({});
    renderRoutes();
    expect(screen.getByText("New task page")).toBeInTheDocument();
  });

  it("does not redirect when only archived tasks remain", () => {
    vi.mocked(queries.useMe).mockReturnValue(ENROLLED);
    tasksBy({ archived: [ROW] });
    renderRoutes();
    expect(screen.queryByText("New task page")).not.toBeInTheDocument();
  });

  it("does not redirect when Organisation is open and empty but Mine has tasks", async () => {
    vi.mocked(queries.useMe).mockReturnValue(ENROLLED);
    tasksBy({ own: [ROW] });
    const user = userEvent.setup();
    renderRoutes();
    await user.click(screen.getByRole("tab", { name: "Organisation" }));
    expect(screen.queryByText("New task page")).not.toBeInTheDocument();
    const empty = screen.getByRole("status");
    expect(empty).toHaveTextContent("No tasks yet");
    expect(empty).toHaveTextContent("Tasks you start appear here.");
  });

  it("redirects an unenrolled caller with no tasks, and never asks for the Organisation list", () => {
    vi.mocked(queries.useMe).mockReturnValue(SOLO);
    tasksBy({});
    vi.mocked(queries.useTasksPaged).mockClear();
    renderRoutes();
    expect(screen.getByText("New task page")).toBeInTheDocument();
    expect(queries.useTasksPaged).not.toHaveBeenCalledWith(
      expect.objectContaining({ scope: expect.anything() }),
      expect.anything(),
    );
    expect(queries.useTasksPaged).not.toHaveBeenCalledWith(expect.objectContaining({ scope: expect.anything() }));
  });

  it("waits for /me before deciding", () => {
    vi.mocked(queries.useMe).mockReturnValue(
      { data: undefined, isPending: true, isError: false } as unknown as ReturnType<typeof queries.useMe>,
    );
    tasksBy({});
    renderRoutes();
    expect(screen.queryByText("New task page")).not.toBeInTheDocument();
  });
});

// Task 058, lists polish: the shared header with fixed slots.
describe("TasksListView — the page header", () => {
  it("keeps the switcher in the filters row and marks the active scope with a blue rule, never a fill", () => {
    vi.mocked(queries.useMe).mockReturnValue(ENROLLED);
    const { container } = renderView();
    const filters = container.querySelector('[data-slot="filters"]') as HTMLElement;
    expect(filters).toContainElement(screen.getByRole("tablist", { name: "Scope" }));
    // The tab language's growing rule at 2 px (owner, round 10): full under
    // the active item, growing to the centre on hover and focus.
    const mine = screen.getByRole("tab", { name: "Mine" });
    expect(mine).toHaveClass("after:h-0.5", "after:bg-blue", "after:scale-x-100", "text-navy");
    expect(mine).not.toHaveClass("bg-blue");
    const organisation = screen.getByRole("tab", { name: "Organisation" });
    expect(organisation).toHaveClass(
      "after:scale-x-0",
      "after:origin-left",
      "hover:after:scale-x-50",
      "focus-visible:after:scale-x-50",
      "after:duration-200",
      "motion-reduce:after:transition-none",
      "font-semibold",
    );
    expect(organisation).not.toHaveClass("after:scale-x-100");
  });

  // Round 11 (owner): the header keeps only the primary; Find a task is a
  // magnifier at the right of the filters row, then the archived toggle.
  it("keeps only New task in the actions slot, and the Find a task magnifier in the filters row", () => {
    vi.mocked(queries.useMe).mockReturnValue(ENROLLED);
    const { container } = renderView();
    const actions = container.querySelector('[data-slot="actions"]') as HTMLElement;
    const filters = container.querySelector('[data-slot="filters"]') as HTMLElement;
    const find = screen.getByRole("button", { name: "Find a task" });
    const primary = screen.getByRole("link", { name: "New task" });
    expect(actions.children).toHaveLength(1);
    expect(actions.firstElementChild).toBe(primary);
    expect(primary).toHaveClass("h-13", "min-w-36");
    expect(filters).toContainElement(find);
    expect(screen.getByRole("tablist", { name: "Scope" })).not.toContainElement(find);
    expect(find).toHaveClass("size-10", "text-grey");
    // The filters row holds only the switcher and the magnifier.
    expect(filters).not.toContainElement(screen.getByRole("button", { name: "Show archived" }));
  });

  it("reserves the filters row for a caller without an organisation (lead ruling P5)", () => {
    vi.mocked(queries.useMe).mockReturnValue(SOLO);
    const { container } = renderView();
    expect(container.querySelector('[data-slot="filters"]')).toHaveClass("min-h-10");
  });

  it("shows the admin's wider-list note in the filters row, not above the list", async () => {
    vi.mocked(queries.useMe).mockReturnValue(
      {
        data: { ...ENROLLED.data, is_admin: true },
      } as unknown as ReturnType<typeof queries.useMe>,
    );
    const user = userEvent.setup();
    const { container } = renderView();
    await user.click(screen.getByRole("tab", { name: "Organisation" }));
    const filters = container.querySelector('[data-slot="filters"]') as HTMLElement;
    expect(filters).toContainElement(screen.getByText("Showing every organisation."));
  });

  it("loads into the list's own frame: five rows the list's height", () => {
    vi.mocked(queries.useMe).mockReturnValue(SOLO);
    tasks.mockReturnValue(
      { data: undefined, isPending: true, isError: false, refetch: vi.fn() } as unknown as Flat,
    );
    renderView();
    const skeleton = screen.getByRole("list", { name: "Loading tasks" });
    expect(skeleton).toHaveAttribute("aria-busy", "true");
    expect(skeleton).toHaveClass("border", "border-line-2", "bg-paper");
    const rows = skeleton.querySelectorAll("li");
    expect(rows).toHaveLength(5);
    for (const row of rows) expect(row).toHaveClass("h-14", "max-md:h-21");
  });
});

// Lead ruling, 2026-11-05: an enrolled caller whose Mine list is empty opens
// on Organisation when colleagues have tasks, so those tasks are reachable.
describe("TasksListView — the scope it opens on", () => {
  const COLLEAGUE_ROW = { ...ROW, task_id: "task-2", name: "Colleague's task", is_owner: false, owner_display: "Grace Hopper" };

  it("opens on Organisation when Mine is empty and Organisation has tasks", () => {
    vi.mocked(queries.useMe).mockReturnValue(ENROLLED);
    tasksBy({ org: [COLLEAGUE_ROW] });
    renderRoutes();
    expect(screen.getByRole("tab", { name: "Organisation" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("link", { name: /Colleague's task/ })).toBeInTheDocument();
    expect(queries.useProjects).toHaveBeenCalledWith({ scope: "all" });
  });

  it("also opens on Organisation when the caller has only archived tasks of their own", () => {
    vi.mocked(queries.useMe).mockReturnValue(ENROLLED);
    tasksBy({ archived: [ROW], org: [COLLEAGUE_ROW] });
    renderRoutes();
    expect(screen.getByRole("tab", { name: "Organisation" })).toHaveAttribute("aria-selected", "true");
  });

  it("opens on Mine when the caller has tasks of their own, and does not ask for Organisation", () => {
    vi.mocked(queries.useMe).mockReturnValue(ENROLLED);
    tasksBy({ own: [ROW], org: [COLLEAGUE_ROW] });
    vi.mocked(queries.useTasksPaged).mockClear();
    renderRoutes();
    expect(screen.getByRole("tab", { name: "Mine" })).toHaveAttribute("aria-selected", "true");
    expect(queries.useTasksPaged).toHaveBeenCalledWith({ scope: "all" }, { enabled: false });
    expect(queries.useTasksPaged).not.toHaveBeenCalledWith({ scope: "all" }, { enabled: true });
  });

  it("keeps the caller's own pick: Mine stays open, empty, once they choose it", async () => {
    vi.mocked(queries.useMe).mockReturnValue(ENROLLED);
    tasksBy({ org: [COLLEAGUE_ROW] });
    const user = userEvent.setup();
    renderRoutes();
    await user.click(screen.getByRole("tab", { name: "Mine" }));
    expect(screen.getByRole("tab", { name: "Mine" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("status")).toHaveTextContent("No tasks yet");
  });

  it("holds the loading frame while Organisation is on its way, rather than flash an empty Mine", () => {
    vi.mocked(queries.useMe).mockReturnValue(ENROLLED);
    tasks.mockImplementation(((query: TasksArg) =>
      query?.scope === "all"
        ? { data: undefined, isPending: true, isError: false, refetch: vi.fn() }
        : { data: { data: [] }, isPending: false, isError: false, refetch: vi.fn() }) as unknown as (...args: unknown[]) => Flat);
    renderRoutes();
    expect(screen.getByRole("list", { name: "Loading tasks" })).toBeInTheDocument();
    expect(screen.queryByText("No tasks yet")).not.toBeInTheDocument();
  });
});

describe("TasksListView — a list that failed to load", () => {
  it("says so in the list's frame with a 40 px Retry that asks again", async () => {
    vi.mocked(queries.useMe).mockReturnValue(SOLO);
    const refetch = vi.fn();
    tasks.mockReturnValue(
      { data: undefined, isPending: false, isError: true, error: { code: "server_error" }, refetch } as unknown as Flat,
    );
    const user = userEvent.setup();
    renderView();
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Your tasks couldn't be loaded.");
    expect(alert).toHaveClass("border", "border-line-2", "bg-paper");
    const retry = screen.getByRole("button", { name: "Retry" });
    expect(retry).toHaveClass("h-10");
    await user.click(retry);
    expect(refetch).toHaveBeenCalled();
  });
});

// Round 11 (owner): Archived is not a scope. The switcher keeps Mine and
// Organisation; a quiet "Show archived" at the list's foot lists the
// archived tasks of the open scope under an "Archived" heading.
describe("TasksListView — the Archived toggle", () => {
  const ARCHIVED_ROW = { ...ROW, task_id: "task-9", name: "Old bus fares task", status: "archived" };
  const COLLEAGUE_ARCHIVED_ROW = {
    ...ROW,
    task_id: "task-8",
    name: "Retired school meals task",
    status: "archived",
    is_owner: false,
    owner_display: "Grace Hopper",
  };
  const toggle = () => screen.getByRole("button", { name: /^(Show|Hide) archived$/ });

  it("sits at the list's foot, not in the filters row, and the switcher keeps two scopes", () => {
    vi.mocked(queries.useMe).mockReturnValue(ENROLLED);
    tasksBy({ own: [ROW] });
    const { container } = renderRoutes();
    const filters = container.querySelector('[data-slot="filters"]') as HTMLElement;
    expect(filters).not.toContainElement(toggle());
    const list = screen.getByRole("list");
    expect(list.compareDocumentPosition(toggle()) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Archived" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("tab").map((tab) => tab.getAttribute("aria-selected"))).toHaveLength(2);
    expect(screen.queryByRole("tab", { name: "Archived" })).not.toBeInTheDocument();
    // The quiet control at Caption (owner, round 11): Grey words over the
    // Line 2 underline, never a button box.
    expect(toggle()).toHaveAccessibleName("Show archived");
    expect(toggle()).toHaveAccessibleName("Show archived");
    expect(toggle()).toHaveClass("text-caption", "text-grey", "underline", "decoration-line-2", "min-h-10");
    expect(toggle()).not.toHaveClass("border", "bg-blue");
  });

  it("on Mine, lists the reader's archived tasks and turns back to the active list", async () => {
    vi.mocked(queries.useMe).mockReturnValue(ENROLLED);
    tasksBy({ own: [ROW], archived: [ARCHIVED_ROW], orgArchived: [COLLEAGUE_ARCHIVED_ROW] });
    const user = userEvent.setup();
    renderRoutes();
    expect(screen.queryByText("Old bus fares task")).not.toBeInTheDocument();

    await user.click(toggle());
    expect(toggle()).toHaveAccessibleName("Hide archived");
    expect(toggle()).toHaveAccessibleName("Hide archived");
    expect(screen.getByRole("heading", { level: 2, name: "Archived" })).toHaveClass("text-meta");
    expect(screen.getByRole("tab", { name: "Mine" })).toHaveAttribute("aria-selected", "true");
    const row = screen.getByRole("link", { name: /^Old bus fares task · Archived/ });
    expect(within(row).getByText("Archived")).toBeInTheDocument();
    expect(screen.queryByText("Healthier childhoods")).not.toBeInTheDocument();
    expect(screen.queryByText("Retired school meals task")).not.toBeInTheDocument();
    // The reader's own list: no owner column.
    expect(within(row).queryByText("You")).not.toBeInTheDocument();
    expect(queries.useTasksPaged).toHaveBeenCalledWith({ scope: "mine", status: "archived" });

    await user.click(toggle());
    expect(toggle()).toHaveAccessibleName("Show archived");
    expect(screen.queryByRole("heading", { name: "Archived" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^Healthier childhoods/ })).toBeInTheDocument();
    expect(screen.queryByText("Old bus fares task")).not.toBeInTheDocument();
  });

  it("on Organisation, lists the organisation's archived tasks with the owner column, and keeps the toggle across scopes", async () => {
    vi.mocked(queries.useMe).mockReturnValue(ENROLLED);
    tasksBy({ own: [ROW], archived: [ARCHIVED_ROW], orgArchived: [ARCHIVED_ROW, COLLEAGUE_ARCHIVED_ROW] });
    const user = userEvent.setup();
    renderRoutes();
    await user.click(screen.getByRole("tab", { name: "Organisation" }));
    await user.click(toggle());
    expect(queries.useTasksPaged).toHaveBeenCalledWith(
      { scope: "all", status: "archived" },
      { enabled: true },
    );
    const colleague = screen.getByRole("link", { name: /^Retired school meals task · Archived/ });
    expect(within(colleague).getByText("Grace Hopper")).toBeInTheDocument();
    const own = screen.getByRole("link", { name: /^Old bus fares task · Archived/ });
    expect(within(own).getByText("You")).toBeInTheDocument();

    // Back to Mine with the toggle still on: the reader's archive alone.
    await user.click(screen.getByRole("tab", { name: "Mine" }));
    expect(toggle()).toHaveAccessibleName("Hide archived");
    expect(screen.getByRole("link", { name: /^Old bus fares task · Archived/ })).toBeInTheDocument();
    expect(screen.queryByText("Retired school meals task")).not.toBeInTheDocument();
  });

  it("does not ask for the organisation's archive until it is open", () => {
    vi.mocked(queries.useMe).mockReturnValue(ENROLLED);
    tasksBy({ own: [ROW] });
    vi.mocked(queries.useTasksPaged).mockClear();
    renderRoutes();
    expect(queries.useTasksPaged).not.toHaveBeenCalledWith(
      { scope: "all", status: "archived" },
      { enabled: true },
    );
  });

  it("says 'No archived tasks' when the open scope has none", async () => {
    vi.mocked(queries.useMe).mockReturnValue(ENROLLED);
    tasksBy({ own: [ROW], orgArchived: [COLLEAGUE_ARCHIVED_ROW] });
    const user = userEvent.setup();
    renderRoutes();
    await user.click(toggle());
    const empty = screen.getByRole("status");
    expect(empty).toHaveTextContent(/^No archived tasks$/);
    // The way back stays under the empty list.
    expect(toggle()).toHaveAccessibleName("Hide archived");
    // Organisation has one from a colleague.
    await user.click(screen.getByRole("tab", { name: "Organisation" }));
    expect(screen.getByRole("link", { name: /^Retired school meals task · Archived/ })).toBeInTheDocument();
  });

  it("gives a reader with no organisation the toggle without a switcher, and sends no scope", async () => {
    vi.mocked(queries.useMe).mockReturnValue(SOLO);
    tasksBy({ own: [ROW], archived: [ARCHIVED_ROW] });
    vi.mocked(queries.useTasksPaged).mockClear();
    const user = userEvent.setup();
    renderRoutes();
    expect(screen.queryByRole("tablist", { name: "Scope" })).not.toBeInTheDocument();
    await user.click(toggle());
    expect(screen.getByRole("link", { name: /^Old bus fares task · Archived/ })).toBeInTheDocument();
    expect(queries.useTasksPaged).toHaveBeenCalledWith({ status: "archived" });
    expect(queries.useTasksPaged).not.toHaveBeenCalledWith(expect.objectContaining({ scope: expect.anything() }));
  });
});

// Round 10: the list stops at the server's page (50); "Show more" at its
// foot asks for the next page of the same filters.
describe("TasksListView — Show more", () => {
  const page = (from: number, count: number) =>
    Array.from({ length: count }, (_, index) => ({
      ...ROW,
      task_id: `task-${from + index}`,
      name: `Task number ${from + index}`,
    }));

  it("shows no control when every task is listed", () => {
    vi.mocked(queries.useMe).mockReturnValue(SOLO);
    tasks.mockReturnValue({
      data: { data: [ROW], pagination: { page: 1, page_size: 50, total_items: 1 } },
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as Flat);
    renderView();
    expect(screen.queryByRole("button", { name: "Show more" })).not.toBeInTheDocument();
  });

  it("asks for the next page, appends it without repeats, moves focus to the first new row and goes once all are shown", async () => {
    vi.mocked(queries.useMe).mockReturnValue(SOLO);
    const fetchNextPage = vi.fn();
    const first = { data: page(1, 50), pagination: { page: 1, page_size: 50, total_items: 52, has_more: true } };
    tasks.mockImplementation(((query: TasksArg) =>
      query?.status === "archived"
        ? { data: { data: [] }, isPending: false, isError: false, refetch: vi.fn() }
        : { pages: [first], hasNextPage: true, fetchNextPage, isPending: false, isError: false, refetch: vi.fn() }) as unknown as (...args: unknown[]) => Flat);
    const user = userEvent.setup();
    const view = renderView();
    expect(screen.getAllByRole("listitem")).toHaveLength(50);
    const more = screen.getByRole("button", { name: "Show more" });
    expect(more).toHaveClass("h-10", "border-line-2");
    await user.click(more);
    expect(fetchNextPage).toHaveBeenCalledTimes(1);
    // The next page lands, repeating the last row of page 1 (a task moved
    // across the boundary), and the server says there is no more.
    const second = { data: page(50, 3), pagination: { page: 2, page_size: 50, total_items: 52, has_more: false } };
    tasks.mockImplementation(((query: TasksArg) =>
      query?.status === "archived"
        ? { data: { data: [] }, isPending: false, isError: false, refetch: vi.fn() }
        : { pages: [first, second], hasNextPage: false, fetchNextPage, isPending: false, isError: false, refetch: vi.fn() }) as unknown as (...args: unknown[]) => Flat);
    view.rerender(withClient(<MemoryRouter><TasksListView /></MemoryRouter>));
    expect(screen.getAllByRole("listitem")).toHaveLength(52);
    expect(screen.getAllByText("Task number 50")).toHaveLength(1);
    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByRole("link", { name: /^Task number 51 · / })),
    );
    expect(screen.queryByRole("button", { name: "Show more" })).not.toBeInTheDocument();
  });

  it("shares the foot row with Show archived, Show more first and Show archived at the right (round 11)", () => {
    vi.mocked(queries.useMe).mockReturnValue(SOLO);
    tasks.mockReturnValue({
      data: { data: page(1, 50), pagination: { page: 1, page_size: 50, total_items: 60, has_more: true } },
      hasNextPage: true,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as Flat);
    renderView();
    const more = screen.getByRole("button", { name: "Show more" });
    const archived = screen.getByRole("button", { name: "Show archived" });
    const row = more.parentElement as HTMLElement;
    expect(row).toContainElement(archived);
    expect(archived.parentElement).toHaveClass("ml-auto");
    expect(more.compareDocumentPosition(archived) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("holds the control, disabled, while the next page is on its way", () => {
    vi.mocked(queries.useMe).mockReturnValue(SOLO);
    tasks.mockReturnValue({
      data: { data: page(1, 50), pagination: { page: 1, page_size: 50, total_items: 60, has_more: true } },
      hasNextPage: true,
      isFetchingNextPage: true,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as Flat);
    renderView();
    expect(screen.getByRole("button", { name: "Show more" })).toBeDisabled();
  });

  it("keeps the rows and offers Retry at the foot when the next page fails", async () => {
    vi.mocked(queries.useMe).mockReturnValue(SOLO);
    const fetchNextPage = vi.fn();
    tasks.mockReturnValue({
      data: { data: page(1, 50), pagination: { page: 1, page_size: 50, total_items: 60, has_more: true } },
      hasNextPage: true,
      fetchNextPage,
      isPending: false,
      // TanStack sets isError on a failed next page too; the list stays.
      isError: true,
      isFetchNextPageError: true,
      error: { code: "server_error" },
      refetch: vi.fn(),
    } as unknown as Flat);
    const user = userEvent.setup();
    renderView();
    expect(screen.getAllByRole("listitem")).toHaveLength(50);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Your tasks couldn't be loaded.");
    await user.click(within(alert).getByRole("button", { name: "Retry" }));
    expect(fetchNextPage).toHaveBeenCalledTimes(1);
  });
});

// Owner, round 12: "There should be a way to delete or archive and rename
// tasks and projects on the tasks/project lists." Each owner's row has the
// headers' menu beside its link.
describe("TasksListView — the row's menu (round 12)", () => {
  const ENROLLED = {
    data: { user_id: "u1", display_name: "Ada Lovelace", organisation: { org_id: "org-1", name: "Dept" }, is_admin: false },
  } as unknown as ReturnType<typeof queries.useMe>;
  const COLLEAGUE_ROW = { ...ROW, task_id: "task-2", name: "Grace's task", is_owner: false, owner_display: "Grace Hopper" };

  beforeEach(() => {
    taskMutations.update.mockReset();
    taskMutations.archive.mockReset();
  });

  it("gives only the owner's rows the control, beside the link and never inside it", async () => {
    vi.mocked(queries.useMe).mockReturnValue(ENROLLED);
    tasks.mockReturnValue({ data: { data: [ROW, COLLEAGUE_ROW] }, isPending: false, isError: false, refetch: vi.fn() } as unknown as Flat);
    const user = userEvent.setup();
    renderView();
    await user.click(screen.getByRole("tab", { name: "Organisation" }));
    const control = screen.getByRole("button", { name: "Task settings: Healthier childhoods" });
    expect(control.closest("a")).toBeNull();
    expect(control.closest("li")).toContainElement(screen.getByRole("link", { name: /^Healthier childhoods/ }));
    expect(screen.queryByRole("button", { name: "Task settings: Grace's task" })).not.toBeInTheDocument();
    // Quiet until hovered or focused from md up; always there on a phone.
    expect(control).toHaveClass("h-10", "w-10", "text-grey", "md:opacity-0", "md:group-hover:opacity-100", "md:group-focus-within:opacity-100");
  });

  it("renames on the row with Save name and Cancel, then gives focus back to the control", async () => {
    vi.mocked(queries.useMe).mockReturnValue(ENROLLED);
    taskMutations.update.mockImplementation((_body: unknown, options: { onSuccess: () => void }) => options.onSuccess());
    const user = userEvent.setup();
    renderView();
    await user.click(screen.getByRole("button", { name: "Task settings: Healthier childhoods" }));
    await user.click(screen.getByRole("menuitem", { name: "Rename" }));
    const field = screen.getByRole("textbox", { name: "Task name" });
    expect(field).toHaveValue("Healthier childhoods");
    expect(field).toHaveFocus();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
    // The row is the field while it is edited: no link to follow.
    expect(screen.queryByRole("link", { name: /^Healthier childhoods/ })).not.toBeInTheDocument();
    await user.clear(field);
    await user.type(field, "Healthier childhoods in Hackney");
    await user.click(screen.getByRole("button", { name: "Save name" }));
    expect(taskMutations.update).toHaveBeenCalledWith({ name: "Healthier childhoods in Hackney" }, expect.anything());
    expect(screen.queryByRole("textbox", { name: "Task name" })).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: "Task settings: Healthier childhoods" })).toHaveFocus());
  });

  it("cancels a rename without saving", async () => {
    vi.mocked(queries.useMe).mockReturnValue(ENROLLED);
    const user = userEvent.setup();
    renderView();
    await user.click(screen.getByRole("button", { name: "Task settings: Healthier childhoods" }));
    await user.click(screen.getByRole("menuitem", { name: "Rename" }));
    await user.type(screen.getByRole("textbox", { name: "Task name" }), " 2");
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(taskMutations.update).not.toHaveBeenCalled();
    expect(screen.getByRole("link", { name: /^Healthier childhoods/ })).toBeInTheDocument();
  });

  it("archives after the confirm in words, and the row folds out of the list", async () => {
    vi.mocked(queries.useMe).mockReturnValue(ENROLLED);
    taskMutations.archive.mockImplementation((_body: unknown, options: { onSuccess: () => void }) => options.onSuccess());
    const user = userEvent.setup();
    renderView();
    await user.click(screen.getByRole("button", { name: "Task settings: Healthier childhoods" }));
    await user.click(screen.getByRole("menuitem", { name: "Archive" }));
    expect(screen.getByText("Archiving removes this task from your active tasks.")).toHaveFocus();
    expect(screen.getByRole("button", { name: "Keep it" })).toBeInTheDocument();
    expect(taskMutations.archive).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Archive" }));
    expect(taskMutations.archive).toHaveBeenCalledTimes(1);
    // It folds (height and opacity) where it stood, then leaves for good,
    // even though the list still holds it until the refetch lands.
    const fold = screen.getByRole("link", { name: /^Healthier childhoods/ }).closest("[data-leaving]");
    expect(fold).toHaveClass("grid-rows-[0fr]", "opacity-0", "duration-200");
    await waitFor(() => expect(screen.queryByRole("link", { name: /^Healthier childhoods/ })).not.toBeInTheDocument());
  });

  it("keeps the row on Keep it, and offers no Archive on an archived task", async () => {
    vi.mocked(queries.useMe).mockReturnValue(ENROLLED);
    const user = userEvent.setup();
    renderView();
    await user.click(screen.getByRole("button", { name: "Task settings: Healthier childhoods" }));
    await user.click(screen.getByRole("menuitem", { name: "Archive" }));
    await user.click(screen.getByRole("button", { name: "Keep it" }));
    expect(taskMutations.archive).not.toHaveBeenCalled();
    expect(screen.getByRole("link", { name: /^Healthier childhoods/ })).toBeInTheDocument();

    tasks.mockReturnValue({
      data: { data: [{ ...ROW, status: "archived" }] }, isPending: false, isError: false, refetch: vi.fn(),
    } as unknown as Flat);
    await user.click(screen.getByRole("button", { name: "Show archived" }));
    await user.click(screen.getByRole("button", { name: "Task settings: Healthier childhoods" }));
    expect(screen.getByRole("menuitem", { name: "Rename" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Archive" })).not.toBeInTheDocument();
  });
});

// Owner, round 12: the row's control is the three dots, not the headers'
// chevron, and a task row's menu adds the task to a project (the Share
// page's change, the header's same step).
describe("TasksListView — the row's menu: the dots and Add to project (round 12)", () => {
  const ENROLLED = {
    data: { user_id: "u1", display_name: "Ada Lovelace", organisation: { org_id: "org-1", name: "Dept" }, is_admin: false },
  } as unknown as ReturnType<typeof queries.useMe>;
  const projectsOf = (rows: { project_id: string; name: string }[]) =>
    ({ data: { data: rows } }) as unknown as ReturnType<typeof queries.useProjects>;

  beforeEach(() => {
    taskMutations.update.mockReset();
  });

  it("draws the three dots in the row's control", () => {
    vi.mocked(queries.useMe).mockReturnValue(ENROLLED);
    renderView();
    const control = screen.getByRole("button", { name: "Task settings: Healthier childhoods" });
    const dots = control.querySelector("svg path");
    expect(dots?.getAttribute("d")).toBe("M3.5 8h0M8 8h0M12.5 8h0");
  });

  it("adds the task to a project it is not in, through the app's dropdown, with Add and Cancel", async () => {
    vi.mocked(queries.useMe).mockReturnValue(ENROLLED);
    vi.mocked(queries.useProjects).mockReturnValue(
      projectsOf([
        { project_id: "p-1", name: "Child health" },
        { project_id: "p-2", name: "Net zero homes" },
      ]),
    );
    tasks.mockReturnValue({
      data: { data: [{ ...ROW, project_ids: ["p-1"] }] }, isPending: false, isError: false, refetch: vi.fn(),
    } as unknown as Flat);
    taskMutations.update.mockImplementation((_body: unknown, options: { onSuccess: () => void }) => options.onSuccess());
    const user = userEvent.setup();
    renderView();
    await user.click(screen.getByRole("button", { name: "Task settings: Healthier childhoods" }));
    await user.click(screen.getByRole("menuitem", { name: "Add to project" }));
    expect(screen.getByRole("button", { name: "Add" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
    await user.click(screen.getByRole("combobox", { name: "Add to a project" }));
    expect(screen.queryByRole("option", { name: "Child health" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("option", { name: "Net zero homes" }));
    await user.click(screen.getByRole("button", { name: "Add" }));
    expect(taskMutations.update).toHaveBeenCalledWith({ project_ids: ["p-1", "p-2"] }, expect.anything());
    await waitFor(() => expect(screen.getByRole("button", { name: "Task settings: Healthier childhoods" })).toHaveFocus());
  });

  it("says so in the step when the change is refused", async () => {
    vi.mocked(queries.useMe).mockReturnValue(ENROLLED);
    vi.mocked(queries.useProjects).mockReturnValue(projectsOf([{ project_id: "p-2", name: "Net zero homes" }]));
    taskMutations.update.mockImplementation((_body: unknown, options: { onError: () => void }) => options.onError());
    const user = userEvent.setup();
    renderView();
    await user.click(screen.getByRole("button", { name: "Task settings: Healthier childhoods" }));
    await user.click(screen.getByRole("menuitem", { name: "Add to project" }));
    await user.click(screen.getByRole("combobox", { name: "Add to a project" }));
    await user.click(screen.getByRole("option", { name: "Net zero homes" }));
    await user.click(screen.getByRole("button", { name: "Add" }));
    expect(screen.getByRole("alert")).toHaveTextContent("The projects couldn't be changed. Try again.");
  });

  // Round 13: never disabled; a task in every project still has New project….
  it("offers New project… when the task is in every project, and adds the task to the one it makes", async () => {
    vi.mocked(queries.useMe).mockReturnValue(ENROLLED);
    vi.mocked(queries.useProjects).mockReturnValue(projectsOf([{ project_id: "p-1", name: "Child health" }]));
    tasks.mockReturnValue({
      data: { data: [{ ...ROW, project_ids: ["p-1"] }] }, isPending: false, isError: false, refetch: vi.fn(),
    } as unknown as Flat);
    taskMutations.createProject.mockImplementation(
      (_body: unknown, options: { onSuccess: (project: { project_id: string; name: string }) => void }) =>
        options.onSuccess({ project_id: "p-new", name: "Coastal towns" }),
    );
    taskMutations.update.mockImplementation((_body: unknown, options: { onSuccess: () => void }) => options.onSuccess());
    const user = userEvent.setup();
    renderView();
    await user.click(screen.getByRole("button", { name: "Task settings: Healthier childhoods" }));
    const item = screen.getByRole("menuitem", { name: "Add to project" });
    expect(item).toBeEnabled();
    await user.click(item);
    await user.click(screen.getByRole("combobox", { name: "Add to a project" }));
    expect(screen.getAllByRole("option").map((option) => option.textContent)).toEqual(["New project…"]);
    await user.click(screen.getByRole("option", { name: "New project…" }));
    await user.type(screen.getByRole("textbox", { name: "New project name" }), "Coastal towns");
    await user.click(screen.getByRole("button", { name: "Create" }));
    expect(taskMutations.createProject).toHaveBeenCalledWith({ name: "Coastal towns" }, expect.anything());
    expect(screen.getByRole("combobox", { name: "Add to a project" })).toHaveTextContent("Coastal towns");
    await user.click(screen.getByRole("button", { name: "Add" }));
    expect(taskMutations.update).toHaveBeenCalledWith({ project_ids: ["p-1", "p-new"] }, expect.anything());
  });
});
