import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

  it("has its own top bar: the OPS chip, the three sections, the waiting count and the account icon", async () => {
    renderOps("/people");
    const nav = screen.getByRole("navigation");
    expect(within(nav).getByText("OPS")).toBeInTheDocument();
    expect(await within(nav).findByRole("link", { name: "People" })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Organisations" })).toBeInTheDocument();
    // One request is waiting in the fixtures.
    expect(await within(nav).findByRole("link", { name: "Waitlist, 1 waiting" })).toBeInTheDocument();
    expect(within(nav).queryByRole("link", { name: "Back to Policy Atlas" })).toBeNull();
    expect(within(nav).queryByText(/New|Tasks|Projects/)).toBeNull();
    // The account icon opens who is signed in (Priya Shah).
    await userEvent.setup().click(await within(nav).findByRole("button", { name: "Account" }));
    expect(await screen.findByText("Priya Shah", { selector: "p" })).toBeInTheDocument();
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
    // A way out all the same: the account menu with Sign out.
    await userEvent.setup().click(screen.getByRole("button", { name: "Account" }));
    expect(await screen.findByRole("menuitem", { name: "Sign out" })).toBeInTheDocument();
  });

  it("does not show the sections until the first call answers", () => {
    renderOps("/people");
    expect(within(screen.getByRole("navigation")).queryByRole("link", { name: "People" })).toBeNull();
  });

  it("signed out, shows one Sign in button at the top bar's right", async () => {
    const signIn = vi.fn();
    renderOps("/people", { ...mockOpsAuth, status: "unauthenticated", user: null, signIn });
    const button = within(screen.getByRole("navigation")).getByRole("button", { name: "Sign in" });
    expect(screen.getByRole("main")).toBeEmptyDOMElement();
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
