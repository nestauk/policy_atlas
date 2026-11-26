import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { authenticatedRouter, publicRouter } from "../../routes";
import { UnsubscribeView } from "./UnsubscribeView";

const TOKEN = "tok-123";
const BAD_LINK = /This link does not work/;

function arriveWith(search: string) {
  window.history.replaceState(null, "", `/unsubscribe${search}`);
}

function answer(status: number) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status }));
}

beforeEach(() => arriveWith(`?token=${TOKEN}`));

afterEach(() => {
  vi.restoreAllMocks();
  window.history.replaceState(null, "", "/");
});

describe("Unsubscribe page", () => {
  it("asks first and sends nothing on arrival", () => {
    const fetchSpy = answer(204);
    render(<UnsubscribeView />);

    expect(screen.getByRole("heading", { name: "Stop product updates?" })).toBeInTheDocument();
    expect(
      screen.getByText(
        "We still email you when there is something you must know about your account, for example planned downtime.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Unsubscribe" })).toBeEnabled();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("unsubscribes on the button, then subscribes again on the link", async () => {
    const user = userEvent.setup();
    const fetchSpy = answer(204);
    render(<UnsubscribeView />);

    await user.click(screen.getByRole("button", { name: "Unsubscribe" }));
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe(`/api/v1/unsubscribe?token=${TOKEN}`);
    expect(init).toMatchObject({ method: "POST", credentials: "omit" });
    expect(init).not.toHaveProperty("body");
    expect(init).not.toHaveProperty("headers");
    expect(
      await screen.findByRole("heading", { name: "You will get no more product updates" }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Changed your mind? Get product updates again" }));
    expect(fetchSpy).toHaveBeenCalledTimes(2);
    expect(fetchSpy.mock.calls[1][0]).toBe(`/api/v1/resubscribe?token=${TOKEN}`);
    expect(
      await screen.findByRole("heading", { name: "You will get product updates again" }),
    ).toBeInTheDocument();
  });

  it("shows busy and sends once when the button is pressed twice", async () => {
    const user = userEvent.setup();
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockReturnValue(new Promise(() => {}));
    render(<UnsubscribeView />);

    const button = screen.getByRole("button", { name: "Unsubscribe" });
    await user.click(button);
    await user.click(button);

    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it("shows the bad-link words and the address when the link has no token", () => {
    arriveWith("");
    const fetchSpy = answer(204);
    render(<UnsubscribeView />);

    expect(screen.getByRole("heading", { name: BAD_LINK })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "discoveryhub@nesta.org.uk" })).toHaveAttribute(
      "href",
      "mailto:discoveryhub@nesta.org.uk",
    );
    expect(screen.queryByRole("button", { name: "Unsubscribe" })).not.toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("shows the bad-link words when the server does not know the token", async () => {
    const user = userEvent.setup();
    answer(404);
    render(<UnsubscribeView />);

    await user.click(screen.getByRole("button", { name: "Unsubscribe" }));

    expect(await screen.findByRole("heading", { name: BAD_LINK })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "discoveryhub@nesta.org.uk" })).toHaveAttribute(
      "href",
      "mailto:discoveryhub@nesta.org.uk",
    );
  });

  it("says to try again and keeps the button when the server fails", async () => {
    const user = userEvent.setup();
    answer(500);
    render(<UnsubscribeView />);

    await user.click(screen.getByRole("button", { name: "Unsubscribe" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong. Try again.");
    expect(screen.getByRole("heading", { name: "Stop product updates?" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Unsubscribe" })).toBeEnabled();
  });

  it("takes the token out of the address bar when the page opens", () => {
    render(<UnsubscribeView />);

    expect(window.location.pathname).toBe("/unsubscribe");
    expect(window.location.search).toBe("");
  });

  it("sends no referrer while shown, and stops when the page goes", () => {
    const referrerMeta = () => document.head.querySelector('meta[name="referrer"]');
    const { unmount } = render(<UnsubscribeView />);

    expect(referrerMeta()).toHaveAttribute("content", "no-referrer");
    unmount();
    expect(referrerMeta()).toBeNull();
  });

  it.each([
    ["signed out", publicRouter],
    ["signed in", authenticatedRouter],
  ])("opens without sign-in from the %s routes", (_, router) => {
    const memory = createMemoryRouter(router.routes, { initialEntries: ["/unsubscribe"] });
    render(<RouterProvider router={memory} />);

    expect(screen.getByRole("heading", { name: "Stop product updates?" })).toBeInTheDocument();
  });
});
