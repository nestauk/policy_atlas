import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { opsMock } from "../mock";
import { pick, renderOps, withOpsMock } from "../testing";

withOpsMock();

const PROJECT = "00000000-0000-4000-8000-0000000000aa";

function row(name: string) {
  return screen.getAllByRole("row").find((element) => element.textContent?.startsWith(name)) as HTMLElement;
}

describe("Organisations", () => {
  it("lists overrides, the defaults in grey, domains and the row menu", async () => {
    const user = userEvent.setup();
    const router = renderOps("/organisations");
    expect(await screen.findByRole("heading", { name: "Organisations" })).toBeInTheDocument();
    const headers = screen.getAllByRole("columnheader").map((cell) => cell.textContent);
    expect(headers).toEqual([
      "Name",
      "People",
      "Tasks per year",
      "Simultaneous tasks",
      "Self-signup domain",
      "Created",
      "Actions",
    ]);
    const nesta = row("Nesta");
    expect(nesta).toHaveTextContent("100");
    const grey = within(nesta).getByText((_, element) => element?.tagName === "SPAN" && /^default\s· 3$/.test(element.textContent ?? ""));
    expect(grey).toHaveClass("text-grey");
    expect(nesta).toHaveTextContent("nesta.org.uk");
    expect(within(row("Westbury Council")).getByText("westbury.gov.uk, westbury.example")).toBeInTheDocument();
    expect(within(row("Policy Lab")).getByText("—")).toBeInTheDocument();
    expect(row("Policy Lab")).toHaveTextContent("default · 50");
    await user.click(within(nesta).getByRole("button", { name: "Actions for Nesta" }));
    await user.click(await screen.findByRole("menuitem", { name: "Set quota defaults…" }));
    expect(router.state.location.pathname).toMatch(/^\/organisations\/.+\/quota$/);
  });

  it("adds an organisation, and says when the name is taken", async () => {
    const user = userEvent.setup();
    renderOps("/organisations");
    await user.click(await screen.findByRole("button", { name: "Add organisation" }));
    const dialog = await screen.findByRole("dialog", { name: "Add organisation" });
    await user.type(within(dialog).getByLabelText("Name"), "Nesta");
    await user.click(within(dialog).getByRole("button", { name: "Create" }));
    expect(await within(dialog).findByText("An organisation with that name already exists.")).toBeInTheDocument();
    await user.clear(within(dialog).getByLabelText("Name"));
    await user.type(within(dialog).getByLabelText("Name"), "Harbour Trust");
    await user.click(within(dialog).getByRole("button", { name: "Create" }));
    expect(await screen.findByText("Created Harbour Trust · recorded")).toBeInTheDocument();
    expect(await screen.findByText("Harbour Trust")).toBeInTheDocument();
  });

  it("moves a project from its pasted web address, with the toast alone", async () => {
    const user = userEvent.setup();
    renderOps("/organisations");
    const panel = await screen.findByRole("region", { name: "Move a task or project to another organisation" });
    expect(panel).toHaveTextContent("Paste the id from its web address");
    await user.type(within(panel).getByLabelText("Task or project id"), `https://policyatlas.uk/projects/${PROJECT}`);
    await pick(user, "Move to", "Nesta");
    await user.click(within(panel).getByRole("button", { name: "Move" }));
    expect(await screen.findByText("Moved 1 project and 4 tasks into Nesta · recorded")).toBeInTheDocument();
    expect(within(panel).queryByText(/project\(s\)/)).toBeNull();
    expect(opsMock.writes.at(-1)?.body).toMatchObject({ project_id: PROJECT });
  });

  it("says when no task or project has the id", async () => {
    const user = userEvent.setup();
    renderOps("/organisations");
    const panel = await screen.findByRole("region", { name: "Move a task or project to another organisation" });
    const field = within(panel).getByLabelText("Task or project id");
    await user.type(field, "not-an-id");
    await pick(user, "Move to", "Nesta");
    await user.click(within(panel).getByRole("button", { name: "Move" }));
    expect(await within(panel).findByText("No task or project has that id.")).toBeInTheDocument();
    expect(field).toHaveAttribute("aria-invalid", "true");
    expect(field).toHaveAccessibleDescription(/No task or project has that id\./);
  });

  it("says when nothing matches the search, inside the table's frame", async () => {
    const user = userEvent.setup();
    renderOps("/organisations");
    await user.type(await screen.findByRole("searchbox", { name: "Find an organisation" }), "zzz");
    expect(screen.getByRole("status")).toHaveTextContent("No organisations match.");
    expect(screen.getAllByRole("columnheader")).toHaveLength(7);
  });

  it("tries a bare id as a task, then as a project", async () => {
    const user = userEvent.setup();
    opsMock.override = (method, path, body) =>
      method === "POST" && path === "/api/v1/ops/rows/assign" && (body as { task_id?: string }).task_id != null
        ? new Response(JSON.stringify({ error: { code: "not_found", message: "resource not found" } }), { status: 404 })
        : undefined;
    renderOps("/organisations");
    const panel = await screen.findByRole("region", { name: "Move a task or project to another organisation" });
    await user.type(within(panel).getByLabelText("Task or project id"), PROJECT);
    await pick(user, "Move to", "Policy Lab");
    await user.click(within(panel).getByRole("button", { name: "Move" }));
    expect(await screen.findByText("Moved 1 project and 4 tasks into Policy Lab · recorded")).toBeInTheDocument();
    expect(opsMock.writes.map((write) => write.body)).toEqual([
      expect.objectContaining({ task_id: PROJECT }),
      expect.objectContaining({ project_id: PROJECT }),
    ]);
  });
});
