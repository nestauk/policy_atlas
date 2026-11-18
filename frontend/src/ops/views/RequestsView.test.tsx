import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { EMPTY_ORG as WESTBURY_FOR_TEST } from "../mock/fixtures";
import { apiError, opsMock } from "../mock";
import { renderOps, withOpsMock } from "../testing";

withOpsMock();

function row(name: string) {
  return screen.getByText(name, { selector: "span" }).closest("tr") as HTMLElement;
}

describe("Waitlist", () => {
  it("shows the self-signup line and the three status chips with their actions", async () => {
    renderOps("/waitlist");
    expect(await screen.findByRole("heading", { name: "Waitlist" })).toBeInTheDocument();
    expect(
      screen.getByText("Self-signup on for nesta.org.uk, westbury.gov.uk · 2 of 20 invitations sent this hour"),
    ).toBeInTheDocument();
    expect(within(row("Ana Lopez")).getByText("Waiting")).toBeInTheDocument();
    expect(within(row("Ana Lopez")).getByRole("button", { name: "Approve into…" })).toBeInTheDocument();
    expect(within(row("Ben Cole")).getByText("Invited 1 d ago")).toBeInTheDocument();
    expect(within(row("Ben Cole")).queryByRole("button")).toBeNull();
    expect(within(row("Jon Reyes")).getByText("Check: already in Policy Lab")).toBeInTheDocument();
    // The address goes in router state, never the URL (it would reach the access log).
    expect(within(row("Jon Reyes")).getByRole("link", { name: "Open person" })).toHaveAttribute("href", "/people");
  });

  it("says when there are no requests, inside the table's frame", async () => {
    opsMock.requests.items = [];
    renderOps("/waitlist");
    expect(await screen.findByText("No requests yet.")).toHaveAttribute("role", "status");
    expect(screen.getAllByRole("columnheader")).toHaveLength(5);
  });

  it("Open person lands on People searching for the address, with the address kept out of the URL", async () => {
    const user = userEvent.setup();
    const router = renderOps("/waitlist");
    await screen.findByRole("heading", { name: "Waitlist" });
    await user.click(within(row("Jon Reyes")).getByRole("link", { name: "Open person" }));
    expect(await screen.findByRole("searchbox", { name: "Find a person, organisation or cohort" })).toHaveValue(
      "jon.reyes@policylab.example",
    );
    expect(router.state.location.pathname).toBe("/people");
    expect(router.state.location.search).toBe("");
    expect(screen.getAllByRole("row")).toHaveLength(2);
  });

  it("says Self-signup off when it is", async () => {
    opsMock.requests.self_signup.enabled = false;
    renderOps("/waitlist");
    expect(await screen.findByText("Self-signup off")).toBeInTheDocument();
  });

  it("approves into an organisation", async () => {
    const user = userEvent.setup();
    renderOps("/waitlist");
    await user.click(await screen.findByRole("button", { name: "Approve into…" }));
    const dialog = await screen.findByRole("dialog", { name: "Approve Ana Lopez" });
    expect(dialog).toHaveAccessibleDescription(
      "Cognito emails them a temporary password. If the address already has an account, it is enrolled without an email.",
    );
    expect(within(dialog).getByRole("combobox", { name: "Organisation" })).toHaveTextContent("Choose an organisation.");
    expect(within(dialog).getByRole("button", { name: "Approve" })).toBeDisabled();
    await user.click(within(dialog).getByRole("combobox", { name: "Organisation" }));
    await user.click(await screen.findByRole("option", { name: "Westbury Council" }));
    await user.click(within(dialog).getByRole("button", { name: "Approve" }));
    expect(await screen.findByText("Ana Lopez approved · recorded")).toBeInTheDocument();
    expect(opsMock.writes.at(-1)?.body).toEqual({ org_id: WESTBURY_FOR_TEST });
    expect(await within(row("Ana Lopez")).findByText(/^Invited /)).toBeInTheDocument();
    // The row's button is gone: focus goes to the table.
    await waitFor(() => expect(screen.getByRole("table", { name: "Waitlist" })).toHaveFocus());
  });

  it("turns the row to Check when the address is enrolled elsewhere", async () => {
    opsMock.override = (method, path) =>
      method === "POST" && path.endsWith("/approve")
        ? apiError(
            409,
            "enrolled_elsewhere",
            "ana.lopez@westbury.gov.uk is already in Nesta. Nothing was written. Move them from the People list (`user enrol`).",
          )
        : undefined;
    const user = userEvent.setup();
    renderOps("/waitlist");
    await user.click(await screen.findByRole("button", { name: "Approve into…" }));
    const dialog = await screen.findByRole("dialog", { name: "Approve Ana Lopez" });
    await user.click(within(dialog).getByRole("combobox", { name: "Organisation" }));
    await user.click(await screen.findByRole("option", { name: "Nesta" }));
    await user.click(within(dialog).getByRole("button", { name: "Approve" }));
    expect(await within(row("Ana Lopez")).findByText("Check: already in Nesta")).toBeInTheDocument();
    expect(within(row("Ana Lopez")).getByText(/is already in Nesta\. Nothing was written/)).toBeInTheDocument();
    expect(within(row("Ana Lopez")).getByRole("link", { name: "Open person" })).toBeInTheDocument();
  });
});
