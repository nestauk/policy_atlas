import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { apiError, mockOpsAuth, opsMock } from "./mock";
import { renderOps, withOpsMock } from "./testing";

withOpsMock();

describe("the ops shell", () => {
  it("says Loading… while the first call is out, and nothing else", async () => {
    renderOps("/people");
    const main = screen.getByRole("main");
    expect(within(main).getByRole("status")).toHaveTextContent("Loading…");
    expect(main).toHaveTextContent(/^Loading…$/);
    expect(await screen.findByRole("heading", { name: "People" })).toBeInTheDocument();
  });

  it("has its own top bar: the Ops chip, the three sections, the waiting count and the way back", async () => {
    renderOps("/people");
    const nav = screen.getByRole("navigation");
    expect(within(nav).getByText("Ops")).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "People" })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Organisations" })).toBeInTheDocument();
    // One request is waiting in the fixtures.
    expect(await within(nav).findByRole("link", { name: "Requests 1" })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Back to Policy Atlas" })).toBeInTheDocument();
    expect(within(nav).queryByText(/New|Tasks|Projects/)).toBeNull();
    // The signed-in person's initials (Priya Shah).
    expect(await within(nav).findByRole("button", { name: "Account" })).toHaveTextContent("PS");
  });

  it("on a 403 shows exactly the two sentences, with no retry", async () => {
    opsMock.override = () => apiError(403, "forbidden", "your account does not have the ops role");
    renderOps("/people");
    const main = screen.getByRole("main");
    expect(await within(main).findByText("Your account does not have the ops role.")).toBeInTheDocument();
    expect(within(main).getByText("Ask an operator to grant it from the command line.")).toBeInTheDocument();
    expect(main).toHaveTextContent(
      /^Your account does not have the ops role\.Ask an operator to grant it from the command line\.$/,
    );
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
    expect(screen.queryByRole("link", { name: "People" })).toBeNull();
  });

  it("signed out, shows one Sign in button", async () => {
    const signIn = vi.fn();
    renderOps("/people", { ...mockOpsAuth, status: "unauthenticated", user: null, signIn });
    const main = screen.getByRole("main");
    const button = within(main).getByRole("button", { name: "Sign in" });
    expect(main).toHaveTextContent(/^Sign in$/);
    button.click();
    expect(signIn).toHaveBeenCalled();
  });

  it("shows Sign in when the call is still 401 after the refresh", async () => {
    opsMock.override = () => apiError(401, "unauthenticated", "authentication is required");
    renderOps("/people", { ...mockOpsAuth, getAccessToken: async () => "expired" });
    expect(await screen.findByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });

  it("sends / to /people", async () => {
    const router = renderOps("/");
    expect(await screen.findByRole("heading", { name: "People" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/people");
  });
});
