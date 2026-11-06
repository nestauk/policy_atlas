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
    // Nothing archived, so no Archived entry either (round 10).
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

/** The lists answering per query: `own` for Mine (or unscoped), `org` for Organisation. */
function tasksBy({ own = [] as unknown[], archived = [] as unknown[], org = [] as unknown[] }) {
  tasks.mockImplementation(((query: TasksArg) => {
    const rows =
      query?.status === "archived" ? archived : query?.scope === "all" ? org : own;
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

  it("puts Find a task and New task in the actions slot: 40 px ghost, then the 52 px primary", () => {
    vi.mocked(queries.useMe).mockReturnValue(SOLO);
    const { container } = renderView();
    const actions = container.querySelector('[data-slot="actions"]') as HTMLElement;
    const find = screen.getByRole("button", { name: "Find a task" });
    const primary = screen.getByRole("link", { name: "New task" });
    expect(actions).toContainElement(find);
    expect(actions).toContainElement(primary);
    expect(find).toHaveClass("h-10", "text-body", "font-semibold");
    expect(primary).toHaveClass("h-13", "min-w-36");
    // The primary is last: rightmost in the cluster.
    expect(actions.lastElementChild).toBe(primary);
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

// Round 10: the reader's archived tasks, behind an Archived entry in the
// filters row that shows only while there are some.
describe("TasksListView — Archived", () => {
  const ARCHIVED_ROW = { ...ROW, task_id: "task-9", name: "Old bus fares task", status: "archived" };

  it("offers Archived when the reader has archived tasks, and lists them with the status word Archived", async () => {
    vi.mocked(queries.useMe).mockReturnValue(ENROLLED);
    tasksBy({ own: [ROW], archived: [ARCHIVED_ROW] });
    const user = userEvent.setup();
    renderRoutes();
    expect(screen.queryByText("Old bus fares task")).not.toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Archived" }));
    expect(screen.getByRole("tab", { name: "Archived" })).toHaveAttribute("aria-selected", "true");
    const row = screen.getByRole("link", { name: /^Old bus fares task · Archived/ });
    expect(within(row).getByText("Archived")).toBeInTheDocument();
    expect(screen.queryByText("Healthier childhoods")).not.toBeInTheDocument();
    // The reader's own list: no owner column.
    expect(within(row).queryByText("You")).not.toBeInTheDocument();
    expect(queries.useTasksPaged).toHaveBeenCalledWith({ scope: "mine", status: "archived" });
  });

  it("does not offer Archived when nothing is archived", () => {
    vi.mocked(queries.useMe).mockReturnValue(ENROLLED);
    tasksBy({ own: [ROW] });
    renderRoutes();
    expect(screen.queryByRole("tab", { name: "Archived" })).not.toBeInTheDocument();
  });

  it("gives a reader with no organisation Mine and Archived, and sends no scope", async () => {
    vi.mocked(queries.useMe).mockReturnValue(SOLO);
    tasksBy({ own: [ROW], archived: [ARCHIVED_ROW] });
    const user = userEvent.setup();
    renderRoutes();
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual(["MineMine", "ArchivedArchived"]);
    await user.click(screen.getByRole("tab", { name: "Archived" }));
    expect(screen.getByRole("link", { name: /^Old bus fares task · Archived/ })).toBeInTheDocument();
    expect(queries.useTasksPaged).toHaveBeenCalledWith({ status: "archived" });
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
