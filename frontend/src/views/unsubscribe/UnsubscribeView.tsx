import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { apiBaseUrl } from "../../api/client";
import { buttonVariants } from "../../ui/brand/Button";
import { Card } from "../../ui/brand/Card";
import { cn } from "../../ui/brand/cn";
import { LINK_CLASS, PROSE_LINK_CLASS } from "../../ui/brand/inlineActions";
import { NavLogo } from "../../ui/brand/Nav";

/** Where a person writes when their link does not work. */
const CONTACT_ADDRESS = "discoveryhub@nesta.org.uk";

const SERVICE_EMAIL_LINE =
  "We still email you when there is something you must know about your account, for example planned downtime.";

type Stage = "arrive" | "unsubscribed" | "resubscribed" | "bad";
type Answer = "done" | "bad" | "failed";

/**
 * Switch product updates off or on for the person the token names. Public:
 * no sign-in, no cookie, no body. A 404 means the token is unknown or
 * badly formed.
 */
async function sendChoice(action: "unsubscribe" | "resubscribe", token: string): Promise<Answer> {
  try {
    const response = await fetch(
      `${apiBaseUrl()}/api/v1/${action}?token=${encodeURIComponent(token)}`,
      { method: "POST", credentials: "omit", referrerPolicy: "no-referrer" },
    );
    if (response.ok) return "done";
    return response.status === 404 ? "bad" : "failed";
  } catch {
    return "failed";
  }
}

/**
 * The page an email's unsubscribe link opens, at `/unsubscribe?token=…`.
 *
 * Arriving changes nothing, because mail scanners open links: only the
 * button sends. The token is a secret in the address, so the page reads it
 * once, takes it out of the address bar and sends no referrer while shown.
 * A reload therefore shows the bad-link state.
 */
export function UnsubscribeView() {
  const [token] = useState(() => new URLSearchParams(window.location.search).get("token") || null);
  const [stage, setStage] = useState<Stage>(token === null ? "bad" : "arrive");
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const actionRef = useRef<HTMLButtonElement>(null);

  useLayoutEffect(() => {
    if (window.location.search !== "" || window.location.hash !== "") {
      window.history.replaceState(window.history.state, "", window.location.pathname);
    }
    const referrer = document.createElement("meta");
    referrer.name = "referrer";
    referrer.content = "no-referrer";
    document.head.append(referrer);
    return () => referrer.remove();
  }, []);

  // The control was disabled while busy, which drops its focus: give it back.
  useEffect(() => {
    if (failed) actionRef.current?.focus();
  }, [failed]);

  const choose = async (action: "unsubscribe" | "resubscribe") => {
    if (token === null || busy) return;
    setBusy(true);
    setFailed(false);
    const answer = await sendChoice(action, token);
    setBusy(false);
    if (answer === "failed") {
      setFailed(true);
      return;
    }
    setStage(answer === "bad" ? "bad" : action === "unsubscribe" ? "unsubscribed" : "resubscribed");
    // The control that was pressed is gone; the new heading says what happened.
    headingRef.current?.focus();
  };

  const heading = {
    arrive: "Stop product updates?",
    unsubscribed: "You will get no more product updates",
    resubscribed: "You will get product updates again",
    bad: "This link does not work",
  }[stage];

  const failure = failed && (
    <p role="alert" className="mt-4 text-body text-red">
      Something went wrong. Try again.
    </p>
  );

  return (
    <main className="mx-auto w-full max-w-2xl px-4 py-10 md:px-6 md:py-16">
      <Card className="px-5 py-6 md:px-10 md:py-8">
        <NavLogo />
        <h1
          ref={headingRef}
          tabIndex={-1}
          className="mt-6 font-sans text-heading font-bold text-navy outline-none"
        >
          {heading}
        </h1>

        {stage === "bad" && (
          <p className="mt-2.5 max-w-prose-measure text-body text-ink">
            Write to{" "}
            <a href={`mailto:${CONTACT_ADDRESS}`} className={PROSE_LINK_CLASS}>
              {CONTACT_ADDRESS}
            </a>{" "}
            and we will unsubscribe you.
          </p>
        )}

        {(stage === "arrive" || stage === "unsubscribed") && (
          <p className="mt-2.5 max-w-prose-measure text-body text-ink">{SERVICE_EMAIL_LINE}</p>
        )}

        {stage === "arrive" && (
          <>
            {failure}
            <button
              ref={actionRef}
              type="button"
              className={cn(buttonVariants(), "mt-6")}
              disabled={busy}
              aria-busy={busy || undefined}
              onClick={() => void choose("unsubscribe")}
            >
              Unsubscribe
            </button>
          </>
        )}

        {stage === "unsubscribed" && (
          <>
            {failure}
            <p className="mt-3.5">
              <button
                ref={actionRef}
                type="button"
                className={cn(LINK_CLASS, "text-left text-body")}
                disabled={busy}
                aria-busy={busy || undefined}
                onClick={() => void choose("resubscribe")}
              >
                Changed your mind? Get product updates again
              </button>
            </p>
          </>
        )}
      </Card>
    </main>
  );
}
