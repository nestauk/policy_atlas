import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { apiError, json, opsMock } from "../mock";
import { renderOps, withOpsMock } from "../testing";

withOpsMock();

async function openPeople() {
  renderOps("/people");
  await screen.findByRole("heading", { name: "People" });
  return userEvent.setup();
}

function row(name: string): HTMLElement {
  const cell = screen.getByText(name, { selector: "span" });
  return cell.closest("tr") as HTMLElement;
}

function selectionBar(): HTMLElement {
  const bar = document.querySelector<HTMLElement>("[data-selection-bar]");
  if (bar === null) throw new Error("no selection bar");
  return bar;
}

async function rowMenu(user: ReturnType<typeof userEvent.setup>, name: string) {
  await user.click(screen.getByRole("button", { name: `Actions for ${name}` }));
  return screen.findByRole("menu", { name: `Actions for ${name}` });
}

describe("People", () => {
  it("lists the columns with their words: organisation or not enrolled, flags, the quota and the invitation", async () => {
    await openPeople();
    const headers = screen.getAllByRole("columnheader").map((cell) => cell.textContent);
    expect(headers).toEqual([
      "Select everyone shown",
      "Name",
      "Email",
      "Organisation",
      "Cohorts",
      "Flags",
      "Tasks this year",
      "Invited",
      "Actions",
    ]);
    expect(row("Tom Ellis")).toHaveTextContent("12 of 100");
    expect(row("Tom Ellis")).toHaveTextContent("25 min ago");
    expect(row("Priya Shah")).toHaveTextContent("no limit");
    expect(within(row("Priya Shah")).getByText("Admin")).toBeInTheDocument();
    expect(within(row("Priya Shah")).getByText("Ops")).toBeInTheDocument();
    expect(within(row("Sam Holt")).getByText("not enrolled")).toBeInTheDocument();
    // No address, and in no cohort.
    expect(within(row("Jon Reyes")).getAllByText("—")).toHaveLength(2);
    expect(row("Priya Shah")).toHaveTextContent("Priority panel");
  });

  it("filters by name, email or organisation, and opens on ?q=", async () => {
    const user = await openPeople();
    await user.type(screen.getByRole("searchbox", { name: "Find a person, organisation or cohort" }), "policy lab");
    expect(screen.getByText("Jon Reyes")).toBeInTheDocument();
    expect(screen.queryByText("Tom Ellis")).toBeNull();
  });

  it("disables Resend inside the hour with its hint, and De-enrol for an unenrolled person with no flag", async () => {
    const user = await openPeople();
    const menu = await rowMenu(user, "Tom Ellis");
    const resend = within(menu).getByRole("menuitem", { name: /Resend invitation/ });
    // aria-disabled, not disabled: still reachable by the arrow keys, so the hint is read.
    expect(resend).toHaveAttribute("aria-disabled", "true");
    expect(resend).not.toHaveAttribute("disabled");
    await user.click(resend);
    expect(opsMock.writes).toEqual([]);
    expect(resend).toHaveTextContent(/sent 25 min ago, try again after \d\d:\d\d/);
    await user.keyboard("{Escape}");
    const samMenu = await rowMenu(user, "Sam Holt");
    expect(within(samMenu).getByRole("menuitem", { name: "De-enrol" })).toHaveAttribute("aria-disabled", "true");
    expect(within(samMenu).getByRole("menuitem", { name: /Resend invitation/ })).not.toHaveAttribute("aria-disabled");
  });

  it("shows the selection bar, and a bulk confirmation names every person", async () => {
    const user = await openPeople();
    await user.click(screen.getByRole("checkbox", { name: "Select Tom Ellis" }));
    await user.click(screen.getByRole("checkbox", { name: "Select Jon Reyes" }));
    const bar = selectionBar();
    expect(bar).toHaveTextContent("2 selected");
    for (const name of ["Set quota…", "Move to…", "Resend invitation", "De-enrol", "Offboard…", "Clear selection"]) {
      expect(within(bar).getByRole("button", { name })).toBeInTheDocument();
    }
    await user.click(within(bar).getByRole("button", { name: "De-enrol" }));
    const dialog = await screen.findByRole("dialog", { name: "De-enrol 2 people?" });
    expect(dialog).toHaveTextContent("Tom Ellis");
    expect(dialog).toHaveTextContent("jon.reyes@policylab.example");
    await user.click(within(dialog).getByRole("button", { name: "De-enrol" }));
    expect(await screen.findByText("2 done, 0 failed · recorded")).toBeInTheDocument();
    expect(opsMock.writes.at(-1)).toMatchObject({
      path: "/api/v1/ops/people/de-enrol",
      body: { user_ids: ["sub-tom", "sub-jon"] },
    });
  });

  it("ticks everyone shown from the header and clears the selection", async () => {
    const user = await openPeople();
    await user.click(screen.getByRole("checkbox", { name: "Select everyone shown" }));
    expect(selectionBar()).toHaveTextContent("6 selected");
    await user.click(screen.getByRole("button", { name: "Clear selection" }));
    expect(document.querySelector("[data-selection-bar]")).toBeNull();
  });

  it("shows a failed row's message under the name, and the counts in the toast", async () => {
    const user = await openPeople();
    opsMock.override = (method, path) =>
      method === "POST" && path === "/api/v1/ops/people/enrol"
        ? json({
            results: [
              { user_id: "sub-tom", outcome: "ok", message: "moved", action_id: "a1" },
              { user_id: "sub-jon", outcome: "failed", message: "Cognito refused the change", action_id: "a2" },
            ],
          })
        : undefined;
    await user.click(screen.getByRole("checkbox", { name: "Select Tom Ellis" }));
    await user.click(screen.getByRole("checkbox", { name: "Select Jon Reyes" }));
    await user.click(screen.getByRole("button", { name: "Move to…" }));
    const dialog = await screen.findByRole("dialog", { name: "Move 2 people to an organisation" });
    expect(dialog).toHaveTextContent("Their tasks and projects move with them and become private.");
    expect(within(dialog).getByRole("button", { name: "Move" })).toBeDisabled();
    await user.click(within(dialog).getByRole("combobox", { name: "Organisation" }));
    await user.click(await screen.findByRole("option", { name: "Policy Lab" }));
    await user.click(within(dialog).getByRole("button", { name: "Move" }));
    expect(await screen.findByText("1 done, 1 failed · recorded")).toBeInTheDocument();
    expect(within(row("Jon Reyes")).getByText("Cognito refused the change")).toBeInTheDocument();
  });

  it("moves one person with its own summary in the toast", async () => {
    const user = await openPeople();
    const menu = await rowMenu(user, "Sam Holt");
    await user.click(within(menu).getByRole("menuitem", { name: "Enrol or move to an organisation…" }));
    const dialog = await screen.findByRole("dialog", { name: "Move Sam Holt to an organisation" });
    await user.click(within(dialog).getByRole("combobox", { name: "Organisation" }));
    await user.click(await screen.findByRole("option", { name: "Nesta" }));
    await user.click(within(dialog).getByRole("button", { name: "Move" }));
    expect(await screen.findByText("Moved Sam Holt to Nesta · recorded")).toBeInTheDocument();
  });

  it("offboards one person once the typed address matches", async () => {
    const user = await openPeople();
    const menu = await rowMenu(user, "Jon Reyes");
    await user.click(within(menu).getByRole("menuitem", { name: "Offboard…" }));
    const dialog = await screen.findByRole("dialog", { name: "Offboard Jon Reyes?" });
    const field = within(dialog).getByLabelText("Type the email to confirm");
    expect(field).toHaveAttribute("placeholder", "jon.reyes@policylab.example");
    const button = within(dialog).getByRole("button", { name: "Offboard" });
    expect(button).toBeDisabled();
    await user.type(field, "jon.reyes@policylab");
    expect(button).toBeDisabled();
    await user.type(field, ".example");
    expect(button).toBeEnabled();
    expect(within(dialog).getByRole("button", { name: "Keep the account" })).toBeInTheDocument();
    await user.click(button);
    expect(await screen.findByText(/· recorded$/)).toBeInTheDocument();
  });

  it("offboards several by typing the count, under every name and address", async () => {
    const user = await openPeople();
    await user.click(screen.getByRole("checkbox", { name: "Select Tom Ellis" }));
    await user.click(screen.getByRole("checkbox", { name: "Select Mara Okafor" }));
    await user.click(screen.getByRole("checkbox", { name: "Select Sam Holt" }));
    await user.click(screen.getByRole("button", { name: "Offboard…" }));
    const dialog = await screen.findByRole("dialog", { name: "Offboard 3 people?" });
    for (const text of ["Tom Ellis", "tom.ellis@nesta.org.uk", "Mara Okafor", "mara.okafor@nesta.org.uk", "Sam Holt"]) {
      expect(dialog).toHaveTextContent(text);
    }
    const field = within(dialog).getByLabelText("Type the number of people to confirm");
    const button = within(dialog).getByRole("button", { name: "Offboard" });
    await user.type(field, "2");
    expect(button).toBeDisabled();
    await user.clear(field);
    await user.type(field, "3");
    expect(button).toBeEnabled();
    await user.click(button);
    expect(await screen.findByText("3 done, 0 failed · recorded")).toBeInTheDocument();
  });

  it("marks rows still cooling down after a bulk resend", async () => {
    const user = await openPeople();
    await user.click(screen.getByRole("checkbox", { name: "Select Tom Ellis" }));
    await user.click(screen.getByRole("checkbox", { name: "Select Sam Holt" }));
    await user.click(screen.getByRole("button", { name: "Resend invitation" }));
    expect(await screen.findByText("1 done, 1 too soon · recorded")).toBeInTheDocument();
    expect(within(row("Tom Ellis")).getByText("Sent less than an hour ago")).toBeInTheDocument();
  });

  it("says when the list cannot load, with Try again", async () => {
    opsMock.override = (method, path) =>
      method === "GET" && path === "/api/v1/ops/people" ? apiError(500, "internal", "internal server error") : undefined;
    const user = userEvent.setup();
    renderOps("/people");
    expect(await screen.findByRole("alert")).toHaveTextContent(/^Could not load the people list\. Try again$/);
    opsMock.override = undefined;
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Tom Ellis")).toBeInTheDocument();
  });
});

describe("People, after the review", () => {
  it("still opens on a plain ?q= search word", async () => {
    renderOps("/people?q=okafor");
    expect(await screen.findByText("Mara Okafor")).toBeInTheDocument();
    expect(screen.queryByText("Tom Ellis")).toBeNull();
  });

  it("clears the selection when the search changes, so a bulk action names only rows in sight", async () => {
    const user = await openPeople();
    await user.click(screen.getByRole("checkbox", { name: "Select Tom Ellis" }));
    await user.click(screen.getByRole("checkbox", { name: "Select Jon Reyes" }));
    await user.type(screen.getByRole("searchbox", { name: "Find a person, organisation or cohort" }), "policy lab");
    expect(document.querySelector("[data-selection-bar]")).toBeNull();
    await user.click(screen.getByRole("checkbox", { name: "Select everyone shown" }));
    await user.click(within(selectionBar()).getByRole("button", { name: "De-enrol" }));
    const dialog = await screen.findByRole("dialog", { name: "De-enrol Jon Reyes?" });
    expect(dialog).not.toHaveTextContent("Tom Ellis");
    await user.click(within(dialog).getByRole("button", { name: "De-enrol" }));
    await screen.findByText(/· recorded$/);
    expect(opsMock.writes.at(-1)?.body).toEqual({ user_ids: ["sub-jon"] });
  });

  it("refuses a bulk quota that is not a whole number", async () => {
    const user = await openPeople();
    await user.click(screen.getByRole("checkbox", { name: "Select Tom Ellis" }));
    await user.click(screen.getByRole("checkbox", { name: "Select Jon Reyes" }));
    await user.click(within(selectionBar()).getByRole("button", { name: "Set quota…" }));
    const dialog = await screen.findByRole("dialog", { name: "Quota for 2 people" });
    await user.type(within(dialog).getByLabelText("Tasks per year"), "ten");
    await user.click(within(dialog).getByRole("button", { name: "Save quota" }));
    expect(within(dialog).getByText("Enter a whole number, or leave it empty.")).toBeInTheDocument();
    expect(opsMock.writes).toEqual([]);
  });

  it("says when nothing matches, inside the table's frame", async () => {
    const user = await openPeople();
    await user.type(screen.getByRole("searchbox", { name: "Find a person, organisation or cohort" }), "zzz");
    expect(screen.getByRole("status")).toHaveTextContent("No people match.");
    expect(screen.getAllByRole("columnheader")).toHaveLength(9);
  });

  it("keeps the selection bar's room, so ticking a box does not move the table", async () => {
    const user = await openPeople();
    const slot = screen.getByRole("table", { name: "People" }).parentElement?.previousElementSibling as HTMLElement;
    expect(slot).toHaveClass("min-h-12");
    expect(slot).toBeEmptyDOMElement();
    await user.click(screen.getByRole("checkbox", { name: "Select Tom Ellis" }));
    expect(slot).toContainElement(selectionBar());
  });

  it("returns focus to the row's menu button when its dialog closes", async () => {
    const user = await openPeople();
    const menu = await rowMenu(user, "Jon Reyes");
    await user.click(within(menu).getByRole("menuitem", { name: "Offboard…" }));
    const dialog = await screen.findByRole("dialog", { name: "Offboard Jon Reyes?" });
    await user.click(within(dialog).getByRole("button", { name: "Keep the account" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Actions for Jon Reyes" })).toHaveFocus());
  });

  it("returns focus to the table when a bulk action cleared the selection", async () => {
    const user = await openPeople();
    await user.click(screen.getByRole("checkbox", { name: "Select Tom Ellis" }));
    await user.click(screen.getByRole("checkbox", { name: "Select Jon Reyes" }));
    await user.click(within(selectionBar()).getByRole("button", { name: "De-enrol" }));
    const dialog = await screen.findByRole("dialog", { name: "De-enrol 2 people?" });
    await user.click(within(dialog).getByRole("button", { name: "De-enrol" }));
    await screen.findByText("2 done, 0 failed · recorded");
    await waitFor(() => expect(screen.getByRole("table", { name: "People" })).toHaveFocus());
  });

  it("reads each dialog's consequence sentence as its description, before the confirm field", async () => {
    const user = await openPeople();
    await user.click(screen.getByRole("checkbox", { name: "Select Tom Ellis" }));
    await user.click(screen.getByRole("checkbox", { name: "Select Jon Reyes" }));
    await user.click(within(selectionBar()).getByRole("button", { name: "Offboard…" }));
    const dialog = await screen.findByRole("dialog", { name: "Offboard 2 people?" });
    expect(dialog).toHaveAccessibleDescription(/^This stops them signing in/);
    const sentence = within(dialog).getByText(/^This stops them signing in/);
    const field = within(dialog).getByLabelText("Type the number of people to confirm");
    expect(sentence.compareDocumentPosition(field) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(dialog).getByRole("button", { name: "Keep the accounts" })).toBeInTheDocument();
  });

  it("the bulk quota dialog has Cancel first, then Clear and inherit beside Save quota, and the plural warning", async () => {
    const user = await openPeople();
    await user.click(screen.getByRole("checkbox", { name: "Select Tom Ellis" }));
    await user.click(screen.getByRole("checkbox", { name: "Select Jon Reyes" }));
    await user.click(within(selectionBar()).getByRole("button", { name: "Set quota…" }));
    const dialog = await screen.findByRole("dialog", { name: "Quota for 2 people" });
    const buttons = within(dialog)
      .getAllByRole("button")
      .map((button) => button.textContent);
    expect(buttons.slice(-3)).toEqual(["Cancel", "Clear and inherit", "Save quota"]);
    expect(within(dialog).getByLabelText("Simultaneous tasks")).toHaveAccessibleDescription(
      "Warning: this limit protects the shared run capacity. A higher number lets these people take more of it at the same time, which can slow other people's runs.",
    );
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(opsMock.writes).toEqual([]);
  });
});

describe("People, cohorts", () => {
  it("adds the ticked people to a cohort, and finds people by cohort name", async () => {
    const user = await openPeople();
    const row = (name: string) => screen.getByText(name, { selector: "span[title]" }).closest("tr") as HTMLElement;
    await user.click(within(row("Tom Ellis")).getByRole("checkbox"));
    await user.click(within(row("Jon Reyes")).getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Add to cohort…" }));
    const dialog = await screen.findByRole("dialog", { name: "Add 2 people to a cohort" });
    await user.click(within(dialog).getByRole("combobox", { name: "Cohort" }));
    await user.click(await screen.findByRole("option", { name: "DHSC V3 pilot" }));
    await user.click(within(dialog).getByRole("button", { name: "Add" }));
    expect(await screen.findByText("2 done, 0 failed · recorded")).toBeInTheDocument();
    expect(opsMock.writes.at(-1)).toMatchObject({
      path: "/api/v1/ops/people/cohort-add",
      body: { cohort_id: "00000000-0000-4000-8000-00000000000e" },
    });
    await user.type(screen.getByRole("searchbox", { name: "Find a person, organisation or cohort" }), "dhsc");
    await waitFor(() => expect(screen.getAllByRole("row")).toHaveLength(3));
  });

  it("removes one person from a cohort they are in, offering only their cohorts", async () => {
    const user = await openPeople();
    await user.click(screen.getByRole("button", { name: "Actions for Priya Shah" }));
    await user.click(screen.getByRole("menuitem", { name: "Remove from cohort…" }));
    const dialog = await screen.findByRole("dialog", { name: "Remove Priya Shah from a cohort" });
    await user.click(within(dialog).getByRole("combobox", { name: "Cohort" }));
    expect(screen.queryByRole("option", { name: "DHSC V3 pilot" })).toBeNull();
    await user.click(screen.getByRole("option", { name: "Priority panel" }));
    await user.click(within(dialog).getByRole("button", { name: "Remove" }));
    expect(await screen.findByText("Removed Priya Shah from Priority panel · recorded")).toBeInTheDocument();
  });
});

