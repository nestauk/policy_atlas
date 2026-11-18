import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { opsMock } from "../mock";
import { PANEL } from "../mock/fixtures";
import { renderOps, withOpsMock } from "../testing";

withOpsMock();

describe("Cohorts", () => {
  it("lists cohorts with people, dates and links", async () => {
    renderOps("/cohorts");
    const table = await screen.findByRole("table", { name: "Cohorts" });
    const row = (name: string) => within(table).getByText(name).closest("tr") as HTMLElement;
    expect(row("Priority panel")).toHaveTextContent("Policy leads from HMT");
    expect(within(row("Priority panel")).getByRole("link", { name: "example.org/panel-notes" })).toHaveAttribute(
      "href",
      "https://example.org/panel-notes",
    );
    expect(row("DHSC V3 pilot")).toHaveTextContent("1 Dec 2026 – 31 Jan 2027");
  });

  it("creates a cohort with links one per line", async () => {
    const user = userEvent.setup();
    renderOps("/cohorts");
    await user.click(await screen.findByRole("button", { name: "Add cohort" }));
    const dialog = await screen.findByRole("dialog", { name: "Add cohort" });
    await user.type(within(dialog).getByLabelText("Name"), "Spending bid users");
    await user.type(within(dialog).getByLabelText("Links (optional)"), "https://a.example/plan{Enter}{Enter}https://b.example");
    await user.click(within(dialog).getByRole("button", { name: "Create" }));
    expect(await screen.findByText("Created Spending bid users · recorded")).toBeInTheDocument();
    expect(opsMock.writes.at(-1)?.body).toEqual({
      name: "Spending bid users",
      description: null,
      starts_on: null,
      ends_on: null,
      links: ["https://a.example/plan", "https://b.example"],
    });
  });

  it("refuses an end before the start without sending, and shows a taken name", async () => {
    const user = userEvent.setup();
    renderOps("/cohorts");
    await user.click(await screen.findByRole("button", { name: "Add cohort" }));
    const dialog = await screen.findByRole("dialog", { name: "Add cohort" });
    await user.type(within(dialog).getByLabelText("Name"), "priority panel");
    await user.type(within(dialog).getByLabelText("Start date (optional)"), "2027-02-01");
    await user.type(within(dialog).getByLabelText("End date (optional)"), "2027-01-01");
    await user.click(within(dialog).getByRole("button", { name: "Create" }));
    expect(within(dialog).getByRole("alert")).toHaveTextContent("The end date is before the start date.");
    expect(opsMock.writes).toEqual([]);
    await user.clear(within(dialog).getByLabelText("End date (optional)"));
    await user.click(within(dialog).getByRole("button", { name: "Create" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("A cohort named 'priority panel' already exists.");
  });

  it("edits and deletes a cohort", async () => {
    const user = userEvent.setup();
    renderOps("/cohorts");
    await user.click(await screen.findByRole("button", { name: "Actions for Priority panel" }));
    await user.click(screen.getByRole("menuitem", { name: "Edit…" }));
    const dialog = await screen.findByRole("dialog", { name: "Edit Priority panel" });
    expect(within(dialog).getByLabelText("Links (optional)")).toHaveValue("https://example.org/panel-notes");
    await user.click(within(dialog).getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Saved Priority panel · recorded")).toBeInTheDocument();
    expect(opsMock.writes.at(-1)?.path).toBe(`/api/v1/ops/cohorts/${PANEL}`);

    await user.click(screen.getByRole("button", { name: "Actions for Priority panel" }));
    await user.click(screen.getByRole("menuitem", { name: "Delete…" }));
    const confirm = await screen.findByRole("dialog", { name: "Delete Priority panel?" });
    expect(confirm).toHaveTextContent("This takes the label off 1 person.");
    await user.click(within(confirm).getByRole("button", { name: "Delete" }));
    expect(await screen.findByText("Deleted Priority panel · recorded")).toBeInTheDocument();
    expect(screen.queryByText("Priority panel", { selector: "span" })).toBeNull();
  });
});
