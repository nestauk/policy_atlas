import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { opsMock } from "../mock";
import { DHSC, DHSC_PILOT, LINK_ACTIVE } from "../mock/fixtures";
import { pick, renderOps, withOpsMock } from "../testing";

withOpsMock();

function row(label: string) {
  return screen.getByRole("cell", { name: label }).closest("tr") as HTMLElement;
}

/** A local day `days` from today, as a date field holds it. */
function dayFromToday(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() + days);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

async function openMenu(user: ReturnType<typeof userEvent.setup>, label: string, item: string) {
  await user.click(screen.getByRole("button", { name: `Actions for ${label}` }));
  await user.click(await screen.findByRole("menuitem", { name: item }));
}

describe("Invite links", () => {
  it("lists each link with its uses, domains and status; a revoked link offers Copy link only", async () => {
    const user = userEvent.setup();
    renderOps("/invite-links");
    await screen.findByRole("heading", { name: "Invite links" });
    expect(screen.getByRole("link", { name: "Invite links" })).toHaveAttribute("href", "/invite-links");
    const active = row("DHSC pilot");
    expect(active).toHaveTextContent("DHSC pilot 2027");
    expect(active).toHaveTextContent("dhsc.exampleukhsa.example");
    expect(active).toHaveTextContent("63 of 120");
    expect(within(active).getByText("ACTIVE")).toBeInTheDocument();
    expect(within(row("Treasury workshop")).getByText("FULL")).toBeInTheDocument();
    expect(within(row("Autumn test")).getByText("EXPIRED")).toBeInTheDocument();
    await user.click(within(row("Old pilot")).getByRole("button", { name: "Actions for Old pilot" }));
    expect((await screen.findAllByRole("menuitem")).map((item) => item.textContent)).toEqual(["Copy link"]);
  });

  it("creates a link that works to the end of the chosen day, then shows it to copy", async () => {
    const user = userEvent.setup();
    renderOps("/invite-links");
    await user.click(await screen.findByRole("button", { name: "Create link" }));
    const dialog = await screen.findByRole("dialog", { name: "Create invite link" });
    await user.type(within(dialog).getByLabelText("Label"), "Spring pilot");
    await pick(user, "Organisation", "DHSC");
    await user.click(within(dialog).getByRole("button", { name: /^Cohorts/ }));
    await user.click(await screen.findByRole("checkbox", { name: "DHSC pilot 2027" }));
    await user.keyboard("{Escape}");
    await user.type(within(dialog).getByLabelText("Email domains"), "dhsc.example{Enter}ukhsa.example");
    await user.type(within(dialog).getByLabelText("Maximum uses"), "120");
    const day = dayFromToday(30);
    fireEvent.change(within(dialog).getByLabelText("Expires on"), { target: { value: day } });
    await user.click(within(dialog).getByRole("button", { name: "Create link" }));

    const created = await screen.findByRole("dialog", { name: "Invite link created" });
    const body = opsMock.writes.at(-1)?.body as Record<string, unknown>;
    expect(body).toMatchObject({
      label: "Spring pilot",
      org_id: DHSC,
      cohort_ids: [DHSC_PILOT],
      allowed_domains: ["dhsc.example", "ukhsa.example"],
      max_uses: 120,
    });
    expect(body.expires_at).toMatch(new RegExp(`^${day}T23:59:59[+-]\\d\\d:\\d\\d$`));
    const url = opsMock.inviteLinks.at(-1)?.url ?? "";
    expect(url).toMatch(/#invite=[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$/);
    expect(within(created).getByText(url)).toBeInTheDocument();
    expect(created).toHaveTextContent(
      "Anyone with this link and an address at one of these domains can get an account. Share it only with the group.",
    );
    await user.click(within(created).getByRole("button", { name: "Copy link" }));
    expect(await screen.findByText("Link copied")).toBeInTheDocument();
    expect(await navigator.clipboard.readText()).toBe(url);
  });

  it("shows the server's refusal in the create dialog", async () => {
    const user = userEvent.setup();
    renderOps("/invite-links");
    await user.click(await screen.findByRole("button", { name: "Create link" }));
    const dialog = await screen.findByRole("dialog", { name: "Create invite link" });
    await user.type(within(dialog).getByLabelText("Label"), "Spring pilot");
    await pick(user, "Organisation", "DHSC");
    await user.type(within(dialog).getByLabelText("Email domains"), "dhsc.example{Enter}ana@dhsc.example");
    await user.type(within(dialog).getByLabelText("Maximum uses"), "120");
    fireEvent.change(within(dialog).getByLabelText("Expires on"), { target: { value: dayFromToday(30) } });
    await user.click(within(dialog).getByRole("button", { name: "Create link" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "Line 2: enter a domain such as dhsc.gov.uk, with no @.",
    );
  });

  it("copies a link from its row without the code in the toast", async () => {
    const user = userEvent.setup();
    renderOps("/invite-links");
    await screen.findByRole("heading", { name: "Invite links" });
    await openMenu(user, "DHSC pilot", "Copy link");
    expect(await screen.findByText("Link copied")).toBeInTheDocument();
    expect(await navigator.clipboard.readText()).toBe("https://policy-atlas.example/#invite=K7Q2-M9XD-3FHP");
    expect(screen.queryByText(/K7Q2/)).toBeNull();
  });

  it("edits a link's maximum uses, and refuses a maximum below its uses", async () => {
    const user = userEvent.setup();
    renderOps("/invite-links");
    await screen.findByRole("heading", { name: "Invite links" });
    await openMenu(user, "DHSC pilot", "Edit…");
    const dialog = await screen.findByRole("dialog", { name: "Edit DHSC pilot" });
    expect(dialog).toHaveTextContent("To change these, revoke this link and create a new one.");
    const maxUses = within(dialog).getByLabelText("Maximum uses");
    await user.clear(maxUses);
    await user.type(maxUses, "10");
    await user.click(within(dialog).getByRole("button", { name: "Save" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "This link already has 63 uses. The maximum cannot be lower.",
    );
    await user.clear(maxUses);
    await user.type(maxUses, "200");
    await user.click(within(dialog).getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Saved DHSC pilot")).toBeInTheDocument();
    expect(opsMock.writes.at(-1)).toMatchObject({
      path: `/api/v1/ops/invite-links/${LINK_ACTIVE}`,
      body: { label: "DHSC pilot", max_uses: 200 },
    });
    await waitFor(() => expect(row("DHSC pilot")).toHaveTextContent("63 of 200"));
  });

  it("revokes a link after a confirmation that the accounts it made stay", async () => {
    const user = userEvent.setup();
    renderOps("/invite-links");
    await screen.findByRole("heading", { name: "Invite links" });
    await openMenu(user, "DHSC pilot", "Revoke…");
    const dialog = await screen.findByRole("dialog", { name: "Revoke DHSC pilot?" });
    expect(dialog).toHaveAccessibleDescription(
      "People who use the link after this get no account through it. The 63 accounts already made stay.",
    );
    await user.click(within(dialog).getByRole("button", { name: "Revoke link" }));
    expect(await screen.findByText("Revoked DHSC pilot")).toBeInTheDocument();
    expect(opsMock.writes.at(-1)?.path).toBe(`/api/v1/ops/invite-links/${LINK_ACTIVE}/revoke`);
    expect(await within(row("DHSC pilot")).findByText("REVOKED")).toBeInTheDocument();
  });
});
