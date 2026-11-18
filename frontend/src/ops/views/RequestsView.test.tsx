import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { EMPTY_ORG as WESTBURY_FOR_TEST } from "../mock/fixtures";
import { apiError, opsMock } from "../mock";
import { renderOps, withOpsMock } from "../testing";

withOpsMock();

function row(name: string) {
  return screen.getByText(name, { selector: "button" }).closest("tr") as HTMLElement;
}

describe("Waitlist", () => {
  it("explains self-signup and lists only requests waiting for a decision", async () => {
    renderOps("/waitlist");
    expect(await screen.findByRole("heading", { name: "Waitlist" })).toBeInTheDocument();
    expect(screen.getByText(/^Self-signup is on for/)).toHaveTextContent(
      "Self-signup is on for nesta.org.uk, westbury.gov.uk. Requests from these addresses get an account and an invitation automatically within a minute, up to 20 an hour (2 sent this hour). Other requests wait here until someone approves or rejects them.",
    );
    expect(within(row("Ana Lopez")).getByText("Waiting")).toBeInTheDocument();
    expect(within(row("Ana Lopez")).getByRole("button", { name: "Approve" })).toBeInTheDocument();
    expect(within(row("Ana Lopez")).getByRole("button", { name: "Reject" })).toBeInTheDocument();
    // Ben Cole was invited: he is on People now, not here.
    expect(screen.queryByRole("button", { name: "Ben Cole" })).toBeNull();
    expect(within(row("Jon Reyes")).getByText("Already in Policy Lab")).toBeInTheDocument();
    // The address goes in router state, never the URL (it would reach the access log).
    expect(within(row("Jon Reyes")).getByRole("link", { name: "Open person" })).toHaveAttribute("href", "/people");
  });

  it("says when there are no requests, inside the table's frame", async () => {
    opsMock.requests.items = [];
    renderOps("/waitlist");
    expect(await screen.findByText("No requests yet.")).toHaveAttribute("role", "status");
    expect(screen.getAllByRole("columnheader")).toHaveLength(6);
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
    expect(
      await screen.findByText("Self-signup is off. Every request waits here until someone approves or rejects it."),
    ).toBeInTheDocument();
  });

  it("approves into an organisation", async () => {
    const user = userEvent.setup();
    renderOps("/waitlist");
    await user.click(await screen.findByRole("button", { name: "Approve" }));
    const dialog = await screen.findByRole("dialog", { name: "Approve Ana Lopez" });
    expect(dialog).toHaveAccessibleDescription(
      "Policy Atlas will email them a temporary password. If the address already has an account, it is enrolled without an email.",
    );
    expect(within(dialog).getByRole("combobox", { name: "Organisation" })).toHaveTextContent("Choose an organisation.");
    expect(within(dialog).getByRole("button", { name: "Approve" })).toBeDisabled();
    await user.click(within(dialog).getByRole("combobox", { name: "Organisation" }));
    await user.click(await screen.findByRole("option", { name: "Westbury Council" }));
    await user.click(within(dialog).getByRole("button", { name: "Approve" }));
    expect(await screen.findByText("Ana Lopez approved")).toBeInTheDocument();
    expect(opsMock.writes.at(-1)?.body).toEqual({ org_id: WESTBURY_FOR_TEST });
    // Approved, the request leaves the waitlist: focus goes to the table.
    await waitFor(() => expect(screen.queryByRole("button", { name: "Ana Lopez" })).toBeNull());
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
    await user.click(await screen.findByRole("button", { name: "Approve" }));
    const dialog = await screen.findByRole("dialog", { name: "Approve Ana Lopez" });
    await user.click(within(dialog).getByRole("combobox", { name: "Organisation" }));
    await user.click(await screen.findByRole("option", { name: "Nesta" }));
    await user.click(within(dialog).getByRole("button", { name: "Approve" }));
    expect(await within(row("Ana Lopez")).findByText("Already in Nesta")).toBeInTheDocument();
    expect(within(row("Ana Lopez")).getByText(/is already in Nesta\. Nothing was written/)).toBeInTheDocument();
    expect(within(row("Ana Lopez")).getByRole("link", { name: "Open person" })).toBeInTheDocument();
  });

  it("opens a request's details from its name, with Approve when it waits", async () => {
    const user = userEvent.setup();
    renderOps("/waitlist");
    await user.click(await screen.findByRole("button", { name: "Ana Lopez" }));
    const dialog = await screen.findByRole("dialog", { name: "Ana Lopez" });
    expect(dialog).toHaveTextContent("Role or reason");
    expect(dialog).toHaveTextContent("Organisation");
    await user.click(within(dialog).getByRole("button", { name: "Approve" }));
    expect(await screen.findByRole("dialog", { name: "Approve Ana Lopez" })).toBeInTheDocument();
  });

  it("approves several waiting requests into one organisation, one call each", async () => {
    const user = userEvent.setup();
    renderOps("/waitlist");
    const waiting = await screen.findAllByRole("checkbox", { name: /^Select (?!every)/ });
    await user.click(screen.getByRole("button", { name: `Select all ${waiting.length} waiting` }));
    const bar = document.querySelector("[data-selection-bar]") as HTMLElement;
    expect(bar).toHaveTextContent(`${waiting.length} selected`);
    await user.click(within(bar).getByRole("button", { name: "Approve" }));
    const dialog = await screen.findByRole("dialog", { name: `Approve ${waiting.length} requests` });
    await user.click(within(dialog).getByRole("combobox", { name: "Organisation" }));
    await user.click(await screen.findByRole("option", { name: "Policy Lab" }));
    await user.click(within(dialog).getByRole("button", { name: "Approve" }));
    expect(await screen.findByText(new RegExp(`approved$`))).toBeInTheDocument();
    expect(opsMock.writes.filter((write) => write.path.endsWith("/approve"))).toHaveLength(waiting.length);
  });

  it("rejects a request without an email after a confirmation", async () => {
    const user = userEvent.setup();
    renderOps("/waitlist");
    await user.click(within(await screen.findByText("Ana Lopez", { selector: "button" }).then((b) => b.closest("tr") as HTMLElement)).getByRole("button", { name: "Reject" }));
    const dialog = await screen.findByRole("dialog", { name: "Reject Ana Lopez?" });
    expect(dialog).toHaveAccessibleDescription(
      "This will remove them from the waitlist. No account is created and no email is sent.",
    );
    await user.click(within(dialog).getByRole("button", { name: "Reject" }));
    expect(await screen.findByText("Ana Lopez rejected")).toBeInTheDocument();
    expect(opsMock.writes.at(-1)?.path).toMatch(/\/reject$/);
    await waitFor(() => expect(screen.queryByRole("button", { name: "Ana Lopez" })).toBeNull());
    // The record stays: Show rejected brings it back, greyed, with no actions.
    await user.click(screen.getByRole("button", { name: "Show rejected" }));
    expect(await within(await screen.findByText("Ana Lopez", { selector: "button" }).then((b) => b.closest("tr") as HTMLElement)).findByText(/^Rejected /)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Hide rejected" })).toHaveAttribute("aria-pressed", "true");
  });

  it("deletes a rejected request for good, and can still approve one", async () => {
    const user = userEvent.setup();
    renderOps("/waitlist");
    const rowOf = async (name: string) =>
      (await screen.findByText(name, { selector: "button" })).closest("tr") as HTMLElement;
    await user.click(within(await rowOf("Ana Lopez")).getByRole("button", { name: "Reject" }));
    await user.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Reject" }));
    await screen.findByText("Ana Lopez rejected");
    await user.click(screen.getByRole("button", { name: "Show rejected" }));
    const rejected = await rowOf("Ana Lopez");
    expect(within(rejected).getByRole("button", { name: "Approve" })).toBeInTheDocument();
    await user.click(within(rejected).getByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("dialog", { name: "Delete Ana Lopez's request?" });
    expect(dialog).toHaveAccessibleDescription(
      "This removes the request permanently. If they ask again, a new request appears here.",
    );
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));
    expect(await screen.findByText("Ana Lopez's request deleted")).toBeInTheDocument();
    expect(opsMock.writes.at(-1)).toMatchObject({ method: "DELETE" });
    await waitFor(() => expect(screen.queryByText("Ana Lopez", { selector: "button" })).toBeNull());
  });
});

