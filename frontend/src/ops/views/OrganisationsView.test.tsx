import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { renderOps, withOpsMock } from "../testing";

withOpsMock();

function row(name: string) {
  return screen.getAllByRole("row").find((element) => element.textContent?.startsWith(name)) as HTMLElement;
}

describe("Organisations", () => {
  it("lists overrides, the defaults, domains and the row menu", async () => {
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
    expect(
      within(nesta).getByText((_, element) => element?.tagName === "SPAN" && /^default\s· 3$/.test(element.textContent ?? "")),
    ).toBeInTheDocument();
    expect(nesta).toHaveTextContent("nesta.org.uk");
    expect(within(row("Westbury Council")).getByText("westbury.gov.uk, westbury.example")).toBeInTheDocument();
    expect(within(row("Policy Lab")).getByText("—")).toBeInTheDocument();
    expect(within(row("Policy Lab")).getByRole("link", { name: "Policy Lab" })).toHaveAttribute(
      "href",
      "/people?org=00000000-0000-4000-8000-00000000000b",
    );
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
    expect(await screen.findByText("Created Harbour Trust")).toBeInTheDocument();
    expect(await screen.findByText("Harbour Trust")).toBeInTheDocument();
  });

  it("says when nothing matches the search, inside the table's frame", async () => {
    const user = userEvent.setup();
    renderOps("/organisations");
    await user.type(await screen.findByRole("searchbox", { name: "Find an organisation" }), "zzz");
    expect(screen.getByRole("status")).toHaveTextContent("No organisations match.");
    expect(screen.getAllByRole("columnheader")).toHaveLength(7);
  });

  it("sorts by a column on click, and reverses on the second click", async () => {
    const user = userEvent.setup();
    renderOps("/organisations");
    await screen.findByRole("table");
    const names = () => screen.getAllByRole("row").slice(1).map((row) => within(row).getAllByRole("cell")[0].textContent);
    await user.click(screen.getByRole("button", { name: "Sort by people" }));
    expect(names()).toEqual(["Westbury Council", "Policy Lab", "Nesta"]);
    expect(screen.getByRole("columnheader", { name: /People/ })).toHaveAttribute("aria-sort", "ascending");
    await user.click(screen.getByRole("button", { name: "Sort by people" }));
    expect(names()).toEqual(["Nesta", "Policy Lab", "Westbury Council"]);
  });
});

