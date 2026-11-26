import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { apiError, opsMock } from "../mock";
import { DHSC_PILOT, NESTA } from "../mock/fixtures";
import { pick, renderOps, withOpsMock } from "../testing";

withOpsMock();

async function fill(email: string, org = "Nesta") {
  const user = userEvent.setup();
  const router = renderOps("/people/new");
  await screen.findByRole("heading", { name: "Add a person" });
  await user.type(screen.getByLabelText("Email"), email);
  await user.type(screen.getByLabelText("Display name"), "Ana Lopez");
  await pick(user, "Organisation", org);
  await user.click(screen.getByRole("button", { name: "Create and send invitation" }));
  return router;
}

describe("Add a person", () => {
  it("shows the fields and the sentences of What happens", async () => {
    renderOps("/people/new");
    await screen.findByRole("heading", { name: "Add a person" });
    expect(within(screen.getByRole("main")).getByRole("link", { name: "People" })).toHaveAttribute("href", "/people");
    expect(screen.getByLabelText("Display name")).not.toHaveAccessibleDescription();
    expect(screen.getByRole("region", { name: "What happens" })).toHaveTextContent(
      /temporary password\. It is valid for 30 days\..*No email is sent, because they can already sign in\.If the email already belongs to another organisation, nothing changes\.The person joins the cohorts you choose here\.$/,
    );
  });

  it("sends the chosen cohorts and names them in the toast", async () => {
    const user = userEvent.setup();
    renderOps("/people/new");
    await screen.findByRole("heading", { name: "Add a person" });
    await user.type(screen.getByLabelText("Email"), "ana.lopez@westbury.gov.uk");
    await user.type(screen.getByLabelText("Display name"), "Ana Lopez");
    await pick(user, "Organisation", "Nesta");
    await user.click(screen.getByRole("button", { name: /^Cohorts/ }));
    await user.click(await screen.findByRole("checkbox", { name: "Priority panel" }));
    await user.click(screen.getByRole("checkbox", { name: "DHSC pilot 2027" }));
    await user.keyboard("{Escape}");
    const chosen = screen.getByRole("list", { name: "Cohorts: chosen" });
    await user.click(within(chosen).getByRole("button", { name: "Remove Priority panel" }));
    await user.click(screen.getByRole("button", { name: "Create and send invitation" }));
    expect(
      await screen.findByText("Invitation sent to ana.lopez@westbury.gov.uk. Added to DHSC pilot 2027."),
    ).toBeInTheDocument();
    expect(opsMock.writes.at(-1)?.body).toEqual({
      email: "ana.lopez@westbury.gov.uk",
      display_name: "Ana Lopez",
      org_id: NESTA,
      cohort_ids: [DHSC_PILOT],
      reactivate: true,
    });
  });

  it("asks for an organisation when none is chosen, and links the error to its field", async () => {
    const user = userEvent.setup();
    renderOps("/people/new");
    await screen.findByRole("heading", { name: "Add a person" });
    const select = screen.getByRole("combobox", { name: "Organisation" });
    expect(select).toHaveTextContent("Choose an organisation.");
    await user.type(screen.getByLabelText("Email"), "ana@x.org");
    await user.type(screen.getByLabelText("Display name"), "Ana Lopez");
    await user.click(screen.getByRole("button", { name: "Create and send invitation" }));
    expect(select).toHaveFocus();
    expect(select).toHaveAttribute("aria-invalid", "true");
    expect(select).toHaveAccessibleDescription("Choose an organisation.");
    expect(opsMock.writes).toEqual([]);
  });

  it("sends the invitation, toasts it and goes back to People", async () => {
    const router = await fill("ana.lopez@westbury.gov.uk");
    expect(await screen.findByText("Invitation sent to ana.lopez@westbury.gov.uk")).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/people");
  });

  it("says when an existing unenrolled account was added without an email", async () => {
    await fill("sam.holt@example.com");
    expect(await screen.findByText("Added to Nesta, no email sent")).toBeInTheDocument();
  });

  it("puts enrolled_elsewhere under the email and keeps what was typed", async () => {
    await fill("jon.reyes@policylab.example");
    expect(
      await screen.findByText("Already in Policy Lab. Use Enrol or move from the People list."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveValue("jon.reyes@policylab.example");
    expect(screen.getByLabelText("Email")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText("Display name")).toHaveValue("Ana Lopez");
  });

  it("puts ops_refused's message under the form", async () => {
    opsMock.override = (method, path) =>
      method === "POST" && path === "/api/v1/ops/people"
        ? apiError(409, "ops_refused", "ana@x.org already exists in the pool — use user enrol")
        : undefined;
    await fill("ana@x.org");
    expect(await screen.findByRole("alert")).toHaveTextContent("ana@x.org already exists in the pool — use user enrol");
    expect(screen.getByLabelText("Email")).toHaveValue("ana@x.org");
  });

  it("narrows the organisations as you type, and Enter takes the only match", async () => {
    const user = userEvent.setup();
    renderOps("/people/new");
    await screen.findByRole("heading", { name: "Add a person" });
    await user.click(screen.getByRole("combobox", { name: "Organisation" }));
    await user.type(screen.getByRole("searchbox", { name: "Find or create an organisation" }), "lab");
    expect(screen.queryByRole("option", { name: "Nesta" })).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Policy Lab" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Create organisation “lab”" })).toBeInTheDocument();
    await user.clear(screen.getByRole("searchbox", { name: "Find or create an organisation" }));
    await user.type(screen.getByRole("searchbox", { name: "Find or create an organisation" }), "policy lab{Enter}");
    expect(screen.getByRole("combobox", { name: "Organisation" })).toHaveTextContent("Policy Lab");
    expect(opsMock.writes).toEqual([]);
  });

  it("creates a new organisation from the picker and chooses it", async () => {
    const user = userEvent.setup();
    renderOps("/people/new");
    await screen.findByRole("heading", { name: "Add a person" });
    await user.click(screen.getByRole("combobox", { name: "Organisation" }));
    await user.type(screen.getByRole("searchbox", { name: "Find or create an organisation" }), "Fresh Org");
    await user.click(screen.getByRole("option", { name: "Create organisation “Fresh Org”" }));
    expect(await screen.findByRole("combobox", { name: "Organisation" })).toHaveTextContent("Fresh Org");
    expect(opsMock.writes.map((write) => write.body)).toEqual([{ name: "Fresh Org" }]);
  });

  it("says so when the new organisation's name is taken", async () => {
    const user = userEvent.setup();
    opsMock.override = (method, path) =>
      method === "POST" && path === "/api/v1/ops/organisations" ? apiError(409, "conflict", "exists") : undefined;
    renderOps("/people/new");
    await screen.findByRole("heading", { name: "Add a person" });
    await user.click(screen.getByRole("combobox", { name: "Organisation" }));
    await user.type(screen.getByRole("searchbox", { name: "Find or create an organisation" }), "Taken{Enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent("An organisation with that name already exists.");
  });
});
