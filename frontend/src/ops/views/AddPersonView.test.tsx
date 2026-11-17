import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { apiError, opsMock } from "../mock";
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
  it("shows the fields, their help and the three sentences of What happens", async () => {
    renderOps("/people/new");
    await screen.findByRole("heading", { name: "Add a person" });
    expect(within(screen.getByRole("main")).getByRole("link", { name: "People" })).toHaveAttribute("href", "/people");
    expect(screen.getByText("Shown to colleagues. Not the email.")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "What happens" })).toHaveTextContent(
      /from no-reply@localhost\. It is valid for 30 days\..*no email is sent\..*you are told which one\./,
    );
  });

  it("sends the invitation, toasts it as recorded and goes back to People", async () => {
    const router = await fill("ana.lopez@westbury.gov.uk");
    expect(await screen.findByText("Invitation sent to ana.lopez@westbury.gov.uk · recorded")).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/people");
  });

  it("says when an existing unenrolled account was added without an email", async () => {
    await fill("sam.holt@example.com");
    expect(await screen.findByText("Added to Nesta, no email sent · recorded")).toBeInTheDocument();
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
});
