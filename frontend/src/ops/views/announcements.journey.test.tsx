import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { opsMock } from "../mock";
import { composeExample, countLine, renderOps, withOpsMock } from "../testing";

/*
 * The design annex's five scenes, played end to end against the ops mock:
 * the list; compose, whose count follows the kind; the test that unlocks
 * the send; the confirm dialog and the list changing under it; the result
 * page and its retry. The email shows in the compose preview.
 */

withOpsMock();
beforeEach(() => window.localStorage.clear());

describe("sending an announcement", () => {
  it("plays the five scenes", async () => {
    const user = userEvent.setup();
    renderOps("/announcements");

    // 1. The list, with three sent announcements.
    await user.click(await within(screen.getByRole("navigation")).findByRole("link", { name: "Announcements" }));
    const list = await screen.findByRole("table", { name: "Announcements" });
    expect(within(list).getAllByRole("row")).toHaveLength(4);
    await user.click(screen.getByRole("link", { name: "New announcement" }));

    // 2. Compose: the count follows the kind, and so does the email's footer.
    await screen.findByRole("heading", { name: "New announcement" });
    await composeExample(user);
    expect(await countLine(79)).toBeInTheDocument();
    const preview = screen.getByRole("region", { name: /Preview/ });
    expect(preview).toHaveTextContent("Unsubscribe from product updates");
    await user.click(screen.getByRole("radio", { name: /Service notice/ }));
    expect(await countLine(81)).toBeInTheDocument();
    expect(preview).toHaveTextContent("This is a service notice about your account.");
    await user.click(screen.getByRole("radio", { name: /Product update/ }));
    expect(await countLine(79)).toBeInTheDocument();

    // The send waits for a test of the current text.
    const checkAndSend = screen.getByRole("button", { name: "Check and send" });
    expect(checkAndSend).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Send a test to me" }));
    expect(await screen.findByRole("status")).toHaveTextContent(/^Test sent to you at/);
    expect(checkAndSend).toBeEnabled();
    await user.type(screen.getByRole("textbox", { name: "Message" }), " Reply with questions.");
    expect(checkAndSend).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Send a test to me" }));
    await waitFor(() => expect(checkAndSend).toBeEnabled());

    // 3. The confirm dialog for 79 people; the list changes before the send.
    opsMock.listChangesOnNextSend = true;
    await user.click(checkAndSend);
    const dialog = await screen.findByRole("dialog", { name: "Send this email to 79 people?" });
    await user.type(within(dialog).getByLabelText("Type 79 to confirm"), "79");
    await user.click(within(dialog).getByRole("button", { name: "Send to 79 people" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "The list changed: it is now 79 people. Check it and confirm again.",
    );
    await user.type(within(dialog).getByLabelText("Type 79 to confirm"), "79");
    await user.click(within(dialog).getByRole("button", { name: "Send to 79 people" }));

    // 4. The result page: 77 sent, 2 failed, 3 left out; then the retry.
    await screen.findByRole("heading", { name: "What's new: theory of change maps", level: 1 });
    const summary = screen.getByRole("region", { name: "Result" });
    expect(summary).toHaveTextContent(/77 sent.*2 failed.*3 left out/);
    await user.click(within(summary).getByRole("button", { name: "Try the 2 failed again" }));
    await waitFor(() => expect(summary).toHaveTextContent(/^79 sent3 left out/));

    // The list now starts with it, and the unsent text is gone.
    await user.click(within(screen.getByRole("main")).getByRole("link", { name: "Announcements" }));
    const after = await screen.findByRole("table", { name: "Announcements" });
    expect(within(after).getAllByRole("row")[1]).toHaveTextContent(/What's new: theory of change maps.*You.*79 sent$/);
    expect(window.localStorage.length).toBe(0);
  });
});
