import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { opsMock } from "../mock";
import { renderOps, withOpsMock } from "../testing";

withOpsMock();

const rows = () => screen.getAllByRole("row").slice(1);

describe("Announcements", () => {
  it("lists every email sent, newest first, with who sent it and its result", async () => {
    renderOps("/announcements");
    await screen.findByRole("heading", { name: "Announcements" });
    expect(screen.getByText("Email people who have an account. Every email you send is recorded here.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "New announcement" })).toHaveAttribute("href", "/announcements/new");
    expect(rows().map((row) => within(row).getAllByRole("cell")[0].textContent)).toEqual([
      "What's new: theory of change maps",
      "Your pilot starts on Monday",
      "Sign-in now needs an authenticator app",
    ]);
    expect(rows()[0]).toHaveTextContent(/Product update.*Spring pilot, Nesta, 1 person.*You.*77 sent · 2 failed/);
    expect(rows()[1]).toHaveTextContent(/Service notice.*Spring pilot.*Ana Ruiz.*17 sent$/);
  });

  it("says Sending: N of M while rows wait", async () => {
    const [first] = opsMock.announcements;
    first.created_at = new Date().toISOString();
    first.recipients = first.recipients.map((row, index) => (index < 10 && row.status === "sent" ? { ...row, status: "pending" } : row));
    renderOps("/announcements");
    await screen.findByRole("heading", { name: "Announcements" });
    expect(rows()[0]).toHaveTextContent("Sending: 67 of 79");
  });

  it("says so when nothing was sent yet", async () => {
    opsMock.announcements = [];
    renderOps("/announcements");
    expect(await screen.findByText("No announcements yet.")).toBeInTheDocument();
  });
});
