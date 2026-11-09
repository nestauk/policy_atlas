import { render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { TooltipProvider } from "../ui/radix/Tooltip";
import { NameMenu, projectArchiveSentence, soloTaskCount, ProjectName } from "./NameMenu";

const projectMutations = vi.hoisted(() => ({
  rename: vi.fn(),
  archive: vi.fn((_: undefined, options: { onSuccess: () => void }) => options.onSuccess()),
}));

vi.mock("../api/mutations", () => ({
  useUpdateProject: () => ({ mutate: projectMutations.rename, isPending: false }),
  useArchiveProject: () => ({ mutate: projectMutations.archive, isPending: false }),
}));

type Done = { onSuccess: () => void; onError: () => void };

function menu(overrides: Partial<Parameters<typeof NameMenu>[0]> = {}) {
  const rename = vi.fn((_: string, done: Done) => done.onSuccess());
  const archive = vi.fn((_: void, done: Done) => done.onSuccess());
  render(
    <TooltipProvider>
      <NameMenu
        name="NEET in Tower Hamlets"
        label="Task settings"
        fieldLabel="Task name"
        titleClassName="text-title"
        below={<span>Options scoping</span>}
        canEdit
        rename={rename}
        renameError="The task couldn't be renamed. Try again."
        archive={archive}
        archiveSentence="Archiving removes this task from your active tasks."
        archiveError="The task couldn't be archived. Try again."
        {...overrides}
      />
    </TooltipProvider>,
  );
  return { rename, archive, user: userEvent.setup() };
}

// Owner, round 11: the header's name and its menu, shared by a task and a project.
describe("NameMenu", () => {
  it("shows the name with a 40 px chevron control on its baseline, and the short line under it (round 12)", () => {
    menu();
    const name = screen.getByText("NEET in Tower Hamlets");
    const chevron = screen.getByRole("button", { name: "Task settings" });
    expect(chevron).toHaveClass("h-10", "w-10", "self-baseline");
    // The chevron shares the name's line; the capability is on its own line under them.
    // The name sits in its own box (round 14: it changes smoothly), on the
    // chevron's line.
    const line = name.parentElement?.parentElement as HTMLElement;
    expect(chevron.parentElement).toBe(line);
    expect(line).toHaveClass("items-baseline");
    const capability = screen.getByText("Options scoping");
    expect(capability.parentElement).not.toBe(line);
    expect(line.nextElementSibling).toBe(capability);
  });

  it("keeps the short line under the field while renaming", async () => {
    const { user } = menu();
    await user.click(screen.getByRole("button", { name: "Task settings" }));
    await user.click(screen.getByRole("menuitem", { name: "Rename" }));
    expect(screen.getByRole("textbox", { name: "Task name" })).toBeInTheDocument();
    expect(screen.getByText("Options scoping")).toBeInTheDocument();
  });

  it("shows a colleague the name alone", () => {
    menu({ canEdit: false });
    expect(screen.queryByRole("button", { name: "Task settings" })).toBeNull();
  });

  it("opens a menu with focus on its first item and moves with the arrow keys", async () => {
    const { user } = menu();
    await user.click(screen.getByRole("button", { name: "Task settings" }));
    expect(screen.getByRole("menuitem", { name: "Rename" })).toHaveFocus();
    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("menuitem", { name: "Archive" })).toHaveFocus();
  });

  it("renames in place with Save and Cancel, then gives focus back to the chevron", async () => {
    const { user, rename } = menu();
    await user.click(screen.getByRole("button", { name: "Task settings" }));
    await user.click(screen.getByRole("menuitem", { name: "Rename" }));
    const field = screen.getByRole("textbox", { name: "Task name" });
    expect(field).toHaveFocus();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
    await user.clear(field);
    await user.type(field, "NEET in East London{Enter}");
    expect(rename).toHaveBeenCalledWith("NEET in East London", expect.anything());
    expect(screen.queryByRole("textbox")).toBeNull();
    await vi.waitFor(() => expect(screen.getByRole("button", { name: "Task settings" })).toHaveFocus());
  });

  // Owner, round 13: the button reads "Save"; a screen reader hears "Save name".
  it("shows Save on the rename field's button, named Save name", async () => {
    const { user } = menu();
    await user.click(screen.getByRole("button", { name: "Task settings" }));
    await user.click(screen.getByRole("menuitem", { name: "Rename" }));
    const save = screen.getByRole("button", { name: "Save name" });
    expect(save).toHaveTextContent(/^Save$/);
  });

  it("cancels a rename on Escape and says so when a save fails", async () => {
    const { user } = menu({ rename: (_name: string, done: Done) => done.onError() });
    await user.click(screen.getByRole("button", { name: "Task settings" }));
    await user.click(screen.getByRole("menuitem", { name: "Rename" }));
    await user.type(screen.getByRole("textbox"), " 2");
    await user.click(screen.getByRole("button", { name: "Save name" }));
    expect(screen.getByRole("alert")).toHaveTextContent("The task couldn't be renamed. Try again.");
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.getByText("NEET in Tower Hamlets")).toBeInTheDocument();
  });

  it("archives only after a second step in words, its sentence taking focus", async () => {
    const { user, archive } = menu();
    await user.click(screen.getByRole("button", { name: "Task settings" }));
    await user.click(screen.getByRole("menuitem", { name: "Archive" }));
    expect(archive).not.toHaveBeenCalled();
    const group = screen.getByRole("group", { name: "Archiving removes this task from your active tasks." });
    expect(screen.getByText("Archiving removes this task from your active tasks.")).toHaveFocus();
    expect(group).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Archive" }));
    expect(archive).toHaveBeenCalledTimes(1);
  });

  it("goes back without archiving on Keep it", async () => {
    const { user, archive } = menu();
    await user.click(screen.getByRole("button", { name: "Task settings" }));
    await user.click(screen.getByRole("menuitem", { name: "Archive" }));
    await user.click(screen.getByRole("button", { name: "Keep it" }));
    expect(archive).not.toHaveBeenCalled();
    expect(screen.queryByRole("group")).toBeNull();
    await vi.waitFor(() => expect(screen.getByRole("button", { name: "Task settings" })).toHaveFocus());
  });

  it("offers no Archive when the thing cannot be archived from here", async () => {
    const { user } = menu({ archive: undefined });
    await user.click(screen.getByRole("button", { name: "Task settings" }));
    expect(screen.queryByRole("menuitem", { name: "Archive" })).toBeNull();
  });
});

// Owner, round 11: "add a way to archive (and rename) projects".
describe("ProjectName", () => {
  function page(archived = false) {
    render(
      <MemoryRouter initialEntries={["/projects/p1"]}>
        <Routes>
          <Route path="/projects/p1" element={<h1><ProjectName projectId="p1" name="NEET" isOwner archived={archived} soloTasks={3} /></h1>} />
          <Route path="/projects" element={<p>Projects list</p>} />
        </Routes>
      </MemoryRouter>,
    );
    return userEvent.setup();
  }

  it("archives the project after the confirm and goes to the Projects list", async () => {
    const user = page();
    await user.click(screen.getByRole("button", { name: "Project settings" }));
    await user.click(screen.getByRole("menuitem", { name: "Archive" }));
    // Round 14: the sentence says what happens to the tasks in no other project.
    expect(
      screen.getByText("Archiving removes this project from your active projects and archives its 3 tasks that are in no other project."),
    ).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "Archive" }));
    expect(projectMutations.archive).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("Projects list")).toBeInTheDocument();
  });

  it("renames in the title, and offers only Rename once archived", async () => {
    const user = page(true);
    await user.click(screen.getByRole("button", { name: "Project settings" }));
    expect(screen.queryByRole("menuitem", { name: "Archive" })).toBeNull();
    await user.click(screen.getByRole("menuitem", { name: "Rename" }));
    const field = screen.getByRole("textbox", { name: "Project name" });
    expect(field.closest("h1")).not.toBeNull();
    await user.type(field, " 2{Enter}");
    expect(projectMutations.rename).toHaveBeenCalledWith({ name: "NEET 2" }, expect.anything());
  });
});

// Owner, round 14: the archive confirm says what happens to the tasks.
describe("projectArchiveSentence", () => {
  it("names the tasks it archives, one or many, and leaves the clause out at none", () => {
    expect(projectArchiveSentence(2)).toBe(
      "Archiving removes this project from your active projects and archives its 2 tasks that are in no other project.",
    );
    expect(projectArchiveSentence(1)).toBe(
      "Archiving removes this project from your active projects and archives its 1 task that is in no other project.",
    );
    expect(projectArchiveSentence(0)).toBe("Archiving removes this project from your active projects.");
    expect(projectArchiveSentence(null)).toBe("Archiving removes this project from your active projects.");
  });

  it("reads the count off a project row, until the generated type carries it", () => {
    expect(soloTaskCount({ project_id: "p1", solo_task_count: 4 })).toBe(4);
    expect(soloTaskCount({ project_id: "p1" })).toBeNull();
  });
});

// Owner, round 14: the backend names the task from its confirmed question
// under the reader; the header changes the name smoothly, not with a cut.
describe("NameMenu — a name that changes on screen (round 14)", () => {
  function renderName(name: string) {
    return (
      <TooltipProvider>
        <NameMenu
          name={name}
          label="Task settings"
          fieldLabel="Task name"
          titleClassName="text-heading"
          canEdit={false}
          rename={vi.fn()}
          renameError=""
          archiveSentence=""
          archiveError=""
        />
      </TooltipProvider>
    );
  }

  it("fades the old name out, then reveals the new one at the streamed text's pace", async () => {
    const view = render(renderName("Untitled task"));
    expect(screen.queryByTestId("name-leaving")).toBeNull();
    view.rerender(renderName("Reducing NEET numbers in Tower Hamlets"));
    const leaving = screen.getByTestId("name-leaving");
    expect(leaving).toHaveTextContent("Untitled task");
    expect(leaving).toHaveClass("anim-fade-out");
    // A screen reader hears the new name at once.
    expect(screen.getByText("Reducing NEET numbers in Tower Hamlets")).toHaveClass("sr-only");
    // After the old name's 150 ms fade, the reveal.
    const revealing = await screen.findByTestId("name-revealing");
    expect(screen.queryByTestId("name-leaving")).toBeNull();
    // It starts from nothing and grows by whole words to the whole name.
    expect((revealing.textContent ?? "").length).toBeLessThan("Reducing NEET numbers in Tower Hamlets".length);
    await waitFor(() => expect(screen.getByTestId("name-revealing")).toHaveTextContent("Reducing NEET numbers in Tower Hamlets"));
    await waitFor(() => expect(screen.queryByTestId("name-revealing")).toBeNull(), { timeout: 2000 });
    expect(screen.getByText("Reducing NEET numbers in Tower Hamlets")).not.toHaveClass("sr-only");
  });

  // Lead, round 14: the chevron fades out with the old name and back when
  // the reveal ends, so it never sits at the left mid-reveal; it keeps its
  // place and its focus.
  it("fades the menu's chevron while the new name is revealed, keeping it in place", async () => {
    function named(name: string) {
      return (
        <TooltipProvider>
          <NameMenu
            name={name}
            label="Task settings"
            fieldLabel="Task name"
            titleClassName="text-heading"
            canEdit
            rename={vi.fn()}
            renameError=""
            archiveSentence=""
            archiveError=""
          />
        </TooltipProvider>
      );
    }
    const view = render(named("Untitled task"));
    const chevron = screen.getByRole("button", { name: "Task settings" });
    const box = chevron.previousElementSibling as HTMLElement;
    expect(box).toHaveClass("peer");
    expect(box).not.toHaveAttribute("data-changing");
    expect(chevron.className).toContain("peer-data-[changing=true]:opacity-0");
    view.rerender(named("Reducing NEET numbers in Tower Hamlets"));
    expect(box).toHaveAttribute("data-changing", "true");
    // Still in the row and still a focusable button.
    expect(screen.getByRole("button", { name: "Task settings" })).toBe(chevron);
    chevron.focus();
    expect(chevron).toHaveFocus();
    await waitFor(() => expect(box).not.toHaveAttribute("data-changing"), { timeout: 2000 });
  });

  it("just commits the reader's own rename", async () => {
    const user = userEvent.setup();
    function Host() {
      const [name, setName] = useState("Untitled task");
      return (
        <TooltipProvider>
          <NameMenu
            name={name}
            label="Task settings"
            fieldLabel="Task name"
            titleClassName="text-heading"
            canEdit
            rename={(next, done) => {
              setName(next);
              done.onSuccess();
            }}
            renameError=""
            archiveSentence=""
            archiveError=""
          />
        </TooltipProvider>
      );
    }
    render(<Host />);
    await user.click(screen.getByRole("button", { name: "Task settings" }));
    await user.click(screen.getByRole("menuitem", { name: "Rename" }));
    await user.clear(screen.getByRole("textbox", { name: "Task name" }));
    await user.type(screen.getByRole("textbox", { name: "Task name" }), "NEET in Tower Hamlets{Enter}");
    expect(screen.getByText("NEET in Tower Hamlets")).toBeInTheDocument();
    expect(screen.queryByTestId("name-leaving")).toBeNull();
    expect(screen.queryByTestId("name-revealing")).toBeNull();
  });

  it("is a cut under reduced motion", () => {
    vi.stubGlobal("matchMedia", (query: string) => ({
      matches: query.includes("reduce"),
      media: query,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    }));
    const view = render(renderName("Untitled task"));
    view.rerender(renderName("Reducing NEET numbers in Tower Hamlets"));
    expect(screen.queryByTestId("name-leaving")).toBeNull();
    expect(screen.queryByTestId("name-revealing")).toBeNull();
    expect(screen.getByText("Reducing NEET numbers in Tower Hamlets")).toBeInTheDocument();
    vi.unstubAllGlobals();
  });
});
