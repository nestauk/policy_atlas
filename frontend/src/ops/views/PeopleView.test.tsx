import { screen, within } from "@testing-library/react";
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
    expect(within(row("Jon Reyes")).getByText("—")).toBeInTheDocument();
  });

  it("filters by name, email or organisation, and opens on ?q=", async () => {
    const user = await openPeople();
    await user.type(screen.getByRole("searchbox", { name: "Find by name, email or organisation" }), "policy lab");
    expect(screen.getByText("Jon Reyes")).toBeInTheDocument();
    expect(screen.queryByText("Tom Ellis")).toBeNull();
  });

  it("disables Resend inside the hour with its hint, and De-enrol for an unenrolled person with no flag", async () => {
    const user = await openPeople();
    const menu = await rowMenu(user, "Tom Ellis");
    const resend = within(menu).getByRole("menuitem", { name: /Resend invitation/ });
    expect(resend).toBeDisabled();
    expect(resend).toHaveTextContent(/sent 25 min ago, try again after \d\d:\d\d/);
    await user.keyboard("{Escape}");
    const samMenu = await rowMenu(user, "Sam Holt");
    expect(within(samMenu).getByRole("menuitem", { name: "De-enrol" })).toBeDisabled();
    expect(within(samMenu).getByRole("menuitem", { name: /Resend invitation/ })).toBeEnabled();
  });

  it("shows the selection bar, and a bulk confirmation names every person", async () => {
    const user = await openPeople();
    await user.click(screen.getByRole("checkbox", { name: "Select Tom Ellis" }));
    await user.click(screen.getByRole("checkbox", { name: "Select Jon Reyes" }));
    const bar = screen.getByRole("toolbar", { name: "Selected people" });
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
    expect(screen.getByRole("toolbar", { name: "Selected people" })).toHaveTextContent("6 selected");
    await user.click(screen.getByRole("button", { name: "Clear selection" }));
    expect(screen.queryByRole("toolbar", { name: "Selected people" })).toBeNull();
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
    expect(await screen.findByText("1 done, 0 failed · recorded")).toBeInTheDocument();
    expect(within(row("Tom Ellis")).getByText("Sent less than an hour ago")).toBeInTheDocument();
  });

  it("says when the list cannot load, with Try again", async () => {
    opsMock.override = (method, path) =>
      method === "GET" && path === "/api/v1/ops/people" ? apiError(500, "internal", "internal server error") : undefined;
    const user = userEvent.setup();
    renderOps("/people");
    expect(await screen.findByText("Something went wrong. Try again.")).toBeInTheDocument();
    opsMock.override = undefined;
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Tom Ellis")).toBeInTheDocument();
  });
});
