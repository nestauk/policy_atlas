import { act, fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { apiError, opsMock, opsMockFetch } from "../mock";
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

/**
 * Answer through the mock, but hold each write `matches` picks until the test
 * releases it. Returns the release of each held call, in order, and every
 * create call the page sent (held or not).
 */
function holdCalls(matches: (path: string, body: string) => boolean) {
  const held: Array<() => void> = [];
  const creates: string[] = [];
  vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = new Request(input, init);
    const path = new URL(request.url).pathname;
    if (request.method === "GET") return opsMockFetch(request);
    const body = await request.clone().text();
    if (path === "/api/v1/ops/people") creates.push(body);
    if (matches(path, body)) await new Promise<void>((go) => held.push(go));
    return opsMockFetch(request);
  });
  return { held, creates };
}

/** Let late answers land: the in-memory calls settle well within this. */
const settle = () => act(() => new Promise((done) => setTimeout(done, 50)));

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

  it("shows the file chosen last, even when an earlier file's check answers after it", async () => {
    const { held } = holdCalls((path) => path === "/api/v1/ops/people/import-check");
    renderOps("/people/new");
    await userEvent.setup().click(await screen.findByRole("button", { name: "Many from a file" }));
    const chooser = screen.getByLabelText("File");
    const choose = (csv: string) =>
      fireEvent.change(chooser, { target: { files: [new File([csv], "pilot.csv", { type: "text/csv" })] } });
    choose("email,name\nfirst@nesta.org.uk,First File\n");
    await vi.waitFor(() => expect(held).toHaveLength(1));
    choose("email,name\nsecond@nesta.org.uk,Second File\n");
    await vi.waitFor(() => expect(held).toHaveLength(2));
    held[1]();
    expect(await screen.findByText("second@nesta.org.uk")).toBeInTheDocument();
    held[0]();
    await settle();
    expect(screen.getByText("second@nesta.org.uk")).toBeInTheDocument();
    expect(screen.queryByText("first@nesta.org.uk")).toBeNull();
  });

  it("never turns a deactivated person back on: counts and lists them, and Try again leaves them out", async () => {
    let outage = true;
    opsMock.override = (method, path, body) =>
      method === "POST" && path === "/api/v1/ops/people" && (body as { email: string }).email === "down@nesta.org.uk" && outage
        ? apiError(503, "unavailable", "")
        : undefined;
    const { user } = await chooseFile("email,name\nada.quinn@example.org,Ada Quinn\ndown@nesta.org.uk,Dee Down\n");
    await pick(user, "Organisation", "Nesta");
    await user.click(await screen.findByRole("button", { name: "Create 2 accounts and send invitations" }));
    expect(
      await findLine("0 invited · 0 added, no email · 0 already in another organisation · 1 deactivated · 1 failed"),
    ).toBeInTheDocument();
    const sent = opsMock.writes.filter((write) => write.path === "/api/v1/ops/people").map((write) => write.body);
    expect(sent).toEqual([expect.objectContaining({ reactivate: false }), expect.objectContaining({ reactivate: false })]);
    expect(
      within(screen.getByRole("table")).getByText("Deactivated. To turn this person back on, add them with One person."),
    ).toBeInTheDocument();

    outage = false;
    opsMock.writes = [];
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(
      await findLine("1 invited · 0 added, no email · 0 already in another organisation · 1 deactivated · 0 failed"),
    ).toBeInTheDocument();
    expect(createdEmails()).toEqual(["down@nesta.org.uk"]);
  });

  it("while people are being added, says how far it is and keeps the switch from dropping the run", async () => {
    const { held } = holdCalls((path) => path === "/api/v1/ops/people");
    const { user } = await chooseFile("email,name\none@nesta.org.uk,One\ntwo@nesta.org.uk,Two\n");
    await pick(user, "Organisation", "Nesta");
    await user.click(await screen.findByRole("button", { name: "Create 2 accounts and send invitations" }));
    expect(await findLine("Adding people: 0 of 2.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "One person" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Many from a file" })).toBeDisabled();
    held[0]();
    expect(await findLine("Adding people: 1 of 2.")).toBeInTheDocument();
    await vi.waitFor(() => expect(held).toHaveLength(2));
    held[1]();
    expect(await findLine("2 invited · 0 added, no email · 0 already in another organisation · 0 failed")).toHaveFocus();
    expect(screen.getByRole("button", { name: "One person" })).toBeEnabled();
  });

  it("asks before moving to another page during a run, and a confirmed move adds no one else", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const { held, creates } = holdCalls((path) => path === "/api/v1/ops/people");
    const { user, router } = await chooseFile(
      "email,name\none@nesta.org.uk,One\ntwo@nesta.org.uk,Two\nthree@nesta.org.uk,Three\n",
    );
    await pick(user, "Organisation", "Nesta");
    await user.click(await screen.findByRole("button", { name: "Create 3 accounts and send invitations" }));
    await vi.waitFor(() => expect(held).toHaveLength(1));
    await user.click(screen.getByRole("link", { name: "Cohorts" }));
    expect(confirm).toHaveBeenCalledWith(
      "People are still being added. If you leave now, the rest are not added. Leave this page?",
    );
    expect(router.state.location.pathname).toBe("/cohorts");
    held[0]();
    await settle();
    expect(creates).toHaveLength(1);
  });
});
