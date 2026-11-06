import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { TooltipProvider } from "../ui/radix/Tooltip";
import { NameMenu, ProjectName } from "./NameMenu";

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
        after={<span>Options scoping</span>}
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
  it("shows the name, what follows it and a 40 px chevron control for the owner only", () => {
    menu();
    expect(screen.getByText("NEET in Tower Hamlets")).toBeInTheDocument();
    expect(screen.getByText("Options scoping")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Task settings" })).toHaveClass("h-10", "w-10");
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
          <Route path="/projects/p1" element={<h1><ProjectName projectId="p1" name="NEET" isOwner archived={archived} /></h1>} />
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
    expect(screen.getByText("Archiving removes this project from your active projects. Its tasks stay as they are.")).toHaveFocus();
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
