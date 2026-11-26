import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AnnouncementDetail, AnnouncementResult } from "../api";
import { json, opsMock } from "../mock";
import { renderOps, withOpsMock } from "../testing";

withOpsMock();
afterEach(() => vi.useRealTimers());

const ID = "00000000-0000-4000-8000-0000000000aa";
const PATH = `/api/v1/ops/announcements/${ID}`;

function row(name: string, status: AnnouncementResult["status"], reason: string | null = null, overlay: AnnouncementResult["overlay"] = null): AnnouncementResult {
  return { user_id: `sub-${name}`, name, email: `${name.toLowerCase()}@example.org`, organisation: "Nesta", status, reason, overlay };
}

function detail(recipients: AnnouncementResult[], minutesAgo: number, more: Partial<AnnouncementDetail> = {}): AnnouncementDetail {
  const counts = { pending: 0, sending: 0, sent: 0, failed: 0, left_out: 0 };
  for (const each of recipients) counts[each.status] += 1;
  return {
    announcement_id: ID,
    subject: "Planned downtime",
    kind: "service_notice",
    audience_summary: "Everyone",
    sent_by_name: "Ana Ruiz",
    created_at: new Date(Date.now() - minutesAgo * 60_000).toISOString(),
    counts,
    body: "We are down on Sunday.",
    button_label: null,
    button_url: null,
    image_url: "https://policyatlas.example/email-images/map.png",
    image_alt: "A map of the outage",
    recipients,
    suppression_unreadable: false,
    ...more,
  };
}

const resultOf = (name: string) =>
  within(screen.getAllByRole("row").find((element) => element.textContent?.startsWith(name)) as HTMLElement).getAllByRole("cell")[3];

describe("an announcement's result", () => {
  it("says each person's result in words, beside a mark", async () => {
    const answer = detail(
      [
        row("Ada", "sent"),
        row("Ben", "sent", null, "bounced"),
        row("Cy", "sent", null, "marked_as_spam"),
        row("Dee", "failed", "MessageRejected"),
        row("Eve", "failed", "Throttling"),
        row("Fox", "failed", "AccountSendingPausedException"),
        row("Gil", "failed", "SomethingElse"),
        row("Hal", "left_out", "not_signed_in"),
        row("Ida", "left_out", "suppressed_complaint"),
        row("Jo", "sending"),
      ],
      10,
      { suppression_unreadable: true },
    );
    opsMock.override = (method, path) => (method === "GET" && path === PATH ? json(answer) : undefined);
    renderOps(`/announcements/${ID}`);
    await screen.findByRole("heading", { name: "Planned downtime", level: 1 });
    expect(screen.getByText(/^Service notice · Sent by Ana Ruiz · .* · To Everyone$/)).toBeInTheDocument();
    expect(screen.getByText("We could not check for bounces just now.")).toBeInTheDocument();
    expect(
      ["Ada", "Ben", "Cy", "Dee", "Eve", "Fox", "Gil", "Hal", "Ida", "Jo"].map((name) => resultOf(name).textContent),
    ).toEqual([
      "Sent",
      "Bounced: the address does not exist",
      "Marked as spam",
      "Failed: the mail service refused the email",
      "Failed: the mail service was busy",
      "Failed: sending is paused for this account",
      "Failed: the email could not be sent",
      "Left out: has not signed in yet",
      "Left out: marked our email as spam",
      "Not confirmed",
    ]);
    expect(within(resultOf("Ada")).getByText("", { selector: "[data-tone='green']" })).toBeInTheDocument();
  });

  it("reads again every 3 seconds while people wait, offers no retry meanwhile, and stops when nothing waits", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const waiting = detail([row("Ada", "pending"), row("Ben", "sending"), row("Cy", "failed", "Throttling")], 0);
    const done = detail([row("Ada", "sent"), row("Ben", "sent"), row("Cy", "failed", "Throttling")], 0);
    let reads = 0;
    opsMock.override = (method, path) => {
      if (method !== "GET" || path !== PATH) return undefined;
      reads += 1;
      return json(reads === 1 ? waiting : done);
    };
    renderOps(`/announcements/${ID}`);
    await screen.findByRole("heading", { name: "Planned downtime", level: 1 });
    expect(resultOf("Ada")).toHaveTextContent("Waiting");
    expect(resultOf("Ben")).toHaveTextContent("Sending");
    expect(screen.getByRole("region", { name: "Result" })).toHaveTextContent("2 waiting");
    expect(screen.queryByRole("button", { name: /failed again/ })).toBeNull();
    await act(() => vi.advanceTimersByTimeAsync(3000));
    expect(await screen.findByRole("button", { name: "Try the 1 failed again" })).toBeInTheDocument();
    expect(resultOf("Ada")).toHaveTextContent("Sent");
    await act(() => vi.advanceTimersByTimeAsync(10_000));
    expect(reads).toBe(2);
  });

  it("tries the failed again, and they turn to sent", async () => {
    const user = userEvent.setup();
    renderOps(`/announcements/${opsMock.announcements[0].announcement_id}`);
    const summary = await screen.findByRole("region", { name: "Result" });
    expect(summary).toHaveTextContent(/77 sent.*2 failed.*3 left out/);
    expect(summary).toHaveTextContent("“Sent” means the mail service accepted the email. We do not track who opens it.");
    await user.click(within(summary).getByRole("button", { name: "Try the 2 failed again" }));
    await waitFor(() => expect(summary).toHaveTextContent(/^79 sent3 left out/));
    expect(within(summary).queryByRole("button", { name: /failed again/ })).toBeNull();
    expect(opsMock.writes.at(-1)?.path).toMatch(/\/retry$/);
  });

  it("filters the table to one result", async () => {
    const user = userEvent.setup();
    renderOps(`/announcements/${opsMock.announcements[0].announcement_id}`);
    await screen.findByRole("region", { name: "Result" });
    await user.click(screen.getByRole("button", { name: "Left out" }));
    expect(screen.getAllByRole("row").slice(1).map((each) => within(each).getAllByRole("cell")[0].textContent)).toEqual([
      "Kwame Osei",
      "Marta Nowak",
      "Sofia Lindqvist",
    ]);
  });

  it("shows the message that was sent, with the picture's description in place of the picture", async () => {
    const user = userEvent.setup();
    renderOps(`/announcements/${opsMock.announcements[0].announcement_id}`);
    await screen.findByRole("region", { name: "Result" });
    await user.click(screen.getByRole("button", { name: "Show the message that was sent" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("img", { name: "A theory of change map with five linked boxes" })).not.toHaveAttribute("src");
    expect(dialog).toHaveTextContent("Unsubscribe from product updates");
    expect(dialog).toHaveTextContent("Questions? Reply to this email or write to discoveryhub@nesta.org.uk.");
  });
});
