import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as mutations from "../api/mutations";
import * as queries from "../api/queries";
import { NewTaskView } from "./NewTaskView";

vi.mock("../api/queries", () => ({
  useProjects: vi.fn(),
  useTasks: vi.fn(),
}));

vi.mock("../api/mutations", () => ({
  useCreateTask: vi.fn(),
  useCreateProject: vi.fn(),
}));

const mutate = vi.fn();
const createProject = vi.fn();

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
  createProject.mockReset();
  vi.mocked(mutations.useCreateProject).mockReturnValue(
    { mutate: createProject, isPending: false, isError: false } as unknown as ReturnType<
      typeof mutations.useCreateProject
    >,
  );
  vi.mocked(mutations.useCreateTask).mockReturnValue(
    { mutate, isPending: false, isError: false } as unknown as ReturnType<
      typeof mutations.useCreateTask
    >,
  );
  vi.mocked(queries.useProjects).mockReturnValue(
    { data: { data: [] } } as unknown as ReturnType<typeof queries.useProjects>,
  );
  vi.mocked(queries.useTasks).mockReturnValue(
    { data: { data: [] } } as unknown as ReturnType<typeof queries.useTasks>,
  );
});

describe("NewTaskView — capability step", () => {
  it("lists all four capabilities", () => {
    renderNewTask();
    expect(screen.getByText("Evidence search")).toBeInTheDocument();
    expect(screen.getByText("Options scoping")).toBeInTheDocument();
    expect(screen.getByText("Theory of change")).toBeInTheDocument();
    expect(screen.getByText("Mapping stakeholders")).toBeInTheDocument();
  });

  it("renders the two unavailable capabilities as inert, not as buttons", () => {
    renderNewTask();
    for (const name of ["Theory of change", "Mapping stakeholders"]) {
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
    expect(screen.getByRole("combobox", { name: "Project" })).toHaveTextContent("Housing");
  });

  it("opens on the prompt with no eyebrow restating the page (owner, 2026-11-04)", () => {
    renderNewTask();
    expect(screen.queryByText("New task")).toBeNull();
    const heading = screen.getByRole("heading", { name: "What would you like to do?" });
    expect(heading).toBeInTheDocument();
    // The title is the page's first line: nothing sits above it in its column.
    expect(heading.previousElementSibling).toBeNull();
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
  // Owner, round 13: a reader with no project never saw the field.
  it.each(["evidence_search", "options_scoping"])(
    "shows the Project field on %s with no projects: None, then New project…",
    async (key) => {
      const user = userEvent.setup();
      renderNewTask(`/new?capability=${key}`);
      const project = screen.getByRole("combobox", { name: "Project" });
      expect(project).toHaveTextContent("None");
      await user.click(project);
      expect(screen.getAllByRole("option").map((option) => option.textContent)).toEqual(["None", "New project…"]);
    },
  );

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

    await user.click(screen.getByRole("combobox", { name: "Project" }));
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
    await user.click(screen.getByRole("combobox", { name: "Project" }));
    expect(screen.getByRole("option", { name: "A colleague's project" })).toBeInTheDocument();
  });

  // Task 044: the second selectable kind. Same form shape (question, project
  // and the search to start from), one create request, and the capability
  // travels in it.
  it("moves to the question step when Options scoping is picked", async () => {
    const user = userEvent.setup();
    renderNewTask();
    await user.click(screen.getByRole("button", { name: /Options scoping/ }));
    expect(
      screen.getByRole("heading", { name: "What are you trying to change?" }),
    ).toBeInTheDocument();
  });

  it.each([
    ["evidence_search", "What do you need evidence on?", "Evidence search"],
    ["options_scoping", "What are you trying to change?", "Options scoping"],
  ])("opens the %s question on its heading, with no capability line above it (owner, round 10)", (key, heading, name) => {
    renderNewTask(`/new?capability=${key}`);
    const title = screen.getByRole("heading", { name: heading });
    expect(title.previousElementSibling).toBeNull();
    expect(title).not.toHaveClass("mt-2");
    expect(screen.queryByText(name)).toBeNull();
  });

  it("reads 'Prepare plan' on the scoping form, not the ES's 'Start'", () => {
    renderNewTask("/new?capability=options_scoping");
    expect(screen.getByRole("button", { name: "Prepare plan" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start" })).not.toBeInTheDocument();
  });

  it("creates a scoping task with one request carrying its capability", async () => {
    const user = userEvent.setup();
    renderNewTask("/new?capability=options_scoping");
    await user.type(
      screen.getByLabelText("Your question"),
      "How do we cut the number of young people not in work or study?",
    );
    await user.click(screen.getByRole("button", { name: "Prepare plan" }));
    expect(mutate).toHaveBeenCalledTimes(1);
    expect(mutate.mock.calls[0][0]).toEqual({
      question: "How do we cut the number of young people not in work or study?",
      projectId: null,
      capability: "options_scoping",
      fromTaskIds: [],
    });
  });

  it("falls back to the picker for a capability that cannot be created", () => {
    renderNewTask("/new?capability=theory_of_change");
    expect(screen.getByText("Options scoping")).toBeInTheDocument();
    expect(screen.queryByLabelText("Your question")).not.toBeInTheDocument();
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
    expect(screen.getByRole("combobox", { name: "Project" })).toBeInTheDocument();
  });
});

// Owner, round 13 (item 6): user testing found "Starts from" unclear. Two
// plain optional fields replace it, each a label and one Body Grey sentence:
// "Project" on both capabilities, and on options scoping "Evidence search to
// start from", both the app's dropdown with "None" first and chosen.
describe("NewTaskView — the optional fields (round 13)", () => {
  const PROJECTS = [
    { project_id: "project-1", name: "Housing", description: null, created_at: "2026-01-01T00:00:00Z", task_count: 1, is_owner: true },
    { project_id: "project-2", name: "Child health", description: null, created_at: "2026-01-01T00:00:00Z", task_count: 1, is_owner: true },
  ];
  const done = { status: "succeeded" };
  const SEARCHES = [
    { task_id: "es-1", name: "Childhood obesity", capability: "evidence_search", project_ids: ["project-2"], latest_run: done },
    { task_id: "es-2", name: "Housing supply", capability: "evidence_search", project_ids: ["project-1"], latest_run: done },
    { task_id: "es-5", name: "Housing costs", capability: "evidence_search", project_ids: ["project-1"], latest_run: done },
    // Not offered: unfinished, in no project, or not an Evidence search.
    { task_id: "es-3", name: "Still running", capability: "evidence_search", project_ids: ["project-1"], latest_run: { status: "running" } },
    { task_id: "es-4", name: "In no project", capability: "evidence_search", project_ids: [], latest_run: done },
    { task_id: "os-1", name: "A scoping task", capability: "options_scoping", project_ids: ["project-1"], latest_run: done },
  ];
  const project = () => screen.getByRole("combobox", { name: "Project" });
  const check = (name: string) => screen.getByRole("checkbox", { name: new RegExp(`^${name}`) });

  beforeEach(() => {
    vi.mocked(queries.useProjects).mockReturnValue(
      { data: { data: PROJECTS } } as unknown as ReturnType<typeof queries.useProjects>,
    );
    vi.mocked(queries.useTasks).mockReturnValue(
      { data: { data: SEARCHES } } as unknown as ReturnType<typeof queries.useTasks>,
    );
  });

  it("gives the Evidence search the Project field alone, its sentence under the label and None chosen", () => {
    renderNewTask("/new?capability=evidence_search");
    expect(project()).toHaveTextContent("None");
    expect(screen.getByText("Add this task to a project. You can do this later too.")).toHaveClass("text-body", "text-grey");
    expect(screen.queryByRole("group", { name: "Evidence search to start from" })).not.toBeInTheDocument();
    expect(screen.queryByText(/Starts from/)).not.toBeInTheDocument();
  });

  it("gives options scoping a checklist of the finished searches in a project, none checked, 24 px under Project", () => {
    renderNewTask("/new?capability=options_scoping");
    const group = screen.getByRole("group", { name: "Evidence search to start from" });
    expect(group).toHaveClass("mt-6");
    expect(
      within(group).getByText(
        "Optional. An evidence search you have already run gives the scoping its sources and report; without one it searches for each option.",
      ),
    ).toHaveClass("text-body", "text-grey");
    const boxes = within(group).getAllByRole("checkbox");
    expect(boxes.map((box) => box.textContent)).toEqual([
      "Childhood obesityChild health",
      "Housing supplyHousing",
      "Housing costsHousing",
    ]);
    for (const box of boxes) expect(box).toHaveAttribute("aria-checked", "false");
    expect(screen.queryByText(/Starts from/)).not.toBeInTheDocument();
  });

  it("files the task in a checked search's project and disables the others, In another project", async () => {
    const user = userEvent.setup();
    renderNewTask("/new?capability=options_scoping");
    await user.click(check("Housing supply"));
    expect(check("Housing supply")).toHaveAttribute("aria-checked", "true");
    expect(project()).toHaveTextContent("Housing");
    expect(check("Childhood obesity")).toBeDisabled();
    expect(check("Childhood obesity")).toHaveTextContent("In another project");
    await user.click(check("Housing costs"));
    await user.type(screen.getByLabelText("Your question"), "How do we build more homes?");
    await user.click(screen.getByRole("button", { name: "Prepare plan" }));
    expect(mutate.mock.calls[0][0]).toEqual({
      question: "How do we build more homes?",
      projectId: "project-1",
      capability: "options_scoping",
      fromTaskIds: ["es-2", "es-5"],
    });
  });

  it("unchecks the searches a newly chosen project does not hold", async () => {
    const user = userEvent.setup();
    renderNewTask("/new?capability=options_scoping");
    await user.click(check("Childhood obesity"));
    await user.click(project());
    await user.click(screen.getByRole("option", { name: "Housing" }));
    expect(check("Childhood obesity")).toHaveAttribute("aria-checked", "false");
    expect(check("Childhood obesity")).toBeDisabled();
    await user.type(screen.getByLabelText("Your question"), "What would cut obesity?");
    await user.click(screen.getByRole("button", { name: "Prepare plan" }));
    expect(mutate.mock.calls[0][0]).toMatchObject({ projectId: "project-1", fromTaskIds: [] });
  });

  it("unchecks a search on a second press", async () => {
    const user = userEvent.setup();
    renderNewTask("/new?capability=options_scoping");
    await user.click(check("Housing supply"));
    await user.click(check("Housing supply"));
    expect(check("Housing supply")).toHaveAttribute("aria-checked", "false");
  });

  it("sends no project when None is chosen", async () => {
    const user = userEvent.setup();
    renderNewTask("/new?capability=evidence_search&project=project-1");
    await user.click(project());
    await user.click(screen.getByRole("option", { name: "None" }));
    await user.type(screen.getByLabelText("Your question"), "A question");
    await user.click(screen.getByRole("button", { name: "Start" }));
    expect(mutate.mock.calls[0][0]).toMatchObject({ projectId: null });
  });
});

describe("NewTaskView — New project… (round 13)", () => {
  const PROJECTS = [
    { project_id: "project-1", name: "Housing", description: null, created_at: "2026-01-01T00:00:00Z", task_count: 1, is_owner: true },
  ];
  const project = () => screen.getByRole("combobox", { name: "Project" });

  beforeEach(() => {
    vi.mocked(queries.useProjects).mockReturnValue(
      { data: { data: PROJECTS } } as unknown as ReturnType<typeof queries.useProjects>,
    );
  });

  it("lists None, the reader's projects, then New project…", async () => {
    const user = userEvent.setup();
    renderNewTask("/new?capability=evidence_search");
    await user.click(project());
    expect(screen.getAllByRole("option").map((option) => option.textContent)).toEqual([
      "None",
      "Housing",
      "New project…",
    ]);
  });

  it("opens a focused name field, creates the project, then the task in it", async () => {
    createProject.mockImplementation((_body: unknown, options: { onSuccess: (project: { project_id: string }) => void }) =>
      options.onSuccess({ project_id: "project-new" }),
    );
    const user = userEvent.setup();
    renderNewTask("/new?capability=options_scoping");
    await user.click(project());
    await user.click(screen.getByRole("option", { name: "New project…" }));
    const name = screen.getByRole("textbox", { name: "New project name" });
    expect(name).toHaveFocus();
    expect(name).toHaveClass("text-body");
    await user.type(name, "Coastal towns");
    await user.type(screen.getByLabelText("Your question"), "What would help coastal towns?");
    await user.click(screen.getByRole("button", { name: "Prepare plan" }));
    expect(createProject).toHaveBeenCalledWith({ name: "Coastal towns" }, expect.anything());
    expect(mutate).toHaveBeenCalledTimes(1);
    expect(mutate.mock.calls[0][0]).toEqual({
      question: "What would help coastal towns?",
      projectId: "project-new",
      capability: "options_scoping",
      fromTaskIds: [],
    });
  });

  it("creates no task when a named project cannot be made on Start, and says so", async () => {
    createProject.mockImplementation((_body: unknown, options: { onError: () => void }) => options.onError());
    const user = userEvent.setup();
    renderNewTask("/new?capability=evidence_search");
    await user.click(project());
    await user.click(screen.getByRole("option", { name: "New project…" }));
    await user.type(screen.getByRole("textbox", { name: "New project name" }), "Coastal towns");
    await user.type(screen.getByLabelText("Your question"), "A question");
    await user.click(screen.getByRole("button", { name: "Start" }));
    expect(mutate).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("The project couldn't be created. Try again.");
  });

  // Owner, round 13: typing a name did nothing until the task was made.
  // "Create" (or Enter) makes the project at once and chooses it.
  it("makes the project on Create and chooses it, closing the field; the task then goes in it", async () => {
    createProject.mockImplementation(
      (_body: unknown, options: { onSuccess: (project: { project_id: string; name: string }) => void }) =>
        options.onSuccess({ project_id: "project-new", name: "Coastal towns" }),
    );
    const user = userEvent.setup();
    renderNewTask("/new?capability=evidence_search");
    await user.click(project());
    await user.click(screen.getByRole("option", { name: "New project…" }));
    expect(screen.getByRole("button", { name: "Create" })).toBeDisabled();
    await user.type(screen.getByRole("textbox", { name: "New project name" }), "Coastal towns");
    await user.click(screen.getByRole("button", { name: "Create" }));
    expect(createProject).toHaveBeenCalledWith({ name: "Coastal towns" }, expect.anything());
    expect(screen.queryByRole("textbox", { name: "New project name" })).not.toBeInTheDocument();
    // Chosen at once, before the projects' refetch lists it.
    expect(project()).toHaveTextContent("Coastal towns");
    await waitFor(() => expect(project()).toHaveFocus());
    await user.type(screen.getByLabelText("Your question"), "A question");
    await user.click(screen.getByRole("button", { name: "Start" }));
    expect(createProject).toHaveBeenCalledTimes(1);
    expect(mutate.mock.calls[0][0]).toMatchObject({ projectId: "project-new" });
  });

  it("makes the project on Enter in the name, without starting the task", async () => {
    createProject.mockImplementation(
      (_body: unknown, options: { onSuccess: (project: { project_id: string; name: string }) => void }) =>
        options.onSuccess({ project_id: "project-new", name: "Coastal towns" }),
    );
    const user = userEvent.setup();
    renderNewTask("/new?capability=evidence_search");
    await user.type(screen.getByLabelText("Your question"), "A question");
    await user.click(project());
    await user.click(screen.getByRole("option", { name: "New project…" }));
    await user.type(screen.getByRole("textbox", { name: "New project name" }), "Coastal towns{Enter}");
    expect(createProject).toHaveBeenCalledTimes(1);
    expect(mutate).not.toHaveBeenCalled();
    expect(project()).toHaveTextContent("Coastal towns");
  });

  it("keeps the name and says so under the field when Create fails", async () => {
    createProject.mockImplementation((_body: unknown, options: { onError: () => void }) => options.onError());
    const user = userEvent.setup();
    renderNewTask("/new?capability=evidence_search");
    await user.click(project());
    await user.click(screen.getByRole("option", { name: "New project…" }));
    const name = screen.getByRole("textbox", { name: "New project name" });
    await user.type(name, "Coastal towns");
    await user.click(screen.getByRole("button", { name: "Create" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/^The project couldn't be created\. Try again\.$/);
    expect(name).toHaveValue("Coastal towns");
    expect(name).toHaveAttribute("aria-invalid", "true");
  });

  it("reads a blank name as None", async () => {
    const user = userEvent.setup();
    renderNewTask("/new?capability=evidence_search");
    await user.click(project());
    await user.click(screen.getByRole("option", { name: "New project…" }));
    await user.type(screen.getByLabelText("Your question"), "A question");
    await user.click(screen.getByRole("button", { name: "Start" }));
    expect(createProject).not.toHaveBeenCalled();
    expect(mutate.mock.calls[0][0]).toMatchObject({ projectId: null });
  });

  it("swaps the dropdown for the name, with Create and Cancel beside it; Cancel brings back None", async () => {
    const user = userEvent.setup();
    renderNewTask("/new?capability=evidence_search");
    await user.click(project());
    await user.click(screen.getByRole("option", { name: "New project…" }));
    expect(screen.queryByRole("combobox", { name: "Project" })).not.toBeInTheDocument();
    const name = screen.getByRole("textbox", { name: "New project name" });
    expect(name.parentElement).toContainElement(screen.getByRole("button", { name: "Create" }));
    expect(name.parentElement).toContainElement(screen.getByRole("button", { name: "Cancel" }));
    await user.type(name, "Coastal");
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("textbox", { name: "New project name" })).not.toBeInTheDocument();
    expect(project()).toHaveTextContent("None");
    expect(createProject).not.toHaveBeenCalled();
  });

  it("leaves the name field on Escape, back to None with focus on the dropdown", async () => {
    const user = userEvent.setup();
    renderNewTask("/new?capability=evidence_search");
    await user.click(project());
    await user.click(screen.getByRole("option", { name: "New project…" }));
    await user.type(screen.getByRole("textbox", { name: "New project name" }), "Coastal{Escape}");
    expect(screen.queryByRole("textbox", { name: "New project name" })).not.toBeInTheDocument();
    expect(project()).toHaveTextContent("None");
    await waitFor(() => expect(project()).toHaveFocus());
  });
});
