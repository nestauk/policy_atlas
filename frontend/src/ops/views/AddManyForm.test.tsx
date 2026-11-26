import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { apiError, opsMock } from "../mock";
import { pick, renderOps, withOpsMock } from "../testing";

withOpsMock();

async function chooseFile(csv: string) {
  const user = userEvent.setup();
  const router = renderOps("/people/new");
  await user.click(await screen.findByRole("button", { name: "Many from a file" }));
  await user.upload(screen.getByLabelText("File"), new File([csv], "pilot.csv", { type: "text/csv" }));
  return { user, router };
}

/** The counts line, read whole: its figures sit in their own spans, and each dot binds with a no-break space. */
const findLine = (text: string) =>
  screen.findByText((_, node) => node?.tagName === "P" && node.textContent?.replace(/\s/g, " ") === text);

const createdEmails = () =>
  opsMock.writes.filter((write) => write.path === "/api/v1/ops/people").map((write) => (write.body as { email: string }).email);

describe("Add many from a file", () => {
  it("lists the file's problems and keeps Create off while there are any", async () => {
    await chooseFile("email,name\nana@dhsc.example,Ana\nnot-an-address,Bo\nana@dhsc.example,Ana again\n");
    const problems = await screen.findByRole("alert");
    expect(problems).toHaveTextContent("This file has 2 problems. Correct the file and choose it again.");
    expect(within(problems).getByText("Line 3: this is not an email address.")).toBeInTheDocument();
    expect(within(problems).getByText("Line 4: this email is already on line 2.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create accounts and send invitations" })).toBeDisabled();
    expect(createdEmails()).toEqual([]);
  });

  it("creates each person in file order through the one-person route and counts the outcomes", async () => {
    const { user, router } = await chooseFile(
      "name,email\nNew Person,new.person@nesta.org.uk\nSam Holt,sam.holt@example.com\nJon Reyes,jon.reyes@policylab.example\n",
    );
    await pick(user, "Organisation", "Nesta");
    expect(await screen.findByText("3 people are ready to add to Nesta.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Create 3 accounts and send invitations" }));
    expect(
      await findLine("1 invited · 1 added, no email · 1 already in another organisation · 0 failed"),
    ).toBeInTheDocument();
    expect(createdEmails()).toEqual(["new.person@nesta.org.uk", "sam.holt@example.com", "jon.reyes@policylab.example"]);
    const notAdded = screen.getByRole("table");
    expect(within(notAdded).getByText("Already in another organisation (Policy Lab). Not tried again.")).toBeInTheDocument();
    expect(within(notAdded).queryByText("new.person@nesta.org.uk")).toBeNull();
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Done" }));
    expect(router.state.location.pathname).toBe("/people");
  });

  it("tries again only the people whose call got no answer or a server error, never a refused one", async () => {
    let outage = true;
    opsMock.override = (method, path, body) => {
      if (method !== "POST" || path !== "/api/v1/ops/people") return undefined;
      const email = (body as { email: string }).email;
      if (email === "down@nesta.org.uk" && outage) return apiError(503, "unavailable", "");
      if (email === "refused@nesta.org.uk") return apiError(409, "ops_refused", "this address cannot be used");
      return undefined;
    };
    const { user } = await chooseFile(
      "email,name\ndown@nesta.org.uk,Dee Down\nrefused@nesta.org.uk,Ray Fused\nfine@nesta.org.uk,Fin Fine\n",
    );
    await pick(user, "Organisation", "Nesta");
    await user.click(await screen.findByRole("button", { name: "Create 3 accounts and send invitations" }));
    expect(
      await findLine("1 invited · 0 added, no email · 0 already in another organisation · 1 refused · 1 failed"),
    ).toBeInTheDocument();
    expect(screen.getByText("This address cannot be used.")).toBeInTheDocument();
    expect(screen.getByText("The server had an error. You can try again.")).toBeInTheDocument();

    outage = false;
    opsMock.writes = [];
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(
      await findLine("2 invited · 0 added, no email · 0 already in another organisation · 1 refused · 0 failed"),
    ).toBeInTheDocument();
    expect(createdEmails()).toEqual(["down@nesta.org.uk"]);
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });
});
