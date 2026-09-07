import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as mutations from "../api/mutations";
import * as queries from "../api/queries";
import { NewTaskView } from "./NewTaskView";

vi.mock("../api/queries", () => ({
  useProjects: vi.fn(),
}));

vi.mock("../api/mutations", () => ({
  useCreateTask: vi.fn(),
}));

const mutate = vi.fn();

function renderNewTask(initialPath = "/new") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/new" element={<NewTaskView />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  mutate.mockClear();
  vi.mocked(mutations.useCreateTask).mockReturnValue(
    { mutate, isPending: false, isError: false } as unknown as ReturnType<
      typeof mutations.useCreateTask
    >,
  );
  vi.mocked(queries.useProjects).mockReturnValue(
    { data: { data: [] } } as unknown as ReturnType<typeof queries.useProjects>,
  );
});

describe("NewTaskView — capability step", () => {
  it("lists all four capabilities", () => {
    renderNewTask();
    expect(screen.getByText("Evidence search")).toBeInTheDocument();
    expect(screen.getByText("Scoping policy options")).toBeInTheDocument();
    expect(screen.getByText("Theory of change")).toBeInTheDocument();
    expect(screen.getByText("Mapping stakeholders")).toBeInTheDocument();
  });

  it("renders the three unavailable capabilities as inert, not as buttons", () => {
    renderNewTask();
    for (const name of ["Scoping policy options", "Theory of change", "Mapping stakeholders"]) {
      const li = screen.getByText(name).closest("li");
      expect(li).not.toBeNull();
      expect(within(li!).getByText("Coming soon")).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: new RegExp(name) })).not.toBeInTheDocument();
    }
  });

  it("moves to the question step when Evidence search is picked", async () => {
    const user = userEvent.setup();
    renderNewTask();
    await user.click(screen.getByRole("button", { name: /Evidence search/ }));
    expect(
      screen.getByRole("heading", { name: "What do you need evidence on?" }),
    ).toBeInTheDocument();
  });

  it("keeps a project preset when opened from a project, and still starts on the capability picker", async () => {
    const user = userEvent.setup();
    vi.mocked(queries.useProjects).mockReturnValue(
      {
        data: {
          data: [
            {
              project_id: "project-1",
              name: "Housing",
              description: null,
              created_at: "2026-01-01T00:00:00Z",
              task_count: 0,
              is_owner: true,
            },
          ],
        },
      } as unknown as ReturnType<typeof queries.useProjects>,
    );
    renderNewTask("/new?project=project-1");
    expect(
      screen.getByRole("heading", { name: "What would you like to do?" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Evidence search/ }));
    expect(screen.getByLabelText(/Add to a project/)).toHaveTextContent("Housing");
  });

  it("shows the capability-picker eyebrow and prompt", () => {
    renderNewTask();
    expect(screen.getByText("New task")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "What would you like to do?" }),
    ).toBeInTheDocument();
  });
});

describe("NewTaskView — question step", () => {
  it("disables Send while the box is empty and enables it once text is typed", async () => {
    const user = userEvent.setup();
    renderNewTask("/new?capability=evidence_search");
    const send = screen.getByRole("button", { name: "Start" });
    expect(send).toBeDisabled();
    await user.type(screen.getByLabelText("Your question"), "Hello");
    expect(send).toBeEnabled();
  });

  it("submits on Enter but not on Shift+Enter", async () => {
    const user = userEvent.setup();
    renderNewTask("/new?capability=evidence_search");
    const textarea = screen.getByLabelText("Your question");
    await user.type(textarea, "What works for X?");

    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: true });
    expect(mutate).not.toHaveBeenCalled();

    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });
    expect(mutate).toHaveBeenCalledOnce();
    expect(mutate.mock.calls[0][0]).toMatchObject({
      question: "What works for X?",
      projectId: null,
    });
  });

  it("states the Enter / Shift+Enter key hint", () => {
    renderNewTask("/new?capability=evidence_search");
    expect(screen.getByText(/Shift\+Enter/)).toBeInTheDocument();
  });
});

describe("NewTaskView — project selector", () => {
  it("has no project selector when there are no projects", () => {
    renderNewTask("/new?capability=evidence_search");
    expect(screen.queryByLabelText(/Add to a project/)).not.toBeInTheDocument();
  });

  it("offers the project selector when a project exists, and passes the choice to mutate", async () => {
    const user = userEvent.setup();
    vi.mocked(queries.useProjects).mockReturnValue(
      {
        data: {
          data: [
            {
              project_id: "project-1",
              name: "Housing",
              description: null,
              created_at: "2026-01-01T00:00:00Z",
              task_count: 0,
              is_owner: true,
            },
          ],
        },
      } as unknown as ReturnType<typeof queries.useProjects>,
    );
    renderNewTask("/new?capability=evidence_search");

    await user.click(screen.getByLabelText(/Add to a project/));
    await user.click(screen.getByRole("option", { name: "Housing" }));
    await user.type(screen.getByLabelText("Your question"), "A question");
    await user.click(screen.getByRole("button", { name: "Start" }));

    expect(mutate).toHaveBeenCalledOnce();
    expect(mutate.mock.calls[0][0]).toMatchObject({
      question: "A question",
      projectId: "project-1",
    });
  });

  it("offers a colleague-owned, org-visible project — colleague assignment (owner ruling 2026-08-27)", async () => {
    const user = userEvent.setup();
    vi.mocked(queries.useProjects).mockReturnValue(
      {
        data: {
          data: [
            {
              project_id: "project-1",
              name: "Housing",
              description: null,
              created_at: "2026-01-01T00:00:00Z",
              task_count: 0,
              is_owner: true,
            },
            {
              project_id: "project-2",
              name: "A colleague's project",
              description: null,
              created_at: "2026-01-01T00:00:00Z",
              task_count: 0,
              is_owner: false,
            },
          ],
        },
      } as unknown as ReturnType<typeof queries.useProjects>,
    );
    renderNewTask("/new?capability=evidence_search");
    await user.click(screen.getByLabelText(/Add to a project/));
    expect(screen.getByRole("option", { name: "A colleague's project" })).toBeInTheDocument();
  });

  it("keeps the project selector when every project is colleague-owned", () => {
    vi.mocked(queries.useProjects).mockReturnValue(
      {
        data: {
          data: [
            {
              project_id: "project-2",
              name: "A colleague's project",
              description: null,
              created_at: "2026-01-01T00:00:00Z",
              task_count: 0,
              is_owner: false,
            },
          ],
        },
      } as unknown as ReturnType<typeof queries.useProjects>,
    );
    renderNewTask("/new?capability=evidence_search");
    expect(screen.getByLabelText(/Add to a project/)).toBeInTheDocument();
  });
});
