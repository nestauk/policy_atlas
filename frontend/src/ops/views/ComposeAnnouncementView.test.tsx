import { cleanup, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { apiError, opsMock } from "../mock";
import { composeExample, countLine, renderOps, withOpsMock } from "../testing";

withOpsMock();
beforeEach(() => window.localStorage.clear());

async function openCompose() {
  const user = userEvent.setup();
  const router = renderOps("/announcements/new");
  await screen.findByRole("heading", { name: "New announcement" });
  return { user, router };
}

async function testedExample() {
  const opened = await openCompose();
  await composeExample(opened.user);
  await countLine(79);
  await opened.user.click(screen.getByRole("button", { name: "Send a test to me" }));
  expect(await screen.findByRole("status")).toHaveTextContent(/^Test sent to you at \d\d:\d\d$/);
  return opened;
}

describe("New announcement", () => {
  it("counts who gets it from the server's answer, which follows the kind", async () => {
    const { user } = await openCompose();
    await composeExample(user);
    expect(await countLine(79)).toBeInTheDocument();
    expect(screen.getByText(/82 chosen\. 3 left out: 2 unsubscribed from product updates, 1 deactivated\./)).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: /Service notice/ }));
    expect(await countLine(81)).toBeInTheDocument();
    expect(screen.getByText(/82 chosen\. 1 left out: 1 deactivated\./)).toBeInTheDocument();
    const kinds = opsMock.writes.filter((write) => write.path.endsWith("/recipients")).map((write) => (write.body as { kind: string }).kind);
    expect(kinds.at(-1)).toBe("service_notice");
  });

  it("keeps Check and send off until a test of the current text succeeded, and off again after an edit", async () => {
    const { user } = await openCompose();
    await composeExample(user);
    await countLine(79);
    const send = screen.getByRole("button", { name: "Check and send" });
    expect(send).toBeDisabled();
    expect(send).toHaveAccessibleDescription("You must send yourself a test before you can send.");
    await user.click(screen.getByRole("button", { name: "Send a test to me" }));
    expect(await screen.findByRole("status")).toHaveTextContent(/^Test sent to you at \d\d:\d\d$/);
    expect(send).toBeEnabled();
    await user.type(screen.getByRole("textbox", { name: "Subject" }), "!");
    expect(send).toBeDisabled();
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("puts a field rule from the server under its field", async () => {
    const { user } = await openCompose();
    await composeExample(user);
    await user.type(screen.getByRole("textbox", { name: "Button text (optional)" }), "Open");
    await user.type(screen.getByRole("textbox", { name: "Button link" }), "http://policyatlas.example");
    await user.click(screen.getByRole("button", { name: "Send a test to me" }));
    const link = screen.getByRole("textbox", { name: "Button link" });
    expect(await screen.findByText("The button link must start with https://.")).toBeInTheDocument();
    expect(link).toHaveAttribute("aria-invalid", "true");
    expect(link).toHaveAccessibleDescription("The button link must start with https://.");
    expect(screen.getByRole("button", { name: "Check and send" })).toBeDisabled();
  });

  it("opens the failure dialog with Try again when the test is not sent", async () => {
    const { user } = await openCompose();
    await composeExample(user);
    opsMock.override = (_method, path) =>
      path === "/api/v1/ops/announcements/test" ? apiError(502, "upstream_failed", "the test email was not sent (Throttling)") : undefined;
    await user.click(screen.getByRole("button", { name: "Send a test to me" }));
    const dialog = await screen.findByRole("dialog", { name: "The test email was not sent." });
    opsMock.override = undefined;
    await user.click(within(dialog).getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("status")).toHaveTextContent(/^Test sent to you at/);
  });

  it("sends only once the number is typed, then opens the result", async () => {
    const { user, router } = await testedExample();
    await user.click(screen.getByRole("button", { name: "Check and send" }));
    const dialog = await screen.findByRole("dialog", { name: "Send this email to 79 people?" });
    expect(dialog).toHaveTextContent("You cannot take an email back after you send it.");
    expect(dialog).toHaveTextContent("Spring pilot, Nesta, Tomás Ferreira");
    expect(dialog).toHaveTextContent("3 people: 2 unsubscribed from product updates, 1 deactivated.");
    const confirm = within(dialog).getByRole("button", { name: "Send to 79 people" });
    await user.type(within(dialog).getByLabelText("Type 79 to confirm"), "78");
    expect(confirm).toBeDisabled();
    await user.clear(within(dialog).getByLabelText("Type 79 to confirm"));
    await user.type(within(dialog).getByLabelText("Type 79 to confirm"), "79");
    await user.click(confirm);
    await screen.findByRole("heading", { name: "What's new: theory of change maps", level: 1 });
    expect(router.state.location.pathname).toMatch(/^\/announcements\/[0-9a-f-]+$/);
  });

  it("when the list changed, shows the new numbers and asks for the number again", async () => {
    const { user } = await testedExample();
    opsMock.listChangesOnNextSend = true;
    await user.click(screen.getByRole("button", { name: "Check and send" }));
    const dialog = await screen.findByRole("dialog", { name: "Send this email to 79 people?" });
    await user.type(within(dialog).getByLabelText("Type 79 to confirm"), "79");
    await user.click(within(dialog).getByRole("button", { name: "Send to 79 people" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "The list changed: it is now 79 people. Check it and confirm again.",
    );
    expect(within(dialog).getByLabelText("Type 79 to confirm")).toHaveValue("");
    expect(within(dialog).getByRole("button", { name: "Send to 79 people" })).toBeDisabled();
    const sends = () => opsMock.writes.filter((write) => write.path === "/api/v1/ops/announcements");
    const first = (sends()[0].body as { fingerprint: string }).fingerprint;
    await user.type(within(dialog).getByLabelText("Type 79 to confirm"), "79");
    await user.click(within(dialog).getByRole("button", { name: "Send to 79 people" }));
    await screen.findByRole("heading", { name: "What's new: theory of change maps", level: 1 });
    expect((sends()[1].body as { fingerprint: string }).fingerprint).not.toBe(first);
  });

  it("keeps the unsent text when the page is opened again", async () => {
    const { user } = await openCompose();
    await user.click(screen.getByRole("radio", { name: /Service notice/ }));
    await user.type(screen.getByRole("textbox", { name: "Subject" }), "Planned downtime");
    cleanup();
    await openCompose();
    expect(screen.getByRole("textbox", { name: "Subject" })).toHaveValue("Planned downtime");
    expect(screen.getByRole("radio", { name: /Service notice/ })).toHaveAttribute("aria-checked", "true");
  });
});
